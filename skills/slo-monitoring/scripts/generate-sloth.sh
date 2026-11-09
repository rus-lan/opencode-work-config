#!/usr/bin/env bash
# =============================================================================
# generate-sloth.sh
# -----------------------------------------------------------------------------
# Утилита клонирования / генерации / обновления SLO-мониторинга (sloth.yaml)
# для всех сервисов, описанных в services-slogen.yaml.
#
# Для каждого сервиса:
#   0. git clone <repo> ./apps/<company>/<name> (или pull существующего);
#   1. переключение на master + git pull; создание уникальной ветки
#      feature/sloth-<дата-время> (уникальная дата => нет пересечений веток);
#   2. slokit generate   -> configs/slo-kit.yaml;
#   3. slo-kit generate  -> configs/slo.yaml, configs/alerts.yaml;
#   4. slo-kit generate sloth -> configs/sloth.yaml;
#   5. slo-kit lint      -> валидация (exit 0 = ок);
#   6. копирует configs/sloth.yaml в helm-репозиторий компании.
#
# Helm-репозиторий клонируется с git.ecom.tech/ecom/cicd/<company>/helm в
# ./helm/<company>. Компания (company) задаётся в каждом сервисе файла
# services-slogen.yaml (smkt|sbl|mm|kpr|ecomtech). В helm-репо переключается
# master + pull, затем уникальная ветка feature/sloth-<дата-время>.
#
# Клонирование в ./apps/ генерирует УНИКАЛЬНЫЕ каталоги: базово имя из поля
# name, при коллизии — суффикс -2, -3 … чтобы клонирование не падало.
#
# Асинхронный запуск: каждый сервис в фоновом процессе, --jobs ограничивает
# максимум одновременных процессов.
#
# Использование:
#   ./generate-sloth.sh                 # все сервисы, -j 4
#   ./generate-sloth.sh --jobs 2        # максимум 2 параллельно
#   ./generate-sloth.sh <service>       # только один сервис (имя из name)
#   ./generate-sloth.sh --skip-git      # не трогать git (ветки/клоны-обновления)
#   ./generate-sloth.sh --no-clone      # не клонировать/обновлять, использовать ./apps/*
#
# Требования:
#   - бинарники slokit и slo-kit на PATH (или SLOTKIT_BIN/SLOKIT_BIN)
#   - services-slogen.yaml рядом со скриптом
#   - git-доступ к репозиториям сервисов и helm-репо компаний
# =============================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES_MD="$SCRIPT_DIR/services-slogen.yaml"   # источник правды (YAML)
PARSE_PY="$SCRIPT_DIR/sloth-parse.py"            # Python-yaml парсер
APPS_ROOT="$SCRIPT_DIR/apps"                     # клоны репозиториев сервисов
HELM_ROOT="$SCRIPT_DIR/helm"                     # корень helm-репо компаний
LOG_DIR="$SCRIPT_DIR/.sloth-logs"

SLOTKIT_BIN="${SLOTKIT_BIN:-slokit}"
SLOKIT_BIN="${SLOKIT_BIN:-slo-kit}"

JOBS=4
ONLY_SERVICE=""
SKIP_GIT=0
NO_CLONE=0

usage() {
  sed -n '2,35p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jobs)      JOBS="$2"; shift 2 ;;
    --help|-h)   usage ;;
    --skip-git)  SKIP_GIT=1; shift ;;
    --no-clone)  NO_CLONE=1; shift ;;
    -*) echo "Неизвестный флаг: $1" >&2; usage ;;
    *) ONLY_SERVICE="$1"; shift ;;
  esac
done

[[ -f "$SERVICES_MD" ]] || { echo "Нет services-slogen.yaml рядом со скриптом ($SERVICES_MD)" >&2; exit 2; }

mkdir -p "$APPS_ROOT" "$LOG_DIR"

# Уникальная дата для веток: feature/sloth-<YYYYmmdd-HHMMSS>.
GEN_TS="$(date +%Y%m%d-%H%M%S)"
FEATURE_BRANCH="feature/sloth-$GEN_TS"
echo "Уникальная ветка запуска: $FEATURE_BRANCH"

# Сопоставление профилей: slokit записывает профиль 1-в-1, но текущий slo-kit
# не принимает некоторые значения. Известные rejected-профили нормализуем.
declare -A PROFILE_MAP=(
  ["ecom-go-legacy"]="ecomtech-letsgo"
)

# ----------------------------------------------------------------------------
# Разбор services-slogen.yaml через sloth-parse.py.
# Вывод: <name>\t<ns>\t<company>\t<repo>\t<profile>\t<team>\t<cc>\t<helm_list>
# ----------------------------------------------------------------------------
parse_services() {
  python3 "$PARSE_PY" "$SERVICES_MD"
}

sanitize() { echo "$1" | sed -E 's/[^A-Za-z0-9._-]+/-/g'; }

# Переключить репозиторий на master + pull, затем создать уникальную ветку.
# $1 = путь к репо
sync_branch() {
  local repo_dir="$1" pull_out=""
  if [[ $SKIP_GIT -eq 1 ]]; then return 0; fi
  if ! git -C "$repo_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "  [SKIP] не git-репозиторий: $repo_dir"; return 0
  fi
  # всегда на master и актуальные данные
  git -C "$repo_dir" checkout master >/dev/null 2>&1 || git -C "$repo_dir" checkout main >/dev/null 2>&1 || true
  git -C "$repo_dir" reset --hard HEAD >/dev/null 2>&1 || true
  pull_out="$(git -C "$repo_dir" pull --ff-only 2>&1)" || {
    echo "  [WARN] git pull: $(printf '%s\n' "$pull_out" | tail -1)"
  }
  # уникальная ветка feature/sloth-<ts>: создать, либо (если существует) пересоздать
  if git -C "$repo_dir" rev-parse --verify -q "$FEATURE_BRANCH" >/dev/null 2>&1; then
    git -C "$repo_dir" branch -D "$FEATURE_BRANCH" >/dev/null 2>&1 || true
  fi
  git -C "$repo_dir" checkout -b "$FEATURE_BRANCH" >/dev/null 2>&1 && echo "  на ветке $FEATURE_BRANCH"
  return 0
}

# ----------------------------------------------------------------------------
# Сборка списка сервисов + уникальных каталогов ./apps/<company>/<name>.
# Репозитории сервисов разделяются по company (как helm/<company>), чтобы
# гарантировать уникальность каталогов даже при совпадении имён у сервисов
# разных компаний.
# ----------------------------------------------------------------------------
mapfile -t SERVICES < <(parse_services)
(( ${#SERVICES[@]} )) || { echo "Нет сервисов в services-slogen.yaml (пустой список services)" >&2; exit 4; }

declare -A USED_NAMES=()
declare -A APP_DIR_FOR=()     # name -> app_dir
declare -A COMPANIES=()       # множество компаний

for spec in "${SERVICES[@]}"; do
  IFS=$'\t' read -r name ns company repo profile team cc helm_cell <<< "$spec"
  # каталог: ./apps/<company>/<name>
  base="$(sanitize "$name")"
  comp_dir="$(sanitize "${company:-default}")"
  dir="$APPS_ROOT/$comp_dir/$base"
  n=2
  while [[ -n "${USED_NAMES[$dir]:-}" ]]; do
    dir="$APPS_ROOT/$comp_dir/${base}-${n}"; n=$((n+1))
  done
  USED_NAMES["$dir"]=1
  APP_DIR_FOR["$name"]="$dir"
  [[ -n "$company" ]] && COMPANIES["$company"]=1
done

# ----------------------------------------------------------------------------
# Клонирование / обновление helm-репо компаний (последовательно).
# Каждая компания -> helm/<company>. Всегда master + pull + unique branch.
# ----------------------------------------------------------------------------
declare -A HELM_DIR_FOR=()    # company -> helm_dir

if [[ $SKIP_GIT -eq 0 ]]; then
  for company in "${!COMPANIES[@]}"; do
    [[ -z "$company" ]] && continue
    helm_dir="$HELM_ROOT/$company"
    helm_url="https://git.ecom.tech/ecom/cicd/$company/helm"
    if [[ $NO_CLONE -eq 0 ]]; then
      if [[ ! -d "$helm_dir/.git" ]]; then
        echo "[helm:$company] клонирую $helm_url -> $helm_dir"
        git clone "$helm_url" "$helm_dir" >/dev/null 2>&1 || { echo "  [FAIL] clone helm $company"; continue; }
        echo "  OK: helm/$company клонирован"
      else
        echo "[helm:$company] обновляю (master + pull)"
        git -C "$helm_dir" checkout master >/dev/null 2>&1 || git -C "$helm_dir" checkout main >/dev/null 2>&1 || true
        git -C "$helm_dir" pull --ff-only >/dev/null 2>&1 || echo "  [WARN] pull helm/$company"
      fi
    fi
    sync_branch "$helm_dir"
    HELM_DIR_FOR["$company"]="$helm_dir"
  done
fi

# ----------------------------------------------------------------------------
# Один сервис.
# $1=name $2=ns $3=company $4=repo $5=app_dir $6=profile $7=team $8=cc $9=helm_cell
# ----------------------------------------------------------------------------
service_job() {
  local name="$1" ns="$2" company="$3" repo="$4" app_dir="$5" profile="$6" team="$7" cc="$8" helm_cell="$9"
  local status=0 h dst helm_dir
  local logf="$LOG_DIR/$name.log"
  local helm_list=()
  IFS='|' read -r -a helm_list <<< "$helm_cell"

  helm_dir="${HELM_DIR_FOR[$company]:-$HELM_ROOT/$company}"

  {
    echo "==== СЕРВИС: $name (ИС=$ns, company=$company, profile=$profile, team=$team, cc=$cc) ===="
    echo "Repo:     $repo"
    echo "App dir:  $app_dir"
    echo "Helm dir: $helm_dir"
    echo "Branch:   $FEATURE_BRANCH"

    # --- 0. клонирование / обновление репозитория сервиса ---
    if [[ $NO_CLONE -eq 0 ]]; then
      if [[ ! -d "$app_dir/.git" ]]; then
        echo "--- clone ---"
        if git clone "$repo" "$app_dir" 2>&1; then
          echo "  OK: клонирован в $app_dir"
        else
          echo "  [FAIL] git clone $repo"; return 1
        fi
      else
        echo "--- уже существует, обновляю (master + pull) ---"
        git -C "$app_dir" checkout master >/dev/null 2>&1 || git -C "$app_dir" checkout main >/dev/null 2>&1 || true
        git -C "$app_dir" pull --ff-only 2>&1 | tail -3 || echo "  [WARN] pull"
      fi
    else
      [[ -d "$app_dir" ]] || { echo "  [FAIL] --no-clone, но нет каталога: $app_dir"; return 1; }
    fi

    # --- ветка: master + pull + unique branch ---
    sync_branch "$app_dir"

    cd "$app_dir" || { echo "  ОШИБКА cd"; return 1; }

    # --- 1. slokit generate (блок информации сервиса) ---
    local eff_profile="$profile"
    [[ -n "${PROFILE_MAP[$profile]:-}" ]] && eff_profile="${PROFILE_MAP[$profile]}" && \
      echo "  [MAP] профиль $profile -> $eff_profile (ограничение slo-kit)"
    echo "--- slokit generate ---"
    if [[ -n "$eff_profile" ]]; then
      "$SLOTKIT_BIN" generate --profile "$eff_profile" --namespace "$ns" --team "$team" --cost-centre "$cc" "$app_dir" 2>&1 | tail -5 || status=1
    else
      "$SLOTKIT_BIN" generate --namespace "$ns" --team "$team" --cost-centre "$cc" "$app_dir" 2>&1 | tail -5 || status=1
    fi
    if [[ ! -f configs/slo-kit.yaml ]]; then
      echo "  [FAIL] configs/slo-kit.yaml не создан"; status=1
    fi

    # --- 1b. Нормализация slo-kit.yaml под ограничения текущего slo-kit.
    # slokit может сгенерировать правило oif/outgoing для letsgo, которое
    # slo-kit v26.10.1 отклоняет; преобразуем в поддерживаемые custom + custom_latency.
    if [[ -f configs/slo-kit.yaml ]] && [[ -f "$SCRIPT_DIR/sloth-normalize.py" ]]; then
      echo "--- нормализация slo-kit.yaml (letsgo rule types) ---"
      python3 "$SCRIPT_DIR/sloth-normalize.py" configs/slo-kit.yaml
    fi

    # --- 2. slo-kit generate paas ---
    echo "--- slo-kit generate (slo.yaml + alerts.yaml) ---"
    "$SLOKIT_BIN" generate --in configs/slo-kit.yaml --out configs/slo.yaml --alerts configs/alerts.yaml 2>&1 | tail -8 || status=1

    # --- 3. slo-kit generate sloth (sloth.yaml) ---
    echo "--- slo-kit generate sloth ---"
    "$SLOKIT_BIN" generate sloth --in configs/slo-kit.yaml --output-dir configs/ 2>&1 | tail -8 || status=1
    if [[ ! -f configs/sloth.yaml ]]; then
      echo "  [FAIL] configs/sloth.yaml не создан"; status=1
    fi

    # --- 4. lint ---
    echo "--- slo-kit lint ---"
    "$SLOKIT_BIN" lint --spath="$app_dir" 2>&1 | tail -8
    local lint_rc=$?
    if [[ $lint_rc -ne 0 ]]; then echo "  [WARN] lint exit=$lint_rc (см. выше)"; fi

    # --- 5. копирование в helm-репо компании ---
    echo "--- копирование sloth.yaml в helm ($helm_dir) ---"
    for h in "${helm_list[@]}"; do
      [[ -z "$h" ]] && continue
      h="${h#./}"
      if [[ "$h" = /* ]]; then dst="$h"; else dst="$helm_dir/$h"; fi
      mkdir -p "$(dirname "$dst")"
      if cp configs/sloth.yaml "$dst/sloth.yaml"; then
        echo "  OK -> $dst/sloth.yaml"
      else
        echo "  [FAIL] копирование в $dst"; status=1
      fi
    done

    if [[ $status -eq 0 ]]; then echo "РЕЗУЛЬТАТ: OK"; else echo "РЕЗУЛЬТАТ: ЧАСТИЧНО/ОШИБКИ"; fi
  } > "$logf" 2>&1

  echo "[$name] $(grep -E 'РЕЗУЛЬТАТ|lint exit|клонирован|pull|OK ->|на ветке' "$logf" | tr '\n' ' ')"
  return $status
}

# ----------------------------------------------------------------------------
# Запуск (асинхронная очередь).
# ----------------------------------------------------------------------------
JOBS=$(( JOBS >= 1 ? JOBS : 1 ))
running=0
pids=()

for spec in "${SERVICES[@]}"; do
  IFS=$'\t' read -r name ns company repo profile team cc helm_cell <<< "$spec"
  if [[ -n "$ONLY_SERVICE" && "$name" != "$ONLY_SERVICE" ]]; then continue; fi
  app_dir="${APP_DIR_FOR[$name]}"

  while (( running >= JOBS )); do
    for i in "${!pids[@]}"; do
      if ! kill -0 "${pids[$i]}" 2>/dev/null; then
        wait "${pids[$i]}"; unset 'pids[$i]'; ((running--))
      fi
    done
    sleep 0.2
  done

  service_job "$name" "$ns" "$company" "$repo" "$app_dir" "$profile" "$team" "$cc" "$helm_cell" &
  pids+=($!); ((running++))
done

for p in "${pids[@]:-}"; do
  [[ -n "$p" ]] && wait "$p" 2>/dev/null
done

echo
echo "===== Завершено (ветка $FEATURE_BRANCH). Логи: $LOG_DIR/*.log ====="
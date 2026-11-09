#!/usr/bin/env sh
# Установщик slo-monitoring.
#
# Работает в двух режимах, определяемых автоматически по тому, как скрипт
# запущен:
#
#   ЛОКАЛЬНЫЙ — запущен как ./install.sh (или sh install.sh) внутри каталога
#               компонента: ставит прямо из текущего каталога, без сети.
#   УДАЛЁННЫЙ — запущен через `curl ... | sh` без компонента рядом: сам
#               install.sh скачивается из ветки `main` приватного проекта через
#               GitLab raw API, затем скачивает архив соответствующего релиза с
#               GitLab, проверяет его sha256 и ставит из него.
#
# Usage:
#   curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
#     "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fslo-monitoring%2Finstall.sh/raw?ref=main" \
#     | SLOTH_TOKEN="$GITLAB_TOKEN" sh
#   ИЛИ, внутри каталога компонента:
#   ./install.sh
#
# Оба режима кладут скилл в ~/.config/opencode/skills/slo-monitoring/
# (каталог скиллов opencode), opencode-команду /sloth в
# ~/.config/opencode/commands/sloth.md и команды-лаунчеры sloth и sloth-bot
# в ~/.local/bin/.
#
# Переменные окружения:
#   INSTALL_DIR                 Каталог для команд sloth/sloth-bot -- действует
#                                и в локальном, и в удалённом режиме
#                                (по умолчанию: $HOME/.local/bin)
#
#   Только в удалённом режиме (на локальную установку из клона не влияют):
#   SLOTH_VERSION               Поставить конкретную версию вместо latest,
#                                например: SLOTH_VERSION=1.0.0 sh install.sh
#   SLOTH_TOKEN                 Personal Access Token GitLab для доступа к
#                                приватному проекту. Приоритет над GITLAB_TOKEN.
#                                Сылается как заголовок PRIVATE-TOKEN на все
#                                запросы к GitLab API (поиск тега, скачивание
#                                архива и checksum). Пустое значение/не задан --
#                                без заголовка, подходит для публично читаемого
#                                проекта.
#   GITLAB_TOKEN                Глобальный PAT GitLab (из окружения пользователя).
#                                Используется, если SLOTH_TOKEN не задан.
#   SLOTH_HOST                  Хост GitLab, по умолчанию https://git.ecom.tech.
#                                Например: SLOTH_HOST=https://gitlab.example.com
#   SLOTH_SKIP_CHECKSUM         1, чтобы пропустить проверку sha256, если её
#                                в принципе нельзя выполнить (нет sha256sum/
#                                shasum, не скачался checksums-sha256.txt).
#                                Настоящее несовпадение checksum всегда
#                                фатально, этот флаг его не обходит.
#
# Флаги: --uninstall   удалить skill, opencode-команду /sloth и команды
#                       sloth/sloth-bot, поставленные этим скриптом
#        --force       перезаписать команды sloth/sloth-bot и sloth.md в целях
#                       назначения, даже если там уже лежит чужой файл (без
#                       этого флага install.sh отказывается перезаписывать
#                       файл, который поставил не он)
#        -h, --help    показать эту справку
#
# Написан на POSIX sh (без bash-измов) -- скрипт пайпится в `sh` при
# удалённой установке и должен работать под sh/dash/bash/zsh одинаково.

set -eu

SKILL_NAME="slo-monitoring"
GITLAB_HOST="${SLOTH_HOST:-https://git.ecom.tech}"
GITLAB_PROJECT="ecom/dev/common/personal/e001-ai-hub"
GITLAB_PROJECT_ENC="ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub"
# Теги GitLab глобально уникальны в репозитории, поэтому этот компонент
# использует свой префикс тега <category>/<id> = skills/slo-monitoring, а его
# версии лежат в тегах skills/slo-monitoring/vX.Y.Z. "latest" резолвится НЕ через
# permalink/latest (он отдаёт последний релиз ВСЕГО репозитория и с несколькими
# компонентами неверен), а фильтрацией списка релизов по этому префиксу.
COMPONENT_TAG_PREFIX="skills/slo-monitoring"
ASSET_TARBALL="slo-monitoring.tar.gz"
ASSET_CHECKSUMS="checksums-sha256.txt"

SKILL_DEST="$HOME/.config/opencode/skills/$SKILL_NAME"
COMMANDS_DIR="$HOME/.config/opencode/commands"
COMMANDS_DEST="$COMMANDS_DIR/sloth.md"
COMMANDS_MARKER="# slo-monitoring:command -- installed by install.sh, safe to remove"
BIN_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
LAUNCHER_SLOTH="$BIN_DIR/sloth"
LAUNCHER_BOT="$BIN_DIR/sloth-bot"
LAUNCHER_MARKER_SLOTH="# slo-monitoring:sloth launcher -- installed by install.sh, safe to remove"
LAUNCHER_MARKER_BOT="# slo-monitoring:sloth-bot launcher -- installed by install.sh, safe to remove"
FORCE=0

# Обязательные файлы -- один и тот же список для локального клона и для
# распакованного архива релиза (см. scripts/release.sh, BUNDLE_ITEMS).
# install.sh включён, чтобы установленная копия была самостоятельной
# (можно переустановить/удалить прямо из ~/.config/opencode/skills/slo-monitoring/).
BUNDLE_ITEMS="SKILL.md README.md scripts VERSION install.sh examples"

err() { printf 'ошибка: %s\n' "$1" >&2; }
info() { printf '%s\n' "$1"; }

usage() {
  cat <<'EOF'
Использование:
  curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
    "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fslo-monitoring%2Finstall.sh/raw?ref=main" \
    | SLOTH_TOKEN="$GITLAB_TOKEN" sh
  ./install.sh                    (внутри каталога компонента -- ставит из текущего каталога)
  ./install.sh --uninstall
  ./install.sh -h|--help

Без флагов -- устанавливает или обновляет skill slo-monitoring:
  - копирует его в ~/.config/opencode/skills/slo-monitoring/
  - кладёт opencode-команду /sloth в ~/.config/opencode/commands/sloth.md
  - кладёт команды sloth и sloth-bot в ~/.local/bin/ (или $INSTALL_DIR)

  --uninstall   удалить skill, opencode-команду /sloth и команды sloth/sloth-bot,
                поставленные этим скриптом
  --force       перезаписать команды sloth/sloth-bot и sloth.md, даже если по
                этим путям уже лежат чужие файлы (без флага install.sh откажется)
  -h, --help    показать эту справку
EOF
}

# Определяет, откуда ставить, если это ЛОКАЛЬНЫЙ режим: печатает каталог
# компонента в stdout и возвращает 0. Возвращает 1 (без вывода), если это
# УДАЛЁННЫЙ режим -- в частности, `curl ... | sh` устанавливает $0 в "sh"
# (имя интерпретатора, а не путь к файлу), так что `[ -f "$0" ]` там всегда
# ложно.
detect_source_dir() {
  if [ -f "$0" ]; then
    candidate="$(cd "$(dirname "$0")" && pwd)"
    if [ -f "$candidate/SKILL.md" ] && [ -d "$candidate/scripts" ] \
        && [ -f "$candidate/scripts/generate-sloth.sh" ]; then
      printf '%s' "$candidate"
      return 0
    fi
  fi
  return 1
}

# Проверяет, что все обязательные файлы есть в $1 (каталог-источник -- либо
# корень компонента, либо распакованный архив релиза). $2 -- строка
# подсказки, печатается в конце сообщения об ошибке.
check_source() {
  src="$1"
  hint="$2"
  for item in $BUNDLE_ITEMS; do
    if [ ! -e "$src/$item" ]; then
      err "не найден $src/$item"
      [ -n "$hint" ] && echo "$hint" >&2
      exit 1
    fi
  done
}

# Копирует BUNDLE_ITEMS из $1 в SKILL_DEST.
install_skill() {
  src="$1"
  was_installed=0
  [ -d "$SKILL_DEST" ] && was_installed=1

  mkdir -p "$(dirname "$SKILL_DEST")"
  rm -rf "$SKILL_DEST"
  mkdir -p "$SKILL_DEST"
  for item in $BUNDLE_ITEMS; do
    cp -R "$src/$item" "$SKILL_DEST/$item"
  done
  find "$SKILL_DEST" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
  find "$SKILL_DEST" -type f -name '*.py[co]' -delete 2>/dev/null || true
  # scripts/release.sh is a build-time tool, not something the skill needs
  # at runtime -- drop it if present (local installs from a checkout have it).
  rm -f "$SKILL_DEST/scripts/release.sh"
  chmod +x "$SKILL_DEST"/scripts/*.sh 2>/dev/null || true
  chmod +x "$SKILL_DEST"/scripts/*.py 2>/dev/null || true

  if [ "$was_installed" = "1" ]; then
    info "skill обновлён в $SKILL_DEST"
  else
    info "skill установлен в $SKILL_DEST"
  fi
}

# Ставит один лаунчер. $1 = путь, $2 = маркер, $3 = команда запуска (bash + скрипт).
install_launcher_one() {
  launcher="$1"
  marker="$2"
  cmd="$3"

  mkdir -p "$BIN_DIR"

  # Refuse to clobber a file at $launcher that this script didn't create --
  # only a file already carrying our marker (a prior install of ours) is
  # safe to overwrite silently. Anything else needs an explicit --force.
  if [ -e "$launcher" ] && ! grep -qF "$marker" "$launcher" 2>/dev/null; then
    if [ "$FORCE" = "1" ]; then
      info "$launcher уже существует и не похож на файл, созданный install.sh -- перезаписываю (--force)"
    else
      err "$launcher уже существует и не похож на файл, созданный install.sh."
      echo "  install.sh не перезаписывает чужие файлы без --force." >&2
      echo "  переместите или удалите $launcher вручную, либо запустите: install.sh --force" >&2
      exit 1
    fi
  fi

  cat > "$launcher" <<EOF
#!/usr/bin/env bash
$marker
exec bash "$cmd" "\$@"
EOF
  chmod +x "$launcher"
  info "команда $(basename "$launcher") установлена в $launcher"
}

install_launchers() {
  # sloth -> generate-sloth.sh, sloth-bot -> sloth-bot.sh (только если этих имён нет).
  install_launcher_one "$LAUNCHER_SLOTH" "$LAUNCHER_MARKER_SLOTH" "$SKILL_DEST/scripts/generate-sloth.sh"
  install_launcher_one "$LAUNCHER_BOT" "$LAUNCHER_MARKER_BOT" "$SKILL_DEST/scripts/sloth-bot.sh"
}

# Ставит opencode-команду /sloth: копирует scripts/sloth.md в
# ~/.config/opencode/commands/sloth.md и добавляет в КОНЕЦ файла
# маркер-комментарий, чтобы install.sh мог позже отличить «наш» файл от чужого.
#
# Маркер обязан идти ПОСЛЕ frontmatter (после закрывающего '---'): opencode
# парсит команды через gray-matter, который требует, чтобы файл начинался
# строго со строки '---'. Если бы маркер стоял ПЕРЕД frontmatter, gray-matter
# не разобрал бы frontmatter, и поля `agent: build` / `subtask: true` /
# `description` потерялись бы. Детекция установки (grep -qF "$COMMANDS_MARKER")
# от позиции не зависит, поэтому uninstall/переустановка продолжают работать.
#
# Наш файл всегда перезаписывается; чужой (без маркера) -- только с --force.
install_sloth_command() {
  src_md="$1"
  [ -f "$src_md" ] || { err "не найден $src_md"; exit 1; }

  mkdir -p "$COMMANDS_DIR"

  if [ -e "$COMMANDS_DEST" ] && ! grep -qF "$COMMANDS_MARKER" "$COMMANDS_DEST" 2>/dev/null; then
    if [ "$FORCE" = "1" ]; then
      info "$COMMANDS_DEST уже существует и не похож на файл, созданный install.sh -- перезаписываю (--force)"
    else
      err "$COMMANDS_DEST уже существует и не похож на файл, созданный install.sh."
      echo "  install.sh не перезаписывает чужие файлы без --force." >&2
      echo "  переместите или удалите $COMMANDS_DEST вручную, либо запустите: install.sh --force" >&2
      exit 1
    fi
  fi

  # Весь src_md (начинается с '---') пишется как есть, маркер -- в самый конец,
  # уже ПОСЛЕ закрывающего frontmatter.
  cat "$src_md" > "$COMMANDS_DEST"
  printf '\n<!-- %s -->\n' "$COMMANDS_MARKER" >> "$COMMANDS_DEST"
  info "команда sloth установлена в $COMMANDS_DEST"
}

check_path() {
  case ":$PATH:" in
    *":$BIN_DIR:"*) return 0 ;;
  esac

  shell_name="$(basename "${SHELL:-}")"
  case "$shell_name" in
    zsh) rc_file="$HOME/.zshrc" ;;
    bash) rc_file="$HOME/.bashrc" ;;
    *) rc_file="" ;;
  esac

  echo ""
  echo "$BIN_DIR ещё не в PATH -- команды sloth / sloth-bot сами не найдутся."
  if [ -n "$rc_file" ]; then
    echo "Добавьте эту строку в $rc_file, затем откройте новый терминал (или выполните: . $rc_file):"
  else
    echo "Добавьте эту строку в rc-файл вашей оболочки (~/.bashrc, ~/.zshrc и т.п.), затем откройте новый терминал:"
  fi
  echo "  export PATH=\"$BIN_DIR:\$PATH\""
}

# --- удалённый режим: скачать релиз с GitLab, проверить checksum, поставить ---

# Проверяет $1 (скачанный файл) против sha256 из checksums-sha256.txt,
# который лежит рядом с ним по адресу $3/checksums-sha256.txt. $2 -- имя
# файла, под которым он должен встречаться в checksums-sha256.txt.
# Несовпадение checksum всегда фатально. Три случая, когда проверку в
# принципе нельзя выполнить (нет sha256sum/shasum, не скачался
# checksums-sha256.txt, в нём нет строки для этого файла), можно понизить
# до предупреждения через SLOTH_SKIP_CHECKSUM=1.
verify_checksum() {
  file="$1"
  asset="$2"
  base_url="$3"

  sha_cmd=""
  if command -v sha256sum >/dev/null 2>&1; then
    sha_cmd="sha256sum"
  elif command -v shasum >/dev/null 2>&1; then
    sha_cmd="shasum -a 256"
  fi

  if [ -z "$sha_cmd" ]; then
    if [ "${SLOTH_SKIP_CHECKSUM:-}" = "1" ]; then
      echo "slo-monitoring: ПРЕДУПРЕЖДЕНИЕ: нет ни sha256sum, ни shasum -- пропускаю проверку целостности." >&2
      return 0
    fi
    err "нет ни sha256sum, ни shasum -- не могу проверить скачанный файл."
    echo "  установите SLOTH_SKIP_CHECKSUM=1, чтобы поставить без проверки." >&2
    exit 1
  fi

  checksums_url="${base_url}/${ASSET_CHECKSUMS}"
  tmp_checksums=$(mktemp "${TMPDIR:-/tmp}/slo-monitoring-sha.XXXXXX")
  if ! curl -fsSL $CURL_AUTH_ARGS -o "$tmp_checksums" "$checksums_url"; then
    rm -f "$tmp_checksums"
    if [ "${SLOTH_SKIP_CHECKSUM:-}" = "1" ]; then
      echo "slo-monitoring: ПРЕДУПРЕЖДЕНИЕ: не удалось скачать $ASSET_CHECKSUMS -- пропускаю проверку целостности." >&2
      return 0
    fi
    err "не удалось скачать $ASSET_CHECKSUMS -- не могу проверить скачанный файл."
    echo "  установите SLOTH_SKIP_CHECKSUM=1, чтобы поставить без проверки." >&2
    exit 1
  fi

  expected=$(grep -E "  ${asset}\$" "$tmp_checksums" | awk '{print $1}' | head -1)
  rm -f "$tmp_checksums"
  if [ -z "$expected" ]; then
    if [ "${SLOTH_SKIP_CHECKSUM:-}" = "1" ]; then
      echo "slo-monitoring: ПРЕДУПРЕЖДЕНИЕ: нет записи checksum для '$asset' -- пропускаю проверку целостности." >&2
      return 0
    fi
    err "нет записи checksum для '$asset' в $ASSET_CHECKSUMS -- не могу проверить скачанный файл."
    echo "  установите SLOTH_SKIP_CHECKSUM=1, чтобы поставить без проверки." >&2
    exit 1
  fi

  actual=$($sha_cmd "$file" | awk '{print $1}')
  if [ "$expected" != "$actual" ]; then
    err "несовпадение checksum для $asset -- установка прервана."
    echo "  ожидалось: $expected" >&2
    echo "  получено:  $actual" >&2
    exit 1
  fi
  info "checksum проверен ($asset)."
}

# "latest" резолвится в один конкретный тег фильтрацией списка релизов по
# префиксу тега этого компонента (COMPONENT_TAG_PREFIX), а дальше архив и его
# checksum скачиваются из этого же <version>-пути Generic Package Registry.
run_remote_install() {
  info "slo-monitoring: удалённая установка -- ищу релиз на GitLab..."

  api_base="$GITLAB_HOST/api/v4/projects/$GITLAB_PROJECT_ENC"

  # Токен для доступа к приватному проекту. Приоритет: SLOTH_TOKEN >
  # GITLAB_TOKEN (глобальный PAT). Оба пустые/не заданы -- без заголовка
  # (подходит для публично читаемого проекта).
  TOKEN_VAL="${SLOTH_TOKEN:-${GITLAB_TOKEN:-}}"
  CURL_AUTH_ARGS=""
  [ -n "$TOKEN_VAL" ] && CURL_AUTH_ARGS="-H PRIVATE-TOKEN:$TOKEN_VAL"

  if [ -n "${SLOTH_VERSION:-}" ]; then
    resolved_tag="v${SLOTH_VERSION#v}"
    version="${resolved_tag#v}"
    info "slo-monitoring: ставлю зафиксированную версию ${resolved_tag}..."
  else
    # "latest" для ЭТОГО компонента резолвится фильтрацией списка релизов по
    # его префиксу тега (COMPONENT_TAG_PREFIX = skills/slo-monitoring).
    releases_json=$(curl -fsSL $CURL_AUTH_ARGS "$api_base/releases?per_page=100&sort=desc&order_by=released_at")
    resolved_tag=$(printf '%s' "$releases_json" \
      | grep -o '"tag_name":"[^"]*"' \
      | sed 's/.*"tag_name":"//; s/"$//' \
      | grep "^${COMPONENT_TAG_PREFIX}/" \
      | head -1)
    [ -n "$resolved_tag" ] || resolved_tag=""
    if [ -z "${resolved_tag:-}" ]; then
      err "не удалось найти последний релиз компонента $SKILL_NAME."
      echo "  проверьте доступ к проекту (приватный проект требует GITLAB_TOKEN или SLOTH_TOKEN) и что" >&2
      echo "  релизы с префиксом тега '$COMPONENT_TAG_PREFIX/' уже созданы:" >&2
      echo "  $GITLAB_HOST/$GITLAB_PROJECT/-/releases" >&2
      exit 1
    fi
    version="${resolved_tag#${COMPONENT_TAG_PREFIX}/v}"
    info "slo-monitoring: последний релиз -- ${resolved_tag}."
  fi

  base_url="$GITLAB_HOST/api/v4/projects/$GITLAB_PROJECT_ENC/packages/generic/slo-monitoring/${version}"

  work_dir=$(mktemp -d "${TMPDIR:-/tmp}/slo-monitoring-install.XXXXXX")
  cleanup() { rm -rf "$work_dir" 2>/dev/null; }
  trap cleanup EXIT
  trap 'cleanup; exit 129' HUP
  trap 'cleanup; exit 130' INT
  trap 'cleanup; exit 131' QUIT
  trap 'cleanup; exit 143' TERM

  download_url="${base_url}/${ASSET_TARBALL}"
  tmp_file=$(mktemp "$work_dir/.dl.XXXXXX")
  info "slo-monitoring: скачиваю ${ASSET_TARBALL}..."
  if ! curl -fsSL $CURL_AUTH_ARGS -o "$tmp_file" "$download_url"; then
    err "не удалось скачать $ASSET_TARBALL с $download_url"
    if [ -n "${SLOTH_VERSION:-}" ]; then
      echo "  проверьте, что релиз ${resolved_tag} существует и содержит этот файл:" >&2
      echo "  $GITLAB_HOST/$GITLAB_PROJECT/-/releases/${resolved_tag}" >&2
    else
      echo "  проверьте доступ к проекту (приватный проект требует GITLAB_TOKEN или SLOTH_TOKEN) или список релизов" >&2
      echo "  этого компонента (префикс тега '$COMPONENT_TAG_PREFIX/'):" >&2
      echo "  $GITLAB_HOST/$GITLAB_PROJECT/-/releases" >&2
    fi
    exit 1
  fi

  verify_checksum "$tmp_file" "$ASSET_TARBALL" "$base_url"

  tarball="$work_dir/$ASSET_TARBALL"
  mv "$tmp_file" "$tarball"

  extract_dir="$work_dir/extracted"
  mkdir -p "$extract_dir"
  tar xzf "$tarball" -C "$extract_dir"

  src_dir="$extract_dir/$SKILL_NAME"
  if [ ! -d "$src_dir" ]; then
    err "архив релиза распакован, но каталог $SKILL_NAME внутри него не найден -- повреждённый или несовместимый релиз."
    exit 1
  fi

  check_source "$src_dir" "Архив релиза повреждён или несовместим -- попробуйте переустановить."
  install_skill "$src_dir"
  install_launchers
  install_sloth_command "$src_dir/scripts/sloth.md"
}

do_uninstall() {
  if [ -d "$SKILL_DEST" ]; then
    rm -rf "$SKILL_DEST"
    info "удалён $SKILL_DEST"
  else
    info "$SKILL_DEST не найден, пропускаю"
  fi

  for pair in \
    "$LAUNCHER_SLOTH|$LAUNCHER_MARKER_SLOTH" \
    "$LAUNCHER_BOT|$LAUNCHER_MARKER_BOT" \
  ; do
    launcher="${pair%%|*}"
    marker="${pair#*|}"
    if [ -f "$launcher" ] && grep -qF "$marker" "$launcher" 2>/dev/null; then
      rm -f "$launcher"
      info "удалён $launcher"
    elif [ -e "$launcher" ]; then
      info "$launcher существует, но не похож на файл, созданный install.sh -- оставляю как есть"
    else
      info "$launcher не найден, пропускаю"
    fi
  done

  # opencode-команда /sloth
  if [ -f "$COMMANDS_DEST" ] && grep -qF "$COMMANDS_MARKER" "$COMMANDS_DEST" 2>/dev/null; then
    rm -f "$COMMANDS_DEST"
    info "удалён $COMMANDS_DEST"
  elif [ -e "$COMMANDS_DEST" ]; then
    info "$COMMANDS_DEST существует, но не похож на файл, созданный install.sh -- оставляю как есть"
  else
    info "$COMMANDS_DEST не найден, пропускаю"
  fi

  exit 0
}

finish() {
  echo ""
  echo "Готово."
  check_path

  echo ""
  echo "Дальше выполните по порядку:"
  echo "  1. sloth-bot --check      # проверка окружения (git/python3+yaml/go/docker, бинарники)"
  echo "  2. bash \$HOME/.config/opencode/skills/slo-monitoring/scripts/install-tools.sh   # обновить slokit + slo-kit"
  echo "  3. sloth                  # сгенерировать / обновить SLO для всех сервисов"
}

main() {
  action=""
  for arg in "$@"; do
    case "$arg" in
      --uninstall) action="uninstall" ;;
      --force) FORCE=1 ;;
      -h|--help) usage; exit 0 ;;
      *)
        err "неизвестный флаг: $arg"
        usage
        exit 2
        ;;
    esac
  done

  if [ "$action" = "uninstall" ]; then
    do_uninstall
  fi

  if source_dir=$(detect_source_dir); then
    info "slo-monitoring: локальная установка из $source_dir"
    check_source "$source_dir" "Запускайте install.sh из каталога компонента slo-monitoring."
    install_skill "$source_dir"
    install_launchers
    install_sloth_command "$source_dir/scripts/sloth.md"
  else
    run_remote_install
  fi

  finish
}

main "$@"
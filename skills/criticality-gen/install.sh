#!/usr/bin/env sh
# Установщик скилла criticality-gen.
#
# Работает в двух режимах, определяемых автоматически по тому, как скрипт
# запущен:
#
#   ЛОКАЛЬНЫЙ — запущен как ./install.sh (или sh install.sh) внутри клона
#               репозитория: ставит прямо из текущего каталога, без сети.
#   УДАЛЁННЫЙ — запущен через `curl ... | sh` без репозитория рядом: сам
#               install.sh скачивается из ветки `main` приватного проекта
#               через GitLab raw API, затем скачивается архив соответствующего
#               релиза с GitLab, проверяется его sha256 и ставится из него.
#
# Куда ставится (два режима установки):
#
#   ГЛОБАЛЬНО (по умолчанию) — скилл в ~/.config/opencode/skills/criticality-gen/,
#     команда /criticality_gen в ~/.config/opencode/commands/criticality_gen.md;
#     с флагом --claude скилл дополнительно ставится в ~/.claude/skills/.
#
#   В ПРОЕКТ (--project <каталог>) — скилл в <каталог>/.opencode/skills/,
#     команда в <каталог>/.opencode/commands/, цели make в
#     <каталог>/.opencode/Makefile, фасад в <каталог>/Makefile и шаблон
#     <каталог>/is.example.yaml. Чужие файлы не перезаписываются.
#
# Usage:
#   curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
#     "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fcriticality-gen%2Finstall.sh/raw?ref=main" \
#     | CRITICALITY_TOKEN="$GITLAB_TOKEN" sh
#   ИЛИ, внутри клона репозитория:
#   ./install.sh
#   ./install.sh --project /путь/к/проекту
#
# Переменные окружения:
#   OPENCODE_SKILLS_DIR          Каталог скиллов opencode
#                                (по умолчанию: $HOME/.config/opencode/skills)
#   OPENCODE_COMMANDS_DIR        Каталог команд opencode
#                                (по умолчанию: $HOME/.config/opencode/commands)
#   CLAUDE_SKILLS_DIR            Каталог скиллов Claude
#                                (по умолчанию: $HOME/.claude/skills)
#
#   Только в удалённом режиме (на локальную установку из клона не влияют):
#   CRITICALITY_VERSION         Поставить конкретную версию вместо latest,
#                                например: CRITICALITY_VERSION=1.0.0 sh install.sh
#   CRITICALITY_TOKEN           Personal Access Token GitLab для доступа к
#                                приватному проекту. Приоритет над GITLAB_TOKEN.
#   GITLAB_TOKEN                Глобальный PAT GitLab (из окружения пользователя).
#                                Используется, если CRITICALITY_TOKEN не задан.
#   CRITICALITY_HOST            Хост GitLab, по умолчанию https://git.ecom.tech.
#   CRITICALITY_SKIP_CHECKSUM   1, чтобы пропустить проверку sha256, если её
#                                в принципе нельзя выполнить (нет sha256sum/
#                                shasum, не скачался checksums-sha256.txt).
#                                Настоящее несовпадение checksum всегда
#                                фатально, этот флаг его не обходит.
#
# Флаги: --project <dir> развернуть проект: скилл и команда в .opencode/,
#                        .opencode/Makefile, Makefile, is.example.yaml
#        --uninstall   удалить всё, что поставил этот скрипт (глобально или,
#                       с --project, только поставленное в этот проект)
#        --force       перезаписать существующий каталог/файл, даже если его
#                       поставил не этот скрипт (без флага — отказ)
#        --dry-run     показать, что будет сделано, ничего не писать
#        --claude      дополнительно установить скилл в ~/.claude/skills/
#        -h, --help    показать эту справку
#
# Написан на POSIX sh (без bash-измов) -- скрипт пайпится в `sh` при
# удалённой установке и должен работать под sh/dash/bash/zsh одинаково.

set -eu

SKILL_NAME="criticality-gen"
COMMAND_NAME="criticality_gen.md"
GITLAB_HOST="${CRITICALITY_HOST:-https://git.ecom.tech}"
GITLAB_PROJECT="ecom/dev/common/personal/e001-ai-hub"
GITLAB_PROJECT_ENC="ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub"
# Теги GitLab глобально уникальны в репозитории, поэтому этот компонент
# использует свой префикс тега <category>/<id> = skills/criticality-gen.
# "latest" резолвится фильтрацией списка релизов по этому префиксу.
COMPONENT_TAG_PREFIX="skills/criticality-gen"
ASSET_TARBALL="criticality-gen.tar.gz"
ASSET_CHECKSUMS="checksums-sha256.txt"

OPENCODE_SKILLS_DIR="${OPENCODE_SKILLS_DIR:-$HOME/.config/opencode/skills}"
OPENCODE_COMMANDS_DIR="${OPENCODE_COMMANDS_DIR:-$HOME/.config/opencode/commands}"
COMMANDS_DEST="$OPENCODE_COMMANDS_DIR/$COMMAND_NAME"
CLAUDE_SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

# Маркер установки: только каталог с этим маркером перезаписывается без
# --force и удаляется через --uninstall.
INSTALL_MARKER=".${SKILL_NAME}-installed"
# Маркер проектной установки (в проекте может быть свой .opencode с другими
# скиллами, поэтому признак «наш» хранится внутри каталога скилла).
PROJECT_MARKER=".${SKILL_NAME}-project"
# Маркер команды ставится в конец файла — уже ПОСЛЕ закрывающего `---`
# frontmatter, иначе gray-matter не разберёт команду.
COMMANDS_MARKER="# ${SKILL_NAME}:command -- installed by install.sh, safe to remove"

FORCE=0
DRY_RUN=0
WITH_CLAUDE=0
PROJECT_DIR=""

# Обязательные файлы -- один и тот же список для локального клона и для
# распакованного архива релиза (см. scripts/release.sh, BUNDLE_ITEMS).
# commands/ и project/ входят в бандл: установленная копия самодостаточна.
# install.sh тоже входит: `make selftest` проверяет его наличие и правила
# исключения мусора в самом каталоге скилла, а установленная копия остаётся
# самостоятельной (переустановка/удаление прямо из неё).
BUNDLE_ITEMS="SKILL.md README.md VERSION CHANGELOG.md criteria templates references docs scripts commands project install.sh"

err() { printf 'ошибка: %s\n' "$1" >&2; }
info() { printf '%s\n' "$1"; }
warn() { printf 'ВНИМАНИЕ: %s\n' "$1" >&2; }

usage() {
  cat <<'EOF'
Использование:
  curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
    "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fcriticality-gen%2Finstall.sh/raw?ref=main" \
    | CRITICALITY_TOKEN="$GITLAB_TOKEN" sh
  ./install.sh                    (внутри клона репозитория -- ставит из текущего каталога)
  ./install.sh --project /путь    (развернуть проект целиком)
  ./install.sh --dry-run          (показать действия, ничего не писать)
  ./install.sh --uninstall
  ./install.sh -h|--help

Без флагов -- устанавливает или обновляет skill criticality-gen:
  - копирует его в ~/.config/opencode/skills/criticality-gen/ (приоритет,
    opencode) и кладёт команду /criticality_gen в
    ~/.config/opencode/commands/criticality_gen.md;
    с --claude скилл ставится ещё и в ~/.claude/skills/criticality-gen/

  --project <dir>  развернуть проект для работы со скиллом:
                   <dir>/.opencode/skills/criticality-gen (копия),
                   <dir>/.opencode/commands/criticality_gen.md,
                   <dir>/.opencode/Makefile, <dir>/Makefile,
                   <dir>/is.example.yaml -- существующие чужие файлы
                   не перезаписываются; дальше: cd <dir> && make init
  --uninstall   удалить поставленное: из $HOME -- скилл и команду; с
                --project -- только то, что поставил этот скрипт в проект
  --force       перезаписать существующий каталог/файл, даже если его поставил
                не этот скрипт (без флага install.sh откажется)
  --dry-run     показать, что будет сделано, ничего не писать
  --claude      дополнительно поставить скилл в ~/.claude/skills/
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
    if [ -f "$candidate/SKILL.md" ] && [ -f "$candidate/VERSION" ]; then
      printf '%s' "$candidate"
      return 0
    fi
  fi
  return 1
}

# Проверяет, что все обязательные файлы есть в $1 (каталог-источник -- либо
# корень компонента в клоне, либо распакованный архив релиза). $2 -- строка
# подсказки.
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

# Копирует $1 в $2 один-в-один, без мусора локальных прогонов.
copy_item() {
  cp -R "$1" "$2"
  # Python-артефакты и служебные файлы ОС в поставку не входят: они появляются
  # от локальных запусков скрипта и ломают воспроизводимость бандла.
  rm -rf "$2/__pycache__" 2>/dev/null || true
  find "$2" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$2" -name '*.pyc' -type f -exec rm -f {} + 2>/dev/null || true
  find "$2" -name '.pytest_cache' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$2" -name '.DS_Store' -type f -exec rm -f {} + 2>/dev/null || true
}

# Безопасно ставит каталог скилла в $1 (целевой родительский каталог скиллов:
# ~/.config/opencode/skills или ~/.claude/skills). $2 -- маркер установки,
# $3 -- строка «что это за режим» для плана dry-run.
# Возвращает 0, если установка выполнена (или была бы выполнена при --dry-run).
install_skill_into() {
  dest_root="$1"
  marker="$2"
  label="$3"
  dest="$dest_root/$SKILL_NAME"

  # Источник и цель не должны совпадать: `rm -rf` цели уничтожил бы источник.
  if [ -d "$dest" ] && [ -d "$src" ]; then
    src_abs="$(cd "$src" && pwd)"
    dest_abs="$(cd "$dest" && pwd)"
    if [ "$src_abs" = "$dest_abs" ]; then
      err "источник и цель установки совпадают: $dest_abs"
      echo "  укажите другой каталог (--project <путь>) или уберите скилл из источника." >&2
      exit 1
    fi
  fi

  if [ -e "$dest" ] && [ ! -d "$dest" ]; then
    err "$dest существует и не является каталогом."
    exit 1
  fi
  if [ -d "$dest" ] && [ "$FORCE" != "1" ] \
     && [ ! -f "$dest/$marker" ] \
     && [ ! -f "$dest/$INSTALL_MARKER" ] \
     && [ ! -f "$dest/$PROJECT_MARKER" ]; then
    err "$dest уже существует и не похож на каталог, созданный install.sh."
    echo "  install.sh не перезаписывает чужие каталоги без --force." >&2
    echo "  переместите или удалите $dest вручную, либо запустите: install.sh --force" >&2
    exit 1
  fi

  if [ "$DRY_RUN" = "1" ]; then
    info "dry-run: установил бы скилл ($label) в $dest"
    info "dry-run:   из $src: $BUNDLE_ITEMS"
    return 0
  fi

  mkdir -p "$dest_root"
  rm -rf "$dest"
  mkdir -p "$dest"
  for item in $BUNDLE_ITEMS; do
    copy_item "$src/$item" "$dest/$item"
  done
  : > "$dest/$marker"
  info "skill $SKILL_NAME установлен в $dest"
}

# Ставит opencode-команду /criticality_gen из $1 (путь к .md внутри источника).
install_command() {
  src_md="$1"
  [ -f "$src_md" ] || { err "не найден $src_md"; exit 1; }

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

  if [ "$DRY_RUN" = "1" ]; then
    info "dry-run: установил бы команду в $COMMANDS_DEST"
    return 0
  fi

  mkdir -p "$OPENCODE_COMMANDS_DIR"
  # Весь src_md (начинается с '---') пишется как есть, маркер -- в самый конец,
  # уже ПОСЛЕ закрывающего frontmatter.
  cat "$src_md" > "$COMMANDS_DEST"
  printf '\n<!-- %s -->\n' "$COMMANDS_MARKER" >> "$COMMANDS_DEST"
  info "команда /criticality_gen установлена в $COMMANDS_DEST"
}

install_skill() {
  src="$1"
  install_skill_into "$OPENCODE_SKILLS_DIR" "$INSTALL_MARKER" "opencode"
  install_command "$src/commands/$COMMAND_NAME"
  if [ "$WITH_CLAUDE" = "1" ]; then
    install_skill_into "$CLAUDE_SKILLS_DIR" "$INSTALL_MARKER" "claude"
  fi
}

# --- проектная установка: скилл + команда + make-цели + шаблон is.example.yaml ---

# $1 -- исходный файл, $2 -- целевой путь, $3 -- чем является (для сообщений).
# Существующий файл, совпадающий с нашим, считается своим; чужой -- не
# перезаписывается (WARN, код 0): установка проекта продолжается.
install_project_file() {
  src_file="$1"
  dest_file="$2"
  what="$3"

  if [ -e "$dest_file" ]; then
    if cmp -s "$src_file" "$dest_file"; then
      info "$what уже установлен и совпадает: $dest_file"
      return 0
    fi
    if [ "$FORCE" = "1" ]; then
      if [ "$DRY_RUN" = "1" ]; then
        info "dry-run: перезаписал бы $what: $dest_file (--force)"
        return 0
      fi
      cp "$src_file" "$dest_file"
      info "$what перезаписан (--force): $dest_file"
      return 0
    fi
    warn "$dest_file уже существует и отличается от шаблона -- оставляю как есть."
    echo "  чтобы перезаписать: install.sh --project $PROJECT_DIR --force" >&2
    return 0
  fi

  if [ "$DRY_RUN" = "1" ]; then
    info "dry-run: положил бы $what: $dest_file"
    return 0
  fi
  mkdir -p "$(dirname "$dest_file")"
  cp "$src_file" "$dest_file"
  info "$what установлен: $dest_file"
}

install_project() {
  src="$1"
  dir="$PROJECT_DIR"
  p_skill="$dir/.opencode/skills/$SKILL_NAME"
  p_command="$dir/.opencode/commands/$COMMAND_NAME"

  if [ -e "$dir" ] && [ ! -d "$dir" ]; then
    err "$dir существует и не является каталогом."
    exit 1
  fi
  if [ -d "$p_skill" ] && [ "$FORCE" != "1" ] && [ ! -f "$p_skill/$PROJECT_MARKER" ] && [ ! -f "$p_skill/$INSTALL_MARKER" ]; then
    err "$p_skill уже существует и не похож на каталог, созданный install.sh."
    echo "  install.sh не перезаписывает чужие каталоги без --force." >&2
    echo "  переместите или удалите $p_skill вручную, либо запустите: install.sh --project $dir --force" >&2
    exit 1
  fi

  if [ "$DRY_RUN" = "1" ]; then
    info "dry-run: проектная установка в $dir"
    info "dry-run:   скилл   -> $p_skill"
    info "dry-run:   команда -> $p_command"
    info "dry-run:   make    -> $dir/.opencode/Makefile"
    info "dry-run:   фасад   -> $dir/Makefile"
    info "dry-run:   шаблон  -> $dir/is.example.yaml"
  else
    mkdir -p "$dir/.opencode/skills" "$dir/.opencode/commands"
  fi

  # Скилл кладём копией (симлинк не нужен: проект должен быть независим от
  # расположения источника).
  install_skill_into "$dir/.opencode/skills" "$PROJECT_MARKER" "project"

  # Команда -- в проектном каталоге команд, с тем же маркером в конце.
  src_md="$src/commands/$COMMAND_NAME"
  [ -f "$src_md" ] || { err "не найден $src_md"; exit 1; }
  if [ -e "$p_command" ] && ! grep -qF "$COMMANDS_MARKER" "$p_command" 2>/dev/null && [ "$FORCE" != "1" ]; then
    warn "$p_command уже существует и не похож на файл, созданный install.sh -- оставляю как есть."
    echo "  чтобы перезаписать: install.sh --project $dir --force" >&2
  elif [ "$DRY_RUN" = "1" ]; then
    info "dry-run: установил бы команду в $p_command"
  else
    cat "$src_md" > "$p_command"
    printf '\n<!-- %s -->\n' "$COMMANDS_MARKER" >> "$p_command"
    info "команда /criticality_gen установлена в $p_command"
  fi

  install_project_file "$src/project/Makefile" "$dir/.opencode/Makefile" "make-цели (.opencode/Makefile)"
  install_project_file "$src/project/facade.Makefile" "$dir/Makefile" "корневой Makefile-фасад"
  install_project_file "$src/project/is.example.yaml" "$dir/is.example.yaml" "шаблон is.example.yaml"

  echo ""
  info "Дальше:"
  info "  cd $dir && make init     # каркас: is.yaml, catalog.yaml, INDEX.md, is/, .gitignore"
  info "  cd $dir && make help     # все цели и текущее состояние ИС"
}

do_uninstall() {
  sweep_one() {
    dest_root="$1"
    marker="$2"
    dest="$dest_root/$SKILL_NAME"
    if [ -d "$dest" ] && [ -f "$dest/$marker" ]; then
      [ "$DRY_RUN" = "1" ] && { info "dry-run: удалил бы $dest"; return; }
      rm -rf "$dest"
      info "удалён $dest"
    elif [ -e "$dest" ]; then
      info "$dest существует, но не похож на установленный install.sh -- оставляю как есть"
    else
      info "$dest не найден, пропускаю"
    fi
  }

  remove_command() {
    dest_file="$1"
    if [ -f "$dest_file" ] && grep -qF "$COMMANDS_MARKER" "$dest_file" 2>/dev/null; then
      [ "$DRY_RUN" = "1" ] && { info "dry-run: удалил бы $dest_file"; return; }
      rm -f "$dest_file"
      info "удалён $dest_file"
    elif [ -e "$dest_file" ]; then
      info "$dest_file существует, но не похож на файл, созданный install.sh -- оставляю как есть"
    else
      info "$dest_file не найден, пропускаю"
    fi
  }

  # Удаляет файл, поставленный в проект, только если он совпадает с нашим
  # ($1 -- наш файл, $2 -- файл в проекте, $3 -- что это).
  remove_project_file() {
    src_file="$1"
    dest_file="$2"
    what="$3"
    if [ ! -e "$dest_file" ]; then
      info "$dest_file не найден, пропускаю"
      return 0
    fi
    if [ -f "$src_file" ] && cmp -s "$src_file" "$dest_file"; then
      [ "$DRY_RUN" = "1" ] && { info "dry-run: удалил бы $what: $dest_file"; return 0; }
      rm -f "$dest_file"
      info "удалён $what: $dest_file"
      return 0
    fi
    if [ ! -f "$src_file" ]; then
      info "$dest_file оставлен: нет исходника для сравнения"
      return 0
    fi
    info "$dest_file отличается от нашего шаблона -- оставляю как есть"
  }

  uninstall_project() {
    src="$1"
    dir="$PROJECT_DIR"
    info "проектная установка: $dir"
    sweep_one "$dir/.opencode/skills" "$PROJECT_MARKER"
    remove_command "$dir/.opencode/commands/$COMMAND_NAME"
    remove_project_file "$src/project/Makefile" "$dir/.opencode/Makefile" "make-цели (.opencode/Makefile)"
    remove_project_file "$src/project/facade.Makefile" "$dir/Makefile" "корневой Makefile-фасад"
    # is.example.yaml -- шаблон проекта: удаляем только если он не изменён.
    remove_project_file "$src/project/is.example.yaml" "$dir/is.example.yaml" "шаблон is.example.yaml"
  }

  if [ -n "$PROJECT_DIR" ]; then
    if [ -z "${UNINSTALL_SRC:-}" ]; then
      warn "нет исходника компонента: удалю скилл и команду по маркерам, а Makefile и шаблон оставлю (сравнить не с чем)."
      echo "  точное удаление: запустите install.sh --uninstall --project из клона репозитория." >&2
    fi
    uninstall_project "${UNINSTALL_SRC:-}"
    exit 0
  fi

  sweep_one "$OPENCODE_SKILLS_DIR" "$INSTALL_MARKER"
  remove_command "$COMMANDS_DEST"
  if [ "$WITH_CLAUDE" = "1" ] || [ -d "$CLAUDE_SKILLS_DIR/$SKILL_NAME" ]; then
    sweep_one "$CLAUDE_SKILLS_DIR" "$INSTALL_MARKER"
  fi
  exit 0
}

# --- удалённый режим: скачать релиз с GitLab, проверить checksum, поставить ---

# Проверяет $1 (скачанный файл) против sha256 из checksums-sha256.txt по $3.
# $2 -- имя файла, под которым он должен встречаться. Несовпадение checksum
# всегда фатально; невозможность проверки можно понизить до предупреждения
# через CRITICALITY_SKIP_CHECKSUM=1.
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
    if [ "${CRITICALITY_SKIP_CHECKSUM:-}" = "1" ]; then
      echo "criticality-gen: ПРЕДУПРЕЖДЕНИЕ: нет ни sha256sum, ни shasum -- пропускаю проверку целостности." >&2
      return 0
    fi
    err "нет ни sha256sum, ни shasum -- не могу проверить скачанный файл."
    echo "  установите CRITICALITY_SKIP_CHECKSUM=1, чтобы поставить без проверки." >&2
    exit 1
  fi

  checksums_url="${base_url}/${ASSET_CHECKSUMS}"
  tmp_checksums=$(mktemp "${TMPDIR:-/tmp}/criticality-gen-sha.XXXXXX")
  # CURL_AUTH_ARGS намеренно не в кавычках: это набор слов "-H PRIVATE-TOKEN:..."
  # либо пустая строка; word splitting здесь и есть нужное поведение.
  if ! curl -fsSL $CURL_AUTH_ARGS -o "$tmp_checksums" "$checksums_url"; then
    rm -f "$tmp_checksums"
    if [ "${CRITICALITY_SKIP_CHECKSUM:-}" = "1" ]; then
      echo "criticality-gen: ПРЕДУПРЕЖДЕНИЕ: не удалось скачать $ASSET_CHECKSUMS -- пропускаю проверку целостности." >&2
      return 0
    fi
    err "не удалось скачать $ASSET_CHECKSUMS -- не могу проверить скачанный файл."
    echo "  установите CRITICALITY_SKIP_CHECKSUM=1, чтобы поставить без проверки." >&2
    exit 1
  fi

  expected=$(grep -E "  ${asset}\$" "$tmp_checksums" | awk '{print $1}' | head -1)
  rm -f "$tmp_checksums"
  if [ -z "$expected" ]; then
    if [ "${CRITICALITY_SKIP_CHECKSUM:-}" = "1" ]; then
      echo "criticality-gen: ПРЕДУПРЕЖДЕНИЕ: нет записи checksum для '$asset' -- пропускаю проверку целостности." >&2
      return 0
    fi
    err "нет записи checksum для '$asset' в $ASSET_CHECKSUMS -- не могу проверить скачанный файл."
    echo "  установите CRITICALITY_SKIP_CHECKSUM=1, чтобы поставить без проверки." >&2
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

run_remote_install() {
  info "criticality-gen: удалённая установка -- ищу релиз на GitLab..."

  api_base="$GITLAB_HOST/api/v4/projects/$GITLAB_PROJECT_ENC"

  TOKEN_VAL="${CRITICALITY_TOKEN:-${GITLAB_TOKEN:-}}"
  CURL_AUTH_ARGS=""
  [ -n "$TOKEN_VAL" ] && CURL_AUTH_ARGS="-H PRIVATE-TOKEN:$TOKEN_VAL"

  if [ -n "${CRITICALITY_VERSION:-}" ]; then
    resolved_tag="v${CRITICALITY_VERSION#v}"
    version="${resolved_tag#v}"
    info "criticality-gen: ставлю зафиксированную версию ${resolved_tag}..."
  else
    releases_json=$(curl -fsSL $CURL_AUTH_ARGS "$api_base/releases?per_page=100&sort=desc&order_by=released_at")
    resolved_tag=$(printf '%s' "$releases_json" \
      | grep -o '"tag_name":"[^"]*"' \
      | sed 's/.*"tag_name":"//; s/"$//' \
      | grep "^${COMPONENT_TAG_PREFIX}/" \
      | head -1)
    [ -n "$resolved_tag" ] || resolved_tag=""
    if [ -z "${resolved_tag:-}" ]; then
      err "не удалось найти последний релиз компонента $SKILL_NAME."
      echo "  проверьте доступ к проекту (приватный проект требует GITLAB_TOKEN или CRITICALITY_TOKEN) и что" >&2
      echo "  релизы с префиксом тега '$COMPONENT_TAG_PREFIX/' уже созданы:" >&2
      echo "  $GITLAB_HOST/$GITLAB_PROJECT/-/releases" >&2
      exit 1
    fi
    version="${resolved_tag#${COMPONENT_TAG_PREFIX}/v}"
    info "criticality-gen: последний релиз -- ${resolved_tag}."
  fi

  base_url="$GITLAB_HOST/api/v4/projects/$GITLAB_PROJECT_ENC/packages/generic/criticality-gen/${version}"

  work_dir=$(mktemp -d "${TMPDIR:-/tmp}/criticality-gen-install.XXXXXX")
  cleanup() { rm -rf "$work_dir" 2>/dev/null; }
  trap cleanup EXIT
  trap 'cleanup; exit 129' HUP
  trap 'cleanup; exit 130' INT
  trap 'cleanup; exit 131' QUIT
  trap 'cleanup; exit 143' TERM

  download_url="${base_url}/${ASSET_TARBALL}"
  tmp_file=$(mktemp "$work_dir/.dl.XXXXXX")
  info "criticality-gen: скачиваю ${ASSET_TARBALL}..."
  if ! curl -fsSL $CURL_AUTH_ARGS -o "$tmp_file" "$download_url"; then
    err "не удалось скачать $ASSET_TARBALL с $download_url"
    if [ -n "${CRITICALITY_VERSION:-}" ]; then
      echo "  проверьте, что релиз ${resolved_tag} существует и содержит этот файл:" >&2
      echo "  $GITLAB_HOST/$GITLAB_PROJECT/-/releases/${resolved_tag}" >&2
    else
      echo "  проверьте доступ к проекту или список релизов" >&2
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
  install_from_source "$src_dir"
}

# Общая точка выбора режима установки: проект или глобально.
install_from_source() {
  src="$1"
  if [ -n "$PROJECT_DIR" ]; then
    install_project "$src"
  else
    install_skill "$src"
  fi
}

finish() {
  if [ "$DRY_RUN" = "1" ]; then
    echo ""
    echo "dry-run: ничего не записано. Повторите без --dry-run, чтобы применить план."
    return 0
  fi
  if [ -n "$PROJECT_DIR" ]; then
    echo ""
    echo "Готово: проект $PROJECT_DIR развёрнут."
    echo "Скилл и команда лежат в $PROJECT_DIR/.opencode/ — opencode прочитает их"
    echo "при следующем запуске в этом каталоге."
    return 0
  fi
  echo ""
  echo "Готово."
  echo "Скилл criticality-gen и команда /criticality_gen установлены: opencode"
  echo "прочитает их при следующем запуске (перезапустите сессию opencode, если"
  echo "он уже запущен)."
  echo ""
  echo "Для работы нужны python3 и git; для сбора значений — MCP Confluence и"
  echo "Grafana. Данные проекта (is/, catalog.yaml, is.yaml) скилл ищет по --root,"
  echo "env CRITICALITY_ROOT или подъёмом от текущего каталога."
  echo "Чтобы развернуть проект целиком: install.sh --project /путь/к/проекту"
}

main() {
  action=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --uninstall) action="uninstall" ;;
      --force) FORCE=1 ;;
      --dry-run) DRY_RUN=1 ;;
      --claude) WITH_CLAUDE=1 ;;
      --project)
        [ $# -ge 2 ] || { err "флаг --project требует каталог: --project <путь>"; exit 2; }
        PROJECT_DIR="$2"
        shift
        ;;
      --project=*)
        PROJECT_DIR="${1#--project=}"
        ;;
      -h|--help) usage; exit 0 ;;
      *)
        err "неизвестный флаг: $1"
        usage
        exit 2
        ;;
    esac
    shift
  done

  if [ -n "$PROJECT_DIR" ]; then
    # Проект — абсолютным путём: все сообщения и make-цели должны быть
    # однозначными независимо от cwd. Каталог создаётся только при реальной
    # установке: --dry-run и --uninstall ничего не пишут.
    if [ -d "$PROJECT_DIR" ]; then
      PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
    elif [ "$DRY_RUN" = "1" ] || [ "$action" = "uninstall" ]; then
      case "$PROJECT_DIR" in
        /*) : ;;
        *) PROJECT_DIR="$(pwd)/$PROJECT_DIR" ;;
      esac
    else
      mkdir -p "$PROJECT_DIR"
      PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
    fi
  fi

  source_dir=""
  if detected=$(detect_source_dir); then
    source_dir="$detected"
    info "criticality-gen: локальная установка из $source_dir"
    check_source "$source_dir" "Запускайте install.sh из корня компонента criticality-gen."
  fi

  if [ "$action" = "uninstall" ]; then
    UNINSTALL_SRC="$source_dir"
    do_uninstall
  fi

  if [ -n "$source_dir" ]; then
    install_from_source "$source_dir"
  else
    run_remote_install
  fi

  finish
}

main "$@"

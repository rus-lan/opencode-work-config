#!/usr/bin/env bash
# =============================================================================
# install-tools.sh — установка / обновление инструментов генерации SLO.
# -----------------------------------------------------------------------------
# Обёртка над операционной памяткой ~/UPDATING_SLO_TOOLS.md. Устанавливает и
# обновляет:
#   * slokit  (~/.local/bin/slokit)   — генератор slo-kit.yaml из сканирования
#   * slo-kit (~/.local/bin/slo-kit)  — конвертер/линтер slo-kit.yaml -> sloth
# Проверяет/ставит зависимости: git, python3 + PyYAML (нужны для
# services-slogen.yaml и sloth-parse.py).
#
# Использование:
#   ./install-tools.sh           # проверить зависимости и обновить оба бинарника
#   ./install-tools.sh --check   # только проверить версии и зависимости
#   ./install-tools.sh slokit    # обновить только slokit
#   ./install-tools.sh slo-kit   # обновить только slo-kit (через Docker)
#
# Зависимости сборки slokit: Go toolchain (go build).
# Зависимости сборки slo-kit: Docker (pull dreg.sbmt.io/content/slo-kit:latest).
# =============================================================================

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BIN_DIR="$HOME/.local/bin"
SLOTKIT_DST="$BIN_DIR/slokit"
SLOKIT_DST="$BIN_DIR/slo-kit"

# Источник slokit: локальный git-клон (go-модуль slo-kit-generator)
SLOTKIT_SRC="${SLOTKIT_SRC:-$HOME/.config/opencode/skills/slo-kit-generator}"
SLOTKIT_CMD="${SLOTKIT_CMD:-/tmp/slokit_new}"

# Источник slo-kit: Docker-образ (основной канал; gitlab.sbmt.io сейчас недоступен)
SLOKIT_IMAGE="${SLOKIT_IMAGE:-dreg.sbmt.io/content/slo-kit:latest}"
SLOKIT_TMP="/tmp/slo-kit-new"

MODE="all"           # all | slokit | slo-kit | check
DO_CHECK=0

usage() {
  grep -E '^# ' "$0" | sed 's/^# \{0,1\}//' | sed -n '1,20p'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage ;;
    --check|-c) MODE="check"; shift ;;
    slokit) MODE="slokit"; shift ;;
    slo-kit) MODE="slo-kit"; shift ;;
    *) echo "Неизвестный аргумент: $1" >&2; usage ;;
  esac
done

mkdir -p "$BIN_DIR"

say()  { printf '\033[1;34m[install]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  OK\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m WARN\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# ----------------------------------------------------------------------------
# Зависимости
# ----------------------------------------------------------------------------
check_deps() {
  say "Проверка зависимостей..."
  local missing=()
  for c in git python3; do
    if have "$c"; then ok "$c: $(command -v "$c")"; else missing+=("$c"); warn "$c не найден"; fi
  done
  # python3 + PyYAML (для sloth-parse.py / services-slogen.yaml)
  if have python3; then
    if python3 -c "import yaml" >/dev/null 2>&1; then
      ok "python3 PyYAML: $(python3 -c "import yaml;print(yaml.__version__)")"
    else
      missing+=("python3-PyYAML"); warn "python3 yaml-модуль не установлен (pip install pyyaml / apt python3-yaml)"
    fi
  fi
  # slokit
  if have "$SLOTKIT_DST" || have slokit; then ok "slokit: $(command -v slokit || echo $SLOTKIT_DST)"; else warn "slokit не установлен"; fi
  # slo-kit
  if have "$SLOKIT_DST" || have slo-kit; then ok "slo-kit: $(command -v slo-kit || echo $SLOKIT_DST) ($($SLOKIT_DST --version 2>/dev/null || echo n/a))"; else warn "slo-kit не установлен"; fi
  if have go;   then ok "go (для сборки slokit): $(command -v go)";  else missing+=("go");   fi
  if have docker; then ok "docker (для slo-kit): $(command -v docker)"; else missing+=("docker"); fi
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo
    warn "Отсутствуют: ${missing[*]}"
    echo "  Установите их вручную, затем перезапустите. См. также ~/UPDATING_SLO_TOOLS.md"
    return 1
  fi
  echo
  return 0
}

# ----------------------------------------------------------------------------
# slokit: сборка из исходников (go build)
# ----------------------------------------------------------------------------
update_slokit() {
  say "Обновление slokit ($SLOTKIT_DST)"
  [[ -d "$SLOTKIT_SRC" ]] || fail "Нет исходников slokit: $SLOTKIT_SRC"
  have go || fail "Нет Go toolchain (требуется для сборки slokit)"

  ( cd "$SLOTKIT_SRC" && git fetch origin 2>&1 | tail -2 ) || warn "git fetch slokit не удался (обновлю из текущего HEAD)"
  ( cd "$SLOTKIT_SRC" && go build -o "$SLOTKIT_CMD" ./cmd/slokit ) || fail "go build slokit не удался"
  install -m 755 "$SLOTKIT_CMD" "$SLOTKIT_DST"
  ok "slokit установлен: $SLOTKIT_DST ($(stat -c %s "$SLOTKIT_DST" 2>/dev/null) bytes)"
}

# ----------------------------------------------------------------------------
# slo-kit: Docker pull -> create -> cp (основной способ из ~/UPDATING_SLO_TOOLS.md)
# ----------------------------------------------------------------------------
update_slo_kit() {
  say "Обновление slo-kit ($SLOKIT_DST)"
  if have docker; then
    # бэкап старой версии
    if [[ -f "$SLOKIT_DST" ]]; then
      ver="$("$SLOKIT_DST" --version 2>/dev/null | awk '{print $NF}' || echo "unknown")"
      cp "$SLOKIT_DST" "$SLOKIT_DST.bak-$ver" && ok "бэкап старой версии: $SLOKIT_DST.bak-$ver"
    fi
    docker pull "$SLOKIT_IMAGE" || fail "docker pull $SLOKIT_IMAGE"
    local cid
    cid="$(docker create "$SLOKIT_IMAGE")" || fail "docker create"
    docker cp "$cid:/app/slo-kit" "$SLOKIT_TMP" || docker cp "$cid:/usr/local/bin/slo-kit" "$SLOKIT_TMP" || { docker rm "$cid" >/dev/null 2>&1; fail "не найден slo-kit внутри образа"; }
    docker rm "$cid" >/dev/null 2>&1
    install -m 755 "$SLOKIT_TMP" "$SLOKIT_DST"
    ok "slo-kit установлен: version $($SLOKIT_DST --version 2>/dev/null)"
  else
    warn "Нет docker; пропускаю slo-kit. (Запасной способ — сборка из gitlab.sbmt.io, сейчас недоступен.)"
  fi
}

# ----------------------------------------------------------------------------
# Действия
# ----------------------------------------------------------------------------
if [[ "$MODE" == "check" ]]; then
  check_deps || exit 0
  exit 0
fi

check_deps || exit 1

case "$MODE" in
  all)     update_slokit; update_slo_kit ;;
  slokit)  update_slokit ;;
  slo-kit) update_slo_kit ;;
esac

echo
say "Готово. Проверка: slokit --help ; slo-kit --version"
say "Полная памятка по обновлению инструментов: ~/UPDATING_SLO_TOOLS.md"
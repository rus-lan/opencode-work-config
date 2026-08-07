#!/usr/bin/env bash
# shellcheck disable=SC2317
set -euo pipefail

# =============================================================================
# setup-opencode-config.sh
# Автоматическая установка конфигурации Opencode на новом устройстве
# Поддерживает: Linux, macOS
# =============================================================================

REPO_URL="git@github.com:rus-lan/opencode-work-config.git"
CONFIG_DIR="$HOME/.config/opencode"
OPENCODE_BIN=""

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---- helpers ----

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
info()  { echo -e "${BLUE}[i]${NC} $1"; }

section() {
  echo ""
  echo -e "${BLUE}══════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}  $1${NC}"
  echo -e "${BLUE}══════════════════════════════════════════════════${NC}"
}

confirm() {
  echo -en "${YELLOW}[?]${NC} $1 [Y/n] "
  read -t 10 -r response
  case "$response" in
    [nN][oO]|[nN]) return 1 ;;
    *) return 0 ;;
  esac
}

# ---- step 1: detect OS ----

detect_os() {
  section "1/7 — Определение операционной системы"

  case "$(uname -s)" in
    Linux*)  OS="linux" ;;
    Darwin*) OS="macos" ;;
    *)
      error "Неподдерживаемая ОС: $(uname -s)"
      error "Поддерживаются только Linux и macOS"
      exit 1
      ;;
  esac

  ARCH=$(uname -m)
  log "ОС: ${OS}, архитектура: ${ARCH}"
}

# ---- step 2: check / install opencode ----

check_opencode() {
  section "2/7 — Проверка установки opencode"

  if command -v opencode &>/dev/null; then
    OPENCODE_BIN=$(command -v opencode)
    local version
    version=$(opencode --version 2>/dev/null || true)
    log "Opencode уже установлен: ${OPENCODE_BIN} (${version:-версия неизвестна})"
    return 0
  fi

  warn "Opencode не найден"

  # Проверка ~/.local/bin
  if [ -x "$HOME/.local/bin/opencode" ]; then
    OPENCODE_BIN="$HOME/.local/bin/opencode"
    log "Opencode найден в ~/.local/bin: ${OPENCODE_BIN}"
    export PATH="$HOME/.local/bin:$PATH"
    return 0
  fi

  if ! confirm "Установить opencode сейчас?"; then
    warn "Установка opencode пропущена. Установи вручную: https://opencode.ai/install"
    return 1
  fi

  info "Установка opencode..."

  local install_cmd="curl -fsSL https://opencode.ai/install | sh"

  if eval "$install_cmd"; then
    # После curl установки бинарник в ~/.local/bin
    if [ -x "$HOME/.local/bin/opencode" ]; then
      OPENCODE_BIN="$HOME/.local/bin/opencode"
      export PATH="$HOME/.local/bin:$PATH"
    elif command -v opencode &>/dev/null; then
      OPENCODE_BIN=$(command -v opencode)
    fi
    log "Opencode успешно установлен"
  else
    error "Не удалось установить opencode"
    error "Установи вручную: https://opencode.ai/install"
    return 1
  fi
}

# ---- step 3: clone / pull config repo ----

setup_config_repo() {
  section "3/7 — Настройка репозитория конфигурации"

  if [ -d "$CONFIG_DIR/.git" ]; then
    info "Репозиторий уже существует. Выполняю git pull..."
    if git -C "$CONFIG_DIR" pull --ff-only 2>/dev/null; then
      log "Конфигурация обновлена"
    else
      warn "Не удалось выполнить pull. Возможно, есть незакоммиченные изменения."
      warn "Проверь вручную: cd ${CONFIG_DIR} && git status"
    fi
    return 0
  fi

  # Если директория существует но это не git-репо
  if [ -d "$CONFIG_DIR" ]; then
    warn "Директория ${CONFIG_DIR} существует, но это не git-репозиторий."
    if confirm "Удалить и склонировать заново?"; then
      rm -rf "$CONFIG_DIR"
    else
      error "Не могу продолжить. Очисти директорию вручную: rm -rf ${CONFIG_DIR}"
      exit 1
    fi
  fi

  info "Клонирование репозитория конфигурации..."

  # Сначала пробуем SSH
  if git clone "$REPO_URL" "$CONFIG_DIR" 2>/dev/null; then
    log "Репозиторий склонирован (SSH)"
    return 0
  fi

  warn "SSH-клонирование не удалось. Пробую HTTPS..."

  local https_url
  https_url="https://github.com/rus-lan/opencode-work-config.git"

  if git clone "$https_url" "$CONFIG_DIR"; then
    log "Репозиторий склонирован (HTTPS)"
    warn "Рекомендуется настроить SSH-ключи для удобства: https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
    return 0
  fi

  error "Не удалось склонировать репозиторий."
  error "SSH: ${REPO_URL}"
  error "HTTPS: ${https_url}"
  error "Проверь доступ к GitHub и права доступа к репозиторию."
  exit 1
}

# ---- step 4: install npm dependencies ----

install_deps() {
  section "4/7 — Установка npm-зависимостей"

  if [ ! -f "$CONFIG_DIR/package.json" ]; then
    error "package.json не найден в ${CONFIG_DIR}"
    exit 1
  fi

  info "Установка зависимостей: npm install"

  if npm install --prefix "$CONFIG_DIR" 2>/dev/null; then
    log "npm-зависимости установлены"
  else
    warn "npm install завершился с ошибками (возможно, не все пакеты установлены)"
    warn "Проверь вручную: cd ${CONFIG_DIR} && npm install"
  fi
}

# ---- step 4b: install guard hooks ----
setup_hooks() {
  section "4b/7 — Установка guard-хуков"

  if [ -d "$CONFIG_DIR/.git" ]; then
    local hooks_dir="$CONFIG_DIR/.git/hooks"
    mkdir -p "$hooks_dir"
    if [ -f "$CONFIG_DIR/guard.sh" ]; then
      cp "$CONFIG_DIR/guard.sh" "$hooks_dir/pre-commit"
      chmod +x "$hooks_dir/pre-commit"
      log "guard.sh → .git/hooks/pre-commit: установлен"
    fi
    if [ -f "$CONFIG_DIR/pre-commit.sh" ]; then
      cp "$CONFIG_DIR/pre-commit.sh" "$hooks_dir/pre-commit"
      chmod +x "$hooks_dir/pre-commit"
      log "pre-commit.sh → .git/hooks/pre-commit: установлен"
    fi
  fi
}

# ---- step 5: create .env file ----

setup_env() {
  section "5/7 — Настройка переменных окружения"

  if [ -f "$CONFIG_DIR/.env" ]; then
    log ".env уже существует"
    if [ ! -s "$CONFIG_DIR/.env" ] || grep -q "=$" "$CONFIG_DIR/.env"; then
      warn "Некоторые переменные в .env не заполнены"
      warn "Отредактируй: ${CONFIG_DIR}/.env"
    fi
    return 0
  fi

  if [ ! -f "$CONFIG_DIR/.env.example" ]; then
    warn ".env.example не найден, пропускаю создание .env"
    warn "Создай вручную: touch ${CONFIG_DIR}/.env"
    return 0
  fi

  cp "$CONFIG_DIR/.env.example" "$CONFIG_DIR/.env"
  log ".env создан из .env.example"

  warn "ВАЖНО: Отредактируй ${CONFIG_DIR}/.env и заполни API-токены:"
  echo ""
  echo -e "  ${BLUE}ECOM_QWEN35_122b_TOKEN${NC}         — Qwen 3.5 122B"
  echo -e "  ${BLUE}ECOM_QWEN36_35b_TOKEN${NC}           — Qwen 3.6 35B"
  echo -e "  ${BLUE}ECOM_DEEPSEEK4_FLASH_TOKEN${NC}      — DeepSeek v4 flash"
  echo -e "  ${BLUE}ECOM_GIGA3_10b_TOKEN${NC}            — Giga v3 10B"
  echo -e "  ${BLUE}ECOM_QWEN35_122b_NO_THINK_TOKEN${NC} — Qwen 3.5 122B (no-think)"
  echo -e "  ${BLUE}ECOM_QWEN36_35b_NO_THINK_TOKEN${NC}  — Qwen 3.6 35B (no-think)"
  echo ""
}

# ---- step 6: add ~/.local/bin to PATH ----

setup_path() {
  section "6/7 — Проверка PATH"

  # Определяем shell конфиг файл
  local shell_config=""
  case "${SHELL:-}" in
    */zsh) shell_config="$HOME/.zshrc" ;;
    */bash) shell_config="$HOME/.bashrc" ;;
    *)
      # Если SHELL неопределен, проверяем наличие файлов
      if [ -f "$HOME/.zshrc" ]; then
        shell_config="$HOME/.zshrc"
      elif [ -f "$HOME/.bashrc" ]; then
        shell_config="$HOME/.bashrc"
      elif [ -f "$HOME/.bash_profile" ]; then
        shell_config="$HOME/.bash_profile"
      else
        shell_config="$HOME/.profile"
      fi
      ;;
  esac

  # Проверка что ~/.local/bin в PATH
  local local_bin="$HOME/.local/bin"
  local in_path=false

  if echo "$PATH" | tr ':' '\n' | grep -qx "$local_bin"; then
    in_path=true
  fi

  if [ "$in_path" = true ]; then
    log "${local_bin} уже в PATH"
    return 0
  fi

  warn "${local_bin} не найден в PATH"

  if confirm "Добавить ${local_bin} в PATH через ${shell_config}?"; then
    echo "" >> "$shell_config"
    echo "# Opencode" >> "$shell_config"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$shell_config"
    export PATH="$HOME/.local/bin:$PATH"
    log "PATH обновлён в ${shell_config}"
    warn "Перезапусти терминал или выполни: source ${shell_config}"
  else
    warn "Добавь вручную: echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ${shell_config}"
  fi
}

# ---- step 7: verify installation ----

verify_installation() {
  section "7/7 — Проверка установки"

  local errors=0

  # Проверка opencode
  if command -v opencode &>/dev/null || [ -x "$HOME/.local/bin/opencode" ]; then
    local ver
    ver=$(opencode --version 2>/dev/null || echo "версия неизвестна")
    log "Opencode: ${ver}"
  else
    error "Opencode не найден в PATH"
    errors=$((errors + 1))
  fi

  # Проверка конфигурации
  if [ -f "$CONFIG_DIR/opencode.json" ]; then
    log "Конфигурация: ${CONFIG_DIR}/opencode.json"
  else
    error "opencode.json не найден в ${CONFIG_DIR}"
    errors=$((errors + 1))
  fi

  # Проверка .env
  if [ -f "$CONFIG_DIR/.env" ]; then
    local empty_vars
    empty_vars=$(grep -c "=$" "$CONFIG_DIR/.env" 2>/dev/null || true)
    if [ "$empty_vars" -gt 0 ]; then
      warn "В .env не заполнены ${empty_vars} переменных"
    else
      log ".env: все переменные заполнены"
    fi
  else
    warn ".env не найден"
  fi

  # Проверка node_modules
  if [ -d "$CONFIG_DIR/node_modules" ]; then
    log "node_modules: установлены"
  else
    warn "node_modules не найдены (возможно, не выполнен npm install)"
    errors=$((errors + 1))
  fi

  # Проверка агентов
  local agent_count
  agent_count=$(find "$CONFIG_DIR/agents" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  local subagent_count=$((agent_count > 3 ? agent_count - 3 : 0))
  log "Агенты: ${agent_count} (3 primary + ${subagent_count} subagent types)"

  # Проверка скиллов
  local skill_count
  skill_count=$(find "$CONFIG_DIR/skills" -name "SKILL.md" 2>/dev/null | wc -l | tr -d ' ')
  log "Скиллы: ${skill_count}"

  # Проверка правил
  local rule_count
  rule_count=$(find "$CONFIG_DIR/rules" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  log "Правила: ${rule_count} (авто-загружаются через instructions)"

  # Проверка MCP
  log "MCP: aistats + playwright"
  if command -v aistats &>/dev/null; then
    log "aistats CLI: доступен"
  else
    warn "aistats CLI не найден — установи для трекинга метрик: https://github.com/t34-dev/aistats"
  fi

  echo ""
  if [ "$errors" -eq 0 ]; then
    log "Установка завершена успешно!"
  else
    warn "Установка завершена с ${errors} ошибками. Проверь вывод выше."
  fi

  echo ""
  echo -e "  ${BLUE}Конфигурация:${NC}  ${CONFIG_DIR}"
  echo -e "  ${BLUE}Документация:${NC}  ${CONFIG_DIR}/CONFIG_DOCUMENTATION.md"
  echo -e "  ${BLUE}Правила:${NC}       ${rule_count} (авто-загружаются)"
  echo -e "  ${BLUE}Агенты:${NC}        ${agent_count}"
  echo -e "  ${BLUE}Скиллы:${NC}        ${skill_count}"
  echo -e "  ${BLUE}MCP:${NC}           aistats, playwright"
  echo -e "  ${BLUE}Защита:${NC}        guard.sh (dangerous compound-команды)"
  echo -e "  ${BLUE}Запуск:${NC}        opencode"
}

# ---- main ----

cleanup() {
  echo ""
  warn "Прервано пользователем"
  exit 1
}

main() {
  trap cleanup INT TERM

  for cmd in git node npm; do
    if ! command -v "$cmd" &>/dev/null; then
      error "${cmd} не найден. Установи ${cmd} и запусти скрипт снова."
      exit 1
    fi
  done

  echo ""
  echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║  Установка конфигурации Opencode               ║${NC}"
  echo -e "${BLUE}║  Репозиторий: rus-lan/opencode-work-config     ║${NC}"
  echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
  echo ""

  detect_os
  check_opencode || warn "Продолжаем без opencode (установи позже)"
  setup_config_repo
  install_deps
  setup_hooks
  setup_env
  setup_path
  verify_installation

  echo ""
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}  Установка завершена!${NC}"
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo -e "  ${BLUE}Конфигурация:${NC}  ${CONFIG_DIR}"
  echo -e "  ${BLUE}Документация:${NC}  ${CONFIG_DIR}/CONFIG_DOCUMENTATION.md"
  echo -e "  ${BLUE}Запуск:${NC}        opencode"
  echo ""
  echo -e "  ${YELLOW}Не забудь заполнить API-токены:${NC}"
  echo -e "  ${CONFIG_DIR}/.env"
  echo ""
}

main "$@"
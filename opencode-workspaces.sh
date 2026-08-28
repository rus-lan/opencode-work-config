# Key: shell command suffix.
# Value: workspace directory name.
#
# Example:
#   oc-go -> ~/workspaces/letsgo/.opencode
typeset -gA OC_LABEL_TO_WORKSPACE
OC_LABEL_TO_WORKSPACE=(
  ba     ba
  sa     sa
  qa     qa
  go     letsgo
#  node   node
#  vue    vue
#  react  react
#  sec    sec
#  arch   arch
)

oc-workspace() {
  local workspace_name="${1:-}"
  local config_dir

  if [[ -z "$workspace_name" ]]; then
    echo "Использование: oc-workspace <workspace> [аргументы opencode]" >&2
    return 2
  fi

  config_dir="$HOME/workspaces/$workspace_name/.opencode"

  if [[ ! -d "$config_dir" ]]; then
    echo "Не найдена .opencode: $config_dir" >&2
    return 1
  fi

  if git -C "$config_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if ! git -C "$config_dir" pull --ff-only; then
      echo "Предупреждение: не удалось обновить workspace: $workspace_name" >&2
      echo "Используется локальная конфигурация: $config_dir" >&2
    fi
  else
    echo "Предупреждение: .opencode не является Git-репозиторием: $config_dir" >&2
    echo "Автообновление пропущено; используется локальная конфигурация." >&2
  fi

  shift

  OPENCODE_CONFIG_DIR="$config_dir" \
    command opencode "$@"
}

oc-all() {
  local tmp_dir
  local overlay_dir
  local workspace_name
  local source_dir
  local relative_path
  local file_path

  local -a source_dirs
  local -A seen_files

  if ! command -v rsync >/dev/null 2>&1; then
    echo "Не найден rsync. Установи его, например: sudo apt install rsync" >&2
    return 1
  fi

  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/opencode-all.XXXXXXXX")" || {
    echo "Не удалось создать временную директорию для OpenCode overlay." >&2
    return 1
  }

  overlay_dir="$tmp_dir/.opencode"

  if ! mkdir -p "$overlay_dir"; then
    rm -rf "$tmp_dir"
    echo "Не удалось создать OpenCode overlay: $overlay_dir" >&2
    return 1
  fi

  for workspace_name in "${(@u)OC_LABEL_TO_WORKSPACE}"; do
    source_dir="$HOME/workspaces/$workspace_name/.opencode"

    if [[ ! -d "$source_dir" ]]; then
      echo "Предупреждение: workspace пропущен, нет .opencode: $source_dir" >&2
      continue
    fi

    if git -C "$source_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      if ! git -C "$source_dir" pull --ff-only; then
        echo "Предупреждение: не удалось обновить workspace: $workspace_name" >&2
        echo "Используется локальная версия: $source_dir" >&2
      fi
    else
      echo "Предупреждение: Git недоступен для workspace: $workspace_name" >&2
      echo "Используется локальная версия: $source_dir" >&2
    fi

    source_dirs+=("$source_dir")
  done

  if (( ${#source_dirs[@]} == 0 )); then
    rm -rf "$tmp_dir"
    echo "Не найдено ни одной .opencode-конфигурации для сборки." >&2
    return 1
  fi

  # Не допускаем тихого перезаписывания одинаковых файлов.
  # Конфликт agents/foo.md, commands/bar.md и т.п. прервёт запуск.
  for source_dir in "${source_dirs[@]}"; do
    while IFS= read -r -d '' file_path; do
      relative_path="${file_path#$source_dir/}"

#      if [[ -n "${seen_files[$relative_path]-}" ]]; then
#        echo "Конфликт OpenCode overlay: $relative_path" >&2
#        echo "  первый источник: ${seen_files[$relative_path]}" >&2
#        echo "  второй источник: $source_dir" >&2
#        rm -rf "$tmp_dir"
#        return 1
#      fi

      seen_files[$relative_path]="$source_dir"
    done < <(
      find "$source_dir" \
        -path "$source_dir/.git" -prune -o \
        \( -type f -o -type l \) -print0
    )
  done

  for source_dir in "${source_dirs[@]}"; do
    if ! rsync -a --exclude='.git' "$source_dir/" "$overlay_dir/"; then
      rm -rf "$tmp_dir"
      echo "Не удалось добавить workspace в overlay: $source_dir" >&2
      return 1
    fi
  done

  echo "OpenCode overlay собран: $overlay_dir" >&2
  echo "Подключены workspace: ${(j:, :)source_dirs}" >&2

  OPENCODE_CONFIG_DIR="$overlay_dir" \
    command opencode "$@"

  rm -rf "$tmp_dir"

  return 0
}

# Генерация профильных функций:
#
#   oc-qa    -> oc-workspace qa     --agent qa-lead
#   oc-sa    -> oc-workspace sa     --agent sa-lead
#   oc-go    -> oc-workspace letsgo --agent letsgo-lead
#
# Значения берутся только из статической карты выше, поэтому eval здесь
# не получает пользовательский ввод.
local label workspace_name

for label workspace_name in ${(kv)OC_LABEL_TO_WORKSPACE}; do
  eval "oc-${label}() {
    oc-workspace ${workspace_name} \"\$@\" --agent ${workspace_name}-lead
  }"
done

unset label workspace_name

# Основной режим: все workspace + оркестратор.
oca() {
  oc-all "$@" --agent orchestrator
}

#!/usr/bin/env bash
# =============================================================================
# sloth-bot.sh — автоматический запуск полного цикла генерации SLO без ручной
# валидации (для cron-планировщика, напр. раз в 3 дня).
# -----------------------------------------------------------------------------
# Делает:
#   1. обновляет инструменты (slokit, slo-kit) — install-tools.sh;
#   2. прогоняет generate-sloth.sh — обход всех сервисов, клонирование
#      репозиториев сервисов и helm-репо компании, генерация sloth.yaml,
#      публикация в ./helm/<company> с уникальной веткой feature/sloth-<date>;
#   3. пишет краткий отчёт в ./sloth-bot-report-<date>.md и лог.
#
# Запуск без ручной валидации: скрипт сам не останавливается на ошибках
# отдельных сервисов (они помечаются в отчёте), всегда доводит обход до конца
# и формирует итоговый отчёт.
#
# Crontab (каждые 3 дня в 03:00) — скрипт пользуется своим каталогом, путь
# можно указывать либо из установленного скилла, либо из клона инструментария:
#   0 3 */3 * *  "$HOME/.config/opencode/skills/slo-monitoring/scripts/sloth-bot.sh" >> "$HOME/.config/opencode/skills/slo-monitoring/scripts/.sloth-logs/bot-cron.log" 2>&1
#
# Запуск:
#   ./sloth-bot.sh                # полный цикл (tools + generate) локально
#   ./sloth-bot.sh --docker       # полный цикл в изолированном контейнере
#   ./sloth-bot.sh --no-tools     # пропустить обновление инструментов
#   ./sloth-bot.sh --check        # только проверка готовности окружения
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATE="$(date +%Y%m%d-%H%M)"
REPORT="$SCRIPT_DIR/sloth-bot-report-$DATE.md"
LOG_DIR="$SCRIPT_DIR/.sloth-logs"
mkdir -p "$LOG_DIR"

MODE_DOCKER=0
DO_TOOLS=1

usage() { grep -E '^# ' "$0" | sed 's/^# \{0,1\}//' | sed -n '1,22p'; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage ;;
    --docker)  MODE_DOCKER=1; shift ;;
    --no-tools) DO_TOOLS=0; shift ;;
    --check)   ./install-tools.sh --check; exit $? ;;
    *) echo "Неизвестный аргумент: $1" >&2; usage ;;
  esac
done

{
  echo "# Отчёт запуска SLO-бота — $DATE"
  echo
  echo "## Окружение"
  echo "- Ветка: feature/sloth-$DATE"
  echo "- Режим: $([[ $MODE_DOCKER -eq 1 ]] && echo 'Docker-изоляция' || echo 'локально')"
  echo "- slokit: $(command -v slokit || echo n/a)"
  echo "- slo-kit: $(slo-kit --version 2>/dev/null || echo n/a)"
  echo
} > "$REPORT"

# --- 1/2. обновление инструментов ---
if [[ $DO_TOOLS -eq 1 ]]; then
  {
    echo "## Шаг 1/2 — установка/обновление инструментов"
    echo
    ./install-tools.sh || echo "- [WARN] install-tools.sh завершился с ошибкой"
  } >> "$REPORT"
else
  {
    echo "## Шаг 1/2 — пропущено (--no-tools)"
    echo
  } >> "$REPORT"
fi

# --- 2/2. генерация ---
{
  echo "## Шаг 2/2 — генерация SLO по services-slogen.yaml"
  echo
} >> "$REPORT"

if [[ $MODE_DOCKER -eq 1 ]]; then
  ./docker/run.sh >> "$REPORT" 2>&1 || echo "- [FAIL] docker/run.sh завершился с ошибкой" >> "$REPORT"
else
  ./generate-sloth.sh --jobs 4 >> "$REPORT" 2>&1 || echo "- [FAIL] generate-sloth.sh завершился с ошибкой" >> "$REPORT"
fi

# --- сводка ---
{
  echo
  echo "## Сводка по сервисам"
  echo
  for f in "$LOG_DIR"/*.log; do
    [[ -f "$f" ]] || continue
    name="$(basename "$f" .log)"
    res="$(grep -E 'РЕЗУЛЬТАТ:' "$f" | head -1 | sed 's/.*РЕЗУЛЬТАТ: *//')"
    echo "- **$name**: ${res:-(нет результата)}"
  done | sort
  echo
  echo "_Сформировано автоматически sloth-bot.sh в $DATE._"
} >> "$REPORT"

echo "Отчёт: $REPORT"
echo "Готово. Проверьте $REPORT и при необходимости pull/push веток."
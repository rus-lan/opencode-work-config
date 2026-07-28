#!/bin/bash
# Получение метрик контекста для текущей сессии opencode

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Форматирование чисел с разделителями
format_number() {
    local num=$1
    if [ "$num" -ge 1000000 ]; then
        echo "$(echo "scale=1; $num / 1000000" | bc)M"
    elif [ "$num" -ge 1000 ]; then
        echo "$(echo "scale=1; $num / 1000" | bc)K"
    else
        echo "$num"
    fi
}

# Получить метрики из aistats (если доступен)
get_aistats_metrics() {
    if command -v aistats &> /dev/null; then
        aistats report --format json 2>/dev/null || echo "{}"
    else
        echo "{}"
    fi
}

# Получить конфигурацию модели
get_model_config() {
    local model="$1"
    local config_file="$HOME/.config/opencode/opencode.json"
    
    if [ -f "$config_file" ]; then
        # Используем jq для парсинга JSON
        if command -v jq &> /dev/null; then
            jq -r ".provider | to_entries[] | select(.value.models | has(\"$model\")) | .value.models[\"$model\"]" "$config_file" 2>/dev/null || echo "{}"
        else
            echo "{}"
        fi
    else
        echo "{}"
    fi
}

# Получить текущую сессию
get_current_session() {
    # Пытаемся получить из aistats или используем дефолтное значение
    if command -v aistats &> /dev/null; then
        aistats projects --format json 2>/dev/null | jq -r '.[0].name // "unknown"' || echo "unknown"
    else
        echo "unknown"
    fi
}

# Расчет процента использования
calc_percentage() {
    local used=$1
    local total=$2
    if [ "$total" -gt 0 ]; then
        echo "scale=1; $used * 100 / $total" | bc
    else
        echo "0"
    fi
}

# Основной вывод метрик
show_metrics() {
    local session=$(get_current_session)
    local model="${OPENCODE_MODEL:-qwen3.5-122b}"
    
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${BLUE}Context Metrics${NC}  Session: ${GREEN}$session${NC}"
    echo -e "${CYAN}╠════════════════════════════════════════════════════════╣${NC}"
    
    # Получаем конфигурацию модели
    local model_config=$(get_model_config "$model")
    
    # Контекстный лимит (по умолчанию 1M если не указан)
    local context_limit=$(echo "$model_config" | jq -r '.limit.context // 1000000')
    local output_limit=$(echo "$model_config" | jq -r '.limit.output // "N/A"')
    
    echo -e "${CYAN}║${NC}  Model: ${YELLOW}$model${NC}"
    echo -e "${CYAN}║${NC}  Context Limit: ${GREEN}$(format_number $context_limit)${NC} tokens"
    [ "$output_limit" != "N/A" ] && echo -e "${CYAN}║${NC}  Output Limit: ${GREEN}$(format_number $output_limit)${NC} tokens"
    echo -e "${CYAN}╠════════════════════════════════════════════════════════╣${NC}"
    
    # Rate Limits
    echo -e "${CYAN}║${NC}  ${BLUE}Rate Limits:${NC}"
    
    local hourly=$(echo "$model_config" | jq -r '.limit.hourly // empty')
    local daily=$(echo "$model_config" | jq -r '.limit.daily // empty')
    local weekly=$(echo "$model_config" | jq -r '.limit.weekly // empty')
    local monthly=$(echo "$model_config" | jq -r '.limit.monthly // empty')
    
    [ -n "$hourly" ] && echo -e "${CYAN}║${NC}    • Hourly: ${GREEN}$(format_number $hourly)${NC}"
    [ -n "$daily" ] && echo -e "${CYAN}║${NC}    • Daily: ${GREEN}$(format_number $daily)${NC}"
    [ -n "$weekly" ] && echo -e "${CYAN}║${NC}    • Weekly: ${GREEN}$(format_number $weekly)${NC}"
    [ -n "$monthly" ] && echo -e "${CYAN}║${NC}    • Monthly: ${GREEN}$(format_number $monthly)${NC}"
    
    # Effort
    local effort_current=$(echo "$model_config" | jq -r '.effort.current // empty')
    local effort_limit=$(echo "$model_config" | jq -r '.effort.limit // empty')
    
    if [ -n "$effort_current" ]; then
        echo -e "${CYAN}╠════════════════════════════════════════════════════════╣${NC}"
        echo -e "${CYAN}║${NC}  ${BLUE}Effort:${NC} ${GREEN}$effort_current${NC}"
        [ -n "$effort_limit" ] && echo -e "${CYAN}║${NC}    Max: ${YELLOW}$effort_limit${NC}"
    fi
    
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Проверка лимитов и предупреждения
check_limits() {
    local used=$1
    local total=$2
    
    local percentage=$(calc_percentage $used $total)
    local int_percentage=${percentage%.*}
    
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}Usage Analysis:${NC}"
    
    if [ "$int_percentage" -lt 50 ]; then
        echo -e "  ${GREEN}✓${NC} Context usage is healthy (${percentage}%)"
    elif [ "$int_percentage" -lt 80 ]; then
        echo -e "  ${YELLOW}⚠${NC} Moderate usage (${percentage}%) - consider monitoring"
    else
        echo -e "  ${RED}✗${NC} High usage (${percentage}%) - consider compacting session"
    fi
    
    echo ""
}

# Аргументы
case "${1:-}" in
    "watch")
        interval="${2:-30}"
        echo "Watching context metrics every $interval seconds. Press Ctrl+C to stop."
        while true; do
            clear
            show_metrics
            sleep $interval
        done
        ;;
    "limits")
        show_metrics
        ;;
    "effort")
        model="${OPENCODE_MODEL:-qwen3.5-122b}"
        model_config=$(get_model_config "$model")
        effort_current=$(echo "$model_config" | jq -r '.effort.current // "not set"')
        effort_limit=$(echo "$model_config" | jq -r '.effort.limit // "not set"')
        echo -e "${BLUE}Effort Configuration:${NC}"
        echo -e "  Current: ${GREEN}$effort_current${NC}"
        echo -e "  Limit: ${YELLOW}$effort_limit${NC}"
        ;;
    *)
        show_metrics
        ;;
esac

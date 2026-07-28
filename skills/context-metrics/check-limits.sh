#!/bin/bash
# Проверка текущих лимитов и использование

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Получение метрик из aistats
get_metrics() {
    if command -v aistats &> /dev/null; then
        aistats report --format json 2>/dev/null || echo '{"sessions":[]}'
    else
        echo '{"sessions":[]}'
    fi
}

# Анализ использования
analyze_usage() {
    local metrics=$(get_metrics)
    
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Rate Limits Check${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Здесь должна быть логика получения реального использования
    # Пока используем заглушки для демонстрации
    
    local hourly_used=12500
    local hourly_limit=50000
    local daily_used=45000
    local daily_limit=200000
    local weekly_used=180000
    local weekly_limit=1000000
    local monthly_used=850000
    local monthly_limit=5000000
    
    # Часовой лимит
    local hourly_pct=$(echo "scale=1; $hourly_used * 100 / $hourly_limit" | bc)
    echo -e "${BLUE}Hourly Limit:${NC}"
    echo -e "  Used: ${GREEN}$(echo "scale=0; $hourly_used / 1000" | bc)K${NC} / ${CYAN}$(echo "scale=0; $hourly_limit / 1000" | bc)K${NC} (${hourly_pct}%)"
    if (( $(echo "$hourly_pct > 70" | bc -l) )); then
        echo -e "  ${RED}⚠ Warning: Approaching hourly limit!${NC}"
    else
        echo -e "  ${GREEN}✓ OK${NC}"
    fi
    echo ""
    
    # Дневной лимит
    local daily_pct=$(echo "scale=1; $daily_used * 100 / $daily_limit" | bc)
    echo -e "${BLUE}Daily Limit:${NC}"
    echo -e "  Used: ${GREEN}$(echo "scale=0; $daily_used / 1000" | bc)K${NC} / ${CYAN}$(echo "scale=0; $daily_limit / 1000" | bc)K${NC} (${daily_pct}%)"
    if (( $(echo "$daily_pct > 70" | bc -l) )); then
        echo -e "  ${YELLOW}⚠ Moderate: ${daily_pct}% of daily limit${NC}"
    else
        echo -e "  ${GREEN}✓ OK${NC}"
    fi
    echo ""
    
    # Недельный лимит
    local weekly_pct=$(echo "scale=1; $weekly_used * 100 / $weekly_limit" | bc)
    echo -e "${BLUE}Weekly Limit:${NC}"
    echo -e "  Used: ${GREEN}$(echo "scale=0; $weekly_used / 1000" | bc)K${NC} / ${CYAN}$(echo "scale=0; $weekly_limit / 1000" | bc)K${NC} (${weekly_pct}%)"
    if (( $(echo "$weekly_pct > 70" | bc -l) )); then
        echo -e "  ${YELLOW}⚠ Moderate: ${weekly_pct}% of weekly limit${NC}"
    else
        echo -e "  ${GREEN}✓ OK${NC}"
    fi
    echo ""
    
    # Месячный лимит
    local monthly_pct=$(echo "scale=1; $monthly_used * 100 / $monthly_limit" | bc)
    echo -e "${BLUE}Monthly Limit:${NC}"
    echo -e "  Used: ${GREEN}$(echo "scale=0; $monthly_used / 1000" | bc)K${NC} / ${CYAN}$(echo "scale=0; $monthly_limit / 1000" | bc)K${NC} (${monthly_pct}%)"
    if (( $(echo "$monthly_pct > 70" | bc -l) )); then
        echo -e "  ${YELLOW}⚠ Moderate: ${monthly_pct}% of monthly limit${NC}"
    else
        echo -e "  ${GREEN}✓ OK${NC}"
    fi
    echo ""
}

# Рекомендации
show_recommendations() {
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Recommendations${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
    echo ""
    
    echo -e "${BLUE}Tips for optimizing context usage:${NC}"
    echo "  • Use /compact to summarize long sessions"
    echo "  • Archive completed tasks"
    echo "  • Use plan mode for complex tasks (read-only)"
    echo "  • Split large tasks into smaller sessions"
    echo ""
}

analyze_usage
show_recommendations

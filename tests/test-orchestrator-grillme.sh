#!/bin/bash

# Opencode Configuration Test Suite
# Tests orchestrator + grill-me integration

CONFIG_DIR="$HOME/.config/opencode"
TOTAL=0
PASSED=0
FAILED=0

pass() { echo "✓ PASS $1"; ((PASSED++)); ((TOTAL++)); }
fail() { echo "✗ FAIL $1"; ((FAILED++)); ((TOTAL++)); }

echo "=========================================="
echo "  Opencode Configuration Tests"
echo "=========================================="
echo ""

# [1/4] Orchestrator configuration
echo "[1/4] Orchestrator конфигурация"

if [ -f "$CONFIG_DIR/agents/orchestrator.md" ]; then
  pass "Файл agents/orchestrator.md существует"
else
  fail "Файл agents/orchestrator.md не найден"
fi

if jq -e '.agent.orchestrator' "$CONFIG_DIR/opencode.json" > /dev/null 2>&1; then
  pass "Агент orchestrator есть в opencode.json"
else
  fail "Агент orchestrator не найден в opencode.json"
fi

if jq -r '.agent.orchestrator.permission.skill // "deny"' "$CONFIG_DIR/opencode.json" | grep -q "allow"; then
  pass "orchestrator.permission.skill = allow"
else
  fail "orchestrator.permission.skill не allow"
fi

echo ""

# [2/4] Grill-me skill
echo "[2/4] Grill-me скилл"

if [ -d "$CONFIG_DIR/skills/grill-me" ]; then
  pass "Директория skills/grill-me/ существует"
else
  fail "Директория skills/grill-me/ не найдена"
fi

if [ -f "$CONFIG_DIR/skills/grill-me/SKILL.md" ]; then
  pass "Файл skills/grill-me/SKILL.md существует"
else
  fail "Файл skills/grill-me/SKILL.md не найден"
fi

if grep -q "name: grill-me" "$CONFIG_DIR/skills/grill-me/SKILL.md" 2>/dev/null; then
  pass "SKILL.md содержит name: grill-me"
else
  fail "SKILL.md не содержит name: grill-me"
fi

if grep -qi "триггер\|use when" "$CONFIG_DIR/skills/grill-me/SKILL.md" 2>/dev/null; then
  pass "SKILL.md содержит триггеры"
else
  fail "SKILL.md не содержит триггеры"
fi

echo ""

# [3/4] Global configuration
echo "[3/4] Глобальная конфигурация"

if jq empty "$CONFIG_DIR/opencode.json" 2>/dev/null; then
  pass "opencode.json - валидный JSON"
else
  fail "opencode.json - невалидный JSON"
fi

if jq -e '.default_agent == "orchestrator"' "$CONFIG_DIR/opencode.json" > /dev/null 2>&1; then
  pass "default_agent = orchestrator"
else
  fail "default_agent != orchestrator"
fi

SKILL_COUNT=$(ls -1 "$CONFIG_DIR/skills/" 2>/dev/null | wc -l)
if [ "$SKILL_COUNT" -ge 15 ]; then
  pass "Минимум 15 скиллов ($SKILL_COUNT найдено)"
else
  fail "Меньше 15 скиллов ($SKILL_COUNT найдено)"
fi

AGENT_COUNT=$(jq -r '.agent | keys | length' "$CONFIG_DIR/opencode.json" 2>/dev/null)
if [ "$AGENT_COUNT" -ge 3 ]; then
  pass "Минимум 3 агента ($AGENT_COUNT найдено)"
else
  fail "Меньше 3 агентов ($AGENT_COUNT найдено)"
fi

if jq -e '.mcp | keys | length > 0' "$CONFIG_DIR/opencode.json" > /dev/null 2>&1; then
  pass "Есть MCP серверы"
else
  fail "Нет MCP серверов"
fi

if [ -f "$CONFIG_DIR/plugins/aistats.js" ]; then
  pass "Плагин aistats.js существует"
else
  fail "Плагин aistats.js не найден"
fi

if [ -f "$CONFIG_DIR/plugins/herdr-agent-state.js" ]; then
  pass "Плагин herdr-agent-state.js существует"
else
  fail "Плагин herdr-agent-state.js не найден"
fi

echo ""

# [4/4] Models
echo "[4/4] Модели"

PROVIDER_COUNT=$(jq -r '.provider | keys | length' "$CONFIG_DIR/opencode.json" 2>/dev/null)
if [ "$PROVIDER_COUNT" -ge 4 ]; then
  pass "Минимум 4 провайдера ($PROVIDER_COUNT найдено)"
else
  fail "Меньше 4 провайдеров ($PROVIDER_COUNT найдено)"
fi

if jq -e '.provider."ecom-qwen35-122b"' "$CONFIG_DIR/opencode.json" > /dev/null 2>&1; then
  pass "Есть модель ecom-qwen35-122b"
else
  fail "Нет модели ecom-qwen35-122b"
fi

if jq -e '.provider."ecom-qwen36-35b"' "$CONFIG_DIR/opencode.json" > /dev/null 2>&1; then
  pass "Есть модель ecom-qwen36-35b"
else
  fail "Нет модели ecom-qwen36-35b"
fi

echo ""
echo "=========================================="
echo "  Results: $PASSED passed, $FAILED failed (Total: $TOTAL)"
echo "=========================================="

if [ $FAILED -eq 0 ]; then
  echo "All tests passed!"
  exit 0
else
  echo "Some tests failed!"
  exit 1
fi

#!/bin/bash
# Context Consistency Check
# Validates that context persistence is working correctly

set -e

CONFIG_DIR="$HOME/.config/opencode"
CONTEXT_FILE="/tmp/opencode-session-context.md"

echo "🔍 Context Consistency Check"
echo ""

# 1. Check if context file exists
if [ -f "$CONTEXT_FILE" ]; then
  echo "  ✓ Context file exists: $CONTEXT_FILE"
  
  # 2. Check if context has required sections
  REQUIRED_SECTIONS=(
    "Session Context"
    "Recent Error Patterns"
    "Zero-Rework Protocol Checklist"
  )
  
  MISSING_SECTIONS=0
  for SECTION in "${REQUIRED_SECTIONS[@]}"; do
    if grep -q "$SECTION" "$CONTEXT_FILE"; then
      echo "    ✓ Section: $SECTION"
    else
      echo "    ✗ Section: $SECTION (missing)"
      MISSING_SECTIONS=$((MISSING_SECTIONS + 1))
    fi
  done
  
  if [ $MISSING_SECTIONS -gt 0 ]; then
    echo ""
    echo "  ⚠ Context file is incomplete"
    echo "  Run context-persistence.sh to regenerate"
    exit 1
  fi
  
  # 3. Check context age
  CONTEXT_AGE=$(( ($(date +%s) - $(stat -c %Y "$CONTEXT_FILE")) / 60 ))
  if [ $CONTEXT_AGE -gt 1440 ]; then
    echo "  ⚠ Context is outdated ($CONTEXT_AGE minutes old)"
    echo "  Context should be refreshed daily"
    exit 1
  else
    echo "  ✓ Context age: $CONTEXT_AGE minutes (fresh)"
  fi
  
else
  echo "  ⚠ Context file not found: $CONTEXT_FILE"
  echo "  Run context-persistence.sh to create"
  exit 1
fi

echo ""
echo "✓ Context consistency check passed"
exit 0

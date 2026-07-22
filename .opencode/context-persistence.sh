#!/bin/bash
# Context Persistence Layer
# Injects relevant error patterns and lessons learned at session start

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/opencode"
CONTEXT_FILE="/tmp/opencode-session-context.md"

# Current task context
TASK_PROMPT="${1:-}"
TASK_TYPE="${2:-general}"

echo "🔄 Context Persistence: Loading session context..."

# 1. Check if aistats is available for error queries
if ! command -v aistats &> /dev/null; then
  echo "  ⚠ aistats not available, using static context"
  
  # Use static error patterns from prompts directory
  if [ -f "$CONFIG_DIR/prompts/error-patterns.md" ]; then
    cat "$CONFIG_DIR/prompts/error-patterns.md" > "$CONTEXT_FILE"
  else
    echo "# Session Context" > "$CONTEXT_FILE"
    echo "" >> "$CONTEXT_FILE"
    echo "No error patterns available. aistats not configured." >> "$CONTEXT_FILE"
  fi
else
  echo "  ✓ aistats available, querying recent errors..."
  
  # 2. Query error database for recent patterns
  # Note: This assumes aistats has an errors command - adjust based on actual API
  ERRORS=$(aistats errors --last 7days --format json 2>/dev/null || echo "[]")
  
  # 3. Build context file
  cat > "$CONTEXT_FILE" << EOF
# Session Context

## Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

## Task Type: ${TASK_TYPE}

---

## Recent Error Patterns (Last 7 Days)

\`\`\`json
${ERRORS}
\`\`\`

---

## Lessons from Similar Tasks

EOF

  # 4. Extract and format patterns (simplified - adjust based on actual aistats output)
  if [ "$ERRORS" != "[]" ] && [ -n "$ERRORS" ]; then
    echo "- Pattern detected in recent sessions - review before implementation" >> "$CONTEXT_FILE"
  else
    echo "- No recent error patterns for this task type" >> "$CONTEXT_FILE"
  fi
  
  echo "" >> "$CONTEXT_FILE"
  echo "---" >> "$CONTEXT_FILE"
  echo "" >> "$CONTEXT_FILE"
  echo "## Zero-Rework Protocol Checklist" >> "$CONTEXT_FILE"
  cat >> "$CONTEXT_FILE" << 'EOF'

Before implementing, verify:
- [ ] Spec is clear and complete
- [ ] Implementation plan reviewed
- [ ] Similar patterns from past sessions considered
- [ ] Pre-commit validation will pass
- [ ] Edge cases identified

---

## Context Injection Complete

Use this context to inform implementation decisions.
EOF
fi

# 5. Output context file path for agent to read
echo "  ✓ Context loaded: $CONTEXT_FILE"
echo "CONTEXT_FILE=$CONTEXT_FILE"

# 6. If task prompt provided, combine and output
if [ -n "$TASK_PROMPT" ]; then
  echo "" >> "$CONTEXT_FILE"
  echo "---" >> "$CONTEXT_FILE"
  echo "" >> "$CONTEXT_FILE"
  echo "## Original Task" >> "$CONTEXT_FILE"
  echo "$TASK_PROMPT" >> "$CONTEXT_FILE"
  
  echo "CONTEXT_MERGED=$CONTEXT_FILE"
fi

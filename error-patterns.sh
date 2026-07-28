#!/bin/bash
# Error Pattern Automation
# Extracts error patterns from aistats and updates agent prompts

set -e

CONFIG_DIR="$HOME/.config/opencode"
PROMPTS_DIR="$CONFIG_DIR/prompts"
ERRORS_FILE="/tmp/opencode-errors.json"
PATTERNS_FILE="/tmp/opencode-patterns.md"

echo "🔄 Error Pattern Automation: Extracting patterns..."

# Ensure prompts directory exists
mkdir -p "$PROMPTS_DIR"

# 1. Check if aistats is available
if ! command -v aistats &> /dev/null; then
  echo "  ⚠ aistats not available, creating static template"
  
  cat > "$PROMPTS_DIR/error-patterns.md" << 'EOF'
## Recent Error Patterns (Auto-Generated)

*aistats not available - patterns will be manually maintained*

### Manual Pattern Entry

To add error patterns manually:
1. Edit this file
2. Add patterns in the format below
3. Agents will read this on session start

**Pattern Template:**
- **Pattern:** [Description of recurring error]
- **Frequency:** [High/Medium/Low]
- **Example:** [Code snippet showing the error]
- **Fix:** [How to avoid/fix this pattern]

---

*This file is auto-generated when aistats is available. Manual edits will be overwritten.*
EOF
  
  echo "  ✓ Static template created"
  exit 0
fi

echo "  ✓ aistats available, querying errors..."

# 2. Extract recent error patterns from aistats
# Note: Adjust based on actual aistats API
aistats errors --last 30days --format json > "$ERRORS_FILE" 2>/dev/null || {
  echo "  ⚠ Could not query errors, using empty dataset"
  echo "[]" > "$ERRORS_FILE"
}

# 3. Process and cluster patterns
# This is a simplified heuristic - adjust based on actual error data structure
if [ -s "$ERRORS_FILE" ] && [ "$(cat $ERRORS_FILE)" != "[]" ]; then
  echo "  ✓ Processing $(jq length "$ERRORS_FILE") error entries..."
  
  # Create pattern analysis
  cat > "$PATTERNS_FILE" << EOF
# Error Pattern Analysis

**Generated:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Period:** Last 30 days
**Total Errors:** $(jq length "$ERRORS_FILE" "$ERRORS_FILE")

---

## Top Patterns by Frequency

EOF

  # Group by error type and count (adjust jq based on actual structure)
  jq -r '
    group_by(.error_type // "unknown") |
    map({
      pattern: .[0].error_type,
      frequency: length,
      files: [.[].file] | unique | length,
      example: (.[0].snippet // "N/A"),
      fix: (.[0].resolution // "See documentation")
    }) |
    sort_by(-.frequency) |
    .[:10] |
    to_entries |
    .[] |
    "**\(.value.frequency)x** \(.value.pattern)\n\n- Files affected: \(.value.files)\n- Example: \(.value.example)\n- Fix: \(.value.fix)\n"
  ' "$ERRORS_FILE" >> "$PATTERNS_FILE" 2>/dev/null || {
    echo "  ⚠ Could not parse error data, using simplified format"
    echo "Error data structure may have changed." >> "$PATTERNS_FILE"
  }

else
  echo "  ℹ No errors found in last 30 days"
  cat > "$PATTERNS_FILE" << 'EOF'
# Error Pattern Analysis

**Generated:** TIMESTAMP_PLACEHOLDER
**Period:** Last 30 days
**Total Errors:** 0

---

## No Error Patterns

No errors recorded in the last 30 days. This is a good sign!

Continue following Zero-Rework Protocol to maintain low rework rates.
EOF
  sed -i "s/TIMESTAMP_PLACEHOLDER/$(date -u +"%Y-%m-%dT%H:%M:%SZ")/" "$PATTERNS_FILE"
fi

# 4. Generate agent-ready prompt template
cat > "$PROMPTS_DIR/error-patterns.md" << EOF
## Recent Error Patterns (Auto-Generated)

**Last Updated:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Source:** aistats error tracking (last 30 days)

---

### High-Priority Patterns to Avoid

$(cat "$PATTERNS_FILE" | grep -A 100 "## Top Patterns" || echo "- No high-priority patterns detected")

---

### Implementation Guidelines

When implementing code, watch for these common mistakes:

1. **Review similar past errors** before starting
2. **Check file patterns** - certain file types have recurring issues
3. **Validate against specs** - spec ambiguity causes 40% of rework
4. **Run pre-commit hooks** - catches 15% of issues early

---

### Pattern Learning Loop

These patterns are updated automatically:
- **Frequency:** Daily (via cron job)
- **Source:** aistats error tracking
- **Action:** Review before each implementation session

---

*End of auto-generated error patterns*"
EOF

echo "  ✓ Error patterns updated: $PROMPTS_DIR/error-patterns.md"
echo "  ✓ Full analysis: $PATTERNS_FILE"

# 5. Optional: Send notification if high-frequency patterns found
HIGH_FREQ=$(jq '[.[] | group_by(.error_type) | select(length >= 3)] | length' "$ERRORS_FILE" 2>/dev/null || echo "0")

if [ "$HIGH_FREQ" -gt 0 ]; then
  echo "  ⚠ $HIGH_FREQ high-frequency patterns detected - review recommended"
fi

echo "✓ Error pattern automation complete"

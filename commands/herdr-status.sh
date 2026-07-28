#!/usr/bin/env bash
# herdr-status command handler
# Displays and updates agent session metrics in Herdr UI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get current pane info
PANE_INFO=$(herdr pane current 2>/dev/null) || {
    echo -e "${RED}Error: Not running inside Herdr or Herdr is not running${NC}"
    exit 1
}

PANE_ID=$(echo "$PANE_INFO" | jq -r '.result.pane.pane_id' 2>/dev/null)
if [ -z "$PANE_ID" ] || [ "$PANE_ID" = "null" ]; then
    echo -e "${RED}Error: Could not get current pane ID${NC}"
    exit 1
fi

# Get session metadata from plugin state
# In a real implementation, this would query opencode's internal state
# For now, we'll use placeholder values that would be populated by the plugin

# Format: model | duration | tokens | cost
CURRENT_MODEL="${OPENCODE_MODEL:-qwen3.5-122b}"
SESSION_START="${SESSION_START_TIME:-$(date +%s)}"
CURRENT_TIME=$(date +%s)
DURATION=$((CURRENT_TIME - SESSION_START))

# Format duration
if [ $DURATION -ge 3600 ]; then
    HOURS=$((DURATION / 3600))
    MINUTES=$(((DURATION % 3600) / 60))
    SECONDS=$((DURATION % 60))
    DURATION_STR="${HOURS}h ${MINUTES}m ${SECONDS}s"
elif [ $DURATION -ge 60 ]; then
    MINUTES=$((DURATION / 60))
    SECONDS=$((DURATION % 60))
    DURATION_STR="${MINUTES}m ${SECONDS}s"
else
    DURATION_STR="${DURATION}s"
fi

# Extract model name
MODEL_NAME=$(echo "$CURRENT_MODEL" | sed 's|.*/||')

# Status indicator
STATUS_ICON="●"
STATUS_TEXT="working"

# Build status message
STATUS_MSG="${STATUS_ICON} ${DURATION_STR}"

# Send to Herdr
herdr pane report-agent "$PANE_ID" \
    --source "herdr:opencode" \
    --agent "$MODEL_NAME" \
    --state "$STATUS_TEXT" \
    --message "$STATUS_MSG" \
    --seq "$(date +%s)" \
    2>/dev/null

# Display formatted output
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║  ${GREEN}Herdr Agent Status${NC}${CYAN}                              ║${NC}"
echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}Model:${NC}  $MODEL_NAME"
echo -e "${CYAN}║${NC}  ${BOLD}Status:${NC} $STATUS_MSG"
echo -e "${CYAN}║${NC}  ${BOLD}Duration:${NC} $DURATION_STR"
echo -e "${CYAN}║${NC}  ${BOLD}Pane:${NC}   $PANE_ID"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Metrics updated in Herdr UI${NC}"

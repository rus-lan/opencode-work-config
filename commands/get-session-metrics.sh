#!/usr/bin/env bash
# get-session-metrics.sh
# Fetches current session metrics from aistats and formats them for Herdr
# Returns valid JSON even when no session is active (exit 0)

set -uo pipefail

fallback() {
  cat <<EOF
{
    "model": "${MODEL:-unknown}",
    "duration": "0s",
    "tokens_in": "0",
    "tokens_out": "0",
    "cost": "\$0.00",
    "status": "unknown"
}
EOF
  exit 0
}

if command -v aistats &> /dev/null; then
    METRICS=$(aistats report --json 2>/dev/null) || {
      fallback
    }

    if [ -n "$METRICS" ]; then
        INPUT_TOKENS=$(echo "$METRICS" | jq -r '.totals.tokens.input // 0' 2>/dev/null)
        OUTPUT_TOKENS=$(echo "$METRICS" | jq -r '.totals.tokens.output // 0' 2>/dev/null)
        COST=$(echo "$METRICS" | jq -r '.totals.costUsd // 0' 2>/dev/null)
        DURATION_MS=$(echo "$METRICS" | jq -r '.totals.activeTimeMs // 0' 2>/dev/null)

        format_tokens() {
            local tokens=$1
            if [ "$tokens" -ge 1000000 ] 2>/dev/null; then
                echo "$(echo "scale=1; $tokens / 1000000" | bc 2>/dev/null)M"
            elif [ "$tokens" -ge 1000 ] 2>/dev/null; then
                echo "$((tokens / 1000))K"
            else
                echo "$tokens"
            fi
        }

        DURATION_MS=${DURATION_MS:-0}
        if [ "$DURATION_MS" -gt 0 ] 2>/dev/null; then
            DURATION_SEC=$((DURATION_MS / 1000))
            HOURS=$((DURATION_SEC / 3600))
            MINUTES=$(((DURATION_SEC % 3600) / 60))
            SECONDS=$((DURATION_SEC % 60))

            DURATION_STR=""
            [ "$HOURS" -gt 0 ] && DURATION_STR="${HOURS}h "
            [ "$MINUTES" -gt 0 ] && DURATION_STR="${DURATION_STR}${MINUTES}m "
            DURATION_STR="${DURATION_STR}${SECONDS}s"
        else
            DURATION_STR="0s"
        fi

        COST=${COST:-0}
        if [ "$(echo "$COST > 0" | bc 2>/dev/null)" -eq 1 ] 2>/dev/null; then
            if [ "$(echo "$COST < 0.01" | bc 2>/dev/null)" -eq 1 ] 2>/dev/null; then
                COST_STR=$(printf '\$%.4f' "$COST")
            else
                COST_STR=$(printf '\$%.2f' "$COST")
            fi
        else
            COST_STR="\$0.00"
        fi

        INPUT_FORMATTED=$(format_tokens "$INPUT_TOKENS")
        OUTPUT_FORMATTED=$(format_tokens "$OUTPUT_TOKENS")

        cat <<EOF
{
    "model": "${MODEL:-unknown}",
    "duration": "$DURATION_STR",
    "tokens_in": "$INPUT_FORMATTED",
    "tokens_out": "$OUTPUT_FORMATTED",
    "cost": "$COST_STR",
    "status": "active"
}
EOF
        exit 0
    fi
fi

fallback
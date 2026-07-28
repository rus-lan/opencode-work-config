#!/usr/bin/env bash
# get-session-metrics.sh
# Fetches current session metrics from aistats and formats them for Herdr

set -e

# Try to get metrics from aistats
if command -v aistats &> /dev/null; then
    METRICS=$(aistats report --format json 2>/dev/null) || METRICS=""
    
    if [ -n "$METRICS" ]; then
        # Parse metrics
        INPUT_TOKENS=$(echo "$METRICS" | jq -r '.tokens?.input // 0' 2>/dev/null)
        OUTPUT_TOKENS=$(echo "$METRICS" | jq -r '.tokens?.output // 0' 2>/dev/null)
        COST=$(echo "$METRICS" | jq -r '.costUsd // 0' 2>/dev/null)
        DURATION_MS=$(echo "$METRICS" | jq -r '.durationMs // 0' 2>/dev/null)
        
        # Format tokens
        format_tokens() {
            local tokens=$1
            if [ "$tokens" -ge 1000000 ]; then
                echo "$(echo "scale=1; $tokens / 1000000" | bc)M"
            elif [ "$tokens" -ge 1000 ]; then
                echo "$((tokens / 1000))K"
            else
                echo "$tokens"
            fi
        }
        
        # Format duration
        if [ "$DURATION_MS" -gt 0 ]; then
            DURATION_SEC=$((DURATION_MS / 1000))
            HOURS=$((DURATION_SEC / 3600))
            MINUTES=$(((DURATION_SEC % 3600) / 60))
            SECONDS=$((DURATION_SEC % 60))
            
            if [ $HOURS -gt 0 ]; then
                DURATION_STR="${HOURS}h ${MINUTES}m ${SECONDS}s"
            elif [ $MINUTES -gt 0 ]; then
                DURATION_STR="${MINUTES}m ${SECONDS}s"
            else
                DURATION_STR="${SECONDS}s"
            fi
        else
            DURATION_STR="0s"
        fi
        
        # Format cost
        if [ "$(echo "$COST > 0" | bc -l)" -eq 1 ]; then
            if [ "$(echo "$COST < 0.01" | bc -l)" -eq 1 ]; then
                COST_STR=$(printf '$%.4f' "$COST")
            else
                COST_STR=$(printf '$%.2f' "$COST")
            fi
        else
            COST_STR="$0.00"
        fi
        
        INPUT_FORMATTED=$(format_tokens "$INPUT_TOKENS")
        OUTPUT_FORMATTED=$(format_tokens "$OUTPUT_TOKENS")
        
        # Output as JSON for easy parsing
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
    else
        # Fallback to basic info
        cat <<EOF
{
    "model": "${MODEL:-unknown}",
    "duration": "0s",
    "tokens_in": "0",
    "tokens_out": "0",
    "cost": "$0.00",
    "status": "unknown"
}
EOF
    fi
else
    # aistats not available
    cat <<EOF
{
    "model": "${MODEL:-unknown}",
    "duration": "0s",
    "tokens_in": "0",
    "tokens_out": "0",
    "cost": "$0.00",
    "status": "unknown"
}
EOF
fi

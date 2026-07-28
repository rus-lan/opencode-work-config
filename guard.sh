#!/bin/bash
# Guard hook for opencode — protects against dangerous operations
# Source: adapted from claude-config global/hooks/guard.sh
# 
# Usage:
#   ./guard.sh <command>    — check if command is safe
#   ./guard.sh --install    — install as pre-commit hook
#
# Exit codes:
#   0 — safe (or needs user confirmation via normal permission system)
#   1 — blocked (compound command with dangerous operation)

set -euo pipefail

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

CMD="${1:-}"

# ── help ──
if [ -z "$CMD" ] || [ "$CMD" = "--help" ] || [ "$CMD" = "-h" ]; then
    echo "Guard — protection against dangerous compound commands"
    echo ""
    echo "Usage:"
    echo "  ./guard.sh <command>     Check if command is safe"
    echo "  ./guard.sh --install     Install as pre-commit hook"
    echo "  ./guard.sh --list        List dangerous patterns"
    echo ""
    echo "Exit codes:"
    echo "  0  Safe (or needs normal permission prompt)"
    echo "  1  Blocked (compound command with dangerous operation)"
    exit 0
fi

# ── install as pre-commit hook ──
if [ "$CMD" = "--install" ]; then
    HOOKS_DIR="$(git rev-parse --git-dir 2>/dev/null)/hooks"
    if [ -z "$HOOKS_DIR" ] || [ "$HOOKS_DIR" = "/hooks" ]; then
        echo "Not a git repository. Install manually."
        exit 1
    fi
    mkdir -p "$HOOKS_DIR"
    cat > "$HOOKS_DIR/pre-commit" << 'HOOK'
#!/bin/bash
# Guard pre-commit hook — runs before each commit
set -euo pipefail

# Check for TODO/FIXME/HACK markers
if git diff --cached | grep -E 'TODO|FIXME|HACK|XXX' | grep -v 'grep -E' ; then
    echo "⚠ WARNING: Commit contains TODO/FIXME/HACK markers"
fi

# Check for debug code
if git diff --cached | grep -E 'console\.log|print!|println!|fmt\.Print|debugger' | grep -v 'grep -E' | grep -v '//.*console'; then
    echo "⚠ WARNING: Commit contains debug statements"
fi

# Check for large files
MAX_SIZE=1048576  # 1MB
git diff --cached --name-only | while read file; do
    if [ -f "$file" ]; then
        size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)
        if [ "$size" -gt "$MAX_SIZE" ]; then
            echo "⚠ WARNING: Large file staged: $file (${size} bytes)"
        fi
    fi
done

echo "✓ Pre-commit checks passed"
HOOK
    chmod +x "$HOOKS_DIR/pre-commit"
    echo "Installed guard as pre-commit hook in $HOOKS_DIR"
    exit 0
fi

# ── list dangerous patterns ──
if [ "$CMD" = "--list" ]; then
    echo "Dangerous patterns (flagged in compound commands):"
    echo ""
    echo "  rm, unlink                       — file deletion"
    echo "  pip3 install, brew install       — package installation"
    echo "  cargo install, go install         — binary installation"
    echo "  wget, curl -o/-O                 — downloads"
    echo "  git push --force                 — destructive git"
    echo "  git reset --hard                 — destructive git"
    echo "  git clean -fdx                   — destructive git"
    echo ""
    echo "Simple commands pass through (normal permission system handles them)."
    echo "Compound commands (&&, ||, ;, $()) with dangerous ops are BLOCKED."
    exit 0
fi

# ── dangerous pattern check ──
has_dangerous() {
    local cmd="$1"
    # File deletion (excluding git rm)
    if echo "$cmd" | grep -qE '\brm\b' && ! echo "$cmd" | grep -qE '\bgit\s+rm\b'; then
        return 0
    fi
    echo "$cmd" | grep -qE '\bunlink\b' && return 0
    # Package/binary installation
    echo "$cmd" | grep -qE '\b(pip3?|brew|cargo|go)\s+install\b' && return 0
    # Downloads
    echo "$cmd" | grep -qE '\bwget\b' && return 0
    echo "$cmd" | grep -qE '\bcurl\b.*(-o\b|-O\b|--output\b)' && return 0
    # Destructive git
    echo "$cmd" | grep -qE 'git\s+push\s+.*--force' && return 0
    echo "$cmd" | grep -qE 'git\s+reset\s+--hard' && return 0
    echo "$cmd" | grep -qE 'git\s+clean\s+-[fdx]' && return 0
    return 1
}

# ── compound command detection ──
is_compound() {
    echo "$1" | grep -qE '&&|\|\||;|\$\(|`'
}

# ── main ──
if has_dangerous "$CMD"; then
    if is_compound "$CMD"; then
        echo -e "${RED}BLOCKED:${NC} Compound command contains a dangerous operation."
        echo "Split into separate commands so each can be reviewed."
        exit 1
    fi
fi

exit 0
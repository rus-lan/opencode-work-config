#!/bin/bash
# Commit Message Validation
# Ensures commit messages follow project standards

set -e

COMMIT_MSG_FILE="${1:-.git/COMMIT_EDITMSG}"

if [ ! -f "$COMMIT_MSG_FILE" ]; then
  echo "ℹ No commit message file provided, skipping"
  exit 0
fi

COMMIT_MSG=$(cat "$COMMIT_MSG_FILE")

# Extract subject line (first line)
SUBJECT=$(echo "$COMMIT_MSG" | head -1)

echo "🔍 Commit Message Validation"
echo ""

# 1. Check format: type(scope): description
if echo "$SUBJECT" | grep -qE "^(feat|fix|docs|style|refactor|test|chore)(\([a-z-]+\))?: .{1,70}$"; then
  echo "  ✓ Format: Valid"
else
  echo "  ✗ Format: Invalid"
  echo ""
  echo "  Expected: type(scope): description"
  echo "  Examples:"
  echo "    feat(auth): add JWT token refresh"
  echo "    fix(ui): resolve dropdown z-index issue"
  echo "    refactor(api): simplify error handling"
  exit 1
fi

# 2. Check for forbidden content in subject
FORBIDDEN_PATTERNS=(
  "fix the"
  "fixes the"
  "fixed the"
  "bug fix"
  "without this"
  "this fixes"
  "resolve the"
  "solves the"
)

FORBIDDEN_FOUND=0
for PATTERN in "${FORBIDDEN_PATTERNS[@]}"; do
  if echo "$SUBJECT" | grep -qi "$PATTERN"; then
    echo "  ✗ Contains forbidden pattern: '$PATTERN'"
    FORBIDDEN_FOUND=1
  fi
done

if [ $FORBIDDEN_FOUND -eq 0 ]; then
  echo "  ✓ Content: No problem narratives"
else
  echo ""
  echo "  Commit messages should describe WHAT changed, not WHY or the problem."
  echo "  See CLAUDE.md for commit message guidelines."
  exit 1
fi

# 3. Check body length (if present)
BODY_LINES=$(echo "$COMMIT_MSG" | tail -n +2 | grep -v "^$" | wc -l)
if [ $BODY_LINES -gt 2 ]; then
  echo "  ⚠ Body: Too long ($BODY_LINES lines, max 2 recommended)"
  echo "  Commit messages should be concise - the diff carries the detail."
else
  echo "  ✓ Body: Appropriate length"
fi

echo ""
echo "✓ Commit message validation passed"
exit 0

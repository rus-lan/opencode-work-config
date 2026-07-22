#!/bin/bash
# Pre-commit validation suite for Zero-Rework Protocol
# Run as: .git/hooks/pre-commit or manually before commits

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Zero-Rework Pre-commit Validation"
echo "=========================================="

FAILED=0
WARNINGS=0

# 1. Syntax/Type checks
echo -n "  [1/6] Type checking... "
if command -v npx &> /dev/null && [ -f "tsconfig.json" ]; then
  if npx tsc --noEmit 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
  else
    echo -e "${RED}✗${NC}"
    FAILED=$((FAILED + 1))
  fi
else
  echo -e "${YELLOW}⚠ skipped (no tsconfig)${NC}"
  WARNINGS=$((WARNINGS + 1))
fi

# 2. Lint
echo -n "  [2/6] Linting... "
if command -v npx &> /dev/null && [ -f "package.json" ]; then
  if npx eslint --quiet . 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
  else
    echo -e "${RED}✗${NC}"
    FAILED=$((FAILED + 1))
  fi
else
  echo -e "${YELLOW}⚠ skipped (no package.json)${NC}"
  WARNINGS=$((WARNINGS + 1))
fi

# 3. Test
echo -n "  [3/6] Running tests... "
if command -v npx &> /dev/null && [ -f "package.json" ]; then
  if npm test -- --passWithNoTests --maxWorkers=2 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
  else
    echo -e "${RED}✗${NC}"
    FAILED=$((FAILED + 1))
  fi
else
  echo -e "${YELLOW}⚠ skipped (no tests)${NC}"
  WARNINGS=$((WARNINGS + 1))
fi

# 4. Spec traceability
echo -n "  [4/6] Checking spec coverage... "
if [ -f ".opencode/traceability-check.sh" ]; then
  if bash .opencode/traceability-check.sh 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
  else
    echo -e "${YELLOW}⚠ issues found${NC}"
    WARNINGS=$((WARNINGS + 1))
  fi
else
  echo -e "${YELLOW}⚠ skipped (no traceability script)${NC}"
  WARNINGS=$((WARNINGS + 1))
fi

# 5. Context consistency
echo -n "  [5/6] Validating context persistence... "
if [ -f ".opencode/context-check.sh" ]; then
  if bash .opencode/context-check.sh 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
  else
    echo -e "${YELLOW}⚠ context issues${NC}"
    WARNINGS=$((WARNINGS + 1))
  fi
else
  echo -e "${YELLOW}⚠ skipped (no context check)${NC}"
  WARNINGS=$((WARNINGS + 1))
fi

# 6. Commit message format (if commit message file provided)
echo -n "  [6/6] Validating commit message... "
if [ -n "$1" ] && [ -f "$1" ]; then
  COMMIT_MSG=$(cat "$1")
  # Check for proper format: type(scope): description
  if echo "$COMMIT_MSG" | grep -qE "^(feat|fix|docs|style|refactor|test|chore)(\([a-z-]+\))?: .{1,70}"; then
    echo -e "${GREEN}✓${NC}"
  else
    echo -e "${RED}✗${NC}"
    echo "  Commit message should follow: type(scope): description"
    echo "  Example: feat(auth): add JWT token refresh"
    FAILED=$((FAILED + 1))
  fi
else
  echo -e "${YELLOW}⚠ skipped (no commit message)${NC}"
  WARNINGS=$((WARNINGS + 1))
fi

echo "=========================================="

if [ $FAILED -gt 0 ]; then
  echo -e "${RED}✗ Pre-commit validation FAILED${NC}"
  echo "  $FAILED error(s), $WARNING warning(s)"
  echo "  Fix errors before committing."
  exit 1
fi

if [ $WARNINGS -gt 0 ]; then
  echo -e "${YELLOW}⚠ Pre-commit validation PASSED with warnings${NC}"
  echo "  $WARNINGS warning(s) - consider addressing"
else
  echo -e "${GREEN}✓ Pre-commit validation PASSED${NC}"
fi

exit 0

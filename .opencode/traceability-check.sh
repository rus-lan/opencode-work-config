#!/bin/bash
# Spec Traceability Check
# Verifies that all spec requirements have corresponding implementation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC_DIR="${SPEC_DIR:-specs}"
CODE_DIR="${CODE_DIR:-.}"

echo "🔍 Traceability Check: Scanning for requirement coverage..."

# 1. Find spec files
SPEC_FILES=$(find "$SPEC_DIR" -name "*.md" -type f 2>/dev/null | grep -v template)

if [ -z "$SPEC_FILES" ]; then
  echo "  ℹ No spec files found in $SPEC_DIR"
  echo "  ℹ Skipping traceability check"
  exit 0
fi

echo "  ✓ Found $(echo "$SPEC_FILES" | wc -l) spec file(s)"

# 2. Extract requirements and check coverage
TOTAL_REQUIREMENTS=0
COVERED_REQUIREMENTS=0
MISSING_REQUIREMENTS=0

echo ""
echo "## Traceability Matrix"
echo ""

for SPEC_FILE in $SPEC_FILES; do
  SPEC_NAME=$(basename "$SPEC_FILE" .md)
  echo "### $SPEC_NAME"
  echo ""
  
  # Extract acceptance criteria (Given/When/Then format)
  REQUIREMENTS=$(grep -E "^\- \*\*\[x\]\*\*|^\- \*\*\[ \]\*\*" "$SPEC_FILE" 2>/dev/null || true)
  
  if [ -z "$REQUIREMENTS" ]; then
    echo "  ℹ No requirements found in $SPEC_FILE"
    continue
  fi
  
  echo "$REQUIREMENTS" | while read -r REQ; do
    TOTAL_REQUIREMENTS=$((TOTAL_REQUIREMENTS + 1))
    
    # Extract requirement text (remove checkbox)
    REQ_TEXT=$(echo "$REQ" | sed 's/^- \*\*\[.\]\*\* //' | cut -c1-50)
    
    # Check if requirement is implemented (search codebase)
    # This is a simplified check - adjust based on your codebase
    if grep -r "$REQ_TEXT" "$CODE_DIR" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.go" --include="*.rs" 2>/dev/null | grep -v ".git" | head -1; then
      echo "  ✓ $REQ_TEXT"
      COVERED_REQUIREMENTS=$((COVERED_REQUIREMENTS + 1))
    else
      # Check for partial matches (requirement keywords)
      KEYWORDS=$(echo "$REQ_TEXT" | tr ' ' '\n' | grep -vE "^(the|a|an|and|or|but|in|on|at|to|for)$" | head -3)
      FOUND=0
      
      for KEYWORD in $KEYWORDS; do
        if grep -r "$KEYWORD" "$CODE_DIR" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.go" --include="*.rs" 2>/dev/null | grep -v ".git" | grep -v "node_modules" | head -1; then
          FOUND=1
          break
        fi
      done
      
      if [ $FOUND -eq 1 ]; then
        echo "  ~ $REQ_TEXT (partial match)"
        COVERED_REQUIREMENTS=$((COVERED_REQUIREMENTS + 1))
      else
        echo "  ✗ $REQ_TEXT (NOT FOUND)"
        MISSING_REQUIREMENTS=$((MISSING_REQUIREMENTS + 1))
      fi
    fi
  done
  
  echo ""
done

# 3. Summary
echo "## Summary"
echo ""
echo "| Metric | Count |"
echo "|--------|-------|"
echo "| Total Requirements | $TOTAL_REQUIREMENTS |"
echo "| Covered | $COVERED_REQUIREMENTS |"
echo "| Missing | $MISSING_REQUIREMENTS |"
echo "| Coverage | $(if [ $TOTAL_REQUIREMENTS -gt 0 ]; then echo "$((COVERED_REQUIREMENTS * 100 / TOTAL_REQUIREMENTS))%"; else echo "N/A"; fi) |"
echo ""

# 4. Exit with appropriate code
if [ $MISSING_REQUIREMENTS -gt 0 ]; then
  echo "⚠ $MISSING_REQUIREMENTS requirement(s) not found in code"
  echo "  Review before committing."
  exit 0  # Warning, not failure
else
  echo "✓ All requirements traced to implementation"
  exit 0
fi

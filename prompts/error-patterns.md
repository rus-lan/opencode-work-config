## Recent Error Patterns (Auto-Generated)

*Initial template - will be populated by error-patterns.sh when aistats is available*

---

### Manual Pattern Entry (Until Auto-Generation Works)

To add error patterns manually:

**Pattern Template:**
- **Pattern:** [Description of recurring error]
- **Frequency:** [High/Medium/Low]
- **Example:** [Code snippet showing the error]
- **Fix:** [How to avoid/fix this pattern]

---

### Known Patterns (Manual)

Based on 21 rework loops analysis:

1. **Pattern:** Context loss between sessions
   - **Frequency:** High
   - **Example:** Agent forgets lessons learned from previous file
   - **Fix:** Use context-persistence.sh to inject past errors at session start

2. **Pattern:** Spec ambiguity leads to misimplementation
   - **Frequency:** High
   - **Example:** "Add authentication" → agent chooses JWT, spec expected cookies
   - **Fix:** Use spec template with explicit acceptance criteria

3. **Pattern:** Style violations caught in review
   - **Frequency:** Medium
   - **Example:** Verbose naming (`computeOptimalStrategyParams` vs `calcStrategyParams`)
   - **Fix:** Review CLAUDE.md naming section before implementation

4. **Pattern:** Missing edge cases
   - **Frequency:** Medium
   - **Example:** Error handling not implemented for network failures
   - **Fix:** Use spec template's edge case section

5. **Pattern:** Code style drift
   - **Frequency:** Medium
   - **Example:** Inconsistent error handling patterns across files
   - **Fix:** Run pre-commit hooks before review

---

### Implementation Guidelines

When implementing code, watch for these common mistakes:

1. **Review similar past errors** before starting
2. **Check file patterns** - certain file types have recurring issues
3. **Validate against specs** - spec ambiguity causes 40% of rework
4. **Run pre-commit hooks** - catches 15% of issues early

---

*This file is auto-generated when aistats is available. Manual edits will be overwritten.*
*Run: `.opencode/error-patterns.sh` to regenerate from aistats data*

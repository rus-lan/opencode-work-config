---
name: bmad-check-implementation-readiness
version: 1.0.0
description: |
  Verify that a phase is ready for implementation: acceptance criteria defined, dependencies resolved, design reviewed, test plan ready.
license: MIT
compatibility: opencode
allowed-tools:
  - Read
  - Glob
  - Grep
---

# BMAD — Check Implementation Readiness

Invocation: `/bmad-check-implementation-readiness <phase>`

## When to use

- After epics are created and gated by `fable-second-opinion`
- Before starting sprint planning
- Anytime the team needs a readiness checkpoint

## Workflow

### 1. Load artifacts
- `<project>/.bmad/KICKOFF-<phase>.md`
- `<project>/.bmad/epics-<phase>.md`
- Any related design docs or ADRs

### 2. Run readiness checklist

| # | Check | Pass/Fail |
|---|-------|-----------|
| 1 | Scope contract fully covered by epics | |
| 2 | Every story has acceptance criteria | |
| 3 | No hidden dependencies between epics | |
| 4 | Epic execution order is defined | |
| 5 | Design reviewed (ADR or equivalent) | |
| 6 | Test strategy defined per story class | |
| 7 | External dependencies resolved | |
| 8 | Environment / credentials ready | |
| 9 | Risk classification applied to all stories | |
| 10 | Canary slice identified per epic | |

### 3. Diagnose failures
For each failed check:
- Describe what's missing
- Suggest remediation steps
- Estimate effort to fix

### 4. Report
Output a structured readiness report:

```markdown
## Readiness Report: <phase>

### ✅ Passed
- ...

### ❌ Blocking
- [ ] Item 1: <what's missing> → <remediation>
- [ ] Item 2: ...

### ⚠ Warnings
- ...

### Verdict
READY / NOT READY (list blocking items)
```

## Output

- Readiness report (printed to session, optionally saved to `.bmad/readiness-<phase>.md`)
- Verdict: READY or NOT READY with clear blocking items

## Principles

- **Blocking items must be resolved** before sprint planning starts
- **Warnings are advisory** — team may proceed but should address them
- **Re-run after fixing** to confirm readiness
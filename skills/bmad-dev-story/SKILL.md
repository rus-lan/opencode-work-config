---
name: bmad-dev-story
version: 1.0.0
description: |
  Develop a BMAD story: implement code, write tests, verify against acceptance criteria, and run review by risk class.
license: MIT
compatibility: opencode
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Agent
---

# BMAD — Dev Story

Invocation: `/bmad-dev-story <story-id|story-file>`

## When to use

- During sprint execution for each story
- After `bmad-create-story` has fleshed out the story
- When a story needs implementation + test + review in one cycle

## Workflow

### 1. Load story
- Read the detailed story file or epics file entry
- Read sprint status for context and dependencies
- Load relevant codebase files and coding standards

### 2. Implement
- Create/modify source files following the story's technical notes
- Follow project conventions (lint, typecheck, naming)
- Apply fail-closed defaults from the start
- Keep changes minimal — one story = one vertical slice

### 3. Write tests
- Unit tests for business logic
- Integration tests for API/DB boundaries
- Edge cases from acceptance criteria
- Run tests to confirm green

### 4. Verify acceptance criteria
Check each acceptance criterion:
- Is the behavior implemented?
- Do tests cover it?
- Are edge cases handled?

### 5. Review by risk class

#### Ordinary story (обычная)
- Self-review: re-read the diff against acceptance criteria
- Verify: tests pass, lint clean, typecheck clean
- No need for full code review agent

#### CR-required story (CR-обязателен)
- Run full code review via reviewer agent
- Address findings
- Re-check before marking done

### 6. Update sprint status
Mark story as done in `sprint-status-<phase>.yaml`:
```yaml
  - id: "1.1"
    status: done
    review_log:
      review_type: self-review | full-CR
      passed: true
      notes: "..."
```

## Output

- Implemented code (source changes)
- Tests (passing)
- Acceptance criteria verified (pass/fail per criterion)
- Updated sprint status file

## Principles

- **Canary first**: first story of an epic is the narrowest slice to validate the approach
- **Batching**: 2-3 small related stories can share one dev session, but each AC checked separately
- **No red tests**: never mark a story done on failing tests
- **Self-review is real**: read your own diff critically, don't skip it
- **Fail-closed**: security invariants are implemented in the first pass, not deferred
---
name: bmad-create-story
version: 1.0.0
description: |
  Create a detailed user story from an epic stub: define acceptance criteria, add technical notes, identify blocking edges and risk class.
license: MIT
compatibility: opencode
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Agent
---

# BMAD — Create Story

Invocation: `/bmad-create-story <epic-file> <story-id>`

## When to use

- During sprint execution, before developing a story
- When a story stub in the epics file needs to be fleshed out
- As preparation for `bmad-dev-story`

## Workflow

### 1. Load context
- Epics file (`epics-<phase>.md`)
- Sprint status file (to confirm this story is next)
- Relevant design docs, ADRs, and rules

### 2. Flesh out the story

#### Story template

```markdown
## Story <id>: <title>

**Epic**: <epic-name>
**Class**: <обычная | CR-обязателен>
**Depends on**: <story-ids that must be done first>
**Blocks**: <story-ids that depend on this>

### Acceptance Criteria
- [ ] Criterion 1: <concrete, testable behavior>
- [ ] Criterion 2: ...
- [ ] Edge case: <what happens with empty/null/error input>

### Technical Notes
- <implementation guidance>
- <relevant files or modules>
- <migration steps if any>
- <testing approach>

### Security & Risk
- [ ] Data validation / sanitization
- [ ] Auth checks (if applicable)
- [ ] Fail-closed behavior
- [ ] Rate limiting (if public endpoint)

### Definition of Done
- [ ] Code implemented
- [ ] Tests pass
- [ ] Lint/typecheck clean
- [ ] Acceptance criteria verified
- [ ] Self-review done
- [ ] Code review passed (if CR-обязателен)
```

### 3. Apply risk classification
Check against CR-required triggers:
- Money/ledger
- Secrets/crypto
- DB schema/migrations
- Public contracts (proto, REST, error enums)
- Security invariants
- Compute-split values

If any trigger matches, mark class as `CR-обязателен`.

### 4. Update artifacts
- Add detailed story to epics file or create separate story file in `.bmad/stories/`
- Update sprint status file with the refined story

## Output

- Fleshed-out story with full acceptance criteria and technical notes
- Updated sprint status file
- New story file in `.bmad/stories/` (if using separate files)

## Principles

- **Testable criteria**: each acceptance criterion must be verifiable (pass/fail)
- **Edges explicit**: edge cases are part of acceptance criteria, not an afterthought
- **One story = one vertical slice**: not a layer, not a component — a feature end-to-end
- **CR classification**: better to over-classify than miss a dangerous story
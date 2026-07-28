---
name: bmad-create-epics
version: 1.0.0
description: |
  Decompose a high-level specification into epics — major feature areas with coverage mapping against the scope contract.
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

# BMAD — Create Epics

Invocation: `/bmad-create-epics <spec-file|phase>`

## When to use

- After a kickoff file has been created for a phase
- When a spec or PRD needs to be decomposed into epics before writing individual stories

## Workflow

### 1. Read the spec and kickoff
- Load `<project>/.bmad/KICKOFF-<phase>.md`
- Load the PRD or spec document the phase is based on
- Identify the scope contract boundaries (what's in, what's out)

### 2. Identify epics
Each epic is a major feature area. Group by:
- **Layer**: frontend, backend, infra, data
- **Domain**: user management, billing, search, notifications
- **Dependency order**: which epics must come before others

### 3. Create coverage map
Map every line item of the scope contract to an epic. Ensure no gaps.

### 4. Write epics file
Create `<project>/.bmad/epics-<phase>.md`:

```markdown
# Epics: <phase>

## Epic 1: <name>
- [ ] Story 1.1: <description> [class: обычная]
- [ ] Story 1.2: <description> [class: CR-обязателен]
...

## Epic 2: <name>
...
```

### 5. Update README
Add the new epics file to `implementation-artifacts/README.md`.

## Output

- `<project>/.bmad/epics-<phase>.md` — epic breakdown with story stubs
- Coverage map (inline or separate) showing scope contract → epic mapping
- Updated `implementation-artifacts/README.md`

## Principles

- **Full coverage**: every scope contract item maps to at least one story
- **Dependency-aware**: epics are ordered so no epic depends on work not yet done
- **Canary first**: the first story of each epic is a narrow slice
- **Risk classification**: each story gets a class tag (`обычная` or `CR-обязателен`)
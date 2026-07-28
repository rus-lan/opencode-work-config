---
name: bmad-sprint-planning
version: 1.0.0
description: |
  Sprint planning for BMAD phases: prioritize stories by dependency and risk, estimate effort, assign to agents, produce sprint status file.
license: MIT
compatibility: opencode
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# BMAD — Sprint Planning

Invocation: `/bmad-sprint-planning <phase>`

## When to use

- After readiness check passes
- At the start of each sprint within a phase
- When re-planning mid-sprint (re-prioritization)

## Workflow

### 1. Load input artifacts
- `<project>/.bmad/epics-<phase>.md`
- Readiness report (if available)
- Previous sprint status (if re-planning)

### 2. Prioritize stories
Rules for ordering:
- **Dependency first**: stories that unblock others go first
- **Canary first**: first story of each epic is the narrowest slice
- **Risk-adjusted**: high-risk stories started early to surface issues
- **Value-driven**: highest user/value stories get priority within dependency constraints

### 3. Estimate effort
Use t-shirt sizing or story points:

| Size | Effort | Example |
|------|--------|---------|
| XS | <1h | Config change, trivial rename |
| S | 1-3h | Single endpoint, simple component |
| M | 3-8h | Full feature with tests |
| L | 1-3d | Cross-cutting change, migration |
| XL | 3-5d | Large feature, needs decomposition |

### 4. Assign stories
- Each story assigned to a dev agent (or "unassigned")
- CR-required stories annotated with reviewer requirements

### 5. Write sprint status file
Create `<project>/.bmad/sprint-status-<phase>.yaml`:

```yaml
phase: <phase>
sprint: <N>
status: active

stories:
  - id: "1.1"
    title: "..."
    epic: 1
    class: обычная
    assignee: <agent>
    estimate: S
    status: pending  # pending | in-progress | review | done

  - id: "1.2"
    title: "..."
    epic: 1
    class: CR-обязателен
    assignee: <agent>
    reviewer: reviewer-arch
    estimate: M
    status: pending

epic_order:
  - 1
  - 2
  - ...
```

## Output

- `<project>/.bmad/sprint-status-<phase>.yaml` — sprint plan
- Ordered backlog for the sprint

## Principles

- **One sprint per phase** for small phases; large phases may have multiple sprints
- **Update after each story**: mark status (`pending → in-progress → review → done`)
- **Re-plan on discovery**: if a story turns out larger than estimated, split it
- **Don't over-estimate**: prefer splitting large stories over XL estimates
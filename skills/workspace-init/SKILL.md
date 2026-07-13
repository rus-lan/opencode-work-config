---
name: workspace-init
version: 2.3.0
description: Create a workspace wrapper for any project — isolates Claude config from app repos, supports single and multi-app setups, optional methodology initialization
user-invocable: true
---

# Workspace Init — Create a Workspace Wrapper for Any Project

Create a workspace directory that wraps one or more applications under `apps/`, with Claude configuration at the workspace root — isolated from app repositories. Each app inside `apps/` is an independent git repository.

## When to use

Run `/workspace-init` for **any** project — single-app or multi-app. The workspace wrapper ensures:
- Claude config (rules, CLAUDE.md) lives **above** the app, never pollutes the app's git
- Each app in `apps/` is a git submodule (added later via `git submodule add`)
- `apps/` is tracked by workspace git — empty dirs use `.gitkeep` as placeholders
- Routing rules dispatch to specialist agents per app directory
- Scoped rules (each rule applies only to its app's files)
- Optional project methodology (GSD, BMAD) or skills plugin (Superpowers) initialized at workspace root
- Makefile with `clone` target for submodule initialization
- Cross-app coordination guidelines (for multi-app setups)

Works equally well for a single React app or a full monorepo with Go backend + React frontend + Tauri desktop.

**Re-run safe:** If the workspace is already initialized, skips structure creation and offers to add methodologies or apps.

## Step 0 — Detect Existing Workspace

Check if the current directory is already an initialized workspace by looking for `CLAUDE.md` at root containing `<!-- workspace-meta` marker.

**If workspace already exists:**
1. Read `CLAUDE.md` and parse the `<!-- workspace-meta ... -->` block to understand current state
2. Show: "Workspace `<name>` already initialized. Apps: <list>. Methodologies: <list or none>."
3. Offer: "What would you like to do? (add-app / add-methodology / reinitialize)"
   - `add-app` → jump to Step 2 (select apps), then Step 5 (install rules), update CLAUDE.md
   - `add-methodology` → jump to Step 3 (methodology selection only)
   - `reinitialize` → warn "This will regenerate CLAUDE.md and rules. Apps and methodologies are preserved." then proceed from Step 1

**If NOT a workspace:** proceed to Step 1.

## Step 1 — Ensure Central Repo Exists

The central config repo must be at `~/claude-config/`.

**If NOT found:**
Clone it:
```
git clone git@github.com:rus-lan/claude-config.git ~/claude-config
```
If SSH fails, try HTTPS:
```
git clone https://github.com/rus-lan/claude-config.git ~/claude-config
```
If both fail, ask the user for the correct repo URL.

After cloning, run `~/claude-config/install.sh` to set up global config.

**If found:**
Run `git -C ~/claude-config pull` to ensure it's up to date.

## Step 2 — Gather Workspace Info & Select Applications

### Workspace name

1. If `$ARGUMENTS` is provided, use it as the workspace name
2. Otherwise, ask the user for a name

**Location logic:**
- If cwd is empty (no files except `.git/`): use cwd as workspace root
- If cwd has files: abort with message — "This directory is not empty. Create an empty directory first or clean this one."
- If name differs from cwd directory name: create a subdirectory with that name

### Application selection

Present the app type registry:

```
Available app types:

  react      — React frontend (Vite, Tailwind v4, shadcn/ui)
  react-i18n — React frontend + internationalization (i18next)
  nextjs     — Next.js full-stack web app
  go         — Go backend service (Gin, slog, sqlc)
  rust       — Rust backend/library (Axum, Tokio)
  tauri      — Tauri desktop app (Rust + React)
  custom     — Custom app (you specify stack and agent)

Which apps does this workspace need? (e.g., "go, react" or "go backend, react frontend")
```

### App Type Registry

| Type | Agent | Rules | Default dir |
|------|-------|-------|-------------|
| react | react-dev | frontend-components, frontend-hooks, frontend-theme | frontend |
| react-i18n | react-dev | frontend-components, frontend-hooks, frontend-theme, frontend-i18n | frontend |
| nextjs | react-dev | frontend-components, frontend-hooks, frontend-theme | web |
| go | go-dev | go-backend | backend |
| rust | rust-dev | rust-errors, rust-logging, rust-testing | backend |
| tauri | tauri-dev | tauri-bridge, rust-errors, rust-logging, rust-testing, frontend-components, frontend-hooks, frontend-theme | desktop |
| custom | (ask user) | (ask user) | (ask user) |

**For each selected app, ask:**
1. **Directory name** under `apps/` — default from registry, user can override (e.g., `go` app as `api` instead of `backend`)
2. **Source** — one of:
   - `new` — create empty directory with `.gitkeep` (default). Submodule added later
   - `<git-url>` — add as git submodule via `git submodule add <url> apps/<name>`

**Conflict detection:**
- If `tauri` is selected alongside standalone `react` or `rust`, warn: "Tauri already includes React + Rust. Do you want separate apps, or just Tauri?"
- If two apps would get the same default directory name (e.g., two `go` apps both default to `backend`), require explicit names

## Step 3 — Select Methodologies

Present available methodologies:

```
Project methodologies & skill frameworks (optional, can add later with /workspace-init):

  [ ] GSD     — Get Shit Done (open-gsd fork) → spec-driven, fights context rot
      Install: npx @opengsd/gsd-core@latest   (installer asks runtime + local/global)
      Docs:    https://www.opengsd.net/  ·  https://github.com/open-gsd/get-shit-done-redux
      Note:    use the open-gsd fork. The old get-shit-done-cc / gsd-pi packages are
               abandoned (original author left after a trust incident).

  [ ] BMAD    — Breakthrough Method for Agile AI-Driven Development → creates _bmad/, _bmad-output/
      Install: npx bmad-method install
      Docs:    https://docs.bmad-method.org/

  [ ] Superpowers — agentic skills plugin (TDD, systematic-debugging, git-worktrees,
      brainstorm, plan, code-review). A per-task BEHAVIOR layer, NOT a project process.
      Install: global Claude Code plugin (run inside Claude Code, not bash) — see Step 7.
      Docs:    https://github.com/obra/superpowers
      Note:    pairs on top of BMAD/GSD — methodology owns planning/docs, Superpowers
               owns implementation (TDD / worktrees / review).

  [ ] None    — skip for now

Which to initialize? (e.g., "bmad, superpowers" or "gsd" or "none")
```

Multiple selections are allowed. **Never run two PROCESS methodologies at once:** if the user selects both GSD and BMAD, warn: "GSD and BMAD are competing project processes — pick one. Superpowers is a separate behavior layer and can sit on top of either."

## Step 4 — Confirm Plan

Show a summary and ask for confirmation:

```
Workspace: <name>
Location:  <absolute-path>

Apps (each is an independent git repo):
  apps/<dir1>/  — <Type> (<agent> agent, <N> rules) [new | clone: <url>]
  apps/<dir2>/  — <Type> (<agent> agent, <N> rules) [new | clone: <url>]

Rules to install (.claude/rules/):
  <rule-name>.md  — scoped to apps/<dir>/
  ...

Methodologies:
  <methodology-name>  — <what it creates>
  ...
  (or: none selected)

Will also create:
  CLAUDE.md          — workspace brain (routing + coordination) at root
  .gitignore         — workspace defaults

Proceed? (yes / edit / cancel)
```

- `yes` — continue
- `edit` — go back to Step 2
- `cancel` — abort

## Step 5 — Create Workspace Structure

Execute in order:

1. Create workspace directory if not using cwd
2. Initialize git in workspace root: run `git init` (safe if `.git/` already exists — git will just reinitialize)
3. Create `apps/` directory (tracked by workspace git)
4. For each app:
   - **If new:** create `apps/<name>/` with a `.gitkeep` file. Do NOT run `git init` inside — the directory is a placeholder for a future git submodule
   - **If git URL:** run `git submodule add <url> apps/<name>` to add as a git submodule
   - If submodule add fails (auth, URL issue): report error, create empty dir with `.gitkeep` instead
5. Create `Makefile` at workspace root with a `clone` target for submodule initialization:

```makefile
.PHONY: clone

clone:
	git submodule init
	git submodule update --recursive
```

6. Create `.gitignore` at workspace root:

```
# OS
.DS_Store

# Editor
*.backup

# Dependencies & build
node_modules/
target/
dist/
build/

# Environment
.env
.env.local
```

**Important:** Do NOT ignore `apps/`, `.research/`, `_bmad-output/`, `.planning/`, `.gsd/`, or any other methodology/research directories. The workspace tracks ALL of this in git. `apps/` contains submodule references (or `.gitkeep` placeholders) and must be in version control.

## Step 6 — Install Rules

**Delegate rule installation to the rules manager. Never copy rule files or edit their frontmatter by hand.**

Tell the user to run, from the workspace root, and check the rules for their apps:

`! node ~/claude-config/bin/rules-manage.mjs`

The `!` prefix runs the command in the current Claude Code session so the user sees the interactive UI directly. The script:
1. Detects the workspace (from `<!-- workspace-meta` in CLAUDE.md, falling back to scanning `apps/` on disk) and each app's stack from marker files
2. Matches rules to apps by stack and shows the matching for confirmation (with a manual app-picker fallback)
3. Resolves `path_hints:` into concrete `paths:` prefixed with `apps/<dir>/` for every target app
4. Writes one file per rule under the original central filename, with `name:` and `version:` intact — `version:` is required for later `--update` runs, and the exact filename is how the script recognizes installed rules

If apps are still empty placeholder directories at this point, stack detection finds nothing — the user picks target apps manually in the script's fallback prompt, or re-runs the script after submodules are added.

## Step 7 — Initialize Methodologies

For each selected item, run the installation at the **workspace root**:

### GSD (open-gsd fork)
```bash
cd <workspace-root> && npx @opengsd/gsd-core@latest
```
The installer asks for runtime (select "Claude Code") and local vs global — choose **local** to keep it inside the workspace. Follow interactive prompts.
Do NOT use the old `get-shit-done-cc` / `gsd-pi` packages — they are abandoned.

### BMAD
```bash
cd <workspace-root> && npx bmad-method install
```
Creates `_bmad/` and `_bmad-output/` directories. When prompted for IDE, select "Claude Code". Follow any interactive prompts.

### Superpowers (plugin — not an npx install)
Superpowers is a Claude Code **plugin**, installed **globally** (`~/.claude/plugins/`), not scaffolded into the workspace dir. It cannot be installed via bash — tell the user to run these inside Claude Code:
```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```
To scope it to THIS workspace only, add it to `.claude/settings.json`:
```json
{ "enabledPlugins": { "superpowers@superpowers-marketplace": true } }
```
Skills auto-trigger by task context once enabled.

**Pairing Superpowers on top of BMAD/GSD (recommended binding):**
- The methodology owns planning, docs, and story breakdown (incl. story points). Superpowers owns implementation only.
- Treat the methodology's artifacts (PRD / architecture / stories + acceptance criteria) as the authoritative plan. The story's AC is the spec.
- **Skip** Superpowers' `brainstorming` and `writing-plans` — they duplicate the methodology's front-end.
- **Keep** `test-driven-development`, `systematic-debugging`, `code-review`, `git-worktrees`, `subagent-driven-development` for the implementation phase.
- On each handoff, tell Claude explicitly: "plan/architecture already in <methodology dir>, it is authoritative, skip brainstorm/writing-plans, implement the story against its AC."

**If installation fails:** report the error, note it in the report, suggest the user run the command manually.

After installation, verify the expected directories (or, for Superpowers, the plugin) were created.

## Step 8 — Generate CLAUDE.md

Create `CLAUDE.md` **at the workspace root** (not inside `.claude/`). This is the main entry point — Claude sees it first.

The file MUST start with a hidden metadata block for re-run detection:

```markdown
<!-- workspace-meta
name: <workspace-name>
version: 2.0.0
created: <YYYY-MM-DD>
apps:
  - dir: <dir1>, type: <type>, agent: <agent>
  - dir: <dir2>, type: <type>, agent: <agent>
methodologies:
  - bmad
  - superpowers
-->

# <Workspace Name>

## Workspace Architecture

This is a workspace wrapper. Each application lives in `apps/` as a git submodule.

| App | Directory | Stack | Agent |
|-----|-----------|-------|-------|
| <Label> | apps/<dir>/ | <Stack> | <agent> |
| ... | ... | ... | ... |

## Routing Rules

When working on files in a specific app directory, use the corresponding specialist agent:

<For each app, generate a line:>
- **apps/<dir>/** — Use `<agent>` agent. <Brief description of conventions from the agent>.

When a task spans multiple apps, work on each app sequentially:
1. Plan changes for ALL affected apps first
2. Start with the app that defines the interface (usually backend)
3. Delegate to the appropriate agent for each app
4. After all changes: verify that cross-app contracts (APIs, types) are consistent

## Cross-App Coordination

When making changes that affect multiple apps:

- **API contracts**: If you modify an API endpoint in one app, check all other apps that consume it. Update both sides.
- **Types/models**: Each app defines its own types that mirror the API contract. Keep them in sync manually.
- **Environment**: Each app may have its own `.env` file. The workspace root `.env` is not used.

<If methodologies were selected, add:>

## Methodologies

<For each methodology, generate a section:>
### <Methodology Name>
- Directory: `<path>/`
- Docs: <link>
- Initialized: <YYYY-MM-DD>

<If Superpowers was selected AND a methodology (BMAD/GSD) was also selected, add:>
### Superpowers ↔ <Methodology> (layer split)
The Superpowers plugin is enabled (skills auto-trigger).
- **<Methodology> owns** planning, docs, and story breakdown (incl. story points). Its artifacts are the source of truth.
- **Superpowers owns implementation only.** Skip `superpowers:brainstorming` and `superpowers:writing-plans` (they duplicate <Methodology>'s front-end).
- Use from Superpowers on implementation: `test-driven-development`, `systematic-debugging`, `requesting-code-review` / `receiving-code-review`, `using-git-worktrees`, `subagent-driven-development`, `verification-before-completion`.
- One process at a time — never BMAD + GSD together.
<End if>

<If Superpowers was selected WITHOUT a methodology, add:>
### Superpowers
The Superpowers plugin is enabled (skills auto-trigger). No project methodology — its full flow (brainstorm → plan → TDD → review) is the default.
<End if>

<End if>

## Central Config

This workspace uses rules synced from `~/claude-config/`.
- Run `/project-pull` to update rules from central repo.
- Run `/project-push` to push local improvements back to central.
- Run `/workspace-init` again to add apps or methodologies.

Installed from central:
- Rules: <list each rule with version, one per line>
- Agents (global): <list each agent used by this workspace>
```

## Step 9 — Initial Git Commit

Stage and commit all workspace-level files as the initial starting point. This commit only touches workspace git — **never** app repos inside `apps/`.

What gets committed:
- `CLAUDE.md` — workspace brain
- `.claude/rules/*.md` — scoped rules
- `.gitignore` — workspace ignores
- Methodology config files (`.planning/`, `.gsd/`, `_bmad/`) if initialized

```
workspace: initialize <workspace-name>

Apps: <list of app-type (dir-name) pairs>
Methodologies: <list or "none">
Config: <N> rules, routing via CLAUDE.md
```

Do NOT commit if the user declines.

## Step 10 — Report

Show a summary of what was created:

```
Workspace initialized: <name>

Structure:
  <name>/
  ├── CLAUDE.md                — workspace brain (routing + coordination)
  ├── .claude/rules/           — <N> rules (scoped to app directories)
  ├── apps/<dir1>/             — <Type> (submodule placeholder)
  ├── apps/<dir2>/             — <Type> (submodule placeholder)
  ├── Makefile                 — clone target for submodule init
  <if methodologies:>
  ├── .planning/               — GSD v1  (if selected)
  ├── .gsd/                    — GSD v2  (if selected)
  ├── _bmad/                   — BMAD    (if selected)
  </if>
  └── .gitignore

Agents available (global):
  <list of agents relevant to this workspace>

Next steps:
  1. cd <name> (if created as subdirectory)
  2. Start building — Claude routes to the right agent per app directory
  3. Run /project-pull periodically to check for rule updates
  4. Run /workspace-init again to add more apps or methodologies
```

## Rules

- NEVER create the workspace without confirming the plan with the user first (Step 4).
- NEVER install rules or agents without user approval.
- Path scoping is handled automatically by `rules-manage.mjs` via `path_hints:` resolution. Do NOT manually rewrite paths.
- If two apps need the same rule, create ONE file with the original central name containing paths for ALL target apps. Never use suffixed filenames — `rules-manage.mjs` matches by exact filename.
- Do NOT generate application code, boilerplate, or scaffolding. Only create Claude configuration, directory structure, and Makefile.
- Do NOT create docker-compose or other project tooling beyond the Makefile.
- If the target directory already contains files (other than `.git/`, `CLAUDE.md`, `.claude/`, `apps/`), abort and ask the user to use an empty directory.
- Cross-platform: use `~` for home directory.
- If `$ARGUMENTS` is provided, treat it as the workspace name.
- Each app in `apps/` is a git submodule — NEVER mix workspace-level git operations with app-level git.
- When adding submodules, verify the URL is accessible. If it fails, report the error and offer to create an empty dir with `.gitkeep` instead.
- `apps/` directory MUST be tracked by workspace git (never in `.gitignore`). Empty app dirs use `.gitkeep` as placeholders until submodules are added.
- For `custom` app type: ask the user which global agent to use and which rules to install. If no matching agent exists, skip agent routing for that app.
- On re-run: detect existing workspace via `<!-- workspace-meta` in CLAUDE.md. Offer to add apps/methodologies — do NOT recreate what already exists.
- Methodology commands may have interactive prompts — let them run interactively, do not suppress output.
- A workspace holds planning artifacts, internal config, and pre-release product code — it is private by default. When creating a GitHub repository for a workspace, ALWAYS create it private (`gh repo create <owner>/<name> --private --source=. --remote=origin --push`). NEVER create a workspace repo public. To go public later is an explicit, separate user decision.

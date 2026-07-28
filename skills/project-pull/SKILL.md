---
name: project-pull
version: 1.2.0
description: Pull fresh rules, agents, and skills from ~/claude-config to current project
user-invocable: true
---

# Project Pull — Sync Project Rules from Central Repo

Pull updates from `~/claude-config` central repository into the current project.

## What to pull

If `$ARGUMENTS` is provided, treat it as the name of specific file(s) to update.
If `$ARGUMENTS` is empty, check all installed rules/agents/skills for updates.

## Step 1 — Ensure Central Repo Exists

The central config repo is at `~/claude-config/`.

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
After cloning, run the installer: `~/claude-config/install.sh` to set up global config.

**If found:**
Verify it's a git repo with `rules/`, `agents/`, `skills/` directories.

## Step 2 — Git Pull Central

Run `git pull` in the central repo to get the latest version.
If pull fails due to conflicts, warn the user and proceed with whatever version is on disk.
If pull fails due to network issues, warn but continue with local version.

## Step 3 — Compare Versions

Check all files in the current project against central:

- **Rules** (`.opencode/rules/*.md`): Compare `version:` in frontmatter. If central is newer, mark for update.
- **Agents** (`.opencode/agents/*.md`): Compare `version:` in frontmatter.
- **Skills** (`.opencode/skills/*/SKILL.md`): Compare `version:` in frontmatter.

Also check for new files in central that are not installed locally.

Present a summary table:

```
RULE/AGENT/SKILL    LOCAL     CENTRAL   STATUS
rust-errors         1.0.0     1.2.0     update available
go-backend          1.1.0     1.1.0     up to date
frontend-i18n       -         1.0.0     not installed
```

If everything is up to date, tell the user and stop.

## Step 4 — Confirm with User

Ask: "Update N files? (project-specific paths will be preserved)"

## Step 5 — Apply Updates

For each file to update:

1. **For rules**: Read the central file content (after frontmatter). Read local `paths:` block. Write new local file = central content + local paths + central version.
2. **For agents**: Copy central file to local, overwriting entirely (agents have no project-specific parts).
3. **For skills**: Copy central SKILL.md to local, overwriting entirely.

Create `.backup` of each local file before overwriting.

## Step 6 — Report

Show what was updated, with old → new versions.
Mention backup files were created.

## Step 7 — New Files (optional)

If central has files not installed locally, ask:
"Central repo has N new files not in this project: [list]. Install any?"

If user says yes, install them — and **resolve paths** using the algorithm in Step 8.

## Step 8 — Resolve paths for new rules (REQUIRED)

When installing a NEW rule (not updating an existing one), you MUST resolve `path_hints:` from the central file into project-specific `paths:`. Never copy `path_hints:` as-is.

### Algorithm

For each `path_hints:` entry in the central rule:

1. **Glob** the project directory using the hint pattern (e.g., `**/domain/**/*`)
2. **If matches found**: extract the shortest unique directory prefix for each group of matches. For example, if glob `**/domain/**/*` matches:
   - `apps/vscode-gitbox/src/domain/types/git.ts`
   - `apps/vscode-gitbox/src/domain/constants.ts`
   → the common prefix is `apps/vscode-gitbox/src/domain/`
   → the resolved path is `apps/vscode-gitbox/src/domain/**/*`
3. **If no matches**: check if the project has an `apps/` directory. If yes, prefix the hint with `apps/<app-dir>/` for each app directory. If no `apps/`, use the hint as-is.
4. **Deduplicate** the resolved paths.

### Writing the installed file

1. Read the central file content
2. Remove the `path_hints:` block from frontmatter
3. Insert a `paths:` block with the resolved paths
4. Write to `.opencode/rules/<name>.md`

### Example

Central rule has:
```yaml
path_hints:
  - "**/domain/**/*"
  - "**/constants.*"
```

After globbing a workspace project with `apps/vscode-gitbox/`:
```yaml
paths:
  - "apps/vscode-gitbox/src/domain/**/*"
```
(both hints resolved to the same directory, deduplicated)

## Rules

- NEVER overwrite local `paths:` in rules. Always preserve project-specific paths during update.
- ALWAYS backup before overwriting.
- If a local file has a NEWER version than central, skip it and note it (the user likely improved it locally).
- If a file exists locally but NOT in central, leave it alone (it's a project-specific file).

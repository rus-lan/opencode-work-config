---
name: project-push
version: 1.1.0
description: Push improved rules, agents, or skills from current project to ~/claude-config central repo
user-invocable: true
---

# Project Push — Sync Local Improvements to Central Repo

Push local improvements back to the central `~/claude-config` repository.

## What to push

If `$ARGUMENTS` is provided, treat it as the name of the specific file(s) to push.
If `$ARGUMENTS` is empty, auto-detect what changed (see detection step below).

## Step 1 — Ensure Central Repo Exists and Is Fresh

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

**If found:**
Verify it's a git repo with `rules/`, `agents/`, `skills/` directories.
Run `git fetch origin` to check for remote updates.
If local branch is behind remote, run `git pull` to get latest changes before comparing.
This ensures we don't push against stale central data.

## Step 2 — Detect Changes

Compare local project files against central repo:

- **Rules**: Compare content (not `paths:`) of `.opencode/rules/*.md` vs `~/claude-config/rules/*.md`
- **Agents**: Compare `.opencode/agents/*.md` vs `~/claude-config/agents/*.md`
- **Skills**: Compare `.opencode/skills/*/SKILL.md` vs `~/claude-config/skills/*/SKILL.md`

For each file that exists in both locations, extract content (strip frontmatter paths for rules) and diff.
List files where content differs. Skip files that are identical.

If no differences found, tell the user "Everything is in sync" and stop.

## Step 3 — Confirm with User

Show the user:
- Which files have changes
- A brief summary of what changed in each
- The current version in central vs local

Ask: "Push these changes? (patch/minor/major bump, default: patch)"

If the user specifies a bump level, use it. Otherwise default to `patch`.

## Step 4 — Push Changes

For each confirmed file:

1. Read the central version of the file
2. **For rules**: Replace central content (everything after frontmatter) with local content. Keep central template `path_hints:` (do NOT overwrite with project-specific `paths:`). Bump `version:` in central.
3. **For agents/skills**: Replace central file content entirely. Bump `version:` in frontmatter.
4. Update the local file's `version:` to match the new central version.

## Step 5 — Git Commit & Push

In `~/claude-config`:

1. `git add` the changed files
2. `git commit` with message: `update <file-list> to v<new-version>`
3. `git push`

Report success to the user.

## Rules

- NEVER overwrite central template `path_hints:` with project-specific `paths:`. Central rules use `path_hints:` (broad, portable patterns). Installed rules have `paths:` (resolved for the specific project). These must NOT go to central.
- ALWAYS create a backup of the central file before overwriting (`.backup` extension).
- If `git push` fails (e.g., remote has newer changes), tell the user to resolve manually.
- If a file exists locally but NOT in central, ask the user if they want to create it as a new file in central.

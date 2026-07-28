---
name: config-pull
version: 1.0.0
description: Pull latest changes from ~/claude-config remote and install globally to ~/.config/opencode/
user-invocable: true
---

# Config Pull — Update Global Config from Remote

Pull the latest changes from the `~/claude-config` remote repository and apply them globally by running `install.sh`.

## When to use

Run `/config-pull` when:
- You edited `~/claude-config/` on another machine and pushed changes
- You want to sync this machine's global Claude config with the latest version

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

**If found:**
Verify it's a git repo.

## Step 2 — Git Pull

Run `git -C ~/claude-config pull` to fetch and merge the latest changes.

If pull fails due to conflicts, warn the user and stop — they need to resolve manually.
If pull fails due to network issues, warn and stop.

If already up to date (no new changes), tell the user and ask if they still want to re-run `install.sh`.

## Step 3 — Show What Changed

Run `git -C ~/claude-config log --oneline HEAD@{1}..HEAD 2>/dev/null` to show what commits were pulled.

If there are changes, summarize:
```
Pulled N new commits:
  abc1234 update rust-errors to v1.2.0
  def5678 add new agent: tauri-dev
```

## Step 4 — Run install.sh

Execute `~/claude-config/install.sh` to apply changes globally.

This installs to `~/.config/opencode/`:
- `settings.json`
- `CLAUDE.md`
- hooks
- agents
- skills
- git hooks
- shell alias
- statusline (if not already installed)

Show the output of `install.sh` to the user.

## Step 5 — Report

```
Global config updated.

To update project-level rules, run /project-pull in the project directory.
```

## Rules

- NEVER modify files in `~/claude-config/` — this skill only pulls and installs.
- If `git pull` has conflicts, do NOT force-reset. Warn the user to resolve manually.
- If `install.sh` fails, show the error and suggest the user run it manually: `cd ~/claude-config && ./install.sh`

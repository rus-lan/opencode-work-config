---
name: mapps
version: 1.0.0
description: Multi-repo workspace management — clone repos, generate Makefile, build project maps
---

# /mapps

Turn a list of git repositories into a working multi-repo workspace. Clones each repo under `apps/`, generates root `Makefile` with per-repo and aggregate targets, writes LLM wrapper prompts for project maps.

## Usage

```
/mapps                                             # show help
/mapps init <url> [<url>...]                      # create workspace with repos
/mapps init                                        # re-run init (idempotent, reads repos.list)
/mapps add <url> [dir] [branch]                   # add one repo
/mapps rm <name> [--force]                        # remove one repo
/mapps <command> --help                           # show command help
```

## Commands

### `/mapps init [<url>...]`

Idempotent — safe to run again at any time:

1. Creates `repos.list` if it does not exist yet.
2. Appends any URLs passed as arguments (skipped silently if already listed).
3. Clones every repo not yet cloned into `apps/`.
4. Regenerates the root `Makefile` and creates `mk/` if missing.
5. Writes the three wrapper prompt files (Claude Code, opencode, plain prompt).
6. Creates `results/` directory for LLM-generated artifacts.
7. Creates or updates `.gitignore` to ignore `apps/`.
8. Runs `git init` in the workspace root if it is not a git repo yet.

**Examples:**
```
/mapps init git@github.com:you/api.git git@github.com:you/web.git
/mapps init                                        # re-run with existing repos.list
```

### `/mapps add <url> [dir] [branch]`

Appends one repo to `repos.list`, clones it, and regenerates the Makefile.

**Examples:**
```
/mapps add git@github.com:you/auth.git
/mapps add https://github.com/you/service.git my-svc main
```

### `/mapps rm <name> [--force]`

Removes one repo from the workspace. `<name>` is the folder name under `apps/`.

**Examples:**
```
/mapps rm api
/mapps rm api --force
```

## Make Targets

### Per repo (`<dir>` = folder name under `apps/`):

| Target | What it does |
|--------|--------------|
| `build-<dir>` | Runs the detected build command |
| `run-<dir>` | Runs the detected run command (foreground) |
| `test-<dir>` | Runs the detected test command |
| `pull-<dir>` | `git -C apps/<dir> pull` |
| `commit-<dir>` | `git -C apps/<dir> add -A && git commit -m "$(MSG)"` |
| `push-<dir>` | `git -C apps/<dir> push` |

### Aggregates:

| Target | What it does |
|--------|--------------|
| `build-all` | Runs `build-<dir>` for every repo |
| `pull-all` | Runs `pull-<dir>` for every repo |
| `status` | Short `git status` and current branch for every repo |
| `list` | Dir, branch, and detected stack for every repo |

**Note:** `commit-<dir>` needs an `MSG`:
```
make commit-api MSG="fix login bug"
```

## Stack Detection

| Marker | Stack | build | run | test |
|--------|-------|-------|-----|------|
| `go.mod` | go | `go build ./...` | `go run .` | `go test ./...` |
| `package.json` | node | `<pm> run build` | `<pm> run start/dev` | `<pm> run test` |
| `Cargo.toml` | rust | `cargo build` | `cargo run` | `cargo test` |
| `Makefile` | make | `$(MAKE) build` | `$(MAKE) run` | `$(MAKE) test` |

## Output Structure

```
workspace/
  repos.list          # list of repos (one per line)
  Makefile            # generated root Makefile
  mk/                 # per-repo overrides
    <dir>.mk
  apps/               # cloned repos (ignored by git)
    <dir>/
  results/            # LLM-generated artifacts (tracked)
    .gitkeep
  .gitignore          # ignores apps/
  CLAUDE.md           # workspace index
  .claude/
    skills/
      mapps/
        SKILL.md      # this file
  .opencode/
    commands/
      mapps.md        # opencode command
```

## repos.list Format

Plain text file, one repo per line:
```
<url> [dir] [branch]
```

**Examples:**
```
# mapps repos list
git@github.com:user/api.git
https://github.com/user/web.git my-web main
```

## What You Must Do When Invoked

If the user invoked `/mapps` with no arguments or `/mapps --help`/`/mapps -h`, print the `## Usage` section above verbatim and stop.

Otherwise, dispatch to the appropriate command handler:
- `init` → run `mapps init` with provided URLs
- `add` → run `mapps add` with provided args
- `rm` → run `mapps rm` with provided args

Check that `mapps` binary is installed first:
```bash
if ! command -v mapps >/dev/null 2>&1; then
    echo "Installing mapps..."
    go install github.com/rus-lan/multiApps/cmd/mapps@latest
fi
```

Then run the appropriate command with the user's arguments.

## References

- GitHub: https://github.com/rus-lan/multiApps
- Install: `go install github.com/rus-lan/multiApps/cmd/mapps@latest`

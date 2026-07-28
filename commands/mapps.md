---
name: mapps
description: Multi-repo workspace management — clone repos, generate Makefile, build project maps
---

# /mapps

Turn a list of git repositories into a working multi-repo workspace.

## Usage

```
/mapps                                             # show help
/mapps init <url> [<url>...]                      # create workspace with repos
/mapps init                                        # re-run init (idempotent)
/mapps add <url> [dir] [branch]                   # add one repo
/mapps rm <name> [--force]                        # remove one repo
```

## Commands

### `/mapps init [<url>...]`

Creates `repos.list`, clones repos into `apps/`, generates `Makefile`, writes LLM prompts.

**Example:**
```
/mapps init git@github.com:you/api.git git@github.com:you/web.git
```

### `/mapps add <url> [dir] [branch]`

Adds one repo to the workspace.

**Example:**
```
/mapps add git@github.com:you/auth.git
```

### `/mapps rm <name> [--force]`

Removes one repo from the workspace.

**Example:**
```
/mapps rm api
```

## What You Must Do

If invoked with no arguments or `--help`/`-h`, print the `## Usage` section and stop.

Otherwise:
1. Check that `mapps` binary is installed:
   ```bash
   if ! command -v mapps >/dev/null 2>&1; then
       echo "Installing mapps..."
       curl -fsSL https://raw.githubusercontent.com/rus-lan/multiApps/main/install.sh | sh
   fi
   ```

2. Run the appropriate command:
   - `init` → `mapps init <urls>`
   - `add` → `mapps add <args>`
   - `rm` → `mapps rm <name> [--force]`

## References

- GitHub: https://github.com/rus-lan/multiApps

---
name: mapps
description: Multi-repo workspace management — clone repos, generate Makefile, build project maps
agent: build
subtask: true
---

# /mapps — Multi-repo workspace management

If invoked with no arguments or `--help`/`-h`, print the help info from `mapps --help` and stop.

**Init workspace:**
```bash
mapps init <url1> <url2> ...
```

**Add a repo:**
```bash
mapps add <url> [dir] [branch]
```

**Remove a repo:**
```bash
mapps rm <name> [--force]
```

First check that `mapps` is installed. If not, install it:
```bash
curl -fsSL https://raw.githubusercontent.com/rus-lan/multiApps/main/install.sh | sh
```

Then run the appropriate command based on user input. Show the output clearly.

## References

- GitHub: https://github.com/rus-lan/multiApps
- Binary: /home/ruslan/go/bin/mapps

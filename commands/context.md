---
name: context
description: Show context metrics, limits, and usage statistics
agent: build
subtask: true
---

Run the script to show context metrics. Parse any flags the user passed.

**Default (no flags)**: Run `/home/ruslan/.config/opencode/skills/context-metrics/get-context-metrics.sh`

**`--limits`** or **`-l`**: Run `/home/ruslan/.config/opencode/skills/context-metrics/check-limits.sh`

**`--watch`** or **`-w`**: Run `/home/ruslan/.config/opencode/skills/context-metrics/get-context-metrics.sh` in watch mode

**`--effort`** or **`-e`**: Output current effort settings

Display the full output clearly. If the script fails, show the error.

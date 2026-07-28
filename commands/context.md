---
name: context
description: Show context metrics, limits, and usage statistics
---

# /context

Show context metrics, limits, and usage statistics

# handler

type=script
path=~/.config/opencode/context-metrics/get-context-metrics.sh

## Usage

```
/context            # Show current context metrics
/context --watch    # Continuous monitoring
/context --limits   # Check rate limits
/context --effort   # Show effort configuration
```

## Примеры

```
/context            # Show current context metrics
/context --watch    # Continuous monitoring
/context --limits   # Check rate limits
/context --effort   # Show effort configuration
```

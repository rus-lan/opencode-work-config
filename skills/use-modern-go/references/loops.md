# Loops

Правила категории **Loops** из e001-ai-hub. Всего: 2.

## range_over_int

**Since:** Go 1.22 | **Impact:** Critical | **Category:** Loops | **Analyzer:** modernize

Use `for i := range n` when iterating from `0` to `n-1`.

Ranging over an integer is the concise Go 1.22 form for zero-based count loops. Keep a traditional for loop when you need a non-zero start, custom step, or changing bound.

**Плохо (до):**

```go
for i := 0; i < len(items); i++ {
	process(items[i])
}
```

**Хорошо (после):**

```go
for i := range len(items) {
	process(items[i])
}
```

## loopvar_capture

**Since:** Go 1.22 | **Impact:** High | **Category:** Loops | **Analyzer:** modernize

Do not add redundant loop-variable copies before closures or taking addresses; Go 1.22 gives each iteration its own variables.

Go 1.22 gives each loop iteration its own variables, so defensive copies like `v := v` are usually redundant before closures, goroutines, deferred functions, or appending `&v`. Keep an explicit copy only when it serves another purpose. If you need a pointer to the original slice element rather than the per-iteration copy, use `&slice[i]`.

### Пример 1

**Плохо (до):**

```go
for _, item := range items {
	item := item
	go func() {
		process(item)
	}()
}
```

**Хорошо (после):**

```go
for _, item := range items {
	go func() {
		process(item)
	}()
}
```

### Пример 2

**Плохо (до):**

```go
var selected []*Item
for _, item := range items {
	item := item
	if item.Enabled {
		selected = append(selected, &item)
	}
}
```

**Хорошо (после):**

```go
var selected []*Item
for _, item := range items {
	if item.Enabled {
		selected = append(selected, &item)
	}
}
```


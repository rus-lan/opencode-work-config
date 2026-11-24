# Time

Правила категории **Time** из e001-ai-hub. Всего: 3.

## time_tick_gc

**Since:** Go 1.23 | **Impact:** Low | **Category:** Time | **Analyzer:** —

Use `time.Tick` when it fits; Go 1.23 can recover unreferenced tickers without requiring `Stop` for GC.

Go 1.23 made unreferenced tickers recoverable by the garbage collector. Use `time.Tick` for simple forever loops, and use `time.NewTicker` when you need `Stop` or `Reset`.

**Плохо (до):**

```go
ticker := time.NewTicker(time.Second)
defer ticker.Stop()
for range ticker.C {
	poll()
}
```

**Хорошо (после):**

```go
for range time.Tick(time.Second) {
	poll()
}
```

## time_until

**Since:** Go 1.8 | **Impact:** Medium | **Category:** Time | **Analyzer:** —

Use `time.Until(deadline)` instead of `deadline.Sub(time.Now())`.

`time.Until` is the standard spelling for remaining time before a deadline. It is equivalent to `deadline.Sub(time.Now())` but reads in the direction the caller cares about.

**Плохо (до):**

```go
remaining := deadline.Sub(time.Now())
```

**Хорошо (после):**

```go
remaining := time.Until(deadline)
```

## time_since

**Since:** Go 1.0 | **Impact:** High | **Category:** Time | **Analyzer:** —

Use `time.Since(start)` instead of `time.Now().Sub(start)`.

`time.Since` is the standard spelling for elapsed time from a recorded start. It keeps the `time.Now` call inside the time package helper and makes the intent easier to scan.

**Плохо (до):**

```go
elapsed := time.Now().Sub(start)
```

**Хорошо (после):**

```go
elapsed := time.Since(start)
```


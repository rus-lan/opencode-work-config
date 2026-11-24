# Sync

Правила категории **Sync** из e001-ai-hub. Всего: 4.

## sync_waitgroup_go

**Since:** Go 1.25 | **Impact:** High | **Category:** Sync | **Analyzer:** modernize

Use `wg.Go` when spawning goroutines tracked by a `sync.WaitGroup`.

`WaitGroup.Go` starts a goroutine and handles the matching `Add` and `Done` calls. Use it when the goroutine's lifetime is exactly what the `WaitGroup` should track.

**Плохо (до):**

```go
var wg sync.WaitGroup
for _, item := range items {
	wg.Add(1)
	go func() {
		defer wg.Done()
		process(item)
	}()
}
wg.Wait()
```

**Хорошо (после):**

```go
var wg sync.WaitGroup
for _, item := range items {
	wg.Go(func() {
		process(item)
	})
}
wg.Wait()
```

## sync_once_func

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Sync | **Analyzer:** —

Use `sync.OnceFunc` instead of `sync.Once` plus a wrapper closure.

`sync.OnceFunc` wraps a function so that the returned function runs it at most once. It is a compact fit for idempotent cleanup or one-time initialization hooks.

**Плохо (до):**

```go
var once sync.Once
cleanup := func() {
	once.Do(func() {
		close(ch)
	})
}
```

**Хорошо (после):**

```go
cleanup := sync.OnceFunc(func() {
	close(ch)
})
```

## sync_once_value

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Sync | **Analyzer:** —

Use `sync.OnceValue` to memoize a computed value.

`sync.OnceValue` memoizes a computed value safely across goroutines. It replaces a `sync.Once` plus a separate result variable and getter closure.

**Плохо (до):**

```go
var once sync.Once
var value T
getter := func() T {
	once.Do(func() {
		value = computeValue()
	})
	return value
}
```

**Хорошо (после):**

```go
getter := sync.OnceValue(func() T {
	return computeValue()
})
```

## atomic_types

**Since:** Go 1.19 | **Impact:** Medium | **Category:** Sync | **Analyzer:** modernize

Use typed atomics such as `atomic.Bool`, `atomic.Int64`, and `atomic.Pointer[T]` instead of untyped atomic functions.

Typed atomic wrapper values keep the storage and the atomic operations together. They make the value type visible, reduce accidental non-atomic access, and avoid old pointer-alignment pitfalls. Prefer them in new code: replacing a raw `int64` or `unsafe.Pointer` field in an existing type changes its layout and size, and `atomic.Value` differs from `atomic.Pointer[T]` in nil and type handling, so migrate a type deliberately rather than call by call.

### Пример 1

**Плохо (до):**

```go
var enabled int32
atomic.StoreInt32(&enabled, 1)
if atomic.LoadInt32(&enabled) != 0 {
	run()
}
```

**Хорошо (после):**

```go
var enabled atomic.Bool
enabled.Store(true)
if enabled.Load() {
	run()
}
```

### Пример 2

**Плохо (до):**

```go
var ptr unsafe.Pointer
atomic.StorePointer(&ptr, unsafe.Pointer(cfg))
```

**Хорошо (после):**

```go
var ptr atomic.Pointer[Config]
ptr.Store(cfg)
```


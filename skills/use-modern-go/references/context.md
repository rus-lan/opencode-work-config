# Context

Правила категории **Context** из e001-ai-hub. Всего: 4.

## testing_t_context

**Since:** Go 1.24 | **Impact:** High | **Category:** Context | **Analyzer:** modernize

Use `t.Context()` when a test function needs a context tied to the test lifetime; it is already canceled by the time `t.Cleanup` functions run, so do not pass it to cleanup work.

`t.Context()` returns a context tied to the test lifetime. It removes manual background context setup when helper work should stop as the test is ending. The context is canceled before registered `t.Cleanup` functions run, so cleanup that needs a live context must create its own.

**Плохо (до):**

```go
func TestFoo(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	result := doSomething(ctx)
}
```

**Хорошо (после):**

```go
func TestFoo(t *testing.T) {
	ctx := t.Context()
	result := doSomething(ctx)
}
```

## context_after_func

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Context | **Analyzer:** —

Use `context.AfterFunc` to run cleanup when a context is canceled.

`context.AfterFunc` registers work to run after cancellation and returns a stop function. It avoids starting a goroutine whose only job is to wait on `ctx.Done()`.

**Плохо (до):**

```go
go func() {
	<-ctx.Done()
	cleanup()
}()
```

**Хорошо (после):**

```go
stop := context.AfterFunc(ctx, cleanup)
defer stop()
```

## context_timeout_deadline_cause

**Since:** Go 1.21 | **Impact:** Low | **Category:** Context | **Analyzer:** —

Use timeout and deadline contexts with causes when callers need to inspect the cancellation reason.

Timeout and deadline causes let callers distinguish the reason for cancellation with `context.Cause`. Use them when `ctx.Err()` is too coarse for diagnostics or control flow.

**Плохо (до):**

```go
ctx, cancel := context.WithTimeout(parent, d)
defer cancel()
```

**Хорошо (после):**

```go
ctx, cancel := context.WithTimeoutCause(parent, d, errTimeout)
defer cancel()
```

## context_cancel_cause

**Since:** Go 1.20 | **Impact:** Medium | **Category:** Context | **Analyzer:** —

Use `context.WithCancelCause` and `context.Cause` when cancellation needs to carry an error cause.

Cancellation causes let code record why a context was canceled. Callers can inspect `context.Cause(ctx)` instead of only seeing the broad `ctx.Err` result.

**Плохо (до):**

```go
ctx, cancel := context.WithCancel(parent)
cancel()
```

**Хорошо (после):**

```go
ctx, cancel := context.WithCancelCause(parent)
cancel(err)
cause := context.Cause(ctx)
```


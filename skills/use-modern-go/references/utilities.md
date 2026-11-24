# Utilities

Правила категории **Utilities** из e001-ai-hub. Всего: 3.

## stdlib_uuid

**Since:** Go 1.27 | **Impact:** Medium | **Category:** Utilities | **Analyzer:** —

Use the standard library `uuid` package instead of third-party libraries or custom UUID implementations when targeting Go 1.27+.

The standard `uuid` package covers common UUID generation and parsing without an external dependency. Keep a third-party package only when targeting older Go versions or needing behavior outside the standard API.

### Пример 1

**Плохо (до):**

```go
import googleuuid "github.com/google/uuid"

id := googleuuid.New()
text := id.String()
```

**Хорошо (после):**

```go
import "uuid"

id := uuid.New()
text := id.String()
```

### Пример 2

**Плохо (до):**

```go
id, err := googleuuid.Parse(raw)
if err != nil {
	return err
}
```

**Хорошо (после):**

```go
id, err := uuid.Parse(raw)
if err != nil {
	return err
}
```

## new_expression

**Since:** Go 1.26 | **Impact:** High | **Category:** Utilities | **Analyzer:** modernize

Use `new(value)` for pointer fields or arguments instead of generic/type-specific pointer helper functions or temporary variables used only for `&value`.

`new(value)` creates a `*T` from a value expression. In struct literals, prefer `Field: new(value)` for pointer fields over helper calls whose only purpose is returning `&value`; keep helpers only when they add behavior. `new` uses the default type of an untyped constant, so `new(30)` yields `*int` and does not fit a `*time.Duration` or `*int32` field; write `new(30 * time.Second)` or `new(int32(30))` instead.

### Пример 1

**Плохо (до):**

```go
type Config struct {
	Timeout *time.Duration
	Debug   *bool
}

func Pointer[T any](value T) *T {
	return &value
}

cfg := Config{
	Timeout: Pointer(30 * time.Second),
	Debug:   Pointer(true),
}
```

**Хорошо (после):**

```go
type Config struct {
	Timeout *time.Duration
	Debug   *bool
}

cfg := Config{
	Timeout: new(30 * time.Second),
	Debug:   new(true),
}
```

### Пример 2

**Плохо (до):**

```go
type Config struct {
	Retries *int
}

retries := 3
cfg := Config{
	Retries: &retries,
}
```

**Хорошо (после):**

```go
type Config struct {
	Retries *int
}

cfg := Config{
	Retries: new(3),
}
```

## cmp_or

**Since:** Go 1.22 | **Impact:** High | **Category:** Utilities | **Analyzer:** —

Use `cmp.Or` to pick the first non-zero value from a fallback chain.

`cmp.Or` returns the first non-zero value from its arguments. All arguments are evaluated before the call, so it is the wrong choice when later entries are expensive or have side effects, and when a zero value such as `false` or `0` is a valid result rather than a missing one.

**Плохо (до):**

```go
name := os.Getenv("NAME")
if name == "" {
	name = "default"
}
```

**Хорошо (после):**

```go
name := cmp.Or(os.Getenv("NAME"), "default")
```


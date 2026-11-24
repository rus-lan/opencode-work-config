# Errors

Правила категории **Errors** из e001-ai-hub. Всего: 3.

## errors_as_type

**Since:** Go 1.26 | **Impact:** Medium | **Category:** Errors | **Analyzer:** modernize

Use `errors.AsType[T](err)` when checking whether an error matches a specific type.

`errors.AsType` returns the matched error value and a boolean directly. It avoids a separate temporary variable and the pointer-to-target pattern required by `errors.As`.

**Плохо (до):**

```go
var pathErr *os.PathError
if errors.As(err, &pathErr) {
	handle(pathErr)
}
```

**Хорошо (после):**

```go
if pathErr, ok := errors.AsType[*os.PathError](err); ok {
	handle(pathErr)
}
```

## errors_join

**Since:** Go 1.20 | **Impact:** High | **Category:** Errors | **Analyzer:** —

Use `errors.Join` to combine multiple errors while preserving error matching.

`errors.Join` combines multiple non-`nil` errors while preserving error matching through `errors.Is` and `errors.As`. It returns `nil` when there are no non-`nil` errors.

**Плохо (до):**

```go
if err1 != nil && err2 != nil {
	return fmt.Errorf("%v; %w", err1, err2)
}
```

**Хорошо (после):**

```go
return errors.Join(err1, err2)
```

## errors_is

**Since:** Go 1.13 | **Impact:** Critical | **Category:** Errors | **Analyzer:** —

Use `errors.Is(err, target)` instead of `err == target` so wrapped errors are handled correctly.

`errors.Is` walks wrapped errors and honors custom `Is` methods. Direct equality only matches the exact sentinel value and misses errors wrapped with `fmt.Errorf` or custom wrappers.

**Плохо (до):**

```go
if err == os.ErrNotExist {
	return nil
}
```

**Хорошо (после):**

```go
if errors.Is(err, os.ErrNotExist) {
	return nil
}
```


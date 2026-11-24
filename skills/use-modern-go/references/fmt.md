# Fmt

Правила категории **Fmt** из e001-ai-hub. Всего: 1.

## fmt_appendf

**Since:** Go 1.19 | **Impact:** Medium | **Category:** Fmt | **Analyzer:** modernize

Use `fmt.Appendf` when appending formatted text to a byte slice and an intermediate `fmt.Sprintf` string is unnecessary.

`fmt.Appendf` writes formatted output directly into a byte slice. It is useful when code is already accumulating `[]byte` and the extra string allocation from `fmt.Sprintf` is not needed.

**Плохо (до):**

```go
buf = append(buf, []byte(fmt.Sprintf("x=%d", x))...)
```

**Хорошо (после):**

```go
buf = fmt.Appendf(buf, "x=%d", x)
```


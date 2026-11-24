# Testing

Правила категории **Testing** из e001-ai-hub. Всего: 1.

## testing_b_loop

**Since:** Go 1.24 | **Impact:** Medium | **Category:** Testing | **Analyzer:** modernize

Use `b.Loop()` for the main loop in benchmark functions; the iteration count is not known before the loop runs, so a benchmark that sizes fixtures from `b.N` needs reworking rather than a mechanical loop swap.

`b.Loop()` is the modern benchmark loop. It manages benchmark iteration mechanics for you and can remove the need for manual timer control in the benchmark body. `b.N` holds the executed iteration count only after `b.Loop()` returns false, so setup that allocates `b.N` elements before the loop has to be restructured instead of translated line by line.

**Плохо (до):**

```go
func BenchmarkFoo(b *testing.B) {
	for i := 0; i < b.N; i++ {
		doWork()
	}
}
```

**Хорошо (после):**

```go
func BenchmarkFoo(b *testing.B) {
	for b.Loop() {
		doWork()
	}
}
```


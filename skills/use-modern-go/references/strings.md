# Strings

Правила категории **Strings** из e001-ai-hub. Всего: 7.

## strings_bytes_cut_last

**Since:** Go 1.27 | **Impact:** Medium | **Category:** Strings | **Analyzer:** modernize

Use `strings.CutLast` and `bytes.CutLast` instead of `LastIndex` plus manual slicing around the last separator.

`CutLast` splits around the final separator and returns before, after, and found. It removes `LastIndex` checks and manual separator-length slicing.

### Пример 1

**Плохо (до):**

```go
i := strings.LastIndex(path, "/")
if i < 0 {
	return "", path, false
}
dir, file := path[:i], path[i+1:]
```

**Хорошо (после):**

```go
dir, file, found := strings.CutLast(path, "/")
```

### Пример 2

**Плохо (до):**

```go
i := bytes.LastIndex(line, []byte(":"))
if i < 0 {
	return nil, line, false
}
name, value := line[:i], line[i+1:]
```

**Хорошо (после):**

```go
name, value, found := bytes.CutLast(line, []byte(":"))
```

## strings_split_seq

**Since:** Go 1.24 | **Impact:** High | **Category:** Strings | **Analyzer:** modernize

Use `strings.SplitSeq`, `strings.FieldsSeq`, `bytes.SplitSeq`, or `bytes.FieldsSeq` when iterating over split results.

The `SplitSeq` and `FieldsSeq` helpers stream substrings instead of allocating a slice of all parts.

### Пример 1

**Плохо (до):**

```go
for _, part := range strings.Split(s, ",") {
	process(part)
}
```

**Хорошо (после):**

```go
for part := range strings.SplitSeq(s, ",") {
	process(part)
}
```

### Пример 2

**Плохо (до):**

```go
for _, field := range bytes.Fields(b) {
	process(field)
}
```

**Хорошо (после):**

```go
for field := range bytes.FieldsSeq(b) {
	process(field)
}
```

## bytes_clone

**Since:** Go 1.20 | **Impact:** Medium | **Category:** Strings | **Analyzer:** modernize

Use `bytes.Clone` to copy a byte slice.

`bytes.Clone` communicates that a new byte slice is required. It avoids append-copy boilerplate and preserves the standard library's `nil`-slice behavior.

**Плохо (до):**

```go
copied := append([]byte(nil), b...)
```

**Хорошо (после):**

```go
copied := bytes.Clone(b)
```

## strings_cut_prefix_suffix

**Since:** Go 1.20 | **Impact:** High | **Category:** Strings | **Analyzer:** modernize

Use `strings.CutPrefix` or `strings.CutSuffix` when you need both the trimmed result and whether it matched.

`CutPrefix` and `CutSuffix` combine the match check and trimming operation. They avoid writing `HasPrefix` or `HasSuffix` followed by a second operation that repeats the same condition.

**Плохо (до):**

```go
if strings.HasPrefix(s, "pre:") {
	rest := strings.TrimPrefix(s, "pre:")
	use(rest)
}
```

**Хорошо (после):**

```go
if rest, ok := strings.CutPrefix(s, "pre:"); ok {
	use(rest)
}
```

## bytes_cut

**Since:** Go 1.18 | **Impact:** Medium | **Category:** Strings | **Analyzer:** modernize

Use `bytes.Cut` instead of `bytes.Index` plus manual slicing.

`bytes.Cut` returns before, after, and found in one call. It avoids duplicated Index checks and separator-length arithmetic while returning slices of the original byte slice.

**Плохо (до):**

```go
i := bytes.Index(b, sep)
if i < 0 {
	return nil, nil, false
}
before, after := b[:i], b[i+len(sep):]
```

**Хорошо (после):**

```go
before, after, found := bytes.Cut(b, sep)
```

## strings_clone

**Since:** Go 1.18 | **Impact:** Medium | **Category:** Strings | **Analyzer:** —

Use `strings.Clone` to copy a string without retaining shared backing memory.

`strings.Clone` forces a string copy. Use it when retaining a small string derived from a much larger string would otherwise keep the larger backing memory alive.

**Плохо (до):**

```go
copied := string([]byte(s))
```

**Хорошо (после):**

```go
copied := strings.Clone(s)
```

## strings_cut

**Since:** Go 1.18 | **Impact:** Medium | **Category:** Strings | **Analyzer:** modernize

Use `strings.Cut` instead of `strings.Index` plus manual slicing.

`strings.Cut` returns before, after, and found in one call. It makes split-at-first-separator logic explicit and removes manual Index checks and slicing.

**Плохо (до):**

```go
i := strings.Index(s, ":")
if i < 0 {
	return "", "", false
}
key, value := s[:i], s[i+1:]
```

**Хорошо (после):**

```go
key, value, found := strings.Cut(s, ":")
```


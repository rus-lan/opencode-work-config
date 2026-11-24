# Collections

Правила категории **Collections** из e001-ai-hub. Всего: 18.

## maps_keys_values_iter

**Since:** Go 1.23 | **Impact:** High | **Category:** Collections | **Analyzer:** —

Use `maps.Keys` or `maps.Values` directly as iterators instead of manually looping over a map.

`maps.Keys` and `maps.Values` can be ranged over directly when a slice is not needed. This avoids allocating a temporary collection just to iterate.

**Плохо (до):**

```go
for k := range m {
	process(k)
}
```

**Хорошо (после):**

```go
for k := range maps.Keys(m) {
	process(k)
}
```

## slices_collect

**Since:** Go 1.23 | **Impact:** Medium | **Category:** Collections | **Analyzer:** —

Use `slices.Collect` to build a slice from an iterator.

`slices.Collect` materializes an iterator into a slice when a slice is actually required. Prefer ranging over the iterator directly when streaming is enough.

**Плохо (до):**

```go
keys := make([]string, 0, len(m))
for k := range m {
	keys = append(keys, k)
}
```

**Хорошо (после):**

```go
keys := slices.Collect(maps.Keys(m))
```

## slices_sorted

**Since:** Go 1.23 | **Impact:** Medium | **Category:** Collections | **Analyzer:** —

Use `slices.Sorted` to collect and sort iterator values in one step.

`slices.Sorted` collects iterator values and sorts them in one call. It is useful for deterministic output from unordered sources such as map keys.

**Плохо (до):**

```go
keys := make([]string, 0, len(m))
for k := range m {
	keys = append(keys, k)
}
slices.Sort(keys)
```

**Хорошо (после):**

```go
keys := slices.Sorted(maps.Keys(m))
```

## min_max

**Since:** Go 1.21 | **Impact:** High | **Category:** Collections | **Analyzer:** modernize

Use built-in `min` and `max` instead of handwritten comparisons.

The `min` and `max` built-ins express ordered comparisons directly. They remove branch boilerplate when the logic is simply choosing the smaller or larger value.

**Плохо (до):**

```go
if b > a {
	a = b
}
```

**Хорошо (после):**

```go
a = max(a, b)
```

## clear

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Collections | **Analyzer:** —

Use `clear(m)` to delete all map entries or `clear(s)` to zero slice elements.

`clear` is the idiomatic built-in for removing all map entries or zeroing the elements of a slice. For slices it preserves the slice length and capacity.

**Плохо (до):**

```go
for k := range m {
	delete(m, k)
}
```

**Хорошо (после):**

```go
clear(m)
```

## slices_contains

**Since:** Go 1.21 | **Impact:** Critical | **Category:** Collections | **Analyzer:** modernize

Use `slices.Contains` instead of a manual search loop.

`slices.Contains` is the direct membership test for slices of comparable values. It replaces a manual search loop whose only result is whether the element is present.

**Плохо (до):**

```go
found := false
for _, item := range items {
	if item == x {
		found = true
		break
	}
}
```

**Хорошо (после):**

```go
found := slices.Contains(items, x)
```

## slices_index

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Collections | **Analyzer:** —

Use `slices.Index` to find the index of an element, returning `-1` when absent.

`slices.Index` is the direct index lookup for slices of comparable values. It returns `-1` when the value is absent, matching the common handwritten convention.

**Плохо (до):**

```go
index := -1
for i, item := range items {
	if item == x {
		index = i
		break
	}
}
```

**Хорошо (после):**

```go
index := slices.Index(items, x)
```

## slices_index_func

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Collections | **Analyzer:** —

Use `slices.IndexFunc` to find an element by predicate.

`slices.IndexFunc` is the standard predicate-based lookup. Use it when the match depends on fields, derived values, or any condition other than direct equality.

**Плохо (до):**

```go
index := -1
for i, item := range items {
	if item.ID == id {
		index = i
		break
	}
}
```

**Хорошо (после):**

```go
index := slices.IndexFunc(items, func(item Item) bool {
	return item.ID == id
})
```

## slices_sort_func

**Since:** Go 1.21 | **Impact:** High | **Category:** Collections | **Analyzer:** —

Use `slices.SortFunc` with `cmp.Compare` instead of `sort.Slice` for typed comparisons; replace `sort.SliceStable` with `slices.SortStableFunc`, because `slices.SortFunc` is not stable.

`slices.SortFunc` compares typed elements directly, avoiding `sort.Slice` closures that index back into the slice. `cmp.Compare` is the usual comparator for ordered fields. `slices.SortFunc` is not stable, so code that relied on `sort.SliceStable` needs `slices.SortStableFunc` to keep equal elements in their original order.

**Плохо (до):**

```go
sort.Slice(items, func(i, j int) bool {
	return items[i].X < items[j].X
})
```

**Хорошо (после):**

```go
slices.SortFunc(items, func(a, b Item) int {
	return cmp.Compare(a.X, b.X)
})
```

## slices_sort

**Since:** Go 1.21 | **Impact:** High | **Category:** Collections | **Analyzer:** modernize

Use `slices.Sort` for slices of ordered values.

`slices.Sort` is the generic sort for slices of ordered values. It replaces older type-specific helpers and simple `sort.Slice` calls.

**Плохо (до):**

```go
sort.Ints(values)
```

**Хорошо (после):**

```go
slices.Sort(values)
```

## slices_max_min

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Collections | **Analyzer:** —

Use `slices.Max` and `slices.Min` instead of manual loops over ordered values.

`slices.Max` and `slices.Min` capture the common non-empty-slice scan for an ordered maximum or minimum. Keep explicit logic when empty slices or custom comparison rules need special handling.

**Плохо (до):**

```go
maxValue := values[0]
for _, value := range values[1:] {
	if value > maxValue {
		maxValue = value
	}
}
```

**Хорошо (после):**

```go
maxValue := slices.Max(values)
```

## slices_reverse

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Collections | **Analyzer:** —

Use `slices.Reverse` instead of a manual swap loop.

`slices.Reverse` performs an in-place reversal without hand-written index math. It is clearer and less error-prone than open-coded swap loops.

**Плохо (до):**

```go
for i, j := 0, len(items)-1; i < j; i, j = i+1, j-1 {
	items[i], items[j] = items[j], items[i]
}
```

**Хорошо (после):**

```go
slices.Reverse(items)
```

## slices_compact

**Since:** Go 1.21 | **Impact:** Low | **Category:** Collections | **Analyzer:** —

Use `slices.Compact` to remove consecutive duplicates in place.

`slices.Compact` removes consecutive duplicate values in place. If the goal is to remove all duplicates, sort or otherwise group equal values first.

**Плохо (до):**

```go
out := values[:0]
for i, value := range values {
	if i == 0 || value != values[i-1] {
		out = append(out, value)
	}
}
values = out
```

**Хорошо (после):**

```go
values = slices.Compact(values)
```

## slices_clip

**Since:** Go 1.21 | **Impact:** Low | **Category:** Collections | **Analyzer:** modernize

Use `slices.Clip` to remove unused capacity.

`slices.Clip` limits a slice's capacity to its length. Use it to stop retaining excess backing-array capacity or to prevent later appends from reusing hidden capacity.

**Плохо (до):**

```go
s = s[:len(s):len(s)]
```

**Хорошо (после):**

```go
s = slices.Clip(s)
```

## slices_clone

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Collections | **Analyzer:** modernize

Use `slices.Clone` to copy a slice.

`slices.Clone` returns a shallow copy of a slice using the standard helper. It is clearer than append-copy boilerplate and preserves `nil` slices.

**Плохо (до):**

```go
copied := append([]T(nil), values...)
```

**Хорошо (после):**

```go
copied := slices.Clone(values)
```

## maps_clone

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Collections | **Analyzer:** —

Use `maps.Clone` instead of manual map iteration.

`maps.Clone` returns a shallow copy of a map using the standard helper. It preserves `nil` maps and makes the copy operation explicit.

**Плохо (до):**

```go
copied := make(map[string]int, len(src))
for k, v := range src {
	copied[k] = v
}
```

**Хорошо (после):**

```go
copied := maps.Clone(src)
```

## maps_copy

**Since:** Go 1.21 | **Impact:** Medium | **Category:** Collections | **Analyzer:** modernize

Use `maps.Copy` to copy entries from one map into another.

`maps.Copy` copies all entries from one map into another, overwriting existing keys in the destination. It replaces loops whose body only assigns `dst[k] = v`.

**Плохо (до):**

```go
for k, v := range src {
	dst[k] = v
}
```

**Хорошо (после):**

```go
maps.Copy(dst, src)
```

## maps_delete_func

**Since:** Go 1.21 | **Impact:** Low | **Category:** Collections | **Analyzer:** —

Use `maps.DeleteFunc` to delete map entries that match a predicate.

`maps.DeleteFunc` deletes entries selected by a predicate. It keeps the filtering condition in one callback and avoids hand-written delete loops.

**Плохо (до):**

```go
for k, v := range m {
	if shouldDelete(k, v) {
		delete(m, k)
	}
}
```

**Хорошо (после):**

```go
maps.DeleteFunc(m, func(k string, v int) bool {
	return shouldDelete(k, v)
})
```


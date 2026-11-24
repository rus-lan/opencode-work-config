---
name: use-modern-go
version: 1.0.0
description: Используй при написании, изменении, исправлении или рефакторинге Go-кода (файлы .go, go.mod) — применяет современные идиомы Go с учётом целевой версии (slices/maps, errors, context, sync, JSON, generics, testing, time) из e001-ai-hub для Go 1.0–1.27.
license: Apache-2.0
metadata:
  source: https://git.ecom.tech/ecom/dev/common/personal/e001-ai-hub
---

# Modern Go (version-aware)

Применяй современные идиоматичные конструкции Go из e001-ai-hub, сохраняя совместимость с целевой версией Go проекта. 54 правила ниже сгруппированы по категориям в `references/<category>.md` с дословными примерами «до/после». Всё работает офлайн и самодостаточно: без CLI, без сети, без установки.

## Mandatory workflow before editing Go code

1. **Determine the target Go version.** In order:
   - Read the module's `go.mod` (`go 1.24.0` → target `1.24`).
   - If a workspace exists, read `go.work` (`go`/`toolchain` lines).
   - Run `go version` to see the local toolchain.
   - If the user explicitly names a version, that version wins.
2. **Filter the rules.** Discard every rule whose `since` is **greater** than the target version. Exception: the user explicitly asks to modernize, upgrade, or raise the Go version — then apply rules for the requested version.
3. **Consult only relevant references.** Use the index table to find applicable rules, then open `references/<category>.md` only for the categories that matter to the change. Do not read all reference files.
4. **Apply and verify.** Prefer the "Хорошо (после)" form. Make sure the result compiles on the target version and does not change behavior.

## Index of all 54 rules

`since` = minimum Go version. `impact` = priority from the source. Link target is the rule anchor inside the category reference.

| id | since | category | impact | краткая суть | reference |
| --- | --- | --- | --- | --- | --- |
| `maps_keys_values_iter` | 1.23 | Collections | High | Use maps.Keys or maps.Values directly as iterators instead… | [collections](references/collections.md#maps_keys_values_iter) |
| `slices_collect` | 1.23 | Collections | Medium | Use slices.Collect to build a slice from an… | [collections](references/collections.md#slices_collect) |
| `slices_sorted` | 1.23 | Collections | Medium | Use slices.Sorted to collect and sort iterator values… | [collections](references/collections.md#slices_sorted) |
| `min_max` | 1.21 | Collections | High | Use built-in min and max instead of handwritten… | [collections](references/collections.md#min_max) |
| `clear` | 1.21 | Collections | Medium | Use clear(m) to delete all map entries or… | [collections](references/collections.md#clear) |
| `slices_contains` | 1.21 | Collections | Critical | Use slices.Contains instead of a manual search loop | [collections](references/collections.md#slices_contains) |
| `slices_index` | 1.21 | Collections | Medium | Use slices.Index to find the index of an… | [collections](references/collections.md#slices_index) |
| `slices_index_func` | 1.21 | Collections | Medium | Use slices.IndexFunc to find an element by predicate | [collections](references/collections.md#slices_index_func) |
| `slices_sort_func` | 1.21 | Collections | High | Use slices.SortFunc with cmp.Compare instead of sort.Slice for… | [collections](references/collections.md#slices_sort_func) |
| `slices_sort` | 1.21 | Collections | High | Use slices.Sort for slices of ordered values | [collections](references/collections.md#slices_sort) |
| `slices_max_min` | 1.21 | Collections | Medium | Use slices.Max and slices.Min instead of manual loops… | [collections](references/collections.md#slices_max_min) |
| `slices_reverse` | 1.21 | Collections | Medium | Use slices.Reverse instead of a manual swap loop | [collections](references/collections.md#slices_reverse) |
| `slices_compact` | 1.21 | Collections | Low | Use slices.Compact to remove consecutive duplicates in place | [collections](references/collections.md#slices_compact) |
| `slices_clip` | 1.21 | Collections | Low | Use slices.Clip to remove unused capacity | [collections](references/collections.md#slices_clip) |
| `slices_clone` | 1.21 | Collections | Medium | Use slices.Clone to copy a slice | [collections](references/collections.md#slices_clone) |
| `maps_clone` | 1.21 | Collections | Medium | Use maps.Clone instead of manual map iteration | [collections](references/collections.md#maps_clone) |
| `maps_copy` | 1.21 | Collections | Medium | Use maps.Copy to copy entries from one map… | [collections](references/collections.md#maps_copy) |
| `maps_delete_func` | 1.21 | Collections | Low | Use maps.DeleteFunc to delete map entries that match… | [collections](references/collections.md#maps_delete_func) |
| `strings_bytes_cut_last` | 1.27 | Strings | Medium | Use strings.CutLast and bytes.CutLast instead of LastIndex plus… | [strings](references/strings.md#strings_bytes_cut_last) |
| `strings_split_seq` | 1.24 | Strings | High | Use strings.SplitSeq, strings.FieldsSeq, bytes.SplitSeq, or bytes.FieldsSeq when iterating… | [strings](references/strings.md#strings_split_seq) |
| `bytes_clone` | 1.20 | Strings | Medium | Use bytes.Clone to copy a byte slice | [strings](references/strings.md#bytes_clone) |
| `strings_cut_prefix_suffix` | 1.20 | Strings | High | Use strings.CutPrefix or strings.CutSuffix when you need both… | [strings](references/strings.md#strings_cut_prefix_suffix) |
| `bytes_cut` | 1.18 | Strings | Medium | Use bytes.Cut instead of bytes.Index plus manual slicing | [strings](references/strings.md#bytes_cut) |
| `strings_clone` | 1.18 | Strings | Medium | Use strings.Clone to copy a string without retaining… | [strings](references/strings.md#strings_clone) |
| `strings_cut` | 1.18 | Strings | Medium | Use strings.Cut instead of strings.Index plus manual slicing | [strings](references/strings.md#strings_cut) |
| `generic_methods` | 1.27 | Types | Medium | Use generic methods instead of package-level generic helper… | [types](references/types.md#generic_methods) |
| `promoted_field_literals` | 1.27 | Types | Medium | Set embedded struct fields directly with promoted field… | [types](references/types.md#promoted_field_literals) |
| `reflect_type_for` | 1.22 | Types | Low | Use reflect.TypeFor[T]() instead of reflect.TypeOf((T)(nil)).Elem() | [types](references/types.md#reflect_type_for) |
| `any` | 1.18 | Types | Critical | Use any instead of interface{} | [types](references/types.md#any) |
| `sync_waitgroup_go` | 1.25 | Sync | High | Use wg.Go when spawning goroutines tracked by a… | [sync](references/sync.md#sync_waitgroup_go) |
| `sync_once_func` | 1.21 | Sync | Medium | Use sync.OnceFunc instead of sync.Once plus a wrapper… | [sync](references/sync.md#sync_once_func) |
| `sync_once_value` | 1.21 | Sync | Medium | Use sync.OnceValue to memoize a computed value | [sync](references/sync.md#sync_once_value) |
| `atomic_types` | 1.19 | Sync | Medium | Use typed atomics such as atomic.Bool, atomic.Int64, and… | [sync](references/sync.md#atomic_types) |
| `testing_t_context` | 1.24 | Context | High | Use t.Context() when a test function needs a… | [context](references/context.md#testing_t_context) |
| `context_after_func` | 1.21 | Context | Medium | Use context.AfterFunc to run cleanup when a context… | [context](references/context.md#context_after_func) |
| `context_timeout_deadline_cause` | 1.21 | Context | Low | Use timeout and deadline contexts with causes when… | [context](references/context.md#context_timeout_deadline_cause) |
| `context_cancel_cause` | 1.20 | Context | Medium | Use context.WithCancelCause and context.Cause when cancellation needs to… | [context](references/context.md#context_cancel_cause) |
| `errors_as_type` | 1.26 | Errors | Medium | Use errors.AsType[T](err) when checking whether an error matches… | [errors](references/errors.md#errors_as_type) |
| `errors_join` | 1.20 | Errors | High | Use errors.Join to combine multiple errors while preserving… | [errors](references/errors.md#errors_join) |
| `errors_is` | 1.13 | Errors | Critical | Use errors.Is(err, target) instead of err == target… | [errors](references/errors.md#errors_is) |
| `time_tick_gc` | 1.23 | Time | Low | Use time.Tick when it fits; Go 1.23 can… | [time](references/time.md#time_tick_gc) |
| `time_until` | 1.8 | Time | Medium | Use time.Until(deadline) instead of deadline.Sub(time.Now()) | [time](references/time.md#time_until) |
| `time_since` | 1.0 | Time | High | Use time.Since(start) instead of time.Now().Sub(start) | [time](references/time.md#time_since) |
| `stdlib_uuid` | 1.27 | Utilities | Medium | Use the standard library uuid package instead of… | [utilities](references/utilities.md#stdlib_uuid) |
| `new_expression` | 1.26 | Utilities | High | Use new(value) for pointer fields or arguments instead… | [utilities](references/utilities.md#new_expression) |
| `cmp_or` | 1.22 | Utilities | High | Use cmp.Or to pick the first non-zero value… | [utilities](references/utilities.md#cmp_or) |
| `json_v2` | 1.27 | JSON | High | Use encoding/json/v2 for new JSON code in Go… | [json](references/json.md#json_v2) |
| `json_omitzero` | 1.24 | JSON | Medium | Use omitzero on JSON-tagged bool, numeric, struct, and… | [json](references/json.md#json_omitzero) |
| `range_over_int` | 1.22 | Loops | Critical | Use for i := range n when iterating… | [loops](references/loops.md#range_over_int) |
| `loopvar_capture` | 1.22 | Loops | High | Do not add redundant loop-variable copies before closures… | [loops](references/loops.md#loopvar_capture) |
| `http_servemux_patterns` | 1.22 | HTTP | Medium | Use method-aware ServeMux patterns and r.PathValue for path… | [http](references/http.md#http_servemux_patterns) |
| `fmt_appendf` | 1.19 | Fmt | Medium | Use fmt.Appendf when appending formatted text to a… | [fmt](references/fmt.md#fmt_appendf) |
| `url_clone` | 1.27 | URL | Low | Use the URL.Clone and Values.Clone methods from net/url… | [url](references/url.md#url_clone) |
| `testing_b_loop` | 1.24 | Testing | Medium | Use b.Loop() for the main loop in benchmark… | [testing](references/testing.md#testing_b_loop) |

## Rules of application

- Apply these rules to **new code and code you are already changing**. Do not refactor unrelated code in the same edit.
- Skip a rule when:
  - it does not compile on the target Go version;
  - it changes observable behavior (including wire format, error text, memory layout, timing);
  - it clearly does not match the surrounding code or intent.
- Existing code written in the older style is not a defect. Leave it alone unless the user asks for a migration.
- When a rule and local convention conflict, prefer the rule for edited lines, but keep the change minimal and reviewable.
- After edits, run the project's build/test/lint commands if they are known.

## Rules with caveats — read the reference before applying

- `json_v2` — use `encoding/json/v2` **only for new code**; migrating existing `encoding/json` can change wire behavior. See `references/json.md`.
- `new_expression` — `new` uses the default type of untyped constants (`new(30)` is `*int`, not `*time.Duration`/`*int32`). See `references/utilities.md`.
- `cmp_or` — **all** arguments are evaluated eagerly; avoid when later arguments are expensive or have side effects, or when `0`/`false` is a valid value. See `references/utilities.md`.
- `time_tick_gc` — GC can reclaim unreferenced tickers since Go 1.23; use `time.NewTicker` when you need `Stop`/`Reset`. See `references/time.md`.
- `generic_methods` — keep package-level helpers for operations that do not naturally belong to the receiver type. See `references/types.md`.
- `promoted_field_literals` — do not mix a promoted field with the embedded field that promotes it; pointer-embedded paths are unsupported. See `references/types.md`.
- `atomic_types` — replacing raw `int64`/`unsafe.Pointer` fields changes struct layout and size; `atomic.Value` differs from `atomic.Pointer[T]` in nil/type handling. Migrate deliberately, not call by call. See `references/sync.md`.
- `testing_t_context` — `t.Context()` is canceled **before** `t.Cleanup` functions run; cleanup that needs a live context must create its own. See `references/context.md`.

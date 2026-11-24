# Types

Правила категории **Types** из e001-ai-hub. Всего: 4.

## generic_methods

**Since:** Go 1.27 | **Impact:** Medium | **Category:** Types | **Analyzer:** —

Use generic methods instead of package-level generic helper functions when the operation naturally belongs to the type itself.

Generic methods keep operations in the namespace of the type that owns them. Keep package-level helpers for operations that do not naturally belong to one receiver type.

**Плохо (до):**

```go
type Set[T comparable] map[T]struct{}

func Map[T comparable, U any](s Set[T], f func(T) U) []U {
	out := make([]U, 0, len(s))
	for value := range s {
		out = append(out, f(value))
	}
	return out
}

names := Map(users, func(user User) string {
	return user.Name
})
```

**Хорошо (после):**

```go
type Set[T comparable] map[T]struct{}

func (s Set[T]) Map[U any](f func(T) U) []U {
	out := make([]U, 0, len(s))
	for value := range s {
		out = append(out, f(value))
	}
	return out
}

names := users.Map(func(user User) string {
	return user.Name
})
```

## promoted_field_literals

**Since:** Go 1.27 | **Impact:** Medium | **Category:** Types | **Analyzer:** modernize

Set embedded struct fields directly with promoted field names in Go 1.27+ struct literals instead of constructing the embedded struct explicitly.

Go 1.27 allows keyed struct literals to set fields promoted from embedded struct types directly. Use `Field: value` in the outer literal instead of `Embedded: Embedded{Field: value}` when you are just setting promoted fields. Do not mix a promoted field with the embedded field that promotes it; pointer-embedded paths are not supported.

**Плохо (до):**

```go
type AuditInfo struct {
	CreatedBy string
	UpdatedBy string
}

type Document struct {
	AuditInfo
	Name string
	Path string
}

doc := Document{
	AuditInfo: AuditInfo{
		CreatedBy: "alice",
		UpdatedBy: "alice",
	},
	Name: "report.pdf",
	Path: "/documents/report.pdf",
}
```

**Хорошо (после):**

```go
type AuditInfo struct {
	CreatedBy string
	UpdatedBy string
}

type Document struct {
	AuditInfo
	Name string
	Path string
}

doc := Document{
	CreatedBy: "alice",
	UpdatedBy: "alice",
	Name:      "report.pdf",
	Path:      "/documents/report.pdf",
}
```

## reflect_type_for

**Since:** Go 1.22 | **Impact:** Low | **Category:** Types | **Analyzer:** modernize

Use `reflect.TypeFor[T]()` instead of `reflect.TypeOf((*T)(nil)).Elem()`.

`reflect.TypeFor` returns the `reflect.Type` for a compile-time type parameter or type argument. It avoids `nil`-pointer tricks and is clearer for interface types.

**Плохо (до):**

```go
typ := reflect.TypeOf((*T)(nil)).Elem()
```

**Хорошо (после):**

```go
typ := reflect.TypeFor[T]()
```

## any

**Since:** Go 1.18 | **Impact:** Critical | **Category:** Types | **Analyzer:** modernize

Use `any` instead of `interface{}`.

`any` is the built-in alias for `interface{}` introduced with generics. Use it for unconstrained values and type parameters so the code reads in current Go terminology.

**Плохо (до):**

```go
func Decode(v interface{}) error {
	return nil
}
```

**Хорошо (после):**

```go
func Decode(v any) error {
	return nil
}
```


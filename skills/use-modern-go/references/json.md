# JSON

Правила категории **JSON** из e001-ai-hub. Всего: 2.

## json_v2

**Since:** Go 1.27 | **Impact:** High | **Category:** JSON | **Analyzer:** —

Use `encoding/json/v2` for new JSON code in Go 1.27+; leave existing `encoding/json` code unchanged unless migration is explicitly requested.

`encoding/json/v2` has stricter, more interoperable defaults: it rejects invalid UTF-8 and duplicate object names, encodes `nil` slices and maps as empty arrays and objects, and reports invalid JSON-related Go types. Prefer these defaults in new code. Do not replace `encoding/json` in existing code unless migration is explicitly requested, because even a compiling import change can alter wire behavior. For an explicit migration, begin with `jsonv1.DefaultOptionsV1()`, test serialized output and accepted input, then remove or override compatibility options deliberately; later options take precedence.

### Пример 1

**Плохо (до):**

```go
import "encoding/json"

type Pet struct {
	Name      string
	Nicknames []string
}

body, err := json.Marshal(Pet{Name: "Remi"})
// body is {"Name":"Remi","Nicknames":null}
```

**Хорошо (после):**

```go
import "encoding/json/v2"

type Pet struct {
	Name      string
	Nicknames []string
}

// New code uses v2's stricter defaults.
body, err := json.Marshal(Pet{Name: "Remi"})
// body is {"Name":"Remi","Nicknames":[]}
```

### Пример 2

**Плохо (до):**

```go
import "encoding/json"

type Pet struct {
	Name      string
	Nicknames []string
}

// Leave existing v1 code unchanged unless migration is requested.
body, err := json.Marshal(Pet{Name: "Remi"})
// Existing consumers receive {"Name":"Remi","Nicknames":null}.
```

**Хорошо (после):**

```go
import (
	jsonv1 "encoding/json"
	json "encoding/json/v2"
)

type Pet struct {
	Name      string
	Nicknames []string
}

// For an explicit migration, retain existing wire behavior first.
body, err := json.Marshal(
	Pet{Name: "Remi"},
	jsonv1.DefaultOptionsV1(),
)
// Existing consumers still receive {"Name":"Remi","Nicknames":null}.
```

### Пример 3

**Плохо (до):**

```go
import (
	jsonv1 "encoding/json"
	json "encoding/json/v2"
)

type Pet struct {
	Name      string
	Nicknames []string
}

body, err := json.Marshal(
	Pet{Name: "Remi"},
	jsonv1.DefaultOptionsV1(),
)
// body is {"Name":"Remi","Nicknames":null}
```

**Хорошо (после):**

```go
import (
	jsonv1 "encoding/json"
	json "encoding/json/v2"
)

type Pet struct {
	Name      string
	Nicknames []string
}

// Then adopt v2 behavior only after verifying consumers.
body, err := json.Marshal(
	Pet{Name: "Remi"},
	jsonv1.DefaultOptionsV1(),
	json.FormatNilSliceAsNull(false),
)
// body is {"Name":"Remi","Nicknames":[]}
```

## json_omitzero

**Since:** Go 1.24 | **Impact:** Medium | **Category:** JSON | **Analyzer:** modernize

Use `omitzero` on JSON-tagged bool, numeric, struct, and time fields whose zero value should be omitted; keep `omitempty` for empty strings, slices, and maps.

When adding or editing JSON struct tags, use `omitzero` when the Go zero value means the field is absent, such as `false`, `0`, or a zero time. Use `omitempty` when JSON empty-value semantics are intended, especially empty strings, slices, and maps.

**Плохо (до):**

```go
type CacheEntry struct {
	Name      string    `json:"name,omitempty"`
	Warm      bool      `json:"warm,omitempty"`
	Hits      int64     `json:"hits,omitempty"`
	ExpiresAt time.Time `json:"expiresAt,omitempty"`
}
```

**Хорошо (после):**

```go
type CacheEntry struct {
	Name      string    `json:"name,omitempty"`
	Warm      bool      `json:"warm,omitzero"`
	Hits      int64     `json:"hits,omitzero"`
	ExpiresAt time.Time `json:"expiresAt,omitzero"`
}
```


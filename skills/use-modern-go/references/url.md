# URL

Правила категории **URL** из e001-ai-hub. Всего: 1.

## url_clone

**Since:** Go 1.27 | **Impact:** Low | **Category:** URL | **Analyzer:** —

Use the `URL.Clone` and `Values.Clone` methods from `net/url` to copy URLs and `URL` values instead of manual copying.

`URL.Clone` and `Values.Clone` create deep copies using `net/url`'s own representation. They avoid partial manual copies that can accidentally share mutable slices or miss `URL` fields.

### Пример 1

**Плохо (до):**

```go
copy := new(url.URL)
*copy = *base
if base.User != nil {
	username := base.User.Username()
	if password, ok := base.User.Password(); ok {
		copy.User = url.UserPassword(username, password)
	} else {
		copy.User = url.User(username)
	}
}
```

**Хорошо (после):**

```go
copy := base.Clone()
```

### Пример 2

**Плохо (до):**

```go
copy := make(url.Values, len(values))
for key, items := range values {
	copy[key] = append([]string(nil), items...)
}
```

**Хорошо (после):**

```go
copy := values.Clone()
```


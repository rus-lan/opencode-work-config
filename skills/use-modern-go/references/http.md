# HTTP

Правила категории **HTTP** из e001-ai-hub. Всего: 1.

## http_servemux_patterns

**Since:** Go 1.22 | **Impact:** Medium | **Category:** HTTP | **Analyzer:** —

Use method-aware `ServeMux` patterns and `r.PathValue` for path parameters.

The modern `ServeMux` pattern syntax can include an HTTP method and named path wildcards. `r.PathValue` retrieves wildcard values without manual path trimming.

**Плохо (до):**

```go
mux.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	id := strings.TrimPrefix(r.URL.Path, "/api/")
	handleID(w, r, id)
})
```

**Хорошо (после):**

```go
mux.HandleFunc("GET /api/{id}", func(w http.ResponseWriter, r *http.Request) {
	handleID(w, r, r.PathValue("id"))
})
```


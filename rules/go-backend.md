---
name: go-backend
description: Go service patterns — project structure, error wrapping, middleware, testing
version: 1.2.1
---

# Go — Backend Rules

## Project Structure

- `cmd/` — entry points (main packages).
- `internal/` — private application code.
- `pkg/` — public libraries (if any).
- `api/` — API definitions (OpenAPI, protobuf).

## Error Handling

- Wrap errors with context: `fmt.Errorf("operation: %w", err)`.
- Define sentinel errors for known failure modes.
- Never ignore errors — handle or propagate.
- Log at the boundary where you handle the error, not where you create it.

## HTTP Services

- Router: gin (largest ecosystem, rich middleware, built-in validation/binding).
- Middleware chain: logging → auth → rate-limit → handler.
- Structured logging (slog or zerolog).
- Graceful shutdown with context cancellation.

## Concurrency

- Goroutines + channels for concurrent work.
- Always use `context.Context` for cancellation and timeouts.
- `sync.WaitGroup` for fan-out/fan-in.
- `errgroup` for concurrent operations that can fail.

## Testing

- Test names: `Test<Function>_<condition>`.
- Table-driven tests for multiple input/output scenarios.
- `httptest` for HTTP handler testing.
- Mock interfaces, not concrete types.

## Code Style

- `gofmt` and `goimports` on save.
- Short variable names in small scopes, descriptive in large.
- Accept interfaces, return structs.
- No `init()` unless absolutely necessary.

## Observability

Любой сервис ОБЯЗАН использовать `bootstrap.InitObservability` + `bootstrap.GRPCServerOptions` / `bootstrap.GinMiddleware`. Кастомное wiring логгера, tracer-а, метрик через прямой вызов библиотек запрещён.

Полный набор правил — см. `go-observability.md`.
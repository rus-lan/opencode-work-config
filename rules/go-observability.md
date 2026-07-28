---
name: go-observability
description: Go observability patterns — logging, metrics, tracing, health checks
version: 1.0.0
---

# Go — Observability Rules

## Initialization (Mandatory)

Любой сервис ОБЯЗАН использовать `bootstrap.InitObservability` + `bootstrap.GRPCServerOptions` / `bootstrap.GinMiddleware`. Кастомное wiring логгера, tracer-а, метрик через прямой вызов библиотек запрещён.

## Logging (Structured with slog)

- Use `log/slog` (Go 1.21+) for structured logging.
- Log levels: `Debug` (development), `Info` (normal ops), `Warn` (unexpected but handled), `Error` (failures needing attention).
- Always include structured attributes: `slog.String("key", val)`, `slog.Any("struct", s)`.
- Log at the boundary where you handle the error, not where you create it.
- Never log sensitive data (PII, secrets, tokens).
- Use contextual logging via `slog.With("request_id", rid)` in middleware.

```go
slog.Info("request completed",
    slog.String("method", r.Method),
    slog.String("path", r.URL.Path),
    slog.Int("status", w.StatusCode),
    slog.Duration("duration", d),
)
```

## Metrics (OpenTelemetry + Prometheus)

- Use OpenTelemetry SDK for metrics; export via Prometheus exporter.
- Define metrics in dedicated `internal/metrics/` package.
- Standard metrics per service:
  - `http_requests_total` (counter, labels: method, path, status)
  - `http_request_duration_seconds` (histogram, labels: method, path)
  - `requests_in_flight` (gauge)
- Use `bootstrap.GinMiddleware` — it wires metrics automatically.
- Use `bootstrap.GRPCServerOptions` for gRPC metrics.

## Tracing (OpenTelemetry Distributed Tracing)

- Use OpenTelemetry SDK for distributed tracing.
- Propagate context across service boundaries via gRPC metadata or HTTP headers.
- Span naming: `<package>.<function>` or `<http_method> <path>`.
- Add semantic attributes: `http.method`, `http.url`, `http.status_code`, `db.statement`.
- Use `bootstrap.InitObservability` to configure the TracerProvider.

```go
ctx, span := tracer.Start(r.Context(), "service.GetUser")
defer span.End()
span.SetAttributes(attribute.String("user.id", userID))
```

## Error Tracking and Reporting

- Wrap errors with `fmt.Errorf("context: %w", err)` for traceability.
- Report unrecoverable errors to error tracking (Sentry or similar) at the service boundary.
- Do not report expected errors (validation, 4xx) — only 5xx and panics.
- Recover panics in HTTP/gRPC middleware and report them.

## Health Checks and Readiness Probes

- Expose `/healthz` (liveness) and `/readyz` (readiness) endpoints.
- Liveness: simple OK response — service is running.
- Readiness: checks dependencies (DB, queue, upstream) — service can accept traffic.
- Use `bootstrap.InitObservability` for automatic health endpoint registration.

## Common Go Observability Patterns

1. **Middleware-based instrumentation** — inject observability in HTTP/gRPC middleware, not in handlers.
2. **Context propagation** — pass `context.Context` through the call chain; extract trace info at boundaries.
3. **Structured attributes everywhere** — no printf-style logging; use key-value pairs.
4. **Metrics + tracing correlation** — use `trace_id` and `span_id` as metric labels for correlation.
5. **Graceful shutdown** — flush remaining traces/metrics on SIGTERM/SIGINT via `bootstrap` lifecycle hooks.
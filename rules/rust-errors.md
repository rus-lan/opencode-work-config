---
name: rust-errors
description: Error handling — error enums, context, severity levels, thiserror/anyhow patterns
version: 1.1.0
---

# Rust — Error Handling

## Philosophy

- Single error enum per crate/module. No `String` errors, no `.unwrap()`, no `panic!()`.
- Every error variant carries context: which component failed, human-readable message.
- Errors have severity: Warning (continue), Error (stop), Fatal (misconfiguration).
- Always log before returning an error — no silent failures.

## Pattern

```rust
// Good — explicit error with context
.map_err(|e| MyError::ComponentError {
    component: "name".into(),
    message: format!("Failed to process: {e}"),
})?;

// Bad — loses context
.unwrap();
.expect("should work");
.map_err(|e| e.to_string())?;
```

```rust
// Good — log then return
error!("[component] Failed to load: {e}");
return Err(MyError::LoadFailed { ... });

// Bad — silent error
return Err(MyError::LoadFailed { ... });
```

## Derive

- Use `thiserror` for error enum derivation.
- Map external errors explicitly — never expose raw library errors.

## Mutex / Lock Errors

- Never `.unwrap()` on mutex locks.
- Use a dedicated error variant with context string.

## Severity Rules

| Severity | Meaning | Behavior |
|----------|---------|----------|
| Warning  | Non-critical, can continue | Log + continue |
| Error    | Operation failed, stop | Log + return Err |
| Fatal    | Configuration wrong, cannot run | Log + return Err, show to user |
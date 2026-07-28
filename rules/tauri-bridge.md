---
name: tauri-bridge
description: Tauri-React bridge — IPC commands, events, state management, error handling, security, plugins
version: 1.1.0
---

# Tauri v2 — Integration Rules

## Commands

### Definition

- Every command returns `Result<T, Error>`. Never return bare types — the frontend needs to distinguish success from failure.
- Async commands are the default. Use sync only for trivial, non-blocking operations (reading a config value from memory).
- Annotate with `#[tauri::command]` and register in `invoke_handler(tauri::generate_handler![...])`.
- Organize commands in `src-tauri/src/commands/` with one file per domain (e.g., `settings.rs`, `files.rs`, `auth.rs`). Re-export from `commands/mod.rs`.

```rust
// Good — async, returns Result, organized by domain
#[tauri::command]
async fn save_settings(
    state: tauri::State<'_, Mutex<AppState>>,
    settings: UserSettings,
) -> Result<(), Error> {
    let mut state = state.lock().map_err(|_| Error::StateLock("AppState"))?;
    state.settings = settings;
    state.persist()?;
    Ok(())
}

// Bad — sync, no error handling, bare return
#[tauri::command]
fn save_settings(settings: UserSettings) {
    // where does this even go?
}
```

### Argument Conventions

- Rust commands use `snake_case` parameters. Tauri auto-converts from frontend `camelCase`.
- If you need to keep snake_case on both sides, annotate: `#[tauri::command(rename_all = "snake_case")]`.
- Arguments must implement `serde::Deserialize`. Return types must implement `serde::Serialize`.
- Async commands cannot borrow arguments (`&str`, `State<'_, T>`). Use owned types (`String`) or wrap the return in `Result` to work around the lifetime limitation.

### Accessing Injected Types

Commands can inject these types as parameters — Tauri provides them automatically:

| Type | Purpose |
|------|---------|
| `tauri::State<'_, T>` | Managed application state |
| `tauri::AppHandle` | App-wide operations (paths, events, global shortcuts) |
| `tauri::WebviewWindow` | Current webview (label, position, title) |
| `tauri::ipc::Channel<T>` | Streaming data back to a specific frontend caller |
| `tauri::ipc::Request` | Raw IPC request (headers, binary body) |

### Binary Data and Large Payloads

- All standard IPC is JSON-serialized. This is slow for large data (files, images, downloads).
- For large backend-to-frontend transfers, return `tauri::ipc::Response` wrapping raw bytes — avoids JSON serialization entirely.
- For large frontend-to-backend transfers, accept `tauri::ipc::Request` and extract `InvokeBody::Raw`.
- For streaming (download progress, file chunking), use `tauri::ipc::Channel<T>` instead of events.

```rust
// Good — binary response, no JSON overhead
use tauri::ipc::Response;

#[tauri::command]
fn read_file(path: PathBuf) -> Result<Response, Error> {
    let data = std::fs::read(&path)?;
    Ok(Response::new(data))
}

// Good — binary upload with headers
#[tauri::command]
fn upload(request: tauri::ipc::Request) -> Result<(), Error> {
    let tauri::ipc::InvokeBody::Raw(data) = request.body() else {
        return Err(Error::ExpectedRawBody);
    };
    let auth = request.headers().get("Authorization")
        .ok_or(Error::MissingHeader("Authorization"))?;
    // process upload...
    Ok(())
}
```

### Channel Streaming

Use `Channel<T>` when the backend needs to push multiple messages to the frontend within a single command invocation. Channels are ordered and fast — prefer them over events for command-scoped streaming.

```rust
// Rust — streaming progress
#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase", tag = "event", content = "data")]
enum DownloadEvent<'a> {
    Started { url: &'a str, content_length: usize },
    Progress { percent: u8 },
    Finished,
}

#[tauri::command]
async fn download(url: String, on_event: Channel<DownloadEvent<'_>>) -> Result<(), Error> {
    on_event.send(DownloadEvent::Started { url: &url, content_length: 1000 })?;
    for pct in [25, 50, 75, 100] {
        on_event.send(DownloadEvent::Progress { percent: pct })?;
    }
    on_event.send(DownloadEvent::Finished)?;
    Ok(())
}
```

```typescript
// Frontend — receiving channel messages
import { invoke, Channel } from '@tauri-apps/api/core';

const onEvent = new Channel<DownloadEvent>();
onEvent.onmessage = (msg) => {
  if (msg.event === 'progress') console.log(`${msg.data.percent}%`);
};
await invoke('download', { url: 'https://example.com/file', onEvent });
```

## Error Handling

### Error Enum

- Single error enum per crate. All variants carry context.
- Use `thiserror` for `Display`/`Error` derives.
- Manually implement `serde::Serialize` — `thiserror` does not do this and `#[derive(Serialize)]` on error enums with `#[from]` variants fails because source errors are not serializable.

```rust
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("state lock poisoned: {0}")]
    StateLock(&'static str),

    #[error("not found: {0}")]
    NotFound(String),

    #[error("validation: {0}")]
    Validation(String),
}

// REQUIRED — serialize as string for simple errors
impl serde::Serialize for Error {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::ser::Serializer,
    {
        serializer.serialize_str(self.to_string().as_ref())
    }
}
```

### Structured Errors (Recommended for Frontend Matching)

When the frontend needs to match on error kind (show different UI for "not found" vs "validation"), use a tagged serialization wrapper:

```rust
#[derive(serde::Serialize)]
#[serde(tag = "kind", content = "message")]
#[serde(rename_all = "camelCase")]
enum ErrorPayload {
    Io(String),
    NotFound(String),
    Validation(String),
    StateLock(String),
}

impl serde::Serialize for Error {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::ser::Serializer,
    {
        let payload = match self {
            Self::Io(e) => ErrorPayload::Io(e.to_string()),
            Self::NotFound(msg) => ErrorPayload::NotFound(msg.clone()),
            Self::Validation(msg) => ErrorPayload::Validation(msg.clone()),
            Self::StateLock(name) => ErrorPayload::StateLock(name.to_string()),
        };
        payload.serialize(serializer)
    }
}
```

```typescript
// Frontend — typed error handling
type CommandError = {
  kind: 'io' | 'notFound' | 'validation' | 'stateLock';
  message: string;
};

try {
  await invoke('save_settings', { settings });
} catch (e) {
  const err = e as CommandError;
  if (err.kind === 'validation') showValidationError(err.message);
  else showGenericError(err.message);
}
```

### Anti-patterns

```rust
// BAD — loses error context, no matching on frontend
Result<T, String>

// BAD — panics crash the process
.unwrap()
.expect("should never happen")

// BAD — raw library errors leak implementation details
#[error(transparent)]
Anyhow(#[from] anyhow::Error) // anyhow is for apps, not IPC boundaries
```

## Event System

### When to Use Events vs Commands vs Channels

| Mechanism | Direction | Use Case |
|-----------|-----------|----------|
| Commands (`invoke`) | Frontend -> Backend -> Frontend | Request/response, CRUD operations |
| Channels | Backend -> Frontend (within a command) | Streaming within one operation (progress, chunks) |
| Events (`emit`) | Backend -> Frontend (any time) | Lifecycle changes, background notifications, multi-consumer broadcasts |
| Events (`emit`) | Frontend -> Backend | Rarely needed — prefer commands |

### Emission from Rust

```rust
// Global event — all listeners receive it
app_handle.emit("settings-changed", &new_settings)?;

// Targeted event — only "main" webview receives it
app_handle.emit_to("main", "auth-expired", ())?;

// Filtered — conditional delivery
app_handle.emit_filter("notification", &payload, |target| {
    target.label() != "settings"
})?;
```

### Typed Event Payloads

- Always derive `Clone + Serialize` on event payloads.
- Use `#[serde(rename_all = "camelCase")]` so the frontend receives camelCase keys.
- Event payloads are JSON-serialized. Keep them small — events are not designed for large data.

```rust
#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct SettingsChanged {
    theme: String,
    language: String,
    changed_at: u64,
}

app.emit("settings-changed", SettingsChanged {
    theme: "dark".into(),
    language: "en".into(),
    changed_at: now(),
})?;
```

### Frontend Listening

```typescript
import { listen, once } from '@tauri-apps/api/event';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';

// Global listener — receives from emit()
const unlisten = await listen<SettingsChanged>('settings-changed', (event) => {
  applySettings(event.payload);
});

// Webview-specific listener — receives from emit_to("main", ...)
const appWindow = getCurrentWebviewWindow();
const unlisten2 = await appWindow.listen<string>('auth-expired', (event) => {
  redirectToLogin();
});

// One-time listener
await once('app-ready', () => hideLoadingScreen());
```

### Critical Rule: Cleanup Listeners

Webview-specific events are NOT received by global listeners and vice versa. Always call `unlisten()` in React cleanup to prevent memory leaks:

```typescript
useEffect(() => {
  const promise = listen<Payload>('my-event', handler);
  return () => { promise.then((unlisten) => unlisten()); };
}, []);
```

## State Management

### Setup

- Register state in the builder's `setup` closure using `app.manage()`.
- For mutable state, wrap in `std::sync::Mutex`. Tauri wraps state in `Arc` internally — you do not need `Arc<Mutex<T>>`.
- Use `tokio::sync::Mutex` only when holding the lock across `.await` points (e.g., async DB operations). Prefer `std::sync::Mutex` for everything else — it is faster and recommended by Tokio's own docs.

```rust
use std::sync::Mutex;

#[derive(Default)]
struct AppState {
    settings: UserSettings,
    counter: u32,
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            app.manage(Mutex::new(AppState::default()));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_count, increment])
        .run(tauri::generate_context!())
        .unwrap();
}
```

### Accessing State

```rust
// In commands — inject as parameter
#[tauri::command]
fn get_count(state: tauri::State<'_, Mutex<AppState>>) -> Result<u32, Error> {
    let state = state.lock().map_err(|_| Error::StateLock("AppState"))?;
    Ok(state.counter)
}

// Outside commands — from AppHandle (event handlers, setup, plugins)
fn on_some_event(app: &tauri::AppHandle) {
    let state = app.state::<Mutex<AppState>>();
    let mut state = state.lock().unwrap();
    state.counter += 1;
}
```

### Type Alias to Prevent Runtime Panics

If you register `Mutex<AppState>` but request `State<'_, AppState>` (forgetting the Mutex wrapper), Tauri panics at runtime with no compile-time warning. Use a type alias to make the mistake obvious:

```rust
// Define once
type ManagedAppState = Mutex<AppState>;

// Register
app.manage(ManagedAppState::default());

// Use — the alias makes the Mutex wrapper visible
#[tauri::command]
fn get_count(state: tauri::State<'_, ManagedAppState>) -> Result<u32, Error> {
    let state = state.lock().map_err(|_| Error::StateLock("AppState"))?;
    Ok(state.counter)
}
```

### Anti-patterns

```rust
// BAD — .unwrap() on Mutex. If any thread panics while holding the lock, this poisons
// the Mutex and all subsequent .unwrap() calls panic too. Use .map_err() instead.
state.lock().unwrap()

// BAD — holding lock across await points with std::sync::Mutex. This blocks the
// entire thread pool. Use tokio::sync::Mutex if you must hold across awaits.
let guard = state.lock().unwrap();
some_async_fn().await; // guard is still held!

// BAD — Arc<Mutex<T>> when using tauri::State. Tauri already wraps in Arc.
app.manage(Arc::new(Mutex::new(state)))
```

## TypeScript Bindings

### Manual Approach (Default)

Keep TypeScript types that mirror Rust command args and return types in a dedicated file (e.g., `src/types/tauri.ts`). Update manually when Rust changes.

```typescript
// src/types/tauri.ts
export interface UserSettings {
  theme: string;
  language: string;
}

export interface CommandError {
  kind: 'io' | 'notFound' | 'validation' | 'stateLock';
  message: string;
}

// src/hooks/useSettings.ts
import { invoke } from '@tauri-apps/api/core';
import type { UserSettings } from '@/types/tauri';

export async function getSettings(): Promise<UserSettings> {
  return invoke<UserSettings>('get_settings');
}
```

### Automated Approach (tauri-specta)

For larger projects, use `tauri-specta` to auto-generate TypeScript bindings from Rust types at build time. This eliminates manual sync and catches type mismatches at compile time.

```rust
// Rust — annotate commands and types with specta
#[derive(serde::Serialize, specta::Type)]
struct UserSettings { /* ... */ }

#[tauri::command]
#[specta::specta]
async fn get_settings(/* ... */) -> Result<UserSettings, Error> { /* ... */ }
```

Both events and commands get generated bindings. Frontend imports them directly instead of calling `invoke` with string names.

## Security

### Capabilities (Least Privilege)

- Define capability files in `src-tauri/capabilities/` as JSON or TOML.
- One capability file per window or per feature group. Never use a single "allow everything" capability.
- All files in `capabilities/` are automatically enabled. Reference specific ones in `tauri.conf.json` if you want selective loading.

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "main-window",
  "description": "Capabilities for the main application window",
  "windows": ["main"],
  "permissions": [
    "core:path:default",
    "core:event:default",
    "core:window:default",
    "core:app:default",
    "fs:allow-read-file",
    "fs:allow-write-file"
  ]
}
```

### Permission Naming

Permissions follow the pattern `plugin:action` or `core:module:action`:

| Pattern | Example | Meaning |
|---------|---------|---------|
| `allow-*` | `fs:allow-read-file` | Explicitly permits a command |
| `deny-*` | `fs:deny-write-file` | Explicitly blocks a command |
| `default` | `core:path:default` | Plugin's recommended safe defaults |

### Remote URL Access

If your app loads remote content that needs Tauri API access, configure it explicitly:

```json
{
  "identifier": "remote-api",
  "remote": {
    "urls": ["https://*.your-domain.com"]
  },
  "permissions": ["core:event:default"]
}
```

Warning: On Linux and Android, Tauri cannot distinguish between requests from an embedded `<iframe>` and the window itself. Be cautious with remote access grants.

### Content Security Policy

- Set CSP in `tauri.conf.json` under `app.security.csp`. Tauri auto-appends nonces/hashes for bundled scripts at compile time.
- Start strict, loosen only as needed. Avoid `unsafe-inline` for scripts.
- Never load scripts from CDNs — they are attack vectors. Bundle everything.
- If using WASM, add `'wasm-unsafe-eval'` to `script-src`.

### Platform Targeting

Capabilities can be limited to specific platforms:

```json
{
  "identifier": "desktop-only",
  "platforms": ["linux", "macOS", "windows"],
  "permissions": ["global-shortcut:allow-register"]
}
```

## Plugin Architecture

### When to Extract a Plugin

Extract into a plugin when functionality: (a) is reusable across multiple Tauri apps, (b) needs native mobile code (Kotlin/Swift), or (c) has its own permission scope. For app-internal modules, plain Rust modules with commands are simpler.

### Plugin Structure

```
tauri-plugin-{name}/
  src/
    commands.rs    # Plugin commands
    desktop.rs     # Desktop-specific implementation
    mobile.rs      # Mobile-specific implementation
    error.rs       # Plugin error types
    lib.rs         # Setup, lifecycle hooks, exports
    models.rs      # Shared data structures
  permissions/     # Permission TOML/JSON files
  guest-js/        # TypeScript API bindings
```

### Lifecycle Hooks

| Hook | Purpose |
|------|---------|
| `setup` | Initialize state, spawn background tasks |
| `on_navigation` | Validate/block webview navigation (return `false` to block) |
| `on_webview_ready` | Run code when a new webview is created |
| `on_event` | Respond to app events (exit, window events, menu) |
| `on_drop` | Cleanup on plugin destruction |

### Plugin Permissions

Define in `permissions/` directory. Commands declared in `build.rs` auto-generate `allow-*` and `deny-*` permissions:

```rust
// build.rs
const COMMANDS: &[&str] = &["start_scan", "stop_scan"];
fn main() {
    tauri_plugin::Builder::new(COMMANDS).build();
}
```

## Dev vs Prod

- Separate configs: `tauri.conf.json` (prod), `tauri.dev.conf.json` (dev overlay).
- Different app identifiers -> different data dirs -> no conflicts.
- Dev: HTTP, localhost API, dev badge in header, relaxed CSP.
- Prod: HTTPS, updater, production API, strict CSP.
- `pnpm dev` -> dev config. `pnpm build` -> prod config.

## Settings Storage

- Backend: Rust struct persisted as JSON in Tauri `app_data_dir`.
- Frontend: `useSettings()` singleton hook via `useSyncExternalStore`.
- Settings file and pipeline/flow configs are separate — never mix.
- Always persist through a command (invoke `save_settings`) — never write directly from the frontend.

## Anti-patterns Summary

| Anti-pattern | Why It Is Wrong | Do This Instead |
|--------------|----------------|-----------------|
| `invoke` with string error | Frontend cannot match on error kind | Structured error enum with tagged serialization |
| `.unwrap()` on Mutex lock | Poisoned mutex cascading panics | `.map_err()` to custom Error variant |
| Events for large data | JSON-only, not designed for throughput | `Channel<T>` or `ipc::Response` |
| Global "allow-all" capability | Violates least privilege | One capability file per window/feature |
| `Arc<Mutex<T>>` in managed state | Tauri already wraps in Arc | `Mutex<T>` directly |
| Bare return type (no Result) | Frontend cannot catch errors | Always `Result<T, Error>` |
| Sync command for I/O | Blocks the main thread | Async command |
| CDN scripts in webview | XSS attack vector | Bundle all scripts |
| Forgetting `unlisten()` | Memory leak in SPA | Cleanup in `useEffect` return |
| `State<'_, T>` without matching `manage(T)` | Runtime panic, no compile error | Type alias for managed state type |

---
name: frontend-hooks
description: Hook patterns — one per concern, standardized returns, naming conventions
version: 1.3.0
---

# Frontend — Hook Patterns

## Convention

- One hook per concern: `useSettings`, `useTheme`, `useNotifications`, etc.
- All shared hooks live in `hooks/`.
- Feature-specific hooks live in `features/<name>/hooks/`.

## File Naming

- Hook file: **camelCase** matching the hook name — `useTheme.ts`, `useSettings.ts`, `useNotifications.ts`
- One hook per file, file name = hook name
- DON'T use kebab-case for hook files (`use-theme.ts` — wrong)

## Return Pattern

Every data-fetching hook returns:
```typescript
{
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
}
```

## State Management

- Local state: `useState`, `useReducer`.
- Shared state: `useSyncExternalStore` for module-level singletons.
- Server state: dedicated hooks wrapping fetch/invoke calls.
- Never use global mutable variables outside of React state primitives.

## Rules

- Hooks must be pure — no side effects outside of `useEffect`.
- Cleanup functions in every `useEffect` that subscribes to something.
- Dependencies array must be explicit — no eslint-disable for exhaustive-deps.
- Custom hooks are prefixed with `use`.
- Unused parameters must be prefixed with `_` (not removed). `_event`, `_index`, `_ref` signal "parameter exists in the signature but is intentionally unused." Removing `_` later makes it immediately usable without changing the function signature.
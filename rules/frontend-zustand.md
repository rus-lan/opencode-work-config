---
name: frontend-zustand
description: Zustand store patterns — creation, middleware, persistence, actions, naming conventions
version: 1.2.0
---

# Frontend Zustand

Rules for creating and maintaining Zustand stores.

## Directory Structure

- All stores live in a single directory `src/stores/`. One file per store, one store per domain concern.
- Do NOT create multiple store directories (e.g., `stores/` + `zustand/` + `state/`). Single directory only.

## Naming

| Entity | Convention | Example |
|--------|-----------|---------|
| Hook | `useXxxStore` | `useAppStore`, `useLayoutStore` |
| File | `xxxStore.ts` | `appStore.ts`, `layoutStore.ts` |
| Type | `XxxStore` | `AppStore`, `LayoutStore` |
| localStorage key | `'xxxStore'` | `'appStore'`, `'layoutStore'` |
| DevTools key | same as localStorage key | `'appStore'` |

## Store Creation Pattern

Every store follows this structure:

```ts
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

type MyStore = {
  count: number;
  name: string;
};

const defaultMyStore = (): MyStore => ({
  count: 0,
  name: '',
});

export const useMyStore = create(
  devtools(
    persist<MyStore>(defaultMyStore, {
      name: 'myStore',
      partialize: (state) =>
        ({
          name: state.name,
        }) as MyStore,
    }),
    { name: 'myStore' },
  ),
);
```

Key points:

- **Default factory**: every store has a `defaultXxxStore()` function returning initial state. Used for both creation and reset.
- **Middleware order**: `create(devtools(persist(...)))` — devtools wraps persist. Order matters.
- **DevTools always on**: stores without persistence still use `devtools` for Redux DevTools debugging.

## Persistence

### Selective persistence with partialize

Only user-facing settings go to localStorage. Transient state (focus flags, temporary UI state) is excluded:

```ts
partialize: (state) =>
  ({
    theme: state.theme,
    language: state.language,
    // isInputFocused — NOT persisted (transient)
    // isLoading — NOT persisted (transient)
  }) as MyStore,
```

### Empty partialize

For stores that need persist infrastructure but save nothing (ephemeral session data):

```ts
partialize: () => ({}) as MyStore,
```

### Debounced storage

For stores with frequent updates (resize, drag) — prevents excessive writes to localStorage:

```ts
import { createJSONStorage } from 'zustand/middleware';
import type { StateStorage } from 'zustand/middleware';

const debouncedStorage: StateStorage = (() => {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  return {
    getItem: (name) => localStorage.getItem(name),
    setItem: (name, value) => {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        localStorage.setItem(name, value);
        timeoutId = null;
      }, 500);
    },
    removeItem: (name) => {
      if (timeoutId) clearTimeout(timeoutId);
      localStorage.removeItem(name);
    },
  };
})();

// Usage in persist config:
storage: createJSONStorage(() => debouncedStorage),
```

## Actions Pattern

### External helper functions (default)

Actions are exported as standalone functions outside the store. They use `getState()` / `setState()` for synchronous access:

```ts
export const setMyStore = (data: Partial<MyStore>) => {
  useMyStore.setState((state) => ({ ...state, ...data }));
};

export const resetMyStore = () => {
  useMyStore.persist.clearStorage();
  useMyStore.setState(defaultMyStore());
};

export const getMyState = () => useMyStore.getState();
```

Standard helper set per store:

- `setXxxStore(data: Partial<XxxStore>)` — merge partial update
- `resetXxxStore()` — clear storage + reset to defaults
- `getXxxState()` (optional) — synchronous read outside React

### Internal actions (exception)

Complex stores (e.g., modal stack) can have actions inside `create()` when the action needs direct access to `set` closure:

```ts
export const useModalStore = create<ModalState>((set) => ({
  modals: [],
  openModal: (config) => {
    const id = makeId();
    set((state) => ({ modals: [...state.modals, { ...config, id }] }));
    return id;
  },
}));
```

### Reset order

When resetting a persisted store — always `clearStorage()` first, then `setState(defaults)`. This prevents a race where persist rewrites localStorage with the new state before storage is cleared:

```ts
// DO
export const resetMyStore = () => {
  useMyStore.persist.clearStorage();   // 1. clear storage
  useMyStore.setState(defaultMyStore()); // 2. then reset state
};

// DON'T
export const resetMyStore = () => {
  useMyStore.setState(defaultMyStore()); // persist writes to storage immediately
  useMyStore.persist.clearStorage();     // too late — stale data already written
};
```

## Anti-patterns

### DON'T store server data in Zustand

API responses belong in TanStack Query. Zustand is for client-only state.

```ts
// DON'T
const useUserStore = create(() => ({
  user: null, // fetched from API
  fetchUser: async () => { ... },
}));

// DO — use TanStack Query for server state
const { data: user } = useGetMe();
```

### DON'T subscribe to the entire store

Always use a selector. Without a selector, the component re-renders on every store change:

```ts
// DON'T
const store = useAppStore(); // re-renders on ANY change

// DO
const theme = useAppStore((s) => s.theme); // re-renders only when theme changes
```

### DON'T duplicate state between stores

If two stores need the same data — extract to a shared store or pass via function parameters.

### DON'T put business logic in stores

Stores hold state and simple mutations only. Side effects (API calls, navigation, timers) belong in hooks or services.

### DON'T use `any` in store types

For heterogeneous data (modal stack, notification queue), use generics:

```ts
// DON'T
modals: any[];

// DO
modals: ModalConfig<unknown>[];
```

### Prefix unused parameters with `_`

When a store creation callback receives parameters (`set`, `get`) that are not used (e.g., because the store uses the external actions pattern), prefix them with `_` instead of removing them:

```ts
// DON'T — hides that the parameter exists
create(devtools<MyStore>(() => ({ ...defaultMyStore() }), { name: 'myStore' }))

// DO — shows the contract: set is available but intentionally unused
create(devtools<MyStore>((_set) => ({ ...defaultMyStore() }), { name: 'myStore' }))

// DO — same for get
create(devtools<MyStore>((_set, _get) => ({ ...defaults() }), { name: 'myStore' }))
```

This improves readability: `_set` signals "Zustand provides `set`, but this store uses external `setXxxStore()` helpers instead." Removing `_` in the future makes the parameter immediately usable without changing the function signature.
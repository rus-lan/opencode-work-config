---
name: frontend-theme
description: Self-contained theme module — CSS variables, data-theme switching, Vite plugin, code generation, ThemeBox variants, multi-scope (Electron multi-window), Tailwind v4 layer cascade
version: 3.1.0
---

# Frontend — Theme Module

Self-contained module for theme management. Everything lives in one folder (typically `src/theme/` or `packages/ui/src/theme/`) — CSS, config, generation scripts, Vite plugin, UI components, hooks. The folder is **portable**: copy it into any Vite+Tailwind v4+React project, register the Vite plugin, run the generator, done.

## Module Structure

```
theme/
  config.ts                 — MANUAL: BASE_THEME, THEME_SCOPES, isThemeScope
  themes.generated.ts       — AUTO-GEN: AVAILABLE_THEMES, ThemeName, isThemeName
  index.ts                  — MANUAL: public re-exports + `import './index.css'`
  index.css                 — MANUAL: imports all themes + _tailwind
  plugin.ts                 — MANUAL: Vite plugin (theme-watcher)
  script.ts                 — MANUAL: generator (_base.css → AUTO-GEN artefacts)
  telegram-script.ts        — MANUAL: .tdesktop-palette.txt → .base CSS fragment

  ThemeProvider.tsx         — MANUAL: React provider (scope context)
  useTheme.ts               — MANUAL: hook (LIVES IN theme/, not src/hooks/)
  store.ts                  — MANUAL: external store (useSyncExternalStore)
  adapters.ts               — MANUAL: storage + broadcast adapter interfaces
  notification-override.ts  — MANUAL (optional, Electron multi-window only)

  {theme-name}/             — One dir per theme. Folder name is the theme name.
    _base.css               — MANUAL: source of truth, ALL vars live in `.base { ... }`
    _new.css                — AUTO-GEN: [data-theme="X"] selectors with merged vars
    index.css               — MANUAL: `@import './_new.css';`

  _tailwind/
    index.css               — MANUAL: imports tailwind + sub-files
    _colors.css             — AUTO-GEN: @theme inline with --color-* tokens
    _custom-variant.css     — MANUAL: `@custom-variant dark (...)` declarations
    _radius.css, _text.css, _heights.css, _animations.css  — MANUAL (optional)

  _ui/
    ThemeBox.tsx            — MANUAL: <ThemeBox variant=...> wrapper
    types.ts                — AUTO-GEN: type ThemeBoxVariant union
```

## Rules

- **All CSS variables lives in `<theme-name>/_base.css` under one `.base { ... }` block.** Class name is always `.base` — NOT `.dark`, NOT `[data-theme="dark"]`. The theme name is derived from the folder name.
- **AUTO-GEN files are off-limits to humans.** Never edit `_new.css`, `_tailwind/_colors.css`, `_ui/types.ts`, `themes.generated.ts` — they are rewritten on every generator run.
- **`useTheme` lives in `theme/useTheme.ts`**, not in `src/hooks/`. Module owns its own hook.
- **Global styles do NOT live in `theme/`.** Scrollbar styles, mesh backgrounds, titlebar layout, body typography — anywhere outside `theme/`. The theme module owns ONLY colors, theme switching, and Tailwind theme tokens.
- **BASE_THEME defines the full palette.** Other themes (in `<other>/_base.css`) define only the **diff** from BASE_THEME — the generator merges base+override into each `_new.css`.

## Theme Switching Mechanism

Themes switch via `data-theme` attribute on `<html>`:

```html
<html data-theme="dark">
```

The generator emits `[data-theme="X"] { ... }` selectors per theme. CSS cascade does the rest.

## Source of Truth and Inheritance

### `config.ts` (MANUAL)

```ts
import type { ThemeName } from './themes.generated'

export const THEME_SCOPES = ['app'] as const            // add 'notification', 'about' for Electron multi-window
export type ThemeScope = (typeof THEME_SCOPES)[number]

export const BASE_THEME: ThemeName = 'dark'             // the source-of-truth theme
export const isThemeScope = (v: unknown): v is ThemeScope => ...
```

### `themes.generated.ts` (AUTO-GEN)

```ts
export const AVAILABLE_THEMES = ['dark', 'light', 'blue'] as const
export type ThemeName = (typeof AVAILABLE_THEMES)[number]
export const isThemeName = (v: unknown): v is ThemeName => ...
```

The generator builds this file by scanning `theme/index.css` imports.

### Inheritance model

1. `BASE_THEME` (`dark/_base.css`) defines the **complete** set of CSS variables in its `.base { ... }` block.
2. Other themes (`light/_base.css`, `blue/_base.css`) define **only what differs** from BASE_THEME — also inside `.base { ... }`.
3. Generator merges per-theme: `{ ...baseTheme, ...themeOverrides }` → `_new.css`. Result: every `[data-theme="X"]` block contains the full set, with theme-specific overrides where applicable.

```
dark/_base.css   (full palette, ~30 vars)        ← SOURCE
  ├─ light/_base.css   (overrides only, ~20 vars)
  └─ blue/_base.css    (overrides only, ~25 vars)
```

## `.base` Convention (CRITICAL)

Every theme's `_base.css` follows the exact same class name — `.base`. The folder name carries the theme identity.

```css
/* dark/_base.css */
.base {
	--color-background: oklch(0.18 0 0);
	--color-foreground: oklch(0.96 0 0);
	--color-primary: oklch(0.62 0.19 260);
	/* ... */
}

/* light/_base.css — only the diffs */
.base {
	--color-background: oklch(1 0 0);
	--color-foreground: oklch(0.18 0 0);
	/* ... */
}
```

The `.base` selector is consumed by the generator. The runtime sees `[data-theme="dark"] { ... }`, generated from `dark/_base.css`.

### ThemeBox sub-class overrides

Inside `_base.css`, define additional classes alongside `.base` to power `<ThemeBox variant="X">`:

```css
.base { --color-primary: #3b82f6; }
.poligon { --color-primary: #f59e0b; }       /* used by <ThemeBox variant="poligon"> */
.poligon2 { --color-primary: #10b981; }      /* used by <ThemeBox variant="poligon2"> */
```

The generator emits `.theme-poligon`, `.theme-poligon2` selectors and adds them to the `ThemeBoxVariant` type union. `<ThemeBox variant="poligon">` renders as `<div class="theme-poligon">`, scoping the override to the subtree.

## CSS Variable Naming

```
--color-X                      — colors. Tailwind v4 strips the `color-` prefix in @theme inline → `bg-X`, `text-X`.
--radius, --background-gradient — non-color theme vars. Not registered in @theme inline.
```

The generator filters by `--color-*` prefix when writing `_tailwind/_colors.css`. Only color tokens are exposed to Tailwind utilities.

## Two-layer architecture inside `.base`

Optional but recommended pattern when palette grows large:

```css
.base {
	/* Semantic layer — concrete colors (differs per theme) */
	--color-primary: #3b82f6;
	--color-surface: #242830;
	--color-background: #010101;

	/* Component layer — references semantic layer via var() */
	--color-input-bg: var(--color-surface);
	--color-button-primary-bg: var(--color-primary);
	--color-button-primary-bg-hover: color-mix(in oklch, var(--color-primary), white 15%);
}
```

Other themes override only semantic-layer values; component-layer variables resolve to the new semantic values automatically.

## Generation Pipeline

When a developer edits any `_base.css`:

```
*/_base.css (manual edit)
    ↓ [Vite plugin theme-watcher detects change]
    ↓ [exec: pnpm theme:generate]
    ↓
script.ts:
    ├─ Discovers themes from index.css imports (every non-`_*` folder)
    ├─ For each theme: extracts vars from .base + other classes
    ├─ Merges with BASE_THEME's vars
    ├─ Emits {theme}/_new.css with [data-theme="X"] selectors
    ├─ Emits _tailwind/_colors.css with @theme inline { all --color-* tokens }
    ├─ Emits _ui/types.ts with ThemeBoxVariant union
    └─ Emits themes.generated.ts with AVAILABLE_THEMES + type ThemeName
```

### `index.css` (MANUAL — single entry)

```css
@import './_tailwind/index.css';
@import './dark/index.css';
@import './light/index.css';
@import './blue/index.css';
```

This file is imported once at the app entry. The generator parses it to discover themes.

## Vite Plugin

```ts
// theme/plugin.ts
export function viteThemePlugin(options: {
	themeDir?: string
	cwd?: string
	command?: string
	debug?: boolean
} = {}): Plugin {
	let isRunning = false
	let pending = false

	return {
		name: 'theme-watcher',
		configureServer(server) {
			server.watcher.add(`${themeDir}/**/_base.css`)
			const onEvent = (path: string) => {
				if (!path.endsWith('_base.css')) return
				if (isRunning) { pending = true; return }
				isRunning = true
				exec(command, { cwd }, (err) => {
					isRunning = false
					if (pending) { pending = false; onEvent(path) }
				})
			}
			server.watcher.on('change', onEvent)
			server.watcher.on('add', onEvent)
			server.watcher.on('unlink', onEvent)
		},
	}
}
```

**Rules:**
- `isRunning` guard prevents concurrent script invocations; `pending` queues one rerun if a change arrives mid-run.
- Watch ALL `*/_base.css` (every theme can trigger regen), not only BASE_THEME's.
- Watch only `_base.css` (source). Never watch `_new.css` — that is generated output and watching it causes infinite loops.
- Plugin file lives inside `theme/` so the entire folder is portable. Vite configs import it via the consuming package's `./theme-plugin` subpath export.

### Registration

```ts
// apps/web/vite.config.ts (or similar)
import { viteThemePlugin } from '@app/ui/theme-plugin'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const themeDir = resolve(__dirname, '../../packages/ui/src/theme')

export default defineConfig({
	plugins: [react(), tailwindcss(), viteThemePlugin({ themeDir })],
})
```

In Electron-vite the plugin goes only into the `renderer` block. Main and preload do not load CSS.

## Scope (Multi-window Electron)

Independent of ThemeBox. Used to give different physical windows their own theme. Optional for plain SPAs.

`THEME_SCOPES` in `config.ts` lists scopes (`'app'`, `'notification'`, `'about'`). Each scope has its own slot in the store and its own `localStorage` key. The active scope on the current window is set via `setWindowScope('overlay')` once at renderer bootstrap. `useTheme()` reads from the current scope by default (via React context). The `notification-override.ts` module (optional) keeps notification scope in sync with the main scope, with a per-main-theme override.

For Electron multi-window: pair with a `ThemeBroadcastAdapter` to propagate scope changes between renderer processes over IPC.

## useTheme Hook

Lives in `theme/useTheme.ts`. Uses `useSyncExternalStore` to bridge React with the module's external store.

```ts
const { theme, scope, setTheme, toggleTheme, availableThemes } = useTheme()
```

**Rules:**
- Theme is NOT stored in Zustand. The module's `store.ts` is the single in-memory state, persisted via the `ThemeStorageAdapter` (default: `localStorage`).
- `data-theme` attribute on `<html>` is the only CSS handle.
- For multi-window Electron, swap in `ThemeBroadcastAdapter` via `configureThemeAdapters({ broadcast })` at bootstrap.

## ThemeBox Component

```tsx
// theme/_ui/ThemeBox.tsx
export const ThemeBox: FC<PropsWithChildren<ThemeBoxProps>> = ({
	variant = 'base',
	as: Component = 'div',
	className,
	children,
	...props
}) => (
	<Component className={cn(`theme-${variant}`, className)} {...props}>
		{children}
	</Component>
)
```

**How it works:**
1. `<ThemeBox variant="poligon">` renders `<div class="theme-poligon">`.
2. The generator emitted `.theme-poligon { --color-primary: var(--poligon-color-primary); ... }`.
3. Inside the subtree, `--color-primary` resolves to the `poligon` block's value via CSS cascade.

**Scope vs ThemeBox.** Two orthogonal axes:
- **Scope** — which theme an entire window uses (`app` vs `notification`).
- **ThemeBox** — a local override on a subtree within one window.

They compose. Inside a `[data-theme="dark"]` window, `<ThemeBox variant="poligon">` overrides selected vars for its subtree only.

## Telegram Theme Conversion

`telegram-script.ts` parses a `.tdesktop-palette.txt` (Telegram Desktop palette) into a `.base { --color-X: ... }` CSS fragment.

```bash
pnpm theme:telegram <theme-name> [palette-path]
```

Output: `theme/<theme-name>/_telegram.css`. Review and merge contents into `<theme-name>/_base.css` manually. The script never edits `_base.css` directly — palette imports are an authoring aid, not auto-applied.

## Tailwind Integration

The generator writes `_tailwind/_colors.css` with idempotent mappings — `@theme inline { --color-X: var(--color-X); }` for every `--color-*` token in BASE_THEME's `.base`. Tailwind v4 then exposes them as utility classes (`bg-X`, `text-X`, `border-X`, ...). Non-color theme vars (`--radius`, `--background-gradient`) live in `_base.css` but are NOT registered with Tailwind — consume them via raw `var()` or registered manually in `_radius.css` etc.

`@custom-variant dark (&:is([data-theme="dark"] *), [data-theme="dark"]&)` lives in `_tailwind/_custom-variant.css`.

## CSS Layer Cascade (Tailwind v4)

Tailwind v4 puts every utility class inside `@layer utilities`. The CSS @layer
spec gives **unlayered** styles unconditional priority over layered ones,
regardless of selector specificity.

Consequence: a global rule written outside any `@layer` block — even one with
low specificity like `body > *` — overrides every matching Tailwind utility.

```css
/* unlayered — always wins */
body > * {
	position: relative;
	z-index: 1;
}

/* @layer utilities — loses despite higher specificity */
.fixed { position: fixed; }
```

If a portaled component (Radix Dialog, Popover, Tooltip) has
`className="fixed top-1/2 left-1/2 ..."`, the unlayered `body > *` wins because
the portal target is `<body>`. The element renders at `position: relative`
inside normal document flow — usually thousands of pixels below the viewport —
and looks like it "didn't open at all".

### Symptoms

- Modal / popover / tooltip "doesn't appear" — actually it does, but it's
  positioned far off-screen.
- DevTools shows the Tailwind class on the element while computed style
  ignores it.
- Worked in Tailwind v3 (utilities were `!important` by default), broken
  after the v4 migration.
- Specifically affects elements rendered into a portal target — most often
  `body`, sometimes `#root` or a portal-container div.

### How to write global rules safely

1. **Default: wrap global rules in `@layer base`.** Layered rules cannot beat
   layered utilities, so utilities win on specificity again — like in v3.
   ```css
   @layer base {
   	body > * {
   		position: relative;
   		z-index: 1;
   	}
   }
   ```

2. **If a layered rewrite is too risky, exclude portal targets at the selector
   level** via ARIA-role exemptions. Surgical, no behaviour change for
   anything else.
   ```css
   body > *:not([role="dialog"]):not([role="alertdialog"]) {
   	position: relative;
   	z-index: 1;
   }
   ```

3. **Never reach for inline `style={{...}}` or Tailwind `!fixed` on the
   component** as a first fix. It papers over a project-level bug that will
   keep biting every future modal, popover, dropdown, and toast.

### Watchlist

Any of these unlayered patterns will silently override Tailwind utilities
when they constrain layout properties:

```css
body { ... }
html { ... }
body > * { ... }
* + * { ... }
:where(...) { ... }
[role="..."] { ... }
```

Especially dangerous when they touch `position`, `display`, `transform`,
`overflow`, `width`, `height`, or `z-index`.

## npm Scripts

```json
{
	"theme:generate": "tsx ./src/theme/script.ts",
	"theme:telegram": "tsx ./src/theme/telegram-script.ts"
}
```

`tsx` and `@types/node` are devDependencies of the package owning the theme folder. The Vite plugin invokes `pnpm theme:generate` via `exec()`.

## Public Exports (`theme/index.ts`)

```ts
import './index.css'  // side effect — loads all themes + tailwind

export { BASE_THEME, THEME_SCOPES, isThemeScope, type ThemeScope } from './config'
export { AVAILABLE_THEMES, isThemeName, type ThemeName } from './themes.generated'
export { ThemeProvider, useTheme } from './ThemeProvider'
export type { UseThemeResult } from './useTheme'
export { ThemeBox, type ThemeBoxProps } from './_ui/ThemeBox'
export type { ThemeBoxVariant } from './_ui/types'
// + store/adapters/notification-override re-exports as needed
```

## Anti-patterns

### DON'T edit AUTO-GEN files

```
_new.css                   — generated from _base.css
_tailwind/_colors.css      — generated from BASE_THEME's .base
_ui/types.ts               — generated from .className blocks in _base.css
themes.generated.ts        — generated from index.css imports
```

The header comment in each AUTO-GEN file says `// AUTO-GENERATED ... do not edit.` — heed it.

### DON'T name the theme class after the theme

```css
/* DON'T — class name encodes theme identity */
.dark-theme { --color-background: ... }

/* DO — class name is always `.base`, identity comes from folder */
.base { --color-background: ... }
```

### DON'T put `useTheme` in `src/hooks/`

The hook lives **inside** the theme folder. The whole point of a self-contained module is that you can copy `theme/` between projects without dependencies on outside files.

### DON'T put global styles in `theme/`

```css
/* DON'T — body typography is not a theme concern */
/* theme/_global.css */
body { font-family: 'Inter'; }
::-webkit-scrollbar { width: 6px; }

/* DO — outside theme/, imported separately */
/* src/styles/global.css */
body { font-family: 'Inter'; }
```

### DON'T hardcode colors in components

```tsx
// DON'T — hardcoded hex
className="bg-[#1e2329]"

// FALLBACK — arbitrary var (only when variable is not in @theme inline)
className="bg-[var(--color-card)]"

// BEST — use Tailwind utility (works because --color-card is in _tailwind/_colors.css)
className="bg-card"
```

### DON'T watch generated output files in plugin

```ts
// DON'T — creates infinite loop
server.watcher.add('_new.css')

// DO — watch only sources
server.watcher.add('**/_base.css')
```

### DON'T store theme in Zustand

The module owns its own external store (`store.ts`). `useSyncExternalStore` bridges React. No global state library required.

### DON'T register the plugin in Electron `main` or `preload` blocks

Only the renderer loads CSS and runs Vite's dev server with file watching. `main` and `preload` are server-side build targets — the plugin would never trigger there.

### Color replacement validation (MANDATORY)

When replacing hardcoded hex colors with CSS variables:

1. **Find BASE_THEME** — read `theme/config.ts` to get `BASE_THEME`. This is the source of truth — all other themes inherit from it. Always validate colors against this theme first.
2. **Read `{BASE_THEME}/_base.css`** — find the variable and trace its resolved value through all `var()` references to the final concrete hex/rgb.
3. **Compare values** — the resolved value must visually match the color being replaced. If `--color-card` resolves to `#141414` but you're replacing `#1e2329` — that's a mismatch.
4. **Fix mismatches** — update the variable value in `{BASE_THEME}/_base.css`, OR add a new variable, OR pick a different existing variable.
5. **Check other themes** — if the variable is overridden in `light/_base.css` etc., verify those values make sense for that theme.

**Never assume a variable name matches its actual value.** Variable names can be misleading — always verify by reading the CSS.

## Portability Checklist

When copying `theme/` to a new project:

- [ ] Copy entire `theme/` folder
- [ ] Add `./theme-plugin` subpath export to the owning package's `package.json` `exports`
- [ ] Add `tsx`, `@types/node`, `vite` to devDeps of the owning package
- [ ] Add npm scripts `theme:generate`, `theme:telegram`
- [ ] Register `viteThemePlugin({ themeDir })` in each Vite config that serves CSS (web SPA, Electron renderer, Storybook)
- [ ] Run `pnpm theme:generate` once to bootstrap AUTO-GEN files
- [ ] Import `theme/index.css` from the app's main CSS entry
- [ ] Verify Tailwind v4 is installed (`@tailwindcss/vite`)
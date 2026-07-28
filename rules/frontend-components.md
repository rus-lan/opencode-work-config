---
name: frontend-components
description: Component layers (ui-kit → ui → entity → widgets), CVA variants, cn(), forwardRef, naming, Storybook (prerequisites, typing, structure), theming via CSS variables, skeleton/loading layout-shift rules
version: 2.8.1
---

# Frontend — Component Organization

Rules for creating and maintaining React components across the layer hierarchy.

## Layer Hierarchy

Components are organized into strict layers. Higher layers may import from lower layers, never the reverse.

| Layer | Directory | Purpose | Storybook |
|-------|-----------|---------|-----------|
| **ui-kit** | `components/ui-kit/` | Design system primitives (Button, Input, Select, Modal, Tabs, Checkbox) | Required |
| **ui** | `components/ui/` | Composed UI blocks built on top of ui-kit (Badge, Card, DescriptionBlock) | Required |
| **entity** | `components/entity/` | Business entity UI (PayCard, StrategyTemplate) — renders domain data | Required |
| **widgets** | `components/widgets/` | Feature widgets with business logic, API calls, TanStack Query | Not required |

Import direction: `ui-kit ← ui ← entity ← widgets`

**Excluded from this rule:**
- `components/layout/` — covered by `frontend-layouts` rule
- `components/debug/` — development-only, no conventions enforced

### DON'T — no `features/` directory

There is **no `src/features/` layer**. The layer hierarchy `ui-kit → ui → entity → widgets` already covers every reusable presentation piece, and domain modules (`theme/`, `i18n/`, `data/`, etc.) cover everything else. If you find yourself reaching for `features/`, the file belongs in one of:

- a **widget** (`components/widgets/XxxWidget/`) when it owns business logic — toggles state, calls an API, dispatches to a store;
- a **domain module** at the package root (e.g. `theme/`, `i18n/`, `data/`) when it is the provider, hook, or configuration of a feature area. Domain modules MUST be self-contained — pulling the folder into another project should bring all of the feature's code with it.

The promise of this layout is portability: `git mv theme/ ../other-app/src/theme/` should produce a working theme module with no other moves required.

### Providers

Wrapper components (AuthProvider, ThemeProvider) live in a separate top-level directory:

```
src/
  components/   — UI layers
  providers/    — Context providers and app-level wrappers
```

Providers are NOT components. They manage context, auth state, SDK initialization. Keep them outside the component hierarchy.

## File Organization

Every layer follows the same pattern: **category folder → component files inside**.

### Structure

```
ui-kit/
  button/                  # Category folder (lowercase)
    Button/                # Component folder (PascalCase)
      index.tsx            # Component code
      Button.stories.tsx   # Storybook story
      button.css           # Local styles (rare, only when needed)
    ButtonGroup/
      index.tsx
      ButtonGroup.stories.tsx
  input/
    Input/
      index.tsx
      Input.stories.tsx
    NumberInput/
      index.tsx
      NumberInput.stories.tsx
  radio/
    Checkbox/
      index.tsx
    Radio/
      index.tsx
    Switch/
      index.tsx
```

Category folders group related components. This directly maps to Storybook navigation:
- `ui-kit/button/Button` → Storybook path `UI-KIT/button/Button`
- `ui-kit/input/Input` → Storybook path `UI-KIT/input/Input`
- `entity/pay/PayCard` → Storybook path `Entity/pay/PayCard`

**Rules:**
- Category folder: **lowercase kebab-case** (`button`, `input`, `glass-navigation`)
- Component folder: **PascalCase** matching the component name (`Button`, `NumberInput`)
- Main file: always `index.tsx` (single entry point per component)
- Story file: `ComponentName.stories.tsx` co-located in the same folder
- If a component has only one file and no story — still use folder + `index.tsx` for consistency

## Component Pattern

### Basic component

```tsx
import { type VariantProps, cva } from 'class-variance-authority';
import { type HTMLAttributes, forwardRef } from 'react';
import { cn } from '@/utils/cn';

const cardVariants = cva('overflow-hidden rounded-xl border transition-all p-6', {
  variants: {
    variant: {
      default: 'gradient-card border-[#2b3139]',
      auth: 'border-white/5 bg-[#1e2329]/90 shadow-2xl',
    },
    interactive: {
      true: 'cursor-pointer active:scale-[0.99]',
      false: '',
    },
  },
  defaultVariants: { variant: 'default', interactive: false },
});

export interface CardProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant, interactive, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(cardVariants({ variant, interactive }), className)}
        {...props}
      />
    );
  },
);
Card.displayName = 'Card';
```

Key points:
- **forwardRef** with explicit generic types + `displayName` (required for React DevTools)
- **CVA** for all variant logic — no manual conditional class strings
- **cn()** always wraps CVA output + external `className`
- **Props extend HTML attributes** + `VariantProps<typeof xxxVariants>`
- **Omit conflicting props**: `Omit<HTMLAttributes, 'color'>` when CVA defines `color` variant

### For new components (React 19)

New components may use ref-as-prop instead of forwardRef:

```tsx
export interface CardProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {
  ref?: React.Ref<HTMLDivElement>;
}

export const Card = ({ className, variant, interactive, ref, ...props }: CardProps) => {
  return (
    <div
      ref={ref}
      className={cn(cardVariants({ variant, interactive }), className)}
      {...props}
    />
  );
};
```

No `forwardRef` wrapper, no `displayName` needed. Prefer this for all new components.

## CVA (class-variance-authority)

### Defining variants

```tsx
const buttonVariants = cva(
  // Base classes — always applied
  'relative inline-flex items-center justify-center gap-2 border font-medium',
  {
    variants: {
      variant: { filled: '', ghost: 'border-transparent', outline: '', text: 'bg-transparent border-transparent' },
      color: { default: '', primary: '', secondary: '', success: '', danger: '' },
      size: { xs: 'control-xs px-2 text-xs', sm: 'control-sm px-3 text-sm', md: 'control-md px-4 text-base' },
      radius: { none: 'rounded-none', sm: 'rounded-sm', md: 'rounded-md', full: 'rounded-full' },
      fullWidth: { true: 'w-full' },
      loading: { true: 'relative text-transparent' },
      icon: { true: 'p-0 aspect-square' },
    },
    defaultVariants: { color: 'primary', variant: 'filled', size: 'md', radius: 'sm' },
  },
);
```

**Rules:**
- Base string contains layout, typography, and shared interaction classes
- Each variant value is a Tailwind class string (empty string `''` is valid for variants styled via data-attributes)
- Use `defaultVariants` for every variant that has a sensible default
- Size variants use global `control-*` utility classes (which reference `--height-*` CSS variables)

### Data attributes for complex styling

When CVA variant combinations need CSS that can't be expressed inline, use `data-*` attributes:

```tsx
<button
  data-color={color}
  data-variant={variant}
  data-glow={showGlow ? glow : 'none'}
  className={cn(buttonVariants({ variant, color, size }), className)}
>
```

This allows theme CSS to target combinations like `button[data-color="primary"][data-variant="filled"]`.

## cn() Utility

Defined in `src/utils/cn.ts`:

```ts
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

**Usage rules:**
- Always use `cn()` when combining classes — never manual template literals
- CVA output goes first, external `className` goes last (so consumers can override)
- Conditional classes use object syntax inside `cn()`:

```tsx
cn(
  selectVariants({ size, radius, status }),
  isOpen && 'border-focus ring-4',
  disabled && 'opacity-50 cursor-not-allowed',
  className,
)
```

## className Pass-through

Every component MUST accept `className` prop and pass it through `cn()`.

### Simple pass-through

```tsx
export interface BadgeProps {
  className?: string;
  children: ReactNode;
}

export const Badge = ({ className, children }: BadgeProps) => (
  <span className={cn('rounded-full px-2 py-0.5 text-xs', className)}>
    {children}
  </span>
);
```

### Multi-slot classNames

For components with multiple styleable sub-elements, use a `classNames` object:

```tsx
export interface ButtonProps {
  className?: string;
  classNames?: {
    root?: string;
    content?: string;
    contentWrap?: string;
  };
}

// Usage in JSX:
<button className={cn(variants, className, classNames?.root)}>
  <span className={cn('flex items-center', classNames?.contentWrap)}>
    <span className={classNames?.content}>{children}</span>
  </span>
</button>
```

```tsx
// ListItem example:
classNames?: {
  root?: string;
  avatarContainer?: string;
  contentContainer?: string;
  title?: string;
  subtitle?: string;
};
```

## Slot Pattern (Sections)

Components with icon/action slots use named ReactNode props:

```tsx
export interface InputProps {
  leftSection?: ReactNode;   // Icon or label on the left
  icon?: ReactNode;          // Icon on the right
  onIconClick?: () => void;  // Right icon click handler
}

export interface ButtonProps {
  leftSection?: ReactNode;
  rightSection?: ReactNode;
  icon?: boolean;            // Icon-only mode (square button)
}
```

**DO NOT** use `cloneElement` to resize icons. Pass size via props or CSS:

```tsx
// DON'T
{isValidElement(icon) && cloneElement(icon, { size: 20 })}

// DO — let CSS handle sizing
<span className="[&>svg]:size-5">{icon}</span>

// DO — or pass size explicitly from parent
<Button leftSection={<Home size={20} />}>Home</Button>
```

## Theming with CSS Variables

### Two-layer model

Theme variables in `src/theme/` follow a two-layer architecture (see `frontend-theme` rule for full details):

- **Semantic layer** — concrete colors (hex/rgb), the theme palette
- **Component layer** — `var()` references to semantic variables + CSS functions

Components only consume the component-layer variables. They never need to know which theme is active.

### Component-scoped variables

Every ui-kit and ui component uses CSS variables with a component-name prefix:

```
--color-input-bg
--color-input-border
--color-input-border-hover
--color-input-text
--color-input-placeholder
--color-input-ring
--color-input-error-border
--color-input-error-ring
```

These are defined in theme CSS (`src/theme/{theme}/_base.css`) and consumed in components:

```tsx
const inputVariants = cva(
  'w-full border bg-[var(--color-input-bg)] text-[var(--color-input-text)] placeholder:text-[var(--color-input-placeholder)]',
  {
    variants: {
      status: {
        default: 'border-[var(--color-input-border)] focus:ring-[var(--color-input-ring)]',
        error: 'border-[var(--color-input-error-border)] focus:ring-[var(--color-input-error-ring)]',
      },
    },
  },
);
```

### Adding new component variables

When a new component needs theme variables, add them to the **component layer** in `_base.css` (BASE_THEME). Preferred priority:
1. Reference a semantic variable: `--color-newcomp-bg: var(--color-surface);`
2. Modify a semantic variable via CSS function: `--color-newcomp-bg-hover: color-mix(in oklch, var(--color-surface), white 10%);`
3. Direct `rgb()` value if no semantic equivalent fits: `--color-newcomp-glow: rgb(28 28 30 / 0.9);`

This is a recommendation, not a strict rule. Use direct colors when needed, but prefer semantic references for consistency across themes.

### Shared variables across component families

Related components share global size and spacing variables:

```css
/* Global height scale — used by all form controls */
@theme {
  --height-2xs: 36px;
  --height-xs: 40px;
  --height-sm: 44px;
  --height-md: 50px;
  --height-lg: 44px;
  --height-xl: 48px;
  --height-2xl: 52px;
  --height-3xl: 56px;
}

/* Utility classes combining height + font size */
@layer utilities {
  .control-md {
    @apply h-md text-base;
  }
  .control-lg {
    @apply h-lg text-lg;
  }
}
```

Button, Input, Select, Combobox — all use the same `control-*` classes for consistent sizing.

### Variable naming convention

```
--color-{component}-{property}
--color-{component}-{state}-{property}

Examples:
--color-button-default-bg
--color-button-default-bg-hover
--color-checkbox-bg-checked
--color-select-dropdown-bg
--color-input-wrapper-label
```

Semantic groupings for base colors:
```
--color-b-background     — app background
--color-b-text           — primary text
--color-b-text-secondary — secondary text
--color-b-card-bg        — card background
--color-b-field-bg       — field background (shared across inputs)
```

## Exports

### Named exports only

```tsx
// DO
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(/* ... */);
export interface ButtonProps { /* ... */ }

// DON'T
export default Button;
```

### Index files per category (optional)

Category folders MAY have an `index.ts` for convenient imports:

```ts
// components/ui-kit/button/index.ts
export { Button } from './Button';
export type { ButtonProps } from './Button';
export { ButtonGroup } from './ButtonGroup';
export type { ButtonGroupProps } from './ButtonGroup';
```

## Storybook

### Required coverage

| Layer | Storybook required |
|-------|--------------------|
| ui-kit | Yes — every component |
| ui | Yes — every component |
| entity | Yes — every component |
| widgets | No — business logic, uses API/queries |

### Prerequisites (devDependencies)

Before creating `.stories.tsx` files, these packages MUST be in `devDependencies`:

```
@storybook/react          # Meta, StoryObj, StoryFn types + framework
@storybook/test           # fn(), expect(), userEvent
```

**MANDATORY:** When generating the first `.stories.tsx` file in a project, verify Storybook packages are installed. If `@storybook/react` is not in `devDependencies` — install it FIRST. Story files importing from uninstalled packages cause TS2307 errors across ALL story files.

### Story structure

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { fn } from '@storybook/test';
import { Button } from './index';

const meta: Meta<typeof Button> = {
  title: 'UI-KIT/button/Button',  // Matches directory path
  component: Button,
  parameters: { layout: 'centered' },
  args: {
    children: 'Button',
    onClick: fn(),              // Action props use fn() from @storybook/test
  },
  argTypes: {
    variant: { control: 'radio', options: ['filled', 'ghost', 'outline', 'text'] },
    size: { control: 'select', options: ['xs', 'sm', 'md', 'lg', 'xl'] },
  },
  decorators: [
    (Story: React.FC) => (
      <div className="p-4">
        <Story />
      </div>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof meta>;   // Use typeof meta — not typeof Component

export const Default: Story = {
  args: { children: 'Button' },
};

export const AllVariants: Story = {
  render: (args) => (
    <div className="space-y-4">
      {['filled', 'ghost', 'outline'].map((v) => (
        <Button key={v} {...args} variant={v}>{v}</Button>
      ))}
    </div>
  ),
};
```

### Story typing rules

- `const meta: Meta<typeof Component>` — ALWAYS annotate the meta variable with `Meta<>` generic
- `type Story = StoryObj<typeof meta>` — derive from `typeof meta` for full args inference (not `typeof Component`)
- Decorator parameter: ALWAYS type explicitly as `(Story: React.FC) =>` — do NOT use `StoryFn` (it has a 2-arg signature incompatible with JSX `<Story />`)
- Action props use `fn()` from `@storybook/test` — NOT `action()` from deprecated `@storybook/addon-actions`
- Import types with `import type` — only `fn()` needs a value import

**Title convention:** `{Layer}/{category}/{ComponentName}`
- `UI-KIT/button/Button`
- `UI-KIT/input/NumberInput`
- `UI/card/Card`
- `Entity/pay/PayCard`

### File naming

Always `ComponentName.stories.tsx` co-located with `index.tsx`.

## Props

### Interface naming

```tsx
// Always suffix with Props
export interface ButtonProps extends /* ... */ {}
export interface CheckboxProps extends /* ... */ {}
export interface SelectProps extends /* ... */ {}
```

### Extending HTML attributes

```tsx
// Extend native element attributes, Omit conflicting names
export interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'color'>,
    VariantProps<typeof buttonVariants> {
  leftSection?: ReactNode;
  rightSection?: ReactNode;
}
```

### Destructure in signature

```tsx
// DO
export const Button = ({ variant, size, className, children, ...props }: ButtonProps) => {

// DON'T
export const Button = (props: ButtonProps) => {
  const { variant, size } = props;
```

## Design Principles

### Compact but functional

Prefer compact layouts that maximize information density without sacrificing usability. Elements should earn their space — combine related actions, use inline indicators instead of separate rows, collapse secondary info behind hover/expand. But never sacrifice readability for compactness — text must remain legible and touch targets must remain accessible.

### Reuse existing components — never duplicate

Before creating a new component, check if an equivalent already exists in the component hierarchy. This is mandatory:

1. **Buttons/icons**: Always use `ButtonBase` and `IconButton` from ui-kit. Never create one-off `<button>` elements with custom styles for icon actions. If the topbar uses `IconButton` for action buttons, every action button across all pages must use `IconButton` too.

2. **Navigation items**: When a page has a sidebar with selectable items (like `FlowNavItem` on Dashboard), new pages with similar patterns must reuse the same visual language — `rounded-r-xl`, `bg-nav-selected-bg`, left active indicator bar, `ButtonBase` with ripple. If the exact component can't be reused, extract a shared base component that both pages consume.

3. **Cards/containers**: Use existing `Card` component with CVA variants. Don't create new wrapper divs with manual border/bg/padding that duplicate what Card already provides.

4. **Labels/badges**: Use `SectionLabel` for section headers. Don't create new `<p>` elements with manual uppercase/tracking/size that duplicate SectionLabel's styling.

**Rule of thumb**: Before writing a `className` string with more than 3 visual properties (bg, border, rounded, shadow, etc.), search for an existing component that already encapsulates those styles. If you find one, use it. If you don't, consider creating a reusable component in the appropriate layer rather than inlining the styles.

## Anti-patterns

### DON'T use default exports

Named exports are required for consistent imports and better refactoring support.

### DON'T use class components

Functional components only. No `React.Component` or `React.PureComponent`.

### DON'T hardcode colors

Always use CSS variables from the theme system. Never hardcode hex values for colors that should change with themes:

```tsx
// DON'T
className="bg-[#1e2329] text-[#eaecef]"

// DO
className="bg-[var(--color-b-card-bg)] text-[var(--color-b-text)]"
```

### Color replacement validation (MANDATORY)

When replacing a hardcoded hex color with a CSS variable, you MUST verify:

1. **Find BASE_THEME** — read `src/theme/config.ts` to determine which theme is `BASE_THEME` (e.g., `'dark'`). This is the source of truth — all other themes inherit from it
2. **Variable exists** — read `src/theme/{BASE_THEME}/_base.css` (e.g., `src/theme/dark/_base.css`) and confirm the variable is defined there
3. **Value matches** — trace the variable's value through all `var()` references until you reach a concrete hex/rgb value. Compare it with the hex color being replaced — they must produce the same visual result
4. **If no match exists** — either find a different variable that matches, OR update the variable's value in `_base.css` to match the design intent, OR create a new component-scoped variable in the component section of `_base.css`

```tsx
// DON'T — blindly pick a variable by name without checking its value
// Original: bg-[#1e2329] (dark blue-gray card)
// --color-card resolves to #141414 (much darker!) — WRONG
className="bg-[var(--color-card)]"

// DO — verify the value matches before replacing
// 1. Read _base.css: --color-card: var(--color-b-card-bg) → #141414 ≠ #1e2329
// 2. Either update --color-card to #1e2329 in _base.css, or find the right variable
// 3. Then use it:
className="bg-[var(--color-card)]"  // after fixing --color-card: #1e2329
```

**Never assume a variable name matches its actual value.** Always read the theme source file and trace the resolved value before replacing hardcoded colors.

### DON'T use `any` in props

```tsx
// DON'T
interface ModalProps { data: any; }

// DO
interface ModalProps<T = unknown> { data: T; }
```

### DON'T put business logic in ui-kit or ui components

API calls, TanStack Query hooks, navigation, and side effects belong in widgets or pages — not in ui-kit/ui/entity.

### DON'T skip className pass-through

Every component must accept and forward `className`. Without it, consumers cannot customize styling.

### DON'T shrink font sizes below surrounding context

When adding new elements (badges, counters, labels, metadata), match the font size of neighboring elements. Never default to tiny sizes like `text-[10px]` or `text-[11px]` unless the surrounding context already uses that scale. Read the parent and sibling components first, then adopt their typography. A counter next to a heading must use the same `text-*` class as that heading — not a smaller one.

### Prefer canonical Tailwind classes, but allow arbitrary values

When generating code, **prefer canonical classes** over arbitrary bracket syntax:

```tsx
// PREFER — canonical
className="z-1 w-0.75 gap-1 p-2 rounded-lg"

// AVOID — arbitrary equivalents of canonical classes
className="z-[1] w-[3px] gap-[4px] p-[8px] rounded-[8px]"
```

Arbitrary values are acceptable when:
- No canonical equivalent exists: `max-w-[340px]`, `grid-cols-[1fr_2fr]`
- CSS variables / functions: `bg-[var(--color-surface)]`, `origin-[0%_50%]`
- The user explicitly writes or requests an arbitrary value — do NOT rewrite it to canonical form unless asked

### Skeleton / placeholder bars must be `block`, not `inline-block`

A bare `<span>` is inline. An inline element **ignores `width`/`height`** and does not start a new line, so a sizing placeholder built on an inline span renders at zero/collapsed size and stacked bars sit side by side instead of one per line.

Make placeholder/skeleton base classes `block` (or `inline-block` only when the bar is meant to sit inline within text). With `block`:
- `width`/`height` and `w-*`/`h-*` are honored;
- sibling bars stack vertically (so `<Skeleton/>` rows with `mt-*`/`space-y-*` actually separate);
- a caller who genuinely needs an inline bar overrides with `inline-block`/`inline` in `className` — `cn()`/twMerge resolves the display conflict (last wins).

```tsx
// DON'T — inline base: a sized standalone bar collapses, stacked bars run together
const skeletonVariants = cva('inline-block animate-pulse bg-[var(--color-skeleton)]', { /* ... */ });

// DO — block base honors width/height and stacks
const skeletonVariants = cva('block animate-pulse bg-[var(--color-skeleton)]', { /* ... */ });
```

This applies to any sized decorative box (skeletons, spacers, rule lines), not just skeletons.

### Loading state must mirror the loaded shell (no layout shift)

A `loading ? <placeholder/> : <content/>` branch must not change the outer layout box when it flips. Match the loaded state's **container, borders, padding, margins, and element heights** — only the inner text/data becomes a skeleton. Otherwise the page jumps on load.

- **Match line-box height, not a guessed px.** A `text-2xl` value is 32px tall (`h-8`), not `h-7`; `text-3xl` is 36px (`h-9`); `text-sm` ≈ 20px (`h-5`); `text-xs` ≈ 16px (`h-4`). Set the skeleton bar to the loaded line-height, or use a wrap pattern that renders the real element invisibly to reserve its exact box.
- **Reproduce the shell for lists/tables.** If the loaded state is a bordered table or list, the loading state must render the same bordered wrapper + header + body rows at the same row heights — not a flat stack of bars that swaps to chrome on load.
- **Don't collapse the empty state.** A loaded-empty branch (no data) must occupy roughly the same reserved height as the loading and populated states (e.g. center a "No data" message inside the same fixed-height box), or empty/new accounts see the section collapse on load.
- **Reserve to the data ceiling, not a guess.** When a list is `slice(0, N)`, render N skeleton rows so a full list does not grow on load.
- Variable-length lists can't be pixel-perfect across every row count — match row heights and the shell, reserve the max, and accept residual reflow only for the count, never for fixed-dimension widgets (balance, stat cards, charts).
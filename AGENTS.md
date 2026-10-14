# Global rules for OpenCode (migrated from rules/*.md to AGENTS.md)

The `instructions` key is inert in V2; these rules are loaded via AGENTS.md.

---

## rule: bmad-impl-story-cycle.md

---
name: bmad-impl-story-cycle
description: Экономный цикл реализации BMAD-фаз — kickoff → эпики → внешнее ревью → readiness → спринт; ревью историй по классу риска (self-review vs полный CR), Fable-гейт на суммарный дифф эпика
version: 1.0.0
---

# BMAD — Impl Story Cycle (экономный цикл реализации)

Как вести реализацию фаз в проектах с BMAD: один конвейер подготовки фазы + режим
ревью историй по классу риска. Цель — не терять качество на опасных местах и не жечь
время на полном ревью каждой мелкой истории.

## Конвейер фазы

1. **Kickoff**: `KICKOFF-<фаза>-impl-prep.md` в planning-artifacts (генерится скиллом
   `/impl-kickoff`). Одноразовый файл-инструкция для свежей сессии; после выполнения
   удаляется, в README planning-artifacts не индексируется.
2. **[CE]** `bmad-create-epics-and-stories` → `implementation-artifacts/epics-<фаза>.md`
   + coverage map по скоуп-контракту фазы (каждый пункт строки фазировки PRD — в
   какой-то истории) + обновление README implementation-artifacts.
3. **Внешний гейт №1**: `fable-second-opinion` mode A на файл эпиков (полнота против
   PRD, дыры acceptance, скрытые зависимости, порядок).
4. **[IR]** `bmad-check-implementation-readiness` → чинить красное → повторить.
5. **[SP]** `bmad-sprint-planning` → `sprint-status-<фаза>.yaml`.
6. Цикл историй: `bmad-create-story` → `bmad-dev-story` → ревью по классу (ниже) →
   отметка в спринт-файле → следующая.
7. **Конец каждого эпика**: `fable-second-opinion` mode A на суммарный дифф эпика;
   находки → фиксы → точечный re-check; отметка «Fable-гейт пройден (+находки)» в
   спринт-файле. Опционально — `bmad-retrospective`.

## Ревью по классу истории

- **Всегда блокирующие**: тесты, арх-тесты, lint/typecheck. История не закрывается
  на красном.
- **Обычная история**: self-review — та же dev-сессия перечитывает свой дифф против
  acceptance-критериев одним проходом. Полный `bmad-code-review` НЕ запускать.
- **Полный [CR] обязателен**, если история трогает хотя бы одно из:
  - деньги: леджер, списания, цены, балансы;
  - секреты/креды/ключи шифрования/custody-пути;
  - канон-энкодеры, хэши, golden-векторы;
  - публичные контракты: enum кодов ошибок, proto, REST-формы, мок-фикстуры;
  - схему БД / миграции;
  - security-инварианты (fail-closed, allowlist, step-up, rate-limit);
  - расчётные числа, которые фронт обязан не пересчитывать (compute-split).
- Сомневаешься, опасная ли история — считай опасной.

## Ускорители

- **Канарейка-паттерн**: первая история блока — узкий срез (1 источник × 1 объект /
  1 нода / 1 экран), расширение — следующей историей. Ловит контрактные ошибки до
  тиражирования.
- **Батчинг**: 2–3 мелкие связанные истории — одной dev-сессией; acceptance каждой
  проверяется и отмечается в спринт-файле отдельно.
- Fail-closed дефолты, deny-by-default, CAS/идемпотентность — зашивать при первой
  реализации, не «потом».

## Параллельные дорожки

- Параллелить можно только треки без общей кодовой базы (разные сабмодули/репо)
  или независимые корневые фазы.
- Точки сцепления треков (golden-фикстуры общего контракта и т.п.) объявляются в
  kickoff; изменение точки сцепления → кросс-нота другому треку, не молча.
- Фаза, строящаяся на коде другой фазы, с ней не параллелится; её kickoff готовится,
  когда фаза-фундамент прошла экватор.

## Дисциплина

- Коммит — только по явному разрешению пользователя.
- `sprint-status-<фаза>.yaml` обновляется после каждой истории.
- Субагентам в dev-промпт явно вписывать применимые правила проекта из секции
  истории (иначе субагент их не увидит).

## Применение

- Ко всем implementation-фазам BMAD-проектов и их подготовительным сессиям.
- Kickoff-файлы и файлы эпиков ссылаются на это правило вместо пересказа регламента.

---

## rule: confluence-links.md

---
name: confluence-links
description: Поиск и формирование ссылок в Confluence при работе через MCP. Применяется ко всем операциям с контентом Confluence через MCP (confluence_get_page / confluence_update_page / confluence_update_page_section и др.) в любом проекте.
version: 1.0.0
---

# Правила

## 1. Как искать ссылки на страницы (в raw storage)
- Читай страницу только через confluence_get_page(..., convert_to_markdown=False): raw storage-HTML сохраняет точную структуру ссылок (<ac:link>/<ri:page>/<a href>). Markdown её теряет.
- Ищи два типа «ссылок» на страницы Confluence:
  1. Явные <a href="https://space.samokat.ru/pages/viewpage.action?pageId=NNNN">…</a> — текст обычно голый URL или голый id.
  2. Ссылки по page_id, заданные текстом БЕЗ HTML-ссылки: pageId=NNNN или голый номер NNNN (например, в колонке «Источник» таблицы).

## 2. Какие ссылки преобразовывать
- Преобразовывай ТОЛЬКО ссылки на страницы домена https://space.samokat.ru/.
- Другие инстансы Confluence и внешние (GitLab, Grafana и т.п.) НЕ трогать.
- URL-формы на space.samokat.ru: viewpage.action?pageId=NNNN и display/SPACE/TITLE.
- Если page_id не находится на space.samokat.ru или не резолвится — пропустить, оставить как есть.
- Ничего не удалять: менять только представление ссылки, страница_id всегда сохранять.

## 3. Как получить корректные title/space_key
- Каждый page_id резолвь через confluence_get_page(page_id=NNNN, include_metadata=true, convert_to_markdown=False).
- Используй ТОЧНЫЙ title и реальный space_key из ответа. Не выдумывай названия — бери из get_page, иначе ссылка не соберётся.
- Правильный способ ссылки на страницу — Confluence storage <ac:link> (а не голый <a href>): резолвится платформой, человекочитаем и устойчив.

## 4. Как формировать ссылку (storage-разметка)
Самостоятельная ссылка / в ячейке таблицы:
<ac:link><ri:page ri:content-title="<точный title>" ri:space-key="<space_key>"/></ac:link>

В тексте (абзац, список, заголовок), когда важна читаемость и сохранение page_id — формат «кликабельное название [page_id]»:
<ac:link><ri:page ri:content-title="<точный title>" ri:space-key="<space_key>"/></ac:link> [<page_id>]

- page_id НЕ удалять: остаётся текстом рядом со ссылкой.
- Избегать публикации ссылки в виде голого URL https://space.samokat.ru/pages/viewpage.action?pageId=NNNN как текста ссылки.

## 5. Спецсимволы
- В ri:content-title / ri:space-key экранируй XML-спецсимволы (& → &amp;, <, >, "). Кириллица, тире, точки — как есть.

## 6. Запись изменений (лимит payload)
- update_page с большим body (> ~10 КБ) падает на JSON-сериализации («Expected }»). Не заливай всю страницу одним вызовом.
- Для страниц с таблицами/код-блоками/макросами правь ПО СЕКЦИЯМ через confluence_update_page_section(page_id, heading_text=<точный текущий заголовок>, content_format="storage"). Секция — маленький payload.
- Секция под заголовком меняется вместе с вложенными заголовками и содержимым до следующего заголовка того же/высшего уровня. Если ссылка в тексте заголовка H2/H3 — правишь через секцию родительского заголовка, вкладывая исправленный заголовок в new_content.
- После каждой записи — верификация confluence_get_page(..., convert_to_markdown=False): ac:link на месте и закрыт, нет остаточных viewpage.action?pageId= href, таблицы/код-макросы целы.
- Менять только запрошенный page_id; чужие страницы не трогать.

---

## rule: frontend-components.md

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
---

## rule: frontend-hooks.md

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
---

## rule: frontend-theme.md

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

Color replacement validation — see `rules/frontend-components.md`

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
---

## rule: frontend-zustand.md

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
---

## rule: git-commit-push.md

---
name: git-commit-push
description: Глобальный запрет на git commit/push без явного разрешения пользователя
version: 1.0.0
---

# Git Commit/Push — Глобальное Правило

## 🔒 ЖЁСТКОЕ ПРАВИЛО

**НИКОГДА не выполняй git commit или git push без явного разрешения пользователя.**

## Когда разрешено

Единственный случай когда можно делать commit/push:
- **Пользователь ЯВНО сказал:** "закоммить", "запушь", "сделай commit", "отправь в remote"
- Разрешение должно быть в **текущей сессии**, не предполагать что "ранее было разрешено"

## Когда ЗАПРЕЩЕНО

Никогда не делай commit/push в этих случаях:
- ❌ В процессе работы над задачей (даже если "почти готово")
- ❌ После исправления багов
- ❌ После рефакторинга
- ❌ После добавления фич
- ❌ По умолчанию в конце сессии
- ❌ Без явного вопроса "хочешь закоммитить?"

## Что делать вместо этого

1. **Покажи что изменено:** `git status`, `git diff --stat`
2. **Спроси явно:** "Хочешь закоммитить эти изменения?"
3. **Жди явного ответа:** Только после "да", "закоммить", "ок" — делай commit
4. **Не предполагай:** Если пользователь молчит или говорит "потом" — не делай

## Если пользователь просит "не забыть закоммитить"

- Запомни в контексте сессии
- В конце сессии НАПОМНИ: "Есть незакоммиченные изменения. Закоммитить?"
- Не делай автоматически — жди подтверждения

## Для Orchestrator

Оркестратор должен:
- Не спавнить агентов с permission на commit/push без явного разрешения
- В конце сессии спросить: "Закоммитить изменения?"
- Никогда не делать commit/push "на всякий случай"

## Для Build-агента

Build-агент должен:
- Показать `git diff --stat` перед предложением commit
- Спросить явно: "Закоммитить эти N файлов?"
- Ждать подтверждения перед выполнением

## Для Plan-агента

Plan-агент:
- НЕ может делать commit/push вообще (permission edit/write = deny)
- Может только показать diff и предложить build-агенту

## Примеры корректного поведения

✅ **Правильно:**
```
Пользователь: "Добавь кнопку"
Агент: [делает изменения]
Агент: "Готово! Изменены: 3 файла. Закоммитить?"
Пользователь: "Да"
Агент: git commit -m "feat: add button"
```

❌ **Неправильно:**
```
Пользователь: "Добавь кнопку"
Агент: [делает изменения]
Агент: git commit -m "feat: add button"  # Без спроса!
```

## Примечание

Это правило загружается автоматически через `instructions: ["rules/*.md"]` и применяется ко всем агентам.

---

## rule: go-backend.md

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
---

## rule: go-observability.md

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
---

## rule: opencode-implementer.md

---
name: opencode-implementer
description: Надёжная работа с opencode как исполнителем/ревьюером под оркестрацией Claude (модели Z.AI Coding Plan) — конфиг и запуск без зависаний и лишних суб-агентов
version: 1.0.0
---

# opencode как исполнитель (схема `claude (оркестратор) → opencode`)

Когда Claude-оркестратор делегирует код-работу opencode (исполнитель) + read-only ревью, соблюдать всё ниже — иначе opencode виснет или уходит во внутренние суб-агенты вместо прямой работы.

## Модели — только подписка Z.AI Coding Plan, НЕ pay-API

- Провайдер `zai-coding-plan/` = **подписка**. `zai/` = поштучный pay-API (обычно НЕ авторизован — не использовать). Проверка: `cat ~/.local/share/opencode/auth.json` → должен быть провайдер `zai-coding-plan`.
- Исполнитель: `zai-coding-plan/glm-5-turbo`. Ревьюер: `zai-coding-plan/glm-5.2`. Инвариант: **ревьюер ≠ модель исполнителя**.
- **`glm-5v-turbo` НЕ входит в Coding Plan** — API отдаёт «your current subscription plan does not yet include access to GLM-5V-Turbo», opencode бесконечно ретраит и делает 0 работы. Список рабочих: `opencode models | grep glm`. Проверить доступ модели: `opencode run --model zai-coding-plan/<m> "reply READY"`.

## Обязательный конфиг `~/.config/opencode/opencode.jsonc`

opencode НЕ должен порождать собственных суб-агентов; MCP, вешающие bootstrap, — отключить:

```jsonc
{ "$schema": "https://opencode.ai/config.json",
  "agent": { "build": { "permission": { "task": "deny" } },
             "plan":  { "permission": { "task": "deny" } } } }
```

- `permission.task: "deny"` у `build`+`plan` = tool `task` запрещён = **нет спавна суб-агентов**. Иначе `build` уходит в `agent=general mode=subagent` (десятки вызовов) и виснет; `plan` — в `agent=explore`. Промпт-инструкция «не делегируй» НЕнадёжна — нужен гейт на уровне конфига.
- **Инвариант «плоский запуск» (belt-and-suspenders):** opencode-исполнитель/ревьюер обязан работать ПЛОСКО — не спавнить собственных суб-агентов и не запускать вложенный opencode, ДАЖЕ ЕСЛИ конфиг opencode это разрешает (напр. на машине без настроенного `permission.task: "deny"`). Запрет всегда прописывается текстом в самом промпте запуска — не полагаться только на конфиг.

## Запуск

- ВСЕГДА: спека в **ФАЙЛ** (scratchpad) + **КОРОТКИЙ** промпт-ссылка. Исполнитель: `opencode run --model zai-coding-plan/glm-5-turbo --agent build --auto "Прочитай файл целиком <путь> и выполни. Делай сам."`. Ревьюер: `opencode run --model zai-coding-plan/glm-5.2 --agent plan "<короткий read-only промпт или ссылка на focus-файл>"`.
- **НИКОГДА длинный inline-промпт** через фоновый Bash — zsh-eval обёртка фонового запуска ломается/вешает bootstrap на длинном тексте со спецсимволами (симптом: процесс жив, `opencode.log` доходит до `init` и НИКОГДА не стримит, 0-байт вывод, файлы не тронуты).
- **ЛОВУШКА ревьюера: `plan`-агент (без `--auto`) авто-ОТКЛОНЯЕТ чтение external-dir** (`permission requested: external_directory ... auto-rejecting`) — focus/спека-файл для РЕВЬЮЕРА должен лежать ВНУТРИ проекта (напр. gitignored `.research/<topic>/`), НЕ в `/tmp`-scratchpad. Исполнитель (`build --auto`) external-пути авто-апрувит, ему `/tmp` ок; ревьюер — нет.
- Фон (`run_in_background`) + `dangerouslyDisableSandbox: true` (нужна сеть к z.ai). В промпте: git ЗАПРЕТИТЬ, набор файлов ограничить, «делай сам, не делегируй, не создавай суб-агентов». Ревьюеру дополнительно: запретить Edit/Write/исполняющий Bash/любые git-мутации.
- После impl: `git status` / `git diff --stat` — тронуты только нужные файлы + НЕТ бинарников-артефактов (напр. `apps/*/server` от `go build -o`); коммит/пуш — только оркестратор, никогда opencode.

## Диагностика зависания

- Симптом: процесс жив (`pgrep -af "opencode run"`), 0-байт вывод, целевые файлы не тронуты.
- Лог `~/.local/share/opencode/log/opencode.log`, `grep "<run-id>"`:
  - только `bootstrapping → init → cleanup` БЕЗ `message=stream` → встал на старте (длинный inline-промпт / MCP-хэнг / оверлоуд).
  - `agent=general|explore mode=subagent` → ушёл в суб-агентов (проверить, что `permission.task: "deny"` реально в конфиге).
  - `error ... temporarily overloaded` → транзиентный флап z.ai.
- Действие: `pkill -f "opencode run"` → пробой `opencode run ... "reply READY"` (проверить, что сервис отвечает) → релонч (короткий промпт + spec-файл).
---

## rule: README.md

# Opencode Rules

Правила для сабагентов-разработчиков (react-dev, go-dev, rust-dev).
Загружаются через `skill("rule-name")` или по совпадению с задачей.

## Индекс (11 правил)

| Правило | Для кого | Описание |
|---------|----------|----------|
| frontend-components | react-dev | Компонентная архитектура — ui-kit/ui/entity/widgets, CVA, Storybook, cn() |
| frontend-hooks | react-dev | Паттерны хуков — one per concern, return pattern, naming |
| frontend-theme | react-dev | Тема — CSS variables, data-theme, ThemeBox, генерация |
| frontend-zustand | react-dev | Zustand — создание сторов, persist, partialize, actions |
| go-backend | go-dev | Go — структура, ошибки, middleware, HTTP, тесты |
| go-observability | go-dev | Go — логгирование, метрики, трассировка, health checks |
| rust-errors | rust-dev | Rust — error enums, thiserror, severity, Mutex |
| tauri-bridge | rust-dev/react-dev | Tauri v2 — IPC, команды, события, безопасность |
| opencode-implementer | orchestrator | Как opencode работает как executor под оркестрацией |
| bmad-impl-story-cycle | orchestrator | BMAD цикл реализации — эпики, ревью по классу, Fable-гейт |
| git-commit-push | orchestrator | Глобальный запрет на git commit/push без явного разрешения пользователя |
| confluence-links | mcp-confluence | Поиск и формирование ссылок в Confluence при работе через MCP |

## Замечание о размере правил

Правила загружаются каждому агенту через `"instructions": ["rules/*.md"]` в `opencode.json`. Суммарный вес правил ≈ 96 КБ (~20-25K токенов) на сессию, включая агентов, которым правила не нужны (например, `orchestrator` — read: deny, и `go-dev`, которому тащатся React-правила).

**Рекомендация:** если opencode 1.18.x поддерживает per-agent `instructions` во фронтматтере агента — вынести стеко-специфичные правила (frontend-components, frontend-theme, tauri-bridge и т.п.) из глобальных в per-agent, чтобы не инжектить нерелевантный контекст. Механизм загрузки в текущем конфиге не менялся — это ориентир на будущее.
---

## rule: rust-errors.md

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
---

## rule: tauri-bridge.md

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


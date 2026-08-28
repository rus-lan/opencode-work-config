# ⚙️ Конфигурация Opencode — полная документация

**Репозиторий:** `git@github.com:rus-lan/opencode-work-config.git`
**Версия opencode:** 1.18.24
**Модель по умолчанию:** `ecom/deepseek-v4-flash`
**Агент по умолчанию:** `orchestrator`

> Документация обновлена на основе фактического состояния файлов конфигурации.

---

## 📋 Содержание

1. [🏗 Структура каталогов](#-1-структура-каталогов)
2. [📜 opencode.json — главный конфиг](#-2-opencodejson--главный-конфиг)
3. [🤖 Агенты](#-3-агенты)
   - 3.1 [Primary-агенты](#31-primary-агенты)
   - 3.2 [Subagents](#32-subagents)
4. [📋 Правила (Rules)](#-4-правила-rules)
5. [🛠 Skills](#-5-skills)
6. [⌨ Команды](#-6-команды)
7. [🌐 MCP Серверы](#-7-mcp-серверы)
8. [🔌 Плагины](#-8-плагины)
9. [🧩 Провайдеры моделей](#-9-провайдеры-моделей)
10. [🔒 Защита и безопасность](#-10-защита-и-безопасность)
11. [📜 Скрипты](#-11-скрипты)
12. [🧪 Тесты](#-12-тесты)
13. [📚 Документы](#-13-документы)
14. [🚀 Установка на новом устройстве](#-14-установка-на-новом-устройстве)
15. [🔄 Обновление конфигурации](#-15-обновление-конфигурации)
16. [⚠️ Известные расхождения и проблемы](#-16-известные-расхождения-и-проблемы)

---

## 🏗 1. Структура каталогов

```
~/.config/opencode/
├── .env.example              # Шаблон API-токенов
├── .gitignore
├── opencode.json             # Главный конфиг (модели, провайдеры, MCP, permissions)
├── package.json              # npm-зависимости
├── package-lock.json
├── README.md                 # Быстрый старт
├── CONFIG_DOCUMENTATION.md   # Этот файл
├── guard.sh                  # Защита от опасных compound-команд
├── pre-commit.sh             # Pre-commit валидация (Zero-Rework Protocol)
├── context-check.sh          # Проверка consistency контекста сессии
├── metrics.json              # Метрики последней сессии (gitignored)
├── agents/                   # 24 файла описаний агентов (.md)
├── commands/                 # 6 команд (.md) + herdr-status.sh
├── skills/                   # 23 директории скиллов (SKILL.md + ресурсы)
├── plugins/                  # JS-плагины (aistats.js, herdr-agent-state.js)
├── rules/                    # 11 правил (.md) + README.md
├── docs/                     # HERDR_METRICS_INTEGRATION.md
├── prompts/                  # Пусто (только .gitignore — заглушка)
└── node_modules/             # npm-зависимости (gitignored)
```

---

## 📜 2. opencode.json — главный конфиг

Файл `opencode.json` (179 строк). Схема: `https://opencode.ai/config.json`.

### 2.1 Корневые поля

| Поле | Значение | Описание |
|------|----------|----------|
| `$schema` | `https://opencode.ai/config.json` | Ссылка на JSON-схему |
| `model` | `ecom/deepseek-v4-flash` | Модель по умолчанию |
| `default_agent` | `orchestrator` | Агент, запускаемый по умолчанию |
| `small_model` | `ecom/qwen3.8-27b` | Лёгкая модель для нетворческих задач (тайтлы, компактизация) |
| `subagent_depth` | `4` | Максимальная вложенность сабагентов (глубокое дерево декомпозиции) |

### 2.2 Глобальные permissions

```json
"permission": {
  "bash": "allow",
  "edit": "allow"
}
```

Глобальный дефолт для всех агентов. Каждый агент может переопределять permissions в своём `.md` frontmatter — и большинство так и делает. См. §3.

> **Важно:** В `opencode.json` **нет** блока `agent` — конфигурация агентов (модель, permissions, steps) живёт **исключительно** в frontmatter файлов `agents/*.md`. В `opencode.json` также нет блоков `command` и `plugin` — команды и плагины авто-обнаруживаются opencode из соответствующих директорий.

### 2.3 Instructions (авто-загрузка правил)

```json
"instructions": ["rules/*.md"]
```

Все 11 правил из `rules/` автоматически загружаются в system prompt. Правила доступны всем агентам без явного вызова `skill()`.

### 2.4 Watcher

```json
"watcher": {
  "ignore": [
    "node_modules/**", ".git/**", ".bmad/**", ".research/**",
    "*.log", "dist/**", ".next/**", ".cache/**"
  ]
}
```

Watcher не реагирует на изменения в шумных директориях.

### 2.5 Compaction (управление контекстом)

```json
"compaction": {
  "auto": true,
  "reserved": 8000,
  "tail_turns": 3,
  "prune": true
}
```

Автоматическая компактизация при заполнении контекста: резерв 8K токенов, сохранение 3 последних ходов, обрезка старых tool output.

### 2.6 Tool output limits

```json
"tool_output": {
  "max_lines": 2000,
  "max_bytes": 51200
}
```

Предотвращает забивание контекста большим выводом инструментов.

---

## 🤖 3. Агенты

Агенты определяются **только** в `agents/*.md` (24 файла). Конфигурация — в YAML frontmatter каждого файла. Нет блока `agent` в `opencode.json`.

### 3.1 Primary-агенты

| Агент | Модель | Steps | Color | Temp | Роль |
|-------|--------|-------|-------|------|------|
| **orchestrator** | `ecom/deepseek-v4-flash` | 30 | `#FF5733` | 0.15 | Оркестратор — только спавнит сабагентов |
| **build** | `ecom/deepseek-v4-flash` | 50 | `success` | 0.15 | Исполнитель — пишет код, запускает команды |
| **plan** | `ecom/deepseek-v4-flash` | 30 | `info` | — | Планировщик — read-only анализ и план-ревью |

#### Orchestrator (`agents/orchestrator.md`)
- **Роль:** Диспетчер — распределяет задачи между сабагентами. НИЧЕГО не делает сам.
- **Модель:** `ecom/deepseek-v4-flash`, temperature 0.15
- **Permissions:** `task=allow`, `skill=allow`, `todowrite=allow`, `question=allow`, всё остальное `deny` (read/edit/write/bash/glob/grep = deny)
- **Запуск:** Автоматически (агент по умолчанию)

#### Build (`agents/build.md`)
- **Роль:** Исполнитель с полным доступом — пишет код, запускает команды, редактирует файлы, спавнит сабагентов
- **Модель:** `ecom/deepseek-v4-flash`, temperature 0.15
- **Permissions:** Всё `allow` (task, skill, read, write, edit, bash, glob, grep, webfetch, websearch, question)
- **Запуск:** `/build <задача>` или через оркестратора

#### Plan (`agents/plan.md`)
- **Роль:** Планировщик и ревьюер — read-only анализ кода, создание планов, архитектурное ревью. НЕ пишет код.
- **Модель:** `ecom/deepseek-v4-flash`
- **Permissions:** `read=allow`, `glob=allow`, `grep=allow`, `question=allow`, `bash=ask`, `edit=deny`, `write=deny`, `task=deny`

### 3.2 Subagents

| # | Агент | Модель | Hidden | Роль | Ключевые permissions |
|---|-------|--------|--------|------|---------------------|
| 1 | `explore` | `ecom/qwen3.8-27b-no-think` | — | Быстрое исследование кодовой базы (read-only) | read/glob/grep/bash=allow, write/edit=deny, task=allow |
| 2 | `project-mapper` | `ecom/qwen3.8-27b-no-think` | — | Построение карты проекта | read/glob/grep/bash=allow, edit=deny, write=allow, task=allow |
| 3 | `desearch-researcher` | `ecom/deepseek-v4-flash` | — | Глубокий веб-ресёрч | read/write/edit/glob/grep/bash/websearch/webfetch=allow |
| 4 | `desearch-synthesizer` | `ecom/deepseek-v4-flash` | — | Синтез ресёрч-отчётов | read/write/edit/glob/grep/bash/websearch=allow, webfetch=deny |
| 5 | `react-dev` | `ecom/qwen3.8-27b` | — | React/TS разработка | read/write/edit/glob/grep/bash=allow, task=allow |
| 6 | `go-dev` | `ecom/qwen3.8-27b` | — | Go backend разработка | read/write/edit/glob/grep/bash=allow, task=allow |
| 7 | `rust-dev` | `ecom/qwen3.8-27b` | — | Rust разработка | read/write/edit/glob/grep/bash/task=allow |
| 8 | `seo-writer` | `ecom/qwen3.8-27b` | — | SEO-контент (read-only, через task) | read/glob/grep/task/webfetch=allow, write/edit=deny, bash=ask |
| 9 | `reviewer` | `ecom/deepseek-v4-flash` | ✅ hidden | Общий code review (standards + spec) | read/glob/grep=allow, write/edit/bash/task=deny |
| 10 | `reviewer-standards` | `ecom/deepseek-v4-flash` | ✅ hidden | Ревью кодстайла и конвенций | read/glob/grep=allow, edit/write/bash/task=deny |
| 11 | `reviewer-spec` | `ecom/deepseek-v4-flash` | ✅ hidden | Ревью соответствия спецификации | read/glob/grep=allow, edit/write/bash/task=deny |
| 12 | `reviewer-arch` | `ecom/deepseek-v4-flash` | ✅ hidden | Архитектурное ревью | read/glob/grep=allow, edit/write/bash/task=deny |
| 13 | `test-agent` | `ecom/qwen3.8-27b-no-think` | — | Запуск тестов и отчёт | read/glob/grep/bash=allow, write/edit=deny, task=allow |
| 14 | `security-check` | `ecom/deepseek-v4-flash` | — | Аудит security/reliability/simplicity | read/glob/grep/bash=allow, write/edit/task=deny |
| 15 | `soc-check` | `ecom/deepseek-v4-flash` | — | Проверка SOC/контрактов/покрытия | read/glob/grep/bash=allow, write/edit/task=deny |
| 16 | `ui-designer` | `ecom/deepseek-v4-flash` | — | UI/UX дизайн (только спецификации) | read/write/edit/glob/grep=allow, bash/task=deny |
| 17 | `mcp-aistats` | `ecom/qwen3.8-27b-no-think` | — | MCP-обёртка aistats (метрики) | только MCP-инструменты aistats; read/write/edit/bash/glob/grep/task=deny |
| 18 | `mcp-confluence` | `ecom/qwen3.8-27b-no-think` | — | MCP-обёртка Confluence (read/write) | только MCP-инструменты Confluence; file/task=deny |
| 19 | `mcp-jira` | `ecom/qwen3.8-27b-no-think` | — | MCP-обёртка Jira (read/write) | только MCP-инструменты Jira; file/task=deny |
| 20 | `mcp-adr-drawio` | `ecom/qwen3.8-27b` | — | MCP-обёртка ADR drawio (схемы) | MCP-adr-drawio + read/write/glob/grep=allow (для артефактов), bash=deny, task=deny |
| 21 | `mcp-playwright` | `ecom/deepseek-v4-flash` | — | MCP-обёртка playwright (browser-автоматизация) | только MCP-инструменты playwright; file/task=deny |

> **Hidden-агенты** (`hidden: true` в frontmatter) — не появляются в списке доступных агентов UI, но могут вызываться оркестратором через `task()`.

### Модели по агентам — сводка

| Модель | Агенты |
|--------|--------|
| `ecom/deepseek-v4-flash` | orchestrator, build, plan, reviewer, reviewer-standards, reviewer-spec, reviewer-arch, security-check, soc-check, desearch-researcher, desearch-synthesizer, ui-designer, mcp-playwright |
| `ecom/qwen3.8-27b` | react-dev, go-dev, rust-dev, seo-writer, mcp-adr-drawio |
| `ecom/qwen3.8-27b-no-think` | explore, project-mapper, test-agent, mcp-aistats, mcp-confluence, mcp-jira |

---

## 📋 4. Правила (Rules)

11 правил в `rules/`, авто-загружаются через `instructions: ["rules/*.md"]`. Индекс — в `rules/README.md`.

| Правило | Версия | Для кого | Описание |
|---------|--------|----------|----------|
| frontend-components | 2.8.1 | react-dev | Компонентная архитектура — ui-kit/ui/entity/widgets, CVA, cn(), forwardRef, Storybook |
| frontend-hooks | 1.3.0 | react-dev | Паттерны хуков — one per concern, return pattern, naming |
| frontend-theme | 3.1.0 | react-dev | Тема — CSS variables, data-theme, ThemeBox, Vite plugin, генерация |
| frontend-zustand | 1.2.0 | react-dev | Zustand — создание сторов, persist, partialize, actions |
| go-backend | 1.2.1 | go-dev | Go — структура, ошибки, middleware, HTTP, тесты |
| go-observability | 1.0.0 | go-dev | Go — логгирование, метрики, трассировка, health checks |
| rust-errors | 1.1.0 | rust-dev | Rust — error enums, thiserror, severity, Mutex |
| tauri-bridge | 1.1.0 | rust-dev / react-dev | Tauri v2 — IPC, команды, события, безопасность |
| opencode-implementer | 1.0.0 | orchestrator | Как opencode работает как executor под оркестрацией |
| bmad-impl-story-cycle | 1.0.0 | orchestrator | BMAD цикл реализации — эпики, ревью по классу, Fable-гейт |
| git-commit-push | 1.0.0 | все | Глобальный запрет на git commit/push без явного разрешения |

> **Примечание:** `rules/README.md` заявляет «10 правил», но фактически в каталоге 11 `.md`-файлов (в индексе README не учтено правило `git-commit-push`).

---

## 🛠 5. Skills

23 скилла в `skills/`. Каждый — директория с `SKILL.md` (frontmatter: `name`, `description`) и опциональными ресурсами.

| Skill | Описание |
|-------|----------|
| `bmad-check-implementation-readiness` | Проверка готовности фазы к реализации: acceptance criteria, зависимости, дизайн, test plan |
| `bmad-create-epics` | Декомпозиция спеки в эпики с coverage mapping |
| `bmad-create-story` | Создание user story из epic stub: AC, техн. заметки, risk class |
| `bmad-dev-story` | Разработка BMAD-истории: код + тесты + ревью по risk class |
| `bmad-impl` | Облегчённый BMAD-цикл для opencode — эпики → истории → ревью → Fable-гейт |
| `bmad-retrospective` | Ретроспектива спринта/майлстоуна |
| `bmad-sprint-planning` | Планирование спринта: приоритизация, оценки, sprint-status файл |
| `caveman` | Ultra-compressed communication — сокращает токены ~75%, уровни lite/full/ultra |
| `config-pull` | Pull последних изменений из `~/claude-config` в `~/.config/opencode/` |
| `context-metrics` | Мониторинг метрик контекста, лимитов и effort |
| `desearch` | Параллельный deep web research (3-5 углов) с синтезированным отчётом |
| `design` | UI/UX дизайн из скриншотов и промптов — анти-AI-slop, анимации, градиенты |

| `full-workflow` | Полный 7-этапный workflow через orchestrator: map → grill → research → implement → review → testing → safety → soc |
| `graphify` | Построение графа знаний из кода/документов/изображений с query/path/explain tools |
| `grill-me` | Интерактивный допрос плана/решения — разбирает дерево решений шаг за шагом |
| `impl-kickoff` | Валидация readiness и запуск процесса разработки |
| `implement` | Реализация работы по спеке/тикетам |
| `mapps` | Multi-repo workspace management — клонирование, Makefile, карты проектов |
| `project-pull` | Pull правил/агентов/скиллов из `~/claude-config` в текущий проект |
| `project-push` | Push улучшенных правил/агентов/скиллов из проекта в `~/claude-config` |
| `unrobot` | Детекция и удаление AI-маркеров в тексте, 8 языков, pipeline detect → rewrite → verify |
| `workspace-init` | Создание workspace-обёртки для проекта — изоляция конфига от app репозиториев |

> **Внешние скиллы** (авто-загружаются из других каталогов, не входят в этот репозиторий):
> - `~/.agents/skills/` — ask-matt, code-review, codebase-design, diagnosing-bugs, domain-modeling, find-skills, grill-with-docs, grilling, handoff, improve-codebase-architecture, prototype, research, setup-matt-pocock-skills, tdd, teach, to-spec, to-tickets, triage, wayfinder, writing-great-skills
> - `~/.claude/skills/` — team-metrics

---

## ⌨ 6. Команды

6 команд в `commands/` (каждая — `.md` с frontmatter `name`, `description`, опционально `agent`, `subtask`).

| Команда | Agent | Subtask | Описание |
|---------|-------|---------|----------|
| `/context` | build | ✅ | Метрики контекста, лимиты, usage. Флаги: `--limits`, `--watch`, `--effort` |
| `/get-session-metrics` | build | ✅ | Метрики текущей сессии из aistats (`aistats report --format json`). Флаг: `--verbose` |
| `/grill-me` | — | — | Интерактивный допрос. Делегирует в `skills/grill-me/SKILL.md` |
| `/herdr-status` | build | ✅ | Запускает `commands/herdr-status.sh` — метрики сессии в Herdr UI |
| `/m` | — | — | Вызывает tool `get_metrics` — dashboard метрик сессии |
| `/mapps` | build | ✅ | Multi-repo workspace management. Аргументы: `init <url>...`, `add <url>`, `rm <name>`, `--help` |

> **Примечание:** Команды `/start`, `/workflow`, `/build`, `/map`, `/safety-check`, `/soc-check`, `/caveman`, `/unrobot`, `/bmad-impl` и др. — **не имеют** `.md`-файлов в `commands/`. Они реализуются через skills (`full-workflow`, `caveman`, `unrobot`, `bmad-impl`) или прямой вызов агентов оркестратором.

---

## 🌐 7. MCP Серверы

7 MCP-серверов в `opencode.json` → секция `mcp`:

| Сервер | Тип | Команда / URL | Назначение |
|--------|-----|---------------|------------|
| `aistats` | local | `aistats mcp` | Сбор метрик токенов, стоимости, рекомендации по эффективности |
| `playwright` | local | `npx @playwright/mcp@latest --executable-path ${HOME}/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome --headless --no-sandbox --isolated` | E2E тестирование (headless Chromium) |
| `Confluence_Samokat_Read_Only` | remote | `.../Confluence_Samokat_Read_Only/mcp` | Чтение Confluence (`CONFLUENCE_TOKEN`) |
| `Confluence_Samokat_Write` | remote | `.../Confluence_Samokat_Write/mcp` | Запись Confluence (`CONFLUENCE_TOKEN`) |
| `Jira_Samokat_Read_Only` | remote | `.../Jira_Samokat_Read_Only/mcp` | Чтение Jira (`JIRA_TOKEN`) |
| `Jira_Samokat_Write` | remote | `.../Jira_Samokat_Write/mcp` | Запись Jira (`JIRA_TOKEN`) |
| `MCP_adr_drawio` | remote | `http://mcp-adr-drawio-ai-factory.../mcp` | ADR drawio |

Playwright MCP дополнительно настраивает environment: `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64`.

### aistats MCP — возможности
- `aistats_aistats_projects` — список проектов с метриками (sessions, turns, time, tokens, cost)
- `aistats_aistats_report` — отчёт по продуктивности (tokens, cost, time, phase breakdown)
- `aistats_aistats_recommendations` — ранжированные рекомендации по эффективности

### MCP-обёртки (сабагенты)

Для каждого подключённого MCP-сервера создан сабагент-обёртка, который выполняет MCP-действия в **изолированном контексте** и возвращает в основной контекст **только краткий агрегированный результат** — это снижает потребление контекстного окна основного агента.

| Обёртка (`agents/*.md`) | MCP-сервер | Модель | Особенности |
|-------------------------|------------|--------|-------------|
| `mcp-aistats` | aistats | qwen3.8-27b-no-think | Лёгкие метрики; file/bash/task=deny, только aistats-инструменты |
| `mcp-confluence` | Confluence RO + Write | qwen3.8-27b-no-think | Чтение и запись wiki; file/task=deny |
| `mcp-jira` | Jira RO + Write | qwen3.8-27b-no-think | Чтение и запись тикетов; file/task=deny |
| `mcp-adr-drawio` | MCP_adr_drawio | qwen3.8-27b | Генерация ADR-схем; read/write/glob/grep=allow (артефакты), bash=deny, task=deny |
| `mcp-playwright` | playwright | deepseek-v4-flash | Тяжёлая browser-автоматизация/исследование страниц; file/task=deny |

Все обёртки: `task: deny` (терминальные на своём уровне), возвращают только агрегированный итог (ID/ключ/статус/числа), не разворачивая промежуточные подробности. Оркестратор и `build` делегируют обёрткам вместо прямых вызовов MCP-инструментов.

### Глубокая вложенность сабагентов

`subagent_depth: 4` — сабагенты, которым разрешён `task: allow` (`build`, `plan`, `react-dev`, `go-dev`, `rust-dev`, `explore`, `project-mapper`, `test-agent`), могут порождать собственных сабагентов, образуя глубокое дерево декомпозиции. Каждый уровень держит собственный мини-контекст и возвращает наверх только агрегированный результат — поэтому глубина не раздувает основной контекст. Ревьюеры, `security-check`, `soc-check` и MCP-обёртки остаются `task: deny` (читают/выполняют, не декомпозируют).

---

## 🔌 8. Плагины

2 JS-плагина. В `opencode.json` **нет** секции `plugin` — плагины авто-обнаруживаются opencode из директории `plugins/`.

> **Примечание:** файлы `aistats.js` и `herdr-agent-state.js` существуют **только** в `plugins/`. Копий в корне конфига нет (в отличие от того, что указывала старая документация).

### aistats.js (`plugins/aistats.js`)
- **Назначение:** Ингест метрик сессии в aistats при idle
- **Событие:** `session.idle` на root-сессиях (проверяет `parentID`)
- **Fire-and-forget:** не ждёт результата, ошибки глотаются
- **Команда:** `aistats ingest --tool opencode`
- **Зависимость:** `aistats` CLI в PATH

### herdr-agent-state.js (`plugins/herdr-agent-state.js`)
- **Назначение:** Отслеживание состояния агентов в Herdr UI + кастомный tool `get_metrics`
- **Tool:** `get_metrics` — возвращает markdown dashboard с метриками сессии (duration, tokens, cost, model, status, subagents)
- **Состояния:** `working` | `idle` | `blocked`
- **Фичи:** обновление window title Herdr панели, debounced push (300ms), refresh метрик каждые 10 секунд, запись в `metrics.json`, отслеживание дочерних сессий
- **Зависимости:** `node:net`, `node:child_process`, `node:fs`, `node:path`, `@opencode-ai/plugin/tool`

**События:**

| Событие | Действие |
|---------|----------|
| `session.created` | Старт сессии, начало refresh метрик, report в Herdr |
| `session.updated` | Обновление model/tokens/cost из event data |
| `session.idle` | Остановка refresh, финальные метрики, report idle |
| `session.error` | Установка статуса blocked |
| `session.deleted` | Очистка данных сессии |

---

## 🧩 9. Провайдеры моделей

3 провайдера в `opencode.json` → секция `provider`, **2 общих токена** (`ECOM_LLM_TOKEN`, `ECOM_LLM_EXP_TOKEN`). Per-model токенов, timeout и rate-limits в конфиге **нет**.

| Провайдер | Модель | Context | Output | API Key Env | npm-пакет | Base URL |
|----------|--------|---------|--------|-------------|-----------|----------|
| `ecom` | deepseek-v4-flash | 256K | 16K | `ECOM_LLM_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |
| `ecom` | qwen3.8-27b | 256K | 16K | `ECOM_LLM_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |
| `ecom` | qwen3.8-27b-no-think | 128K | 8K | `ECOM_LLM_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |
| `ecom-exp` | glm-5.2 *(экспериментальная)* | 256K | 16K | `ECOM_LLM_EXP_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |
| `zai-coding-plan` | GLM-5.2 *(экспериментальная)* | 1M | 131072 | — (подписка Z.AI) | — (built-in) | `https://api.z.ai/api/coding/paas/v4` |

### Особенности провайдеров

**ecom** — основной провайдер. Использует base URL `https://llm-core-olap.samokat.ru/v1`, npm-пакет `@ai-sdk/openai-compatible`, ключ `ECOM_LLM_TOKEN`, `setCacheKey: true`. Opencode.json **не содержит** per-model токенов, timeout / rate-limits — только базовые `limit` (context/output) на каждую модель.

**ecom-exp** — экспериментальный провайдер. Ключ `ECOM_LLM_EXP_TOKEN`. Содержит единственную экспериментальную модель `glm-5.2`.

**zai-coding-plan** — провайдер подписки Z.AI Coding Plan. Встроенный в opencode, без apiKey (авторизация через `~/.local/share/opencode/auth.json`). Контекст 1M, output 131K — самый большой контекст.

### Модель по умолчанию

Поле `model` в `opencode.json` = `ecom/deepseek-v4-flash`. Малая модель (`small_model`) = `ecom/qwen3.8-27b`.

### glm-5.2 — экспериментальная модель

`ecom-exp/glm-5.2` и `zai-coding-plan/glm-5.2` — **экспериментальные** и не всегда доступны. Они **не назначены ни одному агенту на постоянной основе** и по умолчанию не задействованы. Допускается ТОЛЬКО опциональное использование с fallback-проверкой: в случае недоступности glm-5.2 использовать `ecom/deepseek-v4-flash`. Не подключать как жёсткий дефолт ни одному агенту.

---

## 🔒 10. Защита и безопасность

### guard.sh (`/home/ruslan/.config/opencode/guard.sh`)
Защита от опасных compound-команд (128 строк).

**Блокирует:**
- `rm` в compound-командах (`&&`, `||`, `;`)
- `wget`, `curl -o`/`-O` (скачивание)
- `pip3 install`, `brew install`, `cargo install`, `go install`
- `git push --force`, `git reset --hard`, `git clean -fdx`

**Логика:**
- Простые опасные команды → exit 0 (обычная система разрешений)
- Compound-команды с опасными операциями → exit 1 (блокировка)

**Команды:**
```bash
./guard.sh --list        # Список опасных паттернов
./guard.sh --install     # Установка как pre-commit hook
./guard.sh "ls -la"      # Проверка (exit 0 — безопасно)
./guard.sh "echo hi && rm -rf /tmp"  # Блокировка (exit 1)
```

### pre-commit.sh (`/home/ruslan/.config/opencode/pre-commit.sh`)
Pre-commit валидация по Zero-Rework Protocol (123 строки). 6 этапов:
1. Type checking (`tsc --noEmit`)
2. Linting (`eslint`)
3. Тесты (`npm test`)
4. Spec traceability
5. Context consistency
6. Commit message format (conventional commits)

### context-check.sh (`/home/ruslan/.config/opencode/context-check.sh`)
Проверка consistency контекста сессии (59 строк). Валидирует файл `/tmp/opencode-session-context.md` — наличие секций: Session Context, Recent Error Patterns, Zero-Rework Protocol Checklist.

### Правило git-commit-push
Глобальный запрет на `git commit`/`git push` без явного разрешения пользователя (см. §4, правило `git-commit-push` v1.0.0).

---

## 📜 11. Скрипты

| Скрипт | Строк | Назначение |
|--------|-------|------------|
| `guard.sh` | 128 | Защита от опасных compound-команд (см. §10) |
| `pre-commit.sh` | 123 | Pre-commit валидация Zero-Rework Protocol (см. §10) |
| `context-check.sh` | 59 | Проверка consistency контекста сессии (см. §10) |
| `commands/herdr-status.sh` | 82 | Скрипт для команды `/herdr-status` — вывод метрик сессии в Herdr UI |

### package.json

```json
{
  "dependencies": {
    "@ai-sdk/openai-compatible": "^2.0.41",
    "@opencode-ai/plugin": "^1.18.7"
  }
}
```

---

## 📚 13. Документы

| Документ | Назначение |
|----------|------------|
| `README.md` | Быстрый старт — установка, архитектура, агенты, скиллы, команды, провайдеры |
| `CONFIG_DOCUMENTATION.md` | Этот файл — полная документация конфигурации |
| `rules/README.md` | Индекс правил (11 шт.) |
| `docs/HERDR_METRICS_INTEGRATION.md` | Документация интеграции Herdr (212 строк) — плагин `herdr-agent-state.js`, tool `get_metrics`, события, файл метрик |
| `.env.example` | Шаблон переменных окружения для API-ключей |
| `.gitignore` | Игнорируемые файлы: `node_modules/`, `.env`, `*.log`, `.DS_Store`, `.vscode/`, `.idea/`, `*.swp`, `tmp/`, `temp/`, `*.tmp`, `metrics.json`, `skills/unrobot/test/` |

### .env.example — переменные окружения

```bash
# ECOM TECH
ECOM_LLM_TOKEN=
ECOM_LLM_EXP_TOKEN=
# MCP: Confluence Read-Only / Write
CONFLUENCE_TOKEN=
# MCP: Jira Read-Only / Write
JIRA_TOKEN=
```

Все ecom/ecom-exp модели используют общие токены `ECOM_LLM_TOKEN` / `ECOM_LLM_EXP_TOKEN`; `CONFLUENCE_TOKEN` и `JIRA_TOKEN` — для remote MCP-серверов Confluence/Jira.

---

## 🚀 14. Установка на новом устройстве

### Ручная установка

```bash
# 1. Установить opencode
curl -fsSL https://opencode.ai/install.sh | sh

# 2. Клонировать конфигурацию
git clone git@github.com:rus-lan/opencode-work-config.git ~/.config/opencode

# 3. Установить зависимости
cd ~/.config/opencode && npm install

# 4. Настроить переменные окружения
cp .env.example .env
# Отредактировать .env — вставить API-токены

# 5. Убедиться что ~/.local/bin в PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc

# 6. Проверка
opencode --version    # 1.18.16
opencode run "Hello"
```

### API-токены

| Переменная | Провайдер / MCP | Где взять |
|-----------|------------------|-----------|
| `ECOM_LLM_TOKEN` | ecom (все модели) | Инфраструктура Samokat (llm-core-olap) |
| `ECOM_LLM_EXP_TOKEN` | ecom-exp (glm-5.2) | Инфраструктура Samokat (llm-core-olap) |
| `CONFLUENCE_TOKEN` | Confluence MCP (Read-Only/Write) | Confluence / инфраструктура Samokat |
| `JIRA_TOKEN` | Jira MCP (Read-Only/Write) | Jira / инфраструктура Samokat |
| — | zai-coding-plan | Подписка Z.AI Coding Plan (авторизация через `~/.local/share/opencode/auth.json`) |

Все ecom-* провайдеры используют base URL: `https://llm-core-olap.samokat.ru/v1`

### Guard hooks (рекомендовано)

```bash
~/.config/opencode/guard.sh --install
```

---

## 🔄 15. Обновление конфигурации

```bash
cd ~/.config/opencode && git pull
npm install
```

**Project-level синхронизация:**
- `/project-pull` — pull правил/агентов/скиллов в проект
- `/project-push` — push улучшений из проекта в центральный репо
- `config-pull` skill — pull последних изменений из `~/claude-config`

**После обновления:**
```bash
npm install                              # обновить зависимости
~/.config/opencode/guard.sh --list       # проверить актуальность guard
```

---

## ⚠️ 16. Известные расхождения и проблемы

При сопоставлении файлов конфигурации обнаружены следующие несоответствия:

### 16.1 .env.example и opencode.json синхронизированы
`.env.example` содержит 2 токена (`ECOM_LLM_TOKEN`, `ECOM_LLM_EXP_TOKEN`), которые соответствуют `opencode.json` (там нет per-model токенов). Дополнительно добавлены `CONFLUENCE_TOKEN` и `JIRA_TOKEN` для remote MCP-серверов Confluence/Jira.

### 16.2 Дубликатов плагинов нет
Файлы `aistats.js` и `herdr-agent-state.js` существуют **только** в `plugins/`. Копий в корне конфига нет. Ранее задокументированные «дубликаты в корне» неверны.

### 16.3 rules/README.md считает неправильно
README заявляет «10 правил» и индекс-таблица содержит 10 строк, но фактически в `rules/` лежит **11** `.md`-файлов правил (в индексе не учтён `git-commit-push`). Старая CONFIG_DOCUMENTATION.md в одном месте писала «12 правил», в другом «11».

### 16.4 README.md содержал устаревшие данные
Часть устаревших данных в README исправлена в ходе синхронизации. Остаточные отличия: раздел «Команды (6)» не упоминает `/get-session-metrics` как отдельную команду (реализована через aiStats).

### 16.5 CLAUDE.md отсутствует
Старая CONFIG_DOCUMENTATION.md (§8) упоминала `CLAUDE.md` — «Глобальные правила поведения агента (180 строк)». Файл **не существует** в текущем каталоге конфигурации. Вероятно, удалён или перенесён.

### 16.6 Каталог prompts/ пуст
Содержит только `.gitignore`. Назначение неясно — возможно, заглушка для будущих промптов.

### 16.7 seo-writer — subagent, не primary
Старая документация и README перечисляют `seo-writer` как primary-агента. Фактически в frontmatter `agents/seo-writer.md` указано `mode: subagent`.

### 16.8 Hidden-агенты не документированы
Агенты `reviewer`, `reviewer-standards`, `reviewer-spec`, `reviewer-arch` имеют `hidden: true` в frontmatter — не появляются в UI списке. Старая документация не упоминала этот атрибут.

### 16.9 Модель giga3-10b удалена
Модель `giga3-10b` (провайдер `ecom`) удалена из `opencode.json` и из документации. Ни один агент ранее её не использовал (была не задействована). Теперь провайдер `ecom` содержит 3 модели: `qwen3.8-27b`, `qwen3.8-27b-no-think`, `deepseek-v4-flash`.

### 16.10 Модель qwen3.8-27b-no-think теперь задействована
`qwen3.8-27b-no-think` (128K/8K) ранее не использовалась. Теперь назначена на простые/механические задачи: `explore`, `project-mapper`, `test-agent` и MCP-обёртки (`mcp-aistats`, `mcp-confluence`, `mcp-jira`).

### 16.11 Глубокая вложенность сабагентов
`subagent_depth` поднят с `2` до `4`. `task: allow` включён для `plan`, `react-dev`, `go-dev` (ранее deny) и уже имелся у `build`/`rust-dev`/`seo-writer`/`orchestrator`; дополнительно включён у `explore`, `project-mapper`, `test-agent`. Ревьюеры, `security-check`, `soc-check` и MCP-обёртки остались `task: deny`.

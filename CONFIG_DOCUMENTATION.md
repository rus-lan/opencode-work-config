# ⚙️ Конфигурация Opencode — полная документация

**Репозиторий:** `git@github.com:rus-lan/opencode-work-config.git`
**Версия opencode:** 1.18.7
**Модель по умолчанию:** `ecom-glm-52/glm-5.2`
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
├── aistats.js                # Копия плагина aistats (см. §8 — дубликат)
├── herdr-agent-state.js      # Копия плагина herdr (см. §8 — дубликат)
├── metrics.json              # Метрики последней сессии (gitignored)
├── agents/                   # 19 файлов описаний агентов (.md)
├── commands/                 # 6 команд (.md) + herdr-status.sh
├── skills/                   # 23 директории скиллов (SKILL.md + ресурсы)
├── plugins/                  # JS-плагины (aistats.js, herdr-agent-state.js)
├── rules/                    # 11 правил (.md) + README.md
├── scripts/                  # setup-opencode-config.sh
├── docs/                     # HERDR_METRICS_INTEGRATION.md
├── tests/                    # test-orchestrator-grillme.sh
├── prompts/                  # Пусто (только .gitignore — заглушка)
└── node_modules/             # npm-зависимости (gitignored)
```

---

## 📜 2. opencode.json — главный конфиг

Файл `opencode.json` (220 строк). Схема: `https://opencode.ai/config.json`.

### 2.1 Корневые поля

| Поле | Значение | Описание |
|------|----------|----------|
| `$schema` | `https://opencode.ai/config.json` | Ссылка на JSON-схему |
| `model` | `ecom-glm-52/glm-5.2` | Модель по умолчанию |
| `default_agent` | `orchestrator` | Агент, запускаемый по умолчанию |
| `small_model` | `ecom-qwen36-35b/qwen3.6-35b` | Лёгкая модель для нетворческих задач (тайтлы, компактизация) |
| `subagent_depth` | `2` | Максимальная вложенность сабагентов |

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

Агенты определяются **только** в `agents/*.md` (19 файлов). Конфигурация — в YAML frontmatter каждого файла. Нет блока `agent` в `opencode.json`.

### 3.1 Primary-агенты

| Агент | Модель | Steps | Color | Temp | Роль |
|-------|--------|-------|-------|------|------|
| **orchestrator** | `ecom-glm-52/glm-5.2` | 30 | `#FF5733` | 0.15 | Оркестратор — только спавнит сабагентов |
| **build** | `ecom-deepseek4-flash/deepseek-v4-flash` | 50 | `success` | 0.15 | Исполнитель — пишет код, запускает команды |
| **plan** | `ecom-deepseek4-flash/deepseek-v4-flash` | 30 | `info` | — | Планировщик — read-only анализ и план-ревью |

#### Orchestrator (`agents/orchestrator.md`)
- **Роль:** Диспетчер — распределяет задачи между сабагентами. НИЧЕГО не делает сам.
- **Модель:** `ecom-glm-52/glm-5.2`, temperature 0.15
- **Permissions:** `task=allow`, `skill=allow`, `todowrite=allow`, `question=allow`, всё остальное `deny` (read/edit/write/bash/glob/grep = deny)
- **Запуск:** Автоматически (агент по умолчанию)

#### Build (`agents/build.md`)
- **Роль:** Исполнитель с полным доступом — пишет код, запускает команды, редактирует файлы, спавнит сабагентов
- **Модель:** `ecom-deepseek4-flash/deepseek-v4-flash`, temperature 0.15
- **Permissions:** Всё `allow` (task, skill, read, write, edit, bash, glob, grep, webfetch, websearch, question)
- **Запуск:** `/build <задача>` или через оркестратора

#### Plan (`agents/plan.md`)
- **Роль:** Планировщик и ревьюер — read-only анализ кода, создание планов, архитектурное ревью. НЕ пишет код.
- **Модель:** `ecom-deepseek4-flash/deepseek-v4-flash`
- **Permissions:** `read=allow`, `glob=allow`, `grep=allow`, `question=allow`, `bash=ask`, `edit=deny`, `write=deny`, `task=deny`

### 3.2 Subagents

| # | Агент | Модель | Hidden | Роль | Ключевые permissions |
|---|-------|--------|--------|------|---------------------|
| 1 | `explore` | `ecom-qwen35-122b-no-think/qwen3.5-122b` | — | Быстрое исследование кодовой базы (read-only) | read/glob/grep/bash=allow, write/edit/task=deny |
| 2 | `project-mapper` | `ecom-qwen36-35b-no-think/qwen3.6-35b` | — | Построение карты проекта | read/glob/grep/bash=allow, write/edit/task=deny |
| 3 | `desearch-researcher` | `ecom-glm-52/glm-5.2` | — | Глубокий веб-ресёрч | read/write/edit/glob/grep/bash/websearch/webfetch=allow |
| 4 | `desearch-synthesizer` | `ecom-glm-52/glm-5.2` | — | Синтез ресёрч-отчётов | read/write/edit/glob/grep/bash/websearch=allow, webfetch=deny |
| 5 | `react-dev` | `ecom-qwen36-35b/qwen3.6-35b` | — | React/TS разработка | read/write/edit/glob/grep/bash=allow, task=deny |
| 6 | `go-dev` | `ecom-qwen36-35b/qwen3.6-35b` | — | Go backend разработка | read/write/edit/glob/grep/bash=allow, task=deny |
| 7 | `rust-dev` | `ecom-qwen36-35b/qwen3.6-35b` | — | Rust разработка | read/write/edit/glob/grep/bash/task=allow |
| 8 | `seo-writer` | `ecom-qwen35-122b/qwen3.5-122b` | — | SEO-контент (read-only, через task) | read/glob/grep/task/webfetch=allow, write/edit=deny, bash=ask |
| 9 | `reviewer` | `ecom-deepseek4-flash/deepseek-v4-flash` | ✅ hidden | Общий code review (standards + spec) | read/write/edit/glob/grep=allow, bash/task=deny |
| 10 | `reviewer-standards` | `ecom-deepseek4-flash/deepseek-v4-flash` | ✅ hidden | Ревью кодстайла и конвенций | read/glob/grep=allow, edit/write/bash/task=deny |
| 11 | `reviewer-spec` | `ecom-deepseek4-flash/deepseek-v4-flash` | ✅ hidden | Ревью соответствия спецификации | read/glob/grep=allow, edit/write/bash/task=deny |
| 12 | `reviewer-arch` | `ecom-deepseek4-flash/deepseek-v4-flash` | ✅ hidden | Архитектурное ревью | read/glob/grep=allow, edit/write/bash/task=deny |
| 13 | `test-agent` | `ecom-qwen36-35b/qwen3.6-35b` | — | Запуск тестов и отчёт | read/glob/grep/bash=allow, write/edit/task=deny |
| 14 | `security-check` | `ecom-deepseek4-flash/deepseek-v4-flash` | — | Аудит security/reliability/simplicity | read/glob/grep/bash=allow, write/edit/task=deny |
| 15 | `soc-check` | `ecom-qwen35-122b/qwen3.5-122b` | — | Проверка SOC/контрактов/покрытия | read/glob/grep/bash=allow, write/edit/task=deny |
| 16 | `ui-designer` | `ecom-deepseek4-flash/deepseek-v4-flash` | — | UI/UX дизайн (только спецификации) | read/write/edit/glob/grep=allow, bash/task=deny |

> **Hidden-агенты** (`hidden: true` в frontmatter) — не появляются в списке доступных агентов UI, но могут вызываться оркестратором через `task()`.

### Модели по агентам — сводка

| Модель | Агенты |
|--------|--------|
| `ecom-glm-52/glm-5.2` | orchestrator, desearch-researcher, desearch-synthesizer |
| `ecom-deepseek4-flash/deepseek-v4-flash` | build, plan, reviewer, reviewer-standards, reviewer-spec, reviewer-arch, security-check, ui-designer |
| `ecom-qwen36-35b/qwen3.6-35b` | react-dev, go-dev, rust-dev, test-agent |
| `ecom-qwen35-122b/qwen3.5-122b` | seo-writer, soc-check |
| `ecom-qwen35-122b-no-think/qwen3.5-122b` | explore |
| `ecom-qwen36-35b-no-think/qwen3.6-35b` | project-mapper |

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
| `file-diff` | Сравнение двух файлов с выводом различий в формате unified diff |
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

2 MCP-сервера в `opencode.json` → секция `mcp`:

| Сервер | Тип | Команда | Назначение |
|--------|-----|---------|------------|
| `aistats` | local | `aistats mcp` | Сбор метрик токенов, стоимости, рекомендации по эффективности |
| `playwright` | local | `npx @playwright/mcp@latest --executable-path ${HOME}/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome --headless --no-sandbox --isolated` | E2E тестирование (headless Chromium) |

Playwright MCP дополнительно настраивает environment: `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64`.

### aistats MCP — возможности
- `aistats_aistats_projects` — список проектов с метриками (sessions, turns, time, tokens, cost)
- `aistats_aistats_report` — отчёт по продуктивности (tokens, cost, time, phase breakdown)
- `aistats_aistats_recommendations` — ранжированные рекомендации по эффективности

---

## 🔌 8. Плагины

2 JS-плагина. В `opencode.json` **нет** секции `plugin` — плагины авто-обнаруживаются opencode из директории `plugins/`.

> **Дубликат:** файлы `aistats.js` и `herdr-agent-state.js` существуют **одновременно** в корне конфига и в `plugins/`. См. §16 (Известные проблемы).

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

7 провайдеров в `opencode.json` → секция `provider`:

| Провайдер | Модель | Context | Output | API Key Env | npm-пакет | Base URL |
|-----------|--------|---------|--------|-------------|-----------|----------|
| `zai-coding-plan` | GLM-5.2 | 1M | 131072 | — (подписка Z.AI) | — (built-in) | `https://api.z.ai/api/coding/paas/v4` |
| `ecom-glm-52` | glm-5.2 | 256K | 16K | `ECOM_GLM52_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |
| `ecom-qwen35-122b` | qwen3.5-122b | 128K | 8K | `ECOM_QWEN35_122b_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |
| `ecom-qwen36-35b` | qwen3.6-35b | 128K | 8K | `ECOM_QWEN36_35b_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |
| `ecom-qwen35-122b-no-think` | qwen3.5-122b (no-think) | 128K | 8K | `ECOM_QWEN35_122b_NO_THINK_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |
| `ecom-qwen36-35b-no-think` | qwen3.6-35b (no-think) | 128K | 8K | `ECOM_QWEN36_35b_NO_THINK_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |
| `ecom-deepseek4-flash` | deepseek-v4-flash | 256K | 16K | `ECOM_DEEPSEEK4_FLASH_TOKEN` | `@ai-sdk/openai-compatible` | `https://llm-core-olap.samokat.ru/v1` |

### Особенности провайдеров

**zai-coding-plan** — провайдер подписки Z.AI Coding Plan. Не использует `npm`-пакет (встроенный в opencode) и не требует `apiKey` (авторизация через `~/.local/share/opencode/auth.json`). Контекст 1M, output 131K — самый большой контекст. Используется моделью по умолчанию (`ecom-glm-52/glm-5.2` — НЕ путать, `model` в конфиге указывает на `ecom-glm-52`, но `zai-coding-plan` тоже предоставляет `glm-5.2`).

> **Внимание:** Поле `model` в `opencode.json` = `ecom-glm-52/glm-5.2` (провайдер `ecom-glm-52` — Samokat internal). Провайдер `zai-coding-plan` также предоставляет `glm-5.2` (Z.AI подписка), но не выбран как модель по умолчанию.

**ecom-* провайдеры** (6 шт.) — все используют один base URL `https://llm-core-olap.samokat.ru/v1` и npm-пакет `@ai-sdk/openai-compatible`. Каждый настроен с:
- `timeout: 120000` (120с на полный запрос)
- `chunkTimeout: 60000` (60с между SSE чанками)
- `headerTimeout: 30000` (30с на получение заголовков)
- `setCacheKey: true` (промпт-кэширование для экономии токенов)

**Rate limits** (в `limit` блоке модели):
- `deepseek-v4-flash`: hourly 50K, daily 200K, weekly 1M токенов
- `glm-5.2` (ecom-glm-52): hourly 50K, daily 200K, weekly 1M токенов
- `qwen3.5-122b`: effort `current: high`, `limit: max`

**No-think провайдеры** (`ecom-qwen35-122b-no-think`, `ecom-qwen36-35b-no-think`) — алиасы тех же моделей с отключённым thinking-режимом. Используются агентами `explore` и `project-mapper` для быстрых нетворческих задач.

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
| `scripts/setup-opencode-config.sh` | 426 | Автоматическая установка конфигурации на новом устройстве (Linux/macOS): определение ОС, установка opencode, клон/pull репо, npm install, создание `.env`, добавление `~/.local/bin` в PATH |
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

## 🧪 12. Тесты

### test-orchestrator-grillme.sh (`tests/test-orchestrator-grillme.sh`)
Test suite для проверки конфигурации orchestrator + grill-me интеграции (153 строки). 4 тест-кейса:
1. Orchestrator конфигурация
2. Grill-me конфигурация
3. Интеграция
4. Sanity checks

Запуск:
```bash
bash ~/.config/opencode/tests/test-orchestrator-grillme.sh
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
# Qwen models
ECOM_QWEN35_122b_TOKEN=
ECOM_QWEN36_35b_TOKEN=
ECOM_QWEN35_122b_NO_THINK_TOKEN=
ECOM_QWEN36_35b_NO_THINK_TOKEN=

# DeepSeek models
ECOM_DEEPSEEK4_FLASH_TOKEN=

# Other models
ECOM_GIGA3_10b_TOKEN=
```

> ⚠️ См. §16 — `.env.example` не содержит `ECOM_GLM52_TOKEN`, нужный провайдеру `ecom-glm-52`, и содержит устаревший `ECOM_GIGA3_10b_TOKEN`, не используемый ни одним провайдером в `opencode.json`.

---

## 🚀 14. Установка на новом устройстве

### Автоматическая установка

```bash
bash ~/.config/opencode/scripts/setup-opencode-config.sh
```

Скрипт автоматически:
1. Определит ОС (Linux/macOS)
2. Установит opencode если не установлен
3. Склонирует/pull репозиторий конфига в `~/.config/opencode`
4. Установит npm-зависимости
5. Создаст `.env` из `.env.example` (если нет)
6. Добавит `~/.local/bin` в PATH (если нет)
7. Проверит что opencode работает

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
opencode --version    # 1.18.7
opencode run "Hello"
```

### API-токены

| Переменная | Провайдер | Где взять |
|-----------|-----------|-----------|
| `ECOM_QWEN35_122b_TOKEN` | ecom-qwen35-122b | Инфраструктура Samokat (llm-core-olap) |
| `ECOM_QWEN36_35b_TOKEN` | ecom-qwen36-35b | Инфраструктура Samokat (llm-core-olap) |
| `ECOM_QWEN35_122b_NO_THINK_TOKEN` | ecom-qwen35-122b-no-think | Инфраструктура Samokat (llm-core-olap) |
| `ECOM_QWEN36_35b_NO_THINK_TOKEN` | ecom-qwen36-35b-no-think | Инфраструктура Samokat (llm-core-olap) |
| `ECOM_DEEPSEEK4_FLASH_TOKEN` | ecom-deepseek4-flash | Инфраструктура Samokat (llm-core-olap) |
| `ECOM_GLM52_TOKEN` | ecom-glm-52 | Инфраструктура Samokat (llm-core-olap) — **нет в .env.example** |
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

### 16.1 .env.example не синхронизирован с opencode.json
- **Отсутствует** `ECOM_GLM52_TOKEN` — нужен провайдеру `ecom-glm-52` (модель `glm-5.2`, используется агентами orchestrator, desearch-researcher, desearch-synthesizer). Без этого токена эти агенты не смогут работать через `ecom-glm-52`.
- **Присутствует** `ECOM_GIGA3_10b_TOKEN` — не используется ни одним провайдером в `opencode.json`. В старой документации и README упоминался провайдер `ecom-giga3-10b` (модель giga3-10b), но в текущем `opencode.json` он **отсутствует**.

### 16.2 Дубликаты плагинов
Файлы `aistats.js` и `herdr-agent-state.js` существуют **одновременно** в двух местах:
- Корень: `~/.config/opencode/aistats.js`, `~/.config/opencode/herdr-agent-state.js`
- Каталог плагинов: `~/.config/opencode/plugins/aistats.js`, `~/.config/opencode/plugins/herdr-agent-state.js`

В `opencode.json` нет секции `plugin`. Назначение корневых копий неясно — возможно, legacy. Рекомендуется удалить дубликаты и оставить только `plugins/`.

### 16.3 rules/README.md считает неправильно
README заявляет «10 правил» и индекс-таблица содержит 10 строк, но фактически в `rules/` лежит **11** `.md`-файлов правил (в индексе не учтён `git-commit-push`). Старая CONFIG_DOCUMENTATION.md в одном месте писала «12 правил», в другом «11».

### 16.4 README.md содержит устаревшие данные
- Бейдж «agents-23» — фактически 19 agent-файлов (3 primary + 16 subagents).
- Бейдж «skills-22» — фактически 23 скилла в `skills/`.
- Бейдж «model-qwen3.5--122b» — фактически модель по умолчанию `glm-5.2`.
- В таблице сабагентов указаны `project-mapper` → giga3-10b и `test-agent` → giga3-10b — фактически `project-mapper` использует `ecom-qwen36-35b-no-think/qwen3.6-35b`, `test-agent` — `ecom-qwen36-35b/qwen3.6-35b`.
- В таблице провайдеров указан `ecom-giga3-10b` — отсутствует в `opencode.json`.
- Раздел «Команды (6)» перечисляет 6 команд, но не упоминает `/get-session-metrics`.

### 16.5 CLAUDE.md отсутствует
Старая CONFIG_DOCUMENTATION.md (§8) упоминала `CLAUDE.md` — «Глобальные правила поведения агента (180 строк)». Файл **не существует** в текущем каталоге конфигурации. Вероятно, удалён или перенесён.

### 16.6 Каталог prompts/ пуст
Содержит только `.gitignore`. Назначение неясно — возможно, заглушка для будущих промптов.

### 16.7 seo-writer — subagent, не primary
Старая документация и README перечисляют `seo-writer` как primary-агента. Фактически в frontmatter `agents/seo-writer.md` указано `mode: subagent`.

### 16.8 Hidden-агенты не документированы
Агенты `reviewer`, `reviewer-standards`, `reviewer-spec`, `reviewer-arch` имеют `hidden: true` в frontmatter — не появляются в UI списке. Старая документация не упоминала этот атрибут.

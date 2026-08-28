# ⚡ Opencode Work Configuration

![Version](https://img.shields.io/badge/version-2.0-blue) ![Model](https://img.shields.io/badge/model-deepseek--v4--flash-green) ![Agents](https://img.shields.io/badge/agents-24-orange) ![Skills](https://img.shields.io/badge/skills-23-purple) ![OpenCode](https://img.shields.io/badge/opencode-1.18.16-red)

Готовая конфигурация opencode с 3 primary агентами, 21 сабагентом, полным CI-воркфлоу из 7 этапов и 23 скиллами.

## 🚀 Быстрая установка

```bash
# Клонировать конфиг
git clone git@github.com:rus-lan/opencode-work-config.git ~/.config/opencode

# Установить зависимости
cd ~/.config/opencode && npm install

# Создать .env с API токенами (см. .env.example)
cp .env.example .env
# Отредактировать .env — вставить токены для каждой модели

# Запустить opencode
opencode
```

> **Важно:** Конфигурация использует 3 провайдера (ecom, ecom-exp, zai-coding-plan) с моделями qwen3.8-27b, qwen3.8-27b-no-think, deepseek-v4-flash и экспериментальной glm-5.2. Модель по умолчанию — `ecom/deepseek-v4-flash`. Все провайдеры используют **2 общих токена** — `ECOM_LLM_TOKEN` и `ECOM_LLM_EXP_TOKEN` (без per-model токенов). Убедитесь что ключи указаны в `.env`.

## 🏗 Архитектура

### Primary Agents

| Агент | Модель | Роль |
|-------|--------|------|
| `@orchestrator` | deepseek-v4-flash | 🧠 Оркестратор — ничего не делает сам, только спавнит сабагентов |
| `@build` | deepseek-v4-flash | 🔧 Исполнитель с полным доступом (пишет код, запускает команды) |
| `@plan` | deepseek-v4-flash | 📋 Планирование и ревью (read-only, bash=ask) |

### Сабагенты (21)

| Агент | Модель | Роль |
|-------|--------|------|
| `seo-writer` | qwen3.8-27b | ✍️ SEO-писатель (read-only, write=deny) |
| `explore` | qwen3.8-27b-no-think | 🔍 Поиск файлов и структуры (read-only) |
| `project-mapper` | qwen3.8-27b-no-think | 🗺 Построение карты проекта |
| `react-dev` | qwen3.8-27b | ⚛ React/TS разработка |
| `go-dev` | qwen3.8-27b | 🔵 Go backend разработка |
| `rust-dev` | qwen3.8-27b | 🦀 Rust разработка |
| `ui-designer` | deepseek-v4-flash | 🎨 UI/UX дизайн |
| `desearch-researcher` | deepseek-v4-flash | 🌐 Глубокий веб-ресёрч |
| `desearch-synthesizer` | deepseek-v4-flash | 📄 Синтез ресёрч-отчётов |
| `test-agent` | qwen3.8-27b-no-think | 🧪 Запуск тестов |
| `reviewer` *(hidden)* | deepseek-v4-flash | 👀 Code review |
| `reviewer-arch` *(hidden)* | deepseek-v4-flash | 🏛 Архитектурное ревью |
| `reviewer-spec` *(hidden)* | deepseek-v4-flash | 📐 Ревью по спецификации |
| `reviewer-standards` *(hidden)* | deepseek-v4-flash | 📏 Ревью по кодстайлам |
| `security-check` | deepseek-v4-flash | 🔒 Аудит безопасности |
| `soc-check` | deepseek-v4-flash | ✅ Проверка SOC/контрактов |
| `mcp-aistats` | qwen3.8-27b-no-think | 📊 Обёртка MCP aistats (метрики, изолированный контекст) |
| `mcp-confluence` | qwen3.8-27b-no-think | 📄 Обёртка MCP Confluence (read/write) |
| `mcp-jira` | qwen3.8-27b-no-think | 📋 Обёртка MCP Jira (read/write) |
| `mcp-adr-drawio` | qwen3.8-27b | 🖊 Обёртка MCP_adr_drawio (схемы ADR) |
| `mcp-playwright` | deepseek-v4-flash | 🎭 Обёртка MCP playwright (browser-автоматизация) |

### Workflow

При запуске `/start <задача>` через `@orchestrator` выполняется 7-этапный пайплайн:

```
  0: Project Map         → qwen3.8-27b
  1: Grill-me + Research  → deepseek-v4-flash (researcher × 2-3) + deepseek-v4-flash (synthesizer)
  2: Implementation       → react-dev / go-dev / rust-dev (qwen3.8-27b)
  3: Code Review          → reviewer-standards + reviewer-spec + reviewer-arch (deepseek-v4-flash)
  4: Testing              → test-agent (qwen3.8-27b)
  5: Security Check       → security-check (deepseek-v4-flash)
  6: SOC / Contracts      → soc-check (deepseek-v4-flash)
```

### Model Strategy

| Этап | Модель |
|------|--------|
| Project Map | qwen3.8-27b-no-think |
| Grill-me | deepseek-v4-flash |
| Research | deepseek-v4-flash |
| Synthesis | deepseek-v4-flash |
| Implementation | qwen3.8-27b |
| Code Review | deepseek-v4-flash |
| Testing | qwen3.8-27b-no-think |
| Security Check | deepseek-v4-flash |
| SOC Check | deepseek-v4-flash |
| Titles / Compaction | qwen3.8-27b (`small_model`) |

### 🔱 Глубокая вложенность сабагентов

`subagent_depth: 4` в `opencode.json`. Сабагенты, способные декомпозировать работу вглубь (`build`, `plan`, `react-dev`, `go-dev`, `rust-dev`, `explore`, `project-mapper`, `test-agent`), могут порождать собственных сабагентов. Каждый уровень держит собственный мини-контекст и возвращает наверх **только агрегированный результат** — поэтому глубокая декомпозиция не раздувает контекст основного агента.

Ревьюеры (`reviewer*`), `security-check`, `soc-check` и MCP-обёртки остаются `task: deny` — они читают/выполняют и не декомпозируют.

### 🧩 MCP-обёртки

Для каждого MCP-сервера создан сабагент-обёртка, который выполняет MCP-действия в изолированном контексте и возвращает только краткий результат:
`mcp-aistats`, `mcp-confluence`, `mcp-jira`, `mcp-adr-drawio`, `mcp-playwright`. Оркестратор (и build) делегируют обёрткам вместо прямых вызовов MCP-инструментов — это сокращает потребление основного окна.

### Провайдеры моделей

| Провайдер | Модель | Контекст | Output | Токен |
|-----------|--------|----------|--------|-------|
| `ecom` | deepseek-v4-flash | 256K | 16K | `ECOM_LLM_TOKEN` |
| `ecom` | qwen3.8-27b | 256K | 16K | `ECOM_LLM_TOKEN` |
| `ecom` | qwen3.8-27b-no-think | 128K | 8K | `ECOM_LLM_TOKEN` |
| `ecom-exp` | glm-5.2 *(экспериментальная)* | 256K | 16K | `ECOM_LLM_EXP_TOKEN` |
| `zai-coding-plan` | GLM-5.2 *(экспериментальная)* | 1M | 131072 | подписка Z.AI |

Фактически в `opencode.json` **3 провайдера** (ecom, ecom-exp, zai-coding-plan) и **2 общих токена** (`ECOM_LLM_TOKEN`, `ECOM_LLM_EXP_TOKEN`) — без per-model токенов, timeout и rate-limits.

### Модели провайдеров

- `qwen3.8-27b-no-think` (ecom) — вариант без thinking-режима (128K/8K). Используется для **простых/механических** задач без аналитики: `explore`, `project-mapper`, `test-agent` и все MCP-обёртки (кроме `mcp-playwright` и `mcp-adr-drawio`).
- `ecom-exp/glm-5.2` и `zai-coding-plan/glm-5.2` — **экспериментальные** модели. Используются **ТОЛЬКО опционально** с fallback-проверкой: в случае недоступности glm-5.2 использовать `ecom/deepseek-v4-flash`. По умолчанию **не задействованы ни в одном агенте**, и подключать их на постоянной основе запрещено.

## ⚙️ Версии opencode

| Расположение | Версия | В PATH |
|--------------|--------|--------|
| `~/.local/bin/opencode` | 1.18.16 | ✅ да |
| `~/.opencode/bin/opencode` | 1.18.23 | ❌ нет (вне PATH) |

Рекомендуется привести бинарники к единой версии (например, обновить `~/.local/bin/opencode` до 1.18.23 или удалить устаревший бинарник).

## 🛠 Skills (23)

| Skill | Описание |
|-------|----------|
| `bmad-check-implementation-readiness` | Проверка готовности к реализации |
| `bmad-create-epics` | Декомпозиция спека в эпики |
| `bmad-create-story` | Создание user story с AC |
| `bmad-dev-story` | Разработка истории: код + тесты + ревью |
| `bmad-impl` | BMAD-цикл: эпики → истории → ревью → Fable-гейт |
| `bmad-retrospective` | Ретроспектива спринта |
| `bmad-sprint-planning` | Планирование спринта |
| `caveman` | Ультра-краткий режим (lite/full/ultra) |
| `config-pull` | Пулл конфига из ~/claude-config |
| `context-metrics` | Мониторинг метрик контекста |
| `desearch` | Параллельный глубокий веб-ресёрч |
| `design` | UI дизайн из скриншотов и промптов |

| `full-workflow` | Полный 7-этапный workflow |
| `graphify` | Построение графа знаний кодовой базы |
| `grill-me` | Интерактивный допрос плана/решения |
| `impl-kickoff` | Валидация и запуск разработки |
| `implement` | Реализация задач по спецификации |
| `mapps` | Multi-repo workspace management |
| `project-pull` | Пулл правил/агентов в проект |
| `project-push` | Пуш правил/агентов из проекта |
| `unrobot` | Детекция AI-маркеров, 8 языков |
| `workspace-init` | Создание workspace-обёртки |

> **Примечание:** Дополнительные скиллы (ask-matt, code-review, tdd, research, triage и др.) доступны в `~/.agents/skills/`.

## ⌨ Команды (6)

| Команда | Описание |
|---------|----------|
| `/context` | 📊 Метрики контекста и лимиты |
| `/get-session-metrics` | 📈 Получение метрик сессии из aiStats |
| `/grill-me [тема]` | 🔥 Интерактивный допрос |
| `/herdr-status` | 📟 Статус сессии в Herdr UI |
| `/m` | 📋 Session metrics dashboard |
| `/mapps` | 📁 Multi-repo workspace |

Скиллы также доступны как команды: `/unrobot`, `/bmad-impl` и др.

## 🔌 MCP Серверы (7)

| MCP | Тип | Назначение |
|-----|-----|------------|
| `aistats` | local | 📊 Метрики токенов, стоимости и рекомендации |
| `playwright` | local | 🎭 E2E тестирование (headless Chromium) |
| `Confluence_Samokat_Read_Only` | remote | 📄 Confluence чтение (требует `CONFLUENCE_TOKEN`) |
| `Confluence_Samokat_Write` | remote | 📝 Confluence запись (требует `CONFLUENCE_TOKEN`) |
| `Jira_Samokat_Read_Only` | remote | 📋 Jira чтение (требует `JIRA_TOKEN`) |
| `Jira_Samokat_Write` | remote | ✍️ Jira запись (требует `JIRA_TOKEN`) |
| `MCP_adr_drawio` | remote | 🖊 ADR drawio |

## 🔧 Плагины (2)

| Плагин | Назначение |
|--------|------------|
| `aistats.js` | Сбор метрик токенов, стоимости, длительности сессий |
| `herdr-agent-state.js` | Live session metrics в Herdr UI (модель, статус, длительность, токены, стоимость, сабагенты) |

## 🔗 Интеграции

### Herdr

[Herdr](https://herdr.ai) — веб-интерфейс для мониторинга сессий opencode.

- `/herdr-status` — статус текущей сессии (модель, токены, стоимость, длительность)
- Плагин `herdr-agent-state.js` передаёт live-метрики каждого агента
- Цветовая маркировка: 🟢 активен, 🟡 ожидает, 🔴 ошибка, ⚪ неактивен

### aiStats

Локальный MCP-сервер для сбора и анализа метрик.

- `/get-session-metrics` — метрики текущей сессии
- `aistats projects` — список проектов с метриками
- `aistats report` — отчёт по продуктивности (tokens, cost, time, phase breakdown)
- `aistats recommendations` — рекомендации по оптимизации

## ⚙ Правила (Rules)

`rules/` — 11 правил для сабагентов: frontend-components, frontend-hooks, frontend-theme, frontend-zustand, go-backend, go-observability, rust-errors, tauri-bridge, opencode-implementer, bmad-impl-story-cycle, git-commit-push.

Автоматически загружаются через `instructions: ["rules/*.md"]`.

## 🛡 Honesty Protocol

- Никогда не гадать/выдумывать сигнатуры API
- "I don't know" предпочтительнее предположений
- Ссылаться на конкретные файлы и строки кода

## 🔒 Защита

- `guard.sh` — блокировка опасных compound-команд (rm, force-push, install)
- `pre-commit.sh` — валидация перед коммитом
- Honesty protocol — запрет на гадание и выдумывание

---

📖 **Полная документация:** [CONFIG_DOCUMENTATION.md](./CONFIG_DOCUMENTATION.md) — 897 строк, все детали конфигурации, каждого агента, плагина, команды и провайдера.
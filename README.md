# ⚡ Opencode Work Configuration

![Version](https://img.shields.io/badge/version-2.0-blue) ![Model](https://img.shields.io/badge/model-glm--5.2-green) ![Agents](https://img.shields.io/badge/agents-19-orange) ![Skills](https://img.shields.io/badge/skills-23-purple) ![OpenCode](https://img.shields.io/badge/opencode-1.18.7-red)

Готовая конфигурация opencode с 3 primary агентами, 16 сабагентами, полным CI-воркфлоу из 7 этапов и 23 скиллами.

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

> **Важно:** Конфигурация использует несколько провайдеров (qwen3.5-122b, qwen3.6-35b, deepseek-v4-flash, glm-5.2). Убедитесь что все API-ключи указаны в `.env`.

## 🏗 Архитектура

### Primary Agents

| Агент | Модель | Роль |
|-------|--------|------|
| `@orchestrator` | glm-5.2 | 🧠 Оркестратор — ничего не делает сам, только спавнит сабагентов |
| `@build` | deepseek-v4-flash | 🔧 Исполнитель с полным доступом (пишет код, запускает команды) |
| `@plan` | deepseek-v4-flash | 📋 Планирование и ревью (read-only, bash=ask) |

### Сабагенты (16)

| Агент | Модель | Роль |
|-------|--------|------|
| `seo-writer` | qwen3.5-122b | ✍️ SEO-писатель (read-only, write=deny) |
| `explore` | qwen3.5-122b (no-think) | 🔍 Поиск файлов и структуры (read-only) |
| `project-mapper` | qwen3.6-35b (no-think) | 🗺 Построение карты проекта |
| `react-dev` | qwen3.6-35b | ⚛ React/TS разработка |
| `go-dev` | qwen3.6-35b | 🔵 Go backend разработка |
| `rust-dev` | qwen3.6-35b | 🦀 Rust разработка |
| `ui-designer` | deepseek-v4-flash | 🎨 UI/UX дизайн |
| `desearch-researcher` | glm-5.2 | 🌐 Глубокий веб-ресёрч |
| `desearch-synthesizer` | glm-5.2 | 📄 Синтез ресёрч-отчётов |
| `test-agent` | qwen3.6-35b | 🧪 Запуск тестов |
| `reviewer` *(hidden)* | deepseek-v4-flash | 👀 Code review |
| `reviewer-arch` *(hidden)* | deepseek-v4-flash | 🏛 Архитектурное ревью |
| `reviewer-spec` *(hidden)* | deepseek-v4-flash | 📐 Ревью по спецификации |
| `reviewer-standards` *(hidden)* | deepseek-v4-flash | 📏 Ревью по кодстайлам |
| `security-check` | deepseek-v4-flash | 🔒 Аудит безопасности |
| `soc-check` | qwen3.5-122b | ✅ Проверка SOC/контрактов |

### Workflow

При запуске `/start <задача>` через `@orchestrator` выполняется 7-этапный пайплайн:

```
  0: Project Map         → qwen3.6-35b (no-think)
  1: Grill-me + Research  → glm-5.2 × 2-3 + glm-5.2 (synthesizer)
  2: Implementation       → react-dev / go-dev / rust-dev (qwen3.6-35b)
  3: Code Review          → reviewer-standards + reviewer-spec + reviewer-arch (deepseek-v4-flash)
  4: Testing              → test-agent (qwen3.6-35b)
  5: Security Check       → security-check (deepseek-v4-flash)
  6: SOC / Contracts      → soc-check (qwen3.5-122b)
```

### Model Strategy

| Этап | Модель |
|------|--------|
| Project Map | qwen3.6-35b (no-think) |
| Grill-me | qwen3.5-122b |
| Research | glm-5.2 |
| Synthesis | glm-5.2 |
| Implementation | qwen3.6-35b |
| Code Review | deepseek-v4-flash |
| Testing | qwen3.6-35b |
| Security Check | deepseek-v4-flash |
| SOC Check | qwen3.5-122b |
| Titles / Compaction | qwen3.6-35b (`small_model`) |

### Провайдеры моделей

| Провайдер | Модель | Контекст | Output |
|-----------|--------|----------|--------|
| `zai-coding-plan` | glm-5.2 | 1M | 128K |
| `ecom-qwen35-122b` | qwen3.5-122b | 128K | 8K |
| `ecom-qwen36-35b` | qwen3.6-35b | 128K | 8K |
| `ecom-deepseek4-flash` | deepseek-v4-flash | 256K | 16K |
| `ecom-qwen35-122b-no-think` | qwen3.5-122b (no-think) | 128K | 8K |
| `ecom-qwen36-35b-no-think` | qwen3.6-35b (no-think) | 128K | 8K |
| `ecom-glm-52` | glm-5.2 | 256K | 16K |

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
| `file-diff` | Сравнение двух файлов (unified diff) |
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

## 🔌 MCP Серверы (2)

| MCP | Тип | Назначение |
|-----|-----|------------|
| `aistats` | local | 📊 Метрики токенов, стоимости и рекомендации |
| `playwright` | local | 🎭 E2E тестирование (headless Chromium) |

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

## 📜 Scripts

| Скрипт | Назначение |
|--------|------------|
| `scripts/setup-opencode-config.sh` | Автоматическая установка конфига в `~/.config/opencode` |

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
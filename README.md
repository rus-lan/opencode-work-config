# ⚡ Opencode Work Configuration

![Version](https://img.shields.io/badge/version-2.0-blue) ![Model](https://img.shields.io/badge/model-qwen3.5--122b-green) ![Agents](https://img.shields.io/badge/agents-21-orange) ![Skills](https://img.shields.io/badge/skills-21-purple) ![OpenCode](https://img.shields.io/badge/opencode-1.18.7-red)

Готовая конфигурация opencode с тремя primary агентами, 15 сабагентами, оркестратором, полным CI-воркфлоу из 7 этапов и 21 скиллом.

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

> **Важно:** Конфигурация использует несколько провайдеров (qwen3.5-122b, qwen3.6-35b, deepseek-v4-flash, deepseek-v4-flash:max, giga3-10b). Убедитесь что все API-ключи указаны в `.env`.

## 🏗 Архитектура

### Primary Agents

| Агент | Модель | Роль |
|-------|--------|------|
| `@orchestrator` | qwen3.5-122b (max effort) | 🧠 Оркестратор — ничего не делает сам, только спавнит сабагентов |
| `@build` | qwen3.5-122b | 🔧 Исполнитель с полным доступом (пишет код, запускает команды) |
| `@plan` | qwen3.5-122b | 📋 Планирование и ревью (read-only, bash=ask) |
| `seo-writer` | qwen3.5-122b | ✍️ SEO-писатель (read-only, write=deny) |

### Сабагенты (15)

| Агент | Модель | Роль |
|-------|--------|------|
| `explore` | qwen3.6-35b | 🔍 Поиск файлов и структуры (read-only) |
| `project-mapper` | giga3-10b | 🗺 Построение карты проекта |
| `react-dev` | qwen3.6-35b | ⚛ React/TS разработка |
| `go-dev` | qwen3.6-35b | 🔵 Go backend разработка |
| `rust-dev` | qwen3.6-35b | 🦀 Rust разработка |
| `ui-designer` | qwen3.6-35b | 🎨 UI/UX дизайн |
| `desearch-researcher` | deepseek-v4-flash:max | 🌐 Глубокий веб-ресёрч |
| `desearch-synthesizer` | qwen3.6-35b | 📄 Синтез ресёрч-отчётов |
| `test-agent` | giga3-10b | 🧪 Запуск тестов (fallback: qwen3.6-35b) |
| `reviewer` | qwen3.5-122b | 👀 Code review |
| `reviewer-arch` | qwen3.5-122b | 🏛 Архитектурное ревью |
| `reviewer-spec` | qwen3.5-122b | 📐 Ревью по спецификации |
| `reviewer-standards` | qwen3.5-122b | 📏 Ревью по кодстайлу |
| `security-check` | qwen3.5-122b | 🔒 Аудит безопасности (fallback: qwen3.6-35b) |
| `soc-check` | qwen3.5-122b | ✅ Проверка SOC/контрактов (fallback: qwen3.6-35b) |

### Workflow

При запуске `/start <задача>` через `@orchestrator` выполняется 7-этапный пайплайн:

```
  0: Project Map         → giga3-10b
  1: Grill-me + Research  → deepseek-v4-flash:max × 2-3 + qwen3.6-35b (synthesizer)
  2: Implementation       → react-dev / go-dev / rust-dev (qwen3.6-35b)
  3: Code Review          → reviewer-standards + reviewer-spec + reviewer-arch (qwen3.5-122b)
  4: Testing              → test-agent (giga3-10b / qwen3.6-35b)
  5: Security Check       → security-check (qwen3.5-122b)
  6: SOC / Contracts      → soc-check (qwen3.5-122b)
```

### Model Strategy

| Этап | Модель |
|------|--------|
| Project Map | giga3-10b |
| Grill-me | qwen3.5-122b |
| Research | deepseek-v4-flash:max |
| Synthesis | qwen3.6-35b |
| Implementation | qwen3.6-35b |
| Code Review | qwen3.5-122b |
| Testing | giga3-10b / qwen3.6-35b |
| Security Check | qwen3.5-122b |
| SOC Check | qwen3.5-122b |
| Titles / Compaction | qwen3.6-35b (`small_model`) |

### Провайдеры моделей

| Провайдер | Модель | Контекст | Output |
|-----------|--------|----------|--------|
| `ecom-qwen35-122b` | qwen3.5-122b | 128K | 8K |
| `ecom-qwen36-35b` | qwen3.6-35b | 128K | 8K |
| `ecom-deepseek4-flash-max` | deepseek-v4-flash:max | 256K | 16K |
| `ecom-deepseek4-flash` | deepseek-v4-flash | 256K | 16K |
| `ecom-qwen35-122b-no-think` | qwen3.5-122b (no-think) | 128K | 8K |
| `ecom-qwen36-35b-no-think` | qwen3.6-35b (no-think) | 128K | 8K |
| `ecom-giga3-10b` | giga3-10b | 64K | 4K |

## 🛠 Skills (21)

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

## 🔌 MCP Серверы (3)

| MCP | Тип | Назначение |
|-----|-----|------------|
| `aistats` | local | 📊 Метрики токенов, стоимости и рекомендации |
| `playwright` | local | 🎭 E2E тестирование (headless Chromium) |
| `context7` | remote | 📚 Проверка API библиотек и документации |

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

`rules/` — 11 правил для сабагентов: frontend-components, frontend-hooks, frontend-theme, frontend-zustand, go-backend, rust-errors, tauri-bridge, context7, opencode-implementer, bmad-impl-story-cycle.

Автоматически загружаются через `instructions: ["rules/*.md"]`.

## 🛡 Honesty Protocol

- Никогда не гадать/выдумывать сигнатуры API
- "I don't know" предпочтительнее предположений
- Проверять документацию через context7 MCP
- Ссылаться на конкретные файлы и строки кода

## 🔒 Защита

- `guard.sh` — блокировка опасных compound-команд (rm, force-push, install)
- `pre-commit.sh` — валидация перед коммитом
- Honesty protocol — запрет на гадание и выдумывание

---

📖 **Полная документация:** [CONFIG_DOCUMENTATION.md](./CONFIG_DOCUMENTATION.md) — 897 строк, все детали конфигурации, каждого агента, плагина, команды и провайдера.
# Opencode Work Configuration

Полноценная конфигурация opencode с оркестратором, сабагентами, скиллами и полным workflow.

## Быстрая установка

```bash
git clone git@github.com:rus-lan/opencode-work-config.git ~/.config/opencode
cd ~/.config/opencode && npm install
# Создать .env с API токенами
opencode
```

## Архитектура

### Primary Agents

| Агент | Модель | Роль |
|-------|--------|------|
| `@orchestrator` | qwen3.5-122b | Оркестратор — ничего не делает сам, только спавнит сабагентов |
| `@build` | qwen3.5-122b | Исполнитель с полным доступом (пишет код, запускает) |
| `@plan` | qwen3.5-122b | Планирование и ревью (read-only) |

### Сабагенты (15)

| Агент | Модель | Роль |
|-------|--------|------|
| `explore` | qwen3.6-35b | Поиск файлов и структуры (read-only) |
| `project-mapper` | giga3-10b | Построение карты проекта |
| `react-dev` | qwen3.6-35b | React/TS разработка |
| `go-dev` | qwen3.6-35b | Go backend разработка |
| `rust-dev` | qwen3.6-35b | Rust разработка |
| `ui-designer` | qwen3.6-35b | UI/UX дизайн |
| `desearch-researcher` | deepseek-v4-flash:max | Глубокий веб-ресёрч |
| `desearch-synthesizer` | qwen3.6-35b | Синтез ресёрч-отчётов |
| `test-agent` | giga3-10b | Запуск тестов |
| `reviewer` | qwen3.5-122b | Code review |
| `reviewer-arch` | qwen3.5-122b | Архитектурное ревью |
| `reviewer-spec` | qwen3.5-122b | Ревью по спецификации |
| `reviewer-standards` | qwen3.5-122b | Ревью по кодстайлу |
| `security-check` | qwen3.6-35b | Аудит безопасности |
| `soc-check` | qwen3.6-35b | Проверка SOC/контрактов |

### Workflow (7 этапов)

При запуске `/start <задача>` через `@orchestrator`:

```
Этап 0: Project Map
Этап 1: Grill-me + Deep Research (desearch-researcher × 2-3 + desearch-synthesizer)
Этап 2: Implementation (react-dev / go-dev / rust-dev)
Этап 3: Code Review (reviewer-standards + reviewer-spec + reviewer-arch)
Этап 4: Testing (test-agent — unit + integration + e2e)
Этап 5: Security / Reliability / Simplicity Check
Этап 6: SOC / Contracts / Test Coverage Check
```

### MCP Серверы

| MCP | Тип | Назначение |
|-----|-----|------------|
| aistats | local | Метрики токенов и стоимости |
| playwright | local | E2E тестирование (headless chromium) |
| context7 | remote | Проверка API библиотек и документации |

### Правила (auto-loaded via instructions)

`rules/` — 11 правил для сабагетов: frontend-components, frontend-hooks, frontend-theme, frontend-zustand, go-backend, rust-errors, tauri-bridge, context7, opencode-implementer, bmad-impl-story-cycle

Автоматически загружаются в context через `instructions: ["rules/*.md"]`.

## Skills (14)

- `bmad-impl` — планирование больших задач через эпики/истории
- `caveman` — режим кратких ответов (lite/full/ultra)
- `desearch` — параллельный глубокий ресёрч
- `design` — UI дизайн из скриншотов и промптов
- `full-workflow` — полный 7-этапный workflow
- `graphify` — построение графа знаний кодовой базы
- `grill-me` — интерактивный допрос плана/решения
- `unrobot` — детекция и удаление AI-маркеров из текста (8 языков)
- `config-pull`, `project-pull`, `project-push` — синхронизация конфига
- `context-metrics` — мониторинг контекста
- `mapps` — multi-repo workspace
- `workspace-init` — создание workspace

## Plugins

- `aistats.js` — сбор метрик токенов и стоимости
- `herdr-agent-state.js` — live session metrics в Herdr UI

## Команды

| Команда | Описание |
|---------|----------|
| `/context` | Метрики контекста и лимиты |
| `/get-session-metrics` | Получение метрик сессии из aistats |
| `/grill-me [тема]` | Интерактивный допрос |
| `/herdr-status` | Статус сессии в Herdr |
| `/m` | Session metrics dashboard |
| `/mapps` | Multi-repo workspace |
| `/unrobot <file>` | Удалить AI-маркеры из текста |
| `/bmad-impl <task>` | Планирование реализации |

## Model Strategy

| Этап | Модель |
|------|--------|
| Project Map | giga3-10b |
| Grill-me | qwen3.5-122b |
| Research | deepseek-v4-flash:max |
| Implementation | qwen3.6-35b |
| Code Review | qwen3.5-122b |
| Testing | giga3-10b |
| Security Check | qwen3.5-122b |
| SOC Check | qwen3.5-122b |
| Titles / Compaction | qwen3.6-35b (small_model) |

## Honesty Protocol

Все агенты следуют правилам честности:
- Не гадать, не выдумывать сигнатуры API
- "I don't know" предпочтительнее предположений
- Проверять документацию через context7 MCP
- Ссылаться на конкретные файлы и строки кода

## Защита

- `guard.sh` — блокировка опасных compound-команд (rm, force-push, install)
- `pre-commit.sh` — валидация перед коммитом
- Honesty protocol — запрет на гадание и выдумывание
# Opencode Work Configuration

Рабочая конфигурация opencode с агентами, скиллами и полным workflow оркестрации.

## Быстрая установка

```bash
# 1. Клонировать конфигурацию
git clone git@github.com:rus-lan/opencode-work-config.git ~/.config/opencode

# 2. Установить переменные окружения
cp ~/.config/opencode/.env.example ~/.config/opencode/.env
# Отредактируйте .env с вашими API ключами

# 3. Установить зависимости
cd ~/.config/opencode && npm install

# 4. Готово!
opencode
```

## Основные агенты

| Агент | Модель | Назначение |
|-------|--------|------------|
| `@orchestrator` | qwen3.5-122b | **Строгий оркестратор.** Ничего не делает сам — только спавнит сабагентов |
| `@build` | qwen3.5-122b | Исполнитель с полным доступом (код, bash, тесты) |
| `@plan` | qwen3.5-122b | Планирование и план-ревью (read-only, edit deny) |

### Сабагенты

| Агент | Модель | Назначение |
|-------|--------|------------|
| `project-mapper` | qwen3.6-35b | Построение карты проекта (PROJECT_MAP.md) |
| `explore` | qwen3.6-35b | Поиск файлов, структуры, usages (read-only) |
| `react-dev` | qwen3.6-35b | React/TypeScript разработка |
| `go-dev` | qwen3.6-35b | Go backend разработка |
| `rust-dev` | qwen3.6-35b | Rust разработка |
| `reviewer-standards` | qwen3.5-122b | Code review по стандартам (read-only) |
| `reviewer-spec` | qwen3.5-122b | Code review по спецификации (read-only) |
| `reviewer-arch` | qwen3.5-122b | Архитектурное ревью (read-only) |
| `test-agent` | qwen3.6-35b | Запуск тестов (unit/integration/e2e) |
| `security-check` | qwen3.5-122b | Аудит безопасности/надёжности/простоты |
| `soc-check` | qwen3.5-122b | Проверка SOC/контрактов/тестового покрытия |
| `diagnosing-bugs` | qwen3.6-35b | Диагностика и исправление багов |
| `desearch-researcher` | deepseek-v4-flash:max | Глубокий веб-ресёрч |
| `desearch-synthesizer` | qwen3.6-35b | Синтез результатов ресёрча |
| `ui-designer` | qwen3.6-35b | UI/UX дизайн |

## Полный Workflow (7 этапов)

При запуске `/start <задача>` через `@orchestrator`:

```
Этап 0: Project Map — карта проекта (PROJECT_MAP.md)
Этап 1: Grill-me + Deep Research — допрос плана + параллельный ресёрч
Этап 2: Implementation — параллельная разработка (react/go/rust)
Этап 3: Code Review — 3 параллельных ревьюера (standards + spec + arch)
Этап 4: Testing — unit + integration + e2e тесты
Этап 5: Security / Reliability / Simplicity Check
Этап 6: SOC / Contracts / Test Coverage Check
```

**Золотое правило:** Оркестратор НИЧЕГО не делает сам. Каждый сабагент получает одну атомарную задачу.

## Команды

| Команда | Назначение |
|---------|-----------|
| `/start <задача>` | Полный 7-этапный workflow |
| `/workflow <задача>` | То же самое |
| `/build <задача>` | Без грилла/ресерча, сразу имплементация |
| `/grill-me <тема>` | Только интерактивный допрос |
| `/map` | Только карта проекта |
| `/safety-check` | Только проверка безопасности |
| `/soc-check` | Только проверка SOC/контрактов |
| `/caveman [уровень]` | Режим кратких ответов |
| `/m` | Метрики сессии |
| `/mapps` | Multi-repo workspace |

## Обновление

```bash
cd ~/.config/opencode && git pull && npm install
```

MIT
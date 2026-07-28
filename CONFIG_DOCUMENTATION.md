# ⚙️ Конфигурация Opencode — полная документация

**Репозиторий:** `git@github.com:rus-lan/opencode-work-config.git`
**Версия opencode:** 1.18.7
**Модель по умолчанию:** `ecom-qwen35-122b/qwen3.5-122b`
**Агент по умолчанию:** `orchestrator`

---

## 📋 Содержание

1. [🏗 Архитектура глобального воркфлоу](#-1-архитектура-глобального-воркфлоу)
2. [🤖 Агенты и сабагенты](#-2-агенты-и-сабагенты)
   - 2.1 [Три основных агента](#21-три-основных-агента-primary)
   - 2.2 [Сабагенты](#22-сабагенты-sub-agents)
   - 2.3 [Стратегия моделей по этапам](#23-стратегия-моделей-по-этапам)
3. [🛠 Skills (установленные)](#-3-skills-установленные)
3b. [📋 Правила (Rules)](#-3b-правила-rules)
4. [🔌 Плагины](#-4-плагины)
5. [⌨ Команды](#-5-команды)
6. [🌐 MCP Серверы](#-6-mcp-серверы)
6b. [🔒 Защита и безопасность](#-6b-защита-и-безопасность)
7. [🧩 Провайдеры моделей](#-7-провайдеры-моделей)
8. [📋 Расшифровка файлов конфигурации](#-8-расшифровка-файлов-конфигурации)
9. [🚀 Установка на новом устройстве](#-9-установка-на-новом-устройстве)
10. [🔄 Обновление конфигурации](#-10-обновление-конфигурации)
11. [🛠 Расширение конфигурации](#-11-расширение-конфигурации)

---

## 🏗 1. Архитектура глобального воркфлоу

Полный цикл разработки состоит из **7 этапов**. Оркестратор (`orchestrator`) строго следует золотому правилу: **НИЧЕГО не делает сам** — только спавнит сабагентов через `task()`.

```
/start <задача>  →  Полный 7-этапный workflow
```

### Этап 0: Карта проекта

**Что делает:** Построение карты проекта перед любой работой. Создаёт `PROJECT_MAP.md` в корне проекта.

**Запускаемый сабагент:** `project-mapper`
- Сканирует дерево файлов (исключая `.git/`, `node_modules/`, `dist/`)
- Определяет entry points (`package.json`, `go.mod`, `Cargo.toml`, `Dockerfile`, `main.ts`)
- Определяет стек технологий, тестовые фреймворки
- Сохраняет карту в `PROJECT_MAP.md`

**Модель:** qwen3.6-35b

**Условия пропуска:** Если `PROJECT_MAP.md` уже существует и сессия < 1 часа — можно пропустить.

**Ручной запуск:**
```
/map
```

### Этап 1: Grill-me + Deep Research

**Что делает:** Интерактивный допрос плана пользователем + параллельное веб-исследование.

**Подэтапы:**

1. **Grill-me** — загружается `skill("grill-me")`. Оркестратор только передаёт вопросы от skill пользователю и ответы обратно. Не ведёт диалог сам.
2. **Deep Research** — после грилла запускаются 2-3 `desearch-researcher` с разными углами исследования + 1 `research` для primary source investigation.
3. **Синтез** — результаты сохраняются в `.research/<topic>/`.

**Модели:**
- Grill-me: qwen3.5-122b
- Research: deepseek-v4-flash:max (основная), qwen3.6-35b (синтез)

**Ручной запуск:**
```
/grill-me <тема>
```

### Этап 2: Имплементация

**Что делает:** Декомпозиция задачи на атомарные подзадачи и параллельная разработка.

**Загружаемый skill:** `skill("implement")`

**Правила декомпозиции:**
- Одна задача = один файл (макс 2, если тесно связаны)
- Сабагент получает ТОЧНУЮ спецификацию: типы, сигнатуры, расположение
- Сабагент НЕ принимает архитектурных решений
- Сабагент НЕ выбирает, где разместить файл

**Запускаемые сабагенты:**
- React/TS → `react-dev` (qwen3.6-35b)
- Go → `go-dev` (qwen3.6-35b)
- Rust → `rust-dev` (qwen3.6-35b)
- Mixed → `general` (qwen3.6-35b)

**Ручной запуск:**
```
/build <задача>
```

### Этап 3: Ревью

**Что делает:** 3 параллельных ревью. Все findings возвращаются одним батчем.

**Запускаемые сабагенты (параллельно в одном message):**

| Ревьюер | Фокус | Модель |
|---------|-------|--------|
| `reviewer-standards` | Кодстайл, нейминг, конвенции | qwen3.5-122b |
| `reviewer-spec` | Соответствие требованиям | qwen3.5-122b |
| `reviewer-arch` | Архитектурная целостность | qwen3.5-122b |

**Процесс:**
1. Спавнить 3 параллельных ревьюера
2. Дождаться всех
3. Агрегировать findings
4. Если есть блокирующие issues — исправить через сабагентов-разработчиков
5. Максимум 2 раунда ревью на задачу

### Этап 4: Тестирование

**Что делает:** Параллельный запуск тестов. При падениях — диагностика и исправление.

**Запускаемый сабагент:** `test-agent` (qwen3.6-35b, fallback: qwen3.6-35b)

**Процесс:**
1. Запуск unit + integration + e2e тестов параллельно
2. Если тесты падают — `diagnosing-bugs` с конкретным списком упавших тестов
3. Исправление → перезапуск → повтор до полного прохождения

**Правила test-agent:**
- ❌ Не редактирует сорцы/тесты
- ❌ Не устанавливает зависимости
- ❌ Не исправляет баги
- ✅ Только запускает и отчитывается

### Этап 5: Security/Reliability/Simplicity Check

**Что делает:** Аудит безопасности, надёжности и простоты кода.

**Запускаемый сабагент:** `security-check` (qwen3.5-122b, fallback: qwen3.6-35b)

**Три оси проверки:**
1. **Security** — хардкод секретов, SQL injection, XSS, input validation, auth, CORS
2. **Reliability** — обработка ошибок, timeouts, retry, graceful shutdown, health checks
3. **Simplicity** — сложность кода, абстракции, размер функций/файлов

**Процесс:**
1. Спавнить `security-check` с задачей сканировать код
2. Если критические проблемы — исправить через сабагентов
3. Перезапустить проверку

**Ручной запуск:**
```
/safety-check
```

### Этап 6: SOC/Contracts/Tests Coverage Check

**Что делает:** Проверка Single Source of Truth, контрактов между слоями и тестового покрытия.

**Запускаемый сабагент:** `soc-check` (qwen3.5-122b, fallback: qwen3.6-35b)

**Три оси проверки:**
1. **SST** — дублирование логики, конфигов, типов, магических чисел
2. **Contracts** — API контракты frontend ↔ backend, типы TypeScript ↔ Go/Rust
3. **Test Coverage** — публичные функции без тестов, непротестированные error paths

**Ручной запуск:**
```
/soc-check
```

### Дополнительные возможности конфигурации

#### Авто-загрузка правил (instructions)
Все 11 правил из `rules/` автоматически загружаются в system prompt через `"instructions": ["rules/*.md"]`. Правила доступны всем агентам без явного вызова `skill()`.

#### Лёгкая модель (small_model)
`"small_model": "ecom-qwen36-35b/qwen3.6-35b"` — используется для нетворческих задач (генерация тайтлов, компактизация), экономя квоты qwen3.5-122b.

#### Управление контекстом (compaction)
```json
{
  "auto": true,
  "reserved": 8000,
  "tail_turns": 3,
  "prune": true
}
```
Автоматическая компактизация при заполнении контекста, резерв 8K токенов, сохранение 3 последних ходов, обрезка старых tool output.

#### Игнорирование watcher
```json
{
  "ignore": ["node_modules/**", ".git/**", ".bmad/**", ".research/**", "*.log", "dist/**"]
}
```
Watcher не реагирует на изменения в шумных директориях.

#### Лимиты tool output
```json
{
  "max_lines": 2000,
  "max_bytes": 51200
}
```
Предотвращает забивание контекста большим выводом инструментов.

#### Provider timeouts и setCacheKey
Все 6 провайдеров настроены с:
- `timeout: 120000` (120с на полный запрос)
- `chunkTimeout: 60000` (60с между SSE чанками)
- `headerTimeout: 30000` (30с на получение заголовков)
- `setCacheKey: true` (промпт-кэширование для экономии токенов)

#### Вложенность сабагентов (subagent_depth)
`"subagent_depth": 2` — оркестратор может спавнить сабагентов, которые могут спавнить своих сабагентов.

#### Лимит шагов (steps)
- `build`: 50 шагов
- `orchestrator`: 30 шагов
- `plan`: 30 шагов
Защита от бесконечных циклов выполнения.

---

## 🤖 2. Агенты и сабагенты

### 2.1 Три основных агента (primary)

| Агент | Модель | Роль | Разрешения |
|-------|--------|------|------------|
| **orchestrator** | qwen3.5-122b (temp 0.15) | Оркестратор — только спавнит сабагентов | task/skill/webfetch=allow, read/write/edit/bash=deny |
| **build** | qwen3.5-122b (temp 0.2) | Исполнитель — пишет код, запускает команды | всё allow |
| **plan** | qwen3.5-122b | Планировщик — read-only | edit=deny, bash=ask, read=allow |
| **seo-writer** | ecom-qwen35-122b/qwen3.5-122b | SEO-писатель — генерация SEO-контента | read/task=allow, write/edit/bash=deny |

#### Orchestrator
- **Роль:** Строгий оркестратор. НИЧЕГО не делает сам — только спавнит сабагентов с максимально простыми задачами.
- **Модель:** `ecom-qwen35-122b/qwen3.5-122b`, temperature 0.15
- **Цвет в UI:** `#FF5733`
- **Разрешения:** `task.*=allow`, `skill=allow`, `webfetch=allow`, `websearch=allow`, всё остальное `deny`
- **Запуск:** Автоматически (агент по умолчанию)
- **Когда использовать:** Всегда для старта полного workflow

**Детальный промпт:** `agents/orchestrator.md` (271 строка)

#### Build
- **Роль:** Агент-исполнитель с полным доступом — пишет код, редактирует, запускает команды
- **Модель:** `ecom-qwen35-122b/qwen3.5-122b`, temperature 0.2
- **Цвет в UI:** `success` (зелёный)
- **Разрешения:** Всё `allow`
- **Запуск:** `/build <задача>` или через оркестратора
- **Когда использовать:** Когда нужна прямая реализация без грилла и ресерча

#### Plan
- **Роль:** Планировщик — создаёт и ревьюит планы имплементации до написания кода
- **Модель:** `ecom-qwen35-122b/qwen3.5-122b`
- **Цвет в UI:** `info` (голубой)
- **Разрешения:** `read=allow`, `edit=deny`, `bash=ask`
- **Запуск:** Через `/build` или оркестратора для планирования
- **Когда использовать:** Для создания implementation plan перед кодингом

#### @seo-writer

SEO-писатель для генерации SEO-оптимизированного контента.

| Параметр | Значение |
|----------|----------|
| Модель | ecom-qwen35-122b/qwen3.5-122b |
| Steps | 30 |
| Permission: read | ✅ allow |
| Permission: write | ❌ deny |
| Permission: edit | ❌ deny |
| Permission: bash | ❌ ask |
| Permission: task | ✅ allow |

**Назначение:** Создание SEO-оптимизированного контента с правильной структурой заголовков, ключевыми словами, мета-описаниями. Работает в режиме read-only — генерирует контент через task, не редактирует файлы напрямую.

### 2.2 Сабагенты (sub-agents)

#### 1. explore
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.6-35b |
| **Fallback** | qwen3.6-35b |
| **Роль** | Быстрое исследование кодовой базы — поиск файлов, структуры, usages |
| **Разрешения** | read/glob/grep/bash=allow, write/edit/task=deny |
| **Когда вызывает оркестратор** | Для поиска файлов, структуры, usages перед имплементацией |
| **Команда** | `task({ agent: "explore", prompt: "Найди все файлы, импортящие X" })` |

#### 2. project-mapper
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.6-35b |
| **Fallback** | qwen3.6-35b |
| **Роль** | Построение карты проекта — file tree, entry points, configs, deps, routes |
| **Разрешения** | read/glob/grep/bash=allow, write/task=deny |
| **Когда вызывает оркестратор** | Этап 0 — перед любой работой по проекту |
| **Команда** | `task({ agent: "project-mapper", prompt: "Построй карту проекта" })` |

#### 3. desearch-researcher
| Параметр | Значение |
|----------|----------|
| **Модель** | deepseek-v4-flash:max |
| **Fallback** | deepseek-v4-flash |
| **Роль** | Глубокий веб-ресёрч — ищет, фетчит, пишет structured findings |
| **Разрешения** | read/write/edit/glob/grep/bash/WebSearch/WebFetch=allow |
| **Когда вызывает оркестратор** | Этап 1 — после grill-me, 2-3 параллельных исследователя |
| **Команда** | `task({ agent: "desearch-researcher", prompt: "Исследуй угол: <angle>" })` |

#### 4. desearch-synthesizer
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.6-35b |
| **Fallback** | qwen3.6-35b |
| **Роль** | Синтез результатов нескольких desearch-researcher в единый отчёт |
| **Разрешения** | read/write/edit/glob/grep=allow, bash/task=deny |
| **Когда вызывает оркестратор** | После завершения всех desearch-researcher |
| **Команда** | `task({ agent: "desearch-synthesizer", prompt: "Синтезируй findings из .research/<topic>/" })` |

#### 5. react-dev
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.6-35b |
| **Fallback** | qwen3.6-35b |
| **Роль** | React/TS разработка (React 19, Vite 8, Tailwind v4, Radix, Zustand 5, TanStack Query 5) |
| **Разрешения** | read/write/edit/glob/grep/bash=allow, task=deny |
| **Когда вызывает оркестратор** | Этап 2 — для React/TypeScript задач |
| **Команда** | `task({ agent: "react-dev", prompt: "Создай компонент X" })` |

#### 6. go-dev
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.6-35b |
| **Fallback** | qwen3.6-35b |
| **Роль** | Go backend (Gin/Echo, pgx/GORM/sqlx, OpenTelemetry, testify) |
| **Разрешения** | read/write/edit/glob/grep/bash=allow, task=deny |
| **Когда вызывает оркестратор** | Этап 2 — для Go задач |
| **Команда** | `task({ agent: "go-dev", prompt: "Создай handler X" })` |

#### 7. rust-dev
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.6-35b |
| **Fallback** | qwen3.6-35b |
| **Роль** | Rust разработка (Axum/Actix, SQLx, tokio, serde, clap) |
| **Разрешения** | read/write/edit/glob/grep/bash=allow, task=allow |
| **Когда вызывает оркестратор** | Этап 2 — для Rust задач |
| **Команда** | `task({ agent: "rust-dev", prompt: "Создай модуль X" })` |

#### 8. reviewer (общий)
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.5-122b |
| **Fallback** | qwen3.5-122b |
| **Роль** | Общий code review по двум осям: standards + spec |
| **Разрешения** | read/write/edit/glob/grep=allow, bash/task=deny |
| **Когда вызывает оркестратор** | Для быстрого ревью (не критичного) |
| **Команда** | `task({ agent: "reviewer", prompt: "Проверь код" })` |

#### 9. reviewer-standards
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.5-122b |
| **Роль** | Ревью кодстайла и конвенций — naming, structure, error handling, comments, commits |
| **Разрешения** | read-only (edit/bash/task=deny) |
| **Когда вызывает оркестратор** | Этап 3 — параллельно с reviewer-spec и reviewer-arch |
| **Команда** | `task({ agent: "reviewer-standards", prompt: "Проверь кодстайл" })` |

#### 10. reviewer-spec
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.5-122b |
| **Роль** | Ревью соответствия спецификации — requirements coverage, scope creep, accuracy, DoD |
| **Разрешения** | read-only (edit/bash/task=deny) |
| **Когда вызывает оркестратор** | Этап 3 — параллельно с reviewer-standards и reviewer-arch |
| **Команда** | `task({ agent: "reviewer-spec", prompt: "Проверь соответствие spec" })` |

#### 11. reviewer-arch
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.5-122b |
| **Роль** | Архитектурное ревью — layering, dependency graph, scalability, testability, code smells |
| **Разрешения** | read-only (edit/bash/task=deny) |
| **Когда вызывает оркестратор** | Этап 3 — параллельно с reviewer-standards и reviewer-spec |
| **Команда** | `task({ agent: "reviewer-arch", prompt: "Проверь архитектуру" })` |

#### 12. test-agent
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.6-35b |
| **Fallback** | qwen3.6-35b |
| **Роль** | Запуск тестов (unit/integration/e2e) и отчёт |
| **Разрешения** | read/glob/grep/bash=allow, write/edit/task=deny |
| **Когда вызывает оркестратор** | Этап 4 — параллельный запуск unit/integration/e2e |
| **Команда** | `task({ agent: "test-agent", prompt: "Запусти unit tests" })` |

#### 13. security-check
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.5-122b |
| **Fallback** | qwen3.6-35b |
| **Роль** | Аудит безопасности/надёжности/простоты |
| **Разрешения** | read/glob/grep/bash=allow, write/edit/task=deny |
| **Когда вызывает оркестратор** | Этап 5 |
| **Команда** | `task({ agent: "security-check", prompt: "Проверь безопасность" })` |

#### 14. soc-check
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.5-122b |
| **Fallback** | qwen3.6-35b |
| **Роль** | Проверка SOC/контрактов/тестового покрытия |
| **Разрешения** | read/glob/grep/bash=allow, write/edit/task=deny |
| **Когда вызывает оркестратор** | Этап 6 |
| **Команда** | `task({ agent: "soc-check", prompt: "Проверь SOC" })` |

#### 17. ui-designer
| Параметр | Значение |
|----------|----------|
| **Модель** | qwen3.6-35b |
| **Fallback** | qwen3.6-35b |
| **Роль** | UI/UX дизайн — визуальный дизайн, layout, typography, color systems (только спецификации, не код) |
| **Разрешения** | read/write/edit/glob/grep=allow, bash/task=deny |
| **Когда вызывает оркестратор** | Когда нужен UI/UX дизайн |
| **Команда** | `task({ agent: "ui-designer", prompt: "Спроектируй UI для X" })` |

### 2.3 Стратегия моделей по этапам

| Этап | Модель |
|------|--------|
| Этап 0: Project Map | qwen3.6-35b |
| Этап 1: Grill-me | qwen3.5-122b |
| Этап 1: Research | deepseek-v4-flash:max |
| Этап 2: Implementation | qwen3.6-35b |
| Этап 3: Code Review | qwen3.5-122b |
| Этап 4: Testing | qwen3.6-35b |
| Этап 5: Security Check | qwen3.5-122b |
| Этап 6: SOC Check | qwen3.5-122b |

---

## 🛠 3. Skills (установленные)

| Skill | Описание | Как вызвать | Сценарии использования |
|-------|----------|-------------|----------------------|
| **caveman** | Ultra-compressed communication. Сокращает токены ~75% с сохранением точности. Поддерживает уровни: lite (по умолчанию), full, ultra | user говорит "caveman mode"/"talk like caveman"/"less tokens"/"be brief", или `/caveman [lite\|full\|ultra]` | Длинные сессии, экономия токенов, быстрые ответы |
| **config-pull** | Pull последних изменений из `~/claude-config` remote в `~/.claude/` | user говорит "pull config" | Синхронизация глобальной конфигурации |
| **context-metrics** | Мониторинг и отображение метрик использования контекста, лимитов и effort | `/context` или skill вызывает | Отслеживание расходов токенов, проверка лимитов rate limiting |
| **desearch** | Параллельный deep web research (3-5 углов) с синтезированным отчётом | user хочет исследовать тему | Любое исследование перед реализацией, анализ технологий |
| **design** | UI/UX дизайн из скриншотов/промптов — анти-AI-slop, анимации, градиенты, distinctive typography | user просит дизайн | Создание UI спецификаций, design tokens, компонентных specs |
| **full-workflow** | Запуск полного 7-этапного воркфлоу через `@orchestrator`: map → grill-me → research → implement → review → testing → safety-check → soc-check | `/start <задача>` или `/workflow <задача>` | Старт полного цикла разработки |
| **graphify** | Построение графа знаний из кода/документов/изображений/видео с community detection и query tools | `/graphify <path>`, или вопрос по коду, или `/graphify query "<вопрос>"` | Анализ архитектуры, документация, исследование кодовой базы |
| **grill-me** | Интерактивный допрос решений — разбирает дерево решений шаг за шагом, выявляет слабые места | `/grill-me <тема>`, или "прогони меня через grill-me"/"допроси мой план" | Стресс-тест плана перед реализацией, проверка решений |
| **mapps** | Multi-repo workspace management — клонирование репозиториев, генерация Makefile, карты проектов | `/mapps init <url> [<url>...]`, `/mapps add <url>`, `/mapps rm <name>` | Работа с несколькими репозиториями, создание workspace |
| **project-pull** | Pull правил/агентов/скиллов из `~/claude-config` в текущий проект | skill вызывает воркфлоу | Синхронизация project-level конфига |
| **project-push** | Push улучшенных правил/агентов/скиллов из проекта в `~/claude-config` | skill вызывает воркфлоу | Обновление центрального конфига |
| **workspace-init** | Инициализация workspace для проекта — изоляция конфига от app репозиториев, выбор методологии | `/workspace-init` | Настройка нового проекта, добавление методологий (GSD/BMAD/Superpowers) |

### unrobot — детекция и удаление AI-маркеров
- **Назначение:** Определяет и удаляет AI-маркеры в тексте (filler vocabulary, copula avoidance, rule-of-three, flat sentence rhythm, transition overuse, typography artifacts)
- **Языки:** 8 (en, ru, de, es, fr, pt, zh, ar)
- **Pipeline:** Detect → Rewrite → Verify (3-stage, never skip stage 3)
- **Команда:** `/unrobot <file> [--lang <code>] [--deep]`
- **Документация:** `skills/unrobot/SKILL.md`

### bmad-impl — планирование больших задач
- **Назначение:** Декомпозиция крупных задач через эпики → истории → ревью по классу риска
- **Когда использовать:** Задача на 3+ файла, миграции данных, архитектурные решения
- **Pipeline:** Kickoff → Epics → Stories → Review → Sprint
- **Команда:** `/bmad-impl <task> [--phase <name>]`
- **Документация:** `skills/bmad-impl/SKILL.md`

---

## 📋 3b. Правила (Rules)

11 правил в `rules/`, авто-загружаются через `instructions: ["rules/*.md"]`:

| Правило | Размер | Назначение |
|---------|--------|------------|
| frontend-components | 25 KB | Компонентная архитектура — ui-kit/ui/entity/widgets, CVA, cn(), Storybook |
| frontend-theme | 20 KB | Тема — CSS variables, data-theme, ThemeBox, генерация |
| tauri-bridge | 18 KB | Tauri v2 — IPC, команды, события, безопасность |
| frontend-zustand | 6.7 KB | Zustand — создание сторов, persist, partialize |
| bmad-impl-story-cycle | 5.8 KB | BMAD цикл реализации — эпики, ревью, Fable-гейт |
| opencode-implementer | 7.2 KB | Как opencode работает как executor под оркестрацией |
| context7 | 3 KB | Использование context7 MCP для проверки API |
| frontend-hooks | 1.5 KB | Паттерны хуков — one per concern, return pattern |
| go-backend | 1.8 KB | Go — структура, ошибки, middleware |
| go-observability | 3.0 KB | Go — логгирование, метрики, трассировка, health checks |
| rust-errors | 1.5 KB | Rust — error enums, thiserror, severity |

---

## 🔌 4. Плагины

### aistats.js

- **Назначение:** Ингест метрик сессии в aistats при idle
- **Событие:** `session.idle` на root сессиях (проверяет `parentID`)
- **Fire-and-forget:** не ждёт результата, ошибки глотаются
- **Команда:** `aistats ingest --tool opencode`
- **Зависимость:** `aistats` CLI в PATH

```javascript
// Логика: проверить что это root сессия, запустить aistats ingest не дожидаясь
void $`aistats ingest --tool opencode`.quiet().catch(() => {});
```

### herdr-agent-state.js (v14)

- **Назначение:** Отслеживание состояния агентов в Herdr UI + кастомный tool `get_metrics`
- **Тул:** `get_metrics` — возвращает markdown dashboard с метриками сессии
- **Состояния:** `working` | `idle` | `blocked`
- **Фичи:**
  - Обновление window title Herdr панели
  - Debounced push (300ms)
  - Refresh метрик каждые 10 секунд
  - Запись в `~/.config/opencode/metrics.json`
  - Отслеживание дочерних сессий (subagent sessions)
  - Форматирование токенов (K/M), времени (h m s), стоимости ($)
- **Зависимости:** `node:net`, `node:child_process`, `node:fs`, `node:path`, `@opencode-ai/plugin/tool`
- **ID интеграции:** `HERDR_INTEGRATION_ID=opencode`, версия 14

**События:**
| Событие | Действие |
|---------|----------|
| `session.created` | Старт сессии, начало refresh метрик, report session в Herdr |
| `session.updated` | Обновление model/tokens/cost из event data |
| `session.idle` | Остановка refresh, финальные метрики, report idle |
| `session.error` | Установка статуса blocked |
| `session.deleted` | Очистка данных сессии |

**Tool `get_metrics`:**
```
## Session Metrics
● Status: working
⏱ Duration: 12m 34s
📥 Tokens in: 12K / 8K
💰 Cost: $0.02
🤖 Model: qwen3.5-122b
```

---

## ⌨ 5. Команды

| Команда | Описание | Опции | Как вызвать |
|---------|----------|-------|-------------|
| `/start <задача>` | Полный workflow (grill → research → implement → review → test → safety → soc) | — | user |
| `/workflow <задача>` | То же что `/start` | — | user |
| `/grill-me <тема>` | Только интерактивный допрос | — | user |
| `/build <задача>` | Без грилла/ресерча, сразу имплементация | — | user |
| `/map` | Только построить карту проекта | — | user |
| `/safety-check` | Только проверка безопасности | — | user |
| `/soc-check` | Только проверка SOC/контрактов | — | user |
| `/caveman [lite\|full\|ultra]` | Режим экономии токенов | lite/full/ultra | user |
| `/m` | Показать метрики сессии (вызов `get_metrics` tool) | — | user |
| `/mapps` | Multi-repo workspace management | init/add/rm/help | user |
| `/context [--watch \| --limits \| --effort]` | Метрики контекста и лимиты | --watch, --interval, --limits, --effort | user |
| `/herdr-status` | Показать и обновить метрики сессии в Herdr | — | user |

---

## 🌐 6. MCP Серверы

| Сервер | Тип | Команда | Назначение |
|--------|-----|---------|------------|
| aistats | local | `aistats mcp` | Сбор метрик токенов и стоимости |
| context7 | remote | `https://mcp.context7.com/mcp` | Проверка API библиотек — получение актуальной, версионно-специфичной документации |
| playwright | local | `@playwright/mcp@latest` | E2E тестирование (headless chromium) |

### aistats MCP
Интеграция с системой сбора метрик сессий AiStats. Позволяет:
- Отслеживать длительность сессии
- Собирать статистику по токенам (input/output)
- Мониторить расходы по моделям
- Получать рекомендации по эффективности
Запускается автоматически opencode при старте через секцию `mcp` в `opencode.json`.

### context7 MCP
Context7 — удалённый MCP-сервер для проверки документации библиотек. Используется оркестратором и Honesty Protocol для верификации API-сигнатур вместо гадания. Не требует установки, не создаёт дочерних процессов (в отличие от local/npx MCP).

---

## 🔒 6b. Защита и безопасность

### guard.sh
Скрипт `/home/ruslan/.config/opencode/guard.sh` защищает от опасных compound-команд.

**Блокирует:**
- `rm` в compound-командах (&&, ||, ;)
- `wget`, `curl -o/-O` (скачивание)
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

### pre-commit.sh
Валидация перед коммитом:
1. Type checking (tsc --noEmit)
2. Linting (eslint)
3. Тесты (npm test)
4. Spec traceability
5. Context consistency
6. Commit message format (conventional commits)

---

## 🧩 7. Провайдеры моделей

| Провайдер | Модели | Context Window | Output Limit | Effort по умолч. | API Key Env |
|-----------|--------|---------------|-------------|-------------------|-------------|
| **ecom-qwen35-122b** | qwen3.5-122b | 128K | 8K | high | `ECOM_QWEN35_122b_TOKEN` |
| **ecom-qwen36-35b** | qwen3.6-35b | 128K | 8K | medium | `ECOM_QWEN36_35b_TOKEN` |
| **ecom-deepseek4-flash-max** | deepseek-v4-flash:max | 256K | 16K | high | `ECOM_DEEPSEEL4_FLASH_MAX_TOKEN` |
| **ecom-deepseek4-flash** | deepseek-v4-flash | 256K | 16K | medium | `ECOM_DEEPSEEL4_FLASH_TOKEN` |
| **ecom-giga3-10b** | giga3-10b | 64K | 4K | — | `ECOM_GIGA3_10b_TOKEN` |
| **ecom-qwen35-122b-no-think** | qwen3.5-122b (no-think) | 128K | 8K | — | `ECOM_QWEN35_122b_NO_THINK_TOKEN` |
| **ecom-qwen36-35b-no-think** | qwen3.6-35b (no-think) | 128K | 8K | — | `ECOM_QWEN36_35b_NO_THINK_TOKEN` |

**Детали провайдеров:**

| Провайдер | Base URL | Пакет npm |
|-----------|----------|-----------|
| ecom-qwen35-122b | `https://llm-core-olap.samokat.ru/v1` | `@ai-sdk/openai-compatible` |
| ecom-qwen36-35b | `https://llm-core-olap.samokat.ru/v1` | `@ai-sdk/openai-compatible` |
| ecom-deepseek4-flash-max | `https://llm-core-olap.samokat.ru/v1` | `@ai-sdk/openai-compatible` |
| ecom-deepseek4-flash | `https://llm-core-olap.samokat.ru/v1` | `@ai-sdk/openai-compatible` |
| ecom-giga3-10b | `https://llm-core-olap.samokat.ru/v1` | `@ai-sdk/openai-compatible` |
| ecom-qwen35-122b-no-think | `https://llm-core-olap.samokat.ru/v1` | `@ai-sdk/openai-compatible` |
| ecom-qwen36-35b-no-think | `https://llm-core-olap.samokat.ru/v1` | `@ai-sdk/openai-compatible` |

**Rate limits (DeepSeek):**
- `deepseek-v4-flash:max`: daily 100K, weekly 500K, monthly 2M
- `deepseek-v4-flash`: hourly 50K, daily 200K, weekly 1M

---

## 📋 8. Расшифровка файлов конфигурации

| Файл | Назначение |
|------|-----------|
| `opencode.json` | Главный конфиг — модели, провайдеры, агенты, MCP, permissions |
| `CLAUDE.md` | Глобальные правила поведения агента (180 строк: honesty, quality, testing, naming, git, comments, tokens, research, orchestrator mode) |
| `.env.example` | Шаблон переменных окружения для API-ключей (7 переменных для 5 провайдеров) |
| `.gitignore` | Игнорируемые файлы: `node_modules/`, `.env`, `*.log`, `.DS_Store`, `.vscode/`, `metrics.json` |
| `metrics.json` | Метрики последней сессии (state, model, duration, tokens, cost) |
| `package.json` | npm-зависимости: `@ai-sdk/openai-compatible ^2.0.41`, `@opencode-ai/plugin ^1.18.7` |
| `README.md` | Быстрый старт по конфигурации, команды, агенты |
| `CONFIG_DOCUMENTATION.md` | Полная документация конфигурации (этот файл) |

**Директории:**

| Директория | Назначение |
|------------|-----------|
| `agents/` | Описания агентов (16 `.md` файлов) |
| `commands/` | Команды opencode (9 файлов: context.json/md, m.md, grill-me.md, mapps.md, herdr-status.*) |
| `skills/` | Скиллы (12 директорий с SKILL.md + ресурсы) |
| `plugins/` | Плагины opencode (aistats.js, herdr-agent-state.js) |
| `scripts/` | Вспомогательные скрипты (setup-opencode-config.sh) |
| `docs/` | Документация (HERDR_METRICS_INTEGRATION.md) |
| `node_modules/` | npm-зависимости |

---

## 🚀 9. Установка на новом устройстве

### Быстрая установка (Linux/macOS)

```bash
# 1. Установить opencode (если ещё не установлен)
curl -fsSL https://opencode.ai/install.sh | sh

# ИЛИ через Homebrew (macOS)
brew install opencode

# 2. Склонировать конфигурацию
git clone git@github.com:rus-lan/opencode-work-config.git ~/.config/opencode

# 3. Установить зависимости
cd ~/.config/opencode && npm install

# 4. Настроить переменные окружения (см. .env.example)
cp .env.example ~/.config/opencode/.env
# Отредактируй .env и вставь свои API-ключи

# 5. Убедись что ~/.local/bin в PATH (для opencode)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc  # или ~/.bashrc

# 6. Проверка
opencode --version
opencode run "Hello"  # тестовый запрос
```

### Ручная установка (детально)

**Шаг 1: Установка opencode**

Вариант A — curl (Linux/macOS):
```bash
curl -fsSL https://opencode.ai/install.sh | sh
```

Вариант B — Homebrew (macOS):
```bash
brew install opencode
```

Вариант C — npm (если есть Node.js):
```bash
npm install -g @opencode-ai/cli
```

После установки убедись, что `~/.local/bin` в PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
# или для bash: echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

**Шаг 2: Клонирование конфигурации**

```bash
git clone git@github.com:rus-lan/opencode-work-config.git ~/.config/opencode
```

Если SSH не работает (нет ключа), используй HTTPS:
```bash
git clone https://github.com/rus-lan/opencode-work-config.git ~/.config/opencode
```

**Шаг 3: Установка зависимостей**

```bash
cd ~/.config/opencode && npm install
```

Это установит:
- `@ai-sdk/openai-compatible` — OpenAI-compatible SDK для кастомных провайдеров
- `@opencode-ai/plugin` — плагин SDK для opencode

**Шаг 4: Настройка переменных окружения**

```bash
cp ~/.config/opencode/.env.example ~/.config/opencode/.env
```

Отредактируй `.env` и заполни все API-токены:

| Переменная | Описание | Где взять |
|-----------|----------|-----------|
| `ECOM_QWEN35_122b_TOKEN` | Токен для Qwen 3.5 122B | Инфраструктура компании (llm-core-olap) |
| `ECOM_QWEN36_35b_TOKEN` | Токен для Qwen 3.6 35B | Инфраструктура компании (llm-core-olap) |
| `ECOM_QWEN35_122b_NO_THINK_TOKEN` | Токен для Qwen 3.5 122B (no-think режим) | Инфраструктура компании (llm-core-olap) |
| `ECOM_QWEN36_35b_NO_THINK_TOKEN` | Токен для Qwen 3.6 35B (no-think режим) | Инфраструктура компании (llm-core-olap) |
| `ECOM_DEEPSEEL4_FLASH_MAX_TOKEN` | Токен для DeepSeek v4 flash (max) | Инфраструктура компании (llm-core-olap) |
| `ECOM_DEEPSEEL4_FLASH_TOKEN` | Токен для DeepSeek v4 flash | Инфраструктура компании (llm-core-olap) |
| `ECOM_GIGA3_10b_TOKEN` | Токен для Giga v3 10B | Инфраструктура компании (llm-core-olap) |

Все провайдеры используют единый base URL: `https://llm-core-olap.samokat.ru/v1`

**Шаг 5: Проверка**

```bash
opencode --version
# Должно показать: 1.18.7

opencode run "Привет! Напиши short诗歌 на русском"
# Проверяет модель по умолчанию и агента
```

### Автоматическая установка

Используй скрипт `scripts/setup-opencode-config.sh`:

```bash
bash ~/.config/opencode/scripts/setup-opencode-config.sh
```

Скрипт автоматически:
1. Определит ОС (Linux/macOS)
2. Установит opencode если не установлен
3. Склонирует/pull репозиторий конфига
4. Установит npm-зависимости
5. Создаст `.env` из `.env.example` (если нет)
6. Добавит `~/.local/bin` в PATH (если нет)
7. Проверит что opencode работает

**Шаг 6: Установка guard hooks (рекомендовано)**

Установка pre-commit хуков для защиты от опасных команд:
```bash
~/.config/opencode/guard.sh --install
```

---

## 🔄 10. Обновление конфигурации

```bash
# Получить последние изменения из репозитория
cd ~/.config/opencode && git pull

# Обновить зависимости
npm install
```

**Project-level синхронизация:**
- `/project-pull` — pull правил/агентов/скиллов в проект
- `/project-push` — push улучшений из проекта в центральный репо

**Global config sync:**
- `config-pull` skill — pull последних изменений из `~/claude-config`

**Guard hooks:**
```bash
# Установить guard hooks после обновления
~/.config/opencode/guard.sh --install
```

**После git pull проверь:**
```bash
# Обновить зависимости
npm install

# Проверить, что guard.sh актуален
~/.config/opencode/guard.sh --list
```

---

## 🛠 11. Расширение конфигурации

### Добавление нового агента

1. Создай `.md` файл в `~/.config/opencode/agents/` с frontmatter:
   ```yaml
   ---
   name: my-agent
   mode: subagent
   model: provider/model
   permissions:
     read: allow
     write: allow
   ---
   ```
2. Добавь секцию `agent` в `opencode.json`:
   ```json
   "my-agent": {
     "mode": "subagent",
     "model": "ecom-qwen36-35b/qwen3.6-35b",
     "description": "Описание"
   }
   ```
3. Запушь изменения: `git add → commit → push`

### Добавление нового скилла

1. **Установка из репозитория:** Скопируй skill в `~/.config/opencode/skills/<name>/SKILL.md`
2. **Создание нового:** Создай директорию `~/.config/opencode/skills/<name>/` с `SKILL.md` и frontmatter:
   ```yaml
   ---
   name: my-skill
   description: Описание
   ---
   ```

### Добавление MCP сервера

1. Добавь секцию `mcp` в `opencode.json`:
   ```json
   "mcp": {
     "my-server": {
       "type": "local",
       "command": ["my-server", "--arg"],
       "enabled": true
     }
   }
   ```
2. Перезапусти opencode

### Добавление нового провайдера

1. Добавь секцию `provider` в `opencode.json`:
   ```json
   "my-provider": {
     "npm": "@ai-sdk/openai-compatible",
     "name": "model-name",
     "options": {
       "baseURL": "https://api.example.com/v1",
       "apiKey": "{env:MY_API_KEY}"
     },
     "models": {
       "model-name": {
         "name": "model-name",
         "limit": { "context": 128000, "output": 8192 }
       }
     }
   }
   ```
2. Добавь переменную окружения в `.env.example` и `.env`
3. Перезапусти opencode
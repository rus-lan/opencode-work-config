# 📊 МАСТЕР-ОТЧЁТ ВЕРИФИКАЦИИ OPENCODE

**Дата генерации:** 2026-07-28  
**Конфигурация:** `~/.config/opencode/`  
**Версия opencode:** 1.18.7

---

## Резюме

| Severity | Количество |
|----------|------------|
| CRITICAL | 5 |
| HIGH | 4 |
| MEDIUM | 4 |
| LOW | 3 |
| **ВСЕГО** | **16** |

---

## Таблица всех проблем

| # | Severity | Категория | Проблема | Файл | Строка | Действие |
|---|----------|-----------|----------|------|--------|----------|
| **CRITICAL** |
| 1 | CRITICAL | Агенты | Отсутствует файл агента `build.md` — агент `build` не может работать без промпта | `agents/build.md` | N/A | Создать файл `agents/build.md` с frontmatter и описанием роли исполнителя |
| 2 | CRITICAL | Агенты | Отсутствует файл агента `plan.md` — агент `plan` не может работать без промпта | `agents/plan.md` | N/A | Создать файл `agents/plan.md` с frontmatter и описанием роли планировщика |
| 3 | CRITICAL | Скиллы | Skill `implement` упоминается в CONFIG_DOCUMENTATION.md (строка 88) но директории нет | `skills/implement/` | N/A | Создать директорию `skills/implement/` с SKILL.md или убрать упоминание из документации |
| 4 | CRITICAL | opencode.json | Опечатка в имени переменной окружения: `ECOM_DEEPSEEK4_FLASH_TOKEN` → должно быть `ECOM_DEEPSEEK4_FLASH_TOKEN` | `opencode.json` | строки 95, 112 | Исправить `DEEPSEEK4` → `DEEPSEEK4` во всех упоминаниях (2 раза) |
| 5 | CRITICAL | opencode.json | Мёртвый путь в Playwright MCP: `${HOME}/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome` может не существовать | `opencode.json` | строка 69 | Заменить на `playwright` команду без жёсткого пути или проверить существование |
| **HIGH** |
| 6 | HIGH | Правила | Правило `go-observability.md` не включено в README rules index (строка 176 перечисляет 10 правил без него) | `README.md` | строка 176 | Добавить `go-observability` в список правил в README |
| 7 | HIGH | Правила | Правило `go-observability.md` не включено в CONFIG_DOCUMENTATION.md rules section | `CONFIG_DOCUMENTATION.md` | строки 478-490 | Добавить `go-observability` в таблицу правил CONFIG_DOCUMENTATION |
| 8 | HIGH | Агенты | Агент `seo-writer` имеет mode/permissions mismatch: в agents/ есть `seo-writer.md` но в opencode.json описан с `bash: ask` вместо `bash: deny` | `agents/seo-writer.md`, `opencode.json` | opencode.json:130 | Синхронизировать permissions: установить `bash: deny` в opencode.json или обновить файл агента |
| 9 | HIGH | Файловая система | Директория `commands/` содержит `.md` файлы без соответствующих `.sh` скриптов: `context.md`, `grill-me.md`, `mapps.md`, `m.md` | `commands/` | N/A | Создать `.sh` скрипты для каждой команды или убрать `.md` файлы если команды не нужны |
| **MEDIUM** |
| 10 | MEDIUM | Скиллы | Skill `context-metrics` не имеет версии в frontmatter | `skills/context-metrics/SKILL.md` | строка 1 | Добавить `version: X.Y.Z` в frontmatter |
| 11 | MEDIUM | Скиллы | Skill `full-workflow` не имеет версии в frontmatter | `skills/full-workflow/SKILL.md` | строка 1 | Добавить `version: X.Y.Z` в frontmatter |
| 12 | MEDIUM | Скиллы | Skill `grill-me` не имеет версии в frontmatter | `skills/grill-me/SKILL.md` | строка 1 | Добавить `version: X.Y.Z` в frontmatter |
| 13 | MEDIUM | Скиллы | Skill `mapps` не имеет версии в frontmatter | `skills/mapps/SKILL.md` | строка 1 | Добавить `version: X.Y.Z` в frontmatter |
| **LOW** |
| 14 | LOW | Скиллы | Skill `graphify` имеет устаревшую версию 0.8.39 вместо 1.0.0 | `skills/graphify/SKILL.md` | строка 3 | Обновить `version: 0.8.39` → `version: 1.0.0` |
| 15 | LOW | Документация | README сообщает 15 сабагентов но фактически в `agents/` 17 файлов (без build.md и plan.md) | `README.md` | строка 5, 38 | Обновить счётчик: 15 → 17 сабагентов в README |
| 16 | LOW | Документация | CONFIG_DOCUMENTATION.md упоминает `ecom-giga3-10b` которого нет в opencode.json | `CONFIG_DOCUMENTATION.md` | строки 62, 496 | Удалить упоминание `giga3-10b` или добавить провайдер в opencode.json |

---

## План исправлений

### CRITICAL (сделать немедленно)

#### 1. Создать файл агента `build.md`
**Файл:** `agents/build.md`  
**Действие:** Создать новый файл с frontmatter и описанием роли исполнителя

```yaml
---
name: build
mode: primary
model: ecom-qwen35-122b/qwen3.5-122b
temperature: 0.2
color: success
description: Агент-исполнитель с полным доступом для реализации задач
---
```

Добавить описание роли, разрешений, шагов (50), когда использовать.

#### 2. Создать файл агента `plan.md`
**Файл:** `agents/plan.md`  
**Действие:** Создать новый файл с frontmatter и описанием роли планировщика

```yaml
---
name: plan
mode: primary
model: ecom-qwen35-122b/qwen3.5-122b
color: info
description: Агент для планирования и план-ревью (edit deny)
---
```

Добавить описание роли, разрешений (edit: deny, bash: ask, read: allow), шагов (30).

#### 3. Исправить опечатку `DEEPSEEK4` → `DEEPSEEK4`
**Файл:** `opencode.json`  
**Строки:** 95, 112  
**Действие:** Заменить все упоминания `DEEPSEEK4` на `DEEPSEEK4`

```diff
- "apiKey": "{env:ECOM_DEEPSEEK4_FLASH_TOKEN}"
+ "apiKey": "{env:ECOM_DEEPSEEK4_FLASH_TOKEN}"
```

Также обновить `.env.example` и `.env` если они существуют.

#### 4. Исправить мёртвый путь Playwright MCP
**Файл:** `opencode.json`  
**Строка:** 69  
**Действие:** Заменить жёсткий путь на динамический или проверить существование

**Вариант A (рекомендуется):** Использовать `playwright` команду без жёсткого пути:
```json
"command": [
  "npx",
  "@playwright/mcp@latest",
  "--headless",
  "--no-sandbox",
  "--isolated"
]
```

**Вариант B:** Проверить существование пути перед запуском через pre-check скрипт.

#### 5. Создать или удалить skill `implement`
**Файл:** `skills/implement/SKILL.md`  
**Действие:** Либо создать директорию и файл, либо убрать упоминание из CONFIG_DOCUMENTATION.md

**Если skill нужен:**
```bash
mkdir -p skills/implement
```

Создать `SKILL.md` с frontmatter и описанием pipeline имплементации.

**Если skill не нужен:** Удалить упоминание из CONFIG_DOCUMENTATION.md строки 88-98.

---

### HIGH (сделать в ближайшее время)

#### 6. Добавить `go-observability` в README rules index
**Файл:** `README.md`  
**Строка:** 176  
**Действие:** Добавить `go-observability` в список правил

```diff
- `rules/` — 11 правил для сабагентов: frontend-components, frontend-hooks, frontend-theme, frontend-zustand, go-backend, rust-errors, tauri-bridge, opencode-implementer, bmad-impl-story-cycle.
+ `rules/` — 12 правил для сабагентов: frontend-components, frontend-hooks, frontend-theme, frontend-zustand, go-backend, go-observability, rust-errors, tauri-bridge, opencode-implementer, bmad-impl-story-cycle.
```

#### 7. Добавить `go-observability` в CONFIG_DOCUMENTATION.md
**Файл:** `CONFIG_DOCUMENTATION.md`  
**Строки:** 478-490  
**Действие:** Добавить строку в таблицу правил

```diff
| go-backend | 1.8 KB | Go — структура, ошибки, middleware |
+| go-observability | 3.4 KB | Go — OpenTelemetry, observability patterns |
| rust-errors | 1.5 KB | Rust — error enums, thiserror, severity |
```

#### 8. Синхронизировать permissions `seo-writer`
**Файл:** `opencode.json`  
**Строка:** 130  
**Действие:** Исправить `bash: ask` → `bash: deny`

```diff
"seo-writer": {
  "mode": "primary",
  "model": "ecom-qwen35-122b/qwen3.5-122b",
  "permission": {
    "task": "allow",
-   "bash": "ask",
+   "bash": "deny",
    "write": "deny",
    "read": "allow",
    "edit": "deny"
  },
```

#### 9. Создать `.sh` скрипты для commands/
**Файлы:** `commands/context.sh`, `commands/grill-me.sh`, `commands/mapps.sh`, `commands/m.sh`  
**Действие:** Создать исполняемые скрипты для каждой команды

**Пример для `commands/context.sh`:**
```bash
#!/bin/bash
# Команда /context — метрики контекста и лимиты
opencode run "/context"
```

Сделать исполняемыми: `chmod +x commands/*.sh`

---

### MEDIUM (по возможности)

#### 10-13. Добавить версии в frontmatter скиллов

**Файлы и действия:**

| Skill | Файл | Добавить |
|-------|------|----------|
| context-metrics | `skills/context-metrics/SKILL.md` | `version: 1.0.0` |
| full-workflow | `skills/full-workflow/SKILL.md` | `version: 1.0.0` |
| grill-me | `skills/grill-me/SKILL.md` | `version: 1.0.0` |
| mapps | `skills/mapps/SKILL.md` | `version: 1.0.0` |

**Пример:**
```yaml
---
name: context-metrics
version: 1.0.0
description: Мониторинг и отображение метрик использования контекста, лимитов и effort
---
```

---

### LOW (по желанию)

#### 14. Обновить версию `graphify`
**Файл:** `skills/graphify/SKILL.md`  
**Строка:** 3  
**Действие:** Обновить версию

```diff
- version: 0.8.39
+ version: 1.0.0
```

#### 15. Обновить счётчик сабагентов в README
**Файл:** `README.md`  
**Строки:** 5, 38  
**Действие:** Обновить 15 → 17

```diff
- Готовая конфигурация opencode с тремя primary агентами, 15 сабагентами...
+ Готовая конфигурация opencode с четырьмя primary агентами, 17 сабагентами...

- ### Сабагенты (15)
+ ### Сабагенты (17)
```

Также добавить недостающих сабагентов в таблицу: `explore`, `project-mapper`, `ui-designer`.

#### 16. Удалить упоминание `giga3-10b` из документации
**Файл:** `CONFIG_DOCUMENTATION.md`  
**Строки:** 62, 496  
**Действие:** Либо удалить упоминание, либо добавить провайдер

**Если модель не используется:**
```diff
- | `ecom-giga3-10b` | giga3-10b | 64K | 4K |
+ (удалить строку)
```

**Если модель нужна:** Добавить провайдер в `opencode.json` аналогично другим провайдерам.

---

## Статус исправлений

| # | Severity | Проблема | Статус | Дата исправления |
|---|----------|----------|--------|------------------|
| 1 | CRITICAL | build.md отсутствует | ⏳ TODO | |
| 2 | CRITICAL | plan.md отсутствует | ⏳ TODO | |
| 3 | CRITICAL | skill("implement") отсутствует | ⏳ TODO | |
| 4 | CRITICAL | Опечатка DEEPSEEK4 | ⏳ TODO | |
| 5 | CRITICAL | Playwright MCP путь | ⏳ TODO | |
| 6 | HIGH | go-observability в README | ⏳ TODO | |
| 7 | HIGH | go-observability в CONFIG_DOCUMENTATION | ⏳ TODO | |
| 8 | HIGH | seo-writer permissions | ⏳ TODO | |
| 9 | HIGH | commands/.sh скрипты | ⏳ TODO | |
| 10 | MEDIUM | context-metrics версия | ⏳ TODO | |
| 11 | MEDIUM | full-workflow версия | ⏳ TODO | |
| 12 | MEDIUM | grill-me версия | ⏳ TODO | |
| 13 | MEDIUM | mapps версия | ⏳ TODO | |
| 14 | LOW | graphify версия | ⏳ TODO | |
| 15 | LOW | README сабагенты 15→17 | ⏳ TODO | |
| 16 | LOW | giga3-10b упоминание | ⏳ TODO | |

---

## Рекомендации

1. **Немедленно исправить CRITICAL проблемы** — они блокируют работу агентов и могут вызвать runtime ошибки
2. **Создать pre-commit hook** для проверки:
   - Существования всех агентов из opencode.json
   - Отсутствия опечаток в именах переменных окружения
   - Актуальности документации
3. **Добавить CI-проверку** для валидации конфигурации
4. **Регулярно обновлять версии скиллов** и синхронизировать с upstream
5. **Создать `.env.example`** если отсутствует, с правильными именами переменных

---

**Отчёт сгенерирован автоматически на основе верификации конфигурации opencode.**

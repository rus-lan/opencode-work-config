# Миграция конфигурации OpenCode v1 → v2.0.28 — пошаговая инструкция

## 1. Цель

Мигрировать конфигурацию OpenCode с v1 на **v2.0.28** в рамках одного сеанса
(одной сессии одного сабагента / build-агента). Цель — привести глобальный
конфиг, глобальные агенты и локальные плагины к формату v2, чтобы:

- `opencode` запускался без ошибок конфигурации;
- не потерять настройки прав, провайдеров, MCP-серверов, агентов и плагинов;
- каждый изменяемый файл был безопасно сохранён в `.bak`.

> Воркспейсы (project-level `opencode.jsonc`) **не** трогаем — они уже
> мигрированы. Работаем только с перечисленными ниже глобальными файлами.

Эта инструкция излагает правила и примеры. **Версии пакетов, точные имена API
и структуру v2-событий исполнитель обязан сверять с официальными доками**
(см. раздел 8). Не выдумывать имена/API/версии.

---

## 2. Обязательные требования к работе

### 2.1 Бэкап перед КАЖДЫМ изменяемым файлом

Перед любой правкой создайте резервную копию:

```sh
cp <file> <file>.v1.bak
# пример
cp ~/.config/opencode/opencode.jsonc ~/.config/opencode/opencode.jsonc.v1.bak
cp ~/.config/opencode/agents/reviewer.md ~/.config/opencode/agents/reviewer.md.v1.bak
```

- Делайте бэкап непосредственно перед изменением каждого конкретного файла,
  точечно. Не делайте один общий бэкап «на всё».
- Не удаляйте `.bak`-файлы по завершении — они остаются как страховка.
- В финальном отчёте (блок D) укажите список всех созданных `.bak`.

### 2.2 Не выдумывать API и версии

- Все факты о v2 (имена полей, действий, структура фронтматтера, плагинные API,
  версии SDK/пакетов) — ТОЛЬКО из официальной документации
  `https://opencode.ai/v2/docs/`. Источники перечислены в разделе 8.
- Если какая-то деталь не подтверждается доками, **пометить её как
  «НЕ ПОДТВЕРЖДЕНО — требует сверки» и НЕ выдумывать** значение. Оставить
  комментарий `// TODO(v2): уточнить ...` и перейти дальше.
- Точные версии пакетов (`@opencode/plugin@...`, `@opencode/ai/providers/...`) —
  сверить с доком providers/build-plugins и фактическим установленным пакетом,
  не гадать.

### 2.3 Проверяемость

После каждого логического блока — при возможности вызывайте `opencode --version`
и `opencode` (см. блок D). Ошибки валидации конфига должны быть устранены до
перехода к следующему блоку.

---

## 3. Блок A — Глобальный конфиг `~/.config/opencode/opencode.jsonc`

Это основной файл. Разбит на подсекции. Правим каждый блок, .bak — перед началом.

### A.1 `permission` (объект) → `permissions` (массив)

В v1 это был объект. В v2 это **массив упорядоченных правил**
`{ action, resource, effect }`. Правила обрабатываются по порядку,
**побеждает последнее совпавшее**.

Маппинг действий (перенесите каждое правило, сохраняя прежний `resource`
и `effect`):

| v1 action           | v2 action            | Примечание |
| ------------------- | -------------------- | ---------- |
| `read`              | `read`               | — |
| `bash`              | `shell`              | **переименование** |
| `task`              | `subagent`           | **переименование** |
| `skill`             | `skill`              | — |
| `webfetch`          | `webfetch`           | — |
| `edit`              | `edit`               | покрывает edit/write/patch |
| `external_directory`| `external_directory` | — |
| `glob`              | `glob`               | — |
| `grep`              | `grep`               | — |
| `list`              | `read`               | — |
| `doom_loop`         | **УДАЛИТЬ**          | нет такого действия в v2 (doc: посл. действия) |
| `todowrite`         | **УДАЛИТЬ**          | нет todo-инструмента |
| `atlassian_jira_*` / `atlassian_confluence_*` / `gitlab_*` | `{ action: "<server>_<tool>", resource: "*", effect: ... }` | правила MCP-инструментов; см. A.3 |

Пример v1:

```jsonc
{
  "permission": {
    "read": true,
    "bash": "git status *",
    "todo": true
  }
}
```

Пример v2 (для наглядности значений):

```jsonc
{
  "permissions": [
    { "action": "shell", "resource": "git status *", "effect": "allow" },
    { "action": "shell", "resource": "git diff *", "effect": "allow" },
    { "action": "shell", "resource": "git push *", "effect": "deny" },
    { "action": "subagent", "resource": "*", "effect": "allow" },
    { "action": "jira_toolname", "resource": "*", "effect": "allow" }
  ]
}
```

> На практике преобразуйте реальные значения вашего файла. `effect` — одно из
> `allow` / `deny` / `ask`. v1 булево `true` для действия ≈ v2 `effect: "allow"`
> с `resource: "*"`.

Указания по MCP-tool правилам: инструменты именуются как
`<server>_<tool>` где `<server>` — имя MCP-сервера (пробелы и недопустимые
символы → `_`). Для серверов `jira`, `confluence`, `gitlab` их инструменты в v2
станут `jira_<tool>`, `confluence_<tool>`, `gitlab_<tool>`. Переносите только те
тела правил, которые реально есть в v2-наборе инструментов (сверьтесь со списком
подключённых серверов и их инструментов перед переносом).

### A.2 `provider` (ед.ч.) → `providers` (мн.ч.)

В v1 был объект `provider` с ключами `npm` и `options`. В v2 — объект
`providers`, ключевой по ID провайдера, с полями `package` и `settings`.

v1 → v2:

| v1                          | v2                                |
| --------------------------- | --------------------------------- |
| `"npm": "@ai-sdk/openai-compatible"` | `"package": "@opencode/ai/providers/openai-compatible"` |
| `"options": { baseURL, apiKey, setCacheKey }` | `"settings": { ... }` |
| `{env:...}` в apiKey        | ОСТАВИТЬ как есть (env-подстановка поддерживается в provider settings) |

Пример:

```jsonc
// v1
{
  "provider": {
    "ecom": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "https://ecom.example/v1",
        "apiKey": "{env:ECOM_API_KEY}",
        "setCacheKey": "cache-ecom"
      }
    }
  }
}

// v2
{
  "providers": {
    "ecom": {
      "package": "@opencode/ai/providers/openai-compatible",
      "settings": {
        "baseURL": "https://ecom.example/v1",
        "apiKey": "{env:ECOM_API_KEY}"
      }
    }
  }
}
```

Пункты для исполнителя:

- Провайдеры в этом конфиге — `ecom`, `ecom-exp`. Перенесите оба.
- `"npm": "@ai-sdk/openai-compatible"` — **исполнитель сверяет точный v2-пакет
  с доком providers** (`@opencode/ai/providers/openai-compatible` — подтверждено
  в доке). Если у `ecom-exp` свой пакет — подставьте соответствующий.
- `setCacheKey` — в доках не подтверждён как поле v2 `settings`. Если не
  находится — пометить `// TODO(v2): setCacheKey не обнаружен, проверено до 2026-10` и
  при неуверенности НЕ выдумывать эквивалент.
- `{env:VAR}` в `apiKey` оставлять — env-подстановка в provider settings
  документирована (см. в доке providers: `"apiKey": "{env:OLLAMA_API_KEY}"`).

### A.3 `mcp.<name>` → `mcp.servers.<name>`

В v2 имена серверов лежат **не** напрямую под `mcp`, а под
`mcp.servers.<name>`. Поле `"enabled": true` в v2 отсутствует — вместо него
используется `"disabled": false` (или просто убрать поле, т.к по умолчанию
сервер подключён).

- **Local** (stdio): `{ "type": "local", "command": [...], "environment": {} }`
- **Remote** (Streamable HTTP): `{ "type": "remote", "url": "...", "headers": {...}, "oauth": false, "timeout": {...} }`

Пример:

```jsonc
// v1
{
  "mcp": {
    "playwright": {
      "enabled": true,
      "type": "local",
      "command": ["bunx", "@playwright/mcp"],
      "env": { "KEEP": "value" }
    }
  }
}

// v2
{
  "mcp": {
    "servers": {
      "playwright": {
        "type": "local",
        "command": ["bunx", "@playwright/mcp"],
        "environment": { "KEEP": "value" }
      }
    }
  }
}
```

Указания:

- `"enabled": true` → убрать (или `"disabled": false`, эквивалент). `false` →
  `"disabled": true`.
- `env` → **`environment`** для local-серверов.
- Remote: по умолчанию в v2 используется OAuth; если сервер работает на
  api-key — ставьте `oauth: false`. `headers` — строковые значения, допускается
  `{env:VAR}`-подстановка.
- `timeout` — целые миллисекунды, при необходимости.
- Переносим **всё**, что было в этом конфиге под `mcp.*`, под
  `mcp.servers.*`.

### A.4 `instructions: ["rules/*.md"]` → НЕ работает в v2

Согласно доке config: `instructions` принимается, но **не загружается**;
используйте `AGENTS.md`.

```jsonc
{
  "instructions": ["rules/*.md"] // НЕ ЗАГРУЖАЕТСЯ в v2 — перенесите содержимое в AGENTS.md
}
```

Порядок действий:

1. Оставьте поле `instructions` **с комментарием** о необходимости переноса в
   `AGENTS.md` (чтобы не потерять след).
2. **Опционально** создайте `~/.config/opencode/AGENTS.md`, объединив содержимое
   файлов из `~/.config/opencode/rules/*.md`. Каталог/файлы сверьте с тем, что
   реально есть. Если rules-файлов нет — просто оставьте комментарий.

### A.5 `compaction`: v1-поля → v2

В v1 использовались `{ auto, reserved, tail_turns, prune }`. В v2 используются
`{ auto, keep: { tokens }, buffer }`. `reserved`, `tail_turns`, `prune` в v2
**не валидны** (см. doc compaction «Migration»).

Пример:

```jsonc
// v1
{
  "compaction": { "auto": true, "reserved": 8000, "tail_turns": 3, "prune": true }
}

// v2 (рекомендация исполнителя)
{
  "compaction": { "auto": true, "keep": { "tokens": 15000 }, "buffer": 20000 }
}
```

Указания:

- Значения `keep.tokens` / `buffer` исполнитель выбирает разумными — например
  `keep.tokens: 15000` (совпадает с дефолтом v2) и `buffer: 20000`. Пометьте,
  что это **рекомендация**, а не требование.
- Не вставляйте `reserved`/`tail_turns`/`prune` в v2.

### A.6 Оставить как есть (не трогать)

- `$schema`
- `model`
- `small_model`
- `default_agent`
- `subagent_depth`
- `watcher`
- `tool_output`

Проверьте в v2-схеме `https://opencode.ai/config.json`, что все они существуют.
Если какой-то из «оставить» окажется не в схеме — помеченный TODO, не удаляйте
без проверки.

### A.7 Итог по файлу

После правок конфиг должен содержать (`$schema` в начале), и все блоки выше.
Прогнать валидацию: `opencode --version` (см. блок D).

---

## 4. Блок B — Глобальные агенты `~/.config/opencode/agents/*.md`

Это **26 файлов** (frontmatter, `---`-блоки). Перед каждым — `.bak`. По одному
файлу за раз.

### B.1 frontmatter `permission:` (объект) → `permissions:` (YAML-список)

В v2 фронтматтер агента: `permissions:` — YAML-список правил вида
`- action: X` / `resource: "*"` / `effect: Y`. Маппинг действий как в A.1:

| v1            | v2         |
| ------------- | ---------- |
| `task`        | `subagent` |
| `bash`        | `shell`    |
| `write`       | `edit`     |
| `list`        | `read`     |
| `todowrite`   | УДАЛИТЬ    |

Пример:

```yaml
# v1
---
permission:
  read: true
  bash: true
  write: true
---

# v2
---
permissions:
  - action: read
    resource: "*"
    effect: allow
  - action: shell
    resource: "*"
    effect: allow
  - action: edit
    resource: "*"
    effect: allow
---
```

> Обязательно: если у вас clearance/права были заданы, сохранить их
> эквивалентно; если права не нужны (или вы не уверены) — можно оставить
> минимальный список или опустить (по умолчанию v2 базовая политика).

### B.2 УДАЛИТЬ legacy-поля

Из фронтматтера удалить (не переносить):

- `temperature` (есть в `build.md`, `orchestrator.md`, `plan.md` — удалить там тоже)
- `prompt`
- `tools`
- `disable`
- `maxSteps`
- старое `permission` (после переноса в `permissions` его не должно остаться)

Пример legacy-фронтматтера, который надо очистить:

```yaml
---
temperature: 0.7
maxSteps: 10
prompt: "..."
tools: [...]
disable: false
---
```

### B.3 `color: success` / `color: info` → hex

v2 принимает **только** hex-значение цвета (6-значный hex, напр `#ff6b6b`).
Не поддерживаются именованные цветовые метки v1 (`success`, `info`, ...).

- Заменить на валидный hex: напр. `#2ecc71` для зелёного/успеха, `#3498db`
  для синего/инфо — **либо удалить строку `color:`** целиком.

Пример:

```yaml
# v1
color: success
# v2 — одно из:
color: "#2ecc71"
# или вовсе удалить строку
```

### B.4 ОСТАВИТЬ как есть

- `description`
- `mode` (значения: `primary` / `subagent` / `all`)
- `model`
- `steps`
- `hidden`
- `name`

### B.5 Формат и порядок

- Один файл за раз; `.bak` перед каждым.
- После правки каждого файла — визуальная проверка фронтматтера, что он валидный
  YAML (отступы для вложенных списков — 2 пробела, значения под `- action:`).
- Перечень файлов (26): сверьте перечисление в каталоге
  `~/.config/opencode/agents/` реально существующих `.md`; процесс применяется
  ко всем фронтматтер-файлам.

---

## 5. Блок C — Плагины

### C.1 Перемещение плагинов в `~/.config/opencode/plugins/`

В v2 автозагрузка локальных плагинов происходит из **`plugins/`** под
конфиг-каталогом, а не из `_plugins/`. Переместите:

```sh
mkdir -p ~/.config/opencode/plugins
mv ~/.config/opencode/_plugins/aistats.js ~/.config/opencode/plugins/aistats.js
mv ~/.config/opencode/_plugins/herdr-agent-state.js ~/.config/opencode/plugins/herdr-agent-state.js
```

> Для файлового discover достаточно каталога `~/.config/opencode/plugins/` —
> **явная запись в `plugins:` не обязательна**. (В конфиг можно не добавлять
> их в массив `plugins`.) Сверьтесь с доком plugins (раздел «Discover»).

### C.2 `package.json` в `~/.config/opencode/`

Обновить зависимости на v2 SDK:

| Пакет (v1)              | Действие                     |
| ----------------------- | ---------------------------- |
| `@opencode-ai/plugin@^1.18.7` | заменить на `@opencode/plugin@2.0.28` (v2 SDK) |
| `@ai-sdk/openai-compatible` | проверить и при необходимости заменить на актуальный v2-пакет (сверить с доками providers/build-plugins) |

Пример обновлённой части:

```jsonc
{
  "dependencies": {
    "@opencode/plugin": "2.0.28"
  }
}
```

- Перед правкой `.pak`-бэкап `package.json`.
- После правки выполнить установку (`npm install` или `bun install`) в этом
  каталоге и убедиться, что `@opencode/plugin@2.0.28` установлен:
  `ls node_modules/@opencode/plugin` (или `bun pm ls`).

### C.3 `aistats.js` — уже портирован (только переместить)

Этот файл уже использует v2 API:

```js
import { Plugin } from "@opencode/plugin"
export default Plugin.define(...)
```

Действия:
1. Перемещён в `plugins/` (см. C.1).
2. Убедиться, что пакет `@opencode/plugin` установлен (C.2).
3. Ничего в его логике не менять — только проверка импорта и запуска.

### C.4 `herdr-agent-state.js` — ещё на v1 API, нужен порт

Этот файл пока на v1 API (импорт `@opencode-ai/plugin/tool`, экспорт
`HerdrAgentStatePlugin = async () => ({ tool, "tool.execute.before"/after, event })`).
Его надо портировать на v2 API **по образцу уже сделанного порта в
`aistats.js`** и по доке `https://opencode.ai/v2/docs/build/plugins/migrate-v1`.

Ключевые изменения (по подтверждённому в migrate-v1):

- Экспорт: `export default Plugin.define({ id: "herdr-agent-state", setup(ctx){ ... } })`
  (вместо `HerdrAgentStatePlugin = async () => ({...})`).
- События: `ctx.event.subscribe()` — async-iterable; тип события —
  `event.type`, данные — `event.data` (а не `event.properties`).
  `session.idle` — это **событие** в потоке, а не hook;
  пример из дока: `for await (const event of ctx.event.subscribe(...)) { if (event.type === "session.idle") ... }`.
- Custom tool: в v2 регистрация — через `ctx.tool.transform((editor) => { editor.add({...}) })`
  со схемой JSON Schema и возвратом `{ content: ... }` (вместо старого helper `tool()`).
  **Сверьте с доком migrate-v1 / build/plugins — там API может отличаться**;
  не выдумывайте.
- Обороты подпроцесса: `$`/Bun-хелпер из v1 → в v2 импортируйте и управляйте
  `child_process.spawn` (Node) вашего файла.

Порядок:
1. `.v1.bak` для `herdr-agent-state.js`.
2. Портировать по образцу `aistats.js` + док migrate-v1.
3. **Самая рискованная часть.** Если исполнитель не уверен, что находит
   правильное v2-событие/API для конкретного поведения плагина — **пометить
   явным TODO и НЕ выдумывать API**. Оставить закомментированный блок с тем,
   что именно не ясно.
4. После порта: убедиться, что глобальных ошибок импорта нет
   (см. блок D запуск).

> Напоминание: перемещение/переименование файла НЕ достаточно — v1-реализация
> плагинов не запускается в v2. Требуется порт кода.

---

## 6. Блок D — Финальная проверка (обязательно)

1. **Бэкапы.** Убедиться, что `.bak` создан для каждого изменённого файла:
   - `opencode.jsonc.v1.bak`
   - каждый `agents/*.md`.v1.bak (26 шт.)
   - `package.json.v1.bak`
   - `herdr-agent-state.js.v1.bak`
   - (если перемещали `_plugins/*.js` — оригинал уже в `plugins/`; бэкап
     делался до перемещения/порта)
2. **Запуск.**
   ```sh
   opencode --version   # должно показать 2.0.x
   opencode             # должен стартовать без падений/ошибок конфига
   ```
   При появлении ошибок — вернуться и устранить, руководствуясь докой.
3. **Регистрация плагинов.** Убедиться, что `aistats` и `herdr-agent-state`
   видны как загруженные (напр. `opencode plugin list`), либо по логам старта.
   Для локальных файлов в `~/.config/opencode/plugins/` файловый discover
   срабатывает без явной записи в конфиг.
4. **Дифф/резюме.** Показать итоговый отчёт:
   - список изменённых файлов;
   - что изменилось в каждом (кратко);
   - список `.bak`;
   - оставшиеся `TODO(v2)` (нерешённые места — честно, не скрывать);
   - результат проверки `opencode --version`.

---

## 7. Порядок ФАЙЛОВ-КРАТКО (дорожная карта исполнителя)

1. Блок A: `~/.config/opencode/opencode.jsonc` (+ .bak; опц. `AGENTS.md`).
2. Блок B: 26 файлов `~/.config/opencode/agents/*.md` (26 .bak).
3. Блок C: move плагинов, правим `package.json` (+.bak), порт `herdr-agent-state.js`.
4. Блок D: финальная проверка.

---

## 8. Официальные ссылки (источники фактов)

Исполнитель обязан сверяться именно с этими страницами:

- Config: https://opencode.ai/v2/docs/config
- Permissions: https://opencode.ai/v2/docs/permissions
- Agents: https://opencode.ai/v2/docs/agents
- MCP servers: https://opencode.ai/v2/docs/mcp-servers
- Providers: https://opencode.ai/v2/docs/providers
- Plugins: https://opencode.ai/v2/docs/plugins
- Build plugins: https://opencode.ai/v2/docs/build/plugins
- Migrate plugins V1→V2: https://opencode.ai/v2/docs/build/plugins/migrate-v1
- Compaction: https://opencode.ai/v2/docs/compaction
- Instructions: https://opencode.ai/v2/docs/instructions

Схема конфигурации (для валидации полей): https://opencode.ai/config.json

---

## 9. Чек-лист исполнителя

- [ ] `.bak` создан перед правкой каждого файла.
- [ ] **Блок A:** `permission`→`permissions` (массив), башьное `bash`→`shell`,
      `task`→`subagent`, `list`→`read`; удалены `doom_loop` и `todowrite`;
      MCP-tool правила перенесены как `<server>_<tool>`, `resource:"*"`.
- [ ] **Блок A:** `provider`→`providers`; для `ecom` и `ecom-exp` `npm`→`package`
      (пакет сверен с докой), `options`→`settings`; `{env:...}` в apiKey сохранён.
- [ ] **Блок A:** `mcp.<name>`→`mcp.servers.<name>`; `enabled`→убрано/`disabled`;
      local→`command`+`environment`, remote→`url`+`headers`+`oauth`+`timeout`.
- [ ] **Блок A:** `instructions` помечено комментарием; при возможности создан
      `~/.config/opencode/AGENTS.md`.
- [ ] **Блок A:** `compaction` переведён на `{auto, keep.tokens, buffer}`;
      v1-поля удалены.
- [ ] **Блок A:** не тронуты `$schema/model/small_model/default_agent/subagent_depth/watcher/tool_output`.
- [ ] **Блок B:** затронуты все 26 файлов; `permissions` — YAML-список;
      legacy-поля (`temperature/prompt/tools/disable/maxSteps/permission`) удалены;
      `color`—hex или удалён; `description/mode/model/steps/hidden/name` сохранены.
- [ ] **Блок C:** плагины в `~/.config/opencode/plugins/`; `package.json` на v2
      SDK; `aistats.js` перемещён; `herdr-agent-state.js` портирован на v2
      (либо отдельно помечен TODO, если не удалось подтвердить API).
- [ ] **Блок D:** все `.bak` на месте; `opencode --version` устраняет ошибки;
      `opencode` стартует; плагины загружаются; показан дифф/резюме.
- [ ] Все нерешённые места помечены `TODO(v2)` — ничего не выдумано.
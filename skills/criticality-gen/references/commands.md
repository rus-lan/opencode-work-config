---
title: "Справочник команд: criticality-gen"
purpose: Точный синтаксис, флаги и коды возврата всех подкоманд criticality.py.
audience: [ai-agent, human]
read_when: [нужен точный флаг команды, непонятен код возврата, пишете make-цель]
updated: 2026-11-18
status: actual
related: [workflow.md, checklist.md, artifacts.md, interactive.md]
---

# Справочник команд: criticality-gen

Единственный источник синтаксиса. Список подкоманд собран из `build_parser()`,
описания — из `COMMAND_DESCRIPTIONS`; канон фаз и гейтов — [workflow.md](workflow.md),
приёмка — [checklist.md](checklist.md).

## Как вызывать

| Способ | Пример | Когда |
|--------|--------|-------|
| `make <цель>` | `make check IS=erm.mm` | обычная работа из корня проекта (фасад → `.opencode/Makefile`) |
| `make -f .opencode/Makefile <цель>` | `make -f .opencode/Makefile help` | корневого фасада нет |
| `python3 .opencode/skills/criticality-gen/scripts/criticality.py <команда>` | `... validate` | точный флаг, которого нет в make-цели |

Общие флаги всех подкоманд:

| Флаг | Значение |
|------|----------|
| `--root <path>` | корень проекта с данными (`is/`, `catalog.yaml`, `INDEX.md`). По умолчанию: `CRITICALITY_ROOT`, иначе подъём от cwd. `validate`/`check`/`start` печатают `Корень: <path>` и предупреждают, если он не совпадает с cwd |
| `--path <path>` | устаревший синоним `--root` (совместимость) |
| `--no-next` / `--quiet` | не печатать подсказку следующего шага (для скриптов и make-целей) |
| `--debug` | печатать traceback вместо короткого `ERROR` |

## Команды
Колонки: **изменяет файлы** — пишет ли команда в проект; **сеть** — нужен ли git
или внешний доступ.

| Команда | Что делает | Изменяет файлы | Сеть |
|---------|-----------|----------------|------|
| `help` | справка: назначение и границы, подкоманды, воркфлоу, артефакты, состояние ИС | нет | нет |
| `info` | критерии оценки с пояснениями (уровни, сценарии, входы, enum, матрицы) | нет | нет |
| `init` | каркас проекта: `is.yaml`, `catalog.yaml`, `INDEX.md`, папку `is/` | да | нет |
| `prepare` | снимок карточки (`ssot-import`) → `INFORMATION.yaml` → `apps/` (dry-run по умолчанию); клон SSoT не нужен | да (`--apply`) | да (git для `apps/`) |
| `contacts` | контакты команды из ответа MCP `ssot_team` (`--team-json`) → `INFORMATION.yaml → contacts` (dry-run по умолчанию) | да (`--apply`) | нет |
| `validate` | проверить паспорта, `catalog.yaml` и `CRITICALITY.md`; просрочка по `review_date` | нет | нет |
| `verify-titles` | сверить заголовки страниц с Confluence; `--fix` — записать кеш `page_titles` и объявления в критериях (R19) | да (`--fix`) | да (REST) |
| `verify` | все гейты одним прогоном: `criteria-check`, `selftest`, `validate`, `docs-check`, `verify-titles`, `skill-check` | нет | да (REST в `verify-titles`) |
| `index` | сгенерировать таблицу `INDEX.md` (без `--write` — в stdout) | да (`--write`) | нет |
| `due` | просроченные, ближайшие и неоценённые переоценки | нет | нет |
| `scaffold` | создать `is/<код>/`, запись в `catalog.yaml` и `is.yaml` | да | нет |
| `reassess` | переоценка: план (dry-run) или файл + `review_date` (`--apply`) | да (`--apply`) | нет |
| `show` | все поля паспорта и ссылки по одной ИС | нет | нет |
| `next-step` | следующий шаг конвейера по состоянию ИС (`--is` — одна, без него — все) | нет | нет (клоны проверяются, если есть) |
| `score` | детерминированный расчёт критичности (режимы ниже) | нет | нет |
| `criteria show` | напечатать файл критериев (`--json`) | нет | нет |
| `criteria check` | проверить целостность файла критериев | нет | нет |
| `criteria sync-docs` | перегенерировать таблицы `docs/02` (нет файла — WARN, код 0) | да | нет |
| `check` | гейт достаточности данных перед расчётом (strict по умолчанию) | да (`DATA-REQUIREMENTS.*`) | нет |
| `requirements` | лист недостающих данных `DATA-REQUIREMENTS.*` (dry-run по умолчанию) | да (`--apply`) | нет |
| `enrich` | принять заполненный `DATA-REQUIREMENTS.yaml` в `INFORMATION.yaml` | да (`--apply`) | нет |
| `collect` | план сбора `RESEARCH-PLAN.md` (Confluence, Grafana, PromQL) | да (`--apply`) | нет |
| `links` | карта обхода ссылок `LINK-MAP.md`/`.yaml` (снимок `INFORMATION.yaml → ssot_snapshot.links`, `catalog.yaml`, компоненты; файл `entities/.../links.yaml` — fallback без снимка) | да (`--apply`) | нет |
| `sources` | принять `SOURCES-FINDINGS.yaml` → `INFORMATION.yaml#criteria_inputs` (`status: confirmed`) | да (`--apply`) | нет |
| `services` | клоны сервисов + `docs/`/`openspec/` → `SERVICE-FINDINGS.md` | да (`--apply`) | да (git) |
| `ask` | план вопросов человеку по незакрытым входам (кандидаты с провенансом, enum дословно); `--answers` — приём ответов в лист | да (`--apply`, `--answers`) | нет |
| `research` | сбор доказательств по открытым входам в Confluence → `RESEARCH.md` + `CANDIDATES.yaml` (кандидаты только `direct`, с числом шагов) | да | да (REST) |
| `exclude` | исключить ИС из расчёта (`excluded: true` + `reason`) | да | нет |
| `include` | вернуть исключённую ИС в расчёт | да | нет |
| `start` | рендер паспорта, `CRITICALITY.md`, `GENERATION.md`, `actions/*` | да (`--force`) | нет |
| `finalize` | финализация: `approve_link` (= `thread_link` при `handoff_status: published`), `assigned_date` (= `generated_at`), `review_date` (= `generated_at` + период), `criticality`, `criticality_ssot`, `status: confirmed` + `start-apply` → `validate` → `index` → `verify` | да | нет |
| `publish` | паспорт в формате dochub: файл, `_root.yaml`, ветка, коммит, MR | да (`--apply`) | да (`--push`) |
| `ssot-import` | импорт снимка карточки ИС из ответа MCP `ssot_get` в `INFORMATION.yaml → ssot_snapshot` (и `contacts` из `ssot_team` при `--team-json`) | да | нет |
| `ssot-plan` | план применения критичности в SSoT (после `publish`): что меняется, `status` (`changed`/`no_change`/`blocked`) и шаги MCP; `.ssot/<код>-apply-plan.json` | да (план) | нет |
| `ssot` | алиас `ssot-plan`: план обогащения SSoT (шаги MCP) | да (план) | нет |
| `ssot-record` | запись результата формы: `mrUrl` из `ssot_form_save` → `.ssot/<код>-MR.url`, `.ssot/<код>-MR.md` и поля `ssot_*` в `INFORMATION.yaml` | да | нет |
| `ssot-verify` | сверка применённой критичности с SSoT (`ssot_get`) → `ssot_snapshot.verified` | да | нет |
| `handoff` | этап handoff: спросить и отправить тред в `#Criticality_assessment` (MCP, при отказе — REST API) | да (`catalog.yaml`, `.handoff-request.json`) | да (`--send auto`) |
| `handoff-result` | результат MCP: `--message-url` (пишет `thread_link`) или `--failed` (REST-фолбэк) | да (`catalog.yaml`) | да (`--failed`) |
| `handoff-apply` | тонкая обёртка REST-отправки (`--confirm`); идемпотентность общая с `handoff` | да (`catalog.yaml`) | да |

## Флаги по командам

### `help`
По умолчанию печатает и текущее состояние ИС (таблица `код | сценарий | гейт |
уровень | следующий шаг`); `--no-state` — не читать `is.yaml`/`INFORMATION.yaml`
(быстрый вывод, работает без данных проекта; в make — `make help-fast`).

### `info`
`--section {levels,scenarios,inputs,enums,express,detailed,service_lifecycle,provenance}`,
`--json`.

### `init`
`--force` — перезаписать существующий `is.yaml` (остальные файлы не
перезаписываются никогда).

### `prepare`
| Флаг | Значение |
|------|----------|
| `--apply` | записать файлы и выполнить git-команды |
| `--no-clone` | не выполнять git для компонентов (`apps/`); на SSoT не влияет — клона нет, данные карточки приходят из `ssot-import` |
| `--is <код>` | только одна ИС |
| `--force-overwrite` | перезаписать неразобранный `INFORMATION.yaml` (ручные секции будут потеряны) |
| `--allow-empty-sections` | разрешить очищать секции, отсутствующие в снимке SSoT (по умолчанию сохраняется прежняя версия) |
| `--no-backup` | не создавать `INFORMATION.yaml.bak-<UTC>` |
| `--backup-keep <N>` | сколько последних бэкапов хранить (по умолчанию 10) |

### `contacts`
Собирает контакты команды-владельца из ответа MCP `ssot_team` и пишет их в
`INFORMATION.yaml → contacts`. Нужно для упоминаний TA/TL в публикации
(`@<login>` в RocketChat) и для исполнителя задачи Jira (логин).

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС (обязателен); код команды берётся из `catalog.yaml → systems[].team` |
| `--team-json <path\|->` | ответ MCP `ssot_team(code=<team>)` в JSON: путь к файлу или `-` (stdin); без него печатается инструкция и код `2` |
| `--apply` | записать секцию `contacts` в `is/<код>/INFORMATION.yaml` (без флага — dry-run) |
| `--json` | машинная форма: `{"is", "team", "source", "groups", "mentions"}`; `WARN` и ошибки — в stderr, stdout остаётся валидным JSON |

Что читает: ответ MCP `ssot_team(code=<team>)`, переданный через `--team-json`
(`team` — нижним регистром, `t006`). Клон SSoT не читается. `groups[].name` —
роль (`ta`, `tl`, `sa`, `s-arch`, `po`, `dm`, …), `groups[].members[]` — логины.
Логины приводятся к нижнему регистру, дубликаты и пустые строки отбрасываются,
порядок ответа сохраняется. Логин вне allowlist `[a-z0-9][a-z0-9._-]{0,31}`
отбрасывается (`x] @here` ломает YAML, `a\n* TL - @all` — текст сообщения) с
`WARN  в ответе ssot_team пропущены некорректные логины: <…>`. Логины `all`,
`here`, `channel` остаются в группах, но упоминанием не становятся
(`WARN  логин <x> совпадает с зарезервированным упоминанием RocketChat —
упоминание не добавлено`). Код команды — слаг: `team: "../x"` даёт
`некорректный код команды`. Пустая группа — `[]` (участники не выдумываются).

Что пишет: **только** секцию `contacts` (весь остальной файл сохраняется
байт в байт, включая `criteria_inputs`, `facts`, `conflicts`, `notes`).
Пишутся все группы ростера, не только `ta`/`tl`. Перед записью результат
разбирается мини-парсером; если `contacts` не читаются обратно — файл не
меняется и печатается `ERROR`. Та же проверка стоит в `prepare`:
`ERROR: блок contacts не прошёл обратную проверку — файл не записан`
(запись пропускается целиком — файл не остаётся без `contacts`, но и не
становится неразбираемым).

Упоминание — `@<login>`: соответствия login → ФИО в SSoT нет, поэтому в
публикации стоит логин, а не имя. Пустая группа `ta`/`tl` — `WARN «группа
<name> пуста — контакт не будет отмечен»` (не ошибка: публикация соберётся
без упоминания).

Коды: `0` — таблица напечатана (и файл записан с `--apply`); `1` — ИС нет в
`catalog.yaml`, данные `ssot_team` не переданы или не разобраны, `groups` не
список, нет `INFORMATION.yaml` для `--apply`; `2` — не задан `--is` или нет
`--team-json`.

### `validate`
`--date YYYY-MM-DD` — дата отсчёта просрочки (по умолчанию текущая).

Дополнительно печатает WARN (не ERROR — гейт публикации не меняется):
`контакты TA/TL не собраны — выполните make contacts IS=<код> APPLY=1` (секции
`contacts` нет либо она пуста — `team: null`, `groups: {}` — а команда указана в
`catalog.yaml → systems[].team`) и `группа ta|tl пуста в contacts —
обновите: make contacts IS=<код> APPLY=1`.

WARN `критичность в реестре не заполнена (catalog.yaml → criticality /
criticality_ssot = null), конфликт с реестром не проверен; заполняется на этапе
ssot-record` — в паспорте есть `object_criticality_estimation`, а в реестре оба поля
критичности пусты. Сверять не с чем, поэтому «0 расхождений» здесь означало бы
полноту проверки, которой не было. Заполнение реестра — этап изменения внешних
систем (`make ssot-record`), молча из паспорта оно не делается.

Два WARN о незакрытом сборе:

- `ссылка на АДР не собрана: нет facts.adr, catalog.yaml → architecture_page_id
  и confluence_page_id — в публикации будет ⛔ не заполнено` — вся цепочка
  `facts.adr` → `architecture_page_id` → `confluence_page_id` пуста
  (`actions.adr_basis = none`).
- `<вход>: blocking-вход без значения, кандидатов нет и глубокий поиск не
  зафиксирован — выполните tier 2 (references/search.md) и запишите search: в
  CANDIDATES.yaml` — по каждому такому blocking-входу (в `CANDIDATES.yaml` нет
  кандидата и нет записи `search.<вход>`).

### `index`
`--write` — записать файл, `--date YYYY-MM-DD` — дата отчёта.

### `research`
`--is <код>` — одна ИС (без флага — все ИС реестра), `--input <вход>` — только
один вход (`peak_hour_load`, `e2e`, …), `--all` — все ИС явно,
`--timeout <сек>` — общий бюджет времени прогона (по умолчанию 300).

Бюджет времени: перед каждым сетевым вызовом проверяется остаток. Исчерпан —
сбор останавливается, в stderr печатается прогресс `[research] вход N/M: <вход>
— запросов K`, в `RESEARCH.md` ставится «Статус: partial» и раздел «Что
прервано», код возврата **0** (это не поломка сбора: «не найдено» по
непроверенным входам не утверждается). `--allow-partial` — то же для ошибок
отдельных запросов.

Собирает доказательства по открытым входам в Confluence: CQL-запросы
`criteria.inputs.<вход>.queries` (с подстановкой `{is_code}`, `{is_name}`,
`{product}`, `{team}`) плюс маршруты `criteria.inputs.routes` (`e2e`,
`financial_loss`), скачивает `body.storage` найденных страниц, оценивает
доказательство `direct | indirect | none` и пишет:

| Файл | Что внутри |
|------|------------|
| `is/<код>/RESEARCH.md` | вход → выполненные запросы → кандидаты → вердикт; «не найдено» доказано списком запросов |
| `is/<код>/CANDIDATES.yaml` | кандидаты **только** `direct` (`value: null` + `evidence: direct` + `steps: N` + `source`), секция `search` дополняется выполненными запросами |

`direct` — код ИС в структурной ячейке таблицы (шаг процесса, строка реестра);
`indirect` (упоминание в прозе) в кандидаты не берётся. `steps` — сколько
структурных строк содержат код («20 из 89 шагов»). Требует `CONFLUENCE_TOKEN`
(и `CONFLUENCE_BASE_URL` при необходимости): без них — `ERROR`, а не пустой
отчёт. Повторный прогон **идемпотентен**: ключ дедупликации — вход + `page_id`
носителя, кандидаты человека (`value`/`confidence`) не затираются.

### `verify-titles`
`--is <код>` — только страницы этой ИС (страницы продукта проверяются всегда),
`--fix` — записать фактический заголовок в кеш.

Сверяет сохранённые заголовки с REST Confluence. Источник истины для рендера —
кеш `catalog.yaml → page_titles` (`title`, `title_version`,
`title_verified_at`); объявления в `criteria.external_refs.refs[]` и
`criteria.meta.sources[]` — только объявления, и `--fix` приводит их к
фактическим (строчный splice: комментарии и порядок ключей файла критериев
сохраняются). Расхождение — ERROR (код 1). Страница, которой нет (HTTP `404`/`410`), — WARN
«страница недоступна, пропущена», проверка продолжается; прочие ошибки
(`5xx`/timeout) — ERROR «проверка не выполнена», но собранные до сбоя заголовки
всё равно пишутся в кеш (`page_titles` + `titles_verified_at`). Нет
токена/сети — ERROR «проверка не выполнена», а не «OK». Итог: `проверено N страниц, расхождений X, без
зафиксированного title Y, недоступно (404/410) U, устаревших в источнике Z`
(правило R19).

`GENERATION.md` команда не правит: строка `titles: проверено N страниц, <дата>`
рендерится из состояния кеша (`titles_verified_at` + число записей
`page_titles`) при `make start-apply`. Поэтому порядок `start-apply` и
`verify-titles` на результат не влияет — повторный прогон любой
последовательности даёт побайтово тот же `GENERATION.md`. Нет
`titles_verified_at` — строка `titles: не проверялись (make verify-titles)`.

### `verify`
Флагов нет. Один прогон всех гейтов: `criteria-check`, `selftest`, `validate`,
`docs-check`, `verify-titles`, `skill-check`. Печатает строку на гейт и итог
`ИТОГО: N гейтов, X ошибок, Y предупреждений`; код 1 — если провален хотя бы
один гейт (`Результат: FAIL — провалены: …`). Единая точка ответа на вопрос
«всё ли в порядке» перед публикацией.

### `due`
`--months <N>` — период напоминания, `--today YYYY-MM-DD`, `--soon-days <N>`
(горизонт «скоро», по умолчанию 30).

### `scaffold`
`--contour <mm|smkt>` и `--name <name_is>` обязательны (в make: `IS=foo.mm`
или `CONTOUR=mm NAME=foo`); `--asset`, `--arch-code`, `--team`, `--page-id`,
`--criticality-page-id` — необязательные поля записи.

Пишет **оба** реестра: запись в `catalog.yaml → systems` и код в
`is.yaml → is:` (идемпотентно — повтор не дублирует). Если `is.yaml` нет,
создаёт его из `templates/is.example.yaml`. Без записи в `is.yaml` ИС невидима
конвейеру (`check`/`prepare`/`start` берут список ИС оттуда).

`assigned_date` и `review_date` проставляются **сразу** при появлении записи,
от даты генерации (`--date`, по умолчанию сегодня): `assigned_date` = эта дата,
`review_date` = она же + `review_period_months`. Даты попадают и в реестр, и в
каркас паспорта — иначе до `finalize` паспорт уходил бы в dochub без дат
(`publish` не отправляет пустые значения). Явно заданные значения не
перетираются; повторный `finalize` даты не сдвигает.

### `reassess`
`--is <код>`, `--date YYYY-MM-DD`, `--apply` (файл `reassessment-<дата>.md` +
обновление `catalog.yaml → review_date`).

### `show`
`--is <код>`.

### `score`
| Флаг | Значение |
|------|----------|
| `--is <код>` | данные из `is/<код>/INFORMATION.yaml` |
| `--axes legal=3,economic=2,...` | оценки осей (сложный сценарий) |
| `--time <1h\|1-12h\|12-24h\|>24h>` | время до последствий |
| `--cia c=high,i=medium,a=low` | оценки CIA |
| `--business <enum>` + `--cia-level <Low\|Medium\|High\|Critical>` | `final_matrix` |
| `--express` + `--impact <enum>` + `--sla <мин>` + `--consumers <enum>` + `--workload <клиентов/час>` | экспресс-оценка |
| `--selftest` | встроенные проверки расчёта |

Неполный набор обязательных входов — `status: incomplete`, код 1.

### `criteria`
`criteria show [--json]`, `criteria check`, `criteria sync-docs [--check]`
(`--check` только сравнивает и возвращает код 1 при расхождении).

### `check`
| Флаг | Значение |
|------|----------|
| `--is <код>` | только одна ИС |
| `--prepare` | сначала `prepare --apply`, затем гейт (`--no-clone` — без git) |
| `--no-requirements` | не генерировать `DATA-REQUIREMENTS.*` |
| `--diagnostic` | код 0 даже при `BLOCKED` (отладка, не для конвейера) |
| `--strict` | устаревший флаг: strict — поведение по умолчанию |

### `requirements`, `collect`, `services`
`--is <код>`, `--apply`, `--date YYYY-MM-DD`; у `services` ещё `--no-clone`
(анализировать только существующие клоны).

`collect` (план) / `collect-apply` (запись) рендерит `is/IS/RESEARCH-PLAN.md`.
Помимо страниц Confluence и дашбордов Grafana план содержит два раздела,
которые печатаются **для каждой ИС**:

| Раздел | Что даёт | Откуда данные |
|--------|----------|---------------|
| Product scope — процессы ИС | страница Product scope, CQL функциональных областей (`label = "functional-area" and space = currentSpace() and ancestor = <page_id>`), порядок чтения колонки «Сквозной бизнес-процесс (e2e)*» | `catalog.yaml → product_scope_page_id` (или `systems.<код>.product_scope_page_id`), продукт — `catalog.yaml → product` / `systems.<код>.product` |
| Глубокий поиск (tier 2) | tier 1 и tier 2 запросы по каждому незакрытому входу — из реальных кода, названия, продукта, команды, page_id и логинов `contacts` | критерии (`DEEP_SEARCH_TERMS`) + `INFORMATION.yaml` + `catalog.yaml` |

`product_scope_page_id` пуст — `WARN` и `⛔`-строка с подсказкой: дочерняя
страница корня продукта (карточка продукта из `ssot_get`) с заголовком
«<продукт> Product scope». Раздел Product scope печатается и при закрытых
входах расчёта (E2E-процессы нужны публикации независимо от гейта), при
закрытых входах — вместо раздела глубокого поиска строка «Незакрытых входов
нет — глубокий поиск не требуется».

Счётчик шагов включает оба раздела:
`шагов: N (страниц Confluence …, дашбордов Grafana …, поисков …, запросов …,
Product scope 1, глубокий поиск 1)`. Протокол поиска —
[search.md](search.md).

Новые поля `catalog.yaml` (проверяются `validate`: значение, не являющееся
целым числом > 0, — `ERROR`):

| Поле | Смысл |
|------|-------|
| `architecture_page_id` | page_id страницы архитектуры ИС: основание `actions.adr_link`, когда АДР не найдена; дерево от неё — маршрут tier 2; заполняется `prepare`, если пусто |
| `product_scope_page_id` | page_id страницы Product scope продукта — источник E2E-процессов; переопределяется на уровне ИС (`systems.<код>.product_scope_page_id`) |

### `ask`
План вопросов человеку по тем же незакрытым входам, что считает `check`
(blocking первыми, advisory после). Протокол опроса — [interactive.md](interactive.md).

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС (обязателен) |
| `--json` | машинная форма вместо markdown: JSON-массив, один элемент — один вопрос (`input`, `title`, `role`, `method`, `type`, `allowed`, `candidates`, `options`, `search`, `search_done`, `deep_search_missing`). `options` — массив объектов `{number, kind, text}` в фиксированном порядке: кандидаты → `manual` → `source_url` → `freeform` → `waive` (blocking) или `deferred` (advisory) → `exclude`; `kind` — машинный вид ответа для `ANSWERS.yaml`. `WARN` и сообщения об ошибках уходят в stderr, stdout остаётся валидным JSON (или пустым). Влияет только на план: с `--answers` вывод остаётся текстовым |
| `--apply` | записать `is/IS/ASK.md` (без флага — печать в stdout) |
| `--answers <файл.yaml>` | принять ответы человека и записать значения в `DATA-REQUIREMENTS.yaml` (формат — `templates/ANSWERS.yaml`); `INFORMATION.yaml` не меняется |
| `--reason "..."` | причина исключения для `choice: exclude` и варианта «исключить ИС» |
| `--scope {is,catalog}` | куда писать исключение (по умолчанию `is`) |
| `--date YYYY-MM-DD` | дата плана (по умолчанию `catalog.review_date`, не `now()`) |

Порядок кандидатов в вопросе: `is/IS/CANDIDATES.yaml` (`strong`, проверено
человеком) → §6 `SERVICE-FINDINGS.md` («из кода», `weak`) → SSoT
`base.yaml`/`links.yaml` (`weak`). Кандидатов нет — вопрос печатает маршрут
«где взять» (страница Confluence, дашборд Grafana, роль) из листа требований.
Enum раскрывается дословно, всеми значениями: агент не должен додумывать
вариант. `strong` без `source` — `WARN` и понижение до `weak` (неподтверждённое
не выдаётся за проверенное).

Кандидат с `value: null` — **кандидат-основание**: найдено основание, значения
нет («RTO — часы, но числового SLA нет»). Он показывается в плане и в опциях
как «взять кандидат N как основание — значение вписать вручную»; `choice:
candidate` по нему отклоняется, нужен `manual`. `confidence: strong` у такого
кандидата понижается до `weak` с `WARN`.

Оба файла привязаны к ИС полем `is:`. `CANDIDATES.yaml` чужой ИС — `WARN` и
кандидаты не читаются (план строится без них); `ANSWERS.yaml` чужой ИС —
`ERROR`, код `2`, лист не тронут.

**Поиск до вопроса.** Секция `CANDIDATES.yaml → search.<вход>` (`shallow`,
`deep`, `done`, `result`) — запись протокола поиска ([search.md](search.md)).
`done: true` означает, что tier 2 выполнен и зафиксирован. Вопрос по
blocking-входу без сильного кандидата и без `done: true` печатает
`WARN глубокий поиск не зафиксирован для <вход> — выполните tier 2 …` и получает
`deep_search_missing: true` в `--json`; advisory-входам флаг не ставится. В
`--json` поля `search` (запись как есть или `null`) и `search_done` показывают,
что именно уже искали.

`--answers` — единственный писатель листа: значения проходят те же валидаторы,
что гейт (`_ask_value_problem`), поэтому недопустимый enum отклоняется здесь, а
не в `enrich`. Семантика ответа:

| `choice` | Что требует | Что делает |
|----------|-------------|-----------|
| `candidate` | `candidate: <номер>` | значение и `source` наследуются от кандидата |
| `manual` | `value` + `source` | своё значение с источником |
| `source_url` | `source_url` (http/https) + `extracted {value, quote}` | извлечённое значение; для Confluence — `{type: confluence, ref: 'page_id=<id>; «<цитата>»'}`, иначе `manual` с URL и цитатой; без цитаты — отказ |
| `freeform` | `text` + `extracted {value, quote}` + `source` | значение из свободного текста человека |
| `waive` | `reason` (>= 10 символов) + `fallback.mode` (`assume_worst` \| `assume_best` \| `assume_value`; у `assume_value` — `fallback.value`) | закрывает вход без значения: `status: waived` + блок `waive` в листе и `INFORMATION.yaml`; оценка предварительная (R17) |
| `deferred` | — | оставляет вход как есть; blocking-вход оставит ИС в `BLOCKED` |
| `exclude` | `--reason` | исключает ИС из расчёта |

`excluded.reason` вместе с непустыми `answers` — `ERROR`, код `2` (исключение и
приём ответов разделяются на два прогона). Принятое значение в
`INFORMATION.yaml` вносит только `make enrich-apply` — `ask` ручной слой не
трогает.

Ключ ответа — имя входа расчёта **или** имя факта паспорта (`facts` шаблона
`INFORMATION.yaml`: `e2e_processes`, `e2e_status`, `e2e_source_page`,
`dependencies`, `support`, `adr`…). Ответ на факт требует `value` (свободная
структура: список процессов, объект поддержки) и необязательный `source`;
он пишется в секцию `facts` листа и принимается тем же `enrich-apply`.

Коды: `0` — план построен или все ответы приняты (включая `waive`); `1` —
ответы отклонены (недопустимое значение, `manual` без `source`, `source_url`/
`freeform` без цитаты, `waive` без причины или режима допущения,
неизвестный/закрытый вход) или ИС не найдена; `2` — аргументы или файл (нет
файла `--answers`, не задан `--is`, файл чужой ИС или не читается, исключение
вместе с ответами).

### `enrich`
`--is <код>`, `--apply`.

Принимает лист `DATA-REQUIREMENTS.yaml`: секцию `inputs` (входы расчёта →
`INFORMATION.yaml → criteria_inputs`) и необязательную секцию `facts` (факты
паспорта → `INFORMATION.yaml → facts`). Формат факта: `facts: {<имя>: <значение>}`
или `facts: {<имя>: {value: …, source: {type, ref}, status: confirmed}}`; имена
сверяются с ключами `facts:` шаблона `templates/INFORMATION.yaml` — опечатка
отклоняется (код `2`), а не создаёт новый ключ. Так ответ на факт-вопрос
(`e2e_processes`, `dependencies`, `support`, `adr`…) проходит тем же путём, что
ответ по входу: `ask-answers` → лист → `enrich-apply`, без ручной правки
`INFORMATION.yaml`.

### `exclude` / `include`
`--is <код>`, `--reason "..."` (для `exclude`), `--scope {is,catalog}`
(по умолчанию `is` — локально).

### `start`
| Флаг | Значение |
|------|----------|
| `--is <код>` | только одна ИС |
| `--force` | перезаписать существующие артефакты |
| `--dry-run` | рендер в память, без записи |
| `--diff` | печатать diff изменяемых файлов |
| `--date YYYY-MM-DD` | дата генерации |
| `--reassessment` | считать генерацию переоценкой |
| `--create-task` / `--create-confluence` / `--create-message` | пометить action-пакет как `requested` |

### Поля публикации: обязательные и опциональные

`actions/rocketchat-message.md` и текст треда собираются из
`templates/publication.md`. Обязательные поля (пусто → `⛔` и блокировка
отправки): технический архитектор, ссылка на MR паспорта в dochub, ссылка на
карточку ИС в SSoT. Остальные поля опциональны и отправку не блокируют.

`INFORMATION.yaml → publication.extra_info` — свободный текст строки
«Дополнительная информация по оценке»: пусто или ключа нет — буллет не
рендерится вовсе (никакого `⛔`); заполнено — буллет с текстом. `notes` (список
служебных заметок) как источник не используется.

### `finalize`
Финализация после подтверждения SRE: одной командой проставляет поля записи
`catalog.yaml → systems[<код>]` и прогоняет финальные гейты.

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС |
| `--approve-link <URL>` | ссылка на тред подтверждения SRE; **обязательна** (без неё паспорт — черновик), домен — из `criteria.external_refs.approve_link_domains` |
| `--assigned-date YYYY-MM-DD` | дата первой оценки; по умолчанию сегодня, если в реестре пусто |
| `--review-date YYYY-MM-DD` | дата текущей оценки; по умолчанию сегодня + период из критериев (`staleness.review_period_months`); период не задан — пусто + WARN |
| `--criticality <уровень>` | уровень паспорта; по умолчанию `object_criticality_estimation` из паспорта |
| `--dry-run` | показать, что будет записано, без записи и без гейтов |

Поведение:

- `criticality` — из паспорта, `criticality_ssot` — из SSoT severity
  (`ssot_snapshot.base.severity.type`, нормализация по критериям). Расхождение
  (в т.ч. с `--criticality`) — `ERROR` с обоими значениями; не угадывается.
- `status: confirmed`.
- После записи: `start-apply FORCE=1` → `validate` → `index` → `verify`.
  `ERROR` в любом шаге — записанные поля и артефакты ИС откатываются из снимка
  (атомарность), код `1`.
- Без `--approve-link`: `ERROR: подтверждение SRE обязательно; паспорт без
  подтверждения — черновик`.

### `handoff`
Финальный этап: спросить, отправлять ли готовое сообщение в
`#Criticality_assessment`, и при согласии отправить. Текст — тот же рендер
`templates/publication.md`, что в `actions/rocketchat-message.md`.

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС |
| `--send auto` | отправить: MCP, при отказе — REST API |
| `--send manual` | не отправлять; `handoff_mode: manual`, пакет остаётся `pending_manual` |
| `--transport auto` | (по умолчанию) MCP при найденном MCP-сервере Rocket.Chat, иначе REST |
| `--transport mcp` | только запрос для MCP: пишет `is/<код>/.handoff-request.json`, код `0`, статус `mcp_requested` |
| `--transport api` | только REST: `POST /api/v1/chat.postMessage` |
| `--mcp-timeout <сек>` | срок ожидания ответа MCP (по умолчанию 120 или `criteria.handoff.mcp_timeout_seconds`); пишется в `.handoff-request.json → deadline` и `catalog.yaml → handoff_deadline` |
| `--resume` (`--check-mcp`) | проверить срок ожидания MCP и выполнить фолбэк на REST, не дожидаясь следующего запуска |
| `--allow-duplicate-risk` | аварийно: REST-фолбэк без поиска своего сообщения в канале (возможен дубль, если MCP уже отправил) |
| `--thread <tmid>` | ответ в **существующий** тред: `tmid` = id сообщения-родителя из ссылки Rocket.Chat `?msg=<tmid>`. Env-фолбэк: `HANDOFF_THREAD` → `ROCKETCHAT_THREAD` → `RC_THREAD` |
| `--report` | опубликовать **результаты** оценки (отчёт из паспорта/`INFORMATION.yaml`/реестра) вместо запроса согласования: гейты MR/`⛔`/SSoT не применяются, отправка — REST, `handoff_mode: report`. Взаимоисключающий с режимом согласования; требует `--send auto` (или `--dry-run`) |
| `--thread-new` | с `--report`: создать **новый тред** — родитель (итог + основные ссылки) и три ответа с детализацией. `thread_link`/`approve_link` = родитель, `handoff_thread: true`. Повтор идемпотентен (`--force-resend`) |
| `--update-parent` | с `--report`: обновить родителя опубликованного треда через `chat.update` (например, добавить появившийся SSoT-MR); новый тред не создаётся |
| `--dochub-mr-url <URL>` | ссылка на MR в dochub для родителя отчёта (`--thread-new`) |
| `--ssot-mr-url <URL>` | ссылка на MR в SSoT для родителя; с `--update-parent` подставляется в уже отправленного родителя |
| `--force-resend` | повторить отправку, даже если `thread_link` заполнен |
| `--dry-run` | канал, транспорт и **почему он выбран**, MCP-таймаут, длина и фрагменты текста; ничего не отправлено и не записано |

Без `--send` вопрос задаётся только в TTY (`1` — отправить, `2` — оставить
вручную, `3` — отменить). Вне TTY — отказ с подсказкой `SEND=auto|manual`:
дефолта нет, без явного ответа ничего не отправляется.

**Режим отчёта (`--report`).** Текст собирает `_report_text_for_is`: заголовок
«Оценка критичности ИС <код> — <название>», итог (уровень · метод · статус ·
дата генерации), участники (TA/TL/остальные из `contacts`), входные значения с
провенансом (`criteria_inputs` → значение+единица, `source.type` + короткий
`source.ref`, `status`), расчёт (`E`, интервал, score), незаполненные входы
обычным текстом (без `⛔`), ссылки (SSoT-карточка, страница ИС, паспорт,
`CRITICALITY.md`) и «Что дальше». Гейты MR/`⛔`/SSoT **не применяются**;
`--dry-run` печатает текст целиком. Успешная отправка пишет
`handoff_mode: report`, `handoff_status: published`, `thread_link` и
`approve_link` = ссылка на созданное сообщение (с `--thread` — ответ в тред).

**Тред отчёта (`--report --thread-new`).** Родитель — краткий итог (уровень ·
метод · статус · дата генерации), участники (TA/TL) и основные ссылки (SSoT,
MR в dochub, MR в SSoT; ссылки на MR можно передать флагами `--dochub-mr-url`
и `--ssot-mr-url`) плюс строка «Детализация — в ответах ниже». Ответы в тред
(`tmid` = id родителя): 1) входные значения с провенансом; 2) расчёт (`E`,
интервал, score) и незаполненные входы; 3) ссылки на артефакты (паспорт,
`CRITICALITY.md`, страницы). `thread_link`/`approve_link` указывают на
**родителя**, в реестр пишется `handoff_thread: true`; повторный `--thread-new`
не создаёт второй тред (`--force-resend` — обойти). Когда MR появился позже,
`--update-parent --ssot-mr-url <URL>` правит родителя через `chat.update` —
`thread_link` не меняется, новый тред не создаётся.

Предусловия режима согласования (отказ, код `1`): в тексте нет `⛔` в
обязательных полях; `validate` без ERROR; `thread_link` пуст
(идемпотентность). Пишет в `catalog.yaml →
systems.<код>`: `handoff_mode`, `handoff_status`, `thread_link`, `published_at`,
`handoff_error`, `handoff_deadline`, `fallback_reason`, `transport_used`,
`handoff_thread` (тред отчёта).

**MCP сломался → сразу API.** Признаки сбоя и `fallback_reason`:

| Признак | `fallback_reason` | Действие |
|---------|-------------------|----------|
| MCP-сервера Rocket.Chat нет в конфиге | `mcp_unavailable` | сразу REST |
| исполнитель вернул `--failed` | `mcp_failed` | REST-фолбэк |
| истёк `deadline` (см. `--mcp-timeout`) | `mcp_timeout` | автоматически в `handoff`/`--resume` |
| ответ MCP невалиден (URL/хост/`/channel/`/`msg=`) | `mcp_invalid_response` | `thread_link` не пишется, сразу REST |
| `handoff-result` без `--message-url` и без `--failed` | `mcp_format_error` | внятная ошибка + REST |

**Дедупликация.** Перед REST-фолбэком после MCP-попытки скрипт ищет своё
сообщение: имя канала резолвится в `roomId` (`channels.info` → `groups.info`),
затем `GET /api/v1/{channels|groups}.messages?roomId=<id>&count=20`, сравнение
первых 80 символов текста и автора (`u._id`). Найдено — его `_id` становится
`thread_link`, повтор не отправляется. Поиск недоступен — отправки нет без
`--allow-duplicate-risk` (fail-closed).

Ключ дедупликации учитывает тред и режим: при `--thread <tmid>` совпадением
считается только сообщение с тем же `tmid`, а без `--thread` — только
топ-сообщение. Опубликованный отчёт (`handoff_mode: report`) не блокирует
запрос согласования и наоборот — это разные тексты и разные сообщения.

**Ответ в тред (`--thread <tmid>`).** С `tmid` payload `chat.postMessage` шлёт
`roomId` + `tmid` (roomId резолвится по имени канала); `roomId` не резолвится —
WARN и фолбэк на `channel` + `tmid`. `thread_link`/`approve_link` указывают на
**созданный ответ** (`message._id` из ответа API), а не на родителя. Тот же
`tmid` пишется в `.handoff-request.json` для MCP-транспорта.

Канал берётся из `criteria.handoff.channel` (по умолчанию
`#Criticality_assessment`); хардкод в скрипте — только фолбэк.

REST: адрес — `ROCKETCHAT_URL` (по умолчанию
`criteria.external_refs.rocketchat_base`), токен — `ROCKETCHAT_TOKEN`, id
пользователя — `ROCKETCHAT_USER_ID`. Порядок проверки **фиксированный**,
первый непустой выигрывает (переменные не смешиваются между контурами):

| Что | Порядок (слева направо) |
|-----|-------------------------|
| токен | `ROCKETCHAT_TOKEN` → `RC_TOKEN` → `ROCKER_TOKEN` → `ROCKET_TOKEN` → `STRELKA_TOKEN` → `STRELKA_API_TOKEN` |
| `X-User-Id` | `ROCKETCHAT_USER_ID` → `RC_USER_ID` → `ROCKER_USER_ID` → `ROCKET_USER_ID` → `STRELKA_USER_ID` → `ROCKETCHAT_USER` → `ROCKER_USER` → `ROCKET_USER` → `STRELKA_USER` |
| адрес | `ROCKETCHAT_URL` → `RC_URL` → `ROCKET_BASE_URL` → `ROCKET_URL` → `STRELKA_URL` → `STRELKA_BASE_URL` |

`*_USER` (без `_ID`) — нестандартные имена контура; там лежит именно **id**
(17 символов, совпадает с `user._id` из `GET /api/v1/me`), а не логин: логин
(`name@domain`) для `X-User-Id` не годится. Значение с `@` или пробелом
распознаётся как логин и блокирует отправку с явной ошибкой (иначе это
выглядело бы как «истёк токен» → `401`). `ROCKET_BASE_URL` / `ROCKER_TOKEN` —
исторические имена, `STRELKA_*` — второй контур того же Rocket.Chat.
Таймаут 15 с, один повтор только на 5xx/таймаут. Ошибки различаются: `401`
токен (или отсутствующий/неверный `X-User-Id`), `403` права на канал, `404`
канал, `429` rate limit. Токен не печатается и не пишется в файлы; `--dry-run`
показывает только **имя** переменной-источника, не значение.

### `handoff-result`
Результат транспорта `mcp` — ровно один из двух флагов.

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС |
| `--message-url <URL>` | ссылка на отправленное сообщение: проверяется (схема http(s), хост `rocketchat_base`, путь `/channel/`, непустой `msg=`), затем пишутся `thread_link`, `handoff_status: published`, `published_at`, `transport_used: mcp`; файл запроса удаляется. Невалидная ссылка — `mcp_invalid_response`: `thread_link` не пишется, статус `failed`, сразу REST-фолбэк |
| `--failed <причина>` | отказ MCP (`mcp_failed`) → автоматический REST-фолбэк; оба транспорта недоступны — статус `failed`, причина в `handoff_error`, файл запроса сохранён, код `1` |
| `--force-resend` | перезаписать уже опубликованный `thread_link` другой ссылкой (без флага — отказ, код `1`) |
| `--allow-duplicate-risk` | аварийный фолбэк без поиска сообщения в канале (возможен дубль) |
| `--dry-run` | показать, что будет записано/отправлено, без действий |

Без обоих флагов (`--message-url` и `--failed`) — ошибка формата ответа
(`mcp_format_error`): внятное сообщение + REST-фолбэк. С обоими сразу — код `2`,
отправки нет.

### `ssot-import`
Импорт снимка карточки ИС из ответа MCP `ssot_get(group="information-systems",
entity=<код>)` в `INFORMATION.yaml → ssot_snapshot`. Клон SSoT и сеть не
читаются: команда разбирает переданный JSON (путь или `-` для stdin).

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС |
| `--entity-json <path\|->` | ответ MCP `ssot_get` в JSON: путь к файлу или `-` (stdin) |
| `--team-json <path\|->` | ответ MCP `ssot_team(code=<team>)` в JSON: путь или `-`; дополнительно пишет секцию `contacts` |

Поведение:

- пишется **только** `ssot_snapshot` (и `contacts` при `--team-json`), остальной
  файл сохраняется байт в байт; перед записью — обратная проверка разбора;
- **нет `INFORMATION.yaml`** — команда сама создаёт каркас из
  `templates/INFORMATION.yaml` (тот же скелет, что у `prepare`) и сразу пишет в
  него снимок. Это снимает дедлок свежего проекта: `prepare` без снимка файл не
  создаёт, а импорт раньше отказывался писать в несуществующий файл;
- `prepare` сохраняет провенанс снимка (`source: mcp`, `commit`, `version`,
  `imported_at`): пересобираются только секции карточки;
- повторный импорт тех же данных — no-op (файл не меняется);
- сущности нет в ответе — `ERROR` с кодом ИС, ничего не пишется.

### `ssot-plan`
План применения критичности в SSoT (после `publish`): что меняется и какие шаги
MCP предстоит выполнить. Ничего в SSoT не пишет — только план.

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС |
| `--force` | обойти гейт валидации: `WARN` + запись в `is/<код>/.gate-overrides.log` |

Пишет `.ssot/<код>-apply-plan.json`:

| Поле | Значение |
|------|----------|
| `status` | `changed` — есть что менять; `no_change` — `severity` уже соответствует; `blocked` — гейт не пройден или нет данных |
| `changes` | поля `severity` (было/стало), enum из `levels.ssot_enum` |
| `steps` | шаги MCP: `ssot_entity_open` → `ssot_form_fields` → `ssot_ui_select`/`ssot_ui_fill` → `ssot_form_save` |

Поведение:

- уровень берётся из паспорта (`object_criticality_estimation`) и сверяется с
  `catalog.yaml → criticality_ssot`; расхождение — `blocked`, а не выбор «по
  старшинству»;
- enum — из критериев: `levels.ssot_enum` (`Office productivity` →
  `business-operational`, в SSoT такого уровня нет);
- `method: target` и `confirmation` = `approve_link` из реестра (ссылка на
  актуальный тред); нет `approve_link` — `blocked` с причиной (пустое поле в
  форме — ошибка);
- `addon` не добавляется и не меняется — только сохраняется существующее;
- `severity` уже совпадает — `status: no_change`, шагов MCP нет (в треде —
  «не требуется: severity уже соответствует (…)» вместо `⛔`);
- `--force` не отменяет `blocked` от отсутствия данных: он только снимает
  гейт `validate`/fingerprint/blocking-входов (R18).

### `ssot-record`
Запись результата формы `ssot_form_save`: ссылка на созданный ботом SSoT-MR,
версия сущности и статус применения. Правит `INFORMATION.yaml` и `.ssot/`.

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС |
| `--mr-url <URL>` | `mrUrl` из ответа `ssot_form_save` (обязателен) |
| `--version <id>` | идентификатор версии сущности из ответа MCP |
| `--save-json <path\|->` | сырой ответ `ssot_form_save` (путь или stdin) — для провенанса |
| `--status-json <path\|->` | ответ статуса MR (`awaiting_approvers`, `canApply` и т. п.) |

Пишет:

- `.ssot/<код>-MR.url` — ссылка на SSoT-MR; из неё `start` подставляет
  `actions.ssot_mr_text` в текст треда;
- `.ssot/<код>-MR.md` — сводка записи (что менялось, версия, статус);
- поля `ssot_*` в `INFORMATION.yaml`: `ssot_mr_url`, `ssot_version`,
  `ssot_can_apply`, `ssot_status`, `ssot_recorded_at`.

Поведение: `save_not_observed` (форма не вернула `mrUrl`) и
`awaiting_approvers` (MR ждёт апрувов) — не ошибка команды, а записанный
статус: повторяют запись после ответа MCP, а не выдумывают ссылку.

### `ssot-verify`
Сверка применённой критичности с фактическим SSoT: `ssot_verify_change` после
`ssot_apply_changes` и `ssot_wait_master`.

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС |
| `--verify-json <path\|->` | ответ MCP `ssot_verify_change` (путь или stdin) |
| `--matched` | короткая форма: сверка прошла (без JSON) |
| `--ref <ref>` | провенанс проверки (например `ssot_get@<version>`) |
| `--commit <sha>` | коммит мастер-ветки SSoT, на котором проверено |
| `--actual <enum>` | фактический `severity.type` из ответа |

Пишет `ssot_snapshot.verified` (`matched`, `ref`, `commit`, `actual`,
`checked_at`). Расхождение фактического значения с паспортом — `ERROR` (код
1): «применено ≠ рассчитано» не замалчивается.

**Устаревшие флаги.** Клон, ветка и MR больше не создаются скиллом: `--apply`,
`--push`, `--clone`, `--branch`, `--task`, `--passport-mr-url`, `--update-mr`,
`--force-duplicate` у команд SSoT дают явную ошибку
(`ERROR: --<флаг>: SSoT теперь только через MCP: ssot-plan → ssot_entity_open →
ssot_form_save → ssot-record`, код 2), а не тихо
игнорируются. MR создаёт `ssot_form_save`, описание собирает SSoT-приложение;
наши данные — только поля `severity.type`/`severity.confirmation`.

**Гейт валидации (R18).** `publish`, `ssot-plan` и `ssot-record` (и MCP-шаг
`ssot_form_save` за `ssot-plan`) отказывают с кодом 1, если `validate` по ИС даёт
ERROR, `criteria_fingerprint` в `CRITICALITY.md` не совпадает с текущими
критериями или в паспорте/`INFORMATION.yaml` остались незакрытые blocking-входы.
Вывод называет причину и следующий шаг (`make validate`,
`make start-apply IS=<код> FORCE=1`, `make check IS=<код>`). Осознанный обход —
`--force` (`FORCE=1`): печатает `WARN` и дописывает строку в
`is/<код>/.gate-overrides.log`.

### `publish`
| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС |
| `--task <Jira-ключ>` | задача; по умолчанию `jira_task` из реестра/`is.yaml`. Ключа нет — ищется `E001-<N>` в имени текущей ветки и последних коммитах (`WARN` + использование), иначе `ERROR` с подсказкой |
| `--branch <имя>` | по умолчанию `feature/<task>[-<контур>]` |
| `--dochub <path>` | клон dochub (по умолчанию `dochub/`) |
| `--clone` | клона нет — склонировать по URL из `criteria.external_refs.repos.dochub` (`git clone --depth 1`). Без `--dochub` и без клона публикация клонирует **сама** (`WARN`, поддержаны `https://` и `ssh://git@host:port/...`); явный `--dochub` без клона — подсказка с командой |
| `--apply` | записать файлы, создать ветку и коммит |
| `--update` | с `--apply`: обновить существующую ветку вместо новой |
| `--push` | с `--apply`: запушить ветку (создание MR) — только по подтверждению. После успешного пуша ссылка MR пишется в `.publish/<код>-MR.url` (клон) и `.dochub/<код>-MR.url` (проект): `start` подставляет её в `actions.mr_link`, ручное копирование в тред не нужно |
| `--force` | обойти гейт валидации: `WARN` + запись в `is/<код>/.gate-overrides.log` |
| `--force-duplicate` | осознанно создать второй MR, когда по этому паспорту уже есть открытый: `WARN` + запись в `is/<код>/.gate-overrides.log` (`FORCE_DUPLICATE=1`) |

**Enum в паспорте.** Перед записью `object_consumers_type` и
`object_outage_impact` сверяются со схемой dochub: точное значение — как есть;
смысловое совпадение (без скобок/регистра/пунктуации) — каноническое значение
схемы + `WARN`; нет совпадения — `ERROR` со списком допустимых значений.

**Проверка дублей MR.** Перед созданием ветки/коммита `publish` (и
`publish-apply`) запрашивает `GET {gitlab}/api/v4/projects/<path>/merge_requests
?state=opened&search=<код>` и оставляет MR, в `changes` которых есть файл
паспорта этой ИС. Найденный дубль — отказ с кодом 1: номер MR, заголовок, автор,
ветка, дата и таблица расхождений «поле | в MR | в расчёте | источник расчёта»
(провенанс — из `INFORMATION.yaml`). Та же таблица попадает в
`.publish/<код>-MR.md` (раздел 10). `--update` проверку не выполняет — он
обновляет именно существующий MR. Без `GITLAB_TOKEN` печатается `WARN`
«проверка дублей MR не выполнена» и дешёвый фолбэк по веткам клона
(`git branch --remotes --list '*<код>*'`). GitLab-инстанс и путь проекта берутся
из `remote.origin.url`, фолбэк — `criteria.external_refs.repos.dochub.
gitlab_base` / `gitlab_project`.

Поведение:

- клона нет — печатается точная команда
  `клонировать: git clone <URL> <путь>`; URL берётся из `--dochub-url` →
  `catalog.yaml → dochub_url` → `catalog.yaml → dochub.url` →
  `criteria.dochub.url`. URL нигде не задан — вместо команды подсказка
  добавить `dochub_url` (искать репозиторий вручную не нужно);
- `--update` работает **только** для ветки, существующей на `origin`
  (`refs/remotes/origin/<branch>`): локальная ветка без пуша не обновляется,
  команда останавливается с `ERROR: ветка <branch> не найдена на origin`.
  Новая ветка — запуск без `--update`;
- `--reuse-local` — режим для локальной ветки, которой на `origin` нет:
  ветка не пересоздаётся (`git checkout`, история не переписывается), целевые
  файлы пишутся, затем `git diff --cached`. Пусто — печатается `unchanged`,
  код 0, коммит не создаётся (идемпотентный повтор). Есть изменения — коммит
  поверх локальной ветки. `fetch` в этом режиме не выполняется: сеть не нужна.
  Ветка уже на `origin` — отказ с подсказкой `--update`; с `--update`
  несовместим;
- `.publish/<код>-MR.url` создаётся **только** при `--push` (это ссылка на
  созданный MR). `--apply` без `--push` оставляет ветку и коммит локально.
  Ссылка нужна треду `handoff`; основанием SSoT-изменения она больше не
  служит — SSoT-форма берёт данные из карточки ИС.

### `handoff` / `handoff-apply`

Последний этап конвейера: сообщение в `#Criticality_assessment`. Текст
собирается **в момент вызова** из текущего состояния (паспорт, `catalog.yaml`,
`mrUrl` из `ssot_form_save` → `.ssot/<код>-MR.url`, dochub-MR →
`.publish/<код>-MR.url`, `INFORMATION.yaml` → `facts`/`notes`), а не берётся из
`actions/rocketchat-message.md`, который рендерится на `start`.

| Флаг | Значение |
|------|----------|
| `--is <код>` | ИС (обязателен) |
| `--date YYYY-MM-DD` | дата сбора сообщения |
| `--write` | (`handoff`) сохранить точный текст в `actions/handoff-preview.txt` |
| `--allow-incomplete` | разрешить текст с `⛔ не заполнено` (по умолчанию — код 1) |
| `--confirm` | (`handoff-apply`) явное подтверждение публикации; без него — отказ, код 1 |
| `--force-resend` | (`handoff-apply`) переотправить, даже если тред уже опубликован |

Поведение `handoff`:

- печатает блок `=== СООБЩЕНИЕ ДЛЯ ТРЕДА #Criticality_assessment === … ===
  КОНЕЦ СООБЩЕНИЯ ===`, затем `Длина: N символов` и получателя; отправка —
  только по `--send auto` (MCP, при отказе — REST), `--send manual` оставляет
  пакет человеку, `--dry-run` ничего не отправляет и (без `--write`) не пишет;
- остались `⛔` — печатает список незаполненных полей и `ERROR: отправка
  невозможна`, код 1; продолжение — только `--allow-incomplete`;
- гейт не пройден (`BLOCKED`) — сообщение не собирается, код 1.

Поведение `handoff-apply` (тонкая обёртка `handoff --send auto --transport api`):

- креды: `ROCKETCHAT_TOKEN`/`ROCKETCHAT_USER_ID` (алиасы `RC_*`, `STRELKA_*`);
  нет кредов — код 1, ничего не отправлено и не записано;
- `roomId` — `GET /api/v1/channels.info?roomName=Criticality_assessment` (id не
  хардкодится);
- предусловия общие с `handoff`: нет `⛔` в тексте (иначе `--allow-incomplete`),
  `validate` без `ERROR`, паспорт на месте;
- публикация — один `POST /api/v1/chat.postMessage` с `{roomId, text}`;
- идемпотентность общая с `handoff`: перед POST ищется своё сообщение в канале
  (дедупликация по `roomId`), а `catalog.yaml → handoff_status: published` +
  `thread_link` запрещают повтор («уже опубликовано: <ссылка>», код 1);
  осознанная переотправка — `--force-resend`;
- после успеха: `catalog.yaml → handoff_status: published`, `thread_link`,
  `approve_link`, `transport_used`, `published_at`; паспорт НЕ перегенерируется —
  печатается следующая команда (`make finalize IS=<код>`).

Коды: 0 — успех, 1 — нет подтверждения, `⛔`, ошибка сети/прав, гейт не пройден,
сообщение уже опубликовано.

## Make-цели

Полный список — `make help` (`make help-fast` — без чтения состояния). Значимые
переменные: `IS=`, `FORCE=1`, `DATE=`,
`NO_CLONE=1` (только клоны сервисов и `next-step`; на SSoT не влияет),
`DRY=0`, `DIFF=1`, `APPLY=1`, `PUSH=1`, `TASK=`, `NO_REQUIREMENTS=1`,
`JSON=1`, `ANSWERS=`, `REASON=`, `EXCLUDE_SCOPE=`, `ENTITY_JSON=`, `TEAM_JSON=`,
`MR_URL=`, `VERSION=`, `SAVE_JSON=`, `STATUS_JSON=`, `VERIFY_JSON=`.

`make ask` — план вопросов, `make ask-apply` — запись `ASK.md` (без `--apply`
план печатается в stdout), `make ask-answers IS=... ANSWERS=<файл>` — приём
ответов в `DATA-REQUIREMENTS.yaml` (плюс `REASON=`, `EXCLUDE_SCOPE=`).

`make next-step [IS=<код>]` — следующий шаг конвейера (та же логика, что в
подсказке после каждой команды): с `IS=` — одна команда для одной ИС, без него —
список по всем ИС проекта; `NO_CLONE=1` — не проверять клоны (офлайн).

`make research IS=<код>` — сбор кандидатов в Confluence (`INPUT=<вход>` — только
один вход, `ALL=1` — все ИС); `make verify-titles [IS=<код>] [FIX=1]` — сверка
заголовков (R19); `make verify` — все гейты одним прогоном (см. `### verify`).

`make contacts IS=<код> TEAM_JSON=<файл|->` — таблица групп и блок, который был
бы записан (dry-run); `APPLY=1` — запись секции `contacts`; `JSON=1` — машинная
форма. Источник — ответ MCP `ssot_team`, переданный через `TEAM_JSON`.

Составные входы (`axes_scores`, `cia`) записываются в лист под-осями
(`value: {legal: …, economic: …, reputational: …, client: …}` /
`value: {c: …, i: …, a: …}`) — в той форме, которую принимает `enrich`.
После записи лист перечитывается и каждый принятый вход проверяется теми же
валидаторами, что `enrich`; если значение не легло в лист — `ERROR: вход <имя>
принят, но значение не записано — это дефект инструмента`, код `1`, лист
возвращается в состояние до записи, «Принято» не печатается.

`make publish` — план; запись — `make publish-apply` (не `make publish APPLY=1`).
`make finalize IS=<код> APPROVE_LINK=<URL>` — финализация одной командой
(`ASSIGNED_DATE=`, `REVIEW_DATE=`, `CRITICALITY=`, `DRY=1`; либо
`ARGS="--approve-link <URL> --dry-run"` для CLI-формы).
SSoT — четыре цели без клона и git: `make ssot-import IS=<код>
ENTITY_JSON=<файл|-> [TEAM_JSON=<файл|->]` — снимок карточки в
`INFORMATION.yaml`; `make ssot-plan IS=<код> [FORCE=1]` — план и
`.ssot/<код>-apply-plan.json`; `make ssot-record IS=<код> MR_URL=<url>
[VERSION=] [SAVE_JSON=] [STATUS_JSON=]` — результат `ssot_form_save`;
`make ssot-verify IS=<код> VERIFY_JSON=<файл|->` — сверка после применения.

`make handoff IS=<код> SEND=auto` — отправить тред (MCP, при отказе — REST);
`SEND=manual` — оставить пакет вручную; `TRANSPORT=mcp|api` — принудительный
транспорт; `DRY_RUN=1` — предпросмотр, `FORCE_RESEND=1` — обход
идемпотентности. Предпросмотр именно `DRY_RUN=1`: `make handoff … --dry-run`
перехватывает сам make (`-n`, только печать рецепта), а не скилл.
`make handoff-result IS=<код> MESSAGE_URL=<ссылка>` —
результат MCP; `FAILED="причина"` — отказ MCP с REST-фолбэком. `ARGS="…"` —
CLI-форма.

`make handoff-apply IS=<код> CONFIRM=1` — отправка в канал **необратима**:
без `CONFIRM=1` цель падает с `ERROR` до любого сетевого вызова (`FORCE=1` —
`--force-resend`, `ALLOW_INCOMPLETE=1` — отправка текста с ⛔). Команда — тонкая
обёртка того же пути, что `handoff --send auto --transport api`: идемпотентность
и дедупликация общие, после `published` — отказ.

Булевы флаги Makefile включаются **только** значением `1`
(`$(if $(filter 1,$(VAR)),…)`): `PUSH=0`, `FORCE=0`, `CONFIRM=0` — выключено,
как и пустое значение. Флаги-значения (`TASK=`, `BRANCH=`, `SEND=`, …) — как есть.

## Коды возврата

| Код | Значение |
|-----|----------|
| `0` | успех (в том числе `check` при всех `OK`/`SKIPPED`) |
| `1` | `BLOCKED`, `ERROR` валидации/данных, `incomplete` у `score` |
| `2` | ошибка аргументов (например `--push` без `--apply`); `make` отдаёт 2 при ненулевом коде цели |

`check --diagnostic` и `check-diag` печатают `BLOCKED`, но возвращают `0`.

## Примеры

```bash
make init                                   # каркас проекта в пустом каталоге
make scaffold IS=demo.mm                    # папка ИС + записи в catalog.yaml и is.yaml
make prepare                                # план подготовки (dry-run)
make contacts IS=demo.mm                    # контакты TA/TL из SSoT (dry-run)
make contacts IS=demo.mm APPLY=1            # записать секцию contacts в INFORMATION.yaml
make check IS=demo.mm                       # гейт; при BLOCKED — лист требований
make ask IS=demo.mm                         # план вопросов по незакрытым входам
make ask IS=demo.mm JSON=1                  # то же машинной формой (по элементу на вопрос)
make ask-answers IS=demo.mm ANSWERS=is/demo.mm/ANSWERS.yaml  # ответы → лист
make enrich-apply IS=demo.mm                # принять заполненный лист
make start IS=demo.mm DIFF=1                # diff без записи
make start-apply IS=demo.mm FORCE=1         # записать артефакты
make validate                               # 0 ERROR по паспортам и реестру
make finalize IS=demo.mm APPROVE_LINK=https://rocketchat.samokat.ru/channel/Criticality_assessment?msg=x  # подтверждение SRE + гейты
make finalize IS=demo.mm ARGS="--approve-link https://rocketchat.samokat.ru/channel/Criticality_assessment?msg=x --dry-run"  # план без записи
make publish IS=demo.mm TASK=E001-1         # план публикации паспорта в dochub
make publish-apply IS=demo.mm TASK=E001-1   # ветка и коммит в клоне dochub
make ssot-import IS=demo.mm ENTITY_JSON=/tmp/ssot_get.json  # снимок карточки ИС в INFORMATION.yaml
make ssot-plan IS=demo.mm                   # план применения severity + шаги MCP
make ssot-record IS=demo.mm MR_URL=https://git.ecom.tech/ssot/-/merge_requests/1  # mrUrl из ssot_form_save
make ssot-verify IS=demo.mm VERIFY_JSON=/tmp/ssot_get-after.json  # сверка после ssot_apply_changes
make handoff IS=demo.mm DRY_RUN=1           # предпросмотр: канал, транспорт и почему он выбран; ничего не отправлено
make handoff IS=demo.mm SEND=auto           # отправить: MCP, при отказе — REST API
make handoff IS=demo.mm SEND=auto MCP_TIMEOUT=60  # срок ожидания MCP — 60 с
make handoff IS=demo.mm RESUME=1            # MCP не ответил: проверить срок и уйти в API
make handoff IS=demo.mm SEND=manual         # не отправлять: пакет остаётся pending_manual
make handoff-result IS=demo.mm MESSAGE_URL=https://rocketchat.samokat.ru/channel/Criticality_assessment?msg=x  # результат MCP
make handoff-result IS=demo.mm FAILED="MCP недоступен"  # отказ MCP → REST-фолбэк
make handoff-result IS=demo.mm ALLOW_DUPLICATE_RISK=1 FAILED="MCP timeout"  # аварийно: без поиска сообщения
```

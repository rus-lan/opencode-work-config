---
title: "Воркфлоу: criticality-gen"
purpose: Фазы конвейера и гейты между ними.
audience: [ai-agent]
read_when: [запускаете цикл оценки, непонятно, какая фаза следующая]
updated: 2026-11-24
status: actual
related: [rules.md, commands.md, checklist.md, interactive.md, search.md]
---

# Воркфлоу: criticality-gen

Конвейер от списка ИС в `is.yaml` до подтверждённого паспорта в dochub. Каждая
фаза закрывается только своим гейтом; провал гейта останавливает конвейер.

Канонический порядок:

```text
init → prepare → contacts → check → collect → сбор (SSoT/Confluence/Grafana) → services → check
     → ask → enrich → score → start → validate → publish (dochub MR) → ssot-import → ssot-plan
     → MCP: ssot_entity_open → ssot_form_fields → ssot_ui_select/ssot_ui_fill → ssot_form_save
     → ssot-record → MCP: ssot_wait_version → ssot-verify → handoff → finalize
```

Термины разграничены: **`publish`** — публикация паспорта в **dochub** (MR);
**`ssot`** — обогащение **SSoT** через MCP-форму (MR создаёт SSoT, `mrUrl`
возвращает `ssot_form_save`); **`handoff`** — тред согласования в
**`#Criticality_assessment`** (ссылается на оба MR). «Публикация в
`#Criticality_assessment`» — это всегда `handoff`, а не `publish`.

После `handoff` человек (или агент по явному разрешению) делает MCP:
`ssot_mr_approve(confirm:true)` → `ssot_apply_changes(confirm:true)` →
`ssot_wait_master`.

**`handoff` — последний этап конвейера.** Он запускается только после того, как
паспорт опубликован (фаза 8) и SSoT обогащён (фаза 9): сообщение собирается из
финального состояния и ссылается на оба MR. Публикация в тред — ОДНО сообщение,
и только после того, как человек увидел текст целиком и ответил «Публиковать»
(`make handoff IS=<код> SEND=auto`; `make handoff-apply IS=<код> CONFIRM=1` — тот же
путь только по REST).

Обозначения в путях: `IS` — код ИС (`<name_is>.<контур>`, например `erm.mm`),
`COMPONENT` — имя компонента. Папка ИС — плоская: `is/IS/` (например `is/erm.mm/`).

## Сводная таблица фаз

| # | Фаза | Команда | Выход | Гейт | Кто выполняет |
|---|------|---------|-------|------|---------------|
| 0 | `init` | `make init` | `is.yaml`, `catalog.yaml`, `INDEX.md`, `is/` | файлы существуют и разбираются | скрипт |
| 1 | `prepare` | MCP `ssot_get` → `make ssot-import ENTITY_JSON=-`, затем `make prepare` / `make prepare-apply`, затем MCP `ssot_team` → `make contacts IS=... APPLY=1` | `INFORMATION.yaml` (включая `ssot_snapshot` и `contacts`), `apps/IS/` | JSON сущности импортирован, `INFORMATION.yaml` создан, `contacts` собраны из `ssot_team` | скрипт |
| 2 | `check` (первичный) → `collect` → `research` (сбор) → `services` → `check` (сценарный) → `ask` → `enrich` | `make check` → `make requirements IS=...` + `make collect-apply IS=...` → сбор (SSoT/Confluence/Grafana) → `make services-apply IS=...` → `make check` → `make ask IS=...` → `make enrich-apply IS=...`; правка `INFORMATION.yaml` | `DATA-REQUIREMENTS.*`, `RESEARCH-PLAN.md`, `SERVICE-FINDINGS.md`, `ASK.md`, заполненные `criteria_inputs` и `facts` | у каждого значения есть `source` и `status: confirmed`; лист принят `enrich` | человек + скилл |
| 2c | `services` | `make services IS=...` (план) / `make services-apply IS=...` (запись) | `is/IS/SERVICE-FINDINGS.md` | клоны читаются, каждый сервис из `components[]` попал в таблицу, в «не найдено» или в «пропущенные» (`lifecycle: closed`), ничего не собрано и не запущено | скрипт |
| 2d | `ask` | `make ask IS=...` (план) / `make ask-apply IS=...` (запись) / `make ask-answers IS=... ANSWERS=<файл>` (приём ответов) | `is/IS/ASK.md`, `is/IS/CANDIDATES.yaml` → `ANSWERS.yaml` → значения в `DATA-REQUIREMENTS.yaml` | на каждый незакрытый вход — вопрос с дословным enum и маршрутом «где взять»; каждый ответ проходит валидаторы гейта; `INFORMATION.yaml` не изменён ни на байт | агент (вопросы) + человек (ответы) |
| 3 | `check` | `make check` (гейт) / `make check-prepare` (подготовка + гейт) | таблица `ИС / сценарий / blocking n/m / advisory n/m / вердикт / причина` | все строки `OK` | скрипт |
| 4 | `score` | `criticality.py score --is` | уровень + `score_trace` | метод зафиксирован, статус не `incomplete` | скрипт |
| 5 | `start` | `make start IS=erm.mm DIFF=1` → `start-apply FORCE=1` | паспорт, `CRITICALITY.md`, `GENERATION.md`, `actions/*` | рендер без `TemplateError` | скрипт |
| 6 | `actions` | флаги `TASK=1` / `CONFLUENCE=1` / `MESSAGE=1` | Jira-задача, Confluence-страница, текст сообщения | подтверждение человека на каждое внешнее действие | человек + MCP |
| 7 | `verify` | `make validate`, `make docs-check`, `make criteria-check`, `make selftest` | 0 ERROR | все четыре цели — `OK` | скрипт |
| 8 | `publish` | `make publish IS=... TASK=...` (план) → `make publish-apply IS=... TASK=...` | паспорт в dochub, импорт в `_root.yaml`, ветка + коммит, `.publish/<код>-MR.md` | уровень в enum dochub, ключ и путь совпадают с соглашением, дерево клона чистое, коммит: паспорт (+ `_root.yaml` при первой публикации) | скрипт |
| 9 | `ssot` | `make ssot-plan IS=...` → MCP-форма (`ssot_entity_open` → `ssot_form_fields` → `ssot_ui_select`/`ssot_ui_fill` → `ssot_form_save`) → `make ssot-record IS=... MR_URL=<mrUrl>` → `make ssot-verify IS=... VERIFY_JSON=-` | `INFORMATION.yaml → ssot_snapshot.severity` (цель), `mrUrl` и `version` из `ssot_form_save`, доказательство `ssot_verify_change` | `severity.type` — enum SSoT (`levels.ssot_enum`), `confirmation` = `approve_link`, изменены только эти два поля формы base, MR создан SSoT, значение на ветке MR подтверждено `ssot_verify_change` | агент (MCP) + скрипт (`ssot-plan`/`ssot-record`/`ssot-verify`) |
| 10 | `handoff` | `make handoff IS=... SEND=auto` (MCP, при отказе — REST) / `make handoff-result` | тред в `#Criticality_assessment` со ссылкой на dochub-MR и SSoT-MR; `catalog.yaml`: `thread_link` + `approve_link` (= `thread_link`) | тред отправлен; отдельного подтверждения в треде не ждём — гейт это мерж MR | скрипт |
| 11 | `finalize` | `make finalize IS=...` (`APPROVE_LINK=` — только override) | `catalog.yaml → systems[IS]`: `approve_link` (= `thread_link` при `handoff_status: published`), `assigned_date` (= `generated_at`), `review_date` (= `generated_at` + период), `criticality`, `criticality_ssot`, `status: confirmed`; артефакты и `INDEX.md` перегенерированы | `validate`/`index`/`verify` зелёные; ERROR — откат записанных полей; повторный вызов идемпотентен (даты не сдвигаются) | скрипт |

### Даты оценки: привязаны к дате генерации

`assigned_date` и `review_date` — даты **оценки**, а не моменты работы человека
над паспортом. Обе считаются от даты генерации (`generated_at`, параметр
`--date`, по умолчанию сегодня):

- `assigned_date` = дата генерации;
- `review_date` = дата генерации + `review_period_months` (по умолчанию 12).

Даты фиксируются в трёх точках, и все три используют одно правило
(`review_date_from_generation`):

1. `scaffold` — сразу при появлении записи в `catalog.yaml` (и в каркасе
   паспорта), чтобы ИС не жила без дат до `finalize`;
2. `start` (builder) — в паспорт; явное значение реестра/прежнего паспорта —
   override, перегенерация даты не сдвигает;
3. `finalize` — в реестр (флаг → реестр → паспорт → `generated_at`).

`publish` не выбрасывает пустые даты: если в паспорте их нет, они выводятся из
`catalog.yaml` / `generated_at` (иначе обе даты не попадали бы в репозиторий
dochub). Пустое значение уходит в dochub только когда вывести дату не из чего.

## Фаза 0 — init

| Поле | Значение |
|------|----------|
| Вход | шаблоны скилла: `templates/is.example.yaml`, `templates/catalog.yaml`, `templates/INDEX.md` |
| Действие | `make init` (или `criticality.py init --force`) |
| Выход | `is.yaml` (список ИС и `ssot.url`), `catalog.yaml` (реестр), `INDEX.md` (каркас), папка `is/` |
| Гейт | файлы существуют, YAML разбирается, `ssot.url` непуст, реестр валиден |
| Кто выполняет | скрипт |
| Что делать при провале | показать, как заполнить `is.yaml` и `catalog.yaml`; существующие файлы не перезаписывать (`is.yaml` — только `--force`) |

Свежий `is.yaml` **пуст**: активных ИС в шаблоне нет, чтобы проект не начинался с
выдуманных данных. Это нормальное состояние: `check` печатает «нет ИС» (не
`BLOCKED`), `validate` — `0 ERROR, 0 WARN`, а подсказка ведёт к `make scaffold
IS=<код>` — он создаёт папку ИС и дописывает код в `is.yaml`.

## Фаза 1 — prepare

| Поле | Значение |
|------|----------|
| Вход | `is.yaml` (список ИС, `ssot.url`, переопределения `product` / `teamName`), ответ MCP `ssot_get` |
| Действие | MCP `ssot_get(group="information-systems", entity=<код>)` → `make ssot-import IS=... ENTITY_JSON=-` (снимок в `INFORMATION.yaml → ssot_snapshot`); `make prepare` — план; `make prepare-apply` — запись; затем MCP `ssot_team(code=<team>)` → `make contacts IS=... APPLY=1` |
| Выход | `is/IS/INFORMATION.yaml` (включая секции `ssot_snapshot` и `contacts`), клоны компонентов в `apps/IS/COMPONENT` |
| Гейт | `INFORMATION.yaml → ssot_snapshot.base` непуст (иначе `ERROR: нет данных SSoT`); `INFORMATION.yaml` создан; в итоговой таблице колонка `unreadable` = 0 (каждый нечитаемый `ref` напечатан как `WARN <ref>: <ошибка>`) |
| Кто выполняет | агент (MCP-чтение) + скрипт (`ssot-import`, `git clone` / `git pull` компонентов) |
| Что делать при провале | `ssot_get` вернул `auth_required` или ошибку — `ssot_status`, при необходимости `ssot_login`; снимка нет — `ERROR: нет данных SSoT`, `INFORMATION.yaml` не обновляется; компонент не клонируется — зафиксировать `clone_status: error` и продолжить с остальными. `git_repository` — веб-страница (`/tree/`, `/blob/`), а не git-URL: SKIP + WARN «не git-репозиторий», компонент в списке пропущенных, прогон не блокируется |

Ростер команды приносит MCP `ssot_team(code=<team>)` (команда — `catalog.yaml →
team`), его пишет `make contacts IS=... TEAM_JSON=-` (или `ssot-import
--team-json`); `prepare` этот блок переносит без изменений — клон SSoT не
читается.
Отдельная цель `make contacts IS=... APPLY=1` перезаписывает только эту секцию
и нужна, когда ростер команды изменился (пересборка `INFORMATION.yaml` целиком
не требуется). Секция `contacts` — копия ростера: `groups[].name` — роль
(`ta`, `tl`, `sa`, …), `groups[].members[]` — логины; упоминание в RocketChat —
`@<login>` (соответствия login → ФИО в SSoT нет). Ростера нет (`ssot_team` не
передан) — `contacts` печатает инструкцию и код 2, `prepare` не падает.

`prepare` не перезаписывает ручные секции (`criteria_inputs`, `facts`,
`conflicts`, `notes`) — они переносятся в перегенерированный
`INFORMATION.yaml` дословно, поэтому повторный `prepare` после ручной правки
не меняет `sha1sum` файла. Это контракт, а не случайность.

Если существующий `INFORMATION.yaml` не разобран, `prepare` печатает `ERROR` и
**не перезаписывает файл** (иначе ручные секции потерялись бы). Перезапись —
только `--force-overwrite` (`make prepare-apply FORCE_OVERWRITE=1`), осознанно.

**Без снимка SSoT файл не пишется.** Если `INFORMATION.yaml → ssot_snapshot`
пуст, `prepare --apply` печатает подсказку `MCP ssot_get → ssot-import` и
`ERROR: нет данных SSoT — ИС <код> не импортирована (INFORMATION.yaml не
обновлён)`, возвращая ненулевой код: автоматические секции иначе стали бы
пустыми. Снимок приносит только MCP (`ssot_get`), клон SSoT не читается.
Порядок на свежем проекте: `ssot-import` сам создаёт `INFORMATION.yaml` из
`templates/INFORMATION.yaml` и пишет снимок, затем `prepare --apply`
пересобирает секции, **сохраняя провенанс** (`source: mcp`, `commit`,
`version`, `imported_at`).
**Секция, отсутствующая в SSoT, сохраняется:** в файле остаётся прежняя версия, печатается
`WARN: секция <имя> отсутствует в SSoT — сохранена прежняя версия (N записей)`;
очистить её можно только `--allow-empty-sections`. Кода ИС нет в снимке — это
ошибка (`ERROR: нет данных SSoT — ИС <код> не импортирована`, код 1,
файл не создаётся): пустой скелет маскировал бы опечатку в коде. Перед записью
создаётся `INFORMATION.yaml.bak-<YYYYMMDDTHHMMSSZ>` (UTC, при коллизии в секунду
суффикс `-1`/`-2`, ротация `--backup-keep N`, по умолчанию 10;
`--no-backup` отключает), запись атомарная (`tempfile` + `fsync` + `os.replace`).

Перед `git pull --ff-only` клонов компонентов выполняется
`git -C <dir> fetch --prune`; ветка не переключается — `checkout`/`reset`/`clean`
запрещены git-allowlist'ом (`clone`, `pull`, `fetch`, `rev-parse`, `log`,
`status`, `show`, `diff`, `ls-remote`), попытка другой подкоманды — `ERROR:
git-команда '<x>' запрещена скиллом (allowlist: …)` и ненулевой код. Все вызовы
git идут через один хелпер `_run_git` (он вызывает `_git_only`); прямых
`subprocess` с git нет — проверяет `make selftest`. Схема `git_repository`
валидируется до git-вызова: только `https://`, `ssh://`, `git@host:path`;
`file://`, `http://`, локальные пути — `ERROR: недопустимая схема
git_repository: <значение> (допустимы https://, ssh://, git@)`, код 1. Если pull
невозможен — `WARN`, клон не ломается. `--no-clone` (`NO_CLONE=1`) отключает
git-операции по компонентам. `INFORMATION.yaml` — версионируемый ручной слой: он
коммитится в git; `apps/`, `is.yaml` — нет.

## Фаза 2 — enrich (дозаполнение)

| Поле | Значение |
|------|----------|
| Вход | `INFORMATION.yaml`, `ssot_snapshot`, Confluence-страницы ИС, дашборды Grafana, GitLab, ответы людей; при `BLOCKED` — `DATA-REQUIREMENTS.yaml` |
| Действие | `make requirements IS=...` (лист) → `make collect-apply IS=...` (план сбора) → сбор по плану (SSoT → Confluence → Grafana) → `make services-apply IS=...` (`SERVICE-FINDINGS.md`) → `make check IS=...` → `make ask IS=...` (план вопросов) → `make enrich IS=...` (проверка) → `make enrich-apply IS=...` (запись в `criteria_inputs`) |
| Выход | `INFORMATION.yaml` с полным набором входов; `DATA-REQUIREMENTS.md`/`.yaml`, `RESEARCH-PLAN.md` и `ASK.md` (пока есть незакрытые входы) |
| Гейт | у каждого непустого значения есть `source`; `status` ∈ `missing \| derived \| confirmed`; лист принимается только с `source: {type, ref}` и `status: confirmed` |
| Кто выполняет | человек (значения) + скилл (чтение SSoT/Confluence, сверка, запись) |
| Что делать при провале | не додумывать: `null` + `status: missing` и запрос адресату (R1, R10); нет источника — `make exclude IS=... REASON="..."` (R11) |

### 2a. Лист требований и план сбора (`collect`)

`check` и `start` при `BLOCKED` сами пишут `is/IS/DATA-REQUIREMENTS.md`
и `.yaml`; `make requirements IS=...` пересобирает лист, `APPLY=1` — записывает.
В листе перечислены **все незакрытые** входы (blocking выбранного сценария +
detailed-входы вне его blocking-набора)
с полями «что это → зачем → где взять → у кого → как подтвердить» и готовым
фрагментом `criteria_inputs` для `INFORMATION.yaml`. Лист идемпотентен: дата
берётся из `--date` → `catalog.review_date` → `history[-1].date`, `now()` нет.
Лист предупреждает: заполнение любого advisory detailed-входа (`axes_scores`,
`cia`, `time_to_impact`) переключает ИС на сложный сценарий и требует
`time_to_impact` — тогда `BLOCKED` называет переключение, а не только
недостающий вход.
Когда незакрытых входов не осталось, файлы листа удаляются — «выполнено» не
пишется.

**`check` безопасен для заполненного листа:** значения сливаются (`value`,
`source`, `status`, `bucket`/`unit`/`notes`), вычисляемые
`switches_scenario`/`scenario_note` пересчитываются по критериям. Сливаются
только поля, ещё не принятые в `INFORMATION.yaml`: закрытое поле (значение +
`status: confirmed`/`derived`/`legacy`) из листа исчезает — лист производен от
`INFORMATION.yaml`, а не накопителен. Порядок не
важен — заполнять лист можно до, между и после прогонов `check`; принимает
значения по-прежнему `enrich`. Если рендер теряет заполненные значения, файл не
перезаписывается: пишется `.new` и команда возвращает ненулевой код. Read-only
прогон без касания листа — `NO_REQUIREMENTS=1`.

#### План сбора (`collect`)

`make collect IS=...` (план) / `make collect-apply IS=...` (запись) считает гейт
и рендерит `is/IS/RESEARCH-PLAN.md`: какие страницы Confluence открыть (с
`page_id` из снимка `INFORMATION.yaml → ssot_snapshot.links`, `catalog.confluence_page_id`,
`criticality_source_page_id`, `dr_page_id`, `decision_log_page_id`), что на них
искать, какие дашборды Grafana проверить (папка продукта E001 + компоненты-шлюзы),
какие запросы PromQL выполнить и кто подтверждает каждое значение. Пустые
`dr_page_id`, `criticality_source_page_id` и `decision_log_page_id` в
`catalog.yaml` не молчат: план печатает по строке `⛔` на каждое незаполненное
поле — иначе таблица входов адресует значение на страницу, которую план не
знает. План идемпотентен (дата — `--date` → `catalog.review_date`), при
отсутствии незакрытых входов удаляется, исключённые ИС (`SKIPPED`) пропускаются.
Маршруты, формулы и ловушки — [data-sources.md](data-sources.md).

План содержит ещё два раздела, которые печатаются для каждой ИС:

- **Product scope — процессы ИС (E2E).** Источник `facts.e2e_processes` —
  не дерево ИС, а Product scope продукта: страница
  `catalog.yaml → product_scope_page_id` (или
  `systems.<код>.product_scope_page_id`), её функциональные области с меткой
  `functional-area`, в глоссарии которых ИС названа колонкой «Код мастер-системы
  (опционально)», а процесс — «Сквозной бизнес-процесс (e2e)*». План печатает
  CQL `label = "functional-area" and space = currentSpace() and ancestor =
  <page_id>` и порядок чтения. Поле пустое — план печатает `WARN` и `⛔` с
  подсказкой, где взять `page_id` (JSON сущности продукта из `ssot_get` —
  дочерняя страница корня продукта с заголовком «<продукт> Product
  scope»). Раздел печатается и при закрытых входах расчёта: E2E-процессы нужны
  публикации независимо от гейта.
- **Глубокий поиск (tier 2).** По каждому незакрытому входу — готовые запросы
  tier 1 (код и название ИС, namespace шлюзов, группа GitLab, `grep` по SSoT) и
  tier 2 (код + термин входа, название + термин, CQL функциональных областей,
  дерево от архитектуры ИС, страница ИС и дети, DR-страница, журнал решений,
  команда + термин, логины владельцев из `contacts`, namespace + панель).
  Строки собираются из реальных значений ИС — заглушек вида `<код>` нет.
  Протокол и таблица «симптом → следующий запрос» — [search.md](search.md).

Оба раздела попадают в счётчик шагов: `collect` печатает
`шагов: N (…, Product scope 1, глубокий поиск 1)`.

### 2b. Сбор (`research`)

| Источник | Что берём | Как фиксируем |
|----------|-----------|---------------|
| Confluence | пользователи продукта, влияние при простое, SLA/RTO, сценарии отказа, ПДн, E2E-процессы (Product scope) | `source: {type: confluence, ref: '<page_id>, раздел <название>'}`, дословная цитата в `evidence` |
| Grafana | пик RPS шлюза → `peak_hour_load = peak_rps × 3600` | `source: {type: grafana, ref: 'dashboard uid=<uid>, panel <id>, expr: <PromQL>, окно 7d/30d'}` |
| Экспертно | `axes_scores`, `cia`, финансовые потери | `source: {type: manual, ref: '<роль: логин>'}`, `status: confirmed` |

**Два прохода.** Сбор идёт `tier 1` → `tier 2`: сначала точные идентификаторы
(код ИС, название, namespace шлюза, группа GitLab, `grep` по SSoT), затем
комбинации (код + термин входа, CQL функциональных областей, дерево от
архитектуры ИС, DR-страница, журнал решений, команда, логины владельцев).
Готовые запросы для каждого незакрытого входа печатает `collect` в разделе
«Глубокий поиск» `RESEARCH-PLAN.md`. Протокол, фиксация и таблица «симптом →
следующий запрос» — [search.md](search.md).

**Результат поиска фиксируется, а не запоминается.** Каждый вход получает
запись `is/IS/CANDIDATES.yaml → search.<вход>`: `shallow` (запросы tier 1),
`deep` (запросы tier 2), `done: true` (tier 2 выполнен) и `result` (что дал
поиск; «не найдено — …» тоже результат). Без `done: true` «не найдено» не
доказано: `ask` печатает `WARN глубокий поиск не зафиксирован для <вход>` и
ставит `deep_search_missing: true` в `--json`, а `validate` предупреждает по
blocking-входу без значения, без кандидатов и без записи `search`.

Из документов не выводятся `axes_scores` и `cia`: в источниках есть только
итоговый уровень, разбивки по осям и отметок C/I/A нет. Подставлять значения
«по аналогии с другой ИС» запрещено. Ловушки (ADF, rate limit, таймаут Grafana,
игнорируемый фильтр папки, datasource 404) — [failure-modes.md](failure-modes.md).

**Ветка провала гейта.** Tier 1 и tier 2 не дали ни значения, ни основания:

1. **blocking-вход** — `done: true` и `result: «не найдено — …»`, затем
   `make ask IS=...`: вопрос человеку с дословным enum и маршрутом «где взять».
   Догадка не вписывается, гейт остаётся `BLOCKED`. Значений нет и взять их
   негде — исключение ИС (`make exclude IS=... REASON="..."`), а не оценка
   «на глаз» (R11).
2. **advisory-вход** — та же запись `search`, но расчёт не блокируется: паспорт
   будет неполным, `validate` печатает `WARN`.
3. **основание без значения** — кандидат `value: null`, `confidence: weak`,
   `done: true`: человек вписывает значение вручную с этим основанием.
4. **запрос упал** (rate limit, ADF, таймаут) — это не «не найдено»: повторить
   по [failure-modes.md](failure-modes.md), `done` не ставить.

### 2c. Код сервисов (`services`)

| Поле | Значение |
|------|----------|
| Вход | `INFORMATION.yaml#components[]` (имя, `git_repository`), клоны `apps/IS/COMPONENT/` |
| Действие | `make services IS=...` — план; `make services-apply IS=...` — запись; при отсутствии клона выполняется `git clone`, при наличии — `fetch --prune` + `pull --ff-only`; `NO_CLONE=1` (`--no-clone`) git не вызывает — отсутствующие клоны идут в §2 |
| Выход | `is/IS/SERVICE-FINDINGS.md`: сервисы (репозиторий, ветка, `docs/`, `openspec/`, SLO-конфиг), пропущенные по `lifecycle`, цитаты «файл:строка» о назначении, нормативах, потоках и данных, таблица «вход → основание», перечень «не найдено» |
| Гейт | каждый компонент с `git_repository` попал в таблицу сервисов, в «не найдено» или в «пропущенные» (`lifecycle: closed`); ошибка клонирования зафиксирована, а не проглочена; ничего не собрано и не запущено |
| Кто выполняет | скрипт (чтение файлов + `git`) |
| Что делать при провале | нет доступа к репозиторию — передать человеку точную команду и запросить доступ; компонент не клонируется — `clone_error` в отчёте, остальные сервисы анализируются |

**Клоны — основная документация, но не источник значений.** Порядок источников:
клон (`docs/`, `openspec/`) → Confluence → SSoT. Из кода берётся **основание**
(цитата, что сервис делает, какие у него нормативы), а значение входа
по-прежнему подтверждает человек: `SERVICE-FINDINGS.md` не пишет в
`INFORMATION.yaml` и не закрывает входы. Отсутствие `docs/`, `openspec/` или
норматива фиксируется в §7 отчёта, а не замалчивается.

**Закрытые сервисы пропускаются.** Компоненты с `lifecycle: closed`
(`criteria.service_lifecycle.skip`) не клонируются и не анализируются; в отчёте
они собраны в разделе «Пропущенные сервисы» (§2) с причиной из
`service_lifecycle.skip_reason`, в сводке печатается `пропущено (lifecycle): N`.
Компонент без `lifecycle` анализируется как активный, но в отчёт попадает
строка `lifecycle не указан`.

**Инвариант чтения.** Внутри `apps/` разрешён только `git` из allowlist
(`clone`, `pull`, `fetch`, `rev-parse`, `log`, `status`, `show`, `diff`,
`ls-remote`) и чтение файлов; все вызовы идут через один хелпер `_run_git`,
который вызывает `_git_only` до запуска процесса, `--` отделяет пути от опций.
Схема `git_repository` проверяется до git-вызова (`https://`, `ssh://`,
`git@host:path`; иначе ошибка, код 1). Сборка, тесты, установка зависимостей и
запуск скриптов из клона запрещены — повторно фиксируется в отчёте (§8).
Найденное в коде не выдаётся за подтверждённое значение: R12–R14.

### 2d. Вопросы человеку (`ask`)

`make ask IS=...` собирает план вопросов по тем же незакрытым входам, что и
`check` (blocking первыми), и печатает `ASK.md` в stdout; `make ask-apply` —
записывает файл. Вопрос отвечает на четыре вещи: что это, какие значения
допустимы (enum раскрыт **дословно**, всеми значениями), что уже найдено и
откуда (кандидаты с провенансом) и что ответить.

| Поле | Значение |
|------|----------|
| Вход | `INFORMATION.yaml`, критерии (`inputs.required`, `enum_selection`, `time_buckets`), `is/IS/CANDIDATES.yaml` (если есть), `is/IS/SERVICE-FINDINGS.md` §6, JSON сущности из `ssot_get` (снимок `ssot_snapshot`), `DATA-REQUIREMENTS.yaml` |
| Действие | `make ask IS=...` (план) → `make ask IS=... JSON=1` (машинная форма) → `make ask-apply IS=...` (файл) → ответы человека в `ANSWERS.yaml` → `make ask-answers IS=... ANSWERS=<файл>` |
| Выход | `is/IS/ASK.md` (план вопросов), `is/IS/CANDIDATES.yaml` (кандидаты, заполняет агент или человек), `is/IS/ANSWERS.yaml` (ответы) и значения в `DATA-REQUIREMENTS.yaml` |
| Гейт | на каждый незакрытый вход есть вопрос с дословным enum и маршрутом «где взять»; `strong` без `source` понижен до `weak` с `WARN`; каждый принятый ответ проходит валидаторы гейта; `INFORMATION.yaml` не изменён |
| Кто выполняет | агент (собирает кандидатов и задаёт вопросы) + человек (отвечает) |
| Что делать при провале | ответ отклонён — код 1, лист не тронут, причина названа (`недопустимое значение`, `manual без source`, неизвестный вход); значений нет и взять негде — вариант «исключить ИС» с `--reason` |

**Кандидаты и провенанс.** Порядок: `CANDIDATES.yaml` (`strong`, проверено
человеком) → §6 `SERVICE-FINDINGS.md` («из кода», `weak`) → SSoT
`base.yaml`/`links.yaml` (`weak`). Кандидатов нет — вопрос печатает маршрут из
листа требований (страница Confluence, дашборд Grafana, роль). Кандидат из кода
— **основание**, а не значение: если цитата не содержит значения дословно,
вопрос предлагает вписать значение вручную с этим основанием. Ту же форму
(`value: null`) можно записать и в `CANDIDATES.yaml`: «основание найдено,
значения нет» — такой кандидат виден в плане как кандидат-основание, но
`choice: candidate` по нему отклоняется.

**Поиск до вопроса.** Вопрос по blocking-входу, у которого нет ни сильного
кандидата, ни записи `CANDIDATES.yaml → search.<вход>.done: true`, помечается
`deep_search_missing` (`WARN` в тексте, одноимённое поле в `--json`): сначала
два прохода поиска ([search.md](search.md)), потом вопрос. Это не запрет
спрашивать — это требование не выдавать «не искали» за «не нашли».

**Привязка к ИС.** `CANDIDATES.yaml` и `ANSWERS.yaml` несут поле `is:` с кодом
ИС: чужой файл кандидатов — `WARN` и пропуск, чужой файл ответов — `ERROR`,
код 2 (иначе ответы одной ИС молча применились бы к другой).

**`ask` не пишет ручной слой.** Принятые ответы ложатся только в
`DATA-REQUIREMENTS.yaml`; в `INFORMATION.yaml` их вносит `enrich-apply` —
единственный писатель. Поэтому порядок строгий: `ask` → `ask-answers` →
`enrich-apply`. Язык вопросов и ответов — русский (R16). Протокол опроса,
формат `ANSWERS.yaml` и разобранный пример — [interactive.md](interactive.md).

### 2e. Приём значений

`make enrich IS=...` (без записи) проверяет лист теми же валидаторами, что гейт:
`value` + `source: {type, ref}` + `status: confirmed`, значение в допустимом
множестве. Любая ошибка — код 1, `INFORMATION.yaml` не меняется (ни байта).
`make enrich-apply IS=...` вписывает только секцию `criteria_inputs`, остальные
секции сохраняются дословно, после чего пересчитывается остаток листа.

Входы (`inputs.required` в критериях) разбиты по сценарию расчёта и признаку
блокировки:

| Вход | сценарий | blocking |
|------|----------|----------|
| `peak_hour_load` | простой (и сложный) | да |
| `consumers_type` | простой (и сложный) | да |
| `outage_impact` | простой (и сложный) | да |
| `object_sla` | простой (и сложный) | да |
| `axes_scores` | только сложный | да |
| `time_to_impact` | только сложный | да |
| `cia` | только сложный | да |

Сценариев два (`criteria.scenarios`): **простой** — экспресс-оценка по четырём
входам калькулятора, **сложный** — детальная оценка по всем входам
`inputs.required`. Сценарий выбирается **по данным, а не флагом**: если хотя бы
один вход только сложного набора содержит непустое значение — сценарий сложный;
неполный сложный набор — `BLOCKED`, фолбэк на простой сценарий запрещён. Иначе —
простой сценарий. Правило выбора дословно — `scenarios.selection.rule` в
`criteria/criticality-criteria.yaml`.

Заполнение advisory detailed-входа (`axes_scores`, `cia`) переключает ИС на
сложный сценарий и требует `time_to_impact`: лист требований предупреждает об
этом, а причина `BLOCKED` называет переключение.

**Blocking-вход сценария готов**, когда значение есть **и** `status` не `missing`
(значение-заглушка с `status: missing` отсутствием и считается). Отсутствие входа
вне blocking-набора сценария не блокирует — только `WARN`. `outage_impact` и
`consumers_type` валидируются по enum ещё в `start`: невалидное значение —
`BLOCKED` со списком допустимых.

## Фаза 3 — check

| Поле | Значение |
|------|----------|
| Вход | `INFORMATION.yaml` всех ИС из `is.yaml`, `criteria/criticality-criteria.yaml` |
| Действие | `make check` (только гейт) или `make check-prepare` (подготовка + гейт); `make check-diag` — диагностика |
| Выход | таблица `ИС / сценарий / blocking n/m / advisory n/m / вердикт / причина` + итог по причинам + `DATA-REQUIREMENTS.*` для каждой `BLOCKED` ИС |
| Гейт | все строки `OK` (или `SKIPPED` для исключённых), код возврата 0 |
| Кто выполняет | скрипт |
| Что делать при провале | стоп. Вернуть `DATA-REQUIREMENTS.md` (что/зачем/где/у кого/как подтвердить), назвать адресата; лист отключается `--no-requirements` |

`check` **не затирает** заполненный лист: значения сливаются (`value`,
`source`, `status`, `bucket`/`unit`/`notes`), вычисляемые поля пересчитываются,
непринятые значения показываются `WARN` с подсказкой `make enrich-apply`.
Сливаются только ещё не принятые поля: закрытое (значение + `status:
confirmed`/`derived`/`legacy`) из листа исчезает. Потеря значений — ошибка
целостности (файл не перезаписывается, код 1). `validate` проверяет инвариант:
закрытое поле в листе или неверный `blocking_count`/`advisory_count` — ERROR.

`check` — **strict по умолчанию**: при `BLOCKED` CLI возвращает `1`, `make` — `2`
(ненулевой код в обоих случаях). `--diagnostic` (`make check-diag`) печатает
`BLOCKED`, но возвращает `0` — только для отладки, не для конвейера.
`check --prepare` (`make check-prepare`) сначала выполняет `prepare --apply`
(с `--no-clone` при `NO_CLONE=1`), затем гейт: это и есть «`check` стартует
подготовку данных».

ИС с `excluded: true` и `reason` получает вердикт `SKIPPED`: она остаётся в
таблице, но не блокирует конвейер и не попадает в `start`. Исключение берётся
из `catalog.yaml` (версионируемо, `EXCLUDE_SCOPE=catalog`) или из `is.yaml`
(локально, по умолчанию); приоритет — `is.yaml` > `catalog.yaml`, `excluded:
false` в `is.yaml` включает ИС обратно. В таблице печатается причина и источник.
Итоговая строка: `Итого: ИС N, OK a, BLOCKED b, SKIPPED c, CONFLICT d`.
Исключение и возврат — `make exclude IS=... REASON="..." [EXCLUDE_SCOPE=catalog]`
/ `make include IS=... [EXCLUDE_SCOPE=catalog]`.

Гейт валидирует и **значения**, а не только наличие: `cia.c/i/a` ∈
`{low, medium, high}`, `axes_scores.*` ∈ 0..4, `time_to_impact.bucket` из
`time_buckets.order` (или выводится из `value`), `object_sla` — целое `>= 0`
(`0` = простой недопустим), `peak_hour_load` — целое `> 0`,
`consumers_type`/`outage_impact` — из enum. Значение вне множества —
`BLOCKED` с точной причиной, без трейсбека; `check` и `start` дают один вердикт.
Вердикт `OK`/`BLOCKED` считает один и тот же `evaluate_gate`, что и `start` с
`score --is`: команды не могут разойтись. В шапке таблицы печатается
blocking-набор простого и сложного сценария (`criteria.scenarios`), в колонке
`сценарий` — выбранный по данным сценарий ИС (`простой` / `сложный`).

## Фаза 4 — score

| Поле | Значение |
|------|----------|
| Вход | заполненные `criteria_inputs` ИЛИ явные параметры (`--axes`, `--cia`, `--express`) |
| Действие | `python3 scripts/criticality.py score --is erm.mm` |
| Выход | уровень критичности + `score_trace`: сценарий, метод, правило, промежуточные значения, `status` |
| Гейт | сценарий и метод зафиксированы; `status` не `incomplete`; для простого сценария — `status: preliminary` |
| Кто выполняет | скрипт |
| Что делать при провале | `incomplete` — вернуться в фазу 2 и добрать blocking-входы сценария; неполный сложный набор нельзя «закрыть» простым сценарием |

Сложный сценарий приоритетен: он выбирается автоматически при любом непустом
входе только сложного набора. Простой сценарий возможен только при полностью
пустом сложном наборе и обязан быть помечен как предварительный — и в паспорте,
и в `GENERATION.md`. Неполный сложный набор — это `BLOCKED`, а не простой
сценарий.

## Фаза 5 — start

| Поле | Значение |
|------|----------|
| Вход | пройденный гейт (фаза 3), расчёт (фаза 4), шаблоны `templates/` |
| Действие | `make start IS=erm.mm DIFF=1` → просмотр diff → `make start-apply IS=erm.mm FORCE=1` |
| Выход | `criticality-passport.yaml`, `CRITICALITY.md`, `GENERATION.md`, `actions/{jira-task,confluence-page,rocketchat-message}.md` |
| Гейт | `evaluate_gate` = `OK` (тот же расчёт, что в фазе 3), допустимые значения входов, рендер без `TemplateError`; diff просмотрен человеком; при `FORCE` — подтверждение |
| Кто выполняет | скрипт (рендер), человек (просмотр diff) |
| Что делать при провале | `BLOCKED` — **ничего не записано**; перечислить недостающие входы. `TemplateError` — ошибка шаблона: указать файл и строку, чинить шаблон, не «обходить» пустой строкой |

`start` проверяет гейт сам: при `BLOCKED` (включая невалидный enum
`consumers_type` / `outage_impact` и значения вне допустимых множеств) на диск
не пишется ни один файл, даже с `--force`. Ошибка значения — `BLOCKED` с
причиной, без трейсбека.

Без `--force` существующие паспорт и `CRITICALITY.md` не перезаписываются:
сначала `DIFF=1`, потом осознанный `FORCE=1`. Признак переоценки берётся только
из состояния до генерации (`catalog.yaml` → `review_date`/`approve_link` или
`history` в `INFORMATION.yaml`), поэтому два прогона с одной `--date` дают
побайтово одинаковые артефакты; ручное управление — `REASSESSMENT=1`
(`--reassessment`).

## Фаза 6 — actions

| Поле | Значение |
|------|----------|
| Вход | `GENERATION.md`, `actions/*`, подтверждение человека |
| Действие | `make start-apply IS=erm.mm TASK=1 CONFLUENCE=1 MESSAGE=1` (через MCP) либо ручное применение action-пакетов |
| Выход | Jira-задача, Confluence-страница (draft), текст сообщения в `#Criticality_assessment` |
| Гейт | на каждое внешнее действие — явный флаг и подтверждение; получатели и проект проверены |
| Кто выполняет | человек + MCP (Jira / Confluence); сообщение — человек |
| Что делать при провале | MCP недоступен или вернул 404 — остаться на action-пакете, отдать точный текст и инструкцию, зафиксировать в `GENERATION.md` |

MCP RocketChat в системе отсутствует: сообщение всегда формируется как текст
в `actions/rocketchat-message.md`, отправляет человек.

### Если Jira-ключа нет

`publish` (фаза 8) и `ssot` (фаза 9) требуют Jira-ключ: `--task` или
`catalog.yaml → systems.<код>.jira_task`. Задачи для ИС может не быть — её
создают до публикации, порядок обязателен:

1. **JQL-поиск** — не создавать дубль:
   `project = E001 AND summary ~ "<код ИС>" ORDER BY created DESC`. Найденную
   задачу сверить глазами: код ИС/архитектурный код, а не совпадение подстроки.
2. **Пилотная задача проекта — образец полей.** Обязательные поля E001:
   `issuetype`, `customfield_12750` («Роль», значение `TL` — оно же включает
   автопрефикс), `customfield_17207` («Команды», значение — команда из
   `catalog.yaml → team`, сверить с пилотом). **Пилота нет — остановиться** и
   вернуть вопрос владельцу процесса: угадывать значения `customfield` нельзя.
3. **Summary — без `[TL]`.** Jira добавляет префикс сама из поля «Роль»;
   ручной префикс даёт `[TL] [TL] …`.
4. **Создание через REST API** (`POST /rest/api/2/issue`) с полями из шага 2;
   из ответа берётся `key`.
5. **Записать ключ** в `catalog.yaml → systems.<код>.jira_task`, затем
   `make validate` (0 ERROR) и `make publish IS=<код>` — план должен пройти без
   `ERROR: не задан Jira-ключ`.

## Фаза 7 — verify

| Поле | Значение |
|------|----------|
| Вход | сгенерированные артефакты |
| Действие | `make validate`, `make docs-check`, `make criteria-check`, `make selftest` |
| Выход | отчёты проверок, 0 ERROR |
| Гейт | `validate` — 0 ERROR; `docs-check`, `criteria-check`, `selftest` — `OK` |
| Кто выполняет | скрипт |
| Что делать при провале | ERROR — блокер сдачи; WARN — зафиксировать в отчёте и передать владельцу. Не сдавать с ERROR |

## Фаза 8 — publish

Публикация паспорта в **dochub** (MR с `criticality_passport.yaml`). Идёт
**до** `ssot` (фаза 9): внешние изменения выполняются в порядке «dochub, затем
SSoT». Ссылка на dochub-MR для SSoT-MR больше не требуется — `mrUrl` возвращает
`ssot_form_save`; при необходимости ссылка на dochub-MR живёт в
`INFORMATION.yaml`, а не в описании MR.

| Поле | Значение |
|------|----------|
| Вход | зелёный `verify`, `is/IS/criticality-passport.yaml`, клон dochub |
| Действие | `make publish IS=erm.mm TASK=E001-31245` (план) → `make publish-apply IS=erm.mm TASK=E001-31245` |
| Выход | `architecture/app/<контур>/<сущность>/criticality_passport.yaml`, импорт в `_root.yaml`, ветка `feature/<task>` от `origin/master` с коммитом паспорта (+ `_root.yaml` при первой публикации), `<dochub>/.publish/<код>-MR.md` |
| Гейт | уровень отображается в enum dochub; ключ `sber.ecom.<контур>.criticality_passport.<сущность>` и `evaluated_object` `sber.ecom.<контур>.<сущность>` (дефис → подчёркивание) совпадают с `system.yaml`; в паспорте только обязательные поля и заполненные `assigned_date`/`review_date`/`approve_link`; дерево клона чистое; коммит ровно из двух файлов |
| Кто выполняет | скрипт |
| Что делать при провале | код 1 — данные/валидация (гейт не пройден, нет папки ИС или `system.yaml`, уровень вне enum); код 2 — аргументы (`--push` без `--apply`, не задан `--task`). Ничего не писать в dochub до исправления; `--push` и создание MR — только по явному подтверждению человека |

`publish` — это **не** «публикация в `#Criticality_assessment`». Публикация
паспорта — MR в dochub (эта фаза); тред согласования в чате — этап `handoff`
(фаза 10). Команда `make publish` никогда не пишет в чат.

**Клона dochub нет — команда клонирования печатается.** URL репозитория
хранится в данных проекта: `catalog.yaml → dochub_url` (или `dochub.url`),
`criteria.dochub.url`, флаг `--dochub-url` главнее. `publish` печатает
`клонировать: git clone <URL> <путь>`; URL не сконфигурирован — подсказка
добавить `dochub_url` (искать репозиторий вручную не нужно).

**`--update` — только для ветки на `origin`.** `--update` обновляет уже
опубликованную ветку MR (`checkout -B <branch> origin/<branch>`); локальная
ветка без пуша проверку `refs/remotes/origin/<branch>` не проходит —
`ERROR: ветка <branch> не найдена на origin`. Новая ветка — `publish-apply` без
`--update`. Ссылка `.publish/<код>-MR.url` появляется **только** при `--push`
(её читает `start` для `actions.mr_link`); к этапу `ssot` она отношения не имеет:
MR SSoT создаёт MCP-форма, а `mrUrl` возвращает `ssot_form_save`.

## Фаза 9 — ssot

Обогащение **SSoT** критичностью: точечное изменение двух полей формы base
(`severity.type` и `severity.confirmation`) через MCP. Идёт **после** `publish`
и **до** `handoff`: тред согласования ссылается на оба MR — dochub и SSoT.
Локального клона SSoT, ветки, commit и push нет: MR создаёт сам SSoT.

| Поле | Значение |
|------|----------|
| Вход | зелёный `publish` (dochub-MR существует), `is/IS/criticality-passport.yaml`, `catalog.yaml → approve_link` и `criticality_ssot`, ответ `ssot_get` (снимок `ssot_snapshot`) |
| Действие | `make ssot-plan IS=erm.mm` (план: целевые `severity.type`/`confirmation` + гейт R18) → MCP `ssot_entity_open(group="information-systems", entity=<код>)` → `ssot_form_fields` → `ssot_ui_select(target="severity.type", option=<уровень>)` / `ssot_ui_fill(target="severity.confirmation", value=<approve_link>)` → `ssot_form_save` → `make ssot-record IS=erm.mm MR_URL=<mrUrl>` → MCP `ssot_wait_version` → `make ssot-verify IS=erm.mm VERIFY_JSON=-` |
| Выход | MR SSoT с изменёнными `severity.type`/`severity.confirmation`; `mrUrl` и `version` из `ssot_form_save` зафиксированы `ssot-record`; доказательство `ssot_verify_change` |
| Гейт | `severity.type` — enum SSoT (`levels.ssot_enum`); `confirmation` = `approve_link` (актуальный тред); изменены только эти два поля формы base, остальные поля не тронуты; `ssot_form_save` вернул `ok:true` с `version` и `mrUrl` (иначе `save_not_observed`); `ssot_verify_change` подтвердил значение на ветке MR |
| Кто выполняет | скрипт (`ssot-plan`, `ssot-record`, `ssot-verify`) + агент (MCP-форма) |
| Что делать при провале | код 1 — данные/валидация (уровень паспорта расходится с `criticality_ssot`, нет `approve_link`, `confirmation` вне regex, ИС нет в SSoT, гейт R18 не пройден); `auth_required` от MCP — `ssot_status`, при необходимости `ssot_login`; `save_not_observed` — повторить `ssot_form_save`, запись не подтверждена |

**Только два поля.** Правится **только** `severity.type` и
`severity.confirmation` формы base: `components`, `links`, `resources`, `duty`,
`roles` и другие ИС не меняются. Поля `review_date`, `assigned_date`,
`tech_architect` в SSoT отсутствуют — их туда не добавляют (они живут в
`catalog.yaml` и Confluence).

**Гейт R18 до формы.** `ssot-plan` и `ssot-record` отказывают (код ≠ 0), пока
`validate` даёт ERROR, `criteria_fingerprint` не совпадает или blocking-входы не
закрыты; осознанный обход — только `FORCE=1` с записью в
`is/<код>/.gate-overrides.log`.

**После handoff — апрув и применение.** Пока MR не применён, SSoT не обогащён:
`handoff` не закрыт. Человек (или агент по явному разрешению) выполняет
`ssot_mr_approve(confirm:true)` → `ssot_apply_changes(confirm:true)` →
`ssot_wait_master`; `ssot_wait_master` успешен только когда изменение
подтверждено по git-зеркалу (master), а не только по UI.

## Фаза 10 — handoff

Публикация результата в **`#Criticality_assessment`** — тред согласования со
ссылками на **оба** MR (dochub из фазы 8 и SSoT из фазы 9), затем подтверждение
SRE. Это и есть «публикация в чат»; `publish` (фаза 8) — только MR в dochub.

**Сначала вопрос, потом отправка.** `make handoff IS=<код>` спрашивает:
«Отправить сообщение в `#Criticality_assessment` автоматически?» — `1` да
(отправить), `2` нет (оставить пакет вручную), `3` отменить. Без `--send` вне
TTY команда отказывает с подсказкой: дефолта «на всякий случай» нет, без явного
ответа ничего не отправляется. Выбор хранится в
`catalog.yaml → systems.<код>.handoff_mode`.

**Публикация результатов (`--report`).** Отдельный режим: в тред уходит отчёт о
результатах оценки (итог, участники, входы с провенансом, расчёт, ссылки,
«Что дальше»), а не запрос согласования. Гейты MR/`⛔`/SSoT не применяются:
отчёт можно опубликовать в существующий тред (`--thread <tmid>`) сразу после
расчёта. Текст целиком — `--dry-run`; отправка — `--send auto` (REST), режим
пишется как `handoff_mode: report`. С `--thread-new` публикуется **тред**:
родитель — итог, участники и основные ссылки (в т.ч. `--dochub-mr-url` /
`--ssot-mr-url`), три ответа — входы с провенансом, расчёт и артефакты;
`thread_link`/`approve_link` указывают на родителя (`handoff_thread: true`),
повтор идемпотентен. Появившийся позже SSoT-MR подставляется в родителя через
`--update-parent --ssot-mr-url <URL>` (`chat.update`), без нового треда.

**Транспорты:** `mcp` — основной (скрипт пишет `is/<код>/.handoff-request.json`,
исполнитель отправляет через MCP RocketChat, результат возвращает
`handoff-result`); `api` — REST-фолбэк (`chat.postMessage` с токеном). Цепочка
`auto`: MCP → REST → ручной пакет.

**Если MCP сломался — сразу API, без ожидания.** Срок ожидания ответа MCP
(`--mcp-timeout`, `criteria.handoff.mcp_timeout_seconds`, по умолчанию 120 с)
пишется в `handoff_deadline`; истёк — следующая команда `handoff` (и подсказка
`next_step`) сама уходит в REST с `fallback_reason: mcp_timeout`.
Принудительно — `make handoff IS=<код> RESUME=1`.

| Признак сбоя MCP | `fallback_reason` | Действие |
|------------------|-------------------|----------|
| сервера Rocket.Chat нет в конфиге | `mcp_unavailable` | сразу REST |
| исполнитель вернул `--failed` | `mcp_failed` | REST-фолбэк |
| истёк `deadline` | `mcp_timeout` | автоматически (`handoff`/`RESUME=1`) |
| невалидный ответ (URL/хост/`/channel/`/`msg=`) | `mcp_invalid_response` | `thread_link` не пишется, сразу REST |
| `handoff-result` без флагов | `mcp_format_error` | ошибка + REST-фолбэк |

**Дедупликация при фолбэке:** перед POST скрипт ищет своё сообщение в канале
(`GET /api/v1/channels.messages?roomName=<канал>&count=20`, первые 80 символов
текста + автор). Найдено — его `_id` становится `thread_link`, повтор не
отправляется. Поиск недоступен — fail-closed без `--allow-duplicate-risk`.

| Поле | Значение |
|------|----------|
| Вход | зелёный `publish` (dochub-MR), SSoT-MR из фазы 9, `actions/rocketchat-message.md` |
| Действие | `make handoff IS=<код> SEND=auto` (MCP, при отказе — REST API) или `SEND=manual`; затем `make handoff-result IS=<код> MESSAGE_URL=<ссылка>` для транспорта MCP; MCP не ответил — `make handoff IS=<код> RESUME=1` (фолбэк на API с дедупликацией); запросить подтверждение SRE, обновить карточку SSoT, назначить дату переоценки |
| Выход | `thread_link` в `catalog.yaml`, тред согласования, смерженные MR, подтверждение SRE, актуальная карточка SSoT, `reassessment-YYYY-MM-DD.md` при следующем цикле |
| Гейт | в тексте нет `⛔`, `validate` без ERROR, `thread_link` пуст (идемпотентность; `--force-resend` — обход); тред ссылается на оба MR; MR смержены; SRE подтвердил; `criticality_ssot` совпадает с паспортом |
| Кто выполняет | скрипт (`handoff`/`handoff-result`) + человек (ответ на вопрос, подтверждение SRE) |
| Что делать при провале | **оба транспорта отказали** — статус `failed`, причина в `handoff_error`, пакет остаётся `pending_manual`: отправить сообщение из `actions/rocketchat-message.md` руками, затем `make handoff-result IS=<код> MESSAGE_URL=<ссылка>`. Работу не считать законченной: паспорт без подтверждения SRE — черновик, а не оценка |

## Фаза 11 — finalize

Подтверждение SRE зафиксировано в треде — финализация одной командой. Без
`--approve-link` команда отказывает: «подтверждение SRE обязательно; паспорт
без подтверждения — черновик».

| Поле | Значение |
|------|----------|
| Вход | `thread_link` в `catalog.yaml` (тред согласования), `INFORMATION.yaml → publication.extra_info` (опционально), паспорт, SSoT severity |
| Действие | `make finalize IS=<код>`: `catalog.yaml → systems[<код>]` — `approve_link` (= `thread_link` при `handoff_status: published`; `--approve-link` — явный override), `assigned_date` (= `generated_at`), `review_date` (= `generated_at` + `review_period_months`), `criticality` (из паспорта), `criticality_ssot` (из SSoT severity), `status: confirmed`; затем `start-apply FORCE=1` → `validate` → `index` → `verify`. Нет ни флага, ни опубликованного треда (`failed`/`mcp_requested`/пусто) — `ERROR` с подсказкой `make handoff IS=<код> SEND=auto` или явный `--approve-link` |
| Выход | подтверждённая запись реестра, перегенерированные паспорт/`CRITICALITY.md`/`INDEX.md`, зелёные гейты |
| Гейт | домен `approve_link` из `criteria.external_refs.approve_link_domains` (принимается и относительная `/link?rid=…&msg=…`); `criticality` и `criticality_ssot` согласованы (расхождение — `ERROR` с обоими значениями); `validate` без ERROR. Подтверждение фиксируется мержем MR — отдельного ожидания ответа SRE нет |
| Кто выполняет | скрипт |
| Что делать при провале | `ERROR` в `validate`/`index`/`verify` — записанные поля и артефакты ИС откатываются; исправить причину и повторить. `--dry-run` — показать план без записи |

**Запрещено:** отправлять сообщение до завершения всех предыдущих фаз;
отправлять частями; отправлять без показа пользователю; отправлять при наличии
`⛔` в тексте (без `--allow-incomplete`).

**Почему одно сообщение.** Тред читают люди: разбитый на части текст теряет
ссылки и контекст, а «дослать остаток» забывается. Если текст длиннее лимита
канала (`settings/Message_MaxAllowedSize`, при 403 — 5000), команда падает с
ошибкой и требует сократить ИСТОЧНИК (`INFORMATION.yaml` → `facts`/`notes`),
а не резать сообщение.

**Почему только с `CONFIRM=1`.** Публикация необратима: сообщение видят все
участники канала. Поэтому защита двойная — цель `make handoff-apply` без
`CONFIRM=1` печатает отказ, а сам CLI без `--confirm` тоже отказывает (код 1).
Случайный запуск «на всякий случай» не отправляет ничего.

**Идемпотентность.** Опубликованный тред фиксируется в реестре
(`catalog.yaml → handoff_status: published` + `thread_link`), а перед отправкой
дополнительно ищется своё сообщение в канале (`_handoff_find_message` по
`roomId`, сравнение первых 80 символов текста и автора). Найдено — берётся его
`_id`, второй POST не выполняется. Повторный `handoff`/`handoff-apply` при
`published` печатает «уже опубликовано: <ссылка>» и отказывает; осознанная
переотправка — только `--force-resend` (`make handoff … FORCE_RESEND=1`,
`make handoff-apply … FORCE=1`). Своего файла-дайджеста у команды нет:
идемпотентность общая, поэтому `handoff-apply` после `handoff` дубль не создаёт.

## Подсказка следующего шага

После каждой команды скрипт печатает, что делать дальше. Подсказка не
спрашивает человека и не угадывает: она вычисляется по фактическому состоянию
репозитория той же функцией `next_step()`, что заполняет колонку «следующий
шаг» в `help`.

```text
Следующий шаг: make enrich-apply IS=gi.mm — не хватает 1 обязательного входа: object_sla
```

Правила проверяются по порядку, срабатывает первое. Порядок намеренный:
**сначала локальные проблемы уже рассчитанной ИС, и только потом глобальные**
(нет `is.yaml` / нет снимка `ssot_get`) — иначе одна глобальная проблема скрывала бы весь
конвейер.

| Состояние | Подсказка |
|-----------|-----------|
| гейт `BLOCKED`, нет `RESEARCH-PLAN.md` | `make collect-apply IS=<код>` |
| гейт `BLOCKED`, план есть, нет `SERVICE-FINDINGS.md` | `make services-apply IS=<код>` |
| гейт `BLOCKED`, оба файла есть, нет `ASK.md` | `make ask IS=<код>` — план вопросов по незакрытым входам (enum дословно, кандидаты с провенансом) |
| гейт `BLOCKED`, `ASK.md` есть | `make enrich-apply IS=<код>` — не хватает N обязательных входов: `<список>` |
| гейт `OK`, паспорта нет | `make start-apply IS=<код> FORCE=1` |
| паспорт старше изменений `INFORMATION.yaml` | `make start-apply IS=<код> FORCE=1` |
| в листе требований есть непринятые значения | `make enrich-apply IS=<код>` |
| `review_date` просрочен | `make reassess-apply IS=<код>` (план — `make reassess IS=<код>`) |
| `INDEX.md` устарел | `make index` |
| паспорт не проходит `validate` | `make validate` — исправьте ERROR и повторите |
| `severity` в SSoT расходится с паспортом, паспорт не опубликован в dochub | `make publish IS=<код> TASK=<key>` (план; запись — `make publish-apply`) |
| паспорт опубликован в dochub, `severity` в SSoT расходится с паспортом | `make ssot-plan IS=<код>` — обогатите SSoT после публикации (план), затем MCP-форма и `make ssot-record` / `make ssot-verify` |
| паспорт опубликован, SSoT обогащён | `make handoff IS=<код> SEND=auto` — показать сообщение целиком, спросить «Публиковать это сообщение в треде или что-то нужно исправить?», и только после «Публиковать» отправить (MCP → REST); без MCP — `make handoff-apply IS=<код> CONFIRM=1` |
| нет `is.yaml` | `make init` — нет конфигурации проекта |
| `is.yaml` есть, но пуст (ни одной ИС) | `make scaffold IS=<код>` — в конвейере нет ни одной ИС |
| ИС есть в `is.yaml`, папки `is/IS/` нет | `make scaffold IS=<код>` — ИС есть в is.yaml, но папки нет |
| нет данных `ssot_get` (снимок не импортирован) | MCP `ssot_get(group="information-systems", entity=<код>)` → `make ssot-import IS=<код> ENTITY_JSON=-`, затем `make prepare-apply IS=<код>`; пока снимка нет, этап `ssot` не выполнен — `handoff` не советуется |
| у ИС нет `INFORMATION.yaml` (SSoT есть) | `make prepare-apply` — нет рабочего файла данных |
| всё пройдено | `все этапы пройдены` (для сводки — `Все этапы пройдены`) |

**Без циклов.** Подсказка никогда не советует команду, которая ничего не
меняет. Признак публикации берётся из трёх источников (от дешёвого к дорогому):
артефакт `.publish/<код>-MR.url|md` в рабочем дереве; ветка MR в origin
(`git ls-remote --heads origin <ветка>`); паспорт в `origin/master`
(`git show origin/master:<путь>`). Отсюда:

- ветка MR уже есть, а описания MR нет → `make publish-apply IS=<код>
  TASK=<key> UPDATE=1` (обновить существующую ветку), а не обычный `publish`:
  без `--update` команда упадёт «ветка уже существует» — это и был цикл.
  `UPDATE=1` сработает только если ветка есть **на `origin`**: локальная ветка
  без пуша проверку `refs/remotes/origin/<branch>` не проходит (см. фазу 8);
- паспорт уже в `origin/master` (смержен) → сразу `ssot-plan`, публикацию не
  советуем;
- клона `dochub/` или сети нет → публикация «неизвестна», подсказка объясняет
  причину (`make prepare-apply`), код возврата 0.

Без снимка `ssot_get` `next_step` не ведёт в `handoff`: этап `ssot` не выполнен,
пока снимок не импортирован. Подсказка — MCP `ssot_get` →
`make ssot-import IS=<код> ENTITY_JSON=-` → `make prepare-apply`.

Подсказка ведёт к следующему маркеру состояния (`ssot_snapshot`, `INFORMATION.yaml`,
`RESEARCH-PLAN.md`, `SERVICE-FINDINGS.md`, принятые значения листа, паспорт,
`INDEX.md`, `review_date`, папка `is/IS/`): после её выполнения `next_step`
возвращает уже другую команду. Если шаг требует внешнего ресурса (MCP-сессия
SSoT, доступ к репозиторию), подсказка объясняет, **чего не хватает и что сделать
человеку**, — сама команда маркер не сдвинет, пока ресурс не появился, и
следующий вызов вернёт ту же команду с той же причиной. Это осознанно: причина
важнее новизны команды. Проверяется в `make selftest` (состояния конвейера +
отсутствие повторов там, где шаг полностью локальный).

- Для команд по одной ИС (`show`, `score --is`, `reassess`, `enrich`,
  `scaffold`, `exclude`, `include`) подсказка — про эту ИС.
- Для `check`, `validate`, `index` — сводка: по строке на ИС, у которой есть
  следующий шаг; если все готовы — одна строка `Все этапы пройдены`.
- Исключённая ИС (`SKIPPED`) шага не имеет: печатается `SKIPPED — ИС исключена
  из расчёта`.
- `--no-next` (он же `--quiet`) отключает подсказку — для скриптов и
  make-целей: `make criteria-check`, `make docs-check`, `make selftest`
  передают флаг сами.

## Боковые этапы (вне линейного конвейера)

Запускаются по потребности и не являются фазами: конвейер от них не зависит,
`next_step` советует их только когда состояние этого требует.

| Этап | Команда | Выход | Когда |
|------|---------|-------|-------|
| `scaffold` | `make scaffold IS=<код>` (`CONTOUR=mm NAME=foo`) | папка `is/<код>/` (README, паспорт, `CRITICALITY.md`) + запись в `catalog.yaml → systems` и код в `is.yaml → is:` (идемпотентно) | завести новую ИС; оба реестра создаются, если их нет |
| `index` | `make index` | `INDEX.md` (блок между маркерами) | после `validate`, если менялся состав ИС или уровни |
| `due` | `make due` | список просроченных, ближайших и неоценённых переоценок | планирование цикла, перед `reassess` |
| `reassess` | `make reassess IS=<код>` (план) / `make reassess-apply IS=<код>` | `reassessment-YYYY-MM-DD.md` + `catalog.yaml → review_date` | `review_date` истёк; после — новый цикл с фазы 1 |
| `exclude` / `include` | `make exclude IS=<код> REASON="..." [EXCLUDE_SCOPE=catalog]` / `make include IS=<код>` | `excluded: true` + `reason`, вердикт `SKIPPED` (или возврат в расчёт) | данных нет и взять негде; приоритет `is.yaml` > `catalog.yaml` |

## Правила перехода между фазами

1. Фаза закрыта только при выполнении своего гейта; «почти получилось» — не закрытие.
2. Провал гейта останавливает конвейер: последующие фазы не запускаются.
3. Повторный запуск фазы идемпотентен: `prepare` не трогает ручные секции,
   `start` без `--force` не перезаписывает паспорт.
4. Внешняя запись (Jira, Confluence, чат) — только по флагу и подтверждению.
5. Фазы 2 и 10 выполняет человек; скилл готовит данные, проверяет и объясняет,
   но не подписывает оценку.
6. Этап `services` (2c) не заменяет сбор значений: `SERVICE-FINDINGS.md` —
   основание и цитаты, а не подтверждённые входы. Клоны только читаются; сборка
   и запуск запрещены (R12).
7. Финальные этапы идут строго `publish` → `ssot` → `handoff`: `publish`
   создаёт dochub-MR, SSoT-MR (этап `ssot`) создаёт MCP-форма и возвращает
   `mrUrl` в `ssot_form_save`, а тред в `#Criticality_assessment` (этап
   `handoff`) ссылается на оба MR. Обратный порядок оставлял бы тред без
   ссылок: основание SSoT-MR — `mrUrl` из `ssot_form_save`, а не ссылка на
   dochub-MR.
8. Этап `ask` (2d) — единственный вход для вопросов человеку: он раскрывает enum
   дословно и приносит кандидатов с провенансом, поэтому идёт **до** `enrich`.
   Ответы ложатся только в `DATA-REQUIREMENTS.yaml`; ручной слой
   `INFORMATION.yaml` пишет исключительно `enrich-apply` (R4, R10).
9. Внешние изменения — только после зелёной валидации (R18). `publish`,
   `publish-apply`, `ssot-plan`, `ssot-record` отказывают (код ≠ 0) при ERROR в
   `validate`, расхождении `criteria_fingerprint` и незакрытых blocking-входах;
   причина и следующий шаг печатаются в выводе. Осознанный обход — только
   `FORCE=1` (`--force`): `WARN` + строка в `is/<код>/.gate-overrides.log`.
10. Публикация в тред не переводится в `requested`, пока в отрендеренном тексте
    есть `⛔ не заполнено`: `start --create-message` оставляет пакет
    `pending_manual` и печатает «отправка заблокирована: N незаполненных полей»
    со списком в `actions/rocketchat-message.md`.
11. Заголовок страницы печатается только из проверенного кеша
    (`catalog.yaml → page_titles`; `title_verified_at` заполняет
    `make verify-titles FIX=1`); выдуманное название — дефект публикации, нет
    кеша — `[page <id>] <url>` без названия (R19). `make verify` прогоняет
    `verify-titles` вместе с остальными гейтами.

## Что делать при провале гейта

| Провал | Действие скилла | Что вернуть пользователю |
|--------|-----------------|--------------------------|
| Нет `is.yaml` | остановиться, не создавать молча | команда `make init` и формат файла |
| `ssot_get`/`ssot_form_save` вернул `auth_required` или ошибку | `ssot_status`, при необходимости `ssot_login`; проверить, что MCP-сервер `ssot-mcp` поднят | `ssot_status` (authorized / loginInProgress) и подсказка по `ssot_login` |
| `INFORMATION.yaml` отсутствует | остановиться | `make prepare-apply` и путь ожидаемого файла |
| Не хватает blocking-входа | остановиться, отдать `DATA-REQUIREMENTS.md` | `id`, `description`, `source_hint`, «где взять / у кого / как подтвердить» |
| Входы не закрыты, но есть с кем поговорить | собрать план вопросов `make ask IS=...` (enum дословно, кандидаты с провенансом) | вопросы с вариантами ответа и маршрутом «где взять»; после ответов — `make ask-answers` |
| Сложный набор неполон | остановиться: `BLOCKED`, без фолбэка на простой сценарий | каких входов сложного сценария не хватает и у кого запросить |
| Сервис ИС не клонируется | продолжить с остальными, зафиксировать `clone_error` в `SERVICE-FINDINGS.md` | URL репозитория, текст ошибки git, кому запросить доступ |
| В клоне нет `docs/` или `openspec/` | не выдумывать документацию: записать в §7 «Не найдено» | что именно отсутствует и что взято из Confluence вместо этого |
| Лист требований заполнен без источника | `enrich` возвращает ошибку, `INFORMATION.yaml` не меняется | какие записи отклонены и почему (нет `source` / `status` не `confirmed` / значение вне enum) |
| Данных нет и взять негде | `excluded: true` + `reason`, вердикт `SKIPPED` | что именно отсутствует и кто принял решение об исключении |
| Расхождение SSoT ↔ расчёт или SSoT ↔ реестр | записать `conflicts` (`calculation vs ssot` / `ssot vs catalog`) | оба значения, источник каждого и подтверждающий |
| `TemplateError` | остановиться | файл шаблона, строка, путь значения |
| Внешний MCP недоступен | деградировать в action-пакет | готовый текст и инструкция |

Запрещено: обходить гейт, подставлять значения «по умолчанию», продолжать
генерацию с частичным набором входов.

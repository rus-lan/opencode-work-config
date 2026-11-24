---
title: Шаблоны и генерация артефактов
purpose: Описать каталог .opencode/skills/criticality-gen/templates/, мини-движок шаблонов и правило «любой артефакт = шаблон + факты + расчёт».
audience: [ai-agent, human]
read_when: [меняете шаблон или добавляете артефакт, выясняете откуда в паспорте значение, разбираете синтаксис движка]
updated: 2026-11-13
status: actual
related: [09-pipeline.md, 07-scripts.md, 11-skill.md, ../templates]
---

# Шаблоны и генерация артефактов

## Когда читать

- Читать, когда меняете файл в `.opencode/skills/criticality-gen/templates/` или добавляете новый артефакт.
- Читать, когда нужно понять, почему в артефакте стоит `⛔ не заполнено` или `null`.
- Читать, когда разбираете синтаксис `{{ }}` и правила перезаписи.

## Кратко

- Любой артефакт — шаблон из `.opencode/skills/criticality-gen/templates/` + факты из `INFORMATION.yaml` + детерминированный расчёт.
- Нет факта — в артефакте явный маркер, а не придуманное значение; нет обязательного входа — генерация блокируется.
- Движок поддерживает `{{ path }}`, фильтр `or_missing`, блоки `{{#if}}` / `{{#each}}`; список путей — в разделе 3.
- Сгенерированные файлы править запрещено: правка перезапишется; менять нужно `INFORMATION.yaml` или шаблон.
- `.opencode/skills/criticality-gen/templates/INFORMATION.yaml` — скелет, а не шаблон: движком не рендерится.
- `RESEARCH-PLAN.md` — план сбора (страницы, дашборды, запросы); рендерится `collect` при `BLOCKED`.
- `SERVICE-FINDINGS.md` — что даёт код сервисов (`docs/`, `openspec/`): цитаты «файл:строка», нормативы, потоки, «вход → основание»; рендерится `services --apply`.
- `LINK-MAP.md` и `LINK-MAP.yaml` — карта обхода ссылок ИС (узлы с `id`, `kind`, `expand`, `candidate_for`) и контракт обхода для MCP-агента; рендерятся `links --apply`.
- `SOURCES-FINDINGS.yaml` — скелет фактов, которые агент собрал по `LINK-MAP.md`; не рендерится движком, заполняется агентом, принимается `sources --apply`.
- `MR-dochub.md` и `MR-ssot.md` — описания MR для `publish` и `ssot`; рендерятся в строгом режиме: пустая переменная — ошибка, `or_missing`/`default` запрещены.

## 1. Каталог шаблонов

| Файл | Назначение | Обязательные переменные | Когда использовать |
|------|------------|-------------------------|--------------------|
| `.opencode/skills/criticality-gen/templates/criticality-passport.yaml` | канонический паспорт dochub (9 полей) | `passport.id`, `passport.evaluated_object`, `passport.review_date` (из источника: `catalog.yaml` → `history` → прежний паспорт, иначе `null` + WARN), `passport.generated_at` (дата генерации), `identity.asset`, `identity.code`, `refs.express_method_page.url`; остальные `passport.*` — через `or_missing`/`yaml` | всегда (`start`, `scaffold`) |
| `.opencode/skills/criticality-gen/templates/CRITICALITY.md` | человекочитаемый паспорт, 10 обязательных разделов | `identity.*`, `passport.*`, `passport_rows`, `facts.*`, `score_trace.*` (в т.ч. `score_trace.rule_notes` — сноски архивных источников), `meta.criteria_fingerprint`, `components`, `resources`, `links`, `refs.*` (внешние ссылки), `sources`, `todo_items`, `history`, `conflicts` | всегда (`start`, `scaffold`) |
| `.opencode/skills/criticality-gen/templates/GENERATION.md` | отчёт о генерации: метод, входы, промежуточные значения, conventions, расхождения, фингерпринт критериев | `generation.*` (в т.ч. `generation.criteria_fingerprint`, `generation.rule_notes`), `requirements.present` | всегда (`start`) |
| `.opencode/skills/criticality-gen/templates/DATA-REQUIREMENTS.md` | лист недостающих данных для человека: что/зачем/где/у кого/как подтвердить + фрагмент `INFORMATION.yaml` | `requirements.*` (см. §3.1) | `requirements`, автогенерация при `BLOCKED` |
| `.opencode/skills/criticality-gen/templates/DATA-REQUIREMENTS.yaml` | машиночитаемый лист для заполнения (`value`/`source`/`status` + `#`-комментарии) | `requirements.*` | `requirements`, автогенерация при `BLOCKED` |
| `.opencode/skills/criticality-gen/templates/RESEARCH-PLAN.md` | план сбора данных: что искать, страницы Confluence, дашборды и запросы Grafana, формат фиксации | `research.*` (см. §3.2) | `collect`, только при `BLOCKED` |
| `.opencode/skills/criticality-gen/templates/LINK-MAP.md` | карта обхода ссылок для агента: шапка, узлы, «вход → кандидаты», правила обхода по видам, контракт `SOURCES-FINDINGS.yaml`, что делать, если значения нет | `link_map.*` (`is_code`, `generated_at`, `source`, `max_nodes`, `counts`, `nodes`, `inputs`, `truncated`) | `links` с `--apply` |
| `.opencode/skills/criticality-gen/templates/LINK-MAP.yaml` | машиночитаемая карта (`nodes[]` с `id`/`kind`/`ref`/`origin`/`subject`/`expand`/`candidate_for`/`status`); её читает `sources` | `link_map.*` | `links` с `--apply` |
| `.opencode/skills/criticality-gen/templates/SOURCES-FINDINGS.yaml` | скелет результатов обхода (`findings[]`, `not_found[]`) с `#`-комментариями к каждому полю | **не рендерится движком** — заполняет MCP-агент | `sources` (чтение), `sources --apply` (приём) |
| `.opencode/skills/criticality-gen/templates/SERVICE-FINDINGS.md` | код сервисов ИС: список сервисов и их `docs/`/`openspec/`, пропущенные по `lifecycle`, цитаты о назначении/нормативах/потоках, «вход → основание», «не найдено» | `findings.*` (см. §3.3) | `services` с `--apply` |
| `.opencode/skills/criticality-gen/templates/publication.md` | дословный шаблон публикации в `#Criticality_assessment` | `identity.code`, `identity.ta` (упоминание TA: `@<login>` из `contacts`, иначе ФИО `catalog.yaml → tech_architect`), `identity.tl` (упоминание TL: `@<login>` из `contacts`), `actions.mr_link`, `actions.ssot_mr_text` (ссылка, «не требуется» при `ssot_status: no_change` или `⛔`), `actions.ssot_card_link`, `actions.process_link` (буллет рендерится только при `criteria.meta.sources` → `role: process_current`), `actions.old_criticality`, `actions.extra_criteria`, `actions.e2e_list`, `actions.gmv_impact` (значение или маршрут), `actions.adr_link`, `actions.jira.task_key` (номер), `actions.jira.task_link` (ссылка по `criteria.external_refs.jira_base`), `actions.extra_info` (опционально: пусто — буллет не рендерится), `passport.object_criticality_estimation`, `refs.publication_page.url`, `refs.responsibility_registry.url` | всегда (`start` → текст сообщения) |
| `.opencode/skills/criticality-gen/templates/actions/jira-task.md` | инструкция: как создать задачу в Jira | `actions.jira.*`, `actions.labels`, `actions.reassessment`, `actions.e2e_list`, `actions.adr_link`, `identity.*`, `passport.*`, `score_trace.method`, `score_trace.status`, `task_key` | всегда (`start`) |
| `.opencode/skills/criticality-gen/templates/actions/confluence-page.md` | инструкция: страница оценки критичности (draft) | `actions.confluence.*`, `identity.*`, `actions.e2e_list` | всегда (`start`) |
| `.opencode/skills/criticality-gen/templates/actions/rocketchat-message.md` | готовое сообщение + чеклист перед отправкой (ссылки на **оба** MR — dochub и SSoT) | `actions.message.*`, `actions.jira.task_key`, `actions.jira.task_link`, `actions.mr_link`, `actions.ssot_mr_text`, `actions.ssot_card_link`, `actions.adr_link`, `identity.*`, `passport.*` | всегда (`start`) |
| `.opencode/skills/criticality-gen/templates/MR-dochub.md` | описание MR публикации паспорта в dochub (9 блоков) | `mr.*` (см. §3.4) | `publish` (`.publish/<код>-MR.md`) |
| `.opencode/skills/criticality-gen/templates/MR-ssot.md` | описание MR обогащения SSoT (`severity`) | `mr.*` (см. §3.4) | `ssot --apply` (`.ssot/<код>-MR.md`) |
| `.opencode/skills/criticality-gen/templates/INFORMATION.yaml` | YAML-скелет `INFORMATION.yaml` для `prepare` | **не рендерится движком** — это структура, а не шаблон | `prepare` |

`.opencode/skills/criticality-gen/templates/INFORMATION.yaml` — единственный файл в `.opencode/skills/criticality-gen/templates/`, который **не**
проходит через движок: его разбирает мини-парсер YAML, а `prepare` берёт из него
скелет ручных секций (`criteria_inputs`, `facts`, `conflicts`, `notes`).
Поэтому в нём нет управляющих конструкций `{{#if}}` / `{{#each}}`.
Секция `contacts` в этом файле — описание структуры: значения в неё пишет
`prepare` / `make contacts` из `ssot/entities/teams/<team>/team.yaml`, а не
человек (см. [data-sources.md](data-sources.md)).

**Роль `.opencode/skills/criticality-gen/templates/publication.md`.** Это источник текста сообщения, а не отдельный файл-артефакт. `start` рендерит шаблон, извлекает из него блок кода с языком `text` и подставляет результат в `actions/rocketchat-message.md` (поле «Готовое сообщение»). Отдельного файла публикации в папке ИС нет — итоговый текст всегда лежит в action-пакете.

**Расширения скилла в публикации.** Элементы `templates/publication.md`, которых нет
в эталоне [4553986100](https://space.samokat.ru/pages/viewpage.action?pageId=4553986100),
являются инженерными расширениями репозитория:

| Элемент | Что добавлено | Почему |
|---------|---------------|--------|
| TL-буллет | `* TL - {{ identity.tl }}` рядом с техническим архитектором | в эталоне указан только TA; TL нужен SRE для подтверждения |
| SSOT-ссылки | `actions.ssot_mr_text` (ссылка, «не требуется» при `ssot_status: no_change` или `⛔`) и `actions.ssot_card_link` | публикация сопровождает два MR (dochub + SSoT), тред должен ссылаться на оба; при `no_change` MR не нужен — это заполненное поле, а не блокер |
| SSOT-карточка | `actions.ssot_card_link` собирается из шаблона `criteria.external_refs.ssot_card_base` (`https://ssot.ecom.tech/information-systems/{code}`, формат — дословно из чек-листа этого шаблона) | чек-лист требует ссылку на карточку ИС; в скрипте адрес не хардкодится |
| Процесс D6.1.1 | буллет `* Ссылка на процесс D6.1.1 — «<title>» [<page_id>] <url> (действующий, v<version>)` | участник согласования должен видеть действующий процесс, по которому сделана оценка; источник — `criteria.meta.sources` → `role: process_current` |
| provisional-блок | `{{#if score_trace.provisional}}Оценка предварительная…` (R17) | отказ от входа (`waive`) обязан быть виден до согласования |
| GMV | наполнение раздела 3 «Потери GMV / влияние на аудиторию» (`actions.gmv_impact`): значение из `criteria_inputs.financial_loss` либо `⛔ не заполнено` + маршрут (`criteria.inputs.financial_loss.where` + ссылка на канон входов + `DATA-REQUIREMENTS.md`) | в эталоне раздел есть, но без правила заполнения; голое `⛔` не подсказывает, где взять данные |
| Старая критичность | `actions.old_criticality` — `severity.type` из SSoT в исходном виде (`business-critical`) + `severity.addon` в `actions.extra_criteria` (`CONTACT`) | в эталоне поле есть, но источник не задан; подставлять новый уровень нельзя — отсутствие данных маскировалось бы под факт. Fallback: `catalog.yaml → criticality`, затем `⛔ не заполнено` |

При сверке с эталоном эти расширения расхождением не считаются; при
изменении текста на странице их нужно подтвердить у владельца процесса.

**Внешние ссылки (`refs.*`).** Числовые `page_id` живут только в
`criteria/criticality-criteria.yaml` → `external_refs` (`base_url` +
`refs.<name>.id/title`): шаблон не должен знать про конкретный инстанс
Confluence. Скрипт собирает `refs.<name>.url`; `decision_log` переопределяется
записью `catalog.yaml → systems.<код>.decision_log_page_id`, а `confluence_page`
— `systems.<код>.confluence_page_id`. Ссылка не задана → в артефакте
`⛔ не заполнено`, а `start` печатает `WARN external_refs.<name> не задан`.
`criteria check` запрещает «голые» числа, похожие на `page_id`, в `templates/`.

**Фингерпринт критериев.** `start` печатает в `CRITICALITY.md` (frontmatter,
поле `criteria_fingerprint`) и в `GENERATION.md` (§1, строка «Критерии
(фингерпринт)») sha256-12 от секций критериев, которые реально влияют на
артефакты: `meta`, `levels`, `axes`, `time_buckets`, `impact_matrix`, `cia`,
`final_matrix`, `express_method`, `enum_selection`, `inputs`, `scenarios`,
`provenance`. `validate` сравнивает значение с текущими критериями и печатает
WARN `criteria_fingerprint не совпадает: артефакты собраны на <old>, критерии
<new> → перезапустите make start-apply FORCE=1`; артефакты без поля — тоже WARN
(не ERROR). `start DIFF=1` показывает смену фингерпринта отдельной строкой.
mtime файла критериев для этого не используется: он правится постоянно и давал
бы вечно «устаревшие» артефакты.

**Провенанс правил в артефактах.** В таблицах «Использованные правила»
(`CRITICALITY.md` §7, `GENERATION.md` §5) `page N` рендерится markdown-ссылкой
через `criteria.external_refs.base_url`; правило с `source_status:
archived_carrier` получает сноску `†` с текстом своего `source_note` — видно,
почему канон опирается на архивную страницу.

**Ссылки в публикации.** Ни одна ссылка не печатается голым `pageId=`: формат
`«<точный title>» [<page_id>] <url>` (правило `confluence-links`). Название
берётся ТОЛЬКО из проверенного кеша `catalog.yaml → page_titles`
(`make verify-titles FIX=1`, R19); `title` в `INFORMATION.yaml`
(`facts.e2e_source_page`), `meta.sources.title`,
`external_refs.refs.<name>.title` и `architecture_page_title` реестра — это
объявления источника, в артефакт они не попадают. Нет записи кеша — печатается
`[page <id>] <url>`, название не выдумывается.

## 2. Правило «шаблон → артефакт»

1. Артефакт собирается **только** из шаблона. Свободный текст в генераторе
   запрещён: всё, что попадает в файл, должно быть в шаблоне.
2. Значения подставляет движок из контекста рендера. Контекст собирается в
   `build_render_context()` из трёх источников: `catalog.yaml`,
   `INFORMATION.yaml` и `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` (+ расчёт).
3. Отсутствующий путь — **ошибка шаблона**, а не пустая строка. Для
   необязательных полей обязателен фильтр `or_missing`, `default` или `yaml`.
4. Даты в артефактах — только `--date`. Других дат в шаблонах нет: это условие
   побайтового детерминизма.
5. Списки и словари выводятся через `{{#each}}`; пустой список — через
   `{{#if}}` + явный маркер `⛔ не заполнено`.

### Шаблоны принадлежат инструменту, а не проекту

`templates/` лежит внутри `.opencode/skills/criticality-gen/`, а не в корне
проекта. Это значит:

- шаблон меняется для всех ИС сразу и переезжает вместе с инструментом во
  внешний репозиторий; правка шаблона «под одну ИС» запрещена;
- скрипт читает шаблоны от `SKILL_DIR` (каталог скилла), а не от `PROJECT_ROOT`
  (корень проекта с `is/`), поэтому перенос `.opencode/` не ломает генерацию;
- если ИС нужен другой текст — это факт в `INFORMATION.yaml`, а не
  форк шаблона; если нужен другой артефакт — новый файл в `templates/` + запись
  в `START_TEMPLATES` и `make skill-check`.

## 3. Синтаксис движка

Движок — `render_template()` / `render_template_file()` в
`.opencode/skills/criticality-gen/scripts/criticality.py`. Только стандартная библиотека.

| Конструкция | Поведение |
|-------------|-----------|
| `{{ path.to.value }}` | подстановка; отсутствующий путь или `null` — `TemplateError` с файлом и строкой |
| `{{ path \| default: "текст" }}` | значение по умолчанию, если путь отсутствует/`null`/пусто |
| `{{ path \| default: .field }}` | аргумент фильтра — путь к полю текущего элемента `{{#each}}` (например `{{ .name \| default: .person \| default: .value }}`) |
| `{{ path \| or_missing }}` | `null`/пусто → `⛔ не заполнено` |
| `{{ path \| or_missing: null }}` | `null`/пусто → литерал (`null`, `—`, …) |
| `{{ path \| yaml }}` | значение как YAML-скаляр (`null`, кавычки при необходимости) |
| `{{ path \| brief }}` | компактный источник: `type: X, ref: Y` → `X: Y`, хвост после `"; "` отрезается, лимит 240 символов; адрес (`page_id`, `uid`, дашборд) сохраняется |
| `{{#if path}}…{{else}}…{{/if}}` | ветвление; отсутствующий путь — «ложь» |
| `{{#each list}}…{{/each}}` | цикл по списку: `{{ .field }}`, `{{ @index }}` |
| `{{#each map}}…{{/each}}` | цикл по словарю: `{{ @key }}`, `{{ . }}` |
| `{{! комментарий }}` | не выводится |

Блок-теги, стоящие отдельной строкой, съедают свою строку — поэтому шаблоны
читаются как обычный Markdown, без «лестницы» пустых строк.

Сообщение об ошибке всегда содержит файл, строку и путь:

```text
ERROR: шаблон .opencode/skills/criticality-gen/templates/CRITICALITY.md, строка 203: неизвестный путь facts.adr
ERROR: шаблон .opencode/skills/criticality-gen/templates/criticality-passport.yaml, строка 48: путь passport.object_sla = null (добавьте фильтр | or_missing или | yaml)
```

### 3.0. Производные ключи контекста (только для отчётов)

Эти ключи собирает `build_render_context()`; они не поля `INFORMATION.yaml`,
а свёртки уже посчитанных данных — чтобы отчёт не повторял один факт дважды:

| Ключ | Что содержит |
|------|--------------|
| `passport_cells.<поле>` | `value` / `status` / `source` по каждой строке паспорта (`evaluated_object`, `assigned_date`, `review_date`, `generated_at`, `approve_link`) |
| `score_trace.inputs[].source_brief` | внешний адрес источника входа без префикса `type:` — то, что печатает фильтр `brief` |
| `e2e_shared` | `impact` / `status` / `source`, если они одинаковы у всех E2E-процессов; иначе ключ отсутствует и печатается таблица |
| `workload_unit` | единица нагрузки (`клиентов за час пика`, …) — печатается один раз в §3 |

### 3.1. Контекст `requirements.*` (лист недостающих данных)

Шаблоны `DATA-REQUIREMENTS.md` и `DATA-REQUIREMENTS.yaml` рендерятся не через
`START_TEMPLATES`, а через `REQUIREMENTS_TEMPLATES` (команда `requirements`).
Контекст собирает `_requirements_context()`:

| Переменная | Что содержит |
|------------|--------------|
| `requirements.is_code` | код ИС |
| `requirements.generated_at` | дата листа: `--date` → `catalog.review_date/assigned_date` → `history[-1].date` → `null` (не `now()`) |
| `requirements.method` | метод, который выберет гейт на текущих данных (`express`/`detailed`) |
| `requirements.status` | `incomplete` / `complete` |
| `requirements.blocking_count`, `.advisory_count`, `.total_count` | сколько входов не закрыто: обязательных (blocking) / дополнительных (advisory) / всего записей в листе |
| `requirements.scenario_inputs`, `.scenario_inputs_count` | список и число входов выбранного сценария (простой — 4, сложный — 7) |
| `requirements.scenario_is_simple` | `true`, если гейт выбрал простой сценарий |
| `requirements.advisory_switches_scenario` | `true`, если в листе есть advisory-вход, входящий только в сложный набор: его заполнение переключит ИС на сложный сценарий (предупреждение в шапке блока `inputs`) |
| `requirements.items` | только незакрытые входы (blocking выбранного сценария + detailed-входы вне его blocking-набора), в порядке критериев; закрытое поле (значение + `status: confirmed`/`derived`/`legacy`) в лист не попадает |
| `requirements.blocking_items`, `.advisory_items` | те же входы, разделённые по роли |
| `requirements.carried_count` | сколько значений перенесено из существующего листа (слияние при записи; только ещё не принятые поля) |
| `requirements.gate_verdict`, `.gate_reason` | вердикт и причина гейта |

Элемент `requirements.items[]`:

| Поле | Откуда |
|------|--------|
| `.id`, `.description`, `.method`, `.blocking_label` | `criteria.inputs.required` |
| `.title`, `.definition`, `.why`, `.acceptable`, `.where`, `.whom`, `.confirm`, `.example` | `criteria.inputs.required[]` (метаданные процесса, `inputs.guidance_kind: convention`) |
| `.current_label` | текущее состояние входа в `INFORMATION.yaml` |
| `.value_fields` | под-оси для составных входов (`axes_scores`, `cia`), иначе `null` |
| `.value_yaml` | готовый YAML-блок значения (`    value: null` или `value:` + под-оси) — используется во фрагменте и в листе |
| `.value_extra_yaml` | `bucket`/`unit` из существующего листа сразу после `value` (пусто, если не заданы) |
| `.source_yaml` | ` null` либо блок `source:` с `type`/`ref` из существующего листа (слияние) |
| `.status` | `missing` либо сохранённый `confirmed`/`derived` из существующего листа |
| `.extra_yaml` | `notes` из существующего листа (пусто, если не задано) |
| `.carried` | `true`, если значение перенесено из существующего листа |
| `.switches_scenario` | `true` у advisory detailed-входа простого сценария: его заполнение переключает ИС на сложный сценарий (в сложном сценарии — `false`) |
| `.scenario_note` | текст последствия для `.switches_scenario: true` (`заполнение переключает ИС на сложный сценарий: обязательным станет time_to_impact`), иначе `""` |

`requirements.present` (в контексте `start`) — существует ли
`DATA-REQUIREMENTS.md` в папке ИС; по нему §7 `CRITICALITY.md`/`GENERATION.md`
ставит ссылку на остаток требований.

### 3.2. Контекст `research.*` (план сбора данных)

Шаблон `RESEARCH-PLAN.md` рендерится командой `collect`; контекст собирает
`_research_context()`.

| Переменная | Что содержит |
|------------|--------------|
| `research.is_code` | код ИС |
| `research.generated_at` | дата плана: `--date` → `catalog.review_date` → `history[-1].date` → `null` (не `now()`) |
| `research.method`, `.status`, `.gate_verdict`, `.gate_reason` | метод, который выберет гейт, и его вердикт |
| `research.missing_blocking`, `.missing_advisory`, `.missing_total` | сколько входов не закрыто |
| `research.keywords` | список слов для поиска в Confluence |
| `research.fields` | незакрытые входы: `.id`, `.title`, `.blocking_label`, `.method`, `.acceptable`, `.where`, `.whom`, `.confirm`, `.is_load` |
| `research.closed_fields` | закрытые входы одной строкой: `.id`, `.value`, `.source_type` |
| `research.checked_inputs` | входы, у которых прошлый обход не дал результата: `.id`, `.text` |
| `research.exhausted_inputs` | то же, но адреса исчерпаны; `research.exhausted_shared` — `{ids, text}`, если текст одинаков у нескольких входов |
| `research.confluence_pages` | `.page_id`, `.title`, `.role`, `.look_for`, `.url` (из `catalog.yaml` и SSoT `links.yaml`) |
| `research.missing_page_ids` | ⛔-строки по пустым nullable `page_id` в `catalog.yaml` (`dr_page_id`, `criticality_source_page_id`, `decision_log_page_id`): без них план не знает страницу, на которую ссылается таблица входов |
| `research.grafana.folder_uid`, `.folder_name` | папка продукта в Grafana |
| `research.grafana.dashboards` | `.uid`, `.title`, `.url` — дашборды из `links.yaml` карточки ИС |
| `research.grafana.hints` | поисковые запросы: код ИС, компоненты-шлюзы, слова `gateway`/`krakend`/`nginx`/`vts` |
| `research.grafana.queries` | `.field`, `.expr`, `.window`, `.note` — готовые PromQL (только для измеримых входов) |
| `research.product_scope` | `.product`, `.product_root_page_id`, `.product_root_ref`, `.product_root_url`, `.scope_page_id`, `.scope_url`, `.cql`, `.instructions[]`, `.problems[]` — Product scope продукта: где искать E2E-процессы ИС и каким CQL находятся функциональные области (`label = "functional-area" and space = currentSpace() and ancestor = <page_id>`) |
| `research.deep_search` | по каждому незакрытому входу: `.id`, `.title`, `.role`, `.shallow[]` (запросы tier 1), `.deep[]` (запросы tier 2) — из реальных кода, названия, продукта, команды, `page_id` и логинов `contacts` |
| `research.steps`, `.step_counts` | число шагов плана и разбивка по видам (`pages`, `dashboards`, `hints`, `queries`, `product_scope`, `deep`) |
| `research.folder_rel`, `.data_requirements_path` | папка ИС и путь к `DATA-REQUIREMENTS.yaml` |

Текст плана (ловушки источников, формула, порядок фиксации) живёт в шаблоне, а
не в генераторе: генератор подставляет только факты — страницы, дашборды,
запросы, адресатов из критериев.

### 3.3. Контекст `findings.*` (код сервисов)

Шаблон `SERVICE-FINDINGS.md` рендерится командой `services` (запись — только с
`--apply`); контекст собирает `_services_context()`.

| Что | Значение |
|-----|----------|
| Назначение | показать, что говорит документация клонов сервисов: назначение, потребители, нормативы, потоки, данные — и для каких входов это **основание** |
| Кто создаёт | `make services-apply IS=<код>` (`criticality.py services --apply`) |
| Вход | `INFORMATION.yaml#components[]` (`name`, `git_repository`, `lifecycle`), клоны `apps/<код ИС>/<сервис>/` (`docs/`, `openspec/`, SLO-конфиги) |
| Куда пишется | `is/<код ИС>/SERVICE-FINDINGS.md`; перегенерируется, руками не править |

Frontmatter (все поля — из `findings.*`):

| Поле | Что содержит |
|------|--------------|
| `title` | заголовок отчёта по коду ИС |
| `is_code` | код ИС |
| `generated_at` | дата отчёта: `--date` → `catalog.review_date` → `history[-1].date` → `null` (не `now()`) |
| `services_total` | сколько компонентов с `git_repository` у ИС |
| `services_skipped` | сколько пропущено по `lifecycle` (сейчас — `closed`) |
| `services_cloned` | сколько клонов прочитано без ошибки |
| `docs_found`, `openspec_found` | у скольких сервисов есть `docs/` и `openspec/` |
| `slo_configs_found` | у скольких сервисов есть настоящий SLO-конфиг (`slo-kit.yaml`, `slo.yaml`, `alerts.yaml`, `sloth.yaml`); `Chart.yaml`, `values*.yaml`, `deploy/` и `.gitlab-ci.yml` — инфраструктура, а не SLO: они видны в §7, но счётчик не увеличивают |

Разделы отчёта:

| Раздел | Что внутри |
|--------|------------|
| §1 «Сервисы» | таблица `сервис / репозиторий / ветка / docs/ / openspec/ / SLO-конфиг` + дерево файлов `docs/` и `openspec/` |
| §2 «Пропущенные сервисы (lifecycle)» | таблица `сервис / репозиторий / lifecycle / причина` из `service_lifecycle.skip_reason`; строка `lifecycle не указан` для компонентов без значения |
| §3 «Назначение и потребители» | цитаты «файл:строка» о назначении, потребителях, `purpose`/`consumer` |
| §4 «Нормативы (SLO/SLA/RTO)» | цитаты, где `SLA`/`SLO`/`RTO`/`RPO` стоят рядом с числом и единицей, плюс процент доступности, число рядом с «простой» и `objective:` + колонка «пригодно для `object_sla`» (процент доступности — не пригодно) |
| §5 «Потоки данных и автоматизация» | Kafka-топики, шедулеры, кроны; при усечении — сколько всего совпадений |
| §6 «Что даёт основание для входов» | таблица `вход / основание / сервис / файл:строка`; `object_sla` — только цитата с минутами простоя |
| §7 «Не найдено» | чего нет: `docs/`, `openspec/`, SLO-конфиг, основание для входа, ошибки клонирования |
| §8 «Ограничение» | `Клоны сервисов используются только для чтения. Сборка и запуск запрещены.` + напоминание про `lifecycle: closed` |

Ограничения объёма — константы скрипта `SERVICE_TOTAL_NORMS` и
`SERVICE_TOTAL_FLOWS` (по 200 строк на раздел); при усечении шаблон печатает,
сколько совпадений всего.

Отчёт **не пишет** в `INFORMATION.yaml` и не закрывает входы: цитата из клона —
основание, значение подтверждает человек и принимает `enrich` (R14).

### 3.4. Контекст `mr.*` (описания MR)

`MR-dochub.md` рендерит `_publish_mr_text()` (`publish`), `MR-ssot.md` —
`_ssot_mr_text()` (`ssot`). Оба идут через `render_template_file_strict()`:
**пустая переменная — ошибка** (`не заполнено поле '<имя>' в шаблоне <файл>`,
код 1, MR не создаётся), а фильтры `or_missing` и `default` в этих шаблонах
запрещены. Причина: описание MR уходит человеку как есть — подставлять
`⛔ не заполнено` или выдуманный дефолт недопустимо.

Git не пропускает переводы строк в push-опциях («must not contain a NUL or LF
character»), поэтому в `merge_request.description` уходит тот же рендер,
сжатый в одну строку (`_mr_push_option`), а полный многострочный текст ставится
сразу после пуша через GitLab API: `GET /merge_requests?source_branch=…` →
при расхождении `PUT /projects/:id/merge_requests/:iid` (`_mr_description_sync`).
Токен — `GITLAB_TOKEN`; адрес API и проект берутся из `remote.origin.url` клона.
Без токена пуш проходит, печатается `WARN: … описание не верифицировано`.

`MR-dochub.md` (9 блоков: что и зачем, метод, входы, расчёт, провенанс,
чек-лист, ограничения, ссылка на задачу, расхождения с существующим MR):

| Переменная | Что содержит |
|------------|--------------|
| `mr.title` | заголовок `<task>: Паспорт критичности <код> — <уровень dochub>` |
| `mr.code`, `.name`, `.contour`, `.evaluated_object`, `.dochub_key`, `.dochub_path` | идентификация ИС и файла публикации |
| `mr.level_before`, `.level_before_text`, `.level_dochub`, `.level_ssot` | уровень до публикации (в dochub), готовая строка «уровень до + уровень SSoT-реестра с вердиктом совпадает/расходится», enum dochub, уровень паспорта репозитория |
| `mr.task`, `.task_url`, `.branch`, `.closes` | задача, ссылка `browse` из `criteria.external_refs.jira_browse_base`, ветка `feature/<task>`, `Closes <task>` |
| `mr.scenario`, `.method`, `.status` | выбранный сценарий, метод расчёта и его статус |
| `mr.input_rows`, `.calc_rows`, `.provenance_rows`, `.checklist`, `.checklist_note`, `.limitations` | готовые строки блоков (списки строк, а не объекты) |
| `mr.confluence_base` | база ссылки Confluence (`external_refs.base_url`) — по ней блок «Провенанс» резолвит `page_id` |

`MR-ssot.md` (что меняется, основание, проверка, что не меняется, `Closes`):

| Переменная | Что содержит |
|------------|--------------|
| `mr.title` | заголовок `<task>: критичность <код> — <уровень>` |
| `mr.changes[]` | `.field`, `.before`, `.after` — точечные правки `severity`; отсутствующее «было» — `—` |
| `mr.passport_mr` | путь паспорта в dochub, заголовок его MR и ветка |
| `mr.passport_mr_url` | URL dochub-MR (основание; из `.publish/<код>-MR.url` или `--passport-mr-url`); пусто — ошибка |
| `mr.approve_link` | тред согласования (`catalog.yaml → approve_link`) |
| `mr.task` | ключ задачи |
| `mr.checklist[]`, `.unchanged[]` | чек-лист ревьюера и перечень того, что правка не трогает |

### 3.5. Контекст `actions.*`: E2E-процессы и ссылка на АДР

Два поля action-пакета имеют собственную семантику — их нельзя подставлять
«как есть» из `facts`, иначе публикация выдаст одно за другое.

**`actions.e2e_list`** — список E2E-процессов ИС (для `{{#each}}`), источник —
`facts.e2e_processes`, собранный из Product scope продукта или каталога сквозных
процессов (`make research` → `RESEARCH.md`). Элемент — строка `<название
процесса>`, а если у процесса есть сила подтверждения или `source` —
`<название> (шагов <N> из <M>, <evidence>; источник: <url>)`: SRE при
согласовании проверяет именно доказательство (`direct`, «шагов N из M»), а не
голый перечень. Процесс без названия пропускается. Пустой список рендерится
через `{{else}}` → `actions.e2e_text`:

| `facts.e2e_status` | Что печатается |
|--------------------|----------------|
| `not_filled` | `⛔ не заполнено — колонка «Сквозной бизнес-процесс (e2e)» в Product scope <ссылка на страницу> не заполнена.` (страница — `facts.e2e_source_page`; ссылка = «title» [page_id] url из кеша `page_titles`, иначе `[page <id>] url`) |
| `not_found` | `⛔ не найдено — ни одна функциональная область Product scope не указывает <код>; проверьте Product scope: <url или catalog.yaml → product_scope_page_id не заполнен>` |
| пусто / иное | `⛔ не заполнено` |

Пустая ячейка e2e — это отсутствие данных (`not_filled`), а не «процесса нет»:
процесс не выдумывается. `not_found` означает, что ни одна функциональная
область не называет ИС вовсе.

**`actions.adr_link` + `actions.adr_basis`** — ссылка на АДР и её основание.
Цепочка строго в этом порядке:

| Шаг | Условие | `adr_basis` | Значение `adr_link` |
|-----|---------|-------------|---------------------|
| 1 | первая запись `facts.adr[]` с непустым `link` | `adr` | сам `link` |
| 2 | `catalog.yaml → systems.<код>.architecture_page_id` (или `catalog.yaml → architecture_page_id`) | `architecture` | `<url> (архитектура ИС; АДР не найден)` |
| 3 | `catalog.yaml → systems.<код>.confluence_page_id` | `is_page` | `<url> (страница ИС; АДР не найден)` |
| 4 | ничего не заполнено | `none` | `null` → в шаблоне `⛔ не заполнено` |

Основание печатается рядом со ссылкой (`actions.adr_basis_note`, в
`GENERATION.md` — строка «Ссылка на АДР (adr_basis)»), чтобы архитектура ИС не
выдавалась за АДР. Журнал решений (`decision_log_page_id`) в эту цепочку **не
входит**: его роль — маршрут глубокого поиска
([search.md](../references/search.md)), а не подмена АДР. `adr_basis = none` —
`WARN` в `validate`.

## 4. Запрет ручной правки сгенерированного

Сгенерированные файлы (`criticality-passport.yaml`, `CRITICALITY.md`,
`GENERATION.md`, `actions/*.md`) содержат в шапке явную пометку: правки будут
перезаписаны при следующем `make start-apply`.

Правильный путь изменения артефакта:

1. Поправить факт в `is/<код ИС>/INFORMATION.yaml`
   (`criteria_inputs`, `facts`, `identity` — через SSoT).
2. Поправить правило в `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` (если меняется
   методика).
3. `make start IS=<код> DIFF=1` → посмотреть diff.
4. `make start-apply IS=<код> FORCE=1`.
5. `make validate`.

Ручная правка сгенерированного файла допустима только как аварийная мера и
обязана сопровождаться правкой источника, иначе следующий прогон её затрёт.

## 5. Как добавить новый шаблон

1. Положить файл в `.opencode/skills/criticality-gen/templates/` (или `.opencode/skills/criticality-gen/templates/actions/`).
2. Зарегистрировать путь в `START_TEMPLATES` в `.opencode/skills/criticality-gen/scripts/criticality.py` (для артефактов ИС) или в `REQUIREMENTS_TEMPLATES` (для листа требований).
3. Добавить переменные в `build_render_context()` (или в
   `_generation_context()` для отчёта). Если переменная необязательная —
   предусмотреть в шаблоне фильтр `or_missing`.
4. Добавить файл в `_start_artifacts()` (если он пишется на диск) и в таблицу
   §1 этого документа.
5. Проверить: `make start IS=<код>` (dry-run по умолчанию, `DRY=1`), затем
   `make selftest`, `make validate`, `make docs-check`.
   Флаг `--dry-run` — это флаг CLI (`python3 .opencode/skills/criticality-gen/scripts/criticality.py start --dry-run`);
   в `make start` он **не нужен** и перехватывается make как собственный флаг
   (ошибка «unknown option»/игнорирование). Для записи артефактов —
   `make start-apply IS=<код> FORCE=1`.
6. Проверить детерминизм: два прогона с одной `--date` дают одинаковый
   `sha1sum`.

## 6. Шаблоны скиллов (`.opencode/skills/criticality-gen/meta-templates/`)

Отдельный каталог для шаблонов **документации скиллов** (не артефактов ИС).
Он обобщённый: не содержит ни критичности, ни имён полей паспорта. Назначение —
чтобы новый скилл начинался с одинаковой структуры, а не с чистого листа.

| Файл | Куда копировать | Что описывает |
|------|-----------------|---------------|
| `SKILL.md.template` | `skills/<name>/SKILL.md` | frontmatter (`name`, `version`, `description` с «Используйте когда…», `user-invocable`, `compatibility`, `allowed-tools`), «Когда использовать», «Что делает», «Разделение ответственности», «Быстрый старт», «Артефакты», «Правила», «Ограничения» |
| `workflow.md.template` | `skills/<name>/references/workflow.md` | фазы: вход / действие / выход / гейт / кто выполняет; правила перехода; поведение при провале гейта |
| `rules.md.template` | `skills/<name>/references/rules.md` | нумерованные правила с полями «Правило / Зачем / Как проверить / Что делать при нарушении»; обязательные разделы «Запреты», «Провенанс», «Детерминизм», «Обработка нехватки данных» |
| `artifacts.md.template` | `skills/<name>/references/artifacts.md` | реестр: артефакт / путь / шаблон / кто создаёт / входные данные / политика перезаписи / обязателен |
| `dependencies.md.template` | `skills/<name>/references/dependencies.md` | зависимость / тип (`cli\|mcp\|repo\|access`) / обязательна / проверка / что делать если нет |
| `checklist.md.template` | `skills/<name>/references/checklist.md` | приёмка: перед запуском / во время / перед сдачей / после сдачи |

Правила работы с этим каталогом:

1. Шаблон **копируется**, а не редактируется на месте. Изменение шаблона
   меняет все будущие скиллы — это осознанное действие, а не способ поправить
   один скилл.
2. Все места подстановки — `{{ }}`; в готовом скилле их быть не должно
   (`grep -rn "{{" skills/` пуст, проверяется `make skill-check`).
3. Шапка-комментарий шаблона («Скопируйте в `skills/<name>/references/<file>.md`»)
   в готовый файл не переносится.
4. Готовый пример заполнения — `.opencode/skills/criticality-gen/`; разбор — [11-skill.md](11-skill.md).
5. Шаблоны скиллов не участвуют в рендере артефактов: движок
   `.opencode/skills/criticality-gen/scripts/criticality.py` читает только пути из `START_TEMPLATES`, и
   `.opencode/skills/criticality-gen/meta-templates/` там нет.

## 7. Связанные документы

- [09-pipeline.md](09-pipeline.md) — конвейер и раздел «Генерация (`start`)».
- [07-scripts.md](07-scripts.md) — CLI-справочник команды `start`.
- [08-criteria.md](08-criteria.md) — правила расчёта, которые попадают в
  `score_trace`.

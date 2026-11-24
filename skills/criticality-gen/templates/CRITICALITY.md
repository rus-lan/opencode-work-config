---
type: criticality-passport
is_code: {{ identity.code }}
is_name: {{ identity.name | or_missing }}
contour: {{ identity.contour }}
asset: {{ identity.asset | or_missing }}
product: {{ identity.product | or_missing }}
arch_code: {{ identity.arch_code | or_missing }}
team: {{ identity.team | or_missing }}
criticality: {{ passport.object_criticality_estimation | or_missing: null }}
criticality_ssot: {{ identity.criticality_ssot | or_missing: null }}
assigned_date: {{ identity.assigned_date | or_missing: null }}
review_date: {{ identity.review_date | or_missing: null }}
status: {{ identity.status }}
approve_link: {{ passport.approve_link | yaml }}
tags: [критичность, паспорт-критичности, ис, {{ identity.contour }}, {{ identity.name_slug }}, {{ identity.product_slug }}, {{ identity.criticality_slug }}]
aliases: [{{ identity.name | or_missing }}, {{ identity.code }}, {{ identity.arch_code | or_missing }}]
source_confluence: {{ refs.confluence_page.url | or_missing }}
criteria_fingerprint: {{ meta.criteria_fingerprint }}
---

{{#if score_trace.provisional}}
> ## ⚠ Оценка предварительная
>
> Не подтверждены входы: `{{ score_trace.waived_inputs }}`. Оценка построена по
> **диапазону** допустимых значений этих входов, а не по подтверждённым данным:
> человек явно отказался от данных (`status: waived`, правило R17). Паспорт не
> считается подтверждённым, пока входы не закрыты значением с источником.
>
> | Вход | Причина отказа | Допущение в расчёте |
> |------|----------------|---------------------|
{{#each score_trace.assumptions}}> | `{{ .input }}` | {{ .reason | md_cell }} | {{ .mode_label }} |
{{/each}}>
> **Диапазон уровня:** {{ score_trace.provisional_range.min }} – {{ score_trace.provisional_range.max }}{{#if score_trace.provisional_degenerate}} — вход не влияет на уровень выбранного метода{{/if}}
> (в паспорт записан `{{ score_trace.final_level }}` — консервативная оценка по
> режиму допущения).
>
> **Для точной оценки нужны входы:** {{ score_trace.waived_inputs }} — значение
> с `source: {type, ref}` и `status: confirmed` (см. `DATA-REQUIREMENTS.md`).
{{/if}}

# Паспорт критичности: {{ identity.name | or_missing }} ({{ identity.code }})

Оценка {{ passport.assigned_date | or_missing }} · переоценка {{ passport.review_date | or_missing }} · статус `{{ identity.status }}` · метод {{ score_trace.method_label }} (`{{ score_trace.status }}`).
Файл производный: правится через `INFORMATION.yaml` и `make start-apply`, не руками. Машиночитаемый источник — [`criticality-passport.yaml`](criticality-passport.yaml).

## 1. Паспорт

| Поле | Значение | Статус | Источник / обоснование |
|------|----------|--------|------------------------|
{{#each passport_rows}}| {{ .field }} | {{ .value }} | {{ .status }} | {{ .source | md_cell }} |
{{/each}}

Статусы: `✅ подтверждено` — есть источник или подтверждение SRE; `⚠️ требует подтверждения` — значение выведено косвенно; `⛔ не заполнено` — данных нет.

## 2. Расчёт

{{#if score_trace.express}}
| Шаг | Значение |
|-----|----------|
{{#each score_trace.express.rows}}| {{ .label }} | {{ .value }} |
{{/each}}
{{else}}
| Параметр | Значение |
|----------|----------|
{{#each score_trace.axes}}| {{ .title }} (`{{ .id }}`) | {{ .score }} — {{ .scale | or_missing: "—" }} |
{{/each}}| max по осям | {{ score_trace.max_score | or_missing }} |
| Время до неприемлемого ущерба | {{ score_trace.bucket | or_missing }} ({{ score_trace.bucket_definition | or_missing }}) |
| Бизнес-уровень (impact_matrix) | {{ score_trace.business_level | or_missing }} |
{{#each score_trace.cia_rows}}| CIA: {{ .parameter }} | {{ .level }} (F = {{ .weight }}) |
{{/each}}| V = 6·(F(C)+F(I)+F(A)) | {{ score_trace.cia_value | or_missing }} |
| Уровень защищённости | {{ score_trace.protection | or_missing }} ({{ score_trace.protection_scale | or_missing }}) |
| Итог (final_matrix) | {{ score_trace.final_level | or_missing }} |
{{/if}}

**Итоговая критичность:** {{ score_trace.final_level | or_missing }} · возможные результаты расчёта: {{ levels.inline_calculated }}.
Уровень {{ levels.extra }} существует только в dochub-паспорте (в SSoT маппится по `levels.dochub_to_ssot`).

{{#if score_trace.rules}}
**Правила:**

| Правило | kind | Источник |
|---------|------|----------|
{{#each score_trace.rules}}| `{{ .name }}` | {{ .kind }} | {{ .source }} |
{{/each}}
{{/if}}
## 3. Входы

| Вход | Значение | Источник | Статус |
|------|----------|----------|--------|
{{#each score_trace.inputs}}| `{{ .id }}` | {{ .value }} | {{ .source_brief | brief }} | {{ .status }} |
{{/each}}
Нагрузка измеряется в {{ workload_unit }}.

## 4. E2E-процессы

{{#if facts.e2e_processes}}
| Процесс | Обоснование | Шагов | Источник |
|---------|-------------|-------|----------|
{{#each facts.e2e_processes}}| {{ .name | or_missing }} | {{ .evidence | or_missing }} | {{ .steps_label | or_missing }} | {{ .source | or_missing }} |
{{/each}}
Влияние (общее для всех процессов): {{ e2e_shared.impact | or_missing | brief }}. Статус: {{ e2e_shared.status | or_missing }}.
{{else}}
| Процесс | Обоснование | Шагов | Источник |
|---------|-------------|-------|----------|
| E2E-процессы не отрисованы/не привязаны к ИС | ⛔ не заполнено | — | — |
{{/if}}

{{#if facts.e2e_source_page.url}}
Колонка «Сквозной бизнес-процесс (e2e)» в Product scope {{ facts.e2e_source_page.link | or_missing }} не заполнена.
{{/if}}

## 5. Факты ИС

{{#if facts.impact_chain}}
| Что перестаёт работать | Кто замечает первым | Источник | Статус |
|------------------------|---------------------|----------|--------|
{{#each facts.impact_chain}}| {{ .what_breaks | or_missing }} | {{ .who_notices | or_missing }} | {{ .source | or_missing | brief }} | {{ .status | or_missing }} |
{{/each}}
{{else}}
⛔ не заполнено — цепочка влияния не описана.
{{/if}}
### Поддержка и дежурства

| Показатель | Значение |
|------------|----------|
| Инциденты по SLA | {{ facts.support.sla_incidents | or_missing }} |
| Доступность | {{ facts.support.availability | or_missing }} |
| Часы поддержки | {{ facts.support.hours | or_missing }} |
| Статус данных | {{ facts.support.status | or_missing }} |
| Источник | {{ facts.support.source | or_missing: "—" }} |

{{#if duties}}
| Дежурство | Кто | С |
|-----------|-----|---|
{{#each duties}}| {{ .team | or_missing }} | {{ .members | or_missing: "—" }} | {{ .startTime | or_missing: "—" }} |
{{/each}}
{{else}}
⛔ не заполнено — дежурства не зафиксированы.
{{/if}}
### Зависимости

{{#if facts.dependencies.upstream}}
**Upstream:**

| Система | Тип связи | Источник | Статус |
|---------|-----------|----------|--------|
{{#each facts.dependencies.upstream}}| {{ .name | or_missing }} | {{ .type | or_missing }} | {{ .source | or_missing | brief }} | {{ .status | or_missing }} |
{{/each}}
{{else}}
Upstream: ⛔ не заполнено.
{{/if}}
{{#if facts.dependencies.downstream}}
**Downstream:**

| Система | Тип связи | Источник | Статус |
|---------|-----------|----------|--------|
{{#each facts.dependencies.downstream}}| {{ .name | or_missing }} | {{ .type | or_missing }} | {{ .source | or_missing | brief }} | {{ .status | or_missing }} |
{{/each}}
{{else}}
Downstream: ⛔ не заполнено.
{{/if}}
### Компоненты

{{#if components}}
| Компонент | Описание | Язык | Репозиторий | Клонирование |
|-----------|----------|------|-------------|--------------|
{{#each components}}| {{ .name | or_missing }} | {{ .description | or_missing }} | {{ .language | or_missing }} | {{ .git_repository | or_missing }} | {{ .clone_status | or_missing }} |
{{/each}}
{{else}}
⛔ не заполнено — `components` пуст (гейт `make check` блокирует такую ИС).
{{/if}}
### Размещение

{{#if resources}}
| Ресурс | Значение | Тип | Окружение |
|--------|----------|-----|-----------|
{{#each resources}}| {{ .name | or_missing }} | {{ .value | or_missing: "—" }} | {{ .type | or_missing: "—" }} | {{ .environment | or_missing: "—" }} |
{{/each}}
{{else}}
⛔ не заполнено — `resources` пуст.
{{/if}}
### Данные и риски

{{#if facts.data_classification}}
| Вид | Значение | Источник | Статус |
|-----|----------|----------|--------|
{{#each facts.data_classification}}| {{ .kind | or_missing }} | {{ .value | or_missing }} | {{ .source | or_missing | brief }} | {{ .status | or_missing }} |
{{/each}}
{{else}}
Классификация данных: ⛔ не заполнено (ПДн / КТ / SORM не зафиксированы).
{{/if}}
{{#if facts.risks}}
| Риск | Описание | Владелец | Источник | Статус |
|------|----------|----------|----------|--------|
{{#each facts.risks}}| {{ .title | or_missing }} | {{ .description | or_missing }} | {{ .owner | or_missing }} | {{ .source | or_missing | brief }} | {{ .status | or_missing }} |
{{/each}}
{{else}}
Риски: ⛔ не заполнено.
{{/if}}
### ADR

{{#if facts.adr}}
| ID | Название | Статус | Ссылка |
|----|----------|--------|--------|
{{#each facts.adr}}| {{ .id | or_missing }} | {{ .title | or_missing }} | {{ .status | or_missing }} | {{ .link | or_missing }} |
{{/each}}
{{else}}
ADR: не заведены.
{{/if}}
{{#if refs.decision_log.url}}
Decision Log: {{ refs.decision_log.url }}
{{else}}
Decision Log: ⛔ не указан (`catalog.yaml → systems.<код>.decision_log_page_id` пуст).
{{/if}}
## 6. Публикация

| Артефакт | Ссылка | Статус | Источник |
|----------|--------|--------|----------|
| `task` | {{ actions.task_link | or_missing }} | `{{ actions.jira.status }}` | `catalog.yaml → jira_task` |
| `mr` | {{ actions.mr_link | or_missing }} | {{#if actions.mr_link}}создан{{else}}не создан{{/if}} | `.publish/{{ identity.code }}-MR.url` |
| `ssot_card` | {{ actions.ssot_card_link | or_missing }} | — | `criteria.external_refs.ssot_card_base` |
| `ssot_mr` | {{ actions.ssot_mr_ref | or_missing }} | {{#if actions.ssot_mr_link}}создан{{else}}не создан{{/if}} | `.ssot/{{ identity.code }}-MR.url` |
| `approve_link` | {{ passport.approve_link | or_missing }} | {{ passport_cells.approve_link.status }} | {{ passport_cells.approve_link.source | brief }} |

`task` — задача Jira; `mr` — паспорт в dochub; `ssot_card` — карточка ИС; `ssot_mr` — критичность в SSoT; `approve_link` — тред подтверждения.

## 7. Что не подтверждено

{{#if todo_items}}
{{#each todo_items}}- [ ] {{ . }}
{{/each}}
{{else}}
Открытых пунктов не зафиксировано.
{{/if}}
{{#if conflicts}}
**Расхождения с реестром** (не перезаписаны автоматически — нужно решение владельца):

| Поле | Расчёт | Реестр | Правило | Примечание |
|------|--------|--------|---------|------------|
{{#each conflicts}}| `{{ .field }}` | {{ .computed }} | {{ .actual }} | {{ .rule }} | {{ .note }} |
{{/each}}
{{/if}}
{{#if score_trace.conventions}}
**Conventions** (не из источника, требуют подтверждения):

| Правило | status | rationale |
|---------|--------|-----------|
{{#each score_trace.conventions}}| `{{ .name }}` | {{ .status }} | {{ .rationale }} |
{{/each}}
{{/if}}
Недостающие входы: {{#if requirements.present}}[DATA-REQUIREMENTS.md](DATA-REQUIREMENTS.md) — чего не хватает, где взять и у кого{{else}}нет, все входы заполнены{{/if}}.

## 8. История оценок

| Дата | Критичность | Кто | Ссылка на подтверждение |
|------|-------------|-----|-------------------------|
{{#each history}}| {{ .date | or_missing }} | {{ .criticality | or_missing }} | {{ .who | or_missing }} | {{ .link | or_missing }} |
{{/each}}
## 9. Источники

{{#each sources}}- {{ .label }}: {{ .link }}
{{/each}}
{{#if links}}
- Ссылки ИС (`INFORMATION.yaml` → `links`): {{#each links}}{{ @key }} — {{ . }}; {{/each}}
{{/if}}

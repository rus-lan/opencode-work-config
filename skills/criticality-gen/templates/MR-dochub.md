# {{ mr.title }}

| Параметр | Значение |
|----------|----------|
| ИС | `{{ mr.code }}` — {{ mr.name }} (контур `{{ mr.contour }}`) |
| Уровень | **{{ mr.level_dochub }}** (SSoT: `{{ mr.level_ssot }}`) |
| Было | {{ mr.level_before_text }} |
| Метод | `{{ mr.method }}`, {{ mr.status }}, сценарий `{{ mr.scenario }}` |
| Входы | {{ mr.inputs_summary }} |
| Задача | {{ mr.task }} — {{ mr.task_url }} |
| Ветка | `{{ mr.branch }}` |
| Файл | `{{ mr.dochub_path }}` |
| Объект | `{{ mr.evaluated_object }}`, ключ `{{ mr.dochub_key }}` |

## Что меняется

{{ mr.change_summary }}

## Расчёт

Итог расчёта — **{{ mr.level_dochub }}**. Он берётся из последней строки блока
(ячейка `final_matrix[бизнес-уровень][уровень защищённости]`): значение паспорта
в блоке 1 обязано совпадать с ней.

{{#each mr.calc_rows}}- {{ . }}
{{/each}}

## Провенанс входов

Источник каждого входа — `type: ref`. Как открыть источник:

- `confluence: page_id=N` → {{ mr.confluence_base }}N;
- `grafana: dashboard uid=U` — дашборд Grafana по uid;
- `gitlab: <проект>:<путь>` — файл репозитория по этому пути;
- `ssot: <путь>#<поле>` — файл SSoT по пути и полю;
- `manual: <кто>, <дата>` — решение без ссылки: проверяются автор и дата.

{{#if mr.provenance_rows}}
{{#each mr.provenance_rows}}- {{ . }}
{{/each}}
{{/if}}

## 6. Чек-лист ревьюера

{{#each mr.checklist}}- [ ] {{ . }}
{{/each}}

> {{ mr.checklist_note }}

## 7. Известные ограничения

{{#each mr.limitations}}- {{ . }}
{{/each}}

## 8. Ссылка на задачу

Closes {{ mr.closes }}

## 9. Расхождения с существующим MR

Проверка открытых MR по этому паспорту (GitLab API, `state=opened`). Таблица
показывает, чем расчёт отличается от значений в уже открытом MR — ревьюер
видит, почему второй паспорт предлагает другие числа.

| поле | в MR | в расчёте | источник расчёта |
|------|------|-----------|------------------|
{{#each mr.duplicate_rows}}{{ . }}
{{/each}}

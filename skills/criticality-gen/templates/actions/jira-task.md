# Action-пакет: задача в Jira

> Сгенерировано `criticality.py start` из `templates/actions/jira-task.md`; руками не править — меняйте `INFORMATION.yaml`.
> **Статус:** `{{ actions.jira.status }}` · {{#if actions.reassessment}}переоценка{{else}}первичная оценка{{/if}} · **Задача:** {{ actions.jira.task_key | or_missing }}

## 1. Поля задачи

| Поле Jira | Значение | Провенанс |
|-----------|----------|-----------|
| Summary | {{ actions.jira.summary }} | `catalog.yaml` → `name`, `code` |
| Тип задачи | {{ actions.jira.project_type }} | процессом D6.1.1 не задан |
| Проект | {{ actions.jira.project_type }} | процессом D6.1.1 не задан |
| Метки (labels) | {{#each actions.labels}}`{{ . }}` {{/each}} | `templates/publication.md` → чеклист |
| Исполнитель — PdM | {{ actions.jira.assignee_pdm | or_missing }} | `INFORMATION.yaml` → `contacts` (`groups.po` → `groups.dm`), логин |
| Исполнитель — TL | {{ actions.jira.assignee_tl | or_missing }} | `INFORMATION.yaml` → `contacts` (`groups.tl`), логин |
| Автор (reporter) | {{ actions.jira.author | or_missing }} | `INFORMATION.yaml` → `contacts` (`groups.tl`), иначе `catalog.yaml` → `sa` |
| Код ИС | `{{ identity.code }}` | `catalog.yaml` |
| Архитектурный код | {{ identity.arch_code | or_missing }} | `catalog.yaml` → `arch_code` |
| Команда | {{ identity.team | or_missing }} | `catalog.yaml` → `team` |

Summary — без `[TL]`: префикс Jira добавляет сама из поля «Роль» (`customfield_12750`).

## 2. Описание задачи (копировать как есть)

```text
Оценка критичности ИС {{ identity.code }} — {{ identity.name | or_missing }}

Архитектурный код {{ identity.arch_code | or_missing }}; продукт {{ identity.product | or_missing }}; контур/актив {{ identity.contour }} / {{ identity.asset | or_missing }}; команда {{ identity.team | or_missing }}.
Критичность (расчёт / SSoT): {{ passport.object_criticality_estimation | or_missing }} / {{ identity.criticality_ssot | or_missing }}. ADR: {{ actions.adr_link | or_missing }}

E2E-процессы, в которых участвует ИС:
{{#if actions.e2e_list}}
{{#each actions.e2e_list}}- {{ . }}
{{/each}}
{{else}}
- {{ actions.e2e_text }}
{{/if}}

Причина: {{#if actions.reassessment}}плановая переоценка{{else}}первичная оценка{{/if}}, метод {{ score_trace.method }}, статус {{ score_trace.status }}. Приложить: criticality-passport.yaml, GENERATION.md
```

## 3. Как создать (вручную)

1. Открыть Jira → создать задачу в проекте продукта (catalog.yaml → product).
2. Summary и Description — из раздела 2 выше (копировать как есть).
3. Проставить метки из раздела 1 (`Mission_Assesment`; для переоценки — ещё `Reassessment`).
4. Исполнитель — PdM или TL из раздела 1. Если там `⛔ не заполнено` — уточнить
   владельца и дописать его в `INFORMATION.yaml` → `contacts` (`groups.po` /
   `groups.tl`) либо в `roles`.
5. Записать номер задачи в `INFORMATION.yaml` → `facts` (поле для номера задачи
   процессом не задано) и в отчёт; после этого номер попадёт в публикацию при
   следующем `make start-apply`.

## 4. Чего в этом пакете нет

Процедура (JQL-поиск → сверка с пилотом → `POST /rest/api/2/issue` → ключ в `catalog.yaml → jira_task`) — `references/workflow.md` §Если Jira-ключа нет. Проект, тип, спринт, оценка и приоритет процессом не заданы; номер задачи появляется после создания в Jira.

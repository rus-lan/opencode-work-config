# {{ mr.title }}

## Что меняется

| поле | было | стало |
|------|------|-------|
{{#each mr.changes}}| `severity.{{ .field }}` | {{ .before }} | {{ .after }} |
{{/each}}

## Основание

- паспорт в dochub: {{ mr.passport_mr }}
- merge request паспорта: {{ mr.passport_mr_url }}
- тред согласования: {{ mr.approve_link }}
- задача: {{ mr.task }}

## Проверка

{{#each mr.checklist}}- [ ] {{ . }}
{{/each}}

## Что не меняется

{{#each mr.unchanged}}- {{ . }}
{{/each}}

## Апрувы

MR из ветки `feature/<task>` не может пройти джоб `codeowners` для путей
`entities/**` самостоятельно: апрув дают только боты `project_14598_bot_*`, а они
апрувят лишь MR, созданные через SSoT-UI. Поэтому такой MR требует
`@codeowners approve` от maintainer'а проекта (access level ≥ 40) отдельным
комментарием — без него он останется красным.

Если меняется `severity.*`, дополнительно нужен один апрув от SRE или
руководства технической архитектуры (`@akolomytov`, `@evolvenkova`,
`@santonov`, `@schurikov`; точный список — в артефакте джоба `codeowners.json`,
поле `required`).

Closes {{ mr.task }}

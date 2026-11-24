---
type: template
tags: [шаблон, критичность, публикация, rocket-chat]
---

# Текст публикации в `#Criticality_assessment`

Источник: {{ refs.publication_page.url | or_missing }}. Публикуется после обоих MR (dochub — паспорт, SSoT — критичность). Текст собирается в момент вызова: `make handoff IS=<код> SEND=auto` (MCP, при отказе — REST) и `make handoff-apply CONFIRM=1` (тот же путь, только REST; одно сообщение). `start` рендерит предпросмотр в `actions/rocketchat-message.md`. `*текст*` — жирный, `* ` — маркер списка.

```text
{{#if score_trace.provisional}}Оценка предварительная: не подтверждены входы {{ score_trace.waived_inputs }} (диапазон {{ score_trace.provisional_range.min }}–{{ score_trace.provisional_range.max }}). Подробности — в паспорте.

{{/if}}Привет!
Прошу согласовать оценку критичности

*Пилотная оценка критичности по методике сбер*

*1. Участники и критичность ИС {{ identity.code }}. *

* Технический архитектор - {{ identity.ta | or_missing }}
* TL - {{ identity.tl | or_missing }}
* Старая критичность (при наличии) - {{ actions.old_criticality | or_missing }}{{#if actions.extra_criteria}} (доп. критерии: {{ actions.extra_criteria }}){{/if}}
* Новая критичность - {{ passport.object_criticality_estimation | or_missing }}.

*2. E2E процессы, в которых участвует ИС *

{{#if actions.e2e_list}}
{{#each actions.e2e_list}}* {{ . }}
{{/each}}
{{else}}
* {{ actions.e2e_text }}
{{/if}}

*3. Потери GMV / влияние на аудиторию. В случае отказа ИС на 1 час в самом негативном сценарии *

{{ actions.gmv_impact | or_missing }}

*4. Прочее *

* Ссылка на АДР — {{ actions.adr_link | or_missing }}
{{#if actions.process_link}}
* Ссылка на процесс D6.1.1 — {{ actions.process_link }}
{{/if}}
* Ссылка на MR (паспорт в dochub) — {{ actions.mr_link | or_missing }}
* Ссылка на MR (критичность в SSoT) — {{ actions.ssot_mr_text | or_missing }}
* Ссылка на задачу по оценке критичности — {{ actions.jira.task_link | or_missing }}
* Ссылка на SSOT — {{ actions.ssot_card_link | or_missing }}
{{#if actions.extra_info}}
* Дополнительная информация по оценке — {{ actions.extra_info }}
{{/if}}
```

Ссылок на MR в сообщении **две**: паспорт (`publish`, dochub-MR) и критичность
(`ssot`, SSoT-MR). Пустое значение любой из них — `⛔ не заполнено`: отправлять
сообщение с таким маркером нельзя (этап `handoff` не закрыт). Это проверяет
гейт публикации: пока в отрендеренном тексте есть `⛔` в обязательном поле,
action-пакет `actions/rocketchat-message.md` остаётся в статусе
`pending_manual` и печатает список незаполненных полей — `--create-message` в
этом состоянии `requested` не ставит.

Обязательные поля публикации (пустое → `⛔` и блокировка): технический
архитектор, ссылка на MR паспорта в dochub, ссылка на карточку ИС в SSoT.
Остальные поля опциональны: пустое опциональное поле отправку не блокирует, а
свободное «Дополнительная информация по оценке» при пустом значении вообще не
рендерится (буллета нет, `⛔` не появляется).

Исключение — SSoT-MR не требуется: `catalog.yaml → systems.<код>.ssot_status:
no_change` (severity в SSoT уже соответствует расчёту, `make ssot` изменений не
нашёл). Тогда вместо ссылки печатается «не требуется: severity уже соответствует
(…)», и гейт считает это поле заполненным, а не блокером.

Ссылка на задачу Jira собирается из `catalog.yaml → jira_task` по шаблону
`criteria.external_refs.jira_base` (`{key}` → ключ задачи). Нет ключа — прежний
`⛔ не заполнено`.

## Чеклист перед публикацией

*5. Ограничения оценки и что требуется от SRE *

Ограничения:
{{#if actions.handoff_limits}}
{{#each actions.handoff_limits}}* {{ . }}
{{/each}}
{{else}}
* ограничений не зафиксировано
{{/if}}

1. Дождаться подтверждения инженера SRE в треде.
2. Выполнить `make finalize IS=<код> --approve-link <ссылка на тред>` — одной
   командой проставляются `approve_link`, `assigned_date`, `review_date`,
   `criticality`, `criticality_ssot`, `status: confirmed` и прогоняются
   `start-apply` → `validate` → `index` → `verify`. Если `validate` даёт ERROR,
   записанные поля откатываются.
3. Обогащение SSoT делает `make ssot` / `make ssot-apply` (только блок
   `severity`, уровень — по маппингу `levels.ssot` из
   `criteria/criticality-criteria.yaml`); вручную карточку ИС не правят.

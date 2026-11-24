---
is_code: {{ requirements.is_code }}
generated_at: {{ requirements.generated_at | or_missing: null }}
method: {{ requirements.method }}
status: {{ requirements.status }}
---

# Недостающие данные: {{ requirements.is_code }}

Сценарий **{{ requirements.scenario_label }}** (`{{ requirements.scenario }}`) · метод `{{ requirements.method }}` · не закрыто **{{ requirements.blocking_count }}** обязательных, **{{ requirements.advisory_count }}** дополнительных из {{ requirements.scenario_inputs_count }}.
Только открытые поля. Значения вписываются в `DATA-REQUIREMENTS.yaml`, приём — `make enrich-apply IS={{ requirements.is_code }}`.
{{#if requirements.advisory_switches_scenario}}
> Заполнение любого поля из группы «дополнительные» (`time_to_impact`, `axes_scores`, `cia`) переключает ИС на сложный сценарий: обязательными становятся все 7 входов, включая `time_to_impact`. Фолбэк на простой сценарий запрещён.
{{/if}}
## Поля

{{#each requirements.items}}
### {{ .title }} (`{{ .id }}`)

- **Что это:** {{ .definition }} Допустимо: {{ .acceptable }}; пример: `{{ .example }}`
- **Где взять:** {{ .where }}
- **Кто и как подтверждает:** {{ .whom }}; {{ .confirm }}{{#if .is_load}}; пик RPS снимается в Grafana (дашборд, панель, точный PromQL), `peak_hour_load = peak_rps × 3600`{{/if}}
- **Сейчас:** {{ .current_label }} · роль: {{ .blocking_label }}, метод {{ .method }}{{#if .switches_scenario}} · заполнение → сложный сценарий (потребуется time_to_impact){{/if}}

{{/each}}
{{#if requirements.waived_items}}
## Явный отказ от данных (`status: waived`, R17)

Эти входы закрыты осознанным решением человека, а не забыты. Значения нет и не
будет: оценка будет **предварительной** — в `CRITICALITY.md` печатается диапазон
уровней и режим допущения. Блок переносится в `INFORMATION.yaml` командой
`make enrich-apply`; удалить отказ можно только заменой на подтверждённое
значение (`status: confirmed`).

| Вход | Причина отказа | Кто решил | Дата | Режим допущения |
|------|----------------|-----------|------|-----------------|
{{#each requirements.waived_items}}| `{{ .id }}` — {{ .title }} | {{ .reason | md_cell }} | {{ .decided_by }} | {{ .date }} | {{ .mode_label }} |
{{/each}}
{{/if}}
## Готовый фрагмент для `INFORMATION.yaml`

Впишите значения вместо `null`, `source` и `status: confirmed` — блок идёт в секцию `criteria_inputs`.

```yaml
criteria_inputs:
{{#each requirements.items}}  {{ .id }}:
{{ .value_yaml }}{{ .value_extra_yaml }}    source:{{ .source_yaml }}
    status: {{ .status }}{{ .extra_yaml }}
{{/each}}```

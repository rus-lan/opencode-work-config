---
title: "RESEARCH-PLAN — план сбора данных ИС {{ research.is_code }}"
is_code: {{ research.is_code }}
generated_at: {{ research.generated_at | or_missing: null }}
method: {{ research.method }}
missing_blocking: {{ research.missing_blocking }}
missing_advisory: {{ research.missing_advisory }}
status: {{ research.status }}
---

# План сбора данных: {{ research.is_code }}

Гейт `make check`: **{{ research.gate_verdict }}** · метод `{{ research.method }}` · не закрыто **{{ research.missing_blocking }}** blocking, **{{ research.missing_advisory }}** advisory.
Как искать, формулы, ловушки источников и статусы — `references/data-sources.md`. Собирать «по аналогии с другой ИС» запрещено.

## Открытые поля

| Поле | Роль | Допустимые значения | Где искать | Кто подтверждает |
|------|------|---------------------|-----------|------------------|
{{#each research.fields}}| `{{ .id }}` | {{ .blocking_label }} ({{ .method }}) | {{ .acceptable }} | {{ .where }} | {{ .whom }} |
{{/each}}
{{#if research.closed_fields}}
Закрыто, инструкций нет:
{{#each research.closed_fields}}- `{{ .id }}` уже подтверждён: {{ .value }} ({{ .source_type }})
{{/each}}
{{/if}}
{{#if research.exhausted_inputs}}
{{#if research.exhausted_shared}}
Маршрут исчерпан у {{#each research.exhausted_shared.ids}}`{{ . }}` {{/each}}— {{ research.exhausted_shared.text }}
{{else}}
Маршрут исчерпан — адреса проверены, значение даёт только внешний ввод:
{{#each research.exhausted_inputs}}- `{{ .id }}` — {{ .text }}
{{/each}}
{{/if}}
{{else}}
{{#if research.checked_inputs}}
Проверено прошлыми проходами, повторно не обходится:
{{#each research.checked_inputs}}- `{{ .id }}` — {{ .text }}
{{/each}}
{{/if}}
{{/if}}
## Confluence

{{#if research.confluence_all_checked}}
Все страницы маршрута прочитаны — BFS повторять не нужно.
{{else}}
Маршрут: страница ИС вниз (BFS до глубины 2, ≤ 40 страниц) + `catalog.yaml` + `links.yaml` карточки ИС.
{{/if}}
Поиск по словам: {{ research.keywords }}

| page_id | Страница | Что искать | Статус |
|---------|---------|-----------|--------|
{{#each research.confluence_pages}}| `{{ .page_id }}` | {{ .title }} | {{ .look_for }} | {{ .status_note }} |
{{/each}}

{{#if research.missing_page_ids}}
Не заполнено в `catalog.yaml` — эти страницы план не знает:
{{#each research.missing_page_ids}}
⛔ {{ . }}
{{/each}}

{{/if}}
Порядок обхода: DR → Support/SLA → трафик → архитектура → E2E → ИБ → Decision Log.
Читать `confluence_get_page(convert_to_markdown=True)`, детей —
`confluence_get_page_children`.

Ловушки:

- **Новый редактор (ADF).** `confluence_get_page` может вернуть пустой
  `content.value`. Тогда читать `confluence_get_page_history(page_id, version)` —
  история отдаёт полный текст версии.
- **Лимит запросов.** 30 запросов на общий ключ: батчи не больше 10 страниц с
  паузами; на `Rate limit exceeded` — пауза и повтор, а не отказ от сбора.
- **Цитата, а не пересказ.** В результат идёт дословная формулировка раздела и
  `page_id`; «примерно так написано» значением не является.

## Product scope — процессы ИС

Источник E2E-процессов — Product scope продукта: функциональные области с
меткой `functional-area`, в их глоссарии колонка «Код мастер-системы
(опционально)» называет ИС, а «Сквозной бизнес-процесс (e2e)*» — процесс.

{{#if research.product_scope.scope_page_id}}
Product scope: {{ research.product_scope.scope_url }} (page_id
`{{ research.product_scope.scope_page_id }}`), продукт
{{ research.product_scope.product | or_missing }}.

CQL функциональных областей:

```text
{{ research.product_scope.cql }}
```

{{#each research.product_scope.instructions}}- {{ . }}
{{/each}}
{{else}}
⛔ Product scope не определён — E2E-процессы искать негде:
{{#each research.product_scope.problems}}
- {{ . }}
{{/each}}
{{/if}}
{{#if research.product_scope.scope_page_id}}
{{#if research.product_scope.problems}}
Замечания:
{{#each research.product_scope.problems}}
- {{ . }}
{{/each}}
{{/if}}
{{/if}}

Записать результат в `INFORMATION.yaml` → `facts`: `e2e_processes`,
`e2e_status`, `e2e_source_page`. Пустая колонка e2e — `e2e_status: not_filled`,
а не выдуманный процесс; ИС, которую не называет ни одна область —
`e2e_status: not_found`.

## Grafana

{{#if research.grafana.needed}}
Папка {{ research.grafana.folder_name }} (`{{ research.grafana.folder_uid }}`).

{{#if research.grafana.dashboards}}
| uid | Дашборд | Ссылка | Статус |
|-----|---------|--------|--------|
{{#each research.grafana.dashboards}}| {{ .uid | default: "—" }} | {{ .title }} | {{ .url | or_missing: "—" }} | {{ .status_note }} |
{{/each}}
{{else}}
⛔ в `links.yaml` карточки ИС нет ссылок на дашборды.
{{/if}}
{{#if research.grafana.hints}}
Найти в папке:
{{#each research.grafana.hints}}- `grafana_search_dashboards` → {{ . }}
{{/each}}
{{/if}}
{{#if research.grafana.queries}}
| Поле | PromQL | Окно | Заметка |
|------|--------|------|---------|
{{#each research.grafana.queries}}| `{{ .field }}` | `{{ .expr }}` | {{ .window }} | {{ .note }} |
{{/each}}
{{else}}
Метрик для открытых полей нет: из Grafana они не выводятся.
{{/if}}
`peak_hour_load = peak_rps × 3600`; окно и агрегат указывать в `evidence`.
{{else}}
Grafana не нужна: измеримые ею входы закрыты (список — «Закрыто, инструкций нет»).
{{/if}}
## Что считается ответом

Формула нагрузки: `peak_hour_load = peak_rps × 3600`. Запрещено брать как
нагрузку latency, errors, `up`/probe-метрики и число соединений: это не клиенты.
Тяжёлые `max_over_time` на 30d могут отваливаться по таймауту — уменьшать
разрешение подзапроса (`[30d:15m]` вместо `[30d:5m]`).

## Глубокий поиск (tier 2)

Правило: если поверхностный поиск (tier 1 — точные идентификаторы) не дал
результата, глубокий поиск по комбинациям значений **обязателен**. «Не найдено»
доказывается списком выполненных запросов, а не молчанием. Протокол целиком —
`.opencode/skills/criticality-gen/references/search.md`; результат фиксируется в
`CANDIDATES.yaml` → `search.<вход>` (`shallow`, `deep`, `done`, `result`).

{{#if research.deep_search}}
{{#each research.deep_search}}
### `{{ .id }}` — {{ .title }} ({{ .role }})

Tier 1:

{{#each .shallow}}- `{{ . }}`
{{/each}}

Tier 2:

{{#each .deep}}- `{{ . }}`
{{/each}}
{{/each}}
{{else}}
Незакрытых входов нет — глубокий поиск не требуется.
{{/if}}

Если tier 2 не дал значения и вход blocking — это не повод вписывать догадку:
нужен вопрос человеку (`make ask IS={{ research.is_code }}`).

## Как фиксировать результат

| Шаг | Что записать |
|-----|--------------|
| Значение | `value` в `DATA-REQUIREMENTS.yaml`; у составных входов — каждая под-ось |
| Источник | `source: {type, ref}`: `confluence` — `page_id` и раздел; `grafana` — uid дашборда, панель и точный PromQL |
| Подтверждение | `status: confirmed` и кто подтвердил (TL / PdM / SRE / ИБ) |
| Формула | если значение вычислено — формула и исходные числа рядом |
| Цитата | дословная формулировка из источника |

Статусы: `confirmed` — дословно в источнике; `derived` — вычислено по формуле
(формула обязательна) или выведено из enum-правила; `missing` — данных нет.

## Куда записать

`{{ research.data_requirements_path }}` → `make enrich-apply IS={{ research.is_code }}` (без `source` и `status: confirmed` значение отклоняется) → `make check IS={{ research.is_code }}`.

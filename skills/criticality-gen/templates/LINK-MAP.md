---
is_code: {{ link_map.is_code }}
generated_at: {{ link_map.generated_at | or_missing: null }}
nodes: {{ link_map.counts.nodes }}
truncated: {{ link_map.counts.truncated }}
---

# Карта обхода ссылок: {{ link_map.is_code }}

Дата {{ link_map.generated_at | or_missing: "—" }} · узлов {{ link_map.counts.nodes }} (truncated: {{ link_map.counts.truncated }}) · лимит {{ link_map.limits.max_nodes }} · источник `{{ link_map.source.ref }}`.
Скрипт в сеть не ходит: обход выполняет MCP-агент по этому файлу, результаты пишет в `SOURCES-FINDINGS.yaml`, принимает `make sources-apply`. Машиночитаемая копия — `LINK-MAP.yaml`.

| Вид | Узлов |
|-----|-------|
{{#each link_map.counts.by_kind}}| `{{ @key }}` | {{ . }} |
{{/each}}
## Узлы

| id | вид | адрес | subject | кандидат для | статус |
|----|-----|-------|---------|--------------|--------|
{{#each link_map.nodes}}| `{{ .id }}` | `{{ .kind }}` | {{ .address }} | `{{ .subject }}` | {{ .candidate_for | default: "—" }} | `{{ .status }}` |
{{/each}}
## Входы

| Вход | Роль | Кандидаты | Правило |
|------|------|-----------|---------|
{{#each link_map.inputs}}| `{{ @key }}` | {{#if .blocking}}blocking{{else}}advisory{{/if}} | {{ .candidates | default: "—" }} | {{ .rule }} |
{{/each}}
Пустой список кандидатов — узлов нужного вида в карте нет: расширять карточку ИС в SSoT, а не выдумывать значение.

## Правила обхода

- **Confluence**: `confluence_get_page(page_id, convert_to_markdown=True)` → `get_page_children` → `get_attachments` → `get_inline_comments`; `search` — только если в дереве пусто. Пустой `content.value` (ADF) → `get_page_history(page_id, version)`.
- **Grafana**: `get_dashboard(uid)` → `extract_datasource_uids_from_dashboard(uid)` → `query_from_dashboard_panel` или `query_prometheus(expr=…)`; окно (7d/30d) и агрегат указывать в `evidence`. `peak_hour_load = peak_rps × 3600`.
- **GitLab / Jira** (`expand: []`) — факт навигации, не обходятся; **external** — только если на него прямо указывает правило входа.
- Лимит: 30 запросов на ключ, батчи ≤ 10; на `Rate limit exceeded` — пауза и повтор.
- Без `source` и дословной цитаты значение не принимается; пересказ цитатой не считается.

## Контракт `SOURCES-FINDINGS.yaml`

Поля, допустимые значения и примеры — в скелете `templates/SOURCES-FINDINGS.yaml`; файл рядом: `is/<код ИС>/SOURCES-FINDINGS.yaml`. Обязательны `input`, `value`, `source.type` + `source.ref`, `evidence`; `unit` / `status` / `node` — по необходимости.

`not_found` — такой же результат обхода, как `findings`, а не ошибка. Принятый факт важнее пометки `node_status` (`found`/`truncated` пометкой не перезаписываются). После `sources-apply` статусы в `.md` и `.yaml` совпадают.

## Если значения нет

1. Не подставлять похожее — в `findings` ничего не писать.
2. Записать `not_found` (вход, узлы, причина) и эскалировать человеку: `INFORMATION.yaml` → `notes` или тред согласования.
3. `make sources-apply IS={{ link_map.is_code }}` → `make check IS={{ link_map.is_code }}`.

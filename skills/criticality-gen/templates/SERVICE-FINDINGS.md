---
is_code: {{ findings.is_code }}
generated_at: {{ findings.generated_at | or_missing: null }}
services_total: {{ findings.services_total }}
services_cloned: {{ findings.services_cloned }}
---

# Код сервисов: {{ findings.is_code }}

Сервисов {{ findings.services_total }} · прочитано клонов {{ findings.services_cloned }} · пропущено {{ findings.services_skipped }} · `docs/` у {{ findings.docs_found }} · `openspec/` у {{ findings.openspec_found }} · SLO-конфиг у {{ findings.slo_configs_found }}.
Клоны `apps/{{ findings.is_code }}/<сервис>` используются только для чтения: сборка и запуск запрещены. Цитаты дословные, с `файл:строка`.

## 1. Сервисы

| сервис | репозиторий | ветка | docs/ | openspec/ | SLO-конфиг |
|--------|-------------|-------|-------|-----------|------------|
{{#each findings.services}}| `{{ .name }}` | {{ .repository }} | {{ .branch }} | {{#if .docs_present}}да{{else}}нет{{/if}} | {{#if .openspec_present}}да{{else}}нет{{/if}} | {{ .slo_config }} |
{{/each}}
### Что лежит в `docs/` и `openspec/`

{{#each findings.services}}
{{#if .docs_tree}}
`{{ .name }}` — `docs/`:
{{#each .docs_tree}}- `{{ . }}`
{{/each}}
{{/if}}
{{#if .openspec_tree}}
`{{ .name }}` — `openspec/`:
{{#each .openspec_tree}}- `{{ . }}`
{{/each}}
{{/if}}
{{/each}}
Сервисы без `docs/` и `openspec/` здесь не указаны — см. §7.

## 2. Пропущенные сервисы (lifecycle и --no-clone)

{{#if findings.skipped_services}}
| сервис | репозиторий | lifecycle | причина |
|--------|-------------|-----------|---------|
{{#each findings.skipped_services}}| `{{ .name }}` | {{ .repository }} | `{{ .lifecycle }}` | {{ .reason }} |
{{/each}}
Закрытые сервисы не клонируются и не служат основанием для входов (`criteria.service_lifecycle`).
{{else}}
Ни один сервис не пропущен по `lifecycle`.
{{/if}}
{{#if findings.lifecycle_missing}}
lifecycle не указан: {{#each findings.lifecycle_missing}}`{{ . }}` {{/each}}— проанализированы как активные.
{{/if}}
{{#if findings.not_cloned_services}}
### Не склонировано (`--no-clone`)

| сервис | репозиторий | ожидаемый путь | причина |
|--------|-------------|----------------|---------|
{{#each findings.not_cloned_services}}| `{{ .name }}` | {{ .repository }} | `{{ .target }}` | {{ .reason }} |
{{/each}}
git не вызывался: проанализированы только существующие клоны. Склонировать: `make services-apply IS={{ findings.is_code }}` (без `--no-clone`).
{{/if}}
## 3. Назначение и потребители

{{#each findings.services}}
### {{ .name }}

{{#if .skip_note}}
{{ .skip_note }}
{{else}}
{{#if .purpose}}
| файл:строка | дословно |
|-------------|----------|
{{#each .purpose}}| `{{ .file }}:{{ .line }}` | {{ .quote }} |
{{/each}}
{{else}}
—
{{/if}}
{{/if}}
{{/each}}
## 4. Нормативы (SLO/SLA/RTO)

{{#if findings.norms}}
| сервис | файл:строка | дословно | пригодно для object_sla |
|--------|-------------|----------|-------------------------|
{{#each findings.norms}}| `{{ .service }}` | `{{ .file }}:{{ .line }}` | {{ .quote }} | {{ .usable }} |
{{/each}}
{{#if findings.norms_truncated}}
Совпадений всего {{ findings.norms_total }}: в отчёт попали первые, полный список — `grep -rn` по клонам.
{{/if}}
{{else}}
Не найдено: ни в одном клоне нет строки с SLA/SLO/RTO/RPO и числом с единицей (%, минуты, часы), процентом доступности, числом рядом со словом «простой» или `objective:`.
{{/if}}
## 5. Потоки данных и автоматизация

{{#if findings.flows}}
{{#each findings.flows}}- `{{ .service }}` — `{{ .file }}:{{ .line }}` — {{ .quote }}
{{/each}}
{{#if findings.flows_truncated}}
Совпадений всего {{ findings.flows_total }}: в отчёт попали первые, полный список — `grep -rn` по клонам.
{{/if}}
{{else}}
Не найдено: Kafka-топики, шедулеры и кроны.
{{/if}}
## 6. Что даёт основание для входов

Основание — совпадение с формулировкой критериев (`enum_selection.outage_impact.values`, `time_buckets`, «целевое время решения»). Совпадение только по слову основанием не является и вынесено в таблицу ниже.

{{#if findings.basis}}
| вход | основание | сервис | файл:строка |
|------|-----------|--------|-------------|
{{#each findings.basis}}| `{{ .input }}` | {{ .basis }} | `{{ .service }}` | {{ .location }} |
{{/each}}
{{else}}
Ни один вход не получил основания из кода: значения берутся из Confluence, Grafana и экспертных решений.
{{/if}}
{{#if findings.basis_noise}}
**Прочие совпадения по слову** (шум, вход не закрывают):

| вход | совпадение по слову | сервис | файл:строка |
|------|---------------------|--------|-------------|
{{#each findings.basis_noise}}| `{{ .input }}` | {{ .basis }} | `{{ .service }}` | {{ .location }} |
{{/each}}
{{/if}}
## 7. Не найдено

{{#if findings.not_found}}
{{#each findings.not_found}}- {{ . }}
{{/each}}
{{else}}
Ничего не потеряно: `docs/`, `openspec/` и SLO-конфиги найдены у всех сервисов.
{{/if}}
## 8. Ограничение

{{ findings.read_only_note }}
Отчёт не пишет в `INFORMATION.yaml` и не закрывает входы: цитата из клона — основание, значение подтверждает человек и принимает `enrich`.

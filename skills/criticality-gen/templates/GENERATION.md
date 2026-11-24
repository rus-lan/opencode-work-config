# Отчёт о генерации: {{ generation.code }}

Дата **{{ generation.date }}** (`--date`). Производный файл: перезаписывается каждым прогоном.
Метод `{{ generation.method }}` · статус `{{ generation.status }}` · итог **{{ generation.final_level }}** · расхождений с реестром {{ generation.conflicts_count }}.

## 1. Статус

| Параметр | Значение |
|----------|----------|
| ИС | `{{ generation.code }}` |
| Метод расчёта | {{ generation.method }} |
| Статус расчёта | `{{ generation.status }}` |
| Итоговая критичность | {{ generation.final_level }} |
| Расхождений с реестром | {{ generation.conflicts_count }} |
| Критерии (фингерпринт) | {{ generation.criteria_fingerprint }} |

{{ generation.titles_line }}

{{#if generation.conflicts}}
**Расхождения (не перезаписаны автоматически — нужно решение владельца):**

| Поле | Расчёт | Реестр | Правило | Примечание |
|------|--------|--------|---------|------------|
{{#each generation.conflicts}}| `{{ .field }}` | {{ .computed }} | {{ .actual }} | {{ .rule }} | {{ .note }} |
{{/each}}
{{else}}
Расхождений с реестром нет (сверено {{ generation.registry_compared }}, не заполнено {{ generation.registry_empty }}).
{{/if}}

## 2. Промежуточные значения

| Параметр | Значение |
|----------|----------|
{{#each generation.rows}}| {{ .parameter }} | {{ .value }} |
{{/each}}

Ссылка на АДР: **{{ generation.adr_basis_note }}** (поле `actions.adr_link` в
action-пакете: `adr` — найден АДР; `architecture` — АДР не найден, подставлена
архитектура ИС; `is_page` — подставлена страница ИС; `none` — ссылки нет, ⛔).

## 3. Входы с провенансом

| Вход | Значение | Источник | Статус |
|------|----------|----------|--------|
{{#each generation.inputs}}| `{{ .id }}` | {{ .value }} | {{ .source | md_cell }} | {{ .status }} |
{{/each}}
{{#if generation.missing}}
Гейт не пропустит:{{#each generation.missing}} `{{ .id }}`{{/each}}
{{/if}}
## Расхождения с реестром

## 5. Использованные правила

| Правило | kind | Источник |
|---------|------|----------|
{{#each generation.rules}}| `{{ .name }}` | {{ .kind }} | {{ .source_md }}{{#if .note}} †{{/if}} |
{{/each}}
{{#if generation.rule_notes}}
† — источник в архиве, но остаётся единственным носителем части канона:

{{#each generation.rule_notes}}- `{{ .name }}` — {{ .note }}
{{/each}}
{{/if}}

## 6. Conventions (не из источника, требуют подтверждения)

{{#if generation.conventions}}
| Правило | status | rationale |
|---------|--------|-----------|
{{#each generation.conventions}}| `{{ .name }}` | {{ .status }} | {{ .rationale }} |
{{/each}}
{{else}}
Нет.
{{/if}}

## 7. Покрытие `facts`

| Секция | Записей |
|--------|---------|
{{#each generation.facts_present}}| `{{ .section }}` | {{ .count }} |
{{/each}}

**Недостающие данные:** {{#if requirements.present}}[DATA-REQUIREMENTS.md](DATA-REQUIREMENTS.md) — чего не хватает, где взять и у кого{{else}}лист требований не сформирован (запустите `make check` — при незаполненных входах он создаст `DATA-REQUIREMENTS.md`){{/if}}

## 8. Что сгенерировано

{{#each generation.files}}- `{{ . }}`
{{/each}}
## Ограничения

- `derived` — посчитано по формуле из критериев, нужно подтверждение PdM/TL/SRE.
- Промежуточные значения, правила и conventions — [CRITICALITY.md](CRITICALITY.md) §2, §7.
- Недостающие данные: {{#if requirements.present}}[DATA-REQUIREMENTS.md](DATA-REQUIREMENTS.md){{else}}нет, все входы заполнены{{/if}}.

## Воспроизвести

```bash
make start IS={{ generation.code }} DATE={{ generation.date }} FORCE=1
```

Детерминизм: при тех же входах и той же дате результат побайтово совпадает.

## 11. Предупреждения рендера

{{#if generation.warnings}}
Те же строки печатаются в консоль `make start`. Они не меняют расчёт, но
означают неполный артефакт (недоступный источник, нерезолвленное упоминание):

{{#each generation.warnings}}- {{ . }}
{{/each}}
{{else}}
Нет.
{{/if}}


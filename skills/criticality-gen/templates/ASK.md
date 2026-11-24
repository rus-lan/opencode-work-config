---
title: "ASK — план вопросов по недостающим входам ИС {{ ask.is_code }}"
is_code: {{ ask.is_code }}
generated_at: {{ ask.generated_at | or_missing: null }}
scenario: {{ ask.scenario }}
scenario_title: "{{ ask.scenario_title }}"
method: {{ ask.method }}
verdict: {{ ask.verdict }}
questions: {{ ask.total }}
blocking_count: {{ ask.blocking_count }}
advisory_count: {{ ask.advisory_count }}
---

# Вопросы по недостающим входам: {{ ask.is_code }}

> Сгенерировано `criticality.py ask` из `criteria/criticality-criteria.yaml`,
> `INFORMATION.yaml` и `{{ ask.candidates_path }}`. Руками этот файл не правят:
> ответы вписываются в `{{ ask.answers_path }}` и принимаются командой
> `make ask-answers`.

## Что это за файл

- Готовый план вопросов человеку по каждому **незакрытому** входу: что это,
  какие значения допустимы (enum раскрыт дословно), что уже найдено и откуда.
- Значения не выдуманы: кандидат с уверенностью `strong` всегда имеет
  провенанс (`source: {type, ref}`); кандидат без источника понижен до `weak`.
- Отвечать нужно **по-русски** (R16). Ответ на другом языке не принимается как
  значение входа — переспросите по-русски, а не переводите молча.

## Как отвечать

1. Выберите номер варианта в блоке «Варианты ответа» (нумерация — с 1).
2. Ответ внесите в `{{ ask.answers_path }}` (формат — `templates/ANSWERS.yaml`):

   ```yaml
   answers:
     <вход>:
       choice: candidate   # candidate | manual | source_url | freeform | waive | deferred | exclude
       candidate: 1        # номер из «Найденные кандидаты», если choice: candidate
       value: <значение>   # если choice: manual
       source: {type: <тип>, ref: '<где взято>'}   # обязателен для manual и freeform
       # source_url: '<url>' + extracted {value, quote} — ссылка и дословная цитата
       # freeform: '<текст>' + extracted {value, quote} + source
       # waive: reason (>= 10 символов) + fallback {mode, value?} — отказ от данных (R17)
   ```

3. Примите ответы: `make ask-answers IS={{ ask.is_code }} ANSWERS=<файл>`.
   Значения попадут в `{{ ask.requirements_path }}` со `status: confirmed`,
   а `INFORMATION.yaml` запишет только `make enrich-apply`.

## Состояние гейта

Сценарий: **{{ ask.scenario_label }}** (`{{ ask.scenario }}`) — {{ ask.scenario_title }}. Метод расчёта: `{{ ask.method }}`.
Вердикт: **{{ ask.verdict }}**{{#if ask.reason}} — {{ ask.reason }}{{/if}}.
Вопросов: **{{ ask.total }}** (blocking {{ ask.blocking_count }}, advisory {{ ask.advisory_count }}).

{{#if ask.problems}}
### Замечания к `{{ ask.candidates_path }}`

{{#each ask.problems}}- {{ . }}
{{/each}}
{{/if}}
{{#each ask.items}}
---

## {{ .number }}. `{{ .input }}` — {{ .title }}

| Поле | Значение |
|------|----------|
| Вход | `{{ .input }}` |
| Роль | {{ .role_label }} |
| Метод | {{ .method }} |
| Тип значения | {{ .type_label }} |
| Сейчас | {{ .current }} |
| У кого | {{ .whom }} |
| Как подтвердить | {{ .confirm }} |

**Что это.** {{ .definition }}

**Допустимые значения** (дословно из критериев):

{{#each .allowed_rows}}{{ .number }}. {{ .text }}
{{/each}}

**Где взять.** {{ .where }}

**Найденные кандидаты** ({{ .candidate_count }}):

{{#each .candidates}}{{ .number }}. {{ .value_text }} — {{ .label }}
   - откуда: {{ .source_text }}
   - доказательство: {{ .evidence_label }}
   - уверенность: {{ .confidence_label }}
{{/each}}{{#if .candidates}}{{else}}- кандидатов нет: значение нужно взять из источника или у эксперта (см. «Где взять»).
{{/if}}

**Варианты ответа**:

{{#each .options}}{{ .number }}. {{ .text }}
{{/each}}

**Если ответа нет.** {{ .empty_consequence }}.

{{/each}}
---

## Что дальше

```bash
make ask-answers IS={{ ask.is_code }} ANSWERS={{ ask.answers_path }}   # принять ответы
make enrich-apply IS={{ ask.is_code }}                                # записать в INFORMATION.yaml
make check IS={{ ask.is_code }}                                       # повторить гейт
```

Если данных нет и взять их негде — ИС исключается, а не заполняется догадкой:
`make exclude IS={{ ask.is_code }} REASON="<причина>"` (обратно — `make include`).

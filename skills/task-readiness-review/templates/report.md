# Готовность и оценка задачи {{task_key}}

> Шаблон отчёта по одной задаче. Порядок секций 1–8 фиксирован: рендерер заполняет слоты, но не
> переставляет и не переименовывает блоки. Слот без данных в источнике заполняется литералом
> `N/A (нет данных в источнике)` — числа, ссылки и имена не выдумываются.
>
> **Куда уходит рендер.** `report.md` — самостоятельный файл; при публикации его содержание уходит в
> задачу Jira **двумя комментариями** (по умолчанию, `jira.comment_mode: post`): «Результаты валидации»
> (из `validation.json`) и «Результаты оценки» (из `estimate.json`). Маркеры идемпотентности
> (`task-readiness-review:validation:<TASK-KEY>` и `task-readiness-review:estimate:<TASK-KEY>`) и обрезку
> по лимиту Jira добавляет рендерер комментариев (`publish`), а **не этот шаблон**: в `report.md` маркеров
> нет, и секции ниже от них не зависят. При `output.target: confluence|obsidian` тот же текст
> дополнительно публикуется страницей/заметкой.
>
> Прогон: `{{run_id}}` · проверено: `{{checked_at}}` · оценено: `{{estimated_at}}` ·
> модель: `v{{model_version}}` (`{{model_checksum}}`).

## 1. Задача

| Поле | Значение |
|---|---|
| Ключ | {{task_key}} |
| Заголовок | {{task_summary}} |
| Тип | {{issue_type}} |
| Роль | {{role}} |
| Вид работ | {{work_kind}} |
| Что делается (по заголовку и тексту) | {{intent_line}} |
| Спринт | {{sprint}} |
| Статус | {{status}} |
| Ссылка | {{task_url}} |

## 2. Вердикт готовности

**{{verdict}}** — {{verdict_reason}}

Проверок: passed {{checks_passed}} · failed {{checks_failed}} · na {{checks_na}}.
Проверка с зависимостями: {{with_dependencies}}.

{{analysis_block}}

## 3. Что не готово (блокирует оценку)

{{gaps_required_block}}

## 4. Что стоит уточнить

{{gaps_optional_block}}

## 5. Оценка по ролям

Только роли, для которых есть работа. Ожидаемое значение и границы диапазона — из шкалы
`{{scale}}`; QA-строка помечена источником числа (`Jira` — поле заполнено, `расчёт модели` — выведено
по бакету). QA-записи нет, когда тип задачи не требует QA-оценки (Задача, Tech Debt, ADR, Релиз,
Дизайн): тогда под итогом печатается `QA: не требуется (тип «…») — …`.

| Роль | Ожидаемо (sp) | Диапазон | Уверенность | Сценарии (min/base/max) | Обоснование |
|---|---|---|---|---|---|
| {{role_name}} | {{role_expected}} | {{role_range_low}}–{{role_range_high}} | {{role_confidence}} | {{role_scenario_min}} / {{role_scenario_base}} / {{role_scenario_max}} | {{role_reason}} |

**Итого:** ожидаемо {{total_expected}} sp, диапазон {{total_range_low}}–{{total_range_high}} sp.

{{totals_line}}

{{resources_line}}

{{params_line}}

**Основания параметров:**

{{params_evidence}}

## 6. Вариативность и условия

{{variability_summary}}

## 7. Провенанс оценки

{{provenance_summary}}

## 8. Как перегенерировать

Команда: `/task-readiness-review refresh {{task_key}}`

- Что изменится: {{refresh_expected_changes}}
- Что останется прежним: {{refresh_unchanged}}
- Куда смотреть diff: {{delta_path}}

Перегенерация создаёт новый прогон и `delta.md`; артефакты предыдущего прогона не переписываются.

<!-- SLOTS
Список слотов и правило заполнения. Слот без данных в источнике = N/A (нет данных в источнике);
не выдумывать значения, ссылки, ключи и имена.

Секция 1 (задача)
  {{task_key}}            ключ Jira как есть
  {{task_summary}}        заголовок задачи как в Jira
  {{issue_type}}          тип задачи Jira
  {{role}}                роль из validation.role_map (BA|SA|BE|FE|QA|DEVOPS|OTHER)
  {{work_kind}}           implementation|research|bugfix|tech_debt|analysis|testing|unknown
  {{sprint}}              спринт задачи; нет данных — N/A
  {{status}}              статус задачи в Jira
  {{task_url}}            ссылка на задачу

Секция 2 (вердикт)
  {{verdict}}             OK|WARN|BLOCKED — из validation.json
  {{verdict_reason}}      одна строка: почему именно этот вердикт
  {{checks_passed}}       число проверок со status=PASS
  {{checks_failed}}       число проверок со status=FAIL
  {{checks_na}}           число проверок со status=NA
  {{with_dependencies}}   true|false — учитывались ли связанные задачи

Секции 3–4 (пробелы)
  {{gaps_required_block}} готовый компактный блок: заголовок с числом REQUIRED-пробелов и
                          суммой шагов штрафа, до 3 пунктов «чего не хватает — почему это
                          влияет», «и ещё N», ссылка на шаблон и путь к validation.json
  {{gaps_optional_block}} то же для RECOMMENDED/OPTIONAL (до 3 пунктов)
  {{template_link}}       ссылка на целевой шаблон описания задачи (validation.template_url;
                          пусто — путь к templates/task-description.md)
  {{validation_path}}     путь к полному списку пробелов: runs/<KEY>/<RUN>/validation.json
  {{gap_id}}              check-id правила, породившего пробел (для табличных шаблонов)
  {{gap_severity}}        REQUIRED|RECOMMENDED|OPTIONAL
  {{gap_what}}            что именно отсутствует (факт, не оценка)
  {{gap_role}}            кому адресован вопрос (target_role)
  {{gap_where}}           где искать ответ (where_to_find)

Секция 5 (оценка)
  {{scale}}               шкала Story Points из модели
  {{role_name}}           роль строки; у QA — с пометкой источника: `QA (Jira)`, `QA (расчёт модели)`
  {{role_expected}}       ожидаемое значение роли в шкале
  {{role_range_low}}      нижняя граница диапазона роли
  {{role_range_high}}     верхняя граница диапазона роли
  {{role_confidence}}     high|medium|low
  {{role_scenario_min}}   points сценария optimistic
  {{role_scenario_base}}  points сценария base
  {{role_scenario_max}}   points сценария pessimistic
  {{role_reason}}         почему получилось это число (из scenarios[].reason); при надбавке
                          RS-01 (ресурсы, `bonus_sp > 0`) значение помечается `до RS-01` —
                          «Ожидаемо» в таблице уже включает надбавку
  {{total_expected}}      сумма ожидаемых значений ролей, включая QA
  {{total_range_low}}     сумма нижних границ
  {{total_range_high}}    сумма верхних границ
  {{totals_line}}         `Dev: N SP · QA: M SP · Итого: N+M SP` (без QA — `Dev: N SP · Итого: N SP`
                          и строка `QA: не требуется (тип «…») — …` из `estimate.qa_scope`)
  {{resources_line}}      надбавка за дополнительные ресурсы (`RS-01`):
                          `Ресурсы: allure, e2e → +2 SP (mode add)`; нет ресурсов — пустая строка
                          (не `N/A`), строка из отчёта исчезает
  {{total_dev}}           слагаемое без QA
  {{total_qa}}            QA-слагаемое (пусто, если QA не оценивалась)
  {{params_line}}         параметры задачи weight/heat/connectivity → множитель и baseline
  {{params_evidence}}     основания параметров: сигнал → вклад, отдельными пунктами

Секция 6 (вариативность)
  {{variability_summary}} 1–2 предложения: множитель параметров, штрафы, QA, бакет эталона
  {{variability_line}}    полная строка причины (для табличных шаблонов)
  {{variability_rule_id}} id правила модели или check-id
  {{variability_cause}}   причина сдвига
  {{variability_effect}}  эффект в шагах шкалы или в уверенности
  {{variability_from}}    значение до сдвига
  {{variability_to}}      значение после сдвига

Секция 7 (провенанс)
  {{provenance_summary}}  1–2 предложения: бакет (base, n, reference), множитель, штрафы, QA,
                          источник модели. Полные записи — в estimate.json
  {{prov_role}}           роль, к которой относится запись (для табличных шаблонов)
  {{prov_kind}}           reference|sprint_stats|rule|model
  {{prov_value}}          значение, которое подтверждается
  {{prov_source}}         идентификатор источника (бакет эталона, бакет статистики, правило)

Секция 8 (перегенерация)
  {{refresh_expected_changes}} что изменится после обновления данных
  {{refresh_unchanged}}        что останется прежним
  {{delta_path}}               путь к delta.md нового прогона

Служебные (шапка)
  {{run_id}}              идентификатор прогона (UTC, %Y-%m-%dT%H-%M-%SZ)
  {{checked_at}}          момент проверки
  {{estimated_at}}        момент расчёта оценки
  {{model_version}}       версия модели
  {{model_checksum}}      контрольная сумма модели

Правило: слот без данных = N/A (нет данных в источнике). Не выдумывать.
-->

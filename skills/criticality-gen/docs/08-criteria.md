---
title: Критерии расчёта критичности
purpose: Разобрать файл критериев — что за правило, откуда оно, как применяется и что делать при нехватке данных.
audience: [ai-agent, human]
read_when: [меняете правила расчёта, нужен kind и провенанс правила, гейт заблокировал расчёт]
updated: 2026-11-12
status: actual
related: [02-methodology.md, ../criteria/criticality-criteria.yaml, 09-pipeline.md, 07-scripts.md]
---

# Критерии расчёта критичности

## Когда читать

- Читать, когда меняете `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` и нужен порядок правки.
- Читать, когда нужно понять, почему правило считается документированным или конвенцией (`kind`).
- Читать, когда `make check` вернул `BLOCKED` и нужно понять, каких входов не хватает.

## Кратко

- Единственный машиночитаемый источник правил — `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml`; этот документ его разбирает.
- У каждого правила есть `kind`: `documented` (из источника) или `convention` (конвенция репозитория).
- `make criteria-check` проверяет целостность файла, `make selftest` — детерминизм расчёта.
- Сценариев два: простой (`express`, четыре входа калькулятора) и сложный (`detailed`, все семь входов `inputs.required`); фолбэк со сложного на простой запрещён.
- Гейт блокирует расчёт, если нет обязательных входов выбранного сценария; подстановка «примерных» значений запрещена.
- Значения шкал и матриц в этом документе не копируются: они в файле критериев и в [02-methodology.md](02-methodology.md).

Единственный машиночитаемый источник правил —
[`criteria/criticality-criteria.yaml`](../criteria/criticality-criteria.yaml).

## 1. Зачем отдельный файл критериев

До появления файла правила расчёта жили в трёх местах: таблицы в
[02-methodology.md](02-methodology.md), константы в `.opencode/skills/criticality-gen/scripts/criticality.py` и
«здравый смысл» того, кто заполнял паспорт. Любое из них могло разойтись с
остальными, а число в паспорте нельзя было проверить.

Теперь правила — данные, а не код:

- **Один источник.** Шкалы, матрицы, веса, границы и enum берутся из YAML.
  Скрипт не содержит собственной копии матриц.
- **Проверяемость.** `criteria check` валидирует сам файл: полнота матриц,
  монотонность весов и границ, наличие `kind` у каждого правила.
- **Детерминизм.** `score --selftest` прогоняет все 20 ячеек impact-матрицы,
  все 16 ячеек финальной матрицы, границы CIA и гейт неполных данных. Одна и
  та же входная модель всегда даёт один и тот же уровень.
- **Провенанс.** У каждого правила есть `kind` и, если правило из источника,
  `page_id`. Convention-правила помечены и не могут «притвориться»
  документированными.

## 2. Принципы

| Принцип | Что означает на практике |
|---------|--------------------------|
| Провенанс | Любое числовое значение в артефакте имеет источник. Нет источника — `null`, а не «примерно так». |
| Полнота входов | Расчёт выполняется только при полном наборе **blocking**-входов выбранного сценария (`inputs.required` + `blocking: true`); advisory-входы дают `WARN`, но не блокируют. |
| Детерминизм | Одна и та же входная модель даёт один и тот же уровень; никаких «на глаз». |
| Явные конвенции | Convention-правила применяются только с явной пометкой в результате (`status: needs_validation`). |

## 3. Карта правил: `kind`, источник, применение

`kind: documented` — дословно из Confluence (`page_id` обязателен).
`kind: convention` — инженерное решение репозитория, которого нет в источнике
(`rationale` + `status: needs_validation` обязательны).

| Правило | kind | Источник | Как применяется |
|---------|------|----------|-----------------|
| `external_refs` | **convention** | — | Именованные внешние документы процесса/методики (`base_url` + `refs.<name>.id/title`): `page_id` живут только здесь, шаблоны не содержат знаний об инстансе Confluence; незаполненная ссылка → `⛔ не заполнено` + `WARN`. `jira_base` (`{key}`) — шаблон ссылки на задачу Jira: ключ из `catalog.yaml → jira_task`, нет ключа — `⛔`. `repos.<dochub\|ssot>` (`url` + `branch` + `note`) — канон адресов репозиториев: `publish`/`ssot` печатают из них готовую команду клонирования (`--clone` выполняет её), `prepare` проверяет доступность (`git ls-remote`, таймаут 10 с, недоступность — `WARN`) |
| `provenance` | documented | 4567212024 | Допустимые типы провенанса (`types`) — **10** в порядке канона: `ssot`, `is_yaml_override`, `catalog`, `confluence`, `gitlab`, `jira`, `grafana`, `attachment`, `ssot_links`, `manual`; у каждого типа — `description`. Список обязан совпадать с `PROVENANCE_TYPES` в скрипте (состав и порядок) |
| `provenance.manual_decision` | documented | 4567212024 | Решение владельца без дословной цитаты — это `manual` с ref вида «решение PdM, `<YYYY-MM-DD>`; `INFORMATION.yaml#notes`». Без ссылки на решение — `missing`, а не `manual` |
| `levels` | documented | 4207454433 (**архив**, `archived_carrier`) | Шкала из 4 уровней и их определения; `levels.rank` задаёт порядок старшинства. Страница в архиве, но заменить шкалу нечем — правило помечено `source_status: archived_carrier` и несёт `source_note` |
| `levels.dochub_extra_level` | documented | 4566730084 | Уровень `Mission critical+` существует только в dochub-паспорте; методикой не производится (балл 5 калькулятора даёт `Mission critical`), в SSoT маппится в `Mission critical` |
| `levels.dochub_to_ssot` | documented | 4566730084 | Маппинг 5 dochub-уровней в 3 уровня SSoT |
| `ssot_severity_normalization` | **convention** | — | kebab-case `severity.type` из SSoT → Title Case уровень паспорта (`office-productivity` → `Office productivity`); значение вне карты → `null` + `WARN`, а не догадка |
| `axes` | documented | 4207454433 (**архив**) | Четыре оси 0–4; агрегация `max` |
| `time_buckets` | documented | 4207454433 (**архив**) | Четыре корзины времени до негативных последствий |
| `impact_matrix` | documented | 4207454433 (**архив**) | `max(оси)` × время → бизнес-уровень (20 ячеек) |
| `cia` | documented | 4207454433 (**архив**, `archived_carrier`) | Параметры C/I/A и три уровня; описания — единственный носитель (страница в архиве) |
| `cia.descriptions` | documented | 4207454433 (**архив**, `archived_carrier`) | Описания уровней C/I/A; единственный носитель — правило помечено `source_status: archived_carrier` и несёт `source_note` |
| `cia.weights` | documented | 4207454433 (**архив**) | Веса F(low)=0.1, F(medium)=0.22, F(high)=0.56; страница в архиве — при изменении методики перенести таблицу в 4566730084 |
| `cia.protection_levels` | documented | 4566730084 | Границы V → Low/Medium/High/Critical |
| `cia.thresholds` | documented | 4566730084 | Те же границы числами (`low_upper`/`medium_upper`/`high_upper`) — единственный источник для рендера артефактов; `criteria check` сверяет с `protection_levels.ranges` |
| `cia.protection_levels.boundary_convention` | **convention** | 4566730084 | `V = 8.0` трактуется как `Critical` (источник задаёт только `V > 8`) |
| `cia.protection_to_level` | documented | 4207454433 (**архив**) | Уровень защищённости → бизнес-шкала |
| `final_matrix` | documented | 4207454433 (**архив**) + 4566730084 | Итог = ячейка матрицы (бизнес-уровень × уровень защищённости); 16 ячеек; `max(бизнес, ИБ)` не применяется |
| `inputs` | documented | 4567543163 | Перечень входных данных и варианты заполнения; у каждого входа `method`, `blocking`, `source_page_id`, `where` |
| `inputs.gate` | documented | 4566730084 | Нет хотя бы одного **blocking**-входа выбранного сценария → `BLOCKED`, расчёт не выполняется; непустой `blocking: false` — `WARN`, расчёт выполняется. Дословно: «Неполный сложный набор — это BLOCKED, а не повод посчитать простой сценарий» |
| `scenarios` | **convention** | — | Два сценария расчёта: простой (`express`, четыре входа калькулятора) и сложный (`detailed`, все входы `inputs.required`). Сценарий выбирается по данным, фолбэк запрещён |
| `scenarios.simple` | **convention** | — | Простой сценарий: `peak_hour_load`, `consumers_type`, `outage_impact`, `object_sla`; отсутствие любого — `BLOCKED` |
| `scenarios.complex` | **convention** | — | Сложный сценарий: все семь входов `inputs.required`; отсутствие любого — `BLOCKED`, фолбэк на простой сценарий запрещён |
| `scenarios.selection` | **convention** | — | Сценарий выбирается по данным: непустой любой вход только сложного набора (`time_to_impact`, `axes_scores`, `cia`) → сложный, иначе простой |
| `service_lifecycle` | **convention** | — | Сервисы с `lifecycle: closed` выведены из эксплуатации: не клонируются, не анализируются, не служат основанием для входов; применяется к `prepare` и `services` |
| `service_lifecycle.skip` | **convention** | — | Список пропускаемых значений `lifecycle` (сейчас `closed`), причина пропуска (`skip_reason`) и правило `evidence_rule`: закрытый сервис не может быть источником для `criteria_inputs` и `facts` |
| `express_method` | documented | артефакт `docs/reference/calculator/` | Экспресс-оценка по калькулятору критичности: `E`, `t`, интервалы, матрица, `score_to_level` |
| `express_method.formula` | documented | артефакт `docs/reference/calculator/` | Формулы `E`, `t`, балла и итога — дословно из файла |
| `express_method.client_coefficients` | documented | артефакт `docs/reference/calculator/` | 7 коэффициентов типа клиентов (`Расчет!A50:B56`) |
| `express_method.impact_coefficients` | documented | артефакт `docs/reference/calculator/` | 6 коэффициентов характера влияния (`Расчет!D51:F56`) |
| `express_method.impact_categories` | documented | артефакт `docs/reference/calculator/` | Категория последствий для каждого влияния (на расчёт не влияет) |
| `express_method.intervals` | documented | артефакт `docs/reference/calculator/` | 6 интервалов недоступности, проверка `lo < t <= hi` (`Расчет!B9:C14`) |
| `express_method.matrix` | documented | артефакт `docs/reference/calculator/` | Матрица 4×6 «последствия × интервал», порядок строк = порядок проверки (`Расчет!D26:I29`) |
| `express_method.score_to_level` | documented | артефакт `docs/reference/calculator/` | Балл 1..5 → код уровня `OP/BO/BC/MC/MC+` (`Расчет!B35:C39`) |
| `express_method.calculator_level_codes` | documented | артефакт `docs/reference/calculator/` | Код уровня калькулятора → полный уровень `levels.order` |
| `express_method.numerics` | **convention** | — | Округление `t` до 9 знаков перед сравнением с границами интервалов |
| `enum_selection.consumers_type` | documented | 4552328348 (`source_defect`) | Семь допустимых значений типа клиентов; на странице список неполон (нет «Физические лица», дубль «Сотрудники…») — канон в xlsx `Расчет!A50:B56` |
| `enum_selection.consumers_type.selection_rule` | documented | 4552328348 | Выбирать наиболее негативный сценарий; внешние клиенты приоритетнее |
| `enum_selection.outage_impact` | documented | 4552328348 (`source_defect`) | Шесть допустимых значений характера влияния; на странице 4 из 6 — канон в xlsx `Расчет!D51:D56` |
| `enum_selection.outage_impact.severity_order` | documented | артефакт `docs/reference/calculator/` | Порядок возрастания негативности = коэффициенты влияния (0.2 … 3.0) |
| `conflicts` | **convention** | — | Приоритет источников при расхождении: dochub → страница критичности → SSoT |
| `staleness` | **convention** | — | Период переоценки 12 месяцев (процессом не задан) |
| `artifacts` | **convention** | — | Артефакт собирается только из шаблона и фактов; свободный текст — только в обосновании |

Итого 39 правил: 29 `documented`, 10 `convention`. Число печатает
`make criteria-check` (`правил с kind: 39 (documented 29, convention 10)`) —
таблица выше обязана совпадать с ним.

## 4. Уровни критичности

Порядок уровней, ранги и определения — `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` → `levels.order`, `levels.rank`, `levels.definitions`; человекочитаемая шкала — [02-methodology.md](02-methodology.md), раздел 2.

Обязательно учитывать два правила:

- Ранг задаёт старшинство: `Office productivity` < `Business operational` < `Business critical` < `Mission critical`.
- `Mission critical+` существует только в dochub-паспорте: методикой не производится, в SSoT маппится в `Mission critical`.

Два набора уровней различаются в контексте рендера и в проверках:

| Набор | Что содержит | Где применяется |
|-------|--------------|-----------------|
| `levels.calculated` (`levels.order`) | только уровни, которые может выдать расчёт | `CRITICALITY.md` (возможные результаты расчёта), шапка и поле `object_criticality_estimation` паспорта |
| `levels.all` (`level_set`: `levels.order` + `levels.dochub_extra_level`) | плюс внешний dochub-уровень | `publication.md` (публикация в dochub), проверка enum в `validate` |

`validate` принимает `Mission critical+` как значение enum (оно приходит из
dochub-реестра), но если этот уровень стоит в паспорте как результат расчёта —
печатает `WARN: уровень 'Mission critical+' не производится методикой
(dochub-уровень) — проверьте происхождение`. Расчёт (`score`, `start`) этот
уровень выдать не может: `final_matrix` и `express_method.score_to_level`
содержат только уровни `levels.order`.

## 5. Оси последствий 0–4

Шкалы осей — `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` → `axes.items`; таблица — [02-methodology.md](02-methodology.md), раздел 4.1 (генерируется, руками не править).

Итоговая оценка по осям — **максимум**, а не сумма (`axes.aggregation: max`): одна тяжёлая ось поднимает уровень целиком.

## 6. Время до негативных последствий

| Корзина | Значение | Как вводить в CLI |
|---------|----------|-------------------|
| `<1h` | менее 1 часа | `<1h`, `<1 часа` |
| `1-12h` | от 1 до 12 часов | `1-12h`, `1-12 ч` |
| `12-24h` | от 12 до 24 часов | `12-24h`, `12–24 ч` |
| `>24h` | более 24 часов | `>24h`, `> 24 часов` |

CLI нормализует запись: регистр, пробелы, длинное тире и слова «час/часа/часов»
не важны.

## 7. Матрица «время × оценка»

Ячейки — `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` → `impact_matrix.cells`; таблица — [02-methodology.md](02-methodology.md), раздел 5 (генерируется, руками не править). Строка — `max` по осям, колонка — время до негативных последствий.

Свойство: матрица монотонна — рост оценки или сокращение времени не понижает уровень. Проверка — `make criteria-check`.

## 8. ИБ-часть: CIA и уровень защищённости

Описания уровней, веса и границы — `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` → `cia.descriptions`, `cia.weights`, `cia.protection_levels`, `cia.protection_to_level`; таблицы — [02-methodology.md](02-methodology.md), раздел 7 (генерируются, руками не править).

Формула:

```text
V = 6 * (F(C) + F(I) + F(A))
```

Арифметика в скрипте целочисленная: веса хранятся в сотых (10/22/56), поэтому `V` считается без ошибок плавающей точки и сравнение с границами детерминировано. Возможные значения `V`: 1.80, 2.52, 3.24, 3.96, 4.56, 5.28, 6.00, 6.72, 7.92, 8.04, 10.08.

## 9. Финальная матрица `final_matrix` (бизнес-уровень × уровень защищённости)

Ячейки — `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` → `final_matrix.cells`; таблица — [02-methodology.md](02-methodology.md), раздел 8 (генерируется, руками не править).

Правило: `итоговая критичность = final_matrix.cells[бизнес-уровень][уровень защищённости]`.
Правило `max(бизнес, ИБ)` не применяется: в трёх ячейках строки `Office productivity`
матрица ниже максимума, и источник истины — сама матрица:

| Бизнес | Защищённость | Ячейка `final_matrix` | `max(бизнес, ИБ)` дал бы | Δ ранга |
|---|---|---|---|---|
| Office productivity | Medium | Office productivity | Business operational | −1 |
| Office productivity | High | Business operational | Business critical | −1 |
| Office productivity | Critical | Business critical | Mission critical | −1 |

Остальные 13 ячеек совпадают с максимумом. `final_matrix` — единственный
источник итога: код читает ячейку и не вычисляет максимум.

## 10. Как считается экспресс-оценка

> **Это не конвенция, а перенесённый артефакт.** `express_method` имеет
> `kind: documented`, `status: validated`; `source_artifact` —
> [`reference/calculator/калькулятор критичности упрощенный.xlsx`](reference/calculator/калькулятор%20критичности%20упрощенный.xlsx).
> Коэффициенты, интервалы, матрица и отображение «балл → уровень» перенесены
> из файла дословно, рантайм-зависимости от xlsx нет. Результат экспресс-оценки
> по-прежнему имеет статус **preliminary** и требует подтверждения SRE.

**Простой сценарий — это ровно калькулятор, и ничего больше.** Если выбран
простой сценарий (`scenarios.simple`), уровень считается только по четырём
входам и только по алгоритму `express_method`: ни `impact_matrix`, ни `cia`, ни
оценки по осям в нём не участвуют. **Сложный сценарий** (`scenarios.complex`)
наоборот, использует `axes_scores` → `impact_matrix`, `cia` → `final_matrix` и
входы калькулятора как часть своего набора; его входы экспресс-расчётом не
подменяются. Неполный сложный набор — `BLOCKED`, а не «посчитаем хотя бы
экспрессом» (`scenarios.complex.rule`).

Формулы (`express_method.formula`):

```text
E              = коэф. типа клиентов × коэф. характера влияния × клиентов/час
t[severity]    = порог[severity] / E × 60 + SLA        (минуты)
score[interval] = матрица[первая подходящая severity][interval]
J              = max(score по всем интервалам)
level          = score_to_level[J] → levels.dochub_to_ssot
```

Пороги: `Неприемлемые` 50 000, `Высокие` 10 000, `Средние` 1 000,
`Низкие` 100 баллов/час. Значения коэффициентов, интервалов и матрицы — в
файле критериев (`express_method.client_coefficients`,
`impact_coefficients`, `intervals`, `matrix`, `score_to_level`); в этой
документации они не дублируются.

Порядок шагов:

1. Взять наиболее негативный сценарий влияния; внешние клиенты приоритетнее
   внутренних (`enum_selection.consumers_type.selection_rule`).
2. Посчитать `E`. Любой из четырёх входов (`peak_hour_load`, `consumers_type`,
   `outage_impact`, `object_sla`) обязателен: без него расчёт не выполняется
   (`BLOCKED`).
3. Для каждой severity посчитать `t`; результат округляется до 9 знаков
   (`express_method.numerics`).
4. Для каждого интервала недоступности взять балл первой подходящей severity —
   порядок строк матрицы совпадает с порядком проверки в исходной формуле.
5. `J = max` по интервалам, уровень — `score_to_level[J]`.

### 10.1 Отклонения от исходного файла

Зафиксированы в `express_method.deviations_from_artifact`:

| В xlsx | В скилле | Почему |
|--------|----------|--------|
| пустой SLA в арифметике = 0 | `object_sla` обязателен (blocking); значение `0` допустимо и означает «простой недопустим», отрицательные запрещены | иначе паспорт получал бы уровень по несуществующему нормативу |
| пустые клиенты/тип/влияние → `E = 0` → `#N/A` | `BLOCKED` (`IncompleteError`) | «нет уровня» — не результат оценки |
| уровень `MC+` | в паспорт пишется `Mission critical` (`levels.dochub_to_ssot`), «калькулятор: MC+» — в `score_trace`/`GENERATION.md` | `MC+` существует только в dochub-паспорте |
| значения enum с хвостовыми и двойными пробелами | сравнение по канонической форме (strip + схлопывание пробелов) | в файле у двух значений влияния реальный хвостовой пробел, у одного типа клиентов — двойной |

### 10.2 Контрольный пример

`erm.mm`: нагрузка `75 528` клиентов/час, тип клиентов «Сотрудники компаний
Группы (Внутренние клиенты)», влияние «Клиент не смог узнать необходимую
информацию (Внутренние и внешние клиенты)», SLA `240` мин.

| Шаг | Значение |
|-----|----------|
| `E = 0.2 × 0.2 × 75 528` | **3 021.12** баллов/час |
| `t` «Низкие» | `100/3021.12×60 + 240` = **241.986** мин |
| `t` «Средние» | **259.86** мин |
| `t` «Высокие» | **438.602** мин |
| `t` «Неприемлемые» | **1233.009** мин |
| Интервал всех четырёх | `#4` (>4 ч – ≤24 ч) |
| Первая подходящая severity в `#4` | «Неприемлемые» → балл **3** |
| `J = max` | **3** |
| Уровень | `BC` → **Business critical** |

Пример проверяется `make selftest` вместе с 42 золотыми векторами
«корзина E × корзина SLA» и границами SLA/нагрузки
(`scripts/fixtures/express-golden-vectors.csv`).

Заполнение исходного калькулятора для этого примера —
[`reference/calculator/example-erm.mm.png`](reference/calculator/example-erm.mm.png)
(75528 / Сотрудники Группы / не смог узнать информацию / 240 → BC).

## 11. Что делать, если данных нет

Гейт описан в `inputs.gate` (documented, 4566730084): если хотя бы одного
блокирующего входа выбранного сценария нет — **расчёт не выполняется**.

### 11.1 Выбор сценария и гейт

У каждого входа в `inputs.required` два поля:

| Поле | Значения | Смысл |
|------|----------|-------|
| `method` | `detailed` \| `express` \| `both` | к какому набору относится вход (используется расчётом) |
| `blocking` | `true` \| `false` | блокирует ли отсутствие значения расчёт этим набором |

Наборы описаны не полем `method`, а секцией `scenarios` (`kind: convention`,
`status: validated`): сценариев **два**, и они различаются требованиями к
полноте.

| Сценарий | Метод | Обязательные входы |
|----------|-------|--------------------|
| простой | `express` | `peak_hour_load`, `consumers_type`, `outage_impact`, `object_sla` |
| сложный | `detailed` | те же четыре + `axes_scores`, `time_to_impact`, `cia` (все семь `inputs.required`) |

**Сценарий выбирается по данным, а не по флагу CLI** (`scenarios.selection.rule`):

- если хотя бы один вход, относящийся **только** к сложному набору
  (`time_to_impact`, `axes_scores`, `cia`), содержит непустое значение —
  сценарий сложный. Неполный сложный набор — `BLOCKED`, **фолбэк на простой
  сценарий запрещён** (иначе паспорт молча понижался бы в точности);
- иначе — сценарий простой, и он требует ровно четыре входа калькулятора.

**Blocking-вход готов**, когда значение присутствует **и** его `status` не
`missing`. Значение с `status: missing` считается отсутствующим — это ловит
случай, когда поле заполнено «заглушкой».

**Advisory-входы** (`blocking: false`) не мешают расчёту: их отсутствие
печатается как `WARN: не заполнено, требуется для полноты паспорта (не
блокирует): …`.

Один и тот же расчёт (`evaluate_gate`) используют `check`, `start` и
`score --is` — вердикт не может разойтись между командами.

### 11.2 Текущие входы

| Вход | простой сценарий | сложный сценарий |
|------|------------------|------------------|
| `peak_hour_load` | **обязателен** | **обязателен** |
| `consumers_type` | **обязателен** | **обязателен** |
| `outage_impact` | **обязателен** | **обязателен** |
| `object_sla` | **обязателен** | **обязателен** |
| `axes_scores` | — | **обязателен** |
| `time_to_impact` | — | **обязателен** |
| `cia` | — | **обязателен** |

В простом сценарии обязательны четыре входа: `E = коэф. типа × коэф. влияния ×
клиентов/час`, поэтому без нагрузки или типа клиентов уровень не определить. В
сложном обязательны все семь: `axes_scores` дают строку `impact_matrix`,
`time_to_impact` — колонку, `cia` — уровень защищённости для `final_matrix`.

`criteria check` требует, чтобы у каждого входа были оба поля, чтобы в каждом
методе был хотя бы один blocking-вход и чтобы `scenarios.simple`/`scenarios.complex`
покрывали ровно эти входы (простой — 4, сложный — все 7).

### 11.3 Поведение инструментов

| Ситуация | Поведение |
|----------|-----------|
| `score --is <код>` без `INFORMATION.yaml` | `Статус: incomplete`, перечень недостающих критериев с подсказкой «где взять», код возврата 1 |
| `score --axes` без `--time` | `incomplete` (не хватает `time_to_impact`), код 1 |
| `score --express` без любого из 4 входов (`--workload`, `--consumers`, `--impact`, `--sla`) | `incomplete` с перечнем отсутствующих, код 1 |
| `score --cia` без одного из C/I/A | `incomplete` (`cia.A` и т.п.), код 1 |
| `check` | таблица `ИС \| сценарий \| blocking n/m \| advisory n/m \| вердикт \| причина`; strict по умолчанию — ненулевой код при `BLOCKED` (CLI → 1, make → 2) |
| `check --diagnostic` | код 0 даже при `BLOCKED` (отладочный прогон) |
| `check --prepare` | `prepare --apply` + гейт (как `check` в `INFORMATION.md`) |
| `start` при `BLOCKED` | печатает причины и **ничего не пишет** на диск; ненулевой код (CLI → 1, make → 2) |
| `start` с невалидным enum или значением вне множества | `BLOCKED` со списком допустимых значений, файлы не изменены, без трейсбека |

## 12. Как менять критерии

1. Правится **только** `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml`.
2. Новое правило обязано иметь `kind`:
   - `documented` + `page_id`/`source_page_id`, если правило есть в Confluence;
   - `convention` + `rationale` + `status: needs_validation`, если это решение
     репозитория. Не выдавать конвенцию за источник.
3. Обновить этот документ (`docs/08-criteria.md`): таблицу правил и
   соответствующую таблицу значений.
4. Перегенерировать таблицы методики:

   ```bash
   make docs-sync    # таблицы в docs/02-methodology.md из файла критериев
   make docs-check   # проверка: расхождений нет (ненулевой код: CLI → 1, make → 2)
   ```

   Таблицы осей, impact-матрицы, CIA и финальной матрицы в
   [02-methodology.md](02-methodology.md) **генерируются** из
   `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` между маркерами
   `<!-- BEGIN/END GENERATED: ... -->`; править их руками запрещено —
   следующая `make docs-sync` затрёт правку.
5. Прогнать:

   ```bash
   python3 .opencode/skills/criticality-gen/scripts/criticality.py criteria check
   python3 .opencode/skills/criticality-gen/scripts/criticality.py score --selftest
   make validate
   ```

   Первые две команды — обязательны: `criteria check` ловит неполные матрицы,
   разрывы границ и немонотонные веса, `score --selftest` — расхождение
   расчёта с файлом.
6. Если меняется enum — синхронно править константы `CONSUMERS_TYPES` /
   `OUTAGE_IMPACTS` в `.opencode/skills/criticality-gen/scripts/criticality.py`: `criteria check` сверяет их с
   файлом и падает при расхождении.

Формат файла — блок-стиль YAML без inline-словарей и без многострочных
скаляров (`|`, `>`): файл обязан разбирать встроенный мини-парсер
`.opencode/skills/criticality-gen/scripts/criticality.py`, когда PyYAML не установлен.

## 13. Известные дефекты источника и расхождения

| Что | Суть | Как обращаемся |
|-----|------|----------------|
| Ось **A** в CIA | Формулировки `low`/`medium`/`high` дословно дублируют ось **C** («утечка общедоступных данных», «искажение незначимых данных», «простой <4 часов») и не описывают доступность | Значения приведены дословно (`source_defect: true` в файле критериев). Применение требует подтверждения владельца методики |
| Граница `V = 8` | Источник задаёт `V > 8 → Critical`, оставляя `V = 8` без уровня | Convention: `V >= 8 → Critical` (`boundary_convention`, `needs_validation`) |
| Формула экспресс-калькулятора | `упрощенный.xlsx` — вложение Confluence, недоступно машинно | `express_method` — convention, результат `preliminary` |
| Порядок негативности `outage_impact` | В источнике не пронумерован | Convention `severity_order`, `needs_validation` |
| Срок переоценки | Процесс D6.1.1 не задаёт календарный срок | Convention: 12 месяцев (`staleness`) |

> **Расхождение таблиц `docs/02` устранено.** Ранее §5 и §7 методики
> расходились с файлом критериев (ячейка `0 × <1h`, границы CIA). Теперь эти
> таблицы генерируются из `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` командой
> `make docs-sync`, проверка — `make docs-check`; руками их править запрещено.

## 14. Команды

```bash
# сам файл критериев
python3 .opencode/skills/criticality-gen/scripts/criticality.py criteria show          # человекочитаемо
python3 .opencode/skills/criticality-gen/scripts/criticality.py criteria show --json   # машиночитаемо
python3 .opencode/skills/criticality-gen/scripts/criticality.py criteria check         # валидация файла
python3 .opencode/skills/criticality-gen/scripts/criticality.py criteria sync-docs     # таблицы docs/02 из файла
python3 .opencode/skills/criticality-gen/scripts/criticality.py criteria sync-docs --check  # проверка расхождений

# расчёт
python3 .opencode/skills/criticality-gen/scripts/criticality.py score --axes legal=3,economic=2,reputational=1,client=4 --time '<1h'
python3 .opencode/skills/criticality-gen/scripts/criticality.py score --cia c=high,i=medium,a=low
python3 .opencode/skills/criticality-gen/scripts/criticality.py score --business 'Business critical' --cia-level High
python3 .opencode/skills/criticality-gen/scripts/criticality.py score --express --impact '<enum>' --sla 30
python3 .opencode/skills/criticality-gen/scripts/criticality.py score --is erm.mm
python3 .opencode/skills/criticality-gen/scripts/criticality.py score --selftest

# гейт данных
python3 .opencode/skills/criticality-gen/scripts/criticality.py check
python3 .opencode/skills/criticality-gen/scripts/criticality.py check --strict
```

Через `make`: `make criteria`, `make criteria-check`, `make docs-sync`,
`make docs-check`, `make score`, `make check`, `make selftest`. Полный
справочник — [07-scripts.md](07-scripts.md).

## 15. Источники

Состав сверен с первоисточниками 2026-11-18 (`meta.synced_at`); версии и статусы —
`meta.sources` в файле критериев.

| page_id | Документ | space | v | Обновлён | Статус | Роль |
|---------|----------|-------|---|----------|--------|------|
| [4566730084](https://space.samokat.ru/pages/viewpage.action?pageId=4566730084) | Методика и оригинальные расчёты | ECOMCS | 11 | 2026-11-17 | current | канон формул, интервалов, выбора сценария, границ CIA, маппинга уровней, «итог — ячейка `final_matrix`» |
| [4567543163](https://space.samokat.ru/pages/viewpage.action?pageId=4567543163) | Критерии оценки: входы и варианты заполнения | ECOMCS | 12 | 2026-11-17 | current | канон требований к 7 входам |
| [4567212024](https://space.samokat.ru/pages/viewpage.action?pageId=4567212024) | Данные, источники и провенанс | ECOMCS | 11 | 2026-11-17 | current | канон 10 типов провенанса и статусов значения |
| [4552328348](https://space.samokat.ru/pages/viewpage.action?pageId=4552328348) | Заполнение паспорта критичности (ЧЕРНОВИК) | SMKT | 14 | 2026-11-16 | draft | артефакт экспресса; списки enum дефектны |
| [4566714956](https://space.samokat.ru/pages/viewpage.action?pageId=4566714956) | Заполнение паспорта критичности (детальная оценка) (ЧЕРНОВИК) | SMKT | 3 | 2026-11-13 | draft | артефакт детальной оценки |
| [4553977278](https://space.samokat.ru/pages/viewpage.action?pageId=4553977278) | ЧЕРНОВИК 2026-10 D6.1.1. Процесс оценки критичности ИС | SMKT | 14 | 2026-11-18 | draft | черновик процесса 2026-10 |
| [3855374712](https://space.samokat.ru/pages/viewpage.action?pageId=3855374712) | D6.1.1. Процесс оценки критичности ИС | SMKT | 67 | 2026-10-08 | current | действующий процесс |
| [4207454433](https://space.samokat.ru/pages/viewpage.action?pageId=4207454433) | [DRAFT] Методика оценки критичности ИС (новая) | infrastructure | 3 | 2025-12-01 | **archived_carrier** | единственный носитель 20 ячеек `impact_matrix`, 16 ячеек `final_matrix`, шкал осей, описаний CIA; статус `archived_carrier` = документ в архиве, но заменить его нечем — правила ссылаются на него осознанно и объясняют причину в `source_note` |
| [3823234487](https://space.samokat.ru/pages/viewpage.action?pageId=3823234487) | Требования к ИС, в зависимости от критичности | SMKT | 45 | 2026-03-16 | supporting | вспомогательный: ни одно правило на него не ссылается |

Правило, опирающееся на архивный источник, обязано само нести пометку:
`source_status: archived` — ссылка историческая; `source_status: archived_carrier` —
документ в архиве, но остаётся единственным носителем части канона, поэтому
правило ссылается на него осознанно и объясняет причину в `source_note`.
Без пометки это ошибка: `criteria check` падает, а `validate` печатает `WARN`.
Так архивная методика не выдаётся за действующую.

### 15.1. Маршруты входа (`criteria.inputs.routes` и необязательные входы)

Маршруты не входят в гейт и не выбирают сценарий: это «где искать», когда
входа нет в `inputs.required`/`optional`, но он нужен для паспорта. Читает их
`make research` (`_research_input`) и агент на tier 2
([`references/search.md`](../references/search.md)).

| Маршрут | Что искать | Где | Ловушки |
|---------|------------|-----|---------|
| `e2e` (`inputs.routes.e2e`, `kind: convention`) | участие ИС в сквозных процессах: карточка процесса + код ИС в колонке «Информационная система» таблицы шагов | Каталог сквозных процессов 2.0 (3790195333), Реестр сквозных процессов (3700777856), Реестр ИС (4060332274, колонки «Наименование ИС / Код ИС / Название процесса»); запросы: `label = "checkliste2e" AND text ~ "{is_code}"`, `label = "e2e-process-card" AND space = SMKT AND text ~ "{is_name}"`, `text ~ "{is_code}" AND title ~ "BP"` | Пустая колонка «Сквозной бизнес-процесс (e2e)» в Product scope — **не** отсутствие процессов (в таблице-глоссарии пометка «В рамках пилота не заполняем»): идти в каталог процессов, а не писать `not_filled`. Карточка без таблицы шагов — основание, не значение |
| `financial_loss` (`inputs.optional.financial_loss`, advisory) | денежная оценка потерь по сценариям простоя (руб. + период), пороги: до 1 млн / 1–10 / 10–50 / свыше 50 млн | финансовая модель продукта и расчёты PdM, DR-страница ИС (сценарии), методология 4261521386 «Расчёт недополученного GMV» (средний чек 750 ₽), прецеденты 4196617026 / 4417913261 / 4417940072 | Блок «Оценка ущерба» в постмортемах T006 — пустой шаблон, не данные. Дашборд Grafana `WjUcCb_Zz` «GMV, AOV, Conversion» — общесетевой GMV, к ИС не атрибутируется. Внутренняя ИС (нет заказов клиентов) → `0 руб/час` со ссылкой на DR-страницу, а не «примерно» |

`e2e` пока `kind: convention`: маршрут найден глубоким поиском, но канон входов
(4567543163) его не описывает — статус снимается подтверждением владельца
методики. `financial_loss` в уровень не входит: он обогащает обоснование, а не
меняет `final_matrix`.

## Связанные документы

- [02-methodology.md](02-methodology.md) — методика с генерируемыми таблицами шкал и матриц.
- [criticality-criteria.yaml](../criteria/criticality-criteria.yaml) — сам файл критериев.
- [09-pipeline.md](09-pipeline.md) — как критерии применяются в гейте и генерации.
- [07-scripts.md](07-scripts.md) — команды `criteria`, `score`, `check`, `selftest`.

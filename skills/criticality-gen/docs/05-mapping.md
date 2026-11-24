---
title: Маппинг и идентификаторы
purpose: Свести в одном месте коды, page_id и правила соответствия между репозиторием, dochub, SSoT, Confluence и GitLab.
audience: [ai-agent, human]
read_when: [паспорт «не находится» по коду, переносите критичность в SSoT, нужен page_id или GitLab-группа ИС]
updated: 2026-11-24
status: actual
related: [09-pipeline.md, 03-fields.md, 08-criteria.md]
---

# Маппинг и идентификаторы

## Когда читать

- Читать, когда ищете ИС по коду, arch code или page_id.
- Читать, когда переносите подтверждённую критичность в карточку SSoT.
- Читать, когда сверяете приоритет источников данных об ИС.

## Кратко

- Код ИС — `<name_is>.<контур>`; `evaluated_object` — `sber.ecom.<контур>.<name_is>`; `id` паспорта — `sber.ecom.<контур>.criticality_passport.<name_is>`.
- Критичность dochub (5 значений) маппится в SSoT (3 значения); `Office productivity` поднимается до `Business operational`.
- Приоритет источников: SSoT → Confluence → `catalog.yaml` → `is.yaml`.
- `catalog.yaml` — производная от SSoT и Confluence; расхождение с SSoT — ошибка в реестре.
- `INFORMATION.yaml` — слой данных между SSoT и паспортом; ручные секции автоматика не перезаписывает.

Документ о том, как одна и та же ИС называется в разных системах: в этом
репозитории, в dochub, в SSoT, в Confluence и в GitLab. Ошибка в
идентификаторе — самая частая причина, по которой паспорт «не находится».

## 1. Маппинг критичности Dochub → SSoT

В dochub пять уровней, в SSoT — три. Карта соответствия хранится только в `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` → `levels.dochub_to_ssot` и здесь не копируется; напечатать — `make criteria`.

Почему `Office productivity` поднимается до `Business operational`: SSoT не
различает «инструмент эффективности» и «операционную систему», а занижать
уровень в SSoT опаснее, чем завышать — от него зависят дежурства и мониторинг.

`make validate` проверяет это правило: несоответствие — ERROR.

## 1.1. Маппинг SSoT `severity.type` → критичность паспорта

В карточке ИС SSoT критичность лежит в блоке `severity` (`severity.type`) и
записана в **kebab-case**; карточку приносит ответ MCP `ssot_get` (снимок —
`INFORMATION.yaml → ssot_snapshot`). В паспорте уровень пишется Title Case,
поэтому `make prepare` нормализует значение по карте
[`ssot_severity_normalization`](../criteria/criticality-criteria.yaml)
(`kind: convention`, `status: needs_validation`).

Карта соответствия хранится только в файле критериев (`ssot_severity_normalization.map`) и не копируется сюда: копия разошлась бы с источником. Напечатать карту — `make criteria`.

Правила:

1. Значение вне карты **не угадывается**: `identity.criticality_ssot: null`,
   `criticality_source: null`, `WARN «неизвестный severity.type: <x>»`.
2. `make criteria-check` проверяет наличие секции и то, что все значения карты
   входят в `levels.order`.
3. Расхождение `identity.criticality_ssot` (SSoT) с `catalog.yaml →
   criticality_ssot` — конфликт `ssot vs catalog`: он попадает в `conflicts`
   при `make start` и печатается как `WARN` в `make check`; авторитет у SSoT,
   реестр автоматически не перезаписывается.

Провенанс значения: `criticality_source: {type: ssot, ref:
"entities/information-systems/<код>/base.yaml#severity.type"}` — путь внутри
снимка `ssot_snapshot` (секция `base` ответа `ssot_get`).

## 2. Схема кодов

| Сущность | Формат | Пример | Где задаётся |
|----------|--------|--------|--------------|
| Код ИС | `<name_is>.<контур>` | `erm.mm` | Имя папки `is/<код ИС>/` (например `is/erm.mm/`) |
| Контур | `mm`, `smkt` | `smkt` | Часть кода ИС после последней точки |
| Продукт | `Exxx` | `E001` | `catalog.yaml` → `product` |
| Архитектурный код | `E001.A<N>` | `E001.A11` | Confluence, раздел Architecture продукта |
| Product scope | `E001FA<NNN>` | `E001FA100` | Confluence, раздел Product scope |
| Команда | `T<NNN>` | `T102` | Реестр ответственных |
| Актив | `ММ`, `СМКТ`, `СБЛ`, `СМ` | `ММ` | `catalog.yaml` → `asset` |

Product scope продукта E001:

| Код | Название |
|-----|----------|
| `E001FA100` | Покупатели и заказы |
| `E001FA102` | Тикеты |
| `E001FA232` | Платформа ЕРМ |

> В старом README префикс продукта был набран с кириллической «Е» вместо
> латинской `E`. Правильно только латинское `E001FA`: с кириллицей поиск по
> коду ничего не находит. Поэтому `make validate` проверяет все `.md`/`.yaml`
> репозитория (кроме `.git`) на кириллическую букву перед `001` — паттерн
> `[А-Яа-яЁё]0*01\b`; находка — ERROR с путём и номером строки.

## 3. Идентификаторы паспорта

```
код ИС            = <name_is>.<контур>                       → erm.mm
evaluated_object  = sber.ecom.<контур>.<name_is>             → sber.ecom.mm.erm
id паспорта       = sber.ecom.<контур>.criticality_passport.<name_is>
                                                             → sber.ecom.mm.criticality_passport.erm
```

`id` — это ключ объекта внутри секции `ecom.criticality_passport` в YAML. Он
не произвольный: `make validate` сверяет его с путём папки.

## 4. Соответствие ИС и источников

| Код ИС | arch code | Confluence (ИС) | DR | Decision Log | Оценка критичности | GitLab |
|--------|-----------|-----------------|----|--------------|--------------------|--------|
| `cc-exchanger.mm` | `E001.A10` | [3995290956](https://space.samokat.ru/pages/viewpage.action?pageId=3995290956) | [4552334964](https://space.samokat.ru/pages/viewpage.action?pageId=4552334964) | [3995290965](https://space.samokat.ru/pages/viewpage.action?pageId=3995290965) | [3995290983](https://space.samokat.ru/pages/viewpage.action?pageId=3995290983) | `ecom/dev/is/mm/cc-exchanger` |
| `erm.mm` | `E001.A11` | [3925149771](https://space.samokat.ru/pages/viewpage.action?pageId=3925149771) | [4556239121](https://space.samokat.ru/pages/viewpage.action?pageId=4556239121) | [3959026055](https://space.samokat.ru/pages/viewpage.action?pageId=3959026055) | [4003511156](https://space.samokat.ru/pages/viewpage.action?pageId=4003511156) | `ecom/dev/is/mm/erm` |
| `faq.mm` | `E001.A05` | [3959336825](https://space.samokat.ru/pages/viewpage.action?pageId=3959336825) | [4552334965](https://space.samokat.ru/pages/viewpage.action?pageId=4552334965) | [3959336863](https://space.samokat.ru/pages/viewpage.action?pageId=3959336863) | [3984443979](https://space.samokat.ru/pages/viewpage.action?pageId=3984443979) | `ecom/dev/is/mm/faq` |
| `gi.mm` | `E001.A13` | [3793622572](https://space.samokat.ru/pages/viewpage.action?pageId=3793622572) | [4556239122](https://space.samokat.ru/pages/viewpage.action?pageId=4556239122) | [3793622606](https://space.samokat.ru/pages/viewpage.action?pageId=3793622606) | [3982999861](https://space.samokat.ru/pages/viewpage.action?pageId=3982999861) | `ecom/dev/is/mm/gi` |
| `ts.mm` | `E001.A14` | [3954535119](https://space.samokat.ru/pages/viewpage.action?pageId=3954535119) | [4556239123](https://space.samokat.ru/pages/viewpage.action?pageId=4556239123) | [3954536147](https://space.samokat.ru/pages/viewpage.action?pageId=3954536147) | [3982999847](https://space.samokat.ru/pages/viewpage.action?pageId=3982999847) | `ecom/dev/is/mm/ts` |
| `cc-exchanger.smkt` | `E001.A12` | [4103717673](https://space.samokat.ru/pages/viewpage.action?pageId=4103717673) | [4552334962](https://space.samokat.ru/pages/viewpage.action?pageId=4552334962) | [4103718535](https://space.samokat.ru/pages/viewpage.action?pageId=4103718535) | [4204577803](https://space.samokat.ru/pages/viewpage.action?pageId=4204577803) | `ecom/dev/is/smkt/cc-exchanger` |

Все page_id также лежат в `catalog.yaml` в корне проекта — скрипты берут их
оттуда, а не из этого документа. Таблица здесь для людей.

GitLab-группа ИС: `https://git.ecom.tech/ecom/dev/is/<контур>/<name_is>`;
репозитории сервисов лежат внутри группы (`<репозитории сервисов>`).
Это **внешний** namespace GitLab — он не связан с раскладкой репозитория
паспортов (`is/<код ИС>/`) и при переносе папок не меняется.

## 5. Путь в dochub

```
architecture/app/<контур>/<сущность>/criticality_passport.yaml
```

Пример: `erm.mm` → `architecture/app/mm/erm/criticality_passport.yaml`,
`cc-exchanger.smkt` → `architecture/app/smkt/cc-exchanger/criticality_passport.yaml`.

Практика (всё это делает `make publish` / `make publish-apply`):

1. Файл кладётся рядом с остальной архитектурной документацией ИС; папка ИС и
   `system.yaml` в ней должны уже существовать — иначе публикация отказывает.
2. В `_root.yaml` в секцию `imports` добавляется ссылка на файл — без этого
   паспорт не собирается в общий документ. Импорт добавляется один раз и входит
   в тот же коммит, что и паспорт.
3. Ветка `feature/<task>` (при нескольких ИС с одной задачей —
   `feature/<task>-<контур>`) создаётся от `origin/master`. При первой
   публикации коммит содержит два файла — паспорт и `_root.yaml`; при повторной
   оценке (`publish --update`) `_root.yaml` уже импортирует паспорт, поэтому в
   диффе остаётся только паспорт — это норма.
4. Ключ верхнего уровня всегда `ecom.criticality_passport`, внутри — один
   объект `sber.ecom.<контур>.criticality_passport.<сущность>`, где дефис
   заменён на подчёркивание (`cc-exchanger` → `cc_exchanger`).
5. Уровень критичности пишется в верхнем регистре (`Business operational` →
   `BUSINESS_OPERATIONAL`) по соответствию из критериев
   (`levels.publish_enum`), а не жёстко зашитым списком.
6. В паспорте только обязательные поля схемы dochub плюс `assigned_date`,
   `review_date`, `approve_link`, если они заполнены; `generated_at`,
   комментарии и `null`-поля не переносятся.

## 6. Где искать ответственных

| Что нужно | Где смотреть |
|-----------|--------------|
| Актуальный TL/SA/владелец ИС | Реестр изменений ответственных 2026: [4323248283](https://space.samokat.ru/pages/viewpage.action?pageId=4323248283) |
| Ответственные 2024–2025 (история) | [3774661271](https://space.samokat.ru/pages/viewpage.action?pageId=3774661271) |
| Команда и роли в SSoT | Карточка ИС в `ssot.ecom.tech` (ответ `ssot_get`, секции `roles` и `duty`; ростер команды — `ssot_team`) |
| Системный архитектор продукта | `catalog.yaml` → `sa` (сейчас Рожков Р.А.) |

Если ответственный сменился — сначала обновите реестр ответственных и SSoT,
потом паспорт. Иначе подтверждение в треде будет от человека, которого уже нет
в системе.

## 7. Перенос в SSoT

1. Взять `criticality_ssot` из паспорта/реестра.
2. Прочитать карточку ИС: ответ MCP `ssot_get(group="information-systems",
   entity=<код>)` → `make ssot-import IS=<код> ENTITY_JSON=-` (снимок в
   `INFORMATION.yaml → ssot_snapshot`). Навигация по карточке в UI —
   `ssot_entity_open`.
3. Посчитать цель и шаги формы: `make ssot-plan IS=<код>` — целевые
   `severity.type`/`severity.confirmation`, гейт R18 и план
   `.ssot/<код>-apply-plan.json`.
4. Убедиться, что секция `components` карточки содержит актуальные репозитории
   сервисов; если расходится — это отдельная правка карточки через SSoT-UI, а
   не этап `ssot`.

Критичность (`severity.type` и `severity.confirmation`) меняется только через
MCP-форму: MR создаёт SSoT, остальные поля карточки (компоненты, роли,
размещение, дата оценки) в этой правке не трогаются. Этап идёт **после**
публикации паспорта в dochub (`make publish-apply`); ссылка на dochub-MR для
SSoT-MR не требуется — `mrUrl` возвращает `ssot_form_save`. Порядок этапов —
`references/workflow.md`.

### Запись severity: только через MCP-форму

**Гейт CI.** Для путей `entities/**` джоб `codeowners` требует минимум один апрув от ботов
`project_14598_bot_*`. Эти боты апрувят только MR, созданные через SSoT-UI, поэтому MR,
созданный напрямую в GitLab мимо SSoT-UI, пройти проверку не может — независимо
от содержимого и от апрувов людей.

Проверено на практике: MR !5404–!5409 в data-storage упали на пункте
«МР можно создавать только через SSoT-UI», имея апрувы техлида и других сотрудников.
Все шесть были закрыты и пересозданы через UI как !5551–!5556.

**Дополнительный гейт для критичности.** Если меняется `severity.*` в карточке, бот SSOT
добавляет в MR блок `@codeowners extend`, требующий **один** апрув от SRE или руководства
технической архитектуры: `@akolomytov`, `@evolvenkova`, `@santonov`, `@schurikov`.
Точный список на конкретном MR — в артефакте джоба `codeowners.json` (поле `required`).
Этот гейт действует и на MR, созданных через UI.

| Что меняется | Кто обязан апрувить |
|---|---|
| `links`, `components`, `roles`, `resources`, `duty` | Техлид ИС |
| карточка с изменением `severity.*` | Техлид ИС **+ минимум один** из SRE/техархитектуры |

**Порядок записи** (MCP `ssot-mcp`):

1. `ssot_entity_open` → `ssot_form_fields` → `ssot_ui_select`/`ssot_ui_fill` →
   `ssot_form_save` — правка формы; создаётся бот-MR
   `api/information-systems/<код>/<stamp>-<suffix>`, ответ содержит `mrUrl` и
   `version`.
2. `make ssot-record IS=<код> MR_URL=<mrUrl>` — `.ssot/<код>-MR.url`,
   `.ssot/<код>-MR.md` и поля `ssot_*` в `INFORMATION.yaml`.
3. Апрувы: техлид ИС и (для `severity.*`) один из SRE/техархитектуры.
4. `ssot_mr_approve(confirm: true)` → `ssot_apply_changes(confirm: true)` после
   того, как `canApply` станет `true` → `ssot_wait_master`.
5. `ssot_verify_change` → `make ssot-verify IS=<код> VERIFY_JSON=-` — сверка
   применённого значения (`.ssot/<код>-verify.json`).

Клона SSoT и git-операций у скилла нет: MR вне SSoT-UI не пройдёт джоб
`codeowners` для путей `entities/**`. Данные SSoT живут в репозитории
`ssh://git@git.ecom.tech:5022/ecom/infrastructure/products-and-services/ssot/ecomtech/data-storage.git`
(`is.yaml → ssot.url`); скилл читает их только через MCP `ssot_get`.

## 8. Источники данных об ИС

Данные об ИС приходят из пяти мест. Приоритет при расхождении — сверху вниз
(первый источник главнее):

| # | Источник | Что даёт | Приоритет |
|---|----------|----------|-----------|
| 1 | **SSoT** — карточка ИС через MCP `ssot_get` (данные в `ssh://git@git.ecom.tech:5022/ecom/infrastructure/products-and-services/ssot/ecomtech/data-storage.git`, веб-UI: https://ssot.ecom.tech/) | канонические атрибуты ИС: название, тип, продукт, команда, критичность, сервисы и их репозитории, дежурства, размещение, роли | **высший**: при расхождении прав SSoT |
| 2 | **Confluence** | процесс (D6.1.1), методика, архитектура ИС, DR, Decision Log, оценка критичности, сервисные страницы; значения входов: тип клиентов, влияние при простое, SLA/RTO, сценарии отказа | высокий: источник истины по процессу и архитектуре |
| 3 | **Grafana** | измеренная нагрузка: панели трафика шлюзов папки продукта E001 → пик RPS → `peak_hour_load` | высокий для нагрузки: единственный измеренный источник; для остальных полей не применяется |
| 4 | **`catalog.yaml`** (этот репозиторий) | курируемый реестр: код ИС, путь, arch code, команда, критичность и маппинг в SSoT, все page_id, GitLab-группа, статус | производная от SSoT + Confluence |
| 5 | **`is.yaml`** (корень, gitignored) | список ИС для анализа + `ssot.url`; вход для подготовки данных | рабочий конфиг, не источник истины |

### 8.0. Провенанс: что берём и какой `ref`

Каждое значение в `INFORMATION.yaml` несёт `source: {type, ref}`. Форма `ref`
зависит от типа — иначе источник нельзя перепроверить.

| `type` | Что берём | Форма `ref` |
|--------|-----------|-------------|
| `ssot` | атрибуты карточки ИС: название, тип, продукт, команда, критичность, компоненты, дежурства, размещение, роли | `entities/information-systems/<код>/base.yaml#severity.type` — путь внутри снимка `ssot_snapshot` (ответ `ssot_get`) |
| `confluence` | тип клиентов, влияние при простое, SLA/RTO, сценарии отказа, E2E, ПДн, ADR | `<page_id>, раздел «<название>»` — дословная цитата в `evidence` |
| `grafana` | пиковая нагрузка (`peak_rps` → `peak_hour_load = peak_rps × 3600`) | `dashboard uid=<uid>, panel <id>, datasource <uid>, expr: <точный PromQL>, окно 7d/30d` |
| `catalog` | arch code, актив, page_id, GitLab-группа | `catalog.yaml#systems.<код>.<поле>` |
| `is_yaml_override` | переопределение `product` / `teamName` | `is.yaml#is.<код>` |
| `gitlab` | документация клонов сервисов (`docs/`, `openspec/`), SLO-конфиг; репозиторий или MR | цитата из клона — `apps/<код ИС>/<сервис>/<файл>:<строка>`; репозиторий — `https://git.ecom.tech/ecom/dev/is/<контур>/<name_is>` |
| `jira` | задача процесса | `E001-1234` |
| `attachment` | вложение Confluence: таблица, выгрузка, калькулятор | `docs/reference/calculator/<файл>.xlsx` или `page_id=<id>, вложение <имя>` |
| `ssot_links` | ссылка из карточки ИС в SSoT (секция `links`): дашборды, DRP, паспорт поддержки | `entities/information-systems/<код>/links.yaml` — путь внутри снимка `ssot_snapshot` |
| `manual` | экспертное решение: `axes_scores`, `cia`, финансовые потери | `<роль: логин>` + `status: confirmed`; решение владельца без цитаты — `решение PdM, <YYYY-MM-DD>; INFORMATION.yaml#notes` |

Правила: `confluence` без `page_id` и раздела — не источник; `grafana` без
uid/панели/PromQL — не источник; `gitlab` без сервиса и строки (для цитаты из
клона) — не источник; `manual` без имени подтвердившего — не источник; решение
владельца без ссылки на само решение — `missing`, а не `manual`
(`criteria.provenance.manual_decision`). Порядок
сбора при `BLOCKED` — `collect` → сбор по плану (SSoT, Confluence, Grafana) →
`services` → `check` → `enrich`
([09-pipeline.md](09-pipeline.md) §2.2.1).

Промежуточные артефакты сбора — `RESEARCH-PLAN.md` (что открыть и у кого
спросить), `LINK-MAP.md`/`.yaml` (какие узлы обходить и в каком порядке),
`SOURCES-FINDINGS.yaml` (что агент нашёл, с цитатами) и `SERVICE-FINDINGS.md`
(цитаты из документации клонов). Это не источники значений: `source.type`
остаётся `confluence` / `grafana` / `gitlab` / `manual` / `attachment` /
`ssot_links`, а цитата «файл:строка» из `SERVICE-FINDINGS.md` — основание
для разговора с владельцем, а не подтверждённое значение. Закрытые сервисы
(`lifecycle: closed`, `criteria.service_lifecycle.skip`) в отчёт не попадают: они
не клонируются и основанием для входов не служат.

### 8.1. Структура карточки ИС в SSoT

Ответ `ssot_get` (снимок `INFORMATION.yaml → ssot_snapshot`) приходит ключами по
разделам карточки:

```text
base        # name, type, product, team, criticality (severity.type)
components  # сервисы: name, описание, языки, статусы, gitRepository
duty        # ответственные за дежурства (on-call)
links       # основные ссылки по ИС для навигации
resources   # размещение ИС в инфраструктуре
roles       # ролевая модель: код, тип роли, критичность роли, ответственный
```

Полезные детали:

- `base` — первое, что нужно сверить с `catalog.yaml` (название, продукт,
  команда, критичность).
- `components` → поле `gitRepository` — единственный надёжный способ
  получить список репозиториев сервисов ИС: по нему `make services-apply`
  клонирует сервисы в `apps/<код ИС>/<сервис>/` и читает их документацию
  (`docs/`, `openspec/`), не собирая и не запуская код. GitLab API из окружения
  недоступен, поэтому всё, чего нет в `gitRepository` (MR, пайплайны, покрытие),
  в паспорт не попадает и остаётся TODO для TL.
- `duty` — кто реально дежурит; нужен для эскалации при инциденте.
- `resources` — размещение (кластеры/ДЦ), сверяется с разделами
  «Зависимости» в `CRITICALITY.md`.

### 8.2. `catalog.yaml` — производная, а не источник

`catalog.yaml` собран из SSoT и Confluence и поддерживается вручную. Из этого
следуют два правила:

1. **Расхождение с SSoT — ошибка в `catalog.yaml`**, а не в SSoT. Правьте реестр
   (и паспорт), затем `make validate`.
2. **Расхождение с Confluence по page_id/архитектуре** — проверяйте страницу:
   Confluence первичен для архитектуры и процесса, SSoT — для атрибутов ИС,
   Grafana — для нагрузки (`peak_hour_load`).

### 8.3. `is.yaml` — список ИС для анализа

`is.yaml` лежит в корне и **gitignored** (как и `apps/`). Формат и
процесс подготовки данных описаны в `INFORMATION.md` в корне проекта:

```yaml
is:
  erm.mm: true            # анализировать как есть
  cc-exchanger.mm: true
ssot:
  url: ssh://git@git.ecom.tech:5022/ecom/infrastructure/products-and-services/ssot/ecomtech/data-storage.git
```

Отличие от `catalog.yaml`: `is.yaml` — это **входной конфиг для анализа**
(какие ИС обрабатывать и откуда брать SSoT), а `catalog.yaml` — **результат**
(реестр с уже собранными данными). Не путайте их: `is.yaml` читают команды
`prepare` (подготовка данных) и `check` (гейт достаточности), а `catalog.yaml` —
`validate`, `index`, `due`, `show`, `score`.

### 8.4. `INFORMATION.yaml` — слой данных между SSoT и паспортом

`is/<код ИС>/INFORMATION.yaml` — единственное место, где встречаются
SSoT и ручные входы критериев. Его собирает `make prepare-apply`
(см. [09-pipeline.md](09-pipeline.md)); паспорт и `CRITICALITY.md` берут числа
только отсюда.

```text
SSoT (ответ `ssot_get` → `ssot_snapshot`)
        │  + переопределения is.yaml (product, teamName)
        ▼
INFORMATION.yaml ── автоматические секции: meta, identity, components,
        │           resources, duties, links, roles, ssot_snapshot
        │  + ручные секции: criteria_inputs, conflicts, notes
        ▼
criticality-passport.yaml / CRITICALITY.md  (make start, этап 2b)
```

Правила приоритета:

1. **Автоматические секции** — проекция SSoT. Расхождение с SSoT — ошибка не в
   `INFORMATION.yaml`: правьте SSoT (или `catalog.yaml`, если речь об
   `arch_code`). Ручная правка этих секций будет затёрта следующим `prepare`.
2. **Переопределения `is.yaml`** (`product`, `teamName`) сильнее SSoT и
   помечаются `product_source: {type: is_yaml_override, ref: "is.yaml#is.<код>.product"}`
   / `team_source: {type: is_yaml_override, ref: "is.yaml#is.<код>.teamName"}`.
3. **Ручные секции** (`criteria_inputs`, `conflicts`, `notes`) сильнее всего и
   никогда не перезаписываются автоматикой.
4. **`catalog.yaml` и `INFORMATION.yaml` не дублируют друг друга**: реестр
   отвечает за навигацию и историю оценок (page_id, статус, даты), а
   `INFORMATION.yaml` — за данные ИС и входы расчёта.

Провенанс каждого значения записывается объектом `{ type, ref }` с `type` из
списка `ssot | is_yaml_override | catalog | confluence | gitlab | jira | grafana | attachment | ssot_links | manual`.
Значение без источника остаётся `null` со `status: missing` — «примерных»
чисел в этом слое нет.

## 9. Источники

- Продукт E001: [3910775831](https://space.samokat.ru/pages/viewpage.action?pageId=3910775831)
- Методика: [4566730084](https://space.samokat.ru/pages/viewpage.action?pageId=4566730084) («Методика и оригинальные расчёты», ECOMCS, v13, 2026-11-17)
- Носитель матриц `impact_matrix` / `final_matrix` и шкал осей: [4207454433](https://space.samokat.ru/pages/viewpage.action?pageId=4207454433) (архив, `archived_carrier`, v3, 2025-12-01)
- Процесс D6.1.1: [3855374712](https://space.samokat.ru/pages/viewpage.action?pageId=3855374712)
- Реестр ответственных 2026: [4323248283](https://space.samokat.ru/pages/viewpage.action?pageId=4323248283)
- Реестр ответственных 2024–25: [3774661271](https://space.samokat.ru/pages/viewpage.action?pageId=3774661271)

## Связанные документы

- [09-pipeline.md](09-pipeline.md) — как SSoT превращается в `INFORMATION.yaml`.
- [03-fields.md](03-fields.md) — формат полей паспорта.
- [04-reassessment.md](04-reassessment.md) — когда критичность переносится в SSoT.
- [12-requirements.md](12-requirements.md) — источники значений и процедуры сбора.
- `catalog.yaml` (корень проекта) — реестр с кодами, page_id и GitLab-группами.
- `INFORMATION.md` (корень проекта) — спецификация подготовки данных и формат `is.yaml`.

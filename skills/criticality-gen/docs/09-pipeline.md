---
title: Пайплайн подготовки данных и генерации
purpose: Описать конвейер «is.yaml → SSoT → INFORMATION.yaml → гейт → артефакты» и его отличия от INFORMATION.md.
audience: [ai-agent, human]
read_when: [готовите данные из SSoT, make check вернул BLOCKED, нужно понять откуда берётся поле паспорта]
updated: 2026-11-24
status: actual
related: [08-criteria.md, 07-scripts.md, 10-templates.md, 05-mapping.md, rules.md]
---

# Пайплайн подготовки данных и генерации

## Когда читать

- Читать, когда готовите данные: `make init` → `make ssot-import` → `make prepare-apply` → `make check`.
- Читать, когда нужно понять, какое поле паспорта из какого файла снимка SSoT берётся.
- Читать, когда `make check` вернул `BLOCKED` и нужно найти недостающий вход.
- Читать, когда сверяете фактическую реализацию с `INFORMATION.md`.

## Кратко

- Конвейер, его фазы и гейты — один источник: `.opencode/skills/criticality-gen/references/workflow.md`; здесь описана только подготовка данных (`ssot-import` → `prepare` → `INFORMATION.yaml`).
- Автоматические секции `INFORMATION.yaml` — проекция снимка карточки ИС; ручные секции (`criteria_inputs`, `facts`, `conflicts`, `notes`) автоматика не перезаписывает.
- `make ssot-import` — снимок карточки ИС из ответа MCP `ssot_get` в `INFORMATION.yaml`; `make prepare` — план без записи; `make prepare-apply` — запись файлов и git-операции по компонентам; закрытые сервисы (`lifecycle: closed`) не клонируются.
- Гейт `make check` strict: при `BLOCKED` возвращает ненулевой код; `make check-diag` — код 0. Сценарий расчёта выбирается по данным: простой (4 входа) или сложный (все 7).
- `make services-apply` собирает `SERVICE-FINDINGS.md` из документации клонов (`docs/`, `openspec/`); клоны только читаются.
- `make start` — dry-run, `make start-apply` — запись; паспорт и `CRITICALITY.md` перезаписываются только с `FORCE=1`.

Документ описывает конвейер «конфиг → SSoT → данные ИС → гейт → артефакты»,
реализованный в `scripts/criticality.py`, и то, как он соотносится с
`INFORMATION.md` в корне проекта.

## 1. Схема пайплайна

```text
is.yaml  (что анализируем + ssot.url)
   │
   ├─► ssot-import                снимок карточки ИС из MCP ssot_get
   │      INFORMATION.yaml ← ssot_snapshot: base, components, duty, links,
   │      resources, roles (+ contacts из ssot_team); сети и клона нет
   │
   ├─► prepare (apps/)            git clone / git pull  (сеть — только с --apply)
   │      apps/<код ИС>/<сервис>/            ← git clone / pull компонентов
   │                                          (lifecycle: closed — skip, не клонируется)
   │
   ├─► is/<код ИС>/INFORMATION.yaml              ← make prepare-apply
   │      автоматические секции: meta, identity, components, resources, duties,
   │                             links, roles, ssot_snapshot
   │      ручные секции:         criteria_inputs, facts, conflicts, notes,
   │                             publication (extra_info — опциональный текст треда)
   │                             (переносятся дословно; повторный prepare не меняет sha1)
   │
   ├─► make check                 ПЕРВИЧНЫЙ ГЕЙТ: полон ли набор входов сценария
   │      сценарий: простой (4 входа) | сложный (все 7, фолбэк запрещён)
   │      BLOCKED  → здесь же создаётся DATA-REQUIREMENTS.md/.yaml
   │                 (что это, зачем, где взять, у кого, как подтвердить)
   │      SKIPPED  → ИС исключена (catalog.yaml или is.yaml → excluded: true), не блокирует
   │
   ├─► make collect-apply         ПЛАН СБОРА: RESEARCH-PLAN.md
   │      страницы Confluence (page_id, что искать) + дашборды Grafana
   │      и запросы PromQL + кто подтверждает; пустой — удаляется
   │
   ├─► make research              СБОР ДОКАЗАТЕЛЬСТВ: RESEARCH.md + CANDIDATES.yaml
   │      CQL-запросы criteria.inputs.<вход>.queries по каждому открытому входу
   │      (плюс маршруты criteria.inputs.routes: e2e, financial_loss)
   │      оценка direct | indirect | none; кандидат — только direct
   │      у кандидата фиксируется сила доказательства: «шагов N»
   │      повторный прогон не дублирует кандидатов (ключ page_id + вход)
   │      любая проблема сбора — код 1 (--allow-partial → WARN, отчёт неполный)
   │
   ├─► сбор: SSoT → Confluence → Grafana
   │      SSoT:        идентификация ИС и список компонентов
   │      Confluence:  дерево страниц ИС, BFS до глубины 2
   │      Grafana:     папка E001 → панели трафика → peak_rps × 3600
   │      экспертно:   axes_scores, cia (из документов не выводятся)
   │
   ├─► make services-apply        КОД СЕРВИСОВ: SERVICE-FINDINGS.md
   │      клоны apps/<код ИС>/<сервис>/ → docs/ и openspec/
   │      цитаты «файл:строка», нормативы, потоки, «вход → основание»
   │      lifecycle: closed — пропущены, не клонируются и не анализируются
   │      только чтение: сборка и запуск запрещены (_git_only)
   │
   ├─► make check                 ГЕЙТ: определение сценария + полнота его набора
   │      BLOCKED  → дальше нельзя: лист DATA-REQUIREMENTS.md/.yaml уже лежит
   │      SKIPPED  → ИС исключена (catalog.yaml или is.yaml → excluded: true), не блокирует
   │      OK       → расчёт разрешён
   │
   ├─► make ask                   ВОПРОСЫ ЧЕЛОВЕКУ: ASK.md (или --json)
   │      незакрытые входы, enum дословно, кандидаты с провенансом
   │      порядок кандидатов: direct (шагов N) → indirect → прочее;
   │      внутри группы — по числу совпадений (references/search.md §4)
   │
   ├─► make ask-answers           ОТВЕТЫ: ANSWERS.yaml → DATA-REQUIREMENTS.yaml
   │      ответы принимаются теми же валидаторами, что гейт
   │      INFORMATION.yaml не меняется ни на байт
   │
   ├─► make enrich-apply          при BLOCKED: приём заполненного DATA-REQUIREMENTS.yaml
   │      значения → INFORMATION.yaml (source + status: confirmed)
   │      лист и план перегенерируются с остатком; пустые — удаляются
   │      затем make check повторяется до OK
   │
   ├─► make start                 генерация артефактов ИС из шаблонов
   │
   ├─► make validate              0 ERROR по паспортам и реестру
   │      + verify-titles: заголовки страниц сверены с Confluence (R19)
   │
   ├─► make index                 INDEX.md (если менялся состав ИС или уровни)
   │      is/<код ИС>/criticality-passport.yaml + CRITICALITY.md
   │      + GENERATION.md + actions/{jira-task,confluence-page,rocketchat-message}.md
   │
   ├─► make publish-apply         паспорт в формате dochub (клон, ветка, коммит, MR)
   │      architecture/app/<контур>/<сущность>/criticality_passport.yaml
   │      + _root.yaml (импорт)  + .publish/<код>-MR.md
   │      пуш и создание MR — только --push по подтверждению человека
   │      ссылка MR после пуша: .publish/<код>-MR.url в клоне и
   │      .dochub/<код>-MR.url в проекте (её читает start → actions.mr_link)
   │
   └─► make ssot-plan             ОБОГАЩЕНИЕ SSoT критичностью (severity)
          план из снимка SSoT: целевые severity.type и severity.confirmation,
          гейт R18 → .ssot/<код>-apply-plan.json + шаги MCP
          MCP: ssot_entity_open → ssot_form_fields → ssot_ui_select /
               ssot_ui_fill → ssot_form_save (MR создаёт SSoT, отдаёт mrUrl+version)
          → make ssot-record MR_URL=<mrUrl> VERSION=<version> → .ssot/<код>-MR.url|md
          → ssot_wait_version → make ssot-verify VERIFY_JSON=- → .ssot/<код>-verify.json
          severity в SSoT уже совпадает → no_change, MR не создаётся

   └─► make finalize              ФИНАЛИЗАЦИЯ (approve_link = thread_link при handoff_status: published)
          catalog.yaml → systems[<код>]: approve_link, assigned_date,
          review_date, criticality, criticality_ssot, status: confirmed
          даты — от даты генерации паспорта (generated_at), не от момента finalize
          затем start-apply FORCE=1 → validate → index → verify
          ERROR в validate — записанные поля откатываются (атомарность)
```

Канонический порядок — единственный правильный:

```text
init  →  ssot-import (снимок карточки ИС из MCP ssot_get)
      →  prepare (компоненты)  →  check (первичный гейт)  →  collect (план сбора)
      →  research (сбор кандидатов)  →  сбор: SSoT → Confluence → Grafana
      →  services (клоны сервисов + docs/ и openspec/ → SERVICE-FINDINGS.md)
      →  check (определение сценария + гейт)
      →  при BLOCKED: ask (вопросы)  →  ask-answers  →  enrich-apply  →  check
      →  score (расчёт без записи)  →  start-apply (артефакты)
      →  validate (+ verify-titles)  →  index
      →  publish (dochub-MR)  →  ssot-plan  →  MCP ssot_form_save  →  ssot-record
      →  ssot-verify  →  handoff  →  finalize (после подтверждения SRE)
```

`make verify` — единая точка проверки **всех** результатов: `criteria-check`,
`selftest`, `validate`, `docs-check`, `verify-titles`, `skill-check` одним
прогоном. Итоговая строка `ИТОГО: N гейтов, X ошибок, Y предупреждений` —
единственный ответ на вопрос «всё ли в порядке»; гонять гейты по одному имеет
смысл только при разборе конкретной ошибки. Код возврата ≠ 0 — провал хотя бы
одного гейта (какие именно — печатается в строке `Результат: FAIL — провалены:`).
`make verify` требует `CONFLUENCE_TOKEN` (гейт `verify-titles`): в офлайне и CI
без токена он падает по дизайну — «проверка не выполнена» вместо «всё OK».

`research` намеренно **не** предлагается в `next_step`: это инструмент сбора
доказательств, а не обязательный этап конвейера — уровень считается и без него,
и его отсутствие не блокирует паспорт.

Термины разграничены: `publish` — MR с паспортом в **dochub**; `ssot` — MR с
блоком `severity` в **SSoT**, его создаёт MCP-форма (`ssot_form_save` возвращает
`mrUrl` и `version`); `handoff` — тред согласования в
**`#Criticality_assessment`** со ссылками на оба MR.
«Публикация в `#Criticality_assessment`» — это `handoff`, а не `publish`.
`handoff` — последний этап: `make handoff SEND=auto` собирает текст из текущего
состояния, печатает его целиком и отправляет ОДНИМ сообщением только после
явного подтверждения человеком (MCP, при отказе — REST);
`make handoff-apply CONFIRM=1` — тонкая обёртка того же пути только по REST,
с общей идемпотентностью.
`index` — боковой этап: выполняется, когда менялся состав ИС или уровни.

### 1.1. Инвариант порядка: внешние изменения — только после зелёной валидации

Полный цикл строго в таком порядке (перескочить этап нельзя):

1. **полное исследование** — все входы из всех источников (`prepare-apply`,
   `collect-apply`, `services-apply`, MCP Confluence/Grafana, `ask`);
2. **заполнение критериев** — значения с провенансом (`enrich-apply`);
3. **оценка критичности** — расчёт (`check` → `start-apply`);
4. **проверка валидности ВСЕХ результатов** — `make validate` без ERROR и
   `criteria_fingerprint` артефактов = текущим критериям;
5. **внешние изменения** — `publish-apply` (MR в dochub), затем `ssot-plan` →
   MCP `ssot_form_save` (MR создаёт SSoT) → `ssot-record` → `ssot-verify`;
6. **тред для публикации** — `handoff` в `#Criticality_assessment`.

Формировать MR до зелёной валидации **запрещено** (`references/rules.md`, R18):
внешняя ветка живёт дольше локального прогона и видна другим командам, а
паспорт, посчитанный по старым критериям, читается как действующий.

| Гейт | Где | Что проверяет | Отказ |
|------|-----|---------------|-------|
| Полнота входов | `make check`, `start` | blocking-входы выбранного сценария закрыты, значения в допустимых множествах | `BLOCKED` + `DATA-REQUIREMENTS.*`, расчёт не выполняется |
| Валидация | `make validate` | 0 ERROR по паспортам и реестру | код ≠ 0, `Результат: FAIL` |
| Фингерпринт критериев | `make validate` (WARN), `publish`/`ssot-plan` (отказ) | `criteria_fingerprint` в `CRITICALITY.md` = текущим критериям | `ERROR: … criteria_fingerprint не совпадает … make start-apply IS=<код> FORCE=1` |
| Внешние изменения | `publish`, `publish-apply`, `ssot-plan`, `ssot-record` | зелёный `validate` + совпавший фингерпринт + закрытые blocking-входы | код 1, причина и следующий шаг в выводе; обход — только `FORCE=1` (`--force`) с WARN и записью в `is/<код>/.gate-overrides.log` |
| Публикация в тред | `handoff` | в тексте сообщения нет `⛔ не заполнено`, `validate` без ERROR, SSoT-MR записан и подтверждён `ssot-verify` (либо `ssot_status: no_change`), `thread_link` ещё пуст | код 1 с причиной: список незаполненных полей / ERROR validate / SSoT-MR не подтверждён / «уже опубликовано»; при `⛔` статус пакета остаётся `pending_manual` |

Подсказка `next_step` (в `make help`, в `make next-step [IS=<код>]` и после
каждой команды) знает тот же порядок: `validate` → проверка фингерпринта →
`publish` → `ssot` → `handoff`, и не советует внешний шаг, пока предыдущий не
пройден. После отправки треда (`handoff_status: published`) подсказка ведёт к
`make finalize IS=<код> APPROVE_LINK=<ссылка>`, а не к повторному `handoff`.

Обоснование порядка: информация собирается из всех источников — включая клоны
сервисов — **до** расчёта; сценарий (простой/сложный) определяется на гейте
после сбора; при нехватке данных расчёт блокируется, значения принимаются через
`enrich`, затем гейт повторяется. Поэтому `services` не может стоять раньше
`сбор`: клоны сервисов — такой же источник оснований, как Confluence и Grafana,
и их цитаты должны попасть в лист требований до `enrich`. Финальные этапы
(`publish` → `ssot` → `handoff`) упорядочены по зависимостям: SSoT обогащается
после публикации паспорта (MR создаёт MCP-форма), а тред ссылается на оба MR —
dochub и SSoT.

Правило гейта (из `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml`, `inputs.gate`): если
хотя бы один blocking-вход выбранного сценария недоступен, расчёт **не
выполняется** — возвращается `incomplete`/`BLOCKED` со списком недостающих
входов и требованием указать источник либо значение. Сценариев два
(`criteria.scenarios`): простой — четыре входа калькулятора, сложный — все семь
входов `inputs.required`; неполный сложный набор блокирует расчёт, фолбэк на
простой запрещён.

Гейт считается **одной функцией** `evaluate_gate(info, criteria)` — её
используют `check`, `start` и `score --is`. Разные команды не могут дать разный
вердикт на одних и тех же данных.

## 2. Шаги: команда, чтение, запись, идемпотентность

| Шаг | Команда | Что читает | Что пишет | Идемпотентность |
|-----|---------|------------|-----------|-----------------|
| 0. Конфиг | `make init` | `is.example.yaml` | `is.yaml`, `.gitignore` | Не перезаписывает существующие файлы (`is.yaml` — только с `FORCE=1`); `.gitignore` дополняется отсутствующими записями (`/apps/`, `/dochub/`, `/.dochub/`, бэкапы) |
| 1. Снимок SSoT | `make ssot-import IS=<код> ENTITY_JSON=-` | ответ MCP `ssot_get` (JSON карточки ИС), при `TEAM_JSON=` — ответ `ssot_team` | `INFORMATION.yaml → ssot_snapshot` (base, components, duty, links, resources, roles) + `contacts` | Да: повторный импорт тех же данных — no-op (`imported_at` сохраняется) |
| 2. Данные ИС | `make prepare-apply` | `INFORMATION.yaml → ssot_snapshot`, `catalog.yaml`, `is.yaml` | `is/<код ИС>/INFORMATION.yaml` | Да: файл пишется только если нормализованный текст изменился (`unchanged` иначе) |
| 3. Компоненты | `make prepare-apply` | `components.yaml` → `gitRepository`, `lifecycle` | `apps/<код ИС>/<component_name>/`; закрытые (`lifecycle: closed`) не клонируются | Да: существующий репозиторий → `pull --ff-only`, не пересоздаётся; закрытый компонент печатается как `skip (lifecycle: closed)` |
| 4. Гейт | `make check` | `is.yaml`, `INFORMATION.yaml`, `criteria/` | `DATA-REQUIREMENTS.md` + `.yaml` для каждой `BLOCKED` ИС | Да: дата листа из `catalog.yaml`, не `now()` |
| 4a. План сбора | `make collect` / `make collect-apply IS=<код>` | `INFORMATION.yaml`, `catalog.yaml`, снимок SSoT (`ssot_snapshot.links`, `ssot_snapshot.components`), `criteria/` | `RESEARCH-PLAN.md` для каждой `BLOCKED` ИС | Да: дата плана из `--date`/`catalog.yaml`, не `now()` |
| 4b. Карта обхода | `make links` / `make links-apply IS=<код>` | снимок SSoT (`ssot_snapshot.links`), `catalog.yaml` (`*_page_id`), `INFORMATION.yaml#components[]` (`ssot_snapshot.components`), `criteria/` | `is/<код ИС>/LINK-MAP.md` (контракт обхода) + `LINK-MAP.yaml` (карта: `nodes[]` с `kind`/`ref`/`origin`/`expand`/`candidate_for`/`status`) | Да: дата из `--date`/`catalog.review_date`, `now()` нет; дедупликация по `(вид, ключ адреса, subject)`; повторный `--apply` — `unchanged`; расхождение без `--force` — `CONFLICT` и код 1 |
| 4c. Приём источников | обход по `LINK-MAP.md` (MCP-агент) → `make sources` / `make sources-apply IS=<код>` | `is/<код ИС>/SOURCES-FINDINGS.yaml`, `LINK-MAP.yaml`, `INFORMATION.yaml`, `criteria/` | `INFORMATION.yaml#criteria_inputs` (`status: confirmed`, с бэкапом) + статусы узлов `LINK-MAP.yaml` | Да при тех же фактах; проверки те же, что у гейта/`enrich`; любое отклонение — код 1 (принятые при этом записываются); в dry-run файлы не меняются |
| 4d. Сбор | MCP Confluence + MCP Grafana (по плану и карте) | дерево страниц ИС, панели трафика папки E001 | `SOURCES-FINDINGS.yaml` (заполняет агент), `DATA-REQUIREMENTS.yaml` (человек) | — (внешние системы только читаются) |
| 4e. Код сервисов | `make services` / `make services-apply IS=<код>` | `INFORMATION.yaml#components[]` (`git_repository`, `lifecycle`), клоны `apps/<код ИС>/<сервис>/` (`docs/`, `openspec/`, SLO-конфиги) | `apps/<код ИС>/<сервис>/` (clone/pull) + `is/<код ИС>/SERVICE-FINDINGS.md` | Да: дата отчёта из `--date`/`catalog.review_date`, не `now()`; закрытые сервисы пропускаются; `NO_CLONE=1` (`--no-clone`) не вызывает git — отсутствующие клоны идут в §2 отчёта |
| 4f. Дозаполнение | `make enrich-apply IS=<код>` | `DATA-REQUIREMENTS.yaml`, `INFORMATION.yaml` | `INFORMATION.yaml` (секция `criteria_inputs`), остаток листа и плана | Да при тех же значениях |
| 5. Генерация | `make start` / `make start-apply` | `INFORMATION.yaml`, `criteria/`, `.opencode/skills/criticality-gen/templates/`, `catalog.yaml` | артефакты ИС | Да при одинаковых входах и `--date`: побайтово одинаковый результат; паспорт и `CRITICALITY.md` без `--force` не перезаписываются |
| 6. Валидация | `make validate` | `catalog.yaml`, паспорта, `CRITICALITY.md` | ничего (stdout) | Да; просрочка считается по `due_date = review_date + период переоценки`, где `review_date` **из реестра** (паспорт — копия), поэтому дата генерации её не маскирует |
| 7. Публикация | `make publish` / `make publish-apply IS=<код> TASK=<key>` | `is/<код ИС>/criticality-passport.yaml`, схема клона dochub (`_metamodel_/`), `<папка ИС>/system.yaml`, `criteria/` | в клоне dochub: `architecture/app/<контур>/<сущность>/criticality_passport.yaml`, импорт в `_root.yaml`, ветка `feature/<task>` + коммит, `.publish/<код>-MR.md` | Да при том же входе: паспорт и `_root.yaml` рендерятся детерминированно; повторный запуск упирается в существующую ветку и просит `--branch`; `.publish/` грязью не считается |
| 8. Обогащение SSoT | `make ssot-plan IS=<код>` → MCP-форма → `make ssot-record IS=<код> MR_URL=<mrUrl> VERSION=<version>` → `make ssot-verify IS=<код> VERIFY_JSON=-` | `is/<код ИС>/criticality-passport.yaml`, `catalog.yaml` (`criticality_ssot`, `approve_link`), `criteria/levels.ssot_enum`, `INFORMATION.yaml → ssot_snapshot` (текущий `severity`), ответы MCP `ssot_form_save` / `ssot_verify_change` | `.ssot/<код>-apply-plan.json` (план и шаги MCP), MR SSoT с изменёнными `severity.type`/`severity.confirmation` (MR создаёт SSoT), `.ssot/<код>-MR.url`, `.ssot/<код>-MR.md`, `.ssot/<код>-verify.json`; в `INFORMATION.yaml` — `ssot_status`, `ssot_mr_url`, `ssot_version`, `ssot_can_apply`, `ssot_recorded_at`, `ssot_snapshot.verified`; в `catalog.yaml` → `systems.<код>.ssot_status` (`no_change` / `mr_pending` / `mr_created` / `mr_verified` / `mr_unverified`) | Да: повторный `ssot-record` с тем же `mrUrl`/`version` — no-op; `ssot-plan` при совпавшем `severity` пишет `no_change` и MR не создаётся (в публикации — «не требуется», а не `⛔`); `ssot-verify` перезаписывает `.ssot/<код>-verify.json` |
| 9. Индекс | `make index` | `catalog.yaml` + паспорта | `INDEX.md` (блок между маркерами) | Да при той же `--date`; `review_date` — из реестра |
| 9a. Тред | `make handoff IS=<код> SEND=auto` / `make handoff-result IS=<код> MESSAGE_URL=<url>` | `is/<код>/actions/rocketchat-message.md` (тот же рендер `publication.md`), паспорт, `catalog.yaml`, `.dochub/`/`.ssot/` (ссылки на MR) | `catalog.yaml → systems.<код>`: `handoff_mode`, `handoff_status`, `thread_link`, `approve_link` (= `thread_link`), `published_at`, `handoff_error`, `handoff_deadline`, `fallback_reason`, `transport_used`; `is/<код>/.handoff-request.json` при транспорте MCP | Да: повторная отправка при заполненном `thread_link` запрещена (`--force-resend` — осознанный обход); `approve_link` = тред согласования, подтверждение — мерж MR |

`make prepare` — это **dry-run**: печатает план, git-команды и итоговую таблицу,
ничего не пишет и не ходит в сеть. `make prepare-apply` выполняет то же самое с
записью. Флаг `--no-clone` (`NO_CLONE=1`) полностью отключает git-операции по
компонентам — полезно на машине без доступа к `git.ecom.tech` и в тестах.

**`prepare-apply` без снимка SSoT не пишет и падает.** Если
`INFORMATION.yaml → ssot_snapshot` пуст, команда печатает
`ERROR: prepare: нет данных SSoT — данные ИС не обновлены; импортируйте снимок: criticality.py ssot-import --is <код> --entity-json -`
и возвращает ненулевой код; `INFORMATION.yaml` не изменяется (ни один файл, ни
`components`, ни `resources`). Снимок приносит только MCP (`ssot_get`); клона
SSoT нет. Раньше в этом состоянии автоматические секции молча превращались в
пустые — это была потеря данных.

**Секция, отсутствующая в снимке, сохраняется.** Если в снимке SSoT нет
файла/ключа для секции (`components.yaml`, `resources.yaml`, `duty.yaml`,
`links.yaml`, `roles.yaml`, `base.yaml`), `prepare` оставляет в
`INFORMATION.yaml` прежнюю версию секции и печатает
`WARN: секция <имя> отсутствует в SSoT — сохранена прежняя версия (N записей)`.
Очистить такие секции можно только осознанно — `--allow-empty-sections`
(тогда печатается число удалённых записей). Dry-run печатает те же сведения:
какие секции остались бы прежними.

**Бэкап и атомарная запись.** Перед записью `INFORMATION.yaml` рядом
создаётся `INFORMATION.yaml.bak-<YYYYMMDD-HHMMSS>` (`--no-backup` отключает;
`*.bak*` в `.gitignore`). Все записи файлов атомарные: временный файл в той же
папке → `flush` + `fsync` → `os.replace`; обрыв процесса не оставляет
обрезанный YAML.

### 2.1. Флаги `prepare`

| Флаг | Смысл |
|------|-------|
| `--dry-run` (по умолчанию) | ничего не пишет, git не вызывает; печатает, какие секции были бы сохранены из-за отсутствия в снимке SSoT |
| `--apply` | пишет `INFORMATION.yaml`, для компонентов выполняет `git clone` / `git fetch --prune` + `git pull --ff-only`; компоненты с `lifecycle: closed` не клонируются (печатается `skip (lifecycle: closed)`) |
| `--no-clone` | не выполнять git-операции по компонентам (`apps/`) |
| `--is <код>` | обработать одну ИС, например `--is erm.mm` |
| `--force-overwrite` | перезаписать `INFORMATION.yaml`, даже если он не разобран (ручные секции будут потеряны — только осознанно) |
| `--allow-empty-sections` | разрешить очищать автоматические секции, отсутствующие в снимке SSoT (по умолчанию сохраняется прежняя версия); печатает число удалённых записей |
| `--no-backup` | не создавать `INFORMATION.yaml.bak-<дата>` перед записью |

Перед обновлением существующего клона компонента (`apps/`)
выполняется `git fetch --prune`, затем `git pull --ff-only`. Ветка не
переключается: `checkout`/`reset`/`clean` запрещены git-allowlist'ом скилла
(`clone`, `pull`, `fetch`, `rev-parse`, `log`, `status`, `show`, `diff`,
`ls-remote`); попытка другой подкоманды — `ERROR: git-команда '<x>' запрещена
скиллом (allowlist: …)` и ненулевой код. Если `pull --ff-only` невозможен
(локальные изменения/расхождение истории), клон не ломается: печатается
`WARN`, данные не теряются.

Таймаут git — 120 секунд на команду. `shell=True` не используется: команды
передаются списком аргументов. Ошибка клонирования одного компонента не
прерывает прогон — компонент получает `clone_status: error`, ошибка попадает в
отчёт, остальные ИС обрабатываются.

**Защита ручных данных.** Если существующий `INFORMATION.yaml` не разобран
мини-парсером, `prepare` печатает `ERROR` и **не перезаписывает файл**:
ручные секции (`criteria_inputs`, `facts`, `conflicts`, `notes`) иначе были бы
потеряны. Прогон возвращает ненулевой код; перезапись — только с
`--force-overwrite` (`make prepare-apply FORCE_OVERWRITE=1`).

### 2.2. Генерация (`start`)

`start` — единственная команда, которая пишет артефакты ИС. Любой артефакт —
это **шаблон + факты из `INFORMATION.yaml` + детерминированный расчёт**. Нет
факта — в артефакте явный маркер (`⛔ не заполнено` / `null`), а не придуманное
значение.

```bash
make start                      # dry-run: рендер в память, список файлов
make start IS=erm.mm DIFF=1     # dry-run + diff изменяемых файлов
make start-apply IS=erm.mm      # записать (паспорт и CRITICALITY.md — только с FORCE=1)
make start-apply IS=erm.mm FORCE=1
```

**1. Гейт.** Для каждой ИС проверяется структура (`папка`, `INFORMATION.yaml`,
перечисленные компоненты) и полнота входов **для выбранного сценария**. Вердикт
считает та же функция, что и `make check`:

| Сценарий | Метод | Blocking-входы (обязательны) | Advisory (не блокируют) | Статус результата |
|----------|-------|------------------------------|-------------------------|-------------------|
| простой | `express` | `peak_hour_load`, `consumers_type`, `outage_impact`, `object_sla` (4) | — | `preliminary` |
| сложный | `detailed` | те же 4 + `axes_scores` (все 4 оси), `time_to_impact`, `cia` (C, I, A) — все 7 | — | `complete` |

Экспресс-метод считается по алгоритму калькулятора критичности
(`express_method`, `kind: documented`, источник —
[`docs/reference/calculator/`](../docs/reference/calculator/)):

```text
E = коэф. типа клиентов × коэф. характера влияния × клиентов/час
t = порог / E × 60 + SLA        (пороги 100 / 1 000 / 10 000 / 50 000)
балл интервала = матрица[первая подходящая severity][интервал]
уровень = max(балл) → score_to_level → levels.dochub_to_ssot
```

Поэтому в простом сценарии все четыре входа обязательны: без `peak_hour_load`
или `consumers_type` `E = 0`, без `outage_impact` неизвестен коэффициент
влияния, без `object_sla` не сдвигаются времена наступления последствий.
Отсутствие любого из них — `BLOCKED`, а не «примерный» уровень.

Правило выбора сценария (`scenarios.selection.rule`, детерминированное):

1. если **хотя бы один** вход, относящийся только к сложному набору
   (`time_to_impact`, `axes_scores`, `cia`), содержит непустое значение —
   сценарий сложный; при этом неполный сложный набор = `BLOCKED`
   (фолбэк на простой сценарий **не** применяется: ошибка в данных не должна
   превращаться в другой уровень);
2. иначе — простой сценарий; неполный набор из четырёх входов = `BLOCKED`.

Готовность blocking-входа: значение есть **и** `status != missing`. Значение,
помеченное `status: missing`, считается неподтверждённым и блокирует расчёт —
даже если число вписано. Advisory-входы не блокируют, но попадают в WARN
«не заполнено, требуется для полноты паспорта».

`BLOCKED` означает: артефакты **не пишутся**, в отчёт попадает перечень
недостающих входов с `source_hint` из `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml`,
ненулевой код возврата (CLI → 1, `make` → 2).

**2. Расчёт.** Только по правилам из `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml`:
`business_level` — `impact_matrix`, `protection_level` и `V` — CIA,
`final_level` — `final_matrix`. Никаких значений «по памяти».

**3. Расхождения с реестром.** Авторитет значения SSoT — `identity.criticality_ssot`
из `INFORMATION.yaml` (источник SSoT); `catalog.yaml` — вторичен. Фиксируются
два вида конфликтов, оба попадают в `conflicts`, `GENERATION.md` и §1/§7
`CRITICALITY.md` с пометкой «требует подтверждения»:

| Конфликт | Что сравнивается |
|----------|------------------|
| `calculation vs ssot` | расчёт (`levels.dochub_to_ssot`) vs `identity.criticality_ssot` |
| `ssot vs catalog` | `identity.criticality_ssot` vs `catalog.criticality_ssot` |

Дополнительно `criticality` (расчёт) сравнивается с `catalog.criticality`.
Реестр автоматически не перезаписывается: в паспорт идёт расчёт, в
frontmatter `CRITICALITY.md` — значение SSoT.

**4. Что рендерится** (всегда, независимо от флагов):

| Файл | Назначение |
|------|------------|
| `criticality-passport.yaml` | канонический паспорт, 9 полей; `review_date` = `--date` |
| `CRITICALITY.md` | человекочитаемый паспорт, 9 разделов |
| `GENERATION.md` | отчёт: метод, входы с провенансом, промежуточные значения, conventions, недостающее, расхождения, список артефактов |
| `actions/jira-task.md` | как создать задачу в Jira (summary, description, метки, исполнитель) |
| `actions/confluence-page.md` | как создать/обновить страницу оценки (структура, вложения) |
| `actions/rocketchat-message.md` | готовое сообщение в `#Criticality_assessment` + чеклист |

**5. Флаги.**

| Флаг | Смысл |
|------|-------|
| `--is <код>` | только одна ИС (по умолчанию все из `is.yaml`) |
| `--force` | перезаписать существующие `criticality-passport.yaml` и `CRITICALITY.md` |
| `--dry-run` | рендер в память, печать списка файлов и diff, без записи |
| `--diff` | печатать diff изменяемых файлов |
| `--date YYYY-MM-DD` | дата генерации (по умолчанию системная; единственная дата в артефактах) |
| `--create-task` | action-пакет Jira получает статус `requested` (создаёт агент через MCP) |
| `--create-confluence` | то же для страницы Confluence |
| `--create-message` | то же для сообщения в Rocket.Chat |

Флаги `--create-*` **не ходят во внешние системы**: они меняют статус в шапке
action-пакета (`pending_manual` → `requested`) и добавляют в отчёт строку «что
должен выполнить агент через MCP».

**6. Защита.** Без `--force` существующие `criticality-passport.yaml` и
`CRITICALITY.md` не перезаписываются: печатается diff, ненулевой код возврата
(CLI → 1, `make` → 2), файлы не изменены. Action-пакеты и `GENERATION.md` —
производные, перезаписываются всегда. В `--dry-run` защита только
информационная: печатается предупреждение, что для реальной записи нужен
`--force`.

**7. Детерминизм.** При одинаковых входах и одной и той же `--date` результат
побайтово одинаков (проверяется `sha1sum` всех артефактов). В шаблонах нет
других дат, кроме `--date`. Признак переоценки определяется **только
состоянием до генерации** (`catalog.yaml` → `review_date`/`approve_link` либо
`history` в `INFORMATION.yaml`), а не сгенерированным паспортом: иначе второй
`start --force` с той же `--date` менял бы `actions/*`. Ручное управление —
флаг `--reassessment`.

**8. Поведение без данных.** Нет `INFORMATION.yaml` → `BLOCKED`; нет
компонентов → `BLOCKED`; частичный детальный набор → `BLOCKED`; пустая секция
`facts` → в `CRITICALITY.md` явные `⛔ не заполнено` (раздел не пропадает).

### 2.2.1. Сбор данных

`BLOCKED` — это не «спросите людей», а маршрут: `make collect-apply IS=<код>`
рендерит `is/<код ИС>/RESEARCH-PLAN.md` из `templates/RESEARCH-PLAN.md`,
`make links-apply IS=<код>` — `LINK-MAP.md` + `LINK-MAP.yaml` (все ссылки ИС с
классификацией, `expand` и `candidate_for`), а `make sources-apply IS=<код>`
принимает заполненный агентом `SOURCES-FINDINGS.yaml`. План отвечает на четыре
вопроса: какие страницы открыть, что на них искать, какие запросы выполнить и
кто подтверждает значение; карта превращает эти вопросы в конкретные узлы с
идентификаторами и порядком обхода.

| Источник | Что берём | Как фиксируется |
|----------|-----------|-----------------|
| Клоны сервисов (`docs/`, `openspec/`) | назначение, потребители, заявленные нормативы (SLA/SLO/RTO), потоки данных, упоминания ПДн | цитата «файл:строка» в `SERVICE-FINDINGS.md` — **основание**, а не значение |
| Confluence | пользователи продукта, влияние при простое, SLA/RTO, сценарии отказа, ПДн | `source: {type: confluence, ref: '<page_id>, раздел <название>'}`, дословная цитата в `evidence` |
| Grafana | пик RPS шлюза → `peak_hour_load = peak_rps × 3600` | `source: {type: grafana, ref: 'dashboard uid=<uid>, panel <id>, expr: <PromQL>, окно 7d/30d'}` |
| Экспертно | `axes_scores`, `cia`, финансовые потери | `source: {type: manual, ref: '<роль: логин>'}`, `status: confirmed` |

Правила сбора:

1. **Источник — часть значения.** Значение без `source: {type, ref}` в
   `INFORMATION.yaml` не попадает: `enrich` такой лист отклоняет.
2. **Документ не равен оценке.** `axes_scores` и `cia` из страниц и SSoT не
   выводятся: в источниках есть только итоговый уровень.
3. **Формула обязательна для `derived`.** Например `4h × 60 = 240 мин` или
   `20.98 rps × 3600 = 75528`.
4. **Ловушки источников** (ADF-страницы, лимит 30 запросов Confluence, таймаут
   Grafana на 30d, игнорируемый фильтр папки, datasource 404) — в
   [`references/data-sources.md`](../references/data-sources.md)
   и `references/failure-modes.md`; сводка — [12-requirements.md](12-requirements.md) §4.3.

План идемпотентен, исключённые ИС пропускает (`SKIPPED`), а когда незакрытых
входов не осталось — удаляет `RESEARCH-PLAN.md` вместе с листом требований.
Подробно про источники и запреты — [12-requirements.md](12-requirements.md) §4–§9.

### 2.3. Сбор из клонов сервисов (`services`)

`make services-apply IS=<код>` читает клоны `apps/<код ИС>/<сервис>/` и
рендерит `is/<код ИС>/SERVICE-FINDINGS.md` из
`templates/SERVICE-FINDINGS.md`. Это второй (после `RESEARCH-PLAN.md`) артефакт
маршрута сбора: план говорит, **куда** идти, отчёт — **что там написано**.

| Поле | Значение |
|------|----------|
| Вход | `INFORMATION.yaml#components[]` (`name`, `git_repository`, `lifecycle`), клоны `apps/<код ИС>/<сервис>/` |
| Действие | `make services` — план; `make services-apply` — запись; нет клона → `git clone`, есть → `git fetch --prune` + `pull --ff-only`; `NO_CLONE=1` — git не вызывается, отсутствующие клоны идут в §2 |
| Выход | `SERVICE-FINDINGS.md`: §1 сервисы (репозиторий, ветка, `docs/`, `openspec/`, SLO-конфиг), §2 пропущенные по `lifecycle`, §3 назначение и потребители, §4 нормативы, §5 потоки, §6 «вход → основание», §7 «не найдено», §8 ограничение |
| Гейт | каждый компонент с `git_repository` попал в таблицу сервисов, в «не найдено» или в «пропущенные»; ошибка клонирования зафиксирована; ничего не собрано и не запущено |

**Порядок источников:** `docs/`/`openspec/` клона → Confluence → снимок SSoT.
Документация клона — основная по назначению, потребителям и заявленным
нормативам; Confluence нужен, когда в клоне пусто или требуется подтверждение.
Цитата из клона — основание, а не подтверждённое значение: `SERVICE-FINDINGS.md`
не пишет в `INFORMATION.yaml` и не закрывает входы.

**Что искать:** назначение и потребители; нормативы доступности и простоя
(SLO/SLA/RTO/RPO, `objective:`, число рядом со словом «простой»); потоки данных
(Kafka-топики, шедулеры, кроны); упоминания ПДн. Цитата всегда дословная и с
`файл:строка`; пересказ не годится.

**Пропуск закрытых сервисов.** Компоненты с `lifecycle: closed`
(`criteria.service_lifecycle.skip`) не клонируются и не анализируются: в отчёте
они в §2 «Пропущенные сервисы (lifecycle)» с причиной из `skip_reason`, в сводке
печатается `пропущено (lifecycle): N`, в frontmatter — `services_skipped: N`.
Компонент без `lifecycle` анализируется как активный, но помечается
`lifecycle не указан`.

**Запрет сборки и запуска.** Внутри `apps/` разрешён только `git` из
allowlist (`clone`, `pull`, `fetch`, `rev-parse`, `log`, `status`, `show`,
`diff`, `ls-remote`) и чтение файлов. Сборка, тесты, установка
зависимостей и запуск скриптов из клона запрещены — это форсит движок
(`_git_only`) и повторяет §8 отчёта. Найденное в коде не выдаётся за
подтверждённое значение (R12, R14).

### 2.4. Вопросы человеку (`ask`)

`make ask IS=<код>` превращает `BLOCKED` в готовый список вопросов: те же
незакрытые входы, что в листе, но сформулированные так, чтобы человек мог
ответить, а не гадать. План печатается в stdout, `make ask-apply` пишет
`is/<код ИС>/ASK.md`, `make ask IS=<код> JSON=1` — машинная форма (один элемент
на вопрос) для агента.

| Что даёт вопрос | Откуда берётся |
|-----------------|----------------|
| что это и зачем нужно | `inputs.required` критериев (`title`, `role`, `method`) |
| какие значения допустимы | `enum_selection` / `time_buckets` — enum раскрывается **дословно**, всеми значениями |
| что уже найдено и откуда | `is/<код ИС>/CANDIDATES.yaml` (`strong`) → §6 `SERVICE-FINDINGS.md` («из кода», `weak`) → снимок SSoT (`ssot_snapshot.base`, `ssot_snapshot.links`, `weak`) |
| что ответить | варианты: взять кандидата, ввести своё значение, указать ссылку на страницу, ввести произвольный текст, отказаться от данных (`waive`, R17; у advisory — оставить пустым), исключить ИС (`--reason`) |

Кандидат из кода — **основание**, а не значение: если цитата не содержит
значения дословно, вопрос предлагает вписать значение вручную с этим
основанием. `strong` без `source` понижается до `weak` с `WARN` —
неподтверждённое не выдаётся за проверенное.

Ответы человек пишет в `is/<код ИС>/ANSWERS.yaml` (формат —
`templates/ANSWERS.yaml`), принимает их `make ask-answers IS=<код>
ANSWERS=<файл>`. Принятые значения проходят те же валидаторы, что гейт, и
ложатся **только** в `DATA-REQUIREMENTS.yaml`: `INFORMATION.yaml` не меняется ни
на байт — его пишет `make enrich-apply`. Недопустимый ответ — код 1 и причина,
лист не тронут. Протокол опроса — [`references/interactive.md`](../references/interactive.md).

### 2.5. Остановка и дозаполнение

`BLOCKED` — не тупик и не приглашение «поставить примерно»: это запрос данных,
материализованный в файле. Схема:

```text
make check (первичный гейт)
   │        BLOCKED → DATA-REQUIREMENTS.md/.yaml создаются здесь же
   │
   ├─ OK / BLOCKED ─► make collect-apply   RESEARCH-PLAN.md
   │                        │
   │                        ▼
   │                  make links-apply     LINK-MAP.md + LINK-MAP.yaml
   │                        │  карта ссылок: снимок SSoT (links), catalog, компоненты
   │                        ▼
   │                  обход по LINK-MAP.md  MCP Confluence + MCP Grafana
   │                        │  агент → SOURCES-FINDINGS.yaml (findings + not_found)
   │                        ▼
   │                  make sources-apply    INFORMATION.yaml ← criteria_inputs
   │                        │  status: confirmed; статусы узлов found/visited
   │                        ▼
   │                  make check (повторный гейт после приёма источников)
   │                        │
   │                        ▼
   │                  make services-apply  SERVICE-FINDINGS.md
   │                        │  клоны сервисов: docs/, openspec/
   │                        ▼
   │                  make check (определение сценария + гейт)
   │                        │
   │                        ├─ OK ─────────────────────────────► make start
   │                        │
   │                        └─ BLOCKED ─► DATA-REQUIREMENTS.md + .yaml
   │                                       make ask           ASK.md: вопросы, enum дословно
   │                                          ▼
   │                                       (человек: TL / PdM / SRE / ИБ отвечает:
   │                                        value + source + status или ANSWERS.yaml)
   │                                          ▼
   │                                   make ask-answers   ответы → DATA-REQUIREMENTS.yaml
   │                                          ▼
   │                                   make enrich        dry-run: что будет принято
   │                                   make enrich-apply  INFORMATION.yaml ← значения; лист → остаток
   │                                          │
   │                                          └─► make check  (повторять, пока не OK)
   │
   └─ SKIPPED ──► ИС исключена (catalog.yaml или is.yaml → excluded: true):
                   расчёт не выполняется
```

| Вердикт | Что означает | Код возврата `check` | Что делать |
|---------|--------------|----------------------|------------|
| `OK` | все blocking-входы выбранного сценария заполнены и подтверждены, значения допустимы | 0 | `make start` |
| `BLOCKED` | не хватает blocking-входа или значение вне допустимого множества; артефакты не пишутся | 1 (`make` → 2) | заполнить `DATA-REQUIREMENTS.yaml` → `make enrich-apply` → повторить `check` |
| `SKIPPED` | ИС исключена из расчёта: `excluded: true` + `reason` в `catalog.yaml` (версионируемо) или в `is.yaml` (локальное переопределение) | 0 (не считается BLOCKED) | ничего; вернуть в расчёт — `make include IS=<код> [EXCLUDE_SCOPE=catalog]` |
| `CONFLICT` | расхождение SSoT ↔ `catalog.yaml` (`ssot vs catalog`, счётчик в итоговой строке `check`) либо вердикт `start`: сгенерированные `criticality-passport.yaml`/`CRITICALITY.md` отличаются от существующих, а `--force` не задан | 1 (`make` → 2) для `start`; расхождение SSoT ↔ каталог код возврата не меняет | `make start IS=<код> DIFF=1`, затем `make start-apply IS=<код> FORCE=1`; расхождение SSoT ↔ каталог — сверить карточку SSoT и `catalog.yaml` |

Итоговая строка гейта: `Итого: ИС N, OK a, BLOCKED b, SKIPPED c, CONFLICT d.`

**Автогенерация.** `check`, `check-prepare` и `start` для каждой `BLOCKED`
(не исключённой) ИС сами вызывают `requirements --apply` и печатают:

```text
Лист недостающих данных (DATA-REQUIREMENTS.yaml → make enrich-apply):
  - лист требований: is/gi.mm/DATA-REQUIREMENTS.yaml — чего не хватает: 1 blocking, 3 advisory
```

Отключить — `NO_REQUIREMENTS=1` (`--no-requirements`). `start` при `BLOCKED`
по-прежнему **не пишет** артефакты паспорта: он только создаёт лист и
останавливается.

**Состав листа.** Лист содержит только **незакрытые** входы: обязательные входы
выбранного сценария (blocking) плюс detailed-входы (advisory). Так человек видит
полный путь к детальному набору; `blocking n/m` в таблице гейта при этом
показывает только входы выбранного сценария. У `gi.mm` (простой сценарий, 3 из 4
обязательных заполнены) лист содержит 4 записи: 1 blocking + 3 advisory. Рядом
с листом лежит `RESEARCH-PLAN.md` — те же поля, но с маршрутом сбора (страницы,
дашборды, запросы, адресаты).

**Дозаполнение переключает сценарий.** Advisory-вход в простом сценарии — не
безобидная «опция»: заполнение любого detailed-входа (`time_to_impact`,
`axes_scores`, `cia`) переключает ИС на сложный сценарий
(`scenarios.selection.rule`), после чего обязательными становятся все 7 входов.
Если `time_to_impact` при этом нет, гейт даёт `BLOCKED`, а причина называет
переключение. Лист предупреждает об этом в шапке блока `inputs` и помечает такие
входы `switches_scenario: true` / `scenario_note`. Обратный переход — только
удалением значения из `INFORMATION.yaml`, осознанно; фолбэк запрещён.

**Идемпотентность.** `requirements` не использует `now()`: дата листа —
`--date` → `catalog.yaml → review_date/assigned_date` → `history[-1].date` →
`null`. Повторный прогон с теми же данными даёт побайтово те же файлы.

**Когда лист исчезает.** Нет недостающих входов — `DATA-REQUIREMENTS.md` и
`DATA-REQUIREMENTS.yaml` удаляются (в `start` — на OK-прогоне, не в dry-run).
Лист существует только пока есть что дозаполнять.

**Исключение ИС.** Исключение — это решение «ИС не оценивается», и оно
обязано быть воспроизводимым. Хранится в двух местах с разным охватом:

| Где | Команда | Охват | Версионируется |
|-----|---------|-------|----------------|
| `catalog.yaml → systems.<код>` | `make exclude IS=<код> REASON="<причина>" EXCLUDE_SCOPE=catalog` | все, кто работает с репозиторием | да |
| `is.yaml → is.<код>` | `make exclude IS=<код> REASON="<причина>"` (по умолчанию `--scope is`) | только текущая машина | нет |

Приоритет: **`is.yaml` > `catalog.yaml`**. Запись `excluded: false` в `is.yaml`
явно включает ИС обратно, даже если в каталоге стоит `excluded: true` — это
локальное переопределение общего решения.

```yaml
# catalog.yaml
systems:
  - code: ts.mm
    ...
    excluded: true
    reason: "нет владельца данных — решение команды от 2026-11-12"
```

Вердикт печатает источник исключения и причину:
`SKIPPED | нет владельца данных (источник: catalog.yaml)`. `validate`
требует непустой `reason` при `excluded: true` — иначе `ERROR`. Вернуть ИС —
`make include IS=<код> EXCLUDE_SCOPE=catalog` (или без `EXCLUDE_SCOPE` для
локальной записи).


### 2.6. Тред в `#Criticality_assessment` (`handoff`)

`handoff` — финальный этап конвейера и единственная команда, которая **пишет во
внешний чат**. Поэтому она сначала спрашивает, а отправляет только по явному
ответу.

**Вопрос.** Без `--send` в TTY печатается выбор:

```text
Отправить сообщение в #Criticality_assessment автоматически?
  1 — да, отправить (MCP, при отказе — REST API)
  2 — нет, оставить пакет для ручной отправки
  3 — отменить
```

Если stdin не терминал (скрипт, CI), команда **не ждёт ввода**: печатает вопрос
и отказывает с подсказкой `SEND=auto` / `SEND=manual`. Дефолта «на всякий
случай» нет: без явного ответа ничего не отправляется. Выбор пишется в
`catalog.yaml → systems.<код>.handoff_mode: auto|manual`.

**Предусловия** (любое нарушение — код 1, до любой отправки):

1. в тексте нет `⛔ не заполнено` в обязательных полях
   (`_publication_missing_fields`: TA, MR паспорта, ссылка на SSOT); строка
   `не требуется: …` (при `ssot_status: no_change`) — заполненное поле, не дыра;
2. `validate` по этой ИС без ERROR (тот же гейт, что у `publish`/`ssot-plan`);
3. SSoT-MR записан и подтверждён: `.ssot/<код>-MR.url` есть, а
   `ssot_snapshot.verified.matched: true` после `ssot-verify` (либо
   `ssot_status: no_change`). Иначе `ERROR: handoff … заблокирован — SSoT-MR не
   подтверждён` и подсказка `make ssot-verify IS=<код> VERIFY_JSON=-`;
4. сообщение ещё не опубликовано: `thread_link` пуст. Повтор запрещён
   (идемпотентность), `--force-resend` — осознанный обход.

**Два транспорта.**

| Транспорт | Как работает | Когда |
|-----------|--------------|-------|
| `mcp` (основной) | Скрипт не умеет говорить по MCP сам: пишет `is/<код>/.handoff-request.json` (`channel`, `text`, `requested_at`, `deadline`, `timeout_seconds`, `attempt`), печатает `HANDOFF_REQUEST: mcp — …` и завершается с кодом 0, статус `mcp_requested`. Исполнитель отправляет через MCP RocketChat и возвращает результат командой `handoff-result` | `--transport mcp` или `auto` при найденном MCP-сервере Rocket.Chat в конфиге opencode |
| `api` (фолбэк) | `POST {ROCKETCHAT_URL}/api/v1/chat.postMessage` с `X-Auth-Token` и `X-User-Id`; таймаут 15 с, один повтор только на 5xx/таймаут (4xx не повторяется) | `--transport api`, либо `auto` без MCP-сервера, либо MCP признан нерабочим (см. таблицу ниже) |

**Таймаут MCP.** Ожидание ответа ограничено: `--mcp-timeout <сек>` →
`criteria.handoff.mcp_timeout_seconds` → 120 с. Срок пишется в
`.handoff-request.json → deadline` и в `catalog.yaml → handoff_deadline`.
Любая следующая команда `handoff` (и `next_step`, который её советует), увидев
`handoff_status: mcp_requested` с истёкшим сроком, **сама** уходит в REST с
`fallback_reason: mcp_timeout`. Принудительно — `make handoff IS=<код> RESUME=1`
(`--resume`/`--check-mcp`): проверяет срок и выполняет фолбэк, не дожидаясь
следующего запуска.

**Признак сбоя MCP → действие.** MCP-канал считается нерабочим в любом из
случаев ниже; во всех них пишутся `handoff_status`, `handoff_error`,
`fallback_reason`, `transport_used: mcp|api|manual`.

| Признак | Как обнаруживается | `fallback_reason` | Действие |
|---------|--------------------|-------------------|----------|
| MCP-сервера нет в конфиге | `_rocketchat_mcp_server()` → None | `mcp_unavailable` | сразу REST, шаг MCP пропускается |
| Исполнитель вернул `--failed` | `handoff-result --failed "<причина>"` | `mcp_failed` | REST-фолбэк |
| Истёк `deadline` | `handoff_deadline` в `catalog.yaml` / `deadline` в файле запроса | `mcp_timeout` | автоматический REST-фолбэк в `handoff` и по `--resume` |
| Ответ невалиден | URL не парсится, схема не http(s), хост ≠ `rocketchat_base`, нет `/channel/`, нет непустого `msg=` | `mcp_invalid_response` | `thread_link` не пишется, статус `failed`, сразу REST |
| Ошибка формата ответа | `handoff-result` без `--message-url` и без `--failed` | `mcp_format_error` | внятная ошибка + REST-фолбэк |
| Оба флага сразу | `--message-url` и `--failed` вместе | — | отказ (код 2), отправки нет: непонятно, ушло сообщение или нет |

**Дедупликация при фолбэке.** MCP-исполнитель мог отправить сообщение, но не
вернуть ссылку; слепой повтор через REST создал бы дубль в треде. Поэтому перед
POST скрипт ищет своё сообщение:
`GET /api/v1/channels.messages?roomName=<канал>&count=20`, сравнивает первые
80 символов текста (`criteria.handoff.message_match_prefix`) и автора
(`u._id` = `X-User-Id`). Найдено — берётся его `_id` как `thread_link`, повтор
не отправляется. Поиск недоступен — fail-closed: отправки нет, пока не указан
аварийный `--allow-duplicate-risk` (тогда печатается `WARN` о риске дубля).
Если `thread_link` уже `published`, повторная отправка запрещена
(`--force-resend` — осознанный обход).

**Цепочка `auto`:** MCP → REST → ручной пакет. Если MCP-сервера Rocket.Chat в
конфиге нет, шаг MCP пропускается сразу (не нужно ждать `handoff-result`). Если
REST тоже недоступен (нет токена/`X-User-Id`, 401/403/404/429), статус
`failed`, причина — в `handoff_error`, пакет остаётся `pending_manual`, а в
выводе печатается, что именно сделать руками. В отчёте всегда назван
сработавший транспорт: `transport: mcp|api|manual`.

**Результат MCP** — `handoff-result`:

- `--message-url <url>` — ссылка **проверяется**: URL парсится, схема
  `http(s)`, хост совпадает с `criteria.external_refs.rocketchat_base` (или env
  `ROCKETCHAT_URL`), путь содержит `/channel/`, есть непустой `msg=`. Прошла —
  записать `thread_link`, `handoff_status: published`, `published_at`,
  `transport_used: mcp`, удалить `.handoff-request.json`, напечатать следующий
  шаг (`make finalize IS=<код> APPROVE_LINK=<url>`). Не прошла — это
  `mcp_invalid_response`: `thread_link` не пишется, статус `failed`, сразу
  REST-фолбэк (с дедупликацией). Повтор с **другим** URL при уже
  опубликованном `thread_link` — отказ (код 1) без `--force-resend`; тот же
  URL — идемпотентный no-op;
- `--failed <причина>` — автоматический REST-фолбэк (`mcp_failed`); если он
  недоступен — статус `failed`, файл запроса сохраняется, код 1;
- ни `--message-url`, ни `--failed` — ошибка формата ответа
  (`mcp_format_error`): внятное сообщение + REST-фолбэк, а не молчаливый отказ;
- оба флага сразу — код 2, отправки нет (непонятно, ушло сообщение или нет).

**Настройка REST.** Адрес — `ROCKETCHAT_URL` (по умолчанию
`criteria.external_refs.rocketchat_base`), токен — `ROCKETCHAT_TOKEN`, id
пользователя — `ROCKETCHAT_USER_ID`. Порядок проверки **фиксированный**: берётся
первый непустой, переменные разных контуров не смешиваются.

| Что | Порядок (слева направо) |
|-----|-------------------------|
| токен | `ROCKETCHAT_TOKEN` → `RC_TOKEN` → `ROCKER_TOKEN` → `ROCKET_TOKEN` → `STRELKA_TOKEN` → `STRELKA_API_TOKEN` |
| `X-User-Id` | `ROCKETCHAT_USER_ID` → `RC_USER_ID` → `ROCKER_USER_ID` → `ROCKET_USER_ID` → `STRELKA_USER_ID` → `ROCKETCHAT_USER` → `ROCKER_USER` → `ROCKET_USER` → `STRELKA_USER` |
| адрес | `ROCKETCHAT_URL` → `RC_URL` → `ROCKET_BASE_URL` → `ROCKET_URL` → `STRELKA_URL` → `STRELKA_BASE_URL` |

`*_USER` (без `_ID`) — нестандартные имена контура, принимаются последними:
значение там — **id** (17 символов, совпадает с `user._id` из `GET /api/v1/me`),
а не логин (`name@domain` для `X-User-Id` не годится). Если id не задан,
сообщение об ошибке перечисляет все поддерживаемые имена и подсказывает, что id
берётся из `GET /api/v1/me` → `_id` (или из UI-профиля Rocket.Chat). Токен не
печатается, не логируется и не пишется в файлы; `--dry-run` показывает только
**имя** переменной-источника, не значение.

**Ошибки REST различаются:** `401` — токен истёк/неверен, `403` — нет прав на
канал, `404` — канал не найден, `429` — rate limit, таймаут — сеть. Успех —
ссылка `{base}/channel/<канал из criteria.handoff.channel>?msg=<message._id>`.

**`--dry-run`** печатает канал, транспорт, длину текста и его начало/конец,
ничего не отправляя и не меняя `catalog.yaml` (файл запроса тоже не создаётся).

**`approve_link` = ссылка на тред согласования.** `handoff` после успешной
публикации пишет `thread_link` и сразу `approve_link` тем же значением;
`finalize` без `--approve-link` берёт `thread_link` по умолчанию (флаг —
только явный override). Отдельного ожидания ответа SRE нет: подтверждение
фиксируется **мержем MR** — без аппрува MR не смержится. Нет ни флага, ни
треда — `ERROR: сначала отправьте тред: make handoff IS=<код> SEND=auto`.

**Даты — от даты генерации.** `assigned_date` = `generated_at` (параметр
`--date` генерации паспорта), `review_date` = `generated_at` +
`review_period_months`. Поэтому паспорт в MR уже содержит обе даты, а
повторный `finalize` идёт идемпотентно и не сдвигает их.


## 3. Раскладка папок

```text
.
├── catalog.yaml                # реестр ИС: код, путь, критичность, page_id (коммитится)
├── INDEX.md                    # сводная таблица паспортов, генерируется make index
├── INFORMATION.md              # спецификация подготовки данных и генерации
├── README.md                   # точка входа: обзор, быстрый старт, карта документации
├── Makefile                    # фасад: цели в .opencode/Makefile
├── is.yaml                     # вход: список ИС + ssot.url (gitignored)
├── is.example.yaml             # шаблон is.yaml (в репозитории)
├── .gitignore                  # создаётся make init: apps/, dochub/, .dochub/, бэкапы
├── apps/                       # клоны компонентов ИС (gitignored; prepare-apply / services-apply)
│   └── <код ИС>/<сервис>/      # только чтение: сборка и запуск запрещены
├── .opencode/                  # инструмент: переносится целиком, данные не содержит
│   ├── Makefile                # цели: init/prepare/check/start/…/skill-*
│   ├── commands/
│   │   └── criticality_gen.md  # контракт подкоманд /criticality_gen
│   └── skills/criticality-gen/
│       ├── SKILL.md            # точка входа скилла
│       ├── install.sh          # установка в другой проект
│       ├── references/         # workflow, data-sources, rules, artifacts, dependencies, failure-modes, checklist
│       ├── scripts/
│       │   └── criticality.py  # CLI: init/prepare/validate/index/due/scaffold/reassess/show/score/check/requirements/collect/links/sources/services/enrich/start/publish/ssot-import/ssot-plan/ssot-record/ssot-verify
│       ├── criteria/
│       │   └── criticality-criteria.yaml
│       └── templates/
│           ├── INFORMATION.yaml        # скелет INFORMATION.yaml (ручные секции)
│           ├── criticality-passport.yaml
│           ├── CRITICALITY.md
│           ├── GENERATION.md
│           ├── DATA-REQUIREMENTS.md    # лист требований: что/зачем/где/у кого
│           ├── DATA-REQUIREMENTS.yaml  # машиночитаемый лист для заполнения
│           ├── RESEARCH-PLAN.md        # план сбора: Confluence, Grafana, адресаты
│           ├── SERVICE-FINDINGS.md     # код сервисов: docs/, openspec/, «вход → основание»
│           ├── publication.md
│           ├── actions/
│           │   ├── jira-task.md
│           │   ├── confluence-page.md
│           │   └── rocketchat-message.md
│           └── skill/          # шаблоны скиллов для других предметных областей
├── docs/                       # документация процесса, полей, скриптов, шаблонов
└── is/
    └── <код ИС>/              # например is/erm.mm/, is/cc-exchanger.smkt/
        ├── README.md           # make scaffold: ссылки на Confluence и GitLab ИС
        ├── INFORMATION.yaml    # снимок карточки ИС (ssot_snapshot) + ручные входы критериев и facts
        ├── criticality-passport.yaml
        ├── CRITICALITY.md
        ├── GENERATION.md       # после первого успешного make start
        ├── DATA-REQUIREMENTS.md    # пока гейт BLOCKED: что заполнить и где взять
        ├── DATA-REQUIREMENTS.yaml  # лист для заполнения; удаляется, когда входов не осталось
        ├── RESEARCH-PLAN.md        # план сбора данных; удаляется вместе с листом
        ├── SERVICE-FINDINGS.md     # что даёт код сервисов: docs/, openspec/, «вход → основание»
        ├── actions/            # после первого успешного make start
        │   ├── jira-task.md
        │   ├── confluence-page.md
        │   └── rocketchat-message.md
        └── reassessment-YYYY-MM-DD.md   # после make reassess
```

### 3.0. Что версионируется, а что нет

| Путь | В git | Почему |
|------|-------|--------|
| `is/<код ИС>/INFORMATION.yaml` | **да, коммитится** | ручной слой данных с провенансом (`criteria_inputs`, `facts`, `conflicts`, `notes`); потеря файла = потеря данных |
| `is/<код ИС>/` (остальное) | да | паспорт, `CRITICALITY.md`, `GENERATION.md`, action-пакеты, `DATA-REQUIREMENTS.*` — артефакты оценки |
| `.ssot/` | да | локальные артефакты этапа SSoT: план, ссылка на MR, описание MR, результат проверки (`ssot-plan`/`ssot-record`/`ssot-verify`) |
| `apps/` | нет (gitignored) | клоны компонентов ИС, воспроизводятся `prepare --apply` / `services --apply`; только чтение |
| `is.yaml` | нет (gitignored) | локальный конфиг (список ИС + `ssot.url`); шаблон — `is.example.yaml` |

`INFORMATION.yaml` — единственный источник ручных входов расчёта. Он не
регенерируется из SSoT: `prepare` переносит ручные секции дословно. Поэтому
файл обязан быть в git. `make validate` и `make check` печатают
`WARN`, если файл существует, но не отслеживается git (проверка мягкая:
если git недоступен — молча пропускается).

### 3.0.1. `apps/` — только чтение

`apps/<код ИС>/<сервис>/` — клоны репозиториев компонентов. Они нужны как
**документация**: `docs/`, `openspec/`, конфиги SLO. Правила жёсткие:

| Что | Правило |
|-----|---------|
| Разрешено | `git clone` / `git fetch --prune` / `git pull --ff-only` / `git rev-parse` / `git log` / `git status` / `git show` / `git diff` / `git ls-remote` и чтение файлов; `checkout`/`reset`/`clean` отклоняются allowlist'ом |
| Запрещено | установка зависимостей, сборка, тесты, `docker`, запуск скриптов и сервисов из клона |
| Почему | чужой репозиторий в неизвестном состоянии; прогон менял бы окружение и делал результат невоспроизводимым (R12) |
| Кто форсит | движок (`_git_only`) и §8 отчёта `SERVICE-FINDINGS.md` |
| Закрытые сервисы | компоненты с `lifecycle: closed` не клонируются вовсе (`criteria.service_lifecycle.skip`) |

Найденное в коде — основание для входа, а не подтверждённое значение: значение
по-прежнему принимает человек через `enrich` (R14).

### 3.1. Правило `<код ИС> → is/<код ИС>/`

Код ИС — это `<name_is>.<контур>` (например `erm.mm`). Каноническая раскладка —
**плоская**: папка называется ровно так же, как код ИС.

```text
erm.mm            → is/erm.mm/
cc-exchanger.smkt → is/cc-exchanger.smkt/
```

Код разбирается по **последней** точке: `erm.mm` → `name_is = erm`,
`контур = mm`; контур нужен для `id`, `evaluated_object`, актива и GitLab-ссылки,
но на путь папки не влияет. Канонический путь совпадает с `catalog.yaml` → `path`,
с проверками `make validate` и со спецификацией `is/<код ИС>/` в
`INFORMATION.md` в корне проекта.

### 3.2. Legacy-фолбэк `is/<контур>/<name_is>/`

Историческая раскладка — `is/<контур>/<name_is>/` (то есть `is/mm/erm/`) —
**legacy-фолбэк**. Её видят не все команды (полный список — §3.3): если
канонической папки `is/<код ИС>/` нет, но существует legacy-папка, `prepare`
использует её и печатает

```text
WARN: erm.mm: используется legacy-раскладка is/mm/erm/ (каноническая: is/<код ИС>)
```

Если ни канонической, ни legacy-папки нет — создаётся каноническая `is/<код ИС>/`.
Новые ИС заводятся только в канонической раскладке: `make scaffold CONTOUR=<контур> NAME=<name_is>`
и `make prepare-apply` создают именно её. Перенос legacy-папки в каноническую
раскладку — единственный способ включить ИС во все проверки.

### 3.3. Legacy-раскладка: поддержка по командам

| Команда | Поддерживает `is/<контур>/<name_is>/` | Как ведёт себя |
|---------|---------------------------------------|----------------|
| `prepare` | **да** | `is_layout`: если канонической папки нет, а legacy-папка существует — использует её и печатает WARN (см. §3.2) |
| `score --is` | **да** | `is_layout`: ищет `INFORMATION.yaml` в каноне `is/<код ИС>/`, иначе в legacy-папке (WARN не печатает) |
| `check` | **да** | `is_folder`: `catalog.yaml` → `path`, иначе `is_layout` → legacy с `WARN` |
| `start` | **да** | `is_folder`: `catalog.yaml` → `path`, иначе `is_layout` → legacy с `WARN` |
| `requirements` | **да** | `_requirements_paths` → `is_folder`: каталог, иначе legacy-папка (WARN не печатает) |
| `enrich` | **да** | тот же `_requirements_paths` → `is_folder`; лист и `INFORMATION.yaml` берутся из legacy-папки (WARN не печатает) |
| `reassess` | **да** | `is_folder`: каталог, иначе legacy с `WARN`; файл пишется в найденную папку |
| `show` | нет | путь паспорта берётся только из `catalog.yaml` → `path`; при отсутствии файла — WARN «показываю данные реестра» |
| `validate` | нет | сканирует `is/*/criticality-passport.yaml` (канон); legacy-папка даёт WARN «legacy-раскладка `is/<контур>/<name_is>/` не поддержана validate/index/due» (не ERROR) |
| `index` | нет | путь берётся из `catalog.yaml` → `path` |
| `due` | нет | путь берётся из `catalog.yaml` → `path` |

Практический вывод: legacy-раскладку видят `prepare`, `score`, `check`, `start`,
`requirements`, `enrich` и `reassess` — они находят папку через `is_folder` или
`is_layout` (канон `is/<код ИС>/`, иначе legacy). Не видят `show`, `validate`,
`index` и `due`: они работают по `catalog.yaml` → `path` и по паспортам в
канонической раскладке, поэтому ИС из legacy-папки выпадает из `validate`,
`index` и `due`. Перенос в каноническую раскладку — единственный способ включить
её во все проверки.

## 4. `INFORMATION.yaml`: что внутри

Файл — единственный слой данных между SSoT и паспортом. Снимок карточки ИС пишет
`ssot-import`, автоматические секции собирает `prepare`, вручную файл
**дополняется**; больше ниоткуда паспорт числа не берёт.

| Секция | Кто пишет | Что содержит |
|--------|-----------|--------------|
| `schema_version` | prepare | версия схемы (сейчас `1`) |
| `is` | prepare | код ИС |
| `meta` | prepare | `generated_by`, `layout`, `sources` (провенанс), `ssot_url`, `missing_sources`, `unreadable_sources` |
| `identity` | prepare | код, название, контур, актив, тип, статус, `lifecycle`, продукт и команда с пометкой источника (`ssot`/`override`), критичность SSoT (`severity.type`), arch code из `catalog.yaml`; у каждого значения — провенанс (см. §4.3) |
| `components` | prepare | список компонентов: `name`, `description`, `language`, `status`, `git_repository`, `cloned_to`, `clone_status` |
| `resources` | prepare | размещение ИС в инфраструктуре (из `resources.yaml`) |
| `duties` | prepare | дежурные (из `duty.yaml`) |
| `links` | prepare | навигационные ссылки (из `links.yaml`) |
| `roles` | prepare | ролевая модель (из `roles.yaml`) |
| `ssot_snapshot` | `ssot-import` | снимок карточки ИС из ответа MCP `ssot_get`: `base` (в нём `severity`), `components`, `duty`, `links`, `resources`, `roles`, `source: mcp`, `commit`, `version`, `imported_at`, `verified {matched, ref, commit, actual, checked_at}` |
| `ssot_status` | `ssot-plan` / `ssot-record` / `ssot-verify` | статус этапа SSoT: `no_change` (severity уже совпадает), `mr_pending` (план есть, MR ещё не создан), `mr_created` (`mrUrl` записан `ssot-record`), `mr_verified` / `mr_unverified` (по `ssot-verify`) |
| `ssot_mr_url`, `ssot_version`, `ssot_can_apply`, `ssot_recorded_at` | `ssot-record` | факты созданного MR: ссылка и версия из `ssot_form_save`, признак `canApply`, метка записи |
| `criteria_inputs` | **руками** | значения входов критериев + `source` + `status` |
| `facts` | **руками** | обогащение паспорта: `impact_chain`, `e2e_processes`, `dependencies` (upstream/downstream), `data_classification`, `risks`, `support`, `adr`, `decision_log` |
| `conflicts` | **руками** | зафиксированные расхождения `{ field, values, chosen, rule, status }` |
| `notes` | **руками** | заметки по ИС |

Правила:

1. **Автоматические секции авторитетны.** `identity` берётся из снимка SSoT; если
   значение в SSoT неверное — правьте карточку в SSoT (MCP-форма:
   `ssot_entity_open` → `ssot_form_save`), а не `INFORMATION.yaml`. Ручная
   правка автоматической секции будет затёрта следующим `prepare-apply`.
2. **Ручные секции неприкосновенны.** `criteria_inputs`, `facts`, `conflicts`, `notes`
   переживают любой `prepare-apply`: `prepare` читает существующий файл и
   переносит их в новый документ как есть.
3. **Ничего не выдумывается.** Любое число или факт без источника остаётся
   `null`, а `status` — `missing`. Нет данных — нет значения, а не «примерно
   столько».

### 4.1. Статусы входов критериев

| `status` | Значение | Поведение гейта (`check`/`start`) |
|----------|----------|-----------------------------------|
| `missing` | значения нет **или оно не подтверждено** | blocking-вход считается отсутствующим → `BLOCKED` (даже если `value` вписано) |
| `derived` | значение выведено из другого поля/источника | засчитывается, но печатается предупреждение «нужно подтверждение» |
| `confirmed` | значение подтверждено владельцем (PdM/TL/SRE) | засчитывается без предупреждений |

`check` берёт список входов не из кода, а из
`.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` → `inputs.required`, вместе с полями
`method` (`detailed`/`express`/`both`) и `blocking` (`true`/`false`), а наборы
входов сценариев — из `scenarios.simple` / `scenarios.complex`.
Добавили критерий в файл — гейт сразу его учитывает; `blocking: false` делает
вход advisory (WARN, но не блокировка).

### 4.1.1. Провенанс `gitlab`: документация клонов

Тип `gitlab` в провенансе описывает репозиторий сервиса. Первичный источник
значений для него — не GitLab-веб, а клон: `apps/<код ИС>/<сервис>/docs/` и
`openspec/`, `ref` = `<сервис>/<файл>:<строка>`. Ссылка на репозиторий нужна
лишь для воспроизводимости; подробнее — [05-mapping.md](05-mapping.md) §8.0.

### 4.2. Провенанс

Любая ссылка на источник записывается объектом `{ type, ref }`:

| `type` | Что означает | Пример `ref` |
|--------|--------------|--------------|
| `ssot` | файл карточки ИС в снимке SSoT | `entities/information-systems/erm.mm/base.yaml#severity.type` |
| `is_yaml_override` | переопределение из локального `is.yaml` | `is.yaml#is.erm.mm` |
| `catalog` | поле реестра этого репозитория | `catalog.yaml#systems.erm.mm` |
| `confluence` | страница Confluence: `page_id` и раздел | `https://space.samokat.ru/pages/viewpage.action?pageId=3925149771` |
| `gitlab` | репозиторий, файл с номером строки или MR | `https://git.ecom.tech/ecom/dev/is/mm/erm` |
| `jira` | задача | `E001-1234` |
| `grafana` | дашборд, панель, точный запрос | `dashboard uid=ermmm_20250813_2, panel 64, expr: sum(rate(...[5m]))` |
| `attachment` | вложение Confluence (таблица, выгрузка, калькулятор) | `docs/reference/calculator/калькулятор критичности упрощенный.xlsx` |
| `ssot_links` | ссылка из карточки ИС в снимке SSoT (`links.yaml`) | `entities/information-systems/erm.mm/links.yaml` |
| `manual` | ручное значение, подтверждённое человеком | `manual` + `status: confirmed` |

Порядок и состав списка — канон [4567212024](https://space.samokat.ru/pages/viewpage.action?pageId=4567212024);
`criteria.provenance.types` и `PROVENANCE_TYPES` в скрипте обязаны совпадать с
ним и по составу, и по порядку. `type` вне этого списка — ошибка провенанса:
значение без источника в паспорт не попадает. Решение владельца без дословной
цитаты — это `manual` с ref на само решение (`provenance.manual_decision`);
без ссылки на решение — `missing`, а не `manual`.

**Решение владельца — не догадка.** Если дословной цитаты в источнике нет, а
владелец (PdM) решение принял, значение пишется как `source: {type: manual, ref:
'решение PdM, <YYYY-MM-DD>; INFORMATION.yaml#notes'}` со `status: confirmed`, а само
решение (кто, когда, что решил, почему) — в `INFORMATION.yaml#notes`. Новый тип
провенанса для этого не вводится. Правило зафиксировано в
`criteria/criticality-criteria.yaml → provenance.manual_decision` и в R1
(`references/rules.md`). Пересказ источника, «по аналогии с другой ИС» и
«обычно так» решением владельца не являются — это R1-нарушение.

### 4.3. Маппинг снимка SSoT → `INFORMATION.yaml`

Автоматические секции собираются детерминированно: одно и то же поле снимка
SSoT (`INFORMATION.yaml → ssot_snapshot`) всегда попадает в одно и то же поле
`INFORMATION.yaml`, а провенанс записывается рядом (`{ type, ref }` или
`*_source`).

| Поле `INFORMATION.yaml` | Источник в снимке SSoT | Провенанс |
|-------------------------|---------------|-----------|
| `identity.name` | `base.yaml → title` | `name_source: {type: ssot, ref: "…/base.yaml#title"}` |
| `identity.product` | `base.yaml → other.product` (или `is.yaml → is.<код>.product`) | `product_source: {type: ssot\|is_yaml_override, ref: "…/base.yaml#other.product" \| "is.yaml#is.<код>.product"}` |
| `identity.team` | `base.yaml → teamName` (или `is.yaml → is.<код>.teamName`) | `team_source: {type: ssot\|is_yaml_override, ref: "…/base.yaml#teamName" \| "is.yaml#is.<код>.teamName"}` |
| `identity.criticality_ssot` | `base.yaml → severity.type` через `ssot_severity_normalization` | `criticality_source: {type: ssot, ref: "…/base.yaml#severity.type"}` |
| `identity.lifecycle` | `base.yaml → lifecycle` (это **не** `status` паспорта) | `lifecycle_source: {type: ssot, ref: "…/base.yaml#lifecycle"}` |
| `identity.asset` | `catalog.yaml → systems.<код>.asset` | `asset_source: {type: catalog, ref: "catalog.yaml#systems.<код>.asset"}` |
| `identity.type` | `base.yaml → other.type` (если есть; иначе `null`) | `type_source: {type: ssot, ref: "…/base.yaml#other.type"}` |
| `identity.arch_code` | `catalog.yaml → systems.<код>.arch_code` | `arch_code_source: {type: catalog, ref: "catalog.yaml#systems.<код>"}` |
| `components[].language` | `components.yaml → programmingLanguage` | `language_source: {type: ssot, ref: "…/components.yaml#<name>.programmingLanguage"}` |
| `components[].status` | `components.yaml → lifecycle` | `status_source: {type: ssot, ref: "…/components.yaml#<name>.lifecycle"}` |
| `resources` | `resources.yaml → sites / k8sClusters / netboxRoles / infraResources` | `source: {type: ssot, ref: "…/resources.yaml#<ключ>"}` у каждой записи |
| `duties` | `duty.yaml → onCallSchedule` | `source: {type: ssot, ref: "…/duty.yaml#onCallSchedule"}` у каждой записи |
| `links` | `links.yaml → links` | `meta.sources` |
| `roles` | `roles.yaml → roles` | `meta.sources` |

Нормализации (детерминированные, без «примерных» значений):

| Что | Правило | Почему |
|-----|---------|--------|
| Код продукта | `e001` → `E001` | В `catalog.yaml` и паспорте код продукта пишется заглавными |
| Код команды | `t100` → `T100` | То же для `team` |
| `severity.type` | kebab-case → Title Case по карте `ssot_severity_normalization` из `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` | В SSoT уровни в kebab-case, в паспорте — Title Case. Значение вне карты → `identity.criticality_ssot: null` + `WARN «неизвестный severity.type: <x>»` (не угадывается) |
| `duties[].startTime` | строка `HH:MM` (секунды отбрасываются) | Время нельзя превращать в секунды: YAML 1.1 читает `10:00:00` как `36000`. Значение пишется в кавычках |
| `duties[].duration` | строка (`P1D`) | ISO-8601 duration — не число |
| `resources` | плоский список `{name, value, type, environment, source, status}`; `environment` в SSoT нет → `null`; неизвестная структура сохраняется в `raw` | Ничего не теряется, форма единая для рендера |

### 4.4. Что принципиально требует человека

Автоматика заполняет **только** то, что есть в SSoT. Всё, что требует суждения,
остаётся `null` / `missing` и блокирует расчёт — это не недоработка, а
требование методики (нет источника — нет значения).

| Что | Где | Кто заполняет | Почему нельзя взять из SSoT |
|-----|-----|---------------|-----------------------------|
| `criteria_inputs.peak_hour_load` | `INFORMATION.yaml` | TL (пик RPS в Grafana: папка E001, панели трафика) | В SSoT нет нагрузки; формула `peak_rps × 3600` |
| `criteria_inputs.consumers_type` | `INFORMATION.yaml` | PdM (страница ИС в Confluence, «Пользователи продукта») | В SSoT нет типа клиентов |
| `criteria_inputs.outage_impact` | `INFORMATION.yaml` | PdM + TL (DR-страница ИС) | В SSoT нет характера влияния при простое |
| `criteria_inputs.object_sla` | `INFORMATION.yaml` | SRE (Support-страница: SLA решения; DR-страница: RTO) | В SSoT нет SLA/RTO/RPO |
| `criteria_inputs.axes_scores` | `INFORMATION.yaml` | TL + ИБ + финансы | Оценки 0–4 по осям — экспертное суждение |
| `criteria_inputs.time_to_impact` | `INFORMATION.yaml` | SRE + TL (DR-сценарии: кеш, репликация) | В SSoT нет сценариев простоя |
| `criteria_inputs.cia` | `INFORMATION.yaml` | ИБ | C/I/A — классификация ИБ, не атрибут SSoT |
| `facts.impact_chain` | `INFORMATION.yaml` | TL + PdM | Цепочка «что ломается → кто замечает» — экспертное знание |
| `facts.e2e_processes` | `INFORMATION.yaml` | PdM | Перечень E2E-процессов в SSoT не ведётся |
| `facts.data_classification` (риск потери/утечки данных) | `INFORMATION.yaml` | TL + ИБ | ПДн / КТ / SORM — классификация ИБ |
| `facts.risks` | `INFORMATION.yaml` | TL | Реестр рисков — не атрибут карточки ИС |
| `facts.adr` | `INFORMATION.yaml` | TL / архитектор | Ссылки на ADR в SSoT не хранятся |

Два поля выводятся из SSoT частично и требуют подтверждения:

- **`facts.support.hours`** — выводится из `duty.yaml → onCallSchedule`
  (график дежурств), но это расписание on-call, а не SLA поддержки; статус
  остаётся `derived`, пока SRE не подтвердит.
- **`facts.decision_log`** — `page_id` Decision Log берётся из
  `catalog.yaml → decision_log_page_id`; **содержимое** страницы автоматика не
  читает — оно доступно только через Confluence (MCP), поэтому решения
  переносятся человеком/агентом.

## 5. Поведение при отсутствии данных

| Ситуация | Поведение |
|----------|-----------|
| Нет `is.yaml` | `ERROR: нет is.yaml — выполните make init`, код возврата 1 |
| Нет снимка SSoT (`ssot_snapshot` пуст) | `ERROR: prepare: нет данных SSoT — данные ИС не обновлены; импортируйте снимок: criticality.py ssot-import --is <код> --entity-json -`, код 1; `INFORMATION.yaml` не изменяется (dry-run печатает то же, файлы не пишутся) |
| Снимок SSoT не импортирован у одной ИС | в отчёте `ERROR (нет в SSoT)`, `0/6` секций; файл этой ИС не обновляется, остальные обрабатываются; снимок приносит MCP `ssot_get` → `make ssot-import` |
| Кода ИС нет в снимке | `ERROR: нет данных SSoT — ИС <код> не импортирована`, код 1: пустой скелет маскировал бы опечатку в коде |
| Нет части секций снимка SSoT | не падение: отсутствующие refs пишутся в `meta.missing_sources`, счётчик в отчёте показывает `n/6` |
| Секция снимка не разобрана | `WARN <ref>: <ошибка>` в консоль и в итоговую таблицу (счётчик `unreadable`), ref и текст ошибки — в `meta.unreadable_sources`; прогон продолжается |
| Нет `catalog.yaml` | `WARN`; `arch_code` остаётся `null` |
| Компонент без `gitRepository` | `clone_status: not_cloned`, `cloned_to` заполнен, ошибки нет |
| Каталог компонента занят не-git-папкой | `clone_status: error` + запись в отчёте, прогон не прерывается |
| Компонент с `lifecycle: closed` | не клонируется: `skip (lifecycle: closed)` в выводе `prepare`/`services`, в `SERVICE-FINDINGS.md` §2 — таблица пропущенных, в сводке `пропущено (lifecycle): N` |
| Сервис не клонируется (`services`) | прогон продолжается: `clone_error` в отчёте, остальные сервисы анализируются; `SERVICE-FINDINGS.md` всё равно пишется. При `--no-clone` git не вызывается, отсутствующие клоны — `WARN` + §2 «Не склонировано (`--no-clone`)» |
| В клоне нет `docs/` или `openspec/` | это факт, а не ошибка: §7 «Не найдено» отчёта, дальше Confluence |
| Нет blocking-входа выбранного сценария | `make check` → `BLOCKED` и ненулевой код (CLI → 1, make → 2); создаются `DATA-REQUIREMENTS.md`/`.yaml`; `make start` → `BLOCKED`, артефакты не пишутся |
| Неполный сложный сценарий | `BLOCKED` без фолбэка на простой: перечень недостающих входов сложного набора |
| Нет `RESEARCH-PLAN.md` при `BLOCKED` | `make collect-apply IS=<код>` создаёт план; ИС без папки и `SKIPPED` план не получают |
| Нет `LINK-MAP.yaml` при `links` в снимке SSoT | `make links-apply IS=<код>` создаёт карту; расхождение с существующей картой без `--force` — `CONFLICT` и код 1, файлы не меняются |
| Нет `SOURCES-FINDINGS.yaml` для `make sources` | `ERROR: нет SOURCES-FINDINGS.yaml — сначала выполните обход по LINK-MAP.md`, код 1; файлы не меняются |
| Факт в `SOURCES-FINDINGS.yaml` отклонён | `sources` печатает причину (вход не из `criteria.inputs.required`, значение вне множества, `source.type` вне провенанса, пустой `evidence`, `node` не из карты), код 1; принятые факты при `--apply` записываются |
| Нет `SERVICE-FINDINGS.md` | `make services-apply IS=<код>` создаёт отчёт; ИС без папки и `SKIPPED` отчёт не получают |
| `DATA-REQUIREMENTS.yaml` заполнен без `source` или без `status: confirmed` | `make enrich` → `ERROR` списком, код 1, `INFORMATION.yaml` не меняется |
| `DATA-REQUIREMENTS.yaml` содержит значение вне допустимого множества | `make enrich` → `ERROR` с ожидаемым набором (те же валидаторы, что у гейта), файл не меняется |
| Нет `DATA-REQUIREMENTS.yaml` для `make enrich` | `ERROR: нет … — сначала выполните make requirements IS=<код>`, код 1 |
| ИС исключена (`catalog.yaml` или `is.yaml` → `excluded: true`) | `check`/`start`/`score --is`/`requirements` → `SKIPPED` с причиной и источником; `--strict` из-за неё не падает; артефакты не трогаются |
| Значение входа вне допустимого множества | `make check` → `BLOCKED` с точной причиной и ожидаемым набором; `make start` → тот же вердикт, без трейсбека |
| Advisory-вход не заполнен | `WARN «не заполнено, требуется для полноты паспорта»`; вердикт не меняется |
| `INFORMATION.yaml` битый YAML | `prepare` печатает `ERROR` и **не перезаписывает файл** (ручные секции сохраняются); перезапись — только `--force-overwrite`, код возврата 1 |
| `INFORMATION.yaml` существует, но не в git | `make check`/`make validate` печатают `WARN: не отслеживается git — данные могут быть потеряны`; git недоступен — проверка молча пропускается |

## 6. Соответствие `INFORMATION.md`

| Пункт `INFORMATION.md` | Реализация |
|------------------------|------------|
| 1. Снимок карточки ИС из SSoT | `make ssot-import IS=<код> ENTITY_JSON=-`: ответ MCP `ssot_get` → `INFORMATION.yaml → ssot_snapshot`; клон и сеть не нужны; повторный импорт тех же данных — no-op |
| 2. Создать структуру `is/<код ИС>/` по списку из `is:` | `prepare --apply` создаёт `is/<код ИС>/` — каноническая раскладка (совпадает со спецификацией `is/<код ИС>/`); `is/<контур>/<name_is>/` поддержана как legacy с WARN (см. §3.2) |
| 3. В каждой папке ИС — `INFORMATION.yaml` со всеми данными из SSoT и переопределениями | `prepare --apply` собирает `INFORMATION.yaml` из снимка (`ssot_snapshot`: шесть секций); `product`/`teamName` из `is.yaml` переопределяют снимок и помечаются `*_source: override`. Неразобранный файл не перезаписывается (`--force-overwrite`) |
| 4. `apps/<код ИС>/<component_name>` — клоны компонентов из `components.yaml` | `prepare --apply` клонирует по полю `gitRepository` в `apps/<код ИС>/<component_name>`; существующий репозиторий обновляется `fetch --prune` + `pull --ff-only`; компонент с `lifecycle: closed` пропускается (`skip (lifecycle: closed)`) |
| 5. Проверка достаточности данных для расчёта | `make check` — единая функция `evaluate_gate`: читает `inputs.required` (с `method`/`blocking`), `status` и **значения** входов, выбирает метод |
| 6. Если хотя бы один критерий недоступен — последующие команды возвращают ошибку | `check` strict по умолчанию → `BLOCKED` и код 1 (make → 2); `--diagnostic` — только для отладки (код 0); `score --is` → `incomplete` + код 1; `start` → `BLOCKED` и артефакты не пишутся |
| `/criticality_gen init` создаёт `is.yaml` из `is.example.yaml` | `make init` (не перезаписывает существующий; `FORCE=1` — перезапись) |
| `/criticality_gen check` стартует подготовку данных | `make check-prepare` = `prepare --apply` + гейт (с `--no-clone` при `NO_CLONE=1`). `make check` — только гейт (read-only), `make check-diag` — гейт в диагностическом режиме |
| `/criticality_gen start` рендерит файлы в папке ИС `is/<код ИС>/` | `make start` (dry-run) / `make start-apply` (запись): паспорт, `CRITICALITY.md`, `GENERATION.md`, action-пакеты — в `is/<код ИС>/` (см. `INFORMATION.md` §«Артефакты») |
| Флаги `--create-task`, `--create-confluence`, `--create-message` | Внешние системы по умолчанию не трогаются: готовятся action-пакеты для ручного выполнения. Флаг меняет статус пакета на `requested` и попадает в отчёт как «выполнить агенту через MCP» |
| SSoT: снимок карточки ИС (`ssot_get`) → `ssot_snapshot.{base,components,duty,links,resources,roles}` | Прочитаны все шесть секций снимка; отсутствующие фиксируются в `meta.missing_sources` |
| SSoT: `products/<product>/{base,links}.yaml`, `teams/<team>/team.yaml`, `schemas/` | Пока не читаются: продукт и команда берутся из `base.yaml` ИС и переопределений `is.yaml`. Подключение — при необходимости обогащения паспорта |
| Команды вызываются как `/criticality_gen ...` | В репозитории — `python3 .opencode/skills/criticality-gen/scripts/criticality.py <команда>` и цели `make`; скилл-обёртка — отдельный слой |

### 6.1. Прочие расхождения

1. **Раскладка.** Спецификация (`is/<код ИС>/`) и репозиторий совпадают: канон —
   плоская `is/<код ИС>/` (6 существующих паспортов, `catalog.yaml` → `path`,
   `make validate`). Историческая форма `is/<контур>/<name_is>/` работает как
   legacy-фолбэк в `prepare`, `score`, `check`, `start`, `requirements`,
   `enrich` и `reassess`; `show`/`validate`/`index`/`due` её не видят (см. §3.3).
2. **Порядок шагов.** В `INFORMATION.md` подготовка данных инициируется
   командой `check`; здесь это делает `check --prepare` / `make check-prepare`
   (подготовка + гейт). `make check` по умолчанию остаётся read-only гейтом,
   чтобы диагностика не ходила в сеть и не писала файлы; `make check-diag` —
   тот же гейт с кодом 0 при `BLOCKED`.
3. **Переопределения.** Поддерживаются ровно два ключа — `product` и
   `teamName`. Любой другой ключ в `is.yaml` → `ERROR` (чтобы опечатка не
   терялась молча).
4. **`ssot_snapshot`.** `INFORMATION.md` не описывает хранение исходных данных;
   здесь снимок карточки ИС (ответ MCP `ssot_get`) сохраняется в
   `INFORMATION.yaml → ssot_snapshot` дословно, чтобы любое поле паспорта можно
   было проследить до источника.

## 7. Типовой сценарий

Порядок шагов, гейты и команды — один источник:
[`references/workflow.md`](../references/workflow.md)
(фазы 0–10 и боковые этапы). Здесь не дублируется.

Что специфично для подготовки данных:

- `make init` создаёт каркас (`is.yaml`, `catalog.yaml`, `INDEX.md`, `is/`) и
  `.gitignore` с записями `/apps/`, `/dochub/`, `/.dochub/` и бэкапами: клоны не
  попадают в `git add -A` (существующий `.gitignore` только дополняется);
  список ИС и `ssot.url` заполняются в `is.yaml`.
- `make ssot-import` пишет снимок карточки ИС (ответ MCP `ssot_get`) в
  `INFORMATION.yaml → ssot_snapshot`; `make prepare-apply` пишет только
  автоматические секции, ручные (`criteria_inputs`, `facts`, `conflicts`,
  `notes`) переносятся дословно.
- `is/<код ИС>/INFORMATION.yaml` — версионируемый ручной слой: он коммитится в
  git; `apps/`, `is.yaml` — нет.

## 8. Связанные документы

- `INFORMATION.md` (корень проекта) — исходное описание процесса.
- [07-scripts.md](07-scripts.md) — CLI reference.
- [08-criteria.md](08-criteria.md) — правила расчёта и `inputs.required`.
- [05-mapping.md](05-mapping.md) — идентификаторы и приоритет источников.
- [04-reassessment.md](04-reassessment.md) — runbook переоценки.
- [12-requirements.md](12-requirements.md) — лист недостающих данных, источники значений, процедуры сбора и `enrich`.
- [`references/data-sources.md`](../references/data-sources.md) — карта источников, формулы, статусы, ловушки.

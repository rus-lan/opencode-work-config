---
name: criticality-gen
title: criticality-gen — оценка и переоценка критичности ИС
version: 1.1.0
description: |
  Генерация и переоценка паспортов критичности ИС по процессу D6.1.1 — из is.yaml
  через SSoT-репозиторий (INFORMATION.yaml) и детерминированный расчёт по
  criteria/criticality-criteria.yaml. Артефакты рендерятся только по шаблонам и
  только из фактов: нет данных — блокировка, а не догадка.
  Используйте когда нужно: оценить критичность ИС, переоценить критичность,
  сгенерировать criticality-passport.yaml / CRITICALITY.md, подготовить данные
  по ИС из SSoT, проверить достаточность данных для оценки, получить лист
  недостающих данных (DATA-REQUIREMENTS), собрать значения из Confluence и
  Grafana по плану (RESEARCH-PLAN) и карте обхода ссылок (LINK-MAP), принять
  найденные факты (SOURCES-FINDINGS), прочитать документацию клонов сервисов
  (docs/ и openspec/ → SERVICE-FINDINGS), вписать подтверждённые значения,
  обогатить SSoT критичностью (`severity`) и подготовить MR по шаблону,
  исключить ИС из расчёта, обновить INDEX.md или найти просроченные переоценки.
user-invocable: true
compatibility: opencode
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
purpose: Вести ИС по конвейеру оценки критичности — от is.yaml до артефактов и передачи человеку.
audience: [ai-agent]
read_when: [запрос на оценку или переоценку ИС, установка скилла, разбор BLOCKED]
updated: 2026-11-19
status: actual
related: [references/workflow.md, references/commands.md, references/rules.md, references/search.md]
---

# criticality-gen

Скилл ведёт одну ИС по конвейеру оценки критичности. Канон фаз, гейтов и
порядок шагов — один: **[references/workflow.md](references/workflow.md)**
(`init → prepare → contacts → check → collect → сбор → services → check → enrich
→ score → start → validate → publish → ssot → handoff`; боковые этапы `due`,
`reassess`, `exclude`, `scaffold` — там же). Этот файл последовательность не
дублирует.

Порядок — инвариант (R18): **исследование → критерии → расчёт → валидация ВСЕХ
результатов → внешние изменения (MR в dochub, затем SSoT) → тред**. `publish` и
`ssot` (с `--apply` и без) отказывают, пока `validate` даёт ERROR, фингерпринт
критериев не совпадает или blocking-входы не закрыты; обход — только `FORCE=1`
с записью в `is/<код>/.gate-overrides.log`. Action-пакет сообщения не
переводится в `requested`, пока в отрендеренном тексте есть `⛔ не заполнено`.

Нет данных — конвейер не идёт дальше: `check`/`start` сами пишут
`DATA-REQUIREMENTS.md` и `.yaml` с формой «что это → зачем → где взять →
у кого → как подтвердить», `collect` пишет `RESEARCH-PLAN.md` — какие страницы
Confluence открыть, какие дашборды и запросы Grafana выполнить, где искать
E2E-процессы ИС (Product scope продукта) и какие запросы tier 2 выполнить по
каждому незакрытому входу, кто подтверждает, а `services` — `SERVICE-FINDINGS.md`
с цитатами из документации клонов сервисов (`docs/`, `openspec/`). Человек
возвращает заполненный лист через `enrich`, и только после `OK` гейта выполняется
`start`.

Поиск идёт в два прохода: tier 1 — точные идентификаторы, tier 2 — комбинации
значений; «не найдено» доказывается списком выполненных запросов в
`CANDIDATES.yaml → search.<вход>`, а не молчанием —
[references/search.md](references/search.md).

Скилл — тонкая обёртка: **вся логика в `scripts/criticality.py`**, правила
расчёта — в `criteria/criticality-criteria.yaml`, тексты артефактов — в
`templates/`. Скилл выбирает команду, читает результат и объясняет человеку,
чего не хватает. Он не считает критичность сам.

## Установка

Глобально (скилл + команда `/criticality_gen`): `./install.sh` из клона или
`curl … | sh` — см. [README.md](README.md). В проект целиком:
`./install.sh --project <каталог>` — кладёт скилл в `.opencode/skills/`, команду
в `.opencode/commands/`, `Makefile`, `.opencode/Makefile` и `is.example.yaml` в
корень; дальше `cd <каталог> && make init`. Проверить, что будет сделано, —
`./install.sh --dry-run` (в обоих режимах).

## Пути

Инструмент и данные разделены, поэтому в этом скилле действуют два правила:

- **Относительные пути внутри скилла — от каталога скилла** (base directory).
  Каталог скилла скрипт определяет сам: `SKILL_DIR` =
  `Path(__file__).absolute().parent.parent`, то есть родитель `scripts/`.
  Раскладка установки на `SKILL_DIR` не влияет — работают все три:
  - глобальная установка: `~/.config/opencode/skills/criticality-gen/`;
  - проектная установка: `<проект>/.opencode/skills/criticality-gen/`;
  - запуск из клона репозитория: `skills/criticality-gen/`.

  Внутри скилла от `SKILL_DIR` берутся `scripts/criticality.py`,
  `criteria/criticality-criteria.yaml`, `templates/`, `references/`, `docs/`.
  Это файлы инструмента; они переезжают вместе со скиллом и не зависят от
  того, в какой проект он установлен.
- **Пути данных — от корня проекта**: `is/<код ИС>/INFORMATION.yaml`,
  `catalog.yaml`, `INDEX.md`, `is.yaml`, `docs/`. Корень определяется
  автоматически: `--root <path>` → env `CRITICALITY_ROOT` → подъём от cwd до
  первого каталога с `catalog.yaml`/`is.example.yaml`/`.git` → подъём от
  каталога скилла. Если корень не найден — ошибка с требованием `--root`.

Запуск, в зависимости от раскладки:

- в проекте с установленным `.opencode/Makefile` — `make <цель>` (корневой
  `Makefile` — фасад на `.opencode/Makefile`);
- глобальная установка (в проекте нет `.opencode/Makefile`) —
  `python3 ~/.config/opencode/skills/criticality-gen/scripts/criticality.py --root . <команда>`;
- из клона репозитория —
  `python3 skills/criticality-gen/scripts/criticality.py --root <проект> <команда>`.

Шаблон `is.example.yaml` в скилле один — `templates/is.example.yaml` (пустой
каркас). `install.sh --project` копирует его в корень проекта: проектный
`is.example.yaml` приоритетнее шаблона при `make init`, поэтому копия обязана
совпадать с шаблоном, а не содержать список ИС конкретного продукта.

## Команды

Полный справочник — синтаксис, все флаги, коды возврата:
[references/commands.md](references/commands.md). Список подкоманд и описания
берутся из `build_parser()` и `COMMAND_DESCRIPTIONS`, поэтому `make help`
показывает ровно их.

Частые цели: `make init`, `make prepare`, `make contacts`, `make check`,
`make requirements`, `make collect-apply`, `make services-apply`,
`make research`, `make ask`, `make ask-answers`, `make enrich-apply`,
`make score`, `make start-apply`, `make validate`, `make verify-titles`,
`make verify`, `make finalize`, `make ssot` / `make ssot-apply`, `make publish` /
`make publish-apply`, `make index`, `make due`.

`make finalize IS=<код>` — финализация: одной командой проставляет
`approve_link`, `assigned_date`, `review_date`, `criticality`,
`criticality_ssot`, `status: confirmed` и прогоняет `start-apply FORCE=1` →
`validate` → `index` → `verify`; `ERROR` в `validate` — откат записанных
полей.

- `approve_link` — **ссылка на тред согласования**. `handoff` после успешной
  публикации пишет `thread_link` и сразу `approve_link` тем же значением;
  `finalize` без `--approve-link` берёт `thread_link` только при
  `handoff_status: published` (флаг — явный override). Подтверждение
  фиксируется **мержем MR** — отдельного ожидания ответа SRE нет. При
  `failed` — `ERROR` с причиной из `handoff_error`; при `mcp_requested`/пустом
  статусе — `ERROR`; в обоих случаях подсказка `make handoff IS=<код>
  SEND=auto` или явный `--approve-link`.
- `assigned_date` = дата генерации паспорта (`generated_at`), `review_date` =
  она же + `review_period_months`. Источники по порядку: явный флаг → реестр →
  паспорт → `generated_at` → `today()` (последний — только если
  `generated_at` нет, с WARN). Даты не зависят от момента `finalize`, поэтому
  паспорт в MR уже содержит их, а повторный `finalize` идемпотентен.

`make contacts IS=<код>` собирает контакты команды-владельца (TA/TL и остальные
роли) из `ssot/entities/teams/<team>/team.yaml` в `INFORMATION.yaml → contacts`
(`APPLY=1` — запись, `JSON=1` — машинная форма). Без этого в публикации не будет
упоминаний: в тексте стоит `@<полный username>` (`@dkozlov@ecom.tech`).
Короткий логин в `mentions[]` RocketChat не попадает, поэтому `start` резолвит
`login → users.info → username` и кеширует результат в
`catalog.yaml → rocketchat_users`; не удалось резолвить — остаётся `@<login>`
и WARN в `GENERATION.md`/`validate`. Логин с доменом (`rrozhkov@ecom.tech`)
используется как есть.

**Подсказка следующего шага.** После каждой команды (кроме `help`, `info`,
`score --express`) скрипт печатает конкретную следующую команду с причиной —
`Следующий шаг: make enrich-apply IS=gi.mm — не хватает 1 обязательного входа:
object_sla`. Для `check` / `validate` / `index` — сводка по всем ИС; если все
готовы — `Все этапы пройдены`. Логика одна (`next_step()`), она же заполняет
колонку «следующий шаг» в `help`; отключается `--no-next` / `--quiet`.
Подробнее — [references/workflow.md](references/workflow.md).

**Навигация по критериям.** `make info` (или `info --section <имя>`) печатает
шкалы, матрицы, enum'ы и входы дословно из файла критериев — без хардкода в
скрипте. `info --json` даёт те же данные структурой для машинного чтения.

**Итог и пороги — из критериев.** Итоговая критичность берётся из ячейки
`final_matrix.cells[бизнес-уровень][уровень защищённости]`; правило
`max(бизнес, ИБ)` не применяется (в трёх ячейках строки `Office productivity`
матрица ниже максимума). Границы CIA для артефактов рендерятся из
`cia.thresholds`, уровни и маппинг SSoT — из `levels`. Списков уровней и
порогов в коде и шаблонах нет: правка критериев меняет и расчёт, и артефакты.

**Ошибки.** Одна строка `ERROR: <человеческий текст>` и код `1`, без traceback;
ошибки разбора YAML — с `<файл>:<строка>:<колонка>`. Traceback печатается только
с `--debug` (глобальный флаг, работает и после подкоманды).

Вердикты гейта: `OK` / `BLOCKED` / `SKIPPED` / `CONFLICT`. `SKIPPED` — ИС
исключена (`excluded: true` + `reason`), не считается `BLOCKED`; `CONFLICT` —
расхождение SSoT ↔ `catalog.yaml` (`ssot vs catalog`, в `check`) либо отличие
сгенерированных файлов от существующих без `--force` (в `start`).

## Восемь инвариантов

1. **Факт-или-null.** Любое значение без источника `{type, ref}` — это `null`
   со `status: missing`. Слов «примерно», «обычно», «скорее всего» в артефактах
   не бывает: [references/rules.md](references/rules.md) R1.
2. **Шаблон-или-ничего.** Артефакт создаётся только рендером файла из
   `templates/`. Ручная правка сгенерированного запрещена — правка идёт в
   `INFORMATION.yaml`, затем повторный `start`: R2.
3. **Гейт-или-блокировка.** `check` (strict по умолчанию) обязателен до `start`.
   Сценарий выбирается по данным: непустой любой вход только сложного набора →
   `сложный`, иначе `простой`; неполный сложный набор — `BLOCKED` без фолбэка на
   простой сценарий. Нет любого **blocking**-входа сценария или значение вне
   допустимого множества — стоп с перечнем «чего нет / где взять»: R3, R10.
   Входы вне blocking-набора сценария расчёт не блокируют — только `WARN`.
   Заполнение detailed-входа переключает сценарий: лист требований предупреждает
   об этом (`switches_scenario`), после переключения нужен `time_to_impact`.
   Исключение — осознанный отказ от данных (`status: waived`, R17): вход
   считается закрытым, но расчёт помечается предварительным (диапазон), а не
   выдаётся за подтверждённое значение.
4. **Нет данных → файл требований, а не догадка.** При `BLOCKED` создаётся
   `DATA-REQUIREMENTS.md`/`.yaml` с адресатами и способом подтверждения,
   `collect` — `RESEARCH-PLAN.md` с маршрутом сбора (страницы Confluence,
   дашборды и запросы Grafana, Product scope продукта для E2E-процессов ИС,
   запросы tier 2 по каждому входу), `services` — `SERVICE-FINDINGS.md` с
   цитатами из `docs/` и `openspec/`. Порядок: `collect` → сбор по плану (SSoT,
   Confluence, Grafana) в два прохода ([search.md](references/search.md)) →
   `services` → `check` → `enrich`. Лист без `source: {type, ref}` и `status: confirmed` команда
   `enrich` отклоняет, и `INFORMATION.yaml` не меняется. Данных нет совсем →
   `excluded: true` + `reason` (в `catalog.yaml` для общего решения, в `is.yaml`
   — локально), а не выдуманное значение: R11. Осознанный отказ от данных —
   третий законный исход: `status: waived` + `waive {reason, decided_by, date,
   fallback}` закрывает вход, но оценка становится предварительной — диапазон
   уровней в `CRITICALITY.md`/`GENERATION.md`/публикации и пометка `(предв.)` в
   `INDEX.md`, паспорт берёт консервативный уровень по режиму допущения: R17.
   `check` не затирает заполненный
   лист: значения сливаются (`value`, `source`, `status`), вычисляемые поля
   пересчитываются; `NO_REQUIREMENTS=1` — прогон без касания листа. Лист
   производен от `INFORMATION.yaml`: закрытое поле (значение +
   `status: confirmed`/`derived`/`legacy`) в него не попадает.
5. **Клоны только читаются.** В `apps/` разрешён единственный процесс — `git`
   из allowlist (`clone` / `pull` / `fetch` / `rev-parse` / `log` / `status` /
   `show` / `diff` / `ls-remote`); `checkout`/`reset`/`clean` отклоняются до
   запуска процесса. Все вызовы git идут через один хелпер `_run_git`
   (allowlist-валидация `_git_only`), прямых `subprocess` с git нет — проверяет
   `make selftest`. Схема `git_repository` проверяется до git-вызова: только
   `https://`, `ssh://`, `git@host:path`; иначе ошибка, код 1. Сборка, тесты,
   установка зависимостей и запуск кода сервиса запрещены; цитата из кода —
   основание, а не подтверждённое значение: R12, R14. Офлайн/read-only —
   `--no-clone` (`NO_CLONE=1`).
6. **Закрытые сервисы не анализируются.** Сервис с `lifecycle: closed`
   (`criteria.service_lifecycle.skip`) выведен из эксплуатации: он не
   клонируется, не анализируется, не служит основанием для входов и не попадает
   в план `collect`. Пропущенные перечислены в разделе «Пропущенные сервисы»
   отчёта и строкой `<имя>: пропущен (lifecycle: closed)`: R15.
7. **SSoT обогащается точечно и по шаблону.** `ssot` — единственный этап,
   который пишет в клон SSoT, и только блок `severity` файла
   `entities/information-systems/<код>/base.yaml`: `type` — из
   `levels.ssot_enum` критериев, `confirmation` — из `approve_link` реестра.
   Остальные ключи, их порядок, комментарии и форматирование сохраняются
   побайтово; расхождений нет — `изменений нет`, ветка и коммит не создаются.
   Запись идёт веткой `feature/<task>` и MR строго по шаблону
   `templates/MR-ssot.md`: незаполненная переменная шаблона — ошибка, а не
   пустая строка в MR. `--push` допустим только вместе с `--apply` и только по
   подтверждению человека.
8. **Язык — только русский.** Все артефакты, вопросы пользователю, сообщения CLI
   и тексты ошибок — на русском. Скилл ожидает ответы пользователя только на
   русском: ответ на другом языке не принимается как значение входа. Значения
   enum берутся дословно из `criteria/criticality-criteria.yaml` (они русские);
   свободный текст (`source.ref`, `notes`, `reason`, `conflicts`) — тоже на
   русском. Латиница допустима только там, где это идентификатор, а не проза:
   логины, URL, page_id, uid дашбордов, PromQL, ключи Jira/MR, имена файлов и
   сервисов, значения enum из внешних систем (`business-critical` в SSoT): R16.

## Ссылки

| Файл | Содержимое |
|------|------------|
| [references/workflow.md](references/workflow.md) | канон флоу: фазы 0–10 (включая 2c `services`, 8 `publish`, 9 `ssot`, 10 `handoff`) и боковые этапы, вход/команда/выход/гейт |
| [references/interactive.md](references/interactive.md) | интерактивный слой `ask`: когда спрашивать, как превратить `--json` в вопросы, язык ответов, приём ответов, разобранный пример |
| [references/commands.md](references/commands.md) | синтаксис и все флаги подкоманд, коды возврата |
| [references/data-sources.md](references/data-sources.md) | карта источников (код сервиса / Confluence / Grafana / эксперт), процедуры сбора, формулы, статусы, запреты и ловушки |
| [references/search.md](references/search.md) | протокол поиска: tier 1 (точные идентификаторы) → tier 2 (комбинации), фиксация в `CANDIDATES.yaml → search`, доказательство «не найдено», «симптом → следующий запрос» |
| [references/rules.md](references/rules.md) | правила R1–R19 с проверкой и реакцией на нарушение |
| [references/artifacts.md](references/artifacts.md) | реестр артефактов, шаблоны, политика перезаписи |
| [references/dependencies.md](references/dependencies.md) | python3, git, ssh к SSoT, MCP; что делать, если нет |
| [references/failure-modes.md](references/failure-modes.md) | симптом → причина → действие → как чинить |
| [references/checklist.md](references/checklist.md) | приёмочный чеклист до/во время/перед сдачей/после |

## Быстрый старт

```bash
make init                                  # 1. каркас: is.yaml, catalog.yaml, INDEX.md, is/, .gitignore
make check-prepare NO_CLONE=1              # 2. подготовка данных (INFORMATION.yaml) + гейт
make contacts IS=erm.mm APPLY=1            # 2b. контакты TA/TL из SSoT team.yaml → contacts
make check-diag                            #    только гейт в диагностическом режиме (код 0)
make start IS=erm.mm DIFF=1                # 3. dry-run: показать, что будет сгенерировано
```

Запись артефактов и проверка — следующие два шага, после просмотра diff:

```bash
make start-apply IS=erm.mm FORCE=1         # записать паспорт и action-пакеты
make validate                              # проверить: 0 ERROR
make publish IS=erm.mm TASK=E001-31245     # план публикации паспорта в dochub: файл, ключ, ветка, MR
make publish-apply IS=erm.mm TASK=E001-31245  # ветка и коммит в клоне dochub (без push)
make ssot IS=erm.mm TASK=E001-31245        # план обогащения SSoT: severity + confirmation, MR со ссылкой на dochub-MR
make ssot-apply IS=erm.mm TASK=E001-31245  # ветка feature/<task> и коммит в клоне SSoT (без push)
make handoff IS=erm.mm DRY_RUN=1           # предпросмотр: канал, транспорт, текст; ничего не отправлено
make handoff IS=erm.mm SEND=auto           # тред в #Criticality_assessment: MCP, при отказе — REST API
make handoff IS=erm.mm SEND=manual         # не отправлять: пакет остаётся pending_manual
make handoff-result IS=erm.mm MESSAGE_URL=<ссылка на сообщение>  # результат MCP → thread_link
```

Если `check` вернул `BLOCKED` (strict по умолчанию → ненулевой код), не
запускайте `start`. Гейт уже создал лист требований — передайте его адресатам:

```bash
make requirements IS=erm.mm                # что именно нужно: план, без записи
make collect-apply IS=erm.mm               # RESEARCH-PLAN.md: страницы, дашборды, запросы
make links-apply IS=erm.mm                 # LINK-MAP.md/.yaml: карта обхода ссылок
# обход по LINK-MAP.md через MCP (Confluence/Grafana) → SOURCES-FINDINGS.yaml
make sources-apply IS=erm.mm               # принять факты → criteria_inputs (status: confirmed | derived)
make services IS=erm.mm                    # план: клоны сервисов, docs/, openspec/, нормативы
make services-apply IS=erm.mm              # SERVICE-FINDINGS.md: цитаты «файл:строка»
make research IS=erm.mm                    # Confluence: RESEARCH.md + CANDIDATES.yaml (кандидаты direct)
make ask IS=erm.mm                         # план вопросов: кандидаты с провенансом, enum дословно
make ask IS=erm.mm JSON=1                  # то же машинной формой: один вопрос = один элемент
make ask-answers IS=erm.mm ANSWERS=is/erm.mm/ANSWERS.yaml  # принять ответы в лист
make enrich IS=erm.mm                      # проверить заполненный лист (без записи)
make enrich-apply IS=erm.mm                # вписать подтверждённые значения
make check                                 # повторить гейт
```

`is/erm.mm/DATA-REQUIREMENTS.md` — человеческая форма «что/зачем/где/у кого/как
подтвердить»; `DATA-REQUIREMENTS.yaml` — тот же лист для заполнения. Без
`source: {type, ref}` и `status: confirmed` значение не принимается.
Если данных нет и взять их негде — ИС исключается, а не заполняется догадкой:
`make exclude IS=erm.mm REASON="..."` (обратно — `make include IS=erm.mm`).
`INFORMATION.yaml` — версионируемый слой ручных данных: он **коммитится в git**;
`ssot/`, `apps/`, `is.yaml` — нет.

## Чего скилл НЕ делает

- **Не выдумывает числа.** Нет `peak_hour_load`, `object_sla`, `axes_scores`,
  `cia` — значит `null` и `status: missing`, а не оценка «на глаз». Оценки осей
  и CIA из документов не выводятся: это экспертное решение.
- **Не собирает значения за человека.** `collect` строит план сбора, но не
  ходит в Confluence и Grafana и не вписывает найденное в лист. `services` читает
  клоны и цитирует документацию, но значение по-прежнему подтверждает человек.
- **Не собирает и не запускает код сервисов.** В `apps/` разрешён только `git`:
  ни сборки, ни тестов, ни установки зависимостей, ни запуска скриптов из клона
  (R12). Клон — источник документации, а не способ «проверить, что работает».
- **Не заполняет лист требований за человека.** `enrich` только проверяет и
  переносит уже подтверждённые значения; придумать `source` он не может.
- **Не мержит MR** в dochub и не пушит в SSoT: это шаг `handoff`, его делает человек.
- **Не публикует в тред без подтверждения.** `handoff` — последний этап конвейера:
  он собирает финальное сообщение из текущего состояния (паспорт, `catalog.yaml`,
  `.publish`/`.ssot`, `INFORMATION.yaml` → `facts`/`notes`), печатает его ЦЕЛИКОМ и
  отправляет только по явному согласию (`--send auto`; MCP, при отказе — REST),
  всегда ОДНИМ сообщением: разбивать текст на части запрещено, сокращать надо
  источник. `handoff-apply` с `CONFIRM=1` — тонкая обёртка того же пути только по
  REST (идемпотентность и дедупликация общие). Текст с `⛔` не публикуется без
  `--allow-incomplete`; без кредов `ROCKETCHAT_TOKEN`/`ROCKETCHAT_USER_ID`
  (алиасы `RC_*`, `STRELKA_*`) команда падает, ничего не отправив.
- **Не правит SSoT сверх `severity`.** `ssot` пишет только `severity.type` и
  `severity.confirmation` в `base.yaml` (по флагу `--apply`, в ветку
  `feature/<task>`) и ничего не пушит без `--push` и подтверждения человека.
  Остальные поля SSoT меняет человек через свой MR.
- **Не отправляет сообщения без явного ответа.** `handoff` сначала спрашивает
  («отправить автоматически?»); без `--send` вне TTY отказывает, а `SEND=manual`
  оставляет пакет `pending_manual`. Транспорты: MCP (основной — запрос в
  `.handoff-request.json`, результат через `handoff-result`) и REST
  `chat.postMessage` (фолбэк, токен из env). Оба отказали — отправляет человек
  по `actions/rocketchat-message.md`, ссылка возвращается `handoff-result`.
- **Не разрешает расхождения молча.** Конфликт SSoT ↔ расчёт фиксируется в
  `conflicts` и в `GENERATION.md`, оба значения остаются в артефакте.
- **Не обходит гейт.** «Почти полный набор» — это `BLOCKED`, а не `preliminary`.

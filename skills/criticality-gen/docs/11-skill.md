---
title: Скилл criticality-gen
purpose: Описать слои скилла, два корня (инструмент в .opencode/ и данные проекта), установку в другой проект и шаблоны скиллов для других предметных областей.
audience: [ai-agent, human]
read_when: [ставите или обновляете скилл, выносите инструмент в другой проект, делаете скилл для другой области, скилл не виден в opencode]
updated: 2026-11-24
status: actual
related: [../SKILL.md, ../commands/criticality_gen.md, 10-templates.md, 09-pipeline.md]
---

# Скилл `criticality-gen`

## Когда читать

- Читать, когда устанавливаете, обновляете или удаляете скилл.
- Читать, когда переносите инструмент в другой проект или во внешний репозиторий.
- Читать, когда скилл не виден в opencode или читает не тот корень.
- Читать, когда делаете скилл для другой предметной области по шаблонам `.opencode/skills/criticality-gen/meta-templates/`.

## Кратко

- Инструмент целиком живёт в каталоге скилла (`skills/criticality-gen/` в репозитории инструмента, `.opencode/skills/criticality-gen/` после установки в проект): движок, критерии, шаблоны, справочники. Данные проекта — в корне (`is/`, `catalog.yaml`, `INDEX.md`, `docs/`).
- Скилл — тонкая обёртка над `scripts/criticality.py`: выбирает команду, читает результат, объясняет нехватку данных.
- Четыре слоя: скилл (LLM) → скрипт → критерии → шаблоны; смешение слоёв запрещено.
- opencode подхватывает project-level скилл и команду из `.opencode/` автоматически; при глобальной установке — из `~/.config/opencode/`.
- Скилл не содержит чисел, формул и текстов артефактов.
- Клоны сервисов (`apps/`) читаются только `git`: сборка, тесты и запуск запрещены, закрытые сервисы (`lifecycle: closed`) не анализируются.
- Проверка структуры — `make skill-check`, корни — `make paths`.

`INFORMATION.md` требует двух вещей: команды `/criticality_gen` и скилла,
который ищет и клонирует репозитории, собирает данные и проводит оценку
критичности.

## 1. Слои

Четыре слоя, у каждого одна ответственность. Смешение слоёв — главная причина
расхождений между паспортом и методикой.

| Слой | Файл | Отвечает за | Кто меняет |
|------|------|-------------|------------|
| Скилл (LLM) | `.opencode/skills/criticality-gen/SKILL.md` + `references/` | выбор команды, объяснение результата, остановка при нехватке данных | разработчик скилла |
| Скрипт | `.opencode/skills/criticality-gen/scripts/criticality.py` | детерминизм: парсинг снимка SSoT, гейт, расчёт, рендер | разработчик инструмента |
| Критерии | `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` | правила расчёта: матрицы, enum, `inputs.required`, `kind` | владелец методики (MR) |
| Шаблоны | `.opencode/skills/criticality-gen/templates/*` | тексты артефактов и action-пакетов | разработчик инструмента |

Скилл не содержит ни чисел, ни формул, ни текстов артефактов. Если для ответа
нужно правило — оно берётся из критериев, если текст — из шаблона.

## 2. Структура и два корня

```text
.opencode/                                  # инструмент — переносится целиком
├── Makefile                                # все цели: init/prepare/check/start/…/skill-*
├── commands/
│   └── criticality_gen.md                  # opencode-команда /criticality_gen
└── skills/criticality-gen/
    ├── SKILL.md                            # frontmatter + обзор, команды, пути, восемь инвариантов
    ├── install.sh                          # установка: глобально (~/.config/opencode) или --project <каталог>
    ├── references/                         # 8 файлов: workflow, rules, commands, artifacts, dependencies, failure-modes, checklist, data-sources
    ├── scripts/
    │   └── criticality.py                  # движок: детерминированный расчёт и рендер
    ├── criteria/
    │   └── criticality-criteria.yaml       # единственный источник правил расчёта
    └── templates/                          # тексты артефактов + actions/ (3 сообщения)
```

**Три раскладки одного набора файлов.** В репозитории инструмента скилл лежит
в `skills/criticality-gen/`; после `install.sh --project <каталог>` — в
`<каталог>/.opencode/skills/criticality-gen/`; после глобальной установки — в
`~/.config/opencode/skills/criticality-gen/`. Внутри скилла все относительные
пути считаются от каталога скилла (`SKILL_DIR`), поэтому одна и та же копия
работает во всех трёх. Пути `.opencode/skills/...` в этом документе — проектная
раскладка, а не требование к репозиторию.

Корень проекта (данные) — то, где лежат `is/`, `catalog.yaml`, `INDEX.md`,
`is.yaml`, `docs/`; корневой `Makefile` — фасад на `.opencode/Makefile`.

Скрипт держит два независимых корня:

| Корень | Что это | Как определяется |
|--------|---------|------------------|
| `SKILL_DIR` | каталог скилла: `scripts/`, `criteria/`, `templates/` | `Path(__file__).parent.parent` (не резолвит симлинк) |
| `PROJECT_ROOT` | корень проекта: `is/`, `catalog.yaml`, `INDEX.md`, `docs/` | `--root` → env `CRITICALITY_ROOT` → подъём от cwd до `catalog.yaml`/`is.example.yaml`/`.git` → подъём от `SKILL_DIR` |

Поэтому из любого cwd внутри проекта `make <цель>` и прямой вызов скрипта
работают без флагов, а шаблоны и критерии находятся и после переноса
`.opencode/` в другой репозиторий. Правило для текстов скилла: относительные
пути инструмента (`scripts/…`, `criteria/…`, `templates/…`) — от каталога
скилла, пути данных (`is/…`, `catalog.yaml`, `INDEX.md`) — от корня проекта.

## 3. Фаза → references → команда

| Фаза | Где описана | Команда |
|------|-------------|---------|
| навигация | `SKILL.md` § «Команды», `07-scripts.md` §1.2–1.4 | `make help` (справка + состояние), `make info [SECTION=...] [JSON=1]` (критерии с пояснениями) |
| 0 `init` | `references/workflow.md` § «Фаза 0» | `make init` |
| 1 `prepare` | `references/workflow.md` § «Фаза 1» | `make prepare` / `make prepare-apply` |
| 2 `collect` → сбор → `services` → `check` → `enrich` | `references/workflow.md` § «Фаза 2» (2a–2d), `references/data-sources.md`, `rules.md` R1/R4/R11/R12/R14/R15 | `make requirements IS=<код>` + `make collect-apply IS=<код>` → сбор (SSoT/Confluence/Grafana) + `make services-apply IS=<код>` → `make check` → `make enrich-apply IS=<код>` |
| 3 `check` | `references/workflow.md` § «Фаза 3», `rules.md` R3 | `make check` (гейт) / `make check-prepare` (подготовка + гейт) |
| 4 `score` | `references/workflow.md` § «Фаза 4», `rules.md` R5 | `python3 .opencode/skills/criticality-gen/scripts/criticality.py score --is <код>` |
| 5 `start` | `references/workflow.md` § «Фаза 5», `rules.md` R2/R7/R8 | `make start IS=<код> DIFF=1` → `make start-apply IS=<код> FORCE=1` |
| 6 `actions` | `references/workflow.md` § «Фаза 6», `rules.md` R9 | `make start-apply ... TASK=1 CONFLUENCE=1 MESSAGE=1` |
| 7 `verify` | `references/workflow.md` § «Фаза 7», `references/checklist.md` | `make validate`, `make docs-check`, `make criteria-check`, `make selftest` |
| 8 `publish` | `references/workflow.md` § «Фаза 8», `references/commands.md` § «publish» | `make publish IS=<код> TASK=<key>` → `make publish-apply IS=<код> TASK=<key>` |
| 9 `ssot` | `references/workflow.md` § «Фаза 9», `references/checklist.md` | `make ssot-import IS=<код> ENTITY_JSON=<файл\|->` → `make ssot-plan IS=<код>` → MCP-форма → `make ssot-record IS=<код> MR_URL=<mrUrl>` → `make ssot-verify IS=<код> VERIFY_JSON=<файл\|->` |
| 10 `handoff` | `references/workflow.md` § «Фаза 10», `references/checklist.md` | вручную: тред в `#Criticality_assessment` со ссылками на dochub-MR и SSoT-MR, подтверждение SRE; апрув и применение MR — `ssot_mr_approve`/`ssot_apply_changes` с `confirm:true` |

Этап 2c `services` встроен в фазу 2: `make services IS=<код>` показывает план
(какие репозитории клонировать, где `docs/` и `openspec/`), `make
services-apply IS=<код>` пишет `is/<код ИС>/SERVICE-FINDINGS.md` с цитатами
«файл:строка». Клоны читаются только `git` — сборка и запуск запрещены (R12),
цитата из кода — основание, а не значение (R14), закрытые сервисы не
анализируются (R15). Подробности — [07-scripts.md](07-scripts.md) §14, структура
отчёта — [10-templates.md](10-templates.md) §3.3.

Отдельные подкоманды вне конвейера: `scaffold` (завести ИС:
`make scaffold CONTOUR=mm NAME=<name_is>`), `requirements` (лист недостающих
данных: `make requirements IS=<код>`), `enrich` (принять заполненный лист:
`make enrich IS=<код>` / `make enrich-apply IS=<код>`), `exclude` / `include`
(`make exclude IS=<код> REASON="..."` / `make include IS=<код>`),
`reassess` (`make reassess IS=<код>` — план, `make reassess-apply IS=<код>` —
запись и `review_date`), `validate` (`make validate`),
`index` (`make index`), `due` (`make due`),
`criteria` (`make criteria` / `make criteria-check`), `help` (`make help` —
подкоманды, воркфлоу, артефакты и текущее состояние ИС) и `info` (`make info` —
критерии с пояснениями дословно из файла критериев, `SECTION=<имя>` и `JSON=1`).
Этап `ssot` (`ssot-import` → `ssot-plan` → MCP-форма → `ssot-record` →
`ssot-verify`) идёт после `publish` (dochub-MR). Клона, ветки и коммита нет:
карточку читает MCP `ssot_get`/`ssot_team` (снимок пишет `ssot-import`), целевые
значения считает `ssot-plan` (только `severity.type` и `severity.confirmation`
формы base), MR создаёт `ssot_form_save`, `mrUrl`/`version` фиксирует
`ssot-record`, независимую проверку даёт `ssot_verify_change` → `ssot-verify`.
`severity` уже совпадает — `status: no_change`, MR не создаётся. Тред в
`#Criticality_assessment` — это `handoff`, а не `publish`; апрув и применение
MR — `ssot_mr_approve`/`ssot_apply_changes` с `confirm:true` у человека.
После каждой команды конвейера скрипт печатает подсказку
`Следующий шаг: <команда> — <причина>` (отключается `--no-next`).

## 4. Правила

Полные формулировки — `.opencode/skills/criticality-gen/references/rules.md`. Кратко:

| # | Правило |
|---|---------|
| R1 | Факт-или-null: значение без `{type, ref}` → `null` + `status: missing` |
| R2 | Только шаблон: артефакт — рендер `.opencode/skills/criticality-gen/templates/*`, ручная правка запрещена |
| R3 | Гейт: `check` (strict по умолчанию) до `start`; сценарий — по данным: любой непустой вход только сложного набора (`time_to_impact`, `axes_scores`, `cia`) → сложный (`detailed`), иначе простой (`express`); неполный сложный набор — `BLOCKED` без фолбэка на простой; нехватка blocking-входа или значение вне множества — стоп, advisory — только WARN |
| R4 | Провенанс: `source = {type, ref}`, `type` из фиксированного перечисления |
| R5 | Конвенции помечаются `kind: convention` + `status: needs_validation` |
| R6 | Расхождения не разрешаются молча: `conflicts` + оба значения |
| R7 | Детерминизм: одинаковые входы и `--date` → побайтово одинаковый результат |
| R8 | Безопасная запись: без `--force` паспорт не перезаписывается |
| R9 | Внешние действия — только по флагу и подтверждению |
| R10 | Остановка вместо догадки: список полей и адресатов |
| R11 | Остановка с файлом требований: при `BLOCKED` — `DATA-REQUIREMENTS.*`; `enrich` принимает только `value` + `source` + `status: confirmed`; нет данных — `excluded: true` + `reason` в `catalog.yaml` (общее) или `is.yaml` (локально), вердикт `SKIPPED` |
| R12 | Клоны сервисов — только чтение: в `apps/` разрешён `git` из allowlist (`clone`/`pull`/`fetch`/`rev-parse`/`log`/`status`/`show`/`diff`/`ls-remote`), сборка, тесты и запуск запрещены; `--no-clone` (`NO_CLONE=1`) отключает git |
| R13 | Сценарий выбирается по данным: непустой вход только сложного набора → сложный, иначе простой; частично заполненный сложный набор не даёт права на расчёт |
| R14 | Код — основание, а не значение: цитата «файл:строка» подтверждает вход только после подтверждения человеком |
| R15 | Закрытые сервисы не клонируются: `lifecycle: closed` (`criteria.service_lifecycle.skip`) — не анализ и не основание для входов, перечислены в §2 `SERVICE-FINDINGS.md` |
| R16 | Язык — только русский: артефакты, вопросы, CLI и ошибки — русские, ответы пользователя принимаются только на русском; латиница — лишь идентификаторы (логины, URL, `page_id`, uid, PromQL, ключи Jira/MR, имена файлов/сервисов, enum внешних систем); `validate`/`enrich` — `WARN` о прозе не на русском в свободных полях |

### Восемь инвариантов скилла

1. Факт-или-null — R1.
2. Шаблон-или-ничего — R2.
3. Гейт-или-блокировка — R3, R10.
4. Нет данных → файл требований, а не догадка (`DATA-REQUIREMENTS.*`,
   `RESEARCH-PLAN.md`, `SERVICE-FINDINGS.md`) — R11.
5. Клоны только читаются — R12, R14.
6. Закрытые сервисы не анализируются — R15.
7. SSoT обогащается точечно и только через MCP: `type` — из
   `levels.ssot_enum`, `confirmation` — из `approve_link`; MR создаёт
   `ssot_form_save`, клона, ветки и push нет, апрув/применение — только человек
   с `confirm:true`.
8. Язык — только русский: артефакты, вопросы и ошибки — на русском, ответы
   пользователя принимаются только на русском, латиница — только идентификаторы
   — R16.

## 5. Установка, обновление, удаление

opencode обнаруживает project-level скиллы в `<проект>/.opencode/skills/<name>/SKILL.md`
и команды в `<проект>/.opencode/commands/**/*.md` автоматически — регистрация в
`opencode.json` не нужна. Глобальная установка (`./install.sh` без флагов)
кладёт скилл в `~/.config/opencode/skills/` и команду в
`~/.config/opencode/commands/` — тогда он доступен в любом проекте.
Поэтому «установка» = либо положить инструмент в `.opencode/` нужного проекта
(`--project`), либо поставить его глобально.

После `install.sh --project <каталог>` он уже на месте: `/criticality_gen` и
скилл `criticality-gen` видны из корня этого проекта без каких-либо действий.

```bash
make paths                # ROOT (данные) и SKILL_DIR (инструмент)
make skill-check          # структура: frontmatter, references, scripts/criteria/templates, плейсхолдеры
```

### В другой проект

```bash
./install.sh --project /путь/к/проекту            # скилл + команда + Makefile + is.example.yaml
./install.sh --project /путь/к/проекту --dry-run  # план, ничего не пишется
./install.sh --uninstall --project /путь/к/проекту
```

Через make: `make skill-install TARGET=/путь [FORCE=1]`,
`make skill-uninstall TARGET=/путь`.

Что создаётся в целевом проекте:

```text
<target>/.opencode/skills/criticality-gen        # копия скилла (маркер .criticality-gen-project)
<target>/.opencode/commands/criticality_gen.md   # команда /criticality_gen (маркер в конце файла)
<target>/.opencode/Makefile                      # все цели make
<target>/Makefile                                # корневой фасад на .opencode/Makefile
<target>/is.example.yaml                         # шаблон is.yaml (копия templates/is.example.yaml)
```

Ставится копией, а не симлинком: проект не зависит от расположения источника,
обновление — повторный запуск установщика. Чужое не перезаписывается:
`Makefile`, `.opencode/Makefile` и `is.example.yaml` ставятся только если файла
нет (иначе — `ВНИМАНИЕ` и файл остаётся как есть, код 0); каталог скилла без
маркера — только с `--force`. `--uninstall --project` удаляет поставленное и
оставляет файлы, которые отличаются от наших шаблонов (сравнение `cmp -s`).
После установки — `cd <target> && make init`.

### Глобально

```bash
./install.sh              # скилл в ~/.config/opencode/skills/criticality-gen/ + команда
./install.sh --claude     # ещё и в ~/.claude/skills/criticality-gen/
./install.sh --dry-run    # план, ничего не пишется
./install.sh --uninstall  # удалить поставленное (маркер .criticality-gen-installed)
```

Без клона — `curl … | sh` с проверкой sha256; команда и переменные окружения —
в `README.md` компонента.

### Во внешний репозиторий

Переносится только инструмент: `.opencode/skills/criticality-gen` и
`.opencode/commands/criticality_gen.md` (при необходимости — `.opencode/Makefile`
и корневой фасад). Данные и документация (`is/`, `catalog.yaml`, `INDEX.md`,
`docs/`, `is.yaml`) остаются в проекте. После переноса ничего в скрипте менять
не нужно: `SKILL_DIR` считается от файла скрипта, `PROJECT_ROOT` — от cwd/env/`--root`.

Проверка после установки:

```bash
ls -l <target>/.opencode/skills/criticality-gen
ls -l <target>/.opencode/commands/criticality_gen.md
cd <target> && make paths && make validate
```

## 6. Скилл для другой предметной области

В `.opencode/skills/criticality-gen/meta-templates/` лежат обобщённые шаблоны, не привязанные к критичности. Назначение каждого файла и его целевой путь — [10-templates.md](10-templates.md), раздел 6; здесь только порядок работы.

Порядок:

1. `mkdir -p .opencode/skills/<name>/references` и скопировать шесть шаблонов под нужными именами.
2. Заменить все `{{ }}`; удалить шапки-комментарии шаблонов.
3. Заполнить `name` строго по имени каталога, `description` — с блоком «Используйте когда…».
4. Проверить: `grep -rn "{{" .opencode/skills/<name>/` — пусто.
5. Добавить цель проверки по образцу `make skill-check` (frontmatter, references, отсутствие плейсхолдеров).

Шаблоны не редактируются под конкретный скилл: изменение шаблона меняет все
будущие скиллы. Специфика живёт в готовом скилле, а не в `.opencode/skills/criticality-gen/meta-templates/`.

## 7. Что запрещено менять

| Объект | Почему |
|--------|--------|
| `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` под конкретную ИС | файл критериев — общая методика; правка под ИС ломает сопоставимость и `criteria-check` |
| `.opencode/skills/criticality-gen/templates/*` под конкретную ИС | шаблоны принадлежат инструменту, а не проекту: правка под одну ИС ломает остальные и теряется при обновлении инструмента |
| Сгенерированные артефакты (`criticality-passport.yaml`, `CRITICALITY.md`, `GENERATION.md`, `actions/*`) | перезаписываются следующим `start`; менять нужно источник (R2) |
| `apps/` и `.ssot/` | `apps/` — клоны компонентов: источник правды — их репозитории, разрешён только `git` (R12). `.ssot/` — служебные артефакты SSoT (`apply-plan.json`, `MR.url`/`.md`, `verify.json`): пишут только `ssot-plan`/`ssot-record`/`ssot-verify`, руками не правят |
| `.opencode/skills/criticality-gen/meta-templates/*.template` под один скилл | шаблон общий; специфика — в `.opencode/skills/<name>/` |
| Числа и уровни в тексте скилла | скилл не считает; числа берутся из расчёта и критериев |

## 8. Диагностика

| Симптом | Проверка |
|---------|----------|
| Скилл не виден в opencode | `ls .opencode/skills/criticality-gen/SKILL.md`; скилл должен лежать в `<проект>/.opencode/skills/` |
| Команда не находится | `ls .opencode/commands/criticality_gen.md` |
| Скрипт не находит данные | `make paths`; при необходимости `--root <путь>` или env `CRITICALITY_ROOT` |
| Скрипт не находит шаблоны/критерии | `make paths` → `SKILL_DIR`; файлы должны быть в `<SKILL_DIR>/templates` и `<SKILL_DIR>/criteria` |
| Скилл «не тот» после правок | симлинк ведёт не туда: `readlink -f <target>/.opencode/skills/criticality-gen`, затем `--force` |
| Структура сломана | `make skill-check` |
| Плейсхолдеры остались | `grep -rn "{{" .opencode/skills/` |
| Ошибки в references | все ссылки из `SKILL.md` проверяются в `make skill-check` |

## 9. Связанные документы

- [09-pipeline.md](09-pipeline.md) — конвейер `is.yaml` → `ssot-import` → `INFORMATION.yaml` → `check` → `start` → `validate` → `publish` → `ssot-plan`/`ssot-record`/`ssot-verify` → `handoff`.
- [10-templates.md](10-templates.md) — каталог `.opencode/skills/criticality-gen/templates/`, движок и правило «шаблон → артефакт».
- [07-scripts.md](07-scripts.md) — CLI-справочник `.opencode/skills/criticality-gen/scripts/criticality.py`.
- [08-criteria.md](08-criteria.md) — правила расчёта и `kind`.
- [04-reassessment.md](04-reassessment.md) — runbook переоценки (боковой этап `reassess`).

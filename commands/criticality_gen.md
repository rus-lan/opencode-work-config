---
name: criticality_gen
description: Генерация и переоценка паспортов критичности ИС по D6.1.1 — init, prepare, check, requirements, collect, services, enrich, exclude, score, start, reassess, validate, index, publish, ssot-import, ssot-plan, ssot-record, ssot-verify, due. Останавливается, если данных не хватает, и выдаёт лист требований.
agent: build
subtask: true
title: "/criticality_gen — паспорта критичности ИС"
purpose: Дать точку входа в скилл criticality-gen через одну команду с подкомандами.
audience: [ai-agent]
read_when: [пользователь вызвал /criticality_gen, нужна подкоманда скилла]
updated: 2026-11-24
status: actual
related: [../skills/criticality-gen/SKILL.md, ../skills/criticality-gen/references/workflow.md, ../skills/criticality-gen/references/commands.md]
---

# /criticality_gen — паспорта критичности ИС

Тонкая обёртка над скиллом `criticality-gen`. Аргумент `$ARGUMENTS` — имя
подкоманды. Никакой собственной логики: правила, фазы и гейты — в скилле
`criticality-gen` (`SKILL.md` и `references/`).

## Что делать

1. Загрузи скилл `criticality-gen` (skill tool) и прочитай его `SKILL.md`.
2. Разбери `$ARGUMENTS`: первый токен — подкоманда, остальные — её параметры
   (например `start erm.mm`, `check --strict`).
3. Выполни соответствующую команду из таблицы ниже через `bash` в корне
   репозитория. Покажи фактический вывод, не пересказ.
4. Если подкоманда вернула `BLOCKED`/ненулевой код — остановись, покажи путь к
   `DATA-REQUIREMENTS.md` и `RESEARCH-PLAN.md` и перечисли, чего не хватает и у
   кого это взять (правила R3, R10 и R11 скилла). Порядок сбора:
   `collect` → сбор по плану (SSoT, Confluence, Grafana) → `services`
   (`docs/`/`openspec/` клонов) → `check` → `enrich`. Не заполняй значения сам и не подставляй их «по аналогии».
5. Не коммить и не пушить: изменения остаются рабочей копией, коммит — отдельное
   решение человека.

## Подкоманды

| Аргумент | Команда | Что делает |
|----------|---------|------------|
| `help` | `make help` / `python3 .opencode/skills/criticality-gen/scripts/criticality.py help [--no-state]` | справка: назначение и границы, все подкоманды, воркфлоу, артефакты по этапам, текущее состояние ИС (`код \| сценарий \| гейт \| уровень \| следующий шаг`); `make help-fast` — то же без чтения состояния |
| `info` | `make info [SECTION=<имя>] [JSON=1]` / `python3 .opencode/skills/criticality-gen/scripts/criticality.py info [--section <имя>] [--json]` | критерии оценки с пояснениями дословно из `criteria/criticality-criteria.yaml`: уровни, сценарии, входы, enum'ы, экспресс, детальная матрица, service_lifecycle, провенанс |
| `init` | `make init` | создать `is.yaml` из `is.example.yaml` |
| `prepare` | `make prepare` (план) / `make prepare-apply` (запись) | `INFORMATION.yaml` из снимка карточки (`ssot-import`) и `apps/<код ИС>/`; клон SSoT не нужен; кода нет в снимке — ошибка (файл не создаётся); секция, отсутствующая в снимке, сохраняется; бэкап `INFORMATION.yaml.bak-<UTC-метка>` с ротацией; флаги `--allow-empty-sections`, `--no-backup`, `--backup-keep N` |
| `check` | `make check-prepare` (подготовка + гейт) / `make check` (только гейт) | гейт достаточности: `OK` / `BLOCKED` / `SKIPPED` / `CONFLICT`; strict по умолчанию; при `BLOCKED` пишет `DATA-REQUIREMENTS.*` |
| `check --diagnostic` | `make check-diag` | гейт без ошибки при `BLOCKED` (код 0) |
| `requirements` | `make requirements IS=<код>` (план) / `make requirements IS=<код> APPLY=1` | лист `DATA-REQUIREMENTS.md`/`.yaml`: что/зачем/где/у кого/как подтвердить |
| `collect` | `make collect IS=<код>` (план) / `make collect-apply IS=<код>` | `RESEARCH-PLAN.md`: страницы Confluence (`page_id`, что искать), дашборды Grafana и PromQL, кто подтверждает; закрытые сервисы (`lifecycle: closed`) в план не попадают |
| `services` | `make services IS=<код>` (план) / `make services-apply IS=<код>`; `NO_CLONE=1` — без git | `SERVICE-FINDINGS.md`: клоны сервисов (ветка, `docs/`, `openspec/`, SLO-конфиг), цитаты «файл:строка», «вход → основание», «не найдено»; сервисы с `lifecycle: closed` пропускаются (не клонируются и не анализируются, раздел «Пропущенные сервисы»); сборка и запуск запрещены, git — только из allowlist (`clone`, `pull`, `fetch`, `rev-parse`, `log`, `status`, `show`, `diff`, `ls-remote`) |
| `enrich` | `make enrich IS=<код>` (проверка) / `make enrich-apply IS=<код>` | принять заполненный лист: `value` + `source` + `status: confirmed`; пишет только `criteria_inputs` (комментарии `#` сохраняются) |
| `exclude` / `include` | `make exclude IS=<код> REASON="..."` / `make include IS=<код>` | исключить ИС из расчёта (`excluded: true` + `reason`, вердикт `SKIPPED`) или вернуть |
| `score` | `python3 .opencode/skills/criticality-gen/scripts/criticality.py score --is <код>` | детерминированный расчёт критичности |
| `start` | `make start IS=<код> DIFF=1` → `make start-apply IS=<код> FORCE=1` | рендер паспорта, `CRITICALITY.md`, `GENERATION.md`, `actions/*` |
| `scaffold` | `make scaffold CONTOUR=<mm\|smkt> NAME=<name>` | папка `is/<код ИС>/` (например `is/foo.mm/`), запись в `catalog.yaml` и код в `is.yaml` (идемпотентно; нет `is.yaml` — создаётся из шаблона); `PAGE_ID` / `CRITICALITY_PAGE_ID` — если страницы уже есть |
| `reassess` | `make reassess IS=<код>` (план) / `make reassess-apply IS=<код>` (запись) | создать файл переоценки `reassessment-YYYY-MM-DD.md` и обновить `catalog.yaml → review_date` |
| `validate` | `make validate` | проверка паспортов и реестра (0 ERROR); расхождение копии `review_date` с реестром и `Mission critical+` как результат расчёта — WARN |
| `index` | `make index` | перегенерировать `INDEX.md` |
| `due` | `make due` | просроченные и ближайшие переоценки |
| `criteria` | `make criteria` / `make criteria-check` | показать критерии / проверить их целостность |
| `publish` | `make publish IS=<код> TASK=<key>` (план) / `make publish-apply IS=<код> TASK=<key>` (ветка + коммит) | паспорт в формате dochub: `architecture/app/<контур>/<сущность>/criticality_passport.yaml`, ключ `sber.ecom.<контур>.criticality_passport.<сущность>`, уровень в верхнем регистре; импорт в `_root.yaml`; ветка `feature/<task>` от `origin/master`; коммит из двух файлов; описание MR в `<dochub>/.publish/<код>-MR.md`. `PUSH=1` — только с записью и только по явному подтверждению. Это публикация в **dochub**, не в чат |
| `ssot-import` | `make ssot-import IS=<код> ENTITY_JSON=<файл\|-> [TEAM_JSON=<файл\|->]` | снимок карточки ИС из ответа MCP `ssot_get` → `INFORMATION.yaml → ssot_snapshot` (+ `contacts` из `ssot_team`); клон и сеть не нужны; повторный импорт — no-op |
| `ssot-plan` | `make ssot-plan IS=<код> [FORCE=1]` | план обогащения SSoT критичностью (после `publish`): `status` (`changed`/`no_change`/`blocked`), поля `severity.type` (из `levels.ssot_enum`) и `severity.confirmation` (= `approve_link`), шаги MCP; пишет `.ssot/<код>-apply-plan.json`, SSoT не меняет |
| `ssot-record` | `make ssot-record IS=<код> MR_URL=<mrUrl> [VERSION=] [SAVE_JSON=] [STATUS_JSON=]` | результат `ssot_form_save`: `.ssot/<код>-MR.url`, `.ssot/<код>-MR.md`, поля `ssot_mr_url`/`ssot_version`/`ssot_can_apply`/`ssot_status`/`ssot_recorded_at` в `INFORMATION.yaml` |
| `ssot-verify` | `make ssot-verify IS=<код> VERIFY_JSON=<файл\|->` | сверка применённой критичности с SSoT (`ssot_verify_change` после `ssot_apply_changes`) → `ssot_snapshot.verified` |
| `handoff` | вручную | тред в `#Criticality_assessment` со ссылками на dochub-MR и SSoT-MR (`mrUrl` из `ssot_form_save`; текст — `actions/rocketchat-message.md`), подтверждение SRE. Это публикация в **чат** |

Дополнительно: `make selftest`, `make docs-check` — проверки перед сдачей;
`make show IS=<код>` — сводка по ИС.

Итоговая критичность в выводе `score`/`start` — ячейка `final_matrix`
(бизнес-уровень × уровень защищённости), а не максимум бизнес/ИБ. Ошибки
печатаются как `ERROR: <текст>` с кодом 1 без traceback; traceback — только с
`--debug`.

## Аргументы CLI → переменные make

Флаги `criticality.py` передаются в make **именованными переменными**, а не
как есть:

| Пользователь написал | Запускать |
|----------------------|-----------|
| `help` | `make help` |
| `help --no-state` | `python3 .opencode/skills/criticality-gen/scripts/criticality.py help --no-state` |
| `info` | `make info` |
| `info --section levels` | `make info SECTION=levels` |
| `info --json` | `make info JSON=1` |
| `check` | `make check-prepare` (подготовка + гейт) или `make check` (только гейт) |
| `check --strict` | `make check` (strict — поведение по умолчанию) |
| `check --diagnostic` | `make check-diag` |
| `check --is erm.mm` | `make check IS=erm.mm` |
| `check --prepare` | `make check-prepare` |
| `check --no-requirements` | `make check NO_REQUIREMENTS=1` (лист не пишется, не обновляется, не удаляется) |
| `prepare --apply` | `make prepare-apply` (без снимка `ssot-import` не пишет и падает) |
| `prepare --allow-empty-sections` | `make prepare-apply ALLOW_EMPTY_SECTIONS=1` (осознанно очистить секции, отсутствующие в SSoT) |
| `prepare --no-backup` | `make prepare-apply NO_BACKUP=1` (без `INFORMATION.yaml.bak-<UTC-метка>`) |
| `prepare --backup-keep N` | `make prepare-apply BACKUP_KEEP=5` (хранить 5 последних бэкапов) |
| `prepare --no-clone` | `make prepare-apply NO_CLONE=1` (git для `apps/` не вызывается) |
| `requirements --is erm.mm` | `make requirements IS=erm.mm` |
| `requirements --apply` | `make requirements IS=erm.mm APPLY=1` |
| `collect --is erm.mm` | `make collect IS=erm.mm` |
| `collect --apply` | `make collect-apply IS=erm.mm` |
| `collect --date 2026-11-11` | `make collect IS=erm.mm DATE=2026-11-11` |
| `services --is erm.mm` | `make services IS=erm.mm` |
| `services --apply` | `make services-apply IS=erm.mm` |
| `services --date 2026-11-11` | `make services IS=erm.mm DATE=2026-11-11` |
| `services --no-clone` | `make services IS=erm.mm NO_CLONE=1` / `make services-apply IS=erm.mm NO_CLONE=1` (git не вызывается; отсутствующие клоны — §2) |
| `requirements --date 2026-11-11` | `make requirements IS=erm.mm DATE=2026-11-11` |
| `enrich --is erm.mm` | `make enrich IS=erm.mm` |
| `enrich --apply` | `make enrich-apply IS=erm.mm` |
| `exclude --is erm.mm --reason "нет данных"` | `make exclude IS=erm.mm REASON="нет данных"` |
| `include --is erm.mm` | `make include IS=erm.mm` |
| `reassess --is erm.mm` | `make reassess IS=erm.mm` (план, dry-run) |
| `reassess --apply` | `make reassess-apply IS=erm.mm` (файл + `catalog.yaml → review_date`) |
| `reassess --date 2026-11-11 --apply` | `make reassess-apply IS=erm.mm DATE=2026-11-11` |
| `index --date 2026-11-12` | `make index DATE=2026-11-12` |
| `validate --date 2026-11-12` | `make validate DATE=2026-11-12` (просрочка от указанной даты) |
| `scaffold mm foo` | `make scaffold CONTOUR=mm NAME=foo` |
| `start --force` | `make start-apply FORCE=1` |
| `start --reassessment` | `make start-apply REASSESSMENT=1` |
| `start --dry-run` | `make start` (`DRY=1` по умолчанию) |
| `start --diff` | `make start DIFF=1` |
| `start --date 2026-11-11` | `make start DATE=2026-11-11` / `make start-apply DATE=2026-11-11` |
| `start --create-task` | `make start-apply TASK=1` |
| `start --create-confluence` | `make start-apply CONFLUENCE=1` |
| `start --create-message` | `make start-apply MESSAGE=1` |
| `start --no-requirements` | `make start DIFF=1 NO_REQUIREMENTS=1` (лист не трогается) |
| `publish --is erm.mm --task E001-31245` | `make publish IS=erm.mm TASK=E001-31245` |
| `publish --is erm.mm --task E001-31245 --apply` | `make publish-apply IS=erm.mm TASK=E001-31245` |
| `publish --is erm.mm --task E001-31245 --apply --push` | `make publish-apply IS=erm.mm TASK=E001-31245 PUSH=1` (только по явному подтверждению) |
| `publish --dochub /путь/к/dochub` | `make publish IS=erm.mm TASK=E001-31245 DOCHUB=/путь/к/dochub` |
| `publish --branch feature/E001-31245-mm` | `make publish IS=erm.mm TASK=E001-31245 BRANCH=feature/E001-31245-mm` |
| `ssot-import --is erm.mm --entity-json /tmp/ssot_get.json` | `make ssot-import IS=erm.mm ENTITY_JSON=/tmp/ssot_get.json` |
| `ssot-import --team-json /tmp/ssot_team.json` | `make ssot-import IS=erm.mm ENTITY_JSON=... TEAM_JSON=/tmp/ssot_team.json` |
| `ssot-plan --is erm.mm` | `make ssot-plan IS=erm.mm` |
| `ssot-plan --is erm.mm --force` | `make ssot-plan IS=erm.mm FORCE=1` (только по явному подтверждению) |
| `ssot-record --is erm.mm --mr-url <url>` | `make ssot-record IS=erm.mm MR_URL=<mrUrl из ssot_form_save>` |
| `ssot-verify --is erm.mm --verify-json /tmp/ssot_get-after.json` | `make ssot-verify IS=erm.mm VERIFY_JSON=/tmp/ssot_get-after.json` |

## Если аргумент не передан

Ничего не запускай. Напечатай список подкоманд с одной строкой описания
(таблица выше) и примеры:

```text
/criticality_gen help
/criticality_gen info
/criticality_gen info --section express
/criticality_gen init
/criticality_gen prepare
/criticality_gen check
/criticality_gen requirements erm.mm
/criticality_gen collect erm.mm
/criticality_gen services erm.mm
/criticality_gen enrich erm.mm
/criticality_gen start erm.mm
/criticality_gen reassess erm.mm
/criticality_gen reassess-apply erm.mm
/criticality_gen validate
/criticality_gen ssot-import erm.mm --entity-json /tmp/ssot_get.json
/criticality_gen ssot-plan erm.mm
/criticality_gen publish erm.mm --task E001-31245
/criticality_gen due
```

Затем спроси, что запускать.

## Флаги, которые нельзя ставить молча

- `FORCE=1` — перезапись существующего паспорта и `CRITICALITY.md` (без него
  `start` печатает `CONFLICT … файлы не изменены` и возвращает ненулевой код:
  CLI → 1, make → 2).
- `TASK=1` / `CONFLUENCE=1` / `MESSAGE=1` — только помечают action-пакет как
  `requested`; само внешнее действие (Jira, Confluence, сообщение) выполняется
  по явному подтверждению человека в этой сессии.
- `NO_REQUIREMENTS=1` — не создавать `DATA-REQUIREMENTS.*` при `BLOCKED`; только
  для отладки, иначе адресат не увидит, что и где взять.
- `exclude` — необратимо меняет `is.yaml` (ИС выпадает из расчёта); `reason`
  обязателен, `include` возвращает ИС.
- `publish --apply` — пишет в клон dochub (паспорт + `_root.yaml`) и создаёт
  ветку/коммит; без `--apply` это dry-run. `--push` — только с `--apply` и только
  по явному подтверждению человека: пуш и создание MR — внешнее действие.
- `ssot_form_save` и применение MR — только по явному подтверждению человека:
  `ssot_mr_approve(confirm: true)` → `ssot_apply_changes(confirm: true)` →
  `ssot_wait_master`. Обогащение SSoT идёт ДО публикации в
  `#Criticality_assessment` (тред ссылается на SSoT-MR из `mrUrl`).
  `ssot-plan --force` (как и `publish --force`) — осознанный обход гейта R18.
- Публикация не меняет `criteria_inputs`, `catalog.yaml` и `is/`: источник — уже
  сгенерированный паспорт. Обогащение SSoT не меняет `catalog.yaml`, `is/` и
  другие файлы карточки ИС: в форме правятся только `severity.type` и
  `severity.confirmation`.

## Ссылки

- `.opencode/skills/criticality-gen/SKILL.md` — обзор и инварианты.
- `.opencode/skills/criticality-gen/references/workflow.md` — канон флоу: фазы 0–10, боковые этапы и гейты.
- `.opencode/skills/criticality-gen/references/commands.md` — синтаксис и все флаги подкоманд.
- `.opencode/skills/criticality-gen/references/checklist.md` — приёмочный чеклист.
- `.opencode/skills/criticality-gen/references/failure-modes.md` — что делать при ошибке.
- `.opencode/skills/criticality-gen/references/data-sources.md` — карта источников, процедуры Confluence и Grafana.

<!-- # criticality-gen:command -- installed by install.sh, safe to remove -->

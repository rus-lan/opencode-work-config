---
title: "Артефакты: criticality-gen"
purpose: "Реестр артефактов скилла: что вход, что производное, кто создаёт и как перезаписывается."
audience: [ai-agent]
read_when: [нужно понять, какой файл переживает прогон, добавляете новый артефакт]
updated: 2026-11-18
status: actual
related: [workflow.md, commands.md, interactive.md]
---

# Артефакты: criticality-gen

Артефакт — это либо вход (ручной, переживает прогоны), либо производное
(генерируется и перезаписывается). Смешивать классы нельзя: производное всегда
восстанавливается из входа.

Обозначения в путях: `IS` — код ИС (`<name_is>.<контур>`, например `erm.mm`),
`COMPONENT` — имя компонента. Папка ИС — плоская: `is/IS/` (например `is/erm.mm/`).

## Реестр

| Артефакт | Путь | Шаблон | Кто создаёт | Входные данные | Политика перезаписи | Обязателен |
|----------|------|--------|-------------|----------------|---------------------|------------|
| `is.yaml` | `is.yaml` | `templates/is.example.yaml` | `criticality.py init` | шаблон скилла | `never` (только `--force`) | да |
| Клон SSoT | `ssot/` | — | `criticality.py prepare --apply` (`git clone` / `git pull`); `ssot --apply` — ветка `feature/<task>` + коммит | `is.yaml#ssot.url` | `always` (git pull; локальные правки запрещены, кроме `ssot --apply` — только блок `severity`) | да |
| Описание SSoT-MR | `<ssot>/.ssot/IS-MR.md` | `templates/MR-ssot.md` (строгий рендер) | `criticality.py ssot --apply` | паспорт, `catalog.yaml` (`approve_link`), `criteria.levels.ssot_enum` | `always` (в клоне SSoT, грязью не считается) | нет (при `ssot --apply`) |
| Описание MR публикации | `<dochub>/.publish/IS-MR.md` | `templates/MR-dochub.md` (строгий рендер) | `criticality.py publish --apply` | паспорт, `catalog.yaml`, расчёт | `always` (в клоне dochub, грязью не считается) | нет (при `publish --apply`) |
| `INFORMATION.yaml` | `is/IS/INFORMATION.yaml` | `templates/INFORMATION.yaml` (скелет) | `prepare --apply` — автосекции; человек — `criteria_inputs`, `facts`, `conflicts`, `notes` | `ssot/entities/information-systems/IS/*.yaml`, `catalog.yaml`, `is.yaml` | `always` для автосекций, `never` для ручных | да |
| Клоны компонентов | `apps/IS/COMPONENT/` | — | `prepare --apply` (`git clone` / `git pull`) | `ssot/.../components.yaml#gitRepository` | `always` (git pull) | нет |
| Файл требований (человеку) | `is/IS/DATA-REQUIREMENTS.md` | `templates/DATA-REQUIREMENTS.md` | `criticality.py requirements --apply` (также автоматически из `check`/`start` при `BLOCKED`) | `INFORMATION.yaml`, критерии, `is.yaml` | `always`; удаляется, когда незакрытых входов нет | нет (только при `BLOCKED`) |
| Файл требований (для заполнения) | `is/IS/DATA-REQUIREMENTS.yaml` | `templates/DATA-REQUIREMENTS.yaml` | то же | то же | `always`; удаляется вместе с `.md` | нет (только при `BLOCKED`) |
| План сбора данных | `is/IS/RESEARCH-PLAN.md` | `templates/RESEARCH-PLAN.md` | `criticality.py collect --apply` | `INFORMATION.yaml`, критерии, `catalog.yaml`, SSoT `links.yaml`/`components.yaml` | `always`; удаляется, когда незакрытых входов нет | нет (только при `BLOCKED`) |
| Протокол выполненного поиска | `is/IS/RESEARCH.md` | — (рендер из `_research_report`) | `criticality.py research` | `criteria.inputs.*`/`routes.*` (CQL-запросы), `INFORMATION.yaml`, `catalog.yaml`, Confluence REST | `always` (перезаписывается каждым прогоном) | нет |
| Находки по коду сервисов | `is/IS/SERVICE-FINDINGS.md` | `templates/SERVICE-FINDINGS.md` | `criticality.py services --apply` | клоны `apps/IS/COMPONENT/` (только чтение), `INFORMATION.yaml#components[]` | `always` | нет (этап `services`) |
| Пропущенные сервисы | `is/IS/SERVICE-FINDINGS.md` §2 | `templates/SERVICE-FINDINGS.md` | то же | `INFORMATION.yaml#components[].lifecycle`, `criteria.service_lifecycle` | `always` (часть отчёта) | нет |
| План вопросов | `is/IS/ASK.md` | `templates/ASK.md` | `criticality.py ask --apply` | `INFORMATION.yaml`, критерии, `CANDIDATES.yaml`, `SERVICE-FINDINGS.md` §6, SSoT `base.yaml`/`links.yaml` | `always` (при `--apply`); когда незакрытых входов нет, файл не создаётся и не удаляется | нет (этап `ask`) |
| Кандидаты значений | `is/IS/CANDIDATES.yaml` | `templates/CANDIDATES.yaml` | шаг сбора: агент или человек | `SERVICE-FINDINGS.md` §6, SSoT `base.yaml`/`links.yaml`, Confluence/Grafana, экспертиза | `never` (ведёт человек/агент; `ask` только читает) | нет (этап `ask`) |
| Ответы человека | `is/IS/ANSWERS.yaml` | `templates/ANSWERS.yaml` | человек (по плану `ASK.md`) | `ASK.md`, `CANDIDATES.yaml` | `never` (ведёт человек; `ask --answers` только читает) | нет (этап `ask`) |
| Паспорт dochub | `is/IS/criticality-passport.yaml` | `templates/criticality-passport.yaml` | `criticality.py start` | `INFORMATION.yaml` + критерии + расчёт | `only-with-force` | да |
| Человекочитаемый паспорт | `is/IS/CRITICALITY.md` | `templates/CRITICALITY.md` | `criticality.py start` | `INFORMATION.yaml` + критерии + расчёт | `only-with-force` | да |
| Отчёт о генерации | `is/IS/GENERATION.md` | `templates/GENERATION.md` | `criticality.py start` | контекст рендера, `score_trace`, `conflicts` | `always` | да (после `start`) |
| Jira action-пакет | `is/IS/actions/jira-task.md` | `templates/actions/jira-task.md` | `criticality.py start` | `actions.jira.*`, `identity.*`, `passport.*` | `always` | да (после `start`) |
| Confluence action-пакет | `is/IS/actions/confluence-page.md` | `templates/actions/confluence-page.md` | `criticality.py start` | `actions.confluence.*`, `identity.*` | `always` | да (после `start`) |
| RocketChat action-пакет | `is/IS/actions/rocketchat-message.md` | `templates/actions/rocketchat-message.md` | `criticality.py start` | `actions.message.*`, `passport.*` | `always` | да (после `start`) |
| Текст публикации | входит в `actions/rocketchat-message.md` | `templates/publication.md` | `criticality.py start` (предпросмотр); финальный текст — `handoff` в момент вызова | `identity.*`, `actions.*`, `passport.object_criticality_estimation` | `always` | да (после `start`) |
| Предпросмотр отправки | `is/IS/actions/handoff-preview.txt` | — (точный текст) | `criticality.py handoff --write` | текущее состояние ИС | `always` (перезапись) | нет (внутри `is/`) |
| Файл переоценки | `is/IS/reassessment-YYYY-MM-DD.md` | — (генерируется `reassess`) | `criticality.py reassess --is` | текущий паспорт, `due` | `never` (новый файл на дату) | нет |
| Индекс | `INDEX.md` | `templates/INDEX.md` (каркас) | `init` создаёт каркас; `criticality.py index --write` заполняет таблицу | `catalog.yaml` + паспорта | `always` (блок между маркерами) | да |
| Реестр ИС | `catalog.yaml` | `templates/catalog.yaml` | `init` создаёт пустой реестр; `scaffold` дописывает запись; человек правит поля | список ИС, коды, page_id | `append-only` для `scaffold`; ручные правки — человек | да |
| Файл критериев | `criteria/criticality-criteria.yaml` | — | человек (владелец методики) | регламент D6.1.1 | `never` (только MR) | да |

## Политики перезаписи

| Политика | Значение |
|----------|----------|
| `always` | производный файл; перезаписывается каждым прогоном |
| `only-with-force` | перезапись только по явному `--force` (в Makefile — `FORCE=1`) |
| `append-only` | существующее содержимое не меняется, новое дописывается |
| `never` | создаётся один раз, дальше только читается |

## Исходные и производные

| Класс | Артефакты | Кто меняет |
|-------|-----------|------------|
| Исходные (ручные) | `is.yaml`, `INFORMATION.yaml` (`criteria_inputs`, `facts`, `conflicts`, `notes`), `catalog.yaml`, `criteria/criticality-criteria.yaml`, `is/IS/CANDIDATES.yaml`, `is/IS/ANSWERS.yaml` | человек |
| Производные (генерируемые) | `criticality-passport.yaml`, `CRITICALITY.md`, `GENERATION.md`, `actions/*`, `INDEX.md`, `reassessment-*.md`, `DATA-REQUIREMENTS.md`/`.yaml`, `RESEARCH-PLAN.md`, `RESEARCH.md`, `SERVICE-FINDINGS.md`, `ASK.md` | скрипт |
| Внешние клоны | `ssot/`, `apps/` | `git`; правки запрещены, кроме `ssot --apply` (только блок `severity` в `base.yaml`) |

## Что где искать при разборе значения

| Вопрос | Где ответ |
|--------|-----------|
| Откуда взялось значение в паспорте | `GENERATION.md` §3 «Входы с провенансом» |
| Какое правило применилось | `GENERATION.md` §5 «Использованные правила» |
| Что посчитано не по документу | `GENERATION.md` §6 «Conventions» |
| Почему паспорт расходится с реестром | `GENERATION.md` §1 «Расхождения» + `INFORMATION.yaml#conflicts` |
| Чего не хватает и у кого спросить | `DATA-REQUIREMENTS.md` §«Что нужно» (колонки «где взять» / «у кого») |
| Какие вопросы задать человеку и что уже найдено | `ASK.md` (вопрос + варианты ответа) + `CANDIDATES.yaml` (кандидаты с провенансом); ответы — `ANSWERS.yaml` |
| Где искать значение и какой запрос выполнить | `RESEARCH-PLAN.md` (Confluence-страницы, дашборды Grafana, PromQL) + [data-sources.md](data-sources.md) |
| Что уже искали и с каким результатом | `RESEARCH.md` — протокол выполненного поиска: «не найдено» доказано списком запросов, а не отсутствием попытки |
| Что говорит код сервиса: назначение, нормативы, потоки | `SERVICE-FINDINGS.md` (§1 сервисы, §4 нормативы, §6 «вход → основание»); цитаты «файл:строка» |
| Какие сервисы закрыты и почему не анализировались | `SERVICE-FINDINGS.md` §2 «Пропущенные сервисы (lifecycle)» |
| Чего в коде сервиса нет | `SERVICE-FINDINGS.md` §7 «Не найдено» |
| Что осталось руками | `GENERATION.md` §4 «Ограничения» + `actions/*` |

## Связанные правила

- Политика перезаписи и запрет ручной правки — [rules.md](rules.md), R2 и R8.
- Лист требований и приём значений — [rules.md](rules.md), R11.
- Провенанс входов — [rules.md](rules.md), R4.
- Расхождения — [rules.md](rules.md), R6.
- Клоны только читаются, находки — основание, а не значение — [rules.md](rules.md), R12–R14.
- Вопросы и ответы — по-русски, значения не выдумываются — [rules.md](rules.md), R10 и R16; протокол опроса — [interactive.md](interactive.md).

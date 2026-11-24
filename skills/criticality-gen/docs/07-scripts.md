---
title: "CLI: scripts/criticality.py"
purpose: Точка входа в справочник CLI; сам справочник живёт внутри скилла и переносится вместе с ним.
audience: [ai-agent, human]
read_when: [вызываете criticality.py или make-цель, ищете флаг команды]
updated: 2026-11-13
status: actual
related: [09-pipeline.md, 10-templates.md, 04-reassessment.md]
---

# CLI: `scripts/criticality.py`

Справочник команд **не дублируется здесь**: единственный источник — файл
инструмента, который переезжает вместе со скиллом:

- **Синтаксис, все флаги, коды возврата:**
  [`references/commands.md`](../references/commands.md)
- **Фазы, гейты и порядок шагов:**
  [`references/workflow.md`](../references/workflow.md)
- **Приёмка цикла:**
  [`references/checklist.md`](../references/checklist.md)

## Что важно знать про скрипт

- Один файл, подкоманды перечислены в `build_parser()`; `make help` печатает их
  с описаниями из `COMMAND_DESCRIPTIONS` — список и справка не расходятся.
- `PyYAML` используется, если установлен, иначе работает встроенный
  мини-парсер; поведение идентично.
- Сеть — только `git` (`prepare --apply`, `services --apply`, `publish --push`,
  `ssot --push`). `links` и `sources` офлайн: `links` строит карту обхода из
  локальных файлов, `sources` читает `SOURCES-FINDINGS.yaml`, который заполнил
  MCP-агент; ни та, ни другая команда не ходит в Confluence/Grafana. Единственный HTTP-вызов — сверка описания MR через GitLab API
  после пуша `ssot` (`GET`, при расхождении `PUT`); токен — `GITLAB_TOKEN`, без
  него печатается `WARN: … описание не верифицировано`, пуш при этом проходит.
- Ошибки — одной строкой `ERROR: <текст>`, код `1`, без traceback; traceback
  только с `--debug`. Ошибки разбора YAML содержат `<файл>:<строка>:<колонка>`.
- Коды возврата: `0` — успех, `1` — `ERROR`/`BLOCKED`/`incomplete`,
  `2` — ошибка аргументов (и любая неуспешная make-цель).
- Корень данных печатают `validate`, `check`, `start` (`Корень: <path>`);
  выбрать другой — `--root <path>`.

## Публикация и передача

Три последних этапа конвейера — разные вещи, и команды у них разные:

| Этап | Команда | Куда пишет | Что создаёт |
|------|---------|------------|-------------|
| `publish` | `make publish IS=<код> TASK=<key>` (план) / `make publish-apply ...` | клон `dochub/` | `architecture/app/<контур>/<сущность>/criticality_passport.yaml`, импорт в `_root.yaml`, ветка `feature/<task>`, коммит из двух файлов, `.publish/<код>-MR.md` |
| `ssot` | `make ssot IS=<код> TASK=<key>` (план) / `make ssot-apply ...` | клон `ssot/` | только блок `severity` в `entities/information-systems/<код>/base.yaml`, ветка `feature/<task>`, коммит из одного файла, `.ssot/<код>-MR.md` |
| `handoff` | `make handoff IS=<код> SEND=auto` (MCP, при отказе — REST) / `--dry-run` (показ); `handoff-apply` — тонкая обёртка того же пути (REST + `CONFIRM=1`) | `#Criticality_assessment` | тред со ссылками на dochub-MR и SSoT-MR (одно сообщение), `actions/handoff-preview.txt`, `catalog.yaml → handoff_status/thread_link/approve_link/transport_used` |
| `finalize` | `make finalize IS=<код> [APPROVE_LINK=...] [DRY_RUN=1]` | `catalog.yaml`, артефакты | `approve_link`, `assigned_date`, `review_date`, `criticality`, `criticality_ssot`, `status: confirmed` + `start-apply` → `validate` → `index` → `verify` |

Порядок обязателен: `publish` → `ssot` → `handoff`. SSoT-MR в «Основании»
ссылается на dochub-MR (`mr.passport_mr_url`), а тред — на оба MR.

`handoff` — последний этап: текст собирается в момент вызова из текущего
состояния, печатается ЦЕЛИКОМ и отправляется ОДНИМ сообщением только после
явного подтверждения человеком (`CONFIRM=1`). Текст с `⛔ не заполнено` не
публикуется без `--allow-incomplete`; превышение лимита канала — ошибка,
разбиение на части запрещено.

- `PUSH=1` (с `--apply`) пушит ветку и создаёт MR — только по явному
  подтверждению человека; `--push` без `--apply` — ошибка аргументов (код 2).
- Ветка уже существует — `publish-apply ... UPDATE=1` (только если ветка есть
  на `origin`: локальная ветка без пуша `--update` не обновляет); описание уже созданного
  SSoT-MR переписывается `make ssot-mr-apply IS=<код> TASK=<key>` (ветку и
  коммит не трогает).
- Описания MR рендерятся строго по `templates/MR-dochub.md` и
  `templates/MR-ssot.md`: пустая переменная — ошибка, а не пустая строка.
- Расхождений нет — `изменений нет`, ветка и коммит не создаются (код 0).

## Как расширять

Новая подкоманда = `subparsers.add_parser(...)` в `build_parser()` + запись в
`COMMAND_DESCRIPTIONS` + цель в `.opencode/Makefile` (если нужна) + строка в
`references/commands.md`. Поведение и инварианты — `references/rules.md`.

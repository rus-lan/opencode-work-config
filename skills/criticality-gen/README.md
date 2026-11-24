# criticality-gen

Оценка и переоценка критичности информационных систем по процессу D6.1.1: из
`is.yaml` через SSoT-репозиторий (`INFORMATION.yaml`) и детерминированный расчёт
по [`criteria/criticality-criteria.yaml`](./criteria/criticality-criteria.yaml).
Два сценария — простой (экспресс, 4 входа) и сложный (детальная оценка, 7
входов); у каждого значения провенанс `{type, ref}`; артефакты рендерятся только
по шаблонам и только из фактов — нет данных, значит блокировка и лист
требований, а не догадка. Дальше — публикация паспорта в dochub, точечное
обогащение SSoT и передача человеку.

Как это запускать как навык агента — [`SKILL.md`](./SKILL.md). История версий —
[`CHANGELOG.md`](./CHANGELOG.md). Инженерная документация инструмента —
[`docs/`](./docs/README.md); методика и процесс для людей живут в Confluence
(см. [«Документация»](#документация)).

## Когда использовать

- Оценить критичность ИС с нуля или переоценить её (`make check` →
  `make start-apply`).
- Понять, почему расчёт стоит: разобрать `BLOCKED`, получить лист недостающих
  данных, план сбора и карту обхода ссылок (`DATA-REQUIREMENTS.*`,
  `RESEARCH-PLAN.md`, `LINK-MAP.*`), принять факты из `SOURCES-FINDINGS.yaml`.
- Собрать основания из документации клонов сервисов (`docs/`, `openspec/`) —
  `SERVICE-FINDINGS.md` с цитатами «файл:строка».
- Опубликовать готовый паспорт в dochub и обновить критичность в SSoT (`severity`)
  с MR по шаблону.
- Исключить ИС из расчёта, обновить `INDEX.md`, найти просроченные переоценки
  (`exclude`, `index`, `due`, `reassess`).

Триггеры по-английски: «assess information system criticality», «reassess
criticality», «criticality passport», «publish passport to dochub», «update
criticality in SSoT», «why is the gate blocked».

## Что делает и чего не делает

Делает:

- **Держит гейт.** `check` останавливает расчёт, если нет блокирующего входа
  сценария, и создаёт `DATA-REQUIREMENTS.md`/`.yaml` — «что это → зачем → где
  взять → у кого → как подтвердить».
- **Хранит провенанс.** `{type, ref}` из списка `ssot`, `is_yaml_override`,
  `catalog`, `confluence`, `gitlab`, `jira`, `grafana`, `attachment`,
  `ssot_links`, `manual`; значение без источника — `null` и `status: missing`.
- **Считает детерминированно.** Те же входы и та же `--date` — побайтово тот же
  результат; итог берётся из ячейки `final_matrix.cells`, а не из правила
  `max(бизнес, ИБ)`.
- **Рендерит только из шаблонов.** `templates/` — единственный источник текстов
  артефактов; ручная правка сгенерированного запрещена.
- **Публикует и передаёт.** `publish` — MR в dochub, `ssot` — MR в SSoT,
  `handoff` — последний этап: сообщение в тред со ссылками на оба MR, показ
  целиком и публикация одним сообщением только после явного подтверждения.

Не делает (полный список — [`SKILL.md`](./SKILL.md#чего-скилл-не-делает)):

- **Не выдумывает числа.** Нет `peak_hour_load`, `object_sla`, `axes_scores`,
  `cia` — значит `null` и `status: missing`. Оценки осей и CIA из документов не
  выводятся: это экспертное решение.
- **Не собирает значения за человека.** `collect` строит план, но не ходит в
  Confluence и Grafana; `services` цитирует документацию, но значение
  подтверждает человек.
- **Не собирает и не запускает код сервисов.** В `apps/` разрешён только `git`
  из allowlist: ни сборки, ни тестов, ни установки зависимостей, ни запуска
  скриптов из клона.
- **Не мержит MR** и не пушит без `PUSH=1` и подтверждения человека; не правит
  SSoT сверх блока `severity`.
- **Не отправляет сообщения в чат.** MCP RocketChat нет: текст для
  `#Criticality_assessment` формируется как `actions/rocketchat-message.md`,
  отправляет человек.
- **Не обходит гейт.** «Почти полный набор» — это `BLOCKED`, а не
  `preliminary`.

## Требования

| Что | Зачем | Проверка |
|-----|-------|----------|
| `python3` ≥ 3.9 | движок `scripts/criticality.py` | `python3 --version` |
| `git` | клоны `ssot/`, `apps/`, ветки и коммиты `publish`/`ssot` | `git --version` |
| `make` | цели из `.opencode/Makefile` | `make --version` |
| POSIX `sh` | `install.sh` (работает под `sh`/`dash`/`bash`/`zsh`) | `sh -n install.sh` |
| доступ по ssh/https к SSoT | `prepare --apply` клонирует SSoT | `make prepare` |

Сторонних Python-пакетов нет — только стандартная библиотека. `PyYAML`
используется, если установлен; без него работает встроенный мини-парсер с тем же
поведением. Сеть нужна только для `git` (клоны, `--push`) и одного HTTP-вызова
GitLab API при сверке описания MR. Для сбора значений агенту нужны MCP
Confluence и Grafana — сам скрипт в них не обращается.

## Установка

Три способа: глобально (скилл и команда), в проект целиком (`--project`) и
запуск из клона без установки вообще.

### Глобально: скилл + команда `/criticality_gen`

```bash
# из клона репозитория
cd skills/criticality-gen && ./install.sh

# удалённо (ветка main через GitLab raw API, с проверкой sha256)
curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fcriticality-gen%2Finstall.sh/raw?ref=main" \
  | CRITICALITY_TOKEN="$GITLAB_TOKEN" sh
```

Ставится в `~/.config/opencode/skills/criticality-gen/` и
`~/.config/opencode/commands/criticality_gen.md`; с `--claude` — ещё и в
`~/.claude/skills/criticality-gen/`. Перезапустите сессию opencode, если она уже
открыта.

### В проект: `--project <каталог>`

```bash
# из каталога скилла (skills/criticality-gen или его установленной копии)
./install.sh --project /путь/к/проекту
cd /путь/к/проекту && make init
```

Что разворачивается:

```text
<проект>/.opencode/skills/criticality-gen        копия скилла (маркер .criticality-gen-project)
<проект>/.opencode/commands/criticality_gen.md   команда /criticality_gen
<проект>/.opencode/Makefile                      все цели make
<проект>/Makefile                                корневой фасад на .opencode/Makefile
<проект>/is.example.yaml                         шаблон is.yaml (копия templates/is.example.yaml)
```

Что не перезаписывается: существующий `Makefile`, `.opencode/Makefile` и
`is.example.yaml`, отличающиеся от шаблона, остаются как есть (печатается
`ВНИМАНИЕ`, код 0). Каталог скилла без маркера установки — только с `--force`.
Ставится копией, а не симлинком: проект не зависит от расположения источника,
обновление — повторный запуск установщика.

### Из клона, без установки

```bash
python3 skills/criticality-gen/scripts/criticality.py --root /путь/к/проекту check
python3 skills/criticality-gen/scripts/criticality.py --root /путь/к/проекту start --is erm.mm --diff
```

Корень данных определяется так: `--root <path>` → env `CRITICALITY_ROOT` →
подъём от cwd до первого каталога с `catalog.yaml`/`is.example.yaml`/`.git` →
подъём от каталога скилла. Без `--root` и без признаков проекта — ошибка с
требованием указать корень.

### Флаги и переменные

| Флаг | Что делает |
|------|------------|
| `--project <dir>` | развернуть проект (см. выше); чужое не перезаписывается |
| `--dry-run` | показать полный план, ничего не писать (в обоих режимах) |
| `--uninstall` | удалить поставленное: из `$HOME` — скилл и команду, с `--project` — только своё в проекте |
| `--claude` | дополнительно поставить скилл в `~/.claude/skills/` |
| `--force` | перезаписать чужой каталог/файл (без флага — отказ) |
| `-h`, `--help` | справка |

| Переменная | Смысл |
|------------|-------|
| `OPENCODE_SKILLS_DIR` | каталог скиллов opencode (по умолчанию `$HOME/.config/opencode/skills`) |
| `OPENCODE_COMMANDS_DIR` | каталог команд opencode (по умолчанию `$HOME/.config/opencode/commands`) |
| `CLAUDE_SKILLS_DIR` | каталог скиллов Claude (по умолчанию `$HOME/.claude/skills`) |
| `CRITICALITY_VERSION` | поставить конкретную версию вместо latest (только удалённый режим) |
| `CRITICALITY_TOKEN` | PAT GitLab, приоритет над `GITLAB_TOKEN` |
| `CRITICALITY_HOST` | хост GitLab, по умолчанию `https://git.ecom.tech` |
| `CRITICALITY_SKIP_CHECKSUM` | `1` — пропустить проверку sha256, если её нельзя выполнить |

### Проверка установки и удаление

В проекте с установленным `.opencode/Makefile`:

```bash
make paths        # ROOT (данные) и SKILL_DIR (инструмент)
make validate     # паспорта и реестр: 0 ERROR
```

При глобальной установке `make` в проекте нет — вызывайте скрипт напрямую:

```bash
python3 ~/.config/opencode/skills/criticality-gen/scripts/criticality.py --root . check
```

Удаление — из каталога скилла (без `--project` убирает и глобальную копию):

```bash
./install.sh --uninstall --project /путь/к/проекту
./install.sh --uninstall
```

## Быстрый старт

```bash
./install.sh --project .                     # 1. скилл, команда, Makefile, is.example.yaml
make init                                    # 2. каркас: is.yaml, catalog.yaml, INDEX.md, is/, .gitignore
make scaffold IS=erm.mm                      # 3. папка ИС + записи в catalog.yaml и is.yaml
$EDITOR catalog.yaml                         # 4. владелец, page_id, approve_link, review_date
make prepare                                 # 5. план подготовки данных (dry-run)
make prepare-apply                           # 6. клон SSoT + is/erm.mm/INFORMATION.yaml
make check                                   # 7. гейт: OK или BLOCKED + лист требований
make start IS=erm.mm DIFF=1                  # 8. dry-run: что будет сгенерировано
```

Дальше, после просмотра diff:

```bash
make start-apply IS=erm.mm FORCE=1           # записать паспорт, CRITICALITY.md, actions/
make validate                                # 0 ERROR по паспортам и реестру
make publish IS=erm.mm TASK=E001-31245       # план публикации в dochub
```

Если шаг 7 вернул `BLOCKED`, `start` не запускается — гейт уже создал лист:

```bash
make requirements IS=erm.mm                  # план: что именно нужно
make collect-apply IS=erm.mm                 # RESEARCH-PLAN.md: страницы, дашборды, PromQL
make links-apply IS=erm.mm                   # LINK-MAP.md/.yaml: карта обхода ссылок
# обход по LINK-MAP.md через MCP (Confluence/Grafana) → SOURCES-FINDINGS.yaml
make sources-apply IS=erm.mm                 # принять факты → criteria_inputs (status: confirmed | derived)
make services-apply IS=erm.mm                # SERVICE-FINDINGS.md: цитаты из клонов
make research IS=erm.mm                      # Confluence: RESEARCH.md + CANDIDATES.yaml (direct)
make ask IS=erm.mm                           # ASK.md: вопросы, enum дословно, кандидаты
# сбор по плану: SSoT → Confluence → Grafana (делает человек)
make enrich IS=erm.mm                        # проверить заполненный лист (без записи)
make enrich-apply IS=erm.mm                  # вписать подтверждённые значения
make check                                   # повторить гейт
```

## Канон флоу

```text
init → prepare → check → collect → research → сбор (SSoT → Confluence → Grafana)
     → services → check → ask → ask-answers → enrich-apply → score → start
     → validate (+ verify-titles) → index → publish → ssot → handoff
```

Каждая фаза закрывается только своим гейтом; провал останавливает конвейер.
`make verify` — один прогон всех гейтов (`criteria-check`, `selftest`,
`validate`, `docs-check`, `verify-titles`, `skill-check`) и единственный ответ
на вопрос «всё ли в порядке».
Полное описание фаз, входов и гейтов — [`references/workflow.md`](./references/workflow.md).

Термины разграничены, и это не синонимы:

| Этап | Что это | Куда пишет |
|------|---------|------------|
| `publish` | публикация **паспорта** — MR в **dochub** | клон `dochub/`: паспорт в `architecture/app/...`, импорт в `_root.yaml`, ветка, коммит |
| `ssot` | обогащение **SSoT** — MR с блоком `severity` | клон `ssot/`: только `entities/information-systems/<код>/base.yaml` |
| `handoff` | передача человеку — тред в **`#Criticality_assessment`** | чат: ссылки на dochub-MR и SSoT-MR, подтверждение SRE |

Порядок `publish → ssot → handoff` обязателен: SSoT-MR в «Основании» ссылается
на dochub-MR (`mr.passport_mr_url`), а тред — на оба MR. Обратный порядок оставил
бы SSoT-MR без основания, а тред — без ссылок. «Публикация в
`#Criticality_assessment`» — это всегда `handoff`, а не `publish`.

Боковые этапы вне линейного конвейера: `scaffold`, `index`, `due`, `reassess`,
`exclude`/`include`.

## Команды

33 подкоманды `scripts/criticality.py`. Колонка «изменяет файлы» — пишет ли
команда в проект; «сеть» — нужен ли git или внешний доступ. Полный синтаксис и
все флаги — [`references/commands.md`](./references/commands.md).

| Команда | Что делает | Изменяет файлы | Сеть |
|---------|-----------|----------------|------|
| `help` | справка: подкоманды, воркфлоу, артефакты, состояние ИС | нет | нет |
| `info` | критерии с пояснениями (уровни, сценарии, входы, enum, матрицы) | нет | нет |
| `init` | каркас проекта: `is.yaml`, `catalog.yaml`, `INDEX.md`, папку `is/` | да | нет |
| `next-step` | следующий шаг конвейера по текущему состоянию (`make next-step`) | нет | нет |
| `prepare` | `ssot/` → `INFORMATION.yaml` → `apps/` (dry-run по умолчанию) | да (`--apply`) | да |
| `contacts` | контакты TA/TL из SSoT `team.yaml` (упоминания — полный username RocketChat) | да (`--apply`) | нет |
| `validate` | паспорта, `catalog.yaml`, `CRITICALITY.md`; просрочка по `review_date` | нет | нет |
| `verify-titles` | сверка заголовков страниц Confluence с сохранёнными (`--fix`) | да (`--fix`) | да |
| `index` | таблица `INDEX.md` (без `--write` — в stdout) | да (`--write`) | нет |
| `due` | просроченные, ближайшие и неоценённые переоценки | нет | нет |
| `scaffold` | папка `is/<код>/`, запись в `catalog.yaml` и код в `is.yaml` | да | нет |
| `reassess` | переоценка: план или файл `reassessment-<дата>.md` + `review_date` | да (`--apply`) | нет |
| `show` | все поля паспорта и ссылки по одной ИС | нет | нет |
| `score` | детерминированный расчёт критичности | нет | нет |
| `criteria` | `show` / `check` / `sync-docs` — файл критериев и таблицы `docs/02` | да (`sync-docs`) | нет |
| `check` | гейт достаточности данных (strict по умолчанию) | да (`DATA-REQUIREMENTS.*`) | нет |
| `requirements` | лист недостающих данных `DATA-REQUIREMENTS.*` (dry-run по умолчанию) | да (`--apply`) | нет |
| `ask` | интерактивный сбор недостающих входов: `ASK.md`, `--answers` → лист | да (`--apply`/`--answers`) | нет |
| `enrich` | принять заполненный `DATA-REQUIREMENTS.yaml` в `INFORMATION.yaml` | да (`--apply`) | нет |
| `collect` | план сбора `RESEARCH-PLAN.md` (Confluence, Grafana, PromQL) | да (`--apply`) | нет |
| `research` | сбор доказательств по открытым входам (Confluence) | да (`--apply`) | да |
| `links` | карта обхода ссылок `LINK-MAP.md`/`.yaml` (SSoT `links.yaml`, `catalog.yaml`, компоненты) | да (`--apply`) | нет |
| `sources` | принять `SOURCES-FINDINGS.yaml` → `criteria_inputs` (`status` из findings: `confirmed`/`derived`) | да (`--apply`) | нет |
| `services` | клоны сервисов + `docs/`/`openspec/` → `SERVICE-FINDINGS.md` | да (`--apply`) | да (git) |
| `exclude` | исключить ИС из расчёта (`excluded: true` + `reason`) | да | нет |
| `include` | вернуть исключённую ИС в расчёт | да | нет |
| `start` | паспорт, `CRITICALITY.md`, `GENERATION.md`, `actions/*` | да (`--force`) | нет |
| `publish` | паспорт в dochub: файл, `_root.yaml`, ветка, коммит, MR | да (`--apply`) | да (`--push`) |
| `ssot` | `severity` в SSoT (после `publish`): `base.yaml`, ветка, коммит, MR | да (`--apply`) | да (`--push`) |
| `handoff` | тред в `#Criticality_assessment`: вопрос, MCP (основной) → REST-фолбэк, дедупликация по `roomId` | да (`--write`: предпросмотр) | да |
| `handoff-result` | результат MCP-отправки: ссылка на сообщение или причина отказа | да | нет |
| `handoff-apply` | тонкая обёртка REST-отправки (нужен `--confirm`; идемпотентность общая с `handoff`) | да | да |
| `finalize` | подтверждение одной командой: `approve_link`, даты, критичность, `status: confirmed` + гейты | да (`--dry-run`) | нет |

Общие флаги: `--root <path>`, `--no-next`/`--quiet` (не печатать подсказку
следующего шага), `--debug` (traceback вместо короткой строки `ERROR`).
Коды возврата: `0` — успех, `1` — `BLOCKED`/`ERROR`/`incomplete`, `2` — ошибка
аргументов (например `--push` без `--apply`); `make` отдаёт `2` при любом
ненулевом коде цели. `check --diagnostic` (`make check-diag`) печатает `BLOCKED`,
но возвращает `0` — только для отладки, не для конвейера.

### Make-цели по задачам

| Задача | Цели |
|--------|------|
| Начать проект | `make init`, `make scaffold IS=<код>`, `make contacts IS=<код>`, `make next-step`, `make help`, `make help-fast` |
| Подготовить данные | `make prepare`, `make prepare-apply`, `make check-prepare` |
| Проверить | `make check`, `make check-diag`, `make validate`, `make verify-titles`, `make verify`, `make criteria-check`, `make docs-check`, `make selftest` |
| Разобрать `BLOCKED` | `make requirements`, `make collect`/`collect-apply`, `make research`, `make services`/`services-apply`, `make ask`/`ask-apply`/`ask-answers`, `make enrich`/`enrich-apply` |
| Посчитать и записать | `make score`, `make start IS=<код> DIFF=1`, `make start-apply IS=<код> FORCE=1` |
| Опубликовать | `make publish`/`publish-apply`, `make ssot`/`ssot-apply`, `make ssot-mr`/`ssot-mr-apply` |
| Передать в тред (последний этап) | `make handoff IS=<код>` (MCP, при отказе — REST), `make handoff-result IS=<код> MESSAGE_URL=<ссылка>`, `make handoff-apply IS=<код> CONFIRM=1` (только REST), затем `make finalize IS=<код>` |
| Ведение реестра | `make index`, `make due`, `make show IS=<код>`, `make reassess`/`reassess-apply`, `make exclude`/`include` |
| Сам скилл | `make paths`, `make skill-check`, `make skill-install TARGET=<путь>`, `make skill-uninstall TARGET=<путь>` |

Значимые переменные: `IS=`, `FORCE=1`, `DATE=`, `NO_CLONE=1`, `DRY=0`, `DIFF=1`,
`APPLY=1`, `PUSH=1`, `REUSE=1`, `TASK=`, `UPDATE=1`, `NO_REQUIREMENTS=1`,
`CONFIRM=1` (публикация в тред), `WRITE=1` (предпросмотр `handoff`),
`ALLOW_INCOMPLETE=1` (публикация с `⛔`).

## Два сценария оценки

| Сценарий | Метод | Обязательные входы | Когда |
|----------|-------|--------------------|-------|
| Простой | `express` | 4: `peak_hour_load`, `consumers_type`, `outage_impact`, `object_sla` | экспресс-оценка по калькулятору критичности |
| Сложный | `detailed` | 7: те же 4 + `time_to_impact`, `axes_scores`, `cia` | детальная оценка по осям и CIA |

Сценарий выбирается **по данным, а не флагом**: если хотя бы один вход только
сложного набора (`time_to_impact`, `axes_scores`, `cia`) непуст — сценарий
сложный. Иначе — простой. Правило дословно — `scenarios.selection.rule` в
[`criteria/criticality-criteria.yaml`](./criteria/criticality-criteria.yaml);
печатается `make info SECTION=scenarios`.

- **Фолбэк запрещён.** Неполный сложный набор — `BLOCKED`, а не простой сценарий.
  Заполнение advisory-входа (`axes_scores`, `cia`) переключает ИС на сложный
  сценарий и требует `time_to_impact`; лист требований предупреждает об этом
  (`switches_scenario`).
- **Blocking-вход готов**, когда значение есть **и** `status` не `missing`.
  Отсутствие входа вне blocking-набора сценария не блокирует — только `WARN`.
- **Итог — из `final_matrix`.** Уровень берётся из ячейки
  `final_matrix.cells[бизнес-уровень][уровень защищённости]`; правило
  `max(бизнес, ИБ)` не применяется (в трёх ячейках строки `Office productivity`
  матрица ниже максимума). Границы CIA рендерятся из `cia.thresholds`, уровни и
  маппинг SSoT — из `levels`.

## Провенанс и `BLOCKED`

Каждое непустое значение в `INFORMATION.yaml` несёт `source: {type, ref}` и
`status` ∈ `missing | derived | confirmed`. Тип источника — из закрытого списка:
`ssot`, `is_yaml_override`, `catalog`, `confluence`, `gitlab`, `jira`, `grafana`,
`attachment`, `ssot_links`, `manual`. Значение без источника — `null` + `status: missing`; слов «примерно»,
«обычно», «скорее всего» в артефактах не бывает.

При `BLOCKED`:

1. `check`/`start` пишут `is/<код>/DATA-REQUIREMENTS.md` (человеку) и
   `DATA-REQUIREMENTS.yaml` (для заполнения): «что это → зачем → где взять → у
   кого → как подтвердить» + готовый фрагмент `criteria_inputs`.
2. `collect` пишет `RESEARCH-PLAN.md`: какие страницы Confluence открыть (с
   `page_id`), какие дашборды и запросы PromQL выполнить, кто подтверждает.
3. `links` пишет `LINK-MAP.md` + `LINK-MAP.yaml`: все ссылки ИС (SSoT
   `links.yaml`, `page_id` из `catalog.yaml`, компоненты) с классификацией
   `confluence`/`grafana`/`gitlab`/`jira`/`external`, `id`, `expand` и
   `candidate_for`; в сеть не ходит. Обход по карте делает MCP-агент
   (Confluence/Grafana) и заполняет `SOURCES-FINDINGS.yaml`; `sources-apply`
   принимает факты теми же валидаторами, что гейт, и пишет их в
   `INFORMATION.yaml` (статус — из `findings[].status`: `confirmed` или
   `derived`; единица — из `findings[].unit`, если допустима по критериям;
   отклонение — код 1). Затем статусы узлов `LINK-MAP.yaml` обновляются, а
   `LINK-MAP.md` перерисовывается из того же состояния.
4. `services` пишет `SERVICE-FINDINGS.md` с цитатами «файл:строка» из `docs/` и
   `openspec/` клонов — это основание, а не значение.
5. Человек заполняет лист; `enrich` принимает только `value` + `source` +
   `status: confirmed` и только значение из допустимого множества. Любая ошибка —
   код 1, `INFORMATION.yaml` не меняется ни на байт.
6. `enrich-apply` вписывает секцию `criteria_inputs`, остальные секции
   сохраняются дословно; затем `check` повторяется.

**`check` не затирает заполненный лист.** Значения сливаются (`value`, `source`,
`status`, `bucket`/`unit`/`notes`), вычисляемые `switches_scenario` /
`scenario_note` пересчитываются по критериям. Заполнять лист можно до, между и
после прогонов `check`. Лист производен от `INFORMATION.yaml`: поле, уже
закрытое (значение + `status: confirmed`/`derived`/`legacy`), в лист не
попадает — принятое значение исчезает, ручное непринятое остаётся. Если рендер
теряет заполненные значения, файл не перезаписывается: пишется `.new`, код
возврата ненулевой. Read-only прогон без касания листа — `NO_REQUIREMENTS=1`.

Данных нет совсем — ИС исключается, а не заполняется догадкой:
`make exclude IS=<код> REASON="..."` (общее решение —
`EXCLUDE_SCOPE=catalog`; обратно — `make include IS=<код>`). Вердикт `SKIPPED` не
считается `BLOCKED`.

## Артефакты

В папке ИС `is/<код>/`:

| Артефакт | Класс | Кто создаёт |
|----------|-------|-------------|
| `INFORMATION.yaml` | вход (ручной слой) | `prepare --apply` — автосекции; человек — `criteria_inputs`, `facts`, `conflicts`, `notes` |
| `criticality-passport.yaml` | производный | `start` (перезапись только с `--force`) |
| `CRITICALITY.md` | производный | `start` (перезапись только с `--force`) |
| `GENERATION.md` | производный | `start` |
| `actions/{jira-task,confluence-page,rocketchat-message}.md` | производный | `start` |
| `DATA-REQUIREMENTS.md` / `.yaml` | производный | `check`/`start` при `BLOCKED`, `requirements --apply` |
| `RESEARCH-PLAN.md` | производный | `collect --apply` |
| `LINK-MAP.md` / `LINK-MAP.yaml` | производный | `links --apply` |
| `SOURCES-FINDINGS.yaml` | ручной ввод | MCP-агент по `LINK-MAP.md` (принимает `sources --apply`) |
| `SERVICE-FINDINGS.md` | производный | `services --apply` |
| `reassessment-YYYY-MM-DD.md` | производный | `reassess --apply` |

В корне проекта: `is.yaml` (локальный конфиг, gitignored), `catalog.yaml`
(реестр ИС, версионируется), `INDEX.md` (сводная таблица), `is.example.yaml`
(шаблон), клоны `ssot/`, `apps/`, `dochub/` (gitignored). В клонах:
`.publish/<код>-MR.md` — описание dochub-MR, `.ssot/<код>-MR.md` — описание
SSoT-MR. `INFORMATION.yaml` — версионируемый слой ручных данных: он
**коммитится в git**; `ssot/`, `apps/`, `is.yaml` — нет.

Полный реестр с политиками перезаписи — [`references/artifacts.md`](./references/artifacts.md).

## Публикация

`publish` — паспорт в dochub. Пишет `architecture/app/<контур>/<сущность>/criticality_passport.yaml`,
добавляет импорт в `_root.yaml` один раз, создаёт ветку `feature/<task>` (или
`feature/<task>-<контур>`) от `origin/master` и коммит ровно из двух файлов.
Уровень переводится в enum dochub по `levels.publish_enum` критериев, а не по
зашитому списку. `is/`, `catalog.yaml` и `criteria_inputs` публикация не меняет.

`ssot` — критичность в SSoT. Правит **только** блок `severity` в
`entities/information-systems/<код>/base.yaml`: `type` — из `levels.ssot_enum`
(`Office productivity` → `business-operational`), `confirmation` — из
`catalog.yaml → approve_link`. Остальные ключи, их порядок, комментарии и
форматирование сохраняются побайтово. Расхождений нет — `изменений нет`, ветка и
коммит не создаются.

`handoff` — последний этап: сообщение в `#Criticality_assessment` со ссылками на
оба MR, подтверждение SRE, карточка SSoT, дата следующей переоценки.

**Гейт подтверждения.** `make handoff IS=<код> SEND=auto` собирает финальный
текст в момент вызова (паспорт, `catalog.yaml`, `.publish`/`.ssot`,
`INFORMATION.yaml` → `facts`/`notes`) и спрашивает: «Публиковать это сообщение в
треде или что-то нужно исправить?». Отправка — по явному согласию: MCP
(основной канал), при отказе — REST; всегда ОДНИМ сообщением, разбиение на части
запрещено. `make handoff-apply IS=<код> CONFIRM=1` — тонкая обёртка того же пути
только по REST (запуск без MCP). Правки вносятся в источники
(`INFORMATION.yaml`, `catalog.yaml`, критерии), а не в текст сообщения. Текст с
`⛔ не заполнено` не публикуется без `--allow-incomplete`. После отправки в
`catalog.yaml` пишутся `handoff_status: published`, `thread_link`,
`approve_link`, `transport_used`; повтор запрещён (`--force-resend` — осознанный
повтор), а перед POST ищется своё сообщение в канале. Дальше —
`make finalize IS=<код>`.

Строгие правила MR:

- описания рендерятся только по `templates/MR-dochub.md` и
  `templates/MR-ssot.md`; незаполненная переменная — ошибка, а не пустая строка
  в MR (`or_missing`/`default` запрещены);
- в «Основание» SSoT-MR входит кликабельная ссылка на dochub-MR
  (`mr.passport_mr_url`); ссылки нет — `ERROR: не заполнено поле
  'mr.passport_mr_url'`, MR не создаётся;
- `--push` допустим только вместе с `--apply` (иначе код 2) и только по явному
  подтверждению человека;
- ветка уже существует — `publish-apply ... UPDATE=1`; описание уже созданного
  SSoT-MR переписывается `make ssot-mr-apply IS=<код> TASK=<key>` без изменения
  ветки и коммита;
- ветка есть **только локально** (на `origin` её нет) — `publish-apply ...
  REUSE=1` (`--reuse-local`): содержимое не изменилось → `unchanged` и код 0
  без коммита, изменилось → коммит поверх локальной ветки. С `--update`
  несовместим;
- репозиторий dochub для `git clone` берётся по порядку: `--dochub-url` →
  `catalog.yaml → dochub_url` (или вложенный `dochub.url`) →
  `criteria.dochub.url`. URL не сконфигурирован — подсказка добавить
  `dochub_url` в `catalog.yaml`, а не «клон не найден».

**Гейт `entities/**`.** Путь `feature/<task>` (в том числе `make ssot-apply`)
не проходит джоб `codeowners`: апрув дают только боты `project_14598_bot_*`,
а они апрувят лишь MR, созданные через SSoT-UI. Штатный путь записи severity —
UI / MCP `ssot` (`ssot_form_save` → апрувы → `ssot_apply_changes`). Git-путь
остаётся fallback'ом и требует `@codeowners approve` от maintainer'а проекта
(access level ≥ 40) отдельным комментарием. Подробно — «Запись severity: два
пути» в `references/data-sources.md`.

### Jira-ключ и ссылка на задачу

`TASK=<ключ>` (`--task`) — ключ задачи по оценке критичности; обязателен для
`publish`/`ssot`, из него строится ветка `feature/<task>`. По умолчанию ключ
берётся из данных проекта: `catalog.yaml → systems[].jira_task` (прежнее имя
ключа — `task`) или `is.yaml → jira_task`.

Тот же ключ `start` кладёт в action-пакеты: `actions.task_key` и
`actions.task_link` = `<criteria.external_refs.jira_browse_base>/browse/<ключ>`.
Нет `jira_task` — оба поля `None`, шаблон печатает `⛔ не заполнено` (честный
пробел, а не догадка); база не задана — ссылки нет, номер задачи остаётся.
`jira_task` — необязательное поле реестра: добавляется ручной правкой
`catalog.yaml` (после правки — `make validate`).

## Ограничения и известные особенности

- **SSoT обогащается точечно.** Только `severity.type` и `severity.confirmation`
  в `base.yaml`. Поля `review_date`, `assigned_date`, `tech_architect` в SSoT
  отсутствуют — их туда не добавляют: они живут в `catalog.yaml` и Confluence.
- **`review_date` — из реестра.** Дата переоценки считается по
  `catalog.yaml → review_date`; копия в паспорте вторична, иначе дата генерации
  маскировала бы просрочку. Обновляет только `make reassess-apply IS=<код>`.
- **`peak_hour_load` требует методики замера.** Это `peak_rps × 3600` по
  панели Grafana с окном 7d/30d; без дашборда и запроса значение не выводится —
  `null` и лист требований.
- **`lifecycle: closed` не клонируется.** Выведенный из эксплуатации сервис
  (`criteria.service_lifecycle.skip`) не анализируется и не служит основанием для
  входов; пропущенные перечислены в `SERVICE-FINDINGS.md` §2.
- **Сборка и запуск клонов запрещены.** В `apps/` разрешён только `git` из
  allowlist (`clone`, `pull`, `fetch`, `rev-parse`, `log`, `status`, `show`,
  `diff`, `ls-remote`); `checkout`/`reset`/`clean` отклоняются до запуска
  процесса.
- **`catalog.yaml → status` (`draft` / `confirmed`) ставит SRE**, скилл его не
  меняет. Перевод ИС в development — организационное действие после подтверждения
  паспорта, а не шаг конвейера.
- **Оценки осей и CIA — экспертное решение.** Из документов они не выводятся:
  в источниках есть итоговый уровень, но нет разбивки по осям и отметок C/I/A.

## Документация

| Где | Что | Объём |
|-----|-----|-------|
| [`docs/`](./docs/README.md) | инженерная документация инструмента: процесс, методика, поля, пайплайн, шаблоны, CLI, установка | 14 файлов |
| [`references/`](./references/workflow.md) | справочники для агента: workflow, commands, rules, artifacts, data-sources, dependencies, failure-modes, checklist | 8 файлов |
| [`templates/`](./templates/criticality-passport.yaml) | тексты артефактов: паспорт, `CRITICALITY.md`, `GENERATION.md`, листы, планы, MR, `actions/` | 18 файлов |
| [`criteria/`](./criteria/criticality-criteria.yaml) | единственный источник правил расчёта | 1 файл |

**Пользовательская документация ведётся в Confluence**, а не здесь: методика
D6.1.1 — [страница 4552328348](https://space.samokat.ru/pages/viewpage.action?pageId=4552328348).
`docs/` в скилле — для разработки и поддержки инструмента: как он устроен, как
его ставить, что делать при сбое.

Ключевые точки входа:

- [`SKILL.md`](./SKILL.md) — что читает агент: пути, команды, восемь инвариантов.
- [`references/workflow.md`](./references/workflow.md) — фазы 0–10, входы, выходы, гейты.
- [`references/commands.md`](./references/commands.md) — синтаксис, все флаги, коды возврата.
- [`references/rules.md`](./references/rules.md) — правила R1–R16.
- [`references/failure-modes.md`](./references/failure-modes.md) — симптом → причина → действие.

## Разработка и релиз

```bash
python3 ../../ci/validate-skill.py            # frontmatter всех skills/*/SKILL.md
python3 scripts/criticality.py info           # критерии читаются
sh -n install.sh                              # синтаксис установщика
python3 scripts/criticality.py score --selftest  # самопроверки (клон, --project, глобальная установка)
bash scripts/release.sh --dry-run             # план сборки бандла
```

Релиз:

1. Поднять версию в трёх местах: `VERSION`, `version:` в `SKILL.md`,
   `CHANGELOG.md` (значимое — ещё и в корневой `RELEASE-NOTES.md`).
   `scripts/release.sh` сверяет `VERSION` и `version:` в `SKILL.md` и падает при
   расхождении.
2. `bash scripts/release.sh` — собирает `dist/release/criticality-gen.tar.gz`,
   копирует `install.sh`, считает `checksums-sha256.txt`.
3. Коммит и мерж в `main`: тег `skills/criticality-gen/v<version>` создаст
   джоба `publish-release` (запускается вручную в push-пайплайне `main`).
4. В MR обязательна зелёная джоба `validate-skills`.

В бандл входят `SKILL.md`, `README.md`, `VERSION`, `CHANGELOG.md`, `criteria/`,
`templates/`, `references/`, `docs/`, `scripts/`, `commands/`, `project/` и
`install.sh`; `meta-templates/` (authoring-шаблоны) — не входят.

## Диагностика

| Симптом | Причина | Что делать |
|---------|---------|------------|
| `check` → `BLOCKED`, данных нет | нет blocking-входа сценария | лист уже создан: `make requirements IS=<код>` → `make collect-apply IS=<код>` → сбор → `make enrich-apply IS=<код>` → `make check`; если взять негде — `make exclude IS=<код> REASON="..."` |
| `ssot` → `ERROR: не заполнено поле 'mr.passport_mr_url'` | паспорт ещё не опубликован в dochub | сначала `make publish-apply IS=<код> TASK=<key> PUSH=1`, затем `make ssot-apply` |
| `publish-apply` → «ветка уже существует» | ветка MR создана прошлым прогоном | `make publish-apply IS=<код> TASK=<key> UPDATE=1` |
| `publish-apply` → «ветка есть локально, но не на origin» | прошлый прогон создал ветку без push | `make publish-apply IS=<код> TASK=<key> REUSE=1` (`--reuse-local`): без изменений — `unchanged` и код 0, с изменениями — коммит поверх локальной ветки |
| `publish` → «URL репозитория не сконфигурирован» | нет клона `dochub/` и не задан URL | добавить `dochub_url` в `catalog.yaml` (или `--dochub-url <URL>`, `criteria.dochub.url`) |
| `prepare-apply` → `ERROR: нет клона SSoT (ssot/)` | нет доступа, нет `ssot.url` или задан `NO_CLONE=1` | проверить `is.yaml → ssot.url` и доступ по ssh; внешний клон — `make ssot ... SSOT=<путь>` |
| `docs-check` → `WARN` без ошибки | в проекте нет `docs/` | ничего не делать: проверка пропускается с кодом 0 |
| `install.sh --project` не перезаписал `Makefile` | файл существует и отличается от шаблона | это защита от чужого файла: сравните вручную или `--force` |
| `selftest` → `SKIP` на проверках `P*` / `D5` | проверка требует данных проекта (полного паспорта в `is/`, `.opencode/Makefile`), а их нет: клон репозитория, глобальная установка, пустой проект | ничего не делать: это `SKIP` с причиной, а не `FAIL`. Полный набор проверок — в проекте, развёрнутом через `--project` и с паспортом |

Больше симптомов и точных сообщений — [`references/failure-modes.md`](./references/failure-modes.md).

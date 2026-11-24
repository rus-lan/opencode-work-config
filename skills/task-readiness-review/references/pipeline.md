# Конвейер этапов: вход, выход, гейты

Справочник по этапам 5.1–6 скилла `task-readiness-review`: что делает агент, что делает Python, какой
артефакт появляется на диске и по какому условию этап считается пройденным. Нормативный источник —
`CONTRACT.md` §2, §4, §6, §7; полный справочник путей и полей — `artifacts.md`; перечень правил проверки —
`validation-rules.md`; источники данных и деградация MCP → REST — `sources-fallback.md`.

## 0. Как читать этот документ

- **Этап = подкоманда.** Восемь этапов, восемь подкоманд одной команды `/task-readiness-review`.
  Исключение — `check`: одна подкоманда `/task-readiness-review check`, внутри три подшага (5.4.1–5.4.3),
  у каждого своя зона ответственности. Инструкции по подкомандам — `../commands/task-readiness-review.md`.
- **Каждый блок одинаковый:** команда → предусловия → вход → что делает агент → что делает скрипт →
  выход → гейт → идемпотентность. Порядок полей не меняется, чтобы блоки можно было сравнивать глазами.
- **Все пути — относительно корня проекта** (`--root`, алиас `--workdir`; по умолчанию — поиск
  `task-readiness-review.yaml` вверх по дереву, затем текущая директория). Пути внутри скилла помечены явно
  (`<skill>/…`).
- **Скрипт** — это `<skill>/scripts/trr <подкоманда>` (или `python3 -m trr_impl <подкоманда>` из каталога
  `scripts/`). Сеть из Python не ходит никогда: всё сетевое делает агент, Python читает уже положенные файлы.
- **Коды выхода** одни на все подкоманды:

| Код | Имя | Когда |
|---|---|---|
| `0` | OK | успех, в том числе `WARN` |
| `2` | BLOCKED | гейт не пройден: нет данных, нет модели, нет предыдущего прогона |
| `3` | CONFIG_ERROR | конфиг отсутствует, не разбирается, нарушает схему, содержит секрет |
| `4` | MISSING_ARTIFACT | нет обязательного файла-артефакта |
| `5` | SCHEMA_ERROR | артефакт есть, но не соответствует схеме |

Приоритет при нескольких проблемах: `3` → `4` → `5` → `2`.

- **Формат диагностики.** Одна строка на проверку, без ведущих пробелов и цветов. `[MISSING]` и
  `[BLOCKED]` обязаны содержать, что сделать, после `—`:

```
[OK] config: task-readiness-review.yaml
[OK] model: version 3, sha256:ab12…
[WARN] bucket BA/implementation: n=2 < min_sample_n=5 — confidence=low
[MISSING] .task-readiness/model/estimation-model.json — запустите /task-readiness-review train
[BLOCKED] check: нет context.json задачи E001-1234 — соберите снимок задачи в …/runs/E001-1234/<RUN-ID>/context.json
```

## 1. Схема потока

```
                    ┌───────────────┐
                    │ 5.1  install  │
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐  нет ≥1 эталона или ≥1 спринта
                    │ 5.2   init    ├────────────────────────────► BLOCKED (exit 2)
                    └───────┬───────┘                              + .task-readiness/DATA-REQUIREMENTS.md
                            ▼ stage=configured
                    ┌───────────────┐  модель уже обучена и входы не менялись
                    │ 5.3   train   ├────────────────────────────► шаг пропускается,
                    └───────┬───────┘                              модель переиспользуется
                            ▼ stage=trained, state.model_page ≠ null
                    ┌───────────────┐  нет model/estimation-model.json
                    │ 5.4   check   ├────────────────────────────► BLOCKED (exit 2)
                    │ 5.4.1 Jira    │  или state.model_page = null   «модель оценки не обучена»
                    │ 5.4.2 evidence│                                (запустите /task-readiness-review train)
                    │ 5.4.3 rules   │
                    └───────┬───────┘
                            ▼ stage=checked
                    ┌───────────────┐  нет validation.json в прогоне
                    │ 5.4.4 + 5.5   ├────────────────────────────► BLOCKED (exit 2)
                    │   estimate    │                                «сначала /task-readiness-review check»
                    └───────┬───────┘
                            ▼ stage=estimated
              ┌─────────────┴───────────────┐
              ▼                             ▼
      ┌───────────────┐             ┌───────────────┐
      │ 5.6  refresh  │             │ 5.7   enrich  │
      │ новый RUN-ID  │             │ version+1 *   │
      └───────┬───────┘             └───────┬───────┘
              │ delta.md                    │ stage→trained (reason="enrich")
              │                             │ * только если входы изменились
              └─────────────┬───────────────┘
                            ▼
                    ┌───────────────┐  MCP недоступен
                    │ 6   publish   ├────────────────────────────► WARN (exit 0)
                    └───────────────┘                              + actions/<target>-page.md
```

Ветвления, которые важно помнить:

- **`train` не нужно повторять на каждый прогон.** Модель строится один раз; `check`/`estimate` читают
  `model/estimation-model.json` и `state.model_page`. Повторный `train` на неизменных входах — не ошибка,
  но и не новый результат (см. идемпотентность 5.3).
- **`check` без модели запрещён гейтом** — это не «мягкое» предупреждение: вердикт `BLOCKED`, код 2.
- **`refresh` и `enrich` — опциональные ветки.** `refresh` нужен, когда задача изменилась после проверки;
  `enrich` — когда появились новые данные для обучения (спринт, правка эталона, уточнённая роль).
- **`publish` по умолчанию публикует комментарий в задачу** (`comment_mode: post`): отчёт уходит в саму
  задачу, повторный запуск обновляет тот же комментарий. `output.target: none` отключает только
  **дополнительную** страницу/заметку — публикация в Confluence/Obsidian идёт лишь при явно заполненном
  `output.target`.

### 1.1 Переходы `stage`

| Переход | Кто двигает | Условие |
|---|---|---|
| `installed → configured` | `trr init` | конфиг создан и валиден, `state.json` записан |
| `configured → trained` | `trr calibrate` | модель построена, `state.model_checksum` записан |
| `trained → checked` | `trr check` | `validation.json` записан, прогон добавлен в `state.runs` |
| `checked → estimated` | `trr estimate` | `estimate.json` записан |
| `estimated → published` | `publish` | результат опубликован комментарием в задачу (и/или дополнительно по `output.target`) |
| `checked/estimated/published → trained` | `trr calibrate` | **только** `reason="enrich"` (перепубликация страницы модели) |

Любой другой откат этапа — `StateError`. Ручной `trr state set stage …` обходит проверку цепочки, поэтому
этап выставляют модули (`calibrate.py`, `check.py`, `estimate.py`), а не человек.

## 2. Этап 5.1 — install

**Команда:** `/task-readiness-review install`

**Предусловия**

- Доступ к репозиторию `e001-ai-hub` (режим `local`) или к релизу `skills/task-readiness-review/v<version>`
  в GitLab (режим `remote`).
- В окружении есть `sh`, `tar`, а также `sha256sum` или `shasum` (для проверки контрольной суммы в remote).
- Каталог назначения известен: по умолчанию `$HOME/.config/opencode/skills` (и
  `$HOME/.claude/skills` дополнительно с `--claude`), с `--project <dir>` — `<dir>/.opencode/skills`,
  с `--dir <path>` — ровно `<path>`. Каталог создаётся только при реальной установке.

**Вход**

- `install.sh` (POSIX `sh`, пайпится в `sh` при удалённой установке).
- `BUNDLE_ITEMS="SKILL.md README.md VERSION references scripts templates schemas commands task-readiness-review.example.yaml"`
  — ровно этот список, общий с `scripts/release.sh`. `templates/`, `schemas/`, `commands/` и пример конфига
  обязательны: `check` читает из `templates/` шаблон описания задачи, `calibrate` рендерит страницу модели по
  `templates/model-page.md`, `schema_lite` валидирует артефакты по `schemas/*.json`, `install.sh` ставит
  слэш-команды из `commands/`, а `init` копирует `task-readiness-review.example.yaml`. Без них установленная
  из релиза копия ломается на первом же этапе.
- Переменные: `OPENCODE_SKILLS_DIR`, `OPENCODE_COMMAND_DIR` (алиас `OPENCODE_COMMANDS_DIR`),
  `CLAUDE_SKILLS_DIR`, `TASK_READINESS_REVIEW_VERSION`, `TASK_READINESS_REVIEW_TOKEN` (приоритет) →
  `GITLAB_TOKEN`, `TASK_READINESS_REVIEW_HOST`, `TASK_READINESS_REVIEW_SKIP_CHECKSUM`.
- Флаги режима назначения: `--global` (по умолчанию), `--project <dir>`/`--project=<dir>`,
  `--dir <path>`/`--dir=<path>`; служебные — `--dry-run`, `--uninstall`, `--force`, `--claude`,
  `--no-commands`, `--local`, `--version`, `--sha256`, `--insecure-host`.

**Что делает агент**

1. Определяет режим источника: рядом с `$0` есть `SKILL.md` **и** `VERSION` → local, иначе remote.
2. Запускает установку: `./install.sh [--project <dir>|--dir <path>|--global]` (local) либо
   `curl -fsSL <host>/…/install.sh | sh -s -- …` (remote). Перед реальной установкой полезен `--dry-run`.
3. Проверяет маркер владения в целевом каталоге: `.task-readiness-review-installed` (глобально и `--dir`)
   либо `.task-readiness-review-project` (в проекте). Команда `/task-readiness-review` лежит в
   `<command-dir>/task-readiness-review.md` и помечена комментарием в конце файла.
4. Запускает `<skills-dir>/task-readiness-review/scripts/trr selftest` — парсер YAML, 10 схем,
   канонический JSON, цепочка этапов. Провал `selftest` — сигнал, что установился битый бандл.

**Что делает скрипт**

`install.sh` (не `trr`): проверяет наличие элементов `BUNDLE_ITEMS` до установки, в remote-режиме
скачивает tarball, сверяет sha256 с `checksums-sha256.txt`, распаковывает, повторно проверяет
`BUNDLE_ITEMS`, копирует элементы в целевой каталог и ставит маркер.

**Выход**

- `<skills-dir>/task-readiness-review/` — `SKILL.md`, `README.md`, `VERSION`, `references/`, `scripts/`,
  `templates/`, `schemas/`, `commands/`, `task-readiness-review.example.yaml`.
- `<skills-dir>/task-readiness-review/.task-readiness-review-installed` — маркер владения каталогом
  (проектная установка — `.task-readiness-review-project`).
- `<command-dir>/task-readiness-review.md` — единственная слэш-команда: глобально
  `~/.config/opencode/command/`, в проекте `<dir>/.opencode/commands/`, при `--dir <path>` —
  `<path>/../command/`.

**Гейт**

- Нет `SKILL.md`, `VERSION` или любого элемента `BUNDLE_ITEMS` в источнике → отказ до копирования, `exit 1`.
- Реальное несовпадение sha256 → фатально **всегда**, `TASK_READINESS_REVIEW_SKIP_CHECKSUM=1` его не снимает
  (флаг понижает до предупреждения только *невозможность* проверки: нет утилиты, не скачался файл сумм,
  нет записи).
- Целевой каталог существует и не содержит маркера → отказ без `--force` (чужой каталог не перезаписываем).
- Неизвестный флаг → `exit 2`.

**Идемпотентность**

Повторный запуск — это обновление: каталог с маркером перезаписывается без `--force`. `--dry-run` печатает
план и не пишет ничего (ни глобально, ни в проект: каталог проекта в dry-run не создаётся).
`--uninstall` удаляет только артефакты с маркером (каталог скилла и файл команды), чужие оставляет и
сообщает: «существует, но не похож на установленный install.sh — оставляю как есть».

## 3. Этап 5.2 — init

**Команда:** `/task-readiness-review init`

**Предусловия**

- Скилл установлен (`<skill>/task-readiness-review.example.yaml`, `schemas/` на месте).
- Есть доступ хотя бы к одной системе с источниками: Confluence (эталон SP) и Jira (спринты). Доступ
  проверяется пробным чтением, а не «на словах» — см. `sources-fallback.md`.
- Пользователь ответил, где лежит эталон и какие спринты брать (или это уже записано в конфиге).

**Вход**

- `<skill>/task-readiness-review.example.yaml` — шаблон конфига.
- Ответы пользователя: page_id/URL эталона, `board_id` и `sprint_ids`, проект Jira, при необходимости —
  свой `role_map`.
- `sources.reference` / `sources.sprints` — структура **или** свободный текст (схема 1.1 допускает оба
  варианта; свободный текст резолвит ИИ на этом же этапе).

**Что делает агент**

1. Запускает `trr init --non-interactive` — получает `task-readiness-review.yaml` и `state.json`
   (`stage=configured`).
2. Читает конфиг и определяет, что требует резолва: свободный текст в `sources.*`, пустые источники,
   неоднозначные названия.
3. Резолвит эталон через Confluence: `confluence_search` (CQL по заголовку) или `confluence_get_page`
   по `page_id`; при недоступности MCP — REST (`sources-fallback.md`).
4. Резолвит спринты через Jira: `jira_get_sprints_from_board(board_id, state="closed")`, сверяет
   `sprint_ids` с фактическим списком.
5. Записывает `.task-readiness/resolved-sources.json` командой `trr resolve-sources --agent …`:
   на каждый источник — `kind`, `system`, `ref`, `title`, `url`, `resolution_method`, `evidence`
   (цитата/факт, почему это тот самый источник), `confidence`. Без `--agent` команда пишет ручную
   заготовку из конфига (`resolution_method=manual`, `confidence=low`, `evidence` — исходная строка).
6. Валидирует результат: `trr validate resolved-sources .task-readiness/resolved-sources.json`.

**Что делает скрипт**

- `trr init` — копирует пример конфига в корень проекта, разбирает его, валидирует по
  `config.schema.json` + семантические правила (`estimation.scale` обязана совпадать с нормативной
  `[1,2,3,5,8,13,21]`, `factor_clamp` — `0 < min < max`), считает `config_sha256`, пишет
  `.task-readiness/state.json` со `stage=configured`. Если `sources.*` заполнены, сразу пишет
  `resolved-sources.json` в ручном режиме (`manual`/`low`) — без выдуманных `page_id` и заголовков.
- `trr resolve-sources` — пересобирает `resolved-sources.json` из `sources.*`; `--agent <path>`
  подмешивает источники, разрешённые агентом (они главнее догадок из текста). Ручную заготовку
  (`resolution_method=manual` у всех) команда пересобирает без флагов, а файл с источниками агента без
  `--re-resolve` не трогает (`BLOCKED`, код 2). Проверяет минимум данных.
- `trr config-check` — отдельная проверка конфига (схема + запрет секретов по имени ключа).
- `trr validate resolved-sources` — схема артефакта (в том числе непустой `evidence`).

**Выход**

- `task-readiness-review.yaml` — конфиг проекта.
- `.task-readiness/resolved-sources.json` — источники с доказательствами.
- `.task-readiness/state.json` — `stage=configured`, `config_sha256`, пустые `model_checksum`/`model_page`.
- `.task-readiness/DATA-REQUIREMENTS.md` — **только** при провале гейта.

**Гейт**

- Меньше одного эталона (`kind=reference`) или меньше одного спринта (`kind=sprint`) → `BLOCKED`, код 2.
  Агент пишет `.task-readiness/DATA-REQUIREMENTS.md`: что нужно, где взять, кому адресован вопрос.
- Конфиг нарушает схему или содержит ключ-секрет → `CONFIG_ERROR`, код 3 (не «поправим на ходу»).
- `evidence` пустой или из пробелов → `SCHEMA_ERROR`, код 5.
- Провал печатается строкой `[BLOCKED] … — <что сделать>`; исправление — добавить источник в конфиг
  и повторить `trr resolve-sources --re-resolve` (или сразу дописать `resolved-sources.json` и перейти
  к `train`).

**Идемпотентность**

- `trr init` на существующем конфиге без `--force` → `BLOCKED` (код 2), конфиг **не** перезаписывается.
- `trr init --force` перезаписывает конфиг и `state.json` (этап сбрасывается в `configured`, история
  прогонов теряется — это осознанный сброс).
- `resolved-sources.json` с ручной заготовкой пересобирается без флагов; файл с источниками агента без
  `--re-resolve` даёт `BLOCKED` (код 2). С `--re-resolve` артефакт перезаписывается целиком — он описывает
  текущее состояние источников, а не историю.

## 4. Этап 5.3 — train

**Команда:** `/task-readiness-review train`

**Предусловия**

- `task-readiness-review.yaml` валиден (`trr config-check` — `[OK]`).
- `.task-readiness/resolved-sources.json` существует и валиден по схеме.
- Доступ на чтение к эталону и к спринтам; доступ на **запись** к странице модели (Confluence или
  Obsidian) — без него этап завершится `WARN`, а `check` будет заблокирован.

**Вход**

- `resolved-sources.json` — что читать (page_id эталона, board_id + sprint_ids).
- Конфиг — `validation.min_sample_n`, `validation.role_map`, `jira.fields.*`, `estimation.factor_clamp`.
- Сырые данные: таблица эталона SP и задачи закрытых спринтов.

**Что делает агент**

1. Читает эталон: `confluence_get_page(page_id="4278391451", convert_to_markdown=true)` (или Obsidian
   `vault_read`, если эталон там). Нужна именно таблица шкалы, а не пересказ.
2. Вычитывает таблицу **целиком** в `.task-readiness/norm/reference-estimates.json`:
   `source{system,page_id,url,title,retrieved_at,version,space_key}`, `scale`,
   `levels[]` (все строки шкалы: `sp`, описание, 4 маркера, время, `examples{BE,FE,QA}`),
   `buckets[]` (`role`, `work_kind`, `value`, `description`, `evidence` + необязательные `level`,
   `example_count`, `params_hint`), `absent_roles` и `absent_roles_note`.
   `evidence` — цитата строки шкалы; `value` обязан быть элементом шкалы.
3. Читает спринты: `jira_get_sprints_from_board(board_id=6662, state="closed")` → сверяет id;
   затем для каждого спринта `jira_get_sprint_issues(sprint_id=…, fields="summary,issuetype,status,labels,customfield_10004,customfield_13819,customfield_12750", limit=50, start_at=0)`.
   Постранично: `limit` у MCP не больше 50, поэтому цикл до неполной страницы.
4. Пишет `.task-readiness/norm/sprint-sample.json`: `source{board_id, sprints[], retrieved_at, transport}`,
   `rows[]` — по строке на задачу: `sprint`, `key`, `issue_type`, `role` (нормализован по `role_map`,
   неизвестное → `OTHER`), `sp` (число или `null`, никогда `""` и никогда `0` вместо «нет данных»),
   `qa_estimation`, `has_testing`, `status`, `labels` (отсортированы), `summary_sha256` (sha256 от `summary`
   в UTF-8 — текст задачи в статистику не попадает).
5. Валидирует оба файла: `trr validate reference-estimates …`, `trr validate sprint-sample …`.
6. **Векторизация (обязательный шаг при `estimation.vector.enabled: true`, дефолт).** Порядок важен:
   - пишет `.task-readiness/norm/task-texts.json` по `schemas/task-texts.schema.json` из **того же**
     снимка задач, что и `sprint-sample.json` (плюс эталонные задачи, если у них есть текст):
     `built_at`, `source{sprints[], retrieved_at}`, `tasks[]` — по задаче `key`, `summary`, `text`
     (описание без заголовка; документ для векторов = `summary + text`, без описания — только `summary`),
     `role`, `work_kind`,
     `issue_type`, `sp`, `qa_estimation`, `has_testing`. Валидация: `trr validate task-texts …`;
   - `trr vectors build` (`--top-terms`, `--weight-word`, `--min-corpus` — из конфига по умолчанию)
     → `.task-readiness/norm/task-vectors.json` с калибровкой `p90`/`p50`;
   - `trr vectors calibrate` — пересчёт порогов `similar_threshold` (p90) / `dissimilar_threshold` (p50)
     по готовому корпусу. Порог корпуса — `estimation.vector.min_corpus` (по умолчанию 30).
   `vectors build` модель оценки не читает, поэтому порядок «векторы → stats → calibrate» безопасен.
7. Запускает расчёт: `trr stats`, затем `trr calibrate`.
8. Публикует страницу модели: рендерит текст из `.task-readiness/model/estimation-model.md`, пишет
   страницу через MCP (`confluence_*` write / `vault_write`) и фиксирует публикацию командой
   `trr publish --model --no-stage` (`state.model_page` + `state.published[]`, этап не двигается).
9. **Экспорт бандла** — только если `artifacts.export_target ≠ none`: `trr artifact plan --target <t>`
   (сверить адрес), `trr artifact pack` (архив + `manifest.json` с sha256), публикация по target
   (Confluence/GitLab/Obsidian — агентом; `local` — самим `pack`), `trr artifact record` (запись в
   `state.artifacts[]`). Публикация бандла `stage` не двигает; неудача — `[WARN]` +
   `actions/artifact-<target>.md`. Векторы попадают в бандл вместе с текстами:
   `norm/task-texts.json` и `norm/task-vectors.json` стоят в `FILE_ORDER`.

**Что делает скрипт**

- `trr stats` — из `norm/sprint-sample.json` считает `.task-readiness/norm/sprint-stats.json`:
  бакеты `(role, issue_type, work_kind)` с `n`, `mean`, `median`, `p25`, `p75`, `min`, `max`, `coverage`;
  список `insufficient[]` (`"<role>/<work_kind>"`). JSON — единственный обязательный выход; `.md` рядом —
  человекочитаемый спутник, гейт его не требует.
- `trr calibrate [--reason train|enrich]` — из `reference-estimates.json` + `sprint-stats.json` строит
  `.task-readiness/model/estimation-model.json`: `base`, `factor`, `expected`, `range`, `n`, `confidence`,
  `reference`, `provenance[]`; считает `checksum`; дописывает `.task-readiness/model/model-history.jsonl`
  с причиной (`train` по умолчанию, `enrich` — при дообучении); выставляет `stage=trained` и
  `state.model_checksum`. В обеих ветках (входы изменились / не изменились) рендерит три `.md`-зеркала:
  `norm/reference-estimates.md`, `norm/sprint-stats.md`, `model/estimation-model.md`. Ошибка рендера —
  `[WARN]`, модель остаётся валидной. Текст страницы модели рендерится по шаблону
  `templates/model-page.md` и публикуется агентом.
- `trr render-norm` — перерисовывает те же три `.md`-зеркала из существующих JSON без пересчёта модели;
  нет хотя бы одного JSON — код 4, ошибка рендера — код 2.
- `trr model-hash` — печатает `sha256:… version:N` (быстрая сверка, что модель та самая).
- `trr vectors build` — `norm/task-texts.json` → `norm/task-vectors.json`: idf, гибридные векторы и
  калибровка порогов (`p90` / `p50` межбакетных косинусов). Модель оценки не читает и на неё не влияет;
  меньше `min_corpus` задач — `[BLOCKED]` (2), нет текстов — `[MISSING]` (4).
- `trr vectors calibrate` — пересчитывает `similar_threshold` (p90) / `dissimilar_threshold` (p50) по
  готовому `norm/task-vectors.json`; нужен после правки корпуса без пересборки.

**Выход**

- `.task-readiness/norm/reference-estimates.json` (рядом `.md` — спутник для человека)
- `.task-readiness/norm/sprint-sample.json`
- `.task-readiness/norm/sprint-stats.json` (рядом `.md` — спутник)
- `.task-readiness/model/estimation-model.json`
- `.task-readiness/model/estimation-model.md` — обязателен: его наличие проверяет `trr doctor`
- `.task-readiness/model/model-history.jsonl` — строка `{"version":N,"generated_at":"…","checksum":"…","reason":"train"}`
- `.task-readiness/norm/task-texts.json` + `.task-readiness/norm/task-vectors.json` — тексты пишет
  агент, векторы — `trr vectors build` (шаг 6, обязателен при `estimation.vector.enabled: true`)
- `state.json`: `stage=trained`, `model_checksum`, `model_page{system,id,url,hash,version}`, `artifacts[]` (при экспорте)
- страница модели в Confluence/Obsidian
- `.task-readiness/artifacts/<name>.tar.gz` + `manifest.json` внутри (при `artifacts.export_target ≠ none`)

**Гейт**

- Эталон недоступен, спринт не найден, обязательное поле отсутствует → `BLOCKED` (код 2) +
  `.task-readiness/DATA-REQUIREMENTS.md`. Оценок «на глаз» вместо данных не бывает.
- Бакет с `n < min_sample_n` → `WARN` + `coverage=insufficient` + `confidence=low`; бакет остаётся
  в статистике как справка, но не участвует в калибровке (`estimation-model.md`).
- `trr validate` вернул 5 → артефакт не той формы, перечитать источник и перезаписать файл.
- `estimation.vector.enabled: true` (дефолт), а `norm/task-vectors.json` не создан → `train`
  **незавершён**, а не тихий пропуск: `estimate` печатает `[WARN]`, `trr doctor` показывает проблему.
  Догоняется `trr vectors build` (тексты `norm/task-texts.json` — из того же снимка задач).
- Страницу модели опубликовать не удалось → `[WARN]`, `state.model_page=null`; этап остаётся `trained`,
  но `check` будет `BLOCKED` до публикации.
- Место публикации бандла не заполнено при `export_target ≠ none` → `trr artifact plan` печатает
  `[MISSING]` и возвращает код 2 (до сборки); бандл не опубликовался → `[WARN]`, этап остаётся `trained`.

**Идемпотентность**

Повторный `train` на неизменных входах даёт тот же `checksum`: модель **не переписывается**, `version` не
растёт, `model-history.jsonl` не пополняется. Изменился вход (новый спринт, правка эталона) — это уже
`enrich` (5.7), а не «ещё один train»: версия вырастает ровно на 1 и с `reason="enrich"` — при условии,
что входы действительно изменились; иначе модель не переписывается и версия остаётся прежней.

## 5. Этап 5.4 — check

Одна команда `/task-readiness-review check`, три подшага. Подшаги не имеют отдельных команд: это внутренняя
декомпозиция, нужная, чтобы у каждого действия был ровно один источник данных.

### 5.4.1 Чтение задачи (Jira)

**Команда:** `/task-readiness-review check` (подшаг 1 из 3)

**Предусловия**

- Модель на месте: `.task-readiness/model/estimation-model.json` **и** `state.model_page ≠ null`.
- Задача существует и доступна на чтение.

**Вход**

- `--task <KEY>` (например `E001-1234`).
- Конфиг: `jira.project`, `jira.fields.story_points|qa_estimation|role`, `validation.role_map`.

**Что делает агент**

1. Читает задачу: `jira_get_issue(issue_key, fields="summary,description,issuetype,status,labels,priority,parent,customfield_10004,customfield_13819,customfield_12750", include="comments,remote_links")`.
2. Нормализует роль из `customfield_12750` через `role_map`; неизвестное значение → `OTHER` (не ошибка).
3. Разбирает описание на блоки (`sections{}`): 11 полей шаблона описания, блоки передачи в разработку,
   критерии приёмки, сценарии.
4. Фиксирует `work_kind` по смыслу и типу: `Ошибка` → `bugfix`, `Tech Debt` → `tech_debt`,
   `ADR` → `analysis`, `Feature`/`Задача` → `implementation`, при неоднозначности → `unknown`.
   `has_testing` в `context.json` можно поставить, но скрипт его **пересчитает**
   (`detect_has_testing`): заполнена QA Estimation → `true`; иначе тип задачи входит в
   `validation.qa_required_issue_types` (по умолчанию Feature/Ошибка) → `true`; иначе `false` —
   у Задачи, Tech Debt, ADR, Релиза и Дизайна QA-оценки нет, проверку выполняет исполнитель.
   Сигналы тестирования в тексте/метках/разделе остаются только пояснением в причине. Причина
   пишется в сообщение `QA-01` в `validation.json`.
5. Создаёт каталог прогона `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/` (`<RUN-ID>` — UTC-момент старта,
   формат `%Y-%m-%dT%H-%M-%SZ`) и пишет туда `context.json` со всеми 10 обязательными ключами: `task_key`,
   `issue_type`, `role`, `work_kind`, `sp`, `qa_estimation`, `labels`, `fields{}`, `sections{}`, `sources[]`.
   `has_testing` можно положить дополнительно, но скрипт его пересчитает.

**Что делает скрипт**

Ничего: подшаг целиком агентский. Python не умеет ходить в Jira.

**Выход**

- `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/context.json`

**Гейт**

- Нет модели → `BLOCKED` (код 2), строка
  `[BLOCKED] check: модель оценки не обучена — запустите /task-readiness-review train`. Модель есть, но страница
  не опубликована (`state.model_page = null`) → `BLOCKED` (код 2), строка
  `[BLOCKED] check: страница модели не опубликована — запустите /task-readiness-review publish --model (для проекта без Confluence: --target obsidian)`.
  Оба гейта выполняет CLI-обвязка `trr check` (ядро правил модель не читает). Никакого «частичного»
  check без модели. Для проекта без Confluence гейт закрывается офлайн: `publish --model --target
  obsidian --ref local --url .task-readiness/model/estimation-model.md --file
  .task-readiness/model/estimation-model.md --no-stage` пишет `state.model_page` локально (см.
  `references/commands.md` §3.10).
- Страница модели устарела → `BLOCKED` (код 2): `state.model_page.hash` должен совпадать с текущей
  моделью (`model/estimation-model.json`, поле `checksum`), иначе `[BLOCKED] check: страница модели
  устарела (hash <a…> ≠ модель <b…>) — запустите /task-readiness-review publish --model`. После `enrich`/`train`
  модель меняется, а страница остаётся старой — проверка по ней молча врала бы. Артефакт без `hash`
  (до появления гейта) даёт только `[WARN]` и прогон продолжается.
- Задача не читается (404/403) → `BLOCKED` + `DATA-REQUIREMENTS.md` с указанием ключа и требуемого доступа.

**Идемпотентность**

Повторный подшаг в **незавершённый** прогон (нет `estimate.json`) перезаписывает `context.json` того же
`<RUN-ID>`. В завершённый прогон — создаётся новый `<RUN-ID>`: артефакты прошлого прогона не трогаются.

### 5.4.2 Сбор доказательств по ссылкам (Confluence, Obsidian, GitLab)

**Команда:** `/task-readiness-review check` (подшаг 2 из 3)

**Предусловия**

- `context.json` уже содержит ссылки из задачи (`remote_links`, URL в описании, ключи связанных задач).
- Доступ к тем системам, куда ссылаются: Confluence, Obsidian, GitLab. Недоступность системы — не повод
  падать: соответствующая проверка станет `UNKNOWN` (см. `sources-fallback.md`).

**Вход**

- Ссылки из `context.json`: страница эпика, макеты, контракт/OpenAPI, репозиторий и ветка, MR.
- `sources[]` в `context.json` — список ссылок с провенансом.

**Что делает агент**

1. Для каждой ссылки на Confluence — `confluence_get_page(page_id=…)`; вытаскивает то, что закрывает
   пробелы: критерии приёмки, требования БА, описание, сценарии.
2. Для ссылок на Obsidian — `search_simple`/`vault_read` по пути заметки.
3. Для ссылок на репозиторий (только этот подшаг) — GitLab: `repository/tree`, `repository/files`,
   `repository/branches`, `merge_requests`; цель — подтвердить существование контракта/макета/ветки, а не
   читать весь код.
4. Дописывает в `context.json` `sources[]`: `{system, ref, url, what, transport: "mcp"|"rest", retrieved_at}`.
   Ничего не найдено — тоже результат: ссылка остаётся с пометкой «не подтверждено», правило даст `UNKNOWN`.

**Что делает скрипт**

Ничего: сеть — только у агента.

**Выход**

- Обновлённый `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/context.json` (`sources[]`).

**Гейт**

- Мягкий: недоступная система не блокирует check, но каждая неподтверждённая ссылка обязана быть видна
  в `context.json` и превратиться в `UNKNOWN` у соответствующего правила. Молча «дочитать по памяти» нельзя.
- Жёсткий гейт остаётся один: `context.json` обязан содержать 10 ключей — `task_key`, `issue_type`, `role`,
  `work_kind`, `sp`, `qa_estimation`, `labels`, `fields{}`, `sections{}`, `sources[]` — иначе `check.py` падает
  с кодом 5 (`SCHEMA_ERROR`).

**Идемпотентность**

Повторный сбор в том же незавершённом прогоне перезаписывает `sources[]` целиком (это снимок, а не
журнал). `retrieved_at` обновляется — по нему видно, насколько свежи доказательства.

### 5.4.3 Прогон правил и вопросы

**Команда:** `/task-readiness-review check` (подшаг 3 из 3)

**Предусловия**

- `context.json` заполнен (см. 5.4.2), модель на месте.
- `templates/task-description.md` (или `override_template`) доступен — из него берётся версия и sha256
  шаблона.

**Вход**

- `--task <KEY>`, опционально `--with-dependencies`, `--run <RUN-ID>`.
- `context.json`, шаблон, каталог правил в `check.py` (см. `validation-rules.md`).

**Что делает агент**

1. Подтверждает `work_kind` — это единственное смысловое поле, где решение принимает ИИ, и оно
   фиксируется в `context.json` до запуска скрипта. `has_testing` скрипт пересчитывает сам (правило
   `QA-01`), поэтому «подтверждать» его бессмысленно.
2. Запускает `trr check --task <KEY> --run <RUN-ID>` (при `--with-dependencies` — с флагом).
3. Читает `validation.json`: `verdict`, список `FAIL`/`UNKNOWN` с `severity`.
4. Показывает пользователю `questions.json` — вопросы с адресатом (`target_role`) и местом, где искать ответ.
5. Проверяет `comment-draft.md`: при `comment_mode: post` (дефолт) `trr check` печатает план публикации
   вопросов (`[PLAN] questions comment: create|update`) — их публикует агент (см. §9); `draft` оставляет
   только файл.

**Что делает скрипт**

`trr check` — считает содержательный анализ задачи (`analysis.analyze`: понятность, измеримость,
воспроизводимость, границы, связи, сценарии, область, неопределённость) и сверяет `context.json` с
каталогом правил (`check.py`: `CL-01…CL-07` — содержание, `TPL-01…TPL-11` и `TPL-09a` — гигиена 11 полей
описания плюс 9.1, `SA-01`, `SA-02`, `SA-04…SA-09` — блоки передачи в разработку и чек-лист SA,
`QA-01` — QA Estimation, `FT-01` — feature-toggle, `DEP-01…DEP-03` — документация зависимостей),
применяет `condition`-DSL (`NA` при невыполненном условии), считает `verdict` (`BLOCKED` при `REQUIRED`
со статусом `FAIL` **или** `UNKNOWN`, `WARN` при `RECOMMENDED` `FAIL`/`UNKNOWN`, иначе `OK`; `OPTIONAL`
вердикт не меняет), формирует `gaps[]`, `questions.json` и `comment-draft.md`; выставляет
`stage=checked` и добавляет прогон в `state.runs`.
Смысловые id ранних редакций (точечные псевдонимы вида `desc.<поле>`) упразднены — актуальный
каталог и условные severity см. `CONTRACT.md` §6.4 и `references/validation-rules.md`.

**Выход**

- `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/validation.json`
- `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/questions.json`
- `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/comment-draft.md`
- `state.json`: `stage=checked`, запись в `runs[]` (`task_key`, `run_dir`, `verdict`, `checked_at`)

**Гейт**

- `verdict=BLOCKED` — это **результат проверки**, а не сбой скилла: код выхода 0, отчёт печатается,
  `gaps[]` содержит блокирующие пробелы. Пользователь видит, что именно мешает взять задачу в работу.
- `SCHEMA_ERROR` (5) — `context.json` неполный или шаблон не читается; исправление: перечитать задачу,
  дополнить `context.json`, повторить.
- Нет `--task` → ошибка разбора аргументов; ключ не найден → `BLOCKED` + `DATA-REQUIREMENTS.md`.

**Идемпотентность**

Повторный `check` в незавершённом прогоне перезаписывает `validation.json`, `questions.json`,
`comment-draft.md` того же `<RUN-ID>` (и обновляет запись в `state.runs` по `run_dir`, без дублей).
В завершённом прогоне — новый `<RUN-ID>`.

## 6. Этапы 5.4.4 + 5.5 — estimate

**Команда:** `/task-readiness-review estimate`

**Предусловия**

- `validation.json` существует в прогоне (иначе гейт).
- `context.json` существует, модель и `state.model_page` на месте.
- Понятно, для каких ролей есть работа в задаче (роль из Jira + явно упомянутые роли в описании).

**Вход**

- `--task <KEY>`, `--run <RUN-ID>` (по умолчанию — последний незавершённый прогон задачи).
- `validation.json` (пробелы и их severity), `estimation-model.json` (бакеты и `gap_rules`);
  `context.json` — опционально (`role`, `work_kind`): без него `work_kind` считается `implementation`,
  а роли берутся из всех бакетов модели.

**Что делает агент**

1. Подтверждает `work_kind` ещё раз — от него зависит бакет, и ошибка здесь дороже всего.
2. Формулирует `variability_reason` словами: чего в данных нет (например, «BA/SA отсутствуют в эталоне —
   база только из спринтов»), где выборка мала, какие пробелы расширяют диапазон.
3. Запускает `trr estimate --task <KEY> --run <RUN-ID>`.
4. Запускает `trr report --task <KEY> --run <RUN-ID>` и проверяет, что рядом с каждым числом в `report.md`
   есть ссылка на источник (бакет эталона, бакет статистики или правило модели).
5. Показывает пользователю отчёт: `expected`, `range`, три сценария, `confidence`, `blocked_by_gaps`.

**Что делает скрипт**

- `trr estimate` — считает по модели: `base` → `observed = median(sp)` → `factor = clamp(observed/base)` →
  `expected = nearest_scale(base × factor)` → `range` по p25/p75-веткам → `gap_penalty` за `REQUIRED`-пробелы
  (максимум +2 шага). Пишет `estimate.json`: `roles[]` (по роли: `expected`, `range`, три `scenarios`,
  `confidence`, `provenance[]`), `total` (сумма), `variability_reason`, `blocked_by_gaps`.
- **Векторы (этап A):** при `estimation.vector.enabled: true` и наличии `norm/task-vectors.json` с
  `corpus_rows >= min_corpus` в `estimate.json` появляется `similar_tasks[]` (top-`top_k` соседей:
  `key`, `cosine`, `sp`, `role`, `work_kind`, `same_bucket`), а на каждую роль — запись
  `provenance kind=vector_nn` с `source: "task-vectors:<built_at>"`. По умолчанию (`adjust_range: false`)
  числа не меняются. При `adjust_range: true` `range` расширяется до SP соседей того же бакета с
  `cosine >= similar_threshold`, `confidence` понижается до `low`, в `variability_reason` добавляется
  строка `vector_nn: …`; `base`/`expected` не меняются никогда. Нет артефакта или малый корпус — `[WARN]`,
  оценка считается без соседей.
- `trr report` — рендерит `report.md` по шаблону; выставляет `stage=estimated`. `--model` (без `--task`)
  перерисовывает `model/estimation-model.md` из существующего JSON; нет файла/не читается — код 4,
  ошибка рендера — код 2. Секция `## 9. Похожие задачи (справочно)` добавляется **только** при непустом
  `similar_tasks[]`: при `enabled: false` или пустом списке отчёт остаётся из 8 секций (1–8).
- `trr model-hash` — если нужно доказать, какой версией модели считали (`model_version`, `model_checksum`
  в `estimate.json` обязательны).

**Выход**

- `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/estimate.json`
- `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/report.md`
- `state.json`: `stage=estimated`

**Гейт**

- Нет `validation.json` → `MISSING` (код 4): `[MISSING] .task-readiness/runs/<KEY>/<RUN-ID>/validation.json — сначала запустите /task-readiness-review check <KEY>`.
- Нет модели → `MISSING` (код 4): `[MISSING] estimate: нет модели оценки — запустите /task-readiness-review train`.
- Роль без бакета в `roles[]` не попадает, причина — в `variability_reason[]`; если бакетов в модели нет
  вообще → код 5 («оценивать нечем»): выдумывать базу запрещено, лечится `train`/`enrich`.
- `verdict=BLOCKED` в `validation.json` **не** блокирует расчёт: оценка считается, `blocked_by_gaps`
  заполняется, `gap_penalty` расширяет диапазон. Смысл — показать цену неготовности, а не спрятать её.

**Идемпотентность**

Идентичные входы (тот же `validation.json`, тот же `context.json`, та же модель) → байт-в-байт идентичный
`estimate.json` и `report.md` (кроме `estimated_at`). Повторный запуск в завершённом прогоне — новый
`<RUN-ID>`; старый остаётся как история.

## 7. Этап 5.6 — refresh

**Команда:** `/task-readiness-review refresh`

**Предусловия**

- Есть предыдущий прогон: в `state.runs` лежит хотя бы одна запись по этой задаче.
- Задача или её окружение изменились (дописали критерии приёмки, появился макет, задачу переоценили).

**Вход**

- `--task <KEY>`; предыдущий прогон определяется по `state.runs` (последний `run_dir`).
- Новые данные из Jira/Confluence — читаются заново, а не берутся из старого `context.json`.

**Что делает агент**

1. Берёт из `state.runs` последний `run_dir` задачи — это база сравнения.
2. Перечитывает задачу (5.4.1) и доказательства (5.4.2) в **новый** `<RUN-ID>`.
3. Запускает `trr check --task <KEY> --run <NEW-RUN-ID>` и `trr estimate --task <KEY> --run <NEW-RUN-ID>`.
4. Запускает `trr report --task <KEY> --run <NEW-RUN-ID> --delta` — получает `delta.md`.
5. Показывает дельту: что закрылось, что появилось, как изменились `expected`/`range`/`verdict`.

**Что делает скрипт**

`trr check` + `trr estimate` (как в 5.4.3 и 5.5) и `trr report --delta`, который сравнивает два прогона
по `id` правил и по числам оценки, формируя `delta.md`.

**Выход**

- новый каталог `.task-readiness/runs/<TASK-KEY>/<NEW-RUN-ID>/` с `context.json`, `validation.json`,
  `questions.json`, `comment-draft.md`, `estimate.json`, `report.md`
- `.task-readiness/runs/<TASK-KEY>/<NEW-RUN-ID>/delta.md`
- `state.json`: запись о новом прогоне в `runs[]`

**Гейт**

- Нет предыдущего прогона → `BLOCKED` (код 2): `[BLOCKED] refresh: нет предыдущего прогона E001-1234 — сначала /task-readiness-review check`.
- Предыдущий прогон есть, но битый (`validation.json` не читается) → `SCHEMA_ERROR` (5); лечится новым
  полным прогоном, а не правкой старого файла.

**Идемпотентность**

Каждый `refresh` — новый `<RUN-ID>`. Старые прогоны не перезаписываются никогда: `delta.md` существует
именно потому, что история неприкосновенна. Комментарий в задаче `refresh` не трогает: после него
`publish` обновит тот же комментарий (`update` по маркеру/`comment_id`), если результат нужно показать в
задаче.

## 8. Этап 5.7 — enrich

**Команда:** `/task-readiness-review enrich`

**Предусловия**

- Пользователь подтвердил новые данные: добавился спринт, исправлена строка эталона, уточнён `role_map`,
  обнаружена ошибка в `sprint-sample.json`.
- Есть доступ на запись к странице модели (иначе `stage` не сдвинется).

**Вход**

- Подтверждённые значения (что именно и на что менять) — от пользователя, не из догадки.
- Текущие `norm/reference-estimates.json`, `norm/sprint-sample.json`, `model/estimation-model.json`.

**Что делает агент**

1. Фиксирует у пользователя, что меняется и почему (одна строка на изменение).
2. Правит `norm/reference-estimates.json` и/или `norm/sprint-sample.json` — точечно, не перегенерируя
   файл с нуля (иначе потеряется провенанс остальных строк).
3. Валидирует правку: `trr validate reference-estimates …` / `trr validate sprint-sample …`.
4. Запускает `trr stats` и `trr calibrate --reason enrich` — модель получает `version + 1` и запись
   в `model-history.jsonl` с `reason: "enrich"`. Если входы не изменились, версия не растёт: `calibrate`
   печатает `[OK] входы не изменились, версия N не переписана`, и перепубликация страницы не нужна.
5. Перепубликует страницу модели (текст из нового `estimation-model.md`) и фиксирует её командой
   `trr publish --model --no-stage` — обновляются `state.published[]` и `state.model_page`
   (`hash`, `version`), этап не двигается.
6. Проверяет `trr model-hash` — версия и sha256 должны совпасть с тем, что на странице.

**Что делает скрипт**

`trr stats` + `trr calibrate --reason enrich`: пересчёт статистики, новая версия модели (`version+1`)
**только при изменившихся входах**, строка в `model-history.jsonl` с `reason="enrich"`, перевод этапа
`checked|estimated|published → trained` **только** с `reason="enrich"`.

**Выход**

- обновлённые `.task-readiness/norm/reference-estimates.json` / `norm/sprint-sample.json` /
  `norm/sprint-stats.{json,md}`
- `.task-readiness/model/estimation-model.json` с `version = было + 1`
- `.task-readiness/model/model-history.jsonl` (+1 строка)
- перепубликованная страница модели, обновлённый `state.model_page`
- `state.json`: `stage=trained`

**Гейт**

- Без перепубликации страницы модели `stage` не двигается, а `check` остаётся `BLOCKED` (гейт требует
  `state.model_page`). Это защита от «модель новая, а команда читает старую страницу».
- Откат этапа без `reason="enrich"` → `StateError`; попытка понизить версию модели → запрещена (версия
  только растёт).
- Правка, ломающая схему (значение вне шкалы, дубликат `(role, work_kind)`) → `SCHEMA_ERROR` (5).

**Идемпотентность**

Повторный `enrich` с теми же значениями даёт тот же `checksum` — версия не растёт второй раз (сравнение
по `checksum`, как в `train`). Повторная публикация той же страницы перезаписывает её, а не создаёт дубль.

## 9. Этап 6 — publish

**Команда:** `/task-readiness-review publish`

По умолчанию (`jira.comment_mode: post`) результат публикуется **двумя комментариями в саму задачу
Jira**: «Результаты валидации» (маркер `<!-- task-readiness-review:validation:<TASK-KEY> -->`) и
«Результаты оценки» (маркер `<!-- task-readiness-review:estimate:<TASK-KEY> -->`). Повторный запуск
**обновляет** те же комментарии (`comment_id` из `state.published[]` по `ref` вида; без id — поиск по
маркеру вида), а не создаёт вторые. `output.target` — **дополнительная** публикация страницы/заметки
после комментариев.

**Предусловия**

- `report.md` отрендерен (`estimate` уже проходил).
- `jira.comment_mode: post` (дефолт) и право писать комментарии в задачу. `draft`, `--no-jira`, `--draft`
  отключают запись.
- Для `target=confluence` — заполнены `output.confluence.space` и `output.confluence.page_id`;
  для `target=obsidian` — `output.obsidian.path`.

**Вход**

- `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/report.md`
- `jira.comment_mode`, `output.target`, `output.confluence.{space,page_id}`, `output.obsidian.path`

**Что делает агент**

1. Запускает `trr publish --task <KEY>`: скрипт собирает **два** тела — `jira-validation.md`
   («Результаты валидации») и `jira-estimate.md` («Результаты оценки») — маркер вида + текст без
   HTML-комментариев, обрезка до 32767 символов по границе абзаца с хвостом
   `… (полный отчёт: <путь>)`; печатает по плану `create|update` с `comment_id` на каждый вид.
2. Публикует оба тела в Jira через MCP: `action=update` → `jira_update_comment(comment_id, body)`,
   `action=create` → `jira_add_comment(issue_key, body)`; REST fallback — `PUT`/`POST`
   `/rest/api/2/issue/<KEY>/comment`. Если id потерян, сначала ищет комментарий по маркеру вида.
3. Фиксирует id: `trr publish --task <KEY> --comment-id-validation <id> --comment-id-estimate <id>` →
   две записи `target=jira` в `state.published[]` (`ref=<KEY>#validation` и `ref=<KEY>#estimate`, у каждой
   `comment_id` и `marker`) и `stage=published`.
4. `--target confluence|obsidian` → **дополнительно** публикует `report.md` через MCP (страница
   `output.confluence.page_id` или новая в `output.confluence.space`; заметка по `output.obsidian.path`).
5. Печатает итог: ссылка на комментарий, куда дополнительно опубликовано, версия модели, вердикт.

**Что делает скрипт**

`trr report --task <KEY> --run <RUN-ID>` гарантирует, что `report.md` есть и соответствует шаблону.
`trr publish --task <KEY> [--plan-jira|--draft]` готовит тела и план по каждому виду;
`--comment-id-validation`/`--comment-id-estimate` — идемпотентный upsert в `state.published[]` (sha256
тела своего вида) и `stage=published`; легаси `--comment-id` = `--comment-id-estimate`. `trr publish --target … --ref … --url …
--file …` фиксирует страницу/заметку; при `--model` обновляет `state.model_page` (с `--no-stage`).
Саму публикацию Python не делает: сеть — только у агента.

**Выход**

- `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/jira-validation.md` и `jira-estimate.md` — тела двух
  комментариев.
- `state.published[]`: две записи `target=jira` (`ref=<KEY>#validation` и `ref=<KEY>#estimate`), у каждой
  `comment_id`, `marker`; `stage=published`.
- `output.target: confluence|obsidian` → дополнительно страница/заметка; ссылка печатается в stdout и
  попадает в шапку `report.md` («Опубликовано: <url>»).
- `actions/jira-validation.md` и `actions/jira-estimate.md` — **только** при недоступности Jira (готовые
  тексты + шаги).
- `actions/<target>-page.md` — **только** при недоступности MCP страниц.

**Гейт**

- Jira недоступна (MCP и REST) и `401/403` → `WARN`, код 0: работа **не падает**. Агент кладёт
  `.task-readiness/runs/<TASK-KEY>/<RUN-ID>/actions/jira-validation.md` и `actions/jira-estimate.md` с
  готовыми текстами, маркерами видов и шагами («найти по маркеру → обновить/создать →
  `trr publish --comment-id-validation/--comment-id-estimate <id>`»); `stage` не двигается.
- `target=confluence` без `space`/`page_id` → `CONFIG_ERROR` (3): некуда публиковать страницу.
- `comment_mode: draft` (или `--no-jira`/`--draft`) → комментарий **не** отправляется: тело остаётся
  файлом, `stage` не двигается.

**Идемпотентность**

Повторный `publish` **обновляет** те же два комментария: id берётся из `state.published[]` по `ref` вида, а
если потерян — комментарий находится по маркеру вида и обновляется, второй не создаётся. Страница/заметка обновляется по
адресу из конфига, дублей не создаёт.

## 10. Матрица минимальных данных

| Этап | Минимально необходимо | Что будет, если нет | Как исправить |
|---|---|---|---|
| 5.1 install | исходник скилла (репозиторий или релиз) + `sh`, `tar`, `sha256sum`/`shasum` | `exit 1`, ничего не установлено | клонировать репозиторий; задать `TASK_READINESS_REVIEW_VERSION`; проверить элементы `BUNDLE_ITEMS` |
| 5.2 init | ≥ 1 эталон SP + ≥ 1 закрытый спринт + доступ к Confluence/Jira | `BLOCKED` (2) + `DATA-REQUIREMENTS.md` | вписать `page_id` эталона и `board_id`/`sprint_ids`; проверить доступ пробным чтением |
| 5.3 train | `resolved-sources.json` + читаемый эталон + задачи спринтов с заполненными SP | `BLOCKED` (2) + `DATA-REQUIREMENTS.md`; при малой выборке — `WARN` | заполнить Story Points в спринтах, добавить спринты, проверить права на страницу модели |
| 5.4.1 check (Jira) | модель + `state.model_page` + читаемая задача | `BLOCKED` (2): «модель оценки не обучена» или нет доступа | прогнать `train`; проверить ключ задачи и права |
| 5.4.2 check (evidence) | ссылки из задачи + доступ к соответствующим системам | не блокирует: правила по неподтверждённым ссылкам дают `UNKNOWN` | восстановить доступ или подтвердить отсутствие артефакта у пользователя |
| 5.4.3 check (rules) | заполненный `context.json` + шаблон | `SCHEMA_ERROR` (5) | перечитать задачу, дополнить `context.json`, повторить |
| 5.4.4+5.5 estimate | `validation.json` + `context.json` + модель | `MISSING` (4): нет `validation.json` или нет модели | прогнать `check`, затем `train` |
| векторизация (`vectors build`) | `norm/task-texts.json` + `corpus_rows >= estimation.vector.min_corpus` (30) | `[MISSING]` (4) без текстов; `[BLOCKED]` (2) при корпусе меньше `min_corpus` | собрать тексты задач и добавить спринты (`enrich`); либо осознанно снизить `min_corpus` (пол в схеме — 30) |
| векторизация в оценке (`estimate`) | `estimation.vector.enabled: true` + `norm/task-vectors.json` + `corpus_rows >= min_corpus` | **не блокирует**: `[WARN]` и оценка без соседей; секции 9 в отчёте нет | `trr vectors build`; проверить `enabled` и `min_corpus` |
| 5.6 refresh | предыдущий прогон в `state.runs` + новые данные | `BLOCKED` (2): «нет предыдущего прогона» | сначала `check` + `estimate` |
| 5.7 enrich | подтверждённые пользователем значения + право записи на страницу модели | `WARN`, `stage` не двигается, `check` остаётся `BLOCKED` | получить подтверждение; восстановить доступ на запись |
| 6 publish | `report.md` + `jira.comment_mode: post` (дефолт) + право на комментарий; при `--target` — адрес страницы/заметки | Jira недоступна → `WARN` + `actions/jira-validation.md` / `actions/jira-estimate.md`, `stage` не двигается; `comment_mode: draft`/`--no-jira`/`--draft` → записи нет | восстановить Jira (MCP/REST) либо опубликовать руками по action-пакетам и записать id через `trr publish --comment-id-validation/--comment-id-estimate`; для страницы — заполнить `output` |
| импорт бандла (`init --from-artifact`) | `.tar.gz` с `manifest.json` + совпадающий `jira.project` | `SCHEMA_ERROR` (5) при sha256/checksum; `BLOCKED` (2) при чужом проекте без `--allow-foreign-project` | взять бандл своего проекта либо осознанно передать `--allow-foreign-project`; пересобрать бандл при битом файле |
| экспорт бандла (`artifact plan` → `artifact pack` → publish → `record`) | `norm/*` + `model/*` + заполненное место публикации (`artifacts.<target>.*`) | `[MISSING]` (2) на `artifact plan` при незаполненном месте; `WARN` при недоступной системе публикации | заполнить `artifacts.*`; восстановить доступ и повторить публикацию, затем `artifact record` |

## 11. Что НЕ делает скилл

Это не «ограничения реализации», а обещания, которые нельзя нарушать ни при каких флагах:

- **Не коммитит и не пушит.** Ни `git commit`, ни `git push`, ни создание тегов/веток. Ни на одном этапе,
  ни по просьбе «заодно закоммить».
- **Не делает в Jira ничего, кроме одного комментария к анализируемой задаче.** По умолчанию
  (`comment_mode: post`) `publish` публикует туда отчёт, `check` — вопросы; повторный запуск **обновляет**
  тот же комментарий (по `comment_id`/маркеру), второй не создаёт. `comment_mode: draft`, `--no-jira`,
  `--draft` отключают запись.
- **Не меняет задачу в Jira.** Никаких переходов статуса, правок полей, выставления Story Points,
  назначения исполнителя. Единственная запись — комментарий к этой задаче.
- **Не выдумывает оценки без модели.** Нет модели — `BLOCKED` и просьба запустить `train`. Роль без бакета
  в `roles[]` не попадает, причина — в `variability_reason[]`; если бакетов нет вообще — `SCHEMA_ERROR` и
  «оценивать нечем». Числа «примерно столько» в отчёте не появляются никогда.
- **Не ходит в сеть из Python.** Confluence/Jira/Obsidian/GitLab читает и пишет только агент; Python
  работает с файлами, которые агент уже положил на диск.
- **Не хранит секреты.** Токены — только из окружения (`JIRA_TOKEN`, `CONFLUENCE_TOKEN`, `GITLAB_TOKEN`).
  Ключ с похожим на секрет именем в конфиге роняет `config-check` с кодом 3.
- **Не переписывает чужие прогоны.** Один прогон — одна директория; `refresh` создаёт новую.
- **Не публикует страниц и заметок при `target: none`.** Отчёт живёт в stdout и в каталоге прогона;
  комментарий в задачу при `comment_mode: post` — отдельная (основная) публикация, не зависящая от `target`.
- **Не обходит авторизацию.** 401/403 — это `BLOCKED` с инструкцией, а не повод искать обходной путь.
- **Не меняет нормативную шкалу.** `estimation.scale` обязана совпадать с `[1, 2, 3, 5, 8, 13, 21]`;
  расхождение — ошибка конфига, а не «настройка под проект».
- **Не публикует бандл модели сам.** `artifact pack` только собирает архив; в Confluence/GitLab/Obsidian
  его кладёт агент, `artifact record` фиксирует факт. Импорт чужой модели без `--allow-foreign-project`
  заблокирован: смещённая оценка хуже отказа.

## 12. Быстрая шпаргалка

| # | Команда | Главный артефакт | Код при провале |
|---|---|---|---|
| 5.1 | `/task-readiness-review install` | `<skills-dir>/task-readiness-review/` + маркер | 1 |
| 5.2 | `/task-readiness-review init` | `task-readiness-review.yaml`, `resolved-sources.json`, `state.json` | 2 / 3 |
| 5.3 | `/task-readiness-review train` | `norm/*`, `model/estimation-model.json`, страница модели | 2 / 5 |
| 5.4 | `/task-readiness-review check` | `context.json`, `validation.json`, `questions.json`, `comment-draft.md` | 2 / 5 |
| 5.4.4+5.5 | `/task-readiness-review estimate` | `estimate.json`, `report.md` | 2 |
| 5.6 | `/task-readiness-review refresh` | новый `<RUN-ID>` + `delta.md` | 2 |
| 5.7 | `/task-readiness-review enrich` | `estimation-model.json` `version+1` (при изменившихся входах), `model-history.jsonl` | 2 / 5 |
| 6 | `/task-readiness-review publish` | stdout или страница/заметка (+ комментарий при `post`) | 0 (`WARN`) / 3 |
| — | `/task-readiness-review doctor` | чек-лист `[OK]/[WARN]/[MISSING]/[BLOCKED]` | 3 → 4 → 5 → 2 |
| экспорт | `trr artifact plan` → `trr artifact pack` → publish → `artifact record` | `.tar.gz` + `manifest.json`, `state.artifacts[]` | 2 / 3 / 4 / 5 |
| импорт | `trr artifact inspect` → `trr init --from-artifact` | `norm/*`, `model/*`, `stage=trained` | 2 / 5 |

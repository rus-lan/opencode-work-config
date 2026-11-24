# Команды скилла: единая команда, подкоманды и что они делают

Одна слэш-команда `/task-readiness-review <подкоманда>` (файл `commands/task-readiness-review.md`) и
подкоманды `scripts/trr`, у которых нет одноимённой подкоманды команды. Полные инструкции по каждой
подкоманде (шаги агента, MCP → REST, стоп-условия) — в `commands/task-readiness-review.md`; здесь —
сводка: вход, выход, предусловия, гейт. Нормативный источник — `CONTRACT.md` §4, §6; подробные блоки по
этапам — `pipeline.md`; пути и поля артефактов — `artifacts.md`; симптомы и лечение — `troubleshooting.md`.

Все пути — относительно корня проекта (`--root`, алиас `--workdir`; по умолчанию — поиск конфига вверх по
дереву, затем текущая директория).
Пути внутри скилла помечены `<skill>/`. Скрипт — `<skill>/scripts/trr` (эквивалент:
`python3 -m trr_impl <подкоманда>` из каталога `<skill>/scripts`).

## 0. Соглашение об обозначениях

```sh
TRR="${TRR:-$HOME/.config/opencode/skills/task-readiness-review/scripts/trr}"
SKILL_DIR="$(cd "$(dirname "$TRR")/.." && pwd)"
```

`<RUN-ID>` — UTC-момент старта прогона, `%Y-%m-%dT%H-%M-%SZ` (двоеточия заменены дефисами).
`<TASK-KEY>` — ключ Jira как есть (`E001-1234`).

### 0.1 Общие флаги `scripts/trr`

Есть у каждой подкоманды (родительский парсер `common` в `cli.py`):

| Флаг | Что делает |
|---|---|
| `--workdir <dir>` / `--root <dir>` | рабочая директория проекта; по умолчанию — поиск `task-readiness-review.yaml` вверх по дереву, затем текущий каталог |
| `--json` | машинный вывод одной строкой JSON (для скриптов и CI) |
| `--quiet` | печатать только ошибки |
| `--allow-external-file` | разрешает читать файл, переданный в `--file`, **вне рабочей директории**; по умолчанию такой путь запрещён (`[BLOCKED] --file вне рабочей директории`, код `2`) |

`--allow-external-file` — это ослабление защиты, а не удобство: `--file` участвует в подсчёте sha256
публикации, и путь вне проекта может указать на чужой/подменённый файл. Передавать флаг только
осознанно (например, бандл лежит в `/tmp` и пользователь это подтвердил). Для `artifact inspect` и
`artifact unpack` флаг не нужен: путь к скачанному бандлу законно лежит вне проекта.

## 1. Единая точка входа и подкоманды

Вызов: `/task-readiness-review <install|init|train|check|estimate|refresh|enrich|publish|doctor> [аргументы]`.
Первый токен — подкоманда, остаток передаётся ей без изменений. Без аргументов команда печатает справку,
текущий этап (`trr state get stage`) и следующую подкоманду по таблице переходов.

Флоу — обязательная последовательность:

```
install ──► init ──► train ──► check ──► estimate ──► publish
              │        ▲          │          │
              │        │          └─ refresh ◄┘    правки задачи → новый <RUN-ID> + delta.md
              │        │
              │        └── enrich ◄── новые спринты / уточнённый эталон
              │                     (trained|checked|estimated|published → trained → publish --model)
              └──► BLOCKED + .task-readiness/DATA-REQUIREMENTS.md
```

`train` — один раз на проект (повторно — только `enrich`); `check` обязателен перед `estimate`
(`estimate` без `check` возвращает `MISSING` (4)); `refresh` и `enrich` — боковые ветки; `doctor` — вне
цепочки и ничего не меняет.

Перенос модели — отдельная ось, не этап: `artifact pack` (собрать бандл) → публикация агентом →
`artifact record` (зафиксировать) при экспорте; `init --from-artifact` (развернуть бандл) при импорте.
Эти команды не двигают `stage` цепочки, кроме импорта, который сразу ставит `trained`.

| Подкоманда | Этап | Вход | Выход | Предусловия | Гейт | Идемпотентность |
|---|---|---|---|---|---|---|
| `install` | 5.1 install | `install.sh` (local) или релиз `skills/task-readiness-review/v<ver>` (remote); режимы `--global` (по умолчанию) / `--project <dir>` / `--dir <path>`; флаги `--dry-run/--force/--uninstall/--claude/--no-commands/--version/--local/--sha256/--insecure-host` | `<skills-dir>/task-readiness-review/` + маркер (`.task-readiness-review-installed` / `.task-readiness-review-project`) + `<command-dir>/task-readiness-review.md` | `sh`, `tar`, `sha256sum` или `shasum`; полный источник (`SKILL.md`, `VERSION`, обязательные элементы `BUNDLE_ITEMS`; `commands/` опционален — без него скилл ставится без команды) | нет `SKILL.md`/`VERSION`/элемента `BUNDLE_ITEMS` → отказ, `exit 1`; неизвестный флаг → `exit 2`; несовпадение sha256 фатально всегда | повторный запуск = обновление каталога с маркером; `--dry-run` ничего не пишет (и не создаёт каталог проекта); `--uninstall` трогает только артефакты с маркером; `--claude` ставит **дополнительно** в `~/.claude/skills` |
| `init` | 5.2 init | свободный текст («эталон в конфлюенсе …, спринты …») либо путь к yaml; `--from-artifact <bundle>` — переносимый бандл вместо обучения с нуля | `task-readiness-review.yaml`, `.task-readiness/resolved-sources.json` (ручная заготовка `manual`/`low`, если `sources.*` заполнены), `.task-readiness/state.json` (`stage=configured`; с `--from-artifact` — `stage=trained` + `norm/*`, `model/*`, `model_page`) | скилл установлен; доступ к Confluence/Jira проверен пробным чтением (с `--from-artifact` не нужен: данные приходят из бандла) | `< 1` reference или `< 1` sprint → `BLOCKED` (2) + `DATA-REQUIREMENTS.md`; конфиг не по схеме/с секретом → `CONFIG_ERROR` (3); пустой `evidence` → `SCHEMA_ERROR` (5); бандл: sha256/checksum не сошлись или чужой проект без `--allow-foreign-project` → `BLOCKED` (2)/`SCHEMA_ERROR` (5) | на существующем конфиге без `--force` → `BLOCKED` (2), файл не перезаписан; `--force` пересоздаёт конфиг и state (история прогонов теряется); `resolved-sources.json` пересобирается через `trr resolve-sources` (файл с источниками агента — только с `--re-resolve`) |
| `train` | 5.3 train | `resolved-sources.json`, эталон, задачи закрытых спринтов | `norm/reference-estimates.{json,md}`, `norm/sprint-sample.json`, `norm/sprint-stats.{json,md}`, `model/estimation-model.{json,md}`, `model/model-history.jsonl`, страница модели; при `artifacts.export_target != none` — бандл (`artifact pack` → публикация агентом → `artifact record`) | `config-check` = `OK`; `resolved-sources.json` валиден; доступ на чтение эталона/спринтов и на запись страницы модели | эталон недоступен / спринт не найден / поле отсутствует → `BLOCKED` (2) + `DATA-REQUIREMENTS.md`; `validate` → 5; бакет `n < min_sample_n` → `WARN` + `confidence=low` (не блок); страница не опубликована → `WARN`, `model_page=null`; место публикации бандла не задано → `[MISSING]` (2) на `artifact plan` до сборки | те же входы → тот же `checksum`: модель не переписана, версия не растёт, история не пополняется; повторный `artifact pack` при `TASK_READINESS_FIXED_TIME=1` даёт побайтово тот же архив |
| `check` | 5.4.1–5.4.3 | `--task <KEY>`, `[--with-dependencies]`, `[--run <RUN-ID>]`, `[--post]` (флаг слэш-команды), `[--no-jira]`, `[--draft]`, `[--comment-id <id>]`, `[--url <url>]` | `context.json`, `validation.json`, `questions.json`, `comment-draft.md`; `state.stage=checked`, запись в `runs[]`; при `comment_mode: post` — план комментария с вопросами (`[PLAN] questions comment: create\|update`) и запись `target=jira`, `ref=<KEY>#questions` в `published[]` после `--comment-id` | модель + `state.model_page ≠ null` + `model_page.hash == model.checksum`; задача читается | нет модели → `BLOCKED` (2) «модель оценки не обучена»; `model_page=null` → `BLOCKED` (2) «страница модели не опубликована»; `model_page.hash` ≠ текущей модели → `BLOCKED` (2) «страница модели устарела» (`/task-readiness-review publish --model`); `hash` нет → `WARN` (проверяет `trr check`, не ядро правил); нет `context.json` → `BLOCKED` (2); неполный `context.json` → `SCHEMA_ERROR` (5); `verdict=BLOCKED` — результат, код `0`; Jira недоступна → `WARN` (0) + `actions/jira-questions.md` | незавершённый прогон (без `estimate.json`) перезаписывает свои файлы; завершённый — новый `<RUN-ID>`; повторный `check` обновляет **тот же** комментарий с вопросами (`update`), а не создаёт второй |
| `estimate` | 5.4.4 + 5.5 | `--task <KEY>`, `[--run <RUN-ID>]` | `estimate.json`, `report.md`; дополненный `comment-draft.md`; `stage=estimated` | `validation.json` в прогоне; модель на месте (`context.json` — опционально, влияет на точность) | нет `validation.json` → `MISSING` (4) «сначала check»; нет модели → `MISSING` (4) «нет модели оценки»; нет бакетов → `SCHEMA_ERROR` (5); `verdict=BLOCKED` расчёт **не** блокирует | идентичные входы → байт-в-байт идентичный `estimate.json` (кроме `estimated_at`); завершённый прогон → новый `<RUN-ID>` |
| `refresh` | 5.6 | `--task <KEY>`, `[--force]` | новый `<RUN-ID>` с полным набором + `delta.md`; запись в `runs[]` | предыдущий прогон в `state.runs`; в нём есть `validation.json` + `estimate.json` | нет предыдущего прогона → `BLOCKED` (2); битый предыдущий → `SCHEMA_ERROR` (5), лечится новым полным прогоном | каждый запуск — новый `<RUN-ID>`; старые прогоны не перезаписываются никогда; при совпадении хеша снимка — `[OK] изменений нет` |
| `enrich` | 5.7 | список новых спринтов через запятую и/или новые/уточнённые эталонные страницы | обновлённые `norm/*`, `model/estimation-model.json` (`version+1`, **если входы изменились**), `model-history.jsonl` (+1 только вместе с версией), `norm/*.md`, `estimation-model.md` | подтверждённые человеком значения; право записи на страницу модели | новый спринт не найден → `BLOCKED` (2); несовместимое изменение эталона → `CONFLICT` (решает человек); правка ломает схему → `SCHEMA_ERROR` (5) | те же значения → тот же `checksum`, версия второй раз не растёт; повторная публикация перезаписывает страницу, а не создаёт дубль |
| `publish` | 6 | `<TASK-KEY>` (два комментария в задачу) либо `--model` + `--target`; `[--target confluence\|obsidian]`, `[--ref <id>]`, `[--url <url>]`, `[--file <path>]`, `[--model]`, `[--no-stage]`, `[--run <RUN-ID>]`, `[--plan-jira]`, `[--draft]`, `[--no-jira]`, `[--comment-id-validation <id>]`, `[--comment-id-estimate <id>]`, `[--comment-id <id>]` (легаси-алиас оценки), `[--post]` (флаг слэш-команды) | **по умолчанию два комментария в задачу Jira** (`jira.comment_mode: post`): `jira-validation.md` + `jira-estimate.md`, по плану `create\|update` на каждый, две записи `target=jira` (`ref=<KEY>#validation` и `ref=<KEY>#estimate`, у каждой свой `comment_id`, `marker`) в `state.published[]`, `stage=published`; `--target` — **дополнительно** страница/заметка (+`model_page` при `--model`, идёт с `--no-stage`; `--target obsidian` не требует сети и **достаточен для гейта `check`** — пишет `state.model_page` локально с тем же `hash`); `--run` берёт тела и пишет `actions/*` в указанный прогон (по умолчанию — последний на диске) | `validation.json` и `estimate.json` отрендерены; при `post` — право на комментарий в задачу; для `--target` — заполненный адрес (`space`/`path`) | Jira недоступна (MCP и REST) → `WARN` (0) + `actions/jira-validation.md` и `actions/jira-estimate.md`; `target=confluence` без `space`/`page_id` → `CONFIG_ERROR` (3); `--model` без `--target` → `BLOCKED` (2); тело > 32767 символов → обрезка по абзацу + `… (полный отчёт: <путь>)`; `--run` с несуществующим прогоном → `MISSING` (4), а в `--no-jira` — `[WARN]` без action-пакета | повторный `publish` **обновляет оба комментария** (`update` по `comment_id` каждого вида, без id — поиск по маркеру вида), а не создаёт вторые; страница/заметка обновляется по адресу из конфига |
| `doctor` | диагностика | `[--json]`, `[--quiet]`, `[--root <dir>]` | чек-лист `[OK]/[WARN]/[MISSING]/[BLOCKED]`; при `--json` — JSON-строка | скрипт установлен и исполняем | коды по приоритету `3 → 4 → 5 → 2`, иначе `0` | только чтение: файлов не создаёт, состояние не меняет |

## 2. Подкоманды `scripts/trr`, у которых нет одноимённой подкоманды команды

| Подкоманда | Аргументы | Что делает | Основной выход | Коды |
|---|---|---|---|---|
| `init` | `[--force] [--non-interactive] [--from-artifact <bundle>] [--allow-foreign-project]` | копирует пример конфига, валидирует, пишет `state.json`; при заполненных `sources.*` сразу пишет ручной `resolved-sources.json`. `--from-artifact` — разворачивает переносимый бандл (`.tar.gz`) вместо обучения с нуля: проверяет манифест и sha256, кладёт `norm/*` и `model/*`, ставит `stage=trained`, восстанавливает `state.model_page` (см. `artifacts.md` §9); `--allow-foreign-project` снимает блок импорта чужого проекта (остаётся `[WARN]`) | `stage=configured` либо `stage=trained` (с `--from-artifact`) | `0`, `2` (конфиг уже есть / чужой проект без `--allow-foreign-project`), `3`, `4` (нет примера/бандла), `5` (манифест или sha256 не сошлись) |
| `resolve-sources` | `[--re-resolve] [--agent <path>] [--recursive] [--pages-json <path>]` | пишет `.task-readiness/resolved-sources.json` из `sources.*`; без `--agent` — `manual`/`low`, с `--agent` — источники агента главнее; ручную заготовку пересобирает без флагов, файл с источниками агента защищает до `--re-resolve`; `--recursive` включает обход дочерних страниц (равно `sources.confluence.recursive: true`), `--pages-json` принимает дерево страниц от агента (`{id, title, parent_id, depth, body_excerpt}`) и добавляет их с `source_kind=agent`, `parent_ref`, `depth`; проверяет минимум данных | `resolved-sources.json` | `0`, `2` (файл с источниками агента / меньше минимума), `3`, `4` (нет файла агента), `5` |
| `match-sprints` | `--labels "<названия через запятую>" --sprints-file <json>` | сопоставляет `board_labels` с индексом спринтов Jira: точное → нормализованное → префиксное совпадение; `ambiguous`/`missing` не угадываются | `matched: … → id=…`, `ambiguous: …`, `missing: …` | `0`, `2` (есть `ambiguous`/`missing`), `4` (нет файла), `5` |
| `match-fields` | `--names-json <json> --fields-file <json>` | сопоставляет имена полей (`jira.field_names`) с `customfield_*` по нормализованному имени (без префиксного уровня) | `resolved: key → customfield_…`, `missing: …`, `ambiguous: …` | `0`, `2` (есть `ambiguous`/`missing`), `4`, `5` |
| `artifact pack` | `[--out <path>] [--no-sprint-sample]` | собирает переносимый бандл `.tar.gz` из `norm/*` и `model/*` + `manifest.json` с sha256 каждого файла; по умолчанию `.task-readiness/task-readiness-model-v<версия>.tar.gz`; детерминированный (фиксированные mtime/uid/mode) | `[OK] artifact: <путь> sha256=…`, `manifest.json` | `0`, `3` (нет/битый конфиг), `4` (нет модели/норм), `5` |
| `artifact inspect` | `<bundle>` | читает манифест без распаковки: версия формата, проект/борд/спринты, состав корпуса, файлы и их sha256 | сводка манифеста | `0`, `4` (нет файла), `5` (манифест не читается/не по схеме) |
| `artifact unpack` | `<bundle> [--force] [--allow-foreign-project]` | разворачивает бандл в `.task-readiness/`: проверяет `artifact_version`, каждый sha256 и `model.checksum`, сверяет `origin.project` с `jira.project` (чужой проект — `[WARN]` + `--allow-foreign-project`), ставит `stage=trained` и `state.model_page`; `--force` перезаписывает уже лежащие артефакты | `norm/*`, `model/*`, `stage=trained` | `0`, `2` (чужой проект без флага / уже развёрнуто без `--force`), `3` (нет/битый конфиг), `4`, `5` (sha256/checksum не сошлись) |
| `artifact plan` | `--target <local\|confluence\|gitlab\|obsidian>` | печатает, что и куда публиковать: адрес из `artifacts.<target>.*`, имя файла, чего не хватает; ничего не пишет | `[OK] artifact plan: <target>` + адрес либо `[MISSING] config.artifacts.<target>.<ключ>` | `0`, `2` (место публикации не задано), `3` |
| `artifact record` | `--target <local\|confluence\|gitlab\|obsidian> --ref <id> --url <url> [--file <path>]` | фиксирует факт публикации бандла в `state.artifacts[]` (идемпотентный upsert по `(target, ref)`); `--file` добавляет sha256 файла | `[OK] artifact: <target> <ref>` | `0`, `2` (неизвестная цель / битый state), `4` (нет файла бандла) |
| `config-check` | `[--config <path>]` | схема + семантические правила + запрет секретов по имени ключа | `[OK] config valid, sha256=…` | `0`, `3` |
| `doctor` | — | окружение и артефакты | чек-лист | `0`, `3`, `4`, `5`, `2` |
| `state get` | `<key>` | точечное чтение (`model_page.url`) | значение | `0`, `4` |
| `state set` | `<key> <value>` | запись значения (JSON-скаляр или строка); этап так не двигать — для публикации есть `publish` | `[OK] state.<key>` | `0`, `3`, `4` |
| `validate` | `<artifact> <path>` | проверка артефакта по схеме | `[OK] … соответствует схеме` | `0`, `3` (config), `4` (нет файла), `5` |
| `stats` | — | `norm/sprint-sample.json` → `norm/sprint-stats.json` | статистика по бакетам | `0`, `3`, `4`, `5` |
| `calibrate` | `[--reason train\|enrich]` | эталон + статистика → модель, `.md`-зеркала, история версий; причина пишется в историю, `enrich` разрешает откат этапа в `trained` | модель + `model-history.jsonl` | `0`, `3`, `4`, `5` |
| `vectors build` | `[--top-terms <N>] [--weight-word <W>] [--min-corpus <N>]` | `norm/task-texts.json` → `norm/task-vectors.json`: idf, гибридные векторы (word TF-IDF + char 3–5-граммы), калибровка порогов (`similar_threshold = p90` межбакетных косинусов, `dissimilar_threshold = p50`). Дефолты — из `estimation.vector` (`top_terms: 15`, `weight_word: 0.5`, `min_corpus: 30`). `train` не требуется | `norm/task-vectors.json` + `[OK] vectors: N задач, terms=…, threshold=…` | `0`, `2` (корпус меньше `min_corpus`), `4` (нет `task-texts.json`), `5` (файл не по схеме) |
| `vectors similar` | `--task <KEY>` \| `--text-file <path>` \| `--text "<строка>"`, `[--top <N>]`, `[--same-bucket]` | top-N ближайших задач корпуса к задаче или к произвольному тексту; ничего не пишет. `--same-bucket` с `--text` даёт `[WARN]` (у текста нет бакета). Вывод — таблица `cos / key / role / work_kind / sp` или JSON (`--json`) | `[OK]`-таблица соседей + `calibration` в JSON | `0`, `2` (не задан запрос), `4` (нет `task-vectors.json` / задачи нет в корпусе), `5` (артефакт не по схеме или чужой `normalizer.id`) |
| `vectors calibrate` | — | пересчитывает `calibration` по уже собранным векторам и перезаписывает `norm/task-vectors.json`; `[WARN] калибровка ненадёжна (пар < 50)` при малом числе межбакетных пар | `[OK] vectors calibrate: similar=… dissimilar=… pairs=… corpus=…` | `0`, `4` (нет `task-vectors.json`), `5` (артефакт не по схеме) |
| `check` | `--task <KEY> [--with-dependencies] [--run <RUN-ID>] [--draft] [--no-jira] [--comment-id <id>] [--url <url>]` | гейт модели + правила по `context.json`; при `comment_mode: post` печатает план комментария с вопросами, `--comment-id` пишет id в `state.published[]` | `validation.json`, `questions.json`, `comment-draft.md` | `0`, `2`, `3`, `4` (`--comment-id` без `comment-draft.md`), `5` |
| `estimate` | `--task <KEY> [--run <RUN-ID>]` | расчёт по модели | `estimate.json` | `0`, `4`, `5` |
| `report` | `[--task <KEY>] [--run <RUN-ID>] [--delta] [--model]` | рендер отчёта / дельты / страницы модели | `report.md`, `delta.md`, `estimation-model.md` | `0`, `2` (нет предыдущего прогона), `4` (нет прогона/артефакта/JSON модели) |
| `publish` | `--task <KEY> [--run <RUN-ID>] [--plan-jira] [--draft] [--no-jira] [--comment-id-validation <id>] [--comment-id-estimate <id>] [--comment-id <id>] [--url <url>] [--target <confluence\|obsidian> --ref <id> --url <url> --file <path>] [--model] [--no-stage]` | по умолчанию — два комментария в задачу: готовит тела `jira-validation.md` и `jira-estimate.md`, печатает по плану `create\|update` на каждый, с `--comment-id-validation`/`--comment-id-estimate` пишет две записи `target=jira` в `state.published[]` (sha256 тела) и ставит `stage=published`; `--run` — явный прогон для тел и `actions/*`; `--plan-jira`/`--draft` ничего не пишут; `--target` — дополнительная публикация страницы/заметки, при `--model` — `state.model_page` | `[PLAN] jira comment (validation\|estimate): create\|update …` (две строки) + `[OK] тело комментария (…)` либо `[OK] publish: jira <KEY>#validation\|#estimate comment_id=…` | `0`, `2`, `4` (нет `validation.json`/`estimate.json`/`state.json`/файла/прогона из `--run`), `5` |
| `render-norm` | — | перерисовка трёх `.md`-зеркал без пересчёта | `reference-estimates.md`, `sprint-stats.md`, `estimation-model.md` | `0`, `4`, `2` |
| `model-hash` | — | `sha256` и версия модели | `sha256:… version:N` | `0`, `4`, `5` |
| `model-page-payload` | `[--format json\|storage\|md] [--out <path>] [--title <text>] [--page-version N]` | готовит тело страницы модели: `md` — `model/estimation-model.md`; `storage` — Confluence storage XHTML (заголовки, таблицы, `<ac:structured-macro ac:name="code">`, списки, inline `<code>`/`<strong>`, XML-экранирование вне CDATA); `json` (по умолчанию) — тело `POST`/`PUT`: `action` (`create` при `page_id=null`, `update` при `id` в `state.model_page`), `page_id`, `title` («Модель оценки Story Points (версия N)» или `--title`), `space`, `parent_id`, `model_version` (версия модели), `page_version` и его синоним `version` (версия страницы для `PUT`: `--page-version`, иначе `state.model_page.version` + `[WARN]` — там лежит версия **модели**, а не страницы), `body_storage`, `model_checksum`, `body_sha256`, `body_bytes`. Ничего не публикует и не меняет `state` | `json` одной строкой, `storage`/`md` — как есть; `--out` — файл + `[OK] model-page-payload: … action=… page_version=… model_version=…` | `0`, `3` (нет конфига для `json`), `4` (нет модели), `5` (JSON не читается) |
| `snapshot-hash` | `--task <KEY> [--file <path>] [--run <RUN-ID>]` | sha256 канонического JSON подмножества снимка задачи (`SNAPSHOT_FIELDS`: `task_key`, `issue_type`, `role`, `work_kind`, `sp`, `qa_estimation`, `labels`, `fields`, `sections`); по умолчанию — `context.json` последнего прогона, `--file` — любой файл снимка (свежий снимок из Jira) | `sha256:<hex>` одной строкой | `0`, `4` (нет прогона/файла), `5` (битый JSON) |
| `diff-values` | `--task <KEY> (--field <name> … \| --all)` | сравнивает `context.json` двух последних прогонов и печатает `field: old → new` построчно; `--field` — точечный путь (`sp`, `fields.status`), `--all` — все ключи верхнего уровня, кроме волатильных (`sources`) | строки различий (пусто + `[OK] различий нет`) | `0` (различий нет), `2` (различия есть — это ответ, а не сбой), `4` (прогонов меньше двух), `5` |
| `merge-sample` | `[--target <path>] [--source <path>]` | вливает `.task-readiness/.sprint-sample-new.json` в `norm/sprint-sample.json`: дедупликация по `key`, сортировка по `(sprint, key)`, дедупликация спринтов по `id`, проверка схемой до записи | `[OK] добавлено строк: N, спринтов: M — всего строк X, спринтов Y` | `0`, `4` (нет файла), `5` (не проходит схему) |
| `synth` | `--count <N> --out <dir> [--seed <N>] [--from-sprints <ids>] [--include-edge] [--sample <path>] [--coverage-all-buckets\|--no-coverage-all-buckets] [--coverage-quota <N>]` | строит синтетический полигон: `N` снимков задач из реальных комбинаций `norm/sprint-sample.json` (роль, тип, метки) с вариацией наполненности; пишет `contexts.jsonl` + `manifest.json`. Детерминирован: один `--seed` → побайтно один файл. `--from-sprints` — id спринтов Jira (`20365,20366`), имена берутся из `model.sources.sprints`. `--include-edge` — 2 % edge-случаев (пустое/100 КБ описание, 100 связей, юникод, код-блоки, HTML, тип/роль вне словаря, все поля null), каждый вид гарантированно встречается. `--coverage-all-buckets` (по умолчанию включён) — покрытие троек модели: `--coverage-quota` (по умолчанию 20) снимков на каждую тройку `(role, issue_type, work_kind)` из `estimation-model.json`, раскладка равномерная по датасету; 20 троек × 20 = 400 задач на 10 000, остальное — по осям выборки. `--no-coverage-all-buckets` — выключить покрытие (оси только из выборки) | `contexts.jsonl`, `manifest.json` (seed, count, фактические распределения, версия и checksum модели, блок `coverage`: `triples`, `quota`, `planned`, `min_per_triple`, `counts`) | `0`, `2` (`--out` внутри `runs/`, неизвестный id спринта), `4` (нет выборки/модели), `5` |
| `synth-run` | `--dir <dir> [--out <dir2>] [--limit <N>] [--workers <N>]` | прогоняет `check` + `estimate` **в одном процессе** по `contexts.jsonl`: `run_checks(context, default_rules(), with_dependencies=False)` → `estimate(validation, model, context=context)`. Ничего не пишет в `.task-readiness/runs/`; модель только читает. `--workers` — `ThreadPoolExecutor`, результат сортируется по `case_id`. `--limit` — быстрый прогон. Метрики: вердикты, ошибки, schema failures, scale/range/param инварианты, монотонность `weight`/`heat`/`connectivity`, детерминизм 100 задач, покрытие 20 бакетов модели, распределение `expected` против `_expected_sp`, тайминги p50/p95 | `summary.json`, `records.jsonl` | `0` — инварианты чистые; `2` — есть неожиданные ошибки или нарушения инвариантов (разбор в `summary.json`); `4` — нет `contexts.jsonl`/модели |
| `selftest` | — | парсер YAML, 10 схем, канонический JSON, цепочка этапов | `[OK] selftest` | `0`, `5` |

Имена артефактов для `validate`: `config`, `resolved-sources`, `reference-estimates`, `sprint-sample`,
`sprint-stats`, `estimation-model`, `validation`, `questions`, `estimate`, `state`,
`artifact-manifest`, `task-texts`, `task-vectors`.

## 3. Типовые цепочки

### 3.1 Первый запуск в проекте

```text
/task-readiness-review install
/task-readiness-review init "эталон оценки указан на странице в конфлюенсе https://…/T100+Story+Points, спринты T100-T102 26.18, T100-T102 26.19"
/task-readiness-review train
/task-readiness-review check E001-1234
/task-readiness-review estimate E001-1234
/task-readiness-review publish E001-1234        # комментарий с результатом в задачу (по умолчанию)
```

Проверка после установки: `$TRR selftest`; после `init` — `$TRR doctor` (ожидаемы `[MISSING]` на
`norm/*` и модели: обучение ещё не проходило); после `train` — `$TRR model-hash` и
`$TRR state get model_page`.

### 3.2 Повторная оценка другой задачи

```text
/task-readiness-review check E001-5678
/task-readiness-review estimate E001-5678
/task-readiness-review publish E001-5678      # комментарий с результатом в задачу
```

`train` не нужен: модель читается из `model/estimation-model.json`. Если `check` отвечает
`[BLOCKED] check: модель оценки не обучена` — модель удалена или проект новый, тогда `train`.

### 3.3 Обновление знаний (новый спринт, правка эталона)

```text
/task-readiness-review enrich "T100-T102 26.23, T100-T102 26.24"
/task-readiness-review publish --model
```

`enrich` поднимает версию модели только если входы изменились; при неизменных входах модель не
переписывается — `calibrate` печатает `[OK] входы не изменились, версия N не переписана`. Когда версия
выросла, страница модели остаётся старой, пока не выполнена перепубликация; без неё `check` будет
`BLOCKED` (гейт `state.model_page`).

### 3.4 После правок задачи

```text
/task-readiness-review refresh E001-1234
```

Если снимок не изменился — `[OK] изменений нет` и выхода нет; если изменился — новый `<RUN-ID>`,
`delta.md` и обновлённые `validation.json`/`estimate.json`/`report.md`.

### 3.5 Диагностика «ничего не работает»

```text
/task-readiness-review doctor
```

Дальше — по строкам: `[MISSING] config` → `init`; `[MISSING] model` → `train`;
`[BLOCKED] страница модели не опубликована` → `publish --model` (в проекте без Confluence —
`publish --model --target obsidian --ref local --url .task-readiness/model/estimation-model.md
--file .task-readiness/model/estimation-model.md --no-stage`: офлайн, без сети, гейт `check`
закрывается); `[WARN] env … не задана` — только если нужен REST fallback.

### 3.6 Перенос обученной модели в другой проект (экспорт)

```text
$TRR artifact pack --out .task-readiness/artifacts/abc-model.tar.gz
$TRR artifact inspect .task-readiness/artifacts/abc-model.tar.gz
$TRR artifact plan --target confluence    # адрес из artifacts.confluence.*
# публикация — агентом: Confluence (вложение), GitLab (файл в ветке), Obsidian (заметка), local (копия)
$TRR artifact record --target confluence --ref 4279119874 --url https://… --file …/abc-model.tar.gz
```

`artifact pack` собирает архив и манифест, `inspect` показывает, что внутри (проект, спринты, версия
модели), `plan --target` сверяет выбранную цель с заполненностью `artifacts.<target>.*`. Публикует
**агент** через MCP/REST; `record` фиксирует факт в `state.artifacts[]` (повторный вызов обновляет ту же
запись по `(target, ref)`, дубля нет).

### 3.7 Работа на перенесённой модели (импорт)

```text
$TRR init --from-artifact abc-model.tar.gz      # вместо install→init→train
$TRR doctor
/task-readiness-review check E001-1234
```

`--from-artifact` разворачивает `norm/*` и `model/*`, ставит `stage=trained` и восстанавливает
`state.model_page` из `published_page` манифеста — `train` и `publish --model` не нужны. Если проект в
манифесте не совпадает с `jira.project`, импорт блокируется (`2`) до явного `--allow-foreign-project`:
модель чужого проекта даст смещённую оценку. Проверка `doctor` после импорта должна быть чистой; если
`[WARN] артефакт не опубликован` — это значит, что бандл собран без `published_page`.

### 3.8 Похожие задачи по тексту (векторизация, этап A)

```
тексты задач (агент, norm/task-texts.json)
        →  trr vectors build
        →  trr vectors similar --task <KEY>            # проверить соседей глазами
        →  estimation.vector.enabled: true             # (+ adjust_range — только осознанно)
        →  check → estimate → report                   # секция 9 «Похожие задачи (справочно)»
```

```sh
$TRR validate task-texts .task-readiness/norm/task-texts.json
$TRR vectors build --min-corpus 30
$TRR validate task-vectors .task-readiness/norm/task-vectors.json
$TRR vectors similar --task E001-1234 --top 5
$TRR vectors calibrate            # если пороги надо пересчитать без пересборки
```

- `vectors build` работает на любом `norm/task-texts.json`: `train` и обученная модель ему не нужны.
- Меньше `min_corpus` задач — `[BLOCKED]` (2): добавьте спринты через `enrich` и пересоберите тексты.
- `similar` ничего не пишет: это справка «на что похожа задача и сколько стоили соседи».
- В отчёте секция 9 появляется только при непустом `similar_tasks[]`; при `enabled: false` её нет и
  нумерация остаётся 1–8. Подробности — `vectorization.md`.

### 3.9 Локальное SQLite-зеркало

```
любой шаг пайплайна (stats/calibrate/vectors/check/estimate/publish/state)
        →  .task-readiness/trr.sqlite3 (после успеха шага, ошибка БД — только [WARN])
        →  trr db ingest                       # если артефакты появились до включения зеркала
        →  trr db query --sql "SELECT …"       # только чтение
        →  trr db export --out dump.json       # JSON-дамп всех таблиц
```

```sh
$TRR db init                    # создать/мигрировать, идемпотентно
$TRR db check                   # integrity_check=ok, user_version, счётчики, размер
$TRR db ingest                  # бэкфилл из norm/*, model/*, runs/*, state.json
$TRR db stats                   # таблица → строк
$TRR db query --sql "SELECT role, work_kind, value FROM reference_buckets ORDER BY value"
$TRR db query --sql "DROP TABLE meta"    # отказ: только SELECT/WITH/PRAGMA (код 2)
$TRR db export --out /tmp/trr-export.json
```

- Зеркало **включено по умолчанию** (`storage.sqlite.enabled: true`); `false` — `trr db …` даёт
  `[BLOCKED]` (2), файл не создаётся.
- Файлы остаются источником истины: БД не читается ни одним шагом, чтобы посчитать результат.
- `db query` открывает файл как `mode=ro` и пропускает только `SELECT`/`WITH`/`PRAGMA` без присваивания.
- Схема и таблицы — `artifacts.md` §10; ключи конфига — `config.md` §10.

### 3.10 Перепубликация страницы модели (идемпотентно)

Повторная публикация модели (после `calibrate`/`enrich` или ручной правки шаблона) — воспроизводимая
цепочка: тело готовит скрипт, публикует агент через REST, факт фиксирует `publish --model`.

```sh
$TRR calibrate --reason train                                  # 1. модель + estimation-model.md
# 2. агент: GET /rest/api/content/$PAGE_ID?expand=version  → фактическая version (например 5)
$TRR model-page-payload --format json --page-version 6 \
  --out /tmp/model.payload.json                               # 3. тело PUT/POST
# 4. агент: PUT /rest/api/content/$PAGE_ID  (version=page_version=фактическая+1,
#           title/space/ancestors из payload, body.storage.value=body_storage)
#           action=create → POST /rest/api/content
$TRR publish --model --target confluence --ref "$PAGE_ID" \
  --url "https://space.samokat.ru/pages/viewpage.action?pageId=$PAGE_ID" \
  --file .task-readiness/model/estimation-model.md --no-stage  # 5. state.model_page + published[]
$TRR state get model_page && $TRR doctor                       # 6. hash == model.checksum, нет BLOCKED
```

- `model-page-payload` ничего не пишет: `--format md|storage|json`, `--out` — в файл, иначе stdout.
  Версия страницы и версия модели — разные числа, в payload они разделены: `model_version` и
  `page_version` (`version` — синоним `page_version` для тела `PUT`).
- `--page-version N` — **фактическая версия страницы + 1** из `GET ?expand=version`. Без флага
  `page_version` берётся из `state.model_page.version`, где лежит версия **модели**, поэтому команда
  печатает `[WARN]` о ручной сверке; `PUT` с неверным номером → `409 Conflict`.
- `publish --model` идемпотентен по `(target, ref)`: второй вызов печатает `action=update`, обновляет ту
  же запись в `state.published[]` и ту же строку в таблице `publications` — второй публикации нет.
- `--no-stage` обязателен: страница модели публикуется на `trained`/`enriched` и не должна двигать этап.
- Гейт `check`: `state.model_page.hash == model.checksum`; расхождение — `[BLOCKED]` (2) «страница
  модели устарела».
- **Проект без Confluence (офлайн):** шаги 2–4 не нужны — `$TRR publish --model --target obsidian
  --ref local --url .task-readiness/model/estimation-model.md --file
  .task-readiness/model/estimation-model.md --no-stage` пишет `state.model_page` локально, без сети, с
  тем же `hash`; этого достаточно, чтобы гейт `check` прошёл.

### 3.11 Синтетический полигон (проверка модели и правил на объёме)

```bash
# 1. 10 000 снимков из реальных комбинаций выборки; ~1 с, ~50 МБ
$TRR synth --count 10000 --out /tmp/trr-synth --seed 42

# 2. прогон check+estimate в одном процессе (не subprocess на задачу)
$TRR synth-run --dir /tmp/trr-synth --out /tmp/trr-synth-out --workers 4 --json

# быстрый смоук: 200 задач, включая edge-случаи
$TRR synth --count 200 --out /tmp/trr-synth-smoke --seed 42 --include-edge
$TRR synth-run --dir /tmp/trr-synth-smoke --limit 200

# без записи в SQLite (по умолчанию прогон пишется, если storage.sqlite.enabled)
$TRR synth-run --dir /tmp/trr-synth --out /tmp/trr-synth-out --no-record

# покрытие троек модели: 20 снимков на каждую тройку (по умолчанию), затем — оси выборки
$TRR synth --count 10000 --out /tmp/trr-synth-cov --seed 43 --include-edge
# выключить покрытие или изменить квоту
$TRR synth --count 10000 --out /tmp/trr-synth-nocov --seed 43 --no-coverage-all-buckets
$TRR synth --count 10000 --out /tmp/trr-synth-q40 --seed 43 --coverage-quota 40
```

- `synth` — **генератор**, `synth-run` — **харнесс**. Первый детерминирован: `--seed 42` дважды даёт
  побайтно один `contexts.jsonl` (`sha256sum` совпадает), поэтому прогоны сравнимы между собой.
- Покрытие троек (`--coverage-all-buckets`, по умолчанию) делает `buckets.hit = buckets.reachable`:
  каждая тройка `(role, issue_type, work_kind)` модели встречается не менее `--coverage-quota` раз
  (400 задач на 10 000 при квоте 20). Тройка задаётся прямо в снимке (`role`, `issue_type`,
  `work_kind` — легальный ключ `check.CONTEXT_KEYS`), а не подбором осей выборки. ГПСЧ не расходуется
  иначе, поэтому датасет с тем же seed остаётся детерминированным, а «до/после» сравнимо на старом
  датасете (`buckets.hit` там остаётся прежним — оси не перегенерируются).
- Харнесс не создаёт прогонов задач: `contexts.jsonl` читается в память, `validation`/`estimate`
  считаются функциями (`check.run_checks` + `estimate.estimate`), на диск попадают только
  `summary.json` и `records.jsonl` в `--out`. В `.task-readiness/runs/` основного проекта он не пишет;
  `--out` внутри `runs/` отклоняется кодом `2`.
- Модель **только читается** (`.task-readiness/model/estimation-model.json`); версия и checksum
  попадают в `manifest.json` и `summary.json`, чтобы прогон нельзя было спутать с другим.
- Код выхода `2` — это результат измерения, а не сбой инструмента: `summary.json` содержит примеры
  нарушений (schema, scale, range, params, монотонность). Код `4` — нет `contexts.jsonl`/модели.
- Ни задач Jira, ни страниц Confluence полигон не создаёт и не публикует: это офлайн-проверка
  арифметики и каталога правил.

**Запись в SQLite (`--record`).** По умолчанию `synth-run` пишет результат в зеркало, если
`storage.sqlite.enabled: true`; `--no-record` выключает запись, `--record` включает явно. Пишется:

| Куда | Что |
|------|-----|
| `synth_runs` | одна строка на прогон: `run_id`, `created_at`, `seed`, `count`, `model_checksum`, `summary` (полный `summary.json` как JSON-текст) |
| `metrics` (`scope='synth'`) | числовые метрики прогона: `total`, `ok`, `warn`, `blocked`, `errors`, `unestimable`, `unexpected_errors`, `schema_failures`, `scale_violations`, `range_violations`, `param_violations`, `monotonicity_violations`, `buckets_hit`, `buckets_total`, `buckets_reachable`, `buckets_probe`, `p50_ms`, `p95_ms` |

`run_id` детерминирован (`synth-<seed>-<sha256[:12]>` от `summary` без `timing`/`harness`): повторный
прогон того же датасета обновляет ту же строку, а не плодит дубли. `metrics` — журнал, строки копятся:
по ним видно тренд между прогонами. Схема БД — `user_version=4`.

```bash
# что записалось
$TRR db query "SELECT run_id, seed, count, created_at FROM synth_runs ORDER BY created_at"
$TRR db query "SELECT name, value FROM metrics WHERE scope='synth' ORDER BY id DESC LIMIT 20"
```

## 4. Коды выхода `scripts/trr` и что делать

Приоритет при нескольких проблемах: `3 → 4 → 5 → 2`.

| Код | Имя | Когда | Что делать |
|---|---|---|---|
| `0` | OK | успех, в том числе `WARN` (малая выборка, недоступная публикация, нехватка токена) | идти дальше; `WARN` показать пользователю, но не выдавать за ошибку |
| `2` | BLOCKED | гейт не пройден: нет данных, нет обученной модели, нет `context.json`, конфиг уже существует, спринт/поле не сопоставились однозначно, бандл из чужого проекта без `--allow-foreign-project`, место публикации бандла не задано | прочитать строку `[BLOCKED] … — <что сделать>`, выполнить названный этап; при нехватке данных — `DATA-REQUIREMENTS.md` |
| `3` | CONFIG_ERROR | конфиг отсутствует, не разбирается, нарушает схему, содержит секрет, некуда публиковать | `$TRR config-check` покажет путь до поля; править `task-readiness-review.yaml` (секреты — только env) |
| `4` | MISSING_ARTIFACT | нет обязательного файла: модели, `validation.json`, `estimate.json`, `report.md`, `sprint-sample.json`, примера конфига | создать названным этапом (`train` / `check` / `estimate` / `init`), не подкладывать файл из другого проекта |
| `5` | SCHEMA_ERROR | артефакт есть, но не соответствует схеме (в т.ч. неполный `context.json`, неизвестное имя артефакта, повреждённая модель — `check` отвечает `[MISSING] check: модель не читается`) | `$TRR validate <artifact> <path>` даст путь до поля; перечитать источник и перезаписать артефакт (модель — пересборкой, не правкой JSON: `troubleshooting.md` §22) |

Правило чтения диагностики: `[OK]` — проверка пройдена; `[WARN]` — работа возможна, но качество ниже
(показывать); `[MISSING]` — нужного артефакта/входа нет **или** он нечитаем (код уточняет причину:
`3` — конфиг, `4` — файла нет, `5` — битый/не по схеме; строка печатается и для существующего файла);
`[BLOCKED]` — гейт не пройден (файл есть, но не годен, либо не выполнено предусловие этапа). У
`[MISSING]` и `[BLOCKED]` после `—` всегда стоит, что сделать; если действия нет — это баг, а не подсказка.

Отдельно про модель: `check` считает sha256 модели раньше, чем применяет правила, поэтому битый
`model/estimation-model.json` — это код `5` со строкой `[MISSING] check: модель не читается — …`, а не
`BLOCKED` (`troubleshooting.md` §22). Расхождение `state.model_page.hash` с текущей моделью — наоборот,
`BLOCKED` (2) «страница модели устарела», и `doctor` с недавних пор печатает ту же строку.

# Справочник артефактов

Полный перечень файлов, которые скилл `task-readiness-review` читает и пишет: путь, кто создаёт, кто
потребляет, какая схема действует, обязателен файл или нет, что он означает и что делать, если его нет.
Нормативный источник — `CONTRACT.md` §2, §5, §8; этапы и гейты — `pipeline.md`; ключи конфига — `config.md`.

## 0. Общие правила

- **Все пути — относительно корня проекта** (`--root`, алиас `--workdir`; по умолчанию — поиск
  `task-readiness-review.yaml` вверх по дереву, затем текущая директория). Артефакты скилла (схемы, шаблоны)
  живут внутри установленного скилла и помечены `<skill>/…`.
- **Пишет только Python, читает и Python, и агент.** Сеть из Python не ходит: Confluence/Jira/Obsidian
  читает агент через MCP, Python работает с уже положенными файлами.
- **JSON пишется детерминированно**: `json.dumps(sort_keys=True, ensure_ascii=False, indent=2)` + ровно
  один `\n`, UTF-8, перевод строки `\n` (без CRLF). Одинаковый вход → байт-в-байт одинаковый файл.
- **Время внутри вычисляемых полей** допускается только в `resolved_at`, `retrieved_at`, `computed_at`,
  `generated_at`, `checked_at`, `estimated_at`, `updated_at`. Всё остальное от времени не зависит.
- **Секретов в артефактах нет.** Токены — только из переменных окружения (`JIRA_TOKEN`,
  `CONFLUENCE_TOKEN`, `GITLAB_TOKEN`).
- **Запись атомарна**: временный файл в том же каталоге + `os.replace`. Оборванная запись не оставляет
  полуфайла; `.tmp`-файлы после успеха не остаются.

## 1. Сводная таблица

| Путь | Производитель | Схема | Обязателен |
|---|---|---|---|
| `task-readiness-review.yaml` | `init` (копия примера), правит человек | `config.schema.json` | да |
| `.task-readiness/state.json` | `init`, `train`, `check`, `estimate`, `publish`, `enrich` | `state.schema.json` | да |
| `.task-readiness/resolved-sources.json` | `init` (агент резолвит, Python нормализует) | `resolved-sources.schema.json` | да |
| `.task-readiness/DATA-REQUIREMENTS.md` | `init`/`train` при `BLOCKED` | — | только при `BLOCKED` |
| `.task-readiness/norm/reference-estimates.json` | `train` (агент вычитывает эталон) | `reference-estimates.schema.json` | да для `train` |
| `.task-readiness/norm/reference-estimates.md` | `calibrate` (рендер), `render-norm` | — | нет |
| `.task-readiness/norm/sprint-sample.json` | `train` (агент вычитывает спринты) | `sprint-sample.schema.json` | да для `train` |
| `.task-readiness/norm/sprint-stats.json` | `stats` | `sprint-stats.schema.json` | да для `calibrate` |
| `.task-readiness/norm/sprint-stats.md` | `calibrate` (рендер), `render-norm` | — | нет |
| `.task-readiness/model/estimation-model.json` | `calibrate` | `estimation-model.schema.json` | да для `check`/`estimate` |
| `.task-readiness/model/estimation-model.md` | `calibrate` (`report.render_model_page`), `report --model`, `render-norm` | — | нет по схеме; `doctor` без него — `MISSING` (4) |
| `.task-readiness/model/model-history.jsonl` | `calibrate`/`enrich` | — | нет |
| `.task-readiness/norm/task-texts.json` | агент на `train`/`enrich` (вычитывает тексты из Jira) | `task-texts.schema.json` | да для `vectors build` |
| `.task-readiness/norm/task-vectors.json` | `trr vectors build` | `task-vectors.schema.json` | да для секции 9 / `similar` |
| `.task-readiness/artifacts/<name>.tar.gz` | `artifact pack` | `artifact-manifest.schema.json` (манифест внутри) | нет |
| `.task-readiness/runs/<KEY>/<RUN-ID>/context.json` | `check` (заполняет агент) | не фиксируется жёстко | да для `estimate` |
| `.task-readiness/runs/<KEY>/<RUN-ID>/validation.json` | `check` | `validation.schema.json` | да |
| `.task-readiness/runs/<KEY>/<RUN-ID>/questions.json` | `check` | `questions.schema.json` | да |
| `.task-readiness/runs/<KEY>/<RUN-ID>/estimate.json` | `estimate` | `estimate.schema.json` | да для `report` |
| `.task-readiness/runs/<KEY>/<RUN-ID>/report.md` | `report` | — | да после `estimate` |
| `.task-readiness/runs/<KEY>/<RUN-ID>/delta.md` | `report --delta` / `refresh` | — | только при наличии предыдущего прогона |
| `.task-readiness/runs/<KEY>/<RUN-ID>/comment-draft.md` | `check` | — | да (создаётся всегда) |
| `.task-readiness/runs/<KEY>/<RUN-ID>/jira-validation.md` | `publish` | — | да при `comment_mode: post` (тело комментария «Результаты валидации» с маркером) |
| `.task-readiness/runs/<KEY>/<RUN-ID>/jira-estimate.md` | `publish` | — | да при `comment_mode: post` (тело комментария «Результаты оценки» с маркером) |
| `.task-readiness/runs/<KEY>/<RUN-ID>/actions/jira-validation.md` | `publish`/`check` при недоступности Jira | — | только при `WARN` + ручной публикации |
| `.task-readiness/runs/<KEY>/<RUN-ID>/actions/jira-estimate.md` | `publish` при недоступности Jira | — | только при `WARN` + ручной публикации |
| `.task-readiness/trr.sqlite3` | любой шаг пайплайна (`stats`, `calibrate`, `vectors`, `check`, `estimate`, `publish`, `state`), `db init`/`db ingest` | `PRAGMA user_version` = 1 (см. §10) | нет — зеркало, файлы остаются источником истины |

## 2. Артефакты корня и `.task-readiness/`

### 2.1 `task-readiness-review.yaml`

- **Производитель:** `init` копирует `<skill>/task-readiness-review.example.yaml`; дальше файл правит
  человек. `init --force` перезаписывает.
- **Потребитель:** все подкоманды через `config.load_config` + `config.validate_config`.
- **Схема:** `config.schema.json` (schema version 1.3).
- **Обязателен:** да. Без него любая подкоманда — `CONFIG_ERROR` (3).
- **Что означает:** единственный файл настроек проекта: источники, порог выборки, поля Jira, куда
  публиковать. Секретов в нём быть не может.
- **Нет файла:** `[MISSING] config: task-readiness-review.yaml — скопируйте пример из скилла и заполните
  sources.reference и sources.sprints`; запустите `/task-readiness-review init`.
- **Подробности:** `config.md`.

### 2.2 `.task-readiness/state.json`

- **Производитель:** `init` (создаёт, `stage=configured`), затем этапы `train`, `check`,
  `estimate`, `enrich`, `publish`. Этап выставляют модули (`calibrate.py`, `check.py`, `estimate.py`,
  `state.add_publication`), а не ручной `state set`.
- **Потребитель:** `doctor` (проверяет то же условие свежести, что и гейт `check`:
  `model_page.hash` == `model.checksum`), гейты этапов (`check` требует `state.model_page ≠ null` и
  совпадения `model_page.hash` с текущим `model.checksum`; сам `stage` при этом не проверяется),
  `publish` (id опубликованной страницы).
- **Схема:** `state.schema.json`.
- **Обязателен:** да.
- **Что означает:** «где мы в конвейере». `stage` только растёт по цепочке
  `installed → configured → trained → checked → estimated → published`; единственный разрешённый откат —
  `trained` после `enrich` с `reason="enrich"`. `runs[]` — история прогонов, отсортированная по
  `(task_key, run_dir)`.
- **`published[]` (опционально):** история публикаций отчётов, комментариев в задачу и страниц модели.
  Поле не входит в `required`: отсутствие ключа означает «публикаций ещё не было» (`default_state`
  создаёт `published: []`). Каждая запись — `target` (`confluence|jira|obsidian`), `ref` (id страницы
  Confluence, ключ задачи Jira с суффиксом вида комментария — `<KEY>#validation`, `<KEY>#estimate`,
  `<KEY>#questions` — или путь заметки Obsidian), `url`, `published_at` (UTC), `content_sha256`
  опубликованного текста; опционально `comment_id` (id комментария Jira) и `marker` (маркер
  идемпотентности в его теле). Пишется через
  `trr publish` → `state.add_publication`; дедупликация по `(target, ref)` — повторная публикация в ту же
  цель обновляет запись (новые `published_at` и `content_sha256`), а не плодит дубликаты; при обновлении
  без `comment_id`/`marker` прежние значения сохраняются. Список отсортирован по `(target, ref)`.
  Успешная публикация отчёта/комментария переводит `stage` в `published`; публикация страницы модели идёт
  с `--no-stage` и этап не двигает.
- **Правило «один комментарий на задачу на вид»:** для задачи может быть не больше трёх записей
  `target=jira` — `ref=<KEY>#validation` (результаты валидации), `ref=<KEY>#estimate` (результаты оценки)
  и `ref=<KEY>#questions` (вопросы). Каждый вид обновляется на месте: `comment_id` из записи → `update`;
  id потерян → комментарий ищется по маркеру своего вида, второй не создаётся. Запись `ref=<KEY>` без
  суффикса — легаси версии 0.2.x (единственный комментарий «отчёт»): при апгрейде оценка находит её и
  обновляет старый комментарий, а не создаёт второй; если новый вид фиксируется на том же `comment_id`,
  легаси-запись удаляется — две записи не должны делить один id.
- **`artifacts[]` (опционально):** история публикаций **обученного бандла** (не отчёта). Каждая запись —
  `target` (`local|confluence|gitlab|obsidian`), `ref` (id страницы/путь в GitLab/путь заметки/локальный
  путь), `url`, `published_at` (UTC), `artifact_sha256` (sha256 файла `.tar.gz`; `null` — файл не передан)
  и `manifest_checksum` (checksum модели на момент публикации, с префиксом `sha256:`; `null` — модели не
  было). Пишется только `trr artifact record`; дедупликация по `(target, ref)`, сортировка по
  `(target, ref)`. `doctor` сравнивает `manifest_checksum` с текущим `model.checksum` и предупреждает
  `[WARN] бандл модели старше модели`, если после `enrich` бандл не пересобирали.
- **Нет файла:** `[MISSING] state.json — запустите /task-readiness-review init`; `init` создаст его заново
  (`init --force` пересоздаёт и конфиг).

### 2.3 `.task-readiness/resolved-sources.json`

- **Производитель:** `init` (ручная заготовка, если `sources.*` заполнены) и `trr resolve-sources`.
  Агент находит источники через MCP и передаёт список с `evidence` (`--agent`); Python
  (`sources.merge_resolved`) нормализует свободный текст конфига, дополняет недостающие поля,
  сортирует и валидирует схемой. Без `--agent` файл пишется в ручном режиме: `resolution_method=manual`,
  `confidence=low`, `evidence` — исходная строка конфига, `title` — заглушка из `ref` (настоящий
  заголовок дописывает агент), `page_id` не выдумывается.
- **Потребитель:** `train` (что читать), `sources.check_readiness` (гейт данных), `doctor`,
  `sources.sprint_keys` (ярлык провенанса `sprints:26.18..26.22`).
- **Схема:** `resolved-sources.schema.json`.
- **Обязателен:** да.
- **Что означает:** «чем именно подтверждён каждый источник». У каждого элемента 8 полей:
  `kind` (`reference|sprint`), `system` (`confluence|jira|obsidian|file`), `ref`, `title`, `url`
  (`null` допустим), `resolution_method` (`confluence_search|confluence_url|obsidian_search|obsidian_path|jira_sprint_search|manual`),
  `evidence` (непустой), `confidence` (`high|medium|low`). Список отсортирован по `(kind, system, ref)`.
- **Гейт:** минимум один `kind=reference`, минимум один `kind=sprint`, у каждого источника непустой
  `evidence`. Нарушение — `BLOCKED` (2) с сообщением `[BLOCKED] … — …`.
- **Нет файла / пусто:** `[BLOCKED] источники: нет .task-readiness/resolved-sources.json — запустите
  /task-readiness-review init и заполните sources.reference и sources.sprints`; параллельно создаётся
  `DATA-REQUIREMENTS.md`.

### 2.4 `.task-readiness/DATA-REQUIREMENTS.md`

- **Производитель:** `init`/`train` при `BLOCKED`.
- **Потребитель:** человек и агент: что нужно получить, где взять, кому адресован вопрос.
- **Схема:** нет (Markdown).
- **Обязателен:** только при `BLOCKED`; при успехе файла быть не должно.
- **Что означает:** чек-лист недостающих данных. Числа «на глаз» не подставляются — вместо них файл
  требований.
- **Нет файла при `BLOCKED`:** это баг — перезапустите этап; сообщения `[BLOCKED]` в stdout содержат тот
  же перечень.

## 3. Нормализованные данные: `norm/`

### 3.1 `norm/reference-estimates.json`

- **Производитель:** `train` — эталонную таблицу Story Points вычитывает агент (MCP → REST → `BLOCKED`).
- **Потребитель:** `calibrate` (база бакетов), `report.render_model_page`.
- **Схема:** `reference-estimates.schema.json`.
- **Обязателен:** да для `train`.
- **Что означает:** эталон как данные: `source{system,page_id,url,title,retrieved_at,version,space_key}`,
  `scale` (ровно 7 значений), `buckets[]` (`role`, `work_kind`, `value`, `description`, `evidence`,
  необязательные `level`, `example_count`, `params_hint`), `levels[]` (полная матрица таблицы),
  `absent_roles[]` (роли, которых в эталоне нет) и необязательный `absent_roles_note` — чем именно
  проверено отсутствие.
  `value` обязан быть элементом шкалы; дубликат `(role, work_kind)` — `SCHEMA_ERROR`.
- **`levels[]` — это и есть матрица 7×8.** Отдельного ключа `matrix` нет: строка источника = элемент
  `levels`, колонки — поля элемента. `sp` (колонка «Кол-во»), `description`, `uncertainty`,
  `refactoring`, `research`, `decomposition`, `time` — дословный текст ячеек, `null` если ячейка
  пуста; `examples` — `{BE:[…], FE:[…], QA:[…]}` из bold-подзаголовков внутри колонки «Примеры»
  (нет подзаголовка — нет ключа). `params_hint` — приор уровня (`weight`/`heat`), формула —
  `references/estimation-model.md` §13.6. Поле необязательное: артефакт без `levels` валиден, и
  `calibrate` его не читает — модель строится по `buckets[]`.
- **Промежуточный артефакт:** `norm/reference-table.raw.json` — сырой разбор таблицы (все 7 строк,
  все 58 примеров, включая пример строки SP=21 без подзаголовка роли в `examples_unassigned`).
  Схемы у него нет, скилл его не читает: он нужен, чтобы любой мог перепроверить `levels[]`/`buckets[]`
  против источника, не заходя в Confluence.
- **Нет файла:** `[BLOCKED] train: нет norm/reference-estimates.json — прочитайте эталон и повторите
  /task-readiness-review train`; причина недоступности фиксируется в `DATA-REQUIREMENTS.md`.

### 3.2 `norm/reference-estimates.md`

- **Производитель:** `calibrate` — рендер `report.render_reference_estimates` из уже записанного
  `reference-estimates.json` (в обеих ветках: и при изменении входов, и когда они не изменились).
  `trr render-norm` перерисовывает зеркало без пересчёта модели.
- **Потребитель:** человек (глазами), публикация страницы модели.
- **Схема:** нет.
- **Обязателен:** нет.
- **Что означает:** человекочитаемое зеркало `reference-estimates.json` для ревью: видно, откуда взялось
  каждое значение шкалы. Разделы: шапка источника (включая версию страницы и пространство), **полная
  матрица эталонной таблицы** (SP · описание · 4 маркера · примерное время · число примеров по ролям),
  приоры уровней (`weight`/`heat`) и бакеты с `level`, `example_count`, приорами и цитатой. `null`-ячейки
  печатаются как `N/A`, а не роняют рендер. Числа берутся из JSON, не пересчитываются.
- **Нет файла:** ничего не блокирует; пересоздаётся `calibrate` или `trr render-norm` (ошибка рендера —
  `[WARN]`, модель при этом остаётся валидной).

### 3.3 `norm/sprint-sample.json`

- **Производитель:** `train` — спринты и задачи вычитывает агент.
- **Потребитель:** `stats`.
- **Схема:** `sprint-sample.schema.json`.
- **Обязателен:** да для `train`/`stats`.
- **Что означает:** сырая выборка: `source{board_id,sprints[],retrieved_at,transport}` + `rows[]` с 10
  полями. `sp`/`qa_estimation` — число или `null` (никогда `""`/`0` вместо «нет данных»),
  `has_testing` — boolean, `summary_sha256` — sha256 текста задачи (сам текст не хранится),
  `labels` — отсортированный массив.
- **Нет файла:** `[BLOCKED] stats: нет norm/sprint-sample.json — прочитайте закрытые спринты и повторите
  /task-readiness-review train`.

### 3.4 `norm/sprint-stats.json`

- **Производитель:** `stats` (чистый расчёт из `sprint-sample.json`).
- **Потребитель:** `calibrate`.
- **Схема:** `sprint-stats.schema.json`.
- **Обязателен:** да для `calibrate`.
- **Что означает:** агрегаты по бакетам `(role, issue_type, work_kind)`: `n`, `mean`, `median`, `p25`,
  `p75`, `min`, `max`, `coverage` (`sufficient` при `n >= min_sample_n`, иначе `insufficient`).
  `insufficient[]` — строки `"<role>/<work_kind>"`. Перцентили — линейная интерполяция, округление до 2
  знаков.
- **Нет файла:** `[MISSING] norm/sprint-stats.json — запустите /task-readiness-review train` (подкоманда `stats`).

### 3.5 `norm/sprint-stats.md`

- **Производитель:** `calibrate` — рендер `report.render_sprint_stats` из уже записанного
  `sprint-stats.json` (в обеих ветках `calibrate`). `trr render-norm` перерисовывает зеркало без
  пересчёта модели.
- **Потребитель:** человек.
- **Схема:** нет.
- **Обязателен:** нет.
- **Что означает:** таблица бакетов с пометкой недостаточной выборки — чтобы `WARN` был виден без чтения
  JSON. Числа берутся из JSON, не пересчитываются.
- **Нет файла:** не блокирует; пересоздаётся `calibrate` или `trr render-norm` (ошибка рендера —
  `[WARN]`).

### 3.6 `norm/task-texts.json` и `norm/task-vectors.json` — векторизация (этап A)

Оба файла реализованы и пишутся в `.task-readiness/norm/`. Оба входят в бандл `artifact pack`
(см. §9.1), поэтому переносятся вместе с моделью.

- **`norm/task-texts.json`** — производитель: **агент** на `train`/`enrich` (Python в Jira не ходит).
  Схема — `task-texts.schema.json`. Обязателен для `trr vectors build`; без него — `[MISSING]` (4).
  Ключи верхнего уровня: `built_at`, `source{sprints[], retrieved_at}`, `tasks[]`; задача —
  `key`, `summary`, `text`, `role`, `work_kind`, `issue_type`, `sp`, `qa_estimation`, `has_testing`.
  `summary` — заголовок как в Jira, `text` — конкатенация секций описания без заголовка (оба могут
  быть пустыми). Текст хранится отдельным файлом, а не в `sprint-sample.json` (там только
  `summary_sha256`), чтобы статистика оставалась без текста задачи.
- **`norm/task-vectors.json`** — производитель: `trr vectors build` (пересчёт порогов —
  `trr vectors calibrate`). Схема — `task-vectors.schema.json`. Нужен для `trr vectors similar`
  и для секции 9 отчёта. Ключи верхнего уровня: `version`, `built_at`,
  `normalizer{id, lang, truncate, char_ngrams, stopwords_sha256}`, `top_terms`, `weight_word`,
  `weight_char`, `idf[[term, value]]`, `calibration{similar_threshold, dissimilar_threshold,
  corpus_rows, method, dissimilar_method, pairs, confidence}`, `vectors[]`; вектор —
  `key`, `role`, `work_kind`, `sp`, `qa_estimation`, `terms[[term, weight]]`, `norm`.
- **Пороги не задаются числом:** `similar_threshold = p90` межбакетных косинусов
  (`method: p90_inter`), `dissimilar_threshold = p50` (`dissimilar_method: p50_inter`); меньше
  50 пар — `confidence: low` и `[WARN]` в CLI.
- **Чувствительность:** `task-texts.json` — потенциально чувствительные данные (описания задач).
  Отдельного ключа «не класть тексты в бандл» в конфиге нет: `artifacts.include_sprint_sample`
  управляет только `norm/sprint-sample.json`. Если тексты не должны уезжать в общий
  GitLab/Confluence — файл исключается из бандла вручную (осознанное решение команды).
- **Импорт бандла векторы не пересчитывает:** `artifact unpack` / `init --from-artifact`
  разворачивают `norm/task-vectors.json` как есть, и `vectors similar` работает сразу, если
  `calibration.corpus_rows >= estimation.vector.min_corpus` (иначе `estimate` печатает `[WARN]` и
  считает без соседей).
- **Нет файлов:** при `estimation.vector.enabled: true` (дефолт) это незавершённый `train`, а не норма:
  `train` обязан собрать оба файла. `estimate` без `task-vectors.json` печатает
  `[WARN] estimate: векторы включены, но norm/task-vectors.json нет — запустите trr vectors build;
  оценка без похожих задач` и считает по бакетам; `trr doctor` показывает проблему. Норма — только
  при осознанном `enabled: false`. Подробности — `vectorization.md`.


## 4. Модель: `model/`

### 4.1 `model/estimation-model.json`

- **Производитель:** `calibrate` (из `reference-estimates.json` + `sprint-stats.json`); `enrich` даёт
  `version+1`, только если входы изменились (иначе версия не переписывается).
- **Потребитель:** `check` (гейт), `estimate`, `report`, `report.render_model_page`, `model-hash`.
- **Схема:** `estimation-model.schema.json`.
- **Обязателен:** да для `check`/`estimate`; для `check` дополнительно нужен `state.model_page ≠ null`
  и `state.model_page.hash`, совпадающий с `checksum` текущей модели (гейт свежести `trr check`, код 2;
  артефакт без `hash` — только `WARN`).
- **Что означает:** правила оценки как данные. `buckets[]` — `base`, `factor`, `expected`, `range`, `n`,
  `confidence`, `reference` (`yes|none`), `provenance[]` (минимум `base`/`factor`/`expected`);
  `gap_rules[]` — `rule_id`, `condition`, `penalty_steps` (1–2), `applies_to[]`; `absent_roles[]`;
  `sources{reference,sprints[]}`; `params` — настройки множителя `weight`/`heat`/`connectivity`;
  `resources` — настройки надбавки `RS-01` (`rule_id`, `enabled`, `sp_per_resource`, `mode`,
  `items` — каталог «ресурс → алиасы», `provenance[]`). `checksum` = sha256 канонического JSON
  **без** поля `checksum`. `buckets` отсортированы по `(role, issue_type, work_kind)`,
  `gap_rules` — по `rule_id`.
- **Нет файла:** `[MISSING] .task-readiness/model/estimation-model.json — запустите
  /task-readiness-review train`.
- **Версионирование:** версия только растёт; `train` без изменений входов версию не меняет и файл не
  переписывает.

### 4.2 `model/estimation-model.md`

- **Производитель:** `calibrate` через `report.render_model_page(model, <skill>/templates/model-page.md)`;
  `trr report --model` и `trr render-norm` перерисовывают страницу из существующего JSON без пересчёта.
- **Потребитель:** человек, публикация страницы модели (`publish`).
- **Схема:** нет.
- **Обязателен:** нет по схеме; `trr doctor` считает отсутствие `MISSING` (код 4) — страница модели
  нужна для публикации, поэтому её отсутствие видно как проблема окружения.
- **Что означает:** страница «как скилл валидирует и оценивает задачи» — 16 секций, все данные
  артефактов без пересказа: шапка (версия, checksum, `generated_at`, шкала, версия скилла); источники
  (`sources.reference` целиком — system, page_id, title, space, url, version, retrieved_at;
  `sources.sprints[]` — id, name, state, start, end); матрица эталона 7 × 8 (SP, описание, четыре
  маркера, время, примеры BE/FE/QA) и приоры уровней; роли модели; формула по бакетам; `absent_roles`
  и `insufficient`; 10 бакетов эталона с `evidence`; статистика 20 бакетов (`n, mean, median, p25, p75,
  min, max, coverage`, `sample_rows`); 20 бакетов модели (`base, factor, params_multiplier, expected,
  range, n, confidence, reference, params_profile_source`); провенанс каждой записи (`field, kind,
  source, detail`); `gap_rules` (`rule_id, condition, penalty_steps, applies_to`); блок `params`
  (enabled, clamp, коэффициенты и `coefficients_source`, defaults, `profile_source`, провенанс);
  подраздел §5.1 страницы модели (`templates/model-page.md`) и блок `resources` (правило `RS-01`: enabled, `sp_per_resource`, mode, каталог
  ресурсов с алиасами, провенанс).
  Слот без данных рендерится как `N/A (нет данных в источнике)`; таблицы собираются в
  `report.model_page_slots` и рендерятся в `templates/model-page.md`.
- **Нет файла:** `check` не блокирует; `doctor` — `[MISSING] … — запустите /task-readiness-review train
  (описание модели не отрендерено)`; пересоздаётся `calibrate`, `trr report --model` или `trr render-norm`.

### 4.3 `model/model-history.jsonl`

- **Производитель:** `calibrate`, `enrich`.
- **Потребитель:** человек, аудит версий.
- **Схема:** нет; по одной JSON-строке на версию.
- **Обязателен:** нет.
- **Что означает:** `{"version":N,"generated_at":"…","checksum":"…","reason":"train|enrich"}`. Позволяет
  доказать, что модель не переписывалась «назад».
- **Нет файла:** не блокирует; следующая калибровка начнёт историю заново (версия при этом не
  сбрасывается в JSON модели).

## 5. Прогон задачи: `runs/<TASK-KEY>/<RUN-ID>/`

### 5.1 `context.json`

- **Производитель:** `check` — агент заполняет рабочий вход Python.
- **Потребитель:** `check` (правила), `estimate`, `report`.
- **Схема:** жёстко не фиксируется, но обязательны 10 ключей: `task_key`, `issue_type`, `role`,
  `work_kind`, `sp`, `qa_estimation`, `labels`, `fields{}`, `sections{}`, `sources[]`. Нет любого из них —
  `SCHEMA_ERROR` (5). Дополнительные ключи (например, `has_testing`) допускаются: `check` пересчитывает
  `has_testing` правилом `QA-01`.
- **Необязательные ключи, которые читают правила:**
  - `fields.absent_in_project` — список полей, которых **нет в проекте** задачи (`"Команда"`, `"Sprint"`,
    `"Роль"`, `"Story Points"`, `"Эпик"`, `"Связи"`). Правила `TPL-02/05/07/08/10/11` отвечают `NA`
    вместо `FAIL`: «поля нет в проекте» и «поле не заполнено» — разные факты. Ключа нет — поведение
    прежнее;
  - `sections.task` / `sections.solution` — объём работ («Решение», «Тех.решение», «Задача», «Что нужно
    сделать»): основание `SA-08`. Если блок оставлен заголовком в `description`, правило найдёт его само;
  - `dependencies` / `documentation` — для `DEP-01…DEP-03` (`--with-dependencies`).
- **Обязателен:** да для `check` (снимок — вход правил). `estimate` без `context.json` не падает, но
  `work_kind` молча становится `implementation`, а роли берутся из всех бакетов модели — точность падает.
- **Что означает:** что именно прочитано из задачи: поля Jira, извлечённые блоки описания, ссылки с
  провенансом, выбранный `work_kind`.
- **Нет файла:** отдельного гейта у `estimate` нет — оценка считается, но грубее (см. выше). Снимок
  пересобирается через `/task-readiness-review check`.

### 5.2 `validation.json`

- **Производитель:** `check`.
- **Потребитель:** `estimate` (штраф за REQUIRED-пробелы), `report`, `refresh` (diff), `state.runs[]`.
- **Схема:** `validation.schema.json`.
- **Обязателен:** да.
- **Что означает:** по одной записи на правило (`id`, `section`, `severity`, `status`, `evidence`,
  `message`, необязательное `why`), итоговый `verdict` (`OK|BLOCKED|WARN`), `gaps[]` — по одной записи
  на каждый `FAIL`/`UNKNOWN` со `severity != OPTIONAL` — и необязательный блок `analysis` с метриками
  содержательного анализа (`clarity`, `testability`, `reproduction`, `scope`, `dependencies`,
  `scenarios`, `area`, `ambiguity`, `signals`). `checks` и `gaps` отсортированы по `id`.
  Вердикт: `BLOCKED` — `FAIL`/`UNKNOWN` у `REQUIRED` (`CL-01` и `SA-08` — других `REQUIRED` в
  каталоге нет), `WARN` — у `RECOMMENDED`, `OPTIONAL` вердикт не меняет.
- **`work_intent[]`** (rules version 4) — что делается по задаче: `{intent, confidence, evidence,
  source}`. Восемь intent-ов: `schema_migration`, `data_migration`, `data_export`, `dashboard`,
  `integration`, `refactor`, `test_coverage`, `research`. Собирается из заголовка, описания и
  `sections{}` (кроме «Цели»); различает «миграцию данных» (`insert into`, «загрузить») и «миграции»
  (`alter table`, «создать схемы»). Ось **справочная**: на `verdict` и числа оценки не влияет, в отчёте
  печатается строкой «Что делается: …». Поле объявлено в `validation.schema.json` (схема запрещает
  неизвестные ключи).
- **Нет файла:** `[MISSING] .task-readiness/runs/<KEY>/<RUN-ID>/validation.json — сначала /task-readiness-review check`.

### 5.3 `questions.json`

- **Производитель:** `check`.
- **Потребитель:** агент (комментарий в Jira), человек.
- **Схема:** `questions.schema.json`.
- **Обязателен:** да (создаётся вместе с `validation.json`).
- **Что означает:** готовые вопросы по пробелам: `id` = `"q." + id пробела`, `text`, `why`,
  `target_role`, `where_to_find`, `blocking` (true для REQUIRED), `comment_draft_path`.
- **Нет файла:** не блокирует оценку; пересоздаётся `check`.

### 5.4 `estimate.json`

- **Производитель:** `estimate`.
- **Потребитель:** `report`, `refresh`/`delta.md`, `state.runs[]`.
- **Схема:** `estimate.schema.json`.
- **Обязателен:** да для `report`.
- **Что означает:** числа по ролям (`expected`, `range`, три сценария `base|optimistic|pessimistic`,
  `confidence`, непустой `provenance[]`), `total`, `variability_reason[]`, `blocked_by_gaps[]`;
  необязательная копия `analysis` из `validation.json` (чтобы отчёт читал блок «Что видно из задачи»
  без соседнего файла).
  `roles[]` — только роли, для которых есть работа, отсортированы по `role`. Роль в снимке не указана →
  оценивается одна доминирующая роль вида работ и появляется необязательное `role_assumed: true`
  (`provenance` роли содержит `field=role, source=estimate:role-assumed`); суммы по всем ролям модели
  в этом случае нет.
- **QA:** отдельная запись `role=QA` (необязательные `source: jira|model|derived|assumed` и
  `qa_bucket`), слагаемое `total.expected`/`total.range` и необязательный блок
  `total.qa {expected, source, bucket}`. Пустое `qa_estimation` не блокирует проверку (`QA-01` всегда
  `PASS`): при типе задачи из `validation.qa_required_issue_types` QA считается по QA-бакету
  (`source=derived`), иначе записи нет и появляется необязательный `qa_scope` — «не требуется
  (тип «…») — проверка результата входит в объём роли …».
- **Нет файла:** `[BLOCKED] report: нет estimate.json — сначала /task-readiness-review estimate`.

### 5.5 `report.md`

- **Производитель:** `report` (рендер `<skill>/templates/report.md`). Подкоманда `trr estimate` пишет только
  `estimate.json`; отчёт рендерит отдельный `trr report`, который команда `/task-readiness-review estimate`
  запускает сразу после расчёта.
- **Потребитель:** человек, `publish`.
- **Схема:** нет.
- **Обязателен:** да после `estimate`.
- **Что означает:** отчёт из восьми фиксированных секций: задача → вердикт → блокирующие пробелы →
  уточнения → оценка по ролям → вариативность → провенанс → как перегенерировать. Секции 3–4 —
  компактные блоки: заголовок с числом пробелов, до трёх пунктов «чего не хватает — почему это влияет»,
  строка «и ещё N», ссылка на целевой шаблон (`validation.template_url`) и путь к `validation.json`;
  секции 6–7 — по 1–2 предложения. Числа не переформатируются, слот без данных — `N/A (нет данных в
  источнике)`; полные списки остаются в `validation.json`/`estimate.json`.
- **Нет файла:** `[BLOCKED] report: нет report.md — запустите /task-readiness-review estimate` (команда
  `report`).

### 5.6 `delta.md`

- **Производитель:** `report --delta` (или `refresh`).
- **Потребитель:** человек, `publish`.
- **Схема:** нет.
- **Обязателен:** нет; создаётся, только когда есть предыдущий прогон.
- **Что означает:** что изменилось между прогонами: вердикт, оценка по ролям, итог, закрытые/открытые
  пробелы.
- **Нет предыдущего прогона:** `[BLOCKED] delta: нет предыдущего прогона — сначала
  /task-readiness-review refresh`.

### 5.7 `comment-draft.md`

- **Производитель:** `check` (создаётся всегда).
- **Потребитель:** агент, человек; при `comment_mode: post` — тело комментария с вопросами (маркер
  `<!-- task-readiness-review:questions:<TASK-KEY> -->` добавляется при публикации), при `draft` — только
  файл.
- **Схема:** нет.
- **Обязателен:** да (создаётся всегда).
- **Что означает:** черновик комментария в Jira с вопросами по пробелам. `comment_mode: post` — вопросы
  публикуются в задачу (повторный `check` обновляет тот же комментарий, `ref=<KEY>#questions`);
  `draft`/`--no-jira`/`--draft` — только файл.
- **Нет файла:** не блокирует; пересоздаётся `check`.

### 5.8 `jira-validation.md` и `jira-estimate.md`

- **Производитель:** `publish` (при `comment_mode: post`).
- **Потребитель:** агент — ровно эти тексты публикуются в задачу; человек — при ручной публикации.
- **Схема:** нет.
- **Обязателен:** нет (создаются при обычном запуске `publish`; `--plan-jira`/`--draft` их не пишут).
- **Что означает:** готовые тела двух комментариев. Первая строка каждого — свой маркер
  идемпотентности: `<!-- task-readiness-review:validation:<TASK-KEY> -->` и
  `<!-- task-readiness-review:estimate:<TASK-KEY> -->`. Дальше — текст
  `report.render_validation_comment` / `report.render_estimate_comment` (эталон формата —
  `templates/jira-validation-comment.md`, `templates/jira-estimate-comment.md`): валидация — вердикт,
  пробелы, гигиена полей; оценка — итог, таблица ролей, основания, похожие задачи. Длиннее лимита Jira
  (32767 символов) — обрезается по границе абзаца, в хвост дописывается `… (полный отчёт: <путь>)`;
  на штатном формате обрезка не срабатывает.
- **Нет файла:** `publish` соберёт его заново из `validation.json`/`estimate.json`; нет артефакта →
  `MISSING` (4).

### 5.9 `actions/jira-validation.md` и `actions/jira-estimate.md`

- **Производитель:** `publish` при недоступности Jira (MCP и REST) или `401/403`.
- **Потребитель:** человек: что именно опубликовать и как зафиксировать id.
- **Схема:** нет.
- **Обязателен:** только при `WARN`; при успешной публикации файлов быть не должно.
- **Что означает:** готовый текст комментария, маркер, шаги «найти комментарий по маркеру → обновить (PUT)
  или создать (POST) → `trr publish --task <KEY> --comment-id-validation <id>` (либо
  `--comment-id-estimate`)». `stage` не двигается.

## 6. Правила именования директории прогона

```
.task-readiness/runs/<TASK-KEY>/<RUN-ID>/
```

- `<TASK-KEY>` — ключ Jira как есть (`E001-1234`), без нормализации: регистр и дефис сохраняются.
- `<RUN-ID>` — момент старта прогона в **UTC**, формат `%Y-%m-%dT%H-%M-%SZ`, например
  `2026-11-17T09-41-07Z`. Двоеточия заменены на дефисы, чтобы путь был валиден на любой ФС.
- **Один прогон — одна директория.** Артефакты прогона не переписывают артефакты другого `<RUN-ID>`.
- Повторный `check`/`estimate` **дописывает** файлы в тот же `<RUN-ID>`, если прогон не завершён (нет
  `estimate.json`); иначе создаётся новый `<RUN-ID>`.
- «Последний прогон» — лексикографически максимальное имя: формат `%Y-%m-%dT%H-%M-%SZ` сортируется
  хронологически.
- Путь прогона не влияет на содержимое артефактов: одинаковые данные в разных `<RUN-ID>` дают одинаковые
  `validation.json`/`estimate.json` (кроме полей времени).

## 7. Контракт слотов шаблонов отчёта

Шаблоны `<skill>/templates/report.md` и `model-page.md` — Markdown со слотами `{{slot}}`.
`delta.md` пока рендерится встроенным резервным шаблоном `report.DEFAULT_DELTA_TEMPLATE`.
Рендерер (`report.py`) подставляет значения по правилам:

- **Скалярный слот** подставляется один раз. Нет данных — `N/A (нет данных в источнике)`.
  Неизвестный слот — тоже `N/A`: шаблон не может «тихо» оставить пустое место.
- **Слот-строка** (`{{gap_id}}`, `{{role_name}}`, `{{prov_role}}`, `{{variability_line}}`) размножает
  всю строку шаблона по элементам массива. Наборы строк привязаны к секциям:

| Секция | Группа | Источник строк |
|---|---|---|
| 3 | `gap` | `validation.gaps[]` со `severity=REQUIRED` |
| 4 | `gap` | `validation.gaps[]` с остальными `severity` |
| 5 | `role` | `estimate.roles[]` (порядок `BA, SA, BE, FE, QA, DEVOPS, OTHER`) |
| 6 | `variability` | `estimate.variability_reason[]` (по строке на причину) |
| 7 | `prov` | `estimate.roles[].provenance[]` (по строке на запись) |

- Секции 3+4 вместе дают **ровно** `validation.gaps` без повторов и добавлений (в табличных шаблонах);
  секция 5 — ровно `estimate.roles`; секция 7 — ровно записи `provenance[]` (табличные слоты).
- **Компактные блоки (по умолчанию).** Стандартный шаблон печатает секции 3–4 одним скалярным слотом
  `{{gaps_required_block}}` / `{{gaps_optional_block}}`: заголовок, до `MAX_COMPACT_GAPS = 3` пунктов
  (порядок — severity, затем `id`), «и ещё N», ссылка на шаблон и путь к `validation.json`. Секции 6–7 —
  скаляры `{{variability_summary}}` / `{{provenance_summary}}` (1–2 предложения). Слоты-строки
  `{{gap_*}}`, `{{variability_*}}`, `{{prov_*}}` и таблицы (`gaps_table`, `provenance_table`) остаются
  для пользовательских шаблонов.
- **HTML-комментарии** шаблона (`<!-- SLOTS … -->`) — документация: слоты внутри них не подставляются и в
  готовый артефакт комментарии не попадают.
- **Маркер комментария добавляет рендерер, а не шаблон.** `report.md` — самостоятельный файл без маркера;
  при публикации в задачу `publish` собирает два тела: `jira-validation.md` (первая строка
  `<!-- task-readiness-review:validation:<TASK-KEY> -->`) и `jira-estimate.md` (первая строка
  `<!-- task-readiness-review:estimate:<TASK-KEY> -->`); дальше — текст соответствующего рендера без
  HTML-комментариев (и с обрезкой до 32767 символов).
- Порядок ролей фиксирован и не зависит от порядка в JSON; числа печатаются как в JSON (`1.0`, `1.25`),
  без округлений и процентов «на глаз».

## 8. Что коммитить в git, а что нет

`.task-readiness/` — **рабочие артефакты проекта, по умолчанию не коммитятся**. В `.gitignore` проекта
достаточно строки:

```gitignore
.task-readiness/
```

Почему: там лежат прогоны (`runs/`), снимки чужих страниц (`norm/`) и состояние этапов (`state.json`) —
это результат чтения внешних систем, а не исходники; они устаревают и шумят в диффах.

Исключение — **`model/estimation-model.json` можно коммитить как общий артефакт**: это правила оценки,
согласованные командой (шкала, бакеты, штрафы), и их полезно видеть в ревью. Если коммитите модель,
коммитьте и `model/estimation-model.md` (человекочитаемое зеркало) — иначе ревью пойдёт по JSON.
Правило `.gitignore`, разрешающее только модель:

```gitignore
.task-readiness/*
!.task-readiness/model/
.task-readiness/model/*
!.task-readiness/model/estimation-model.json
!.task-readiness/model/estimation-model.md
```

Что не коммитить никогда:

- `task-readiness-review.yaml` — конфиг конкретного проекта и конкретной машины (его создаёт `init`);
- `.task-readiness/state.json` — локальное состояние этапов;
- `.task-readiness/runs/**` — прогоны задач;
- `.task-readiness/norm/**` — снимки внешних страниц и спринтов;
- `.task-readiness/DATA-REQUIREMENTS.md` — рабочий чек-лист нехватки данных;
- `.task-readiness/trr.sqlite3` (и `-wal`/`-shm`) — локальное зеркало: бинарный файл, растёт от прогонов,
  в диффах бесполезен. Он восстанавливается из артефактов командой `trr db ingest`;
- любые `*.tmp` — их не должно оставаться после записи.

Скилл **никогда** не делает `git commit` / `git push` — ни при каких флагах. Решение о коммите
принимает человек.

## 9. Бандл обученной модели (`artifacts/`)

Перенос модели в другой проект — это **архив с манифестом**, а не копия каталога: манифест доказывает
происхождение и целостность. Формат описан `schemas/artifact-manifest.schema.json`.

### 9.1 Что внутри

```
<name>.tar.gz
├── manifest.json
├── norm/reference-estimates.json
├── norm/sprint-sample.json        # только при artifacts.include_sprint_sample: true
├── norm/task-texts.json           # если есть (тексты задач для векторов)
├── norm/sprint-stats.json
├── norm/task-vectors.json         # если есть (векторы, собранные `trr vectors build`)
├── model/estimation-model.json
└── model/estimation-model.md
```

Порядок файлов в `files[]` и в архиве фиксирован (`artifact.FILE_ORDER`: `manifest.json`,
`reference-estimates.json`, `sprint-sample.json`, `task-texts.json`, `sprint-stats.json`,
`task-vectors.json`, `estimation-model.json`, `estimation-model.md`); `manifest.json` в `files[]` не
входит — он не может содержать свой собственный sha256.

`norm/task-texts.json` и `norm/task-vectors.json` кладутся в бандл **как есть**, если существуют:
`artifact unpack` их не пересчитывает, поэтому на новом месте `trr vectors similar` работает сразу, а
`estimate` при `estimation.vector.enabled: true` получает соседей без `trr vectors build` — при условии,
что `calibration.corpus_rows >= estimation.vector.min_corpus`. Помните, что `task-texts.json` содержит
описания задач: отдельного ключа «исключить тексты» в конфиге нет (`artifacts.include_sprint_sample`
управляет только `sprint-sample.json`), поэтому при экспорте в общий GitLab/Confluence это осознанное
решение команды; иначе файл исключается из бандла вручную.


### 9.2 `manifest.json`

Обязательные поля (схема `artifact-manifest`):

| Поле | Что означает |
|---|---|
| `artifact_version` | версия формата, сейчас ровно `1`; иная — `SCHEMA_ERROR` (5) при распаковке |
| `created_at` | UTC-момент сборки; при `TASK_READINESS_FIXED_TIME=1` — `1970-01-01T00:00:00Z` (воспроизводимость) |
| `skill_version` | версия скилла из `VERSION` |
| `model{version,checksum,scale,buckets,absent_roles}` | сводка модели; `checksum` — `sha256:…` без поля `checksum` |
| `origin{project,board_id,sprints,reference_page_id,reference_url}` | откуда обучена; `project` сверяется с `jira.project` |
| `corpus{rows,sprints,insufficient_buckets}` | состав корпуса |
| `files[{path,sha256,bytes}]` | каждый файл бандла |
| `published_page{system,id,url,hash}` | опубликованная страница модели или `null` |

### 9.3 Команды

| Команда | Что делает | Коды |
|---|---|---|
| `trr artifact pack [--out <path>] [--no-sprint-sample]` | собирает `.tar.gz` + манифест | `0`, `4` (нет модели/норм), `5` |
| `trr artifact inspect <bundle>` | читает манифест без распаковки | `0`, `4`, `5` |
| `trr artifact unpack <bundle> [--force] [--allow-foreign-project]` | проверяет `artifact_version`, sha256 и `model.checksum`, разворачивает `norm/*`+`model/*`, ставит `stage=trained`, восстанавливает `state.model_page` | `0`, `2` (чужой проект / уже развёрнуто), `4`, `5` |
| `trr artifact plan --target <local\|confluence\|gitlab\|obsidian>` | печатает адрес публикации по `artifacts.<target>.*`; ничего не пишет | `0`, `2` (место не задано), `3`, `4` |
| `trr artifact record --target … --ref … --url … [--file …]` | пишет `state.artifacts[]` (upsert по `(target, ref)`) | `0`, `2` (неизвестная цель / битый state), `4` (нет файла бандла) |
| `trr init --from-artifact <bundle> [--allow-foreign-project]` | импорт в один шаг: unpack + `stage=trained` | `0`, `2`, `3`, `4`, `5` |

### 9.4 Проверки при импорте

1. `artifact_version` известен (сейчас `1`) — иначе `SCHEMA_ERROR` (5), без «попробовать всё равно».
2. Каждый файл из `files[]` есть и его sha256 совпадает; `bytes` — вторая проверка.
3. `model.checksum` сходится с пересчитанным по `model/estimation-model.json`.
4. `origin.project` равен `jira.project`; иначе `[WARN]` и **блок** до `--allow-foreign-project`.
5. `published_page.hash` равен `model.checksum` — только тогда восстанавливается `state.model_page`;
   иначе `model_page` остаётся `null` (и `doctor` скажет «артефакт не опубликован»).

### 9.5 Экспорт: кто публикует

| `artifacts.export_target` | Кто кладёт файл |
|---|---|
| `none` | никто: `artifact pack` только собирает архив локально |
| `local` | `artifact pack` (по `artifacts.local.path`) |
| `confluence` | агент: страница под `parent_page_id` + вложение |
| `gitlab` | агент: файл в `artifacts.gitlab.path` ветки `branch`; **скилл не пишет git** |
| `obsidian` | агент: заметка/вложение по `artifacts.obsidian.path` |

После публикации — `trr artifact record`; без записи `doctor` покажет `[WARN] артефакт не опубликован`.
Публикация бандла **не** двигает `stage`.

### 9.6 Что не попадает в бандл

- `state.json` целиком — только `published_page` как факт;
- `runs/**` — прогоны задач не переносятся;
- `DATA-REQUIREMENTS.md`, `actions/**` — рабочие файлы;
- токены и конфиг проекта — конфиг создаётся `init` на месте;
- `trr.sqlite3` — зеркало восстанавливается на месте через `trr db ingest`.

## 10. SQLite-зеркало (`.task-readiness/trr.sqlite3`)

Все артефакты выше пишутся **и в файлы, и в локальную БД**. Файлы остаются источником истины и
контрактом; БД — второй адрес тех же данных для запросов, истории метрик и векторов. Публикация в
Confluence — отдельная ось: `storage.sqlite.enabled: false` выключает только зеркало.

```bash
trr db init                        # создать/мигрировать (идемпотентно)
trr db check                       # integrity_check, user_version, счётчики, размер
trr db ingest                      # бэкфилл из артефактов на диске (повторно — без дублей,
                                   #  история версий модели копится; см. §10.2)
trr db stats                       # таблица → строк
trr db export --out dump.json      # JSON-дамп всех таблиц
trr db query --sql "SELECT …"      # только SELECT/WITH/PRAGMA (--limit N, --json)
```

Свойства файла: `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `synchronous=NORMAL`,
`PRAGMA user_version=5`. Рядом появляются `trr.sqlite3-wal` и `trr.sqlite3-shm` — это нормально.

### 10.1 Схема (DDL, `user_version = 5`)

Миграции только вперёд: `1` — базовая схема, `2` — таблица `reference_levels` (матрица эталона),
`3` — множитель параметров (`model_buckets.params_multiplier`/`params_profile`, `estimates.params_json`),
`4` — таблица `synth_runs` (результаты синтетического полигона),
`5` — ключ прогона `(task_key, run_id)` в `runs`/`validations`/`estimates`/`estimate_roles` и разделение
`publications.sha256` на `content_sha256` (файл) и `model_checksum` (модель). Миграция 5 пересоздаёт
таблицы (новая → `INSERT … SELECT` → `drop` → `rename`) и идемпотентна: повторный `db init` на схеме 5
ничего не делает.
`trr db init` / `db ingest` доводят файл до текущей версии сами, пересоздавать БД не нужно.

```sql
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);

CREATE TABLE reference_pages (page_id TEXT PRIMARY KEY, title TEXT, space_key TEXT,
    depth INTEGER, version INTEGER, body_sha256 TEXT, body_len INTEGER, retrieved_at TEXT);

CREATE TABLE reference_buckets (id INTEGER PRIMARY KEY AUTOINCREMENT, model_checksum TEXT NOT NULL,
    role TEXT NOT NULL, work_kind TEXT NOT NULL, value REAL, description TEXT, evidence TEXT,
    UNIQUE (model_checksum, role, work_kind));

-- user_version = 2
CREATE TABLE reference_levels (page_id TEXT NOT NULL, sp INTEGER NOT NULL, description TEXT,
    uncertainty TEXT, refactoring TEXT, research TEXT, decomposition TEXT, time_hint TEXT,
    examples TEXT, params_hint TEXT, PRIMARY KEY (page_id, sp));

CREATE TABLE sprint_rows (sprint TEXT NOT NULL, task_key TEXT NOT NULL, issue_type TEXT, role TEXT,
    sp REAL, qa_estimation REAL, has_testing INTEGER, status TEXT, labels TEXT,
    summary_sha256 TEXT, weight REAL, heat REAL, connectivity REAL, sample_checksum TEXT,
    PRIMARY KEY (task_key, sprint));

CREATE TABLE sprint_stats (model_checksum TEXT NOT NULL, role TEXT NOT NULL, issue_type TEXT NOT NULL,
    work_kind TEXT NOT NULL, n INTEGER, mean REAL, median REAL, p25 REAL, p75 REAL, min REAL,
    max REAL, coverage TEXT, PRIMARY KEY (model_checksum, role, issue_type, work_kind));

CREATE TABLE model_versions (version INTEGER PRIMARY KEY, checksum TEXT UNIQUE, generated_at TEXT,
    payload TEXT, created_at TEXT);

CREATE TABLE model_buckets (model_checksum TEXT NOT NULL, role TEXT NOT NULL, issue_type TEXT NOT NULL,
    work_kind TEXT NOT NULL, base REAL, factor REAL, expected REAL, range_low REAL, range_high REAL,
    n INTEGER, confidence TEXT, reference TEXT,
    PRIMARY KEY (model_checksum, role, issue_type, work_kind));

CREATE TABLE gap_rules (model_checksum TEXT NOT NULL, rule_id TEXT NOT NULL, condition TEXT,
    penalty_steps INTEGER, applies_to TEXT, PRIMARY KEY (model_checksum, rule_id));

CREATE TABLE tasks (task_key TEXT PRIMARY KEY, issue_type TEXT, role TEXT, work_kind TEXT, sp REAL,
    qa_estimation REAL, weight REAL, heat REAL, connectivity REAL, params_source TEXT,
    first_seen TEXT, last_seen TEXT);

-- user_version = 5: RUN-ID (метка времени) не уникален между задачами
CREATE TABLE runs (task_key TEXT NOT NULL DEFAULT '', run_id TEXT NOT NULL, stage TEXT, workdir TEXT,
    created_at TEXT, model_checksum TEXT, config_sha256 TEXT, PRIMARY KEY (task_key, run_id));

CREATE TABLE validations (task_key TEXT NOT NULL DEFAULT '', run_id TEXT NOT NULL, verdict TEXT,
    checks_total INTEGER, checks_failed INTEGER, gaps_total INTEGER, payload TEXT, checked_at TEXT,
    PRIMARY KEY (task_key, run_id));

CREATE TABLE estimates (task_key TEXT NOT NULL DEFAULT '', run_id TEXT NOT NULL, model_version INTEGER,
    model_checksum TEXT, total_expected REAL, total_low REAL, total_high REAL,
    params_multiplier REAL, payload TEXT, estimated_at TEXT, params_json TEXT,
    PRIMARY KEY (task_key, run_id));

CREATE TABLE estimate_roles (task_key TEXT NOT NULL DEFAULT '', run_id TEXT NOT NULL, role TEXT NOT NULL,
    expected REAL, range_low REAL, range_high REAL, confidence TEXT, provenance TEXT,
    PRIMARY KEY (task_key, run_id, role));

CREATE TABLE vectors (task_key TEXT NOT NULL, model_version INTEGER NOT NULL, dim INTEGER,
    vector BLOB, terms TEXT, built_at TEXT, PRIMARY KEY (task_key, model_version));

CREATE TABLE vector_meta (model_version INTEGER PRIMARY KEY, built_at TEXT, corpus INTEGER,
    dim INTEGER, config TEXT);

CREATE TABLE similarities (task_key TEXT NOT NULL, other_key TEXT NOT NULL, cosine REAL,
    same_bucket INTEGER, model_version INTEGER NOT NULL,
    PRIMARY KEY (task_key, other_key, model_version));

-- user_version = 5: sha256 файла и checksum модели — разные величины
CREATE TABLE publications (target TEXT NOT NULL, ref TEXT NOT NULL, url TEXT, content_sha256 TEXT,
    model_checksum TEXT, published_at TEXT, PRIMARY KEY (target, ref));

CREATE TABLE metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, scope TEXT, name TEXT,
    value REAL, labels TEXT);

CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, payload TEXT);

-- user_version=4: результаты синтетического полигона
CREATE TABLE synth_runs (run_id TEXT PRIMARY KEY, created_at TEXT, seed INTEGER, count INTEGER,
    model_checksum TEXT, summary TEXT);
CREATE INDEX idx_synth_runs_created ON synth_runs(created_at);

CREATE INDEX idx_sprint_rows_role_type ON sprint_rows(role, issue_type);
CREATE INDEX idx_estimates_task ON estimates(task_key);
CREATE INDEX idx_runs_task ON runs(task_key);
CREATE INDEX idx_metrics_scope_name ON metrics(scope, name);
```

### 10.2 Что в каждой таблице

| Таблица | Откуда | Что внутри |
|---|---|---|
| `meta` | `connect` | `schema_version`, `keep_vectors`, `keep_payloads`, `vacuum_on_pack`, абсолютный `path`. |
| `reference_pages` | `calibrate`, `db ingest` | Страница эталона: `page_id`, `title`, `space_key`, `retrieved_at`. Тело страницы **не** хранится (`body_sha256`/`body_len` = `NULL`). |
| `reference_buckets` | `calibrate`, `db ingest` | Числа эталона: `role`+`work_kind` → `value`, плюс `description`/`evidence`. Ключ — `(model_checksum, role, work_kind)`; зеркало хранит **текущий** эталон (при смене checksum строки прошлой версии удаляются — эталон это вход модели, а не её версия). |
| `reference_levels` | `calibrate`, `db ingest` | Строки эталонной таблицы: `(page_id, sp)` — PK, дословные ячейки (`description`, `uncertainty`, `refactoring`, `research`, `decomposition`, `time_hint`), `examples` (JSON `{BE,FE,QA}`) и `params_hint` (JSON `{weight,heat}`). Набор уровней страницы перезаписывается целиком. |
| `sprint_rows` | `db ingest` | Строки `norm/sprint-sample.json`: `(task_key, sprint)` — PK, `labels` — JSON-массив, `sample_checksum` — sha256 набора строк. `weight/heat/connectivity` — из `trr params`, если переданы. |
| `sprint_stats` | `stats`, `calibrate`, `db ingest` | Бакеты `norm/sprint-stats.json` под `model_checksum`. `db ingest` инкрементален: он **копит** срезы всех версий модели, какие проходили через пайплайн. Полная пересборка БД с нуля даёт срез только **текущей** модели — прошлые `model_checksum` восстановить не из чего (`model-history.jsonl` хранит лишь `version`/`checksum`/`generated_at`, без payload'ов). |
| `model_versions` | `calibrate`, `db ingest` | Версия модели: `version` (PK), `checksum` (UNIQUE), `generated_at`, `payload` (полный JSON, если `keep_payloads`). |
| `model_buckets` | `calibrate`, `db ingest` | Бакеты модели: `base`, `factor`, `expected`, `range_low`/`range_high`, `n`, `confidence`, `reference`. Как и `sprint_stats`, история версий копится инкрементальным ingest; полная пересборка БД даёт бакеты только текущей модели. |
| `gap_rules` | `calibrate`, `db ingest` | Правила штрафов: `rule_id`, `condition` (`SA-08=FAIL`), `penalty_steps`, `applies_to` (JSON). |
| `tasks` | `db ingest` | Сводка по задачам: тип, роль, вид работ, `sp`, `qa_estimation`, параметры, `first_seen`/`last_seen`. |
| `runs` | `check`, `estimate`, `db ingest` | Прогон: `(task_key, run_id)` — PK (`run_id` — метка времени и **не** уникален между задачами), `stage` (`checked`/`estimated`), `workdir`, `model_checksum`, `config_sha256`. `db ingest` берёт `model_checksum` из `estimate.json` самого прогона, поэтому исторический прогон на v1 не получает сумму текущей v2; нет в артефакте — `NULL`. |
| `validations` | `check` | Вердикт и счётчики: `(task_key, run_id)` — PK, `checks_total`, `checks_failed`, `gaps_total`, `payload` (полный `validation.json`). |
| `estimates` | `estimate` | Итог: `(task_key, run_id)` — PK, `model_version`, `model_checksum`, `total_expected`, `total_low`/`total_high`, `params_multiplier`, `payload` (`estimate.json`). |
| `estimate_roles` | `estimate` | Разбивка по ролям: `(task_key, run_id, role)` — PK, `expected`, `range_low`/`range_high`, `confidence`, `provenance` (JSON). |
| `vectors` | `vectors build`, `db ingest` | Вектор задачи: `dim`, `vector` (BLOB `struct.pack('<Nf')`, float32), `terms` (JSON-массив термов в том же порядке). `db ingest` восстанавливает таблицу из готового `norm/task-vectors.json` (термы уже посчитаны — пересчёт не нужен). |
| `vector_meta` | `vectors build` | Одна строка на версию: `corpus`, `dim` (максимальная длина вектора), `config` (`top_terms`, веса, нормализатор). |
| `similarities` | `vectors similar` | Пары: `task_key` → `other_key`, `cosine`, `same_bucket`, `model_version`. Набор перезаписывается на каждый запрос. |
| `publications` | `publish`, `state`, `db ingest` | Зеркало `state.published[]`: `(target, ref)` — PK, `url`, `published_at`; `content_sha256` — sha256 опубликованного файла (как в `state.published[]`), `model_checksum` — контрольная сумма модели, которой отрендерена страница (`state.model_page.hash`, nullable). |
| `metrics` | `stats`, `calibrate`, `vectors`, `check`, `estimate`, `synth-run` | Журнал метрик: `scope` (`stats`/`model`/`check`/`estimate`/`vectors`/`synth`), `name`, `value`, `labels`. Строки копятся. |
| `events` | `state.save` | Журнал событий: `kind` (`state`), `payload` (этап, `model_checksum`, счётчики `runs`/`published`). |
| `synth_runs` | `synth-run --record` | Прогон полигона: `run_id` (PK, `synth-<seed>-<sha256[:12]>`), `seed`, `count`, `model_checksum`, `summary` (полный `summary.json`). Метрики прогона — в `metrics(scope='synth')`. |

Инварианты:

- **идемпотентность** — все `record_*` пишут через `INSERT … ON CONFLICT … DO UPDATE`; повторный
  `trr db ingest` не плодит строк (проверяется `trr selftest`);
- **`db ingest` инкрементален и копит историю версий** — `sprint_stats`/`model_buckets`/`gap_rules`
  остаются под каждым `model_checksum`, который проходил через пайплайн, а `vectors` — под версией
  векторов. **Полная пересборка БД** (`rm .task-readiness/trr.sqlite3 && trr db ingest`) даёт срез
  **текущей** модели и текущих векторов: прошлых payload'ов в `model/model-history.jsonl` нет, и
  срезы не выдумываются. При истории версий > 1 `db ingest` печатает `[WARN]` об этом. Нужна
  полная история — не удаляйте файл БД, а копите её инкрементальным ingest;
- **`keep_vectors: false`** — `vectors` пуста, `vector_meta` пишется (иначе не отличить «модель не
  собрана» от «векторы не хранятся»);
- **`keep_payloads: false`** — `payload`/`terms` = `NULL`, скалярные поля на месте;
- **секретов нет** — токены не пишутся, конфиг целиком не сохраняется;
- **ошибка БД** (нет прав, диск, битый файл) — `[WARN] storage: …` в stderr, код выхода шага не меняется.

### 10.3 Как читать и выгружать

`db query` — **только чтение**: разрешены `SELECT`, `WITH`, `PRAGMA` (без присваивания); всё остальное,
включая `INSERT`/`UPDATE`/`DROP`/`ATTACH`/`PRAGMA writable_schema`, отклоняется с кодом `2`. Соединение
открывается как `file:…?mode=ro`, поэтому запись невозможна даже при ошибке в проверке.

```bash
# числа эталона
trr db query --sql "SELECT role, work_kind, value FROM reference_buckets ORDER BY value"

# сколько задач FE с sp=3 закрыто в спринте
trr db query --sql "SELECT sprint, COUNT(*) FROM sprint_rows
                    WHERE role='FE' AND sp=3 AND status='Готово' GROUP BY sprint"

# последние метрики проверок
trr db query --sql "SELECT ts, name, value FROM metrics WHERE scope='check' ORDER BY id DESC LIMIT 10"

# машинный вывод: колонки + строки + count
trr db query --sql "SELECT * FROM estimates" --json --limit 5
```

`db export` кладёт все таблицы в один JSON:

```json
{
  "exported_at": "2026-11-17T10:00:00Z",
  "user_version": 1,
  "source": "/…/.task-readiness/trr.sqlite3",
  "tables": {
    "reference_buckets": [{"id": 1, "model_checksum": "…", "role": "BE", "work_kind": "bugfix", "value": 2.0, "…": "…"}],
    "vectors": [{"task_key": "E001-1000", "model_version": 1, "dim": 15, "vector": "hex:1f85…", "terms": "[\"c:imp\", …]"}]
  }
}
```

BLOB-поля (`vectors.vector`) выгружаются строкой `hex:…` — дамп остаётся текстовым JSON. Обратно в
`list[float]`: `struct.unpack('<%df' % dim, bytes.fromhex(value[4:]))`; `terms` — JSON-массив термов в том
же порядке.


## 11. Синтетический полигон (`trr synth` / `trr synth-run`)

Полигон — **не** прогон задачи и **не** артефакт проекта: он живёт в отдельном каталоге (`--out`),
ничего не публикует и не пишет в `.task-readiness/runs/`. Три файла описывают полный цикл:
`contexts.jsonl` + `manifest.json` (генератор) → `summary.json` + `records.jsonl` (харнесс).

### 11.1 `contexts.jsonl`

- **Производитель:** `trr synth`.
- **Потребитель:** `trr synth-run`; человек — для точечного разбора (`trr synth-run --limit`).
- **Формат:** JSON Lines, **одна строка = один снимок задачи**. Ключи отсортированы, разделители
  фиксированы, `ensure_ascii=false`; тот же `--seed` даёт побайтно тот же файл.
- **Состав строки:** полный `context.json` (§5.1) — 10 обязательных ключей `check.CONTEXT_KEYS`
  (`task_key`, `issue_type`, `role`, `work_kind`, `sp`, `qa_estimation`, `labels`, `fields{}`,
  `sections{}`, `sources[]`) плюс `summary`, `description`, `components`, `issuelinks`, `links`,
  `sa_checklist` (в полном снимке), `params`/`weight`/`heat`/`connectivity` при override.
- **Служебный блок `_meta`** (не входит в `CONTEXT_KEYS`, движки его игнорируют):

```json
{
  "case_id": "SYN-000123",
  "index": 123,
  "seed": 42,
  "sprint": "T100-T102 26.17",
  "source_key": "E001-31183",
  "expected_sp": 5,
  "edge": null,
  "axes": {
    "issue_type": "Feature", "role": "QA", "work_kind": "testing",
    "sp": 5, "qa_estimation": null, "description_len": 2000,
    "sections": "all", "labels": "none", "issuelinks": 3,
    "components": 5, "override": false
  }
}
```

`expected_sp` — `sp` из строки спринта **до** применения квоты `null`: по нему считается, на сколько
шагов оценка отличается от исторической. `edge` — вид edge-случая (`null` у обычной задачи), с него
начинается разбор падения.

### 11.2 `manifest.json`

- **Производитель:** `trr synth`.
- **Что означает:** паспорт набора — по нему видно, **что реально сгенерировано**, а не что
  задумывалось.
- **Поля:** `generator`, `generator_version`, `seed`, `count`, `include_edge`, `edge_count`,
  `source{sample_path, rows_used, sprints_available, sprints_selected}`,
  `model{version, checksum}`, `coverage{enabled, quota, triples, planned, min_per_triple, counts{}}`
  (покрытие троек модели: сколько снимков реально пришлось на каждую тройку `role/issue_type/work_kind`
  и каков минимум; при `--no-coverage-all-buckets` — `enabled: false`, `triples: 0`),
  `distributions{}` (фактические счётчики по каждой оси: `issue_type`,
  `role`, `work_kind`, `sp`, `qa_estimation`, `description_len`, `sections`, `labels`, `issuelinks`,
  `components`, `override`, `edge`), `files{contexts, manifest}`.
- Времени в манифесте нет: одинаковый вход → одинаковый файл.
- `generator_version = 2` — генератор с покрытием троек; датасеты версии 1 (без покрытия) остаются
  валидными для сравнения «до/после», но `buckets.hit` у них меньше числа бакетов модели.

### 11.3 `summary.json`

- **Производитель:** `trr synth-run`.
- **Что означает:** метрики качества прогона `check + estimate` на синтетическом наборе.
- **Поля:**

| Поле | Смысл |
|---|---|
| `total`, `ok`, `warn`, `blocked`, `errors` | вердикты `validation.verdict`; `errors` — исключения движков, до 3 примеров с `traceback` в `error_examples[]` |
| `unestimable`, `unexpected_errors` | `unestimable` — подмножество `errors`: `estimate` отказался, потому что у роли нет ни одного бакета в модели. С версии 4 таких отказов быть не должно: роль без бакетов деградирует до `OTHER` (`confidence=low`). Ненулевое значение — дефект деградации. `unexpected_errors` — остальные исключения; только они валят код выхода |
| `schema_failures{cases, examples[]}` | артефакты, не прошедшие `schema_lite.validate` (validation или estimate) |
| `scale_violations{cases, examples[]}` | `roles[].expected ∉ [1,2,3,5,8,13,21]` — контракт шкалы у **каждой роли** |
| `range_violations{cases, examples[]}` | нарушено `range_low <= expected <= range_high` (по роли и по `total`) |
| `total_off_scale{cases, examples[]}` | справочно: `total.expected` — сумма ролей и законно может не лежать на шкале |
| `param_violations{cases, examples[]}` | `weight`/`heat`/`connectivity` вне `[0,1]`, `NaN` или не число |
| `monotonicity{param_groups, probes, violations, worst}` | `expected` не убывает при росте одного параметра (остальные зафиксированы `0.0` и `0.5`); `worst` — худшая пара «уровень → уровень» |
| `determinism{cases, equal, first_diff}` | первые 100 задач прогнаны дважды; сравнение без `duration_ms`/`traceback` |
| `buckets{total, hit, missed[], reachable, unreachable[], note, probe{probes, hit, missed[], errors[]}}` | покрытие 20 бакетов модели. `reachable` — селектор возвращает бакет на его собственной тройке `(role, issue_type, work_kind)`; `unreachable` — бакеты, до которых `estimate` не дотягивается (дефект `select_bucket`). `hit` — что реально встретилось в датасете (может быть меньше `reachable`, если генератор не производит такую комбинацию осей). `probe` — end-to-end проба: на каждый бакет строится снимок и `estimate` обязан вернуть тот же бакет; `probe.hit == probe.probes` = все бакеты достижимы |
| `seed` | `seed` из `manifest.json` датасета (попадает в `synth_runs.seed`); `null` — манифеста нет |
| `distribution{histogram, histogram_roles, mean, median, multi_role_cases, compared_with_sample, differs_from_sample, differs_share, step_histogram}` | распределение `expected`, среднее/медиана, доля и величина расхождения с `_expected_sp` в шагах шкалы; `multi_role_cases` на полигоне `0` (одна роль на снимок, включая `role_assumed`) |
| `timing{total_s, per_task_ms{p50,p95,mean}}` | общее время и время на задачу |
| `harness{in_process, workers, writes_runs, out, limit}`, `model{version, checksum}`, `cases_read` | параметры прогона и модель |

- **Код выхода** `2` — если нарушен хотя бы один инвариант (`unexpected_errors`, schema, scale,
  range, params, monotonicity); `0` — чисто. `unestimable`, покрытие бакетов и распределение —
  информационные, на код не влияют.

### 11.4 `records.jsonl`

- **Производитель:** `trr synth-run`.
- **Формат:** одна строка на задачу, отсортировано по `case_id` (детерминизм при `--workers > 1`).
- **Поля:** `case_id`, `verdict`, `checks_total`, `checks_failed` (`FAIL|UNKNOWN`), `gaps_total`,
  `expected`, `range`, `roles[]` (по роли: `role`, `expected`, `range`), `params{weight, heat,
  connectivity, source, multiplier}`, `bucket{role, issue_type, work_kind, reference}`, `buckets_all[]`,
  `expected_sp`, `edge`, `duration_ms`, `error`, `unestimable`, `schema_errors[]`, `traceback`
  (только у ошибок).

### 11.5 Чего полигон не делает

- Не создаёт задач Jira и страниц Confluence, ничего не публикует.
- Не пишет в `.task-readiness/runs/` и не меняет `state.json`.
- Не меняет модель, эталон, статистику и формулу — только читает.

# Конфиг `task-readiness-review.yaml`

Справочник по единственному файлу настроек, который скилл читает из корня проекта. Нормативный источник —
`CONTRACT.md` §5.1; схема — `<skill>/schemas/config.schema.json` (schema version 1.6); пример —
`<skill>/task-readiness-review.example.yaml`.

## 0. Общие правила

- **Файл создаёт `init`** — копией примера из скилла. Правки делаются в файле проекта, а не в примере
  скилла: `init --force` перезапишет проект целиком.
- **Файл не версионируется в проекте.** Это настройка конкретного проекта и машины (см. `artifacts.md` §8).
- **Секретов в файле нет и быть не может.** Токены — только из переменных окружения (§6).
- **Расширяемость не предусмотрена:** `additionalProperties: false` на всех уровнях. Незнакомый ключ —
  `CONFIG_ERROR` (3) с путём до поля, например `config.validation.min_sample_n`.
- **Дефолты подставляются до валидации** (`config.apply_defaults`), поэтому ключ с дефолтом можно не
  писать. Обязательные по схеме ключи перечислены ниже.
- **Проверка:** `trr config-check` (или `/task-readiness-review doctor`). Успех — `[OK] config valid,
  sha256=…`, ошибка — код 3 и строка `[MISSING] config.<путь> — <причина>`.
- **`config_sha256`** в `state.json` считается от нормализованного конфига (после подстановки дефолтов),
  а не от текста файла: перестановка ключей или комментарии хеш не меняют.

## 1. Все ключи

Тип указан так, как его понимает схема: `string`, `integer`, `number`, `boolean`, `object`, `array`,
`null`; `string | array` — равноправные альтернативы. «Обязателен» — требуется схемой после подстановки
дефолтов (то есть при наличии дефолта ключ можно не писать, но пустого значения без дефолта быть не
может).

| Ключ | Тип | Обязателен | Дефолт | Что означает | Пример |
|---|---|---|---|---|---|
| `skill` | string, const | да | `task-readiness-review` | Маркер файла. Любое другое значение — ошибка конфига: файл не от этого скилла. | `skill: task-readiness-review` |
| `sources` | object | да | `{reference: [], sprints: []}` | Источники данных для обучения модели. Внутри обязательны `reference` и `sprints`. | см. §2–§3 |
| `sources.reference` | string \| array | да | `[]` | Эталоны оценки в Story Points. Либо свободный текст, либо массив: строка или объект с одним из ключей `page_id` / `page_url` / `text`. | см. §2 |
| `sources.reference[].system` | enum `source_system` | нет | выводится | Где лежит эталон: `confluence`, `jira`, `obsidian`, `file`. Для `page_url` — всегда `confluence`; для `page_id` без `system` числовой id считается Confluence, строка — `file`. | `confluence` |
| `sources.reference[].page_id` | string \| integer | один из трёх | — | Прямой id страницы/заметки/файла. Для Confluence — числовой id. Не выдумывается: если его нет в URL, поле остаётся `null`. | `"4278391451"` |
| `sources.reference[].page_url` | string | один из трёх | — | URL Confluence. Три формы: `?pageId=N` и `/spaces/SPACE/pages/N/Title` дают `page_id` без сети; `/display/SPACE/Title` даёт только `space`+`title` и требует поиска агентом. | `"https://…/display/ECOMCS/T100+Story+Points"` |
| `sources.reference[].text` | string | один из трёх | — | Свободный текст: URL-ы, упоминания систем, название страницы. URL-ы и упоминания извлекает Python, остальное резолвит агент. | `"эталон в конфлюенсе, страница T100 Story Points"` |
| `sources.reference[].title` | string \| null | нет | `null` | Ожидаемый заголовок источника; помогает агенту не спутать страницы. | `"T100 Story Points"` |
| `sources.sprints` | string \| array | да | `[]` | Спринты для статистики. Либо строка с названиями/ID через запятую, либо массив: строка или объект с одним из вариантов `board_id`+`sprint_ids` / `board_labels` / `text`. | см. §3 |
| `sources.sprints[].board_id` | integer ≥ 1 | для `sprint_ids` | — | Идентификатор борда Jira. | `6662` |
| `sources.sprints[].sprint_ids` | array (integer ≥ 1) \| string | вариант 1 | — | Закрытые спринты борда: массив целых ≥ 1 либо строка с ID через запятую. По незакрытым статистика недостоверна. | `[20367, 20693]` |
| `sources.sprints[].board_labels` | string \| array | вариант 2 | — | Названия спринтов **как в UI Jira**, строка через запятую или массив строк. Резолвятся в id командой `trr match-sprints`. | `"T100-T102 26.18, T100-T102 26.19"` |
| `sources.sprints[].text` | string | вариант 3 | — | Свободный текст: названия и/или ID спринтов, которые резолвит ИИ. | `"26.20, 26.21"` |
| `sources.confluence` | object | да | `{recursive: false, max_depth: 1, max_pages: 20}` | Обход дерева страниц Confluence вокруг эталона. | |
| `sources.confluence.recursive` | boolean | да | `false` | Обходить ли дочерние страницы эталона (`--pages-json` + `trr resolve-sources --recursive`). | `true` |
| `sources.confluence.max_depth` | integer ≥ 1 | да | `1` | Глубина: `1` — только эталон, `2` — плюс прямые дочерние страницы. | `2` |
| `sources.confluence.max_pages` | integer ≥ 1 | да | `20` | Максимум страниц из дерева; превышение — `[WARN]` и обрезка. | `20` |
| `templates_dir` | string | да | `templates` | Каталог шаблонов **относительно корня скилла**. Менять не нужно. | `templates` |
| `override_template` | string \| null | нет | `null` | Свой шаблон описания задачи вместо встроенного `templates/task-description.md`. `null` — встроенный. См. §4. | `templates/my-task-description.md` |
| `validation` | object | да | `{with_dependencies: false, min_sample_n: 5, role_map: {}}` | Правила проверки готовности. Внутри обязательны `with_dependencies`, `min_sample_n` и `role_map`; `qa_required_issue_types` и `template_url` необязательны (есть дефолты). | |
| `validation.with_dependencies` | boolean | да | `false` | Проверять ли связанные задачи (зависимости). Дороже по времени: на каждую зависимость — чтение Jira. | `false` |
| `validation.min_sample_n` | integer ≥ 1 | да | `5` | Минимальный размер бакета, при котором статистика считается достаточной. Меньше порога — `coverage=insufficient` и `confidence=low`. | `5` |
| `validation.qa_required_issue_types` | array string | нет | `["Feature", "New Feature", "Фича", "Ошибка", "Bug", "Дефект"]` | Типы задач, для которых требуется оценка QA. Типы вне списка (Задача, Tech Debt, ADR, Релиз, Дизайн) QA-оценки не требуют: исполнитель выполняет полный объём, включая проверку результата, поэтому QA-записи в оценке нет. Сравнение — strip + casefold. Пустой список — «QA не нужен нигде». | `["Feature", "Ошибка"]` |
| `validation.role_map` | object | да | `{}` | Отображение значения роли из Jira в enum `role`. Ключ — что приходит из Jira, значение — `BA/SA/BE/FE/QA/DEVOPS/OTHER`. Неизвестное значение не ошибка: роль становится `OTHER`. | `BE: BE` |
| `validation.template_url` | string | нет | `https://space.samokat.ru/pages/viewpage.action?pageId=3882222857` | Ссылка на целевой шаблон описания задачи в компактных блоках отчёта («Что заполнить» / «Что стоит уточнить»). Пустая строка — печатать путь к `templates/task-description.md` вместо ссылки. | `""` |
| `estimation` | object | да | `{scale: [1, 2, 3, 5, 8, 13, 21], factor_clamp: [0.5, 2.0]}` | Правила расчёта оценки. | |
| `estimation.scale` | array integer, ровно 7 | да | `[1, 2, 3, 5, 8, 13, 21]` | **Нормативная** шкала Story Points. Обязана совпадать с эталонной; расхождение — ошибка конфига. См. §7. | `[1, 2, 3, 5, 8, 13, 21]` |
| `estimation.factor_clamp` | array number, ровно 2 | да | `[0.5, 2.0]` | Границы коэффициента калибровки `[min, max]`, требуется `0 < min < max`. | `[0.5, 2.0]` |
| `estimation.params` | object | нет | `{enabled: true, clamp: [0.5, 2.0], coefficients: {…}, defaults: {…}, signals: {}}` | Три эвристических параметра задачи (`weight`/`heat`/`connectivity`). Блок **необязателен**; задаёт множитель формулы оценки (третий сомножитель `base × factor × params_multiplier`). См. §7.2. | |
| `estimation.params.enabled` | boolean | нет | `true` | Выводить ли параметры эвристикой. `false` — все три равны `defaults`, `source=disabled`. | `false` |
| `estimation.params.clamp` | array number, ровно 2 | нет | `[0.5, 2.0]` | Границы множителя `[min, max]`: `0 < min <= 1.0 <= max <= 4.0`. | `[0.6, 1.8]` |
| `estimation.params.coefficients` | object | нет | `{weight: 0.5, heat: 0.4, connectivity: 0.3}` | Коэффициенты множителя при отклонении параметра от `defaults`, каждое `0…2`. | `{weight: 0.7}` |
| `estimation.params.defaults` | object | нет | `{weight: 0.5, heat: 0.5, connectivity: 0.5}` | Значения по умолчанию (`0…1`): сигналов нет или `enabled: false`. | `{weight: 0.4}` |
| `estimation.params.signals` | object | нет | `{}` | Переопределение весов сигналов: «имя сигнала → вес `0…1`». Пустой объект — веса по умолчанию; неизвестные имена игнорируются. См. `estimation-model.md` §13. | `{description_len: 0.3}` |
| `estimation.vector` | object | да | `{enabled: true, adjust_range: false, top_k: 5, min_corpus: 30, top_terms: 15, weight_word: 0.5}` | Векторизация текстов задач (этап A). По умолчанию **включена**: векторы строятся на `train`, похожие задачи — справка. См. §7.1. | |
| `estimation.vector.enabled` | boolean | да | `true` | Включать ли поиск похожих задач: `estimate` читает `norm/task-vectors.json` и пишет `similar_tasks[]`, отчёт получает секцию 9. `false` — векторы не читаются вовсе. | `false` |
| `estimation.vector.adjust_range` | boolean | да | `false` | Этап B: разрешить векторам влиять на числа. `true` — `range` расширяется до SP соседей того же бакета выше `similar_threshold`, `confidence` → `low`, причина в `variability_reason`. `base`/`expected` не меняются никогда. Включать только после `trr vectors similar` и калибровки. | `false` |
| `estimation.vector.top_k` | integer ≥ 1 | да | `5` | Сколько похожих задач возвращать (`similar_tasks[]`, `trr vectors similar --top`). | `5` |
| `estimation.vector.min_corpus` | integer ≥ 30 | да | `30` | Минимальный корпус задач: меньше — `vectors build` даёт `[BLOCKED]` (2), а `estimate` — `[WARN]` и считает без соседей. **Пол — 30:** значение меньше 30 — ошибка конфига (`config.estimation.vector.min_corpus: N < 30`). | `50` |
| `estimation.vector.top_terms` | integer ≥ 1 | да | `15` | Сколько термов хранить на вектор (`trr vectors build --top-terms`). Меньше — компактнее артефакт, грубее близость. | `15` |
| `estimation.vector.weight_word` | number 0…1 | да | `0.5` | Вес словесной части гибрида; вес символьной части = `1 - weight_word` (`trr vectors build --weight-word`). | `0.5` |
| `estimation.resources` | object | нет | `{enabled: true, sp_per_resource: 1, mode: add, items: {allure: […], e2e: […]}}` | Дополнительные ресурсы задачи (правило `RS-01`): allure для тест-кейсов, e2e-сервис автотестирования для автотестов. За каждый распознанный ресурс `+sp_per_resource` SP к оценке основного исполнителя либо верхняя граница диапазона. Блок **необязателен**. См. `estimation-model.md` §9.6. | |
| `estimation.resources.enabled` | boolean | нет | `true` | Распознавать ли ресурсы. `false` — надбавка не применяется, ключ `resources` в `estimate.json` не появляется. | `false` |
| `estimation.resources.sp_per_resource` | number ≥ 0 | нет | `1` | Надбавка за один ресурс в SP. `0` — ресурсы распознаются, но оценку не меняют. | `2` |
| `estimation.resources.mode` | enum `add` \| `upper_bound` | нет | `add` | `add` — прибавить SP за каждый ресурс; `upper_bound` — взять верхнюю границу уже посчитанного диапазона. | `upper_bound` |
| `estimation.resources.items` | object «имя → array string» | нет | `{allure: ["allure", "тест-кейс", …], e2e: ["e2e", "автотест", …]}` | Каталог ресурсов: имя → алиасы (подстроки, сравнение через casefold). Своё имя добавляет ресурс, пустой список выключает существующий (`allure: []`). | `{grafana: ["grafana"]}` |
| `jira` | object | да | `{project: "", fields: {…}, field_names: {…}, resolve_fields_by_name: true, comment_mode: post}` | Поля и режим Jira. | |
| `jira.project` | string | да | `""` | Ключ проекта Jira. **Обязателен:** командного значения по умолчанию нет; пустая строка блокирует `doctor`/`train`. | `ABC` |
| `jira.fields` | object | да | все три пустые | Идентификаторы полей Jira. Пустая строка — «резолвить по имени» из `jira.field_names`. | |
| `jira.fields.story_points` | string | да | `""` | Идентификатор поля Story Points (`customfield_<число>` или системное имя). | `customfield_10004` |
| `jira.fields.qa_estimation` | string | да | `""` | Идентификатор поля QA Estimation. | `customfield_13819` |
| `jira.fields.role` | string | да | `""` | Идентификатор поля Роль. | `customfield_12750` |
| `jira.field_names` | object | да | `{story_points: "Story Points", qa_estimation: "QA Estimation", role: "Роль"}` | Имена полей **как в UI Jira** — для резолва id по имени. См. §9. | |
| `jira.field_names.story_points` | string | да | `Story Points` | Имя поля Story Points в UI. | `Story Points` |
| `jira.field_names.qa_estimation` | string | да | `QA Estimation` | Имя поля QA Estimation в UI. | `QA Estimation` |
| `jira.field_names.role` | string | да | `Роль` | Имя поля Роль в UI. | `Роль` |
| `jira.resolve_fields_by_name` | boolean | да | `true` | Разрешать пустые `fields.*` по именам из `field_names` (`trr match-fields`). `false` — все три id обязаны быть заполнены. | `true` |
| `jira.comment_mode` | enum `comment_mode` | да | `post` | `post` — **дефолт**: `publish` публикует два комментария в анализируемую задачу («Результаты валидации» и «Результаты оценки»), `check` — третий, с вопросами; повторный запуск обновляет тот же комментарий своего вида (по `comment_id`/маркеру), а не создаёт второй. `draft` — только печать и файл, в Jira ничего не уходит. Отключить запись: `draft`, флаг `--no-jira` или `--draft`. См. §5.1. | `post` |
| `output` | object | да | `{target: none, confluence: {space: "", page_id: null}, obsidian: {path: ""}}` | **Дополнительная** публикация отчёта страницей/заметкой (после комментария в Jira). | |
| `output.target` | enum `output_target` | да | `none` | `none` — дополнительной публикации нет (комментарий в задачу всё равно публикуется при `comment_mode: post`); `confluence`/`obsidian` — **дополнительно** страница/заметка. См. §5. | `none` |
| `output.confluence` | object | да | `{space: "", page_id: null}` | Параметры публикации в Confluence: `space` обязателен, `page_id` опционален. | |
| `output.confluence.space` | string | да | `""` | Ключ пространства Confluence; пустая строка — не задано. | `ECOMCS` |
| `output.confluence.page_id` | string \| null | нет | `null` | Страница, куда писать отчёт. `null` — создать новую. | `"4279119874"` |
| `output.obsidian` | object | да | `{path: ""}` | Параметры публикации в Obsidian; обязателен `path`. | |
| `output.obsidian.path` | string | да | `""` | Путь заметки в хранилище Obsidian; пустая строка — не задано. | `projects/abc/report.md` |
| `storage` | object | нет | `{sqlite: {…}}` | Локальное SQLite-зеркало артефактов, метрик и векторов. Блок **необязателен**; отсутствие = дефолты (включено). См. §10. | |
| `storage.sqlite` | object | нет | `{enabled: true, path: .task-readiness/trr.sqlite3, keep_vectors: true, keep_payloads: true, vacuum_on_pack: false}` | Настройки зеркала. Внутри все ключи необязательны. | |
| `storage.sqlite.enabled` | boolean | нет | `true` | Вести ли зеркало. `false` — ни один шаг не пишет в БД, файл не создаётся, `trr db …` → `[BLOCKED]` (2). | `false` |
| `storage.sqlite.path` | string | нет | `.task-readiness/trr.sqlite3` | Файл БД. Относительный путь — от корня проекта; `../…` (выход за проект) — ошибка конфига. Абсолютный путь разрешён, но `config-check` печатает `[WARN]`. Расширение `.sqlite3`/`.db` рекомендуется (иначе `[WARN]`). | `.task-readiness/trr.sqlite3` |
| `storage.sqlite.keep_vectors` | boolean | нет | `true` | Хранить ли векторы задач (`BLOB` float32). `false` — таблица `vectors` пуста, `vector_meta` пишется. | `false` |
| `storage.sqlite.keep_payloads` | boolean | нет | `true` | Хранить ли полные JSON-снимки (`payload` модели/валидации/оценки, `terms` векторов). `false` — только скалярные поля, `payload`/`terms` = `NULL`. | `false` |
| `storage.sqlite.vacuum_on_pack` | boolean | нет | `false` | Выполнять `VACUUM` при `trr db export` (сжимает файл после массовых удалений). | `true` |
| `artifacts` | object | да | `{include_sprint_sample: true, export_target: none, local: {path: null}, confluence: {…}, gitlab: {…}, obsidian: {path: null}}` | Перенос обученной модели: что класть в бандл и куда его публиковать. См. §10. | |
| `artifacts.include_sprint_sample` | boolean | да | `true` | Класть ли в бандл `norm/sprint-sample.json` (сырую выборку спринтов). `true` — бандл самодостаточен для повторного `stats`/`calibrate`; `false` — только производные артефакты (меньше размер и меньше данных о задачах). | `true` |
| `artifacts.export_target` | enum `export_target` | да | `none` | `none` — не публиковать (только `trr artifact pack` вручную); `local`/`confluence`/`gitlab`/`obsidian` — куда публиковать. Если не `none`, место публикации обязано быть заполнено (`config-check` → `[MISSING]`, `doctor` → `[WARN]`). | `none` |
| `artifacts.local` | object | да | `{path: null}` | Локальная/public-папка, куда складывается бандл (`export_target: local`). | |
| `artifacts.local.path` | string \| null | да | `null` | Путь к файлу бандла или каталогу; `null`/`""` — не задано. | `artifacts/` |
| `artifacts.confluence` | object | да | `{space: null, parent_page_id: null, title_template: "Task Readiness model {{model_version}} — {{project}}"}` | Страница Confluence для бандла (`export_target: confluence`). | |
| `artifacts.confluence.space` | string \| null | да | `null` | Ключ пространства Confluence; `null`/`""` — не задано. | `ECOMCS` |
| `artifacts.confluence.parent_page_id` | string \| integer \| null | да | `null` | id родительской страницы, под которой создаётся страница бандла; `null` — не задано (при `export_target: confluence` обязательно). | `"4279119874"` |
| `artifacts.confluence.title_template` | string | да | `Task Readiness model {{model_version}} — {{project}}` | Шаблон заголовка страницы бандла. Подстановки — **двойные** фигурные скобки: `{{model_version}}`, `{{project}}`. | `TRR model {{project}} v{{model_version}}` |
| `artifacts.gitlab` | object | да | `{project: null, path: "task-readiness/", branch: "main"}` | Файл бандла в репозитории GitLab (`export_target: gitlab`). Коммит делает **агент** через MCP: скилл никогда не пишет git. | |
| `artifacts.gitlab.project` | string \| null | да | `null` | id или путь проекта GitLab (`group/project`); `null` — не задано. | `ecom/dev/models` |
| `artifacts.gitlab.path` | string | да | `task-readiness/` | **Каталог** в репозитории, куда кладётся бандл (со слэшем на конце). | `trr/` |
| `artifacts.gitlab.branch` | string | да | `main` | Ветка, в которую публикуется бандл. | `main` |
| `artifacts.obsidian` | object | да | `{path: null}` | Заметка/вложение в хранилище Obsidian (`export_target: obsidian`). | |
| `artifacts.obsidian.path` | string \| null | да | `null` | Путь в хранилище; `null`/`""` — не задано. | `models/abc-trr.md` |

## 2. Свободный текст в источниках

`sources.reference` и `sources.sprints` принимают **либо строку со свободным текстом, либо структуру**
(`string | array`, schema version 1.1+). Свободный текст — равноправная альтернатива, а не «упрощённый
режим»: результат тот же, просто резолв делает ИИ.

### 2.0 Три формы ссылки на эталон

| Форма | Что даёт скрипт без сети | Что делает агент |
|---|---|---|
| `page_id: "4278391451"` | `page_id` как есть | читает страницу по id |
| `page_url: "…?pageId=4278391451"` | `page_id` из query | читает страницу по id |
| `page_url: "…/spaces/ECOMCS/pages/4278391451/T100+Story+Points"` | `page_id` + `space` + `title` | читает страницу по id |
| `page_url: "…/display/ECOMCS/T100+Story+Points"` | только `space` + `title`, `page_id = null` | ищет страницу поиском по space/title; без результата — `[BLOCKED]` |
| `text: "эталон в конфлюенсе, страница …"` | URL-ы и упоминания систем | ищет и подтверждает каждый источник |

Разбор URL — `sources.parse_confluence_url` (детерминированно, без сети). Форма `/display/SPACE/Title`
**не даёт page_id** — это не ошибка конфига, а честный кандидат: `resolve-sources` печатает `[BLOCKED]`
с подсказкой «передайте page_id или найдите страницу поиском», код `2`.

### 2.1 Как писать

Свободный текст можно записать **тремя равноправными способами**: блоком `|` (переносы сохраняются
дословно), одной строкой в кавычках или без, либо многострочным plain-скаляром — продолжением строки
ключа с отступом (строки склеиваются через пробел, пустая строка внутри даёт `\n`).

```yaml
sources:
  reference: |
    эталон оценки указан на страницах в конфлюенсе
    https://space.samokat.ru/display/ECOMCS/T100+Story+Points
    и в obsidian на странице SP-эталон
  sprints: "T100-T102 26.18, T100-T102 26.19"
```

То же самое одной строкой:

```yaml
sources:
  reference: "эталон оценки указан на страницах в конфлюенсе https://space.samokat.ru/display/ECOMCS/T100+Story+Points и в obsidian на странице SP-эталон"
```

И то же самое многострочным plain-скаляром (длинную строку удобно переносить):

```yaml
sources:
  reference: эталон оценки указан на страницах в конфлюенсе
    https://space.samokat.ru/display/ECOMCS/T100+Story+Points
    и в obsidian на странице SP-эталон
```

Правила склейки (`yamlmini`, как YAML folding):

- продолжением считаются строки с отступом **больше**, чем у ключа;
- соседние строки соединяются одним пробелом, пробелы по краям срезаются;
- пустая строка внутри продолжения даёт перевод строки `\n` (две пустые — два `\n`);
- строка, похожая на `ключ: значение`, элементом списка (`- `) или комментарием (`# …`), продолжением
  **не** считается — это ошибка отступа. Если в тексте нужна такая строка, пишите блок `|`;
- значение, начатое с кавычки или `[`/`{`, многострочным быть не может — тоже ошибка отступа.

Допустимо всё, что человек сказал бы коллеге: URL Confluence, путь заметки Obsidian, название страницы,
имена и ID спринтов. Формат строки не ограничивается — единственное требование схемы: строка непустая
(`pattern: "\\S"`).

### 2.2 Кто и когда резолвит источники

Разделение работы — жёсткое:

- `trr init` пишет **ручную заготовку** `resolved-sources.json` (`resolution_method = manual`,
  `confidence = low`, `evidence` = исходная строка конфига) и печатает следующий шаг. Это не резолв:
  заготовка нужна, чтобы гейт данных видел, что источники заявлены.
- `trr resolve-sources` пересобирает файл из конфига (эвристика: URL-ы, имена систем, спринты через
  запятую) и — с `--agent <PATH>` — вливает источники, которые разрешил агент. Источник агента главнее:
  у него настоящее `evidence` и `confidence` выше `low`.
- ИИ (агент скилла) делает собственно резолв: извлекает URL-ы (`https?://…`) и упоминания систем
  (`confluence|конфлюенс`, `obsidian|обсидиан`), ищет каждый источник через MCP (поиск по заголовку,
  чтение по id), сверяет заголовок и содержимое и складывает результат в файл для `--agent` **с
  `evidence`** — короткой цитатой или фактом, доказывающим, что источник тот самый, — и с `confidence`.

Python (`sources.normalize_reference`, `sources.merge_resolved`) при этом:

- **не выдумывает `page_id`**: если его нет в URL, `page_id = null`, а `ref` равен самому URL;
- для упоминания без ссылки («эталон в конфлюенсе») делает кандидата с `page_id = null` и
  `confidence = low` — такой источник виден в файле, но гейт данных по нему не пройдёт;
- дополняет кандидатов из конфига источниками, которые агент уже разрешил (источник агента главнее:
  у него настоящее `evidence`), сортирует список по `(kind, system, ref)` и валидирует схемой.

### 2.2.1 Что резолвит скрипт, а что агент

| Данные | Скрипт (`trr …`) | Агент (MCP → REST) |
|---|---|---|
| `page_url` с `?pageId=` или `/spaces/…/pages/N/…` | `page_id` (+ `space`, `title`) без сети | читает страницу по id |
| `page_url` вида `/display/SPACE/Title` | `space` + `title`, `page_id=null`, `[BLOCKED]` с подсказкой | ищет страницу по space/title, подтверждает `page_id` |
| свободный `text` | извлекает URL-ы и упоминания `confluence`/`obsidian`, делает кандидатов `confidence=low` | находит и подтверждает каждый источник, пишет `evidence` |
| `board_id` + `sprint_ids` | переносит id как есть | сверяет с `state=closed` списком борда |
| `board_labels` | `trr match-sprints`: точное → нормализованное → префиксное совпадение; ambiguous/missing → `[BLOCKED]` со списком | берёт индекс спринтов Jira и передаёт его в `--sprints-file` |
| `sprint` через свободный `text` | делит по запятым, `id=null` | ищет id по имени |
| `jira.field_names` | `trr match-fields`: нормализованное имя → `customfield_*`; ambiguous/missing → `[BLOCKED]` | берёт `/rest/api/2/field` и передаёт в `--fields-file` |
| дерево дочерних страниц Confluence | `trr resolve-sources --recursive --pages-json`: фильтр по `depth`/`max_pages`, `parent_ref`, `source_kind=agent` | обходит `child/page` и складывает страницы в JSON |
| демо-значения примера (`E001`, `6662`, `4278391451`) | `[WARN] … похоже на демо-значение, замените` в `doctor`/`resolve-sources`; `config-check` **не** предупреждает | заменяет на данные своего проекта |

Правило: **скрипт не ходит в сеть и не угадывает.** Всё, что требует чтения Jira/Confluence, делает агент;
всё, что можно решить по строке конфига (URL, запятые, нормализация имён), решает Python — чтобы результат
был детерминированным и проверяемым.

### 2.3 Что фиксируется в `resolved-sources.json`

Итог резолва, а не текст конфига: у каждого источника `kind`, `system`, `ref`, `title`, `url`,
`resolution_method`, `evidence`, `confidence` (см. `artifacts.md` §2.3). Текст свободной формы остаётся
только в конфиге; в артефакте — уже разрешённые страницы и спринты.

### 2.4 Почему повторный запуск без `--re-resolve` не меняет результат

Резолв — это внешнее чтение с `evidence`; повторять его на каждом запуске значило бы получать разные
`resolved_at`, разный `confidence` и «плавающие» артефакты. Поэтому `resolve-sources` бережёт уже
сделанную работу:

- файла нет → собирает из конфига;
- в файле **только ручная заготовка** (`resolution_method = manual` у всех) → пересобирает без флага:
  терять нечего;
- в файле есть **источники агента** (любой другой `resolution_method`) → отказывается работать с кодом 2
  (`[BLOCKED] … уже содержит источники агента — используйте --re-resolve`), потому что молчаливая
  подмена выкинула бы `evidence`.

Обновить осознанно — `trr resolve-sources --re-resolve`. `trr init --force` пересоздаёт конфиг и
состояние целиком; источники он не перерезолвит.

## 3. Спринты через запятую

Свободная форма — строка, разделитель — запятая:

```yaml
sources:
  sprints: "T100-T102 26.18, T100-T102 26.19"
```

Правила нормализации (`sources.normalize_sprints`):

- пробелы вокруг элементов обрезаются;
- пустые элементы (двойные запятые, запятая в конце) отбрасываются;
- дубликаты схлопываются **с сохранением порядка первого появления**;
- для свободного текста `id = null`: числовой ID в строке — подсказка агенту, а не факт. ID резолвит
  `trr resolve-sources` (эвристика) либо агент через MCP, и фиксируется в `resolved-sources.json`
  (`ref` = id спринта, `title` = имя).

**Допустимость ID.** В строке можно писать и имена, и числовые ID, и то и другое:

```yaml
sources:
  sprints: "T100-T102 26.18, 20367"
```

Структурная форма задаёт ID явно и потому предпочтительна, когда ID известны:

```yaml
sources:
  sprints:
    - board_id: 6662
      sprint_ids: [20367, 20693, 20694, 21143, 21144]
```

Ограничения: берутся только **закрытые** спринты (по незакрытым статистика недостоверна); массив строк
тоже допустим (`["T100-T102 26.18", "20367"]`); `sprint_ids` — непустой массив целых ≥ 1.

### 3.1 Спринты по названиям (`board_labels`)

Если ID спринтов неизвестны, а известны названия **как в UI Jira**, используйте третий вариант:

```yaml
sources:
  sprints:
    - board_id: 6662
      board_labels: "T100-T102 26.18, T100-T102 26.19"
```

или массивом строк:

```yaml
sources:
  sprints:
    - board_id: 6662
      board_labels: ["T100-T102 26.18", "T100-T102 26.19"]
```

`board_labels` — строка через запятую либо массив строк; `board_id` при этом обязателен, потому что одно
и то же название может встречаться на разных бордах. Резолв выполняет `trr match-sprints` (§8):

| Шаг | Правило | Результат |
|---|---|---|
| 1 | точное совпадение названия | `matched` |
| 2 | нормализованное: casefold, `ё → е`, схлопнутые пробелы | `matched` (в отчёте видно, что совпало нормализованно) |
| 3 | префиксное: индекс начинается с названия | `matched`, если кандидат **один** |
| 4 | кандидатов несколько | `[BLOCKED]` со списком кандидатов, код `2` |
| 5 | кандидатов нет | `[BLOCKED] … не найден на борде`, код `2` |

Скрипт не ходит в Jira: индекс спринтов борда готовит агент и передаёт файлом
(`trr match-sprints --labels "…" --sprints-file jira-sprints.json`). Индекс — ответ
`/rest/agile/1.0/board/<id>/sprint` (`{"values": [...]}`) либо массив `{id, name, state}`. Фильтр по
`state: closed` делает **агент** при сборке индекса — `match-sprints` состояние не отбрасывает.

## 4. Переопределение шаблона задачи

Ключ — **`override_template`** (верхний уровень, рядом с `templates_dir`). Это канонический путь:

```yaml
templates_dir: templates
override_template: templates/my-task-description.md   # или null
```

- `null` — используется встроенный `<skill>/templates/task-description.md` (11 обязательных полей со
  страницы 3882222857).
- Строка — путь к своему шаблону описания задачи. Путь трактуется так же, как `templates_dir`: от корня
  скилла; для шаблона конкретного проекта удобнее положить файл в проект и указать относительный путь от
  корня проекта — `check` сообщит, если файл не найден.
- Шаблон обязан содержать те же смысловые блоки, иначе правила `TPL-*`/`SA-*` не найдут полей и
  вернут `FAIL`/`UNKNOWN` — это будет видно в `validation.json`, а не «тихо» пройдёт.

**Устаревшая форма `sources.override_template`.** Ради обратной совместимости схема принимает ключ и
внутри `sources`; при чтении значение переносится на верхний уровень (если там `null`), а устаревший ключ
удаляется. Поэтому нормализованный конфиг и `config_sha256` не зависят от формы записи. При этом
печатается предупреждение (в stderr; `config-check` — в stdout):

```
[WARN] sources.override_template устарел — используйте override_template
```

Предупреждение не блокирует: конфиг валиден, но форму стоит поправить. Если ключ задан в обоих местах,
побеждает верхнеуровневый.

## 5. Куда сохранять отчёт

По умолчанию отчёт публикуется **комментарием в задачу Jira** — это `jira.comment_mode: post`, и
`output` для этого не нужен. Раздел `output` управляет **дополнительной** публикацией страницы/заметки.

```yaml
jira:
  comment_mode: post      # post | draft
output:
  target: none            # none | confluence | obsidian
  confluence:
    space: ""             # ключ пространства, например ECOMCS
    page_id: null         # страница публикации; null — создать новую
  obsidian:
    path: ""              # путь заметки в хранилище
```

### 5.1 Комментарий в задачу (`jira.comment_mode`)

- **`post` (дефолт)** — результат уходит в **саму анализируемую задачу** тремя видами комментариев, у
  каждого свой маркер и свой `ref` в `state.published[]`:
  - `validation` — «Результаты валидации» (готовность: вердикт, пробелы, гигиена полей, как
    перегенерировать; Story Points в нём нет): маркер
    `<!-- task-readiness-review:validation:<TASK-KEY> -->`, `ref=<TASK-KEY>#validation`, тело —
    `jira-validation.md` (рендер из `validation.json`);
  - `estimate` — «Результаты оценки» (SP, диапазон, таблица ролей, ресурсы, основания): маркер
    `<!-- task-readiness-review:estimate:<TASK-KEY> -->`, `ref=<TASK-KEY>#estimate`, тело —
    `jira-estimate.md` (рендер из `estimate.json`);
  - `questions` — вопросы из `check`: маркер
    `<!-- task-readiness-review:questions:<TASK-KEY> -->`, `ref=<TASK-KEY>#questions`, тело —
    `comment-draft.md`.

  Повторный запуск **обновляет** тот же комментарий своего вида: `comment_id` берётся из
  `state.published[]` по `ref`, а если он потерян — комментарий ищется по маркеру. Дублей не появляется.
- **Риск, который надо понимать:** это запись в задачу — её видят все участники. Скилл пишет **только**
  комментарии к анализируемой задаче: ни переходов статуса, ни правок полей, ни Story Points, ни
  назначения исполнителя. Никакие другие задачи не трогаются.
- **`draft`** — комментарии только печатаются и лежат в `.task-readiness/runs/<KEY>/<RUN-ID>/`
  (`jira-validation.md` и `jira-estimate.md` для отчёта, `comment-draft.md` для вопросов); в Jira ничего
  не уходит.
- **Как отключить запись, не меняя режим:** `--no-jira` (не писать в Jira вовсе: тексты уходят в
  action-пакеты — `actions/jira-validation.md` и `actions/jira-estimate.md` у `publish`,
  `actions/jira-questions.md` у `check`) и `--draft` (только напечатать текст, `state` не менять).
  Обратно включить при `draft` можно флагом `--post` (флаг слэш-команды).
- Лимит тела комментария Jira — 32767 символов. Длинный текст режется по границе абзаца и получает хвост
  `… (полный отчёт: <путь>)`; путь ведёт на `report.md` прогона (полный человекочитаемый текст), а если
  его нет — на артефакт, из которого собран комментарий.
- Jira недоступна (MCP и REST) или `401/403` → `[WARN]` + action-пакеты (`actions/jira-validation.md` и
  `actions/jira-estimate.md` у `publish`, `actions/jira-questions.md` у `check`), код `0`: работа не
  падает, `stage` не двигается, человек публикует вручную по готовому тексту.

### 5.2 Дополнительная публикация (`output.target`)

- **`target: none`** (дефолт) — дополнительной публикации нет. Отчёт печатается в stdout и лежит в
  каталоге прогона (`runs/<KEY>/<RUN-ID>/report.md`); комментарий в задачу при `comment_mode: post`
  публикуется независимо от этого ключа.
- **`target: confluence`** — нужны `confluence.space` (непустой) и либо `confluence.page_id` (обновить
  страницу), либо `null` (создать новую). Публикуется **после** комментария в Jira; id/url страницы
  пишутся в `state.json` (`published[]`, при `--model` — `model_page`).
- **`target: obsidian`** — нужен `obsidian.path` (путь заметки в хранилище). Публикация — запись заметки
  через MCP Obsidian.
- **MCP страниц недоступен:** публикация не роняет прогон. Команда печатает `[WARN]` и выдаёт
  **action-пакет** — готовый текст отчёта, целевой путь/пространство и точный список шагов, что сделать
  руками (создать страницу, вставить текст, записать id в `state.json`). `stage` при этом не двигается в
  `published`: без реальной публикации этап не считается пройденным.
- Страницы и заметки **никогда** не публикуются молча: только по явной команде `publish` (и только при
  заданном `output.target`).

## 6. Запрет секретов

- Токены берутся **только из переменных окружения**: `JIRA_TOKEN`, `CONFLUENCE_TOKEN`, `GITLAB_TOKEN`.
  В конфиге их быть не может — ни в каком виде, включая «закомментированный» ключ.
- `config-check` рекурсивно проверяет **имена ключей** (не значения) на
  `(?i)(token|secret|password|passwd|api[_-]?key|private[_-]?key|\bpat\b)`. `pat` ищется как отдельное
  слово, поэтому обычный `output.obsidian.path` секретом не считается.
- Найден секрет — `CONFIG_ERROR` (3), сообщение:
  `[MISSING] config.jira.token — ключ похож на секрет: секреты в конфиге запрещены, используйте
  переменные окружения JIRA_TOKEN / CONFLUENCE_TOKEN / GITLAB_TOKEN`.
- Значение секрета в сообщение не попадает: проверяется только имя ключа, чтобы токен не утёк в лог.

## 7. Нормативная шкала

`estimation.scale` **обязана** совпадать с эталонной шкалой Story Points:

```yaml
estimation:
  scale: [1, 2, 3, 5, 8, 13, 21]
```

- Источник — Confluence «T100 Story Points» (page_id `4278391451`), на которой обучена модель.
- Схема требует ровно 7 элементов из закрытого набора `1,2,3,5,8,13,21`; `config.validate_config`
  дополнительно проверяет строгое возрастание и точное совпадение с нормативной шкалой.
- Расхождение — **ошибка конфига** с понятным сообщением, а не тихая подмена:
  `config.estimation.scale: шкала нормативна и должна совпадать с эталонной [1, 2, 3, 5, 8, 13, 21]
  (Confluence «T100 Story Points», page_id 4278391451), получено …`.
- Почему нельзя переопределить: на этой шкале калибруется `factor` и считается `nearest_scale`. Другая
  шкала сделала бы числа отчёта несравнимыми с эталоном и со статистикой спринтов.

### 7.1 Векторизация: `estimation.vector`

```yaml
estimation:
  vector:
    enabled: true         # по умолчанию: векторы строятся на train, estimate ищет аналоги
    adjust_range: false   # по умолчанию: числа не меняются
    top_k: 5
    min_corpus: 30        # пол: значение меньше 30 — ошибка конфига
    top_terms: 15
    weight_word: 0.5
```

- **`enabled: true` по умолчанию.** `train` обязан собрать `norm/task-texts.json` и
  `norm/task-vectors.json`; `estimate` читает артефакт и пишет `similar_tasks[]`, в отчёте появляется
  секция 9. Если артефакта нет — `estimate` печатает `[WARN]` и считает без соседей, а `train`
  считается незавершённым. `enabled: false` — осознанный отказ, векторы не читаются вовсе.
- **`adjust_range: true` меняет ТОЛЬКО `range`/`confidence`/`variability_reason`.** `base` и `expected`
  остаются прежними всегда: векторный сигнал не пересчитывает оценку, он расширяет интервал, если
  похожие задачи того же бакета стоили дороже/дешевле и их `cosine >= similar_threshold`.
- **Включение без калибровки — риск.** `similar_threshold` берётся только из `calibration` артефакта
  (`p90` межбакетных косинусов); ключей `similar_threshold`/`dissimilar_threshold` в конфиге нет
  намеренно. При `calibration.confidence: low` (меньше 50 межбакетных пар) порог — ориентир, и
  `adjust_range: true` лучше не включать.
- **Порядок:** `trr vectors build` (на `train` — обязательный шаг) → `trr vectors calibrate` →
  `trr vectors similar --task <KEY>` (посмотреть соседей) → (осознанно) `adjust_range: true`.
  Подробности — `vectorization.md`.

### 7.2 Эвристические параметры: `estimation.params`

Три числа `0.0 … 1.0`, описывающие задачу по трём осям:

| Параметр | Смысл (формулировка заказчика) | Что даёт |
|---|---|---|
| `weight` | «вес задачи, отражает сложность задачи» | тип задачи, длина описания, критерии приёмки, маркеры декомпозиции/рефакторинга, число компонентов |
| `heat` | «отражает необходимость проработки» | маркеры неопределённости, research-метки, незаполненные обязательные секции, открытые вопросы |
| `connectivity` | «сложность и количество внешних интеграций» | `issuelinks`, integration-метки, упоминания внешних систем, число компонентов |

**Отдельных полей в Jira под них нет.** Значения выводятся эвристически из снимка задачи
(`context.json`) и всегда несут провенанс:

```bash
trr params --task E001-1234 --json          # по снимку прогона
trr params --issue-type Feature --text-file task.md --labels api,integration --links 3
trr params --weight 0.9                     # ручной override
```

Ответ `params.derive(context, cfg)` — по каждому параметру `{value, source, evidence[],
components{}}`, плюс `applied: {enabled, clamp}`:

- `source: heuristic` — значение собрано из сигналов; `evidence[]` объясняет вклад каждого
  («issue_type=Feature → 0.60»), `components{}` — взвешенный вклад;
- `source: override` — число `weight`/`heat`/`connectivity` в context (или `context.params.<имя>`),
  флаги `--weight/--heat/--connectivity` у `trr check` и `trr estimate`. Override приоритетнее
  эвристики и зажимается в `[0, 1]`;
- `source: disabled` — `enabled: false`: все три значения равны `defaults`;
- **сигналов нет** (пустой context) — значения равны `defaults`, это не ошибка.

```yaml
estimation:
  params:
    enabled: true         # false — не выводить эвристику
    clamp: [0.5, 2.0]     # границы множителя: 0 < min <= 1.0 <= max <= 4.0
    coefficients:         # вклад отклонения параметра в множитель (0…2)
      weight: 0.5
      heat: 0.4
      connectivity: 0.3
    defaults:             # значения, когда сигналов нет (0…1)
      weight: 0.5
      heat: 0.5
      connectivity: 0.5
    signals: {}           # переопределение весов сигналов: имя → вес (0…1)
```

- **Блок необязателен.** Без него действуют значения выше; `apply_defaults` дотягивает
  недостающие под-ключи, не затирая пользовательские (например `coefficients: {weight: 0.7}`
  сохранит `heat`/`connectivity` из дефолтов).
- **Множитель** `multiplier = clamp(1 + a*(weight−w₀) + b*(heat−h₀) + c*(connectivity−k₀),
  clamp[0], clamp[1])`, где `a,b,c` — `coefficients`, `w₀,h₀,k₀` — `defaults`. При значениях по
  умолчанию равен `1.0`. Множитель **входит в формулу оценки** третьим сомножителем:
  `expected = nearest_scale(base × factor × params_multiplier)`; база сравнения — профиль параметров
  бакета модели (`params_profile`), при его отсутствии — `defaults`. Поэтому «типовая» задача бакета
  оценку не сдвигает, а отклонение от профиля — сдвигает. `estimate` печатает `[INFO] params: …`
  с применённым множителем и его базой.
- **`signals`** — тонкая настройка весов внутри параметра. Сумма весов параметра = 1.0; неизвестные
  имена игнорируются. Полный список сигналов — `references/estimation-model.md` §13.
- **Ошибки конфига** (код 3): `clamp` без `1.0` внутри границ, `defaults` вне `[0, 1]`,
  `coefficients` вне `[0, 2]`, вес сигнала вне `[0, 1]`.

### 7.3 Дополнительные ресурсы: `estimation.resources`

Надбавка за ресурсы, которые задача затрагивает помимо работы роли: **allure** — при написании
тест-кейсов, **e2e-сервис автотестирования** — при написании автотестов. Правило `RS-01`
(`references/estimation-model.md` §9.6): за каждый распознанный ресурс `+sp_per_resource` SP к оценке
основного исполнителя, либо оценка по верхней границе диапазона.

```yaml
estimation:
  resources:
    enabled: true          # false — правило выключено целиком
    sp_per_resource: 1     # сколько SP добавляет один ресурс (0 — не менять оценку)
    mode: add              # add | upper_bound
    items:                 # имя ресурса → алиасы (подстроки, сравнение через casefold)
      allure: ["allure", "тест-кейс", "тест кейс", "тесткейс", "test case", "testcase"]
      e2e: ["e2e", "автотест", "autotest", "auto-test", "end-to-end", "end to end"]
```

- **Блок необязателен:** без него действуют дефолты выше. `apply_defaults` дотягивает недостающие
  под-ключи; `items` сливается по именам — своё имя добавляет ресурс, пустой список выключает
  существующий (`allure: []`), остальные сохраняют дефолтные алиасы.
- **Детекция** — по тексту снимка задачи: заголовок, описание, `sections{}`, `labels`, `issue_type`.
  Один ресурс = один элемент; `evidence` — короткая цитата, `source` — где нашлось совпадение.
- **Куда не применяется:** к производной QA-записи (`source=derived`) и к QA из Jira — иначе двойной
  счёт (ресурс уже двигает оценку исполнителя).
- **Ошибки конфига** (код 3): `sp_per_resource < 0`, `mode` вне `["add", "upper_bound"]`, `items` не
  объект или алиас не строка.

## 8. Резолв имён: `match-sprints` и `match-fields`

Два ключа конфига задают то, что человек знает, но не помнит наизусть: **названия** спринтов
(`sources.sprints[].board_labels`) и **имена** полей Jira (`jira.field_names`). И то и другое
превращается в id детерминированно, без сети — сеть (Jira REST/MCP) остаётся за агентом.

### 8.1 `trr match-sprints`

```bash
trr match-sprints --labels "T100-T102 26.18, T100-T102 26.19" --sprints-file jira-sprints.json
```

- `--labels` — названия как в UI, через запятую (тот же нормализатор, что и у `sources.sprints`:
  обрезка пробелов, отбрасывание пустых, дедупликация с сохранением порядка).
- `--sprints-file` — JSON-индекс: ответ `/rest/agile/1.0/board/<id>/sprint`, `{"sprints": [...]}`,
  массив `{id, name, state}` или отображение `{name: id}`.
- Три уровня сопоставления: точное → нормализованное (casefold, `ё → е`, схлопнутые пробелы) → префиксное.
- Вывод: `matched: <label> → id=<id> (<name>)`, `ambiguous: … → кандидаты`, `missing: <label>`.
- Коды: `0` — все найдены; `2` — есть `ambiguous`/`missing`; `4` — нет файла; `5` — файл не разбирается.

Агент переносит результат в `resolved-sources.json` (`ref` = id, `title` = имя), и `train` берёт уже
числовые id. Двусмысленность **не** разрешается угадыванием: два спринта с похожими именами — это
`[BLOCKED]` и вопрос человеку.

### 8.2 `trr match-fields`

```bash
trr match-fields --names-json jira-field-names.json --fields-file jira-fields.json
```

- `--names-json` — `{key: имя}` (например выгрузка `jira.field_names`) или массив имён.
- `--fields-file` — ответ `/rest/api/2/field` (`{"values": [...]}`), список `{id, name}` или
  отображение `{id: name}`.
- Сопоставление — **только точное после нормализации** (casefold, `ё → е`, схлопнутые пробелы).
  Префиксного уровня нет намеренно: «Story Points» и «Story Points (old)» — разные поля, и префикс
  молча выбрал бы не то.
- Вывод: `resolved: story_points → customfield_10004`, `missing: <имя>`, `ambiguous: <имя> → …`.
- Коды те же: `0` / `2` / `4` / `5`.

Когда это нужно: `jira.fields.*` пусты, а `jira.resolve_fields_by_name: true` (дефолт). Агент читает
`/rest/api/2/field`, прогоняет `match-fields`, получает `customfield_*` и либо вписывает их в
`jira.fields`, либо передаёт дальше в `resolved-sources.json`. При `resolve_fields_by_name: false` все три
id обязаны быть заполнены — иначе `[MISSING] config.jira.fields.*`.

### 8.3 Почему имена — не id

Имя поля в Jira локализуемо и переименовываемо: `customfield_10004` стабилен, «Story Points» — нет.
Поэтому в конфиге живут **оба** слоя: `field_names` — то, что человек видит и правит; `fields` —
зафиксированные id, которые пишет `match-fields`. Резолв по имени — шаг настройки, а не рантайма:
на каждом запуске `train`/`check` сеть за списком полей не ходит.

## 9. Перенос модели: `artifacts.*`

Секция отвечает на два вопроса: **что** кладётся в переносимый бандл и **куда** он публикуется.
Сам бандл, манифест и проверки целостности — `artifacts.md`; здесь только конфиг.

```yaml
artifacts:
  include_sprint_sample: true        # norm/sprint-sample.json в бандл
  export_target: none                # none | local | confluence | gitlab | obsidian
  local:
    path: null                       # файл или каталог для export_target: local
  confluence:
    space: null                      # ключ пространства
    parent_page_id: null             # родительская страница бандла
    title_template: "Task Readiness model {{model_version}} — {{project}}"
  gitlab:
    project: null                    # group/project или id
    path: "task-readiness/"          # каталог в репозитории
    branch: "main"
  obsidian:
    path: null
```

### 9.1 `include_sprint_sample`

- `true` (дефолт) — в бандл попадает `norm/sprint-sample.json`: бандл самодостаточен, на нём можно
  повторно прогнать `stats` и `calibrate` без доступа к Jira.
- `false` — только производные артефакты (`reference-estimates`, `sprint-stats`, модель). Меньше размер
  и меньше сырых строк задач, но пересчитать статистику из бандла уже нельзя.

### 9.2 `export_target`

`none` (дефолт) — законный режим «не публиковать»: бандл собирается вручную (`trr artifact pack`) и
никуда не уходит, место публикации не требуется. Любой другой target обязывает заполнить **ровно своё**
место:

| `export_target` | Обязательные ключи | Кто публикует |
|---|---|---|
| `none` | — | никто (только локальный `pack`) |
| `local` | `local.path` | скрипт (`artifact pack` кладёт файл) |
| `confluence` | `confluence.space`, `confluence.parent_page_id` | агент через MCP Confluence |
| `gitlab` | `gitlab.project` | агент через MCP GitLab (скилл не пишет git) |
| `obsidian` | `obsidian.path` | агент через MCP Obsidian |

Незаполненное место — не «тихая» ошибка: `config-check` печатает
`[MISSING] config.artifacts.<target>.<ключ>: не задано — <что сделать>` (код `3`), `doctor` — `[WARN]`,
`trr artifact plan --target <target>` — `[MISSING]` с кодом `2`. Проверка в `config.py` (`artifact_place_problems`) смотрит
только текущий `export_target`: пустые места «чужих» целей ошибкой не считаются.

### 9.3 Подстановки в `title_template`

`artifacts.confluence.title_template` — **двойные** фигурные скобки: `{{model_version}}` и `{{project}}`.
Одинарные (`{version}`, `{project}`) не подставляются и останутся в заголовке как текст — это частая
ошибка при копировании шаблона.

### 9.4 Публикация — всегда через агента

Скрипт **не публикует** бандл ни в Confluence, ни в GitLab, ни в Obsidian: он собирает архив, считает
sha256 и печатает план. Публикацию выполняет агент (MCP/REST), после чего `trr artifact record` фиксирует
факт в `state.artifacts[]`. Поэтому `export_target` — это разрешение и адрес, а не действие: `train`
сам никуда не пишет.

## 10. Локальное SQLite-зеркало: `storage.sqlite`

Зеркало — **второй адрес** тех же данных, а не замена файлов: `norm/*.json`, `model/*.json`,
`runs/*/*.json` остаются источником истины и контрактом, БД нужна для запросов (`db query`), истории
метрик (`metrics`, `events`) и векторов (`vectors`). Публикация в Confluence — отдельная ось: выключение
зеркала не влияет на публикацию, включение — не публикует ничего.

### 10.1 Ключи

| Ключ | Дефолт | Что делает |
|---|---|---|
| `storage.sqlite.enabled` | `true` | Вести ли зеркало. `false` — шаги пайплайна пишут только файлы, БД не создаётся. |
| `storage.sqlite.path` | `.task-readiness/trr.sqlite3` | Файл БД. Относительный путь — от корня проекта. |
| `storage.sqlite.keep_vectors` | `true` | Хранить векторы задач (`BLOB` float32, `struct.pack('<Nf')`). |
| `storage.sqlite.keep_payloads` | `true` | Хранить полные JSON-снимки (`payload`, `terms`). |
| `storage.sqlite.vacuum_on_pack` | `false` | `VACUUM` при `trr db export`. |

Блок необязателен: отсутствие `storage` равносильно дефолтам. Все пять ключей тоже необязательны —
`apply_defaults` дотягивает недостающие.

### 10.2 Путь и проверки

- **Относительный путь** разрешается от корня проекта (`--workdir`), а не от текущего каталога:
  `trr db init` из любого места пишет в один и тот же файл.
- **`../…` — ошибка конфига** (3): зеркало не должно уезжать за пределы проекта.
- **Абсолютный путь** разрешён (осознанный выбор — быстрый диск, общий том), но `config-check` печатает
  `[WARN] config.storage.sqlite.path: абсолютный путь … — файл БД вне проекта`.
- **Расширение** `.sqlite3`/`.db` рекомендуется; другое — `[WARN]` (файл всё равно SQLite).

### 10.3 Что попадает в БД

| Шаг | Таблицы |
|---|---|
| `trr stats` | `sprint_stats`, `metrics` |
| `trr calibrate` | `model_versions`, `model_buckets`, `gap_rules`, `reference_pages`, `reference_buckets`, `sprint_stats`, `metrics` |
| `trr vectors build` | `vectors`, `vector_meta`, `metrics` |
| `trr vectors similar` | `similarities` |
| `trr check` | `runs`, `validations`, `metrics`, `events` |
| `trr estimate` | `runs`, `estimates`, `estimate_roles`, `metrics`, `events` |
| `publish` / `state` | `publications`, `events` |
| `trr db ingest` | всё вышеперечисленное из уже лежащих на диске артефактов |

Секретов в БД нет: токены не пишутся, конфиг целиком не сохраняется. Ошибка БД (нет прав, диск, битый
файл) — `[WARN] storage: …` в stderr, код выхода основного шага не меняется.


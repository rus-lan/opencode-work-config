# task-readiness-review

Скилл для агента: проверяет готовность задачи Jira к разработке и считает трудозатраты в story points
по ролям. Готовность — полнота описания (11 полей), блоки передачи SA → разработка, чек-лист review BA,
критерии приёмки и DoD. Оценка — калиброванная модель из эталона Story Points и статистики закрытых
спринтов; каждое число в отчёте имеет provenance.

Полное описание навыка, инварианты и таблица этапов — [SKILL.md](SKILL.md). Справочники —
[references/](references/): конвейер, артефакты, конфиг, модель, правила проверки, источники, команды,
диагностика, векторизация.

## Установка одной командой

```sh
curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Ftask-readiness-review%2Finstall.sh/raw?ref=main" \
  | TASK_READINESS_REVIEW_TOKEN="$GITLAB_TOKEN" sh
```

Проект приватный: `GITLAB_TOKEN` — ваш GitLab PAT с правом чтения проекта. Заголовок `PRIVATE-TOKEN`
аутентифицирует скачивание самого `install.sh` из ветки `main`, а `TASK_READINESS_REVIEW_TOKEN` передаёт
токен внутрь установщика для загрузки релиза из Generic Package Registry.

Локально, из клона репозитория (без сети и без токена):

```sh
git clone git@git.ecom.tech:5022/ecom/dev/common/personal/e001-ai-hub.git
cd e001-ai-hub/skills/task-readiness-review && ./install.sh
```

Что ставится (глобально, по умолчанию):

- скилл → `~/.config/opencode/skills/task-readiness-review/` (с `--claude` также в `~/.claude/skills/`);
- одна слэш-команда `task-readiness-review.md` → `~/.config/opencode/command/` (отключается `--no-commands`);
- маркер `.task-readiness-review-installed` — только такой каталог перезаписывается и удаляется;
  команда помечается комментарием в конце файла.

Режимы установки:

| Режим | Скилл | Команда |
|---|---|---|
| по умолчанию / `--global` | `~/.config/opencode/skills/task-readiness-review/` | `~/.config/opencode/command/task-readiness-review.md` |
| `--project <dir>` | `<dir>/.opencode/skills/task-readiness-review/` | `<dir>/.opencode/commands/task-readiness-review.md` |
| `--dir <path>` | ровно `<path>` | `<path>/../command/task-readiness-review.md` |

Каталоги переопределяются переменными `OPENCODE_SKILLS_DIR`, `OPENCODE_COMMAND_DIR` (алиас
`OPENCODE_COMMANDS_DIR`), `CLAUDE_SKILLS_DIR`. Проектная установка ничего не пишет вне `<dir>/.opencode/`.

Полезные флаги: `--dry-run` (показать план, ничего не писать; каталог проекта не создаётся), `--force`
(перезаписать чужой каталог/файл), `--uninstall` (удалить поставленное по маркерам), `--claude`
(дополнительно в `~/.claude/skills/`), `--no-commands` (только скилл), `--version X.Y.Z` (зафиксировать
версию), `--local <путь>` (источник — локальный каталог), `--sha256 <hex>` (ожидаемая контрольная сумма
архива), `--insecure-host` (нестандартный/самоподписанный GitLab), `-h`.

## Обновление

Повторите команду установки — это обновление: каталог с маркером перезаписывается без `--force`.
Зафиксировать версию и пропустить проверку контрольной суммы (только если её нельзя выполнить):

```sh
TASK_READINESS_REVIEW_VERSION=0.4.0 TASK_READINESS_REVIEW_SKIP_CHECKSUM=1 ./install.sh
```

## Быстрый старт

1. Установить скилл (команда выше) и перезапустить сессию opencode.
2. В проекте создать `task-readiness-review.yaml`: источники эталона, `board_id` и `sprint_ids`, проект
   Jira (или дать подкоманде `init` собрать его из примера `task-readiness-review.example.yaml`).
3. `/task-readiness-review init "<эталон и спринты>"` — резолв источников с `evidence`
   в `.task-readiness/resolved-sources.json`.
4. `/task-readiness-review train` — статистика спринтов, калибровка модели, страница модели.
5. `/task-readiness-review check E001-1234`, затем `/task-readiness-review estimate E001-1234` — вердикт,
   пробелы, вопросы с адресатом и оценка по ролям с диапазоном и провенансом.
6. `/task-readiness-review publish E001-1234` — результат уходит **двумя комментариями в саму задачу Jira**:
   «Результаты валидации» (вердикт, пробелы, гигиена полей) и «Результаты оценки» (SP, диапазон, таблица
   ролей, основания, похожие задачи). Идемпотентно: повторный запуск обновляет оба комментария; при
   `output.target: confluence|obsidian` — дополнительно страница/заметка. `--no-jira`/`--draft` — только
   печать; `/task-readiness-review doctor` — диагностика, если что-то не работает.

Флоу: `install → init → train → check → estimate → publish`; боковые ветки — `refresh` (правки задачи) и
`enrich` (новые спринты/эталон). Без аргументов команда печатает справку, текущий этап
(`trr state get stage`) и следующий шаг.

Артефакты живут в `.task-readiness/` рабочей директории проекта; прогон — отдельный `<RUN-ID>`.

## Флоу скилла

```text
Вход А «с нуля»:        install → init → train → stage=trained
Вход Б «модель готова»: install → init --from-artifact → stage=trained

дальше — на каждую задачу:
  check → estimate → report → publish
  refresh — после правок задачи (новый RUN-ID + delta.md)
  enrich  — после новых данных обучения (version+1 → publish --model)
  doctor  — в любой момент, только читает
```

`train` — один раз на проект, `check` обязателен перед `estimate`, `doctor` вне цепочки. Сеть нужна
только агенту: `init` и `train` читают Confluence и Jira, `check` — задачу, `publish` пишет два
комментария в задачу. `estimate` и `report` работают офлайн; `check --no-jira`, `publish --draft` и
`publish --no-jira` — без записи в Jira.

Полная схема — гейты по этапам, таблица «этап → артефакты → гейт → идемпотентность», каталог
`.task-readiness/` (что переносится между проектами, а что локально) и точка возврата после
`enrich`/`refresh` — в [SKILL.md](SKILL.md) §2.

## Практическое применение

Два сценария: свой проект с обучением и готовый бандл модели. Детали и ожидаемый вывод каждой команды —
[SKILL.md](SKILL.md) §4.

### Сценарий А — с нуля (свой проект, своя модель)

Подготовить: доступ к эталонной странице Story Points и к закрытым спринтам, право писать комментарии в
Jira, токены `JIRA_TOKEN`/`CONFLUENCE_TOKEN` на случай REST fallback.

1. **Установка** — одна команда (раздел выше), меньше минуты.
2. **Конфиг** `task-readiness-review.yaml`: страница эталона, борд и спринты, проект Jira, id трёх полей
   (`Story Points`, `QA Estimation`, `Роль`), типы задач с QA-оценкой, шкала SP. Незаменённые
   демо-значения `doctor` помечает `[WARN]`.
3. **Проверка**: `trr config-check`, затем `trr doctor`. `[MISSING]` на `norm/*` и модели до обучения —
   норма, а не сбой.
4. **Обучение** — `init`, затем `train`. Здесь ждать дольше всего: агент вычитывает эталон и десятки
   задач по закрытым спринтам, Python считает статистику, строит векторы и калибрует модель.
5. **Страница модели** — публикуется сразу после `train`; без неё `check` не пройдёт гейт (SKILL.md §8.1).
6. **Первый прогон**: `check --no-jira` → `estimate` → `report` → `publish --draft` → просмотр тел
   комментариев → `publish`.
7. **Проверка качества**: `confidence` и `n` по бакетам в `model/estimation-model.json`,
   `pairs_nonzero` в `norm/task-vectors.json`; нормы — SKILL.md §4.1.

### Сценарий Б — модель уже готова (обучение не требуется)

Подготовить: бандл `task-readiness-model-v<N>.tar.gz` от команды, которая модель уже обучила, и конфиг
нового проекта.

1. `trr artifact inspect model.tar.gz` — что внутри, для какого проекта и какая версия модели.
2. `trr init --from-artifact model.tar.gz` — модель развёрнута, `stage=trained`, `train` не нужен.
3. `trr doctor` — модель на месте, hash страницы модели совпадает с `model.checksum`;
   `trr calibrate --reason enrich` отвечает «входы не изменились».
4. Дальше обычный цикл по каждой задаче: `check → estimate → report → publish`.

Чего не делать: `train`, `vectors build` и `init --force` — они пересоберут модель и векторы на другом
корпусе, и числа разойдутся с эталоном, на котором модель калибровалась.


## Перепубликация страницы модели

Страница модели (`estimation-model.md`) публикуется не «руками», а телом, которое готовит
`trr model-page-payload`; публикует агент через Confluence REST. Полная процедура — [SKILL.md](SKILL.md) §8.1.

Ключевое: **версия страницы и версия модели — разные числа**. В `state.model_page.version` лежит версия
модели (её пишет `publish --model`), а `PUT /rest/api/content/<id>` требует фактическую версию страницы + 1:

```sh
# 1. фактическая версия страницы (REST, токен из CONFLUENCE_TOKEN)
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/$PAGE_ID?expand=version"   # → version.number, например 5

# 2. тело PUT: page_version = 5 + 1; model_version берётся из модели
trr model-page-payload --format json --page-version 6 --out /tmp/model.payload.json

# 3. PUT /rest/api/content/$PAGE_ID с body.storage.value из payload,
#    затем фиксация факта:
trr publish --model --target confluence --ref "$PAGE_ID" \
  --url "https://space.samokat.ru/pages/viewpage.action?pageId=$PAGE_ID" \
  --file .task-readiness/model/estimation-model.md --no-stage
```

Без `--page-version` команда возьмёт `state.model_page.version` (версию модели) и напечатает `[WARN]`:
номер придётся сверить вручную, иначе Confluence ответит `409 Conflict`. В JSON-payload версии разделены
полями `model_version` и `page_version` (`version` — синоним `page_version`).

## Перенос обученной модели

Модель можно перенести в другой проект, не переобучая: `trr artifact pack` собирает `.tar.gz` с
`manifest.json` (sha256 файлов, версия/checksum модели, происхождение: проект, борд, спринты), затем бандл
публикуется по `artifacts.export_target` (`local`/`confluence`/`gitlab`/`obsidian`), а `trr artifact record`
фиксирует факт в `state.artifacts[]`. На новом месте:

```sh
trr artifact inspect model.tar.gz       # что внутри
trr init --from-artifact model.tar.gz   # stage=trained, без train
```

Импорт проверяет `artifact_version`, sha256 каждого файла и `model.checksum`; модель чужого проекта
(`origin.project ≠ jira.project`) блокируется до явного `--allow-foreign-project`. В бандл не входят
`state.json`, прогоны задач (`runs/**`), `trr.sqlite3` и `model/model-history.jsonl` — это история
конкретного проекта, на новом месте она начинается заново. Пошаговый сценарий «модель уже готова» —
[SKILL.md](SKILL.md) §4.2.

## Векторизация (этап A)

Поиск похожих задач по тексту реализован и **по умолчанию включён** (`estimation.vector.enabled: true`).
Три команды:

```sh
trr vectors build --min-corpus 30      # norm/task-texts.json → norm/task-vectors.json (+ калибровка)
trr vectors similar --task E001-1234   # top-5 соседей: key, cosine, SP, роль, вид работ
trr vectors calibrate                  # пересчитать пороги p90/p50 без пересборки
```

Что работает:

- `norm/task-texts.json` — тексты задач (агент вычитывает из Jira); `norm/task-vectors.json` —
  гибрид словесного TF-IDF и символьных 3–5-грамм, разреженное хранение `top_terms` термов;
- пороги не задаются числом: `similar_threshold = p90` межбакетных косинусов, `dissimilar_threshold = p50`
  (абсолютные `0.5`/`0.2` экспериментом опровергнуты и в коде не используются);
- при `estimation.vector.enabled: true` в `estimate.json` появляется `similar_tasks[]` и
  `provenance kind=vector_nn`, а в отчёте — справочная секция `## 9. Похожие задачи (справочно)`;
- `estimation.vector.adjust_range: true` (по умолчанию `false`) разрешает расширить `range` по соседям
  того же бакета и понизить `confidence`; `base`/`expected` не меняются никогда.

Что включено по умолчанию: `estimation.vector.enabled: true` — векторы строятся на `train`, поэтому
`estimate` сразу находит аналоги; `adjust_range: false`, то есть числа оценки не меняются. Оба артефакта
(`task-texts.json`, `task-vectors.json`) входят в бандл `trr artifact pack`, поэтому переносятся вместе с
моделью и не требуют пересборки на новом месте.

Подробности — [references/vectorization.md](references/vectorization.md); исследование, числа эксперимента
и обоснование калибровки — `docs/superpowers/specs/2026-11-17-task-readiness-review/VECTORIZATION.md`.

## Локальное SQLite-зеркало (`trr db`)

Все артефакты по умолчанию пишутся **и в файлы, и в `.task-readiness/trr.sqlite3`** — включено, ничего
настраивать не нужно (`storage.sqlite.enabled: true`). Файлы остаются источником истины; БД нужна для
запросов, истории метрик и векторов. Публикация в Confluence — отдельная ось: зеркало ничего не публикует.

```sh
trr db init                            # создать/мигрировать (идемпотентно)
trr db ingest                          # бэкфилл из уже лежащих на диске артефактов
trr db stats                           # таблица → строк
trr db query --sql "SELECT role, work_kind, value FROM reference_buckets ORDER BY value"
trr db export --out dump.json          # JSON-дамп всех таблиц
```

Запись идёт после успешного шага и не валит пайплайн: ошибка БД — `[WARN] storage: …`, код выхода шага
не меняется. `db query` — только чтение (`SELECT`/`WITH`/`PRAGMA`); `INSERT`/`DROP`/`ATTACH` отклоняются.
Схема таблиц — [references/artifacts.md](references/artifacts.md) §10, ключи — [references/config.md](references/config.md) §10.

## Требования

- Python 3.9+ и только stdlib: `pip install` не нужен.
- Confluence и Jira: MCP (основной путь) или REST с токенами `CONFLUENCE_TOKEN` и `JIRA_TOKEN`.
- GitLab: токен `GITLAB_TOKEN` — только для сбора доказательств по ссылкам задачи.
- Obsidian: опционально, `OBSIDIAN_VAULT`.
- Для установки: `sh`, `tar`, `sha256sum` или `shasum` (POSIX sh, режимы `--global`/`--project`/`--dir`).

## Чего скилл не делает

Не делает в Jira ничего, кроме двух комментариев к анализируемой задаче — «Результаты валидации» и
«Результаты оценки» — и одного с вопросами: по умолчанию (`comment_mode: post`) `publish` публикует первые
два, `check` — вопросы, повторный запуск обновляет те же комментарии. Ни переходов статуса, ни правок
полей, ни Story Points, ни других задач. Отключить запись: `comment_mode: draft`, `--no-jira`, `--draft`.
Скилл не коммитит и не пушит, не оценивает без обученной модели, не выдумывает `page_id`, `board_id` и
значения Story Points.

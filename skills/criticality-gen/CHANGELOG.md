# Changelog

Все заметные изменения компонента фиксируются в этом файле. Формат основан на
[Keep a Changelog](https://keepachangelog.com/ru/1.0.0/).

## [Unreleased]

### Исправлено

- **`publish` падал с `NameError: _catalog`** при печати плана: в
  `dochub_repo_url` передавалась несуществующая переменная вместо `catalog`.
  `--dry-run` и `--apply` снова работают.
- **`publish` создавал вторую ветку той же задачи.** Если `--branch` не задан и
  на `origin` есть ровно одна ветка `feature/<task>*`
  (например `feature/E001-31346-opercrm-criticality`), используется она
  (`WARN`); несколько — `ERROR` со списком и требованием `--branch`; ни одной —
  прежний `feature/<task>`.
- **Описание MR писало «Было: НЕ ОЦЕНЕНО» при обновлении существующего
  паспорта.** `had_passport` и старый уровень считались в рабочем дереве клона
  (master) до checkout ветки MR. Теперь они читаются с целевой ветки
  (`git show origin/<branch>:<path>`, фолбэк — локальная ветка) и
  пересчитываются после checkout; одинаковый уровень печатается как
  «уровень не изменился», без стрелки в никуда.

### Добавлено

- `handoff --thread <tmid>` (env `HANDOFF_THREAD` → `ROCKETCHAT_THREAD` →
  `RC_THREAD`) — ответ в **существующий** тред Rocket.Chat вместо нового
  топ-сообщения. REST шлёт `roomId` + `tmid`; `roomId` не резолвится — WARN и
  фолбэк на `channel` + `tmid`. `tmid` также попадает в `.handoff-request.json`
  для MCP-транспорта. `thread_link`/`approve_link` указывают на созданный ответ
  (`message._id` из ответа API), а не на родителя.
- `scaffold --date YYYY-MM-DD` — дата генерации для новых ИС.
- **`handoff --report --thread-new` — тред отчёта.** Родитель (top-level) —
  краткий итог: уровень, метод, статус, дата генерации, участники (TA/TL) и
  основные ссылки (SSoT-карточка, MR в dochub, MR в SSoT) плюс строка
  «Детализация — в ответах ниже». Три ответа в тред (`tmid` = id родителя):
  входные значения с провенансом, расчёт (`E`, интервал, score) с
  незаполненными входами, ссылки на артефакты. `thread_link`/`approve_link`
  указывают на родителя, в реестр пишется `handoff_thread: true`; повторный
  `--thread-new` идемпотентен (`--force-resend` — обойти). Новые флаги
  `--dochub-mr-url` и `--ssot-mr-url` подставляют ссылки на MR в родителя.
- **`handoff --report --update-parent`** — правка уже отправленного родителя
  через `chat.update` (например, когда появился SSoT-MR): новый тред не
  создаётся, `thread_link` не меняется.
- **`publish` автономен «из коробки».** Без клона и без `--dochub` публикация
  сама клонирует `criteria.external_refs.repos.dochub.url` в `<проект>/dochub`
  (поддерживаются `https://` и `ssh://git@host:port/...`); отсутствие клона —
  `WARN`, а не `ERROR`.
- **`publish` нормализует enum перед записью паспорта.** Точное значение —
  как есть; смысловое совпадение (без скобок/регистра/пунктуации) →
  каноническое значение схемы dochub + `WARN`; нет совпадения — `ERROR` со
  списком допустимых значений.
- **`publish` предлагает Jira-ключ из git.** Если ключа нет в реестре и не
  задан `--task`, ключ вида `E001-<N>` ищется в имени текущей ветки и в
  последних коммитах: найден — `WARN` + использование, не найден — `ERROR` с
  подсказкой (молчаливого отказа больше нет).
- **`handoff --report` — публикация результатов оценки.** Отдельный текст-отчёт
  (`_report_text_for_is`) из `criticality-passport.yaml`, `INFORMATION.yaml` и
  `catalog.yaml`: итог, участники, входы с провенансом, расчёт (`E`, интервал,
  score), незаполненные входы без `⛔`, ссылки и «Что дальше». Гейты MR/`⛔`/SSoT
  не применяются, отправка — REST (с `--thread` — ответ в тред), `--dry-run`
  печатает текст целиком. Пишет `handoff_mode: report` и
  `handoff_status: published`; дедупликация различает режимы.

### Изменено

- `assigned_date` и `review_date` фиксируются **сразу** при появлении записи ИС
  в `catalog.yaml` (`scaffold`), считаются от даты генерации (`generated_at`)
  и попадают в каркас паспорта. Раньше до `finalize` они оставались пустыми, и
  `publish` не включал их в документ dochub.
- `publish` больше не теряет пустые даты: `_publish_transform` выводит
  `assigned_date` из `generated_at`, а `review_date` — из `generated_at` +
  `review_period_months` (или берёт значение из `catalog.yaml`).
- Одно правило расчёта дат (`review_date_from_generation`) вместо трёх копий
  формулы в `start`, `finalize` и `publish`.
- Дедупликация `handoff` учитывает `tmid`: существующее топ-сообщение с тем же
  текстом больше не считается «своим ответом в треде» (и наоборот).

### Исправлено

- `X-User-Id`, похожий на логин (`user@domain`, пробел), теперь распознаётся и
  блокирует отправку с явной причиной — раньше такой `ROCKETCHAT_USER` давал
  невнятный `401` «истёк токен».
- **Дедлок `INFORMATION.yaml` на свежем проекте.** `prepare` без снимка SSoT не
  создавал файл, а `ssot-import` отказывался писать снимок в несуществующий
  файл — не работал ни один путь. Теперь `ssot-import` сам собирает каркас из
  `templates/INFORMATION.yaml` и сразу пишет снимок; `next-step` при отсутствии
  файла советует `ssot-import` (с подсказкой про MCP `ssot_get`), а не
  `prepare-apply`.
- **`prepare` стирал провенанс снимка SSoT.** После `prepare --apply` из
  `ssot_snapshot` пропадали `source: mcp`, `commit`, `version`, `imported_at`.
  Слияние пересобирает только секции карточки, метаданные переносятся как есть.
- **Не-git репозиторий компонента блокировал прогон.** `git_repository` —
  веб-страница (GitHub/GitLab `/tree/`, `/blob/`) вместо git-URL теперь даёт
  SKIP + WARN «не git-репозиторий» и попадает в список пропущенных (`prepare` —
  «Пропущено (не git-репозиторий)», `services` — §2 «Пропущенные сервисы»),
  а не ошибку клонирования с ненулевым кодом.
- **`links` требовал удалённый клон SSoT.** Команда падала без файла
  `entities/information-systems/<код>/links.yaml`, хотя ссылки уже были в
  `INFORMATION.yaml → ssot_snapshot.links`. Теперь источник — снимок карточки,
  файл `entities/...` остался fallback для проектов без снимка.
- **`confluence.ecom.tech` уходил в `external`.** Классификатор знал только
  `space.samokat.ru`; теперь Confluence распознаётся по любому
  `confluence.*`/`*.confluence.*` хосту.
- **`verify-titles` падал на удалённой странице.** HTTP `404`/`410` теперь WARN
  «страница недоступна, пропущена» — остальные страницы проверяются, кеш
  пишется. Прочие ошибки (`5xx`/timeout) остаются ERROR, но собранные
  заголовки сохраняются перед возвратом кода `1`.


## 2.0.0 — 2026-11-24

**Breaking change: SSoT только через MCP.** Локальный клон `ssot/`, ветки,
коммиты, пуш и MR-описание по шаблону удалены: SSoT читается и правится
исключительно через `ssot-mcp` (нужна SSO-сессия), MR создаёт
`ssot_form_save`.

### Удалено

- клон `ssot/` как источник данных и git-операции над ним: `prepare` больше не
  клонирует SSoT, `--no-clone` относится только к `apps/`;
- команда `ssot` и её флаги `--apply`, `--push`, `--clone`, `--branch`,
  `--task`, `--passport-mr-url`, `--update-mr` — устаревшие флаги дают явную
  ошибку, а не игнорируются молча;
- шаблон `templates/MR-ssot.md`: описание MR собирает SSoT-приложение, наши
  данные — только `severity.type`/`severity.confirmation`;
- `GITLAB_TOKEN` на SSoT-пути и `mr.passport_mr_url` как основание SSoT-MR.

### Добавлено

- `ssot-import --entity-json` — снимок ответа `ssot_get` в
  `INFORMATION.yaml → ssot_snapshot` (+ `contacts` из `ssot_team`);
- `ssot-plan` — `.ssot/<код>-apply-plan.json`, `status: changed|no_change|blocked`,
  шаги MCP, гейты R18;
- `ssot-record --mr-url` — `.ssot/<код>-MR.url`, `.ssot/<код>-MR.md` и поля
  `ssot_*` в `INFORMATION.yaml`;
- `ssot-verify --verify-json` — `ssot_snapshot.verified`;
- `contacts --team-json` — источник `ssot_team` вместо `team.yaml`.

### Изменено

- канон: … → validate → publish (dochub MR) → ssot-import → ssot-plan →
  MCP-форма (`ssot_entity_open` → `ssot_form_fields` → `ssot_ui_select`/
  `ssot_ui_fill` → `ssot_form_save`) → ssot-record → MCP: `ssot_wait_version` →
  ssot-verify → handoff. После handoff: `ssot_mr_approve(confirm: true)` →
  `ssot_apply_changes(confirm: true)` → `ssot_wait_master`;
- гейт R18 закрывает `publish`, `ssot-plan`, `ssot-record` и MCP
  `ssot_form_save`;
- MR-URL для треда берётся из `mrUrl` (`ssot_form_save`), а не из клона.

## [1.1.0] — 2026-11-19

Слой сбора данных и финализации: интерактивный `ask`, карта обхода ссылок
`links`, приём подтверждённых фактов `sources`, отправка треда `handoff` и
`finalize` одной командой.

### Изменено

- **Упоминания в RocketChat — по полному username.** Короткий логин
  (`@dkozlov`) в `mentions[]` не попадает: username в RocketChat хранится с
  доменом. Теперь:
  - `CONTACTS_LOGIN_RE` (он же `ROCKETCHAT_USERNAME_RE`) принимает обе формы —
    `login` и `login@domain`;
  - `start` резолвит `login → GET /api/v1/users.info?username=<login>` (таймаут
    5 с, без ретраев) и берёт `user.username`; результат кешируется в
    `catalog.yaml → rocketchat_users: {<login>: {username, user_id,
    resolved_at}}`, повторный прогон работает из кеша без сети;
  - логин с доменом (`rrozhkov@ecom.tech`) используется как есть, без резолва;
  - резолв не удался (нет токена/сети/404) — остаётся `@<login>` и WARN в
    `GENERATION.md` (§11 «Предупреждения рендера») и `validate`
    (`_check_mentions`);
  - `templates/actions/rocketchat-message.md` печатает `@dkozlov@ecom.tech`.
  Самопроверка: резолв с моком, кеш без сети, отказ с WARN, username с доменом.
- **`assigned_date`/`review_date` — от даты генерации, а не от `finalize`.**
  `assigned_date` = `generated_at` (`--date`), `review_date` = `generated_at` +
  `review_period_months`. Паспорт в MR уже содержит обе даты (publish их
  переносит), `finalize` идемпотентен и не сдвигает их; `--assigned-date` /
  `--review-date` остаются явным override с WARN при расхождении. WARN
  «assigned_date/review_date не заполнен» снят — поля заполняются всегда.
- **`approve_link` = ссылка на тред согласования.** `handoff` после успешной
  публикации пишет `approve_link` = `thread_link` (в реестр и, через рендер, в
  паспорт); `finalize` без `--approve-link` берёт `thread_link` **только при
  `handoff_status: published`**. При `failed` — `ERROR` с причиной из
  `handoff_error` и подсказкой повторить `make handoff IS=<код> SEND=auto` или
  задать `--approve-link` явно; при `mcp_requested`/пустом статусе — `ERROR` с
  той же подсказкой (тред не доказательство согласования). Подтверждение
  фиксируется **мержем MR** — отдельного ожидания ответа SRE нет; `next_step`
  после `handoff` ведёт на `make finalize IS=<код>` без условия «дождаться
  SRE». `approve_link_problem` принимает относительную ссылку
  `/link?rid=…&msg=…`.
- **Порядок источников дат в `finalize`.** Явный флаг → значение реестра →
  значение паспорта → `generated_at` → `today()`; последний шаг только когда
  `generated_at` в паспорте нет вообще, и сопровождается WARN (раньше
  безусловный `or today()` на входе делал fallback на `generated_at`
  недостижимым).
- **Чек-лист ревьюера и повторная оценка.** Пункт про дифф MR больше не требует
  «ровно два файла»: при первой публикации — паспорт и `_root.yaml`, при
  `publish --update` — только паспорт (это норма, сказано и в
  `PUBLISH_CHECKLIST_NOTE`, и в `docs/05-mapping.md`).
- **Шаблон реестра документирует `rocketchat_users`.** В `templates/catalog.yaml`
  появился закомментированный пример кеша резолва логинов (`username`,
  `user_id`, `resolved_at`) — поле уже принималось `validate`, но в шаблоне
  отсутствовало.
- **Комментарий про dry-run у упоминаний.** Приведён к коду: dry-run не
  резолвит логины (ранний возврат без `root`), в артефакте остаётся логин из
  SSoT, сеть не трогается и кеш не пополняется; резолв идёт только в реальном
  прогоне.
- `_publish_limitations` при отсутствии ограничений печатает явную строку:
  строгий рендер описания MR не допускает пустой список.

### Добавлено

- **Финальный шаг `handoff`: вопрос об отправке и два транспорта.** Раньше
  отправка треда в `#Criticality_assessment` была ручной. Теперь:
  - `handoff --is <код> [--send auto|manual] [--transport auto|mcp|api]
    [--force-resend] [--dry-run]` — сначала **спрашивает** («отправить
    автоматически?» `1` да / `2` вручную / `3` отменить); вне TTY без `--send`
    отказывает с подсказкой (дефолта нет). Предусловия: нет `⛔` в обязательных
    полях, `validate` без ERROR, `thread_link` пуст (идемпотентность;
    `--force-resend` — обход).
  - транспорт `mcp` (основной) — «запрос → результат»: пишется
    `is/<код>/.handoff-request.json`, код `0`, статус `mcp_requested`; результат
    принимает `handoff-result --message-url <url>` (пишет `thread_link`,
    `handoff_status: published`, `published_at`, удаляет файл запроса).
  - транспорт `api` (фолбэк) — `POST /api/v1/chat.postMessage` с
    `ROCKETCHAT_TOKEN` + `ROCKETCHAT_USER_ID`; таймаут 15 с, один повтор только
    на 5xx/таймаут; различаются `401`/`403`/`404`/`429`; токен не печатается.
  - цепочка `auto`: MCP → REST → ручной пакет (`failed` + `handoff_error`,
    пакет `pending_manual`); в выводе всегда назван сработавший транспорт.
  - `handoff-result --failed <причина>` — автоматический REST-фолбэк.
  - `catalog.yaml → systems.<код>`: новые поля `handoff_mode`, `handoff_status`,
    `thread_link`, `published_at`, `handoff_error` (+ схема `validate`).
  - `criteria.external_refs.rocketchat_base` — базовый адрес Rocket.Chat для
    REST и сборки ссылки на сообщение (env переопределяет).
  - самопроверка H1–H11 (mock REST, без сети): manual, mcp-запрос,
    handoff-result по ссылке, фолбэк на API, отказ без токена, идемпотентность,
    `⛔`, не-TTY, `--dry-run`, поиск MCP-сервера в JSONC-конфиге opencode.
- **Сбор кандидатов `research` + гейт заголовков `verify-titles` + единая
  проверка `verify`.** Три новые подкоманды и make-цели:
  - `research --is <код> [--input <вход>] [--all]` собирает доказательства в
    Confluence по `criteria.inputs.<вход>.queries` и маршрутам
    (`inputs.routes.e2e`, `inputs.optional.financial_loss`), оценивает
    `direct | indirect | none`, пишет `is/<код>/RESEARCH.md` и
    `is/<код>/CANDIDATES.yaml` (кандидаты только `direct`, с полями
    `evidence: direct` и `steps: N` — «сколько шагов процесса подтверждают»).
    Идемпотентен: ключ дедупликации — вход + `page_id` носителя, правки
    человека не затираются.
  - `verify-titles [--is <код>] [--fix]` сверяет заголовки страниц с REST:
    кеш `catalog.yaml → page_titles` (`title`, `title_version`,
    `title_verified_at`), а `--fix` приводит к фактическим и объявления в
    `criteria.external_refs.refs[]` / `criteria.meta.sources[]` (строчный
    splice — комментарии и порядок ключей файла критериев сохраняются).
  - `verify` — один прогон всех гейтов (`criteria-check`, `selftest`,
    `validate`, `docs-check`, `verify-titles`, `skill-check`) с итогом
    `ИТОГО: N гейтов, X ошибок, Y предупреждений`.
- **Кеш заголовков страниц как единственный источник названий (R19).** Рендер
  печатает название только из `catalog.yaml → page_titles`; нет записи —
  `[page <id>] <url>` без названия. Гейт `validate` проверяет наличие записи,
  `title_verified_at`, версию страницы и расхождение заголовка.
- **Маршруты `e2e` и `financial_loss` в документации критериев.** `docs/08-criteria.md`
  §15.1 — что искать, где (каталог процессов, реестры, финансовая модель,
  методология GMV) и ловушки (пустая колонка Product scope, пустой шаблон
  «Оценка ущерба», общесетевой GMV).
- **Автоподхват ссылки dochub-MR.** `publish --push` пишет
  `.dochub/<код>-MR.url` в проекте (симметрично `.ssot/<код>-MR.url` в клоне
  SSoT), `start` подставляет её в `actions.mr_link` / `actions.publish_mr_link`
  — ручное копирование ссылки в тред больше не нужно; нет файла — прежний
  `⛔ не заполнено`.
- **Сортировка кандидатов по силе доказательства.** `make ask` показывает
  кандидатов в порядке `direct` (с числом шагов) → `indirect` → прочее, внутри
  группы — по числу совпадений; лимит применяется после сортировки. В ASK.md и
  `ask --json` появилось поле «доказательство» (`evidence`,
  `evidence_label`, `steps`).
- **Отказ от данных (`waive`) и предварительная оценка (R17).** У вопроса
  человека появились четыре исхода вместо «взять кандидата / вписать значение»:
  `source_url` (ссылка на страницу или дерево страниц + дословная цитата,
  `extracted {value, quote}`; для Confluence провенанс
  `{type: confluence, ref: 'page_id=<id>; «<цитата>»'}`), `freeform`
  (произвольный текст с данными + обязательный `source`), `waive` (осознанный
  отказ: `reason` >= 10 символов + `fallback.mode` ∈
  `assume_worst | assume_best | assume_value`, у `assume_value` — `value`) и
  `deferred` (только advisory). `deferred` у blocking-входа больше не
  маскируется под отказ: отказ — это `status: waived` с блоком
  `waive {reason, decided_by, date, fallback}`, который едет из
  `ANSWERS.yaml` → `DATA-REQUIREMENTS.yaml` → `INFORMATION.yaml`. Гейт считает
  waived-вход закрытым (`waived_inputs`, `provisional: true`); расчёт перебирает
  домен допустимых значений (enum/бакеты/оси/CIA/целые пороги) и печатает
  **диапазон** уровней и режим допущения, а в паспорт идёт консервативный
  уровень (`assume_worst` → максимум, иначе минимум). `score_trace` получил
  `provisional`, `provisional_range`, `waived_inputs`, `assumptions`;
  `CRITICALITY.md` — блок «⚠ Оценка предварительная» сразу после frontmatter,
  `GENERATION.md` — строку «Предварительная оценка», публикация — строку о
  предварительности, `INDEX.md` — пометку `(предв.)` и легенду. Паспорт
  остаётся каноническим (новых ключей нет), статус артефакта — `draft`.
  Неперечислимый домен — `ERROR`, а не догадка. `ask --json` отдаёт `options`
  как `[{number, kind, text}]` в фиксированном порядке, `validate` проверяет
  `waive` и наличие пометки. Шаблоны `ANSWERS.yaml`, `DATA-REQUIREMENTS.yaml`/
  `.md`, `CRITICALITY.md`, `publication.md`; документация —
  `references/interactive.md`, `references/commands.md`, `references/rules.md`
  (R17), `SKILL.md` (инварианты 3–4); 38 новых проверок `make selftest`.
- **Ссылка на АДР с основанием вместо пустого `⛔` (CHANGE #2).** Публикация и
  action-пакет больше не теряют ссылку на архитектурный документ, когда АДР
  нет: цепочка `facts.adr` → `catalog.yaml → systems.<код>.architecture_page_id`
  → `confluence_page_id` → `None` подставляет архитектуру ИС, страницу ИС или
  явный маркер, а рядом печатается основание (`actions.adr_basis` ∈
  `adr | architecture | is_page | none`, `actions.adr_basis_note`). В
  `GENERATION.md` появилась строка «Ссылка на АДР (adr_basis)» — архитектура не
  выдаётся за АДР. `validate` предупреждает, когда вся цепочка пуста. Новое
  поле реестра `architecture_page_id` (глобальное и на уровне ИС), заполняется
  `prepare` из SSoT-ссылки, если пусто и ссылка найдена (существующее значение
  не перезаписывается, `WARN`, если ссылки в SSoT нет). Шаблоны
  `publication.md`, `actions/jira-task.md`, `actions/confluence-page.md`,
  `GENERATION.md`, `catalog.yaml`, `INFORMATION.yaml`; документация —
  `docs/10-templates.md` §3.5, `references/commands.md`.
- **E2E-процессы ИС из Product scope продукта (CHANGE #3).** Источник
  `facts.e2e_processes` определён явно: страница `catalog.yaml →
  product_scope_page_id`, её функциональные области с меткой `functional-area`,
  колонка «Код мастер-системы (опционально)» называет ИС, колонка «Сквозной
  бизнес-процесс (e2e)*» — процесс. `collect` печатает раздел «Product scope —
  процессы ИС» с CQL
  `label = "functional-area" and space = currentSpace() and ancestor = <page_id>`
  и порядком чтения **для каждой ИС**, включая закрытые входы расчёта; пустое
  поле — `WARN` и `⛔` с подсказкой, где взять `page_id`. Новые факты
  `e2e_status` (`filled | not_filled | not_found`) и `e2e_source_page`
  (`{page_id, title, url}`): пустая ячейка — `not_filled` со ссылкой на
  страницу, отсутствие ИС в областях — `not_found`, выдуманный процесс
  запрещён. `actions.e2e_list` отдаёт `название (источник: url)`, а пустой
  список — `actions.e2e_text` с точной причиной. Шаблоны `RESEARCH-PLAN.md`,
  `INFORMATION.yaml`, `catalog.yaml`; документация —
  `references/workflow.md` §2a, `docs/10-templates.md` §3.2/§3.5.
- **Протокол глубокого поиска: tier 1 → tier 2 (CHANGE #4).** Новый
  `references/search.md`: точные идентификаторы (tier 1) → комбинации значений
  (tier 2), фиксация в `CANDIDATES.yaml → search.<вход>`
  (`shallow`/`deep`/`done`/`result`), доказательство «не найдено» списком
  запросов, таблица «симптом → следующий запрос». `collect` печатает по
  каждому незакрытому входу готовые запросы tier 1/tier 2 из реальных кода,
  названия, продукта, команды, `page_id` и логинов `contacts` (без заглушек);
  `ask` печатает `WARN глубокий поиск не зафиксирован для <вход>` и ставит
  `deep_search_missing: true` в `--json` (поля `search`, `search_done`), а
  `validate` предупреждает по blocking-входу без значения, кандидатов и записи
  поиска. Шаблоны `CANDIDATES.yaml`, `RESEARCH-PLAN.md`; 22 новые проверки
  `make selftest`.
- **Контакты команды (TA/TL) из SSoT → упоминания в публикации.** Новая
  подкоманда `contacts --is <код> [--apply] [--json]` читает
  `ssot/entities/teams/<team>/team.yaml` (`groups[].name` — роль,
  `groups[].members[]` — логины) и пишет копию ростера в
  `INFORMATION.yaml → contacts`. `identity.ta`/`identity.tl` в публикации теперь
  рендерятся упоминаниями RocketChat (`@dkozlov`, `@ipilyaev`) вместо ФИО
  системного архитектора и `⛔ не заполнено`; `actions.jira.assignee_tl`/
  `assignee_pdm` получают логин (`groups.tl`, `groups.po` → `groups.dm`).
  Соответствия login → ФИО в SSoT нет — это задокументировано, печатается логин.
  `prepare` заполняет блок сам (команда в SSoT не найдена — `WARN`, не падение;
  прежние контакты сохраняются), `validate` предупреждает, если контакты не
  собраны или группа `ta`/`tl` пуста. `--json` — машинная форма (`is`, `team`,
  `source`, `groups`, `mentions`), WARN и ошибки в stderr. Новая make-цель
  `contacts` (`APPLY=1`, `JSON=1`), секция в `templates/INFORMATION.yaml`,
  документация — `references/commands.md`, `references/workflow.md`,
  `references/data-sources.md` §1.3, `docs/10-templates.md`; 32 новые проверки
  `make selftest`.
- **Языковой инвариант.** Скилл работает на русском языке и принимает ответы
  только на русском; `validate`/`enrich` предупреждают о прозе не на русском в
  свободных полях (R16). Инвариант №8 в `SKILL.md`, правило R16 в
  `references/rules.md`; проверка мягкая (`WARN`, не блокирует) и не трогает
  идентификаторы: URL, `page_id`, uid, PromQL, ключи Jira/MR, имена
  файлов/сервисов и enum внешних систем.
- **Интерактивный слой `ask`: готовый план вопросов человеку.** Новая подкоманда
  `ask --is <код> [--json] [--apply] [--answers <файл>] [--reason] [--scope]`
  собирает вопросы по тем же незакрытым входам, что `check` (blocking первыми),
  и раскрывает enum **дословно** — все значения `consumers_type`/
  `outage_impact`, а не «спросите владельца методики». Кандидаты идут с
  провенансом: `is/<код>/CANDIDATES.yaml` (`strong`) → §6
  `SERVICE-FINDINGS.md` («из кода», `weak`) → SSoT `base.yaml`/`links.yaml`
  (`weak`); кандидатов нет — печатается маршрут «где взять». `strong` без
  `source` понижается до `weak` с `WARN`: неподтверждённое не выдаётся за
  проверенное. `--json` отдаёт машинную форму (один элемент — один вопрос, ключи
  `input`/`title`/`role`/`method`/`type`/`allowed`/`candidates`/`options`), WARN
  уходят в stderr. `--answers` принимает ответы (`candidate` наследует `source`,
  `manual` требует явный, `deferred` не заполняет, `exclude` требует `--reason`)
  и пишет **только** в `DATA-REQUIREMENTS.yaml`; `INFORMATION.yaml` остаётся
  байт в байт — его пишет `enrich-apply`. Новые шаблоны `ASK.md`,
  `CANDIDATES.yaml`, `ANSWERS.yaml`, протокол опроса —
  `references/interactive.md`, фаза 2d — `references/workflow.md`, make-цели
  `ask`/`ask-apply`/`ask-answers`, подсказка `next_step` ведёт в `ask` до
  `enrich`.
- **`finalize` — подтверждение SRE одной командой.** Новая подкоманда и
  make-цель: `approve_link` (обязателен, домен — из
  `criteria.external_refs.approve_link_domains`), `assigned_date` (сегодня,
  если в реестре пусто), `review_date` (сегодня + `staleness.review_period_months`;
  периода нет — пусто + WARN), `criticality` (из паспорта), `criticality_ssot`
  (из SSoT severity; расхождение — ERROR с обоими значениями), `status:
  confirmed`. Затем автоматически `start-apply FORCE=1` → `validate` → `index`
  → `verify`; ERROR в любом шаге — откат записанных полей и артефактов ИС
  (атомарность). `--dry-run` — план без записи. Документация —
  `references/commands.md`, `docs/09-pipeline.md`, `SKILL.md`.
- **Свободное поле публикации `publication.extra_info`.** Необязательный текст
  строки «Дополнительная информация по оценке» в `INFORMATION.yaml` (ручная
  секция, переживает `prepare`). Пусто — буллета в публикации нет, `⛔` не
  появляется; заполнено — буллет с текстом. Обязательные поля публикации,
  которые блокируют отправку: TA, MR паспорта (dochub), ссылка на SSOT;
  остальные опциональны.

### Исправлено

- **`handoff-apply` — не второй путь отправки.** У команды была своя логика
  отправки (легаси REST-клиент) и свой дедуп по хешу текста в
  `actions/rocketchat-message.md`; `catalog.yaml → handoff_status` она не
  смотрела, поэтому после `handoff` (`published`) `make handoff-apply
  CONFIRM=1` отправлял второе сообщение в канал. Теперь это тонкая обёртка:
  общие `_handoff_preflight` → `_handoff_api_publish` (дедупликация поиском
  своего сообщения в канале по `roomId`) → `_handoff_api_send` /
  `_handoff_publish_success`; идемпотентность общая (`published` +
  `thread_link` → отказ, `--force-resend` — осознанный повтор), результат
  пишется только в поля реестра. Файл-дайджест и секция «Отправлено» удалены.
- **`make finalize` не существовал.** `next_step` и подсказки скрипта звали
  `make finalize IS=<код>`, а цели в `project/Makefile` не было — make отвечал
  «Нет правила для сборки цели «finalize»». Цель добавлена, пробрасывает
  `APPROVE_LINK`, `DRY_RUN`, `ASSIGNED_DATE`, `REVIEW_DATE`.
- **`unit` из листа игнорировался.** `_sheet_input_problems` звал
  `_normalize_requirement` без `unit`, поэтому `unit: сек` при дефолте `мин`
  проходил молча (240 «секунд» уезжали в расчёт как 240 минут). Теперь `unit`
  проверяется `_requirement_unit_problem` и в листовом пути (`enrich`,
  `ask-answers`), и в ответах, как в `sources-apply`.
- **`--allow-incomplete`/`--write` не пробрасывались make-целью `handoff`.**
  Флаги были у подкоманды, но `make handoff ... ALLOW_INCOMPLETE=1 WRITE=1` их
  терял. Добавлены в рецепт.
- **`handoff` отправлял испорченный текст сообщения.** `cmd_handoff` и
  `handoff-result --failed` читали `INFORMATION.yaml` через
  `_load_info_file(folder / INFORMATION_FILE)`, а функция сама дописывает имя
  файла: путь получался `<папка>/INFORMATION.yaml/INFORMATION.yaml`, данные
  молча становились пустыми, гейт — `BLOCKED`, и в тред уходил текст со `⛔` в
  TL / старой / новой критичности / E2E / GMV, а подпись ТА подменялась ФИО из
  `catalog.yaml`. Теперь передаётся папка. Плюс `_publication_text_for_is`
  грузит кеш заголовков (`page_title_cache`), иначе названия страниц в
  отправляемом тексте превращались в `[page <id>]` и расходились с
  просмотренным action-пакетом.
- **Публикация навсегда заблокирована `⛔` в «Дополнительная информация по
  оценке».** Поле `actions.extra_info` было захардкожено `None`: текст всегда
  содержал `⛔ не заполнено`, гейт `_publication_missing_fields` считал это
  блокером, и этап `handoff` был недостижим. Теперь значение читается из
  `INFORMATION.yaml → publication.extra_info`, пустое опциональное поле не
  рендерится и не блокирует; гейт различает обязательные и опциональные поля.
- **Неверный текст WARN `catalog.criticality`.** Было «заполняется на этапе
  ssot» (ssot пишет только `ssot_status`); стало «заполняется командой
  `make finalize` после подтверждения SRE и мержа MR».
- **Выдуманные заголовки страниц.** `verify-titles --fix` больше не оставляет
  расхождений в источниках объявлений: заголовки в `criteria.external_refs.refs`
  и `criteria.meta.sources` приводятся к фактическим (было 7 «устаревших в
  источнике» при нулевых расхождениях кеша). Рендер названий — только из кеша
  (R19).
- **Шум в проверке `git_repository`.** `validate` предупреждал о каждом
  `https://host/path` без `.git` (10 ложных WARN на `opercrm.smkt`): такой URL
  клонируется, `.git` добавляет git. WARN остаётся только у настоящих дефектов:
  веб-путь (`/tree/`, `/blob/`, `/-/tree/`, `/-/blob/`, `/commits/`), хвостовой
  `/`, параметр/якорь (`?`, `#`). Стало 1 WARN вместо 11.
- **UX команд без `--is`.** `ask`/`research`/`verify-titles` без `--is`
  работают по всем ИС реестра (вместо ошибки «укажите IS=»), `--json` и
  `--answers` по-прежнему требуют одну ИС и печатают это внятной причиной.
- **Публикация и артефакты: факт-или-null, человекочитаемые ссылки, фингерпринт
  критериев.** Содержательные дефекты по итогам двух ревью прогона
  `opercrm.smkt`:
  - **Старая критичность больше не подменяется новым уровнем.** Публикация
    печатает `severity.type` из SSoT в исходном виде плюс `severity.addon` в
    доп. критериях (`business-critical (доп. критерии: CONTACT)`); fallback —
    `catalog.yaml → criticality`, затем `⛔ не заполнено`. Раньше при пустом
    реестре подставлялся расчёт, и отсутствие данных выглядело как факт. Та же
    логика в `CRITICALITY.md` (строка `extra_criteria` с источником SSoT).
  - **Ссылка на действующий процесс D6.1.1 в публикации.** Буллет
    `* Ссылка на процесс D6.1.1 — «<title>» [<page_id>] <url> (действующий,
    v<version>)` рендерится из `criteria.meta.sources` → `role:
    process_current`; источника нет — буллета нет (а не `⛔`).
  - **Ссылка на карточку ИС в SSoT.** `actions.ssot_card_link` собирается из
    нового шаблона `criteria.external_refs.ssot_card_base`
    (`https://ssot.ecom.tech/information-systems/{code}` — формат дословно из
    чек-листа `templates/publication.md`), а не остаётся `None`.
  - **Раздел 3 (GMV).** `actions.gmv_impact` собирается из
    `criteria_inputs.financial_loss`; данных нет — `⛔ не заполнено` плюс
    маршрут: `criteria.inputs.financial_loss.where`, ссылка на канон входов и
    `DATA-REQUIREMENTS.md`.
  - **Голых `pageId=` в публикации больше нет.** Ссылки печатаются как
    `«<title>» [<page_id>] <url>` (правило `confluence-links`): Product scope
    (E2E), архитектура ИС (новое поле реестра
    `systems.<код>.architecture_page_title`), процесс, канон входов.
  - **Фингерпринт критериев.** `start` пишет sha256-12 от влияющих на артефакты
    секций критериев в `CRITICALITY.md` (frontmatter) и `GENERATION.md` (§1);
    `validate` предупреждает о расхождении (и об артефактах без поля),
    `start DIFF=1` показывает смену отдельной строкой. mtime критериев не
    используется — иначе артефакты были бы вечно устаревшими.
  - **Мелочи артефактов.** Одна пустая строка после frontmatter (было две);
    `page N` в таблицах провенанса — markdown-ссылка через `base_url`; правило
    с `source_status: archived_carrier` получает сноску `†` со своим
    `source_note`.
  Обновлены `docs/10-templates.md`, `templates/catalog.yaml`, 17 новых проверок
  `make selftest`.
- **Предварительная оценка (R17): 15 дефектов по итогам кросс-модельного
  ревью.** Диапазон уровней больше не занижается, а артефакты не расходятся с
  `INFORMATION.yaml`:
  - **Домен нагрузки включал не все точки смены балла.** Перебирались только
    пороги и границы интервалов; матрица баллов не монотонна по номеру
    интервала, поэтому максимум терялся. Пример из боевых критериев:
    `object_sla=60`, `c·i=0.1`, `load=200000` → `t=210` → балл 4 →
    **Mission critical**, а на пороге `load=50000` (`t=660`) — балл 3 →
    Business critical; `assume_worst` сообщал BC. В домен добавлены оба предела
    (`load=1` и `load→+∞`, сентинел `10^9`) — теперь диапазон включает
    `Mission critical`.
  - **Составные домены перечислялись по углам** (`axes_scores` — all-0/all-4,
    `cia` — all-low/all-high), что опиралось на недоказанную монотонность.
    Теперь перебираются полностью: 5⁴ = 625 и 3³ = 27 наборов.
  - **Waived-вход наследовал значение прежнего паспорта** (`object_sla: 240` из
    старого `criticality-passport.yaml` подставлялся как `legacy`). Теперь
    `status: waived` → `null`/`⛔`, без падения в legacy/existing.
  - **`decided_by`/`date` конкретного входа терялись** — читались только из
    файла/блока `ANSWERS.yaml`. Теперь приоритет: поле входа → файл → дефолт.
  - **Ложный провенанс `confluence`.** `pageId=` в чужом редиректе
    (`https://evil.example/redirect?pageId=…`) выдавался за проверенную
    страницу. Тип `confluence` теперь только для хоста
    `criteria.external_refs.base_url` (по умолчанию `space.samokat.ru`), иначе
    `manual` с полным URL; креды `user:pass@` из URL вырезаются.
  - **Markdown-инъекция в таблицы.** Цитата (`extracted.quote`) и
    `waive.reason` попадали в ячейку как есть: `|`/перевод строки ломали
    таблицу `CRITICALITY.md`/`GENERATION.md`. Добавлен фильтр шаблонов
    `| md_cell` (экранирует `|`, схлопывает переводы строк).
  - **Цитата `freeform` терялась** — `source.ref` писался без неё. Теперь
    дописывается `'<ref>; «<цитата>»'`.
  - **`search` игнорировал `is:`** — `search.done: true`, скопированный из
    другой ИС, глушил WARN о незафиксированном tier 2. Теперь `is:`/
    `schema_version` проверяются так же, как у кандидатов (WARN, записи
    отбрасываются).
  - **`validate` и `ask` расходились по tier 2**: `validate` снимал WARN при
    любой записи `search.<вход>`, даже `done: false`. Теперь оба используют
    предикат `done: true` (`_search_covers`).
  - **Битые `facts.adr` молча давали `adr_basis: architecture`.** Теперь
    `start` и `validate` печатают WARN «в facts.adr есть записи, но ни у одной
    нет ссылки…».
  - **`validate` не проверял `facts.e2e_status`**: неизвестное значение молча
    нормализовалось, отсутствие статуса и `filled` с пустым `e2e_processes` не
    ловились. Добавлены три WARN; нормализация сохранена.
  - **Устаревшая пометка `(предв.)`.** Добавлена зеркальная проверка (пометка
    есть, а waived-входов нет → ERROR) и сверка уровня паспорта с текущей
    предварительной оценкой (расхождение → ERROR с обоими значениями).
  - **`value` вместе с `status: waived`** больше не принимается (ERROR): вход
    не может быть одновременно готовым и отказом.
  - **Вырожденный диапазон** (`min == max`) теперь сопровождается пояснением
    «вход не влияет на уровень выбранного метода» в `score` и `CRITICALITY.md`.
  - **Исключённые ИС** пропускаются проверкой `_check_waived_inputs` — их
    устаревшие артефакты не поднимают ERROR (как в `enrich`/`start`).
  Документация: `references/rules.md` (R17), `references/interactive.md`,
  `references/search.md`; +31 проверка `make selftest` (1245).
- **`contacts`: allowlist логинов — мусор из `team.yaml` не ломает ни YAML, ни
  публикацию.** Раньше `_clean_logins` принимал любую непустую строку: логин
  `x] @here` рвал inline-список (`ta: [x] @here]`), а `a\n* TL - @all`
  подставлялся в текст сообщения RocketChat как есть — с переводом строки,
  буллетом и пингом канала. Теперь логин обязан совпадать с
  `[a-z0-9][a-z0-9._-]{0,31}` (после `strip`/lower), иначе он отбрасывается:
  `make contacts` печатает
  `WARN  в team.yaml пропущены некорректные логины: <…>`, а в блок
  `INFORMATION.yaml → contacts` значение не попадает. Фильтр стоит в
  `_clean_logins`, то есть действует и на `prepare`, и на `_contacts_yaml_block`,
  и на путь рендера — одной точки достаточно.
- **`contacts`: логины `all`/`here`/`channel` больше не пингуют канал.**
  `@all`/`@here` — служебные адресаты RocketChat, поэтому `_mentions` их
  пропускает с `WARN  логин <x> совпадает с зарезервированным упоминанием
  RocketChat — упоминание не добавлено`. Логин остаётся обычным участником
  `contacts.groups` (это факт SSoT) — подавляется только упоминание.
- **`prepare`: блок `contacts` проходит обратную проверку до записи.** Раньше
  проверка (`parse_yaml` + round-trip групп) была только в
  `_write_contacts_section`, а `prepare` вставлял блок в текст и писал без неё:
  битый блок делал `INFORMATION.yaml` неразбираемым, следующий `prepare`
  получал `existing = None`, и `splice_manual_sections` терял
  `criteria_inputs`/`facts`. Теперь общая проверка
  `_contacts_roundtrip_problem` стоит в обоих путях; при расхождении печатается
  `ERROR: блок contacts не прошёл обратную проверку — файл не записан`, запись
  пропускается (без fallback «писать без contacts»), код возврата `1`.
- **`start --force`: перезапись идентичного файла снимает ложный
  `passport_stale`.** `_start_one` пропускал `_atomic_write`, когда
  отрендеренный текст совпадал с диском, поэтому mtime не рос, а
  `collect_state` считает паспорт устаревшим по `info_mtime > passport_mtime`:
  подсказка `make start-apply … FORCE=1` не могла погасить состояние (типичный
  случай — `make contacts --apply` меняет `INFORMATION.yaml`, но не текст
  паспорта). Теперь при `--force` (и не в dry-run) файл перезаписывается даже
  идентичными байтами — `_atomic_write` обновляет mtime. Определение
  staleness не менялось.
- **`validate`: WARN о контактах больше не вводит в заблуждение.** Пустой блок
  (`contacts: {team: null, source: {type: null, ref: null}, groups: {}}`) —
  truthy-словарь, поэтому `if not contacts` не срабатывал и вместо «не собраны»
  печатались два WARN «группа ta/tl пуста». Условие заменено на
  `not _contacts_groups(contacts) and not contacts.get("team")`; текст WARN о
  пустой группе теперь честно указывает на локальную копию:
  `группа <name> пуста в contacts — обновите: make contacts IS=<код> APPLY=1`
  (раньше он утверждал «пуста в team.yaml»).
- **`contacts`: мелкие фиксы.** Код команды проверяется как слаг
  (`[a-z0-9][a-z0-9._-]*`) — `team: "../x"` даёт `некорректный код команды
  '../x'` вместо чтения файла вне `ssot/entities/teams/`; чтение/запись
  `INFORMATION.yaml` в `cmd_contacts` обёрнуты в `except (OSError,
  UnicodeDecodeError)` → `ERROR: <путь> не прочитан/не записан: <exc>` вместо
  сырого traceback; `prepare` предупреждает, что ключи сохранённых `contacts`
  вне `team/source/groups` не переносятся. 45 новых проверок `make selftest`
  (allowlist, `@all`, обратная проверка `prepare`, снятие `passport_stale`,
  оба WARN-условия, код команды).
- **`ask-answers`: значения составных входов (`axes_scores`, `cia`) не
  записывались в лист — исправлено; добавлена пост-проверка записи.** При приёме
  ответов в блок листа писалось `merged_block["value"] = entry["value"]`, но у
  составных входов `_normalize_requirement` держит под-оси в верхнем уровне
  записи (форма `INFORMATION.yaml.criteria_inputs`), а не под `value:` — в
  `DATA-REQUIREMENTS.yaml` уходил `value: null` при живых под-осях. Команда
  печатала «Принято: … (7)», а следующий `enrich` принимал только 5 входов и
  держал ИС в `BLOCKED`: человеку приходилось править лист руками. Теперь
  значение для листа строит `_requirement_block_value` (под-оси — под `value:`),
  а после записи лист перечитывается и каждый принятый вход проверяется общим с
  `enrich` валидатором `_sheet_input_problems`. Не легло — `ERROR: вход <имя>
  принят, но значение не записано — это дефект инструмента`, код `1`, лист
  возвращается в состояние до записи, «Принято» не печатается. Проверка
  `enrich` переведена на тот же валидатор, чтобы пути приёма не расходились.
  Самопроверка: под-оси в листе, `enrich` dry-run принимает 7/7, инъекция
  старого дефекта даёт код `1` и откат.
- **`ask`: `value: null` в `CANDIDATES.yaml` больше не пропуск, а
  кандидат-основание.** `_ask_candidate_blocks` выбрасывал такого кандидата с
  `WARN «пропущен (нет значения)»`, хотя смысл файла — фиксировать и
  **основание без значения** («RTO — часы, но числового SLA нет»); шаблон
  `CANDIDATES.yaml` при этом сам содержал `axes_scores: {legal: null, …}` и
  ругался на своей же копии. Теперь `value: null` — законная форма: кандидат
  виден в плане и в опции «Взять кандидат N как основание — значение вписать
  вручную», `_ask_value_problem` для него не вызывается, а
  `confidence: strong` понижается до `weak` (`WARN`: основание сильным не
  бывает). `choice: candidate` по такому кандидату отклоняется с текстом
  «не содержит значения (основание)» — формулировка покрывает и цитату из
  кода, и запись в `CANDIDATES.yaml`. Шаблон переведён на `value: null`,
  правила формы дополнены.
- **`ask`: привязка `ANSWERS.yaml`/`CANDIDATES.yaml` к ИС.** Ни один файл не
  нёс код ИС, а имена входов у всех ИС одинаковы — `make ask-answers
  IS=<одна> ANSWERS=is/<другая>/ANSWERS.yaml` молча применял ответы к чужой
  ИС с кодом `0`. Добавлено поле `is:`: у ответов чужой код — `ERROR`
  «ANSWERS.yaml принадлежит ИС '<x>', а запрошена '<y>'», код `2`, ничего не
  пишется; у кандидатов — `WARN` и пропуск чтения (план строится без них).
  В шаблон `ANSWERS.yaml` добавлено `is: <код>`.
- **`ask --json`: ранние ошибки больше не ломают JSON в stdout.** Неизвестная
  ИС, пустой `is.yaml`, ошибка критериев/каталога, отсутствующий файл ответов
  (и отсутствующая папка/`INFORMATION.yaml`) печатали `ERROR` в stdout —
  потребитель получал не JSON. Теперь при `--json` эти сообщения уходят в
  `stderr`; в `--help` отмечено, что `--json` влияет только на план (с
  `--answers` вывод текстовый).
- **`ask`: `status` убран из `ANSWERS.yaml`** — поле было декоративным:
  `_ask_apply_answers` всегда пишет `confirmed` сам. В шаблоне вместо поля —
  комментарий, что `status` проставляется автоматически.
- **`ask`: нечитаемый файл ответов/кандидатов — чистый `ERROR`, без
  трейсбека.** `load_yaml` разворачивал только ошибки разбора, а
  `UnicodeDecodeError`/`IsADirectoryError` вылетали наверх. Оба обработчика
  ловят `(YamlError, OSError, UnicodeDecodeError)`.
- **`ask`: `excluded.reason` вместе с ответами — отказ до записи.** Один файл
  не может одновременно исключить ИС и принять значения: `ERROR: нельзя
  одновременно исключить ИС и принять ответы — разделите на два прогона`,
  код `2`.
- **`slo_configs_found` больше не считает инфраструктуру SLO-конфигом.**
  `_service_configs` проверял только существование файлов из
  `SERVICE_CONFIG_FILES`, включая `.gitlab-ci.yml`, — счётчик показывал 9 при
  нуле SLO. Теперь SLO-конфиг — только `slo-kit.yaml`, `slo.yaml`, `alerts.yaml`,
  `sloth.yaml` (`SLO_CONFIG_FILES`, `_slo_configs`), а `Chart.yaml`,
  `values*.yaml`, `deploy/` и `.gitlab-ci.yml` остаются в сообщении §7 «нет
  SLO/SLA-конфигурации». На `opercrm.smkt`: `slo_configs_found` 9 → 0.
- **§4 «Нормативы» больше не собирает упоминания аббревиатур.** `SLA`/`SLO`/
  `RTO`/`RPO` считаются нормативом только вместе с числом и единицей измерения
  (`SLA_UNIT`: `%`, `мин`, `мс`, `ч`, `час`, `дн`) в той же строке, и только вне
  строковых литералов (`SERVICE_QUOTED_RE`): заголовки задач JIRA, имена
  GraphQL-enum, подписи i18n и `alias: "297"` в причинах компенсации отсекаются.
  Каталоги `__generated__`, `locales`, `i18n` не сканируются. На `opercrm.smkt`:
  строк §4 22 → 0.
- **`downtime`/`outage` ищутся по границам слова** (`DOWNTIME_EN`, `OUTAGE_EN`):
  `gracefulShutdownTimeout: 10000` содержит `downtime` внутри
  (`shut` + `downtime` + `out`) и больше не выдаётся за описание влияния простоя
  — ни в §4, ни в основании `outage_impact`/`time_to_impact`.
- **`object_sla` требует минуты простоя, а не любую цифру.** Вместо
  `_DIGIT_IN_TEXT` (любая цифра — годился `E001-29572` и `alias: "297"`)
  основанием становится только цитата, проходящая ту же проверку, что
  `_sla_usability`: минуты рядом со словом «простой». На `opercrm.smkt`: строк §6
  11 → 4, оснований `object_sla` — 0.
- **RESEARCH-PLAN не молчит о пустых `page_id` в `catalog.yaml`.** Для
  незаполненных `dr_page_id`, `criticality_source_page_id` и
  `decision_log_page_id` план печатает по строке `⛔` (`_missing_catalog_pages`):
  таблица входов адресует `outage_impact`/`object_sla`/`time_to_impact` на
  DR-страницу, и без `page_id` поиск идёт только по дереву от страницы ИС.
- **`make init` создаёт `.gitignore`** (идемпотентно: существующий файл только
  дополняется отсутствующими записями, вывод — `создан` / `дополнен (N записей)`).
  `prepare-apply` клонирует `ssot/` (~40 МБ) и `apps/` прямо в корень проекта;
  без `.gitignore` `git add -A` закоммитил бы чужой код. Записи: `/ssot/`,
  `/apps/`, `/dochub/`, `is/*/*.bak-*` + артефакты атомарной записи
  (`*.new`, `*.broken`, `*.tmp`, `*.bak*`).
- **`_git_repository_problem()` распознаёт веб-страницу репозитория**: URL с
  `/tree/`, `/blob/`, `/commits/`, `/-/tree/`, `/-/blob/` в пути (например
  `https://github.com/bitnami/containers/tree/main/bitnami/redis`) — это не URL
  для `git clone` (такой clone падал с кодом 128). Теперь это `action: web_ui`
  с понятным сообщением и подсказкой URL клона; в `prepare` — WARN, прогон не
  прерывается (в отличие от недопустимой схемы, которая остаётся блокирующей).
- **Провенанс и маршруты критериев: расхождения с первоисточниками.** Гейт
  ссылался на 4553977278, где формулировок гейта нет — теперь 4566730084
  (`source_quote`). `inputs` ссылался на страницу процесса вместо канона входов
  (4567543163). `meta.sources` не знал канон-страниц методики, входов и
  провенанса и действующего процесса, а архивная 4207454433 подавалась как
  обычный источник — теперь `source_status: archived`. `PROVENANCE_TYPES` и
  `provenance.types` расширены с 8 до 10 значений (добавлены `attachment`,
  `ssot_links`). Заголовки публикации, реестра ответственных и артефакта
  экспресса приведены к реальным; реестр ответственных описан как журнал заявок
  на оргизменения, а не ростер. Списки enum (7 типов клиентов, 6 влияний)
  помечены `source_defect: true`: на 4552328348 они неполны и задублированы,
  канон — xlsx-калькулятор. `_criteria_source` больше не зависит от слова
  «экспресс» в заголовке: сначала ищет по `role`.

### Изменено

- **`next_step` на этапе handoff спрашивает об отправке.** Подсказка вместо
  «тред в #Criticality_assessment» ведёт в `make handoff IS=<код> SEND=auto`
  и прямо формулирует вопрос «отправить автоматически? | оставить вручную».
- **`finalize` подсказывает `ссылка на тред: <thread_link>`.** `thread_link`
  (наше сообщение) и `approve_link` (подтверждение SRE) остаются раздельными:
  `finalize` принимает только `--approve-link`.
- **Fallback ТА в публикации — `tech_architect`, затем `sa`.** Как и обещает
  `templates/catalog.yaml`: без `contacts.groups.ta` и `tech_architect` подпись
  больше не превращается в `⛔`, если в реестре есть `sa`.
- **Ссылка на задачу Jira и статус SSoT в публикации.** `templates/publication.md`
  и `actions/rocketchat-message.md` больше не печатают `⛔` там, где факт
  известен:
  - ключ задачи (`catalog.yaml → jira_task` / `is.yaml → task`) превращается в
    ссылку по шаблону `criteria.external_refs.jira_base` (`{key}` →
    `https://jira.samokat.ru/browse/<key>`); нет ключа — прежний `⛔`;
  - `make ssot` сам выставляет `catalog.yaml → systems.<код>.ssot_status`
    (`no_change` — severity уже совпадает, `mr_pending` — коммит без пуша,
    `mr_created` — MR создан); при `no_change` в треде печатается
    «не требуется: severity уже соответствует (…)», и гейт отправки считает это
    поле заполненным, а не блокером (`_publication_missing_fields`).
  Шаблоны `publication.md`, `actions/rocketchat-message.md`, `catalog.yaml`;
  критерии — `external_refs.jira_base`; документация — `docs/08-criteria.md`,
  `docs/09-pipeline.md`, `docs/10-templates.md`, `references/commands.md`;
  самопроверка — 4 новых проверки `make selftest`.

- **ADR-фолбэк на журнал решений удалён.** В первой редакции CHANGE #2
  рассматривался фолбэк `facts.decision_log` → `actions.adr_link`, но у
  `decision_log` нет слота в enum `adr | architecture | is_page | none`:
  подставлять журнал решений за АДР значило бы выдать один документ за другой.
  Цепочка осталась строгой (`facts.adr` → архитектура ИС → страница ИС →
  `None`), а журнал решений используется только как маршрут глубокого поиска
  (`references/search.md`). `architecture_page_id` при этом закрывает
  практическую дыру: у большинства ИС АДР нет, а страница архитектуры есть.
- **`catalog.yaml`: новые поля `architecture_page_id` и
  `product_scope_page_id`** — оба на верхнем уровне реестра и на уровне ИС
  (`systems.<код>.*`); на уровне ИС переопределяют глобальное значение.
  `validate` проверяет `page_id` (`ERROR` на значение, не являющееся целым
  числом > 0), порядок полей в реестре зафиксирован (`CATALOG_FIELD_ORDER`),
  комментарии шаблона и проекта синхронизированы.
- **`prepare` пишет `architecture_page_id` в `catalog.yaml`**, если поле пусто
  и в SSoT-карточке есть ссылка на архитектуру: вставка идёт построчно
  (`_set_catalog_entry_field`), комментарии и форматирование сохраняются,
  непустое значение не перезаписывается.
- **`collect` печатает Product scope и глубокий поиск для каждой ИС**, включая
  ветку «недостающих входов нет»: E2E-процессы нужны публикации независимо от
  гейта расчёта. Счётчик шагов получил поля `product_scope` и `deep`.
- **`INFORMATION.yaml → facts`**: `e2e_processes` принимает и строки (legacy), и
  словари `{name, impact, status, source}`; добавлены `e2e_status` и
  `e2e_source_page`. `facts_block` нормализует обе формы, поэтому старые файлы
  читаются без миграции.
- **Синхронизация критериев с первоисточниками (2026-11-18).** Числа расчёта не
  менялись; обновлены провенанс, состав источников и маршруты к данным:
  - `meta.sources` — 9 записей с `space`, `version`, `updated`, `role`,
    `source_status`; добавлены канон-страницы 4566730084 (методика), 4567543163
    (входы), 4567212024 (провенанс) и действующий процесс 3855374712.
    4207454433 помечен `source_status: archived` (архив «Архив (мусор)» —
    единственный носитель 20/16 ячеек матриц, шкал осей и описаний CIA).
    `meta.synced_at` фиксирует дату сверки, блок `meta.canon` — где что лежит.
  - `provenance` — `kind: documented`, `page_id: 4567212024`, **10** типов в
    порядке канона (`attachment`, `ssot_links` добавлены) с описаниями; новый
    узел `provenance.manual_decision`: решение владельца без цитаты — `manual`
    с ref на решение, без ссылки — `missing`.
  - `inputs.page_id → 4567543163`; `inputs.gate.page_id → 4566730084` +
    `source_quote`; у `axes_scores`/`time_to_impact`/`cia` —
    `switches_scenario: true`; у каждого входа `source_page_id`, а `where`
    дополнен маршрутами: Grafana-ловушка 5-минутки, Product scope, DRP-план,
    TIER-фреймворк 4433941403 (с оговоркой «TIER ≠ критичность 1:1»),
    ИБ-методика 4566723467 (5 классов ≠ low/medium/high; «УЗ-N» — ошибка),
    пороги финансовых потерь.
  - `enum_selection`: оба enum помечены `source_defect: true` (на 4552328348
    список неполон/задублирован), канон значений — xlsx-калькулятор;
    `source_artifact` добавлен к обоим.
  - `levels.dochub_extra_level`/`dochub_to_ssot`, `cia.thresholds`/
    `protection_levels`/`boundary_convention`, `express_method`,
    `final_matrix`, `scenarios.selection` — `source_page_id: 4566730084`;
    `cia.descriptions`/`weights` остались на 4207454433 с пометкой архива.
  - `external_refs`: исправлены реальные заголовки публикации и реестра
    ответственных (журнал заявок, не ростер), добавлены 13 ссылок (методика,
    входы, провенанс, процесс и его черновик, TIER, реестры ИС/ММ, шаблон DRP,
    классы защищённости, ИБ-методика, пилот, требования).
  - Код: `_criteria_source` ищет сначала по `role`, затем по заголовку
    (обратная совместимость); `PROVENANCE_TYPES` — 10 значений; новые проверки
    `criteria check` (10 типов, полнота `meta.sources`, `where`/`source_page_id`
    у входов, `switches_scenario`, архивный источник без пометки); `validate`
    печатает WARN на архивную ссылку без `source_status: archived`;
    `docs-check` проверяет `references/data-sources.md` (канон маршрутов + все
    `page_id` из критериев). +19 проверок `make selftest`.
  - Документация: `docs/08-criteria.md` (таблица источников с версиями и
    статусами, 10 типов провенанса, 38 правил), `docs/09-pipeline.md` §4.2,
    `docs/05-mapping.md`, `docs/10-templates.md` (расширения публикации),
    `references/data-sources.md` §1 (канон маршрутов, новые источники).

## [1.0.0] — 2026-11-13

Первая версия компонента: скилл перенесён из проекта паспортов критичности
(`.opencode/skills/criticality-gen`) и приведён к конвенции репозитория.

### Добавлено

- **22 подкоманды** `scripts/criticality.py` — `help`, `info`, `init`,
  `prepare`, `validate`, `index`, `due`, `scaffold`, `reassess`, `show`,
  `score`, `criteria`, `check`, `requirements`, `enrich`, `collect`,
  `services`, `exclude`, `include`, `start`, `publish`, `ssot`; запись в файлы
  — только по `--apply` (у `start` — `--force`), после каждой команды
  печатается конкретный следующий шаг (`next_step()`), отключается
  `--no-next` / `--quiet`.
- **Два сценария оценки** (`простой` / `сложный`) с гейтом по blocking-входам:
  неполный сложный набор — `BLOCKED` без фолбэка на простой; вердикты гейта
  `OK` / `BLOCKED` / `SKIPPED` / `CONFLICT`.
- **Провенанс значений** `{type, ref}` (`ssot`, `is_yaml_override`, `catalog`,
  `confluence`, `gitlab`, `jira`, `grafana`, `manual`); значение без источника —
  `null` + `status: missing`, а не догадка.
- **`DATA-REQUIREMENTS.md` / `.yaml`** — лист недостающих данных «что это →
  зачем → где взять → у кого → как подтвердить»; заполненные значения человек
  вписывает в `.yaml`, `enrich` переносит их в `INFORMATION.yaml` только с
  `source` и `status: confirmed`.
- **`RESEARCH-PLAN.md`** (`collect`) и **`SERVICE-FINDINGS.md`** (`services`) —
  маршрут сбора (страницы Confluence, дашборды и запросы Grafana) и цитаты
  «файл:строка» из `docs/` и `openspec/` клонов сервисов.
- **`publish` в dochub** — паспорт в формате dochub, импорт в `_root.yaml`,
  ветка `feature/<task>` и коммит из двух файлов; уровень переводится в enum
  dochub по `levels.publish_enum` критериев.
- **`ssot`** — точечное обогащение карточки ИС: только блок `severity`
  (`type` из `levels.ssot_enum`, `confirmation` из `approve_link`), остальные
  ключи и форматирование сохраняются побайтово.
- **`handoff`** — этап передачи человеку: тред в `#Criticality_assessment` со
  ссылками на dochub-MR и SSoT-MR (текст — `templates/actions/rocketchat-message.md`).
- **Строгие MR-шаблоны** `templates/MR-dochub.md` и `templates/MR-ssot.md`:
  незаполненная переменная — ошибка, а не пустая строка в MR.
- **1008 самопроверок** — `make selftest` (`criteria check` + `score --selftest`)
  на golden-векторах `scripts/fixtures/express-golden-vectors.csv`.
- **`install.sh`** — глобальная установка в `~/.config/opencode` (скилл +
  команда `/criticality_gen`), режим `--project <каталог>` для развёртывания
  проекта (`Makefile`, `.opencode/Makefile`, `is.example.yaml`), `--dry-run`,
  `--uninstall`, `--force`, `--claude`, удалённая установка `curl … | sh` с
  проверкой sha256.
- **`scripts/release.sh`** — сборка бандла `dist/release/criticality-gen.tar.gz`
  + `install.sh` + `checksums-sha256.txt` со сверкой `VERSION` ↔ `version:`
  в `SKILL.md` ↔ аргумента.
- **`docs/`** (13 глав + `reference/`) и **`references/`** (8 файлов) —
  методика, критерии, пайплайн, шаблоны, CLI и правила перенесены внутрь
  компонента: скилл самодостаточен.

### Изменено

- **`SKILL.md`**: раздел «Пути» переписан под три раскладки установки
  (глобальная, проектная, запуск из клона) — `SKILL_DIR` определяет скрипт,
  корень данных — `--root` / `CRITICALITY_ROOT` / подъём от cwd; добавлен
  раздел «Установка»; относительные ссылки резолвятся от каталога скилла.
- **`install.sh`** переписан по конвенции репозитория (POSIX sh, локальный и
  удалённый режимы, маркер `.criticality-gen-installed`, env-префикс
  `CRITICALITY_*`) — вместо прежнего project-only установщика с `--target`.
- **`meta-templates/`** (authoring-материал для создания новых скиллов) в
  бандл не входит: ни `BUNDLE_ITEMS` в `install.sh`, ни `release.sh` его не
  копируют.
- **Шаблон `is.example.yaml`** остаётся один — `templates/is.example.yaml`
  (пустой каркас); `project/is.example.yaml` — его точная копия, потому что
  проектный файл приоритетнее шаблона при `make init`.

### Исправлено

- **`selftest` работает в трёх раскладках** (клон репозитория, `--project`,
  глобальная установка): проверка `D5` (`make help` / `help-fast`) читает
  `.opencode/Makefile` только в проектной раскладке, в остальных даёт `SKIP` с
  причиной «нет проектной раскладки», а не `FileNotFoundError`. Причины всех
  `SKIP` теперь печатаются построчно.
- **`selftest` не падает на данных проекта**: фикстура dochub регистрирует
  каждую публикуемую ИС, поэтому `P8/P9/P13/P14` проходят при любом коде ИС, а
  не только при `erm.mm` / `cc-exchanger` (раньше 29 ложных `FAIL`).
- **`score` и `criteria` без проекта**: корень данных нужен только `--is` и
  `criteria sync-docs`; калькулятор (`--axes`, `--cia`, `--business`,
  `--express`), `--selftest`, `criteria show` и `criteria check` работают на
  чистой системе сразу после установки.
- **`info` печатает корректный путь критериев**: относительный путь считается
  от корня проекта, а не от произвольного cwd; вне проекта печатается
  абсолютный путь (раньше из `/tmp` выводилось `opencode/clean/home1/…`).

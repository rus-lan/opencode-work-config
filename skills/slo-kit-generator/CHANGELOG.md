# Changelog

## [4.3.0] - 2026-08-17

### Обновлено под slo-kit 26.8.3 (consistency-баг починен)

slo-kit 26.8.3 устранил второй триггер ложных exit 3 — расхождение ожидающей логики lint с генератором. Теперь lint прогоняет тот же пайплайн, что и generate (`PrepareSLIs`/`PrepareAlerts` + paas-рендереры по временной копии файла); дублирующая логика (`PrepareSLOData`/`MakeAlerts`/`SLIGroup`/`scanner.ParseAlerts`) удалена. Дополнительно починена неидемпотентность `slo.yaml` для нового файла (без секции `slos:`).

#### Изменено
- SKILL.md шаг 5: «В ≥ 26.8.3 ложных триггеров exit 3 нет»
- SKILL.md шаг 6: «Ложные срабатывания exit 3 (только для < 26.8.3)» — consistency-баг помечен как починенный в 26.8.3; «В ≥ 26.8.3 exit 3 означает реальное расхождение»
- SKILL.md шаг 7: Makefile/CI-комментарии — `allow_failure: true` помечено как убираемое в ≥ 26.8.3
- slo-kit-schema.md: mismatch-секция — «В ≥ 26.8.3 lint строит ожидаемое тем же пайплайном, что и generate»; consistency-баг помечен < 26.8.3
- makefile-example: комментарий таргета `slo-kit` — «в ≥ 26.8.3 — чистый workflow без ложных exit 3»

## [4.2.2] - 2026-08-17

### Исправлено: точный механизм ложных срабатываний lint

Анализ исходников slo-kit (ast-index) показал, что описание в [4.2.1] было неточным:

- Строка timestamp в заголовке `slo.yaml` **исключена** из сравнения lint (первая строка пропускается, `internal/lint/lint.go`) — она триггером не является
- Реальный триггер exit 3 — **проверка версии**: точное равенство «версия в файле == версия бинарника». Файл, сгенерированный более старой версией (штамп от времени коммита), всегда падал — ложное срабатывание
- Найден второй баг: ожидающая логика линтера (`makeUpdatedSLOConfig`/`MakeAlerts` в `internal/config`) расходится с реальным генератором (`internal/output/paas`): лейблы `maturity: "experimental"`, `context`, `product`/`repo` в group links, `team`/`sbmt_team` в алертах, порядок лейблов, trailing spaces в expr. Даже свежесгенерированный файл может давать «Содержание файла slo.yaml отличается от ожидаемого»

#### Изменено
- SKILL.md шаги 5-7: описание переписано под точный механизм (version-check + consistency-bug, не timestamp)
- slo-kit-schema.md: mismatch-секция — version-check (направленный) и consistency-bug
- makefile-example: комментарий таргета `slo-kit` — generate перештампует версию

#### Фикс в самом slo-kit (Unreleased, ожидается 26.8.2)
- Направленный version-check: файл со старой версией — info-строка без влияния на exit code; ошибкой остаётся файл, сгенерированный новее бинарника
- Флаг `--ignore-version` для полного отключения проверки

## [4.2.1] - 2026-08-17

### Исправлено: ложное срабатывание lint по timestamp

Проблема: `slo-kit lint` (exit 3) сравнивает `slo.yaml` на диске с только что сгенерированным вариантом, а заголовок файла содержит время генерации. Расхождение только в строке timestamp — ожидаемое ложное срабатывание, но документация давала нерабочий совет («запускайте generate и lint в одном вызове», ссылка на несуществующий таргет `make slo-kit`) и не объясняла, что такой diff можно игнорировать.

#### Изменено
- SKILL.md шаг 5: вместо «запускайте в одном вызове» — объяснение, что timestamp в заголовке меняется при каждом `generate`, а timestamp-only diff при lint — ложное срабатывание
- SKILL.md шаг 6: инструкция как отличить ложный mismatch (diff только `# Generated at ...`) от реального; предупреждение не зацикливаться на повторной генерации; рекомендуемая связка `generate && lint`
- SKILL.md шаг 7: Makefile-сниппет дополнен таргетом `slo-kit` (slo-gen + slo-lint); CI-сниппет запускает `generate` перед `lint`, комментарий к `allow_failure`
- makefile-example: добавлены таргеты `slo-gen-paas` (PaaS-формат slo.yaml + alerts.yaml) и `slo-kit` (generate + lint подряд)
- slo-kit-schema.md: секция mismatch переписана — timestamp-only = ложное срабатывание, добавлен пункт про реальные расхождения

## [4.2.0] - 2026-07-29

### Workflow: интервью перед генерацией

#### Изменено
- Pipeline: `scan → generate → доработка` → `scan → интервью → generate+fill`
- Шаг 2: вместо сразу `slokit generate` — опрос пользователя **по группам** с примерами:
  - Группа 1: Группировка (по тегам / одна группа / кастомная, исключение healthz)
  - Группа 2: Метаданные (namespace, product, cost_centre, team, title, description, user_impact)
  - Группа 3: Alerts и serviceTier (enabled, notify, min_severity, serviceTier, latency_limit, runbook)
- Шаг 3: `slokit generate` + заполнение TODO в один проход (вместо отдельного шага доработки)
- "Разделение ответственности": роль агента — опрос + заполнение (не просто "доработка черновика")
- Description в frontmatter: "генерирует черновик" → "опрашивает пользователя и генерирует"
- Pipeline-диаграмма обновлена

#### Обновлено
- Evals 13, 14, 25, 33: добавлены assertions на интервью (опрос по группам с примерами)
- Evals 4, 6: custom SLI → нативный outgoing (из [4.1.0])
- Evals 37-44: 8 новых evals для outgoing типа

## [4.1.0] - 2026-07-29

### Актуализация по результатам генерации ticket-system

#### Исправлено
- `consumer` → `consumers`, `job` → `jobs` во всех примерах и схеме (ключи consists_of — множественное число)
- `job` тип для ecomtech-letsgo: убрано "не поддерживается" — нативная поддержка есть (`background_jobs_*` метрики)
- `is_lag_enabled` для ecomtech-letsgo: не поддерживается, warning игнорировать
- Consumer для letsgo: только latency, без availability (уточнено)

#### Добавлено
- Обязательные мета-поля: `title`, `description`, `user_impact.degraded/outage`, `service_name_humanized`, `links`
- Секция "Подготовка configs/" — теги-маркеры alerts.yaml, формат values.yaml
- Секция "slo.yaml mismatch" — причины и решения
- `allow_arbitrary_window: true` для custom latency queries с фиксированным subquery
- Заметка: `exported_endpoint` в http rules игнорируется (генератор маппит `handler` автоматически)
- Пример заполнения метаданных (product, cost_centre, team) в SKILL.md
- Что доработать в slo-kit: парсинг `app.letsgo.yaml` schedule controllers для jobs сканера — **реализовано** в slo-kit (`ParseJobsFromLetsgoYaml`)
- Нативный `outgoing` rule type для `http_outgoing_requests_*` — **реализован** в slo-kit (`internal/ruletypes/outgoing/`)

## [4.0.0] - 2026-07-29

### Переход от CLI к knowledge base

Skill полностью переработан: из Go CLI-инструмента (`slokit`) в базу знаний + workflow-гайд для агента.

#### Удалено
- Go CLI код: `cmd/`, `internal/`, `tests/`, `go.mod`, `go.sum`, `Makefile`
- `data-template.json` — агент пишет YAML напрямую, без промежуточного data.json
- CLI команды: `wizard`, `parse-openapi`, `parse-metrics`, `generate`
- TUI wizard (Bubble Tea)
- Все Go-зависимости (cobra, bubbletea, bubbles, lipgloss, yaml.v3)

#### Добавлено
- `references/profiles-reference.md` — единый справочник всех профилей и метрик по платформам
- Профиль `ecom-ruby` (Ruby / Space) — http, graphql, consumer (Karafka), job (que)
- Метрики Space: `ruby_kafka_consumer_batch_messages_duration_seconds_*`, `que_jobs_*`, `que_job_runtime_seconds_*`
- Workflow-гайд в SKILL.md: 5 шагов от сканирования кода до генерации артефактов
- Секция "Сервисы с нестандартными метриками" — инструкция для сервисов типа goods-issues
- 2 новых eval-кейса: ecom-ruby (HTTP+GraphQL+Kafka+que) и custom metrics (gi_*)

#### Изменения
- SKILL.md: полностью переписан — workflow-гайд вместо CLI-документации
- README.md: убраны build/CLI/deps, оставлены профили, справочники, примеры
- `slo-kit-schema.md`: обновлены профильные таблицы (добавлен ecom-ruby, graphql для Ruby)
- `ecom-tech-profile.md`: переименован в "Ecom-tech Profiles" (множественное), добавлен ecom-ruby
- `metrics-reference.md": полностью переписан — метрики по всем платформам (letsgo, ruby/space, kuper-go, kuper-ruby)
- evals: обновлены промпты (9 кейсов вместо 7), добавлены assertions для custom SLI и ecom-ruby
- .gitignore: упрощён (убраны Go-секции)

#### Обоснование
Анализ реальных сервисов (ticket-system, goods-issues) показал:
- `slo-kit lint --spath` уже сканирует код (OpenAPI, Karafka, Que, GraphQL, routes, jobs)
- `slokit parse-openapi` дублирует slo-kit lint
- `slokit generate` из data.json избыточен — LLM пишет YAML напрямую лучше, чем заполняет data.json
- `slokit wizard` (TUI) — для людей, не для агента
- Единственная уникальная фича — `parse-metrics` (.txt → SLI) — нишевая, агент читает код лучше
- Для сервисов с кастомными метриками (goods-issues) ни slokit, ни slo-kit не помогают — нужен агент с knowledge base

## [3.0.0] - 2026-07-28

### Переписывание на Go

Полностью переписан с Python на Go. Единый статический бинарник, без внешних рантайм-зависимостей.

#### Добавлено
- CLI на Cobra с командами: `wizard`, `parse-openapi`, `parse-metrics`, `generate`
- Интерактивный TUI wizard на Bubble Tea (вместо Python input() циклов)
- Кросс-платформенная сборка: `make build-all` (linux/amd64, darwin/amd64, darwin/arm64)
- Go-тесты: `generator_test.go`, `openapi_test.go`, `metricsparser_test.go`, `promql_test.go`
- Команда `parse-metrics` для парсинга PromQL .txt файлов в SLI пары

#### Удалено (Python)
- `scripts/` директория (wizard.py, parse_openapi.py, generate_slokit.py, parse_metrics_txt.py)
- Python-тесты (test_generate_slokit.py, test_parse_openapi.py, test_integration.py, test_error_handling.py)
- `pytest.ini`, `requirements-dev.txt`
- `.venv/`, `.pytest_cache/`

#### Изменения
- SKILL.md: добавлены инструкция сборки, формат data.json, workflow-гайд, выбор профиля
- README.md: полностью переписан под Go-реализацию
- evals.json: приведён к схеме skill-creator, добавлены assertions
- `.gitignore`: убраны Python-секции
- Версия Go: 1.25+

## [2.1.0] - 2026-06-05

### Изменения
- **Объединение v1 и v2**: `generate_slokit_v2.py` удалён, весь функционал перенесён в `generate_slokit.py`
- Удалён `references/generate_slokit_v2.md` (дублировал документацию из SKILL.md)
- Обновлены ссылки в документации

## [2.0.0] - 2026-05-08

### Добавлено

#### Новые возможности
- **Внешние интеграции** — поддержка мониторинга исходящих HTTP запросов (http_outgoing)
- **Кастомные метрики** — произвольные PromQL запросы для SLI
- **Многоконтекстная конфигурация** — разбивка по bounded contexts
- **Фоновые задачи** — поддержка background_jobs_* метрик

### Изменения

#### exported_endpoint для всех HTTP метрик
- Лейбл `exported_endpoint` используется во ВСЕХ HTTP метриках вместо `endpoint`
- Применяется как для входящих (`http_incoming_requests_*`), так и для исходящих (`http_outgoing_requests_*`) запросов
- По умолчанию `exported_endpoint` = `handler` (path pattern), если не указан явно
- Поддержка `x-exported-endpoint` в OpenAPI spec для кастомных значений

#### Новые метрики
- **HTTP Incoming**: `http_incoming_requests_total`, `http_incoming_requests_duration_*`
- **HTTP Outgoing**: `http_outgoing_requests_total`, `http_outgoing_requests_duration_*`
- **Background Jobs**: `background_jobs_total`, `background_jobs_success`, `background_jobs_failure`, `background_jobs_duration_*`
- **Kafka Consumers**: `event_consumer_handle_duration_*`

#### Новые файлы
- `references/metrics-reference.md` — полный справочник метрик
- `references/examples/background-jobs-example.yaml` — пример для фоновых задач

### Обновления

- Обновлён `generate_slokit.py` с поддержкой `background_jobs`
- Обновлён `README.md` с примерами background jobs
- Обновлён `SKILL.md` с новыми типами метрик

#### Новые файлы
- `scripts/generate_slokit.py` — расширенный генератор с поддержкой external, custom и multi-context
- `references/examples/external-integrations-example.yaml` — пример конфигурации для внешних интеграций
- `references/examples/multi-context-example/` — полный пример многоконтекстной конфигурации
- `references/generate_slokit_v2.md` — документация для `generate_slokit.py` (удалён, функционал объединён)

#### Обновлённые файлы
- `scripts/parse_openapi.py` — добавлена поддержка извлечения внешних интеграций через x-outgoing
- `README.md` — добавлены разделы про внешние интеграции и многоконтекстную конфигурацию
- `SKILL.md` — обновлена документация с новыми возможностями и примерами
- `evals/evals.json` — добавлены новые тестовые кейсы для external и multi-context

### Изменения

#### Обновлённая структура примеров
```
references/examples/
├── slo-kit-example.yaml
├── sloth-example.yaml
├── makefile-example
├── external-integrations-example.yaml  # NEW
└── multi-context-example/              # NEW
    ├── README.md
    └── slo-kit/
        ├── slo-kit.yaml
        ├── calls.yaml
        ├── dispatch.yaml
        └── billing.yaml
```

### Документация

- Добавлен пример использования `custom` SLI для внешних интеграций с `http_outgoing_requests_*` метриками
- Добавлена полная документация по многоконтекстной конфигурации
- Обновлены ссылки на примеры в README.md и SKILL.md

### Совместимость

- Обратная совместимость сохранена — старый `generate_slokit.py` продолжает работать
- Функционал `generate_slokit_v2.py` объединён в `generate_slokit.py`, v2 удалён


## [1.0.0] - Предыдущая версия

### Существующие возможности
- Интерактивный wizard для пошагового сбора данных
- Парсинг OpenAPI спецификаций
- Поддержка Kafka consumers с мониторингом лага
- Группировка по тегам
- Генерация sloth.yaml для Kubernetes
- Поддержка профиля ecomtech-letsgo

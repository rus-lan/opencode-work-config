---
name: slo-kit-generator
description: База знаний и CLI генератор slo-kit.yaml конфигураций SLI/SLO мониторинга микросервисов. Сканирует сервис (OpenAPI, app.letsgo.yaml, .env.example, karafka.rb, query_type.rb, routes.rb, que jobs, Spring annotations, go.mod, settings.gradle.kts), опрашивает пользователя по недостающим данным и генерирует slo-kit.yaml. Поддерживает профили: ecomtech-letsgo, ecom-ruby, ecom-kotlin, ecom-go-legacy, kuper-go/ruby/python. Содержит схему YAML, справочник метрик по платформам, примеры конфигов. Используйте когда нужно создать или обновить slo-kit конфигурацию для сервиса, настроить SLO/SLI мониторинг, или сконфигурировать наблюдаемость для микросервиса.
---

# slo-kit-generator

CLI генератор + база знаний для создания `slo-kit.yaml` конфигураций SLI/SLO мониторинга.

CLI (`slokit`) сканирует сервис и генерирует структуру `slo-kit.yaml`. Агент опрашивает пользователя (по группам, с примерами) и заполняет TODO-поля. Внешний `slo-kit` CLI рендерит артефакты и валидирует.

## Когда использовать

- Создать `slo-kit.yaml` для нового сервиса
- Обновить существующий конфиг (добавить endpoints, topics, jobs)
- Сконфигурировать мониторинг для сервиса с нестандартными метриками
- Настроить external integrations (исходящие HTTP)
- Создать многоконтекстную конфигурацию

## Разделение ответственности

| Инструмент | Роль | Команды |
|---|---|---|
| **slokit** (этот skill) | Сканирует код → генерирует структуру `slo-kit.yaml` | `slokit scan`, `slokit generate` |
| **slo-kit CLI** (внешний) | Рендерит артефакты, валидирует конфиг vs код | `slo-kit generate`, `slo-kit lint`, `slo-kit overview` |
| **Агент** | Опрашивает пользователя (по группам, с примерами) → заполняет TODO-поля → настраивает alerts/serviceTier | интерактивно |

## Что парсит slokit

### letsgo-сервисы (профиль `ecomtech-letsgo`)

| Источник | Что извлекает |
|---|---|
| `app.letsgo.yaml` | service name, product, kafkaConsumerGroup drivers, schedule controllers (jobs), http adapters |
| `.env.example` | topic names (`DRIVERS_*_TOPICS`), consumer group IDs |
| `api/openapi/*.yaml` | HTTP endpoints: method, path, tags |

### Ruby-сервисы (профиль `ecom-ruby`)

| Источник | Что извлекает | Регулярка |
|---|---|---|
| `app/graphql/types/query_type.rb` | GraphQL queries | `field :(\w+),\s*resolver:` |
| `app/graphql/types/mutation_type.rb` | GraphQL mutations | `field :(\w+),\s*mutation:` |
| `karafka.rb` + `deploy/*.yaml` | Kafka topics (резолв env vars) | `topic\s+ENV\.fetch("(KAFKA_\w+_TOPIC)"` |
| `config/routes.rb` | Rails routes (controller#action) | `(get\|post\|put\|patch\|delete)\s+'path',\s*to: 'ctrl#act'` |
| `app/jobs/que/**/*.rb` | Que job classes + queue | `class\s+(Que::[\w:]+)\s*<` + `queue\s*[=:]` |
| `config/que_schedule.yml` | Scheduled que jobs | YAML: `class`, `queue` |

### Kotlin-сервисы (профиль `ecom-kotlin`)

| Источник | Что извлекает | Регулярка |
|---|---|---|
| `settings.gradle.kts` | service name (`rootProject.name`) | `rootProject\.name\s*=\s*["']([^"']+)["']` |
| `build.gradle.kts` | детекция Spring Boot / Kotlin | `spring-boot`, `KotlinCompile` |
| `**/src/main/java/**/*.java` | HTTP endpoints (Spring annotations) | `@(Get\|Post\|Put\|Delete\|Patch)Mapping`, `@RequestMapping` |
| `**/src/main/java/**/*.kt` | HTTP endpoints (Kotlin) | те же Spring annotations |
| `api/openapi/*.yaml` | HTTP endpoints (если есть статический OpenAPI) | YAML paths |

**Fallback:** если OpenAPI spec не найден, slokit парсит Spring-аннотации из `.java`/`.kt` файлов. Class-level `@RequestMapping` комбинируется с method-level `@GetMapping`/`@PostMapping`.

### Go-legacy сервисы (профиль `ecom-go-legacy`)

| Источник | Что извлекает |
|---|---|
| `go.mod` | service name + product (из module path `.../mm/{product}/{service}`) |
| `openapi.yaml` / `openapi.yml` | HTTP endpoints: method, path, tags |

**Метрики:** `http_incoming_requests_duration_sum/count` (latency), `http_incoming_requests_total` (availability). Labels: `endpoint`, `method`, `code`.

## Pipeline: от сканирования до CI

```
slokit scan        интервью (по группам)     slokit generate + fill       slo-kit generate             slo-kit lint
    │                    │                          │                            │                            │
    ▼                    ▼                          ▼                            ▼                            ▼
┌──────────┐    ┌───────────────────┐    ┌────────────────────┐    ┌──────────────┐            ┌──────────────┐
│ сканирует │    │ группировка       │    │ slokit generate    │    │ slo.yaml     │  валидация │ код vs конфиг │
│ код       │───▶│ метаданные        │───▶│ + заполнение TODO  │───▶│ alerts.yaml  │ ─────────▶ │               │
│ показывает│    │ alerts/serviceTier│    │ агентом (1 проход) │    │ sloth CRD    │            │ exit 0 = OK   │
│ что нашёл │    │ с примерами       │    │                    │    │ vmrules      │            │ exit 1 = gaps │
└──────────┘    └───────────────────┘    └────────────────────┘    └──────────────┘            └──────────────┘
```

## Workflow для нового репозитория

### Шаг 1: Scan — проверить что найдено

```bash
make build  # один раз

./slokit scan ~/Documents/ECOM/<service>
# Профили: --profile ecomtech-letsgo (default), ecom-ruby, ecom-kotlin, ecom-go-legacy
```

Вывод показывает: HTTP endpoints (с тегами), consumers (с topics), jobs, GraphQL ops, routes, que jobs, adapters, warnings.

Покажите пользователю что найдено — это основа для опроса на следующем шаге.

### Шаг 2: Интервью — собрать недостающие данные

После сканирования опросите пользователя **по группам**. Для каждого поля покажите пример ожидаемого формата. Не запускайте генерацию, пока не получите ответы.

#### Группа 1: Группировка

Покажите найденные endpoints с тегами и спросите:

- Как сгруппировать HTTP endpoints? По тегам (рекомендуется) / одна группа / кастомная
- Исключить служебные endpoints? (healthz, status, pprof — обычно да)
- Consumers и jobs — в отдельных группах или вместе с API?

#### Группа 2: Метаданные

| Поле | Пример | Описание |
|---|---|---|
| `namespace` | `cs-com-hub`, `ts`, `erm` | Kubernetes namespace |
| `product` | `ts`, `cs-e080-core-platform` | Код продукта (из `app.letsgo.yaml` metadata.product или спросить) |
| `cost_centre` | `E001`, `E080` | E + код проекта (E001 Инструменты оператора, E080 Core Platform) |
| `team` | `t102`, `t080` | Команда (T102 TICKETS, T006 OCRM, T100 ERM, T080) |
| `service_name_humanized` | `Ticket System` | Человекочитаемое имя для алертов |
| `title` | `Ticket System` | Краткое название сервиса |
| `description` | `Система учёта тикетов оператора` | Описание сервиса |
| `user_impact.degraded` | `Замедление обработки тикетов` | Что происходит при деградации |
| `user_impact.outage` | `Невозможность создания тикетов` | Что происходит при полном сбое |

#### Группа 3: Alerts и serviceTier

| Поле | Пример | Описание |
|---|---|---|
| `alerts.enabled` | `false` → потом `true` | Включить алертинг (по умолчанию false) |
| `alerts.notify` | `[t102, oncall]` | Кому слать алерты |
| `alerts.min_severity` | `warning` | Минимальный severity (info / warning / error) |
| `serviceTier` per group | `1` (critical), `2` (core), `3` (internal), `4` (low) | Важность группы |
| `latency_limit` per group | `0.5` (API), `5` (consumers), `2` (external) | Порог задержки в секундах |
| `runbook` | `https://wiki...` | Ссылка на runbook в labels групп |

### Шаг 3: Generate + заполнение

Запустите генерацию с метаданными из интервью:

```bash
./slokit generate --namespace <ns> --team <team> --cost-centre <cc> ~/Documents/ECOM/<service>
# Профили: --profile ecomtech-letsgo (default), ecom-ruby, ecom-kotlin, ecom-go-legacy
```

Создаёт `configs/slo-kit.yaml` со структурой (endpoints, consumers, jobs) и TODO-плейсхолдерами.

Затем **в один проход** заполните все TODO-поля из ответов пользователя:

- Метаданные (title, description, user_impact, service_name_humanized, links)
- Alerts (enabled, notify, min_severity)
- serviceTier и latency_limit для каждой группы
- runbook URL в labels
- Удалите служебные endpoints (healthz, status, pprof)
- Настройте группировку согласно ответам пользователя
- Если consumer topics пустые в `.env.example` — добавьте вручную

**Что генерируется автоматически (slokit):**

| Тип | Как | Пример |
|---|---|---|
| HTTP (letsgo) | группы по OpenAPI тегам | `http: [{method: GET, handler: /v1/...}]` |
| HTTP (Ruby) | группы по controller | `http: [{method: POST, controller: graphql, action: execute}]` |
| HTTP (Kotlin) | группы по контроллерам (Spring annotations) | `http: [{method: POST, handler: /order-history/orders/order-lines}]` |
| HTTP (Go-legacy) | группы по OpenAPI тегам | `http: [{method: POST, handler: /tfs/v1/feedback/create}]` |
| Consumer | все topics в одну группу | `consumers: [{topic: ...}]` |
| GraphQL | все ops в одну группу | `graphql: [{operation_name: ..., operation_type: ...}]` |
| Jobs (letsgo) | нативный job тип | `jobs: [{queue: cleanupWorkLogs}]` |
| Jobs (ecom-ruby) | нативный job тип | `jobs: [{queue: ..., job_type: que}]` |
| External (letsgo) | нативный outgoing тип | `outgoing: [{name: ..., endpoint: ...}]` |

**Пример заполненных метаданных:**

```yaml
profile: ecomtech-letsgo
namespace: ts
service: ticket-system
product: ts
service_name_humanized: Ticket System
team: t102
cost_centre: E001

title: Ticket System
description: Система учёта тикетов оператора
user_impact:
  degraded: Замедление обработки тикетов
  outage: Невозможность создания тикетов
```

### Шаг 4: Подготовка configs/

Перед первой генерацией создайте файлы-заглушки:

**configs/alerts.yaml** (теги-маркеры для генератора):
```yaml
# slo-kit-alerts-definition-start
# slo-kit-alerts-definition-end

alerts:
  # slo-kit-alerts-declaration-start
  # slo-kit-alerts-declaration-end
```

**configs/values.yaml** (Kafka topics для линтера):
```yaml
kafka:
  topics:
    - name: topic-name
      type:
        - consumer
```

### Шаг 5: Generate artefacts

```bash
cd ~/Documents/ECOM/<service>

# PaaS формат (slo.yaml + alerts.yaml)
slo-kit generate --in configs/slo-kit.yaml --out configs/slo.yaml --alerts configs/alerts.yaml

# Kubernetes CRD (Sloth)
slo-kit generate sloth --in configs/slo-kit.yaml --output-dir configs/

# VMRules (без Sloth)
slo-kit generate vmrules --in configs/slo-kit.yaml --output-dir configs/
```

**Важно:** строка timestamp в заголовке `slo.yaml` из сравнения lint исключена (первая строка пропускается) — она ложное срабатывание не вызывает. В **slo-kit ≥ 26.8.3** ложных триггеров exit 3 нет: консистентность починена (lint прогоняет тот же пайплайн, что и generate), version-check направленный с 26.8.2. В старых версиях — см. шаг 6.

### Шаг 6: Lint — валидация код vs конфиг

```bash
slo-kit lint --spath=$(pwd)
```

Exit codes: 0=OK, 1=не всё описано, 2=ошибка парсинга, 3=расхождение slo.yaml, 4=конфиг расходится с кодом, 5=дисбаланс весов.

**Ложные срабатывания exit 3 (только для slo-kit < 26.8.3):**

1. **Проверка версии** — сообщение *«Файл slo.yaml был сгенерирован предыдущей версией slo-kit (vX), актуальная версия – vY»*. В заголовке `slo.yaml` версия slo-kit, сгенерировавшая файл. Если версия в файле **старше** версии бинарника — это нормально: файл перештампован в момент коммита, а lint-бинарник (например, `:latest` в CI) новее.
   - **slo-kit ≥ 26.8.2:** старая версия — info-строка без влияния на exit code; ошибкой остаётся только файл, сгенерированный **новее** бинарника. Есть флаг `--ignore-version`.
   - **Старые версии slo-kit (< 26.8.2):** обход — `generate` перед `lint` (generate перештампует заголовок текущей версией, проверка пройдёт):
   ```bash
   slo-kit generate --in configs/slo-kit.yaml --out configs/slo.yaml --alerts configs/alerts.yaml && slo-kit lint --spath=$(pwd)
   ```
2. **Проверка консистентности (баг, починен в 26.8.3)** — сообщение *«Содержание файла slo.yaml отличается от ожидаемого»*. В < 26.8.3 ожидающая логика линтера (`PrepareSLOData`/`MakeAlerts`) была отдельной копией генератора и разошлась с ним: лейблы `maturity: "experimental"`, `context`, `product`/`repo` в group links, `team`/`sbmt_team` в алертах, порядок лейблов, trailing spaces в expr. Даже свежесгенерированный файл давал mismatch. **В ≥ 26.8.3** lint прогоняет тот же пайплайн, что и generate (`PrepareSLIs`/`PrepareAlerts` + paas-рендереры) по временной копии файла — расхождение структурно невозможно, `generate && lint` проходит чисто.

**В ≥ 26.8.3 exit 3 означает реальное расхождение** (не ложное): файл на диске отличается от того, что generate произвёл бы из текущего `slo-kit.yaml`. Реальные проблемы — расхождения в SLI, группах, метаданных.

### Шаг 7: Makefile + CI

Добавить в Makefile (см. [makefile-example](references/examples/makefile-example)):

```makefile
slo-gen:
	docker run --rm -v $(CURDIR):/service dreg.sbmt.io/content/slo-kit:latest \
		./slo-kit generate --in /service/configs/slo-kit.yaml \
		--out /service/configs/slo.yaml --alerts /service/configs/alerts.yaml

slo-lint:
	docker run --rm -v $(CURDIR):/service dreg.sbmt.io/content/slo-kit:latest \
		./slo-kit lint --spath=/service

# generate + lint подряд: в ≥ 26.8.3 — просто чистый workflow;
# в < 26.8.2 — generate ещё и перештамповывает версию в заголовке (обход version-check)
slo-kit: slo-gen slo-lint
```

В `.gitlab-ci.yml`:

```yaml
check:slo-kit:
  image: dreg.sbmt.io/content/slo-kit:latest
  allow_failure: true  # advisory-чек; в < 26.8.3 exit 3 может быть ложным (см. шаг 6). В ≥ 26.8.3 — можно убирать
  stage: tests
  script:
    - /app/slo-kit generate --in configs/slo-kit.yaml --out configs/slo.yaml --alerts configs/alerts.yaml
    - /app/slo-kit lint --spath=$(pwd)
```

## Схема slo-kit.yaml

Полная схема: [slo-kit-schema.md](references/slo-kit-schema.md)

Минимальный пример:

```yaml
profile: ecomtech-letsgo
namespace: cs-com-hub
service: tracker
product: cs-e080-core-platform
team: t080
cost_centre: E080

alerts:
  enabled: true
  notify: [t080, oncall]
  min_severity: warning

groups:
  ticket-api:
    description: Ticket API endpoints
    labels:
      serviceTier: "2"
    defaults:
      latency_limit: "0.5"
    consists_of:
      http:
        - method: GET
          handler: /v1/ticket-system/tickets/{ticketKey}

  consumers:
    description: Kafka consumers
    labels:
      serviceTier: "2"
    defaults:
      latency_limit: "5"
    consists_of:
      consumers:
        - topic: kuper.k-ecom-prod.ecom.megamarket.fct.cw-issues.0
```

## Типы индикаторов

| Тип | Описание | SLI | Профили |
|---|---|---|---|
| `http` | REST endpoints | availability + latency | все кроме ecom-ruby (там controller#action) |
| `grpc` | gRPC methods | availability + latency | kuper-*, ecom-kotlin, ecom-go-legacy |
| `graphql` | GraphQL operations | availability + latency | kuper-ruby, ecom-ruby |
| `consumers` | Kafka consumers | latency (+ availability/lag для kuper-*) | все |
| `jobs` | Background workers | availability + latency | kuper-go, kuper-ruby, ecomtech-letsgo, ecom-ruby |
| `outboxes` | Outbox pattern | availability + latency | kuper-ruby |
| `custom` | Произвольный PromQL | один SLI | все |
| `custom_latency` | Histogram threshold | один SLI | все |
| `oif` | Outbound Interface (`oif_duration`) | availability + latency | все |
| `iif` | Inbound Interface | availability + latency | все |
| `outgoing` | Outgoing HTTP (`http_outgoing_requests_*`) | availability + latency | ecomtech-letsgo |

## Сервисы с нестандартными метриками

Если сервис экспортирует кастомные метрики (не совпадающие со стандартными для профиля):

1. Определите профиль по платформе/языку
2. Используйте `custom` и `custom_latency` вместо нативных типов
3. Напишите PromQL вручную под метрики сервиса

Пример (goods-issues: Go-сервис с custom метриками вместо platform go-backend):

```yaml
profile: ecom-go-legacy

groups:
  api:
    description: HTTP API
    consists_of:
      custom_latency:
        - name: api-latency
          description: Latency API запросов
          metric_name: gi_api_request_duration_histogram
          threshold: 0.5
          labels:
            path: /api/v1/issues
```

> **Примечание:** goods-issues не имеет label `code` в метрике latency — availability SLI невозможен, только latency.

Подробнее: [profiles-reference.md](references/profiles-reference.md)

## Справочники

- [Полная схема slo-kit.yaml](references/slo-kit-schema.md)
- [Профили и метрики по платформам](references/profiles-reference.md)
- [Справочник метрик Prometheus](references/metrics-reference.md)
- [Особенности ecom-tech профиля](references/ecom-tech-profile.md)
- [Примеры конфигов](references/examples/)

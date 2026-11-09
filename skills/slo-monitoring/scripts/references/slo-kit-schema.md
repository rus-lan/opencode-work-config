# slo-kit Schema Reference

Полная схема конфигурации slo-kit с примерами и пояснениями.

## Структура конфига

```yaml
# Обязательные поля верхнего уровня
profile: ecomtech-letsgo          # Профиль сервиса (обязательно)
namespace: cs-com-hub              # Kubernetes namespace (обязательно)
service: tracker                   # Имя сервиса (обязательно)
product: cs-e080-core-platform     # Имя продукта (обязательно)
service_name_humanized: Tracker    # Человекочитаемое имя для алертов (обязательно)

# Обязательные мета-поля
title: Tracker                     # Краткое название сервиса
description: Сервис отслеживания обращений  # Описание сервиса
user_impact:                       # Описание влияния на пользователей (обязательно)
  degraded: Замедление обработки обращений
  outage: Невозможность создания и обработки обращений

# Опциональные поля
team: t080                         # Команда разработки
cost_centre: E080                  # Бюджетный центр

# Опциональные ссылки
links:
  dashboards:
    - https://grafana.example.com/d/tracker
  repositories:
    - https://gitlab.example.com/team/tracker

# Глобальные настройки алертов
alerts:
  enabled: true
  notify:
    - t080
    - oncall
  min_severity: warning            # info | warning | error
  approved_runbook_min_severity: error
  labels:
    jiraproject: none

# Дефолты для всех групп (могут переопределяться на уровне группы)
defaults:
  latency_limit: "0.5"

# Группы мониторинга
groups:
  <group-name>:
    description: <обязательно>
    labels:
      serviceTier: "2"             # 1, 2, 3, или 4
      runbook: "https://wiki.example.com"
      team: t080                   # Переопределение team для группы
      costCentre: E080
      userImpacting: "true"
    defaults:
      latency_limit: "0.5"
    alerts:
      enabled: true
      notify:
        - t080
      min_severity: warning
    consists_of:
      http: [...]
      consumers: [...]
      grpc: [...]
      jobs: [...]
      outgoing: [...]
      custom: [...]
      custom_latency: [...]
      oif: [...]
```

## Обязательные поля

### Метаданные верхнего уровня

| Поле | Тип | Обязательность | Описание | Пример |
|------|-----|----------------|----------|--------|
| `profile` | string | Да | Профиль сервиса | `ecomtech-letsgo`, `ecom-ruby`, `kuper-go`, `kuper-ruby` |
| `namespace` | string | Да | Kubernetes namespace | `cs-com-hub` |
| `service` | string | Да | Имя сервиса | `tracker` |
| `product` | string | Да | Имя продукта | `cs-e080-core-platform` |
| `service_name_humanized` | string | Да | Человекочитаемое имя для алертов | `Tracker` |
| `title` | string | Да | Краткое название сервиса | `Tracker` |
| `description` | string | Да | Описание сервиса | `Сервис отслеживания обращений` |
| `user_impact.degraded` | string | Да | Описание при деградации | `Замедление обработки обращений` |
| `user_impact.outage` | string | Да | Описание при полном сбое | `Невозможность создания обращений` |

### Опциональные поля

| Поле | Тип | Описание | Пример |
|------|-----|----------|--------|
| `team` | string | Команда разработки | `t080` |
| `cost_centre` | string | Бюджетный центр | `E080` |
| `links.dashboards` | array | Ссылки на дашборды | `["https://grafana..."]` |
| `links.repositories` | array | Ссылки на репозитории | `["https://gitlab..."]` |

### Global alerts

| Поле | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `enabled` | boolean | `true` | Включить алертинг |
| `notify` | array | `[]` | Список команд для уведомлений |
| `min_severity` | string | `warning` | Минимальный уровень алерта |

## Типы индикаторов

### HTTP endpoints

```yaml
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
        - method: POST
          handler: /v1/ticket-system/tickets/getpersonallist
        - method: POST
          handler: /v1/ticket-system/comments/create
```

**Поля:**
- `method` (обязательно): HTTP метод (GET, POST, PUT, DELETE, PATCH)
- `handler` (обязательно): Path pattern эндпоинта. Для ecomtech-letsgo генератор автоматически маппит `handler` → `exported_endpoint` в PromQL. Указывать `exported_endpoint` отдельно **не нужно** — поле игнорируется.
- `errors_4xx` (опционально): Считать 4xx ошибками (по умолчанию false)
- `krakend` (опционально): Использовать Krakend-метрики (только для `go` платформы)

### Kafka consumers

```yaml
groups:
  consumers:
    description: Kafka issue event consumers
    labels:
      serviceTier: "2"
    defaults:
      latency_limit: "5"
    consists_of:
      consumers:
        - topic: kuper.k-ecom-prod.ecom.megamarket.fct.cw-issues.0
        - topic: kuper.k-ecom-prod.ecom.samokat.fct.cw-issues.0
        - topic: kuper.k-prod.yc.operations.fct.cw-issues.0
```

**Поля:**
- `topic` (обязательно): Имя Kafka топика
- `is_lag_enabled` (опционально): Включить мониторинг лага (default: false). **Не поддерживается для ecomtech-letsgo** — установка в `true` даёт ошибку валидации. Warning линтера об обязательности можно игнорировать для letsgo.
- `lag_limit` (опционально): Порог лага (требуется если is_lag_enabled=true)

### gRPC endpoints

```yaml
groups:
  grpc-api:
    description: gRPC service methods
    labels:
      serviceTier: "1"
    consists_of:
      grpc:
        - service: OrderService
          method: GetOrder
        - service: OrderService
          method: CreateOrder
```

**Поля:**
- `service` (обязательно): Имя gRPC сервиса
- `method` (обязательно): Имя метода
- `ignore_not_found` (опционально): Исключить NotFound из ошибок

### GraphQL operations

GraphQL-операции (query, mutation, subscription). Поддерживается для профилей `kuper-ruby`, `ecom-ruby` (Ruby) и `ecom-nodejs` (Node.js). Платформа определяется профилем автоматически.

```yaml
groups:
  graphql-api:
    description: GraphQL operations
    labels:
      serviceTier: "1"
    consists_of:
      graphql:
        - operation_name: getOrders
          operation_type: query
        - operation_name: createOrder
          operation_type: mutation
```

**Поля:**
- `operation_name` (обязательно): Имя GraphQL-операции (например `getOrders`, `cancel_opercrm_order`)
- `operation_type` (опционально): `query` | `mutation` | `subscription`. Если не указан, используется для дефолтного `latency_limit`

**Метрики по платформам:**

| Платформа | Availability | Latency |
|---|---|---|
| Node.js | `graphql_queries_encountered_errors` / `graphql_queries_responded` (label: `operationName`) | `graphql_total_request_time_sum`/`count` (label: `operationName`, `success="true"`) |
| Ruby (kuper-ruby) | `ruby_graphql_requests_total` (label: `operation_name`, `operation_status=~"error"`) / total | `ruby_graphql_request_duration_seconds_sum`/`count` (label: `operation_name`) |
| Ruby (ecom-ruby / Space) | аналогично kuper-ruby | аналогично kuper-ruby |

Генерирует два SLI: availability + latency. PromQL строится автоматически на основе `operation_name` и платформы профиля.

**Дефолтный latency_limit:**
- `query` → `2` (секунды)
- `mutation` → `3` (секунды)
- `subscription` / не указан → `3`

### Custom SLI

```yaml
groups:
  custom-metrics:
    description: Custom business metrics
    consists_of:
      custom:
        - name: external-calls
          description: Доступность внешних вызовов
          error_query: sum(rate(errors{service="api"}[{{.window}}]))
          total_query: sum(rate(total{service="api"}[{{.window}}]))
```

**Поля:**
- `name` (обязательно): Идентификатор индикатора
- `description` (обязательно): Описание
- `error_query` + `total_query` ИЛИ `error_ratio_query`: Prometheus запросы
- `allow_arbitrary_window` (опционально): Разрешить запросы без `{{.window}}`

### Outgoing HTTP (letsgo)

Исходящие HTTP запросы через letsgo-адаптеры. Метрики: `http_outgoing_requests_total` / `http_outgoing_requests_duration`.

```yaml
groups:
  external:
    description: Внешние интеграции
    defaults:
      latency_limit: "2.0"
    consists_of:
      outgoing:
        - name: order-service
          description: Order Service (получение и поиск заказов)
          endpoint: .*/api/market/v4/orderService/customerOrder/(get|search)
        - name: user-conductor
          description: User Conductor (поиск профиля)
          endpoint: .*/api/market/v1/userConductor/userProfile/find
          method: POST
```

**Поля:**
- `name` (обязательно): Идентификатор
- `description` (обязательно): Описание
- `endpoint` (обязательно): Regex для `exported_endpoint`. Содержит полный URL с хостом (`http://api.prod.lan/...`), используйте `.*` префикс
- `method` (опционально): HTTP метод (GET, POST, и т.д.)
- `errors_4xx` (опционально): Считать 4xx ошибками (по умолчанию false)

**ВАЖНО:** `job` label = scrape job (имя сервиса-источника), не целевой сервис. Фильтрация только по `exported_endpoint`. `oif` тип не подходит — он хардкожен на `oif_duration` метрику.

### Custom latency (histogram)

```yaml
groups:
  latency-metrics:
    description: Custom latency metrics
    consists_of:
      custom_latency:
        - name: command-exec-time
          description: Время выполнения команды
          metric_name: command_duration_seconds
          threshold: 0.5
          labels:
            service: api
```

**Поля:**
- `name` (обязательно): Идентификатор
- `description` (обязательно): Описание
- `metric_name` (обязательно): Базовое имя метрики (без `_bucket`)
- `threshold` (обязательно): Порог задержки в секундах
- `labels` (опционально): Дополнительные Prometheus labels

## Severity levels

Уровни severity и пороги отклонения от SLO:

| Severity | Порог отклонения | Описание |
|----------|------------------|----------|
| `info` | 0% до −0.1% | Информационный |
| `warning` | −0.1% до −0.5% | Предупреждение |
| `error` | −0.5% до −5% | Ошибка |
| `critical` | от −5% и ниже | Критический |

**Важно:** Для ecom-tech профиля `critical` автоматически капается до `error`.

## Service tiers

Уровни важности сервиса влияют на пороги алертов:

| Tier | Описание | latency_limit дефолт |
|------|----------|---------------------|
| `1` | Критические, user-facing | "0.1" |
| `2` | Важные, core функционал | "0.5" |
| `3` | Внутренние, вспомогательные | "1.0" |
| `4` | Низкий приоритет | "5.0" |

## Наследование конфигурации

Конфигурация наследуется по цепочке:

1. **Глобальные настройки** (уровень конфига)
2. **Настройки группы** (уровень группы)
3. **Настройки индикатора** (уровень consists_of)

Пример:
```yaml
# Глобальный дефолт
defaults:
  latency_limit: "0.5"

groups:
  # Переопределение для группы
  fast-endpoints:
    defaults:
      latency_limit: "0.1"  # Переопределяет глобальный
    consists_of:
      http:
        - method: GET
          handler: /api/fast
          # Использует latency_limit: "0.1"
  
  # Наследует глобальный дефолт
  slow-endpoints:
    consists_of:
      http:
        - method: POST
          handler: /api/slow
          # Использует latency_limit: "0.5" (глобальный)
```

## Примеры групп

### HTTP + Consumer в одной группе

```yaml
groups:
  orders-service:
    description: Orders processing
    labels:
      serviceTier: "1"
    consists_of:
      http:
        - method: GET
          handler: /api/v1/orders/{id}
        - method: POST
          handler: /api/v1/orders
      consumers:
        - topic: kuper.orders.created.0
          is_lag_enabled: true
          lag_limit: 100
```

### Множественные группы по функционалу

```yaml
groups:
  # API endpoints
  public-api:
    description: Public REST API
    labels:
      serviceTier: "1"
    consists_of:
      http:
        - method: GET
          handler: /api/v1/users
        - method: POST
          handler: /api/v1/orders
  
  # Admin endpoints
  admin-api:
    description: Admin API
    labels:
      serviceTier: "2"
    consists_of:
      http:
        - method: GET
          handler: /admin/users
        - method: DELETE
          handler: /admin/cache
  
  # Background processing
  consumers:
    description: Kafka event consumers
    labels:
      serviceTier: "2"
    defaults:
      latency_limit: "5"
    consists_of:
      consumers:
        - topic: orders.created.0
        - topic: payments.processed.0
```

## Генерация и валидация

### Генерация артефактов

```bash
# Генерация slo.yaml и alerts.yaml
slo-kit generate --in=configs/slo-kit.yaml --out=configs/slo.yaml --alerts=configs/alerts.yaml

# Линт (проверяет консистентность конфига и кода)
slo-kit lint --spath=/path/to/service
```

**Важно:** `lint` ожидает конфиг в `configs/slo-kit.yaml` (не `--in` флаг).

### Структура configs/

```
configs/
├── slo-kit.yaml    # Исходный конфиг (правится вручную)
├── slo.yaml        # Сгенерированные SLI (не править вручную!)
├── alerts.yaml     # Сгенерированные алерты (не править вручную!)
└── values.yaml     # Kafka topics для линтера
```

### alerts.yaml — теги-маркеры

Файл `alerts.yaml` должен содержать теги-маркеры перед первой генерацией. Создайте пустой файл:

```yaml
# slo-kit-alerts-definition-start
# slo-kit-alerts-definition-end

alerts:
  # slo-kit-alerts-declaration-start
  # slo-kit-alerts-declaration-end
```

Генератор вставляет алерты между тегами. Пользовательские алерты можно добавлять вне этих блоков.

### slo.yaml / alerts.yaml mismatch

Линтер сравнивает содержимое `slo.yaml`/`alerts.yaml` на диске с ожидаемым вариантом (строка timestamp в заголовке из сравнения исключена). **В ≥ 26.8.3** lint строит «ожидаемое» тем же пайплайном, что и generate (`PrepareSLIs`/`PrepareAlerts` + paas-рендереры по временной копии файла), поэтому exit 3 означает **реальное** расхождение. Ложные срабатывания возможны только в старых версиях:

1. **Проверка версии (< 26.8.2)** — заголовок `slo.yaml` содержит версию slo-kit, сгенерировавшую файл. Старые версии slo-kit: версия в файле **старше** версии бинарника → exit 3 («сгенерирован предыдущей версией») — ложное срабатывание, штамп от времени коммита. Обход: `generate` перед `lint` или `--ignore-version`. В ≥ 26.8.2: старая версия — info-строка без влияния на exit code, ошибкой является файл, сгенерированный **новее** бинарника.
2. **Проверка консистентности (баг, < 26.8.3)** — ожидающая логика (`PrepareSLOData`/`MakeAlerts`) была отдельной копией генератора и разошлась с ним: лейблы `maturity: "experimental"`, `context`, `product`/`repo` в group links, `team`/`sbmt_team` в алертах, порядок лейблов, trailing spaces в expr. Свежесгенерированный файл тоже давал mismatch. **В ≥ 26.8.3** дублирующая логика удалена — lint использует тот же код, что и generate; расхождение структурно невозможно.
3. **Реальные расхождения** — SLI, группы или метаданные отличаются от `slo-kit.yaml`. Требуют внимания: обновите конфиг и перегенерируйте.

### configs/values.yaml — Kafka topics

Линтер проверяет что Kafka topics из `slo-kit.yaml` существуют в `configs/values.yaml`. Формат:

```yaml
kafka:
  topics:
    - name: topic-name-1
      type:
        - consumer
    - name: topic-name-2
      type:
        - consumer
```

Для ecom-tech сервисов где topics хранятся в helm-репозитории, используйте `SLO_KIT_VALUES_PATH`:

```bash
export SLO_KIT_VALUES_PATH=/path/to/helm/chart/dir
```

### Линтер

Линтер проверит:
- Все описанные endpoints существуют в коде
- Все Kafka topics подключены в сервисе (через `configs/values.yaml` или `SLO_KIT_VALUES_PATH`)
- Jobs найдены в коде (для letsgo — поиск `JobWithOptions` в Go-коде)
- Нет неописанных маршрутов/топиков
- Консистентность конфигурации

Флаги игнорирования:
- `--ignore-topics` — пропустить проверку Kafka topics
- `--ignore-jobs` — пропустить проверку jobs
- `--ignore-openapi` — пропустить проверку HTTP endpoints

## Ссылки

- [Профили и метрики по платформам](profiles-reference.md)
- [Особенности ecom-tech профиля](ecom-tech-profile.md)
- [Справочник метрик Prometheus](metrics-reference.md)
- [Примеры конфигов](examples/slo-kit-example.yaml)
- [Официальная документация slo-kit](https://gitlab.sbmt.io/dev-ashunicorn-team/slo-kit)

## Ограничения ecom-tech профиля

Подробное описание ограничений профилей `ecomtech-letsgo` и `ecom-ruby` (неподдерживаемые типы,
severity cap, метрики) см. в [ecom-tech-profile.md](ecom-tech-profile.md).

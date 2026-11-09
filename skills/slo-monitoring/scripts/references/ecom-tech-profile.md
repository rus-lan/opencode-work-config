# Ecom-tech Profiles

Особенности профилей `ecomtech-letsgo` и `ecom-ruby` для slo-kit конфигураций.

## Профили

| Профиль | Язык | Платформа | Описание |
|---|---|---|---|
| `ecomtech-letsgo` | Go (letsgo) | ecom-tech | Go-сервисы на фреймворке letsgo |
| `ecom-ruby` | Ruby | ecom-tech (Space) | Ruby-сервисы на платформе Space (Karafka + que) |

Оба профиля используют `OutputConfig{EcomTech: true, HasCriticalSeverity: false}`.

## Маппинг severity

Платформа ecom-tech использует собственную шкалу severity. Маппинг применяется автоматически:

| slo-kit severity | ecom-tech severity |
|------------------|-------------------|
| `info`           | `low`             |
| `warning`        | `warning`         |
| `error`          | `high`            |
| `critical`       | **не поддерживается** |

## Cap severity

Максимальный severity ограничен до **error** (после маппинга — **high**). Диапазон critical (от −5% и ниже) поглощается error (от −0.5% до −100%).

Группы с `min_severity: critical` или `force_severity: critical` пропускаются с предупреждением:

```
WARNING: group "payments": min_severity "critical" несовместим с ecomtech профилем, алерты пропущены
```

## Дополнительные labels

К алертам автоматически добавляются labels:

| Label | Значение | Описание |
|-------|----------|----------|
| `namespace` | из поля `namespace` | Kubernetes namespace сервиса |
| `destination` | `keephq` | Целевая платформа |

## Формат вывода

### Sloth формат

Упрощённый формат без CRD-обёртки:

**Стандартный формат (kuper-* профили):**
```yaml
apiVersion: sloth.slok.dev/v1
kind: PrometheusServiceLevel
metadata:
  name: cs-com-hub-tracker
  namespace: cs-com-hub
spec:
  service: tracker
  labels:
    ...
  slos:
    ...
```

**Ecom-tech формат:**
```yaml
prometheusServiceLevel:
  service: tracker
  labels:
    component: consumers
    context: cs-com-hub
    costCentre: E080
    product: cs-e080-core-platform
    repo: cs-com-hub
    serviceTier: "2"
    team: t080
    userImpacting: "true"
  slos:
    ...
```

### VMRules формат

Аналогично sloth — упрощённый формат:

**Стандартный формат:**
```yaml
apiVersion: operator.victoriametrics.com/v1beta1
kind: VMRule
metadata:
  name: cs-com-hub-slo
  namespace: cs-com-hub
spec:
  groups:
    - name: slo-alerts
      rules: [...]
```

**Ecom-tech формат:**
```yaml
vmRule:
  groups:
    - name: slo-alerts
      rules: [...]
```

## Метрики Prometheus

### HTTP метрики

Для профиля `ecomtech-letsgo` используются метрики:

| Тип | Метрика | Описание |
|-----|---------|----------|
| Duration | `http_incoming_requests_duration` | Распределение времени запросов |
| Total | `http_incoming_requests_total` | Счётчик запросов |

Пример запроса для latency SLI:
```promql
sum(rate(http_incoming_requests_duration_sum{
    namespace="cs-com-hub",
    service="tracker",
    method="GET",
    exported_endpoint="/api/v1/orders",
    code=~"2.."
}[30s]))
/
sum(rate(http_incoming_requests_duration_count{
    namespace="cs-com-hub",
    service="tracker",
    method="GET",
    exported_endpoint="/api/v1/orders",
    code=~"2.."
}[30s]))
```

Пример запроса для availability SLI:
```promql
sum(increase(http_incoming_requests_total{
    namespace="cs-com-hub",
    service="tracker",
    method="GET",
    exported_endpoint="/api/v1/orders",
    code=~"(0)|(5[0-9][0-9])|(5xx)"
}[{{.window}}]))
```

### Kafka Consumer метрики

Для consumers используются метрики:

| Тип | Метрика | Описание |
|-----|---------|----------|
| Duration | `event_consumer_handle_duration` | Время обработки сообщений |

Пример запроса для latency SLI:
```promql
sum(rate(event_consumer_handle_duration_sum{
    namespace="cs-com-hub",
    service="tracker",
    topic="kuper.k-ecom-prod.ecom.megamarket.fct.cw-issues.0"
}[30s]))
/
sum(rate(event_consumer_handle_duration_count{
    namespace="cs-com-hub",
    service="tracker",
    topic="kuper.k-ecom-prod.ecom.megamarket.fct.cw-issues.0"
}[30s]))
```

## Линтер и SLO_KIT_VALUES_PATH

Для ecom-tech сервисов Kafka topics часто хранятся в отдельном helm-репозитории. Переменная окружения `SLO_KIT_VALUES_PATH` позволяет указать путь:

```bash
export SLO_KIT_VALUES_PATH=/path/to/helm/chart/dir
```

Для удобства локальной работы — файл `.slo-kit.local.env` (gitignored):

```env
SLO_KIT_VALUES_PATH=/path/to/helm/chart/dir
```

В Makefile:

```makefile
-include .slo-kit.local.env

slo-lint:
	docker run --rm \
		-v $(CURDIR):/service \
		$(if $(SLO_KIT_VALUES_PATH),-v $(SLO_KIT_VALUES_PATH):/helm-values -e SLO_KIT_VALUES_PATH=/helm-values) \
		$(SLO_KIT_IMAGE) \
		./slo-kit lint --spath=/service
```

Линтер ищет env-переменные `DRIVERS_CONSUMER_*_TOPICS` в YAML-файлах указанной директории.

## Пример конфигурации

```yaml
profile: ecomtech-letsgo
namespace: cs-com-hub
service: tracker
product: cs-e080-core-platform
service_name_humanized: Tracker
team: t080
cost_centre: E080

title: Tracker
description: Сервис отслеживания обращений
user_impact:
  degraded: Замедление обработки обращений
  outage: Невозможность создания и обработки обращений

alerts:
  enabled: true
  notify:
    - t080
  min_severity: warning

groups:
  ticket-api:
    description: Ticket API endpoints
    labels:
      serviceTier: "2"
      runbook: "https://space.samokat.ru/display/ECOMCS/E080+Runbooks"
    defaults:
      latency_limit: "0.5"
    consists_of:
      http:
        - method: GET
          handler: /v1/ticket-system/tickets/{ticketKey}
        - method: POST
          handler: /v1/ticket-system/tickets/getpersonallist

  consumers:
    description: Kafka issue event consumers
    labels:
      serviceTier: "2"
      runbook: "https://space.samokat.ru/display/ECOMCS/E080+Runbooks"
    defaults:
      latency_limit: "5"
    consists_of:
      consumers:
        - topic: kuper.k-ecom-prod.ecom.megamarket.fct.cw-issues.0
        - topic: kuper.k-ecom-prod.ecom.samokat.fct.cw-issues.0
        - topic: kuper.k-prod.yc.operations.fct.cw-issues.0
```

## Ограничения

### Не поддерживаемые типы

| Тип | ecomtech-letsgo | ecom-ruby | Примечание |
|-----|:---:|:---:|------------|
| `grpc` | - | - | Не поддерживается |
| `graphql` | - | + | ecom-ruby: `ruby_graphql_*` метрики |
| `job` | + | + | ecomtech-letsgo: `background_jobs_*`; ecom-ruby: que jobs (`que_jobs_*`) |
| `outboxes` | - | - | Не поддерживается |
| `http` | + | + | Полная поддержка |
| `consumer` | + (latency) | + (latency) | Только latency, без availability. Lag monitoring не поддерживается — `is_lag_enabled: true` даёт ошибку валидации. Warning линтера об обязательности игнорировать. |
| `custom` | + | + | Полная поддержка |
| `custom_latency` | + | + | Полная поддержка |
| `oif` | + | + | Полная поддержка (`oif_duration` метрика) |
| `iif` | + | + | Полная поддержка |
| `outgoing` | + | - | ecomtech-letsgo: `http_outgoing_requests_*` (letsgo RoundTripper). `job` label = scrape job, фильтрация по `exported_endpoint` |

## Сравнение профилей

| Функция | ecomtech-letsgo | ecom-ruby | kuper-go | kuper-ruby |
|---------|-----------------|-----------|----------|------------|
| HTTP метрики | `http_incoming_requests_*` | `sbmtapp_http_request_duration_seconds_*` | `http_request_duration_seconds_*` | `sbmtapp_http_request_duration_seconds_*` |
| gRPC | - | - | + | + |
| GraphQL | - | + (`ruby_graphql_*`) | - | + (`ruby_graphql_*`) |
| Consumer метрики | `event_consumer_handle_duration` | `ruby_kafka_consumer_batch_messages_duration_seconds` | `kafka_consume_*` | `kafka_consumer_*` |
| Job мониторинг | + (`background_jobs_*`) | + (que: `que_jobs_*`) | + (`workers_job_*`) | + (sidekiq/schked) |
| Outgoing HTTP | + (`http_outgoing_requests_*`) | - | - | - |
| Severity critical | - | - | + | + |
| Формат вывода | Упрощённый | Упрощённый | Полный CRD | Полный CRD |

## Ссылки

- [Основная схема slo-kit](slo-kit-schema.md)
- [Профили и метрики по платформам](profiles-reference.md)
- [Справочник метрик Prometheus](metrics-reference.md)
- [Примеры конфигов](examples/slo-kit-example.yaml)
- [Пример Makefile](examples/makefile-example)

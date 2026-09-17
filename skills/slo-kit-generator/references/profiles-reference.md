# Профили и метрики

Полный справочник профилей slo-kit и соответствующих метрик Prometheus.

## Поддержка типов индикаторов

| Тип | kuper-go | kuper-ruby | kuper-python | ecom-kotlin | ecom-go-legacy | ecomtech-letsgo | ecom-ruby |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| http | + | + | + | + | + | + | + |
| grpc | + | + | + | + | + | - | - |
| graphql | - | + | - | - | - | - | + |
| consumer | + | + | + | + | + | + (latency) | + (latency) |
| job | + | + | - | - | - | + (letsgo) | + (que) |
| outboxes | - | + | - | - | - | - | - |
| custom | + | + | + | + | + | + | + |
| custom_latency | + | + | + | + | + | + | + |
| oif | + | + | + | + | + | + | + |
| iif | + | + | + | + | + | + | + |
| outgoing | - | - | - | - | - | + | - |

## Метрики по платформам

### ecomtech-letsgo (Go / letsgo)

| Тип | Availability | Latency |
|---|---|---|
| http | `http_incoming_requests_total` (labels: `method`, `exported_endpoint`, `code`) | `http_incoming_requests_duration_sum`/`count` (labels: `method`, `exported_endpoint`, `code`) |
| consumer | нет (только latency) | `event_consumer_handle_duration_sum`/`count` (label: `topic`) |
| job | `background_jobs_failure` / `background_jobs_total` (labels: `name`) | `background_jobs_duration_sum`/`count` (labels: `name`) |
| outgoing | `http_outgoing_requests_total` (labels: `exported_endpoint`, `code`, `method`) | `http_outgoing_requests_duration_sum`/`count` (labels: `exported_endpoint`, `code`, `method`) |
| oif | `oif_duration_count` (labels: `out_service`, `out_if_id`, `status`) | `oif_duration_sum`/`count` |
| custom | явный PromQL | явный PromQL |
| custom_latency | — | `metric_name_bucket` (threshold-based) |

**Labels для HTTP:** `env`, `namespace`, `service`, `method`, `exported_endpoint`, `code`

**ВАЖНО:** `outgoing` — для `http_outgoing_requests_*` (letsgo RoundTripper). `oif` — для `oif_duration` (другая инструментация). `job` label = scrape job (имя сервиса), не целевой сервис.

**ВАЖНО:** Лейбл `exported_endpoint` (не `endpoint`!) используется во всех HTTP метриках letsgo.

### ecom-ruby (Ruby / Space)

| Тип | Availability | Latency |
|---|---|---|
| http | `sbmtapp_http_request_duration_seconds_count` (labels: `method`, `exported_endpoint`, `code`) | `sbmtapp_http_request_duration_seconds_sum`/`count` |
| graphql | `ruby_graphql_requests_total` (labels: `operation_name`, `operation_status=~"error"`) | `ruby_graphql_request_duration_seconds_sum`/`count` (label: `operation_name`) |
| consumer | нет (только latency) | `ruby_kafka_consumer_batch_messages_duration_seconds_sum`/`count` (label: `topic`) |
| job (que) | `que_jobs_failed_total` / `que_jobs_executed_total` (labels: `queue`, `worker`) | `que_job_runtime_seconds_sum`/`count` (labels: `queue`, `worker`) |
| custom | явный PromQL | явный PromQL |

**Labels для HTTP:** `namespace`, `service`, `method`, `exported_endpoint`, `code`

**Особенность:** Профиль `ecom-ruby` использует платформу `space-ruby` — обёртку Space над стандартными Ruby-метриками. Метрики Karafka: `ruby_kafka_consumer_batch_*` (не `kafka_consumer_*` как в kuper-ruby). Метрики jobs: `que_*` (не `sidekiq_*` как в kuper-ruby).

### kuper-go (Go / Kuper)

| Тип | Availability | Latency |
|---|---|---|
| http | `http_requests_total` (labels: `method`, `handler`, `code`) | `http_request_duration_seconds_sum`/`count` |
| grpc | `grpc_server_handled_total` (labels: `grpc_service`, `grpc_method`, `grpc_code`) | `grpc_server_handling_seconds_sum`/`count` |
| consumer | `kafka_consume_total` (labels: `topic`, `status`) | `kafka_consume_duration_seconds_sum`/`count` |
| job | `workers_job_failed_total` / `workers_job_total` (label: `queue`) | `workers_job_duration_seconds_sum`/`count` |
| custom | явный PromQL | явный PromQL |

### kuper-ruby (Ruby / Kuper)

| Тип | Availability | Latency |
|---|---|---|
| http | `sbmtapp_http_request_duration_seconds_count` (labels: `controller`, `action`, `code`) | `sbmtapp_http_request_duration_seconds_sum`/`count` |
| grpc | `sbmtapp_grpc_server_handled_total` | `sbmtapp_grpc_server_request_duration_seconds_sum`/`count` |
| graphql | `ruby_graphql_requests_total` (label: `operation_name`) | `ruby_graphql_request_duration_seconds_sum`/`count` |
| consumer | `kafka_consumer_messages_total` (label: `topic`) | `kafka_consumer_duration_seconds_sum`/`count` |
| job (sidekiq) | `sidekiq_jobs_failed_total` / `sidekiq_jobs_executed_total` (labels: `queue`, `worker`) | `sidekiq_job_runtime_seconds_sum`/`count` |
| job (schked) | `schked_job_failed_total` / `schked_job_executed_total` | `schked_job_runtime_seconds_sum`/`count` |
| outboxes | `outbox_events_failed_total` / `outbox_events_total` | `outbox_event_duration_seconds_sum`/`count` |
| custom | явный PromQL | явный PromQL |

**HTTP для Ruby:** использует `controller` + `action` вместо `method` + `handler`.

### kuper-python (Python / Kuper)

| Тип | Availability | Latency |
|---|---|---|
| http | `http_requests_total` (labels: `method`, `handler`, `code`) | `http_request_duration_seconds_sum`/`count` |
| grpc | `grpc_server_handled_total` | `grpc_server_handling_seconds_sum`/`count` |
| consumer | `kafka_consume_total` | `kafka_consume_duration_seconds_sum`/`count` |
| custom | явный PromQL | явный PromQL |

## Ecom-tech особенности

Профили `ecomtech-*` (`ecomtech-letsgo`, `ecom-ruby`) автоматически включают:

- **Severity cap:** critical не генерируется, маппится до error
- **Severity mapping:** info→low, warning→warning, error→high
- **Упрощённый CRD формат:** без `apiVersion`/`kind`/`metadata` обёртки
- **Дополнительные labels:** `namespace`, `destination: keephq`
- **HasCriticalSeverity: false** в OutputConfig

Подробнее: [ecom-tech-profile.md](ecom-tech-profile.md)

## Node.js (GraphQL only)

Для Node.js-сервисов с GraphQL нет нативного профиля. Используйте `custom` SLI:

| Метрика | Описание | Labels |
|---|---|---|
| `graphql_queries_responded` | Всего ответов | `operationName` |
| `graphql_queries_encountered_errors` | Ответы с ошибками | `operationName` |
| `graphql_total_request_time_sum`/`count` | Время выполнения | `operationName`, `success` |

PromQL для availability:
```promql
sum(increase(graphql_queries_encountered_errors{operationName="getOrders"}[{{.window}}]))
/
sum(increase(graphql_queries_responded{operationName="getOrders"}[{{.window}}]))
```

PromQL для latency:
```promql
sum(rate(graphql_total_request_time_sum{operationName="getOrders",success="true"}[30s]))
/
sum(rate(graphql_total_request_time_count{operationName="getOrders",success="true"}[30s]))
```

## ecom-kotlin (Kotlin / Spring Boot)

Нативный профиль для Spring Boot (Java/Kotlin) сервисов на платформе Samokat.

| Тип | Availability | Latency |
|---|---|---|
| http | `http_server_requests_seconds_count` (labels: `service`, `uri`, `method`, `outcome`) | `http_server_requests_seconds_sum`/`count` (labels: `service`, `uri`, `method`, `outcome`) |
| grpc | `grpc_server_handled_total` (labels: `grpc_service`, `grpc_method`, `grpc_code`) | `grpc_server_handling_seconds_sum`/`count` |
| consumer | `kafka_consume_total` (labels: `topic`, `status`) | `kafka_consume_duration_seconds_sum`/`count` |
| custom | явный PromQL | явный PromQL |

**Labels для HTTP:** `namespace`, `service`, `method`, `uri`, `status`, `outcome`, `error_code`

**Двухуровневый SLO:**
- Availability error = `outcome!="SUCCESS"` (HTTP ошибки) + `outcome="SUCCESS",error_code!="none"` (бизнес-ошибки)
- Latency = только `outcome="SUCCESS",error_code="none"` (успешные запросы)

**ВАЖНО:** Используется `service` label (не `application`). Метрика — summary (есть `_sum`/`_count`, нет `_bucket`).

## ecom-go-legacy (Go / platform go-backend / good-tools)

Профиль для Go-сервисов на platform go-backend (good-tools).

| Тип | Availability | Latency |
|---|---|---|
| http | `http_incoming_requests_total` (labels: `method`, `endpoint`, `code`) | `http_incoming_requests_duration_sum`/`count` (labels: `method`, `endpoint`, `code`) |
| grpc | `grpc_server_handled_total` (labels: `grpc_service`, `grpc_method`, `grpc_code`) | `grpc_server_handling_seconds_sum`/`count` |
| consumer | `kafka_consume_total` (labels: `topic`, `status`) | `kafka_consume_duration_seconds_sum`/`count` |
| custom | явный PromQL | явный PromQL |

**Labels для HTTP:** `namespace`, `method`, `endpoint`, `code`

**Отличие от kuper-go:** метрики `http_incoming_requests_*` (platform go-backend) вместо `http_request_duration_seconds_*` (kuper). Labels `endpoint`/`method`/`code` вместо `http_handler`/`http_method`/`http_code_num`.

**Сервисы с нестандартными метриками:** если сервис использует custom метрики (например goods-issues с `gi_api_request_duration_histogram`), используйте `custom`/`custom_latency` SLI вместо нативного `http`.

## Сервисы с нестандартными метриками

Если сервис экспортирует кастомные метрики, не совпадающие со стандартными для профиля:

1. **Определите профиль** по платформе/языку (например `ecomtech-letsgo` для Go на ecom-tech)
2. **Используйте `custom` и `custom_latency`** вместо нативных типов
3. **Напишите PromQL вручную** под метрики сервиса

Пример (goods-issues: Go-сервис с custom метриками, профиль ecom-go-legacy):

```yaml
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

  external:
    description: Внешние интеграции
    consists_of:
      custom:
        - name: jira-availability
          description: Доступность Jira
          error_query: |
            sum(increase(gi_external_status_code_count{service_name="jira",code=~"5.."}[{{.window}}]))
          total_query: |
            sum(increase(gi_external_status_code_count{service_name="jira"}[{{.window}}]))
```

## Источники данных для линтера

Что сканирует `slo-kit lint` по профилям:

| Тип | Ruby (kuper-ruby, ecom-ruby) | Go / Python / Letsgo | Kotlin | Go-legacy |
|---|---|---|---|---|
| HTTP | `routes.log` (rails routes) или `config/routes.rb` | OpenAPI (`.yaml` в `api*/`) | OpenAPI + Spring annotations (`.java`/`.kt`) | OpenAPI (`.yaml`) |
| gRPC | `.proto` в `api/grpc/` | `.proto` в `api/grpc/` | `.proto` в `api/grpc/` | `.proto` в `api/grpc/` |
| GraphQL | `app/graphql/types/query_type.rb` + `mutation_type.rb` | `.graphql` файлы | — | — |
| Kafka topics | `configs/values.yaml` или `SLO_KIT_VALUES_PATH` (kuper) / `karafka.rb` + `deploy/*.yaml` (ecom-ruby) | `configs/values.yaml` или `SLO_KIT_VALUES_PATH` | `configs/values.yaml` | `configs/values.yaml` |
| Jobs | `app/jobs/` + `config/schedule.rb` (sidekiq) / `que_schedule.yml` (que) | `JobWithOptions` в Go-коде. Для letsgo `schedule.CronScheduler` не распознаётся (warning). `app.letsgo.yaml` → `controllers.scheduler.tasks` — skill-сканер парсит, slo-kit пока нет. | — | — |

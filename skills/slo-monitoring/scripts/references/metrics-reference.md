# Справочник метрик для slo-kit

Полная спецификация метрик Prometheus по платформам.

---

## HTTP — Входящие запросы (Inbound)

### ecomtech-letsgo (Go / letsgo)

**Метрика:** `http_incoming_requests_total`, `http_incoming_requests_duration_*`

**Лейблы:** `env`, `namespace`, `service`, `method`, `exported_endpoint`, `code`

**ВАЖНО:** `exported_endpoint` (не `endpoint`!)

```promql
# Availability (error ratio)
sum(increase(http_incoming_requests_total{
  namespace="cs-com-hub", service="tracker",
  method="GET", exported_endpoint="/api/v1/tickets/{id}",
  code=~"5.."
}[{{.window}}]))
/
sum(increase(http_incoming_requests_total{
  namespace="cs-com-hub", service="tracker",
  method="GET", exported_endpoint="/api/v1/tickets/{id}"
}[{{.window}}]))

# Latency
sum(rate(http_incoming_requests_duration_sum{
  namespace="cs-com-hub", service="tracker",
  method="GET", exported_endpoint="/api/v1/tickets/{id}",
  code=~"2.."
}[30s]))
/
sum(rate(http_incoming_requests_duration_count{
  namespace="cs-com-hub", service="tracker",
  method="GET", exported_endpoint="/api/v1/tickets/{id}",
  code=~"2.."
}[30s]))
```

### ecom-ruby / kuper-ruby (Ruby)

**Метрика:** `sbmtapp_http_request_duration_seconds_*`

**Лейблы:** `namespace`, `service`, `method`, `exported_endpoint` (или `controller`+`action` для kuper-ruby), `code`

### kuper-go / kuper-python (Go / Python)

**Метрика:** `http_requests_total`, `http_request_duration_seconds_*`

**Лейблы:** `method`, `handler`, `code`

---

## HTTP — Исходящие запросы (Outbound / External)

### ecomtech-letsgo — нативный `outgoing` тип

**Метрики:** `http_outgoing_requests_total`, `http_outgoing_requests_duration_*`

**Лейблы:** `namespace`, `service`, `exported_endpoint` (полный URL с хостом), `code`, `method`, `job` (scrape job = имя сервиса, **не целевой сервис**)

**Важно:** `job` label всегда равен имени сервиса-источника (scrape job), а не целевому сервису. Целевой сервис идентифицируется только по `exported_endpoint`. `oif` тип НЕ работает — он хардкожен на `oif_duration` метрику. Используйте нативный `outgoing` тип.

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
- `name` (обязательно): идентификатор
- `description` (обязательно): описание
- `endpoint` (обязательно): regex для `exported_endpoint` (полный URL, `.*` матчит хост)
- `method` (опционально): HTTP метод

Генерирует 2 SLI: availability (5xx errors) + latency (threshold-based).

```promql
# Availability (автогенерируется)
sum(increase(http_outgoing_requests_total{
  namespace="ts", service="ticket-system",
  exported_endpoint=~".*/api/market/v1/userConductor/userProfile/find",
  code=~"5.."
}[{{.window}}]))
```

**`exported_endpoint` содержит полный URL:** `http://api.prod.lan/api/market/v1/userConductor/userProfile/find`. Используйте regex с `.*` префиксом для матчит host часть.

## Kafka Consumers

### ecomtech-letsgo

**Метрика:** `event_consumer_handle_duration_*` (только latency, без availability)

**Лейблы:** `namespace`, `service`, `topic`, `group`

**Важно:** letsgo генерирует только latency SLI для consumers. Availability SLI не создаётся — метрики ошибок обработки отсутствуют. Lag monitoring также не поддерживается — `is_lag_enabled: true` даёт ошибку валидации. Warning линтера об обязательности `is_lag_enabled` можно игнорировать.

```promql
sum(rate(event_consumer_handle_duration_sum{
  namespace="cs-com-hub", service="tracker",
  topic="kuper.k-ecom-prod.ecom.megamarket.fct.orders.0"
}[30s]))
/
sum(rate(event_consumer_handle_duration_count{
  namespace="cs-com-hub", service="tracker",
  topic="kuper.k-ecom-prod.ecom.megamarket.fct.orders.0"
}[30s]))
```

### ecom-ruby (Space / Karafka)

**Метрика:** `ruby_kafka_consumer_batch_messages_duration_seconds_*` (только latency)

**Лейблы:** `topic`

### kuper-ruby

**Метрики:** `kafka_consumer_messages_total` (availability), `kafka_consumer_duration_seconds_*` (latency)

### kuper-go

**Метрики:** `kafka_consume_total` (availability), `kafka_consume_duration_seconds_*` (latency)

---

## Background Jobs

### ecom-ruby (que)

**Метрики:** `que_jobs_failed_total`, `que_jobs_executed_total` (availability), `que_job_runtime_seconds_*` (latency)

**Лейблы:** `queue`, `worker`, `namespace`

```promql
# Availability
sum(increase(que_jobs_failed_total{
  namespace="cs-com-hub", queue="default", worker="OrderWorker"
}[{{.window}}]))
/
sum(increase(que_jobs_executed_total{
  namespace="cs-com-hub", queue="default", worker="OrderWorker"
}[{{.window}}]))
```

### kuper-ruby (sidekiq)

**Метрики:** `sidekiq_jobs_failed_total`, `sidekiq_jobs_executed_total` (availability), `sidekiq_job_runtime_seconds_*` (latency)

**Лейблы:** `queue`, `worker`

### kuper-go

**Метрики:** `workers_job_failed_total`, `workers_job_total` (availability), `workers_job_duration_seconds_*` (latency)

**Лейблы:** `queue`

### ecomtech-letsgo

**Метрики:** `background_jobs_failure` / `background_jobs_total` (availability), `background_jobs_duration_*` (latency)

**Лейблы:** `namespace`, `service`, `name`

Нативный `job` тип поддерживается. Поле `queue` в конфиге маппится на label `name` метрик.

```yaml
groups:
  background-jobs:
    description: Фоновые задачи
    consists_of:
      jobs:
        - queue: cleanupWorkLogs
```

```promql
# Availability
sum(increase(background_jobs_failure{
  namespace="ts", service="ticket-system", name="cleanupWorkLogs"
}[{{.window}}]))
/
sum(increase(background_jobs_total{
  namespace="ts", service="ticket-system", name="cleanupWorkLogs"
}[{{.window}}]))

# Latency
sum(rate(background_jobs_duration_sum{
  namespace="ts", service="ticket-system", name="cleanupWorkLogs"
}[30s]))
/
sum(rate(background_jobs_duration_count{
  namespace="ts", service="ticket-system", name="cleanupWorkLogs"
}[30s]))
```

**Примечание:** Сканер `slo-kit lint` ищет вызовы `JobWithOptions` в Go-коде. Если сервис использует другой паттерн регистрации jobs (например `schedule.CronScheduler` + `EnableCleanupWorkLogs`), job не будет найден автоматически — это warning, не ошибка.

---

## GraphQL

### ecom-ruby / kuper-ruby (Ruby)

**Метрики:** `ruby_graphql_requests_total` (availability), `ruby_graphql_request_duration_seconds_*` (latency)

**Лейблы:** `operation_name`, `operation_status`

### Node.js

**Метрики:** `graphql_queries_responded`, `graphql_queries_encountered_errors` (availability), `graphql_total_request_time_*` (latency)

**Лейблы:** `operationName` (camelCase!), `success`

---

## Ключевые моменты

1. **`exported_endpoint` вместо `endpoint`** — во всех HTTP метриках ecom-tech используется лейбл `exported_endpoint`. В конфиге указывайте только `handler` — генератор маппит автоматически.

2. **Время окон** — для latency используется `[30s]` внутри запроса и `{{.window}}` для SLO периода

3. **Code filtering** — для успешных запросов `code=~"2.."`, для ошибок `code=~"5.."`

4. **External integrations** — используйте нативный `outgoing` тип для `http_outgoing_requests_*` метрик (letsgo). `oif` тип работает только с `oif_duration` метрикой. `job` label = scrape job (имя сервиса), не целевой сервис — фильтрация только по `exported_endpoint`.

5. **`allow_arbitrary_window`** — валидатор `custom` требует `{{.window}}` во всех `[...]` селекторах. Для latency queries с фиксированным окном `[30s]` внутри (subquery) добавляйте `allow_arbitrary_window: true`. Пример:
   ```yaml
   custom:
     - name: my-latency
       description: Latency with fixed 30s subquery
       allow_arbitrary_window: true
       error_query: |
         sum_over_time(count((... > 2.0)[{{.window}}:30s]))
       total_query: |
         sum_over_time(count(vector(1))[{{.window}}:30s])
   ```

6. **ecom-ruby vs kuper-ruby** — оба используют `sbmtapp_http_*`, но Kafka метрики разные: `ruby_kafka_consumer_batch_*` (Space) vs `kafka_consumer_*` (Kuper). Jobs: `que_*` (Space) vs `sidekiq_*`/`schked_*` (Kuper)

7. **Сервисы с кастомными метриками** — если сервис экспортирует нестандартные метрики (например `gi_*`), используйте `custom` и `custom_latency` SLI типы с явными PromQL запросами

8. **consists_of ключи** — множественное число: `consumers` (не `consumer`), `jobs` (не `job`)

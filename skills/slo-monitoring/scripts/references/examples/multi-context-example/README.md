# Многоконтекстная конфигурация slo-kit

## Описание

Конфиг можно разбить на несколько файлов-контекстов. Каждый файл описывает отдельную функциональную область сервиса — по аналогии с bounded context из DDD.

Например, в сервисе телефонии контекстами могут быть:
- `calls` — звонки
- `dispatch` — маршрутизация
- `billing` — биллинг

## Структура

```
configs/slo-kit/
├── slo-kit.yaml           # основной конфиг с метаданными
└── slo-kit/               # директория контекстов
    ├── calls.yaml
    ├── dispatch.yaml
    └── billing.yaml
```

## Основной файл (slo-kit.yaml)

Содержит общие метаданные сервиса:

```yaml
# configs/slo-kit/slo-kit.yaml
profile: ecomtech-letsgo
namespace: cs-com-hub
service: phone-service
product: cs-telecom-platform
team: team-telecom
cost_centre: T080

alerts:
  enabled: true
  notify:
    - team-telecom
    - oncall
  min_severity: warning

# Контексты автоматически загружаются из директории ./slo-kit/
```

## Файлы контекстов

Каждый контекст содержит секцию `groups` и опционально переопределяет team:

### calls.yaml

```yaml
# configs/slo-kit/slo-kit/calls.yaml
# Контекст: звонки
# Функциональная область: управление звонками

team: team-calls  # дефолтный team для всех групп контекста

groups:
  calls-setup:
    description: Настройка звонков
    labels:
      serviceTier: "1"
    # team не указан → team-calls из контекста
    defaults:
      latency_limit: "0.5"
    consists_of:
      custom:
        - name: call-setup-avl
          description: Доступность настройки звонков
          error_query: sum(rate(call_errors{type="setup"}[{{.window}}]))
          total_query: sum(rate(call_total{type="setup"}[{{.window}}]))

        - name: call-setup-latency
          description: Задержка настройки звонков (500ms порог)
          error_query: |
            sum_over_time(count(((sum(rate(call_setup_duration_sum[30s]))
          /sum(rate(call_setup_duration_count[30s])))
          OR on() vector(0))
          > 0.5)
        [{{.window}}:30s])
          total_query: sum_over_time(count(vector(1))[{{.window}}:30s])

  calls-active:
    description: Активные звонки
    labels:
      serviceTier: "1"
      team: team-calls-core  # переопределение team для этой группы
    defaults:
      latency_limit: "0.3"
    consists_of:
      custom:
        - name: active-calls-availability
          description: Доступность активных звонков
          error_query: sum(rate(call_drops_unexpected[{{.window}}]))
          total_query: sum(rate(call_active_total[{{.window}}]))
```

### dispatch.yaml

```yaml
# configs/slo-kit/slo-kit/dispatch.yaml
# Контекст: маршрутизация
# Функциональная область: маршрутизация вызовов

team: team-dispatch

groups:
  routing:
    description: Маршрутизация вызовов
    labels:
      serviceTier: "1"
    defaults:
      latency_limit: "0.1"  # Маршрутизация должна быть быстрой
    consists_of:
      custom:
        - name: routing-availability
          description: Доступность маршрутизации
          error_query: sum(rate(routing_errors[{{.window}}]))
          total_query: sum(rate(routing_total[{{.window}}]))

        - name: routing-latency
          description: Задержка маршрутизации (100ms порог)
          error_query: |
            sum_over_time(count(((sum(rate(routing_duration_sum[10s]))
          /sum(rate(routing_duration_count[10s])))
          OR on() vector(0))
          > 0.1)
        [{{.window}}:10s])
          total_query: sum_over_time(count(vector(1))[{{.window}}:10s])

  failover:
    description: Failover механизмы
    labels:
      serviceTier: "1"
    consists_of:
      custom:
        - name: failover-success-rate
          description: Успешность failover
          error_query: sum(rate(failover_failures[{{.window}}]))
          total_query: sum(rate(failover_attempts[{{.window}}]))
```

### billing.yaml

```yaml
# configs/slo-kit/slo-kit/billing.yaml
# Контекст: биллинг
# Функциональная область: тарификация и учёт

team: team-billing

groups:
  rating:
    description: Тарификация
    labels:
      serviceTier: "2"  # Биллинг менее критичен чем звонки
    defaults:
      latency_limit: "1.0"
    consists_of:
      custom:
        - name: rating-availability
          description: Доступность тарификации
          error_query: sum(rate(rating_errors[{{.window}}]))
          total_query: sum(rate(rating_total[{{.window}}]))

        - name: rating-accuracy
          description: Точность тарификации (нулевые ошибки)
          error_ratio_query: sum(rate(rating_balance_errors[{{.window}}]))

  invoicing:
    description: Выставление счётов
    labels:
      serviceTier: "3"
    defaults:
      latency_limit: "5.0"
    consists_of:
      custom:
        - name: invoice-generation
          description: Генерация счётов
          error_query: sum(rate(invoice_generation_errors[{{.window}}]))
          total_query: sum(rate(invoice_generation_total[{{.window}}]))
```

## Использование

### Генерация sloth.yaml

```bash
# Основной конфиг читает все контексты из ./slo-kit/
slo-kit generate sloth --in configs/slo-kit/slo-kit.yaml --output-dir configs/slo-kit
```

### Проверка конфигурации

```bash
# Линтер проверит все контексты
slo-kit lint --spath configs/slo-kit
```

## Преимущества многоконтекстной конфигурации

1. **Разделение ответственности** — каждая команда работает со своим контекстом
2. **Модульность** — легче поддерживать и тестировать
3. **Гибкость** — разные SLA для разных функциональных областей
4. **Масштабируемость** — можно добавлять новые контексты без изменения существующих

## Ограничения

- Каждый контекст — отдельный YAML файл
- Метаданные (namespace, service, product) задаются только в основном файле
- Alerts настраиваются глобально (в основном файле)
- Для переопределения alerts на уровне группы используйте `alerts.enabled: false` в группе

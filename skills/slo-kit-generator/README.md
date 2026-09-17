# slo-kit-generator

База знаний и workflow для создания `slo-kit.yaml` конфигураций SLI/SLO мониторинга микросервисов.

## Что это

Skill содержит справочники метрик, схему YAML, примеры конфигов и пошаговый workflow для агента. Skill не включает CLI-инструмент — агент использует внешний `slo-kit` CLI для сканирования кода и генерации артефактов, а `slo-kit.yaml` пишет напрямую.

## Workflow

```
1. Определить профиль (по платформе и языку сервиса)
2. slo-kit lint --spath <service>     → сканирование кода
3. Изучить метрики (docs/metrics.md, ast-index)
4. Написать slo-kit.yaml              → напрямую, по схеме и примерам
5. slo-kit generate                    → slo.yaml + alerts.yaml / CRDs
6. slo-kit lint                        → валидация
```

## Профили

| Профиль | Платформа | Язык | Нативные типы |
|---|---|---|---|
| `ecomtech-letsgo` | ecom-tech | Go (letsgo) | http, consumer, job, outgoing, oif, iif, custom, custom_latency |
| `ecom-ruby` | ecom-tech (Space) | Ruby | http, graphql, consumer, job (que), custom, custom_latency |
| `kuper-go` | Kuper | Go | http, grpc, consumer, job, custom, custom_latency |
| `kuper-ruby` | Kuper | Ruby | http, grpc, graphql, consumer, job, outboxes, custom, custom_latency |
| `kuper-python` | Kuper | Python | http, grpc, consumer, custom, custom_latency |

Подробнее: [profiles-reference.md](references/profiles-reference.md)

## Справочники

- [Полная схема slo-kit.yaml](references/slo-kit-schema.md) — все поля, типы индикаторов, severity, inheritance
- [Профили и метрики по платформам](references/profiles-reference.md) — какая метрика у какого профиля
- [Справочник метрик Prometheus](references/metrics-reference.md) — PromQL примеры для каждого типа
- [Особенности ecom-tech профиля](references/ecom-tech-profile.md) — severity cap, формат вывода, ограничения

## Примеры

- [slo-kit-example.yaml](references/examples/slo-kit-example.yaml) — HTTP + consumer
- [external-integrations-example.yaml](references/examples/external-integrations-example.yaml) — исходящие HTTP (custom SLI)
- [background-jobs-example.yaml](references/examples/background-jobs-example.yaml) — фоновые задачи
- [multi-context-example/](references/examples/multi-context-example/) — многоконтекстная конфигурация
- [sloth-example.yaml](references/examples/sloth-example.yaml) — пример сгенерированного sloth.yaml
- [makefile-example](references/examples/makefile-example) — Makefile для CI

## Интеграция с slo-kit CLI

```bash
# Docker
docker pull dreg.sbmt.io/content/slo-kit:latest

# Из исходников
go build -o slo-kit ./cmd/slo-kit
```

Команды:

```bash
slo-kit generate --in slo-kit.yaml --out slo.yaml --alerts alerts.yaml  # PaaS
slo-kit generate sloth --in slo-kit.yaml --output-dir .                 # Kubernetes CRD
slo-kit generate vmrules --in slo-kit.yaml --output-dir .               # VMRules
slo-kit lint --spath=/path/to/service --in slo-kit.yaml                 # Валидация
slo-kit overview --in slo-kit.yaml                                      # Обзор групп
```

## Ссылки

- [Документация slo-kit](https://gitlab.sbmt.io/dev-ashunicorn-team/slo-kit)
- [Sloth GitHub](https://github.com/slok/sloth)

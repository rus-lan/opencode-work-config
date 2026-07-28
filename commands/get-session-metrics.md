---
name: get-session-metrics
description: Получение метрик текущей сессии из aistats.
agent: build
subtask: true
---

## Использование

/get-session-metrics
/get-session-metrics --verbose

## Описание

Фетчит метрики из aistats (`aistats report --format json`), форматирует их в JSON и выводит в понятном виде. Используется плагинами и интеграциями (Herdr).

## Поля вывода

| Поле | Описание |
|------|----------|
| `model` | Имя текущей модели |
| `duration` | Длительность сессии (человеко-читаемый формат) |
| `tokens_in` | Входящие токены |
| `tokens_out` | Исходящие токены |
| `cost` | Стоимость в USD |
| `status` | Статус сессии (active/unknown) |

## Зависимости

- `aistats` CLI (опционально — если не установлен, возвращает базовую информацию)
- `jq` для парсинга JSON (опционально)

## Пример

```json
{
    "model": "qwen3.5-122b",
    "duration": "12m 34s",
    "tokens_in": "12K",
    "tokens_out": "8K",
    "cost": "$0.02",
    "status": "active"
}
```

## Связанные команды

- `/herdr-status` — отображение метрик в Herdr UI
- `/context` — метрики контекста и лимиты
- `/m` — session metrics dashboard (get_metrics tool)
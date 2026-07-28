# Herdr Agent Metrics Integration

## Обзор

Плагин `herdr-agent-state.js` отправляет полную информацию о сессии агента в Herdr UI:

- ✅ **Модель агента** — имя используемой модели
- ✅ **Длительность сессии** — время работы в читаемом формате
- ✅ **Использование токенов** — входящие/исходящие токены
- ✅ **Кэш** — чтение/запись кэша (если доступно)
- ✅ **Расходы** — текущие затраты в USD (если доступны)
- ✅ **Статус** — активная/неактивная сессия
- ✅ **Количество активных сабагентов** — в реальном времени

## get_metrics — Custom Tool

Плагин регистрирует кастомный инструмент `get_metrics`, доступный в любой сессии:

```
get_metrics — возвращает markdown dashboard и JSON с метриками сессии
(длительность, токены, стоимость, модель, статус, активные сабагенты)
```

Используй это в промптах: "покажи метрики сессии" или команда `/m`.

## Как это работает

### Автоматическое обновление

Плагин автоматически отслеживает события сессии:

1. **session.created** — начало сессии, сбор начальных метрик
2. **session.updated** — обновление модели/параметров
3. **session.idle** — конец сессии, финальные метрики
4. **Периодическое обновление** — каждые 10 секунд во время активной сессии

### Файл метрик

Метрики также сохраняются в `~/.config/opencode/metrics.json` для внешних интеграций:
```json
{
  "state": "working",
  "model": "qwen3.5-122b",
  "duration": "12m 34s",
  "tokens_total": 20000,
  "cost": 0.02,
  "subagents": 3,
  "timestamp": 1712345678
}
```

### Интеграция с aistats

Если установлен `aistats`, плагин автоматически собирает метрики:

```bash
# Проверка наличия aistats
which aistats

# Получение метрик
aistats report --format json
```

Метрики включают:
- `tokens.input` — входящие токены
- `tokens.output` — исходящие токены
- `tokens.cacheRead` — чтение кэша
- `tokens.cacheWrite` — запись кэша
- `costUsd` — текущие расходы
- `durationMs` — длительность сессии

## Команды

### `/herdr-status`

Показывает и обновляет метрики текущей сессии в Herdr UI.

```bash
/herdr-status
/herdr-status --verbose
/herdr-status --watch
```

### `/get-session-metrics`

Получение сырых метрик в JSON-формате.

```bash
/get-session-metrics
```

### `/context`

Показывает метрики использования контекста и лимиты модели.

```bash
/context
/context --watch
/context --limits
```

### `/m`

Быстрый вызов `get_metrics` — session metrics dashboard.

```bash
/m
```

## Отображение в Herdr UI

Информация об агенте отображается в:

1. **Workspace label** — показывает статус агента (`● working` / `○ idle` / `⚠ blocked`)
2. **Pane metadata** — модель и кастомный статус через `report-agent`
3. **Tab information** — если настроено в конфигурации

### Проверка статуса

```bash
herdr workspace list
herdr pane get <pane_id>
herdr pane current
```

## Конфигурация

### Плагины

Плагин автоматически загружается из:
```
~/.config/opencode/plugins/herdr-agent-state.js
```

### Переменные окружения

Для работы внутри Herdr панели требуются:
- `HERDR_ENV=1` — флаг запуска внутри Herdr
- `HERDR_SOCKET_PATH` — путь к сокету Herdr
- `HERDR_PANE_ID` — ID текущей панели

Если переменные не установлены, плагин работает в CLI-режиме, используя `herdr` команду для отправки метрик.

## Взаимодействие с другими компонентами

| Компонент | Роль |
|-----------|------|
| `guard.sh` | Защита от опасных compound-команд (rm, force-push) — не влияет на метрики |
| `aistats.js` (plugin) | Сбор метрик токенов и стоимости при завершении сессии |
| `context7` (MCP) | Проверка API библиотек — не связан с метриками |
| `pre-commit.sh` | Валидация перед коммитом — не связан с метриками |
| `metrics.json` | Runtime-файл с текущими метриками сессии |

## Обновление

### Перезагрузка конфигурации Herdr

```bash
herdr server reload-config
```

### Переустановка интеграции

```bash
herdr integration uninstall opencode
herdr integration install opencode
```

## Устранение проблем

### Метрики не отображаются

1. Проверьте, запущен ли Herdr: `herdr status`
2. Проверьте, запущен ли opencode внутри Herdr: `herdr pane current`
3. Убедитесь, что плагин загружен: `herdr integration status | grep opencode`

### Ошибки сбора метрик

1. Проверьте наличие aistats: `which aistats`
2. Проверьте логи Herdr: `tail -f ~/.config/herdr/herdr-server.log`

### Статус "unknown"

1. Перезапустите opencode
2. Убедитесь, что плагин отправляет события
3. Проверьте логи opencode

## Примеры метрик

- **Длительность**: `12m 34s`, `1h 23m 45s`, `0s`
- **Токены**: `12K`, `1.5M`, `0`
- **Расходы**: `$0.02`, `$0.0045`, `$0.00`

Полная строка статуса:
```
● 12m 34s | 12K/8K tokens | $0.02 | agents:3 | qwen3.5-122b
```

## Будущие улучшения

- [ ] Интеграция с rate limits моделей
- [ ] Предупреждения о приближении к лимитам
- [ ] Историческая статистика по сессиям
- [ ] Кастомизация формата отображения
- [ ] Экспорт метрик в внешние системы мониторинга

## Ссылки

- [Herdr Documentation](https://herdr.dev)
- [Opencode Configuration](./opencode.json)
- [aistats MCP](./aistats/index.md)
- [Commands: get-session-metrics](./commands/get-session-metrics.md)
- [Commands: herdr-status](../commands/herdr-status.md)
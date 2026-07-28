# Context Metrics Skill

Скилл для мониторинга и управления метриками использования контекста в opencode.

## Установка

Скилл уже находится в `~/.config/opencode/skills/context-metrics/`

Добавьте в `opencode.json`:

```json
{
  "skills": {
    "enabled": [
      "context-metrics"
    ]
  }
}
```

## Использование

### Команды

```bash
# Показать метрики контекста
context-metrics

# Непрерывный мониторинг (каждые 30 сек)
context-metrics watch

# Проверка лимитов
context-metrics limits

# Показать effort
context-metrics effort
```

### Через opencode

```
/context
/context watch
/context limits
/context effort
```

## Функции

- ✅ Отображение текущего использования контекста
- ✅ Показ rate limits (часовые/дневные/недельные/месячные)
- ✅ Отображение effort информации
- ✅ Умные предупреждения о приближении к лимитам
- ✅ Рекомендации по оптимизации

## Интеграция

Скилл автоматически работает с конфигурацией из `opencode.json` и использует метрики из aistats.

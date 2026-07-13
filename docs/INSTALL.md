# Установка opencode с нуля

Полная инструкция по настройке opencode на чистом компьютере.

## Требования

- Go 1.24+
- Node.js 18+
- git
- SSH ключ для доступа к GitHub

## Шаг 1: Установить opencode

```bash
# Через npm
npm install -g @opencode/opencode

# Или через bun
bun add -g @opencode/opencode
```

## Шаг 2: Клонировать конфигурацию

```bash
git clone git@github.com:rus-lan/opencode-work-config.git ~/.config/opencode
```

## Шаг 3: Настроить переменные окружения

```bash
# Скопировать пример
cp ~/.config/opencode/.env.example ~/.config/opencode/.env

# Отредактировать с вашими ключами
nano ~/.config/opencode/.env
```

Заполните переменные:

```bash
# Qwen models
ECOM_QWEN35_122b_TOKEN=your_token_here
ECOM_QWEN36_35b_TOKEN=your_token_here

# DeepSeek models
ECOM_DEEPSEEL4_FLASH_MAX_TOKEN=your_token_here
ECOM_DEEPSEEL4_FLASH_TOKEN=your_token_here

# Other models
ECOM_QWEN35_122b_NO_THINK_TOKEN=your_token_here
ECOM_QWEN36_35b_NO_THINK_TOKEN=your_token_here
ECOM_GIGA3_10b_TOKEN=your_token_here
```

## Шаг 4: Установить зависимости

```bash
cd ~/.config/opencode
npm install
```

## Шаг 5: Установить дополнительные утилиты

```bash
# mapps (multi-repo workspace)
go install github.com/rus-lan/multiApps/cmd/mapps@latest

# graphify (knowledge graph) - опционально
uv tool install graphifyy
```

## Шаг 6: Проверить работу

```bash
# Запустить opencode
opencode

# Проверить скиллы
# В интерактивной сессии попробуйте:
# /caveman
# /grill-me
# /mapps
```

## Структура конфигурации

```
~/.config/opencode/
├── opencode.json           # Основная конфигурация
├── agents/                 # Агенты
│   ├── reviewer.md         # Code review (qwen3.5-122b)
│   ├── desearch-researcher.md  # Web research (deepseek-v4-flash:max)
│   ├── desearch-synthesizer.md # Synthesis (qwen3.6-35b)
│   ├── go-dev.md           # Go development (qwen3.6-35b)
│   ├── react-dev.md        # React development (qwen3.6-35b)
│   ├── rust-dev.md         # Rust development (qwen3.6-35b)
│   ├── ui-designer.md      # UI design (qwen3.6-35b)
│   └── explore.md          # Code exploration (qwen3.6-35b-no-think)
├── skills/                 # Скиллы
│   ├── caveman/            # Режим кратких ответов
│   ├── grill-me/           # Интерактивный допрос
│   ├── mapps/              # Multi-repo workspace
│   ├── graphify/           # Knowledge graph
│   ├── desearch/           # Web research
│   └── design/             # UI/UX design
├── commands/               # Кастомные команды
│   └── mapps.md
├── plugins/                # Плагины
│   ├── aistats.js
│   └── herdr-agent-state.js
└── CLAUDE.md               # Глобальные правила
```

## Обновление конфигурации

```bash
cd ~/.config/opencode
git pull origin main
npm install
```

## Доступные команды

### Скиллы

| Команда | Описание |
|---------|----------|
| `/caveman` | Режим кратких ответов (lite/full/ultra) |
| `/grill-me` | Интерактивный допрос плана/решений |
| `/mapps` | Много-репозиторный workspace |
| `/graphify` | Knowledge graph |
| `/desearch` | Веб-исследование |
| `/design` | UI/UX дизайн |

### Агенты

Агенты запускаются автоматически через `task` инструмент в зависимости от задачи:

- **reviewer** — code review
- **desearch-researcher** — веб-поиск
- **desearch-synthesizer** — синтез исследований
- **go-dev** — Go разработка
- **react-dev** — React разработка
- **rust-dev** — Rust разработка
- **ui-designer** — UI дизайн
- **explore** — навигация по коду

## Модельная конфигурация

| Агент | Модель | Fallback |
|-------|--------|----------|
| reviewer | qwen3.5-122b | qwen3.5-122b-no-think |
| desearch-researcher | deepseek-v4-flash:max | deepseek-v4-flash |
| desearch-synthesizer | qwen3.6-35b | qwen3.6-35b-no-think |
| go-dev | qwen3.6-35b | qwen3.6-35b-no-think |
| react-dev | qwen3.6-35b | qwen3.6-35b-no-think |
| rust-dev | qwen3.6-35b | qwen3.6-35b-no-think |
| ui-designer | qwen3.6-35b | qwen3.6-35b-no-think |
| explore | qwen3.6-35b-no-think | giga3-10b |

## Workflow

```
Phase 1: Research (parallel)
  ├─ desearch-researcher (multiple angles)
  └─ explore (codebase mapping)
           ↓
Phase 2: Synthesis
  └─ desearch-synthesizer
           ↓
Phase 3: Implementation (parallel)
  ├─ react-dev / go-dev / rust-dev
  └─ ui-designer
           ↓
Phase 4: Review Gate
  └─ reviewer (blocking)
```

## Troubleshooting

### SSH ключи

Убедитесь, что SSH ключ добавлен в ssh-agent:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

### Проверка доступа к GitHub

```bash
ssh -T git@github.com
```

### Ошибки npm

```bash
# Очистить кэш
npm cache clean --force

# Переустановить зависимости
rm -rf node_modules package-lock.json
npm install
```

## Ссылки

- [opencode docs](https://opencode.ai)
- [Конфигурация](https://github.com/rus-lan/opencode-work-config)
- [multiApps](https://github.com/rus-lan/multiApps)
- [graphify](https://github.com/safishamsi/graphify)

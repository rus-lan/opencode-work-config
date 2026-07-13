# Opencode Work Configuration

Рабочая конфигурация opencode с агентами, скиллами и workflow.

## Быстрая установка

```bash
# 1. Клонировать конфигурацию
git clone git@github.com:rus-lan/opencode-work-config.git ~/.config/opencode

# 2. Установить переменные окружения (см. .env.example)
cp ~/.config/opencode/.env.example ~/.config/opencode/.env
# Отредактируйте .env с вашими API ключами

# 3. Установить зависимости
cd ~/.config/opencode
npm install

# 4. Установить дополнительные утилиты
curl -fsSL https://raw.githubusercontent.com/rus-lan/multiApps/main/install.sh | sh

# 5. Готово! Запустите opencode в любом проекте
opencode
```

## Структура

```
~/.config/opencode/
├── opencode.json           # Основная конфигурация
├── agents/                 # Конфигурация агентов
│   ├── desearch-researcher.md
│   ├── desearch-synthesizer.md
│   ├── explore.md
│   ├── go-dev.md
│   ├── react-dev.md
│   ├── reviewer.md
│   ├── rust-dev.md
│   └── ui-designer.md
├── skills/                 # Встроенные скиллы
│   ├── caveman/
│   ├── desearch/
│   ├── design/
│   ├── graphify/
│   ├── grill-me/
│   └── ...
├── commands/               # Кастомные команды
│   └── mapps.md
└── CLAUDE.md               # Глобальные правила
```

## Переменные окружения

Создайте `~/.config/opencode/.env`:

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

## Агенты

| Агент | Модель | Назначение |
|-------|--------|------------|
| reviewer | qwen3.5-122b | Code review |
| desearch-researcher | deepseek-v4-flash:max | Веб-исследования |
| desearch-synthesizer | qwen3.6-35b | Синтез исследований |
| go-dev | qwen3.6-35b | Go разработка |
| react-dev | qwen3.6-35b | React разработка |
| rust-dev | qwen3.6-35b | Rust разработка |
| ui-designer | qwen3.6-35b | UI дизайн |
| explore | qwen3.6-35b-no-think | Поиск по коду |

## Скиллы

| Скилл | Команда | Назначение |
|-------|---------|------------|
| caveman | `/caveman` | Режим кратких ответов |
| grill-me | `/grill-me` | Интерактивный допрос |
| mapps | `/mapps` | Много-репозиторный workspace |
| graphify | `/graphify` | Knowledge graph |
| desearch | `/desearch` | Веб-исследование |
| design | `/design` | UI/UX дизайн |

## Workflow

```
Phase 1: Research (parallel)
  ├─ desearch-researcher (angle 1)
  ├─ desearch-researcher (angle 2)
  └─ explore (codebase mapping)
           ↓
Phase 2: Synthesis
  └─ desearch-synthesizer
           ↓
Phase 3: Implementation (parallel)
  ├─ react-dev (frontend)
  ├─ go-dev (backend)
  └─ ui-designer (design)
           ↓
Phase 4: Review Gate
  └─ reviewer (blocking)
```

## Обновление конфигурации

```bash
# Обновить из remote
cd ~/.config/opencode
git pull origin main

# Переустановить зависимости
npm install
```

## Перенос на новый компьютер

```bash
# Полный перенос
git clone git@github.com:rus-lan/opencode-work-config.git ~/.config/opencode
cp ~/.config/opencode/.env.example ~/.config/opencode/.env
# Отредактируйте .env
cd ~/.config/opencode && npm install
curl -fsSL https://raw.githubusercontent.com/rus-lan/multiApps/main/install.sh | sh
```

## Лицензия

MIT

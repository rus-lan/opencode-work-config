---
name: opencode-implementer
description: Надёжная работа с opencode как исполнителем/ревьюером под оркестрацией Claude (модели Z.AI Coding Plan) — конфиг и запуск без зависаний и лишних суб-агентов
version: 1.0.0
---

# opencode как исполнитель (схема `claude (оркестратор) → opencode`)

Когда Claude-оркестратор делегирует код-работу opencode (исполнитель) + read-only ревью, соблюдать всё ниже — иначе opencode виснет или уходит во внутренние суб-агенты вместо прямой работы.

## Модели — только подписка Z.AI Coding Plan, НЕ pay-API

- Провайдер `zai-coding-plan/` = **подписка**. `zai/` = поштучный pay-API (обычно НЕ авторизован — не использовать). Проверка: `cat ~/.local/share/opencode/auth.json` → должен быть провайдер `zai-coding-plan`.
- Исполнитель: `zai-coding-plan/glm-5-turbo`. Ревьюер: `zai-coding-plan/glm-5.2`. Инвариант: **ревьюер ≠ модель исполнителя**.
- **`glm-5v-turbo` НЕ входит в Coding Plan** — API отдаёт «your current subscription plan does not yet include access to GLM-5V-Turbo», opencode бесконечно ретраит и делает 0 работы. Список рабочих: `opencode models | grep glm`. Проверить доступ модели: `opencode run --model zai-coding-plan/<m> "reply READY"`.

## Обязательный конфиг `~/.config/opencode/opencode.jsonc`

opencode НЕ должен порождать собственных суб-агентов; MCP, вешающие bootstrap, — отключить:

```jsonc
{ "$schema": "https://opencode.ai/config.json",
  "agent": { "build": { "permission": { "task": "deny" } },
             "plan":  { "permission": { "task": "deny" } } } }
```

- `permission.task: "deny"` у `build`+`plan` = tool `task` запрещён = **нет спавна суб-агентов**. Иначе `build` уходит в `agent=general mode=subagent` (десятки вызовов) и виснет; `plan` — в `agent=explore`. Промпт-инструкция «не делегируй» НЕнадёжна — нужен гейт на уровне конфига.
- **Инвариант «плоский запуск» (belt-and-suspenders):** opencode-исполнитель/ревьюер обязан работать ПЛОСКО — не спавнить собственных суб-агентов и не запускать вложенный opencode, ДАЖЕ ЕСЛИ конфиг opencode это разрешает (напр. на машине без настроенного `permission.task: "deny"`). Запрет всегда прописывается текстом в самом промпте запуска — не полагаться только на конфиг.
- **Context7 (`type: "remote"`)** — настроен в opencode.json как remote MCP. Используй его для проверки API библиотек, версий пакетов и документации. Remote MCP (в отличие от local/npx) не создаёт дочерних процессов и не вешает старт. Для spec-driven правок где docs не нужны — можно пропустить.

## Запуск

- ВСЕГДА: спека в **ФАЙЛ** (scratchpad) + **КОРОТКИЙ** промпт-ссылка. Исполнитель: `opencode run --model zai-coding-plan/glm-5-turbo --agent build --auto "Прочитай файл целиком <путь> и выполни. Делай сам."`. Ревьюер: `opencode run --model zai-coding-plan/glm-5.2 --agent plan "<короткий read-only промпт или ссылка на focus-файл>"`.
- **НИКОГДА длинный inline-промпт** через фоновый Bash — zsh-eval обёртка фонового запуска ломается/вешает bootstrap на длинном тексте со спецсимволами (симптом: процесс жив, `opencode.log` доходит до `init` и НИКОГДА не стримит, 0-байт вывод, файлы не тронуты).
- **ЛОВУШКА ревьюера: `plan`-агент (без `--auto`) авто-ОТКЛОНЯЕТ чтение external-dir** (`permission requested: external_directory ... auto-rejecting`) — focus/спека-файл для РЕВЬЮЕРА должен лежать ВНУТРИ проекта (напр. gitignored `.research/<topic>/`), НЕ в `/tmp`-scratchpad. Исполнитель (`build --auto`) external-пути авто-апрувит, ему `/tmp` ок; ревьюер — нет.
- Фон (`run_in_background`) + `dangerouslyDisableSandbox: true` (нужна сеть к z.ai). В промпте: git ЗАПРЕТИТЬ, набор файлов ограничить, «делай сам, не делегируй, не создавай суб-агентов». Ревьюеру дополнительно: запретить Edit/Write/исполняющий Bash/любые git-мутации.
- После impl: `git status` / `git diff --stat` — тронуты только нужные файлы + НЕТ бинарников-артефактов (напр. `apps/*/server` от `go build -o`); коммит/пуш — только оркестратор, никогда opencode.

## Context7 MCP

Context7 настроен как remote MCP в opencode.json (`"mcp"."context7"`). Используй его:
- Для проверки актуальных сигнатур API библиотек
- Для уточнения версий пакетов
- Вместо гадания или полагания на training data

Не использовать context7 если:
- Задача чисто spec-driven (правки по готовой спеке)
- Кодовая база не использует внешние библиотеки с сомнительными API

## Диагностика зависания

- Симптом: процесс жив (`pgrep -af "opencode run"`), 0-байт вывод, целевые файлы не тронуты.
- Лог `~/.local/share/opencode/log/opencode.log`, `grep "<run-id>"`:
  - только `bootstrapping → init → cleanup` БЕЗ `message=stream` → встал на старте (длинный inline-промпт / MCP-хэнг / оверлоуд).
  - `agent=general|explore mode=subagent` → ушёл в суб-агентов (проверить, что `permission.task: "deny"` реально в конфиге).
  - `error ... temporarily overloaded` → транзиентный флап z.ai.
- Действие: `pkill -f "opencode run"` → пробой `opencode run ... "reply READY"` (проверить, что сервис отвечает) → релонч (короткий промпт + spec-файл).
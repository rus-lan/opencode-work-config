# harness-analytics

Скилл для агента: как считать аналитику собственного harness по локальной телеметрии
opencode. Отвечает на вопросы «что жрёт токены», «какие инструменты падают или тормозят»,
«работают ли скиллы и MCP», «почему агент тормозит».

Данных скилл не хранит: всё считает `duck-harness` (компонент `tools/duck-harness`).
Скилл даёт схему вьюх, готовые запросы, грабли и формат отчёта.

## Что внутри

| Раздел SKILL.md | Что даёт |
|---|---|
| Как обращаться | MCP `duck_query`/`duck_schema` как основной путь, CLI как запасной |
| Вьюхи `h` | 17 вьюх: сессии, модели, tool-вызовы, ошибки, скиллы, контекст, сабагенты, Code Mode, health MCP, самопроверки |
| Выгрузки `d` | Как файлы из `~/data/exports` становятся таблицами и как их джойнить с телеметрией |
| Метрики `m` | 19 вьюх E001: ТТМ, LT, Flow Efficiency, CR, DORA, деплои, инциденты, MTTR, CFR |
| Рецепты | Готовые SQL под частые вопросы |
| Грабли | 12 проверенных: схема V2, `cost = 0`, средняя латентность, отказы против сбоев |
| Отчёт | Формат среза `results/harness/harness-health-<дата>.md` |

## Требования

- `duck-harness` — источник данных. В тексте скилла путь
  `~/Documents/ECOM/mcps/duck-harness/bin/duck-harness`; после установки из
  `tools/duck-harness` бинарь лежит в `~/.local/share/duck-harness/bin/duck-harness` —
  поправьте путь под свою машину.
- MCP-сервер `duck-harness` (его ставит `install.sh` компонента `tools/duck-harness`)
  либо CLI.
- Выгрузки в `~/data/exports` — нужны только для схем `d` и `m`.

## Установка

Компонент `skills/harness-analytics` хаба `e001-ai-hub`:

```bash
curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fharness-analytics%2Finstall.sh/raw?ref=main" \
  | HARNESS_ANALYTICS_TOKEN="$GITLAB_TOKEN" sh
```

Скилл ложится в `~/.config/opencode/skills/harness-analytics/`; флаг `--claude` ставит
копию в `~/.claude/skills/`, `--uninstall` удаляет установленное.

На этом скилле работают команды `/health` и `/retro` из компонента
`commands/harness-commands`.

---
name: harness-analytics
version: 0.1.0
description: |
  Аналитика собственного harness по локальной телеметрии opencode (opencode.db):
  токены и стоимость сессий, latency и ошибки tool/MCP-вызовов, какие скиллы
  реально загружаются, что попадает в контекст, использование сабагентов,
  «harness health»-срез. Используй, когда спрашивают «что жрёт токены», «сколько
  стоит сессия/день», «какие инструменты падают или тормозят», «работают ли
  скиллы/MCP», «почему агент тормозит», «сделай срез по сессиям/телеметрии»,
  «harness health» — даже если слово DuckDB или SQL не звучит.
---

# harness-analytics

Telemetry-слой harness: read-only SQL по снимку `~/.local/share/opencode/opencode.db`.
Движок — `duck-harness` (DuckDB + sqlite-сканер), репозиторий `~/Documents/ECOM/mcps/duck-harness`.

## Как обращаться

1. **MCP-инструмент** `duck_query` (сервер `duck-harness`): `{query, limit}` → markdown-таблица.
   `duck_schema` — список вьюх и колонок. Это предпочтительный путь.
2. **CLI** (когда MCP-процесс старый или нужен другой формат):
   ```bash
   ~/Documents/ECOM/mcps/duck-harness/bin/duck-harness --sql "select * from h.tool_stats" --format tsv
   ```
   Флаги: `--limit`, `--format markdown|json|tsv`, `--snapshot-max-age` (по умолчанию 10m),
   `--db` / `OPENCODE_DB`, `--snapshot=false` (читать живую базу).

## Вьюхи (схема `h`)

| Вьюха | Что даёт |
|---|---|
| `data_range` | период, число сессий, суммарные токены — начинать с неё |
| `sessions` | сессии: `kind` root/child, `agent`, `model_id`, `provider_id`, `variant`, токены, `duration_min` |
| `model_usage` | сессии и токены по модели/провайдеру/варианту |
| `tool_calls` | каждый tool-вызов: `tool`, `status`, `latency_ms`, `error`, `target`, `at` |
| `tool_stats` | по инструментам: `calls`, `errors`, `p50_ms`, `p80_ms`, `p95_ms`, `slow_calls` (>60 с) |
| `errors` | ошибки по инструментам, сгруппированы по тексту |
| `skill_loads` | загрузки скиллов: `skill`, `loads`, `sessions` |
| `context_files` | файлы, которые чаще всего читались в контекст |
| `subagents` | дочерние сессии по агенту и модели |
| `execute_inner_tools` | MCP-вызовы внутри `execute` (Code Mode, с 01.09): `session_id`, `server`, `server_norm`, `tool_name`, `at` |
| `execute_inner_stats` | агрегат: `calls`, `sessions`, `first_day`, `last_day` по серверу и тулу |
| `server_calls_daily` | единый таймлайн MCP: `day`, `server_norm`, `calls`, `calls_source` (direct до 01.09 / inner после) |
| `mcp_health_7d` | health MCP-серверов за 7 дней: `server_norm`, `calls`, `errors`, `err_pct`; ошибки — только прямых вызовов (внутренние падают целиком на execute) |
| `self_check` | самопроверки телеметрии: `check_id`, `status` (ok/warn/fail), `detail`; все ok на здоровом снимке — начинать срез с неё |
| `daily_activity` | по дням: сессии, токены, `hours` |
| `expensive_sessions` | сессии по убыванию входных токенов |
| `part` | сырая проекция tool-вызовов (таблица, обычно не нужна) |

## Выгрузки (схема `d`)

Файлы из `~/data/exports` (csv/tsv/parquet/json) при старте становятся таблицами схемы `d`:
`jira/2026-11-06/issues.csv` → `d.jira_2026_11_06_issues`, `RPS по контурам.csv` → `d.vm_rps_po_konturam`
(транслит кириллицы, только `[a-z0-9_]`). Имена смотреть через `duck_schema(schema="d")` или
`duck-harness --schema=d`. Джойнить с телеметрией можно в одном запросе.

## Метрики Jira (схема `m`)

Если в `~/data/exports/jira/` есть `e001_epics.parquet` и `e001_epic_status.parquet`, при старте
появляется схема `m` — готовые метрики E001. Смотреть `duck_schema(schema="m")`.

| Вьюха | Что даёт |
|---|---|
| `m.epic_metrics` | по эпику: `ttm_days`, `lt_days`, `touch_days`, `wasted_days`, `flow_efficiency_pct`, `commitment_days`, `committed`, `team` |
| `m.quarter_summary` | по кварталу: `throughput`, LT (avg/median/p80), TTM (avg/median), CR% |
| `m.team_summary` | то же в разрезе команды (`T006/T100/T102/T083`) |
| `m.epics` / `m.epic_status` | нормализованные эпики и история статусов |
| `m.mr` | merge requests: `project`, `team`, `lead_days` (created→merged), `merged_week`, `is_revert`, `is_hotfix` |
| `m.mr_by_team` | по команде и кварталу: merged, авторы, проекты, lead median/p80, доля revert/hotfix |
| `m.mr_weekly` | по команде и неделе: merged, lead median |
| `m.deployments` | деплои из helm-репо: `is_deploy` (смена `image.tag`), `old_tag`→`new_tag`, `service_path` |
| `m.deploy_by_team` | по команде и кварталу: деплои, сервисы, дни с деплоем, деплоев/неделю, конфиг-коммиты |
| `m.deploy_weekly` | по команде и неделе: деплои, затронутые сервисы |
| `m.incidents` | инциденты Jira PIR: `manifested_at` → `ended_at`, `mttr_hours`, `is_measured` |
| `m.mttr_by_priority` | MTTR по приоритету и кварталу (median/p80/mean) |
| `m.mttr_monthly` | MTTR по месяцам, отдельно критические |
| `m.incident_is` | инцидент ↔ ИС (из `autosys`/`Insight`/`Затронутые ИС`), одна строка = пара |
| `m.mttr_by_is` | MTTR по ИС |
| `m.mttr_by_team` | MTTR по команде (ИС → команда через `d.cedrus_is_teams`) |
| `m.change_failure` | CFR-прокси: инцидентов на 100 деплоев по команде и кварталу |

Правила: throughput и CR — только `status = 'Done'`; LT в среднее попадает при `lt_days between 1 and 365`.
Формулы — `Assist/docs/production-metrics-methodology.md`. Отчёты-образцы:
`Assist/results/harness/e001-metrics-2026Q4.md`, `Assist/results/harness/dora-2026Q4.md`.

**Deployment frequency — настоящая**: деплой в ecom.tech = коммит в `ecom/cicd/<team>/helm`, меняющий
`image.tag` в values сервиса (проверяется по диффу). Репозитории: `ecom/cicd/smkt/helm` (T006, `opercrm`),
`ecom/cicd/mm/helm` (T100: `erm`, `cc-exchanger`; T102: `ts`), `ecom/cicd/ecomtech/helm` (T083).

**MTTR — настоящий**: инциденты из Jira `PIR`, MTTR = `customfield_11828` (окончание) − `customfield_11820`
(проявление); `is_measured` отсекает отрицательные и дольше 30 дней. Медиана по «Среднему» ~1.5 ч, среднее
в 8 раз больше — брать медиану/p80, не среднее.

**ИС инцидента** — из `autosys` (`customfield_18500`, код в `[…]`), `Информационная система (Insight)`
(`26700`) и `Затронутые ИС (Insight)` (`27000`, код перед `(AMM-…)`); нормализуется до первого сегмента
(`opercrm.smkt` → `opercrm`). `d.cedrus_is_teams` даёт ИС → команду, отсюда `m.mttr_by_team` и
`m.change_failure`. Покрытие: ИС есть у ~2/3 инцидентов, на наши команды приходится ~43 из 323.

Остальное — прокси: lead time = создание MR → мерж (не коммит → деплой), change failure rate = доля
`revert`/`hotfix`.

## Рецепты

```sql
-- обзор
select * from h.data_range;

-- кто жжёт токены
select model_id, sum(sessions) sessions, sum(tokens_input) tin, sum(tokens_output) tout
from h.model_usage group by 1 order by tin desc;

-- дорогие сессии
select title, model_id, tokens_input, duration_min, created_at
from h.expensive_sessions limit 10;

-- здоровье инструментов
select tool, calls, errors, round(100.0*errors/calls,1) err_pct, p50_ms, p80_ms, p95_ms, slow_calls
from h.tool_stats order by calls desc limit 20;

-- что именно падает
select tool, error, count from h.errors order by count desc limit 20;

-- скиллы: что работает, что мёртвое
select skill, loads, sessions from h.skill_loads order by loads desc;

-- что зря тянется в контекст
select file, reads, sessions from h.context_files order by reads desc limit 20;

-- сабагенты
select agent, model_id, sessions, tokens_input from h.subagents order by sessions desc;

-- динамика по дням
select day, sessions, tokens_input, hours from h.daily_activity order by day desc limit 14;

-- выгрузки: что загрузилось
-- (MCP) duck_schema {schema: "d"}; CLI: duck-harness --schema=d

-- джойн телеметрии с выгрузкой (например, задачи Jira за период)
select j.status, count(*) issues
from d.jira_2026_11_06_issues j group by 1;

-- метрики E001
select * from m.quarter_summary;

-- DORA по командам
select * from m.deploy_by_team;
select * from m.deploy_weekly order by committed_week desc limit 20;
select * from m.mr_by_team;
select * from m.mttr_monthly;
select * from m.mttr_by_priority;
select * from m.mr_weekly order by merged_week desc limit 20;
select key, team, lt_days, ttm_days, committed from m.epic_metrics order by lt_days desc limit 10;
```

## Грабли (проверено на данных 06.11.2026)

- **Схема V2.** Актуальные данные — `session_v2` + `session_message`; таблицы `session`/`message`/`part`
  это legacy (последняя запись 01.09.2026). Tool-вызовы лежат в `session_message.data.content[]`,
  имя инструмента — `$.name` (в V1 было `$.tool`), время — `$.time.created`/`$.time.completed`.
- **`cost = 0`** у всех сессий и сообщений: провайдеры цену не отдают. Деньги не считаются — только токены.
- **Токены** бери из `session_v2.tokens_*` (равны сумме по сообщениям). `cache_read/write` = 0.
- **`avg` по latency не использовать** — выбросы: на `bash` даёт 152 с при p80 26 мс. Только квантили.
- **`question` и `webfetch`** в latency включают ожидание человека/сети — не трактовать как «медленный инструмент».
- **`hours` в `daily_activity`** — разница `time_updated − time_created`, включает паузы (бывает 139 ч в сутки).
- **Отказы ≠ сбои.** Половина «ошибок» — `Permission denied`, `user declined`, `Tool execution interrupted`.
  При анализе отделяй отказы пользователя/правил от технических сбоев (trino, HTTP 4xx/5xx, timeout).
- **MCP внутри execute (с 01.09.2026).** Прямых `mcp-*` в `h.tool_calls` после 01.09 почти нет —
  частоту и состав серверов брать из `h.execute_inner_stats` / `h.server_calls_daily`. Латенс
  внутренних вызовов не восстановим — только counts; динамический `tools[var]` в статистику не
  попадает (лёгкое занижение). Агрегаты и джойны — по `server_norm` (склеивает `mcp-atlassian`
  и `atlassian`; `gitlab` и `gitlab-spring-mcp` не склеивает).
- **Имя скилла** — opencode с 01.09 передаёт его в `state.input.id` (было `.name`); сканер читает
  оба ключа, пустых строк в `h.skill_loads` быть не должно.
- **Один писатель.** Если появится собственная `harness.duckdb` с агрегатами — писать в неё может только
  один процесс; DuckDB не держит двух писателей.
- **Движок только читает**: `select/with/describe/summarize/explain`, один запрос, deny-лист на
  `attach/copy/install/load/create/insert/…` и `read_csv|read_parquet|read_json|glob`.
  Файлы и сеть закрыты (`enable_external_access=false`).

## Отчёт

Формат среза — `~/Documents/Assist/results/harness/harness-health-<YYYY-MM-DD>.md`
(пример: `harness-health-2026-11-06.md`): обзор → токены по моделям → инструменты → ошибки →
скиллы → сабагенты → дорогие сессии → контекст → оговорки → команды воспроизведения.

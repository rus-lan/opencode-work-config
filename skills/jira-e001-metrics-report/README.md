# jira-e001-metrics-report

Скилл для агента: генератор аналитического отчёта по метрикам PI
(Initiative) и Epic проекта **E001** (команды T006 OCRM / T100 ERM /
T102 TICKETS) на данных **Cedrus** (Trino). Считает ТТМ PI Single, CR PI,
LT Epic, CR Epic по кварталам и месяцам и собирает HTML-отчёт
(`FORMAT=report`) или компактную панель (`FORMAT=dashboard`) с KPI-карточками
против целей OKR PTL E001 H2-2026.

- **Для агента** (модели): `SKILL.md` — методология расчёта, рабочий
  процесс, обязательные разделы отчёта, триггеры, накопленные знания по
  публикации в Confluence.
- **Для человека**: этот файл — установка и сопровождение.
- **Для разработчиков скилла**: `evals/evals.json` — сценарии проверки
  качества (формат skill-creator, см. `skill-creator`).

Источник данных — MCP-сервер `cedrus` (витрина данных Jira, таблицы
`datalake_smkt.prsd_service_desk.jira_issue_4` / `jira_issue_history_hist`).
Опциональная валидация статусов — MCP-сервер `atlassian` (живой Jira API).

## Установка скилла

Приоритет — **opencode** (`~/.config/opencode/skills/`); `--claude` добавляет
установку в `~/.claude/skills/`.

```sh
# из клона репозитория (локально, без сети):
./install.sh

# в opencode и дополнительно в Claude:
./install.sh --claude

# удалённо, из релиза приватного проекта (нужен токен):
curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fjira-e001-metrics-report%2Finstall.sh/raw?ref=main" \
  | JIRA_E001_METRICS_REPORT_TOKEN="$GITLAB_TOKEN" sh
```

Флаги и переменные — в шапке `install.sh`:

| Флаг / env | Назначение |
|---|---|
| `--claude` | дополнительно установить в `~/.claude/skills/` |
| `--force` | перезаписать чужой каталог скилла |
| `--uninstall` | удалить установленное этим скриптом |
| `--dry-run` | показать действия, ничего не писать |
| `-h`, `--help` | справка |
| `OPENCODE_SKILLS_DIR` | каталог opencode-скиллов (дефолт `~/.config/opencode/skills`) |
| `CLAUDE_SKILLS_DIR` | каталог Claude-скиллов (дефолт `~/.claude/skills`) |
| `JIRA_E001_METRICS_REPORT_VERSION` | конкретная версия при удалённой установке |
| `JIRA_E001_METRICS_REPORT_TOKEN` / `GITLAB_TOKEN` | PAT для приватного проекта |
| `JIRA_E001_METRICS_REPORT_SKIP_CHECKSUM=1` | пропустить проверку sha256 (не рекомендуется) |

## Что в каталоге

```
skills/jira-e001-metrics-report/
├── SKILL.md                    # инструкция для агента (frontmatter + методология + процесс)
├── README.md                   # этот файл
├── VERSION                     # версия компонента (источник истины)
├── CHANGELOG.md                # Keep a Changelog
├── install.sh                  # установка; приоритет — opencode
├── scripts/release.sh          # сборка бандла в dist/release/
├── references/
│   ├── queries.md              # параметризованные SQL-запросы к Cedrus
│   ├── template.html           # эталонный HTML-шаблон полного отчёта
│   └── dashboard-template.html # шаблон компактной панели (Chart.js)
└── evals/
    └── evals.json              # сценарии проверки качества скилла
```

Файлы `VERSION` / `SKILL.md#version` / `CHANGELOG.md` / `RELEASE-NOTES.md`
должны меняться согласованно (см. `RELEASING.md` в корне репозитория).

## Релиз

1. Поднимите версию: `VERSION`, `version:` в frontmatter `SKILL.md`, запись в
   `CHANGELOG.md`, при значимых изменениях — пункт в корневом
   `RELEASE-NOTES.md`.
2. Проверьте локально:
   ```sh
   python3 ../../ci/validate-skill.py SKILL.md
   bash scripts/release.sh
   ```
   (release.sh собирает `dist/release/jira-e001-metrics-report.tar.gz` +
   `install.sh` + `checksums-sha256.txt`; проверить валидатором — именно
   `SKILL.md`.)
3. Коммит, мерж в `main`; джоба `publish-release` создаст тег
   `skills/jira-e001-metrics-report/v<version>` и релиз (см.
   `ci/publish-release.sh`).

## Проверка качества (evals)

`evals/evals.json` — набор промптов с ассершенами (формат skill-creator):
полный отчёт за квартал (ТТМ/CR/LT, разбивка по месяцам), сверка с
дашбордом, «почему июнь = 18 а не 17», dashboard-формат, прогнозные
ТТМ/LT по незакрытым задачам. Прогон: по методике `skill-creator`
(workspace `jira-e001-metrics-report-workspace/`, итерации, `eval-viewer`
для просмотра).
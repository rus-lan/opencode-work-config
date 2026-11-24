---
title: "Зависимости: criticality-gen"
purpose: Зависимости скилла и их проверка до первой фазы.
audience: [ai-agent]
read_when: [первый запуск на новой машине, скилл не может клонировать или рендерить]
updated: 2026-11-12
status: actual
related: [failure-modes.md, commands.md]
---

# Зависимости: criticality-gen

Скилл проверяет зависимости до первой фазы. Зависимость без проверки
обнаруживается в середине работы — на клонировании или на рендере, когда
половина артефактов уже создана.

## Обязательные и опциональные

| Зависимость | Тип | Обязательна | Проверка | Что делать если нет |
|-------------|-----|-------------|----------|---------------------|
| `python3` ≥ 3.9 (stdlib) | cli | да | `python3 --version` | установить python3; без него не работает `scripts/criticality.py` — дальше идти нельзя |
| `git` | cli | да | `git --version` | установить git; без него `prepare` не склонирует `apps/` |
| `make` | cli | нет | `make --version` | вызывать `python3 scripts/criticality.py <команда>` напрямую — все цели Makefile тонкие |
| MCP `ssot-mcp` (read) | mcp | да | `ssot_status` → `authorized`, `ssot_get` отвечает | запустить сервер `ssot-mcp` и пройти SSO; до этого `INFORMATION.yaml` не из чего собрать — `ssot-import` нечего импортировать |
| PyYAML | cli | нет | `python3 -c "import yaml"` | скрипт использует встроенный мини-парсер; предупредить, что сложный YAML может разобраться неполно — проверить `make check` |
| MCP Confluence (read) | mcp | нет | инструмент `confluence_get_page` доступен | читать страницы вручную и заполнять `source: {type: confluence, ref: '<page_id>, раздел'}`; лимит 30 запросов на ключ, батчи ≤10 страниц |
| MCP Grafana | mcp | нет | `grafana_search_dashboards`, `grafana_get_dashboard`, `grafana_query_prometheus` доступны | снять нагрузку вручную (дашборд → панель → `peak_rps × 3600`); без пика простой сценарий не считается — `BLOCKED`, вход blocking |
| MCP Confluence (write) | mcp | нет | инструмент `confluence_create_page` / `update_page` доступен | `--create-confluence` только помечает `actions/confluence-page.md` как `requested`; без MCP пакет остаётся ручным |
| MCP Jira (read/write) | mcp | нет | инструменты `jira_*` доступны | `--create-task` только помечает `actions/jira-task.md` как `requested`; без MCP пакет остаётся ручным |
| MCP GitLab | mcp | нет | инструмент `gitlab_*` доступен | ссылки на MR и репозитории вписывать вручную |
| MCP RocketChat | mcp | — | **отсутствует в системе** | всегда action-пакет: текст сообщения формируется, отправляет человек |

## Этап `services`: нужен только `git`

Для клонов сервисов **не требуются** компиляторы, пакетные менеджеры, Docker и
тестовые раннеры: `services` клонирует репозитории и читает файлы. Проверка —
`git --version` и доступ к хосту репозитория (`git ls-remote <url> HEAD`).

| Зависимость | Обязательна | Проверка | Что делать если нет |
|-------------|-------------|----------|---------------------|
| `git` | да | `git --version` | установить git; без него клон не обновится и `SERVICE-FINDINGS.md` останется с `clone_error` |
| доступ к хосту репозитория сервиса | да (для чтения кода) | `git ls-remote <git_repository> HEAD` | запросить доступ у владельца репозитория; до получения — `SERVICE-FINDINGS.md` с ошибкой клонирования, сбор данных идёт по Confluence |
| компилятор / `go` / `npm` / `gradle` / `docker` | **нет** | не проверяется | не нужен: сборка и запуск из клонов запрещены (R12) |

Правило: если для «понимания сервиса» требуется запустить его код — это не этап
`services`. Значение всё равно подтверждает человек, а не результат запуска.

## Типы зависимостей

| Тип | Что означает | Пример |
|-----|--------------|--------|
| `cli` | исполняемый файл в `PATH` | `python3`, `git`, `make` |
| `mcp` | MCP-сервер, доступный агенту | confluence, jira, gitlab |
| `repo` | git-репозиторий, клон или доступ по ssh | `apps/IS/COMPONENT` |
| `access` | права/сеть/учётка | SSO-сессия к SSoT (MCP), PAT GitLab |

## Отсутствующие MCP: деградация, а не отказ

| MCP | Статус | Поведение скилла |
|-----|--------|------------------|
| Confluence (read) | доступен | читает дерево страниц ИС, ставит `source: {type: confluence, ref: '<page_id>, раздел'}`; ADF-страницы читает через `confluence_get_page_history` |
| Grafana | доступен | снимает пик RPS с панелей трафика папки E001, ставит `source: {type: grafana, ref: 'dashboard uid, panel, expr'}` |
| Confluence (write) | доступен | `--create-confluence` помечает пакет как `requested`; страницу создаёт агент через MCP по `actions/confluence-page.md` |
| Jira | доступен | `--create-task` помечает пакет как `requested`; задачу создаёт агент через MCP по `actions/jira-task.md` |
| GitLab | доступен | подставляет ссылки на MR и репозитории |
| RocketChat | **отсутствует** | сообщение в `#Criticality_assessment` — только текст в `actions/rocketchat-message.md`; отправляет человек |

Лимиты MCP-источников, которые влияют на план сбора:

| Источник | Лимит / ограничение | Как обходить |
|----------|---------------------|--------------|
| Confluence | 30 запросов на общий ключ; лимит делится между агентами | батчи ≤10 страниц с паузами, при `Rate limit exceeded` — пауза и повтор |
| Confluence | глубина дерева не ограничена | BFS до глубины 2, максимум 40 страниц на ИС |
| Grafana | тяжёлые `max_over_time` на 30d отваливаются по таймауту | уменьшать разрешение подзапроса (`[30d:15m]`) или сузить окно |
| Grafana | фильтр папки в поиске игнорируется | фильтровать результат на клиенте по uid папки E001 |

Правило: отсутствие MCP никогда не блокирует локальные артефакты. Оно
блокирует только автоматическую внешнюю запись — и тогда создаётся action-пакет
с готовым текстом и инструкцией.

## Проверка перед запуском

```bash
python3 --version >/dev/null 2>&1 || echo "MISSING python3"
git --version >/dev/null 2>&1 || echo "MISSING git"
[ -f is.yaml ] || echo "MISSING is.yaml (make init)"
python3 - <<'PY' || true
try:
    import yaml  # noqa: F401
    print("PyYAML: есть")
except ImportError:
    print("PyYAML: нет — используется встроенный мини-парсер")
PY
[ -d apps ] || echo "WARN apps/ отсутствует (prepare-apply создаст)"
[ -f .opencode/skills/criticality-gen/criteria/criticality-criteria.yaml ] || echo "MISSING criteria/criticality-criteria.yaml (в каталоге скилла)"
```

Ожидаемый результат: ни одной строки `MISSING`. Любая строка `MISSING` —
остановка с указанием, что установить или у кого запросить доступ. `WARN`
не блокирует. `PyYAML: нет` не блокирует, но требует проверить разбор
`INFORMATION.yaml` через `make check` (strict — поведение по умолчанию).

## Доступ к SSoT

SSoT читается и правится **только через MCP `ssot-mcp`**: клона, ssh-ключа и
git-доступа к репозиторию SSoT скиллу не нужно.

Проверка:

```text
ssot_status          → authorized (сервер запущен, SSO-сессия активна)
ssot_get(group="information-systems", entity="<код>")  → карточка ИС
ssot_team(code="<team>")                                → ростер команды
```

`auth_required` или ошибка MCP — это `access`-блокер: скилл останавливается и
передаёт человеку действие (перезапустить `ssot-mcp`, пройти SSO), а не
подставляет данные «по памяти».

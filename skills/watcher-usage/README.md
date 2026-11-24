# watcher-usage

Скилл для агента: правила ведения и использования **watcher** — общей базы
фактов (SQLite + гибридный поиск). Не привязан к информационным системам:
хранит любые проверенные знания, полезные между сессиями (сервисы,
инфраструктура, договорённости, решения, люди, процессы).

- **Для агента** (модели): `SKILL.md` — правила ведения базы, поиск, чек-листы
  сценариев, CLI/MCP-справочник, устранение неполадок.
- **Для человека**: этот файл — установка и сопровождение.
- **Для разработчиков скилла**: `evals/evals.json` — сценарии проверки
  качества (формат skill-creator, см. `skill-creator`).

watcher ставится **отдельно** — скилл только описывает, как им пользоваться.
Установка watcher: `cargo build --release` из
[`tools/watcher`](../../tools/watcher/README.md) либо релизный `install.sh`
компонента `watcher` (тег `tools/watcher/vX.Y.Z`).

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
  "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fwatcher-usage%2Finstall.sh/raw?ref=main" \
  | WATCHERUSAGE_TOKEN="$GITLAB_TOKEN" sh
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
| `WATCHERUSAGE_VERSION` | конкретная версия при удалённой установке |
| `WATCHERUSAGE_TOKEN` / `GITLAB_TOKEN` | PAT для приватного проекта |
| `WATCHERUSAGE_SKIP_CHECKSUM=1` | пропустить проверку sha256 (не рекомендуется) |

## Что в каталоге

```
skills/watcher-usage/
├── SKILL.md           # инструкция для агента (frontmatter + правила + справочники)
├── README.md          # этот файл
├── VERSION            # версия компонента (источник истины)
├── CHANGELOG.md       # Keep a Changelog
├── install.sh         # установка; приоритет — opencode
├── scripts/release.sh # сборка бандла в dist/release/
└── evals/
    ├── evals.json         # сценарии проверки качества скилла
    └── check_answers.py   # проверка answer.md по assertions (PASS/FAIL таблица)
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
   bash scripts/release.sh --dry-run 2>/dev/null || bash scripts/release.sh
   ```
   (release.sh собирает `dist/release/watcher-usage.tar.gz` + `install.sh` +
   `checksums-sha256.txt`; проверить валидатором — именно `SKILL.md`.)
3. Коммит, мерж в `main`; джоба `publish-release` создаст тег
   `skills/watcher-usage/v<version>` и релиз (см. `ci/publish-release.sh`).

## Проверка качества (evals)

`evals/evals.json` — набор промптов с ассершенами (формат skill-creator):
сохранение факта (kind/sensitivity/параметризация), поиск «что мы знаем о X»,
отказ от shareable-факта с секретом, не-сохранение одноразового контекста,
разбор инцидента, MCP-дозированная выдача. Прогон: по методике `skill-creator`
(workspace `watcher-usage-workspace/`, итерации, `eval-viewer` для просмотра);
автопроверка ответов — `evals/check_answers.py <root>` (таблица PASS/FAIL,
`--group with_skill`, `--json`, `--min-score N` для gate в CI).
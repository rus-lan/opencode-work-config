---
name: slo-monitoring
version: 1.0.0
description: |
  Инструментарий генерации/обновления SLO-мониторинга (sloth.yaml / slo.yaml /
  alerts.yaml) для набора сервисов. CLI-пайплайн `generate-sloth.sh` клонирует
  каждый сервис и helm-репо компании из services-slogen.yaml, генерирует
  slo-kit.yaml → slo.yaml/alerts.yaml → sloth.yaml, прогоняет slo-kit lint и
  публикует sloth.yaml в helm-репозиторий. Плюс sloth-parse.py (YAML→TSV),
  sloth-normalize.py (letsgo oif/jobs→custom), install-tools.sh (slokit+slo-kit)
  и автоматический бот sloth-bot.sh для cron, с изолированным прогоном в Docker.

  TRIGGER при запросах вида «сгенерируй/обнови SLO», «sloth.yaml», «SLO для
  набора сервисов», «slokit», «slo-kit», «обнови SLO-мониторинг», «запусти
  sloth-бот», а также по-английски: "generate SLO", "update sloth.yaml",
  "SLO monitoring for services", "run sloth bot" — или при вызове /sloth.
user-invocable: true
compatibility: opencode
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# slo-monitoring

Bulk-генерация / обновление SLO-мониторинга для набора сервисов, описанных в
`scripts/services-slogen.yaml`. Для каждого сервиса по цепочке:

```
git clone/pull  →  slokit generate (configs/slo-kit.yaml)
               →  sloth-normalize.py (letsgo rule types)
               →  slo-kit generate (configs/slo.yaml + configs/alerts.yaml)
               →  slo-kit generate sloth (configs/sloth.yaml)
               →  slo-kit lint
               →  cp configs/sloth.yaml → helm/<company>/<chart>/sloth.yaml
```

Все скрипты — относительно каталога скилла `<skill-dir>`; после установки через
`install.sh` это `~/.config/opencode/skills/slo-monitoring/`. Исполняемые файлы лежат в
`<skill-dir>/scripts/`, источник правды — `<skill-dir>/scripts/services-slogen.yaml`,
база знаний (профили, метрики, схема slo-kit) — в `<skill-dir>/scripts/references/`.

## Локальный прогон

```sh
# все сервисы, до 4 параллельных процессов
bash <skill-dir>/scripts/generate-sloth.sh

# один сервис по имени (name из services-slogen.yaml)
bash <skill-dir>/scripts/generate-sloth.sh <name>

# ограничить параллельность
bash <skill-dir>/scripts/generate-sloth.sh --jobs 2

# не трогать git (перегенерировать файлы на месте)
bash <skill-dir>/scripts/generate-sloth.sh --skip-git

# не клонировать/обновлять, использовать уже существующие каталоги
bash <skill-dir>/scripts/generate-sloth.sh --no-clone
```

Предварительно поставьте/обновите инструменты `slokit` и `slo-kit`:

```sh
bash <skill-dir>/scripts/install-tools.sh            # обновить оба
bash <skill-dir>/scripts/install-tools.sh --check    # только проверить окружение
```

## Через бота (без ручной валидации, для cron)

`sloth-bot.sh` обновляет инструменты, обходит все сервисы и пишет отчёт
`<skill-dir>/scripts/sloth-bot-report-<дата>.md` (сервисы с ошибками помечаются,
обход всегда доводится до конца):

```sh
bash <skill-dir>/scripts/sloth-bot.sh                # полный цикл локально
bash <skill-dir>/scripts/sloth-bot.sh --docker       # в изолированном контейнере
bash <skill-dir>/scripts/sloth-bot.sh --no-tools     # не обновлять инструменты
bash <skill-dir>/scripts/sloth-bot.sh --check        # только проверка окружения
```

## Через GitLab CI

Ту же генерацию (через `docker/run.sh` или `sloth-bot.sh --docker`) можно
запускать из GitLab CI. Рабочий шаблон — `examples/.gitlab-ci.yml` компонента
(установленный: `~/.config/opencode/skills/slo-monitoring/examples/.gitlab-ci.yml`).
Подробности — в `README.md` (секция «Запуск в GitLab CI (пример)»).

## Через cron (раз в 3 дня)

Бот сам по себе не коммитит и не пушит — он только генерирует файлы и ветку
`feature/sloth-<дата-время>`. Пример crontab:

```
0 3 */3 * * "$HOME/.config/opencode/skills/slo-monitoring/scripts/sloth-bot.sh" --docker >> "$HOME/.config/opencode/skills/slo-monitoring/scripts/.sloth-logs/bot-cron.log" 2>&1
```

## Установка

Один из способов (см. README.md, раздел «Установка»):

```sh
curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fslo-monitoring%2Finstall.sh/raw?ref=main" \
  | SLOTH_TOKEN="$GITLAB_TOKEN" sh
```

`install.sh` кладёт скилл в `~/.config/opencode/skills/slo-monitoring/`,
регистрирует opencode-команду `/sloth` в `~/.config/opencode/commands/sloth.md` и
ставит в `~/.local/bin/` команды-лаунчеры `sloth` (→ `generate-sloth.sh`) и
`sloth-bot` (→ `sloth-bot.sh`), после чего их можно вызывать коротко: `sloth`,
`sloth-bot`, а в opencode — командой `/sloth`.

## Требования

- `git`, `python3` + PyYAML (`py3-yaml`), `go` (сборка slokit), `docker`
  (получение slo-kit; опционально для Docker-контура);
- бинарники `slokit` и `slo-kit` на PATH (или в `~/.local/bin`);
- **исходники `slo-kit-generator`** для сборки `slokit` (go-модуль) — внешний
  репозиторий, не входящий в hub. Переменная `SLOTKIT_SRC` (по умолчанию
  `~/.config/opencode/skills/slo-kit-generator`) указывает на локальный git-клон;
  если его нет — `install-tools.sh slokit` завершится с `FAIL`. Переопределяется
  через `SLOTKIT_SRC=/путь/к/клону`;
- git-доступ к `git.ecom.tech` (HTTPS через `~/.netrc` или SSH-ключ);
- внутренний DNS (для Docker-контура пробрасывается из host `resolv.conf`).

Проверка готовности: `bash <skill-dir>/scripts/sloth-bot.sh --check`.

Полная документация и устройство — в [`README.md`](./README.md) и
[`scripts/BOT.md`](./scripts/BOT.md); справка по пайплайну —
`bash <skill-dir>/scripts/generate-sloth.sh --help`.
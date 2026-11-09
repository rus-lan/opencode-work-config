# slo-monitoring

Инструментарий генерации / обновления **SLO-мониторинга** для набора сервисов.
Читает источник правды `services-slogen.yaml`, для каждого сервиса клонирует
репозиторий и helm-репо компании, генерирует `configs/slo-kit.yaml` →
`configs/slo.yaml` + `configs/alerts.yaml` → `configs/sloth.yaml`, прогоняет
`slo-kit lint` и публикует `sloth.yaml` в helm-репозиторий компании.

Упакован как **skill-компонент** hub `e001-ai-hub` в `skills/slo-monitoring/`
и может ставиться/запускаться тремя способами:

1. **локально** — одной командой из клона инструментария;
2. **удалённо** — `curl | sh` из ветки `main` приватного проекта через GitLab
   raw API;
3. **лаунчеры в `~/.local/bin/`** — короткие команды `sloth` и `sloth-bot`.

Также есть **автоматический бот** (`sloth-bot.sh`) для запуска по cron без
ручной валидации и **изолированный прогон в Docker** (`scripts/docker/`).

---

## Что это

`scripts/` содержит сам инструментарий:

| Файл | Назначение |
|---|---|
| `scripts/generate-sloth.sh` | **Исполнитель**: clone → generate → lint → publish. Флаги `--jobs N`, `--skip-git`, `--no-clone`, позиционный `<name>`, `PROFILE_MAP` |
| `scripts/sloth-parse.py` | PyYAML-парсер `services-slogen.yaml` → TSV (для `generate-sloth.sh`) |
| `scripts/sloth-normalize.py` | Пост-обработка `configs/slo-kit.yaml`: `oif`/`jobs` → `custom` + `custom_latency` для letsgo (ограничение slo-kit v26.10.1) |
| `scripts/install-tools.sh` | Установка/обновление `slokit` (go build) и `slo-kit` (Docker). Флаги `--check`, `slokit`, `slo-kit` |
| `scripts/sloth-bot.sh` | Автономный цикл для cron. Флаги `--docker`, `--no-tools`, `--check`; пишет `sloth-bot-report-<дата>.md` |
| `scripts/services-slogen.yaml` | **Источник правды** — список сервисов (name/namespace/company/repo/profile/team/cost_centre/helm) |
| `scripts/docker/` | Изолированный прогон: `Dockerfile`, `run.sh`, `run-in-container.sh` (opencode base, DNS, chown) |
| `scripts/references/` | База знаний: `ecom-tech-profile.md`, `metrics-reference.md`, `profiles-reference.md`, `slo-kit-schema.md`, `examples/` |
| `scripts/sloth.md` | opencode-команда `/sloth` (обёртка над `generate-sloth.sh`) |
| `scripts/BOT.md` | Инструкция по автоматизации бота |

Все скрипты определяют свой каталог через
`SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` и работают
относительно него (каталоги `apps/`, `helm/`, `.sloth-logs/` создаются рядом со
скриптами), поэтому **не зависят** от того, где закаталогирован скилл.

---

## Установка

### Локально (из клона репозитория hub)

Клонируйте hub (или возьмите этот каталог уже внутри клона) и выполните из
`skills/slo-monitoring/`:

```sh
./install.sh
```

`install.sh` определит, что он запущен из клона (рядом есть `SKILL.md`), и
поставит скилл из текущего каталога без сети: скопирует бандл в
`~/.config/opencode/skills/slo-monitoring/`, зарегистрирует opencode-команду
`/sloth` в `~/.config/opencode/commands/sloth.md` и положит лаунчеры `sloth` и
`sloth-bot` в `~/.local/bin/`.

### Удалённо (одной командой, из ветки `main`)

```sh
curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fslo-monitoring%2Finstall.sh/raw?ref=main" \
  | SLOTH_TOKEN="$GITLAB_TOKEN" sh
```

`install.sh` скачивается из ветки `main` приватного проекта через GitLab raw API
(`repository/files/.../raw?ref=main`); `SLOTH_TOKEN=$GITLAB_TOKEN` передаётся
установщику для доступа к приватному репозиторию и загрузке релиза
(`slo-monitoring.tar.gz`) из Registry. Проверяет sha256, распаковывает и ставит
то же самое: скилл в `~/.config/opencode/skills/slo-monitoring/`, opencode-команду
`/sloth` в `~/.config/opencode/commands/sloth.md` + лаунчеры в `~/.local/bin/`.

> Команды-лаунчеры `sloth`/`sloth-bot` создаются, **только если** в `~/.local/bin/`
> ещё нет файла с таким именем (а чужие файлы никогда не перезаписываются без
> `--force`).

---

## Использование

После установки (или прямо из клона — через `bash <skill-dir>/scripts/...`) у
вас есть два уровня: короткие команды `sloth`/`sloth-bot` и прямой вызов
скриптов.

### 1. Обновить инструменты

```sh
sloth  # лаунчер только для generate-sloth.sh
scripts/install-tools.sh --check   # или напрямую: check окружения
bash <skill-dir>/scripts/install-tools.sh   # обновить slokit + slo-kit
```

### 2. Сгенерировать / обновить SLO

```sh
# все сервисы из services-slogen.yaml, до 4 параллельных процессов
sloth

# один сервис по имени
sloth <name>

# ограничить параллельность
sloth --jobs 2

# не трогать git (перегенерировать файлы на месте)
sloth --skip-git

# не клонировать/обновлять, использовать существующие каталоги apps/*
sloth --no-clone

sloth --help
```

Результат для каждого сервиса: `configs/sloth.yaml` в репозитории сервиса и
копия `configs/sloth.yaml` в `helm/<company>/<chart>/sloth.yaml`. Подробный лог
по каждому сервису — в `.sloth-logs/<name>.log`. Все операции идут на новой
уникальной ветке `feature/sloth-<дата-время>`; скрипт **сам не коммитит и не
пушит**.

### 3. Через бота (cron, без ручной валидации)

```sh
sloth-bot                # полный цикл локально
sloth-bot --docker       # в изолированном контейнере
sloth-bot --no-tools     # не обновлять инструменты
sloth-bot --check        # только проверка окружения
```

Пишет отчёт `<skill-dir>/scripts/sloth-bot-report-<дата>.md`; сервисы с ошибками
помечаются, обход всегда доводится до конца. Бот **не** коммитит и не пушит
(безопасный режим) — при необходимости push добавьте отдельным шагом.

### 4. Через cron (раз в 3 дня)

```cron
0 3 */3 * * "$HOME/.config/opencode/skills/slo-monitoring/scripts/sloth-bot.sh" --docker >> "$HOME/.config/opencode/skills/slo-monitoring/scripts/.sloth-logs/bot-cron.log" 2>&1
```

### 5. Через opencode-команду `/sloth`

`scripts/sloth.md` — команда `/sloth` для opencode (обёртка над
`generate-sloth.sh`). `install.sh` регистрирует её автоматически в
`~/.config/opencode/commands/sloth.md` (с маркером-комментарием, чтобы её можно
было безопасно переустановить/удалить). После установки `/sloth` доступен прямо
в opencode; подробности в самом файле и в `scripts/BOT.md`.

---

## Изолированный прогон в Docker

`scripts/docker/run.sh` собирает образ `sloth-verify` (opencode base + git /
python3 / yaml) и запускает `generate-sloth.sh` внутри чистого контейнера.
Проект монтируется томом (ничего не зашивается в образ), git-креды (`~/.netrc`,
`~/.ssh`) подключаются только на чтение, внутренний DNS пробрасывается из
`resolv.conf` host'а, а владелец сгенерированных файлов возвращается к
host-UID/GID через `chown`. Из корня каталога со скриптами:

```sh
bash scripts/docker/run.sh              # все сервисы
bash scripts/docker/run.sh <service>    # один сервис
```

---

## Запуск в GitLab CI (пример)

Эту же генерацию можно запускать **из GitLab CI через Docker** — в изолированном
контейнере, по расписанию или вручную, без ручной возни с окружением. Готовый
самостоятельный пример — `examples/.gitlab-ci.yml` внутри компонента:

- в установленном скилле: `~/.config/opencode/skills/slo-monitoring/examples/.gitlab-ci.yml`;
- в клоне hub: `skills/slo-monitoring/examples/.gitlab-ci.yml`.

Пример **не управляет корневым `.gitlab-ci.yml` hub**: это шаблон, который кладётся
в ваш собственный проект/ветку, ведущий «набор сервисов» (там живёт
`scripts/services-slogen.yaml`), и адаптируется под свой раннер (`docker:dind` или
shell-раннер с docker). Что он делает:

1. в `before_script` готовит окружение (git / python3+pyyaml / bash / curl),
   настраивает git-креды для `git.ecom.tech` в `~/.netrc` и проверяет/готовит
   бинарники `slokit` и `slo-kit` в `$HOME/.local/bin`;
2. в `script` запускает `bash scripts/docker/run.sh` (или
   `bash scripts/sloth-bot.sh --docker --no-tools` для полного автоцикла с отчётом);
3. в `artifacts` фиксирует `sloth-bot-report-*.md`, логи `.sloth-logs/` и
   сгенерированные `helm/**/sloth.yaml`.

Джобы даны в двух вариантах: ручной (`when: manual`) и по расписанию (`schedule`,
cron-пример `0 3 */3 * *`).

### Переменные CI, которые нужно задать

На проекте (Settings > CI/CD > Variables) определите как минимум:

| Переменная | Назначение |
|---|---|
| `GITLAB_TOKEN` | Токен с правами `ReadRepository` на все репозитории сервисов и helm-репо компании (`git.ecom.tech/ecom/cicd/<company>/helm`). Пишется в `~/.netrc` для HTTPS-клонирования. Mark protected/masked, если джоба ходит по расписанию. |
| `SLOTH_SKILL_PATH` | Путь к каталогу скилла (где `scripts/docker/run.sh`). По умолчанию — `~/.config/opencode/skills/slo-monitoring`; для клона hub укажите `./skills/slo-monitoring`. |
| Внутренний DNS | Если раннер **не** резолвит `git.ecom.tech` — пропишите IP internal DNS (см. комментарии в примере: `/etc/hosts` или `nameserver` в `resolv.conf`; `docker/run.sh` пробрасывает nameserver'ы host'а в контейнер). |
| Пути к бинарникам | `slokit`/`slo-kit` должны лежать в `$HOME/.local/bin` (скрипт монтирует их в контейнер). В примере они либо восстанавливаются из артефакта/секрета (`SLOTH_TOOLS_CACHE`), либо ставятся `install-tools.sh` (нужны Go-тулчейн + клон `slo-kit-generator` и доступ к `dreg.sbmt.io`). |

> Замечание: `install-tools.sh` для сборки `slokit` требует Go-тулчейн и локальный
> клон `slo-kit-generator` (`SLOTKIT_SRC`), а для `slo-kit` — доступ к
> `dreg.sbmt.io`. Для CI надёжнее подготовить бинарники заранее и восстановить из
> артефакта/секрета, чем собирать в `before_script`. См. комментарии в самом
> `examples/.gitlab-ci.yml`.

---

## Профили (известное ограничение slo-kit)

`slokit generate` записывает профиль 1-в-1, но текущий `slo-kit` (v26.10.1)
принимает только `[kuper-go, kuper-ruby, kuper-python, ecomtech-letsgo,
ecomtech-kotlin, ecomtech-python]`. `generate-sloth.sh` содержит `PROFILE_MAP`,
нормализующий rejected-профили (сейчас `ecom-go-legacy` → `ecomtech-letsgo`);
`sloth-normalize.py` дополнительно переводит несобираемые rule type `oif`/`jobs`
в поддерживаемые `custom` + `custom_latency`. См. `scripts/references/`.

---

## Требования к окружению

- `git`, `python3` + PyYAML (`py3-yaml`; для `sloth-parse.py` /
  `services-slogen.yaml`);
- `go` — сборка `slokit`;
- **исходники `slo-kit-generator`** (go-модуль, из которого собирается `slokit`).
  Это внешний репозиторий, в hub он **не входит**: `install-tools.sh` ждёт
  локальный git-клон по пути из переменной `SLOTKIT_SRC` (по умолчанию
  `~/.config/opencode/skills/slo-kit-generator`). Если клона нет —
  `install-tools.sh slokit` завершается с `FAIL`. Укажите другой путь через
  `SLOTKIT_SRC=/путь/к/клону`;
- `docker` — получение `slo-kit` и изолированный контур;
- бинарники `slokit` и `slo-kit` на PATH (или в `~/.local/bin`);
- git-доступ к `git.ecom.tech` (HTTPS через `~/.netrc`, или SSH-ключ);
- внутренний DNS (для Docker-контура пробрасывается из host `resolv.conf`).

Проверка готовности: `sloth-bot --check` (или `scripts/install-tools.sh --check`).

---

## Лицензия и примечания

- Компонент распространяется по конвенциям hub `e001-ai-hub` как skill-релиз
  (`skills/slo-monitoring`). Версия задаётся в `VERSION` (единственный источник
  правды, сверяется с `version:` в frontmatter `SKILL.md`); история — в
  `CHANGELOG.md`.
- Инструмент предназначен для внутренней инфраструктуры СберМаркета
  (`git.ecom.tech`). Внешние репозитории и секреты не требуются: git-доступ —
  через `~/.netrc`/SSH, токены не зашиваются в конфиги.
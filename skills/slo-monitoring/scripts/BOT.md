# SLO-бот: автоматизация генерации SLO-мониторинга без ручной валидации

Этот документ — полная инструкция, по которой собирается **бот**, выполняющий
полный цикл генерации SLO каждые 3 дня в автоматическом режиме (без ручной
валидации).

## Что делает бот (один запуск)

1. **Обновляет инструменты**: `install-tools.sh` (slokit из go build, slo-kit
   через docker pull) и проверяет зависимости (git, python3+PyYAML, go, docker).
2. **Обходит все сервисы** из `services-slogen.yaml`:
   - клонирует репозиторий сервиса в `./apps/<company>/<имя>` (разделение по компании);
   - для сервиса и для helm-репо компании переключается на **master** и делает
     `git pull` (актуальные данные);
   - создаёт **уникальную ветку** `feature/sloth-<дата-время>` (каждый запуск —
     своя, без пересечений);
   - генерирует `configs/slo-kit.yaml` → `slo.yaml`/`alerts.yaml` → `sloth.yaml`;
   - валидирует (`slo-kit lint`);
   - копирует `sloth.yaml` в helm-репозиторий компании.
3. **Клонирует helm-репо** `git.ecom.tech/ecom/cicd/<company>/helm` в
   `./helm/<company>` (company берётся из каждого сервиса). Тоже master + pull +
   уникальная ветка.
4. **Пишет отчёт** `sloth-bot-report-<дата>.md` со сводкой по каждому сервису.

## Как собрать бота

### Вариант A — готовый cron-скрипт (рекомендуется)

Скрипт `sloth-bot.sh` уже реализует весь цикл и не требует интерактива:

```bash
# локально
./sloth-bot.sh

# в изолированном Docker-контуре
./sloth-bot.sh --docker

# без обновления инструментов
./sloth-bot.sh --no-tools
```

**Cron (раз в 3 дня в 03:00):**

```
0 3 */3 * * "$HOME/.config/opencode/skills/slo-monitoring/scripts/sloth-bot.sh" --docker >> "$HOME/.config/opencode/skills/slo-monitoring/scripts/.sloth-logs/bot-cron.log" 2>&1
```

`sloth-bot.sh` не валидирует результаты интерактивно: сервисы, у которых
генерация упала (ограничения профиля slo-kit и т.п.), помечаются в отчёте как
«ЧАСТИЧНО/ОШИБКИ», но обход продолжается и отчёт формируется всегда.

> **Ветки `feature/sloth-<ts>` не пушатся автоматически.** Если нужен
> автоматический push (commit+push сгенерированных `sloth.yaml` в helm и сервисы),
> в конфиг бота нужно добавить шаг с явным `git push` на эту ветку. По умолчанию
> бот **не коммитит и не пушит** (безопасный режим).

### Вариант B — opencode-агент / skill

Инструментарий упакован как навык `slo-monitoring` (см.
`skills/slo-monitoring/SKILL.md` в hub, или
`~/.config/opencode/skills/slo-monitoring/SKILL.md` после установки) и
opencode-команда `/sloth` (после установки —
`~/.config/opencode/commands/sloth.md`). Бот может быть opencode-агентом,
который на каждый тик:

```
/sloth
```

и затем по отчёту `.sloth-logs/*.log` и `sloth-bot-report-<date>.md` принимает
решение о push. Чтобы агент работал полностью автономно (без ручной валидации),
поведение «коммитить всегда на feature/sloth-<ts>» должно быть прописано в его
системном промпте.

## Поток данных

```
services-slogen.yaml            (company, repo, profile, helm-цели)
        │  (git clone/pull)
        ▼
./apps/<company>/<service>       ── master + pull ──► feature/sloth-<ts>
        │  slokit generate
        ▼
configs/slo-kit.yaml
        │  slo-kit generate (+sloth)
        ▼
configs/sloth.yaml ──cp──► ./helm/<company>/<chart>/sloth.yaml
                                  (helm-репо: master+pull → feature/sloth-<ts>)
```

## Отказоустойчивость (без ручной валидации)

| Ситуация | Поведение бота |
|---|---|
| Сервис не генерируется (job/oif не поддержан для профиля) | ОТМЕЧАЕТСЯ в отчёте, обход продолжается |
| Репозиторий недоступен / clone fail | `[FAIL]` в логе, переход к следующему |
| Нет helm-репо для company | `[FAIL] clone helm <company>`, сервисы этой company пропускают копирование |
| Один сервис упал | не влияет на остальные (асинхронно, `--jobs`) |

## Требования к окружению бота

- `git`, `python3` + PyYAML, `go`, `docker`;
- бинарники `slokit` и `slo-kit` (`~/.local/bin`) или каналы их установки;
- git-доступ к `git.ecom.tech` (HTTPS через `~/.netrc`, или SSH ключ);
- внутренний DNS (для Docker-контура пробрасывается из host `resolv.conf`).

Проверка готовности: `./sloth-bot.sh --check` (или `./install-tools.sh --check`).

## См. также

- `sloth-bot.sh` — исполняемый цикл бота.
- `generate-sloth.sh` — сам пайплайн генерации.
- `services-slogen.yaml` — источник правды.
- `README.md`, `~/.config/opencode/skills/slo-monitoring/README.md` — полная документация (в hub: `skills/slo-monitoring/README.md`).
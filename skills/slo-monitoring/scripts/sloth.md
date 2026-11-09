---
name: sloth
description: Клонирование репозиториев сервисов из services-slogen.yaml в ./apps/<company>/ и генерация/обновление SLO (sloth.yaml) с публикацией в ./helm/<company>.
agent: build
subtask: true
---

# /sloth — генерация SLO-мониторинга для сервисов

Команда читает `services-slogen.yaml` (список сервисов в YAML), для каждого сервиса:
1. клонирует репозиторий (`repo:`) в `./apps/<company>/<имя>` (разделение по company, как и helm; если клона ещё нет) либо обновляет существующий (`git pull`), до-создавая недостающие файлы;
2. генерирует `configs/slo-kit.yaml`, `configs/slo.yaml`, `configs/alerts.yaml`, `configs/sloth.yaml`;
3. выполняет `slo-kit lint`;
4. копирует `configs/sloth.yaml` в каждый каталог из блока `helm:` (в `./helm`).

Имена каталогов в `./apps/` разделяются по компании (`./apps/<company>/<имя>`,
как и helm-репо `./helm/<company>`), что даёт уникальность каталогов даже при
совпадении имён у сервисов разных компаний; при коллизии в пределах одной
компании добавляется суффикс `-2`, `-3`, …

Эта команда — тонкая обёртка над `./generate-sloth.sh` (см. его `--help`).

## Использование

```bash
# все сервисы из services-slogen.yaml, до 4 параллельных процессов
./generate-sloth.sh

# один сервис по имени
./generate-sloth.sh <name>

# ограничить параллельность
./generate-sloth.sh --jobs 2

# не трогать git-ветки (только перегенерировать файлы)
./generate-sloth.sh --skip-git

# не клонировать/обновлять, использовать уже существующие ./apps/*
./generate-sloth.sh --no-clone
```

## Профили (известное ограничение slo-kit)

`slokit generate` записывает профиль (`profile:`) в `slo-kit.yaml` 1-в-1 из `services-slogen.yaml`. Текущий `slo-kit` (v26.10.1) принимает только
`[kuper-go, kuper-ruby, kuper-python, ecomtech-letsgo, ecomtech-kotlin, ecomtech-python]`.
Поэтому в `generate-sloth.sh` задан `PROFILE_MAP`, который нормализует rejected-профили
(сейчас `ecom-go-legacy` → `ecomtech-letsgo`) автоматически. См. README.

## Про коммиты

Скрипт сам **не** коммитит и не пушит. После генерации вручную выполняйте в репозиториях
(сервисов и helm) `git add` + `git commit` на ветке `feature/sloth`, затем push.

## Связанные файлы

- `services-slogen.yaml` — источник правды (список сервисов)
- `sloth-parse.py` — Python-PyYAML парсер (вывод TSV)
- `generate-sloth.sh` — исполнитель всего пайплайна
- `helm/` — корень helm-репозитория (всегда в корне набора)
---
title: Поиск и навигация
purpose: Дать проверенные рецепты поиска по репозиторию и правила навигации в Obsidian.
audience: [ai-agent, human]
read_when: [нужно найти ИС или значение без скрипта, ищете «где посмотреть критичность ИС X», настраиваете Obsidian]
updated: 2026-11-24
status: actual
related: [07-scripts.md, 05-mapping.md, 09-pipeline.md]
---

# Поиск и навигация

## Когда читать

- Читать, когда нужно найти ИС, поле или page_id и непонятно, где искать.
- Читать, когда `grep`/`find` дают пустой результат и нужно понять, ожидаемо ли это.
- Читать, когда открываете репозиторий как vault в Obsidian.

## Кратко

- Канонические рецепты даны на `grep`/`find`: они есть в любом окружении; `rg`-эквивалент указан рядом.
- Точка входа для поиска — `catalog.yaml`; точка входа для машинной выборки — `make show IS=<код>`.
- Любое изменение критичности обязано оставить след в трёх местах: `criticality-passport.yaml`, `CRITICALITY.md`, `INDEX.md`.
- Пустой результат по `Mission critical`, `reassessment-*.md` и `apps/` (до `make prepare-apply` / `make services-apply`) — ожидаемое состояние, а не поломка поиска.
- SSoT не ищется `grep` по файлам: карточку читает `ssot_get` (список — `ssot_list`), снимок лежит в `INFORMATION.yaml → ssot_snapshot`.

Репозиторий устроен так, чтобы по нему можно было искать без специального
инструмента: `grep`, `find`, Obsidian и один скрипт покрывают все типовые
вопросы.

## 1. Соглашения об именах

| Файл | Где | Зачем именно так |
|------|-----|------------------|
| `criticality-passport.yaml` | `is/<код ИС>/` | Одно и то же имя во всех ИС → `find is -name 'criticality-passport.yaml'` находит все паспорта |
| `CRITICALITY.md` | рядом с YAML | Капс, чтобы отличать человекочитаемый паспорт от служебного `README.md` и не путать с документацией |
| `README.md` | `is/<код ИС>/` | Ссылки на Confluence и GitLab ИС в frontmatter (`source_confluence_is`, `source_gitlab`); стандартное имя для просмотра папки |
| `reassessment-YYYY-MM-DD.md` | рядом | Дата в имени = сортировка и отсутствие перезаписи: каждая переоценка отдельный файл |
| `SERVICE-FINDINGS.md` | `is/<код ИС>/` | Имя фиксировано шаблоном и скриптом: отчёт о клонах сервисов (`docs/`, `openspec/`, нормативы, «вход → основание»), перезаписывается `make services-apply` |
| `catalog.yaml` | корень | Единственный машиночитаемый реестр; имя фиксировано в скриптах |
| `INDEX.md` | корень | Генерируемая сводка; капс, чтобы стояла рядом с `README.md` и бросалась в глаза |

Папки: `is/<код ИС>/` — плоская раскладка, имя папки совпадает с кодом ИС
`<name_is>.<контур>` (например `is/erm.mm/`, `is/cc-exchanger.smkt/`), где
`<контур>` — `mm` или `smkt`, а `<name_is>` — латиница в нижнем регистре,
допускается дефис (`cc-exchanger`).

## 2. `catalog.yaml` — единственный реестр

Это точка входа для скриптов и для человека, который не помнит кодов.
В нём на каждую ИС: код, название, контур, актив, путь, продукт, arch code,
команда, SA, критичность, маппинг в SSoT, все page_id, GitLab-группа, dochub
object, даты и статус.

Правила:

- Добавили ИС — добавили запись (или `make scaffold`, он сделает сам).
- Изменили критичность — изменили и в реестре, и в паспорте. Иначе `make validate` даст WARN `CONFLICT` (не ERROR).
- Не удаляйте записи «на время»: ИС из реестра без папки — WARN, папка без записи — ERROR.

## 3. Рецепты поиска

### Инструменты

| Инструмент | Наличие | Роль |
|------------|---------|------|
| `grep` | есть всегда (GNU grep в составе базовой системы) | **канонические рецепты ниже — на нём** |
| `find` | есть всегда | поиск файлов по имени |
| `ripgrep` (`rg`) | может отсутствовать — проверка `command -v rg` | опциональное ускорение; эквивалент на `grep` дан рядом с каждым рецептом |
| `yq` / `jq` | опционально | разбор YAML/JSON, см. §4 |

Все команды выполняются из корня репозитория. Если `command -v rg` ничего не
вернул — берите `grep`-вариант: он даёт тот же результат, только медленнее на
больших деревьях. Флаги `grep`, использованные ниже: `-r` — рекурсивно,
`-n` — с номерами строк, `-l` — только имена файлов, `--include='шаблон'` —
фильтр по имени файла, `-E` — расширенное регулярное выражение.

### Найти все паспорта

```bash
find is -name 'criticality-passport.yaml'
grep -rl --include='criticality-passport.yaml' 'ecom.criticality_passport' is
```

`find` — самый прямой способ; `grep -rl` перечисляет те же файлы, отбирая их по
содержимому (dochub-объект `ecom.criticality_passport` есть в каждом валидном
паспорте).

`rg`-эквивалент: `rg --files -g 'criticality-passport.yaml'`.

### По коду ИС

```bash
grep -rn --include='*.md' --include='*.yaml' 'erm\.mm' is catalog.yaml docs
grep -rl --include='*.md' --include='*.yaml' 'erm\.mm' is catalog.yaml docs   # только имена файлов
```

`rg`-эквивалент: `rg -n 'erm\.mm' is catalog.yaml docs` и `rg -l 'erm\.mm' is catalog.yaml docs`.

### По уровню критичности

```bash
grep -rn 'Business critical' catalog.yaml is
grep -rn 'object_criticality_estimation: Mission critical' is
```

`rg`-эквивалент: `rg -n 'Business critical' catalog.yaml is`.

В текущем состоянии репозитория результат второй команды **пуст по существу**:
среди шести ИС E001 нет ни одной уровня `Mission critical` — максимальный
уровень `Business critical`. Это не поломка поиска.

### По команде

```bash
grep -rn 'team: T102' catalog.yaml
grep -rn 'T102' is
```

`rg`-эквивалент: `rg -n 'team: T102' catalog.yaml`, `rg -n 'T102' is`.

### По метке Obsidian

```bash
grep -rn --include='*.md' 'паспорт-критичности' .
grep -rn --include='*.md' 'tags:.*business-critical' is
```

`rg`-эквивалент: `rg -n 'паспорт-критичности' --glob '*.md'`, `rg -n 'tags:.*business-critical' is`.

В YAML-frontmatter тег хранится без `#` (`tags: [..., паспорт-критичности, ...]`),
поэтому `#` в шаблон поиска не ставится — иначе `grep`/`rg` ищет решётку,
которой в файле нет. В самом Obsidian тег по-прежнему пишется как
`#паспорт-критичности`.

### По page_id

```bash
grep -rn '3995290956' .
```

`rg`-эквивалент: `rg -n '3995290956' .`.

### По незаполненным полям (что осталось собрать)

```bash
grep -rn --include='criticality-passport.yaml' ': null' is
grep -rn --include='CRITICALITY.md' '⛔ не заполнено' is
grep -rn --include='CRITICALITY.md' '\- \[ \]' is
```

`rg`-эквиваленты: `rg -n ': null' is --glob 'criticality-passport.yaml'`,
`rg -n '⛔ не заполнено' is --glob 'CRITICALITY.md'`,
`rg -n '\- \[ \]' is --glob 'CRITICALITY.md'`.

### По истории переоценок

```bash
find is -name 'reassessment-*.md'
grep -rn --include='reassessment-*.md' 'Новая критичность' is
```

`rg`-эквивалент: `rg --files -g 'reassessment-*.md'`, `rg -n 'Новая критичность' is --glob 'reassessment-*.md'`.

В текущем состоянии репозитория результат **пуст по существу**: переоценок ещё
не проводилось, ни одного `reassessment-*.md` нет. Первый файл создаёт
`make reassess-apply IS=<код>` (план — `make reassess IS=<код>`; см.
[04-reassessment.md](04-reassessment.md)).

### По входному конфигу `is.yaml`

```bash
grep -n -e '\.mm:' -e '\.smkt:' is.yaml
```

`rg`-эквивалент: `rg -n '\.mm:|\.smkt:' is.yaml`.

`is.yaml` gitignored и может отсутствовать — это входной конфиг для анализа
(см. `INFORMATION.md` в корне проекта), а не часть репозитория. Если файла
нет, `grep` вернёт ошибку «No such file» — это ожидаемо.

### Проверка «нет кириллицы в кодах»

```bash
grep -rnE '[А-Яа-яЁё]0*01\b' --include='*.md' --include='*.yaml' .
```

Код возврата `grep`: `0` — находки есть (это ERROR, печатаются путь и строка),
`1` — находок нет (проверка пройдена), `2` — ошибка вызова (например, битый
шаблон). **Не добавляйте `|| echo "кириллицы нет"`** — такая конструкция
превращает любую ошибку (включая `command not found` при отсутствии `rg`) в
ложный успех. Если сомневаетесь в коде возврата, проверьте его явно:

```bash
grep -rnE '[А-Яа-яЁё]0*01\b' --include='*.md' --include='*.yaml' .; echo "grep exit=$?"
```

`rg`-эквивалент: `rg -n '[А-Яа-яЁё]0*01\b' --glob '*.md' --glob '*.yaml' .`.

Ту же проверку автоматически и надёжнее выполняет `make validate`
(`python3 .opencode/skills/criticality-gen/scripts/criticality.py validate`) — по всем `.md`/`.yaml` репозитория,
кроме `.git`; находка даёт ERROR с путём и номером строки, а отсутствие
инструмента исключено (проверка встроена в скрипт).

### Данные ИС в SSoT

SSoT не ищется `grep` по файлам — локального клона нет. Карточка читается
MCP-инструментами:

```text
ssot_get(group="information-systems", entity="<name_is>.<контур>")  # карточка ИС
ssot_list(group="information-systems")                              # если код неизвестен
ssot_team(code="<team>")                                            # ростер команды
```

`<name_is>.<контур>` — полный код ИС, ровно как в `catalog.yaml` (например
`erm.mm`, `cc-exchanger.smkt`). Ответ `ssot_get` приходит секциями карточки
(`base`, `components`, `duty`, `links`, `resources`, `roles`); критичность
лежит в `base → severity` (`severity.type`, `severity.confirmation`), поэтому
поиск по `criticality` вернёт пусто. Снимок ответа в репозитории —
`INFORMATION.yaml → ssot_snapshot` (его пишет `make ssot-import IS=<код>
ENTITY_JSON=-`): по нему работают `grep`-рецепты, когда MCP недоступен.

Навигация по карточке — `ssot_entity_open(group="information-systems",
entity=<код>)`: открывает форму карточки (дальше `ssot_form_fields`), это
точка входа и для чтения, и для точечной правки `severity.*`.

> **Важно.** Если MCP `ssot-mcp` не авторизован (`ssot_status` ≠
> `authorized`), `ssot_get` вернёт `auth_required`: сначала `ssot_status`,
> при необходимости `ssot_login`, затем повтор. Веб-UI SSoT:
> https://ssot.ecom.tech/.

### Документация клонов сервисов

```bash
find 'apps/<код ИС>' -maxdepth 2 -type d \( -name docs -o -name openspec \)
grep -rln --include='*.md' 'API' 'apps/<код ИС>'
grep -n 'норматив' 'is/<код ИС>/SERVICE-FINDINGS.md'
```

`apps/<код ИС>/<сервис>/` — клоны сервисов: в них ищут назначение сервиса,
заявленные нормативы (SLA/RTO, PDB), потоки и обработку данных. Начинать обычно
надо не с `grep` по клону, а с `is/<код ИС>/SERVICE-FINDINGS.md`: там уже собраны
цитаты «файл:строка», таблица «вход → основание» и раздел «не найдено».
Компоненты с `lifecycle: closed` не клонируются и в отчёт не попадают, а сборка
и запуск кода сервисов запрещены — в `apps/` работает только `git`.

`rg`-эквивалент: `rg --files 'apps/<код ИС>' -g 'docs/**'`,
`rg -l 'API' 'apps/<код ИС>' -g '*.md'`.

> **Важно.** Каталог `apps/` **не версионируется**: он появляется после
> `make prepare-apply` (клоны компонентов из SSoT) и `make services-apply`
> (обновление клонов + `SERVICE-FINDINGS.md`). До этого `find`/`grep` вернут
> пусто — это ожидаемо.

## 4. Доступ «как к JSON»: `show --is`

Вместо `yq`/`jq` (их может не быть в окружении) используйте встроенную команду:

```bash
python3 .opencode/skills/criticality-gen/scripts/criticality.py show --is erm.mm
```

Она печатает все поля паспорта и ссылки. Для машинной обработки удобнее читать
`catalog.yaml` тем же мини-парсером:

```bash
python3 - <<'EOF'
import importlib.util
spec = importlib.util.spec_from_file_location("cp", ".opencode/skills/criticality-gen/scripts/criticality.py")
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)
data = cp.load_yaml("catalog.yaml")
for s in data["systems"]:
    print(s["code"], "|", s["criticality"], "|", s["team"])
EOF
```

Если `yq` установлен, он тоже работает — `catalog.yaml` обычный YAML:

```bash
yq '.systems[] | [.code, .criticality, .team] | join(" | ")' catalog.yaml
```

## 5. Obsidian

Репозиторий открывается как vault. Навигация строится на трёх механизмах:

**Теги.** В frontmatter каждого паспорта:

```yaml
tags: [критичность, паспорт-критичности, ис, mm, erm, e001, business-critical]
```

Поиск в Obsidian:

| Запрос | Что найдёт |
|--------|------------|
| `tag:#паспорт-критичности` | все паспорта ИС |
| `tag:#mm` | все паспорта контура ММ |
| `tag:#business-critical` | все ИС уровня Business critical |
| `tag:#переоценка` | файлы переоценок |
| `path:reassessment` | все `reassessment-*.md` |

**Frontmatter.** Поля `criticality`, `team`, `contour`, `status` доступны
плагину Dataview, если он установлен. Пример запроса:

````text
```dataview
TABLE criticality, team, review_date, status
FROM "is"
WHERE type = "criticality-passport"
SORT criticality DESC
```
````

**Aliases.** В `aliases` лежат полное название, код и arch code:

```yaml
aliases: [Единое рабочее место оператора ММ, erm.mm, E001.A11]
```

Поэтому `[[Единое рабочее место оператора ММ]]` и `[[erm.mm]]` ведут в один и
тот же файл. Ссылайтесь в заметках на удобное имя — Obsidian сам подставит
правильную ссылку.

**Обратные ссылки.** Каждый `CRITICALITY.md` ссылается на `catalog.yaml`,
`INDEX.md` и документацию — панель backlinks показывает, из каких мест
пришли к паспорту.

## 6. Таблица «что искать → где → чем»

| Что искать | Где | Чем |
|------------|-----|-----|
| Критичность конкретной ИС | `catalog.yaml`, `is/*/CRITICALITY.md` | `make show IS=<код>`, `grep -rn '<код>' is` |
| Все ИС уровня Business critical | `catalog.yaml` | `grep -rn 'Business critical' catalog.yaml` |
| ИС команды T102 | `catalog.yaml` | `grep -rn 'T102' catalog.yaml` |
| Паспорт в формате dochub | `is/*/criticality-passport.yaml` | `find is -name 'criticality-passport.yaml'` |
| Что не заполнено | паспорта и CRITICALITY.md | `grep -rn --include='criticality-passport.yaml' ': null' is`, `grep -rn --include='CRITICALITY.md' '⛔ не заполнено' is` |
| История оценок ИС | `reassessment-*.md`, раздел 9 CRITICALITY.md | `find is -name 'reassessment-*.md'` |
| Что просрочено | `catalog.yaml` + паспорта | `make due` |
| Страница Confluence ИС | `catalog.yaml` → `confluence_page_id` | `grep -rn '<page_id>' .` |
| GitLab-группа ИС | `catalog.yaml` → `gitlab_group` | `grep -rn 'gitlab_group' catalog.yaml` |
| Ответственный | `catalog.yaml` → `sa`; реестр ответственных | `make show IS=<код>` |
| Список ИС для анализа (входной конфиг) | `is.yaml` в корне (gitignored, см. `INFORMATION.md` в корне проекта) | `cat is.yaml`, `grep -n -e '\.mm:' -e '\.smkt:' is.yaml` |
| Критерии расчёта (шкалы, матрицы, веса, границы) | `.opencode/skills/criticality-gen/criteria/criticality-criteria.yaml` | `make criteria`, `make criteria-check` |
| Данные ИС в SSoT (сервисы, репозитории, дежурства, роли, размещение) | карточка ИС в SSoT (веб-UI https://ssot.ecom.tech/); снимок — `INFORMATION.yaml → ssot_snapshot` | `ssot_get(group="information-systems", entity="<код>")`, `ssot_list`; навигация — `ssot_entity_open` |
| Документация клонов сервисов (назначение, нормативы, потоки) | `apps/<код ИС>/<сервис>/docs/`, `openspec/`; готовые цитаты — `is/<код ИС>/SERVICE-FINDINGS.md` (`apps/` не версионируется, появляется после `make prepare-apply` / `make services-apply`) | `find 'apps/<код ИС>' -maxdepth 2 -type d \( -name docs -o -name openspec \)`, `grep -n 'норматив' 'is/<код ИС>/SERVICE-FINDINGS.md'` |

Все команды колонки «Чем» проверены в текущем состоянии репозитория; где
результат пуст по существу (Mission critical, `reassessment-*.md`), это отмечено
в §3. Если установлен `ripgrep`, любую
команду `grep -rn` можно заменить на `rg -n`, `grep -rl` — на `rg -l`,
`find … -name` — на `rg --files -g`.

## 7. Правило трёх следов

**Любое изменение критичности обязано оставить след в трёх местах:**

1. `criticality-passport.yaml` — каноническое значение (источник истины для dochub).
2. `CRITICALITY.md` — сводка, обоснование и строка в истории оценок.
3. `INDEX.md` — перегенерируется командой `make index` (руками не править).

Плюс синхронизация с `catalog.yaml` (проверяется `make validate`) и с SSoT
(ручной шаг, см. [05-mapping.md](05-mapping.md)). Если хотя бы один след
отсутствует — оценка считается незавершённой.

## 8. Связанные документы

- [04-reassessment.md](04-reassessment.md) — что делать после того, как нашли
- [05-mapping.md](05-mapping.md) — все идентификаторы и page_id
- [07-scripts.md](07-scripts.md) — полный справочник команд

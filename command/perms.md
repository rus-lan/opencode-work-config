---
description: Политика прав — что разрешать, что спрашивать, что запрещать; сверка накопленных «always» с конфигом
---
Разбери политику прав: $ARGUMENTS (пусто = весь срез).

Цель — не список команд, а решение по каждому правилу: allow, ask или deny. Права расширяются только
осознанно: кнопка «always» в диалоге расширяет их молча, мимо ревью.

## 1. Источники

| что | где | смысл |
|---|---|---|
| зафиксированная политика | `~/.config/opencode/opencode.jsonc`, секция `permission` | что решили осознанно |
| накопленные «always» | `~/.local/share/opencode/opencode.db` → `oc.permission` | что разрешили кнопкой |
| история решений | `~/.local/share/opencode/retro/sessions.jsonl` (плагин `session-retro`) | что спрашивали и как ответили: `once` / `always` / `reject` |
| фактическое использование | `h.tool_calls.target` (duck-harness) | что реально нужно |

Запросы (CLI `duck-harness --snapshot=false`, MCP-сервер падает на снапшоте):

```bash
D=~/Documents/ECOM/mcps/duck-harness/bin/duck-harness
$D --snapshot=false --format tsv --sql "select action, resource from oc.permission order by 1,2"
$D --snapshot=false --format tsv --sql "select target, count(*) n from h.tool_calls
  where tool in ('bash','shell') and target is not null group by 1 order by n desc limit 100"
```

Конфиг: `awk '/^    "bash": \{/,/^      "\*": "ask"/' opencode.jsonc`.

История решений по правам:

```bash
tail -200 ~/.local/share/opencode/retro/sessions.jsonl | jq -r '.permissions[]? | [.action,.reply,.resource] | @tsv'
```

## 2. Критерий — три класса

**allow** — read-only, обратимо, без сети и без чужого состояния. Ошибка стоит потерянного времени,
не данных: `ls`, `head`, `tail`, `wc`, `grep`, `rg`, `find`, `sed -n`, `jq`, `sort`, `uniq`, `cut`,
`git log|status|diff|show|blame|rev-parse`, `go build|test|vet|fmt`, `cargo check|test|clippy`,
`make test|check|ci`, `ast-index`, `skill-search`, `watcher`.

**ask** — пишет или ходит наружу, откат неочевиден из текста команды: `cp`, `mv`, `ln`, `rm`,
`mkdir`, `git add|commit|checkout|reset|rm|push|pull|merge|stash`, `npm|pip install`, `go get`,
`docker *`, `curl|wget`, `python3|node|ruby|perl|source`, `kill|pkill`, `open`, `sqlite3`,
`make install`, `webfetch`.

**deny** — восстановление невозможно или раскрывается секрет: `~/.secrets/*`, `*.env`, `*.zshrc`,
ssh-ключи, `rm -rf`, `git push --force`, `git reset --hard`, `sudo`, `security *`, `chmod 777`.

Как решать спорный случай:

1. **Паттерн узкий.** `python3 *` не бывает allow — только конкретный скрипт (`python3 ./scripts/lint.py`).
   Широкий allow прячет всё, что допишут в команду справа.
2. **`"*": "ask"` — база.** Allow добавляется по факту использования, а не заранее «на всякий случай».
3. **Секрет и деструктив — только deny**, даже если команда выглядит безобидно: `head ~/.secrets/x`
   читает секрет так же, как `cat`.
4. **Правило без использования 60 дней удаляется.** Разрешённое «на всякий случай» — это поверхность атаки.

## 3. Что делать с расхождениями

- **promote** — используется часто, класс allow → добавить в `permission.bash` конфига.
- **promote по сигналу** — ответ `once` на одно и то же правило три раза и больше, при этом `reject` = 0 →
  в конфиг.
- **единичный `reject` ничего не решает.** Один отказ — случайность или невнимательность, а не позиция:
  правило остаётся в `ask`, решение откладывается до следующего среза. Пересматривать, только если
  отказ повторится.
- **`reject` дважды и больше** → в allow не добавлять: это уже решение, а не промах.
- **исключение — класс deny.** Один `reject` на `rm -rf`, `.secrets`, `git reset --hard` подтверждает
  `deny` сразу: здесь сомнений нет, и цена ошибки несопоставима.
- **demote** — в `oc.permission` лежит то, что конфиг держит в `ask` (`curl *`, `rm *`, `docker run *`,
  `git push *`, `python3 *`) → убрать накопленное правило, оставить ask.
- **deny** — попало в «always», но класс deny → убрать правило и, если паттерн реально встречается,
  добавить явный `deny` в конфиг.
- **мусор** — правило не использовалось 60 дней → убрать.

## 4. Применение — только с подтверждением

1. Покажи таблицу решений: правило → класс → действие → причина.
2. Правку `opencode.jsonc` делай после явного «да», с бэкапом `opencode.jsonc.bak-<дата>`.
3. Удаление строк из `oc.permission` — прямая правка SQLite. Без отдельного подтверждения не трогать:
   сначала бэкап базы, затем `delete from permission where action=? and resource=?` по одному правилу.
4. После правки — `/reload`, затем одна проверка: команда из класса ask должна снова спрашивать.

## 5. Ответь коротко

Сколько правил накоплено, сколько расходятся с конфигом, сколько из них класс ask/deny.
Главный риск — одной строкой. Что предлагаешь сделать — списком, без применения.

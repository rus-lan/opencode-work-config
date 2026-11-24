# use-modern-go

Агентский скилл: современные идиомы Go с учётом целевой версии языка. Сводка
54 правил из e001-ai-hub (Go 1.0–1.27), разложенная по
категориям в `references/`. Работает офлайн: без CLI, без сети, без установки
зависимостей.

## Зачем

Go развивается быстро: `any`, `slices`/`maps`, `errors.Is`, `for range n`,
`t.Context()`, `encoding/json/v2` и десятки других улучшений появились в разных
версиях. Агент, который «знает современный Go», часто предлагает конструкцию,
которой нет в целевом `go.mod`, и ломает сборку.

Этот скилл сначала определяет целевую версию, затем отбрасывает правила, чей
`since` больше неё, и применяет только совместимые идиомы — к новому коду и к
строкам, которые и так меняются.

## Когда использовать

- Пишешь, правишь, исправляешь или рефакторишь Go-код (`.go`, `go.mod`).
- Нужно заменить устаревший паттерн на идиоматичный для конкретной версии Go.
- Проверяешь, совместима ли современная конструкция с целевой версией проекта.

Не для миграции «всего проекта на новый Go» без запроса: старый стиль сам по
себе не дефект.

## Установка

### opencode (глобально)

```bash
git clone <repo> use-modern-go
cp -r use-modern-go ~/.config/opencode/skills/use-modern-go
```

Или одной командой через установщик компонента:

```bash
curl -fsSL -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub/repository/files/skills%2Fuse-modern-go%2Finstall.sh/raw?ref=main" \
  | USE_MODERN_GO_TOKEN="$GITLAB_TOKEN" sh
```

`install.sh` ставит скилл в `~/.config/opencode/skills/`; флаг `--claude`
дополнительно ставит в `~/.claude/skills/`. Внутри клона репозитория
`./install.sh` работает без сети.

### opencode (в проект)

Скопировать каталог скилла в `.opencode/skills/use-modern-go` — скилл станет
доступен только в этом проекте.

## Использование

Скилл активируется автоматически при работе с Go-кодом. Обязательный workflow:

1. **Определить целевую версию** — по `go.mod`, затем `go.work`, затем
   `go version`; явно названная пользователем версия важнее.
2. **Отфильтровать правила** — отбросить всё, у чего `since` больше целевой
   версии (кроме явного запроса на модернизацию/апгрейд).
3. **Открыть только нужные справочники** — по индексу в `SKILL.md`, не читая
   все файлы подряд.
4. **Применить и проверить** — предпочитать форму «Хорошо (после)», убедиться,
   что код компилируется на целевой версии и не меняет поведение.

## Что внутри

```
use-modern-go/
  SKILL.md                    # workflow, индекс 54 правил, правила применения
  references/
    collections.md            # slices/maps, min/max, clear
    context.md                # t.Context, AfterFunc, WithCancelCause
    errors.md                 # errors.Is/As/AsType, errors.Join
    fmt.md                    # fmt.Appendf
    http.md                   # method-aware ServeMux, PathValue
    json.md                   # encoding/json/v2, omitzero
    loops.md                  # for range n, loop variable capture
    strings.md                # Cut/CutPrefix/CutSuffix, SplitSeq, Clone
    sync.md                   # wg.Go, OnceFunc/OnceValue, typed atomics
    testing.md                # b.Loop
    time.md                   # time.Since/Until, time.Tick
    types.md                  # any, reflect.TypeFor, generic methods
    url.md                    # URL.Clone, Values.Clone
    utilities.md              # uuid, new(value), cmp.Or
  install.sh                  # установщик (opencode, опция --claude)
  scripts/release.sh          # сборка релизного бандла
```

## Принципы

1. Совместимость с целевой версией важнее «самого нового» синтаксиса.
2. Правило не применяется, если меняет наблюдаемое поведение.
3. Старый, но рабочий код не переписывается без запроса.
4. Правка минимальна и обозрима; несвязанный код не трогается.
5. После правок запускаются известные проекту build/test/lint.

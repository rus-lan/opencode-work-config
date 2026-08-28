# Opencode Rules

Правила для сабагентов-разработчиков (react-dev, go-dev, rust-dev).
Загружаются через `skill("rule-name")` или по совпадению с задачей.

## Индекс (11 правил)

| Правило | Для кого | Описание |
|---------|----------|----------|
| frontend-components | react-dev | Компонентная архитектура — ui-kit/ui/entity/widgets, CVA, Storybook, cn() |
| frontend-hooks | react-dev | Паттерны хуков — one per concern, return pattern, naming |
| frontend-theme | react-dev | Тема — CSS variables, data-theme, ThemeBox, генерация |
| frontend-zustand | react-dev | Zustand — создание сторов, persist, partialize, actions |
| go-backend | go-dev | Go — структура, ошибки, middleware, HTTP, тесты |
| go-observability | go-dev | Go — логгирование, метрики, трассировка, health checks |
| rust-errors | rust-dev | Rust — error enums, thiserror, severity, Mutex |
| tauri-bridge | rust-dev/react-dev | Tauri v2 — IPC, команды, события, безопасность |
| opencode-implementer | orchestrator | Как opencode работает как executor под оркестрацией |
| bmad-impl-story-cycle | orchestrator | BMAD цикл реализации — эпики, ревью по классу, Fable-гейт |
| git-commit-push | orchestrator | Глобальный запрет на git commit/push без явного разрешения пользователя |

## Замечание о размере правил

Правила загружаются каждому агенту через `"instructions": ["rules/*.md"]` в `opencode.json`. Суммарный вес правил ≈ 96 КБ (~20-25K токенов) на сессию, включая агентов, которым правила не нужны (например, `orchestrator` — read: deny, и `go-dev`, которому тащатся React-правила).

**Рекомендация:** если opencode 1.18.x поддерживает per-agent `instructions` во фронтматтере агента — вынести стеко-специфичные правила (frontend-components, frontend-theme, tauri-bridge и т.п.) из глобальных в per-agent, чтобы не инжектить нерелевантный контекст. Механизм загрузки в текущем конфиге не менялся — это ориентир на будущее.
# Opencode Rules

Правила для сабагентов-разработчиков (react-dev, go-dev, rust-dev).
Загружаются через `skill("rule-name")` или по совпадению с задачей.

## Индекс

| Правило | Для кого | Описание |
|---------|----------|----------|
| frontend-components | react-dev | Компонентная архитектура — ui-kit/ui/entity/widgets, CVA, Storybook, cn() |
| frontend-hooks | react-dev | Паттерны хуков — one per concern, return pattern, naming |
| frontend-theme | react-dev | Тема — CSS variables, data-theme, ThemeBox, генерация |
| frontend-zustand | react-dev | Zustand — создание сторов, persist, partialize, actions |
| go-backend | go-dev | Go — структура, ошибки, middleware, HTTP, тесты |
| rust-errors | rust-dev | Rust — error enums, thiserror, severity, Mutex |
| tauri-bridge | rust-dev/react-dev | Tauri v2 — IPC, команды, события, безопасность |
| opencode-implementer | orchestrator | Как opencode работает как executor под оркестрацией |
| bmad-impl-story-cycle | orchestrator | BMAD цикл реализации — эпики, ревью по классу, Fable-гейт |
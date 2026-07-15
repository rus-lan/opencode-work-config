---
name: full-workflow
description: Запускает полный workflow: grill-me → research → implement → review → testing
---

## Команда

Вызывается через: `/workflow [task]`

Если task не указан — использовать текущий контекст.

## Триггеры

Агент должен активировать этот скилл, когда пользователь говорит:
- `/workflow` или `/workflow <тема>`
- "запусти полный workflow"
- "оркестрация задачи"
- "full pipeline"
- "run orchestration"

## Процесс

### Stage 1: Grill-me + Research

1. **Grill-me** — интерактивный допрос плана
   - `skill("grill-me")`
   - Задавать провокационные вопросы
   - Уточнять требования

2. **Parallel Research** — 2-3 параллельных research агента
   - `task({ agent: "desearch-researcher", prompt: "Research angle 1: [конкретный угол]" })`
   - `task({ agent: "desearch-researcher", prompt: "Research angle 2: [другой угол]" })`
   - `task({ agent: "research", prompt: "Primary source investigation" })`

3. **Synthesize** — собрать findings в один документ

### Stage 2: Implementation

1. **Determine stack** — определить стек проекта
   - React/TypeScript → `react-dev`
   - Go → `go-dev`
   - Rust → `rust-dev`
   - Mixed/Unknown → `general`

2. **Parallel Implementation** — спавнить агентов по компонентам
   ```
   task({ agent: "react-dev", prompt: "Implement component A..." })
   task({ agent: "go-dev", prompt: "Implement API endpoint B..." })
   task({ agent: "rust-dev", prompt: "Implement module C..." })
   ```

3. **Wait for completion** — все агенты должны завершиться

### Stage 3: Review

1. **Parallel Review** — 2 параллельных ревьюера
   ```
   task({ agent: "reviewer", prompt: "Standards review — check code smells, conventions..." })
   task({ agent: "reviewer", prompt: "Spec review — check against requirements..." })
   ```

2. **Aggregate findings** — представить два axes отдельно

3. **Fix issues** — если есть критичные проблемы, исправить их

### Stage 4: Testing

1. **Run tests** — запустить тестовые suites
   - Unit tests
   - Integration tests
   - E2E tests (если есть)

2. **Parallel test agents** — при необходимости:
   ```
   task({ agent: "general", prompt: "Run unit tests and report failures" })
   task({ agent: "general", prompt: "Run integration tests and report failures" })
   ```

3. **Bug fixing** — если тесты падают:
   - `task({ agent: "diagnosing-bugs", prompt: "Fix test failures: [list]" })`
   - Re-run tests

4. **Final verification** — все тесты должны пройти

## Model Strategy

| Stage | Model |
|-------|-------|
| Grill-me | qwen3.5-122b |
| Research | deepseek-v4-flash:max |
| Implementation | qwen3.6-35b |
| Review | qwen3.5-122b |
| Testing | qwen3.6-35b |

## Output Format

После каждого этапа:

```
## Stage X Complete: [Stage Name]

**Summary**: 2-3 sentences

**Key Findings/Changes**:
- Bullet points

**Issues Found**: (if any)
- List of problems

**Next**: [Next stage] - ready to proceed? [Yes/No/Modify]
```

## Global Availability

Этот скилл доступен во всех проектах по умолчанию.

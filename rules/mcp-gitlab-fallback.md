---
name: mcp-gitlab-fallback
description: Fallback при сбоях GitLab MCP — ОДНА неудача MCP = немедленный переход на git clone в source/ ИЛИ REST API v4; повторных вызовов MCP в задаче нет
version: 2.0.0
---

# GitLab MCP — одна неудача, дальше git + REST API

## Когда применять

Когда задаче нужны файлы/дерево/код GitLab-репозитория, а MCP-сервер `gitlab` не отдаёт результат: ошибка авторизации (401/403), `aborted`/timeout/обрыв сессии, пустой или обрезанный ответ, ошибка инструмента, зависание без ответа, упор в лимит рекурсии или размера, слишком большой репозиторий.

Триггером fallback является **одна** неудача MCP GitLab, а сам fallback — это `git` **и** REST API.

## Правило одной попытки

- Любой сбой MCP GitLab — 401/403, timeout, `aborted`, пустой или обрезанный ответ, ошибка инструмента, зависание без ответа — это сигнал переключаться **немедленно**.
- Повторных вызовов MCP GitLab в этой задаче не делать: ни ретраев того же инструмента, ни других инструментов того же MCP-сервера.
- Не диагностировать MCP, не ждать «может, отвиснет», не пробовать другие аргументы.
- Fallback обязателен и состоит из двух путей: **git** (клон / `ls-remote` / `git show`) и **REST API** GitLab.

## REST API GitLab

Токен берётся из env `$GITLAB_TOKEN`. Значение не печатать и не логировать.

```bash
# проект по path
curl -sS -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://git.ecom.tech/api/v4/projects/ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub"

# дерево репозитория (рекурсивно, пагинация per_page=100)
curl -sS -H "PRIVATE-TOKEN: $GITLAB_TOKEN" -G \
  "https://git.ecom.tech/api/v4/projects/<URL-ENCODED-PATH>/repository/tree" \
  --data-urlencode "path=skills/criticality-gen" --data-urlencode "ref=main" \
  --data-urlencode "recursive=true" --data-urlencode "per_page=100"

# файл (base64)
curl -sS -H "PRIVATE-TOKEN: $GITLAB_TOKEN" -G \
  "https://git.ecom.tech/api/v4/projects/<URL-ENCODED-PATH>/repository/files/<URL-ENCODED-FILE-PATH>" \
  --data-urlencode "ref=main"
```

- `path` в URL кодируется как `group%2Fproject` (например `ecom%2Fdev%2Fcommon%2Fpersonal%2Fe001-ai-hub`).
- Для больших файлов предпочитать `git clone --filter=blob:none --sparse`, а не API.

## Что делать

1. Одна неудача MCP GitLab → сразу fallback, без повторных вызовов MCP.
2. Клонировать репозиторий локально в подпапку `source/` рабочего проекта (для больших репозиториев — `--filter=blob:none --sparse`):

   ```bash
   mkdir -p source
   git clone https://git.ecom.tech/<group>/<project>.git source/<project>
   ```

   Если HTTPS требует авторизации и падает — попробовать SSH:

   ```bash
   git clone git@git.ecom.tech:<group>/<project>.git source/<project>
   ```

   Для больших репозиториев — `--depth 1` (или `--filter=blob:none`, при необходимости `--sparse`), для конкретной ветки — `--branch <name>`. Нужна нестандартная ветка — `git fetch origin <branch> && git checkout <branch>`.

   **2b. Если клон невозможен или нужен точечный файл** — REST API GitLab (раздел «REST API GitLab» выше): `repository/tree` для дерева, `repository/files` для одного файла.
3. Обязательно добавить `source/` в `.gitignore` целевого проекта: создать файл, если его нет, иначе дописать строку, НЕ затирая существующее содержимое.
4. Дальше работать с локальным клоном (`git ls-files`, `rg`, `cat`, `tree`) — это быстрее и не раздувает контекст ответами MCP.
5. В отчёте указать: способ получения (git/API), путь, ветку, commit hash и дату.

## Запрещено

- Повторно вызывать MCP GitLab после первого сбоя в рамках задачи.
- Коммитить или пушить что-либо из клона без явного разрешения пользователя.
- Клонировать в каталоги проекта вне `source/`.
- Изменять содержимое клона: это read-only источник методики/кода.
- Обходить авторизацию, подбирать креды, отключать проверки TLS.

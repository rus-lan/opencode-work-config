---
name: confluence-links
description: Поиск и формирование ссылок в Confluence при работе через MCP. Применяется ко всем операциям с контентом Confluence через MCP (confluence_get_page / confluence_update_page / confluence_update_page_section и др.) в любом проекте.
version: 1.0.0
---

# Правила

## 1. Как искать ссылки на страницы (в raw storage)
- Читай страницу только через confluence_get_page(..., convert_to_markdown=False): raw storage-HTML сохраняет точную структуру ссылок (<ac:link>/<ri:page>/<a href>). Markdown её теряет.
- Ищи два типа «ссылок» на страницы Confluence:
  1. Явные <a href="https://space.samokat.ru/pages/viewpage.action?pageId=NNNN">…</a> — текст обычно голый URL или голый id.
  2. Ссылки по page_id, заданные текстом БЕЗ HTML-ссылки: pageId=NNNN или голый номер NNNN (например, в колонке «Источник» таблицы).

## 2. Какие ссылки преобразовывать
- Преобразовывай ТОЛЬКО ссылки на страницы домена https://space.samokat.ru/.
- Другие инстансы Confluence и внешние (GitLab, Grafana и т.п.) НЕ трогать.
- URL-формы на space.samokat.ru: viewpage.action?pageId=NNNN и display/SPACE/TITLE.
- Если page_id не находится на space.samokat.ru или не резолвится — пропустить, оставить как есть.
- Ничего не удалять: менять только представление ссылки, страница_id всегда сохранять.

## 3. Как получить корректные title/space_key
- Каждый page_id резолвь через confluence_get_page(page_id=NNNN, include_metadata=true, convert_to_markdown=False).
- Используй ТОЧНЫЙ title и реальный space_key из ответа. Не выдумывай названия — бери из get_page, иначе ссылка не соберётся.
- Правильный способ ссылки на страницу — Confluence storage <ac:link> (а не голый <a href>): резолвится платформой, человекочитаем и устойчив.

## 4. Как формировать ссылку (storage-разметка)
Самостоятельная ссылка / в ячейке таблицы:
<ac:link><ri:page ri:content-title="<точный title>" ri:space-key="<space_key>"/></ac:link>

В тексте (абзац, список, заголовок), когда важна читаемость и сохранение page_id — формат «кликабельное название [page_id]»:
<ac:link><ri:page ri:content-title="<точный title>" ri:space-key="<space_key>"/></ac:link> [<page_id>]

- page_id НЕ удалять: остаётся текстом рядом со ссылкой.
- Избегать публикации ссылки в виде голого URL https://space.samokat.ru/pages/viewpage.action?pageId=NNNN как текста ссылки.

## 5. Спецсимволы
- В ri:content-title / ri:space-key экранируй XML-спецсимволы (& → &amp;, <, >, "). Кириллица, тире, точки — как есть.

## 6. Запись изменений (лимит payload)
- update_page с большим body (> ~10 КБ) падает на JSON-сериализации («Expected }»). Не заливай всю страницу одним вызовом.
- Для страниц с таблицами/код-блоками/макросами правь ПО СЕКЦИЯМ через confluence_update_page_section(page_id, heading_text=<точный текущий заголовок>, content_format="storage"). Секция — маленький payload.
- Секция под заголовком меняется вместе с вложенными заголовками и содержимым до следующего заголовка того же/высшего уровня. Если ссылка в тексте заголовка H2/H3 — правишь через секцию родительского заголовка, вкладывая исправленный заголовок в new_content.
- После каждой записи — верификация confluence_get_page(..., convert_to_markdown=False): ac:link на месте и закрыт, нет остаточных viewpage.action?pageId= href, таблицы/код-макросы целы.
- Менять только запрошенный page_id; чужие страницы не трогать.

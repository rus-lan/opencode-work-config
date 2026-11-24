#!/usr/bin/env python3
"""Markdown → Confluence storage XHTML для страницы модели.

Зачем модуль: страница модели публикуется не агентом «руками», а телом,
которое готовит `trr model-page-payload`. Конвертер детерминированный и без
внешних зависимостей: тот же `.md` даёт те же байты storage.

Что поддерживается (и только это — страница модели других конструкций не
содержит):

* заголовки `#`…`######` → `<h1>`…`<h6>`;
* таблицы с шапкой (`<th>`) и строками (`<td>`); `\\|` внутри ячейки — литерал;
* fenced code → `<ac:structured-macro ac:name="code">` с `<![CDATA[…]]>`;
* списки `-`/`*`/`+` и `1.` → `<ul>`/`<ol>`;
* цитаты `>` → `<blockquote><p>…</p></blockquote>`;
* горизонтальная линия `---` → `<hr/>`;
* inline: `` `code` ``, `**strong**`, `*em*`, `[текст](url)`.

Вне `<![CDATA[…]]>` весь текст экранируется по XML: `&`, `<`, `>`.
"""

import re

__all__ = ["convert", "escape", "inline"]

# Литерал «нет данных» из источников — в storage он не должен превращаться в
# что-то другое: экранирование его не меняет.
_ESCAPES = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"))

HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
UL = re.compile(r"^(\s*)[-*+]\s+(.*)$")
OL = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
TABLE_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
FENCE = re.compile(r"^\s*```(\S*)\s*$")
HR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
CODE_SPAN = re.compile(r"`([^`]+)`")


def escape(text):
    """Экранировать XML-спецсимволы (`&`, `<`, `>`), не трогая порядок."""
    for source, target in _ESCAPES:
        text = text.replace(source, target)
    return text


def inline(text):
    """Экранировать текст и применить inline-markdown; code-спаны первыми."""
    out = []
    position = 0
    for match in CODE_SPAN.finditer(text):
        out.append(_inline_text(text[position : match.start()]))
        out.append("<code>%s</code>" % escape(match.group(1)))
        position = match.end()
    out.append(_inline_text(text[position:]))
    return "".join(out)


def _inline_text(text):
    value = escape(text)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", value)
    value = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        r'<a href="\2">\1</a>',
        value,
    )
    return value


def split_row(line):
    """Ячейки строки таблицы; `\\|` — литеральная черта, не разделитель."""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    cells, buffer, index = [], [], 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text) and text[index + 1] == "|":
            buffer.append("|")
            index += 2
            continue
        if char == "|":
            cells.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(char)
        index += 1
    cells.append("".join(buffer).strip())
    return cells


def _code_macro(language, body):
    return (
        '<ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="language">%s</ac:parameter>'
        "<ac:plain-text-body><![CDATA[%s]]></ac:plain-text-body>"
        "</ac:structured-macro>"
        % (escape(language or "text"), body.replace("]]>", "]]]]><![CDATA[>"))
    )


def convert(md):
    """Markdown → Confluence storage XHTML (одна строка на блок)."""
    lines = (md or "").split("\n")
    out = []
    index = 0
    total = len(lines)
    paragraph = []

    def flush_paragraph():
        if paragraph:
            out.append("<p>%s</p>" % inline(" ".join(paragraph)))
            del paragraph[:]

    while index < total:
        line = lines[index]
        stripped = line.strip()

        fence = FENCE.match(line)
        if fence:
            flush_paragraph()
            language = fence.group(1) or "text"
            index += 1
            body = []
            while index < total and not FENCE.match(lines[index]):
                body.append(lines[index])
                index += 1
            index += 1  # закрывающий fence
            out.append(_code_macro(language, "\n".join(body)))
            continue

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if HR.match(line):
            flush_paragraph()
            out.append("<hr/>")
            index += 1
            continue

        heading = HEAD.match(line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            out.append(
                "<h%d>%s</h%d>"
                % (level, inline(heading.group(2).strip()), level)
            )
            index += 1
            continue

        if (
            stripped.startswith("|")
            and index + 1 < total
            and TABLE_SEP.match(lines[index + 1].strip())
        ):
            flush_paragraph()
            header = split_row(lines[index])
            index += 2
            rows = []
            while index < total and lines[index].strip().startswith("|"):
                rows.append(split_row(lines[index]))
                index += 1
            buffer = ["<table><tbody>", "<tr>"]
            for cell in header:
                buffer.append("<th>%s</th>" % inline(cell))
            buffer.append("</tr>")
            for row in rows:
                buffer.append("<tr>")
                for cell in row:
                    buffer.append("<td>%s</td>" % inline(cell))
                buffer.append("</tr>")
            buffer.append("</tbody></table>")
            out.append("".join(buffer))
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            body = []
            while index < total and lines[index].strip().startswith(">"):
                body.append(re.sub(r"^\s*>\s?", "", lines[index]))
                index += 1
            text = " ".join(item.strip() for item in body if item.strip())
            out.append("<blockquote><p>%s</p></blockquote>" % inline(text))
            continue

        item = UL.match(line) or OL.match(line)
        if item:
            flush_paragraph()
            ordered = bool(OL.match(line))
            tag = "ol" if ordered else "ul"
            pattern = OL if ordered else UL
            buffer = ["<%s>" % tag]
            while index < total:
                current = lines[index]
                match = pattern.match(current)
                if not match:
                    break
                content = [match.group(3) if ordered else match.group(2)]
                index += 1
                while index < total:
                    following = lines[index]
                    following_stripped = following.strip()
                    if not following_stripped:
                        break
                    if UL.match(following) or OL.match(following):
                        break
                    if (
                        HEAD.match(following)
                        or following_stripped.startswith("|")
                        or following_stripped.startswith(">")
                        or HR.match(following)
                    ):
                        break
                    content.append(following_stripped)
                    index += 1
                buffer.append("<li>%s</li>" % inline(" ".join(content)))
                if index < total and not lines[index].strip():
                    following_index = index + 1
                    if following_index < total and pattern.match(lines[following_index]):
                        index = following_index
                        continue
                if index < total and not pattern.match(lines[index]):
                    break
            buffer.append("</%s>" % tag)
            out.append("".join(buffer))
            continue

        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    return "\n".join(out)

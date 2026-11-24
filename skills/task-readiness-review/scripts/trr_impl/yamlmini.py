#!/usr/bin/env python3
"""Минимальный парсер подмножества YAML на stdlib.

Поддерживается ровно то, что нужно конфигу `task-readiness-review.yaml`:

* вложенные словари по отступу (пробелы, шаг не фиксирован — важна вложенность);
* блочные списки `- item` и `- key: value`;
* комментарии `#` (только вне кавычек и только после пробела/начала строки);
* пустые строки;
* скаляры: `null`/`~`/`none`, `true`/`false`/`yes`/`no`, целые, float,
  строки в двойных и одинарных кавычках, bare-строки (в том числе с `:`,
  `,` и `#` внутри — они не ломаются);
* inline-списки `[1, 2, 3]` и inline-словари `{ FE: FE, BE: BE }`;
* блочные скаляры `|`, `|-`, `|+`, `>`, `>-`, `>+` — свободный текст с URL,
  запятыми и решётками сохраняется дословно;
* многострочные plain-скаляры: `key: начало текста` и дальше строки с большим
  отступом склеиваются в одно значение (см. «Многострочный plain-скаляр»).

Принцип: детерминизм и отсутствие сюрпризов важнее полноты YAML. Любая
неподдержанная конструкция — `YamlError` с номером строки, а не «тихо неверный»
результат. Поэтому встроенный парсер — единственный источник истины; PyYAML,
если он установлен, используется только в `cross_check()` для самопроверки
(selftest), но никогда не подменяет разбор.

Многострочный plain-скаляр
--------------------------

Значение, начатое в строке ключа без кавычек и не `|`/`>` (и не `[`/`{`),
продолжается следующими строками, если те:

* имеют отступ **больше** отступа ключа;
* не являются элементом списка (`- ` или `-`);
* не являются парой `ключ:` (двоеточие, за которым пробел или конец строки) —
  такая строка считается ошибкой отступа, как и раньше;
* не являются комментарием (`# …` в начале содержимого) — комментарий
  завершает скаляр, а не становится его частью.

Склейка — как в YAML folding:

* соседние строки соединяются **одним пробелом** (лишние пробелы по краям
  строки срезаются);
* каждая пустая строка внутри продолжения даёт **один перевод строки** `\n`
  (две пустые строки — два `\n`);
* пустые строки в конце продолжения отбрасываются (хвостового `\n` нет);
* скаляр не начинается со значений, разобранных не в строку (`5`, `true`,
  `null`) и не продолжается, если начат с кавычки или inline-коллекции:
  там продолжение по-прежнему ошибка отступа.

Пример:

```yaml
sources:
  reference: эталон оценки указан на странице в конфлюенсе
    https://space.samokat.ru/display/SPACE/Story+Points,
    копия — в obsidian, страница SP-эталон
```

даёт `"эталон оценки указан на странице в конфлюенсе https://…/Story+Points, копия — в obsidian, страница SP-эталон"`.
"""

import re

__all__ = ["YamlError", "cross_check", "load_file", "loads", "parse"]

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$")
# Внимание: `none` НЕ null — это легальное значение enum output_target,
# поэтому в списке только канонические формы YAML.
_NULLS = ("null", "~")
_TRUES = ("true", "yes")
_FALSES = ("false", "no")
_BLOCK_HEADERS = ("|", "|-", "|+", ">", ">-", ">+")


class YamlError(Exception):
    """Ошибка разбора YAML: сообщение, номер строки и (опционально) путь файла."""

    def __init__(self, message, line=None, path=None):
        self.message = message
        self.line = line
        self.path = path
        super().__init__(self._render())

    def _render(self):
        where = self.path or "<string>"
        if self.line is None:
            return "%s: %s" % (where, self.message)
        return "%s:%d: %s" % (where, self.line, self.message)


# ---------------------------------------------------------------------------
# Вспомогательные функции разбора строк
# ---------------------------------------------------------------------------


def _strip_comment(line):
    """Убрать комментарий, не задевая `#` внутри кавычек и внутри слова.

    YAML считает `#` началом комментария только в начале строки или после
    пробельного символа, поэтому `a#b` — это значение `a#b`.
    """
    out = []
    quote = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            out.append(char)
            if char == "\\" and quote == '"' and index + 1 < len(line):
                out.append(line[index + 1])
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'":
            quote = char
            out.append(char)
            index += 1
            continue
        if char == "#" and (index == 0 or line[index - 1] in " \t"):
            break
        out.append(char)
        index += 1
    return "".join(out)


def _find_key_colon(text):
    """Индекс двоеточия, отделяющего ключ от значения, или -1.

    Двоеточие вне кавычек и вне `[]`/`{}`, после которого идёт пробел или
    конец строки. Так `https://example.com` и `{a: b}` не принимаются за
    пару «ключ: значение».
    """
    quote = None
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'":
            quote = char
            index += 1
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        elif char == ":" and depth == 0:
            if index + 1 >= len(text) or text[index + 1] in " \t":
                return index
        index += 1
    return -1


def _split_commas(text):
    """Разбить по запятым верхнего уровня, не задевая кавычки и вложенность."""
    parts = []
    buffer = []
    depth = 0
    quote = None
    for char in text:
        if quote:
            buffer.append(char)
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
            buffer.append(char)
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(buffer).strip())
            buffer = []
            continue
        buffer.append(char)
    tail = "".join(buffer).strip()
    if tail:
        parts.append(tail)
    return parts


_YAML_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "0": "\0",
    '"': '"',
    "\\": "\\",
    "/": "/",
}


def _unescape_double(text):
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            nxt = text[index + 1]
            if nxt in _YAML_ESCAPES:
                out.append(_YAML_ESCAPES[nxt])
                index += 2
                continue
            raise YamlError("неизвестная escape-последовательность '\\%s'" % nxt)
        out.append(char)
        index += 1
    return "".join(out)


def _parse_scalar(token, path, line, column=1):
    """Разобрать скаляр (в том числе inline-список и inline-словарь)."""
    value = token.strip()
    if value == "":
        return None

    if len(value) >= 2 and value[0] == '"':
        if value[-1] != '"':
            raise YamlError("незакрытая двойная кавычка", line, path)
        try:
            return _unescape_double(value[1:-1])
        except YamlError as exc:
            raise YamlError(exc.message, line, path)
    if len(value) >= 2 and value[0] == "'":
        if value[-1] != "'":
            raise YamlError("незакрытая одинарная кавычка", line, path)
        return value[1:-1].replace("''", "'")
    if value[0] in "\"'":
        raise YamlError("незакрытая кавычка в значении %r" % value, line, path)

    if value.startswith("["):
        if not value.endswith("]"):
            raise YamlError("незакрытый inline-список '['", line, path)
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part, path, line, column) for part in _split_commas(inner)]

    if value.startswith("{"):
        if not value.endswith("}"):
            raise YamlError("незакрытый inline-словарь '{'", line, path)
        inner = value[1:-1].strip()
        if not inner:
            return {}
        result = {}
        for part in _split_commas(inner):
            if not part:
                continue
            split = _find_key_colon(part)
            if split < 0:
                raise YamlError(
                    "ожидался формат 'ключ: значение' в inline-словаре, получено %r"
                    % part,
                    line,
                    path,
                )
            key = _unquote_key(part[:split].strip(), path, line)
            result[key] = _parse_scalar(part[split + 1 :], path, line, column)
        return result

    lowered = value.lower()
    if lowered in _NULLS:
        return None
    if lowered in _TRUES:
        return True
    if lowered in _FALSES:
        return False
    if _INT_RE.match(value):
        return int(value)
    if _FLOAT_RE.match(value) and any(ch.isdigit() for ch in value):
        return float(value)
    return value


def _unquote_key(key, path, line):
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
        inner = key[1:-1]
        if key[0] == '"':
            return _unescape_double(inner)
        return inner.replace("''", "'")
    if not key:
        raise YamlError("пустой ключ перед ':'", line, path)
    return key


# ---------------------------------------------------------------------------
# Парсер
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, text, source):
        self.source = source
        self.lines = text.splitlines()
        self.index = 0

    # -- служебное ---------------------------------------------------------

    def _error(self, message, line):
        return YamlError(message, line, self.source)

    def _leading_spaces(self, raw):
        return len(raw) - len(raw.lstrip(" "))

    def _indent(self, raw, line):
        leading = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in leading:
            raise self._error(
                "табуляция в отступе не поддерживается, используйте пробелы", line
            )
        return len(leading)

    def _skip_blank(self):
        while self.index < len(self.lines):
            stripped = self.lines[self.index].strip()
            if stripped == "" or stripped.startswith("#"):
                self.index += 1
                continue
            break

    def _peek(self):
        """(номер строки, отступ, содержимое без комментария) следующей значимой строки."""
        self._skip_blank()
        if self.index >= len(self.lines):
            return None
        raw = self.lines[self.index]
        line = self.index + 1
        return line, self._indent(raw, line), _strip_comment(raw).strip()

    # -- разбор ------------------------------------------------------------

    def parse(self):
        self._skip_blank()
        if self.index >= len(self.lines):
            return {}
        line = self.index + 1
        indent = self._indent(self.lines[self.index], line)
        value = self._parse_block(indent)
        self._skip_blank()
        if self.index < len(self.lines):
            raise self._error(
                "не удалось разобрать строку: %r" % self.lines[self.index].strip(),
                self.index + 1,
            )
        if not isinstance(value, dict):
            raise self._error(
                "корневой элемент должен быть словарём, получено %s"
                % type(value).__name__,
                line,
            )
        return value

    def _parse_block(self, indent):
        peek = self._peek()
        if peek is None or peek[1] < indent:
            return None
        content = peek[2]
        if content == "-" or content.startswith("- "):
            return self._parse_list(indent)
        return self._parse_map(indent)

    def _parse_child(self, parent_indent):
        peek = self._peek()
        if peek is None or peek[1] <= parent_indent:
            return None
        return self._parse_block(peek[1])

    def _reject_deeper(self, parent_indent, line):
        peek = self._peek()
        if peek is not None and peek[1] > parent_indent:
            raise self._error(
                "неожиданный отступ %d — значение уже задано в строке %d"
                % (peek[1], line),
                peek[0],
            )

    # -- многострочный plain-скаляр ---------------------------------------

    @staticmethod
    def _is_plain_start(rest):
        """В строке ключа начат plain-скаляр (не кавычка, не `[`/`{`)."""
        if not rest:
            return False
        return rest[0] not in "\"'[{"

    @staticmethod
    def _continues_plain(content):
        """Строка — продолжение plain-скаляра, а не новая конструкция.

        Продолжением не считаются: элемент списка, пара `ключ:` и комментарий.
        Такие строки с большим отступом остаются ошибкой отступа — «тихо
        проглотить» чужой ключ было бы хуже, чем упасть с номером строки.
        """
        if content == "" or content.startswith("#"):
            return False
        if content == "-" or content.startswith("- "):
            return False
        return _find_key_colon(content) < 0

    def _parse_plain_continuation(self, parent_indent, value, line):
        """Склеить продолжение plain-скаляра по правилам YAML folding.

        `self.index` уже указывает на строку после ключа. Пустые строки внутри
        продолжения дают `\\n`; пустые строки, за которыми продолжения нет,
        не съедаются — их пропустит `_skip_blank`.
        """
        pieces = [value]
        pending_breaks = 0
        while self.index < len(self.lines):
            raw = self.lines[self.index]
            if raw.strip() == "":
                # Пустая строка — часть скаляра, только если дальше он ещё идёт.
                lookahead = self.index
                blanks = 0
                while (
                    lookahead < len(self.lines)
                    and self.lines[lookahead].strip() == ""
                ):
                    blanks += 1
                    lookahead += 1
                if lookahead >= len(self.lines):
                    break
                following = self.lines[lookahead]
                following_content = _strip_comment(following).strip()
                if not self._continues_plain(following_content):
                    break
                if self._indent(following, lookahead + 1) <= parent_indent:
                    break
                pending_breaks += blanks
                self.index = lookahead
                continue

            content = _strip_comment(raw).strip()
            if not self._continues_plain(content):
                break
            if self._indent(raw, self.index + 1) <= parent_indent:
                break
            if pieces and pending_breaks:
                pieces.append("\n" * pending_breaks)
            elif pieces:
                pieces.append(" ")
            pieces.append(content)
            pending_breaks = 0
            self.index += 1
        return "".join(pieces)

    def _parse_map(self, indent):
        result = {}
        while True:
            peek = self._peek()
            if peek is None:
                break
            line, current, content = peek
            if current < indent:
                break
            if current > indent:
                raise self._error(
                    "неожиданный отступ %d (ожидался %d)" % (current, indent), line
                )
            if content == "-" or content.startswith("- "):
                raise self._error(
                    "элемент списка внутри словаря без ключа-родителя", line
                )
            colon = _find_key_colon(content)
            if colon < 0:
                raise self._error(
                    "ожидался формат 'ключ: значение', получено: %r" % content, line
                )
            key = _unquote_key(content[:colon].strip(), self.source, line)
            rest = content[colon + 1 :].strip()
            self.index += 1

            if rest in _BLOCK_HEADERS:
                value = self._parse_block_scalar(current, rest, line)
            elif rest == "":
                value = self._parse_child(current)
            else:
                value = _parse_scalar(rest, self.source, line, current + 1)
                if isinstance(value, str) and self._is_plain_start(rest):
                    value = self._parse_plain_continuation(current, value, line)
                self._reject_deeper(current, line)

            if key in result:
                raise self._error("повторяющийся ключ %r" % key, line)
            result[key] = value
        return result

    def _parse_list(self, indent):
        items = []
        while True:
            peek = self._peek()
            if peek is None:
                break
            line, current, content = peek
            if current < indent:
                break
            if current > indent:
                raise self._error(
                    "неожиданный отступ %d (ожидался %d)" % (current, indent), line
                )
            if not (content == "-" or content.startswith("- ")):
                break

            rest = content[1:].strip()
            if rest == "":
                self.index += 1
                items.append(self._parse_child(current))
                continue

            if rest in _BLOCK_HEADERS:
                self.index += 1
                items.append(self._parse_block_scalar(current, rest, line))
                continue

            if _find_key_colon(rest) >= 0:
                # Элемент списка — словарь. Переписываем строку так, чтобы её
                # отступ совпадал с колонкой первого ключа, и разбираем как map.
                body = _strip_comment(self.lines[self.index])
                content_start = body.index(content) if content in body else current
                offset = body.find(rest, content_start)
                if offset < 0:
                    offset = current + 2
                self.lines[self.index] = " " * offset + rest
                items.append(self._parse_map(offset))
                continue

            item = _parse_scalar(rest, self.source, line, current + 3)
            self.index += 1
            if isinstance(item, str) and self._is_plain_start(rest):
                item = self._parse_plain_continuation(current, item, line)
            items.append(item)
            self._reject_deeper(current, line)
        return items

    def _parse_block_scalar(self, parent_indent, header, line):
        style = header[0]
        chomp = header[1:] if len(header) > 1 else ""

        collected = []
        block_indent = None
        while self.index < len(self.lines):
            raw = self.lines[self.index]
            if raw.strip() == "":
                collected.append("")
                self.index += 1
                continue
            leading = self._leading_spaces(raw)
            if leading <= parent_indent:
                break
            if block_indent is None:
                block_indent = leading
            if leading >= block_indent:
                collected.append(raw[block_indent:])
            else:
                collected.append(raw.strip())
            self.index += 1

        if chomp != "+":
            while collected and collected[-1] == "":
                collected.pop()

        if style == "|":
            text = "\n".join(collected)
        else:
            pieces = []
            previous_empty = True
            for entry in collected:
                if entry == "":
                    pieces.append("\n")
                    previous_empty = True
                else:
                    if pieces and not previous_empty:
                        pieces.append(" ")
                    pieces.append(entry)
                    previous_empty = False
            text = "".join(pieces)

        if chomp == "-":
            return text.rstrip("\n")
        if chomp == "+":
            return text + "\n" if text else ""
        text = text.rstrip("\n")
        return text + "\n" if text else ""


def parse(text, source="<string>"):
    """Разобрать текст YAML в словарь."""
    if not isinstance(text, str):
        raise YamlError("на входе ожидалась строка", None, source)
    return _Parser(text, source).parse()


def loads(text, source="<string>"):
    """Разобрать текст YAML в словарь (основной API)."""
    return parse(text, source)


def load_file(path):
    """Прочитать и разобрать YAML-файл."""
    source = str(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise YamlError("не удалось прочитать файл: %s" % exc, None, source)
    except UnicodeDecodeError as exc:
        raise YamlError("файл не в UTF-8: %s" % exc, None, source)
    return parse(text, source)


# ---------------------------------------------------------------------------
# Кросс-проверка с PyYAML (только для selftest; на разбор не влияет)
# ---------------------------------------------------------------------------

try:  # pragma: no cover - зависит от окружения
    import yaml as _pyyaml
except Exception:  # pragma: no cover
    _pyyaml = None


def _normalize(value):
    """Привести значение к сравнимому виду (даты → строки, кортежи → списки)."""
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return value
    return str(value)


def cross_check(text, source="<string>"):
    """Сравнить встроенный разбор с PyYAML. Возвращает список расхождений.

    Пустой список — расхождений нет либо PyYAML недоступен (второй случай
    виден по `cross_check.available`).
    """
    if _pyyaml is None:
        return []
    try:
        expected = _normalize(_pyyaml.safe_load(text))
    except Exception as exc:  # noqa: BLE001 - сообщение PyYAML информативно
        return ["PyYAML не разобрал текст: %s" % exc]
    try:
        actual = _normalize(loads(text, source))
    except YamlError as exc:
        return ["встроенный парсер не разобрал текст: %s" % exc]
    if expected == actual:
        return []
    return ["результаты расходятся: PyYAML=%r, встроенный=%r" % (expected, actual)]


cross_check.available = _pyyaml is not None

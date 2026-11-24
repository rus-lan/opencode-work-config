#!/usr/bin/env python3
"""Нормализация и проверка источников: `.task-readiness/resolved-sources.json`.

Модуль работает только с файлами: Confluence/Jira/Obsidian читает агент через
MCP и приносит результат в `resolved_by_agent`. Здесь этот результат
нормализуется, дополняется кандидатами из свободного текста конфига,
сортируется, валидируется схемой и записывается детерминированно.

Ключевое правило: **ничего не выдумывать**. Если `page_id` не найден в URL —
поле остаётся `null`, а `ref` равен самому URL. Если источник только упомянут
словами («эталон в конфлюенсе»), он попадает в кандидаты с `page_id = null` и
`confidence = "low"`, чтобы агент на этапе `init` либо разрешил его, либо честно
получил `BLOCKED`.

Формат `resolved-sources.json` — CONTRACT.md §5.2: `resolved_at` + `sources[]`,
у каждого источника все 8 полей, `evidence` непустой.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, unquote_plus, urlsplit

from trr_impl import config as configmod
from trr_impl import limits
from trr_impl import schema_lite

__all__ = [
    "FIXED_TIME",
    "NA_MARKER",
    "SourcesError",
    "check_readiness",
    "expand_children",
    "is_sprint_id",
    "match_field_names",
    "match_sprint_labels",
    "merge_resolved",
    "normalize_reference",
    "normalize_sprint_labels",
    "normalize_sprints",
    "parse_confluence_url",
    "resolved_sources_path",
    "select_child_pages",
    "sprint_keys",
    "sprints_label",
    "system_label",
    "unresolved_url_hints",
]

# Фиксированное время для тестов и golden-прогонов (CONTRACT.md §8: время —
# единственное недетерминированное поле, и оно должно уметь замораживаться).
FIXED_TIME_ENV = "TASK_READINESS_FIXED_TIME"
FIXED_TIME = "1970-01-01T00:00:00Z"

# Заглушка для отчёта: «данных в источнике нет». Одна на весь скилл, чтобы
# формулировка не расползалась по шаблонам.
NA_MARKER = "N/A (нет данных в источнике)"

STATE_DIR = ".task-readiness"
RESOLVED_FILE = "resolved-sources.json"

_URL_RE = re.compile(r"https?://[^\s<>\"']+")

# Хвостовая пунктуация не часть URL: «…/Story+Points,» — запятая из текста.
_URL_TAIL = ".,;:!?)]}\u00bb\u201d'\""

_MENTION_RE = re.compile(
    r"(?i)(confluence|конфлюенс\w*|obsidian|обсидиан\w*)"
)
_MENTION_SYSTEMS = {
    "confluence": "confluence",
    "obsidian": "obsidian",
}
# Порядок обхода упоминаний фиксирован: одинаковый текст → одинаковый список.
_MENTION_ORDER = ("confluence", "obsidian")

_PAGE_ID_RE = re.compile(r"[?&]pageId=(\d+)", re.IGNORECASE)

_RESOLUTION_BY_SYSTEM = {
    "confluence": "confluence_url",
    "obsidian": "obsidian_path",
    "jira": "jira_sprint_search",
    "file": "manual",
}


class SourcesError(Exception):
    """Источники не нормализуются или не проходят схему."""


# ---------------------------------------------------------------------------
# Служебное
# ---------------------------------------------------------------------------


def _now():
    """Момент разрешения источников: UTC ISO-8601 либо замороженное время."""
    if os.environ.get(FIXED_TIME_ENV) == "1":
        return FIXED_TIME
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _collapse(text):
    """Схлопнуть пробелы и переводы строк: `ref` и `evidence` — однострочные."""
    return re.sub(r"\s+", " ", str(text)).strip()


def _strip_url(url):
    return url.rstrip(_URL_TAIL)


def _url_system(url):
    """Система по URL. Неизвестный URL — `file` (честнее, чем угадывать)."""
    low = url.lower()
    if "confluence" in low or "/display/" in low or "viewpage.action" in low:
        return "confluence"
    if "obsidian" in low:
        return "obsidian"
    if "jira" in low or "/browse/" in low or "/secure/" in low:
        return "jira"
    return "file"


def _url_page_id(url):
    """page_id из URL, если он там есть. Иначе None — не выдумываем."""
    match = _PAGE_ID_RE.search(url)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Детерминированные парсеры (без сети)
# ---------------------------------------------------------------------------

# `/display/SPACE/Title+With+Plus` — страница по space/title.
_DISPLAY_RE = re.compile(r"^/display/([^/]+)/([^/]+?)/?$")
# `/spaces/SPACE/pages/NNN/Title` — страница по id внутри пространства.
_SPACES_PAGES_RE = re.compile(r"^/spaces/([^/]+)/pages/(\d+)(?:/([^/]*))?/?$")


def parse_confluence_url(url):
    """Разобрать URL Confluence без сети.

    Возвращает словарь `{"kind", "page_id", "space", "title"}`:

    * `page_id` — `.../pages/viewpage.action?pageId=N` (в том числе с `&src=…`)
      и `/spaces/SPACE/pages/N/title`; `page_id` — целое число;
    * `space_title` — `/display/SPACE/Title+With+Plus` (URL-decode, `+` → пробел);
    * `unknown` — всё остальное (не падаем: URL может быть не Confluence).

    Функция ничего не выдумывает: если `pageId` в URL нет, `page_id` остаётся
    `None`, и вызывающий обязан либо попросить id, либо оставить кандидата
    с низкой уверенностью.
    """
    result = {"kind": "unknown", "page_id": None, "space": None, "title": None}
    text = str(url or "").strip()
    if not text:
        return result

    path = urlsplit(text).path or text

    spaces = _SPACES_PAGES_RE.match(path)
    if spaces:
        result["kind"] = "page_id"
        result["page_id"] = int(spaces.group(2))
        result["space"] = unquote(spaces.group(1))
        if spaces.group(3):
            result["title"] = _collapse(unquote_plus(spaces.group(3)))
        return result

    page_id = _url_page_id(text)
    if page_id:
        result["kind"] = "page_id"
        result["page_id"] = int(page_id)
        return result

    display = _DISPLAY_RE.match(path)
    if display:
        result["kind"] = "space_title"
        result["space"] = unquote(display.group(1))
        result["title"] = _collapse(unquote_plus(display.group(2)))
        return result

    return result


def _norm_name(text):
    """Нормализованное имя для матчинга: casefold, ё→е, схлопнутые пробелы."""
    return _collapse(str(text or "")).casefold().replace("ё", "е")


def normalize_sprint_labels(raw):
    """Разобрать названия спринтов: запятая/перенос строки, trim, дедуп по порядку."""
    if raw is None:
        return []
    items = raw if isinstance(raw, (list, tuple)) else [raw]
    labels = []
    seen = set()
    for item in items:
        for chunk in re.split(r"[,\n\r]+", str(item)):
            label = _collapse(chunk)
            if not label or label in seen:
                continue
            seen.add(label)
            labels.append(label)
    return labels


def _sprint_entries(sprint_index):
    """Привести индекс спринтов к списку `{name, id, state}`.

    Поддержаны: список объектов, ответ Jira (`{"values": [...]}`), обёртка
    `{"sprints": [...]}` и отображение `{name: id}`.
    """
    if isinstance(sprint_index, dict):
        for key in ("sprints", "values"):
            if isinstance(sprint_index.get(key), list):
                sprint_index = sprint_index[key]
                break
        else:
            return [
                {"name": str(name), "id": value, "state": None}
                for name, value in sprint_index.items()
            ]
    if not isinstance(sprint_index, (list, tuple)):
        raise SourcesError(
            "индекс спринтов должен быть массивом или объектом, получено %s"
            % type(sprint_index).__name__
        )
    entries = []
    for item in sprint_index:
        if isinstance(item, dict):
            name = item.get("name")
            if name in (None, ""):
                continue
            entries.append(
                {"name": str(name), "id": item.get("id"), "state": item.get("state")}
            )
        elif isinstance(item, str):
            entries.append({"name": item, "id": None, "state": None})
    return entries


def match_sprint_labels(labels, sprint_index):
    """Сопоставить названия спринтов с индексом `{name, id}`.

    Три уровня, от строгого к мягкому: точное совпадение → нормализованное
    (casefold, ё→е, схлопнутые пробелы) → префиксное (`label` — начало имени).
    Больше одного кандидата — `ambiguous`, ни одного — `missing`: угадывать
    нельзя, иначе статистика соберётся по чужому спринту.
    """
    entries = _sprint_entries(sprint_index)
    matched, ambiguous, missing = [], [], []
    for label in normalize_sprint_labels(labels):
        candidates = [entry for entry in entries if entry["name"] == label]
        if not candidates:
            key = _norm_name(label)
            candidates = [entry for entry in entries if _norm_name(entry["name"]) == key]
        if not candidates:
            key = _norm_name(label)
            candidates = [
                entry
                for entry in entries
                if key and _norm_name(entry["name"]).startswith(key)
            ]
        if len(candidates) == 1:
            entry = candidates[0]
            matched.append(
                {"label": label, "id": entry.get("id"), "name": entry["name"]}
            )
        elif len(candidates) > 1:
            ambiguous.append(
                {
                    "label": label,
                    "candidates": [
                        {"id": entry.get("id"), "name": entry["name"]}
                        for entry in candidates
                    ],
                }
            )
        else:
            missing.append(label)
    return {"matched": matched, "ambiguous": ambiguous, "missing": missing}


def _field_entries(available_fields):
    """Привести список полей Jira к `[{id, name}]`.

    Поддержаны ответ REST (`{"values": [...]}` / `{"fields": [...]}`), список
    объектов и отображение `{id: name}`.
    """
    if isinstance(available_fields, dict):
        for key in ("fields", "values"):
            if isinstance(available_fields.get(key), list):
                available_fields = available_fields[key]
                break
        else:
            return [
                {"id": str(key), "name": str(value)}
                for key, value in available_fields.items()
            ]
    if not isinstance(available_fields, (list, tuple)):
        raise SourcesError(
            "список полей Jira должен быть массивом или объектом, получено %s"
            % type(available_fields).__name__
        )
    entries = []
    for item in available_fields:
        if not isinstance(item, dict):
            continue
        field_id = item.get("id")
        name = item.get("name")
        if field_id in (None, "") or name in (None, ""):
            continue
        entries.append({"id": field_id, "name": str(name)})
    return entries


def match_field_names(available_fields, wanted):
    """Сопоставить имена полей Jira с id по нормализованному имени.

    `wanted` — отображение `{key: имя}` (например `jira.field_names`) или список
    имён. Возвращает `{"resolved": {key: id}, "missing": [...], "ambiguous": [...]}`.
    Сравнение только точное (после нормализации): префикс для полей опасен —
    «Story Points» и «Story Points (old)» легко перепутать.
    """
    entries = _field_entries(available_fields)
    if isinstance(wanted, dict):
        pairs = [(str(key), value) for key, value in wanted.items()]
    elif isinstance(wanted, (list, tuple)):
        pairs = [(str(value), value) for value in wanted]
    else:
        raise SourcesError(
            "имена полей должны быть объектом или массивом, получено %s"
            % type(wanted).__name__
        )

    resolved, missing, ambiguous = {}, [], []
    for key, name in pairs:
        if name in (None, "") or not str(name).strip():
            continue
        norm = _norm_name(name)
        candidates = [entry for entry in entries if _norm_name(entry["name"]) == norm]
        if len(candidates) == 1:
            resolved[key] = candidates[0]["id"]
        elif len(candidates) > 1:
            ambiguous.append(
                {
                    "name": str(name),
                    "candidates": [
                        {"id": entry["id"], "name": entry["name"]}
                        for entry in candidates
                    ],
                }
            )
        else:
            missing.append(str(name))
    return {"resolved": resolved, "missing": missing, "ambiguous": ambiguous}



def system_label(system):
    """Система источника для диагностики: `confluence`, `obsidian` или `unknown`.

    В артефакте `system` — закрытый enum схемы (`confluence|jira|obsidian|file`),
    поэтому «систему определить не удалось» хранится как `file`, а человеку
    показывается как `unknown`. Выдумывать систему нельзя: URL без признаков
    Confluence/Obsidian/Jira остаётся `file`.
    """
    text = str(system or "").strip().lower()
    if text in ("confluence", "obsidian", "jira"):
        return text
    return "unknown"


def _candidate(
    system,
    ref,
    page_id=None,
    title=None,
    source_kind="text",
    url=None,
    url_kind=None,
    board_id=None,
):
    """Кандидат из конфига.

    `source_kind` фиксирует, как источник был задан: `page_id`, `page_url`,
    `board_label`, `text` или `sprint_ids`. `url_kind` — результат
    `parse_confluence_url` (`page_id` / `space_title` / `unknown`), он нужен,
    чтобы `resolve-sources` мог сказать «передайте page_id» вместо угадывания.
    """
    candidate = {
        "system": system,
        "ref": ref,
        "page_id": page_id,
        "source_kind": source_kind,
    }
    if title is not None:
        candidate["title"] = title
    if url is not None:
        candidate["url"] = url
    if url_kind is not None:
        candidate["url_kind"] = url_kind
    if board_id is not None:
        candidate["board_id"] = board_id
    return candidate



def _dedupe(candidates):
    """Убрать повторы по (system, ref), сохранив порядок появления."""
    seen = set()
    result = []
    for item in candidates:
        key = (item["system"], item["ref"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Нормализация sources.reference
# ---------------------------------------------------------------------------


def normalize_reference(raw):
    """Нормализовать `sources.reference`: свободный текст или массив объектов.

    Возвращает `{"raw": <строка>, "candidates": [{"system", "ref", "page_id"}]}`.

    Для строки: сначала URL-ы в порядке появления, затем упоминания систем,
    которых среди URL-ов нет. `page_id` заполняется только если он есть в URL —
    иначе `null`, а `ref` равен URL (или самому тексту для упоминания).
    """
    if isinstance(raw, str):
        return _normalize_reference_text(raw)
    if isinstance(raw, (list, tuple)):
        return _normalize_reference_array(raw)
    raise SourcesError(
        "sources.reference должен быть строкой или массивом, получено %s"
        % type(raw).__name__
    )


def _normalize_reference_text(text):
    raw = str(text)
    collapsed = _collapse(raw)
    candidates = []
    for match in _URL_RE.finditer(raw):
        url = _strip_url(match.group(0))
        if not url:
            continue
        parsed = parse_confluence_url(url)
        system = _url_system(url)
        candidates.append(
            _candidate(
                system,
                url,
                _url_page_id(url),
                title=parsed.get("title"),
                source_kind="page_url",
                url=url,
                url_kind=parsed["kind"],
            )
        )
    candidates = _dedupe(candidates)

    covered = {item["system"] for item in candidates}
    for system in _MENTION_ORDER:
        if system in covered:
            continue
        if not _mentions(raw, system):
            continue
        # Источник упомянут словами, но не разрешён: ref — сам текст, page_id
        # неизвестен. Агент на init либо найдёт страницу, либо оставит BLOCKED.
        candidates.append(_candidate(system, collapsed or raw, None, source_kind="text"))

    return {"raw": raw, "candidates": candidates}


def _mentions(text, system):
    for match in _MENTION_RE.finditer(text):
        word = match.group(1).lower()
        if _MENTION_SYSTEMS.get(word) == system:
            return True
        if word.startswith("конфлюенс") and system == "confluence":
            return True
        if word.startswith("обсидиан") and system == "obsidian":
            return True
    return False


def _normalize_reference_array(items):
    candidates = []
    parts = []
    for item in items:
        if isinstance(item, dict):
            url = item.get("page_url")
            text = item.get("text")
            page_id = item.get("page_id")
            if not _blank(url):
                raw_url = str(url).strip()
                parsed = parse_confluence_url(raw_url)
                resolved_id = (
                    str(parsed["page_id"]) if parsed["page_id"] is not None else None
                )
                candidates.append(
                    _candidate(
                        "confluence",
                        resolved_id or raw_url,
                        resolved_id,
                        title=item.get("title") or parsed.get("title"),
                        source_kind="page_url",
                        url=raw_url,
                        url_kind=parsed["kind"],
                    )
                )
                parts.append(raw_url)
            elif not _blank(text):
                nested = _normalize_reference_text(str(text))
                for candidate in nested["candidates"]:
                    candidate["source_kind"] = "text"
                    if item.get("title") and not candidate.get("title"):
                        candidate["title"] = item["title"]
                candidates.extend(nested["candidates"])
                parts.append(_collapse(text))
            elif not _blank(page_id):
                value = str(page_id).strip()
                system = str(item.get("system") or "").strip()
                if not system:
                    # Числовой id без system — это Confluence page_id; строку
                    # (путь заметки Obsidian, файл) не угадываем.
                    system = "confluence" if value.isdigit() else "file"
                candidates.append(
                    _candidate(
                        system,
                        value,
                        value,
                        title=item.get("title"),
                        source_kind="page_id",
                    )
                )
                parts.append(value)
            else:
                raise SourcesError(
                    "элемент sources.reference без page_id/page_url/text: %r" % (item,)
                )
        elif isinstance(item, str):
            nested = _normalize_reference_text(item)
            candidates.extend(nested["candidates"])
            parts.append(_collapse(item))
        else:
            raise SourcesError(
                "элемент sources.reference должен быть строкой или объектом, "
                "получено %s" % type(item).__name__
            )
    return {"raw": ", ".join(part for part in parts if part), "candidates": _dedupe(candidates)}


def _blank(value):
    """Пустая строка/None — «значение не задано»."""
    return value is None or (isinstance(value, str) and not value.strip())



# ---------------------------------------------------------------------------
# Нормализация sources.sprints
# ---------------------------------------------------------------------------


def normalize_sprints(raw):
    """Нормализовать `sources.sprints` в список `{"name", "id", ...}`.

    Строка: разделитель — запятая/перенос; пробелы обрезаются, пустые элементы
    отбрасываются, дубликаты схлопываются с сохранением порядка. `id` для
    свободного текста всегда `null`: числовой ID в строке — это подсказка
    агенту, а не факт (ID резолвит `trr match-sprints` и фиксирует в
    `resolved-sources.json`).

    Массив: поддержаны строки, объекты `{board_id, sprint_ids[]}`,
    `{board_labels}` (названия как в UI Jira), `{text}` и объекты `{name, id}`.
    У каждой записи есть `source_kind` — как спринт был задан в конфиге.
    """
    if isinstance(raw, str):
        return [
            {"name": name, "id": None, "source_kind": "text"}
            for name in _split_sprint_names(raw)
        ]
    if isinstance(raw, (list, tuple)):
        return _normalize_sprints_array(raw)
    raise SourcesError(
        "sources.sprints должен быть строкой или массивом, получено %s"
        % type(raw).__name__
    )


def _sprint_id_value(value):
    """id спринта: число, если оно числовое; иначе строка как есть."""
    text = str(value).strip()
    return int(text) if text.isdigit() else text



def _split_sprint_names(text):
    names = []
    seen = set()
    for chunk in str(text).split(","):
        name = _collapse(chunk)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _normalize_sprints_array(items):
    result = []
    seen = set()

    def add(entry):
        key = (entry.get("name"), entry.get("id"))
        if key in seen:
            return
        seen.add(key)
        result.append(entry)

    for item in items:
        if isinstance(item, str):
            for name in _split_sprint_names(item):
                add({"name": name, "id": None, "source_kind": "text"})
            continue
        if not isinstance(item, dict):
            raise SourcesError(
                "элемент sources.sprints должен быть строкой или объектом, "
                "получено %s" % type(item).__name__
            )
        board_id = item.get("board_id")
        labels = item.get("board_labels")
        text = item.get("text")
        sprint_ids = item.get("sprint_ids")

        if not _blank(labels):
            for name in normalize_sprint_labels(labels):
                entry = {"name": name, "id": None, "source_kind": "board_label"}
                if board_id is not None:
                    entry["board_id"] = board_id
                add(entry)
            continue

        if not _blank(text):
            for name in _split_sprint_names(text):
                entry = {"name": name, "id": None, "source_kind": "text"}
                if board_id is not None:
                    entry["board_id"] = board_id
                add(entry)
            continue

        if not _blank(sprint_ids):
            values = (
                sprint_ids
                if isinstance(sprint_ids, list)
                else _split_sprint_names(sprint_ids)
            )
            for sprint_id in values:
                value = _sprint_id_value(sprint_id)
                entry = {
                    "name": str(value),
                    "id": value,
                    "source_kind": "sprint_ids",
                }
                if board_id is not None:
                    entry["board_id"] = board_id
                add(entry)
            continue

        name = item.get("name")
        if name in (None, ""):
            raise SourcesError(
                "элемент sources.sprints без sprint_ids/board_labels/text: %r"
                % (item,)
            )
        entry = {"name": _collapse(name), "id": item.get("id"), "source_kind": "text"}
        if item.get("board_id") is not None:
            entry["board_id"] = item["board_id"]
        add(entry)

    return result



# ---------------------------------------------------------------------------
# Слияние с результатом агента
# ---------------------------------------------------------------------------


def _agent_sources(resolved_by_agent):
    """Привести результат агента к списку источников (dict или list)."""
    if not resolved_by_agent:
        return []
    if isinstance(resolved_by_agent, dict):
        sources = resolved_by_agent.get("sources")
        if sources is None:
            raise SourcesError(
                "resolved_by_agent — объект без поля sources; ожидался список источников"
            )
        resolved_by_agent = sources
    if not isinstance(resolved_by_agent, (list, tuple)):
        raise SourcesError(
            "resolved_by_agent должен быть списком источников, получено %s"
            % type(resolved_by_agent).__name__
        )
    result = []
    for item in resolved_by_agent:
        if not isinstance(item, dict):
            raise SourcesError("источник от агента должен быть объектом: %r" % (item,))
        result.append(dict(item))
    return result


def _normalize_source(entry, fallback_kind):
    """Достроить недостающие поля источника, не выдумывая факты.

    Обязательные поля схемы заполняются, но `evidence` никогда не сочиняется:
    если его нет, источник получит `SourcesError` на валидации.
    """
    source = {
        "kind": entry.get("kind") or fallback_kind,
        "system": entry.get("system") or "file",
        "ref": entry.get("ref"),
        "title": entry.get("title"),
        "url": entry.get("url"),
        "resolution_method": entry.get("resolution_method"),
        "evidence": entry.get("evidence"),
        "confidence": entry.get("confidence") or "low",
    }
    if source["ref"] in (None, ""):
        raise SourcesError("у источника пустой ref: %r" % (entry,))
    source["ref"] = str(source["ref"])
    if source["title"] in (None, ""):
        source["title"] = source["ref"]
    source["title"] = _collapse(source["title"])
    if source["url"] is not None:
        source["url"] = str(source["url"])
    if source["resolution_method"] is None:
        source["resolution_method"] = _RESOLUTION_BY_SYSTEM.get(source["system"], "manual")
    if source["evidence"] is None:
        source["evidence"] = ""
    source["evidence"] = _collapse(source["evidence"])

    # Необязательные поля провенанса: как источник был задан и откуда взялся.
    # Сохраняются как есть — их не выдумывает ни один слой.
    page_id = entry.get("page_id")
    if page_id not in (None, ""):
        source["page_id"] = str(page_id)
    source_kind = entry.get("source_kind")
    if source_kind not in (None, ""):
        source["source_kind"] = str(source_kind)
    parent_ref = entry.get("parent_ref")
    if parent_ref not in (None, ""):
        source["parent_ref"] = str(parent_ref)
    board_id = entry.get("board_id")
    if board_id not in (None, ""):
        source["board_id"] = board_id
    depth = entry.get("depth")
    if depth not in (None, ""):
        source["depth"] = depth
    return source



def _match_tokens(value):
    """Токены для сопоставления источника агента с кандидатом из конфига.

    Кроме самого значения берётся «слаг» URL: последний сегмент пути без
    запроса, с раскрытыми `%XX`, `+` и `_`. Так `/display/SPACE/Story+Points`
    совпадает с заголовком «Story Points», хотя page_id в URL нет.
    """
    text = str(value or "").strip()
    tokens = set()
    if text:
        tokens.add(text.lower())
    if "://" in text:
        path = text.split("://", 1)[1]
        path = path.split("?", 1)[0].split("#", 1)[0]
        segment = path.rstrip("/").rsplit("/", 1)[-1]
        segment = unquote(segment).replace("+", " ").replace("_", " ")
        segment = _collapse(segment).lower()
        if segment:
            tokens.add(segment)
    return tokens


def _agent_covers(entry, system, ref):
    """Покрывает ли источник агента кандидата из конфига."""
    if str(entry.get("system") or "") != system:
        return False
    wanted = _match_tokens(ref)
    for field in ("ref", "url", "page_id", "path", "title"):
        if wanted & _match_tokens(entry.get(field)):
            return True
    return False


def merge_resolved(
    normalized_ref,
    normalized_sprints,
    resolved_by_agent=None,
    manual=False,
    sprints_raw=None,
):
    """Собрать `resolved-sources.json` из нормализованных входов и результата агента.

    Порядок источников — `(kind, system, ref)`. `resolved_at` — UTC ISO-8601;
    при `TASK_READINESS_FIXED_TIME=1` — `1970-01-01T00:00:00Z`, чтобы golden-
    прогоны были байт-в-байт идентичны.

    `manual=True` — режим `trr resolve-sources` без агента: в файл попадает
    ровно то, что написано в конфиге. Ничего не додумывается: `page_id` не
    извлекается из воздуха, `resolution_method="manual"`, `confidence="low"`,
    `evidence` — исходная строка конфига. `title` заполняется самим `ref`
    (схема требует непустой `title`), настоящий заголовок и `page_id` дописывает
    агент после чтения источника.

    Результат валидируется `resolved-sources.schema.json`; нарушение схемы —
    `SourcesError` со списком ошибок (не молчаливый пропуск).
    """
    if manual:
        if resolved_by_agent:
            raise SourcesError(
                "manual-режим не принимает источники агента: передайте --agent "
                "или уберите resolved_by_agent"
            )
        payload = _manual_payload(normalized_ref, normalized_sprints, sprints_raw)
        _validate(payload)
        return payload

    agent_entries = _agent_sources(resolved_by_agent)
    sources = []

    # 1. Источники, которые агент уже разрешил: они главнее догадок из текста.
    for entry in agent_entries:
        sources.append(_normalize_source(entry, entry.get("kind") or "reference"))

    def covered(system, ref):
        return any(_agent_covers(entry, system, ref) for entry in agent_entries)

    # 2. Кандидаты из sources.reference, которых агент не покрыл.
    candidates = (normalized_ref or {}).get("candidates") or []
    for candidate in candidates:
        system = str(candidate.get("system") or "file")
        ref = str(candidate.get("ref") or "")
        if not ref or covered(system, ref):
            continue
        page_id = candidate.get("page_id")
        url = candidate.get("url") or (
            ref if ref.startswith("http://") or ref.startswith("https://") else None
        )
        entry = {
            "kind": "reference",
            "system": system,
            "ref": str(page_id) if page_id else ref,
            "title": candidate.get("title") or ref,
            "url": url,
            "resolution_method": (
                "confluence_search"
                if system == "confluence" and url is None
                else _RESOLUTION_BY_SYSTEM.get(system, "manual")
            ),
            "evidence": (
                "источник указан в sources.reference конфига: «%s»" % _shorten(ref)
            ),
            "confidence": "medium" if page_id or url else "low",
            "source_kind": candidate.get("source_kind") or "text",
        }
        if page_id:
            entry["page_id"] = str(page_id)
        sources.append(_normalize_source(entry, "reference"))

    # 3. Спринты из sources.sprints, которых агент не покрыл.
    for sprint in normalized_sprints or []:
        name = _collapse(sprint.get("name") or "")
        sprint_id = sprint.get("id")
        ref = str(sprint_id) if sprint_id not in (None, "") else name
        if not ref:
            continue
        if covered("jira", ref) or covered("jira", name):
            continue
        entry = {
            "kind": "sprint",
            "system": "jira",
            "ref": ref,
            "title": name or ref,
            "url": None,
            "resolution_method": "jira_sprint_search",
            "evidence": ("спринт перечислен в sources.sprints конфига: «%s»" % name),
            "confidence": "medium" if sprint_id not in (None, "") else "low",
            "source_kind": sprint.get("source_kind") or "text",
        }
        if sprint.get("board_id") is not None:
            entry["board_id"] = sprint["board_id"]
        sources.append(_normalize_source(entry, "sprint"))

    sources.sort(key=lambda item: (item["kind"], item["system"], item["ref"]))
    payload = {"resolved_at": _now(), "sources": sources}
    _validate(payload)
    return payload


def _shorten(text, limit=120):
    text = _collapse(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# Ручной резолв: только то, что написано в конфиге
# ---------------------------------------------------------------------------


def _evidence_text(raw, fallback):
    """Evidence ручного резолва: исходная строка конфига без переформатирования.

    Пробелы по краям обрезаются, внутренние (включая переводы строк блочного
    скаляра) сохраняются: `evidence` — это цитата, а не пересказ.
    """
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return str(fallback or "").strip()


def _manual_payload(normalized_ref, normalized_sprints, sprints_raw=None):
    """`resolved-sources.json` без догадок: `manual`, `low`, evidence из конфига."""
    evidence_reference = _evidence_text((normalized_ref or {}).get("raw"), "")
    if isinstance(sprints_raw, str):
        evidence_sprint = _evidence_text(sprints_raw, "")
    elif isinstance(sprints_raw, (list, tuple)):
        names = [
            _collapse(sprint.get("name") or "")
            for sprint in normalized_sprints or []
            if sprint.get("name")
        ]
        evidence_sprint = ", ".join(name for name in names if name)
    else:
        evidence_sprint = ""

    sources = []
    for candidate in (normalized_ref or {}).get("candidates") or []:
        system = str(candidate.get("system") or "file")
        page_id = candidate.get("page_id")
        ref = str(page_id) if page_id not in (None, "") else str(candidate.get("ref") or "")
        if not ref:
            continue
        url = candidate.get("url") or (
            ref if ref.startswith("http://") or ref.startswith("https://") else None
        )
        # URL по space/title не даёт page_id: кандидат сохраняется, но честно
        # помечается как найденный поиском, а не разрешённый по URL.
        unresolved_title = candidate.get("url_kind") == "space_title" and not page_id
        entry = {
            "kind": "reference",
            "system": system,
            "ref": ref,
            # Схема требует непустой title; настоящий заголовок дописывает
            # агент после чтения источника — здесь заглушка из ref.
            "title": candidate.get("title") or ref,
            "url": url,
            "resolution_method": "confluence_search" if unresolved_title else "manual",
            "evidence": _evidence_text(evidence_reference, ref),
            "confidence": "low",
            "source_kind": candidate.get("source_kind") or "text",
        }
        if page_id not in (None, ""):
            entry["page_id"] = str(page_id)
        sources.append(entry)

    for sprint in normalized_sprints or []:
        name = _collapse(sprint.get("name") or "")
        sprint_id = sprint.get("id")
        ref = str(sprint_id) if sprint_id not in (None, "") else name
        if not ref:
            continue
        entry = {
            "kind": "sprint",
            "system": "jira",
            "ref": ref,
            "title": name or ref,
            "url": None,
            "resolution_method": "manual",
            "evidence": _evidence_text(evidence_sprint, name or ref),
            "confidence": "low",
            "source_kind": sprint.get("source_kind") or "text",
        }
        if sprint.get("board_id") is not None:
            entry["board_id"] = sprint["board_id"]
        sources.append(entry)

    # Повтор одного и того же источника в конфиге не должен плодить записи.
    unique = []
    seen = set()
    for item in sources:
        key = (item["kind"], item["system"], item["ref"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    unique.sort(key=lambda item: (item["kind"], item["system"], item["ref"]))
    return {"resolved_at": _now(), "sources": unique}


def _validate(payload):
    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, "resolved-sources")
    except schema_lite.SchemaError as exc:
        raise SourcesError("схема resolved-sources не читается: %s" % exc)
    errors = schema_lite.validate(payload, schema)
    if errors:
        raise SourcesError(
            "resolved-sources не соответствует схеме: %s" % "; ".join(errors)
        )
    return payload


# ---------------------------------------------------------------------------
# Рекурсивный обход дерева Confluence
# ---------------------------------------------------------------------------


def _pages_list(pages):
    """Список страниц дерева: `[...]`, `{"pages": [...]}` или `{"values": [...]}`."""
    if isinstance(pages, dict):
        for key in ("pages", "values", "results"):
            if isinstance(pages.get(key), list):
                return [item for item in pages[key] if isinstance(item, dict)]
        return []
    if isinstance(pages, (list, tuple)):
        return [item for item in pages if isinstance(item, dict)]
    return []


def _page_depth(page, by_id, seen=None):
    """Глубина страницы в дереве: корень (без parent_id) — 1, ребёнок — 2 и т.д."""
    raw = page.get("depth")
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1:
        return raw
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    parent = page.get("parent_id")
    if parent in (None, "") or str(parent) not in by_id:
        return 1
    seen = set(seen or ())
    key = str(page.get("id"))
    if key in seen:
        return 1
    seen.add(key)
    return _page_depth(by_id[str(parent)], by_id, seen) + 1


def _page_sort_key(page):
    raw = str(page.get("id") or "")
    return (page.get("depth") or 0, int(raw) if raw.isdigit() else 0, raw)


def select_child_pages(pages, existing_refs=(), max_depth=1, max_pages=20):
    """Отобрать страницы дерева для `resolved-sources.json`.

    Правила детерминированы и не зависят от порядка в файле:

    * страница с `id`, уже присутствующим среди эталонов, пропускается (это сам
      эталон, а не ребёнок);
    * `depth > max_depth` — пропускается (`max_depth=1` — только эталон);
    * после `max_pages` остальные отбрасываются с `[WARN]`.

    Возвращает `(selected, warnings)`.
    """
    items = _pages_list(pages)
    by_id = {str(item.get("id")): item for item in items if item.get("id") not in (None, "")}
    known = {str(ref) for ref in existing_refs if ref not in (None, "")}

    selected = []
    seen = set()
    for page in items:
        page_id = page.get("id")
        if page_id in (None, ""):
            continue
        key = str(page_id)
        if key in known or key in seen:
            continue
        depth = _page_depth(page, by_id)
        if depth > max_depth:
            continue
        seen.add(key)
        selected.append(
            {
                "id": key,
                "title": _collapse(page.get("title") or key),
                "parent_id": page.get("parent_id"),
                "url": page.get("url"),
                "body_excerpt": page.get("body_excerpt"),
                "depth": depth,
            }
        )

    selected.sort(key=_page_sort_key)
    warnings = []
    if len(selected) > max_pages:
        warnings.append(
            "[WARN] дерево Confluence: страниц %d, в источники попадут первые %d — "
            "увеличьте sources.confluence.max_pages, если нужны все"
            % (len(selected), max_pages)
        )
        selected = selected[:max_pages]
    return selected, warnings


def expand_children(payload, pages, max_depth=1, max_pages=20, parent_ref=None):
    """Добавить в `resolved-sources.json` страницы, найденные обходом дерева.

    `payload` не мутируется: возвращается новая копия. Дочерние страницы
    помечаются `source_kind="agent"` (их принёс агент через `--pages-json`),
    `parent_ref` и `depth` — чтобы в отчёте было видно, откуда страница взялась.
    """
    references = [
        item for item in (payload or {}).get("sources") or [] if item.get("kind") == "reference"
    ]
    existing = [item.get("ref") for item in references]
    if parent_ref in (None, "") and references:
        parent_ref = references[0].get("ref")

    selected, warnings = select_child_pages(
        pages, existing, max_depth=max_depth, max_pages=max_pages
    )

    result = {"resolved_at": (payload or {}).get("resolved_at") or _now(), "sources": []}
    result["sources"].extend(dict(item) for item in (payload or {}).get("sources") or [])

    for page in selected:
        entry = {
            "kind": "reference",
            "system": "confluence",
            "ref": page["id"],
            "title": page["title"],
            "url": page.get("url"),
            "resolution_method": "confluence_search",
            "evidence": "дочерняя страница найдена обходом дерева Confluence "
            "(parent %s, depth %s)%s"
            % (
                page.get("parent_id") or parent_ref or "?",
                page["depth"],
                (": «%s»" % _shorten(page["body_excerpt"], 80))
                if page.get("body_excerpt")
                else "",
            ),
            "confidence": "medium",
            "page_id": page["id"],
            "source_kind": "agent",
            "depth": page["depth"],
        }
        if page.get("parent_id") not in (None, ""):
            entry["parent_ref"] = str(page["parent_id"])
        elif parent_ref not in (None, ""):
            entry["parent_ref"] = str(parent_ref)
        result["sources"].append(entry)

    result["sources"].sort(
        key=lambda item: (item["kind"], item["system"], item["ref"])
    )
    _validate(result)
    return result, warnings


# ---------------------------------------------------------------------------
# Нерезолвленные URL: подсказка вместо угадывания
# ---------------------------------------------------------------------------


def unresolved_url_hints(payload):
    """`[BLOCKED]`-строки для URL, которые не дают page_id.

    URL вида `/display/SPACE/Title` детерминированно разбирается в space/title,
    но не в page_id: поиск страницы по названию выполняет агент через MCP.
    Скрипт в сеть не ходит, поэтому честно просит page_id.
    """
    hints = []
    for item in (payload or {}).get("sources") or []:
        if item.get("kind") != "reference":
            continue
        if item.get("page_id") not in (None, ""):
            continue
        url = item.get("url")
        if not url:
            continue
        parsed = parse_confluence_url(url)
        if parsed["kind"] == "space_title":
            hints.append(
                "[BLOCKED] confluence: URL %s задан по space/title (%s / «%s») — "
                "page_id из него не выводится: передайте page_id или найдите "
                "страницу поиском по space/title через MCP и повторите "
                "`trr resolve-sources --re-resolve`"
                % (url, parsed.get("space") or "?", parsed.get("title") or "?")
            )
        elif parsed["kind"] == "unknown":
            hints.append(
                "[BLOCKED] confluence: URL %s не разобран — ожидается "
                "viewpage.action?pageId=N, /display/SPACE/Title или "
                "/spaces/SPACE/pages/N/Title; передайте page_id"
                % url
            )
    return hints


def is_sprint_id(value):
    """Похоже ли значение на числовой id спринта (а не на его название)."""
    text = str(value if value is not None else "").strip()
    return bool(text) and text.isdigit()



# ---------------------------------------------------------------------------
# Путь и проверка готовности
# ---------------------------------------------------------------------------


def resolved_sources_path(workdir):
    """Путь к resolved-sources.json; принимает и корень проекта, и .task-readiness."""
    base = Path(workdir)
    if base.name == STATE_DIR:
        return base / RESOLVED_FILE
    return base / STATE_DIR / RESOLVED_FILE


def _load_resolved(workdir):
    path = resolved_sources_path(workdir)
    if not path.is_file():
        raise SourcesError("нет файла источников: %s" % path)
    limits.check_size(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise SourcesError("не удалось прочитать %s: %s" % (path, exc))
    except ValueError as exc:
        raise SourcesError("%s — невалидный JSON: %s" % (path, exc))
    if not isinstance(data, dict):
        raise SourcesError("%s должен быть JSON-объектом" % path)
    return data


def check_readiness(workdir):
    """Проверить минимальные данные для этапов init/train.

    Требования (CONTRACT.md §6.1, §7): минимум один источник `kind=reference`,
    минимум один `kind=sprint`, у каждого источника непустой `evidence`.

    Возвращает `(код, сообщения)`: `(0, [])` — данные есть, `(2, [...])` —
    `BLOCKED` с инструкцией, что сделать. Каждое сообщение начинается с
    `[BLOCKED]` и содержит `—` с действием.
    """
    path = resolved_sources_path(workdir)
    display = "%s/%s" % (STATE_DIR, RESOLVED_FILE)
    if not path.is_file():
        return 2, [
            "[BLOCKED] источники: нет %s — запустите /task-readiness-review init и "
            "заполните sources.reference и sources.sprints" % display
        ]

    try:
        payload = _load_resolved(workdir)
    except SourcesError as exc:
        return 2, ["[BLOCKED] источники: %s — пересоздайте файл через /task-readiness-review init" % exc]

    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, "resolved-sources")
    except schema_lite.SchemaError as exc:
        return 2, ["[BLOCKED] источники: схема не читается (%s) — переустановите скилл" % exc]

    errors = schema_lite.validate(payload, schema)
    if errors:
        return 2, [
            "[BLOCKED] источники: %s — %s; исправьте файл и повторите"
            % (display, "; ".join(errors))
        ]

    sources = payload.get("sources") or []
    messages = []

    references = [item for item in sources if item.get("kind") == "reference"]
    if not references:
        messages.append(
            "[BLOCKED] reference: не найден ни один источник kind=reference — "
            "добавьте ссылку на эталон оценки в sources.reference "
            "(страницу эталона Story Points в Confluence или её копию в Obsidian) "
            "и запустите "
            "/task-readiness-review init"
        )
    else:
        for index, item in enumerate(references):
            page_id = item.get("page_id")
            ref = item.get("ref")
            has_ref = isinstance(ref, str) and bool(ref.strip())
            has_page = page_id not in (None, "") and bool(str(page_id).strip())
            if not has_ref and not has_page:
                messages.append(
                    "[BLOCKED] reference: у эталона %d нет ни page_id, ни ref — "
                    "передайте page_id страницы Confluence или URL с pageId "
                    "и повторите `trr resolve-sources --re-resolve`" % index
                )
            elif not has_ref and has_page:
                messages.append(
                    "[BLOCKED] reference: у эталона %d пустой ref при page_id=%s — "
                    "ref должен совпадать с page_id; пересоберите файл командой "
                    "`trr resolve-sources --re-resolve`" % (index, page_id)
                )

    sprints = [item for item in sources if item.get("kind") == "sprint"]
    if not sprints:
        messages.append(
            "[BLOCKED] sprint: не найден ни один источник kind=sprint — "
            "перечислите закрытые спринты в sources.sprints "
            "(например «ABC-DEF 26.18, ABC-DEF 26.19») и запустите "
            "/task-readiness-review init"
        )
    else:
        unresolved = [
            _collapse(item.get("title") or item.get("ref") or "")
            for item in sprints
            if not is_sprint_id(item.get("ref"))
        ]
        if unresolved:
            messages.append(
                "[BLOCKED] sprint: не удалось разрешить спринты: %s — проверьте "
                "названия в UI Jira, сопоставьте их командой `trr match-sprints "
                "--labels \"…\" --sprints-file <json>` и повторите "
                "`trr resolve-sources --re-resolve`" % ", ".join(unresolved)
            )


    for index, item in enumerate(sources):
        evidence = item.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            messages.append(
                "[BLOCKED] evidence: у источника %d (%s %s) пустое поле evidence — "
                "укажите короткую цитату или факт, доказывающий, что источник тот "
                "самый, и повторите /task-readiness-review init"
                % (index, item.get("system"), item.get("ref"))
            )

    if messages:
        return 2, messages
    return 0, []


def sprint_keys(resolved):
    """Имена спринтов в стабильном порядке для провенанса.

    Порядок — как в `resolved.sources` (файл отсортирован по `(kind, system, ref)`,
    поэтому числовые ID дают естественный порядок 26.18 → 26.22). Дубликаты
    схлопываются.
    """
    sources = (resolved or {}).get("sources") or []
    names = []
    seen = set()
    for item in sources:
        if item.get("kind") != "sprint":
            continue
        name = item.get("title") or item.get("ref")
        name = _collapse(name) if name is not None else ""
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def sprints_label(resolved):
    """Ярлык провенанса: `sprints:26.18..26.22` или `sprints:26.18` / `sprints:N/A`."""
    names = sprint_keys(resolved)
    if not names:
        return "sprints:%s" % NA_MARKER
    if len(names) == 1:
        return "sprints:%s" % names[0]
    return "sprints:%s..%s" % (names[0], names[-1])

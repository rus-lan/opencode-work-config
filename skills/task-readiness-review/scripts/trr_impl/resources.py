#!/usr/bin/env python3
"""Дополнительные ресурсы задачи и надбавка к оценке (правило `RS-01`).

Задача может требовать не только работы роли, но и **отдельного ресурса**: для
тест-кейсов это Allure, для автотестов — e2e-сервис автотестирования. Такой
ресурс — самостоятельный кусок работы (подготовка данных, разметка, прогон,
поддержка), поэтому по правилу `RS-01` за каждый распознанный ресурс к оценке
добавляется `estimation.resources.sp_per_resource` SP (по умолчанию 1), либо —
при `mode: upper_bound` — оценка берётся по верхней границе уже посчитанного
диапазона.

Модуль ничего не знает про модель и шкалу: он только отвечает на вопрос «какие
ресурсы упомянуты в снимке задачи». Числа применяет `estimate.py`.

Детерминизм: источники обходятся в фиксированном порядке, результат
сортируется по имени ресурса, время и случайность не используются.
"""

import re

__all__ = [
    "EVIDENCE_LIMIT",
    "RESOURCE_DEFAULTS",
    "RESOURCE_ITEMS",
    "RESOURCE_MODES",
    "detect_resources",
    "resources_settings",
    "resources_summary",
]

# Имя ресурса → алиасы (подстроки, сравнение через casefold).
#
# ВАЖНО: алиас `автотест` НЕ является подстрокой слова «автоматизация», поэтому
# «Корректировка работы 14 автоматизации» ресурсом e2e не считается — это
# исправление самой автоматизации, а не написание автотестов. Проверяется
# тестом (`tests`/`python3 -c`), менять алиасы нужно осознанно.
RESOURCE_ITEMS = {
    "allure": (
        "allure",
        "тест-кейс",
        "тест кейс",
        "тесткейс",
        "test case",
        "testcase",
    ),
    "e2e": (
        "e2e",
        "автотест",
        "autotest",
        "auto-test",
        "end-to-end",
        "end to end",
    ),
}

# Дефолты блока `estimation.resources` конфига. `items` копируется из
# `RESOURCE_ITEMS`: конфиг может добавить свой ресурс или обнулить список
# алиасов существующего (`allure: []` — ресурс больше не распознаётся).
RESOURCE_DEFAULTS = {
    "enabled": True,
    "sp_per_resource": 1,
    "mode": "add",
    "items": RESOURCE_ITEMS,
}

# Допустимые режимы надбавки: `add` — прибавить SP за каждый ресурс,
# `upper_bound` — взять верхнюю границу уже посчитанного диапазона.
RESOURCE_MODES = ("add", "upper_bound")

# Длина цитаты-доказательства: короткая строка, а не абзац описания.
EVIDENCE_LIMIT = 120

# Окно контекста вокруг совпадения — чтобы цитата читалась, а не обрывалась.
_EVIDENCE_WINDOW = 40

# Источники текста в порядке обхода. `sections` разворачивается по ключам.
_TEXT_FIELDS = ("description",)


def _as_text(value):
    """Значение снимка в текст: строки как есть, списки — через перевод строки."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(_as_text(item) for item in value if item is not None)
    return str(value)


def _collapse(text):
    """Схлопнуть пробельные символы: цитата должна быть одной строкой."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _evidence(text, alias):
    """Короткая цитата вокруг совпадения `alias` (≤ `EVIDENCE_LIMIT` символов).

    Сравнение — через `casefold()` (как и сама детекция), но в цитату попадает
    исходный текст: регистр и формулировка автора задачи сохраняются.
    """
    collapsed = _collapse(text)
    if not collapsed:
        return ""
    position = collapsed.casefold().find(alias)
    if position < 0:
        return collapsed[:EVIDENCE_LIMIT]
    start = max(0, position - _EVIDENCE_WINDOW)
    end = min(len(collapsed), position + len(alias) + _EVIDENCE_WINDOW)
    quote = collapsed[start:end].strip()
    if start > 0:
        quote = "…" + quote
    if end < len(collapsed):
        quote = quote + "…"
    return quote[:EVIDENCE_LIMIT]


def _normalized_items(items):
    """`{имя: (алиасы…)}` → `{имя: [алиас, …]}`: строки, strip + casefold.

    Неизвестные типы и пустые строки отбрасываются: битый конфиг не должен
    ронять оценку, он просто не даёт совпадений. Пустой список алиасов
    сохраняется — это способ выключить ресурс из конфига.
    """
    normalized = {}
    if not isinstance(items, dict):
        return normalized
    for name in sorted(items):
        key = str(name).strip()
        if not key:
            continue
        raw = items[name]
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, (list, tuple)):
            continue
        aliases = []
        for alias in raw:
            if not isinstance(alias, str):
                continue
            value = alias.strip().casefold()
            if value and value not in aliases:
                aliases.append(value)
        normalized[key] = aliases
    return normalized


def _source_texts(context):
    """Пары `(source, text)` из снимка задачи в фиксированном порядке.

    Порядок важен для детерминизма: первый найденный источник становится
    доказательством (`evidence`), остальные упоминания не дублируют ресурс.
    """
    pairs = []
    if not isinstance(context, dict):
        return pairs

    fields = context.get("fields") if isinstance(context.get("fields"), dict) else {}
    summary = _as_text(fields.get("summary")) or _as_text(context.get("summary"))
    if summary.strip():
        pairs.append(("summary", summary))

    for name in _TEXT_FIELDS:
        text = _as_text(context.get(name))
        if text.strip():
            pairs.append((name, text))

    sections = context.get("sections")
    if isinstance(sections, dict):
        for key in sorted(sections):
            text = _as_text(sections[key])
            if text.strip():
                pairs.append(("sections.%s" % key, text))

    labels = context.get("labels")
    text = _as_text(labels)
    if text.strip():
        pairs.append(("labels", text))

    issue_type = _as_text(context.get("issue_type"))
    if not issue_type.strip():
        issue_type = _as_text(fields.get("issue_type"))
    if issue_type.strip():
        pairs.append(("issue_type", issue_type))

    return pairs


def detect_resources(context, items=None):
    """Найти дополнительные ресурсы задачи. Возвращает `[{name, evidence, source}]`.

    Источники текста: заголовок (`fields.summary`), описание, значения
    `sections{}`, `labels`, `issue_type`. Поиск — подстрокой по `casefold()`
    тексту, поэтому «Allure» и «allure» равнозначны.

    Один ресурс = один элемент, сколько бы раз он ни упоминался: доказательством
    становится первое совпадение в порядке источников. Результат отсортирован по
    `name` — одинаковый снимок всегда даёт одинаковый список.

    `items` — `{имя: [алиасы]}` (по умолчанию `RESOURCE_ITEMS`); пустой список
    алиасов выключает ресурс, неизвестное имя добавляет новый.
    """
    catalogue = _normalized_items(
        RESOURCE_ITEMS if items is None else items
    )
    pairs = _source_texts(context)

    found = {}
    for name in sorted(catalogue):
        aliases = catalogue[name]
        if not aliases:
            continue
        for source, text in pairs:
            haystack = text.casefold()
            match = next((alias for alias in aliases if alias in haystack), None)
            if match is None:
                continue
            found[name] = {
                "name": name,
                "evidence": _evidence(text, match),
                "source": source,
            }
            break

    return [found[name] for name in sorted(found)]


def _number(value):
    """Число как в JSON: целое остаётся целым, дробное — float."""
    number = float(value)
    return int(number) if number.is_integer() else number


def resources_settings(config=None):
    """Нормализовать блок `estimation.resources`: дефолты + значения конфига.

    Битые значения не роняют оценку, а откатываются к дефолту: конфиг уже
    проверен `config-check`, но `estimate` обязан считать и с частичным блоком.
    `items` сливается по именам: конфиг может добавить ресурс или обнулить
    алиасы существующего, не переписывая остальные.
    """
    settings = {
        "enabled": True,
        "sp_per_resource": 1,
        "mode": "add",
        "items": _normalized_items(RESOURCE_ITEMS),
    }
    if not isinstance(config, dict):
        return settings

    enabled = config.get("enabled")
    if isinstance(enabled, bool):
        settings["enabled"] = enabled

    sp = config.get("sp_per_resource")
    if isinstance(sp, (int, float)) and not isinstance(sp, bool) and sp >= 0:
        settings["sp_per_resource"] = _number(sp)

    mode = config.get("mode")
    if isinstance(mode, str) and mode.strip() in RESOURCE_MODES:
        settings["mode"] = mode.strip()

    items = config.get("items")
    if isinstance(items, dict):
        merged = dict(settings["items"])
        merged.update(_normalized_items(items))
        settings["items"] = merged

    return settings


def resources_summary(context, config=None):
    """Сводка ресурсов для оценки и отчёта.

    Возвращает `{"items", "count", "sp_per_resource", "bonus_sp", "mode"}`;
    `bonus_sp = count × sp_per_resource`. `enabled: false` — пустой список и
    нулевая надбавка: правило выключено целиком.
    """
    settings = resources_settings(config)
    items = detect_resources(context, settings["items"]) if settings["enabled"] else []
    count = len(items)
    sp = settings["sp_per_resource"]
    return {
        "items": items,
        "count": count,
        "sp_per_resource": sp,
        "bonus_sp": _number(count * float(sp)),
        "mode": settings["mode"],
    }

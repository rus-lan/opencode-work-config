#!/usr/bin/env python3
"""Лимиты объёма: чтение входных JSON и обрезка текста в артефактах.

Два независимых ограничения, оба — защита от «мусора в артефактах»:

* **Вход.** Любой входной JSON больше `MAX_INPUT_BYTES` (5 МБ) не читается:
  `check_size` бросает `LimitError`, который CLI превращает в
  `[MISSING] <файл>: превышен лимит 5 МБ` и код 4 (`MISSING_ARTIFACT`).
  Порог одинаков для всех артефактов: ручной JSON такого размера — почти
  наверняка ошибка сборки снимка, а не рабочие данные.
* **Выход.** Свободный текст (`evidence`, `message`, `question`) обрезается до
  `MAX_TEXT_CHARS` (300) символов с многоточием `…`, а список пробелов — до
  `MAX_GAPS` (200) записей. Обрезка детерминированна: одинаковый вход даёт
  одинаковый выход, поэтому golden-сверки остаются стабильными.

Обрезка выполняется при записи артефактов (`check`, `questions`, `report`),
а не при чтении: исходный текст задачи не теряется, теряется только хвост
цитаты в отчёте.
"""

import json
import os

__all__ = [
    "ELLIPSIS",
    "MAX_GAPS",
    "MAX_INPUT_BYTES",
    "MAX_INPUT_MB",
    "MAX_TEXT_CHARS",
    "LimitError",
    "check_size",
    "limit_gaps",
    "read_json",
    "truncate",
]

# 5 МБ — порог входного JSON (см. модульный docstring).
MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_INPUT_MB = MAX_INPUT_BYTES // (1024 * 1024)

# 300 символов свободного текста и 200 пробелов — порог выходных артефактов.
MAX_TEXT_CHARS = 300
MAX_GAPS = 200

ELLIPSIS = "…"


class LimitError(Exception):
    """Входной файл превышает допустимый объём.

    Намеренно **не** наследник `ValueError`: иначе читатели, которые ловят
    `ValueError` как «битый JSON», превратили бы превышение лимита в
    `SCHEMA_ERROR` (5) вместо `MISSING_ARTIFACT` (4).
    """


def check_size(path, limit=MAX_INPUT_BYTES):
    """Проверить размер файла до чтения. `LimitError`, если он больше `limit`.

    Отсутствующий/недоступный файл не считается превышением: пусть `open`
    отдаст свою ошибку, её обработает вызывающая сторона.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size > limit:
        raise LimitError(
            "%s: превышен лимит %d МБ" % (path, limit // (1024 * 1024))
        )


def read_json(path):
    """Прочитать JSON с проверкой размера. Бросает `LimitError`/`OSError`/`ValueError`."""
    check_size(path)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def truncate(text, limit=MAX_TEXT_CHARS):
    """Обрезать свободный текст до `limit` символов, добавив `…`.

    Пустое/`None` значение → пустая строка. Многоточие входит в лимит, поэтому
    результат никогда не длиннее `limit`; уже короткий текст не меняется.
    """
    if text is None:
        return ""
    value = str(text).strip()
    if len(value) <= limit:
        return value
    if limit <= 1:
        return value[:limit]
    return value[: limit - 1] + ELLIPSIS


def limit_gaps(gaps, limit=MAX_GAPS):
    """Оставить не больше `limit` пробелов (порядок сохраняется)."""
    if not isinstance(gaps, list):
        return []
    return gaps[:limit]

#!/usr/bin/env python3
"""Относительные пути артефактов внутри `.task-readiness/`.

Единственный источник истины для путей `norm/*` и `model/*`: их пишут
`stats`/`calibrate`/`vectors`, их читают `estimate`/`check`/`report`, их
перечисляет `artifact pack` (`FILE_ORDER`). Пока литерал лежал в каждом модуле
отдельно, переименование файла требовало правки в пяти местах, а рассинхрон
(`task-texts.json` в одном месте, `task_texts.json` в другом) ломал бандл молча.

Пути заданы от корня `.task-readiness/` (`state.STATE_DIR`), не от корня проекта.
"""

__all__ = [
    "DB_RELATIVE",
    "MODEL_PAGE_RELATIVE",
    "MODEL_RELATIVE",
    "REFERENCE_RELATIVE",
    "SAMPLE_RELATIVE",
    "STATE_DIR_RELATIVE",
    "STATS_RELATIVE",
    "TEXTS_RELATIVE",
    "VECTORS_RELATIVE",
]

# Корень артефактов внутри проекта и файл SQLite-зеркала (storage.sqlite.path).
STATE_DIR_RELATIVE = ".task-readiness"
DB_RELATIVE = "trr.sqlite3"

# Нормативные данные обучения (`norm/`).
REFERENCE_RELATIVE = "norm/reference-estimates.json"
SAMPLE_RELATIVE = "norm/sprint-sample.json"
STATS_RELATIVE = "norm/sprint-stats.json"
TEXTS_RELATIVE = "norm/task-texts.json"
VECTORS_RELATIVE = "norm/task-vectors.json"

# Обученная модель и её `.md`-зеркало (`model/`).
MODEL_RELATIVE = "model/estimation-model.json"
MODEL_PAGE_RELATIVE = "model/estimation-model.md"

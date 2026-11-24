#!/usr/bin/env python3
"""Агрегация выборки спринтов в бакеты `.task-readiness/norm/sprint-stats.json`.

Вход — `norm/sprint-sample.json` (CONTRACT.md §5.4), выход — `norm/sprint-stats.json`
(§5.5). Модуль ничего не читает из сети: выборку кладёт на диск агент.

Правила, зафиксированные контрактом:

- бакет — тройка `(role, issue_type, work_kind)`; порядок бакетов в выводе —
  лексикографический по этой тройке, чтобы одинаковый вход давал одинаковый файл;
- `work_kind` в строке выборки схемой не предусмотрен (§5.4: ровно 10 полей,
  без `work_kind`), поэтому он всегда выводится из `issue_type` по таблице
  `WORK_KIND_BY_ISSUE_TYPE` (CONTRACT.md §3: `Ошибка` → `bugfix`, `Tech Debt` →
  `tech_debt`, `ADR` → `analysis`, `Feature`/`Задача` → `implementation`, иначе
  `unknown`). Лишнее поле `work_kind` в строке не читается: контракт выборки
  закрыт, и подмешивать вид работ в обход `issue_type` нельзя;
- QA-бакеты строятся отдельно — по `qa_estimation` строк с `has_testing == true`,
  с `role="QA"` и `work_kind="testing"`; они не зависят от заполненности `sp`;
- метрики считаются только по непустым значениям: `sp == null` не попадает в
  метрики (и учитывается счётчиком `skipped_rows`, который в схему не входит —
  `additionalProperties: false` в §5.5, поэтому наружу он не выводится);
- перцентили — линейная интерполяция (PERCENTILE.INC / type 7), `median` = `p=0.5`;
- `coverage = sufficient`, если `n >= min_sample_n`, иначе `insufficient`;
  каждый insufficient-бакет попадает в `insufficient[]` строкой `"<role>/<work_kind>"`;
- `computed_at` — единственное недетерминированное поле; при
  `TASK_READINESS_FIXED_TIME=1` подставляется `1970-01-01T00:00:00Z` (golden-тесты).

Округление квантилей — до 2 знаков (CONTRACT.md §8), `min`/`max` — целые:
схема §5.5 требует `integer`, поэтому нецелое значение в бакете — это
`ValueError` с понятным сообщением, а не тихая подмена числа.
"""

import json
import os
import statistics
from pathlib import Path

from trr_impl import config as configmod
from trr_impl import limits
from trr_impl import schema_lite
from trr_impl import state as statemod
from trr_impl import store as storemod
from trr_impl.paths import SAMPLE_RELATIVE, STATS_RELATIVE

__all__ = [
    "FIXED_TIME",
    "FIXED_TIME_ENV",
    "QA_WORK_KIND",
    "ROLES",
    "SAMPLE_RELATIVE",
    "STATS_RELATIVE",
    "WORK_KINDS",
    "WORK_KIND_BY_ISSUE_TYPE",
    "compute",
    "now_utc",
    "percentile",
    "run",
    "skipped_rows",
]

# Метка времени для golden-тестов: единственное недетерминированное поле
# артефакта фиксируется переменной окружения, а не подменой функции.
FIXED_TIME = "1970-01-01T00:00:00Z"
FIXED_TIME_ENV = "TASK_READINESS_FIXED_TIME"


ROLES = ("BA", "SA", "BE", "FE", "QA", "DEVOPS", "OTHER")
WORK_KINDS = (
    "implementation",
    "research",
    "bugfix",
    "tech_debt",
    "analysis",
    "testing",
    "unknown",
)

QA_WORK_KIND = "testing"

# CONTRACT.md §3: вид работ выводится из типа задачи. Строки, которых здесь
# нет (например, «Подзадача»), честно попадают в `unknown`, а не в
# `implementation`: догадка о виде работ запрещена (инвариант 1).
WORK_KIND_BY_ISSUE_TYPE = {
    "Feature": "implementation",
    "Задача": "implementation",
    "Ошибка": "bugfix",
    "Tech Debt": "tech_debt",
    "ADR": "analysis",
    "Исследование": "research",
}

# Знаков после запятой у квантилей (CONTRACT.md §8).
_QUANTILE_DIGITS = 2


# ---------------------------------------------------------------------------
# Время
# ---------------------------------------------------------------------------


def now_utc():
    """Момент расчёта статистики.

    Единственное недетерминированное поле артефакта. Для golden-тестов
    фиксируется `TASK_READINESS_FIXED_TIME=1`.
    """
    if os.environ.get(FIXED_TIME_ENV) == "1":
        return FIXED_TIME
    return statemod.now_utc()


# ---------------------------------------------------------------------------
# Математика
# ---------------------------------------------------------------------------


def percentile(values, p):
    """Перцентиль по линейной интерполяции (PERCENTILE.INC / type 7).

    `h = (n - 1) * p`, `v = x[floor(h)] + (h - floor(h)) * (x[ceil(h)] - x[floor(h)])`.
    При `n = 1` все квантили равны единственному значению.
    """
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("перцентиль от пустого списка не определён")
    if len(ordered) == 1:
        return ordered[0]
    h = (len(ordered) - 1) * float(p)
    low = int(h)
    high = low if h == low else low + 1
    if high >= len(ordered):
        high = len(ordered) - 1
    return ordered[low] + (h - low) * (ordered[high] - ordered[low])


def _quantile(values, p):
    return round(percentile(values, p), _QUANTILE_DIGITS)


def _bound(value, field, key):
    """Граница бакета: схема §5.5 требует integer для min/max."""
    number = float(value)
    if not number.is_integer():
        raise ValueError(
            "бакет %r: %s=%r не целое — схема sprint-stats требует целые min/max; "
            "приведите значения выборки к целым SP" % (key, field, value)
        )
    return int(number)


# ---------------------------------------------------------------------------
# Проверки входа
# ---------------------------------------------------------------------------


def _sample_rows(sample):
    if not isinstance(sample, dict):
        raise ValueError("выборка спринтов должна быть JSON-объектом")
    rows = sample.get("rows")
    if not isinstance(rows, list):
        raise ValueError("sprint-sample.rows должен быть массивом")
    return rows


def _check_row(row, index):
    if not isinstance(row, dict):
        raise ValueError("строка %d выборки должна быть объектом" % index)
    role = row.get("role")
    if role not in ROLES:
        raise ValueError(
            "строка %d: role=%r не входит в допустимые (%s)"
            % (index, role, ", ".join(ROLES))
        )
    issue_type = row.get("issue_type")
    if not isinstance(issue_type, str) or not issue_type.strip():
        raise ValueError("строка %d: issue_type пуст или не строка" % index)
    if not isinstance(row.get("has_testing"), bool):
        raise ValueError("строка %d: has_testing должен быть boolean" % index)


def _check_value(value, field, index):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            "строка %d: %s должен быть числом или null, получено %r"
            % (index, field, value)
        )
    if value < 0:
        raise ValueError("строка %d: %s не может быть отрицательным" % (index, field))


def _work_kind(row):
    """Вид работ строки: только вывод из типа задачи.

    Поля `work_kind` в строке выборки нет (CONTRACT.md §5.4: ровно 10 полей),
    поэтому лишний ключ не читается — иначе вид работ можно было бы подмешать
    в обход контракта.
    """
    return WORK_KIND_BY_ISSUE_TYPE.get(row.get("issue_type"), "unknown")


def skipped_rows(sample):
    """Сколько строк не попало в метрики из-за пустого `sp`.

    В схему sprint-stats (§5.5) поле не входит (`additionalProperties: false`),
    поэтому значение считается и отбрасывается: наружу отдаётся только этим
    хелпером, для диагностики.
    """
    rows = _sample_rows(sample)
    return sum(1 for row in rows if isinstance(row, dict) and row.get("sp") is None)


# ---------------------------------------------------------------------------
# Расчёт
# ---------------------------------------------------------------------------


def compute(sample, min_sample_n):
    """Посчитать статистику по выборке спринтов и проверить её по схеме.

    Возвращает объект `sprint-stats.json` (§5.5). Невалидный результат —
    `ValueError` с перечнем нарушений.
    """
    rows = _sample_rows(sample)
    if (
        isinstance(min_sample_n, bool)
        or not isinstance(min_sample_n, int)
        or min_sample_n < 1
    ):
        raise ValueError(
            "min_sample_n должен быть целым >= 1, получено %r" % (min_sample_n,)
        )

    groups = {}
    for index, row in enumerate(rows):
        _check_row(row, index)

        sp = row.get("sp")
        if sp is not None:
            _check_value(sp, "sp", index)
            key = (row["role"], row["issue_type"], _work_kind(row))
            groups.setdefault(key, []).append(float(sp))

        qa_estimation = row.get("qa_estimation")
        if row["has_testing"] and qa_estimation is not None:
            _check_value(qa_estimation, "qa_estimation", index)
            key = ("QA", row["issue_type"], QA_WORK_KIND)
            groups.setdefault(key, []).append(float(qa_estimation))

    buckets = []
    insufficient = []
    for key in sorted(groups):
        role, issue_type, work_kind = key
        values = groups[key]
        n = len(values)
        coverage = "sufficient" if n >= min_sample_n else "insufficient"
        buckets.append(
            {
                "role": role,
                "issue_type": issue_type,
                "work_kind": work_kind,
                "n": n,
                "mean": round(statistics.mean(values), _QUANTILE_DIGITS),
                "median": _quantile(values, 0.5),
                "p25": _quantile(values, 0.25),
                "p75": _quantile(values, 0.75),
                "min": _bound(min(values), "sp", key),
                "max": _bound(max(values), "sp", key),
                "coverage": coverage,
            }
        )
        if coverage == "insufficient":
            label = "%s/%s" % (role, work_kind)
            if label not in insufficient:
                insufficient.append(label)

    result = {
        "computed_at": now_utc(),
        "sample_rows": len(rows),
        "buckets": buckets,
        "insufficient": insufficient,
    }
    _validate(result)
    return result


def _validate(result):
    """Проверить результат по `sprint-stats.schema.json` (§5.5)."""
    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, "sprint-stats")
    except schema_lite.SchemaError as exc:
        raise ValueError("схема sprint-stats не читается: %s" % exc)
    errors = schema_lite.validate(result, schema, "sprint-stats")
    if errors:
        raise ValueError(
            "sprint-stats не соответствует схеме: %s" % "; ".join(errors)
        )


# ---------------------------------------------------------------------------
# CLI-обвязка (`trr stats`)
# ---------------------------------------------------------------------------


def _emit(message, quiet=False):
    if not quiet:
        print(message)


def _emit_json(args, payload):
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def run(workdir, args=None):
    """Выполнить `trr stats`: прочитать выборку, посчитать, записать артефакт."""
    workdir = Path(workdir)
    quiet = bool(getattr(args, "quiet", False))
    sample_path = workdir / statemod.STATE_DIR / SAMPLE_RELATIVE
    stats_path = workdir / statemod.STATE_DIR / STATS_RELATIVE

    if not sample_path.is_file():
        _emit(
            "[MISSING] %s — запустите /task-readiness-review train (выборка спринтов не выгружена)"
            % SAMPLE_RELATIVE,
            quiet,
        )
        _emit_json(
            args,
            {"status": "blocked", "code": 4, "artifact": SAMPLE_RELATIVE},
        )
        return 4

    try:
        limits.check_size(sample_path)
        with open(sample_path, "r", encoding="utf-8") as handle:
            sample = json.load(handle)
    except OSError as exc:
        _emit("[MISSING] %s — не читается: %s" % (SAMPLE_RELATIVE, exc), quiet)
        _emit_json(args, {"status": "blocked", "code": 5, "artifact": SAMPLE_RELATIVE})
        return 5
    except ValueError as exc:
        _emit("[MISSING] %s — невалидный JSON: %s" % (SAMPLE_RELATIVE, exc), quiet)
        _emit_json(args, {"status": "blocked", "code": 5, "artifact": SAMPLE_RELATIVE})
        return 5

    try:
        cfg = configmod.load_config(configmod.config_path(workdir))
    except configmod.ConfigError as exc:
        _emit("[MISSING] %s — %s" % (configmod.CONFIG_FILENAME, exc), quiet)
        _emit_json(args, {"status": "blocked", "code": 3, "config": None})
        return 3

    min_sample_n = cfg.get("validation", {}).get("min_sample_n", 5)
    try:
        result = compute(sample, min_sample_n)
    except ValueError as exc:
        _emit("[MISSING] sprint-stats — %s" % exc, quiet)
        _emit_json(args, {"status": "blocked", "code": 5, "artifact": STATS_RELATIVE})
        return 5

    schema_lite.write_json(stats_path, result)

    # Зеркало пишется после успешного шага и никогда не валит его: ошибка БД —
    # [WARN] внутри store, код выхода остаётся кодом `stats`.
    storemod.save_stats(workdir, cfg, result)

    for bucket in result["buckets"]:
        if bucket["coverage"] == "insufficient":
            _emit(
                "[WARN] bucket %s/%s: n=%d < min_sample_n=%d — confidence=low"
                % (
                    bucket["role"],
                    bucket["work_kind"],
                    bucket["n"],
                    min_sample_n,
                ),
                quiet,
            )
    _emit(
        "[OK] %s: buckets=%d, sample_rows=%d, insufficient=%d"
        % (
            STATS_RELATIVE,
            len(result["buckets"]),
            result["sample_rows"],
            len(result["insufficient"]),
        ),
        quiet,
    )
    _emit_json(
        args,
        {
            "status": "ok",
            "code": 0,
            "artifact": STATS_RELATIVE,
            "buckets": len(result["buckets"]),
            "sample_rows": result["sample_rows"],
            "insufficient": len(result["insufficient"]),
        },
    )
    return 0

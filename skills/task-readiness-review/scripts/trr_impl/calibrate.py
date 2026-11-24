#!/usr/bin/env python3
"""Построение модели оценки `.task-readiness/model/estimation-model.json`.

Модель — это данные, а не код (PLAN.md §1): база по роли и виду работ, коэффициент
калибровки по статистике спринтов, ожидаемое значение, диапазон, уверенность,
провенанс каждого числа и таблица штрафов за REQUIRED-пробелы.

Формула (PLAN.md §4, CONTRACT.md §8):

1. `base` — значение эталона для пары `(role, work_kind)`; эталона нет →
   фолбэк на пару `(role, "implementation")` (`reference = "fallback"`), а если
   нет и её — `base = nearest_scale(median)`, `reference = "none"`,
   `confidence = "low"`;
2. `factor = clamp(observed / base, factor_clamp[0], factor_clamp[1])`, где
   `observed = median` бакета статистики; бакет с `coverage = insufficient`
   или без медианы → `factor = 1.0` и `confidence = "low"`;
3. `params_multiplier` — множитель эвристических параметров задачи
   (`weight`/`heat`/`connectivity`) по профилю бакета: медиана `params.derive`
   по строкам спринта бакета, если сигналов достаточно; иначе `defaults`
   конфига (множитель ровно `1.0`);
4. `expected = nearest_scale(base * factor * params_multiplier)`;
5. `range = [nearest_scale_down(p25-ветка), nearest_scale_up(p75-ветка)]`,
   с гарантией `range[0] <= expected <= range[1]` и попадания в шкалу;
6. `checksum` — sha256 канонического JSON без поля `checksum` (§8).

Честность BA/SA (PLAN.md §4): эталона по этим ролям нет, поэтому `reference`
всегда `"none"` и `confidence` всегда `"low"` — даже при большой выборке.

`generated_at` — единственное недетерминированное поле; при
`TASK_READINESS_FIXED_TIME=1` подставляется `1970-01-01T00:00:00Z`.
"""

import json
import math
import statistics
from pathlib import Path

from trr_impl import config as configmod
from trr_impl import limits
from trr_impl import params as paramsmod
from trr_impl import resources as resourcesmod
from trr_impl import schema_lite
from trr_impl import state as statemod
from trr_impl import store as storemod
from trr_impl.stats import WORK_KIND_BY_ISSUE_TYPE, now_utc

__all__ = [
    "GAP_RULES",
    "MODEL_RELATIVE",
    "REFERENCE_RELATIVE",
    "build",
    "clamp",
    "content_checksum",
    "nearest_scale",
    "nearest_scale_down",
    "nearest_scale_up",
    "run",
]

MODEL_RELATIVE = "model/estimation-model.json"
MODEL_HISTORY_RELATIVE = "model/model-history.jsonl"
REFERENCE_RELATIVE = "norm/reference-estimates.json"
STATS_RELATIVE = "norm/sprint-stats.json"
SAMPLE_RELATIVE = "norm/sprint-sample.json"

# Таблица штрафов — данные, а не код (PLAN.md §1). Привязка к check-id
# validation.json: `GR-01` ← `SA-08` (нет критериев приёмки), `GR-02` ← `SA-04`
# (нет контракта API при изменении интеграции), `GR-03` ← `TPL-07` (не
# заполнена Роль), `GR-04` ← `QA-01` (нет оценки QA при требуемом тестировании).
# Сортировка по `rule_id` фиксирована (CONTRACT.md §5.6).
GAP_RULES = (
    {
        "rule_id": "GR-01",
        "condition": "SA-08=FAIL",
        "penalty_steps": 2,
        "applies_to": ["SA", "BE", "FE", "QA"],
    },
    {
        "rule_id": "GR-02",
        "condition": "SA-04=FAIL",
        "penalty_steps": 1,
        "applies_to": ["SA", "BE", "FE"],
    },
    {
        "rule_id": "GR-03",
        "condition": "TPL-07=FAIL",
        "penalty_steps": 1,
        "applies_to": ["BA", "SA", "BE", "FE", "QA", "DEVOPS", "OTHER"],
    },
    {
        "rule_id": "GR-04",
        "condition": "QA-01=FAIL",
        "penalty_steps": 1,
        "applies_to": ["QA"],
    },
)

_ROLES = ("BA", "SA", "BE", "FE", "QA", "DEVOPS", "OTHER")
_FACTOR_DIGITS = 4


# ---------------------------------------------------------------------------
# Шкала
# ---------------------------------------------------------------------------


def clamp(value, low, high):
    """`min(max(x, lo), hi)` (CONTRACT.md §8)."""
    return min(max(value, low), high)


def nearest_scale(value, scale):
    """Ближайшее значение шкалы; при равенстве расстояний — большее (§8)."""
    best = None
    for candidate in scale:
        if best is None or abs(value - candidate) <= abs(value - best):
            best = candidate
    if best is None:
        raise ValueError("шкала пуста — нечего округлять")
    return best


def nearest_scale_down(value, scale):
    """Наибольшее значение шкалы `<= value`; ниже шкалы — её минимум."""
    chosen = scale[0]
    for candidate in scale:
        if candidate <= value:
            chosen = candidate
        else:
            break
    return chosen


def nearest_scale_up(value, scale):
    """Наименьшее значение шкалы `>= value`; выше шкалы — её максимум."""
    chosen = scale[-1]
    for candidate in reversed(scale):
        if candidate >= value:
            chosen = candidate
        else:
            break
    return chosen


def _scale(cfg):
    estimation = (cfg or {}).get("estimation") or {}
    scale = estimation.get("scale")
    if (
        not isinstance(scale, list)
        or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in scale
        )
        or any(scale[index] >= scale[index + 1] for index in range(len(scale) - 1))
    ):
        raise ValueError(
            "config.estimation.scale: нужен строго возрастающий список целых, получено %r"
            % (scale,)
        )
    if scale != configmod.NORMATIVE_SCALE:
        raise ValueError(
            "config.estimation.scale: шкала нормативна и должна совпадать с %r, получено %r"
            % (configmod.NORMATIVE_SCALE, scale)
        )
    return list(scale)


def _min_sample_n(cfg):
    value = ((cfg or {}).get("validation") or {}).get("min_sample_n", 5)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(
            "config.validation.min_sample_n: нужно целое >= 1, получено %r" % (value,)
        )
    return value


def _factor_clamp(cfg):
    default = configmod.DEFAULTS["estimation"]["factor_clamp"]
    value = ((cfg or {}).get("estimation") or {}).get("factor_clamp", default)
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(
            isinstance(item, bool) or not isinstance(item, (int, float))
            for item in value
        )
        or not (0 < value[0] < value[1])
    ):
        raise ValueError(
            "config.estimation.factor_clamp: нужно 0 < min < max, получено %r" % (value,)
        )
    return float(value[0]), float(value[1])


def _fmt(value):
    """Детерминированное представление числа в тексте провенанса."""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return "%g" % number


# ---------------------------------------------------------------------------
# Входы
# ---------------------------------------------------------------------------


def _reference_index(reference, scale):
    """Индекс эталона по `(role, work_kind)` с проверкой семантики §5.3.

    Значение записи — `{"value": int, "reference": "yes", "from": (role,
    work_kind)}`. Документированный фолбэк живёт в `_reference_entry`: сама
    пара, которой нет в эталоне, сюда не дописывается — иначе «эталона нет» и
    «взяли соседний вид работ» стали бы неотличимы.
    """
    if not isinstance(reference, dict):
        raise ValueError("reference-estimates должен быть JSON-объектом")
    buckets = reference.get("buckets")
    if not isinstance(buckets, list):
        raise ValueError("reference-estimates.buckets должен быть массивом")
    index = {}
    for position, bucket in enumerate(buckets):
        if not isinstance(bucket, dict):
            raise ValueError("reference-estimates.buckets[%d] не объект" % position)
        role = bucket.get("role")
        work_kind = bucket.get("work_kind")
        value = bucket.get("value")
        if role not in _ROLES:
            raise ValueError(
                "reference-estimates.buckets[%d]: role=%r не входит в допустимые"
                % (position, role)
            )
        if value not in scale:
            raise ValueError(
                "reference-estimates.buckets[%d]: value=%r не входит в шкалу %r"
                % (position, value, scale)
            )
        key = (role, work_kind)
        if key in index:
            raise ValueError(
                "reference-estimates: дубликат пары (%s, %s)" % (role, work_kind)
            )
        index[key] = {"value": value, "reference": "yes", "from": key}
    return index


def _reference_entry(index, role, work_kind):
    """Эталон для пары `(role, work_kind)` с документированным фолбэком.

    Порядок: точная пара → пара `(role, "implementation")` → `None`.

    Фолбэк нужен потому, что статистика строит QA-бакеты с `work_kind=testing`
    (QA Estimation), а таблица эталона описывает виды работ без `testing`.
    Подставлять «нет эталона» было бы регрессом: раньше QA/testing получал базу
    из статистики и `reference=none`, из-за чего `expected` уезжал вниз.

    Результат фолбэка помечается `reference="fallback"` (не `"yes"`): база
    взята у другого вида работ, поэтому уверенность по такому бакету не может
    быть `high`, а `provenance` называет пару-источник.
    """
    direct = index.get((role, work_kind))
    if direct is not None:
        return direct
    if work_kind != "implementation":
        fallback = index.get((role, "implementation"))
        if fallback is not None:
            return {
                "value": fallback["value"],
                "reference": "fallback",
                "from": (role, "implementation"),
            }
    return None


def _reference_source(reference):
    source = reference.get("source")
    if not isinstance(source, dict):
        raise ValueError("reference-estimates.source должен быть объектом")
    for key in ("system", "page_id", "url", "retrieved_at"):
        if not isinstance(source.get(key), str) or not source[key].strip():
            raise ValueError(
                "reference-estimates.source.%s обязателен и непуст" % key
            )
    return {
        "system": source["system"],
        "page_id": str(source["page_id"]),
        "url": source["url"],
        "retrieved_at": source["retrieved_at"],
    }


def _sprint_sources(sample):
    """Спринты калибровки из выборки: порядок `(name, id)` — детерминированный."""
    if not isinstance(sample, dict):
        return []
    source = sample.get("source")
    if not isinstance(source, dict):
        return []
    sprints = source.get("sprints")
    if not isinstance(sprints, list):
        return []
    entries = []
    for item in sprints:
        if not isinstance(item, dict):
            continue
        entries.append(
            {
                "id": int(item["id"]),
                "name": str(item["name"]),
                "state": str(item["state"]),
            }
        )
    entries.sort(key=lambda item: (item["name"], item["id"]))
    return entries


def _absent_roles(reference):
    roles = reference.get("absent_roles")
    if not isinstance(roles, list):
        raise ValueError("reference-estimates.absent_roles должен быть массивом")
    for role in roles:
        if role not in _ROLES:
            raise ValueError(
                "reference-estimates.absent_roles: %r не входит в допустимые" % (role,)
            )
    return list(roles)


# ---------------------------------------------------------------------------
# Профиль параметров бакета и калибровка коэффициентов
# ---------------------------------------------------------------------------

# Минимальное покрытие сигналов параметра (`params.coverage`), при котором
# медиана по строкам спринта считается профилем. Строка выборки содержит только
# `labels` и `issue_type`, поэтому покрытие там мало (weight 0.35, heat 0.25,
# connectivity 0.25): профиль из такой строки — «ограниченный», и параметр без
# покрытия берётся из `defaults` (множитель 1.0), а не из шума.
_PARAM_COVERAGE_MIN = 0.5

# Условия калибровки коэффициентов регрессией: меньше — не подгоняем.
_REGRESSION_MIN_N = 30
_REGRESSION_MIN_VARIANCE = 0.01
_COEFFICIENT_MAX = 2.0


def _sample_rows(sample):
    """Строки выборки спринтов (мусор в списке игнорируется)."""
    rows = sample.get("rows") if isinstance(sample, dict) else None
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _row_context(row):
    """Снимок строки выборки для `params.derive`.

    В строке выборки есть только `labels` и `issue_type` (контракт §5.4):
    описания, связей и секций там нет. Поэтому профиль бакета — ограниченный,
    и это фиксируется в `params_profile_source`.
    """
    context = {"issue_type": row.get("issue_type")}
    if "labels" in row:
        context["labels"] = row.get("labels")
    return context


def _sample_groups(sample, cfg):
    """`{бакет: [derive(), …]}` — строки выборки по бакетам статистики.

    Группировка повторяет `stats.compute`: строка с непустым `sp` попадает в
    `(role, issue_type, work_kind)`, а строка с `has_testing` — ещё и в
    `("QA", issue_type, "testing")` по `qa_estimation`.
    """
    groups = {}
    for row in _sample_rows(sample):
        issue_type = row.get("issue_type")
        if not isinstance(issue_type, str) or not issue_type.strip():
            continue
        role = row.get("role")
        if role in _ROLES and row.get("sp") is not None:
            key = (role, issue_type, WORK_KIND_BY_ISSUE_TYPE.get(issue_type, "unknown"))
            groups.setdefault(key, []).append(paramsmod.derive(_row_context(row), cfg))
        if row.get("has_testing") and row.get("qa_estimation") is not None:
            key = ("QA", issue_type, "testing")
            groups.setdefault(key, []).append(paramsmod.derive(_row_context(row), cfg))
    return groups


def _defaults_profile(cfg):
    settings = paramsmod.settings(cfg)
    return {
        name: float(settings["defaults"][name]) for name in paramsmod.PARAM_NAMES
    }


def _params_profile(rows, cfg, min_sample_n):
    """Профиль параметров бакета: медиана по строкам или `defaults`.

    Возвращает `{profile, source, multiplier, coverage, detail}`:
    `source="bucket"` — все три параметра покрыты сигналами строк;
    `source="sample_limited"` — часть параметров покрыта, остальные из
    `defaults` (множитель тогда ≈ 1.0); `source="defaults"` — строк мало или
    сигналов нет вовсе (множитель ровно 1.0).
    """
    settings = paramsmod.settings(cfg)
    defaults = _defaults_profile(cfg)
    n = len(rows)

    if n < min_sample_n:
        return {
            "profile": defaults,
            "source": "defaults",
            "multiplier": 1.0,
            "coverage": {},
            "detail": (
                "строк спринта в бакете %d < min_sample_n %d — профиль "
                "параметров = defaults, множитель 1.0" % (n, min_sample_n)
            ),
        }

    informative = any(
        float(value) > 0.0
        for entry in rows
        for param in paramsmod.PARAM_NAMES
        for value in (entry.get(param, {}).get("components") or {}).values()
    )
    if not informative:
        return {
            "profile": defaults,
            "source": "defaults",
            "multiplier": 1.0,
            "coverage": {},
            "detail": (
                "строки бакета (n=%d) не дали ни одного ненулевого сигнала — "
                "профиль параметров = defaults, множитель 1.0" % n
            ),
        }

    profile = {}
    coverage = {}
    for name in paramsmod.PARAM_NAMES:
        values = [
            float(entry[name]["value"])
            for entry in rows
            if isinstance(entry.get(name), dict)
        ]
        coverage[name] = max(
            paramsmod.coverage(name, entry[name], cfg)
            for entry in rows
            if isinstance(entry.get(name), dict)
        )
        profile[name] = (
            round(statistics.median(values), 4)
            if values and coverage[name] >= _PARAM_COVERAGE_MIN
            else defaults[name]
        )

    complete = all(
        coverage[name] >= _PARAM_COVERAGE_MIN for name in paramsmod.PARAM_NAMES
    )
    multiplier = paramsmod.multiplier(
        {name: {"value": profile[name]} for name in paramsmod.PARAM_NAMES},
        cfg,
    )
    if complete:
        detail = (
            "медиана параметров по n=%d строкам спринта → множитель %s"
            % (n, _fmt(multiplier))
        )
        source = "bucket"
    else:
        uncovered = [
            "%s %.2f" % (name, coverage[name])
            for name in paramsmod.PARAM_NAMES
            if coverage[name] < _PARAM_COVERAGE_MIN
        ]
        detail = (
            "профиль ограничен строками выборки (n=%d): покрытие сигналов %s "
            "ниже %.2f — эти параметры взяты из defaults, множитель %s"
            % (n, ", ".join(uncovered), _PARAM_COVERAGE_MIN, _fmt(multiplier))
        )
        source = "sample_limited"

    return {
        "profile": profile,
        "source": source,
        "multiplier": multiplier,
        "coverage": coverage,
        "detail": detail,
    }


def _variance(values):
    if not values:
        return 0.0
    mean = sum(values) / float(len(values))
    return sum((value - mean) ** 2 for value in values) / float(len(values))


def _solve_linear(matrix, vector):
    """Решение СЛАУ методом Гаусса с выбором главного элемента; `None` — вырождена."""
    size = len(vector)
    if size == 0 or any(len(row) != size for row in matrix):
        return None
    table = [list(map(float, row)) + [float(vector[index])] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(table[row][column]))
        if abs(table[pivot][column]) < 1e-12:
            return None
        table[column], table[pivot] = table[pivot], table[column]
        divisor = table[column][column]
        for index in range(column, size + 1):
            table[column][index] /= divisor
        for row in range(size):
            if row == column:
                continue
            factor = table[row][column]
            if factor == 0.0:
                continue
            for index in range(column, size + 1):
                table[row][index] -= factor * table[column][index]
    return [table[row][size] for row in range(size)]


def _least_squares(design, values):
    """МНК через нормальные уравнения (без внешних зависимостей)."""
    size = len(design[0]) if design else 0
    matrix = [
        [sum(row[i] * row[j] for row in design) for j in range(size)]
        for i in range(size)
    ]
    vector = [
        sum(row[i] * value for row, value in zip(design, values))
        for i in range(size)
    ]
    return _solve_linear(matrix, vector)


def _r2(design, values, coefficients):
    mean = sum(values) / float(len(values))
    total = sum((value - mean) ** 2 for value in values)
    if total <= 0.0:
        return 1.0
    residual = sum(
        (value - sum(coef * item for coef, item in zip(coefficients, row))) ** 2
        for row, value in zip(design, values)
    )
    return 1.0 - residual / total


def _fit_coefficients(sample, reference_index, cfg):
    """Коэффициенты множителя: регрессия `log(sp / base)` или приор конфига.

    Регрессия строится по строкам выборки, где есть сигналы параметров:
    `log(sp / base) ~ 1 + a·(w-w0) + b·(h-h0) + c·(k-k0)`. Если строк меньше
    `_REGRESSION_MIN_N` или дисперсия любого регрессора ниже
    `_REGRESSION_MIN_VARIANCE`, коэффициенты не подгоняются: берётся приор
    конфига, а причина отказа попадает в провенанс модели.
    """
    settings = paramsmod.settings(cfg)
    prior = {
        name: float(settings["coefficients"][name]) for name in paramsmod.PARAM_NAMES
    }
    defaults = _defaults_profile(cfg)

    observations = []
    for row in _sample_rows(sample):
        sp = row.get("sp")
        if isinstance(sp, bool) or not isinstance(sp, (int, float)) or sp <= 0:
            continue
        role = row.get("role")
        issue_type = row.get("issue_type")
        if role not in _ROLES or not isinstance(issue_type, str) or not issue_type.strip():
            continue
        work_kind = WORK_KIND_BY_ISSUE_TYPE.get(issue_type, "unknown")
        reference = _reference_entry(reference_index, role, work_kind)
        if reference is None:
            continue
        derived = paramsmod.derive(_row_context(row), cfg)
        if not any(
            derived[name].get("components") for name in paramsmod.PARAM_NAMES
        ):
            continue
        regressors = [
            derived[name]["value"] - defaults[name] for name in paramsmod.PARAM_NAMES
        ]
        observations.append((regressors, math.log(float(sp) / float(reference["value"]))))

    n = len(observations)
    if n < _REGRESSION_MIN_N:
        return prior, {
            "source": "prior",
            "n": n,
            "reason": (
                "строк с сигналами %d < %d — коэффициенты взяты из конфига"
                % (n, _REGRESSION_MIN_N)
            ),
        }

    columns = [list(column) for column in zip(*[item[0] for item in observations])]
    weak = [
        paramsmod.PARAM_NAMES[index]
        for index, column in enumerate(columns)
        if _variance(column) < _REGRESSION_MIN_VARIANCE
    ]
    if weak:
        return prior, {
            "source": "prior",
            "n": n,
            "reason": (
                "дисперсия регрессоров %s < %.2f — коэффициенты не "
                "идентифицируются, взяты из конфига"
                % (", ".join(weak), _REGRESSION_MIN_VARIANCE)
            ),
        }

    design = [[1.0] + item[0] for item in observations]
    values = [item[1] for item in observations]
    solved = _least_squares(design, values)
    if solved is None:
        return prior, {
            "source": "prior",
            "n": n,
            "reason": "нормальные уравнения вырождены — коэффициенты взяты из конфига",
        }

    fitted = {
        name: round(min(max(solved[index + 1], 0.0), _COEFFICIENT_MAX), 4)
        for index, name in enumerate(paramsmod.PARAM_NAMES)
    }
    return fitted, {
        "source": "regression",
        "n": n,
        "r2": round(_r2(design, values, solved), 4),
        "reason": "",
    }


def _params_block(cfg, coefficients, fit_info, profile_sources):
    """Блок `params` модели: настройки, коэффициенты и их провенанс."""
    settings = paramsmod.settings(cfg)
    values = {
        name: float(coefficients[name]) for name in paramsmod.PARAM_NAMES
    }
    provenance = [
        {
            "field": "coefficients",
            "kind": "sprint_stats" if fit_info["source"] == "regression" else "rule",
            "source": (
                "sprint-stats:regression"
                if fit_info["source"] == "regression"
                else "config:estimation.params.coefficients"
            ),
            "detail": (
                "регрессия log(sp/base) на (w-w0, h-h0, k-k0): n=%d, r2=%s, "
                "коэффициенты ограничены [0, %.1f]"
                % (fit_info["n"], _fmt(fit_info.get("r2", 0.0)), _COEFFICIENT_MAX)
                if fit_info["source"] == "regression"
                else "%s; коэффициенты: %s"
                % (
                    fit_info["reason"],
                    ", ".join(
                        "%s=%s" % (name, _fmt(values[name]))
                        for name in paramsmod.PARAM_NAMES
                    ),
                )
            ),
        },
        {
            "field": "profile",
            "kind": "rule",
            "source": "estimation-model:params_profile",
            "detail": (
                "профили бакетов: bucket=%d, sample_limited=%d, defaults=%d"
                % (
                    profile_sources.get("bucket", 0),
                    profile_sources.get("sample_limited", 0),
                    profile_sources.get("defaults", 0),
                )
            ),
        },
    ]
    return {
        "enabled": bool(settings["enabled"]),
        "clamp": [float(settings["clamp"][0]), float(settings["clamp"][1])],
        "coefficients": values,
        "coefficients_source": fit_info["source"],
        "defaults": _defaults_profile(cfg),
        "profile_source": (
            "bucket"
            if profile_sources.get("bucket") or profile_sources.get("sample_limited")
            else "defaults"
        ),
        "provenance": provenance,
    }


def _resources_block(cfg):
    """Блок `resources` модели: надбавка за дополнительные ресурсы (`RS-01`).

    Правило `RS-01` живёт в `estimate.py`, но его настройки — часть модели:
    без блока страница модели не смогла бы объяснить, почему оценка задачи с
    тест-кейсами или автотестами выше бакета. Как и `params`/`gap_rules`,
    блок — данные из конфига, а не расчёт по выборке, поэтому версия модели
    растёт при изменении настроек (их видит `content_checksum`).
    """
    settings = resourcesmod.resources_settings(
        ((cfg or {}).get("estimation") or {}).get("resources")
    )
    items = {
        str(name): [str(alias) for alias in aliases]
        for name, aliases in sorted((settings.get("items") or {}).items())
    }
    return {
        "rule_id": "RS-01",
        "enabled": bool(settings["enabled"]),
        "sp_per_resource": float(settings["sp_per_resource"]),
        "mode": str(settings["mode"]),
        "items": items,
        "provenance": [
            {
                "field": "sp_per_resource",
                "kind": "rule",
                "source": "config:estimation.resources",
                "detail": (
                    "надбавка за ресурс: %s SP; mode=%s; enabled=%s"
                    % (
                        _fmt(float(settings["sp_per_resource"])),
                        settings["mode"],
                        "да" if settings["enabled"] else "нет",
                    )
                ),
            },
            {
                "field": "items",
                "kind": "rule",
                "source": "config:estimation.resources.items",
                "detail": "ресурсы: %s"
                % ", ".join(
                    "%s (алиасов %d)" % (name, len(aliases))
                    for name, aliases in items.items()
                ),
            },
        ],
    }


# ---------------------------------------------------------------------------
# Построение модели
# ---------------------------------------------------------------------------


def build(reference, stats, cfg, previous=None, sample=None, version=None):
    """Собрать модель оценки по эталону и статистике спринтов.

    `previous` — прошлая модель (для нумерации версий: `version + 1`),
    `sample` — выборка спринтов (даёт `sources.sprints` и профили параметров),
    `version` — явная версия (нужна CLI-обвязке, чтобы сравнить содержимое с
    прошлой моделью).
    """
    scale = _scale(cfg)
    min_sample_n = _min_sample_n(cfg)
    factor_low, factor_high = _factor_clamp(cfg)
    reference_index = _reference_index(reference, scale)
    source = _reference_source(reference)

    if version is None:
        if previous is not None:
            version = _previous_version(previous) + 1
        else:
            version = 1
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("version модели должен быть целым >= 1, получено %r" % (version,))

    buckets_in = (stats or {}).get("buckets")
    if not isinstance(buckets_in, list):
        raise ValueError("sprint-stats.buckets должен быть массивом")

    groups = _sample_groups(sample, cfg)
    coefficients, fit_info = _fit_coefficients(sample, reference_index, cfg)
    buckets = []
    profile_sources = {}
    for entry in buckets_in:
        key = (
            entry.get("role") if isinstance(entry, dict) else None,
            entry.get("issue_type") if isinstance(entry, dict) else None,
            entry.get("work_kind") if isinstance(entry, dict) else None,
        )
        profile = _params_profile(groups.get(key) or [], cfg, min_sample_n)
        profile_sources[profile["source"]] = profile_sources.get(profile["source"], 0) + 1
        buckets.append(
            _bucket(
                entry,
                reference_index=reference_index,
                scale=scale,
                min_sample_n=min_sample_n,
                factor_low=factor_low,
                factor_high=factor_high,
                page_id=source["page_id"],
                params_profile=profile,
            )
        )

    model = {
        "version": version,
        "generated_at": now_utc(),
        "scale": scale,
        "buckets": buckets,
        "gap_rules": [dict(rule) for rule in GAP_RULES],
        "absent_roles": _absent_roles(reference),
        "sources": {"reference": source, "sprints": _sprint_sources(sample)},
        "params": _params_block(cfg, coefficients, fit_info, profile_sources),
        "resources": _resources_block(cfg),
    }
    model["checksum"] = checksum(model)
    _validate(model)
    return model


def _previous_version(previous):
    version = previous.get("version") if isinstance(previous, dict) else None
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError(
            "в прошлой модели некорректная версия %r — пересоберите её заново" % (version,)
        )
    return version


def _bucket(
    entry,
    reference_index,
    scale,
    min_sample_n,
    factor_low,
    factor_high,
    page_id,
    params_profile=None,
):
    if not isinstance(entry, dict):
        raise ValueError("sprint-stats.buckets: элемент не объект")
    role = entry.get("role")
    issue_type = entry.get("issue_type")
    work_kind = entry.get("work_kind")
    if role not in _ROLES:
        raise ValueError("sprint-stats.buckets: role=%r не входит в допустимые" % (role,))
    n = entry.get("n")
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("sprint-stats.buckets: n=%r должен быть целым >= 0" % (n,))

    median = entry.get("median")
    p25 = entry.get("p25")
    p75 = entry.get("p75")
    coverage = entry.get("coverage")

    reference_entry = _reference_entry(reference_index, role, work_kind)
    stats_source = "sprint-stats:%s/%s/%s" % (role, issue_type, work_kind)

    if reference_entry is None:
        base = nearest_scale(float(median) if median is not None else 1.0, scale)
        reference = "none"
    else:
        base = reference_entry["value"]
        reference = reference_entry["reference"]

    no_data = coverage == "insufficient" or median is None
    if no_data:
        factor = 1.0
    else:
        factor = round(
            clamp(float(median) / float(base), factor_low, factor_high),
            _FACTOR_DIGITS,
        )

    profile = params_profile if isinstance(params_profile, dict) else {}
    profile_values = profile.get("profile") or {}
    multiplier = profile.get("multiplier")
    if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)):
        multiplier = 1.0
    multiplier = round(float(multiplier), _FACTOR_DIGITS)
    profile_source = str(profile.get("source") or "defaults")

    expected = nearest_scale(base * factor * multiplier, scale)

    low_branch = base * ((float(p25) / base) if p25 else 1.0) * factor * multiplier
    high_branch = base * ((float(p75) / base) if p75 else 1.0) * factor * multiplier
    range_low = nearest_scale_down(low_branch, scale)
    range_high = nearest_scale_up(high_branch, scale)
    if range_low > expected:
        range_low = expected
    if range_high < expected:
        range_high = expected

    if reference == "yes" and n >= 2 * min_sample_n:
        confidence = "high"
    elif reference in ("yes", "fallback") and n >= min_sample_n:
        # Фолбэк — база другого вида работ: даже на большой выборке это не
        # даёт права называть уверенность высокой.
        confidence = "medium"
    else:
        confidence = "low"
    if no_data:
        confidence = "low"

    if reference == "yes":
        base_provenance = {
            "field": "base",
            "kind": "reference",
            "source": "confluence:%s" % page_id,
            "detail": "%s/%s = %d (эталон, page_id %s)"
            % (role, work_kind, base, page_id),
        }
    elif reference == "fallback":
        base_provenance = {
            "field": "base",
            "kind": "reference_fallback",
            "source": "confluence:%s" % page_id,
            "detail": (
                "эталона по %s/%s нет: взята пара %s/%s = %d (фолбэк, page_id %s)"
                % (
                    role,
                    work_kind,
                    reference_entry["from"][0],
                    reference_entry["from"][1],
                    base,
                    page_id,
                )
            ),
        }
    else:
        base_provenance = {
            "field": "base",
            "kind": "sprint_stats",
            "source": stats_source,
            "detail": "эталона по %s/%s нет: base = nearest_scale(median %s) = %d"
            % (role, work_kind, _fmt(median) if median is not None else "—", base),
        }

    provenance = [
        base_provenance,
        {
            "field": "factor",
            "kind": "sprint_stats",
            "source": stats_source,
            "detail": (
                "coverage=%s (n=%d), factor = 1.0"
                % (coverage, n)
                if no_data
                else "median %s / base %d = %s, n=%d"
                % (_fmt(median), base, _fmt(factor), n)
            ),
        },
        {
            "field": "params_multiplier",
            "kind": "rule",
            "source": "estimation-model:params_profile",
            "detail": "%s (profile=%s, baseline=defaults)"
            % (profile.get("detail") or "профиль не задан", profile_source),
        },
        {
            "field": "expected",
            "kind": "rule",
            "source": "estimation-model:nearest_scale",
            "detail": "base %d × factor %s × params %s = %s → nearest_scale = %d"
            % (base, _fmt(factor), _fmt(multiplier), _fmt(base * factor * multiplier), expected),
        },
    ]

    result = {
        "role": role,
        "issue_type": issue_type,
        "work_kind": work_kind,
        "base": base,
        "factor": factor,
        "expected": expected,
        "range": [range_low, range_high],
        "n": n,
        "confidence": confidence,
        "reference": reference,
        "provenance": provenance,
    }
    if profile_values:
        result["params_profile"] = {
            name: float(profile_values[name]) for name in paramsmod.PARAM_NAMES
        }
        result["params_multiplier"] = multiplier
        result["params_profile_source"] = profile_source
    return result


def checksum(model):
    """sha256 канонического JSON модели без поля `checksum` (CONTRACT.md §8)."""
    payload = {key: value for key, value in model.items() if key != "checksum"}
    return schema_lite.sha256_canonical(payload)


def content_checksum(model):
    """Контрольная сумма «содержимого» модели: без `checksum` и `generated_at`.

    Нужна CLI-обвязке, чтобы отличить «входы не изменились» от «модель
    пересобрана»: `checksum` по контракту включает `generated_at`, поэтому
    меняется от прогона к прогону и для сравнения не годится.
    """
    payload = {
        key: value
        for key, value in model.items()
        if key not in ("checksum", "generated_at")
    }
    return schema_lite.sha256_canonical(payload)


def _validate(model):
    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, "estimation-model")
    except schema_lite.SchemaError as exc:
        raise ValueError("схема estimation-model не читается: %s" % exc)
    errors = schema_lite.validate(model, schema, "estimation-model")
    if errors:
        raise ValueError(
            "estimation-model не соответствует схеме: %s" % "; ".join(errors)
        )


# ---------------------------------------------------------------------------
# CLI-обвязка (`trr calibrate`)
# ---------------------------------------------------------------------------


def _emit(message, quiet=False):
    if not quiet:
        print(message)


def _emit_json(args, payload):
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _read_json(path):
    """Прочитать JSON. Возвращает `(payload, error)`; ровно одно из них None.

    Превышение лимита объёма — `LimitError` (не ловится здесь): CLI отдаёт по
    нему `MISSING_ARTIFACT` (4), а не «битый JSON» (5).
    """
    limits.check_size(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except OSError as exc:
        return None, "не читается: %s" % exc
    except ValueError as exc:
        return None, "невалидный JSON: %s" % exc


def _append_history(path, model, reason):
    """Дописать версию модели в `model-history.jsonl` (по строке на версию)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "version": model["version"],
            "generated_at": model["generated_at"],
            "checksum": model["checksum"],
            "reason": reason,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def _mark_trained(workdir, model, quiet, reason=None):
    """Отметить этап `trained` в state.json, если состояние существует.

    Вместе с checksum фиксируется `state.model = {version, checksum}`: версия
    модели нужна `doctor` (и человеку) без чтения артефакта, а её отсутствие —
    `[WARN]`, а не повод блокировать.

    `reason="enrich"` разрешает единственный откат цепочки
    (`checked|estimated|published → trained`): модель переобучена, страницу
    модели нужно перепубликовать. Для `train` причина не передаётся.
    """
    checksum = str(model["checksum"])
    version = int(model["version"])
    try:
        statemod.set_stage(
            str(workdir),
            "trained",
            reason="enrich" if reason == "enrich" else None,
            model_checksum=checksum,
            model={"version": version, "checksum": checksum},
        )
    except statemod.StateError as exc:
        _emit("[WARN] state: этап не обновлён — %s" % exc, quiet)


def _render_markdown(base, cfg, reference, stats, model, quiet):
    """Отрендерить три `.md`-зеркала: эталон, статистика, страница модели.

    Рендер — не пересчёт: числа берутся из уже записанных JSON. Ошибка рендера
    не отменяет модель (она уже валидна), поэтому это `[WARN]`, а не отказ.
    Страница модели получает ещё `sprint-sample.json` (даты и доска спринтов) и
    `state.json` (дата и URL публикации): без них эти поля были бы `NA`, хотя
    данные есть.
    """
    from trr_impl import report as reportmod

    templates_dir = str((cfg or {}).get("templates_dir") or "templates")
    template = Path(configmod.SKILL_ROOT) / templates_dir / "model-page.md"
    sample, _sample_error = _read_json(base / SAMPLE_RELATIVE)
    state, _state_error = _read_json(base / "state.json")
    try:
        reportmod.write(
            base / "norm",
            reportmod.render_reference_estimates(reference),
            "reference-estimates.md",
        )
        reportmod.write(
            base / "norm",
            reportmod.render_sprint_stats(stats),
            "sprint-stats.md",
        )
        reportmod.write(
            base / "model",
            reportmod.render_model_page(
                model,
                template if template.is_file() else None,
                reference=reference,
                stats=stats,
                sample=sample if isinstance(sample, dict) else None,
                cfg=cfg,
                state=state if isinstance(state, dict) else None,
            ),
            "estimation-model.md",
        )
    except (OSError, ValueError) as exc:
        _emit("[WARN] .md-зеркала не отрендерены — %s" % exc, quiet)
        return False
    return True


def run(workdir, args=None):
    """Выполнить `trr calibrate`: эталон + статистика → модель.

    `--reason train|enrich` (по умолчанию `train`) фиксируется в
    `model/model-history.jsonl`; при `enrich` этап переводится в `trained`
    с `reason="enrich"` (разрешённый откат после переобучения).
    """
    workdir = Path(workdir)
    quiet = bool(getattr(args, "quiet", False))
    reason = str(getattr(args, "reason", None) or "train")
    if reason not in ("train", "enrich"):
        _emit(
            "[MISSING] calibrate: --reason=%r неизвестен — допустимы train, enrich"
            % reason,
            quiet,
        )
        _emit_json(args, {"status": "blocked", "code": 5, "reason": reason})
        return 5
    base = workdir / statemod.STATE_DIR

    reference_path = base / REFERENCE_RELATIVE
    stats_path = base / STATS_RELATIVE

    if not reference_path.is_file():
        _emit(
            "[MISSING] %s — запустите /task-readiness-review train (эталон не вычитан)"
            % REFERENCE_RELATIVE,
            quiet,
        )
        _emit_json(args, {"status": "blocked", "code": 4, "artifact": REFERENCE_RELATIVE})
        return 4
    if not stats_path.is_file():
        _emit(
            "[MISSING] %s — запустите `scripts/trr stats`" % STATS_RELATIVE,
            quiet,
        )
        _emit_json(args, {"status": "blocked", "code": 4, "artifact": STATS_RELATIVE})
        return 4

    reference, error = _read_json(reference_path)
    if error:
        _emit("[MISSING] %s — %s" % (REFERENCE_RELATIVE, error), quiet)
        _emit_json(args, {"status": "blocked", "code": 5, "artifact": REFERENCE_RELATIVE})
        return 5
    stats, error = _read_json(stats_path)
    if error:
        _emit("[MISSING] %s — %s" % (STATS_RELATIVE, error), quiet)
        _emit_json(args, {"status": "blocked", "code": 5, "artifact": STATS_RELATIVE})
        return 5

    try:
        cfg = configmod.load_config(configmod.config_path(workdir))
    except configmod.ConfigError as exc:
        _emit("[MISSING] %s — %s" % (configmod.CONFIG_FILENAME, exc), quiet)
        _emit_json(args, {"status": "blocked", "code": 3, "config": None})
        return 3

    sample = None
    sample_path = base / SAMPLE_RELATIVE
    if sample_path.is_file():
        sample, _error = _read_json(sample_path)

    model_path = base / MODEL_RELATIVE
    previous = None
    if model_path.is_file():
        previous, _error = _read_json(model_path)
        if previous is not None and not isinstance(previous, dict):
            previous = None

    try:
        if previous is not None:
            candidate = build(
                reference,
                stats,
                cfg,
                sample=sample,
                version=_previous_version(previous),
            )
            if content_checksum(candidate) == content_checksum(previous):
                _emit(
                    "[OK] %s: входы не изменились, версия %d не переписана"
                    % (MODEL_RELATIVE, previous["version"]),
                    quiet,
                )
                _render_markdown(base, cfg, reference, stats, previous, quiet)
                _mark_trained(workdir, previous, quiet, reason)
                # Зеркало идемпотентно: повторная запись той же версии не
                # плодит дубли, поэтому пишем и в ветке «входы не изменились».
                storemod.save_model(workdir, cfg, previous, reference, stats)
                _emit_json(
                    args,
                    {
                        "status": "ok",
                        "code": 0,
                        "artifact": MODEL_RELATIVE,
                        "version": previous["version"],
                        "checksum": previous["checksum"],
                        "changed": False,
                    },
                )
                return 0
        model = build(reference, stats, cfg, previous=previous, sample=sample)
    except ValueError as exc:
        _emit("[MISSING] estimation-model — %s" % exc, quiet)
        _emit_json(args, {"status": "blocked", "code": 5, "artifact": MODEL_RELATIVE})
        return 5

    schema_lite.write_json(model_path, model)
    _append_history(base / MODEL_HISTORY_RELATIVE, model, reason)
    _render_markdown(base, cfg, reference, stats, model, quiet)
    _mark_trained(workdir, model, quiet, reason)
    # Зеркало: версия модели, её бакеты, правила штрафов, эталон и статистика
    # под тем же `model_checksum` — чтобы числа в БД и в файлах сходились.
    storemod.save_model(workdir, cfg, model, reference, stats)

    insufficient = [
        "%s/%s" % (bucket["role"], bucket["work_kind"])
        for bucket in model["buckets"]
        if bucket["confidence"] == "low"
    ]
    for label in insufficient:
        _emit("[WARN] bucket %s: confidence=low" % label, quiet)
    _emit(
        "[OK] %s: version %d, buckets=%d, sha256:%s"
        % (MODEL_RELATIVE, model["version"], len(model["buckets"]), model["checksum"]),
        quiet,
    )
    _emit_json(
        args,
        {
            "status": "ok",
            "code": 0,
            "artifact": MODEL_RELATIVE,
            "version": model["version"],
            "checksum": model["checksum"],
            "changed": True,
        },
    )
    return 0

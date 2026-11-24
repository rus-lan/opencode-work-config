#!/usr/bin/env python3
"""Эвристический вывод параметров `weight` / `heat` / `connectivity`.

Три параметра описывают задачу по трём осям, каждая — число `0.0 … 1.0`:

    weight        вес задачи: сложность и объём (тип, длина описания,
                  критерии приёмки, маркеры декомпозиции/рефакторинга,
                  число затронутых компонентов);
    heat          «теплота»: необходимость проработки (маркеры
                  неопределённости, research-метки, незаполненные секции,
                  открытые вопросы);
    connectivity  «связанность»: сложность и количество внешних интеграций
                  (issuelinks, integration-метки, упоминания внешних систем,
                  число компонентов).

Отдельных полей в Jira под них нет, поэтому значения **выводятся
эвристически** из снимка задачи (`context.json`) и всегда несут провенанс:
`source` (`heuristic` / `override` / `disabled`), `evidence[]` (короткие
строки «сигнал=значение → вклад») и `components{}` (взвешенный вклад каждого
сигнала). Ручной override — число `weight`/`heat`/`connectivity` в context
или в `context.params.<name>`; он приоритетнее эвристики.

Границы и коэффициенты берутся из `estimation.params` конфига (см.
`references/config.md`). Числа входят в формулу оценки как множитель:
`calibrate` считает его по профилю бакета (`params_profile`), `estimate` — по
снимку задачи относительно профиля бакета (`multiplier(..., baseline=…)`).

Модуль чистый: ни сети, ни файлов, ни глобального изменяемого состояния.
"""

import copy
import math
import re

from trr_impl import analysis as analysismod
from trr_impl import config as configmod

__all__ = [
    "PARAM_NAMES",
    "clamp01",
    "coverage",
    "derive",
    "evidence_lines",
    "multiplier",
    "settings",
]

PARAM_NAMES = ("weight", "heat", "connectivity")

# Веса сигналов внутри параметра. Сумма весов каждого параметра = 1.0:
# «все сигналы выражены максимально» → 1.0, «ни одного сигнала» → 0.0.
# Переопределяются плоской картой `estimation.params.signals` (имя сигнала →
# вес), имена сигналов глобально уникальны.
SIGNAL_WEIGHTS = {
    "weight": {
        "issue_type": 0.25,
        "description_len": 0.15,
        "acceptance_items": 0.12,
        "refactor_markers": 0.10,
        "components": 0.13,
        "analysis_numbers": 0.10,
        "analysis_scenarios": 0.10,
        "analysis_components": 0.05,
    },
    "heat": {
        "uncertainty": 0.28,
        "research_labels": 0.20,
        "missing_sections": 0.16,
        "open_questions": 0.16,
        "analysis_ambiguity": 0.12,
        "analysis_clarity_inverse": 0.08,
    },
    "connectivity": {
        "issuelinks": 0.24,
        "integration_labels": 0.20,
        "external_systems": 0.20,
        "linked_components": 0.16,
        "analysis_link_types": 0.12,
        "analysis_integrations": 0.08,
    },
}

# База сложности по типу задачи (сигнал `issue_type`, вес 0.35).
ISSUE_TYPE_BASE = {
    "feature": 0.60,
    "new feature": 0.60,
    "фича": 0.60,
    "tech debt": 0.55,
    "techdebt": 0.55,
    "техдолг": 0.55,
    "ошибка": 0.40,
    "bug": 0.40,
    "исследование": 0.65,
    "research": 0.65,
    "spike": 0.65,
    "adr": 0.30,
    "задача": 0.45,
    "task": 0.45,
}
ISSUE_TYPE_DEFAULT = 0.50

# Маркеры декомпозиции/рефакторинга (сигнал `refactor_markers`).
DECOMPOSITION_MARKERS = (
    "декомпозиц",
    "рефактор",
    "переписать",
    "миграц",
    "схема бд",
)

# Маркеры неопределённости (сигнал `uncertainty`).
UNCERTAINTY_MARKERS = (
    "неизвестн",
    "уточнит",
    "tbd",
    "подводные камни",
    "риск",
)

# Метки, означающие «нужна проработка» (сигнал `research_labels`).
RESEARCH_LABELS = frozenset(
    {"research", "spike", "исследование", "discovery", "discovery-task"}
)

# Обязательные секции описания для `heat`: отсутствие любой из групп —
# сигнал «задача не проработана». Алиасы — как ключи `context.sections`,
# так и человекочитаемые заголовки.
REQUIRED_SECTIONS = (
    ("acceptance", ("acceptance", "acceptance_criteria", "ac", "критерии приемки", "критерии приёмки")),
    ("scope", ("scope", "goal", "task", "цель", "задача")),
    ("dod", ("dod", "definition_of_done", "testing", "definition of done", "определение готовности")),
)

# Упоминания внешних систем (сигнал `external_systems`).
_EXTERNAL_RE = re.compile(
    r"https?://"
    r"|\bapi\b"
    r"|\bконтракт\w*"
    r"|\bинтеграц\w*"
    r"|\bgrpc\b"
    r"|\bkafka\b"
    r"|\bочеред\w*"
    r"|\bwebhook\w*"
    r"|\b[a-zа-яё][a-zа-яё0-9]+-[a-zа-яё][a-zа-яё0-9-]+\b",
    re.IGNORECASE,
)

# Пункт списка: `- `, `* `, `+ `, `1. `, `1) `, `- [ ] `.
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\[[ xX]\]\s+)\S", re.MULTILINE)

# Потолки нормализации: сигнал «насыщается» на этом значении.
_DESCRIPTION_LOG_CAP = 4000
_ACCEPTANCE_CAP = 8
_MARKER_CAP = 3
_COMPONENT_CAP = 5
_QUESTION_CAP = 5
_LINK_CAP = 5
_EXTERNAL_CAP = 5
_SIGNAL_CAP = 8
_SCENARIO_CAP = 3
_AMBIGUITY_CAP = 0.15
_LINK_TYPE_CAP = 3
_INTEGRATION_CAP = 2


# ---------------------------------------------------------------------------
# Служебное
# ---------------------------------------------------------------------------


def clamp01(x):
    """Зажать число в `[0.0, 1.0]`; NaN и мусор → 0.0."""
    try:
        value = float(x)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(value):
        return 0.0
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _number(value):
    """Число из JSON-значения; bool и нечисловой мусор → None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        return None if math.isnan(value) else value
    return None


def _ratio(count, cap):
    """Нормировать счётчик в `[0, 1]`: `count / cap` с зажимом."""
    if count <= 0:
        return 0.0
    return clamp01(float(count) / float(cap))


def _settings(cfg):
    """`estimation.params` конфига поверх дефолтов (без мутации входа)."""
    settings = copy.deepcopy(configmod.DEFAULTS["estimation"]["params"])
    params = None
    if isinstance(cfg, dict):
        estimation = cfg.get("estimation")
        if isinstance(estimation, dict):
            params = estimation.get("params")
    if isinstance(params, dict):
        for key in ("enabled", "clamp", "coefficients", "defaults", "signals"):
            if key not in params or params[key] is None:
                continue
            value = params[key]
            if isinstance(value, dict) and isinstance(settings.get(key), dict):
                merged = dict(settings[key])
                merged.update(value)
                settings[key] = merged
            else:
                settings[key] = value

    settings["enabled"] = bool(settings.get("enabled", True))

    clamp = settings.get("clamp")
    if not (
        isinstance(clamp, list)
        and len(clamp) == 2
        and _number(clamp[0]) is not None
        and _number(clamp[1]) is not None
    ):
        clamp = list(configmod.DEFAULTS["estimation"]["params"]["clamp"])
    low, high = _number(clamp[0]), _number(clamp[1])
    if low > high:
        low, high = high, low
    settings["clamp"] = [low, high]

    for group, fallback in (
        ("coefficients", configmod.DEFAULTS["estimation"]["params"]["coefficients"]),
        ("defaults", configmod.DEFAULTS["estimation"]["params"]["defaults"]),
    ):
        source = settings.get(group) if isinstance(settings.get(group), dict) else {}
        clean = {}
        for name in PARAM_NAMES:
            value = _number(source.get(name))
            clean[name] = float(fallback[name]) if value is None else value
        settings[group] = clean

    signals = settings.get("signals")
    clean_signals = {}
    if isinstance(signals, dict):
        for name, value in signals.items():
            number = _number(value)
            if number is not None and str(name).strip():
                clean_signals[str(name).strip()] = clamp01(number)
    settings["signals"] = clean_signals
    return settings


def _description(context):
    value = context.get("description")
    return value if isinstance(value, str) else ""


def _summary(context):
    value = context.get("summary")
    return value if isinstance(value, str) else ""


def _text(context):
    return (_summary(context) + "\n" + _description(context)).strip()


def _fields(context):
    fields = context.get("fields")
    return fields if isinstance(fields, dict) else {}


def _labels(context):
    """Метки задачи и признак «поле labels вообще присутствует»."""
    if "labels" not in context:
        return set(), False
    raw = context.get("labels")
    if isinstance(raw, str):
        items = raw.split(",")
    elif isinstance(raw, (list, tuple)):
        items = raw
    elif isinstance(raw, dict):
        items = list(raw.keys())
    else:
        return set(), True
    return {str(item).strip().casefold() for item in items if str(item).strip()}, True


def _component_count(context):
    """Число компонентов/сервисов и признак наличия поля."""
    for holder, key in ((context, "components"), (_fields(context), "components")):
        if not isinstance(holder, dict) or key not in holder:
            continue
        value = holder[key]
        if isinstance(value, bool):
            return 0, False
        if isinstance(value, int):
            return max(value, 0), True
        if isinstance(value, (list, tuple, dict)):
            return len(value), True
        if value is None:
            return 0, True
    return 0, False


def _link_count(context):
    """Число issuelinks и признак наличия поля (int — уже посчитанное число)."""
    for holder, key in (
        (_fields(context), "issuelinks"),
        (context, "issuelinks"),
        (context, "links"),
    ):
        if not isinstance(holder, dict) or key not in holder:
            continue
        value = holder[key]
        if isinstance(value, bool):
            return 0, False
        if isinstance(value, int):
            return max(value, 0), True
        if isinstance(value, (list, tuple, dict)):
            return len(value), True
        if value is None:
            return 0, True
    return 0, False


def _question_count(context, text):
    """Число открытых вопросов и признак наличия сигнала."""
    if "questions" in context:
        value = context.get("questions")
        if isinstance(value, bool):
            return 0, False
        if isinstance(value, int):
            return max(value, 0), True
        if isinstance(value, (list, tuple, dict)):
            return len(value), True
        if value is None:
            return 0, True
    count = text.count("?")
    return count, count > 0


def _section_filled(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    return True


def _sections(context):
    sections = context.get("sections")
    if not isinstance(sections, dict) or not sections:
        return None
    return {str(key).strip().casefold(): value for key, value in sections.items()}


def _count_markers(text, markers):
    lowered = text.casefold().replace("ё", "е")
    total = 0
    for marker in markers:
        total += lowered.count(marker)
    return total


def _acceptance_count(context):
    """Критерии приёмки: секция `acceptance`, иначе пункты списка в описании.

    Секция приоритетнее: если она заполнена, описание не пересчитывается —
    иначе одни и те же критерии считались бы дважды.
    """
    count = 0
    sections = _sections(context) or {}
    for key, value in sections.items():
        if key in ("acceptance", "acceptance_criteria", "ac", "критерии приемки", "критерии приёмки"):
            if isinstance(value, str):
                count += len(_LIST_ITEM_RE.findall(value)) or (1 if value.strip() else 0)
            elif isinstance(value, (list, tuple)):
                count += len(value)
            elif isinstance(value, dict):
                count += len(value)
    if count:
        return count
    return len(_LIST_ITEM_RE.findall(_description(context)))


# ---------------------------------------------------------------------------
# Сигналы: (components, evidence, present)
# ---------------------------------------------------------------------------


def _weight_signals(context, analysis=None):
    components, evidence, present = {}, [], 0
    analysis = analysis if isinstance(analysis, dict) else analysismod.analyze(context)
    issue_type = context.get("issue_type")
    if issue_type is None:
        issue_type = _fields(context).get("issue_type")
    issue_type = str(issue_type).strip() if issue_type is not None else ""
    if issue_type:
        base = ISSUE_TYPE_BASE.get(issue_type.casefold(), ISSUE_TYPE_DEFAULT)
        components["issue_type"] = base
        evidence.append("issue_type=%s → %.2f" % (issue_type, base))
        present += 1

    length = len(_description(context))
    if length > 0:
        value = clamp01(math.log1p(length) / math.log1p(_DESCRIPTION_LOG_CAP))
        components["description_len"] = value
        evidence.append("description_len=%d → %.2f" % (length, value))
        present += 1

    acceptance = _acceptance_count(context)
    sections = _sections(context)
    if acceptance > 0 or (sections is not None and any(
        key in ("acceptance", "acceptance_criteria", "ac", "критерии приемки", "критерии приёмки")
        for key in sections
    )):
        value = _ratio(acceptance, _ACCEPTANCE_CAP)
        components["acceptance_items"] = value
        evidence.append("acceptance_items=%d → %.2f" % (acceptance, value))
        present += 1

    markers = _count_markers(_text(context), DECOMPOSITION_MARKERS)
    if markers > 0:
        value = _ratio(markers, _MARKER_CAP)
        components["refactor_markers"] = value
        evidence.append("refactor_markers=%d → %.2f" % (markers, value))
        present += 1

    count, has_components = _component_count(context)
    if has_components:
        value = _ratio(count, _COMPONENT_CAP)
        components["components"] = value
        evidence.append("components=%d → %.2f" % (count, value))
        present += 1

    # Сигналы содержательного анализа (`analysis.analyze`): конкретика объёма,
    # число сценариев, число затронутых экранов/сервисов в тексте.
    numbers = int((analysis.get("signals") or {}).get("numbers") or 0)
    if numbers > 0:
        value = _ratio(numbers, _SIGNAL_CAP)
        components["analysis_numbers"] = value
        evidence.append("analysis_numbers=%d → %.2f" % (numbers, value))
        present += 1

    scenarios = int((analysis.get("scenarios") or {}).get("count") or 0)
    if scenarios > 0:
        value = _ratio(scenarios, _SCENARIO_CAP)
        components["analysis_scenarios"] = value
        evidence.append("analysis_scenarios=%d → %.2f" % (scenarios, value))
        present += 1

    mentioned = int((analysis.get("scope") or {}).get("components") or 0)
    if mentioned > 0:
        value = _ratio(mentioned, _COMPONENT_CAP)
        components["analysis_components"] = value
        evidence.append("analysis_components=%d → %.2f" % (mentioned, value))
        present += 1

    return components, evidence, present


def _heat_signals(context, analysis=None):
    components, evidence, present = {}, [], 0
    analysis = analysis if isinstance(analysis, dict) else analysismod.analyze(context)
    text = _text(context)

    markers = _count_markers(text, UNCERTAINTY_MARKERS)
    markers += text.count("?")
    if markers > 0:
        value = _ratio(markers, _MARKER_CAP)
        components["uncertainty"] = value
        evidence.append("uncertainty=%d → %.2f" % (markers, value))
        present += 1

    labels, has_labels = _labels(context)
    if has_labels:
        value = 1.0 if labels & RESEARCH_LABELS else 0.0
        components["research_labels"] = value
        evidence.append(
            "research_labels=%s → %.2f"
            % (",".join(sorted(labels & RESEARCH_LABELS)) or "нет", value)
        )
        present += 1

    sections = _sections(context)
    if sections is not None:
        missing = 0
        for _name, aliases in REQUIRED_SECTIONS:
            if not any(_section_filled(sections.get(alias)) for alias in aliases):
                missing += 1
        value = _ratio(missing, len(REQUIRED_SECTIONS))
        components["missing_sections"] = value
        evidence.append(
            "missing_sections=%d/%d → %.2f" % (missing, len(REQUIRED_SECTIONS), value)
        )
        present += 1

    count, has_questions = _question_count(context, text)
    if has_questions:
        value = _ratio(count, _QUESTION_CAP)
        components["open_questions"] = value
        evidence.append("open_questions=%d → %.2f" % (count, value))
        present += 1

    # Сигналы содержательного анализа: доля маркеров неопределённости (выше —
    # больше проработки) и обратная понятность (чем понятнее, тем меньше heat).
    ambiguity = analysis.get("ambiguity") or {}
    markers = int(ambiguity.get("markers") or 0)
    if markers > 0:
        ratio = float(ambiguity.get("ratio") or 0.0)
        value = clamp01(ratio / _AMBIGUITY_CAP)
        components["analysis_ambiguity"] = value
        evidence.append(
            "analysis_ambiguity=%d (%.3f) → %.2f" % (markers, ratio, value)
        )
        present += 1

    clarity = float((analysis.get("clarity") or {}).get("score") or 0.0)
    chars = int((analysis.get("signals") or {}).get("chars") or 0)
    if chars > 0:
        value = clamp01(1.0 - clarity)
        components["analysis_clarity_inverse"] = value
        evidence.append(
            "analysis_clarity=%.2f → inverse %.2f" % (clarity, value)
        )
        present += 1

    return components, evidence, present


def _integration_labels():
    """Набор integration-меток — тот же, что в `check._touches_integrations`."""
    try:
        from trr_impl import check as checkmod

        return frozenset(checkmod.INTEGRATION_LABELS)
    except Exception:  # noqa: BLE001 - диагностика не должна падать из-за импорта
        return frozenset(
            {
                "api",
                "contract",
                "contracts",
                "api-contract",
                "integration",
                "integrations",
                "integration-api",
            }
        )


def _connectivity_signals(context, analysis=None):
    components, evidence, present = {}, [], 0
    analysis = analysis if isinstance(analysis, dict) else analysismod.analyze(context)

    count, has_links = _link_count(context)
    if has_links:
        value = _ratio(count, _LINK_CAP)
        components["issuelinks"] = value
        evidence.append("issuelinks=%d → %.2f" % (count, value))
        present += 1

    labels, has_labels = _labels(context)
    if has_labels:
        matched = labels & _integration_labels()
        value = 1.0 if matched else 0.0
        components["integration_labels"] = value
        evidence.append(
            "integration_labels=%s → %.2f"
            % (",".join(sorted(matched)) or "нет", value)
        )
        present += 1

    text = _text(context)
    mentions = len(_EXTERNAL_RE.findall(text))
    if mentions > 0:
        value = _ratio(mentions, _EXTERNAL_CAP)
        components["external_systems"] = value
        evidence.append("external_mentions=%d → %.2f" % (mentions, value))
        present += 1

    count, has_components = _component_count(context)
    if has_components:
        value = _ratio(count, _COMPONENT_CAP)
        components["linked_components"] = value
        evidence.append("components=%d → %.2f" % (count, value))
        present += 1

    # Сигналы содержательного анализа: разные типы связей (blocks / relates /
    # depends) и упоминания интеграций — то, чего нет в счётчике issuelinks.
    dependencies = analysis.get("dependencies") or {}
    link_types = dependencies.get("link_types") or {}
    if isinstance(link_types, dict) and link_types:
        value = _ratio(len(link_types), _LINK_TYPE_CAP)
        components["analysis_link_types"] = value
        evidence.append(
            "analysis_link_types=%d (%s) → %.2f"
            % (len(link_types), ", ".join(sorted(link_types)), value)
        )
        present += 1

    integrations = int(dependencies.get("integrations") or 0)
    if integrations > 0:
        value = _ratio(integrations, _INTEGRATION_CAP)
        components["analysis_integrations"] = value
        evidence.append("analysis_integrations=%d → %.2f" % (integrations, value))
        present += 1

    return components, evidence, present


_HEURISTICS = {
    "weight": _weight_signals,
    "heat": _heat_signals,
    "connectivity": _connectivity_signals,
}


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------


def _override(context, name):
    """Ручной override параметра: `context.<name>` или `context.params.<name>`."""
    value = _number(context.get(name))
    if value is not None:
        return value
    params = context.get("params")
    if isinstance(params, dict):
        value = _number(params.get(name))
        if value is not None:
            return value
    return None


def derive(context, cfg=None):
    """Вывести три параметра из снимка задачи.

    Возвращает `{name: {value, source, evidence, components}, "applied":
    {enabled, clamp}}`. `source`: `heuristic` — из сигналов, `override` —
    ручное число в context, `disabled` — `estimation.params.enabled: false`.
    Отсутствующие поля context не падают: сигналов нет → значение равно
    `estimation.params.defaults`.

    Содержательный анализ (`analysis.analyze`) считается один раз на вызов и
    передаётся в эвристики: три параметра используют одни и те же метрики
    (числа, сценарии, неопределённость, типы связей), и повторный разбор текста
    ничего бы не изменил.
    """
    context = context if isinstance(context, dict) else {}
    settings = _settings(cfg)
    analysis = analysismod.analyze(context)
    result = {}

    for name in PARAM_NAMES:
        default_value = float(settings["defaults"][name])
        override = _override(context, name)
        if not settings["enabled"]:
            result[name] = {
                "value": round(default_value, 4),
                "source": "disabled",
                "evidence": ["params.enabled=false → default %.2f" % default_value],
                "components": {},
            }
            continue
        if override is not None:
            value = clamp01(override)
            result[name] = {
                "value": round(value, 4),
                "source": "override",
                "evidence": ["override %s=%.2f → %.2f" % (name, override, value)],
                "components": {},
            }
            continue

        components, evidence, present = _HEURISTICS[name](context, analysis)
        if present == 0:
            result[name] = {
                "value": round(default_value, 4),
                "source": "heuristic",
                "evidence": ["сигналов нет → default %.2f" % default_value],
                "components": {},
            }
            continue

        weights = dict(SIGNAL_WEIGHTS[name])
        weights.update(
            {
                key: value
                for key, value in settings["signals"].items()
                if key in weights
            }
        )
        weighted = {}
        total = 0.0
        for key in sorted(components):
            contribution = components[key] * weights[key]
            weighted[key] = round(contribution, 4)
            total += contribution
        result[name] = {
            "value": round(clamp01(total), 4),
            "source": "heuristic",
            "evidence": evidence,
            "components": weighted,
        }

    result["applied"] = {
        "enabled": bool(settings["enabled"]),
        "clamp": [float(settings["clamp"][0]), float(settings["clamp"][1])],
    }
    return result


def _param_value(params, name):
    entry = params.get(name) if isinstance(params, dict) else None
    if isinstance(entry, dict):
        value = _number(entry.get("value"))
        if value is not None:
            return value
    return None


def settings(cfg=None):
    """`estimation.params` конфига поверх дефолтов — публичное чтение настроек.

    Нужно вызывающему коду (калибровка модели, оценка), чтобы не дублировать
    разбор конфига и не лезть в приватный `_settings`.
    """
    return _settings(cfg)


def coverage(name, entry, cfg=None):
    """Доля веса сигналов параметра, реально присутствовавших в снимке.

    `entry` — результат `derive()` для одного параметра: его `components{}`
    содержит только сработавшие сигналы. Сумма весов этих сигналов и есть
    покрытие: `1.0` — снимок дал все сигналы параметра, `0.35` — только
    `issue_type`. По покрытию видно, можно ли верить профилю параметра: строка
    выборки спринта без описания и связей даёт мало.
    """
    if name not in PARAM_NAMES or not isinstance(entry, dict):
        return 0.0
    weights = dict(SIGNAL_WEIGHTS[name])
    weights.update(
        {
            key: value
            for key, value in _settings(cfg)["signals"].items()
            if key in weights
        }
    )
    components = entry.get("components") or {}
    return round(sum(weights.get(key, 0.0) for key in components), 4)


def multiplier(params, cfg=None, baseline=None):
    """Множитель к оценке: `clamp(1 + Σ coef*(param - baseline), lo, hi)`.

    `baseline` — точка, в которой множитель равен `1.0`: по умолчанию
    `estimation.params.defaults`, а при калибровке/оценке — профиль бакета
    (`params_profile`). База не заменяет дефолты: относительный сдвиг считается
    от неё, коэффициенты и границы берутся из конфига.
    """
    settings_block = _settings(cfg)
    base = dict(settings_block["defaults"])
    if isinstance(baseline, dict):
        for name in PARAM_NAMES:
            value = _number(baseline.get(name))
            if value is not None:
                base[name] = value
    raw = 1.0
    for name in PARAM_NAMES:
        value = _param_value(params, name)
        if value is None:
            value = float(settings_block["defaults"][name])
        raw += float(settings_block["coefficients"][name]) * (
            value - float(base[name])
        )
    low, high = settings_block["clamp"]
    return round(min(max(raw, low), high), 4)


def evidence_lines(params):
    """Человекочитаемый провенанс: заголовок параметра + строки сигналов."""
    lines = []
    for name in PARAM_NAMES:
        entry = params.get(name) if isinstance(params, dict) else None
        if not isinstance(entry, dict):
            continue
        value = _param_value(params, name)
        lines.append(
            "%s=%.2f (%s)" % (name, value if value is not None else 0.0, entry.get("source", "?"))
        )
        for item in entry.get("evidence") or []:
            lines.append("  · %s" % item)
    return lines

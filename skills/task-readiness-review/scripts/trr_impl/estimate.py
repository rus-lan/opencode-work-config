#!/usr/bin/env python3
"""Оценка задачи `.task-readiness/runs/<TASK>/<RUN-ID>/estimate.json`.

Вход — `validation.json` (§5.7) и модель `estimation-model.json` (§5.6), выход —
`estimate.json` (§5.9). Python считает числа, объяснения вариативности — словами
(PLAN.md §1, CONTRACT.md §6.3).

Правила:

- вид работ берётся из `context.work_kind` (решение агента, §5.4.1) или из
  `validation.work_kind`, если поле есть, иначе `implementation`; когда
  `work_kind` не задан, по каждой роли выбирается бакет с максимальным `n`
  (при равенстве — меньший `work_kind`, затем `issue_type`), то есть
  детерминированно;
- бакет выбирается по четырём уровням (`select_bucket`): точное совпадение
  `(role, issue_type, work_kind)` → `(role, work_kind)` с любым `issue_type` →
  `(role, *)` → бакет роли `OTHER` (и, если у `OTHER` нет подходящего, любой
  бакет модели). Уровень срабатывания попадает в `provenance` каждой роли; всё,
  что ниже первого уровня, — деградация: `confidence=low` и строка в
  `variability_reason[]` (и в `warnings`, если передан список);
- роль, которой нет в модели (например `DEVOPS`), не роняет оценку: числа
  берутся из бакета `OTHER`, роль в `roles[]` остаётся исходной, `confidence=low`,
  причина — в `variability_reason[]`; роль вне словаря скилла (например `TL`)
  оценивается по `OTHER` так же, вместо суммы по всем ролям модели;
- роль не указана в снимке (`role: null` или поля нет) — оценивается ОДНА
  доминирующая роль вида работ: бакет с максимальным `n` (`n` desc → `role`
  asc), `total = roles[0]`, `confidence=low`, причина в `variability_reason[]`,
  запись `field=role, source=estimate:role-assumed` в `provenance`, `[WARN]` в
  `warnings` и `role_assumed: true` в артефакте. Суммы по всем ролям модели
  больше нет: 29/76 SP не значат ничего для одной задачи;
- множитель параметров: `params.derive(context)` даёт `weight`/`heat`/
  `connectivity`, множитель считается относительно `params_profile` бакета
  (иначе `estimation.params.defaults`); `expected` и обе границы диапазона
  умножаются на него, затем округляются до шкалы;
- роли — те, что есть в модели; роль без данных не включается в `roles[]`, но
  попадает в `variability_reason[]` строкой «нет данных по роли <X>»;
- штраф: каждый REQUIRED-пробел, для которого нашлось правило `gap_rules`
  (связь id → `rule_id` задаёт `condition` правила, формат `"SA-08=FAIL"`,
  допускаются `"SA-08=FAIL|UNKNOWN"` и `"TPL-07!=PASS"`), сдвигает
  `expected` и верхнюю границу вверх по шкале; суммарно не более 2 шагов
  (CONTRACT.md §8), нижняя граница не двигается;
- каждый сдвиг фиксируется в `variability_reason[]` строкой
  `GR-01: нет критериев приёмки → +2 шага (3 → 8)`;
- сценарии — ровно три в порядке `base`, `optimistic`, `pessimistic` (§5.9):
  `base` = `expected` со штрафами, `optimistic` = нижняя граница диапазона без
  штрафов, `pessimistic` = верхняя граница со штрафами;
- **QA — отдельная запись `role=QA` и слагаемое `total`** (см. `_qa_entry`):
  роль задачи `QA` — второй записи нет (двойной счёт); `qa_estimation`
  заполнена — значение из Jira как есть (`source=jira`); иначе, если задача
  предполагает тестирование (`check.detect_has_testing`), QA считается моделью
  по QA-бакету (`source=derived`); иначе QA-работы нет. Штрафы `gap_rules` к
  QA-записи не применяются: REQUIRED-пробел уже сдвинул оценку исполнителя, и
  повторять тот же сдвиг в QA — двойной счёт;
- `total` = сумма по ролям (включая QA); `total.qa` — QA-составляющая
  (`expected`/`source`/`bucket`); `blocked_by_gaps` — id всех REQUIRED-пробелов;
- **надбавка за дополнительные ресурсы (правило `RS-01`, см. `_apply_resources`)**:
  allure для тест-кейсов, e2e-сервис автотестирования для автотестов — за каждый
  распознанный ресурс `estimation.resources.sp_per_resource` SP (по умолчанию 1)
  к записи **основного исполнителя** либо (`mode: upper_bound`) оценка по верхней
  границе уже посчитанного диапазона. Надбавка применяется **после** QA-записи и
  **никогда** к записи `source=derived`: это производное число модели, и надбавка
  к нему была бы двойным счётом (ресурс уже двигает оценку исполнителя, а
  QA-составляющая считается от того же объёма). `mode: add` не сужает границы:
  `range = [min(low, expected), max(high, nearest_scale(high + bonus))]`. Блок
  `resources` появляется в `estimate.json`, только когда ресурсы найдены; причина
  — строкой `RS-01: …` в `variability_reason[]`, запись `{"kind":"rule",
  "ref":"RS-01","value":"+N SP за ресурсы: …"}` — в `provenance` роли.

`estimated_at` — единственное недетерминированное поле; при
`TASK_READINESS_FIXED_TIME=1` подставляется `1970-01-01T00:00:00Z`.
"""

import copy
import json
import re
from pathlib import Path

from trr_impl import calibrate as calmod
from trr_impl import check as checkmod
from trr_impl import config as configmod
from trr_impl import limits
from trr_impl import params as paramsmod
from trr_impl import resources as resourcesmod
from trr_impl import schema_lite
from trr_impl import state as statemod
from trr_impl import store as storemod
from trr_impl import vectors as vectorsmod
from trr_impl.paths import MODEL_RELATIVE as _MODEL_RELATIVE
from trr_impl.stats import QA_WORK_KIND, ROLES, WORK_KINDS, now_utc

__all__ = [
    "BUCKET_LEVELS",
    "MAX_PENALTY_STEPS",
    "QA_SHARE_FALLBACK",
    "RULE_DESCRIPTIONS",
    "estimate",
    "run",
    "select_bucket",
    "shift",
]

MAX_PENALTY_STEPS = 2

# Правило надбавки за дополнительные ресурсы (allure, e2e, …): +1 SP за ресурс
# либо верхняя граница диапазона. Описание — references/estimation-model.md §9.6.
RESOURCES_RULE_ID = "RS-01"

# Роль QA: отдельная запись `roles[]` и слагаемое `total` (см. `_qa_entry`).
QA_ROLE = "QA"

# Доля QA от dev-оценки — четвёртый (крайний) уровень деградации QA-записи:
# в модели нет ни одного бакета роли `QA`. Ориентир «QA ≈ четверть работы
# разработки»; применяется только тогда, когда бакета нет вовсе, и помечается
# `confidence=low` + строкой в `warnings`.
QA_SHARE_FALLBACK = 0.25

# Уровни выбора бакета — от точного к самому грубому. Порядок нормативный:
# он определяет и числа оценки, и `buckets.reachable` в полигоне.
BUCKET_LEVEL_EXACT = "exact"
BUCKET_LEVEL_WORK_KIND = "work_kind"
BUCKET_LEVEL_ROLE = "role"
BUCKET_LEVEL_OTHER_ROLE = "other_role"
BUCKET_LEVEL_ANY = "any"

# Человекочитаемые имена уровней — для `provenance` и `variability_reason[]`.
BUCKET_LEVELS = {
    BUCKET_LEVEL_EXACT: "(role, issue_type, work_kind)",
    BUCKET_LEVEL_WORK_KIND: "(role, work_kind) при любом issue_type",
    BUCKET_LEVEL_ROLE: "(role, *) — любой issue_type и work_kind",
    BUCKET_LEVEL_OTHER_ROLE: "бакет роли OTHER",
    BUCKET_LEVEL_ANY: "любой бакет модели",
}

# Человекочитаемое имя штрафа — часть строки `variability_reason[]`.
RULE_DESCRIPTIONS = {
    "GR-01": "нет критериев приёмки",
    "GR-02": "нет контракта API",
    "GR-03": "не заполнена Роль",
    "GR-04": "нет оценки QA",
}

# `gap_rules[].condition` — единственный источник связи «пробел проверки →
# правило штрафа» (CONTRACT.md §5.6): `"<CHECK-ID>=<STATUS>"`, допустимы
# несколько статусов через `|` (`"SA-08=FAIL|UNKNOWN"`) и отрицание
# (`"TPL-07!=PASS"`). Отдельной таблицы id → rule_id нет: правка условия в
# модели меняет штраф без правки кода.
_CONDITION_RE = re.compile(
    r"^\s*(?P<check>[A-Za-z0-9_.-]+)\s*(?P<operator>!=|=)\s*(?P<statuses>.+?)\s*$"
)

_ESTIMATE_FILE = "estimate.json"
_VALIDATION_FILE = "validation.json"
_CONTEXT_FILE = "context.json"
_RUNS_RELATIVE = "runs"


# ---------------------------------------------------------------------------
# Шкала
# ---------------------------------------------------------------------------


def _scale(model):
    scale = model.get("scale")
    if (
        not isinstance(scale, list)
        or not scale
        or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in scale
        )
        or any(scale[index] >= scale[index + 1] for index in range(len(scale) - 1))
    ):
        raise ValueError(
            "estimation-model.scale: нужен строго возрастающий список целых, получено %r"
            % (scale,)
        )
    return list(scale)


def shift(points, steps, scale):
    """Сдвинуть значение вверх по шкале на `steps` шагов (с зажимом в максимум)."""
    if points not in scale:
        raise ValueError("%r не входит в шкалу %r" % (points, scale))
    index = scale.index(points) + int(steps)
    if index >= len(scale):
        index = len(scale) - 1
    return scale[index]


def _steps_word(steps):
    return "+%d шаг" % steps if steps == 1 else "+%d шага" % steps


# ---------------------------------------------------------------------------
# Выбор бакета
# ---------------------------------------------------------------------------


def _pick_bucket(candidates):
    """Самый крупный бакет из списка; при равенстве — детерминированно.

    `n` desc → `work_kind` asc → `issue_type` asc: одинаковый вход всегда даёт
    один и тот же бакет, даже если модель пересобрана с другим порядком строк.
    """
    if not candidates:
        return None
    ordered = sorted(
        candidates,
        key=lambda bucket: (
            -int(bucket.get("n", 0) or 0),
            str(bucket.get("work_kind", "")),
            str(bucket.get("issue_type", "")),
        ),
    )
    return ordered[0]


def select_bucket(buckets, role, work_kind, explicit, issue_type=None):
    """Выбрать бакет роли по четырём уровням. Возвращает `(bucket, level)`.

    Порядок уровней — часть контракта (references/estimation-model.md):

    1. `exact` — точное `(role, issue_type, work_kind)`;
    2. `work_kind` — `(role, work_kind)` при любом `issue_type` (самый крупный);
    3. `role` — `(role, *)`: у роли нет бакета этого вида работ;
    4. `other_role` — бакет роли `OTHER` по тем же уровням 1–3 (деградация роли).

    `explicit=False` (вид работ не задан) сразу начинает с уровня 3: угадывать
    `work_kind` нельзя, поэтому берётся самый крупный бакет роли — прежнее
    поведение сохранено. `work_kind="unknown"` не поднимается до уровня 3:
    CONTRACT.md §5.4.1 требует базу из `implementation`, это делает вызывающий.

    `(None, None)` — у роли нет ни одного бакета; решение о дальнейшей
    деградации (до `OTHER` или любого бакета модели) принимает `estimate`.
    """
    role = str(role)
    issue_type = str(issue_type) if issue_type is not None else None

    if explicit:
        if issue_type:
            bucket = _pick_bucket(
                [
                    item
                    for item in buckets
                    if str(item.get("role")) == role
                    and str(item.get("issue_type")) == issue_type
                    and str(item.get("work_kind")) == work_kind
                ]
            )
            if bucket is not None:
                return bucket, BUCKET_LEVEL_EXACT
        bucket = _pick_bucket(
            [
                item
                for item in buckets
                if str(item.get("role")) == role
                and str(item.get("work_kind")) == work_kind
            ]
        )
        if bucket is not None:
            return bucket, BUCKET_LEVEL_WORK_KIND
        if work_kind == "unknown":
            # Вид работ не определён: база берётся из `implementation` в
            # `estimate` (confidence=low), а не из случайного бакета роли.
            return None, None

    bucket = _pick_bucket(
        [item for item in buckets if str(item.get("role")) == role]
    )
    if bucket is not None:
        return bucket, BUCKET_LEVEL_ROLE
    return None, None


def _bucket_empty(bucket):
    """Бакет без данных: его нет или в нём `n = 0`."""
    if bucket is None:
        return True
    try:
        return int(bucket.get("n", 0) or 0) <= 0
    except (TypeError, ValueError):
        return True


def _baseline_for(bucket, default_baseline):
    """Baseline параметров роли: профиль бакета, иначе дефолты конфига.

    Модель калибрована на своём профиле: задача двигает оценку относительно
    него, а не относительно «нуля». Возвращает `(baseline, источник)`.
    """
    profile = bucket.get("params_profile") if isinstance(bucket, dict) else None
    if isinstance(profile, dict) and all(
        isinstance(profile.get(name), (int, float))
        and not isinstance(profile.get(name), bool)
        for name in paramsmod.PARAM_NAMES
    ):
        return {name: float(profile[name]) for name in paramsmod.PARAM_NAMES}, "bucket"
    return dict(default_baseline), "defaults"


def _min_sample_n(cfg):
    """`validation.min_sample_n` из конфига; битое значение — дефолт 5."""
    value = ((cfg or {}).get("validation") or {}).get("min_sample_n", 5)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return 5
    return value


def _qa_required_types(cfg):
    """`validation.qa_required_issue_types` из конфига; None — дефолт скилла.

    `None` возвращается и когда ключа нет, и когда значение битое (не список):
    тогда `check.detect_has_testing` берёт `QA_REQUIRED_ISSUE_TYPES`.
    """
    value = ((cfg or {}).get("validation") or {}).get("qa_required_issue_types")
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return None


def _qa_scope_text(context, selected, issue_type, qa_required_issue_types):
    """Строка `qa_scope` для estimate.json: почему QA-записи нет.

    Только для случая «тип задачи не требует QA-оценки»: исполнитель выполняет
    полный объём, включая проверку результата. `None` — объяснять нечего (QA —
    оцениваемая роль, нет типа задачи или роли исполнителя, тип требует QA, но
    записи почему-то нет).
    """
    if QA_ROLE in selected or not issue_type:
        return None
    required = checkmod.qa_required_types(qa_required_issue_types)
    if str(issue_type).strip().casefold() in required:
        return None
    role = str((context or {}).get("role") or "").strip()
    if not role:
        return None
    return (
        "не требуется (тип «%s») — проверка результата входит в объём роли %s"
        % (issue_type, role)
    )


def _bucket_label(bucket):
    """Идентификатор бакета `role/issue_type/work_kind` — для provenance и отчёта."""
    return "%s/%s/%s" % (
        bucket.get("role"),
        bucket.get("issue_type"),
        bucket.get("work_kind"),
    )


def _qa_points(value, scale):
    """Значение `qa_estimation` в шкале SP; None — если поле не число.

    Jira отдаёт число; строку `"2"`/`"2,5"` тоже принимаем (люди заполняют
    поле руками). `0`, отрицательное и нечисловое — «не заполнено».
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    else:
        return None
    if number <= 0:
        return None
    points = int(calmod.nearest_scale(number, scale))
    return max(int(scale[0]), points)


def _select_qa_bucket(buckets, work_kind, explicit, issue_type):
    """Бакет QA: `testing` → `implementation` → любой QA. `(bucket, level)`.

    QA-бакеты статистики строятся только для вида работ `testing`
    (`stats.QA_WORK_KIND`). Если такого нет — берётся `implementation`
    (второй уровень), затем любой QA-бакет модели (третий). `(None, None)` —
    в модели нет ни одного QA-бакета.
    """
    bucket, level = select_bucket(
        buckets, "QA", QA_WORK_KIND, explicit, issue_type=issue_type
    )
    if not _bucket_empty(bucket):
        return bucket, level
    bucket, _level = select_bucket(
        buckets, "QA", "implementation", True, issue_type=issue_type
    )
    if not _bucket_empty(bucket):
        return bucket, BUCKET_LEVEL_ROLE
    candidate = _pick_bucket(
        [item for item in buckets if str(item.get("role")) == "QA"]
    )
    if not _bucket_empty(candidate):
        return candidate, BUCKET_LEVEL_ANY
    return None, None


def _qa_entry(
    selected,
    context,
    buckets,
    work_kind,
    explicit,
    issue_type,
    scale,
    params_result,
    cfg,
    default_baseline,
    entries,
    model_version,
    warnings,
    qa_required_issue_types=None,
):
    """QA-составляющая оценки: запись `role=QA` или None.

    Порядок ветвей — первое совпадение выигрывает:

    1. `QA` уже среди оцениваемых ролей (`context.role = QA`) — второй записи
       нет: двойной счёт запрещён, QA-оценка уже посчитана основным циклом;
    2. `qa_estimation` заполнена — значение из Jira как есть (`source=jira`),
       без пересчёта и без штрафов: это факт из задачи, а не вывод модели;
    3. тип задачи входит в `qa_required_issue_types`
       (`validation.qa_required_issue_types` конфига; по умолчанию —
       Feature/Ошибка) — QA считается моделью по QA-бакету (`source=derived`),
       множитель параметров — тот же, что у основной роли, но baseline —
       профиль QA-бакета;
    4. иначе QA-работы нет — записи нет (`has_testing = false`): исполнитель
       выполняет полный объём, включая проверку результата.

    Штрафы `gap_rules` к QA не применяются: REQUIRED-пробел уже сдвинул оценку
    роли-исполнителя, повторять сдвиг в QA — двойной счёт.
    """
    if QA_ROLE in selected:
        return None

    context = context or {}
    value = checkmod.qa_estimation_value(context)
    points = _qa_points(value, scale)
    if points is not None:
        detail = "QA Estimation из Jira = %s SP, без пересчёта" % _fmt(value)
        if warnings is not None:
            warnings.append(
                "[INFO] QA: поле QA Estimation заполнено (%s) → %d SP из Jira"
                % (_fmt(value), points)
            )
        return {
            "role": QA_ROLE,
            "expected": points,
            "range": [points, points],
            "scenarios": [
                {
                    "name": "base",
                    "points": points,
                    "reason": "QA Estimation из Jira: %s SP" % _fmt(value),
                },
                {
                    "name": "optimistic",
                    "points": points,
                    "reason": "QA Estimation из Jira — точное значение, без диапазона",
                },
                {
                    "name": "pessimistic",
                    "points": points,
                    "reason": "QA Estimation из Jira — точное значение, без диапазона",
                },
            ],
            "confidence": "high",
            "source": "jira",
            "provenance": [
                {
                    "field": "qa_estimation",
                    "kind": "reference",
                    "source": "estimate:qa-jira",
                    "detail": "поле QA Estimation = %s → %d SP, значение взято как есть"
                    % (_fmt(value), points),
                },
                {
                    "field": "expected",
                    "kind": "rule",
                    "source": "estimate:qa-jira",
                    "detail": "expected=%d, range=[%d, %d], без params и без gap_rules"
                    % (points, points, points),
                },
            ],
        }

    has_testing, testing_reason = checkmod.detect_has_testing(
        context, qa_required_issue_types
    )
    if not has_testing:
        return None

    bucket, level = _select_qa_bucket(buckets, work_kind, explicit, issue_type)
    min_n = _min_sample_n(cfg)
    params_baseline, baseline_source = _baseline_for(bucket, default_baseline)
    multiplier = paramsmod.multiplier(params_result, cfg, baseline=params_baseline)

    if bucket is None:
        # Крайний случай: в модели нет ни одного QA-бакета. Доля от dev-оценки,
        # confidence=low — число честно помечено как производное.
        dev_total = sum(int(entry["expected"]) for entry in entries)
        points = max(
            int(scale[0]),
            int(calmod.nearest_scale(dev_total * QA_SHARE_FALLBACK, scale)),
        )
        detail = (
            "QA-бакета в модели нет → взято %d%% от dev-оценки (%d SP): %d SP"
            % (int(QA_SHARE_FALLBACK * 100), dev_total, points)
        )
        if warnings is not None:
            warnings.append(
                "[INFO] QA: поле пустое, QA-бакета в модели нет → рассчитано "
                "моделью: %d SP (%d%% от dev)" % (points, int(QA_SHARE_FALLBACK * 100))
            )
        return {
            "role": QA_ROLE,
            "expected": points,
            "range": [int(scale[0]), points],
            "scenarios": [
                {
                    "name": "base",
                    "points": points,
                    "reason": detail,
                },
                {
                    "name": "optimistic",
                    "points": int(scale[0]),
                    "reason": "нижняя граница шкалы: QA-бакета нет, доля от dev",
                },
                {
                    "name": "pessimistic",
                    "points": points,
                    "reason": "верхняя граница совпадает с оценкой: QA-бакета нет",
                },
            ],
            "confidence": "low",
            "source": "derived",
            "provenance": [
                {
                    "field": "qa_estimation",
                    "kind": "rule",
                    "source": "estimate:qa-derived",
                    "detail": detail,
                }
            ],
        }

    label = _bucket_label(bucket)
    base_expected = int(bucket["expected"])
    expected = max(
        int(scale[0]),
        int(calmod.nearest_scale(base_expected * multiplier, scale)),
    )
    lower = int(calmod.nearest_scale_down(int(bucket["range"][0]) * multiplier, scale))
    upper = int(calmod.nearest_scale_up(int(bucket["range"][1]) * multiplier, scale))
    lower = max(int(scale[0]), min(lower, expected))
    upper = max(upper, expected)

    n = int(bucket.get("n", 0) or 0)
    reference = str(bucket.get("reference") or "none")
    if level in (BUCKET_LEVEL_EXACT, BUCKET_LEVEL_WORK_KIND) and (
        reference == "yes" and n >= min_n
    ):
        confidence = "high"
    else:
        confidence = "medium"

    detail = (
        "поле QA Estimation пустое → рассчитано моделью: бакет %s (n=%d, "
        "reference=%s), params ×%s относительно baseline (%s)"
        % (label, n, reference, _fmt(multiplier), baseline_source)
    )
    if warnings is not None:
        warnings.append(
            "[INFO] QA: поле пустое → рассчитано моделью: %d SP (бакет %s, "
            "n=%d, reference=%s)" % (expected, label, n, reference)
        )

    return {
        "role": QA_ROLE,
        "expected": expected,
        "range": [lower, upper],
        "scenarios": [
            {
                "name": "base",
                "points": expected,
                "reason": "expected=%d (base %d × factor %s × params %s), QA без gap_penalty"
                % (
                    expected,
                    int(bucket["base"]),
                    _fmt(bucket["factor"]),
                    _fmt(multiplier),
                ),
            },
            {
                "name": "optimistic",
                "points": lower,
                "reason": "нижняя граница диапазона QA-бакета: %d" % lower,
            },
            {
                "name": "pessimistic",
                "points": upper,
                "reason": "верхняя граница диапазона QA-бакета: %d" % upper,
            },
        ],
        "confidence": confidence,
        "source": "derived",
        "qa_bucket": label,
        "provenance": [
            {
                "field": "expected",
                "kind": "model",
                "source": "estimation-model:%d:%s" % (model_version, label),
                "detail": "expected=%d, range=[%d, %d], QA по бакету %s (base=%d, "
                "n=%d, reference=%s)" % (
                    expected,
                    lower,
                    upper,
                    label,
                    int(bucket["base"]),
                    n,
                    reference,
                ),
            },
            {
                "field": "qa_estimation",
                "kind": "rule",
                "source": "estimate:qa-derived",
                "detail": detail,
            },
            {
                "field": "bucket",
                "kind": "rule",
                "source": "estimate:bucket-select",
                "detail": "уровень выбора: %s — %s; бакет %s; QA-работы (%s)"
                % (
                    level,
                    BUCKET_LEVELS.get(level, level),
                    label,
                    testing_reason,
                ),
            },
            {
                "field": "params_multiplier",
                "kind": "rule",
                "source": "estimate:params",
                "detail": (
                    "params ×%s относительно baseline (%s: weight=%s, heat=%s, "
                    "connectivity=%s)"
                    % (
                        _fmt(multiplier),
                        baseline_source,
                        _fmt(params_baseline["weight"]),
                        _fmt(params_baseline["heat"]),
                        _fmt(params_baseline["connectivity"]),
                    )
                ),
            },
        ],
    }


def _condition_matches(condition, check_id, status):
    """Совпадает ли `gap_rules[].condition` с пробелом `check_id`/`status`.

    Поддерживаются формы `"SA-08=FAIL"`, `"SA-08=FAIL|UNKNOWN"` и
    `"TPL-07!=PASS"`. Неизвестный/битый формат условия просто не даёт штрафа.
    """
    match = _CONDITION_RE.match(str(condition or ""))
    if match is None:
        return False
    if match.group("check") != str(check_id):
        return False
    allowed = [item.strip() for item in match.group("statuses").split("|") if item.strip()]
    if not allowed:
        return False
    matched = str(status) in allowed
    return matched if match.group("operator") == "=" else not matched


def _gap_statuses(validation):
    """Статусы проверок: `id → status` из `validation.checks`."""
    statuses = {}
    for check in validation.get("checks") or []:
        if isinstance(check, dict) and check.get("id") is not None:
            statuses[str(check["id"])] = str(check.get("status"))
    return statuses


def _penalties(validation, model, role):
    """Штрафы роли: список `(rule_id, steps)` и сумма шагов (не больше 2).

    Правило применяется, если `condition` правила ссылается на id пробела и
    его статус подходит. Пробел без статуса (ручной `gaps[]`) считается
    `FAIL`: в `validation.json` в `gaps` попадают только FAIL/UNKNOWN.
    """
    rules = sorted(
        (
            rule
            for rule in (model.get("gap_rules") or [])
            if isinstance(rule, dict)
        ),
        key=lambda rule: str(rule.get("rule_id")),
    )
    statuses = _gap_statuses(validation)
    gaps = [
        gap
        for gap in (validation.get("gaps") or [])
        if isinstance(gap, dict) and gap.get("severity") == "REQUIRED"
    ]
    gaps.sort(key=lambda gap: str(gap.get("id", "")))

    applied = []
    total = 0
    for gap in gaps:
        if total >= MAX_PENALTY_STEPS:
            break
        gap_id = str(gap.get("id", ""))
        status = str(gap.get("status") or statuses.get(gap_id) or "FAIL")
        for rule in rules:
            if not _condition_matches(rule.get("condition"), gap_id, status):
                continue
            if role not in (rule.get("applies_to") or []):
                continue
            steps = int(rule.get("penalty_steps", 0) or 0)
            if steps <= 0:
                continue
            steps = min(steps, MAX_PENALTY_STEPS - total)
            applied.append((str(rule.get("rule_id")), steps))
            total += steps
            break
    return applied, total


# ---------------------------------------------------------------------------
# Векторы текстов (этап A): справочные соседи, без автокоррекции по умолчанию
# ---------------------------------------------------------------------------


def _vector_text(context):
    """Текст запроса из снимка задачи: заголовок + описание (как в task-texts)."""
    if not isinstance(context, dict):
        return ""
    summary = str(context.get("summary") or "").strip()
    text = str(context.get("description") or "").strip()
    if not text:
        sections = context.get("sections")
        if isinstance(sections, dict):
            text = " ".join(
                str(value).strip()
                for _key, value in sorted(sections.items())
                if str(value or "").strip()
            )
    return ("%s %s" % (summary, text)).strip()


def _vector_bucket(context, entries):
    """Бакет запроса `(role, work_kind)`: из снимка, иначе роль исполнителя.

    Роль берётся из снимка; если её там нет — из первой записи, которая **не**
    производная QA (`role=QA` / `source=derived`). Раньше роль выводилась только
    при `len(entries) == 1`, поэтому при наличии QA-записи роль оставалась
    `None`, все соседи получали `same_bucket=false`, и `adjust_range` не
    срабатывал никогда. Когда кроме QA-записи ничего нет, берётся она: другого
    кандидата на роль нет.
    """
    role = context.get("role") if isinstance(context, dict) else None
    work_kind = context.get("work_kind") if isinstance(context, dict) else None
    if role not in ROLES:
        role = None
        for entry in entries:
            candidate = entry.get("role")
            if candidate in ROLES and entry.get("source") != "derived" and candidate != QA_ROLE:
                role = candidate
                break
        if role is None and len(entries) == 1:
            fallback = entries[0].get("role")
            role = fallback if fallback in ROLES else None
    return role, work_kind


def _apply_vectors(
    entries, task_key, context, vector_model, vector_config, scale, reasons, warnings=None
):
    """Добавить `similar_tasks` и (только при `adjust_range: true`) правку диапазона.

    Пороги не задаются числом: `similar_threshold` берётся из калибровки
    артефакта (p90 межбакетных косинусов). `adjust_range: false` — числа
    `expected`/`range`/`confidence` не меняются: векторы остаются справкой.
    Если `adjust_range: true`, а калибровки в артефакте нет, правка не делается
    вовсе (fail-safe): без порога любое соседство расширяло бы диапазон, то есть
    подменяло бы оценку. Причина уходит в `warnings` (`[WARN] vectors: …`).
    Возвращает список соседей или None, если механизм выключен/неприменим.
    """
    if not isinstance(vector_config, dict) or not vector_config.get("enabled"):
        return None
    if not isinstance(vector_model, dict):
        return None

    calibration = vector_model.get("calibration") or {}
    vectors = [item for item in vector_model.get("vectors") or [] if isinstance(item, dict)]
    corpus_rows = int(calibration.get("corpus_rows") or len(vectors))
    try:
        min_corpus = int(vector_config.get("min_corpus", configmod.VECTOR_MIN_CORPUS))
    except (TypeError, ValueError):
        min_corpus = configmod.VECTOR_MIN_CORPUS
    if corpus_rows < min_corpus:
        return None

    text = _vector_text(context)
    if not text:
        return None

    query = vectorsmod.query_vector(text, vector_model)
    role, work_kind = _vector_bucket(context, entries)
    query["key"] = task_key
    query["role"] = role
    query["work_kind"] = work_kind

    try:
        top_k = int(vector_config.get("top_k") or 5)
    except (TypeError, ValueError):
        top_k = 5
    neighbors = vectorsmod.similar(vectors, query, top_k=top_k)
    if not neighbors:
        return []

    threshold = calibration.get("similar_threshold")
    threshold = (
        float(threshold)
        if isinstance(threshold, (int, float)) and not isinstance(threshold, bool)
        else None
    )
    source = "task-vectors:%s" % (vector_model.get("built_at") or "unknown")

    for entry in entries:
        entry.setdefault("provenance", []).append(
            {
                "field": "similar_tasks",
                "kind": "vector_nn",
                "source": source,
                "detail": "top-%d: %s"
                % (
                    len(neighbors),
                    ", ".join(
                        "%s@%.4f" % (item.get("key"), item.get("cosine"))
                        for item in neighbors
                    ),
                ),
            }
        )

    if not vector_config.get("adjust_range"):
        return neighbors

    if threshold is None:
        message = (
            "[WARN] vectors: в артефакте нет calibration.similar_threshold — "
            "adjust_range пропущен"
        )
        if warnings is not None:
            warnings.append(message)
        return neighbors

    scale_values = [int(item) for item in scale]
    for entry in entries:
        candidates = [
            item
            for item in neighbors
            if item.get("same_bucket")
            and item.get("role") == entry.get("role")
            and isinstance(item.get("sp"), (int, float))
            and not isinstance(item.get("sp"), bool)
            and item.get("cosine") >= threshold
        ]
        if not candidates:
            continue
        points = sorted({int(item["sp"]) for item in candidates if int(item["sp"]) in scale_values})
        if not points:
            continue
        low, high = entry.get("range") or [entry["expected"], entry["expected"]]
        new_low = min(int(low), points[0])
        new_high = max(int(high), points[-1])
        if new_low == int(low) and new_high == int(high):
            continue
        entry["range"] = [new_low, new_high]
        # Диапазон расширен по соседям — уверенность не может остаться высокой:
        # это этап B, где векторы реально влияют на интервал.
        entry["confidence"] = "low"
        reasons.append(
            "vector_nn: %d похожих задач в бакете %s/%s (cosine >= %s), "
            "диапазон расширен до [%d, %d]"
            % (
                len(candidates),
                entry.get("role"),
                work_kind or "unknown",
                threshold,
                new_low,
                new_high,
            )
        )

    return neighbors


# ---------------------------------------------------------------------------
# Оценка
# ---------------------------------------------------------------------------


def _resources_config(cfg):
    """Блок `estimation.resources` конфига (None — действуют дефолты модуля)."""
    estimation = (cfg or {}).get("estimation") if isinstance(cfg, dict) else None
    if not isinstance(estimation, dict):
        return None
    block = estimation.get("resources")
    return block if isinstance(block, dict) else None


def _resources_signature(enabled, sp_per_resource, mode, items):
    """Сравнимая подпись настроек `RS-01`: флаг, надбавка, режим, каталог.

    Каталог нормализуется так же, как его хранит модель (`calibrate` пишет
    алиасы из `resources_settings`, то есть strip + casefold) — иначе сравнение
    «модель vs конфиг» давало бы ложное расхождение на регистре.
    """
    normalized = {}
    if isinstance(items, dict):
        for name, aliases in items.items():
            values = aliases if isinstance(aliases, (list, tuple)) else [aliases]
            cleaned = sorted(
                str(alias).strip().casefold()
                for alias in values
                if str(alias).strip()
            )
            normalized[str(name).strip()] = tuple(cleaned)
    try:
        bonus = float(sp_per_resource)
    except (TypeError, ValueError):
        bonus = None
    return (bool(enabled), bonus, str(mode), tuple(sorted(normalized.items())))


def _resources_drift(model, cfg, warnings=None):
    """`[WARN]`, если настройки `RS-01` в модели разошлись с живым конфигом.

    `calibrate` снапшотит `estimation.resources` в модель (страница модели
    обязана объяснять числа), а `estimate` применяет надбавку по конфигу. После
    правки конфига без `train`/`enrich` оценка считается по новым настройкам, а
    объяснение остаётся старым: расхождение печатается, числа при этом не
    меняются — молчаливой подмены провенанса быть не должно.
    """
    if not isinstance(model, dict):
        return None
    block = model.get("resources")
    if not isinstance(block, dict):
        return None
    settings = resourcesmod.resources_settings(_resources_config(cfg))
    model_signature = _resources_signature(
        block.get("enabled"),
        block.get("sp_per_resource"),
        block.get("mode"),
        block.get("items"),
    )
    config_signature = _resources_signature(
        settings.get("enabled"),
        settings.get("sp_per_resource"),
        settings.get("mode"),
        settings.get("items"),
    )
    if model_signature == config_signature:
        return None
    message = (
        "[WARN] resources: настройки RS-01 в модели расходятся с конфигом — "
        "оценка считается по конфигу (enabled=%s, sp_per_resource=%s, mode=%s), "
        "модель объясняет enabled=%s, sp_per_resource=%s, mode=%s%s; "
        "переобучите модель (trr train / enrich)"
        % (
            "да" if config_signature[0] else "нет",
            _fmt_or_unknown(config_signature[1]),
            config_signature[2],
            "да" if model_signature[0] else "нет",
            _fmt_or_unknown(model_signature[1]),
            model_signature[2],
            (
                ", каталог ресурсов тоже различается"
                if model_signature[3] != config_signature[3]
                else ""
            ),
        )
    )
    if warnings is not None:
        warnings.append(message)
    return message


def _primary_entry(entries, context):
    """Запись основного исполнителя: роль из снимка, иначе первая не-QA.

    `source=derived` — производная QA-запись, посчитанная моделью: надбавка за
    ресурсы к ней не применяется (иначе двойной счёт, см. `_apply_resources`).
    Роль вне словаря скилла (`TL`) оценивается по `OTHER` — такая запись тоже
    считается основной: это работа исполнителя, а не производная QA.
    """
    role = str((context or {}).get("role") or "").strip()
    if role:
        for entry in entries:
            if str(entry.get("role")) == role and entry.get("source") != "derived":
                return entry
    for entry in entries:
        if entry.get("role") != QA_ROLE and entry.get("source") != "derived":
            return entry
    return None


def _apply_resources(entries, context, cfg, scale, warnings=None):
    """Применить надбавку `RS-01` за дополнительные ресурсы к основному исполнителю.

    Ресурсы распознаёт `resources.detect_resources` по снимку задачи: allure
    (тест-кейсы), e2e (автотесты) и всё, что добавлено в
    `estimation.resources.items`. Режимы:

    * `add` — `expected = nearest_scale(expected + count × sp_per_resource)`,
      границы не сужаются: `range = [min(low, expected),
      max(high, nearest_scale(high + bonus))]`, `expected` остаётся внутри;
    * `upper_bound` — `expected = range[1]`: ресурсы не добавляют шаг, а
      заставляют взять уже посчитанную верхнюю границу (для задач «на тесты»,
      где объём известен плохо и нижняя оценка заведомо оптимистична).

    Запись выбирается `_primary_entry`: роль из `context.role` (та, что в
    `roles[]` — основная), а **не** производная QA-запись `source=derived`.
    Надбавка вызывается после того, как QA-запись добавлена в `entries`, и
    поэтому не попадает в её расчёт — двойного счёта нет.

    Возвращает блок `resources` для `estimate.json` или None, когда ресурсов
    нет (или `sp_per_resource: 0` в режиме `add` — правило без эффекта).
    """
    summary = resourcesmod.resources_summary(context, _resources_config(cfg))
    count = int(summary.get("count") or 0)
    if count <= 0:
        return None

    mode = str(summary.get("mode") or "add")
    bonus = float(summary.get("bonus_sp") or 0)
    if mode != "upper_bound" and bonus <= 0:
        return None

    entry = _primary_entry(entries, context)
    if entry is None:
        return None

    before = int(entry["expected"])
    low, high = int(entry["range"][0]), int(entry["range"][1])
    if mode == "upper_bound":
        expected = high
        new_low, new_high = low, high
    else:
        expected = int(calmod.nearest_scale(before + bonus, scale))
        new_low = min(low, expected)
        new_high = max(high, int(calmod.nearest_scale(high + bonus, scale)))

    entry["expected"] = expected
    entry["range"] = [new_low, new_high]
    names = ", ".join(str(item.get("name")) for item in summary["items"])
    bonus_text = _fmt(summary.get("bonus_sp") or 0)
    note = "RS-01: ресурсы %s → +%s SP (mode %s)" % (names, bonus_text, mode)
    if mode == "upper_bound":
        note = "RS-01: ресурсы %s → верхняя граница %d SP (mode upper_bound)" % (
            names,
            expected,
        )
    for scenario in entry.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        name = scenario.get("name")
        if name == "base":
            scenario["points"] = expected
            scenario["reason"] = "%s; %s" % (
                str(scenario.get("reason") or "").rstrip("; "),
                note,
            )
        elif name == "optimistic":
            scenario["points"] = new_low
        elif name == "pessimistic":
            scenario["points"] = new_high
    # Провенанс сценариев создаётся вместе с записью роли — до надбавки, поэтому
    # его `detail` описывал бы прежние числа. Синхронизируем: финальные значения
    # сценариев и есть то, что читает отчёт.
    _sync_scenarios_provenance(entry)

    if mode == "upper_bound":
        value = "верхняя граница диапазона за ресурсы: %s" % names
    else:
        value = "+%s SP за ресурсы: %s" % (bonus_text, names)
    entry.setdefault("provenance", []).append(
        {
            "field": "expected",
            "kind": "rule",
            "ref": RESOURCES_RULE_ID,
            "value": value,
            "source": "estimate:resources",
            "detail": (
                "%s; режим %s, ресурсов %d → +%s SP, expected %d → %d, "
                "range [%d, %d]"
                % (
                    note,
                    mode,
                    count,
                    bonus_text,
                    before,
                    expected,
                    new_low,
                    new_high,
                )
            ),
        }
    )
    if warnings is not None:
        warnings.append("[INFO] resources: %s" % note)

    block = {
        "items": summary["items"],
        "count": count,
        "sp_per_resource": summary.get("sp_per_resource", 1),
        "bonus_sp": summary.get("bonus_sp", count),
        "mode": mode,
        "applied_to": str(entry.get("role")),
        "effect": "expected %d → %d SP" % (before, expected),
    }
    if mode == "upper_bound":
        # Шага не прибавляется: берётся уже посчитанная верхняя граница, поэтому
        # `bonus_sp` здесь был бы ложным числом «сколько добавили».
        block["bonus_sp"] = 0
        block["effect"] = "expected = upper bound (%d SP)" % expected
    return block


def _fmt_or_unknown(value):
    """`_fmt`, но нечисло печатается как `н/д` (провенанс не должен падать)."""
    try:
        return _fmt(value)
    except (TypeError, ValueError):
        return "н/д"


def _sync_scenarios_provenance(entry):
    """Переписать `detail` провенанса сценариев по их текущим значениям.

    Запись `{"field": "scenarios"}` создаётся при сборке роли, когда `expected`
    ещё не сдвинут штрафами и надбавкой `RS-01`. Правки сценариев позже (ресурсы)
    обязаны обновлять и `detail` — иначе провенанс объясняет другие числа, чем
    те, что лежат в `scenarios[]`/`expected`.
    """
    points = {}
    for scenario in entry.get("scenarios") or []:
        if isinstance(scenario, dict) and scenario.get("name"):
            points[str(scenario["name"])] = scenario.get("points")
    if not points:
        return
    detail = "optimistic=%s, base=%s, pessimistic=%s" % (
        _fmt_or_unknown(points.get("optimistic")),
        _fmt_or_unknown(points.get("base")),
        _fmt_or_unknown(points.get("pessimistic")),
    )
    for item in entry.get("provenance") or []:
        if isinstance(item, dict) and item.get("field") == "scenarios":
            item["detail"] = detail
            return


def _resources_reason(block):
    """Строка `variability_reason[]` про надбавку за ресурсы (правило `RS-01`)."""
    names = ", ".join(str(item.get("name")) for item in block.get("items") or [])
    if block.get("mode") == "upper_bound":
        return "RS-01: ресурсы %s → верхняя граница диапазона (mode upper_bound)" % (
            names,
        )
    return "RS-01: ресурсы %s → +%s SP (mode %s)" % (
        names,
        _fmt(block.get("bonus_sp") or 0),
        block.get("mode"),
    )


def _dominant_role(buckets, work_kind):
    """Доминирующая роль для `work_kind`: бакет с максимальным `n`.

    Детерминированно: `n` desc → `role` asc (затем `work_kind`, `issue_type` —
    чтобы выбор не зависел от порядка бакетов в модели). Когда бакетов этого
    `work_kind` нет вовсе, роль выбирается по всем бакетам модели: вызывающий
    всё равно деградирует по уровням `select_bucket` вплоть до `OTHER`, но
    суммы по всем ролям не будет.
    """
    def rank(bucket):
        try:
            count = int(bucket.get("n") or 0)
        except (TypeError, ValueError):
            count = 0
        return (
            -count,
            str(bucket.get("role")),
            str(bucket.get("work_kind")),
            str(bucket.get("issue_type")),
        )

    matching = [
        bucket
        for bucket in buckets
        if str(bucket.get("work_kind")) == work_kind
    ]
    chosen = sorted(matching or buckets, key=rank)[0]
    try:
        count = int(chosen.get("n") or 0)
    except (TypeError, ValueError):
        count = 0
    return {
        "role": str(chosen.get("role")),
        "n": count,
        "work_kind": str(chosen.get("work_kind")),
        "issue_type": str(chosen.get("issue_type")),
    }


def estimate(
    validation,
    model,
    roles=None,
    context=None,
    vector_model=None,
    vector_config=None,
    warnings=None,
    cfg=None,
):
    """Посчитать оценку задачи по модели и проверить её по схеме §5.9.

    `context` — необязательный снимок задачи (`context.json`): из него берутся
    `work_kind` (решение агента), `role` (роль задачи) и параметры
    `weight`/`heat`/`connectivity` (override или эвристика `params.derive`).

    `cfg` — нормализованный конфиг: из него читаются `estimation.params`
    (коэффициенты, границы, дефолты). `None` — дефолты конфига.

    `vector_model` — необязательный артефакт `norm/task-vectors.json`,
    `vector_config` — `estimation.vector` из конфига. Векторы добавляют
    справочный `similar_tasks[]`; числа меняются только при
    `adjust_range: true` (по умолчанию выключено) и только если в калибровке
    артефакта есть `similar_threshold` — без порога правка пропускается.

    `warnings` — необязательный список: сюда складываются `[WARN]`-строки
    (например, «`adjust_range` пропущен: нет калибровки»). Движок остаётся
    чистым, печать — за CLI.

    Дополнительные ресурсы (`estimation.resources`, правило `RS-01`): allure для
    тест-кейсов, e2e-сервис автотестирования для автотестов. Надбавка считается
    по снимку задачи (`resources.detect_resources`) и применяется **только** к
    записи основного исполнителя — роль из `context.role` (та, что в `roles[]`
    идёт как основная), а не к производной QA-записи `source=derived`: та уже
    считается от объёма работы, и надбавка к ней была бы двойным счётом. Если
    ресурсов нет (или `sp_per_resource: 0` в режиме `add`), ключ `resources` в
    `estimate.json` не появляется — как `qa_scope`.

    `roles` — необязательный список ролей задачи. По умолчанию берётся роль из
    `context.role`; роль вне словаря скилла (`TL` и подобные) оценивается по
    `OTHER` с `confidence=low` и причиной в `variability_reason[]`; если роли в
    снимке нет вовсе — принимается доминирующая роль вида работ (бакет с
    максимальным `n`, `n` desc → `role` asc) и оценивается только она
    (`role_assumed: true`, `confidence=low`). Явно переданная роль не из
    `ROLES` — по-прежнему `ValueError` (это ошибка вызывающего, а не снимка).
    Роль без бакетов деградирует до `OTHER`/любого бакета модели, а не роняет
    оценку.
    """
    if not isinstance(validation, dict):
        raise ValueError("validation должен быть JSON-объектом")
    if not isinstance(model, dict):
        raise ValueError("модель должна быть JSON-объектом")

    # Снимок задачи необязателен: `estimate(validation, model)` — легальный
    # вызов (например, оценка только по validation). Нормализуем `None` в пустой
    # словарь один раз здесь, чтобы ниже не проверять `isinstance` в каждом
    # обращении (`_qa_entry` → `check.qa_estimation_value`).
    context = context or {}
    if not isinstance(context, dict):
        raise ValueError("context должен быть JSON-объектом или None")

    task_key = validation.get("task_key")
    if not isinstance(task_key, str) or not task_key.strip():
        raise ValueError("validation.task_key обязателен и непуст")

    buckets = model.get("buckets")
    if not isinstance(buckets, list) or not buckets:
        raise ValueError("в модели нет бакетов — оценивать нечем, пересоберите модель")
    for bucket in buckets:
        if not isinstance(bucket, dict):
            raise ValueError("estimation-model.buckets: элемент не объект")

    scale = _scale(model)
    model_version = model.get("version")
    model_checksum = model.get("checksum")
    if isinstance(model_version, bool) or not isinstance(model_version, int):
        raise ValueError("estimation-model.version должен быть целым")
    if not isinstance(model_checksum, str) or not model_checksum.strip():
        raise ValueError("estimation-model.checksum обязателен и непуст")

    work_kind = validation.get("work_kind")
    if work_kind is None and isinstance(context, dict):
        work_kind = context.get("work_kind")
    explicit = work_kind is not None
    if explicit and work_kind not in WORK_KINDS:
        raise ValueError(
            "work_kind=%r не входит в допустимые (%s)"
            % (work_kind, ", ".join(WORK_KINDS))
        )
    if not explicit:
        work_kind = "implementation"

    unknown_role = None
    role_assumed = None
    if roles is None and isinstance(context, dict):
        context_role = context.get("role")
        if isinstance(context_role, str) and context_role.strip():
            role_value = context_role.strip()
            if role_value in ROLES:
                roles = [role_value]
            else:
                # Роль вне словаря скилла (`TL`, `DevOps`, `Аналитик` …). Раньше
                # такая роль молча терялась, и оценка суммировала ВСЕ роли модели
                # (45 SP на пустом снимке). Теперь — деградация до `OTHER`:
                # роль остаётся видимой в отчёте, числа честно помечены low.
                roles = ["OTHER"]
                unknown_role = role_value

    if roles is None:
        # Роль не указана (в снимке её нет или она null). Сумма по всем ролям
        # модели — та же «молчаливая сумма», что убирали для `TL`: 29/76 SP
        # ничего не значат для одной задачи. Вместо неё — доминирующая роль
        # вида работ: бакет с максимальным `n`, детерминированно.
        role_assumed = _dominant_role(buckets, work_kind)
        roles = [role_assumed["role"]]

    if not isinstance(roles, (list, tuple)):
        raise ValueError("roles должен быть списком ролей")
    for role in roles:
        if role not in ROLES:
            raise ValueError("роль %r не входит в допустимые (%s)" % (role, ROLES))
    selected = sorted(set(str(role) for role in roles))

    absent_roles = [
        str(role) for role in (model.get("absent_roles") or []) if role in ROLES
    ]

    required_gaps = [
        gap
        for gap in (validation.get("gaps") or [])
        if isinstance(gap, dict) and gap.get("severity") == "REQUIRED"
    ]
    blocked_by_gaps = sorted({str(gap.get("id")) for gap in required_gaps})

    # Параметры задачи считаются один раз: они не зависят от роли. Множитель —
    # от профиля бакета: модель калибрована на своём профиле, задача двигает
    # оценку относительно него, а не относительно «нуля».
    params_settings = paramsmod.settings(cfg)
    params_result = paramsmod.derive(
        context if isinstance(context, dict) else {}, cfg
    )
    default_baseline = {
        name: float(params_settings["defaults"][name])
        for name in paramsmod.PARAM_NAMES
    }

    missing_roles = []
    assumed_reasons = []
    fallback_reasons = []
    penalty_reasons = []
    reference_reasons = []
    entries = []
    applied_params = []

    if role_assumed is not None:
        note = (
            "роль не указана → принята доминирующая роль %s (n=%d) для work_kind=%s"
            % (role_assumed["role"], role_assumed["n"], work_kind)
        )
        assumed_reasons.append(note)
        if warnings is not None:
            warnings.append("[WARN] estimate: %s" % note)

    # Тип задачи участвует только в выборе бакета (уровень 1): без него на пару
    # `(role, work_kind)` достижим ровно один бакет — самый крупный по `n`.
    issue_type = None
    if isinstance(context, dict):
        candidate = context.get("issue_type")
        if not isinstance(candidate, str) or not candidate.strip():
            fields = context.get("fields")
            candidate = fields.get("issue_type") if isinstance(fields, dict) else None
        if isinstance(candidate, str) and candidate.strip():
            issue_type = candidate.strip()

    for role in selected:
        bucket, level = select_bucket(
            buckets, role, work_kind, explicit, issue_type=issue_type
        )
        fallback_from = None
        role_fallback = None
        if explicit and work_kind == "unknown" and _bucket_empty(bucket):
            # CONTRACT.md §5.4.1: вид работ не определён — база берётся из
            # `implementation`, но уверенность принудительно `low`, и причина
            # попадает в отчёт. Молча подставлять implementation нельзя.
            fallback_from = "implementation"
            candidate, level = select_bucket(
                buckets, role, fallback_from, True, issue_type=issue_type
            )
            bucket = None if _bucket_empty(candidate) else candidate
        if bucket is None:
            # Деградация роли: у неё нет ни одного бакета (DEVOPS и подобные).
            # Порядок — OTHER по тем же уровням 1–3, затем любой бакет модели.
            candidate, candidate_level = select_bucket(
                buckets, "OTHER", work_kind, explicit, issue_type=issue_type
            )
            if _bucket_empty(candidate):
                candidate = _pick_bucket(buckets)
                candidate_level = BUCKET_LEVEL_ANY
            else:
                candidate_level = BUCKET_LEVEL_OTHER_ROLE
            if not _bucket_empty(candidate):
                bucket = candidate
                level = candidate_level
                role_fallback = str(candidate.get("role"))
        if bucket is None:
            missing_roles.append("нет данных по роли %s" % role)
            continue
        if fallback_from is not None:
            note = "work_kind=unknown — база взята из %s, confidence=low" % (
                fallback_from
            )
            if note not in fallback_reasons:
                fallback_reasons.append(note)
        if role_fallback is not None:
            note = (
                "нет бакета для роли %s → fallback %s/%s/%s, confidence=low"
                % (
                    role,
                    bucket.get("role"),
                    bucket.get("issue_type"),
                    bucket.get("work_kind"),
                )
            )
            if note not in fallback_reasons:
                fallback_reasons.append(note)
                if warnings is not None:
                    warnings.append("[WARN] estimate: %s" % note)
        elif explicit and level == BUCKET_LEVEL_ROLE:
            note = (
                "work_kind=%s: у роли %s нет бакета этого вида работ → взят "
                "%s/%s/%s, confidence=low"
                % (
                    work_kind,
                    role,
                    bucket.get("role"),
                    bucket.get("issue_type"),
                    bucket.get("work_kind"),
                )
            )
            if note not in fallback_reasons:
                fallback_reasons.append(note)
                if warnings is not None:
                    warnings.append("[WARN] estimate: %s" % note)
        if unknown_role is not None and role == "OTHER":
            note = (
                "роль %r вне словаря скилла → оценка по OTHER, confidence=low"
                % (unknown_role,)
            )
            if note not in fallback_reasons:
                fallback_reasons.append(note)
                if warnings is not None:
                    warnings.append("[WARN] estimate: %s" % note)

        base_expected = int(bucket["expected"])
        baseline, baseline_source = _baseline_for(bucket, default_baseline)
        params_multiplier = paramsmod.multiplier(
            params_result, cfg, baseline=baseline
        )
        applied_params.append(
            {
                "multiplier": params_multiplier,
                "baseline": baseline,
                "baseline_source": baseline_source,
            }
        )

        # Множитель применяется до штрафов: сначала масштаб по параметрам
        # задачи, затем сдвиг за REQUIRED-пробелы.
        base_expected = calmod.nearest_scale(base_expected * params_multiplier, scale)
        base_range = [
            calmod.nearest_scale_down(int(bucket["range"][0]) * params_multiplier, scale),
            calmod.nearest_scale_up(int(bucket["range"][1]) * params_multiplier, scale),
        ]
        if base_range[0] > base_range[1]:
            base_range[0], base_range[1] = base_range[1], base_range[0]
        applied, steps = _penalties(validation, model, role)

        # Штрафы применяются последовательно: строка объяснения показывает,
        # как менялось `expected` от шага к шагу (3 → 5 → 8).
        expected = base_expected
        for rule_id, rule_steps in applied:
            before = expected
            expected = shift(expected, rule_steps, scale)
            penalty_reasons.append(
                "%s: %s → %s (%d → %d), роль %s"
                % (
                    rule_id,
                    RULE_DESCRIPTIONS.get(rule_id, "штраф за REQUIRED-пробел"),
                    _steps_word(rule_steps),
                    before,
                    expected,
                    role,
                )
            )

        upper = shift(base_range[1], steps, scale)
        lower = base_range[0]
        if upper < expected:
            upper = expected
        if lower > expected:
            lower = expected
        if lower > upper:
            lower = upper

        if bucket.get("reference") == "none" and role not in absent_roles:
            reference_reasons.append(
                "роль %s без эталона (reference=none) — база только из спринтов" % role
            )

        penalty_note = (
            "gap_penalty %s" % _steps_word(steps)
            if steps
            else "REQUIRED-пробелов по роли нет"
        )
        entries.append(
            {
                "role": role,
                "expected": expected,
                "range": [lower, upper],
                "scenarios": [
                    {
                        "name": "base",
                        "points": expected,
                        "reason": "expected=%d (base %d × factor %s × params %s), %s"
                        % (
                            expected,
                            int(bucket["base"]),
                            _fmt(bucket["factor"]),
                            _fmt(params_multiplier),
                            penalty_note,
                        ),
                    },
                    {
                        "name": "optimistic",
                        "points": lower,
                        "reason": "нижняя граница диапазона без штрафов: %d"
                        % lower,
                    },
                    {
                        "name": "pessimistic",
                        "points": upper,
                        "reason": (
                            "верхняя граница диапазона %d + %s"
                            % (base_range[1], penalty_note)
                            if steps
                            else "верхняя граница диапазона без штрафов: %d" % upper
                        ),
                    },
                ],
                "confidence": (
                    "low"
                    if (
                        fallback_from is not None
                        or role_fallback is not None
                        or (explicit and level == BUCKET_LEVEL_ROLE)
                        or (unknown_role is not None and role == "OTHER")
                        or (role_assumed is not None and role == role_assumed["role"])
                    )
                    else str(bucket.get("confidence", "low"))
                ),
                "provenance": [
                    {
                        "field": "expected",
                        "kind": "model",
                        "source": "estimation-model:%d:%s/%s/%s"
                        % (
                            model_version,
                            bucket.get("role"),
                            bucket.get("issue_type"),
                            bucket.get("work_kind"),
                        ),
                        "detail": "expected=%d, range=[%d, %d], %s"
                        % (expected, lower, upper, penalty_note),
                    },
                    {
                        "field": "bucket",
                        "kind": "rule",
                        "source": "estimate:bucket-select",
                        "detail": "уровень выбора: %s — %s; бакет %s/%s/%s%s"
                        % (
                            level,
                            BUCKET_LEVELS.get(level, level),
                            bucket.get("role"),
                            bucket.get("issue_type"),
                            bucket.get("work_kind"),
                            (
                                "; запрошена роль %s" % role
                                if str(bucket.get("role")) != role
                                else ""
                            ),
                        ),
                    },
                    {
                        "field": "params_multiplier",
                        "kind": "rule",
                        "source": "estimate:params",
                        "detail": (
                            "params ×%s относительно baseline (%s: weight=%s, "
                            "heat=%s, connectivity=%s)"
                            % (
                                _fmt(params_multiplier),
                                baseline_source,
                                _fmt(baseline["weight"]),
                                _fmt(baseline["heat"]),
                                _fmt(baseline["connectivity"]),
                            )
                        ),
                    },
                    {
                        "field": "scenarios",
                        "kind": "rule",
                        "source": "estimation-model:%d:gap_rules" % model_version,
                        "detail": "optimistic=%d, base=%d, pessimistic=%d"
                        % (lower, expected, upper),
                    },
                ],
            }
        )
        if role == QA_ROLE:
            # QA — оцениваемая роль задачи: `total.qa` и отчёт должны знать,
            # что число получено моделью, а не из поля QA Estimation.
            entries[-1]["source"] = "model"
        if role_assumed is not None and role == role_assumed["role"]:
            entries[-1]["provenance"].append(
                {
                    "field": "role",
                    "kind": "rule",
                    "source": "estimate:role-assumed",
                    "detail": (
                        "роль не указана → принята доминирующая роль %s (n=%d) "
                        "для work_kind=%s: бакет %s/%s/%s"
                        % (
                            role_assumed["role"],
                            role_assumed["n"],
                            work_kind,
                            bucket.get("role"),
                            bucket.get("issue_type"),
                            bucket.get("work_kind"),
                        )
                    ),
                }
            )

    if not entries:
        raise ValueError(
            "ни одной роли с данными в модели — оценивать нечем (work_kind=%s)"
            % work_kind
        )

    # QA — отдельная запись и слагаемое `total`. Порядок ветвей и запрет
    # двойного счёта — в `_qa_entry`.
    qa_required_types = _qa_required_types(cfg)
    qa_record = _qa_entry(
        selected=selected,
        context=context,
        buckets=buckets,
        work_kind=work_kind,
        explicit=explicit,
        issue_type=issue_type,
        scale=scale,
        params_result=params_result,
        cfg=cfg,
        default_baseline=default_baseline,
        entries=entries,
        model_version=model_version,
        warnings=warnings,
        qa_required_issue_types=qa_required_types,
    )
    if qa_record is not None:
        entries.append(qa_record)

    # QA-записи нет — объясняем это в estimate.json: отчёт печатает строку
    # «QA: не требуется (тип «…») — …» вместо пустоты. Ключ необязательный:
    # без issue_type/роли в снимке он не появляется.
    qa_scope = (
        None
        if qa_record is not None
        else _qa_scope_text(context, selected, issue_type, qa_required_types)
    )

    # Надбавка за дополнительные ресурсы (`RS-01`): allure/e2e и подобные.
    # Считается ПОСЛЕ QA-записи и применяется только к основному исполнителю —
    # производная QA-запись (`source=derived`) уже считается от объёма работы,
    # надбавка к ней была бы двойным счётом.
    _resources_drift(model, cfg, warnings)
    resources_block = _apply_resources(entries, context, cfg, scale, warnings)

    entries.sort(key=lambda entry: entry["role"])

    reasons = []
    reasons.extend(missing_roles)
    reasons.extend(assumed_reasons)
    reasons.extend(fallback_reasons)
    reasons.extend(penalty_reasons)
    reasons.extend(reference_reasons)
    if absent_roles:
        reasons.append(
            "нет данных по %s в эталоне — база только из спринтов"
            % "/".join(absent_roles)
        )
    if qa_record is not None:
        reasons.append(_qa_reason(qa_record))
    if resources_block is not None:
        reasons.append(_resources_reason(resources_block))

    params_block = _params_block(params_result, applied_params, cfg)

    similar_tasks = _apply_vectors(
        entries,
        task_key,
        context,
        vector_model,
        vector_config,
        scale,
        reasons,
        warnings,
    )

    result = {
        "task_key": task_key,
        "estimated_at": now_utc(),
        "model_version": model_version,
        "model_checksum": model_checksum,
        "roles": entries,
        "total": _total_block(entries),
        "variability_reason": reasons,
        "blocked_by_gaps": blocked_by_gaps,
    }
    # Содержательный анализ — не вход оценки, а её объяснение: копируется из
    # validation.json, чтобы estimate.json был самодостаточным (отчёт берёт
    # блок «Что видно из задачи» из него, когда validation рядом нет).
    if isinstance(validation.get("analysis"), dict):
        result["analysis"] = validation["analysis"]
    if qa_scope:
        result["qa_scope"] = qa_scope
    if resources_block is not None:
        result["resources"] = resources_block
    if role_assumed is not None:
        result["role_assumed"] = True
    if params_block is not None:
        result["params"] = params_block
        if params_block["multiplier"] != 1.0:
            reasons.append(
                "params: weight=%s, heat=%s, connectivity=%s → ×%s (baseline: %s)"
                % (
                    _fmt(params_block["weight"]),
                    _fmt(params_block["heat"]),
                    _fmt(params_block["connectivity"]),
                    _fmt(params_block["multiplier"]),
                    params_block["baseline_source"],
                )
            )
    if similar_tasks is not None:
        result["similar_tasks"] = similar_tasks
    _validate(result)
    return result


def _qa_reason(record):
    """Строка `variability_reason[]` про QA-составляющую.

    Формат близок к остальным строкам (`<причина> → <эффект>`), но без
    `rule_id`: это не штраф, а слагаемое `total`. Секция 6 отчёта собирает
    прозу из полей оценки, строка остаётся полным объяснением для JSON.
    """
    if record.get("source") == "jira":
        return "QA: QA Estimation из Jira → %d SP (значение как есть), роль QA" % (
            record["expected"],
        )
    return (
        "QA: поле QA Estimation пустое → рассчитано моделью (%d SP, бакет %s), роль QA"
        % (record["expected"], record.get("qa_bucket") or "доля от dev")
    )


def _total_block(entries):
    """Итог оценки: сумма ВСЕХ ролей (включая QA) и QA-составляющая.

    `total.qa` появляется, когда в `roles[]` есть запись `QA`: отчёту нужна
    строка `Dev: N SP · QA: M SP`. `source` — откуда взялось число
    (`jira`, `derived` или `model` — когда QA и есть оцениваемая роль).
    """
    total = {
        "expected": sum(int(entry["expected"]) for entry in entries),
        "range": [
            sum(int(entry["range"][0]) for entry in entries),
            sum(int(entry["range"][1]) for entry in entries),
        ],
    }
    for entry in entries:
        if entry.get("role") != QA_ROLE:
            continue
        qa = {
            "expected": int(entry["expected"]),
            "source": str(entry.get("source") or "model"),
        }
        if entry.get("qa_bucket"):
            qa["bucket"] = str(entry["qa_bucket"])
        total["qa"] = qa
        break
    return total


def _params_block(params_result, applied, cfg):
    """Блок `params` оценки: значения, провенанс и применённый множитель.

    `applied` — по элементу на роль (`multiplier`, `baseline`,
    `baseline_source`). Когда у ролей разные профили бакетов, множители тоже
    разные: тогда в блоке остаётся множитель относительно `defaults`, а
    фактический множитель роли виден в её `provenance`.
    """
    if not isinstance(params_result, dict):
        return None
    names = paramsmod.PARAM_NAMES
    values = {}
    sources = {}
    for name in names:
        entry = params_result.get(name)
        entry = entry if isinstance(entry, dict) else {}
        number = entry.get("value")
        values[name] = (
            float(number)
            if isinstance(number, (int, float)) and not isinstance(number, bool)
            else 0.0
        )
        sources[name] = str(entry.get("source") or "heuristic")

    settings = paramsmod.settings(cfg)
    defaults = {
        name: float(settings["defaults"][name]) for name in names
    }
    mults = {round(float(item["multiplier"]), 4) for item in applied} or {1.0}
    baselines = {
        tuple(round(float(item["baseline"][name]), 4) for name in names)
        for item in applied
    }
    if len(mults) == 1 and len(baselines) <= 1 and applied:
        multiplier = applied[0]["multiplier"]
        baseline = dict(applied[0]["baseline"])
        baseline_source = applied[0]["baseline_source"]
    else:
        multiplier = paramsmod.multiplier(params_result, cfg)
        baseline = defaults
        baseline_source = "defaults"

    return {
        "weight": round(values["weight"], 4),
        "heat": round(values["heat"], 4),
        "connectivity": round(values["connectivity"], 4),
        "source": sources,
        "evidence": paramsmod.evidence_lines(params_result),
        "multiplier": round(float(multiplier), 4),
        "baseline": {
            name: round(float(baseline[name]), 4) for name in names
        },
        "baseline_source": baseline_source,
        "applied": bool(params_result.get("applied", {}).get("enabled", True)),
    }


def _fmt(value):
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return "%g" % number


def _validate(result):
    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, "estimate")
    except schema_lite.SchemaError as exc:
        raise ValueError("схема estimate не читается: %s" % exc)
    errors = schema_lite.validate(result, schema, "estimate")
    if errors:
        raise ValueError("estimate не соответствует схеме: %s" % "; ".join(errors))


# ---------------------------------------------------------------------------
# CLI-обвязка (`trr estimate`)
# ---------------------------------------------------------------------------


def _emit(message, quiet=False):
    if not quiet:
        print(message)


def _emit_json(args, payload):
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _read_json(path):
    try:
        limits.check_size(path)
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except OSError as exc:
        return None, "не читается: %s" % exc
    except ValueError as exc:
        return None, "невалидный JSON: %s" % exc


def _relative(workdir, path):
    try:
        return str(Path(path).resolve().relative_to(Path(workdir).resolve()))
    except (ValueError, OSError):
        return str(path)


def _config_or_none(workdir):
    """Конфиг проекта или None (для `estimation.params`); битый — None."""
    path = configmod.config_path(workdir)
    if not path.is_file():
        return None
    try:
        return configmod.load_config(path)
    except configmod.ConfigError:
        return None


def _vector_settings(workdir):
    """`estimation.vector` из конфига, всегда слитый с `DEFAULTS`.

    Нет конфига (или он не разбирается) — берутся дефолты из `config.DEFAULTS`,
    как в `vectors._vector_config`: иначе `estimate` молча выключал бы векторы
    (`{}` → `enabled` нет), а `vectors build` строил бы артефакт по дефолтам с
    `enabled: true`. Две разные трактовки одного блока — скрытое расхождение.
    """
    defaults = configmod.DEFAULTS["estimation"]["vector"]
    path = configmod.config_path(workdir)
    if not path.is_file():
        return copy.deepcopy(defaults)
    try:
        cfg = configmod.load_config(path)
    except configmod.ConfigError:
        return copy.deepcopy(defaults)
    block = ((cfg.get("estimation") or {}).get("vector")) or {}
    if not isinstance(block, dict):
        return copy.deepcopy(defaults)
    merged = copy.deepcopy(defaults)
    merged.update(block)
    return merged


def _load_vector_model(workdir, vector_config, quiet):
    """Прочитать `norm/task-vectors.json`, если векторы включены.

    Отсутствие артефакта или малый корпус — `[WARN]`, а не ошибка: оценка
    считается без справочных соседей, числа не меняются.
    """
    if not vector_config.get("enabled"):
        return None
    path = workdir / statemod.STATE_DIR / vectorsmod.VECTORS_RELATIVE
    if not path.is_file():
        _emit(
            "[WARN] estimate: векторы включены, но %s нет — запустите "
            "`trr vectors build`; оценка без похожих задач"
            % vectorsmod.VECTORS_RELATIVE,
            quiet,
        )
        return None
    model, error = _read_json(path)
    if error:
        _emit(
            "[WARN] estimate: %s — %s; оценка без похожих задач"
            % (vectorsmod.VECTORS_RELATIVE, error),
            quiet,
        )
        return None
    calibration = model.get("calibration") or {}
    try:
        corpus = int(calibration.get("corpus_rows") or len(model.get("vectors") or []))
    except (TypeError, ValueError):
        corpus = 0
    try:
        min_corpus = int(
            vector_config.get("min_corpus", configmod.VECTOR_MIN_CORPUS)
        )
    except (TypeError, ValueError):
        min_corpus = configmod.VECTOR_MIN_CORPUS
    if corpus < min_corpus:
        _emit(
            "[WARN] estimate: корпус векторов %d < min_corpus %d — похожие "
            "задачи не ищутся, добавьте спринты через enrich" % (corpus, min_corpus),
            quiet,
        )
        return None
    return model


def _run_dir(workdir, task_key, run_id):
    """Каталог прогона: явный `--run`, иначе последний незавершённый.

    «Незавершённый» — тот, где ещё нет `estimate.json` (CONTRACT.md §2):
    повторный estimate дописывает файлы в тот же прогон.
    """
    root = workdir / statemod.STATE_DIR / _RUNS_RELATIVE / task_key
    if run_id:
        return root / run_id
    if not root.is_dir():
        return None
    candidates = sorted(path for path in root.iterdir() if path.is_dir())
    unfinished = [
        path for path in candidates if not (path / _ESTIMATE_FILE).is_file()
    ]
    if unfinished:
        return unfinished[-1]
    if candidates:
        return candidates[-1]
    return None


def run(workdir, args=None):
    """Выполнить `trr estimate`: validation + модель → estimate.json."""
    workdir = Path(workdir)
    quiet = bool(getattr(args, "quiet", False))
    task_key = getattr(args, "task", None)
    if not task_key:
        _emit("[MISSING] estimate — нужен --task <KEY>", quiet)
        _emit_json(args, {"status": "blocked", "code": 2})
        return 2

    run_dir = _run_dir(workdir, task_key, getattr(args, "run", None))
    if run_dir is None or not (run_dir / _VALIDATION_FILE).is_file():
        display = (
            _relative(workdir, run_dir / _VALIDATION_FILE)
            if run_dir is not None
            else ".task-readiness/runs/%s/<RUN-ID>/%s" % (task_key, _VALIDATION_FILE)
        )
        _emit(
            "[MISSING] %s — сначала запустите /task-readiness-review check <KEY>"
            % display,
            quiet,
        )
        _emit_json(args, {"status": "blocked", "code": 4, "task_key": task_key})
        return 4

    validation, error = _read_json(run_dir / _VALIDATION_FILE)
    if error:
        _emit("[MISSING] %s — %s" % (_VALIDATION_FILE, error), quiet)
        _emit_json(args, {"status": "blocked", "code": 5, "task_key": task_key})
        return 5

    context, _context_error = _read_json(run_dir / _CONTEXT_FILE)
    if _context_error:
        context = None

    # Ручной override эвристических параметров (этап A). Значения участвуют в
    # множителе формулы оценки (`base × factor × params_multiplier`) и
    # фиксируются в снимке прогона; строка [INFO] печатает применённый множитель.
    overrides = {
        name: float(getattr(args, name))
        for name in ("weight", "heat", "connectivity")
        if getattr(args, name, None) is not None
    }
    if overrides:
        if not isinstance(context, dict):
            context = {}
        context.update(overrides)

    model_path = workdir / statemod.STATE_DIR / _MODEL_RELATIVE
    if not model_path.is_file():
        _emit(
            "[MISSING] estimate: нет модели оценки — запустите "
            "/task-readiness-review train",
            quiet,
        )
        _emit_json(args, {"status": "blocked", "code": 4, "task_key": task_key})
        return 4
    model, error = _read_json(model_path)
    if error:
        _emit("[MISSING] %s — %s" % (_MODEL_RELATIVE, error), quiet)
        _emit_json(args, {"status": "blocked", "code": 5, "task_key": task_key})
        return 5

    vector_config = _vector_settings(workdir)
    vector_model = _load_vector_model(workdir, vector_config, quiet)

    warnings = []
    params_cfg = _config_or_none(workdir)
    try:
        result = estimate(
            validation,
            model,
            context=context,
            vector_model=vector_model,
            vector_config=vector_config,
            warnings=warnings,
            cfg=params_cfg,
        )
    except ValueError as exc:
        _emit("[MISSING] estimate — %s" % exc, quiet)
        _emit_json(args, {"status": "blocked", "code": 5, "task_key": task_key})
        return 5

    for warning in warnings:
        _emit(warning, quiet)

    params_result = result.get("params") or {}
    params_multiplier = params_result.get("multiplier", 1.0)
    _emit(
        "[INFO] params: weight=%.2f (%s) heat=%.2f (%s) connectivity=%.2f (%s) "
        "multiplier=%.4f (baseline: %s) — множитель применён к expected и range"
        % (
            params_result.get("weight", 0.0),
            (params_result.get("source") or {}).get("weight", "?"),
            params_result.get("heat", 0.0),
            (params_result.get("source") or {}).get("heat", "?"),
            params_result.get("connectivity", 0.0),
            (params_result.get("source") or {}).get("connectivity", "?"),
            params_multiplier,
            params_result.get("baseline_source", "defaults"),
        ),
        quiet,
    )

    schema_lite.write_json(run_dir / _ESTIMATE_FILE, result)

    try:
        statemod.add_run(
            str(workdir),
            task_key,
            str(run_dir),
            str(validation.get("verdict", "WARN")),
            str(validation.get("checked_at", "")),
        )
        statemod.set_stage(str(workdir), "estimated")
    except statemod.StateError as exc:
        _emit("[WARN] state: этап не обновлён — %s" % exc, quiet)

    # Зеркало: прогон, оценка и разбивка по ролям. `params_cfg` может быть
    # None (конфиг не читается) — store тогда читает конфиг сам.
    storemod.save_estimate(
        workdir,
        params_cfg,
        run_dir.name,
        task_key,
        _relative(workdir, run_dir),
        result,
        params_multiplier=params_multiplier,
    )

    total = result["total"]
    _emit(
        "[OK] estimate: %s total %d [%d..%d]"
        % (task_key, total["expected"], total["range"][0], total["range"][1]),
        quiet,
    )
    _emit_json(
        args,
        {
            "status": "ok",
            "code": 0,
            "task_key": task_key,
            "expected": total["expected"],
            "range": total["range"],
            "params": {
                name: params_result.get(name) for name in paramsmod.PARAM_NAMES
            },
            "params_multiplier": params_multiplier,
        },
    )
    return 0

#!/usr/bin/env python3
"""Синтетический полигон: генератор задач и in-process харнесс `check + estimate`.

Зачем это нужно. Модель оценки и каталог проверок должны выдерживать не только
ту задачу, которую сейчас смотрит агент, но и тысячи разных снимков: пустые
описания, гигантские тексты, неизвестные роли и типы, крайние значения
`weight`/`heat`/`connectivity`. Полигон строит такие снимки **из реальных
комбинаций** `norm/sprint-sample.json` (роль, тип, метки — как в целевых
спринтах), варьирует наполненность и прогоняет `check.run_checks` +
`estimate.estimate` в одном процессе, собирая метрики качества.

Две подкоманды:

    trr synth --count 10000 --out DIR --seed 42 [--from-sprints 20365,...] [--include-edge]
        контексты задач → DIR/contexts.jsonl + DIR/manifest.json

    trr synth-run --dir DIR [--out DIR2] [--limit N] [--workers N] [--json]
        прогон check + estimate по contexts.jsonl → DIR2/summary.json +
        DIR2/records.jsonl

Границы ответственности:

* **ничего не публикует** — ни задач Jira, ни страниц Confluence;
* **не пишет** в `.task-readiness/runs/` рабочего проекта: все результаты
  остаются в `--out`/`--dir`, прогон живёт в памяти;
* **не меняет** модель, эталон, статистику и формулу — только читает их;
* **stdlib** и детерминизм: тот же `--seed` даёт побайтно тот же
  `contexts.jsonl` (сортировка ключей, фиксированные разделители, никакого
  времени в артефактах).

Распределения осей берутся из выборки спринтов; квоты, заданные явно
(`sp=null` 5 %, `qa_estimation=null` 30 %, буквальный `0` 2 %, неизвестная
роль 2 %, 2 % edge-случаев), применяются поверх выборки. Фактические
распределения пишутся в `manifest.json` и в `summary.json` — по ним видно,
что полигон реально сгенерировал, а не что задумывалось.

Покрытие троек модели (`--coverage-all-buckets`, включено по умолчанию).
Оси выборки спринтов не содержат всех комбинаций `(role, issue_type,
work_kind)`, по которым модель умеет считать: у `QA` в выборке нет `Ошибка` и
`Tech Debt`, а `QA/Feature` и `QA/Задача` всегда уходили в `testing`. Поэтому
`--coverage-quota` × <число троек модели> снимков датасета (равномерно по всему
файлу, а не блоком) получают тройку явно (`role`/`issue_type`/`work_kind` в
снимке), а остальные — по существующим осям. Это делает `buckets.hit` равным
числу бакетов модели, не меняя выборку, модель и формулу: `work_kind` —
легальный ключ снимка (`check.CONTEXT_KEYS`).
"""

import concurrent.futures
import hashlib
import json
import math
import random
import statistics
import time
import traceback
from pathlib import Path

from trr_impl import check as checkmod
from trr_impl import config as configmod
from trr_impl import estimate as estimatemod
from trr_impl import params as paramsmod
from trr_impl import paths as pathsmod
from trr_impl import schema_lite
from trr_impl import state as statemod
from trr_impl import store as storemod

__all__ = ["GENERATOR_VERSION", "generate", "run"]

GENERATOR_VERSION = "2"

# Покрытие троек модели: сколько задач на каждую тройку `(role, issue_type,
# work_kind)` гарантирует генератор. 20 троек × 20 = 400 задач на датасете в
# 10 000 — остальное распределяется по осям выборки как раньше.
COVERAGE_QUOTA_DEFAULT = 20

# Шкала Story Points — нормативная (estimation-model.scale). Харнесс сверяет с
# ней `expected`, а не с моделью: расхождение шкалы и модели — отдельный дефект.
SCALE = (1, 2, 3, 5, 8, 13, 21)

# Тип задачи, которого нет в выборке спринтов, но он есть в словаре скилла
# (`ISSUE_TYPE_BASE`): 2 % «хвоста» гарантируют, что ось типа покрывает весь
# словарь, а не только встреченные значения.
TYPE_TAIL = (("Исследование", 0.02),)

# Неизвестная роль: модель её не знает, `estimate` деградирует до `OTHER`
# (`confidence=low`), а не суммирует все роли модели.
# Это законный сценарий снимка (в Jira роль заполнена не по словарю) — его и
# проверяем, а не прячем.
UNKNOWN_ROLES = ("DEVOPS", "TL")
UNKNOWN_ROLE_SHARE = 0.02

# Наполненность описания — равновероятно.
DESCRIPTION_LENGTHS = (0, 50, 200, 500, 2000, 8000)

# Секции: все три группы / частично / ни одной — по третям.
SECTION_MODES = ("all", "partial", "none")

# Метки: категории из брифа с весами. «Смешанные» и «мусорные» — отдельные
# категории, а не случайный шум: по ним видно, как проверки реагируют на
# integration/research-сигналы и на метки вне словаря.
LABEL_CASES = (
    ("none", (), 0.42),
    ("research", ("research",), 0.08),
    ("spike", ("spike",), 0.06),
    ("api", ("api",), 0.10),
    ("integration", ("integration",), 0.08),
    ("api_contract", ("api", "contract"), 0.07),
    ("mixed", None, 0.10),
    ("junk", None, 0.09),
)
_MIXED_LABELS = (
    ("research", "api"),
    ("spike", "integration"),
    ("api", "dea-fe"),
    ("research", "spike", "api"),
)
_JUNK_LABELS = (
    ("urgent", "backend"),
    ("tocs", "DPOReview"),
    ("product_bucket", "toinfr"),
)

# issuelinks: веса из брифа (0 — 40 %, 1 — 25 %, 3 — 15 %, 5 — 10 %, 10 — 7 %,
# 20 — 3 %).
LINK_CASES = ((0, 40), (1, 25), (3, 15), (5, 10), (10, 7), (20, 3))

# Компоненты: 0, 1, 2, 5, 10.
COMPONENT_CASES = ((0, 25), (1, 30), (2, 25), (5, 15), (10, 5))

# Доля задач с ручным override параметров (в т.ч. крайние 0.0 и 1.0).
OVERRIDE_SHARE = 0.05

# Edge-случаи: 2 % бюджета при `--include-edge`. Каждый вид получает свою долю
# поровну; вид попадает в `_meta.edge`, поэтому разбор падения начинается с него.
EDGE_KINDS = (
    "empty_description",
    "huge_description",
    "many_links",
    "unicode",
    "code_blocks",
    "html",
    "unknown_issue_type",
    "unknown_role",
    "all_null",
)

# Пул фраз описания. Часть фраз намеренно несёт сигналы эвристик
# (`refactor_markers`, `uncertainty`, `external_systems`), иначе параметры
# выродились бы в константу и полигон не проверял бы множитель.
_SENTENCES = (
    "Сейчас оператор вручную сверяет заказ с данными склада и тратит на это около 15 минут.",
    "Нужно сократить время обработки заявки до 2 минут и убрать повторный ввод данных.",
    "Затрагиваем сервис заказов и интеграцию с внешним провайдером доставки.",
    "В рамках доработки контракта API добавим поле delivery_slot и валидацию формата.",
    "Риск: часть заказов приходит без региона, поведение нужно уточнить у БА.",
    "Требуется миграция схемы БД и обратная совместимость со старой версией.",
    "Критерии приёмки: ошибок в логах нет, время ответа не более 300 мс.",
    "Декомпозиция: сначала меняем чтение, затем запись, затем включаем фича-тоггл.",
    "Проверяем сценарии: успешный заказ, отказ провайдера, пустой регион.",
    "Нужно добавить метрики и алерт на рост ошибок в течение часа.",
)

_ACCEPTANCE = (
    "- заявка обрабатывается не более 2 минут\n"
    "- ошибок в логах нет\n"
    "- покрытие тестами не ниже 80 %\n"
    "- повторный ввод данных отсутствует"
)
_GOAL = (
    "Сократить время обработки заявки и убрать ручной перенос данных "
    "между системами."
)
_TASK = (
    "1. Добавить чтение слота доставки\n"
    "2. Обновить маппинг для FE\n"
    "3. Покрыть сценарии тестами"
)
_TESTING = (
    "Проверить на стенде staging: успешный заказ, отказ провайдера, "
    "пустой регион. Регресс по оформлению заказа."
)

# Полный шаблон передачи SA → разработка: «все три группы» оси секций — это
# заполненный шаблон целиком, иначе ни одна задача не могла бы пройти
# REQUIRED-правила SA-02/SA-04/SA-05, и распределение вердиктов выродилось бы
# в 100 % BLOCKED (что и показал первый прогон полигона).
_FULL_SECTIONS = {
    "goal": _GOAL,
    "ba_requirements": (
        "Функциональные требования: оператор видит слот доставки, может "
        "изменить его до подтверждения заказа; отказ провайдера показывается "
        "понятным сообщением."
    ),
    "contract": (
        "POST /api/v1/delivery/slot: поле delivery_slot (ISO-8601), ответ 200 "
        "или 409 при занятом слоте. Обратная совместимость сохраняется."
    ),
    "description": (
        "Меняем чтение слота, затем запись, затем включаем фича-тоггл. "
        "Маппинг контрактов и маппинг для FE обновляются в том же релизе."
    ),
    "task": _TASK,
    "scenarios": (
        "Основной: слот свободен — заказ подтверждается. Альтернативный: слот "
        "занят — предлагаем ближайший. Ошибка провайдера — заказ остаётся в "
        "корзине, показываем сообщение."
    ),
    "acceptance_criteria": _ACCEPTANCE,
    "testing": _TESTING,
    "adjustments": "Версия 2: добавлен слот доставки после ревью БА.",
    "toggle": (
        "Риск поломки: низкий. Неопределённость: средняя. Оценка: 3. "
        "Фича-тоггл delivery_slot_v2, раскатка 5 % → 100 %."
    ),
}

# Чек-лист SA (SA-09) в полном снимке: агент фиксирует его отдельным полем,
# поэтому разделы описания не обязаны содержать все ключевые слова.
_FULL_SA_CHECKLIST = {
    "маппинг контрактов": True,
    "ошибки методов API": True,
    "доступы": True,
    "атрибуты": True,
    "фильтры": True,
    "маппинг для FE": True,
}

_SUMMARY_PREFIXES = ("E001", "E002", "E003")
_SUMMARY_ACTIONS = ("добавить", "исправить", "ускорить", "вынести", "проверить")
_SUMMARY_OBJECTS = (
    "слот доставки",
    "маппинг заказа",
    "расчёт стоимости",
    "экран корзины",
    "обработку отказа провайдера",
)

# Поля, которые проверяет каталог правил; часть из них иногда остаётся пустой,
# чтобы вердикт не был одинаковым у всех задач.
_FIELD_NULL_SHARE = 0.08
_NULLABLE_FIELDS = ("project", "team", "epic", "priority", "sprint", "story_points")


# ---------------------------------------------------------------------------
# Служебное
# ---------------------------------------------------------------------------


def _weighted(rng, pairs):
    """Взвешенный выбор из `[(value, weight), ...]` без numpy."""
    total = sum(weight for _value, weight in pairs)
    point = rng.random() * total
    upto = 0.0
    for value, weight in pairs:
        upto += weight
        if point <= upto:
            return value
    return pairs[-1][0]


def _percentile(values, fraction):
    """Перцентиль без интерполяции: детерминированно и без зависимостей."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * fraction))
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _json_line(payload):
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _emit(args, message):
    if not getattr(args, "quiet", False):
        print(message)


def _emit_json(args, payload):
    if getattr(args, "json", False):
        print(_json_line(payload))


def _fail(args, code, message):
    _emit(args, message)
    _emit_json(args, {"status": "blocked", "code": code, "message": message})
    return code


def _resolve_out(workdir, value):
    target = Path(str(value)).expanduser()
    if not target.is_absolute():
        target = Path(workdir) / target
    return target.resolve()


def _runs_root(workdir):
    return Path(workdir) / statemod.STATE_DIR / "runs"


def _is_inside(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _guard_out(workdir, target):
    """Запрет писать в прогоны рабочего проекта: полигон — не прогон задачи."""
    if _is_inside(target, _runs_root(workdir)):
        return (
            "[BLOCKED] synth: --out указывает в %s — полигон не пишет в прогоны "
            "рабочего проекта, выберите отдельный каталог" % _runs_root(workdir)
        )
    return None


# ---------------------------------------------------------------------------
# Источник распределений: выборка спринтов
# ---------------------------------------------------------------------------


def _sample_path(workdir, args):
    explicit = getattr(args, "sample", None)
    if explicit:
        return Path(str(explicit)).expanduser().resolve()
    return Path(workdir) / statemod.STATE_DIR / pathsmod.SAMPLE_RELATIVE


def _load_rows(workdir, args):
    """Прочитать строки выборки и отфильтровать по `--from-sprints`.

    `--from-sprints` принимает id спринтов Jira (`20365,20366`), а в выборке
    лежат имена (`T100-T102 26.16`). Соответствие берётся из
    `model.estimation-model.json → sources.sprints`; без модели фильтр по id
    разрешить нечем — это `[BLOCKED]`, а не тихое «взяли все строки».
    """
    path = _sample_path(workdir, args)
    if not path.is_file():
        return None, "[MISSING] synth: нет выборки спринтов %s" % path, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, "[MISSING] synth: %s не читается — %s" % (path, exc), None
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        return None, "[MISSING] synth: в %s нет строк rows[]" % path, None
    rows = [row for row in rows if isinstance(row, dict) and row.get("role")]

    sprints = sorted({str(row.get("sprint")) for row in rows if row.get("sprint")})
    requested = getattr(args, "from_sprints", None)
    selected = None
    if requested:
        model_path = (
            Path(workdir) / statemod.STATE_DIR / statemod.MODEL_RELATIVE
        )
        if not model_path.is_file():
            return (
                None,
                "[BLOCKED] synth: --from-sprints требует модель %s "
                "(id → имя спринта)" % model_path,
                None,
            )
        try:
            model = json.loads(model_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return None, "[MISSING] synth: модель не читается — %s" % exc, None
        id_to_name = {}
        for entry in (model.get("sources") or {}).get("sprints") or []:
            if isinstance(entry, dict) and entry.get("id") is not None:
                id_to_name[int(entry["id"])] = str(entry.get("name") or "")
        wanted, unknown = set(), []
        for token in str(requested).split(","):
            token = token.strip()
            if not token:
                continue
            try:
                sprint_id = int(token)
            except ValueError:
                unknown.append(token)
                continue
            name = id_to_name.get(sprint_id)
            if name:
                wanted.add(name)
            else:
                unknown.append(token)
        if unknown:
            return (
                None,
                "[BLOCKED] synth: неизвестные id спринтов %s — доступны %s"
                % (", ".join(unknown), ", ".join("%d" % key for key in sorted(id_to_name))),
                None,
            )
        selected = sorted(wanted)
        rows = [row for row in rows if str(row.get("sprint")) in wanted]
        if not rows:
            return (
                None,
                "[MISSING] synth: в выборке нет строк спринтов %s"
                % ", ".join(selected),
                None,
            )
    meta = {
        "sample_path": str(path),
        "rows_used": len(rows),
        "sprints_available": sprints,
        "sprints_selected": selected or sprints,
    }
    return rows, None, meta


def _distributions(rows):
    """Эмпирические пулы значений из выборки (только непустые)."""
    sp_pool = sorted(
        {
            int(row["sp"])
            for row in rows
            if isinstance(row.get("sp"), int) and not isinstance(row.get("sp"), bool)
        }
    )
    qa_pool = sorted(
        {
            int(row["qa_estimation"])
            for row in rows
            if isinstance(row.get("qa_estimation"), int)
            and not isinstance(row.get("qa_estimation"), bool)
            and int(row["qa_estimation"]) > 0
        }
    )
    if not sp_pool:
        sp_pool = [1, 2, 3, 5, 8]
    if not qa_pool:
        qa_pool = [1, 2, 3]
    return sp_pool, qa_pool


# ---------------------------------------------------------------------------
# Генерация одного снимка
# ---------------------------------------------------------------------------


def _description(rng, length):
    if length <= 0:
        return ""
    parts = []
    total = 0
    while total < length:
        sentence = _SENTENCES[rng.randrange(len(_SENTENCES))]
        parts.append(sentence)
        total += len(sentence) + 1
    text = " ".join(parts)
    text = text[:length]
    if len(text) < length:
        text = text + "." * (length - len(text))
    if text.endswith(" "):
        text = text[:-1] + "."
    return text


def _sections(rng, mode):
    """Секции снимка: ключи — как в шаблоне, группы — acceptance/scope/dod."""
    if mode == "none":
        return {}
    if mode == "all":
        return dict(_FULL_SECTIONS)
    groups = {
        "scope": {"goal": _GOAL, "task": _TASK},
        "acceptance": {"acceptance_criteria": _ACCEPTANCE},
        "dod": {"testing": _TESTING},
    }
    names = ["scope", "acceptance", "dod"]
    count = rng.choice((1, 2))
    names = sorted(rng.sample(names, count))
    result = {}
    for name in names:
        result.update(groups[name])
    return result


def _labels(rng):
    mode = _weighted(rng, [(case[0], case[2]) for case in LABEL_CASES])
    for name, values, _weight in LABEL_CASES:
        if name != mode:
            continue
        if values is not None:
            return list(values), name
        if name == "mixed":
            return list(_MIXED_LABELS[rng.randrange(len(_MIXED_LABELS))]), name
        return list(_JUNK_LABELS[rng.randrange(len(_JUNK_LABELS))]), name
    return [], "none"


def _work_kind(role, issue_type):
    """Вид работ, совместимый с бакетами модели.

    `estimate` при явном `work_kind` ищет бакет ровно по `(role, work_kind)` и
    падает, если его нет. Поэтому вид работ выводится из роли и типа так, как
    это сделал бы агент: баг → `bugfix`, техдолг → `tech_debt`, QA по
    Feature/Ошибке → `testing`, остальное → `implementation`.
    """
    kind = str(issue_type or "").strip().casefold()
    if role == "QA":
        return "testing" if kind in ("feature", "ошибка", "bug") else "implementation"
    if role in ("BE", "FE", "OTHER"):
        if kind in ("ошибка", "bug"):
            return "bugfix"
        if kind in ("tech debt", "techdebt", "техдолг"):
            return "tech_debt"
    return "implementation"


def _summary(rng):
    return "%s — %s — %s" % (
        rng.choice(_SUMMARY_PREFIXES),
        rng.choice(_SUMMARY_ACTIONS),
        rng.choice(_SUMMARY_OBJECTS),
    )


def _build_context(rng, index, row, sp_pool, qa_pool, seed, sprint_names,
                   forced=None):
    """Один снимок задачи.

    `forced` — тройка `(role, issue_type, work_kind)` из покрытия бакетов
    модели. Она перекрывает оси выборки, но не трогает ГПСЧ: количество
    случайных чисел на снимок одно и то же, поэтому остальные снимки датасета
    остаются побайтно теми же, а `--seed` по-прежнему детерминирован.
    """
    role = str(row.get("role") or "OTHER")
    issue_type = str(row.get("issue_type") or "Задача")
    labels, labels_mode = _labels(rng)

    # Оси, заданные квотой поверх выборки: неизвестная роль (2 %) и тип, которого
    # в выборке нет, но который есть в словаре скилла (2 %). Без этого полигон
    # проверял бы только встреченные значения и не ловил бы «роль вне словаря».
    if rng.random() < UNKNOWN_ROLE_SHARE:
        role = UNKNOWN_ROLES[rng.randrange(len(UNKNOWN_ROLES))]
    for tail_type, tail_share in TYPE_TAIL:
        if rng.random() < tail_share:
            issue_type = tail_type
    if forced is not None:
        role, issue_type, _forced_kind = forced

    # sp: значение строки, иначе из эмпирического пула; затем квота 5 % null.
    sp = row.get("sp")
    if not isinstance(sp, int) or isinstance(sp, bool):
        sp = rng.choice(sp_pool)
    if rng.random() < 0.05:
        sp = None

    # qa_estimation: значение строки, иначе из пула; 30 % null, 2 % буквальный 0.
    # Буквальный 0 в выборке считается «не заполнено» и уходит в пул: иначе квота
    # 2 % складывалась бы с историческими нулями и переставала быть квотой.
    qa = row.get("qa_estimation")
    if not isinstance(qa, int) or isinstance(qa, bool) or qa <= 0:
        qa = rng.choice(qa_pool)
    quota = rng.random()
    if quota < 0.30:
        qa = None
    elif quota < 0.32:
        qa = 0

    description_len = rng.choice(DESCRIPTION_LENGTHS)
    sections_mode = SECTION_MODES[rng.randrange(len(SECTION_MODES))]
    links = _weighted(rng, LINK_CASES)
    components = _weighted(rng, COMPONENT_CASES)
    summary = _summary(rng)
    description = _description(rng, description_len)

    fields = {
        "project": rng.choice(("E001", "E002", "E003")),
        "team": rng.choice(("T100-T102", "T200-T202", "T300")),
        "issue_type": issue_type,
        "summary": summary,
        "epic": "E001-%d" % (19000 + rng.randrange(500)),
        "priority": rng.choice(("High", "Medium", "Low")),
        "role": role,
        "sprint": str(row.get("sprint") or rng.choice(sprint_names)),
        "story_points": sp,
        "qa_estimation": qa,
        "issuelinks": links,
        "components": ["svc-%02d" % (number + 1) for number in range(components)],
        "status": row.get("status"),
    }
    for name in _NULLABLE_FIELDS:
        if rng.random() < _FIELD_NULL_SHARE:
            fields[name] = None
    if rng.random() < 0.05:
        fields["role"] = None

    context = {
        "task_key": "SYN-%06d" % index,
        "issue_type": issue_type,
        "role": role,
        "work_kind": (
            _forced_kind if forced is not None else _work_kind(role, issue_type)
        ),
        "sp": sp,
        "qa_estimation": qa,
        "labels": labels,
        "summary": summary,
        "description": description,
        "components": fields["components"],
        "issuelinks": links,
        "fields": fields,
        "sections": _sections(rng, sections_mode),
        "sources": [
            {
                "system": "jira",
                "kind": "issue",
                "ref": str(row.get("key") or ""),
                "source_kind": "synthetic",
            }
        ],
    }
    # Связи: TPL-08 читает `links`, а эвристики — `issuelinks`. В реальном
    # снимке есть оба представления, поэтому полигон заполняет оба.
    if links:
        context["links"] = [
            {"key": "E001-%d" % (20000 + rng.randrange(900)), "type": "relates"}
            for _ in range(links)
        ]
        fields["links"] = context["links"]
    if sections_mode == "all" and rng.random() < 0.7:
        context["sa_checklist"] = dict(_FULL_SA_CHECKLIST)

    override = rng.random() < OVERRIDE_SHARE
    if override:
        values = {}
        force_extreme = rng.random() < 0.5
        extreme_names = set()
        if force_extreme:
            extreme_names.add(paramsmod.PARAM_NAMES[rng.randrange(3)])
        for name in paramsmod.PARAM_NAMES:
            if name in extreme_names or rng.random() < 0.2:
                values[name] = rng.choice((0.0, 1.0))
            else:
                values[name] = round(rng.uniform(0.0, 1.0), 2)
        context.update(values)

    meta = {
        "case_id": context["task_key"],
        "index": index,
        "seed": seed,
        "sprint": fields["sprint"],
        "source_key": row.get("key"),
        "expected_sp": row.get("sp"),
        "edge": None,
        "axes": {
            "issue_type": context["issue_type"],
            "role": context["role"],
            "work_kind": context["work_kind"],
            "sp": context["sp"],
            "qa_estimation": context["qa_estimation"],
            "description_len": len(context["description"]),
            "sections": sections_mode,
            "labels": labels_mode,
            "issuelinks": links,
            "components": components,
            "override": override,
        },
    }
    context["_meta"] = meta
    return context


def _apply_edge(context, kind, rng):
    """Применить edge-случай к готовому снимку; `_meta.edge` — метка вида."""
    meta = context["_meta"]
    meta["edge"] = kind
    if kind == "empty_description":
        context["description"] = ""
    elif kind == "huge_description":
        block = _description(rng, 4000)
        context["description"] = (block * 26)[: 100 * 1024]
    elif kind == "many_links":
        context["issuelinks"] = 100
        context["fields"]["issuelinks"] = 100
    elif kind == "unicode":
        context["summary"] = "🚚 Доставка — 到着 — تحسين — обновить слот 🧩"
        context["description"] = (
            "Юникод и эмодзи: 🚀 ✅ 中文 العربية עברית. "
            "Проверяем, что обрезка и JSON не ломаются на многобайтовых символах."
        )
    elif kind == "code_blocks":
        context["description"] = (
            "Пример запроса:\n```json\n{\"slot\": \"2026-11-20T10:00:00Z\"}\n```\n"
            "Ответ должен содержать `delivery_slot` и код 200.\n"
            "```sql\nSELECT id FROM orders WHERE region IS NULL;\n```"
        )
    elif kind == "html":
        context["description"] = (
            "<div class=\"panel\"><h3>Цель</h3><p>Ускорить обработку "
            "<b>заявки</b> до 2 минут.</p><ul><li>слот доставки</li>"
            "<li>валидация региона</li></ul></div>"
        )
    elif kind == "unknown_issue_type":
        context["issue_type"] = "Epic Story"
        context["fields"]["issue_type"] = "Epic Story"
        context["work_kind"] = "implementation"
    elif kind == "unknown_role":
        role = UNKNOWN_ROLES[rng.randrange(len(UNKNOWN_ROLES))]
        context["role"] = role
        context["fields"]["role"] = role
        context["work_kind"] = "implementation"
    elif kind == "all_null":
        context.update(
            {
                "issue_type": None,
                "role": None,
                "work_kind": None,
                "sp": None,
                "qa_estimation": None,
                "labels": [],
                "summary": None,
                "description": "",
                "components": [],
                "issuelinks": None,
                "sections": {},
            }
        )
        context["fields"] = {
            "project": None,
            "team": None,
            "issue_type": None,
            "summary": None,
            "epic": None,
            "priority": None,
            "role": None,
            "sprint": None,
            "story_points": None,
            "qa_estimation": None,
            "issuelinks": None,
            "components": None,
        }
    return context


def _coverage_triples(model):
    """Тройки `(role, issue_type, work_kind)` бакетов модели — цель покрытия.

    Порядок фиксирован (сортировка), поэтому план покрытия не зависит от
    порядка бакетов в `estimation-model.json`.
    """
    triples = set()
    for bucket in (model or {}).get("buckets") or []:
        if not isinstance(bucket, dict):
            continue
        role = bucket.get("role")
        issue_type = bucket.get("issue_type")
        work_kind = bucket.get("work_kind")
        values = (role, issue_type, work_kind)
        if not all(isinstance(item, str) and item.strip() for item in values):
            continue
        triples.add((role.strip(), issue_type.strip(), work_kind.strip()))
    return sorted(triples)


def _coverage_plan(triples, quota, count, edge_count):
    """Индекс снимка → тройка модели, которую он обязан показать.

    Раскладка равномерная (`n * budget // slots`), а не блоком в начале: датасет
    не превращается в «первые 400 задач — покрытие, остальные — шум», и доли
    остальных осей остаются однородными по всему файлу. Бюджет — весь датасет
    без edge-хвоста: edge-случаи намеренно ломают оси, и покрытие они бы портили.
    """
    quota = int(quota or 0)
    budget = int(count) - int(edge_count or 0)
    if quota <= 0 or budget <= 0 or not triples:
        return {}
    slots = min(len(triples) * quota, budget)
    plan = {}
    for number in range(slots):
        plan[(number * budget) // slots] = triples[number % len(triples)]
    return plan


def _coverage_summary(contexts, triples, plan, quota=0):
    """Фактическое покрытие троек в готовом датасете — для `manifest.json`."""
    counts = {triple: 0 for triple in triples}
    for context in contexts:
        meta = context.get("_meta") or {}
        if meta.get("edge"):
            continue
        key = (
            str(context.get("role")),
            str(context.get("issue_type")),
            str(context.get("work_kind")),
        )
        if key in counts:
            counts[key] = counts[key] + 1
    name = lambda triple: "%s/%s/%s" % triple
    return {
        "enabled": bool(triples),
        "quota": int(quota or 0),
        "triples": len(triples),
        "planned": len(plan),
        "min_per_triple": min(counts.values()) if counts else 0,
        "counts": {name(triple): counts[triple] for triple in triples},
    }


def _model_or_empty(workdir):
    """Модель для покрытия: отсутствие файла — не ошибка генерации.

    `trr synth` умеет работать и без модели (тогда покрытия нет, а `manifest`
    пишет `model: null`): полигон не должен требовать модели ради самой
    генерации, но и молча подсовывать чужие тройки не должен.
    """
    path = Path(workdir) / statemod.STATE_DIR / statemod.MODEL_RELATIVE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def generate(workdir, count, seed=42, from_sprints=None, include_edge=False,
             sample=None, coverage_all_buckets=True,
             coverage_quota=COVERAGE_QUOTA_DEFAULT):
    """Сгенерировать `count` снимков. Возвращает `(contexts, manifest)`.

    Чистая функция по отношению к диску: ничего не пишет, только читает
    выборку (и модель для `--from-sprints`).

    `coverage_all_buckets` — включить покрытие троек модели (по умолчанию да);
    `coverage_quota` — сколько снимков на каждую тройку (по умолчанию 20).
    """

    class _Args(object):
        pass

    args = _Args()
    args.sample = sample
    args.from_sprints = from_sprints
    rows, error, meta = _load_rows(workdir, args)
    if error:
        raise ValueError(error)
    sp_pool, qa_pool = _distributions(rows)
    sprint_names = sorted({str(row.get("sprint")) for row in rows if row.get("sprint")})
    rng = random.Random(seed)

    edge_count = (
        max(len(EDGE_KINDS), int(round(count * 0.02))) if include_edge else 0
    )
    edge_start = count - edge_count
    model = _model_or_empty(workdir) if coverage_all_buckets else {}
    triples = _coverage_triples(model) if coverage_all_buckets else []
    plan = (
        _coverage_plan(triples, coverage_quota, count, edge_count)
        if coverage_all_buckets
        else {}
    )
    contexts = []
    for index in range(count):
        row = rows[rng.randrange(len(rows))]
        context = _build_context(
            rng, index + 1, row, sp_pool, qa_pool, seed, sprint_names,
            forced=plan.get(index),
        )
        if index >= edge_start:
            kind = EDGE_KINDS[(index - edge_start) % len(EDGE_KINDS)]
            context = _apply_edge(context, kind, rng)
            # Оси описывают фактический снимок: edge меняет длину, связи и тип.
            axes = context["_meta"]["axes"]
            axes["description_len"] = len(context.get("description") or "")
            axes["issuelinks"] = context.get("issuelinks")
            axes["issue_type"] = context.get("issue_type")
            axes["role"] = context.get("role")
            axes["work_kind"] = context.get("work_kind")
            axes["components"] = len(context.get("components") or [])
        contexts.append(context)

    manifest = _manifest(
        workdir, contexts, seed, meta, include_edge,
        model=model, triples=triples, plan=plan,
        coverage_quota=coverage_quota,
    )
    return contexts, manifest


def _counter(contexts, getter):
    counts = {}
    for context in contexts:
        value = getter(context)
        key = "null" if value is None else str(value)
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _manifest(workdir, contexts, seed, source_meta, include_edge, model=None,
              triples=(), plan=None, coverage_quota=0):
    model_version, model_checksum = None, None
    if isinstance(model, dict) and model:
        model_version = model.get("version")
        model_checksum = model.get("checksum")
    else:
        model_path = Path(workdir) / statemod.STATE_DIR / statemod.MODEL_RELATIVE
        if model_path.is_file():
            try:
                payload = json.loads(model_path.read_text(encoding="utf-8"))
                model_version = payload.get("version")
                model_checksum = payload.get("checksum")
            except (OSError, ValueError):
                pass
    meta = lambda context: context["_meta"]
    return {
        "generator": "trr synth",
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "count": len(contexts),
        "include_edge": bool(include_edge),
        "edge_count": sum(1 for context in contexts if context["_meta"]["edge"]),
        "source": source_meta,
        "model": {"version": model_version, "checksum": model_checksum},
        "coverage": _coverage_summary(contexts, list(triples), plan or {}, coverage_quota),
        "distributions": {
            "issue_type": _counter(contexts, lambda c: c.get("issue_type")),
            "role": _counter(contexts, lambda c: c.get("role")),
            "work_kind": _counter(contexts, lambda c: c.get("work_kind")),
            "sp": _counter(contexts, lambda c: c.get("sp")),
            "qa_estimation": _counter(contexts, lambda c: c.get("qa_estimation")),
            "description_len": _counter(contexts, lambda c: meta(c)["axes"]["description_len"]),
            "sections": _counter(contexts, lambda c: meta(c)["axes"]["sections"]),
            "labels": _counter(contexts, lambda c: meta(c)["axes"]["labels"]),
            "issuelinks": _counter(contexts, lambda c: meta(c)["axes"]["issuelinks"]),
            "components": _counter(contexts, lambda c: meta(c)["axes"]["components"]),
            "override": _counter(contexts, lambda c: meta(c)["axes"]["override"]),
            "edge": _counter(contexts, lambda c: meta(c)["edge"]),
        },
        "files": {"contexts": "contexts.jsonl", "manifest": "manifest.json"},
    }


def write_dataset(contexts, manifest, out_dir):
    """Записать `contexts.jsonl` и `manifest.json`; вернуть сводку файлов."""
    out_dir.mkdir(parents=True, exist_ok=True)
    contexts_path = out_dir / "contexts.jsonl"
    buffer = []
    for context in contexts:
        buffer.append(_json_line(context))
        buffer.append("\n")
    data = "".join(buffer).encode("utf-8")
    contexts_path.write_bytes(data)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_bytes(
        (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    return {
        "contexts": str(contexts_path),
        "manifest": str(manifest_path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


# ---------------------------------------------------------------------------
# Харнесс: check + estimate in-process
# ---------------------------------------------------------------------------


def _load_contexts(directory, limit=None):
    path = Path(directory) / "contexts.jsonl"
    if not path.is_file():
        raise ValueError("[MISSING] synth-run: нет %s" % path)
    contexts = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                context = json.loads(line)
            except ValueError as exc:
                raise ValueError(
                    "[MISSING] synth-run: %s: битая строка — %s" % (path, exc)
                )
            if isinstance(context, dict):
                contexts.append(context)
            if limit is not None and len(contexts) >= limit:
                break
    if not contexts:
        raise ValueError("[MISSING] synth-run: %s пуст" % path)
    return contexts


def _load_model(workdir):
    path = Path(workdir) / statemod.STATE_DIR / statemod.MODEL_RELATIVE
    if not path.is_file():
        raise ValueError("[MISSING] synth-run: нет модели %s" % path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("[MISSING] synth-run: модель не читается — %s" % exc)


def _load_cfg(workdir):
    path = configmod.config_path(workdir)
    if not path.is_file():
        return None
    try:
        return configmod.load_config(path, on_warning=lambda line: None)
    except configmod.ConfigError:
        return None


def _dataset_seed(directory):
    """`seed` из `manifest.json` датасета (None — манифеста нет или он битый).

    Полигон пишет seed в манифест генерации; `summary.json` берёт его оттуда,
    чтобы `synth_runs.seed` в БД не приходилось спрашивать у пользователя.
    """
    path = Path(directory) / "manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    seed = payload.get("seed") if isinstance(payload, dict) else None
    if isinstance(seed, int) and not isinstance(seed, bool):
        return seed
    return None


def _schemas():
    loaded = {}
    for name in ("validation", "estimate"):
        loaded[name] = schema_lite.load_schema(configmod.SCHEMAS_DIR, name)
    return loaded


def _bucket_index(model):
    """`(role, issue_type, work_kind) → bucket` из модели."""
    index = {}
    for bucket in model.get("buckets") or []:
        if not isinstance(bucket, dict):
            continue
        key = (
            str(bucket.get("role")),
            str(bucket.get("issue_type")),
            str(bucket.get("work_kind")),
        )
        index[key] = bucket
    return index


def _bucket_from_source(source):
    """Разобрать `estimation-model:<V>:<ROLE>/<ISSUE_TYPE>/<WORK_KIND>`."""
    if not source.startswith("estimation-model:"):
        return None
    parts = source.split(":", 2)[-1].split("/")
    if len(parts) < 3:
        return None
    return {
        "role": parts[0],
        "issue_type": "/".join(parts[1:-1]),
        "work_kind": parts[-1],
    }


def _bucket_of(estimate_payload):
    """Бакет задачи из provenance первой роли: `estimation-model:V:ROLE/TYPE/KIND`."""
    for entry in estimate_payload.get("roles") or []:
        for item in entry.get("provenance") or []:
            bucket = _bucket_from_source(str(item.get("source") or ""))
            if bucket:
                return bucket
    return None


def _all_buckets(estimate_payload):
    found = set()
    for entry in estimate_payload.get("roles") or []:
        for item in entry.get("provenance") or []:
            source = str(item.get("source") or "")
            bucket = _bucket_from_source(source)
            if bucket:
                found.add(
                    "%s/%s/%s"
                    % (bucket["role"], bucket["issue_type"], bucket["work_kind"])
                )
    return sorted(found)


def _run_case(context, model, rules, cfg, schemas, bucket_index):
    """Один прогон: validation → estimate → запись метрик. Исключения — в `error`."""
    started = time.perf_counter()
    meta = context.get("_meta") or {}
    record = {
        "case_id": str(meta.get("case_id") or context.get("task_key") or ""),
        "verdict": None,
        "checks_total": 0,
        "checks_failed": 0,
        "gaps_total": 0,
        "expected": None,
        "range": None,
        "roles": [],
        "params": None,
        "bucket": None,
        "buckets_all": [],
        "expected_sp": meta.get("expected_sp"),
        "edge": meta.get("edge"),
        "duration_ms": 0.0,
        "error": None,
        "unestimable": False,
        "schema_errors": [],
    }
    try:
        validation = checkmod.run_checks(context, rules, False)
        record["verdict"] = validation.get("verdict")
        checks = validation.get("checks") or []
        record["checks_total"] = len(checks)
        record["checks_failed"] = sum(
            1 for item in checks if item.get("status") in ("FAIL", "UNKNOWN")
        )
        record["gaps_total"] = len(validation.get("gaps") or [])
        record["schema_errors"].extend(
            "validation: %s" % message
            for message in schema_lite.validate(validation, schemas["validation"])
        )

        estimate_payload = estimatemod.estimate(
            validation, model, context=context, cfg=cfg
        )
        total = estimate_payload.get("total") or {}
        record["expected"] = total.get("expected")
        record["range"] = total.get("range")
        record["roles"] = [
            {
                "role": entry.get("role"),
                "expected": entry.get("expected"),
                "range": entry.get("range"),
            }
            for entry in estimate_payload.get("roles") or []
        ]
        params = estimate_payload.get("params") or {}
        record["params"] = {
            "weight": params.get("weight"),
            "heat": params.get("heat"),
            "connectivity": params.get("connectivity"),
            "source": params.get("source"),
            "multiplier": params.get("multiplier"),
        }
        bucket = _bucket_of(estimate_payload)
        if bucket:
            entry = bucket_index.get(
                (bucket["role"], bucket["issue_type"], bucket["work_kind"])
            )
            bucket["reference"] = entry.get("reference") if entry else None
        record["bucket"] = bucket
        record["buckets_all"] = _all_buckets(estimate_payload)
        record["schema_errors"].extend(
            "estimate: %s" % message
            for message in schema_lite.validate(estimate_payload, schemas["estimate"])
        )
    except Exception as exc:  # noqa: BLE001 — полигон измеряет и падения тоже
        record["error"] = "%s: %s" % (type(exc).__name__, exc)
        record["traceback"] = traceback.format_exc(limit=6)
        # `estimate` законно отказывается, когда у роли нет ни одного бакета
        # (например DEVOPS: роль есть в словаре, данных в модели нет). Это не
        # дефект харнесса, а известное ограничение модели — считаем отдельно.
        if isinstance(exc, ValueError) and "ни одной роли с данными" in str(exc):
            record["unestimable"] = True
    finally:
        record["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    return record


def _deterministic_view(record):
    return {
        key: value
        for key, value in record.items()
        if key not in ("duration_ms", "traceback")
    }


def _probe_contexts():
    """Пробы монотонности: меняется ровно один параметр, остальные фиксированы."""
    skeletons = (
        ("BA", "Задача", "implementation"),
        ("BE", "Feature", "implementation"),
        ("FE", "Tech Debt", "tech_debt"),
    )
    levels = (0.0, 0.25, 0.5, 0.75, 1.0)
    probes = []
    for param in paramsmod.PARAM_NAMES:
        for fixed in (0.0, 0.5):
            for role, issue_type, work_kind in skeletons:
                for level in levels:
                    overrides = {
                        name: (level if name == param else fixed)
                        for name in paramsmod.PARAM_NAMES
                    }
                    task_key = "PROBE-%s-%s-%s-%s" % (
                        param,
                        "0" if fixed == 0.0 else "5",
                        role,
                        ("%.2f" % level).replace(".", ""),
                    )
                    context = {
                        "task_key": task_key,
                        "issue_type": issue_type,
                        "role": role,
                        "work_kind": work_kind,
                        "sp": 3,
                        "qa_estimation": 2,
                        "labels": [],
                        "summary": "Проба монотонности — проверить параметр — %s" % param,
                        "description": _description(random.Random(0), 500),
                        "components": ["svc-01", "svc-02"],
                        "issuelinks": 2,
                        "fields": {
                            "project": "E001",
                            "team": "T100-T102",
                            "issue_type": issue_type,
                            "summary": "Проба монотонности",
                            "epic": "E001-19000",
                            "priority": "Medium",
                            "role": role,
                            "sprint": "T100-T102 26.16",
                            "story_points": 3,
                            "qa_estimation": 2,
                            "issuelinks": 2,
                            "components": ["svc-01", "svc-02"],
                        },
                        "sections": {
                            "goal": _GOAL,
                            "task": _TASK,
                            "acceptance_criteria": _ACCEPTANCE,
                            "testing": _TESTING,
                        },
                        "sources": [],
                        "_meta": {
                            "case_id": task_key,
                            "probe": {
                                "param": param,
                                "level": level,
                                "fixed": fixed,
                                "role": role,
                                "issue_type": issue_type,
                            },
                        },
                    }
                    context.update(overrides)
                    probes.append(context)
    return probes


def _monotonicity(model, rules, cfg):
    """Проверить, что `expected` не убывает при росте одного параметра."""
    groups = {}
    for context in _probe_contexts():
        probe = context["_meta"]["probe"]
        key = (probe["param"], probe["fixed"], probe["role"], probe["issue_type"])
        groups.setdefault(key, []).append((probe["level"], context))

    violations = 0
    worst = None
    checked = 0
    for key in sorted(groups):
        items = sorted(groups[key], key=lambda pair: pair[0])
        previous = None
        for level, context in items:
            try:
                validation = checkmod.run_checks(context, rules, False)
                payload = estimatemod.estimate(
                    validation, model, context=context, cfg=cfg
                )
                expected = payload["total"]["expected"]
            except Exception as exc:  # noqa: BLE001
                violations += 1
                if worst is None:
                    worst = {
                        "group": "%s/%s/%s/%s" % key,
                        "error": "%s: %s" % (type(exc).__name__, exc),
                    }
                continue
            checked += 1
            if previous is not None and expected < previous[1]:
                violations += 1
                drop = previous[1] - expected
                if worst is None or drop > worst.get("drop", 0):
                    worst = {
                        "group": "%s/%s/%s/%s" % key,
                        "from_level": previous[0],
                        "from_expected": previous[1],
                        "to_level": level,
                        "to_expected": expected,
                        "drop": drop,
                    }
            previous = (level, expected)
    return {
        "param_groups": len(groups),
        "probes": checked,
        "violations": violations,
        "worst": worst,
        "note": "меняется ровно один параметр; остальные зафиксированы 0.0 и 0.5",
    }


def _scale_index(value):
    try:
        return SCALE.index(int(value))
    except (ValueError, TypeError):
        return None


def _summarize(records, elapsed, model, contexts, determinism):
    total = len(records)
    ok = sum(1 for item in records if item["verdict"] == "OK")
    warn = sum(1 for item in records if item["verdict"] == "WARN")
    blocked = sum(1 for item in records if item["verdict"] == "BLOCKED")
    errors = [item for item in records if item["error"]]
    unestimable = [item for item in errors if item.get("unestimable")]
    unexpected = [item for item in errors if not item.get("unestimable")]

    schema_failures = [item for item in records if item["schema_errors"]]
    # Шкала и диапазон — контракт КАЖДОЙ роли (`roles[].expected` enum шкалы).
    # `total.expected` — сумма ролей, она законно может не лежать на шкале
    # (3+3+2=8, 5+3+2+2=12), поэтому отдельно и только справочно.
    scale_violations = []
    range_violations = []
    for item in records:
        for role in item.get("roles") or []:
            expected = role.get("expected")
            span = role.get("range")
            if expected is not None and expected not in SCALE:
                scale_violations.append(
                    {"case_id": item["case_id"], "role": role.get("role"), "expected": expected}
                )
            if (
                expected is not None
                and isinstance(span, list)
                and len(span) == 2
                and not (span[0] <= expected <= span[1])
            ):
                range_violations.append(
                    {
                        "case_id": item["case_id"],
                        "role": role.get("role"),
                        "expected": expected,
                        "range": span,
                    }
                )
        # Сумма ролей тоже обязана попадать в свой диапазон.
        expected, span = item["expected"], item["range"]
        if (
            expected is not None
            and isinstance(span, list)
            and len(span) == 2
            and not (span[0] <= expected <= span[1])
        ):
            range_violations.append(
                {
                    "case_id": item["case_id"],
                    "role": "total",
                    "expected": expected,
                    "range": span,
                }
            )
    total_off_scale = [
        item
        for item in records
        if item["expected"] is not None and item["expected"] not in SCALE
    ]
    param_violations = []
    for item in records:
        params = item["params"]
        if not params:
            continue
        for name in paramsmod.PARAM_NAMES:
            value = params.get(name)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or math.isnan(float(value))
                or not (0.0 <= float(value) <= 1.0)
            ):
                param_violations.append({"case_id": item["case_id"], "param": name, "value": value})
                break

    model_buckets = _bucket_index(model)
    hit = set()
    for item in records:
        hit.update(item.get("buckets_all") or [])
    all_names = sorted(
        "%s/%s/%s" % key for key in model_buckets
    )
    # `buckets_all` может содержать имена, которых нет в модели (например
    # источник провенанса от другой версии модели). `hit` считаем только по
    # бакетам модели, иначе `hit + missed != total`.
    hit_names = sorted(set(hit) & set(all_names))
    missed = [name for name in all_names if name not in hit_names]

    # Бакеты, до которых `estimate` дотягивается. Раньше выбор шёл только по
    # (role, work_kind), поэтому на пару был достижим один бакет — самый крупный
    # по `n`. Теперь спрашиваем сам селектор: для каждой тройки модели
    # (role, issue_type, work_kind) он обязан вернуть именно её (уровень exact).
    reachable = set()
    for key in sorted(model_buckets):
        chosen, _level = estimatemod.select_bucket(
            model.get("buckets") or [], key[0], key[2], True, issue_type=key[1]
        )
        if chosen is None:
            continue
        reachable.add(
            "%s/%s/%s"
            % (chosen.get("role"), chosen.get("issue_type"), chosen.get("work_kind"))
        )

    expected_values = [item["expected"] for item in records if item["expected"] is not None]
    role_expected = [
        role["expected"]
        for item in records
        for role in (item.get("roles") or [])
        if role.get("expected") is not None
    ]
    histogram = {}
    for value in expected_values:
        histogram[str(value)] = histogram.get(str(value), 0) + 1
    role_histogram = {}
    for value in role_expected:
        role_histogram[str(value)] = role_histogram.get(str(value), 0) + 1
    step_histogram = {}
    compared = 0
    different = 0
    for item in records:
        sampled = item.get("expected_sp")
        if item["expected"] is None or sampled is None:
            continue
        left, right = _scale_index(item["expected"]), _scale_index(sampled)
        if left is None or right is None:
            continue
        compared += 1
        distance = abs(left - right)
        if distance:
            different += 1
            step_histogram[str(distance)] = step_histogram.get(str(distance), 0) + 1

    durations = [item["duration_ms"] for item in records]
    return {
        "total": total,
        "ok": ok,
        "warn": warn,
        "blocked": blocked,
        "errors": len(errors),
        "unestimable": len(unestimable),
        "unexpected_errors": len(unexpected),
        "error_examples": [
            {"case_id": item["case_id"], "error": item["error"], "traceback": item.get("traceback")}
            for item in errors[:3]
        ],
        "schema_failures": {
            "cases": len(schema_failures),
            "examples": [
                {"case_id": item["case_id"], "errors": item["schema_errors"][:3]}
                for item in schema_failures[:3]
            ],
        },
        "scale_violations": {
            "cases": len(scale_violations),
            "examples": scale_violations[:3],
        },
        "range_violations": {
            "cases": len(range_violations),
            "examples": range_violations[:3],
        },
        "total_off_scale": {
            "cases": len(total_off_scale),
            "note": "сумма ролей законно может не лежать на шкале; "
            "не инвариант, справочно",
            "examples": [
                {"case_id": item["case_id"], "expected": item["expected"]}
                for item in total_off_scale[:3]
            ],
        },
        "param_violations": {
            "cases": len(param_violations),
            "examples": param_violations[:3],
        },
        "determinism": determinism,
        "buckets": {
            "total": len(all_names),
            "hit": len(hit_names),
            "missed": missed,
            "reachable": len(reachable),
            "unreachable": [name for name in all_names if name not in reachable],
            "note": "hit — бакеты, встреченные в датасете; reachable — селектор "
            "возвращает бакет на его собственной тройке; probe — end-to-end проба "
            "каждого бакета модели. hit < reachable, когда генератор не производит "
            "такую комбинацию осей (это ограничение датасета, не селектора)",
        },
        "distribution": {
            "histogram": {key: histogram[key] for key in sorted(histogram, key=int)},
            "histogram_roles": {
                key: role_histogram[key] for key in sorted(role_histogram, key=int)
            },
            "mean": round(statistics.mean(expected_values), 3) if expected_values else None,
            "median": statistics.median(expected_values) if expected_values else None,
            "multi_role_cases": sum(
                1 for item in records if len(item.get("roles") or []) > 1
            ),
            "compared_with_sample": compared,
            "differs_from_sample": different,
            "differs_share": round(different / compared, 4) if compared else None,
            "step_histogram": {
                key: step_histogram[key] for key in sorted(step_histogram, key=int)
            },
        },
        "timing": {
            "total_s": round(elapsed, 3),
            "per_task_ms": {
                "p50": round(_percentile(durations, 0.50), 3),
                "p95": round(_percentile(durations, 0.95), 3),
                "mean": round(statistics.mean(durations), 3) if durations else None,
            },
        },
        "model": {
            "version": model.get("version"),
            "checksum": model.get("checksum"),
        },
        "cases_read": len(contexts),
    }


def _bucket_probe_context(role, issue_type, work_kind, index):
    """Минимальный снимок ровно под одну тройку модели — проба достижимости.

    Задача не из `contexts.jsonl`: она нужна, чтобы доказать end-to-end, что
    `check + estimate` возвращают ИМЕННО этот бакет, а не соседний по роли.
    """
    return {
        "task_key": "PROBE-BUCKET-%02d" % index,
        "issue_type": issue_type,
        "role": role,
        "work_kind": work_kind,
        "sp": 3,
        "qa_estimation": 2,
        "labels": [],
        "summary": "Проба бакета — проверить выбор — %s/%s/%s"
        % (role, issue_type, work_kind),
        "description": _description(random.Random(0), 500),
        "components": ["svc-01", "svc-02"],
        "issuelinks": 2,
        "fields": {
            "project": "E001",
            "team": "T100-T102",
            "issue_type": issue_type,
            "summary": "Проба бакета",
            "epic": "E001-19000",
            "priority": "Medium",
            "role": role,
            "sprint": "T100-T102 26.16",
            "story_points": 3,
            "qa_estimation": 2,
            "issuelinks": 2,
            "components": ["svc-01", "svc-02"],
        },
        "sections": {},
        "sources": [],
        "_meta": {
            "case_id": "PROBE-BUCKET-%02d" % index,
            "probe": {"role": role, "issue_type": issue_type, "work_kind": work_kind},
        },
    }


def _bucket_coverage(model, rules, cfg):
    """Прогнать по пробе на каждый бакет модели и вернуть покрытие.

    `hit` — сколько бакетов `estimate` реально вернул на своей же тройке;
    `missed` — какие не вернул (это дефект селектора, а не генератора);
    `errors` — исключения пробы (например, роль вне словаря модели).
    """
    buckets = [bucket for bucket in model.get("buckets") or [] if isinstance(bucket, dict)]
    triples = sorted(
        {
            (
                str(bucket.get("role")),
                str(bucket.get("issue_type")),
                str(bucket.get("work_kind")),
            )
            for bucket in buckets
        }
    )
    hit, missed, errors = [], [], []
    for index, (role, issue_type, work_kind) in enumerate(triples, 1):
        name = "%s/%s/%s" % (role, issue_type, work_kind)
        context = _bucket_probe_context(role, issue_type, work_kind, index)
        try:
            validation = checkmod.run_checks(context, rules, False)
            payload = estimatemod.estimate(validation, model, context=context, cfg=cfg)
        except Exception as exc:  # noqa: BLE001 — проба измеряет и падения
            errors.append({"bucket": name, "error": "%s: %s" % (type(exc).__name__, exc)})
            continue
        found = _bucket_of(payload)
        if found and "%s/%s/%s" % (
            found.get("role"),
            found.get("issue_type"),
            found.get("work_kind"),
        ) == name:
            hit.append(name)
        else:
            missed.append(
                {
                    "bucket": name,
                    "selected": found,
                    "expected": payload.get("roles", [{}])[0].get("expected")
                    if payload.get("roles")
                    else None,
                }
            )
    return {
        "probes": len(triples),
        "hit": len(hit),
        "missed": missed,
        "errors": errors,
        "note": "проба на каждый бакет модели: context(role, issue_type, work_kind) "
        "→ estimate должен вернуть тот же бакет",
    }


def _determinism(model, rules, cfg, schemas, bucket_index, contexts):
    """Первые 100 задач — дважды; сравнение побайтно без `duration_ms`."""
    sample = contexts[: min(100, len(contexts))]
    first = [
        _deterministic_view(_run_case(context, model, rules, cfg, schemas, bucket_index))
        for context in sample
    ]
    second = [
        _deterministic_view(_run_case(context, model, rules, cfg, schemas, bucket_index))
        for context in sample
    ]
    equal = first == second
    first_diff = None
    if not equal:
        for left, right in zip(first, second):
            if left != right:
                first_diff = left["case_id"]
                break
    return {"cases": len(sample), "equal": equal, "first_diff": first_diff}


def harness(workdir, directory, out_dir, limit=None, workers=4):
    """Прогнать `contexts.jsonl` через check + estimate. Возвращает summary."""
    started = time.perf_counter()
    contexts = _load_contexts(directory, limit)
    model = _load_model(workdir)
    cfg = _load_cfg(workdir)
    rules = checkmod.default_rules()
    schemas = _schemas()
    bucket_index = _bucket_index(model)

    records = []
    workers = max(1, int(workers or 1))
    if workers == 1:
        records = [
            _run_case(context, model, rules, cfg, schemas, bucket_index)
            for context in contexts
        ]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    _run_case, context, model, rules, cfg, schemas, bucket_index
                )
                for context in contexts
            ]
            records = [future.result() for future in futures]
    records.sort(key=lambda item: item["case_id"])

    determinism = _determinism(model, rules, cfg, schemas, bucket_index, contexts)
    monotonicity = _monotonicity(model, rules, cfg)
    elapsed = time.perf_counter() - started
    summary = _summarize(records, elapsed, model, contexts, determinism)
    summary["monotonicity"] = monotonicity
    summary["buckets"]["probe"] = _bucket_coverage(model, rules, cfg)
    summary["seed"] = _dataset_seed(directory)
    summary["harness"] = {
        "in_process": True,
        "workers": workers,
        "writes_runs": False,
        "out": str(out_dir),
        "limit": limit,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_bytes(
        (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    with open(out_dir / "records.jsonl", "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(_json_line(record) + "\n")
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _run_synth(workdir, args):
    count = int(getattr(args, "count", 0) or 0)
    if count <= 0:
        return _fail(args, 2, "[BLOCKED] synth: --count должен быть > 0")
    out_dir = _resolve_out(workdir, args.out)
    problem = _guard_out(workdir, out_dir)
    if problem:
        return _fail(args, 2, problem)
    try:
        contexts, manifest = generate(
            workdir,
            count,
            seed=int(getattr(args, "seed", 42)),
            from_sprints=getattr(args, "from_sprints", None),
            include_edge=bool(getattr(args, "include_edge", False)),
            sample=getattr(args, "sample", None),
            coverage_all_buckets=bool(getattr(args, "coverage_all_buckets", True)),
            coverage_quota=int(getattr(args, "coverage_quota", 20) or 0),
        )
    except ValueError as exc:
        message = str(exc)
        return _fail(args, 4 if message.startswith("[MISSING]") else 2, message)
    files = write_dataset(contexts, manifest, out_dir)
    _emit(
        args,
        "[OK] synth: %d задач, seed=%s → %s (%.1f МБ, sha256:%s)"
        % (
            len(contexts),
            manifest["seed"],
            files["contexts"],
            files["bytes"] / (1024.0 * 1024.0),
            files["sha256"][:12],
        ),
    )
    _emit_json(
        args,
        {
            "status": "ok",
            "code": 0,
            "count": len(contexts),
            "seed": manifest["seed"],
            "files": files,
            "distributions": manifest["distributions"],
            "model": manifest["model"],
        },
    )
    return 0


def _run_harness(workdir, args):
    directory = Path(str(args.dir)).expanduser()
    if not directory.is_absolute():
        directory = Path(workdir) / directory
    out_dir = (
        _resolve_out(workdir, args.out)
        if getattr(args, "out", None)
        else directory.resolve() / "out"
    )
    problem = _guard_out(workdir, out_dir)
    if problem:
        return _fail(args, 2, problem)
    limit = getattr(args, "limit", None)
    try:
        summary = harness(
            workdir,
            directory,
            out_dir,
            limit=limit,
            workers=int(getattr(args, "workers", 4) or 4),
        )
    except ValueError as exc:
        message = str(exc)
        return _fail(args, 4 if message.startswith("[MISSING]") else 2, message)

    mono = summary["monotonicity"]
    buckets = summary["buckets"]
    lines = [
        "[OK] synth-run: total=%d ok=%d warn=%d blocked=%d errors=%d "
        "(unestimable=%d, unexpected=%d)"
        % (
            summary["total"],
            summary["ok"],
            summary["warn"],
            summary["blocked"],
            summary["errors"],
            summary["unestimable"],
            summary["unexpected_errors"],
        ),
        "[INFO] schema_fail=%d scale_violations=%d range_violations=%d "
        "param_violations=%d monotonicity_violations=%d"
        % (
            summary["schema_failures"]["cases"],
            summary["scale_violations"]["cases"],
            summary["range_violations"]["cases"],
            summary["param_violations"]["cases"],
            mono["violations"],
        ),
        "[INFO] determinism: cases=%d equal=%s; buckets: hit=%d/%d (reachable %d, "
        "probe %d/%d)"
        % (
            summary["determinism"]["cases"],
            "yes" if summary["determinism"]["equal"] else "no",
            buckets["hit"],
            buckets["total"],
            buckets["reachable"],
            buckets["probe"]["hit"],
            buckets["probe"]["probes"],
        ),
        "[INFO] timing: total=%.2fs p50=%.2fms p95=%.2fms; summary → %s"
        % (
            summary["timing"]["total_s"],
            summary["timing"]["per_task_ms"]["p50"],
            summary["timing"]["per_task_ms"]["p95"],
            out_dir / "summary.json",
        ),
    ]
    for line in lines:
        _emit(args, line)

    # Запись в SQLite: по умолчанию — если зеркало включено; `--no-record`
    # выключает, `--record` включает явно (даже если конфиг не прочитался).
    record = getattr(args, "record", None)
    if record is None:
        record = True
    if record:
        run_id = storemod.save_synth_run(workdir, None, summary)
        if run_id:
            _emit(
                args,
                "[INFO] db: synth run %s → synth_runs + metrics(scope='synth')"
                % run_id,
            )
        else:
            _emit(
                args,
                "[WARN] db: прогон не записан (storage.sqlite выключено или БД "
                "не открывается)",
            )

    _emit_json(args, summary)

    failures = (
        summary["unexpected_errors"]
        + summary["schema_failures"]["cases"]
        + summary["scale_violations"]["cases"]
        + summary["range_violations"]["cases"]
        + summary["param_violations"]["cases"]
        + mono["violations"]
    )
    if failures:
        _emit(
            args,
            "[BLOCKED] synth-run: %d нарушений инвариантов — разбор в summary.json"
            % failures,
        )
        return 2
    return 0


def run(workdir, args):
    """Точка входа для `cli._run_lazy`: `synth` или `synth-run`."""
    command = getattr(args, "command", None)
    if command == "synth-run":
        return _run_harness(workdir, args)
    return _run_synth(workdir, args)

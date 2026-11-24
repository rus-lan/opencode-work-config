#!/usr/bin/env python3
"""Рендер отчёта о готовности/оценке: `report.md`, `delta.md`, страница модели.

Правила (CONTRACT.md §7, §8):

* **Слот без данных — `N/A (нет данных в источнике)`.** Ни одно число не
  дорисовывается: рендер только перекладывает JSON в Markdown.
* **Числа — как в JSON.** `int` печатается как есть, `float` — в JSON-виде
  (`1.0`, `1.25`), без округлений и переформатирования.
* **Порядок ролей фиксирован**: `BA, SA, BE, FE, QA, DEVOPS, OTHER`.
* **Инварианты секций**: секция 5 — ровно роли из `estimate.roles`; секции 3 и
  4 — ровно пробелы из `validation.gaps` (3 — REQUIRED, 4 — остальные), но
  печатаются **компактно**: до трёх пунктов «чего не хватает — почему это
  влияет», строка «и ещё N», ссылка на шаблон и путь к `validation.json`;
  секции 6–7 — выжимка в 1–2 предложения. Полные данные остаются в JSON
  (`validation.json`, `estimate.json`), табличные слоты — для пользовательских
  шаблонов.
* **Детерминизм**: два прогона на одних данных дают идентичные байты. Время
  берётся только из артефактов, не из `now()`.

Шаблон — Markdown со слотами `{{slot}}`. Скалярный слот подставляется один раз;
слот-строка (`{{gap_id}}`, `{{role_name}}`, `{{prov_role}}`, `{{variability_cause}}`)
размножает **всю строку шаблона** по элементам массива — так таблицы собираются
из данных, а не из захардкоженных ячеек. Секции 3/4/5/6/7 получают свои наборы
строк. Неизвестный слот рендерится как `N/A`, поэтому шаблон не может «тихо»
оставить пустое место.

Контракт слотов описан в `references/artifacts.md`.
"""

import json
import os
import re
import tempfile
from pathlib import Path

from trr_impl import analysis as analysismod
from trr_impl import config as configmod
from trr_impl import limits
from trr_impl.sources import NA_MARKER as NA

__all__ = [
    "DEFAULT_DELTA_TEMPLATE",
    "DEFAULT_MODEL_PAGE_TEMPLATE",
    "DEFAULT_REPORT_TEMPLATE",
    "NA",
    "ROLE_ORDER",
    "model_page_slots",
    "model_template",
    "render",
    "render_estimate_comment",
    "render_model_page",
    "render_reference_estimates",
    "render_sprint_stats",
    "render_validation_comment",
    "report_rows",
    "report_slots",
    "run",
    "similar_tasks_table",
    "write",
]

# Порядок ролей в отчёте (CONTRACT.md §3: role enum). Не алфавитный: читателю
# важен путь задачи BA → SA → разработка → QA.
ROLE_ORDER = ("BA", "SA", "BE", "FE", "QA", "DEVOPS", "OTHER")

SCENARIO_ORDER = ("base", "optimistic", "pessimistic")

# Дефолт ссылки на шаблон описания задачи (`validation.template_url`).
DEFAULT_TEMPLATE_URL = configmod.DEFAULT_TEMPLATE_URL

STATE_DIR = ".task-readiness"

EXIT_OK = 0
EXIT_BLOCKED = 2
EXIT_MISSING = 4

_SLOT_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")
_SECTION_RE = re.compile(r"^## (\d+)\. ", re.MULTILINE)

# Слоты, которые по контракту остаются ПУСТОЙ строкой, когда данных нет.
# Обычный слот без данных рендерится как `N/A` (чтобы шаблон не оставлял «тихую»
# дырку), но строка «Ресурсы: …» — необязательная: при отсутствии ресурсов она
# должна исчезнуть, а не напечатать `N/A`.
OPTIONAL_BLANK_SLOTS = frozenset({"resources_line"})

# Слоты, которые размножают строку шаблона по элементам массива.
ROW_SLOTS = {
    "gap": (
        "gap_id",
        "gap_severity",
        "gap_what",
        "gap_role",
        "gap_where",
    ),
    "role": (
        "role_name",
        "role_expected",
        "role_range_low",
        "role_range_high",
        "role_confidence",
        "role_scenario_min",
        "role_scenario_base",
        "role_scenario_max",
        "role_reason",
    ),
    "variability": (
        "variability_line",
        "variability_rule_id",
        "variability_cause",
        "variability_effect",
        "variability_from",
        "variability_to",
    ),
    "prov": (
        "prov_role",
        "prov_kind",
        "prov_value",
        "prov_source",
    ),
}

# Синонимы слотов: шаблон может назвать одно и то же по-разному.
_SLOT_ALIASES = {
    "checks": "checks_table",
    "gaps": "gaps_table",
    "questions": "questions_table",
    "roles": "roles_table",
    "scenarios": "scenarios_table",
    "provenance": "provenance_table",
    "sources": "sources_table",
    "buckets": "buckets_table",
    "gap_rules": "gap_rules_table",
    "version": "model_version",
    "checksum": "model_checksum",
}

# ---------------------------------------------------------------------------
# Шаблоны по умолчанию
# ---------------------------------------------------------------------------

# Резервный шаблон отчёта: используется, если `templates/report.md` в
# установленном скилле отсутствует. Имена слотов совпадают с боевым шаблоном,
# поэтому оба пути рендера дают одинаковую структуру.
DEFAULT_REPORT_TEMPLATE = """\
# Готовность и оценка задачи {{task_key}}

> Прогон: `{{run_id}}` · проверено: `{{checked_at}}` · оценено: `{{estimated_at}}` ·
> модель: `v{{model_version}}` (`{{model_checksum}}`).

## 1. Задача

| Поле | Значение |
|---|---|
| Ключ | {{task_key}} |
| Заголовок | {{task_summary}} |
| Тип | {{issue_type}} |
| Роль | {{role}} |
| Вид работ | {{work_kind}} |
| Что делается (по заголовку и тексту) | {{intent_line}} |
| Спринт | {{sprint}} |
| Статус | {{status}} |
| Ссылка | {{task_url}} |

## 2. Вердикт готовности

**{{verdict}}** — {{verdict_reason}}

Проверок: passed {{checks_passed}} · failed {{checks_failed}} · na {{checks_na}}.
Проверка с зависимостями: {{with_dependencies}}.

{{analysis_block}}

## 3. Что не готово (блокирует оценку)

| check-id | severity | что отсутствует | кто отвечает | где искать |
|---|---|---|---|---|
| {{gap_id}} | {{gap_severity}} | {{gap_what}} | {{gap_role}} | {{gap_where}} |

## 4. Что стоит уточнить

| check-id | severity | что отсутствует | кто отвечает | где искать |
|---|---|---|---|---|
| {{gap_id}} | {{gap_severity}} | {{gap_what}} | {{gap_role}} | {{gap_where}} |

## 5. Оценка по ролям

Шкала: `{{scale}}`.

| Роль | Ожидаемо (sp) | Диапазон | Уверенность | Сценарии (min/base/max) | Обоснование |
|---|---|---|---|---|---|
| {{role_name}} | {{role_expected}} | {{role_range_low}}–{{role_range_high}} | {{role_confidence}} | {{role_scenario_min}} / {{role_scenario_base}} / {{role_scenario_max}} | {{role_reason}} |

**Итого:** ожидаемо {{total_expected}} sp, диапазон {{total_range_low}}–{{total_range_high}} sp.

{{totals_line}}

{{resources_line}}

## 6. Вариативность и условия

- {{variability_line}}

## 7. Провенанс оценки

| роль | источник | значение | откуда |
|---|---|---|---|
| {{prov_role}} | {{prov_kind}} | {{prov_value}} | {{prov_source}} |

## 8. Как перегенерировать

Команда: `/task-readiness-review refresh {{task_key}}`

- Что изменится: {{refresh_expected_changes}}
- Что останется прежним: {{refresh_unchanged}}
- Куда смотреть diff: {{delta_path}}
"""

# Резервный шаблон страницы модели: компактный, с бакетами и формулой.
DEFAULT_MODEL_PAGE_TEMPLATE = """\
# Модель оценки Story Points (версия {{model_version}})

Дата генерации: {{generated_at}}. Контрольная сумма: `{{model_checksum}}`.

Нормативная шкала: {{scale}}.
Роли, отсутствующие в эталоне: {{absent_roles}}.

## 1. Источники

Эталон: {{reference_system}}:{{reference_page_id}} ({{reference_title}}), снимок {{reference_retrieved_at}}.
Спринты: {{sprint_list}}.

## 2. Бакеты

{{buckets_table}}

## 3. Формула

{{formula}}

## 4. Ограничения

{{limitations}}
"""

# Резервный шаблон delta.md.
DEFAULT_DELTA_TEMPLATE = """\
# Изменения оценки задачи {{task_key}}

Предыдущий прогон: `{{previous_run}}`.
Текущий прогон: `{{current_run}}`.

## 1. Вердикт

{{verdict_change}}

## 2. Оценка по ролям

{{roles_delta_table}}

## 3. Итог

{{total_change}}

## 4. Пробелы

{{gaps_change}}
"""


# ---------------------------------------------------------------------------
# Служебное форматирование
# ---------------------------------------------------------------------------


def _num(value):
    """Число как в JSON: int — как есть, float — в JSON-виде, bool — да/нет."""
    if value is None:
        return NA
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value)
    return str(value)


def _num_compact(value):
    """Число для слотов, где хвост `.0` читается как ошибка: `1.0` → `1`.

    Отдельно от `_num`, потому что `_num` держит контракт «float — в JSON-виде»
    (статистика `mean=5.0` — это именно 5.0). Здесь речь о величинах, которые
    по смыслу целые: надбавка `sp_per_resource` в Story Points.
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _num(value)


def _text(value):
    """Значение слота в текст. Пустое значение — `NA`, а не пустая строка."""
    if value is None:
        return NA
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, (int, float)):
        return _num(value)
    if isinstance(value, (list, tuple)):
        if not value:
            return NA
        return "[%s]" % ", ".join(
            item if isinstance(item, str) else _num(item) for item in value
        )
    text = str(value).strip()
    return text or NA


def _cell(value):
    """Ячейка таблицы: без переводов строк и без ломающих `|`."""
    text = _text(value)
    text = re.sub(r"\s*\n\s*", " ", text)
    return text.replace("|", "\\|")


def _table(headers, rows):
    """Markdown-таблица. Нет строк — `NA` (пустая таблица хуже честного N/A)."""
    if not rows:
        return NA
    lines = [
        "| %s |" % " | ".join(headers),
        "|%s|" % "|".join("---" for _ in headers),
    ]
    for row in rows:
        lines.append("| %s |" % " | ".join(_cell(value) for value in row))
    return "\n".join(lines)


def _bullets(items):
    items = [str(item).strip() for item in items or [] if str(item).strip()]
    if not items:
        return NA
    return "\n".join("- %s" % item for item in items)


def _role_key(role):
    try:
        return ROLE_ORDER.index(role)
    except ValueError:
        return len(ROLE_ORDER)


def _sorted_roles(roles):
    """Роли в фиксированном порядке отчёта; неизвестная роль уходит в конец."""
    return sorted(
        roles,
        key=lambda item: (_role_key(item.get("role")), str(item.get("role"))),
    )


def _scenario(role, name):
    for item in role.get("scenarios") or []:
        if item.get("name") == name:
            return item
    return None


def _scenario_points(role, name):
    item = _scenario(role, name)
    return item.get("points") if item else None


# ---------------------------------------------------------------------------
# Чтение артефактов
# ---------------------------------------------------------------------------


def _read_json(path, required):
    path = Path(path)
    if not path.is_file():
        if required:
            raise FileNotFoundError("нет файла %s" % path)
        return None
    try:
        limits.check_size(path)
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise FileNotFoundError("не удалось прочитать %s: %s" % (path, exc))
    except ValueError as exc:
        raise ValueError("%s — невалидный JSON: %s" % (path, exc))
    return data


def _optional_json(path):
    """JSON-объект из файла или None: рендер страницы не падает без норм/state."""
    try:
        data = _read_json(path, required=False)
    except (FileNotFoundError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def model_path_for_run(run_dir):
    """Путь к модели от каталога прогона: `.task-readiness/model/estimation-model.json`."""
    for parent in Path(run_dir).parents:
        if parent.name == STATE_DIR:
            return parent / "model" / "estimation-model.json"
    return None


def _read_template(template_path, default):
    if template_path in (None, ""):
        return default
    path = Path(template_path)
    if not path.is_file():
        raise FileNotFoundError("нет шаблона %s" % path)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _lookup(slots, key):
    if key in slots:
        return slots[key]
    return slots.get(_SLOT_ALIASES.get(key, key))


def _substitute(template, slots, rows_by_section=None):
    """Подставить слоты; слоты-строки размножить по элементам массива.

    HTML-комментарии шаблона (`<!-- … -->`) — документация слотов: подстановка
    в них не выполняется, а в готовый артефакт они не попадают, чтобы в отчёте
    не осталось литеральных `{{slot}}` из справки.
    """
    rows_by_section = rows_by_section or {}
    slot_to_group = {}
    for group, names in ROW_SLOTS.items():
        for name in names:
            slot_to_group[name] = group

    masked, comments = _mask_comments(template)
    chunks = _split_sections(masked)
    output = []
    for number, chunk in chunks:
        groups = rows_by_section.get(number) or {}
        output.extend(_substitute_chunk(chunk, slots, groups, slot_to_group))
    text = "\n".join(output)
    # Комментарии шаблона — документация слотов, в готовый артефакт они не
    # попадают: иначе в отчёте остались бы литеральные `{{slot}}` из справки.
    for marker, _original in comments:
        text = text.replace(marker, "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Ровно один перевод строки в конце — как у остальных артефактов.
    return text.rstrip("\n") + "\n"


def _mask_comments(template):
    """Заменить HTML-комментарии маркерами, чтобы не подставлять в них слоты."""
    comments = []

    def replace(match):
        marker = "\x00trr-comment-%d\x00" % len(comments)
        comments.append((marker, match.group(0)))
        return marker

    masked = re.sub(r"<!--.*?-->", replace, template, flags=re.DOTALL)
    return masked, comments


def _split_sections(template):
    """Разбить шаблон на (номер секции|None, текст) по заголовкам `## N. `."""
    matches = list(_SECTION_RE.finditer(template))
    if not matches:
        return [(None, template)]
    chunks = []
    if matches[0].start() > 0:
        chunks.append((None, template[: matches[0].start()]))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(template)
        chunks.append((int(match.group(1)), template[match.start() : end]))
    return chunks


def _substitute_chunk(chunk, slots, groups, slot_to_group):
    lines = []
    for line in chunk.split("\n"):
        used = {
            slot_to_group[match.group(1)]
            for match in _SLOT_RE.finditer(line)
            if match.group(1) in slot_to_group
        }
        if not used:
            lines.append(_fill(line, slots))
            continue
        if len(used) > 1:
            raise ValueError(
                "в одной строке шаблона смешаны группы слотов: %s"
                % ", ".join(sorted(used))
            )
        rows = groups.get(used.pop()) or []
        if not rows:
            # Данных нет — по контракту строка остаётся, ячейки становятся N/A.
            lines.append(_fill(line, slots))
            continue
        for row in rows:
            merged = dict(slots)
            merged.update(row)
            lines.append(_fill(line, merged))
    return lines


def _fill(line, slots):
    """Подставить слоты в строку; в табличной строке — ещё и экранировать `|`."""
    is_table_row = line.lstrip().startswith("|")

    def replace(match):
        key = match.group(1)
        value = _lookup(slots, key)
        if key in OPTIONAL_BLANK_SLOTS and value in (None, ""):
            return ""
        text = _text(value)
        if is_table_row:
            text = re.sub(r"\s*\n\s*", " ", text).replace("|", "\\|")
        return text

    return _SLOT_RE.sub(replace, line)


# ---------------------------------------------------------------------------
# Слоты отчёта
# ---------------------------------------------------------------------------


def _checks_rows(validation):
    return [
        (
            check.get("id"),
            check.get("section"),
            check.get("severity"),
            check.get("status"),
            limits.truncate(check.get("message")),
        )
        for check in validation.get("checks") or []
    ]


def _gaps_rows(validation):
    return [
        (
            gap.get("id"),
            gap.get("severity"),
            limits.truncate(gap.get("question")),
            gap.get("target_role"),
            gap.get("where_to_find"),
        )
        for gap in validation.get("gaps") or []
    ]


def _questions_rows(validation):
    return [
        (
            gap.get("id"),
            limits.truncate(gap.get("question")),
            gap.get("target_role"),
            gap.get("where_to_find"),
        )
        for gap in validation.get("gaps") or []
    ]


def _roles_rows(estimate):
    return [
        (
            _role_label(role),
            role.get("expected"),
            role.get("range"),
            role.get("confidence"),
            _scenario_points(role, "optimistic"),
            _scenario_points(role, "base"),
            _scenario_points(role, "pessimistic"),
        )
        for role in _sorted_roles(estimate.get("roles") or [])
    ]


def _scenarios_rows(estimate):
    rows = []
    for role in _sorted_roles(estimate.get("roles") or []):
        by_name = {item.get("name"): item for item in role.get("scenarios") or []}
        for name in SCENARIO_ORDER:
            item = by_name.get(name)
            if item is None:
                continue
            rows.append(
                (role.get("role"), item.get("name"), item.get("points"), item.get("reason"))
            )
    return rows


def _provenance_rows(estimate):
    """По строке на каждую запись `roles[].provenance[]` (CONTRACT.md §7.2)."""
    rows = []
    for role in _sorted_roles(estimate.get("roles") or []):
        for record in role.get("provenance") or []:
            rows.append(
                (
                    role.get("role"),
                    record.get("kind"),
                    "%s: %s" % (record.get("field"), record.get("detail")),
                    record.get("source"),
                )
            )
    return rows


def _similar_rows(estimate):
    """Строки похожих задач: key, cosine, sp, role, work_kind, same_bucket."""
    return [
        (
            item.get("key"),
            item.get("cosine"),
            item.get("sp"),
            item.get("role"),
            item.get("work_kind"),
            item.get("same_bucket"),
        )
        for item in estimate.get("similar_tasks") or []
        if isinstance(item, dict)
    ]


def similar_tasks_table(estimate):
    """Таблица похожих задач; пусто — `NA`."""
    return _table(
        ("Задача", "cosine", "SP", "Роль", "Вид работ", "Тот же бакет"),
        _similar_rows(estimate),
    )


# Максимум пунктов в компактных блоках отчёта (секции 3–4): остальное —
# одной строкой «и ещё N». Полные списки живут в validation.json.
MAX_COMPACT_GAPS = 3

# Один пункт — одна строка: «чего не хватает — почему это влияет».
COMPACT_LINE_LIMIT = 120

# Порядок severity в секции 4: сначала то, что сильнее влияет на уверенность.
_SEVERITY_ORDER = {"REQUIRED": 0, "RECOMMENDED": 1, "OPTIONAL": 2}

# Штраф в `variability_reason[]`: `GR-01: … → +2 шага (1 → 3), роль FE`.
_PENALTY_RE = re.compile(r"^GR-[A-Za-z0-9]+:.*→\s*\+(\d+)\s+шаг")

# Путь к шаблону описания задачи внутри скилла — фолбэк, когда
# `validation.template_url` пуст.
TASK_DESCRIPTION_TEMPLATE = "templates/task-description.md"


def _plural(number, one, few, many):
    """Русская форма числительного: 1 пробел / 2 пробела / 5 пробелов."""
    value = abs(int(number))
    if value % 10 == 1 and value % 100 != 11:
        return one
    if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14:
        return few
    return many


def _template_link(template_url):
    """Ссылка на целевой шаблон описания задачи.

    `validation.template_url` пуст → печатаем путь к `templates/task-description.md`
    (ссылка на пустое место хуже честного пути).
    """
    url = DEFAULT_TEMPLATE_URL if template_url is None else str(template_url).strip()
    if not url:
        return "`%s`" % TASK_DESCRIPTION_TEMPLATE
    return "[Шаблон описания задачи](%s)" % url


def _sentence(text):
    """Пункт списка: без хвостовой точки, с заглавной первой буквы."""
    value = re.sub(r"\s+", " ", str(text or "")).strip().rstrip(".;").strip()
    if not value:
        return ""
    return value[0].upper() + value[1:]


def _shorten(text, limit):
    """Обрезать по границе слова, добавив многоточие (лимит соблюдается)."""
    if len(text) <= limit:
        return text
    cut = text[: max(1, limit - 1)]
    space = cut.rfind(" ")
    if space >= 20:
        cut = cut[:space]
    # Незакрытая скобка в обрезке читается как обрыв фразы: отрезаем её хвост.
    if cut.count("(") > cut.count(")"):
        cut = cut[: cut.rfind("(")]
    return cut.rstrip(" ,;:—-(") + "…"


def _lower_first(text):
    """Строчная первая буква — вторая половина пункта идёт после тире."""
    if not text:
        return text
    return text[0].lower() + text[1:]


def _compact_gap_line(gap, what):
    """Один пункт компактного блока: «что не хватает — почему это влияет»."""
    left = _sentence(what or gap.get("question") or gap.get("id"))
    right = _lower_first(_sentence(gap.get("why")))
    if not right:
        return _shorten(left, COMPACT_LINE_LIMIT)
    # Лимит строки соблюдается за счёт левой части: факт можно сократить,
    # объяснение «почему» — нет, иначе пункт теряет смысл.
    allowed = max(20, COMPACT_LINE_LIMIT - len(right) - 3)
    return "%s — %s" % (_shorten(left, allowed), right)


def _penalty_steps(estimate):
    """Сколько шагов шкалы добавили штрафы `gap_rules` (сумма по строкам GR-*)."""
    total = 0
    for reason in estimate.get("variability_reason") or []:
        match = _PENALTY_RE.match(str(reason).strip())
        if match:
            total += int(match.group(1))
    return total


def _penalty_count(estimate):
    """Сколько штрафов `gap_rules` применилось (строк GR-* в причинах)."""
    return sum(
        1
        for reason in estimate.get("variability_reason") or []
        if _PENALTY_RE.match(str(reason).strip())
    )


def _compact_gaps_block(gaps, what, template_url, validation_path, headline, empty):
    """Компактный блок секции 3/4: заголовок, ≤3 пункта, «и ещё N», ссылка.

    Полный список пробелов остаётся в `validation.json`; блок отвечает на
    вопрос «что делать», а не перечисляет всё.
    """
    items = sorted(
        [gap for gap in gaps if isinstance(gap, dict)],
        key=lambda gap: (
            _SEVERITY_ORDER.get(str(gap.get("severity")), len(_SEVERITY_ORDER)),
            str(gap.get("id")),
        ),
    )
    lines = []
    if not items:
        # Пустой блок — одна строка, без «Что заполнить»: заполнять нечего.
        return empty
    lines.extend([headline, ""])
    for gap in items[:MAX_COMPACT_GAPS]:
        lines.append("- %s" % _compact_gap_line(gap, what.get(gap.get("id"))))
    rest = len(items) - MAX_COMPACT_GAPS
    if rest > 0:
        lines.append("- и ещё %d" % rest)
    lines.extend(
        [
            "",
            "Что заполнить: %s · полный список: `%s`"
            % (_template_link(template_url), validation_path),
        ]
    )
    return "\n".join(lines)


def _gaps_headline(required, estimate):
    """Заголовок секции 3: сколько REQUIRED-пробелов и на сколько шагов штраф."""
    count = len(required)
    text = "**%d %s.**" % (
        count,
        _plural(count, "REQUIRED-пробел", "REQUIRED-пробела", "REQUIRED-пробелов"),
    )
    steps = _penalty_steps(estimate)
    if steps:
        text += " Оценка завышена на %d %s." % (
            steps,
            _plural(steps, "шаг", "шага", "шагов"),
        )
    return text


def _notes_headline(gaps):
    """Заголовок секции 4: сколько пунктов стоит уточнить."""
    count = len(gaps)
    return "**%d %s.**" % (
        count,
        _plural(count, "замечание", "замечания", "замечаний"),
    )


def _primary_role(estimate):
    """Роль, по которой объясняется оценка: первая не-QA (иначе первая)."""
    roles = _sorted_roles(estimate.get("roles") or [])
    for role in roles:
        if role.get("role") != "QA":
            return role
    return roles[0] if roles else None


def _model_bucket(model, label):
    """Бакет модели по идентификатору `role/issue_type/work_kind`."""
    for bucket in (model or {}).get("buckets") or []:
        if not isinstance(bucket, dict):
            continue
        if "%s/%s/%s" % (
            bucket.get("role"),
            bucket.get("issue_type"),
            bucket.get("work_kind"),
        ) == label:
            return bucket
    return None


def _bucket_of_role(role):
    """Идентификатор бакета из `provenance` роли (`estimation-model:N:label`)."""
    for record in role.get("provenance") or []:
        source = str(record.get("source") or "")
        if source.startswith("estimation-model:") and source.count(":") >= 2:
            return source.split(":", 2)[2]
    return None


def _bucket_facts(model, label):
    """`base`, `n`, `reference` бакета — или None, если бакета нет в модели."""
    bucket = _model_bucket(model, label)
    if bucket is None:
        return None
    return {
        "base": bucket.get("base"),
        "n": bucket.get("n"),
        "reference": bucket.get("reference"),
    }


def _variability_summary(estimate, model):
    """Секция 6: 1–2 предложения о том, что повлияло на число.

    Полные причины (`variability_reason[]`) остаются в `estimate.json`;
    отчёт печатает выжимку: множитель параметров, штрафы, QA и бакет эталона.
    """
    parts = []
    params = estimate.get("params") or {}
    multiplier = params.get("multiplier")
    if (
        isinstance(multiplier, (int, float))
        and not isinstance(multiplier, bool)
        and round(float(multiplier), 4) != 1.0
    ):
        parts.append("множитель параметров ×%s" % _num(multiplier))

    steps = _penalty_steps(estimate)
    if steps:
        required = len(estimate.get("blocked_by_gaps") or [])
        parts.append(
            "штраф +%d %s (%d REQUIRED-%s)"
            % (
                steps,
                _plural(steps, "шаг", "шага", "шагов"),
                required,
                _plural(required, "пробел", "пробела", "пробелов"),
            )
        )

    qa = (estimate.get("total") or {}).get("qa")
    if isinstance(qa, dict):
        parts.append(
            "QA %s SP (%s)"
            % (
                _num(qa.get("expected")),
                "из Jira" if qa.get("source") == "jira" else "расчёт модели",
            )
        )

    role = _primary_role(estimate)
    label = _bucket_of_role(role) if role else None
    facts = _bucket_facts(model, label) if label else None
    if facts is not None:
        parts.append(
            "эталон взят из бакета %s (n=%s, reference=%s)"
            % (label, _num(facts["n"]), _num(facts["reference"]))
        )

    if estimate.get("role_assumed"):
        parts.append("роль в снимке не указана — принята доминирующая роль вида работ")

    if not parts:
        return "Нет данных о вариативности"
    # Одно предложение с точками с запятой — как в примере отчёта: коротко и
    # без списка, который дублировал бы variability_reason[].
    return _sentence("; ".join(parts)) + "."


def _provenance_summary(estimate, model):
    """Секция 7: 1–2 предложения о происхождении чисел.

    Таблица провенанса больше не печатается (полные записи — в
    `estimate.json`); в отчёте остаются бакет, множитель, штрафы и QA.
    """
    role = _primary_role(estimate)
    if role is None:
        return "Провенанс не записан"
    label = _bucket_of_role(role)
    facts = _bucket_facts(model, label) if label else None
    if label is None and facts is None:
        return "Провенанс не записан"

    sentences = []
    if label:
        facts = facts or {}
        details = []
        if facts.get("base") is not None:
            details.append("base=%s" % _num(facts["base"]))
        if facts.get("n") is not None:
            details.append("n=%s" % _num(facts["n"]))
        if facts.get("reference") is not None:
            details.append("reference=%s" % _num(facts["reference"]))
        text = "Оценка получена из бакета `%s`" % label
        if details:
            text += " (%s)" % ", ".join(details)
        params = estimate.get("params") or {}
        multiplier = params.get("multiplier")
        if isinstance(multiplier, (int, float)) and not isinstance(multiplier, bool):
            text += ", множитель ×%s" % _num(multiplier)
        penalties = _penalty_count(estimate)
        if penalties:
            text += ", %d %s по gap_rules" % (
                penalties,
                _plural(penalties, "штраф", "штрафа", "штрафов"),
            )
        sentences.append(text)

    qa = (estimate.get("total") or {}).get("qa")
    if isinstance(qa, dict):
        if qa.get("source") == "jira":
            sentences.append(
                "QA — %s SP из поля QA Estimation, без пересчёта"
                % _num(qa.get("expected"))
            )
        else:
            bucket = qa.get("bucket")
            if bucket:
                facts = _bucket_facts(model, bucket) or {}
                details = []
                if facts.get("n") is not None:
                    details.append("n=%s" % _num(facts["n"]))
                if facts.get("reference") is not None:
                    details.append("reference=%s" % _num(facts["reference"]))
                sentences.append(
                    "QA — %s SP по бакету `%s`%s"
                    % (
                        _num(qa.get("expected")),
                        bucket,
                        (" (%s)" % ", ".join(details)) if details else "",
                    )
                )
            else:
                sentences.append(
                    "QA — %s SP расчётом модели (бакета QA в модели нет)"
                    % _num(qa.get("expected"))
                )

    version = estimate.get("model_version")
    if version is not None:
        sentences.append("Источник модели: `estimation-model:v%s`" % _num(version))

    if not sentences:
        return "Провенанс не записан"
    return _sentence(". ".join(sentences)) + "."


def _totals_line(estimate):
    """Строка итога секции 5: `Dev: N SP · QA: M SP · Итого: N+M SP`.

    Когда QA-записи нет, вместо пустоты печатается объяснение из `qa_scope`
    («тип задачи не требует QA-оценки — проверку выполняет исполнитель»).
    """
    total = estimate.get("total") or {}
    expected = total.get("expected")
    qa = total.get("qa")
    if not isinstance(qa, dict):
        line = "Dev: %s SP · Итого: %s SP" % (_num(expected), _num(expected))
        scope = str(estimate.get("qa_scope") or "").strip()
        if scope:
            line = "%s\nQA: %s" % (line, scope)
        return line
    qa_points = qa.get("expected")
    dev = expected - qa_points if isinstance(expected, int) else None
    return "Dev: %s SP · QA: %s SP · Итого: %s SP" % (
        _num(dev),
        _num(qa_points),
        _num(expected),
    )


def _resources_line(estimate):
    """Строка секции 5 про надбавку за ресурсы (`RS-01`).

    Пустая строка, когда `estimate.resources` нет: слот `{{resources_line}}`
    объявлен в `OPTIONAL_BLANK_SLOTS` и не превращается в `N/A`.
    """
    resources = estimate.get("resources")
    if not isinstance(resources, dict):
        return ""
    items = [item for item in resources.get("items") or [] if isinstance(item, dict)]
    if not items:
        return ""
    names = ", ".join(str(item.get("name")) for item in items)
    mode = str(resources.get("mode") or "add")
    if mode == "upper_bound":
        return "Ресурсы: %s → верхняя граница диапазона (mode upper_bound)" % names
    return "Ресурсы: %s → +%s SP (mode %s)" % (
        names,
        _num_compact(resources.get("bonus_sp")),
        mode,
    )


def _role_label(role):
    """Имя роли в отчёте: у QA — с пометкой источника числа."""
    name = role.get("role")
    if name != "QA":
        return name
    source = role.get("source")
    if source == "jira":
        return "QA (Jira)"
    if source == "derived":
        return "QA (расчёт модели)"
    return "QA"


def _append_similar_section(text, estimate):
    """Секция 9 — только если `similar_tasks` непуст.

    Нумерация 1–8 не меняется: без похожих задач секция не добавляется вовсе.
    """
    if not (estimate.get("similar_tasks") or []):
        return text
    section = "## 9. Похожие задачи (справочно)\n\n%s\n" % similar_tasks_table(estimate)
    return text.rstrip("\n") + "\n\n" + section


def _sources_rows(context, model):
    rows = []
    for source in context.get("sources") or []:
        if not isinstance(source, dict):
            rows.append((NA, NA, source, NA, NA, NA))
            continue
        rows.append(
            (
                source.get("kind"),
                source.get("system"),
                source.get("ref") or source.get("page_id") or source.get("id"),
                source.get("title"),
                source.get("url"),
                source.get("confidence"),
            )
        )
    if rows:
        return rows
    model_sources = (model or {}).get("sources") or {}
    reference = model_sources.get("reference")
    if isinstance(reference, dict):
        rows.append(
            (
                "reference",
                reference.get("system"),
                reference.get("page_id"),
                reference.get("page_id"),
                reference.get("url"),
                NA,
            )
        )
    for sprint in model_sources.get("sprints") or []:
        rows.append(("sprint", "jira", sprint.get("id"), sprint.get("name"), None, NA))
    return rows


def _verdict_reason(validation):
    """Одна строка: что именно блокирует (или чего не хватает до OK).

    BLOCKED называет правило и его сообщение (а не только id): политика
    «блокируют два правила» бесполезна, если отчёт не говорит, какое из них.
    """
    verdict = validation.get("verdict")
    checks = validation.get("checks") or []
    gaps = validation.get("gaps") or []
    if verdict == "BLOCKED":
        blocking = [
            check
            for check in checks
            if check.get("severity") == "REQUIRED"
            and check.get("status") in ("FAIL", "UNKNOWN")
        ]
        if blocking:
            blocking.sort(key=lambda item: str(item.get("id")))
            return "блокирует: %s" % "; ".join(
                "%s — %s" % (item.get("id"), item.get("message"))
                for item in blocking[:2]
            )
        required = [gap.get("id") for gap in gaps if gap.get("severity") == "REQUIRED"]
        return "есть блокирующие пробелы: %s" % (", ".join(required) or NA)
    if verdict == "WARN":
        notes = [
            str(check.get("id"))
            for check in checks
            if check.get("severity") == "RECOMMENDED"
            and check.get("status") in ("FAIL", "UNKNOWN")
        ]
        if not notes:
            notes = [str(gap.get("id")) for gap in gaps]
        text = ", ".join(notes[:3]) or NA
        if len(notes) > 3:
            text += " и ещё %d" % (len(notes) - 3)
        return "оценка возможна, но точность ниже: %s" % text
    if verdict == "OK":
        return "все проверенные правила пройдены"
    return NA


def _analysis_block(validation, estimate=None):
    """Блок «Что видно из задачи»: метрики содержательного анализа одной строкой.

    Возвращает `""`, если анализа нет (старые артефакты) — тогда шаблон не
    печатает ни заголовок, ни строку. Числа берутся как есть из `analysis`,
    ничего не пересчитывается: отчёт — зеркало артефакта.
    """
    analysis = validation.get("analysis")
    if not isinstance(analysis, dict):
        analysis = (estimate or {}).get("analysis")
    if not isinstance(analysis, dict):
        return ""

    parts = []
    clarity = analysis.get("clarity") or {}
    score = clarity.get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool) and score > 0:
        parts.append("Понятность: %.2f" % float(score))

    testability = analysis.get("testability") or {}
    criteria = testability.get("measurable_criteria")
    if isinstance(criteria, int) and not isinstance(criteria, bool):
        if criteria > 0:
            parts.append("Измеримость: %d %s" % (criteria, _plural(criteria, "критерий", "критерия", "критериев")))
        else:
            parts.append("Измеримость: нет измеримых критериев")

    reproduction = analysis.get("reproduction") or {}
    steps = reproduction.get("steps")
    if reproduction.get("applicable") and isinstance(steps, int) and steps > 0:
        parts.append("Шаги: %d" % steps)

    scenarios = analysis.get("scenarios") or {}
    count = scenarios.get("count")
    if isinstance(count, int) and not isinstance(count, bool) and count > 0:
        parts.append("Сценарии: %d" % count)

    area = analysis.get("area") or {}
    name = str(area.get("name") or "").strip()
    if name:
        confidence = area.get("confidence")
        if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
            parts.append("Область: %s (%.1f)" % (name.upper(), float(confidence)))
        else:
            parts.append("Область: %s" % name.upper())

    dependencies = analysis.get("dependencies") or {}
    links = dependencies.get("links")
    link_types = dependencies.get("link_types") or {}
    if isinstance(links, int) and not isinstance(links, bool) and links > 0:
        kinds = ", ".join(sorted(str(key) for key in link_types))
        parts.append("Связи: %d%s" % (links, " (%s)" % kinds if kinds else ""))
    elif link_types:
        kinds = ", ".join(sorted(str(key) for key in link_types))
        parts.append("Связи: %s" % kinds)

    if not parts:
        return ""
    return "## 2a. Что видно из задачи\n\n%s\n" % " · ".join(parts)


def _intent_line(validation):
    """Строка §1 «Что делается»: подпись intent-а и цитата, без пересчёта.

    Пустая строка, если ось не посчитана (артефакты до версии 4) — тогда
    шаблон печатает `N/A (нет данных в источнике)`, а не выдуманный вид работ.
    """
    items = validation.get("work_intent") or []
    if not isinstance(items, list) or not items:
        return ""
    top = items[0]
    if not isinstance(top, dict):
        return ""
    label = analysismod.intent_label(top.get("intent"))
    if not label:
        return ""
    evidence = str(top.get("evidence") or "").strip()
    if evidence:
        return "%s («%s»)" % (label, _shorten(evidence, 120))
    return label


def _checks_count(validation, status):
    return sum(
        1 for check in validation.get("checks") or [] if check.get("status") == status
    )


def _context_field(context, *keys):
    fields = context.get("fields") or {}
    for key in keys:
        if context.get(key) not in (None, ""):
            return context[key]
        if isinstance(fields, dict) and fields.get(key) not in (None, ""):
            return fields[key]
    return None


def _gap_what_map(validation):
    """check-id → факт из `checks[].message` (не пересказ, а поле артефакта)."""
    return {
        check.get("id"): check.get("message")
        for check in validation.get("checks") or []
    }


def _params_line(estimate):
    """Строка параметров задачи: значения → множитель (и baseline)."""
    params = estimate.get("params")
    if not isinstance(params, dict):
        return NA
    baseline = params.get("baseline") or {}
    baseline_source = params.get("baseline_source") or "defaults"
    multiplier = params.get("multiplier")
    text = "Параметры: weight=%s, heat=%s, connectivity=%s → ×%s (baseline: weight=%s, heat=%s, connectivity=%s, %s)" % (
        _num(params.get("weight")),
        _num(params.get("heat")),
        _num(params.get("connectivity")),
        _num(multiplier),
        _num(baseline.get("weight")),
        _num(baseline.get("heat")),
        _num(baseline.get("connectivity")),
        baseline_source,
    )
    return text


def _params_evidence(estimate):
    """Основания параметров: заголовок параметра — пункт, его сигналы — вложенно."""
    params = estimate.get("params")
    if not isinstance(params, dict):
        return NA
    lines = []
    for item in params.get("evidence") or []:
        text = str(item).strip()
        if not text:
            continue
        if text.startswith("·"):
            lines.append("  - %s" % text.lstrip("· ").strip())
        else:
            lines.append("- %s" % text)
    return "\n".join(lines) if lines else NA


def report_slots(
    validation,
    estimate,
    context=None,
    model=None,
    template_url=None,
    validation_path=None,
):
    """Скалярные слоты отчёта. Чистая функция, без чтения файлов.

    `template_url` — ссылка на целевой шаблон описания задачи из
    `validation.template_url` (None — встроенный дефолт). `validation_path` —
    путь к полному списку пробелов для компактных блоков секций 3–4.
    """
    context = context or {}
    template = validation.get("template") or {}
    total = estimate.get("total") or {}
    total_range = total.get("range") or []
    gaps = validation.get("gaps") or []
    what = _gap_what_map(validation)
    required = [gap for gap in gaps if gap.get("severity") == "REQUIRED"]
    optional = [gap for gap in gaps if gap.get("severity") != "REQUIRED"]
    display = validation_path or "validation.json"
    return {
        "task_key": estimate.get("task_key")
        or validation.get("task_key")
        or context.get("task_key"),
        "run_id": context.get("run_id"),
        "checked_at": validation.get("checked_at"),
        "estimated_at": estimate.get("estimated_at"),
        "verdict": validation.get("verdict"),
        "verdict_reason": _verdict_reason(validation),
        "intent_line": _intent_line(validation),
        "analysis_block": _analysis_block(validation, estimate),
        "with_dependencies": validation.get("with_dependencies"),
        "checks_passed": _checks_count(validation, "PASS"),
        "checks_failed": _checks_count(validation, "FAIL"),
        "checks_na": _checks_count(validation, "NA"),
        "template_name": template.get("name"),
        "template_version": template.get("version"),
        "template_sha256": template.get("sha256"),
        "model_version": estimate.get("model_version"),
        "model_checksum": estimate.get("model_checksum"),
        "task_summary": _context_field(context, "summary", "task_summary"),
        "issue_type": context.get("issue_type"),
        "role": context.get("role"),
        "work_kind": context.get("work_kind"),
        "sprint": _context_field(context, "sprint"),
        "status": _context_field(context, "status"),
        "task_url": _context_field(context, "url", "task_url"),
        "has_testing": context.get("has_testing"),
        "sp": context.get("sp"),
        "qa_estimation": context.get("qa_estimation"),
        "scale": ", ".join(_num(item) for item in (model or {}).get("scale") or []) or NA,
        "total_expected": total.get("expected"),
        "total_range": total_range,
        "total_range_low": total_range[0] if len(total_range) > 0 else None,
        "total_range_high": total_range[1] if len(total_range) > 1 else None,
        # Итог по ролям одной строкой: Dev · QA · Итого.
        "totals_line": _totals_line(estimate),
        # Надбавка за дополнительные ресурсы (RS-01); нет ресурсов — пустая строка.
        "resources_line": _resources_line(estimate),
        "total_dev": (
            total.get("expected") - (total.get("qa") or {}).get("expected")
            if isinstance(total.get("qa"), dict)
            and isinstance(total.get("expected"), int)
            else total.get("expected")
        ),
        "total_qa": (total.get("qa") or {}).get("expected")
        if isinstance(total.get("qa"), dict)
        else None,
        # Компактные блоки секций 3–4: ≤3 пункта, «и ещё N», ссылка на шаблон.
        "gaps_required_block": _compact_gaps_block(
            required,
            what,
            template_url,
            display,
            _gaps_headline(required, estimate),
            "Блокирующих пробелов нет — оценка не завышена.",
        ),
        "gaps_optional_block": _compact_gaps_block(
            optional,
            what,
            template_url,
            display,
            _notes_headline(optional),
            "Уточнять нечего.",
        ),
        "template_link": _template_link(template_url),
        "validation_path": display,
        # Секции 6–7: выжимка в 1–2 предложения (полные данные — в estimate.json).
        "variability_summary": _variability_summary(estimate, model),
        "provenance_summary": _provenance_summary(estimate, model),
        "refresh_expected_changes": (
            "пересчёт пробелов и оценки по актуальным данным; новый RUN-ID и delta.md"
        ),
        "refresh_unchanged": (
            "артефакты предыдущего прогона не переписываются"
        ),
        "delta_path": ".task-readiness/runs/%s/<новый RUN-ID>/delta.md"
        % (estimate.get("task_key") or validation.get("task_key") or "<TASK-KEY>"),
        # Таблицы целиком — для шаблонов, которые собирают их одним слотом.
        "checks_table": _table(
            ("Правило", "Раздел", "Важность", "Статус", "Пояснение"), _checks_rows(validation)
        ),
        "gaps_table": _table(
            ("Пробел", "Важность", "Вопрос", "Кому", "Где искать"), _gaps_rows(validation)
        ),
        "questions_table": _table(
            ("Пробел", "Вопрос", "Кому", "Где искать"), _questions_rows(validation)
        ),
        "roles_table": _table(
            ("Роль", "Ожидание", "Диапазон", "Уверенность", "Оптимистично", "База", "Пессимистично"),
            _roles_rows(estimate),
        ),
        "scenarios_table": _table(
            ("Роль", "Сценарий", "Пункты", "Почему"), _scenarios_rows(estimate)
        ),
        "provenance_table": _table(
            ("Роль", "Тип", "Значение", "Источник"), _provenance_rows(estimate)
        ),
        "variability_reason": _bullets(estimate.get("variability_reason")),
        "params_line": _params_line(estimate),
        "params_evidence": _params_evidence(estimate),
        "blocked_by_gaps": ", ".join(estimate.get("blocked_by_gaps") or []) or NA,
        "absent_roles": ", ".join((model or {}).get("absent_roles") or []) or NA,
        "sources_table": _table(
            ("Тип", "Система", "Ссылка", "Заголовок", "URL", "Уверенность"),
            _sources_rows(context, model),
        ),
        "similar_tasks_table": similar_tasks_table(estimate),
    }


def _variability_row(reason):
    """Разобрать строку `variability_reason` в слоты секции 6.

    `estimate.py` пишет причины уже в формате
    `GR-01: нет критериев приёмки → +2 шага (3 → 8), роль FE`. Рендерер обязан
    разложить её на rule_id / cause / effect / from / to, иначе секция 6
    показывает `N/A` вокруг готовой строки. Причина без этого формата остаётся
    в `cause`, остальные слоты — `NA`.
    """
    text = str(reason).strip()
    match = re.match(
        r"^(?P<rule>[A-Za-z]+-\d+):\s*(?P<cause>.+?)\s*→\s*(?P<effect>[^()]+?)"
        r"(?:\s*\((?P<from>[^)]+?)\s*→\s*(?P<to>[^)]+?)\))?"
        r"(?:,\s*роль\s+(?P<role>[A-Za-z]+))?\s*$",
        text,
    )
    if not match:
        return {
            "variability_line": text,
            "variability_rule_id": NA,
            "variability_cause": text,
            "variability_effect": NA,
            "variability_from": NA,
            "variability_to": NA,
        }
    return {
        "variability_line": text,
        "variability_rule_id": match.group("rule"),
        "variability_cause": match.group("cause").strip(),
        "variability_effect": match.group("effect").strip(),
        "variability_from": (match.group("from") or NA).strip(),
        "variability_to": (match.group("to") or NA).strip(),
    }


def report_rows(validation, estimate):
    """Слоты-строки по секциям: 3/4 — пробелы, 5 — роли, 6 — вариативность, 7 — провенанс."""
    what = _gap_what_map(validation)
    gaps = validation.get("gaps") or []

    def gap_row(gap):
        return {
            "gap_id": gap.get("id"),
            "gap_severity": gap.get("severity"),
            "gap_what": limits.truncate(what.get(gap.get("id")) or gap.get("question")),
            "gap_role": gap.get("target_role"),
            "gap_where": gap.get("where_to_find"),
        }

    roles = []
    for role in _sorted_roles(estimate.get("roles") or []):
        points_range = role.get("range") or []
        base_scenario = _scenario(role, "base") or {}
        roles.append(
            {
                "role_name": _role_label(role),
                "role_expected": role.get("expected"),
                "role_range_low": points_range[0] if len(points_range) > 0 else None,
                "role_range_high": points_range[1] if len(points_range) > 1 else None,
                "role_confidence": role.get("confidence"),
                "role_scenario_min": _scenario_points(role, "optimistic"),
                "role_scenario_base": _scenario_points(role, "base"),
                "role_scenario_max": _scenario_points(role, "pessimistic"),
                "role_reason": _reason_before_resources(
                    base_scenario.get("reason"), estimate, role
                ),
            }
        )

    variability = [
        _variability_row(reason)
        for reason in estimate.get("variability_reason") or []
    ]

    provenance = [
        {
            "prov_role": row[0],
            "prov_kind": row[1],
            "prov_value": row[2],
            "prov_source": row[3],
        }
        for row in _provenance_rows(estimate)
    ]

    return {
        3: {"gap": [gap_row(gap) for gap in gaps if gap.get("severity") == "REQUIRED"]},
        4: {"gap": [gap_row(gap) for gap in gaps if gap.get("severity") != "REQUIRED"]},
        5: {"role": roles},
        6: {"variability": variability},
        7: {"prov": provenance},
    }


def render(run_dir, template_path=None, template_url=None):
    """Отрендерить `report.md` из артефактов прогона.

    `run_dir` — каталог `.task-readiness/runs/<TASK-KEY>/<RUN-ID>`.
    Обязательны `validation.json` и `estimate.json`; `context.json` и модель
    читаются, если есть (иначе соответствующие слоты станут `NA`).
    `template_url` — `validation.template_url` из конфига: ссылка на шаблон
    описания задачи в компактных блоках секций 3–4.
    """
    run = Path(run_dir)
    validation = _read_json(run / "validation.json", required=True)
    estimate = _read_json(run / "estimate.json", required=True)
    context = _read_json(run / "context.json", required=False) or {}
    model = None
    model_path = model_path_for_run(run)
    if model_path is not None and model_path.is_file():
        model = _read_json(model_path, required=False)
    if not context.get("run_id"):
        context = dict(context)
        context["run_id"] = run.name
    template = _read_template(template_path, DEFAULT_REPORT_TEMPLATE)
    text = _substitute(
        template,
        report_slots(
            validation,
            estimate,
            context,
            model,
            template_url=template_url,
            validation_path=_validation_display(run),
        ),
        report_rows(validation, estimate),
    )
    text = _append_similar_section(text, estimate)
    return _append_params_section(text, estimate)


def _validation_display(run):
    """Путь к полному списку пробелов: `runs/<KEY>/<RUN>/validation.json`."""
    run = Path(run)
    return "runs/%s/%s/validation.json" % (run.parent.name, run.name)


def _append_params_section(text, estimate):
    """Добавить строку параметров, если шаблон её не содержит.

    Пользовательский шаблон отчёта может быть старше этапа C: тогда строка
    параметров и её основания дописываются в конец, чтобы отчёт не терял
    объяснение множителя. Отчёт без блока `params` (старая оценка) не меняется.
    """
    params = estimate.get("params")
    if not isinstance(params, dict):
        return text
    if "Параметры:" in text:
        return text
    lines = ["", "## Параметры оценки", "", _params_line(estimate), ""]
    evidence = _params_evidence(estimate)
    if evidence != NA:
        lines.append("**Основания параметров:**")
        lines.append("")
        lines.extend(evidence.split("\n"))
        lines.append("")
    return text.rstrip("\n") + "\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Комментарии в задачу Jira: валидация и оценка
# ---------------------------------------------------------------------------
#
# Два комментария — два разных вопроса читателя. «Результаты валидации»
# отвечают «можно ли брать в работу и что уточнить», «Результаты оценки» —
# «сколько это стоит и на чём основано». Смешивать их нельзя: в оценке не
# должно быть пробелов и инструкций по перегенерации, в валидации — ни одного
# числа SP.
#
# Эталон формата — `templates/jira-validation-comment.md` и
# `templates/jira-estimate-comment.md`. Рендер собран на f-строках, а не на
# подстановке слотов: у комментариев нет пользовательских шаблонов, зато есть
# жёсткое требование «коротко» (валидация ≤ ~40 строк, оценка ≤ ~25), и любая
# лишняя секция — баг формата, а не повод для слота.

# Максимум пунктов в блоках «что уточнить» и «гигиена полей»: остальное —
# одной строкой «и ещё N». Полные списки остаются в validation.json.
MAX_COMMENT_GAPS = 8

# Максимум похожих задач в комментарии оценки: ориентир, а не таблица.
MAX_COMMENT_SIMILAR = 3

# Длина строки «где искать» в блоке пробела: адрес нужен, простыня — нет.
COMMENT_WHERE_LIMIT = 90


def _comment_artifact_path(run, name):
    """Путь артефакта прогона в виде, привычном для читателя комментария."""
    return _validation_display(run).replace("validation.json", name)


def _comment_context_summary(context):
    """Заголовок задачи из снимка: верхний уровень приоритетнее `fields`."""
    return str(_context_field(context, "summary") or "").strip()


def _comment_gap_line(gap, with_where=False):
    """Пункт пробела: id, адресат, что нужно (и где искать)."""
    identifier = str(gap.get("id") or "").strip()
    role = str(gap.get("target_role") or "").strip()
    what = _sentence(gap.get("question") or "")
    head = "**%s**" % identifier if identifier else "**—**"
    if role:
        head += " (%s)" % role
    text = "%s — %s" % (head, what or "уточнить формулировку")
    if with_where:
        where = _shorten(
            re.sub(r"\s+", " ", str(gap.get("where_to_find") or "")).strip(),
            COMMENT_WHERE_LIMIT,
        )
        if where:
            text += " Где искать: %s" % where
    return text


def _comment_gap_block(gaps, headline, empty, with_where=False):
    """Блок пробелов: заголовок, до `MAX_COMMENT_GAPS` пунктов, «и ещё N»."""
    items = sorted(
        [gap for gap in gaps if isinstance(gap, dict)],
        key=lambda gap: str(gap.get("id")),
    )
    if not items:
        return [headline, "", empty, ""]
    lines = [headline, ""]
    for gap in items[:MAX_COMMENT_GAPS]:
        lines.append("- %s" % _comment_gap_line(gap, with_where=with_where))
    rest = len(items) - MAX_COMMENT_GAPS
    if rest > 0:
        lines.append("- и ещё %d — см. полный список" % rest)
    lines.append("")
    return lines


def _hygiene_checks(validation):
    """Провалы правил гигиены полей (`TPL-*`) — не пробелы содержания."""
    checks = [
        check
        for check in validation.get("checks") or []
        if isinstance(check, dict)
        and str(check.get("id") or "").startswith("TPL-")
        and check.get("status") in ("FAIL", "UNKNOWN")
    ]
    checks.sort(key=lambda check: str(check.get("id")))
    return checks


def _hygiene_line(check):
    identifier = str(check.get("id") or "").strip()
    return "**%s** — %s" % (identifier, _sentence(check.get("message") or ""))


def _hygiene_ids(validation):
    """Id правил гигиены, уже показанных отдельным блоком."""
    return {str(check.get("id")) for check in _hygiene_checks(validation)}


def render_validation_comment(run_dir):
    """Тело комментария «Результаты валидации»: только про готовность.

    Читает `validation.json` (+ `context.json` для подписи задачи). Ни одного
    числа SP, диапазона или записи провенанса здесь нет — это предмет второго
    комментария.
    """
    run = Path(run_dir)
    validation = _read_json(run / "validation.json", required=True)
    context = _optional_json(run / "context.json") or {}
    task_key = str(validation.get("task_key") or context.get("task_key") or run.parent.name)
    verdict = str(validation.get("verdict") or NA)
    summary = _comment_context_summary(context)

    title = "## Результаты валидации %s" % task_key
    if summary:
        title += " — %s" % _shorten(summary, 120)
    lines = [title, ""]
    lines.append("**Вердикт: %s** — %s" % (verdict, _sentence(_verdict_reason(validation))))
    intent = _intent_line(validation)
    if intent:
        lines.append("Понято как: %s" % intent)
    lines.append("")

    gaps = [gap for gap in validation.get("gaps") or [] if isinstance(gap, dict)]
    required = [gap for gap in gaps if gap.get("severity") == "REQUIRED"]
    hygiene = _hygiene_checks(validation)
    # Провал правила гигиены приходит и в `gaps[]`, и в `checks[]`. Показываем
    # его один раз — в блоке «Гигиена полей»: там у него есть сообщение проверки.
    hygiene_ids = {str(check.get("id")) for check in hygiene}
    recommended = [
        gap
        for gap in gaps
        if gap.get("severity") == "RECOMMENDED" and str(gap.get("id")) not in hygiene_ids
    ]

    lines.extend(
        _comment_gap_block(
            required,
            "### Блокирующие пробелы (%d)" % len(required),
            "нет — блокирующих пробелов нет",
            with_where=True,
        )
    )
    lines.extend(
        _comment_gap_block(
            recommended,
            "### Что уточнить (%d)" % len(recommended),
            "нечего — замечаний нет",
        )
    )

    if hygiene:
        lines.append("### Гигиена полей (%d)" % len(hygiene))
        lines.append("")
        for check in hygiene[:MAX_COMMENT_GAPS]:
            lines.append("- %s" % _hygiene_line(check))
        rest = len(hygiene) - MAX_COMMENT_GAPS
        if rest > 0:
            lines.append("- и ещё %d — см. полный список" % rest)
        lines.append("")

    lines.append(
        "Полный отчёт: `%s` · пробелы: `%s`"
        % (_comment_artifact_path(run, "report.md"), _validation_display(run))
    )
    lines.append("Перегенерировать: `/task-readiness-review check --task %s`" % task_key)
    return "\n".join(lines).rstrip("\n") + "\n"


def _confidence_rank(value):
    """Порядок уверенности: low < medium < high (для итоговой строки)."""
    return {"low": 0, "medium": 1, "high": 2}.get(str(value or "").strip().casefold(), 1)


def _total_confidence(roles):
    """Уверенность итога — самая слабая из ролей: итог не точнее своей части."""
    values = [role.get("confidence") for role in roles if role.get("confidence")]
    if not values:
        return NA
    return min(values, key=_confidence_rank)


def _role_points(role):
    expected = role.get("expected")
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return expected
    return 0


def _dev_line(roles):
    """`Dev: FE 3 SP` или `Dev: BE 2 + FE 3 = 5 SP`."""
    dev = [role for role in roles if role.get("role") != "QA"]
    if not dev:
        return None
    parts = ["%s %s SP" % (role.get("role"), _num(_role_points(role))) for role in dev]
    if len(parts) == 1:
        return "Dev: %s" % parts[0]
    total = sum(_role_points(role) for role in dev)
    return "Dev: %s = %s SP" % (" + ".join(parts), _num(total))


def _qa_line(estimate, roles):
    """`QA: 2 SP (расчёт модели)` либо объяснение из `qa_scope`."""
    qa_role = next((role for role in roles if role.get("role") == "QA"), None)
    if qa_role is not None:
        source = qa_role.get("source")
        note = "QA Estimation из Jira" if source == "jira" else "расчёт модели"
        return "QA: %s SP (%s)" % (_num(_role_points(qa_role)), note)
    scope = str(estimate.get("qa_scope") or "").strip()
    if scope:
        return "QA: %s" % scope
    return None


def _role_basis(role, context, model):
    """Основание числа в таблице: бакет, n, наличие эталона.

    Короткая строка на роль: читателю нужно понять, откуда взялось число, а не
    прочитать провенанс целиком (он остаётся в `estimate.json`).
    """
    name = str(role.get("role") or "")
    source = str(role.get("source") or "").strip()
    label = _bucket_of_role(role)
    if not label:
        issue_type = str(_context_field(context, "issue_type") or "").strip()
        work_kind = str(_context_field(context, "work_kind") or "").strip()
        label = "%s/%s/%s" % (name, issue_type or "unknown", work_kind or "unknown")

    if name == "QA" and source == "jira":
        return "QA Estimation из Jira"

    facts = _bucket_facts(model, label) or {}
    n = facts.get("n")
    reference = facts.get("reference")
    if reference is None and model is not None:
        reference = "yes" if _model_bucket(model, label) is not None else "no"
    parts = ["бакет %s" % label]
    if n is not None:
        parts.append("n=%s" % _num(n))
    if reference is not None:
        has_reference = str(reference).lower() in ("yes", "true", "1")
        parts.append("эталон есть" if has_reference else "эталона нет")
    basis = ", ".join(parts)
    if name == "QA" and source == "derived":
        return "расчёт модели, %s" % basis
    return basis


def _factor_of_role(role):
    """Фактор роли из `scenarios[base].reason`: `base 3 × factor 0.5 × params …`."""
    for scenario in role.get("scenarios") or []:
        if not isinstance(scenario, dict) or scenario.get("name") != "base":
            continue
        match = re.search(r"factor\s+([0-9]+(?:[.,][0-9]+)?)", str(scenario.get("reason") or ""))
        if match:
            return match.group(1).replace(",", ".")
    return None


def _params_bullet(estimate):
    """Пункт «множитель параметров ×0.6203 (weight/heat/connectivity)»."""
    params = estimate.get("params") or {}
    multiplier = params.get("multiplier")
    if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool):
        return None
    parts = []
    for name in ("weight", "heat", "connectivity"):
        value = params.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            parts.append("%s %s" % (name, _num(round(float(value), 4))))
    text = "множитель параметров ×%s" % _num(multiplier)
    if parts:
        text += " (%s)" % ", ".join(parts)
    return text


def _penalty_bullets(estimate):
    """Пункты «GR-01 +2 шага» — по одной строке на применённый штраф."""
    bullets = []
    for reason in estimate.get("variability_reason") or []:
        text = str(reason).strip()
        match = re.match(r"^(GR-[A-Za-z0-9]+):.*?→\s*\+(\d+)\s+шаг", text)
        if not match:
            continue
        bullets.append("штраф %s: +%s шага к оценке" % (match.group(1), match.group(2)))
    return bullets


def _resources_bonus(estimate):
    """`bonus_sp` надбавки RS-01, если она реально прибавила шаг, иначе 0."""
    resources = estimate.get("resources")
    if not isinstance(resources, dict):
        return 0.0
    bonus = resources.get("bonus_sp")
    if not isinstance(bonus, (int, float)) or isinstance(bonus, bool):
        return 0.0
    return float(bonus) if bonus > 0 else 0.0


def _reason_before_resources(reason, estimate, role):
    """Пометить `expected=N` в причине как значение **до** надбавки RS-01.

    `scenarios[base].reason` собирается до `_apply_resources`, поэтому несёт
    донадбавочное число, а колонка «Ожидаемо» показывает уже итог: рядом
    стоящие `expected=1` и `3` читаются как ошибка, а не как «+2 SP за
    ресурсы». Пометка ставится только строке, к которой надбавка применена
    (`resources.applied_to`), и только в режиме `add` (`bonus_sp > 0`); в
    остальных случаях причина печатается как есть.
    """
    text = str(reason or "")
    if not text or _resources_bonus(estimate) <= 0:
        return reason
    applied_to = str((estimate.get("resources") or {}).get("applied_to") or "").strip()
    if applied_to and str(role.get("role") or "").strip() != applied_to:
        return reason
    return re.sub(
        r"\bexpected=([0-9]+(?:[.,][0-9]+)?)",
        r"expected=\1 до RS-01",
        text,
        count=1,
    )


def _resources_bullet(estimate):
    """Пункт «дополнительные ресурсы: allure, e2e → +2 SP (mode add)»."""
    resources = estimate.get("resources")
    if not isinstance(resources, dict):
        return None
    items = [item for item in resources.get("items") or [] if isinstance(item, dict)]
    if not items:
        return None
    names = ", ".join(str(item.get("name")) for item in items)
    mode = str(resources.get("mode") or "add")
    if mode == "upper_bound":
        return "дополнительные ресурсы: %s → оценка по верхней границе (mode upper_bound)" % names
    return "дополнительные ресурсы: %s → +%s SP (mode %s)" % (
        names,
        _num_compact(resources.get("bonus_sp")),
        mode,
    )


def _absent_roles_bullet(model):
    """Пункт «нет данных по BA/SA/DEVOPS в эталоне» — если модель так говорит."""
    absent = [
        str(item).strip()
        for item in (model or {}).get("absent_roles") or []
        if str(item).strip()
    ]
    if not absent:
        return None
    return "нет данных по %s в эталоне — база только из спринтов" % "/".join(absent)


def _qa_derived_bullet(roles):
    """Пункт «QA посчитан моделью» — когда QA не из Jira."""
    for role in roles:
        if role.get("role") != "QA":
            continue
        if str(role.get("source") or "") == "derived":
            return "QA посчитан моделью (QA Estimation в Jira не заполнена)"
        return None
    return None


def _task_texts_for_run(run):
    """`key → summary` из `norm/task-texts.json` (пусто, если файла нет)."""
    for parent in Path(run).parents:
        if parent.name == STATE_DIR:
            path = parent / "norm" / "task-texts.json"
            break
    else:
        return {}
    data = _optional_json(path) or {}
    titles = {}
    for item in data.get("tasks") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if key and summary:
            titles[key] = summary
    return titles


def _range_extended_by(estimate, model, context):
    """Ключи задач, расширивших диапазон (`vector_nn` в причинах), или [].

    Диапазон расширяют только при `adjust_range: true`: причина в
    `variability_reason[]` начинается с `vector_nn:`. Называем соседей того же
    бакета, чей SP вышел за пределы диапазона бакета в модели, но попал в
    итоговый диапазон роли — именно они и растянули интервал.
    """
    reasons = estimate.get("variability_reason") or []
    if not any(str(reason).strip().startswith("vector_nn:") for reason in reasons):
        return []

    issue_type = str(_context_field(context, "issue_type") or "").strip()
    work_kind = str(_context_field(context, "work_kind") or "").strip()
    keys = []
    for role in estimate.get("roles") or []:
        name = str(role.get("role") or "")
        label = _bucket_of_role(role) or "%s/%s/%s" % (
            name,
            issue_type or "unknown",
            work_kind or "unknown",
        )
        bucket = _model_bucket(model, label) or {}
        base_range = list(bucket.get("range") or []) + [None, None]
        final_range = list(role.get("range") or []) + [None, None]
        base_low, base_high = base_range[0], base_range[1]
        final_low, final_high = final_range[0], final_range[1]
        if None in (base_low, base_high, final_low, final_high):
            continue
        for item in estimate.get("similar_tasks") or []:
            if not isinstance(item, dict) or not item.get("same_bucket"):
                continue
            if item.get("role") != name:
                continue
            sp = item.get("sp")
            if not isinstance(sp, (int, float)) or isinstance(sp, bool):
                continue
            below = sp < base_low and sp >= final_low
            above = sp > base_high and sp <= final_high
            if below or above:
                keys.append(str(item.get("key")))
    return [key for key in dict.fromkeys(keys) if key]


def _similar_bullets(estimate, titles):
    """Пункты «Похожие задачи»: ключ, заголовок, SP, cosine.

    `adjust_range: false` — векторы справочные: комментарий говорит это прямо,
    иначе читатель решит, что диапазон посчитан по соседям.
    """
    items = [
        item
        for item in estimate.get("similar_tasks") or []
        if isinstance(item, dict) and item.get("key")
    ]
    if not items:
        return []
    bullets = []
    for item in items[:MAX_COMMENT_SIMILAR]:
        key = str(item.get("key"))
        title = titles.get(key)
        sp = item.get("sp")
        cosine = item.get("cosine")
        text = "**%s**" % key
        if title:
            text += " «%s»" % _shorten(title, 70)
        if isinstance(sp, (int, float)) and not isinstance(sp, bool):
            text += " — %s SP" % _num(sp)
        if isinstance(cosine, (int, float)) and not isinstance(cosine, bool):
            text += " (cosine %.2f)" % float(cosine)
        bullets.append(text)
    return bullets


def render_estimate_comment(run_dir):
    """Тело комментария «Результаты оценки»: только полезное.

    Строго компактно: заголовок, итог, таблица ролей с основанием, «на чём
    базируется» и (если есть) похожие задачи. Ни пробелов, ни дампа провенанса,
    ни инструкций по перегенерации — это предмет комментария валидации.
    """
    run = Path(run_dir)
    estimate = _read_json(run / "estimate.json", required=True)
    context = _optional_json(run / "context.json") or {}
    model = None
    model_path = model_path_for_run(run)
    if model_path is not None and model_path.is_file():
        model = _optional_json(model_path)

    task_key = str(estimate.get("task_key") or context.get("task_key") or run.parent.name)
    summary = _comment_context_summary(context)
    roles = _sorted_roles(estimate.get("roles") or [])
    total = estimate.get("total") or {}
    expected = total.get("expected")
    low, high = (total.get("range") or [None, None])[:2]

    title = "## Оценка %s" % task_key
    if summary:
        title += " — %s" % _shorten(summary, 120)
    lines = [title, ""]

    headline = "**Итого: %s SP**" % _num(expected)
    if low is not None and high is not None:
        headline += " (диапазон %s–%s, уверенность %s)" % (
            _num(low),
            _num(high),
            _total_confidence(roles),
        )
    totals = [part for part in (_dev_line(roles), _qa_line(estimate, roles)) if part]
    if totals:
        headline += " · %s" % " · ".join(totals)
    lines.extend([headline, ""])

    rows = []
    for role in roles:
        role_low, role_high = (role.get("range") or [None, None])[:2]
        rows.append(
            (
                _role_label(role),
                _num(role.get("expected")),
                "%s–%s" % (_num(role_low), _num(role_high))
                if role_low is not None and role_high is not None
                else NA,
                role.get("confidence"),
                _role_basis(role, context, model),
            )
        )
    if rows:
        lines.append(_table(("Роль", "SP", "Диапазон", "Уверенность", "Основание"), rows))
        lines.append("")

    basis = []
    for role in roles:
        label = _bucket_of_role(role)
        if not label:
            continue
        facts = _bucket_facts(model, label) or {}
        parts = ["бакет %s" % label]
        if facts.get("base") is not None:
            parts.append("base %s" % _num(facts["base"]))
        factor = _factor_of_role(role)
        if factor:
            parts.append("фактор ×%s" % factor)
        basis.append(": ".join([parts[0], ", ".join(parts[1:])]) if len(parts) > 1 else parts[0])
    params_bullet = _params_bullet(estimate)
    if params_bullet:
        basis.append(params_bullet)
    basis.extend(_penalty_bullets(estimate))
    resources_bullet = _resources_bullet(estimate)
    if resources_bullet:
        basis.append(resources_bullet)
    absent = _absent_roles_bullet(model)
    if absent:
        basis.append(absent)
    qa_derived = _qa_derived_bullet(roles)
    if qa_derived:
        basis.append(qa_derived)
    # 3–6 пунктов: больше — уже дамп, меньше — не объясняет число.
    basis = basis[:6]
    if basis:
        lines.append("### На чём базируется оценка")
        lines.append("")
        for bullet in basis:
            lines.append("- %s" % bullet)
        lines.append("")

    titles = _task_texts_for_run(run)
    similar = _similar_bullets(estimate, titles)
    if similar:
        lines.append("### Похожие задачи")
        lines.append("")
        for bullet in similar:
            lines.append("- %s" % bullet)
        extended = _range_extended_by(estimate, model, context)
        if extended:
            lines.append(
                "- диапазон расширен по %s" % ", ".join(extended)
            )
        else:
            lines.append(
                "- справочно, числа не меняет (adjust_range выключен)"
            )
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# Нормализованные данные: `.md`-зеркала `norm/`
# ---------------------------------------------------------------------------


def _reference_rows(reference):
    """Строки бакетов эталона: детерминированный порядок `(role, work_kind)`."""
    buckets = [item for item in reference.get("buckets") or [] if isinstance(item, dict)]
    buckets.sort(key=lambda item: (str(item.get("role")), str(item.get("work_kind"))))
    return [
        (
            bucket.get("role"),
            bucket.get("work_kind"),
            bucket.get("value"),
            bucket.get("level"),
            bucket.get("example_count"),
            (bucket.get("params_hint") or {}).get("weight"),
            (bucket.get("params_hint") or {}).get("heat"),
            bucket.get("description"),
            bucket.get("evidence"),
        )
        for bucket in buckets
    ]


def _level_rows(reference):
    """Строки матрицы эталона: `sp` по возрастанию, `null`-ячейки — как N/A."""
    levels = [item for item in reference.get("levels") or [] if isinstance(item, dict)]
    levels.sort(key=lambda item: item.get("sp") if item.get("sp") is not None else 0)
    rows = []
    for level in levels:
        rows.append(
            (
                level.get("sp"),
                level.get("description"),
                level.get("uncertainty"),
                level.get("refactoring"),
                level.get("research"),
                level.get("decomposition"),
                level.get("time"),
                _examples_summary(level.get("examples")),
            )
        )
    return rows


def _examples_summary(examples):
    """`BE 5 · FE 4 · QA 3` — сколько примеров роли в строке (нет — `NA`)."""
    if not isinstance(examples, dict):
        return NA
    parts = []
    for role in ("BE", "FE", "QA"):
        items = examples.get(role)
        if isinstance(items, list) and items:
            parts.append("%s %d" % (role, len(items)))
    return " · ".join(parts) if parts else NA


def _hint_rows(reference):
    """Строки приоров: `sp | weight | heat | connectivity` из `levels[]`."""
    levels = [item for item in reference.get("levels") or [] if isinstance(item, dict)]
    levels.sort(key=lambda item: item.get("sp") if item.get("sp") is not None else 0)
    rows = []
    for level in levels:
        hint = level.get("params_hint")
        if not isinstance(hint, dict):
            continue
        rows.append(
            (
                level.get("sp"),
                hint.get("weight"),
                hint.get("heat"),
                hint.get("connectivity"),
            )
        )
    return rows


def render_reference_estimates(reference):
    """Markdown-зеркало `norm/reference-estimates.json` — без слотов и времени.

    Показывает источник, нормативную шкалу, роли, отсутствующие в эталоне,
    полную матрицу эталонной таблицы (7 строк × 8 колонок), приоры уровней и
    таблицу бакетов с цитатой (`evidence`) на каждое значение: у каждого числа
    виден провенанс, а не пересказ. Артефакт без `levels` рендерится как раньше
    (раздел матрицы — `N/A`), поэтому старые JSON не ломают рендер.
    """
    reference = reference or {}
    source = reference.get("source") or {}
    source_id = "%s:%s" % (source.get("system") or NA, source.get("page_id") or NA)
    header_rows = [
        ("Источник", source_id),
        ("Заголовок", source.get("title")),
        ("URL", source.get("url")),
    ]
    if source.get("space_key") is not None:
        header_rows.append(("Пространство", source.get("space_key")))
    if source.get("version") is not None:
        header_rows.append(("Версия страницы", source.get("version")))
    header_rows.extend(
        [
            ("Снимок", source.get("retrieved_at")),
            (
                "Шкала",
                ", ".join(_num(item) for item in reference.get("scale") or []),
            ),
            ("Роли вне эталона", ", ".join(reference.get("absent_roles") or [])),
        ]
    )
    lines = ["# Эталон оценки Story Points", "", _table(("Поле", "Значение"), header_rows), ""]
    if reference.get("absent_roles_note"):
        lines.extend(["Провенанс отсутствия ролей: %s" % _text(reference["absent_roles_note"]), ""])
    lines.extend(
        [
            "## Матрица эталонной таблицы",
            "",
            _table(
                (
                    "SP",
                    "Описание",
                    "Неопределённость",
                    "Рефакторинг",
                    "Исследование",
                    "Декомпозиция",
                    "Примерное время",
                    "Примеры (BE · FE · QA)",
                ),
                _level_rows(reference),
            ),
            "",
            "## Приоры уровней",
            "",
            _table(
                ("SP", "weight", "heat", "connectivity"),
                _hint_rows(reference),
            ),
            "",
            "## Бакеты эталона",
            "",
            _table(
                (
                    "Роль",
                    "Вид работ",
                    "Значение (sp)",
                    "Уровень",
                    "Примеров",
                    "weight",
                    "heat",
                    "Что описывает",
                    "Цитата из источника",
                ),
                _reference_rows(reference),
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _stats_rows(stats):
    buckets = [item for item in stats.get("buckets") or [] if isinstance(item, dict)]
    buckets.sort(
        key=lambda item: (
            str(item.get("role")),
            str(item.get("issue_type")),
            str(item.get("work_kind")),
        )
    )
    return [
        (
            bucket.get("role"),
            bucket.get("issue_type"),
            bucket.get("work_kind"),
            bucket.get("n"),
            bucket.get("mean"),
            bucket.get("median"),
            bucket.get("p25"),
            bucket.get("p75"),
            bucket.get("min"),
            bucket.get("max"),
            bucket.get("coverage"),
        )
        for bucket in buckets
    ]


def render_sprint_stats(stats):
    """Markdown-зеркало `norm/sprint-stats.json` — без слотов и времени.

    Одна строка на бакет `(role, issue_type, work_kind)` с `n`, квантилями и
    `coverage`; недостаточная выборка перечислена отдельной строкой, чтобы
    `WARN` был виден без чтения JSON.
    """
    stats = stats or {}
    insufficient = [str(item) for item in stats.get("insufficient") or []]
    lines = [
        "# Статистика спринтов",
        "",
        "Посчитано: `%s`. Строк в выборке: `%s`."
        % (_text(stats.get("computed_at")), _text(stats.get("sample_rows"))),
        "",
        "| Роль | Тип задачи | Вид работ | n | mean | median | p25 | p75 | min | max | coverage |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    rows = _stats_rows(stats)
    if rows:
        lines.extend(
            "| %s |" % " | ".join(_cell(value) for value in row) for row in rows
        )
    else:
        lines.append("| %s |" % " | ".join([NA] * 11))
    lines.extend(
        [
            "",
            "Недостаточная выборка: %s."
            % (", ".join(insufficient) if insufficient else "нет"),
            "",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Страница модели
# ---------------------------------------------------------------------------


def _reference_source(model, reference):
    """Источник эталона: `reference.source` главнее `model.sources.reference`.

    В модели лежит усечённая копия (`system`, `page_id`, `retrieved_at`, `url`),
    полная — в `norm/reference-estimates.json` (`title`, `version`, `space_key`).
    Отсутствие обоих не ошибка: слоты станут `NA`.
    """
    model_source = (model.get("sources") or {}).get("reference") or {}
    reference_source = (reference or {}).get("source") or {}
    merged = {}
    for key in (
        "system",
        "page_id",
        "space_key",
        "title",
        "url",
        "version",
        "retrieved_at",
    ):
        value = reference_source.get(key)
        if value is None:
            value = model_source.get(key)
        if value is not None:
            merged[key] = value
    return merged


def _sprint_rows(model, sample):
    """Спринты калибровки: `id, name, state, start, end`.

    Даты и состояние берутся из `model.sources.sprints[]`, а если там их нет —
    из `norm/sprint-sample.json` (`source.sprints[]`): в модели допустим
    усечённый список, но даты в источнике есть, и терять их нельзя.
    """
    sample_sprints = {}
    for item in ((sample or {}).get("source") or {}).get("sprints") or []:
        if isinstance(item, dict) and item.get("id") is not None:
            sample_sprints[str(item.get("id"))] = item
    rows = []
    for sprint in (model.get("sources") or {}).get("sprints") or []:
        if not isinstance(sprint, dict):
            continue
        extra = sample_sprints.get(str(sprint.get("id"))) or {}
        rows.append(
            (
                sprint.get("id"),
                sprint.get("name"),
                sprint.get("state") or extra.get("state"),
                sprint.get("start") or sprint.get("start_date") or extra.get("start"),
                sprint.get("end") or sprint.get("end_date") or extra.get("end"),
            )
        )
    return rows


def _params_hint_text(hint):
    """`weight=0.5 · heat=0.5 · connectivity=0.5`; нет приоров — `NA`."""
    if not isinstance(hint, dict) or not hint:
        return NA
    parts = [
        "%s=%s" % (name, _num(hint.get(name)))
        for name in ("weight", "heat", "connectivity")
        if hint.get(name) is not None
    ]
    return " · ".join(parts) if parts else NA


def _reference_bucket_rows(reference):
    """Бакеты эталона: роль, вид работ, значение, уровень, примеры, приоры, цитата."""
    buckets = [
        item for item in (reference or {}).get("buckets") or [] if isinstance(item, dict)
    ]
    buckets.sort(
        key=lambda item: (
            _role_key(item.get("role")),
            str(item.get("role")),
            str(item.get("work_kind")),
        )
    )
    return [
        (
            bucket.get("role"),
            bucket.get("work_kind"),
            bucket.get("value"),
            bucket.get("level"),
            bucket.get("example_count"),
            _params_hint_text(bucket.get("params_hint")),
            bucket.get("description"),
            bucket.get("evidence"),
        )
        for bucket in buckets
    ]


def _model_has_params(model):
    return isinstance(model.get("params"), dict)


def _model_bucket_headers(model):
    """Шапка таблицы бакетов модели; без блока `params` — без колонки множителя."""
    headers = ["Роль", "Тип задачи", "Вид работ", "База", "Фактор"]
    if _model_has_params(model):
        headers.append("Множитель (`params_multiplier`)")
    headers.extend(["Ожидание", "Диапазон", "n", "Уверенность", "Эталон"])
    if _model_has_params(model):
        headers.append("Профиль параметров (`params_profile_source`)")
    return headers


def _model_bucket_rows(model):
    """Строки таблицы бакетов модели — ровно под `_model_bucket_headers`."""
    with_params = _model_has_params(model)
    rows = []
    for bucket in _sorted_buckets(model):
        row = [
            bucket.get("role"),
            bucket.get("issue_type"),
            bucket.get("work_kind"),
            bucket.get("base"),
            bucket.get("factor"),
        ]
        if with_params:
            row.append(bucket.get("params_multiplier"))
        row.extend(
            [
                bucket.get("expected"),
                bucket.get("range"),
                bucket.get("n"),
                bucket.get("confidence"),
                bucket.get("reference"),
            ]
        )
        if with_params:
            row.append(bucket.get("params_profile_source"))
        rows.append(tuple(row))
    return rows


def _model_provenance_rows(model):
    """Провенанс по бакетам: одна строка на запись `buckets[].provenance[]`.

    Отдельное имя от `_provenance_rows` (провенанс оценки): раньше оба
    определения назывались одинаково, Python оставлял последнее, и в секции
    провенанса оценки рендерилось `N/A`.
    """
    rows = []
    for bucket in _sorted_buckets(model):
        label = "%s/%s/%s" % (
            bucket.get("role"),
            bucket.get("issue_type"),
            bucket.get("work_kind"),
        )
        for item in bucket.get("provenance") or []:
            if not isinstance(item, dict):
                continue
            rows.append(
                (
                    label,
                    item.get("field"),
                    item.get("kind"),
                    item.get("source"),
                    item.get("detail"),
                )
            )
    return rows


def _roles_rows(model):
    """Роли модели: есть ли эталон и сколько бакетов на роль."""
    counts = {}
    with_reference = set()
    for bucket in model.get("buckets") or []:
        role = bucket.get("role")
        counts[role] = counts.get(role, 0) + 1
        if bucket.get("reference") == "yes":
            with_reference.add(role)
    order = list(ROLE_ORDER) + sorted(
        role for role in counts if role not in ROLE_ORDER and role is not None
    )
    rows = []
    for role in order:
        rows.append(
            (
                role,
                "есть" if role in with_reference else "нет",
                counts.get(role, 0),
                "бакетов нет — роль в модели не оценивается"
                if not counts.get(role)
                else ("reference=none" if role not in with_reference else "—"),
            )
        )
    return rows


def _params_block(model):
    """Блок `params`: настройки, коэффициенты, источники и провенанс."""
    params = model.get("params")
    if not isinstance(params, dict):
        return NA
    coefficients = params.get("coefficients") or {}
    defaults = params.get("defaults") or {}
    clamp = params.get("clamp") or []
    clamp_text = (
        "[%s, %s]" % (_num(clamp[0]), _num(clamp[1])) if len(clamp) >= 2 else NA
    )
    rows = [
        ("Включён (`enabled`)", params.get("enabled")),
        ("Ограничение множителя (`clamp`)", clamp_text),
        (
            "Коэффициенты (`coefficients`)",
            ", ".join(
                "%s=%s" % (name, _num(coefficients.get(name)))
                for name in ("weight", "heat", "connectivity")
                if coefficients.get(name) is not None
            )
            or NA,
        ),
        (
            "Источник коэффициентов (`coefficients_source`)",
            params.get("coefficients_source"),
        ),
        (
            "Профиль по умолчанию (`defaults`)",
            ", ".join(
                "%s=%s" % (name, _num(defaults.get(name)))
                for name in ("weight", "heat", "connectivity")
                if defaults.get(name) is not None
            )
            or NA,
        ),
        ("Источник профиля (`profile_source`)", params.get("profile_source")),
    ]
    provenance = [
        (
            item.get("field"),
            item.get("kind"),
            item.get("source"),
            item.get("detail"),
        )
        for item in params.get("provenance") or []
        if isinstance(item, dict)
    ]
    return "\n".join(
        [
            _table(("Поле", "Значение"), rows),
            "",
            "Провенанс параметров:",
            "",
            _table(("Поле", "Вид", "Источник", "Детали"), provenance),
        ]
    )


def _resources_block(model):
    """Блок `resources`: надбавка `RS-01`, каталог ресурсов и провенанс."""
    resources = model.get("resources")
    if not isinstance(resources, dict):
        return NA
    items = resources.get("items") if isinstance(resources.get("items"), dict) else {}
    rows = [
        ("Правило (`rule_id`)", resources.get("rule_id") or NA),
        (
            "Включено (`enabled`)",
            # Отсутствующий флаг — маркер `N/A`, а не «нет»: «нет» означало бы
            # выключенное правило, хотя блок просто не описывает флаг.
            NA
            if resources.get("enabled") is None
            else ("да" if resources.get("enabled") else "нет"),
        ),
        (
            "Надбавка за ресурс (`sp_per_resource`)",
            _num_compact(resources.get("sp_per_resource")),
        ),
        ("Режим (`mode`)", resources.get("mode") or NA),
        ("Ресурсов в каталоге", len(items) or NA),
    ]
    item_rows = [
        (
            name,
            ", ".join(str(alias) for alias in aliases or []) or NA,
            len(aliases or []),
        )
        for name, aliases in sorted(items.items())
    ]
    provenance = [
        (
            item.get("field"),
            item.get("kind"),
            item.get("source"),
            item.get("detail"),
        )
        for item in resources.get("provenance") or []
        if isinstance(item, dict)
    ]
    return "\n".join(
        [
            _table(("Поле", "Значение"), rows),
            "",
            "Каталог ресурсов (алиасы — подстроки в тексте задачи):",
            "",
            _table(("Ресурс", "Алиасы", "Алиасов"), item_rows),
            "",
            "Провенанс надбавки:",
            "",
            _table(("Поле", "Вид", "Источник", "Детали"), provenance),
        ]
    )


def _model_formula_rows(model):
    rows = []
    for bucket in _sorted_buckets(model):
        base = bucket.get("base")
        factor = bucket.get("factor")
        expected = bucket.get("expected")
        multiplier = bucket.get("params_multiplier")
        has_multiplier = isinstance(multiplier, (int, float)) and not isinstance(
            multiplier, bool
        )
        product = None
        if isinstance(base, (int, float)) and isinstance(factor, (int, float)):
            product = base * factor
            if has_multiplier:
                product *= float(multiplier)
            product = round(product, 4)
        if has_multiplier:
            formula = (
                "nearest_scale(%s × %s × %s) = nearest_scale(%s) → %s"
                % (
                    _num(base),
                    _num(factor),
                    _num(multiplier),
                    _num(product),
                    _num(expected),
                )
            )
        else:
            # Модель до этапа C: поля params_multiplier нет — формула без него.
            formula = "nearest_scale(%s × %s) = nearest_scale(%s) → %s" % (
                _num(base),
                _num(factor),
                _num(product),
                _num(expected),
            )
        rows.append(
            (
                "%s/%s/%s"
                % (bucket.get("role"), bucket.get("issue_type"), bucket.get("work_kind")),
                formula,
            )
        )
    return rows


def _sorted_buckets(model):
    return sorted(
        model.get("buckets") or [],
        key=lambda bucket: (
            _role_key(bucket.get("role")),
            str(bucket.get("role")),
            str(bucket.get("issue_type")),
            str(bucket.get("work_kind")),
        ),
    )


def _model_limitations(model):
    lines = []
    absent = model.get("absent_roles") or []
    if absent:
        lines.append(
            "Роли %s в эталоне отсутствуют: база для них берётся только из "
            "статистики спринтов, reference=none, уверенность ниже, чем у "
            "ролей с эталоном." % ", ".join(absent)
        )
    low = [
        "%s/%s/%s (n=%s)"
        % (
            bucket.get("role"),
            bucket.get("issue_type"),
            bucket.get("work_kind"),
            _num(bucket.get("n")),
        )
        for bucket in _sorted_buckets(model)
        if bucket.get("confidence") == "low"
    ]
    if low:
        lines.append("Бакеты с низкой уверенностью: %s." % ", ".join(low))
    else:
        lines.append("Бакетов с низкой уверенностью нет.")
    return _bullets(lines)


def _skill_version():
    path = Path(configmod.SKILL_ROOT) / "VERSION"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def model_page_slots(model, reference=None, stats=None, sample=None, cfg=None, state=None):
    """Слоты страницы модели: все данные модели, эталона и статистики.

    Страница — не пересказ, а зеркало артефактов: шкала и матрица уровней,
    бакеты эталона с цитатами, статистика спринтов по всем метрикам, бакеты
    модели с множителем, провенанс каждой записи, правила пробелов и блок
    `params`. Любой отсутствующий вход (`reference`/`stats`/`sample`/`cfg`/
    `state` = None) даёт `NA` в слоте, но не ошибку: старые артефакты
    рендерятся.
    """
    model = model or {}
    reference = reference or {}
    stats = stats or {}
    sample = sample or {}
    cfg = cfg or {}
    state = state or {}
    source = _reference_source(model, reference)
    sprints = (model.get("sources") or {}).get("sprints") or []
    gap_penalties = [
        rule.get("penalty_steps")
        for rule in model.get("gap_rules") or []
        if isinstance(rule.get("penalty_steps"), int)
    ]
    low = [
        "%s/%s/%s (n=%s)"
        % (
            bucket.get("role"),
            bucket.get("issue_type"),
            bucket.get("work_kind"),
            _num(bucket.get("n")),
        )
        for bucket in _sorted_buckets(model)
        if bucket.get("confidence") == "low"
    ]
    absent = model.get("absent_roles") or []
    params = model.get("params") if isinstance(model.get("params"), dict) else {}
    clamp = params.get("clamp") or []
    validation = cfg.get("validation") or {}
    try:
        from trr_impl import check as checkmod

        min_description_chars = checkmod.MIN_DESCRIPTION_CHARS
    except (ImportError, AttributeError):
        min_description_chars = validation.get("min_description_chars")

    model_page = state.get("model_page") or {}
    published = {}
    for item in state.get("published") or []:
        if isinstance(item, dict) and str(item.get("ref")) == str(model_page.get("id")):
            published = item
            break
    insufficient = [str(item) for item in stats.get("insufficient") or []]
    return {
        "model_version": model.get("version"),
        "generated_at": model.get("generated_at"),
        "model_checksum": model.get("checksum"),
        "scale": ", ".join(_num(item) for item in model.get("scale") or []) or NA,
        "absent_roles": ", ".join(absent) or NA,
        "reference_system": source.get("system"),
        "reference_page_id": source.get("page_id"),
        "reference_space_key": source.get("space_key"),
        "reference_title": source.get("title"),
        "reference_url": source.get("url"),
        "reference_version": source.get("version"),
        "reference_retrieved_at": source.get("retrieved_at"),
        "reference_scale": ", ".join(
            _num(item) for item in reference.get("scale") or model.get("scale") or []
        )
        or NA,
        "sprints_table": _table(
            ("ID", "Спринт", "Состояние", "Начало", "Конец"),
            _sprint_rows(model, sample),
        ),
        "sprint_count": len(sprints) or None,
        "board_id": (sample.get("source") or {}).get("board_id"),
        "sample_rows": stats.get("sample_rows"),
        "stats_computed_at": stats.get("computed_at"),
        "sprints_retrieved_at": (sample.get("source") or {}).get("retrieved_at"),
        "levels_table": _table(
            (
                "SP",
                "Описание",
                "Неопределённость",
                "Рефакторинг",
                "Исследование",
                "Декомпозиция",
                "Примерное время",
                "Примеры (BE · FE · QA)",
            ),
            _level_rows(reference),
        ),
        "level_hints_table": _table(
            ("SP", "weight", "heat", "connectivity"), _hint_rows(reference)
        ),
        "roles_table": _table(
            ("Роль", "Эталон", "Бакетов", "Ограничение"), _roles_rows(model)
        ),
        "reference_buckets_table": _table(
            (
                "Роль",
                "Вид работ",
                "Значение (sp)",
                "Уровень",
                "Примеров",
                "Приоры (`params_hint`)",
                "Что описывает",
                "Цитата из источника",
            ),
            _reference_bucket_rows(reference),
        ),
        "reference_bucket_count": len(reference.get("buckets") or []),
        "stats_table": _table(
            (
                "Роль",
                "Тип задачи",
                "Вид работ",
                "n",
                "mean",
                "median",
                "p25",
                "p75",
                "min",
                "max",
                "coverage",
            ),
            _stats_rows(stats),
        ),
        "stats_bucket_count": len(stats.get("buckets") or []),
        "insufficient_list": ", ".join(insufficient) if insufficient else "нет",
        "insufficient_count": len(insufficient),
        "base_fallback_source": (
            "статистика спринтов (sprint-stats), потому что в эталоне нет ролей: %s"
            % ", ".join(absent)
            if absent
            else "эталон Story Points"
        ),
        "min_sample_n": validation.get("min_sample_n"),
        "min_description_chars": min_description_chars,
        "factor_clamp_min": clamp[0] if len(clamp) >= 2 else None,
        "factor_clamp_max": clamp[1] if len(clamp) >= 2 else None,
        "gap_penalty_max_steps": max(gap_penalties) if gap_penalties else None,
        "absent_roles_effect": (
            "для ролей %s reference=none, база только из статистики спринтов, "
            "уверенность не может быть high" % ", ".join(absent)
            if absent
            else "все роли есть в эталоне"
        ),
        "insufficient_buckets": ", ".join(low) if low else "нет",
        "validation_rules_path": "references/validation-rules.md",
        "skill_version": _skill_version(),
        "published_at": published.get("published_at"),
        "model_page_url": model_page.get("url"),
        "buckets_table": _table(_model_bucket_headers(model), _model_bucket_rows(model)),
        "model_bucket_count": len(model.get("buckets") or []),
        "provenance_table": _table(
            ("Бакет", "Поле", "Вид", "Источник", "Детали"), _model_provenance_rows(model)
        ),
        "provenance_count": len(_model_provenance_rows(model)),
        "gap_rules_table": _table(
            ("Правило", "Условие", "Шагов", "Роли"),
            [
                (
                    rule.get("rule_id"),
                    rule.get("condition"),
                    rule.get("penalty_steps"),
                    ", ".join(rule.get("applies_to") or []),
                )
                for rule in model.get("gap_rules") or []
            ],
        ),
        "gap_rules_count": len(model.get("gap_rules") or []),
        "resources_block": _resources_block(model),
        "resources": _resources_block(model),
        "resources_rule_id": (model.get("resources") or {}).get("rule_id")
        if isinstance(model.get("resources"), dict)
        else None,
        "resources_sp_per_resource": (
            _num_compact((model.get("resources") or {}).get("sp_per_resource"))
            if isinstance(model.get("resources"), dict)
            else None
        ),
        "resources_mode": (model.get("resources") or {}).get("mode")
        if isinstance(model.get("resources"), dict)
        else None,
        "params_block": _params_block(model),
        "params_enabled": params.get("enabled"),
        "params_clamp": (
            "[%s, %s]" % (_num(clamp[0]), _num(clamp[1])) if len(clamp) >= 2 else None
        ),
        "params_coefficients_source": params.get("coefficients_source"),
        "params_profile_source": params.get("profile_source"),
        "formula": _table(("Бакет", "Расчёт"), _model_formula_rows(model)),
        "limitations": _model_limitations(model),
    }


_APPENDIX_SECTIONS = (
    ("reference_buckets_table", "### Эталонные бакеты"),
    ("stats_table", "### Статистика спринтов"),
    ("buckets_table", "## Приложение. Бакеты модели"),
    ("provenance_table", "### Провенанс бакетов"),
    ("gap_rules_table", "### Правила пробелов"),
    ("params_block", "### Параметры модели"),
    ("resources_block", "### Дополнительные ресурсы (RS-01)"),
    ("formula", "### Формула по бакетам"),
)


def _append_model_appendix(text, template, model, slots=None):
    """Добавить таблицы данных, которых нет в шаблоне.

    Боевой `templates/model-page.md` содержит все слоты. Резервный (встроенный)
    шаблон короче — тогда недостающие таблицы добавляются приложением из данных
    модели, чтобы страница не теряла провенанс, статистику и правила.
    """
    slots = slots or model_page_slots(model)
    missing = [
        (title, slots[key])
        for key, title in _APPENDIX_SECTIONS
        if "{{%s}}" % key not in template
    ]
    if not missing:
        return text
    appendix = []
    for title, value in missing:
        appendix.extend([title, "", value, ""])
    return text.rstrip("\n") + "\n\n" + "\n".join(appendix).rstrip("\n") + "\n"


def render_model_page(
    model, template_path=None, reference=None, stats=None, sample=None, cfg=None, state=None
):
    """Отрендерить страницу модели оценки (`estimation-model.md`).

    `reference`/`stats`/`sample`/`cfg`/`state` — источники данных для секций
    эталона, статистики, спринтов, порогов и публикации. Без них страница
    рендерится (старые артефакты не ломаются), но соответствующие секции — `NA`.
    """
    template = _read_template(template_path, DEFAULT_MODEL_PAGE_TEMPLATE)
    slots = model_page_slots(
        model, reference=reference, stats=stats, sample=sample, cfg=cfg, state=state
    )
    text = _substitute(template, slots)
    return _append_model_appendix(text, template, model, slots)


def model_template(workdir):
    """Шаблон страницы модели из `templates_dir` конфига; None — встроенный."""
    return _template_for(workdir, "model-page.md")


# ---------------------------------------------------------------------------
# Запись
# ---------------------------------------------------------------------------


def write(run_dir, text, filename="report.md"):
    """Атомарно записать файл прогона: tmp в том же каталоге + `os.replace`."""
    target = Path(run_dir) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = text if text.endswith("\n") else text + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=".%s-" % filename, suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, str(target))
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return target


# ---------------------------------------------------------------------------
# delta.md
# ---------------------------------------------------------------------------


def _delta_slots(
    current_validation,
    current_estimate,
    previous_validation,
    previous_estimate,
    current_run,
    previous_run,
):
    current_roles = {item.get("role"): item for item in current_estimate.get("roles") or []}
    previous_roles = {item.get("role"): item for item in previous_estimate.get("roles") or []}
    roles = sorted(
        set(current_roles) | set(previous_roles),
        key=lambda role: (_role_key(role), role),
    )
    rows = []
    for role in roles:
        now = current_roles.get(role) or {}
        before = previous_roles.get(role) or {}
        rows.append(
            (
                role,
                before.get("expected"),
                now.get("expected"),
                before.get("range"),
                now.get("range"),
                before.get("confidence"),
                now.get("confidence"),
            )
        )

    current_total = current_estimate.get("total") or {}
    previous_total = previous_estimate.get("total") or {}
    current_gaps = {gap.get("id") for gap in current_validation.get("gaps") or []}
    previous_gaps = {gap.get("id") for gap in previous_validation.get("gaps") or []}
    closed = sorted(previous_gaps - current_gaps)
    opened = sorted(current_gaps - previous_gaps)

    return {
        "task_key": current_estimate.get("task_key"),
        "current_run": current_run,
        "previous_run": previous_run,
        "verdict_change": "%s → %s"
        % (previous_validation.get("verdict") or NA, current_validation.get("verdict") or NA),
        "roles_delta_table": _table(
            (
                "Роль",
                "Было",
                "Стало",
                "Было (диапазон)",
                "Стало (диапазон)",
                "Было (уверенность)",
                "Стало (уверенность)",
            ),
            rows,
        ),
        "total_change": "%s %s → %s %s"
        % (
            _num(previous_total.get("expected")),
            _num(previous_total.get("range")),
            _num(current_total.get("expected")),
            _num(current_total.get("range")),
        ),
        "gaps_change": _bullets(
            ["закрыт: %s" % gap_id for gap_id in closed]
            + ["открыт: %s" % gap_id for gap_id in opened]
        ),
    }


# ---------------------------------------------------------------------------
# Подкоманда `trr report`
# ---------------------------------------------------------------------------


def _emit(args, message):
    if not getattr(args, "quiet", False):
        print(message)


def _emit_json(args, payload):
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _finish(args, code, message, **payload):
    _emit(args, message)
    data = {"status": "ok" if code == EXIT_OK else "blocked", "code": code}
    data.update(payload)
    _emit_json(args, data)
    return code


def _runs_root(workdir, task_key):
    return Path(workdir) / STATE_DIR / "runs" / str(task_key)


def _select_run(runs_root, run_id=None):
    if run_id:
        candidate = Path(runs_root) / str(run_id)
        return candidate if candidate.is_dir() else None
    if not Path(runs_root).is_dir():
        return None
    candidates = sorted(path for path in Path(runs_root).iterdir() if path.is_dir())
    return candidates[-1] if candidates else None


def _previous_run(runs_root, current):
    if not Path(runs_root).is_dir():
        return None
    candidates = sorted(
        path
        for path in Path(runs_root).iterdir()
        if path.is_dir() and path.name < Path(current).name
    )
    return candidates[-1] if candidates else None


def _template_for(workdir, name):
    """Шаблон из `templates_dir` конфига; None — использовать встроенный."""
    templates_dir = "templates"
    try:
        cfg = configmod.load_config(configmod.config_path(workdir))
        templates_dir = cfg.get("templates_dir") or "templates"
    except configmod.ConfigError:
        pass
    path = Path(configmod.SKILL_ROOT) / str(templates_dir) / name
    return path if path.is_file() else None


def _template_url_for(workdir):
    """`validation.template_url` из конфига; None — встроенный дефолт.

    Пустая строка — законное значение: отчёт печатает путь к
    `templates/task-description.md` вместо ссылки.
    """
    try:
        cfg = configmod.load_config(configmod.config_path(workdir))
    except configmod.ConfigError:
        return None
    validation = cfg.get("validation")
    if not isinstance(validation, dict) or "template_url" not in validation:
        return None
    value = validation.get("template_url")
    return "" if value is None else str(value)


def _relative(workdir, path):
    try:
        return str(Path(path).resolve().relative_to(Path(workdir).resolve()))
    except (ValueError, OSError):
        return str(path)


def _render_model_artifact(workdir, args):
    """`report --model`: перерендерить `model/estimation-model.md` из JSON.

    Ничего не пересчитывает: только читает `model/estimation-model.json` и
    пишет человекочитаемое зеркало. Нет файла или он не читается — код 4
    (`MISSING_ARTIFACT`): без JSON рендерить нечего.
    """
    base = Path(workdir) / STATE_DIR
    model_path = base / "model" / "estimation-model.json"
    display = _relative(workdir, model_path)
    if not model_path.is_file():
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s — запустите /task-readiness-review train" % display,
        )
    try:
        model = _read_json(model_path, required=True)
    except (FileNotFoundError, ValueError) as exc:
        return _finish(args, EXIT_MISSING, "[MISSING] %s — %s" % (display, exc))
    if not isinstance(model, dict):
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s — должен быть JSON-объектом" % display,
        )
    try:
        cfg = configmod.load_config(configmod.config_path(workdir))
    except configmod.ConfigError:
        cfg = None
    try:
        text = render_model_page(
            model,
            model_template(workdir),
            reference=_optional_json(base / "norm" / "reference-estimates.json"),
            stats=_optional_json(base / "norm" / "sprint-stats.json"),
            sample=_optional_json(base / "norm" / "sprint-sample.json"),
            cfg=cfg,
            state=_optional_json(base / "state.json"),
        )
        target = write(base / "model", text, "estimation-model.md")
    except (OSError, ValueError) as exc:
        return _finish(
            args, EXIT_BLOCKED, "[BLOCKED] report --model: %s" % exc
        )
    return _finish(
        args,
        EXIT_OK,
        "[OK] model: %s" % _relative(workdir, target),
        path=str(target),
    )


def run(workdir, args):
    """Точка входа подкоманды `report` (cli.py вызывает `run(workdir, args)`)."""
    if getattr(args, "model", False):
        return _render_model_artifact(workdir, args)

    task_key = getattr(args, "task", None)
    if not task_key:
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] report: не указан --task — укажите ключ задачи Jira, "
            "например --task E001-1234",
        )

    runs_root = _runs_root(workdir, task_key)
    run_dir = _select_run(runs_root, getattr(args, "run", None))
    if run_dir is None:
        requested = getattr(args, "run", None)
        if requested:
            return _finish(
                args,
                EXIT_MISSING,
                "[MISSING] report: нет прогона %s у задачи %s — проверьте --run "
                "или запустите /task-readiness-review check" % (requested, task_key),
            )
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] report: нет ни одного прогона задачи %s — сначала "
            "/task-readiness-review check" % task_key,
        )

    if not (run_dir / "validation.json").is_file():
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s — сначала /task-readiness-review check"
            % _relative(workdir, run_dir / "validation.json"),
        )
    if not (run_dir / "estimate.json").is_file():
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s — сначала /task-readiness-review estimate"
            % _relative(workdir, run_dir / "estimate.json"),
        )

    if getattr(args, "delta", False):
        previous = _previous_run(runs_root, run_dir)
        if previous is None:
            return _finish(
                args,
                EXIT_BLOCKED,
                "[BLOCKED] delta: у задачи %s нет предыдущего прогона — сначала "
                "/task-readiness-review refresh" % task_key,
            )
        if not (previous / "estimate.json").is_file() or not (
            previous / "validation.json"
        ).is_file():
            return _finish(
                args,
                EXIT_MISSING,
                "[MISSING] delta: в предыдущем прогоне %s нет validation.json "
                "или estimate.json — запустите /task-readiness-review check и "
                "/task-readiness-review estimate" % _relative(workdir, previous),
            )
        text = _substitute(
            _read_template(_template_for(workdir, "delta.md"), DEFAULT_DELTA_TEMPLATE),
            _delta_slots(
                _read_json(run_dir / "validation.json", required=True),
                _read_json(run_dir / "estimate.json", required=True),
                _read_json(previous / "validation.json", required=True),
                _read_json(previous / "estimate.json", required=True),
                run_dir.name,
                previous.name,
            ),
        )
        target = write(run_dir, text, "delta.md")
        return _finish(
            args,
            EXIT_OK,
            "[OK] delta: %s" % _relative(workdir, target),
            path=str(target),
        )

    try:
        text = render(
            run_dir,
            _template_for(workdir, "report.md"),
            _template_url_for(workdir),
        )
    except (FileNotFoundError, ValueError) as exc:
        return _finish(args, EXIT_BLOCKED, "[BLOCKED] report: %s" % exc)
    target = write(run_dir, text)
    return _finish(
        args,
        EXIT_OK,
        "[OK] report: %s" % _relative(workdir, target),
        path=str(target),
    )

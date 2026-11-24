#!/usr/bin/env python3
"""Детерминированный движок проверки полноты задачи.

Вход — снимок задачи (`context.json`, его собирает агент через MCP), каталог
правил (`CHECKS`) и флаг `with_dependencies`. Выход — `validation.json` по
`schemas/validation.schema.json`; из него же строятся `questions.json` и
черновик комментария для Jira.

Правила — **данные**, а не код: `CHECKS` — модульная таблица, человекочитаемое
зеркало лежит в `references/validation-rules.md`. Изменение каталога требует
бампа версии правил и golden-теста.

Что нормативно (перенесено в скилл из Confluence, работает офлайн):

    templates/task-description.md        — 11 полей описания задачи
    templates/sa-handoff-checklist.md    — блоки SA-шаблона + DoD
    templates/ba-review-checklist.md     — ревью задач BA
    templates/feature-toggle-criteria.md — скоринг фича-тогла

Происхождение шаблонов (page_id и названия страниц-источников) — в
`references/validation-rules.md` §1: сам движок на Confluence не ссылается.

`run()` — диспетчер: с `str`/`Path` первым аргументом работает как CLI-команда
(её вызывает `cli.py`), со словарём — как чистый движок. Чистая точка входа
движка — `run_checks(context, rules, with_dependencies, qa_required_issue_types)`.
"""

import hashlib
import json
import os
import re
from pathlib import Path

from trr_impl import analysis as analysismod
from trr_impl import config as configmod
from trr_impl import limits
from trr_impl import publish as publishmod
from trr_impl import report as reportmod
from trr_impl import schema_lite
from trr_impl import state as statemod
from trr_impl import store as storemod

__all__ = [
    "CHECKS",
    "CONTEXT_KEYS",
    "DEFAULT_SECTIONS",
    "INTEGRATION_LABELS",
    "QA_REQUIRED_ISSUE_TYPES",
    "RULES_VERSION",
    "build_questions",
    "default_rules",
    "detect_has_testing",
    "qa_estimation_value",
    "qa_required_types",
    "render_comment_draft",
    "rules_from_template",
    "run",
    "run_checks",
]

# Обязательные ключи снимка задачи (`context.json`, CONTRACT.md §5.4).
# Значение может быть `null` — важен сам ключ: он показывает, что агент
# посмотрел поле в Jira и не нашёл данных, а не забыл его вовсе.
CONTEXT_KEYS = (
    "task_key",
    "issue_type",
    "role",
    "work_kind",
    "sp",
    "qa_estimation",
    "labels",
    "fields",
    "sections",
    "sources",
)

# Версия каталога правил. Меняется вместе с CHECKS; попадает в справочник и
# в сообщения диагностики, чтобы прогоны разных версий нельзя было спутать.
# 4: SA-08 принимает «объём работ» (раздел «Решение»/«Задача»/«Необходимо» или
#    строка «маркер долженствования + глагол») как достаточное основание;
#    поля, отсутствующие в проекте (`fields.absent_in_project`), дают NA;
#    добавлена ось `work_intent` (на вердикт и числа не влияет).
# 3: SA-08 принимает критерии-«результат работ» и источники «Цель»/заголовок.
RULES_VERSION = "4"

# Порог «основное описание заполнено» (TPL-09).
MIN_DESCRIPTION_CHARS = 200

# Значения, которые считаются «поле не заполнено».
EMPTY_VALUES = frozenset(
    {"n/a", "na", "n/d", "нд", "н/д", "none", "null", "нет", "-", "—", "–", "?"}
)

# Ядро алиасов раздела «Критерии приёмки» — отделено от алиасов «Ожидаемого
# результата», чтобы SA-08 мог сказать, какой из двух разделов использован.
ACCEPTANCE_CORE_ALIASES = ("критерии приемки", "критерии приёмки", "ac")

# «Ожидаемый результат» — эквивалент критериев приёмки: терминология команд
# разная, а требование одно — по заполнению задачи должно быть понятно, как
# система работает в нормальном состоянии.
EXPECTED_RESULT_ALIASES = (
    "ожидаемый результат",
    "ожидаемый результат (expected result)",
    "expected result",
    "ожидаемое поведение",
    "как должно работать",
    "как должно работать в нормальном состоянии",
)

# «Цель» — третий источник содержания для SA-08. Критерии приёмки в части
# задач фиксируются как результат работ («подготовлены тест-кейсы»,
# «проведено ревью»), и тогда цель задачи вместе с заголовком описывает
# готовность полнее, чем отсутствующий раздел критериев.
GOAL_ALIASES = ("цель", "цель задачи", "goal")

# Подпись источника SA-08, когда критерием стал сам заголовок задачи. Отдельная
# строка нужна сообщению: «критериев: 1» здесь означало бы «в разделе критериев
# один пункт», хотя раздела нет вовсе.
SUMMARY_CRITERIA_SOURCE = "заголовок задачи"

# «Объём работ» — раздел, где зафиксировано, что надо сделать. Если известно,
# что надо сделать, — понятно, что меняется и как это проверять, поэтому такой
# раздел (или строка «необходимо + глагол действия») — достаточное основание для
# SA-08. Формулировки взяты из корпуса 223 задач
# (`.task-readiness/analysis/corpus-patterns.md` §5.1): «Задача» 27, «Решение» 7,
# «Необходимо» 5, «Тех.решение» 5, «Техническое решение» 2.
#
# Список синхронен с `analysis.WORK_SCOPE_ALIASES` (там же — почему копия, а не
# импорт). Английские синонимы — канонические имена ключей `sections{}`.
WORK_SCOPE_ALIASES = (
    "задача",
    "решение",
    "техническое решение",
    "тех.решение",
    "тех решение",
    "что нужно сделать",
    "что надо сделать",
    "необходимо",
    "изменения",
    "изменения проекта",
    "описание решения",
    "перечень работ",
    "ход работ",
    "план работ",
    "механика выгрузки",
    "описание изменений",
    "как сделать",
    "предлагаемое решение",
    "task",
    "solution",
    "work scope",
    "scope of work",
    "what to do",
)

# Канонические имена полей, которых может не быть в проекте задачи
# (`context.fields.absent_in_project`). Правило по такому полю — `NA`, а не
# `FAIL`: «поля нет в проекте» и «поле не заполнено» — разные факты, и требовать
# заполнить несуществующее поле нельзя.
ABSENT_FIELD_NAMES = {
    "team": "Команда",
    "sprint": "Sprint",
    "role": "Роль",
    "story_points": "Story Points",
    "epic": "Эпик",
    "links": "Связи",
}

# Разделы шаблона передачи SA → разработка (templates/sa-handoff-checklist.md).
DEFAULT_SECTIONS = {
    "goal": ["цель", "цель задачи"],
    "ba_requirements": ["требования ба", "бизнес-требования", "требования"],
    "mockup": ["макет", "ссылка на макет", "дизайн"],
    "contract": ["контракт", "контракты api", "контракт api"],
    "description": ["описание", "описание решения"],
    "task": ["задача", "что делать"],
    "work_scope": list(WORK_SCOPE_ALIASES),
    "scenarios": ["сценарии", "сценарии / альтернативные сценарии"],
    "acceptance_criteria": list(ACCEPTANCE_CORE_ALIASES)
    + list(EXPECTED_RESULT_ALIASES),
    "adjustments": ["корректировки", "изменения", "внесение корректировок", "версии", "версия"],
    "testing": ["тестирование", "план тестирования", "как тестировать"],
    "toggle": ["feature-toggle", "фича-тоггл", "фича тоггл", "скоринг тоггла"],
}

# Заголовки, которые считаются «мягкими» (строка `Заголовок: значение`), даже
# если они не относятся ни к одной проверяемой секции: формат бага и служебные
# блоки описания. Нужны, чтобы такой заголовок закрывал предыдущий блок.
_KNOWN_EXTRA = (
    "проблем",
    "окружен",
    "шаг",
    "фактическ",
    "ожидаем",
    "контекст",
    "риск",
    "неопределен",
    "вычислен",
    "проверк",
    "тестирован",
    "ограничен",
    "макет",
)

_KNOWN_TITLES = frozenset(
    alias for aliases in DEFAULT_SECTIONS.values() for alias in aliases
)

# Ключевые слова для разбора собственного шаблона (`override_template`).
# Порядок важен: заголовок относится к первой подошедшей группе.
_SECTION_KEYWORDS = (
    ("goal", ("цель", "назначен")),
    ("ba_requirements", ("требован", "функциональные требован")),
    ("mockup", ("макет", "дизайн")),
    ("contract", ("контракт", "спецификац", "api")),
    ("scenarios", ("сценар",)),
    # «Ожидаемый результат» — эквивалент критериев приёмки, поэтому проверяется
    # раньше остальных групп: иначе мягкий заголовок «Ожидаемый результат: …»
    # не распознаётся как известный и рвёт блок описания.
    ("acceptance_criteria", ("критери", "приемк", "ожидаем", "expected", "как должно")),
    ("description", ("описан", "решение", "реализац")),
    ("task", ("задач", "что делать", "объем работ")),
    ("adjustments", ("корректировк", "изменени", "верси")),
    ("testing", ("тестирован", "проверк")),
    ("toggle", ("toggle", "тоггл", "скоринг")),
)

# Пункты чек-листа SA (templates/sa-handoff-checklist.md), SA-09.
SA_CHECKLIST_ITEMS = (
    ("маппинг контрактов", ("маппинг контракт",)),
    ("ошибки методов API", ("ошибк",)),
    ("доступы", ("доступ",)),
    ("атрибуты", ("атрибут",)),
    ("фильтры", ("фильтр",)),
    ("маппинг для FE", ("маппинг для fe", "маппинг fe", "маппинг для фронт")),
)

# Разделы документации затронутых контрактов, DEP-01..DEP-03.
DOC_REQUIREMENTS = {
    "DEP-01": {
        "label": "service-overview",
        "aliases": ("service-overview", "service overview", "обзор сервиса"),
    },
    "DEP-02": {
        "label": "logic-api / logic-event / logic-cron",
        "aliases": ("logic-api", "logic-event", "logic-cron", "logic api", "логика"),
    },
    "DEP-03": {
        "label": "testing-overview",
        "aliases": ("testing-overview", "testing overview", "как тестировать"),
    },
}

_TPL_WHERE = (
    "Confluence: страница-эталон описания задачи (нормативный шаблон — "
    "templates/task-description.md); поля задачи в Jira"
)
_SA_WHERE = (
    "Confluence: страница-эталон передачи в разработку (нормативный шаблон — "
    "templates/sa-handoff-checklist.md); описание задачи"
)

# Каталог проверок. Ключи: id, section, severity, kind, target_role, question,
# where_to_find, why + параметры конкретного вида проверки.
CHECKS = (
    # --- содержание задачи (content-based, не шаблон) --------------------
    # Блокируют только два правила: понятность сути (CL-01) и измеримость
    # критерия приёмки (SA-08). Остальные содержательные правила дают WARN:
    # они влияют на точность оценки, но не на право задачи быть оценённой.
    {
        "id": "CL-01",
        "section": "Понятность задачи",
        "severity": "REQUIRED",
        "kind": "clarity",
        "metric": "clarity.score",
        "min": 0.35,
        "target_role": "BA",
        "question": "Что именно нужно сделать и зачем: понятна ли суть задачи из описания?",
        "where_to_find": "поле «Описание» в задаче Jira; комментарии BA",
        "why": "непонятная задача не декомпозируется и оценивается наугад",
        "pass_message": "суть задачи понятна",
        "fail_message": "суть задачи непонятна",
    },
    {
        "id": "CL-02",
        "section": "Сценарии",
        "severity": "RECOMMENDED",
        "kind": "scenarios",
        "min_scenarios": 1,
        "min_steps": 2,
        "target_role": "BA",
        "question": "Какие сценарии покрывает задача: основной, альтернативные, ошибочные?",
        "where_to_find": "раздел «Сценарии» или шаги воспроизведения в описании задачи",
        "why": "неописанные сценарии — типичный источник недооценки",
    },
    {
        "id": "CL-03",
        "section": "Границы объёма",
        "severity": "RECOMMENDED",
        "kind": "scope",
        "metric": "scope.score",
        "min": 0.4,
        "target_role": "BA",
        "question": "Где границы работ: что входит в задачу, а что нет?",
        "where_to_find": "раздел «Цель»/«Задача» и обороты «не входит», «в рамках», «только для»",
        "why": "без границ объём работ растёт по ходу разработки",
        "pass_message": "границы объёма понятны",
        "fail_message": "границы объёма не описаны",
    },
    {
        "id": "CL-04",
        "section": "Связи и интеграции",
        "severity": "RECOMMENDED",
        "kind": "dependencies",
        "metric": "dependencies.score",
        "min": 0.4,
        "target_role": "SA",
        "question": "Какие связи и интеграции затрагивает задача: блокеры, зависимости, внешние системы?",
        "where_to_find": "блок «Связи» в задаче Jira; упоминания сервисов и интеграций в описании",
        "why": "неописанные связи и интеграции меняют объём и порядок работ",
        "pass_message": "связи и интеграции описаны",
        "fail_message": "связи и интеграции не описаны",
    },
    {
        "id": "CL-05",
        "section": "Неопределённость",
        "severity": "RECOMMENDED",
        "kind": "ambiguity",
        "metric": "ambiguity.ratio",
        "max": 0.15,
        "target_role": "BA",
        "question": "Какие места задачи ещё не решены и кто должен их уточнить?",
        "where_to_find": "описание задачи: «уточнить», «неизвестно», «TBD», открытые вопросы",
        "why": "высокая неопределённость = скрытая работа на проработку",
        "pass_message": "неопределённости в тексте мало",
        "fail_message": "много маркеров неопределённости",
    },
    {
        "id": "CL-06",
        "section": "Область задачи",
        "severity": "OPTIONAL",
        "kind": "area",
        "metric": "area.confidence",
        "min": 0.3,
        "target_role": "BA",
        "question": "К какой подсистеме относится задача: API, UI, ETL, платежи, инфраструктура?",
        "where_to_find": "компоненты, метки, эпик и текст задачи",
        "why": "область определяет, чей опыт нужен для оценки",
        "pass_message": "область определима",
        "fail_message": "область не определима",
    },
    {
        "id": "CL-07",
        "section": "Качество описания",
        "severity": "OPTIONAL",
        "kind": "clarity",
        "metric": "clarity.score",
        "min": 0.7,
        "target_role": "BA",
        "question": "Достаточно ли описания, чтобы разработка начала работу без уточнений?",
        "where_to_find": "поле «Описание» в задаче Jira",
        "why": "хорошо описанная задача оценивается точнее",
        "pass_message": "задача описана хорошо",
        "fail_message": "описание можно усилить",
    },
    # --- 11 полей шаблона описания задачи (гигиена, не блокирует) ---------
    {
        "id": "TPL-01",
        "section": "Проект",
        "severity": "OPTIONAL",
        "kind": "field",
        "field": "project",
        "target_role": "BA",
        "question": "К какому проекту относится задача?",
        "where_to_find": _TPL_WHERE,
        "why": "без проекта задача не попадает в план и статистику",
    },
    {
        "id": "TPL-02",
        "section": "Команда",
        "severity": "OPTIONAL",
        "kind": "field",
        "field": "team",
        "target_role": "BA",
        "question": "Какая команда владелец задачи?",
        "where_to_find": _TPL_WHERE,
        "why": "команда определяет, чья оценка и чей спринт",
    },
    {
        "id": "TPL-03",
        "section": "Тип задачи",
        "severity": "RECOMMENDED",
        "kind": "field",
        "field": "issue_type",
        "target_role": "BA",
        "question": "Какой тип задачи в Jira: Feature, Задача, Ошибка, Tech Debt?",
        "where_to_find": _TPL_WHERE,
        "why": "тип задачи задаёт базу оценки и формат описания",
    },
    {
        "id": "TPL-04",
        "section": "Заголовок",
        "severity": "OPTIONAL",
        "kind": "field",
        "field": "summary",
        "target_role": "BA",
        "question": "Как звучит заголовок задачи в формате «метка — действие — объект»?",
        "where_to_find": _TPL_WHERE,
        "why": "по заголовку задачу находят и относят к сервису",
    },
    {
        "id": "TPL-05",
        "section": "Эпик",
        "severity": "OPTIONAL",
        "kind": "field",
        "field": "epic",
        "target_role": "BA",
        "question": "В какой эпик входит задача?",
        "where_to_find": _TPL_WHERE,
        "why": "вне эпика задачу нельзя спланировать и оценить",
    },
    {
        "id": "TPL-06",
        "section": "Приоритет",
        "severity": "OPTIONAL",
        "kind": "field",
        "field": "priority",
        "target_role": "BA",
        "question": "Какой приоритет у задачи?",
        "where_to_find": _TPL_WHERE,
        "why": "приоритет задаёт SLA и порядок разбора",
    },
    {
        "id": "TPL-07",
        "section": "Роль",
        "severity": "RECOMMENDED",
        "kind": "field",
        "field": "role",
        "target_role": "BA",
        "question": "Какая роль исполнителя: BA, SA, BE, FE или QA?",
        "where_to_find": "поле «Роль» в задаче Jira; " + _TPL_WHERE,
        "why": "роль выбирает бакет эталонной оценки",
    },
    {
        "id": "TPL-08",
        "section": "Связь с другими задачами",
        "severity": "RECOMMENDED",
        "kind": "links",
        "field": "links",
        "target_role": "SA",
        "question": "С какими задачами связана эта задача (блокеры, зависимости)?",
        "where_to_find": "блок «Связи» в задаче Jira; " + _TPL_WHERE,
        "why": "связанные блокеры меняют объём и порядок работ",
    },
    {
        "id": "TPL-09",
        "section": "Основное описание",
        "severity": "RECOMMENDED",
        "kind": "description_length",
        "min_chars": MIN_DESCRIPTION_CHARS,
        "target_role": "BA",
        "question": "Где основное описание задачи: контекст, цель, требования, критерии?",
        "where_to_find": "поле «Описание» в задаче Jira; " + _TPL_WHERE,
        "why": "по пустому описанию объём работ не определить",
    },
    {
        "id": "TPL-09a",
        "section": "Внесение корректировок (9.1)",
        "severity": "RECOMMENDED",
        "kind": "section",
        "aliases_key": "adjustments",
        "target_role": "BA",
        "question": "Какие корректировки вносились в задачу после первой версии описания?",
        "where_to_find": "раздел «9.1. Внесение корректировок» в описании задачи",
        "why": "без истории правок непонятно, какая версия требований актуальна",
    },
    {
        "id": "TPL-10",
        "section": "Sprint",
        "severity": "OPTIONAL",
        "kind": "field",
        "field": "sprint",
        "target_role": "BA",
        "question": "В какой спринт взята задача (или в спринт Estimation, если готова к оценке)?",
        "where_to_find": "поле Sprint в задаче Jira",
        "why": "без спринта задачу не видно в планировании",
    },
    {
        "id": "TPL-11",
        "section": "Story Points",
        "severity": "RECOMMENDED",
        "kind": "field",
        "field": "story_points",
        "target_role": "SA",
        "question": "Проставлена ли оценка Story Points по итогам Planning Poker?",
        "where_to_find": "поле Story Points в задаче Jira",
        "why": "до оценки отсутствие нормально, после оценки — расхождение с планом",
    },
    # --- блоки шаблона SA ------------------------------------------------
    {
        "id": "SA-01",
        "section": "Цель",
        "severity": "RECOMMENDED",
        "kind": "section",
        "aliases_key": "goal",
        "target_role": "BA",
        "question": "Какая цель у задачи: что должно измениться в итоге?",
        "where_to_find": "раздел «Цель» в описании задачи; " + _SA_WHERE,
        "why": "без цели нельзя понять, что именно оценивать",
    },
    {
        "id": "SA-02",
        "section": "Требования БА",
        "severity": "RECOMMENDED",
        "kind": "section",
        "aliases_key": "ba_requirements",
        "target_role": "BA",
        "question": "Какие требования БА реализует задача?",
        "where_to_find": "раздел «Требования БА» в описании задачи; страница функции в Confluence",
        "why": "требования задают объём функциональности",
    },
    {
        "id": "SA-04",
        "section": "Контракт",
        # Блокируют ровно два правила — CL-01 и SA-08. Контракт остаётся
        # RECOMMENDED даже при изменении интеграций: его отсутствие искажает
        # точность оценки, но не делает задачу непонятной.
        "severity": "RECOMMENDED",
        "kind": "section",
        "aliases_key": "contract",
        "target_role": "SA",
        "question": "Есть ли контракт (API/схема данных) и где он описан?",
        "where_to_find": "раздел «Контракт» в описании задачи; спецификация API в Confluence",
        "why": "без контракта разработка угадывает форму данных",
        "fail_note": "влияет на точность оценки (не блокирует)",
        "fail_note_integration": (
            "задача затрагивает интеграции — контракт критичен для точности"
        ),
    },
    {
        "id": "SA-05",
        "section": "Описание решения",
        "severity": "RECOMMENDED",
        "kind": "section",
        "aliases_key": "description",
        "target_role": "SA",
        "question": "Как предлагается реализовать задачу технически?",
        "where_to_find": "раздел «Описание» в описании задачи; " + _SA_WHERE,
        "why": "без описания решения оценка превращается в догадку",
    },
    {
        "id": "SA-06",
        "section": "Задача",
        "severity": "RECOMMENDED",
        "kind": "section",
        "aliases_key": "task",
        "target_role": "SA",
        "question": "Что именно нужно сделать: перечень работ по задаче?",
        "where_to_find": "раздел «Задача» в описании задачи",
        "why": "перечень работ — основа декомпозиции и оценки",
    },
    {
        "id": "SA-07",
        "section": "Сценарии",
        "severity": "RECOMMENDED",
        "kind": "section",
        "aliases_key": "scenarios",
        "target_role": "BA",
        "question": "Какие сценарии и альтернативные сценарии нужно поддержать?",
        "where_to_find": "раздел «Сценарии / Альтернативные сценарии» в описании задачи",
        "why": "альтернативные сценарии — типичный источник недооценки",
    },
    {
        "id": "SA-08",
        "section": "Критерии приёмки",
        "severity": "REQUIRED",
        "kind": "acceptance_criteria",
        "aliases_key": "acceptance_criteria",
        "target_role": "BA",
        "question": "Какие измеримые критерии приёмки у задачи или какой результат работ должен быть получен?",
        "where_to_find": "раздел «Критерии приёмки» → «Ожидаемый результат» → "
        "«Объём работ» («Решение»/«Задача»/«Необходимо») → «Цель» + "
        "заголовок задачи; комментарии BA",
        "why": "без критериев, зафиксированного результата работ или описанного "
        "объёма работ объём и готовность не проверяемы",
    },
    {
        "id": "SA-09",
        "section": "Чек-лист SA",
        "severity": "RECOMMENDED",
        "kind": "sa_checklist",
        "target_role": "SA",
        "question": "Пройден ли чек-лист SA: маппинг контрактов, ошибки методов API, доступы, атрибуты, фильтры, маппинг для FE?",
        "where_to_find": _SA_WHERE,
        "why": "непройденный чек-лист SA = скрытые вопросы у разработки",
    },
    # --- QA / feature-toggle ----------------------------------------------
    {
        "id": "QA-01",
        "section": "QA Estimation",
        "severity": "RECOMMENDED",
        "kind": "qa_estimation",
        "field": "qa_estimation",
        "target_role": "QA",
        "question": "Какая оценка тестирования (QA Estimation) у задачи? Нужна "
        "только для типов задач, где требуется отдельная проверка QA "
        "(`validation.qa_required_issue_types`) — у остальных проверку "
        "выполняет исполнитель",
        "where_to_find": "поле QA Estimation в задаче Jira; контакт QA команды",
        "why": "QA требуется только для типов из `validation.qa_required_issue_types`; "
        "для остальных типов проверку результата выполняет исполнитель, "
        "поэтому поле не обязательно",
    },
    {
        "id": "FT-01",
        "section": "Feature-toggle",
        "severity": "RECOMMENDED",
        "kind": "feature_toggle",
        "target_role": "SA",
        "question": "Посчитан ли скоринг фича-тогла по таблицам риска, неопределённости и оценки?",
        "where_to_find": "Confluence: критерии feature-toggle (нормативный шаблон — "
        "templates/feature-toggle-criteria.md); раздел «Feature-toggle» в описании задачи",
        "why": "без скоринга решение о тоггле принимается на глаз",
    },
    # --- документация зависимостей ----------------------------------------
    {
        "id": "DEP-01",
        "section": "Документация зависимостей",
        "severity": "OPTIONAL",
        "condition": "with_dependencies",
        "kind": "dependency_doc",
        "target_role": "SA",
        "question": "Где раздел service-overview для затронутого сервиса?",
        "where_to_find": "документация сервиса: раздел service-overview",
        "why": "без обзора сервиса неизвестны границы изменений",
    },
    {
        "id": "DEP-02",
        "section": "Документация зависимостей",
        "severity": "OPTIONAL",
        "condition": "with_dependencies",
        "kind": "dependency_doc",
        "target_role": "SA",
        "question": "Где описание логики: logic-api, logic-event или logic-cron?",
        "where_to_find": "документация сервиса: раздел logic-api / logic-event / logic-cron",
        "why": "логика вызова определяет точки правок",
    },
    {
        "id": "DEP-03",
        "section": "Документация зависимостей",
        "severity": "OPTIONAL",
        "condition": "with_dependencies",
        "kind": "dependency_doc",
        "target_role": "SA",
        "question": "Где раздел testing-overview для затронутого контракта?",
        "where_to_find": "документация сервиса: раздел testing-overview",
        "why": "без плана тестирования QA оценивает вслепую",
    },
)

_CHECKS_BY_ID = {entry["id"]: entry for entry in CHECKS}


class CheckError(Exception):
    """Вход движка непригоден (нет обязательных ключей контекста)."""


# ---------------------------------------------------------------------------
# Нормализация текста и разбор секций
# ---------------------------------------------------------------------------


def _normalize(text):
    """Привести заголовок/алиас к сравнимому виду."""
    value = str(text).strip().strip("*_").strip()
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()
    value = value.strip(":：.").strip()
    value = value.replace("ё", "е").replace("Ё", "Е")
    value = re.sub(r"\s+", " ", value)
    return value.casefold()


def _heading_of(line, soft_known_only=True):
    """Вернуть (заголовок, текст-на-той-же-строке) или None.

    Понимает всю разметку, которая реально встречается в описаниях задач:

    - жёсткие Markdown-заголовки `# Заголовок` и `**Заголовок**` — всегда;
    - Jira `h3. Заголовок` (h1…h6);
    - Jira-курсив `*Заголовок:*` / `*Заголовок*: значение` — доминирующая
      разметка корпуса (113 задач из 223);
    - Jira жирный курсив `{*}Заголовок{*}` / `{*}Заголовок:{*}`;
    - «мягкий» заголовок `Заголовок: значение` — только если начало строки
      похоже на название раздела шаблона. Иначе любая фраза с двоеточием
      («Сократить время: оператор получает…») рвала бы блок на части.

    Курсив принимается заголовком, только если строка — заголовок и есть:
    `*Заголовок:*` (двоеточие внутри), `*Заголовок*: значение`, либо название
    известно шаблону. Иначе `*важно*` посреди текста резало бы блок.
    """
    raw = line.strip()
    if not raw:
        return None
    if raw.startswith("#"):
        body = raw.lstrip("#").strip()
        return (_normalize(body), "") if body else None
    match = re.match(r"^\*\*(.+?)\*\*\s*:?\s*(.*)$", raw)
    if match:
        return _normalize(match.group(1)), match.group(2).strip()
    match = re.match(r"^h[1-6]\.\s*(.+)$", raw, re.IGNORECASE)
    if match:
        return _normalize(match.group(1)), ""
    match = re.match(r"^\{\*\}(.{2,80}?)\{\*\}(.*)$", raw)
    if match:
        return _normalize(match.group(1)), match.group(2).lstrip(":").strip()
    match = re.match(r"^\*([^*]{2,60})\*\s*(.*)$", raw)
    if match:
        title = _normalize(match.group(1))
        rest = match.group(2).strip()
        if rest.startswith(":"):
            return title, rest.lstrip(":").strip()
        if not rest or _is_known_title(title):
            return title, rest
        return None
    if raw[0] in "*-|>`":
        return None
    match = re.match(r"^([^:]{1,80}):\s*(.*)$", raw)
    if match:
        title = _normalize(match.group(1))
        if soft_known_only and not _is_known_title(title):
            return None
        return title, match.group(2).strip()
    return None


def _is_known_title(title):
    """Похоже ли начало строки на название раздела шаблона."""
    if len(title) > 60 or len(title.split()) > 6:
        return False
    if _classify_heading(title) is not None:
        return True
    if title in _KNOWN_TITLES:
        return True
    if any(title.startswith(word) for word in _KNOWN_EXTRA):
        return True
    return any(_matches(title, alias) for alias in _KNOWN_TITLES)


def _blocks(text):
    """Разбить текст на блоки (заголовок, содержимое) в порядке появления."""
    result = []
    title = None
    buffer = []
    for line in (text or "").splitlines():
        heading = _heading_of(line)
        if heading is not None:
            if title is not None:
                result.append((title, "\n".join(buffer).strip()))
            title, inline = heading
            buffer = [inline] if inline else []
        elif title is not None:
            buffer.append(line)
    if title is not None:
        result.append((title, "\n".join(buffer).strip()))
    return result


def _matches(title, alias):
    if title == alias:
        return True
    return len(alias) >= 4 and title.startswith(alias)


def _find_section(text, aliases):
    """Найти содержимое секции по любому из алиасов; None, если пусто."""
    for title, content in _blocks(text):
        if any(_matches(title, alias) for alias in aliases):
            if content.strip():
                return content.strip()
    return None


def _classify_heading(title):
    for key, keywords in _SECTION_KEYWORDS:
        if any(title.startswith(word) for word in keywords):
            return key
    return None


# ---------------------------------------------------------------------------
# Правила (rules)
# ---------------------------------------------------------------------------


def _template_info(path):
    """{name, version, sha256} для файла шаблона."""
    target = Path(path)
    if not target.is_file():
        return {
            "name": target.name or "task-description.md",
            "version": "1",
            "sha256": hashlib.sha256(b"").hexdigest(),
        }
    raw = target.read_bytes()
    version = "1"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    match = re.search(r"(?m)^version:\s*(\S+)\s*$", text)
    if match:
        version = match.group(1).strip("'\"")
    return {
        "name": target.name,
        "version": version,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def default_rules():
    """Правила по умолчанию: штатный шаблон описания задачи."""
    path = Path(configmod.SKILL_ROOT) / "templates" / "task-description.md"
    return {"template": _template_info(path), "sections": dict(DEFAULT_SECTIONS)}


def rules_from_template(path):
    """Правила из собственного шаблона (`sources.override_template`).

    Заголовки шаблона классифицируются по ключевым словам; секции, которых в
    шаблоне нет, остаются с алиасами по умолчанию. Нечитаемый шаблон —
    `CheckError`: тихо проверять по чужому шаблону нельзя.
    """
    target = Path(path)
    if not target.is_file():
        raise CheckError("шаблон не найден: %s" % target)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise CheckError("шаблон не читается: %s: %s" % (target, exc))

    sections = {key: list(value) for key, value in DEFAULT_SECTIONS.items()}
    for title, _content in _blocks(text):
        key = _classify_heading(title)
        if key is None:
            continue
        if title not in sections[key]:
            sections[key] = sections[key] + [title]
    return {"template": _template_info(target), "sections": sections}


def _aliases(rules, key):
    sections = (rules or {}).get("sections") or {}
    aliases = sections.get(key)
    if not aliases:
        aliases = DEFAULT_SECTIONS.get(key) or []
    if isinstance(aliases, str):
        aliases = [aliases]
    return [_normalize(alias) for alias in aliases if str(alias).strip()]


def _template_block(rules):
    template = (rules or {}).get("template")
    if isinstance(template, dict):
        name = str(template.get("name") or "").strip()
        version = str(template.get("version") or "").strip()
        checksum = str(template.get("sha256") or "").strip()
        if name and version and checksum:
            return {"name": name, "version": version, "sha256": checksum}
    return default_rules()["template"]


# ---------------------------------------------------------------------------
# Значения полей
# ---------------------------------------------------------------------------


def _is_filled(value):
    """«Поле заполнено»: не пусто, не null, не N/A/н/д/-, не пустой список."""
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        return text.casefold().rstrip(".") not in EMPTY_VALUES
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    return True


def qa_estimation_value(context):
    """Заполненное значение `qa_estimation` из снимка задачи, иначе None.

    Публичная обёртка над `_context_value` + `_is_filled`: `0`, пустая строка,
    `N/A` и `н/д` — это «поле не заполнено», а не оценка. Нужна и проверке
    (`QA-01`), и оценке (`estimate._qa_entry`): обе обязаны понимать «пусто»
    одинаково.

    `context` может быть `None` (оценка без снимка задачи): тогда поля нет,
    и функция возвращает `None`, а не падает на `None.get`.
    """
    if not isinstance(context, dict):
        return None
    value = _context_value(context, "qa_estimation")
    return value if _is_filled(value) else None


def _context_value(context, field):
    if not isinstance(context, dict):
        # Снимка задачи нет (`estimate(..., context=None)`, `detect_has_testing(None)`):
        # любое поле отсутствует. Раньше здесь был `None.get` → AttributeError.
        return None
    if field in ("task_key", "summary", "description", "issue_type", "labels"):
        value = context.get(field)
        if value is not None:
            return value
    fields = context.get("fields") or {}
    if isinstance(fields, dict) and field in fields:
        return fields[field]
    return context.get(field)


def _description(context):
    if not isinstance(context, dict):
        return ""
    return str(context.get("description") or "")


def _summary_text(context):
    """Заголовок задачи: верхний уровень снимка, иначе `fields.summary`."""
    return str(_context_value(context, "summary") or "")


def _section_content(context, key, rules):
    sections = context.get("sections") or {}
    if isinstance(sections, dict) and key in sections:
        value = sections[key]
        if _is_filled(value):
            return str(value).strip()
    return _find_section(_description(context), _aliases(rules, key))


def _section_any(context, key, aliases):
    """Содержимое секции по ключу `sections{}` или по любому из алиасов.

    Кроме точного ключа просматриваются остальные ключи `sections{}` (агент
    разбирает описание в произвольные имена вида `expected_result`) и заголовки
    описания. `_` в имени ключа считается пробелом: `expected_result` и
    «expected result» — один и тот же раздел.
    """
    sections = context.get("sections") or {}
    if isinstance(sections, dict):
        value = sections.get(key)
        if _is_filled(value):
            return str(value).strip()
        for name, value in sections.items():
            if not _is_filled(value):
                continue
            title = _normalize(name).replace("_", " ")
            if any(_matches(title, alias) for alias in aliases):
                return str(value).strip()
    return _find_section(_description(context), aliases)


def _criteria_content(context, rules):
    """(content, source_label) разделов критериев: приёмка → ожидаемый результат.

    Терминология команд разная, требование одно: по заполнению задачи должно
    быть понятно, что должно получиться. Это два первых (сильных) источника
    SA-08; «объём работ», «цель» и заголовок проверяются отдельно.
    """
    aliases = _aliases(rules, "acceptance_criteria")
    expected = {_normalize(alias) for alias in EXPECTED_RESULT_ALIASES}
    core = [alias for alias in aliases if alias not in expected] or aliases
    content = _section_any(context, "acceptance_criteria", core)
    if content:
        return content, "раздел «Критерии приёмки»"
    content = _section_any(
        context,
        "expected_result",
        [alias for alias in aliases if alias in expected] or aliases,
    )
    if content:
        return content, "раздел «Ожидаемый результат»"
    return None, None


def _goal_criteria(context):
    """(content, source_label) — цель задачи + заголовок, последний фолбэк SA-08.

    Заголовок **не подменяет** критерии: он добавляется контекстом к цели, а
    когда цели нет — остаётся единственным источником, и подпись говорит это
    прямо (`SUMMARY_CRITERIA_SOURCE`).
    """
    goal = _section_any(context, "goal", list(GOAL_ALIASES))
    summary = _summary_text(context).strip()
    if goal:
        content = "%s\n%s" % (goal, summary) if summary else goal
        return content, "цель задачи + заголовок"
    if summary:
        return summary, SUMMARY_CRITERIA_SOURCE
    return None, None


def _acceptance_content(context, rules):
    """(content, source_label) для SA-08 по приоритету сильных источников.

    Сильные источники: «Критерии приёмки» → «Ожидаемый результат» → «Цель» +
    заголовок. «Объём работ» проверяется отдельно (`analysis.work_scope`):
    у него своя формулировка сообщения, потому что это основание другого рода.
    """
    content, source = _criteria_content(context, rules)
    if content:
        return content, source
    return _goal_criteria(context)


def _labels(context):
    labels = _context_value(context, "labels") or []
    if not isinstance(labels, (list, tuple)):
        return set()
    return {str(item).strip().casefold() for item in labels if str(item).strip()}


# Метки, означающие «задача трогает интеграции»: сигнал `integration_labels`
# в `params.derive` и подсказка в сообщении `SA-04`. Вердикт по ним больше не
# меняется — эскалация `SA-04` до REQUIRED отменена.
INTEGRATION_LABELS = frozenset(
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


def _touches_integrations(context):
    if _labels(context) & INTEGRATION_LABELS:
        return True
    text = _description(context).casefold()
    return bool(
        re.search(r"(изменени|правк|нов|доработк)\w*\s+(контракт|api|интеграц)", text)
    )


def _is_new_feature(context):
    issue_type = str(context.get("issue_type") or "").strip().casefold()
    if issue_type in ("feature", "new feature", "фича"):
        return True
    return bool(_labels(context) & {"feature", "toggle", "feature-toggle"})


def _toggle_evidence(context, rules):
    content = _section_content(context, "toggle", rules)
    if content:
        return content
    for attachment in context.get("attachments") or []:
        name = attachment
        if isinstance(attachment, dict):
            name = attachment.get("filename") or attachment.get("name") or ""
        if re.search(r"(?i)(toggle|тоггл|scoring|скоринг)", str(name)):
            return "вложение: %s" % name
    text = _description(context).casefold()
    if "риск поломки" in text and "неопределен" in text.replace("ё", "е"):
        return "таблицы «Риск поломки» и «Неопределённость» в описании задачи"
    return None


def _sa_checklist_evidence(context):
    declared = context.get("sa_checklist")
    found = set()
    if isinstance(declared, dict):
        found.update(
            str(key).casefold() for key, value in declared.items() if _is_filled(value)
        )
    elif isinstance(declared, (list, tuple)):
        found.update(str(item).casefold() for item in declared)
    text = _description(context).casefold().replace("ё", "е")
    text += " " + " ".join(sorted(found))
    present, missing = [], []
    for label, keywords in SA_CHECKLIST_ITEMS:
        if any(word in text for word in keywords):
            present.append(label)
        else:
            missing.append(label)
    return present, missing


def _documentation_text(context):
    parts = []
    for key in ("documentation", "docs", "dependencies"):
        value = context.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, dict):
                    parts.extend(str(v) for v in item.values())
                else:
                    parts.append(str(item))
        elif isinstance(value, dict):
            parts.extend(str(v) for v in value.values())
    fields = context.get("fields") or {}
    if isinstance(fields, dict):
        for key in ("documentation", "docs", "dependencies"):
            value = fields.get(key)
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, (list, tuple)):
                parts.extend(str(item) for item in value)
    parts.append(_description(context))
    return " ".join(parts).casefold().replace("ё", "е")


def _affected_contracts(context):
    for holder in (context, context.get("fields") or {}):
        if not isinstance(holder, dict):
            continue
        value = holder.get("dependencies")
        if isinstance(value, (list, tuple)) and value:
            return list(value)
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return []


# Маркеры «задача про тестирование» в заголовке/описании. Больше не включают
# QA-оценку: тип задачи решает (`QA_REQUIRED_ISSUE_TYPES`). Остались только
# информационной пометкой в причине `detect_has_testing`.
TESTING_TEXT_MARKERS = (
    "тест",
    "автотест",
    "test",
    "qa",
    "покрыть тестами",
    "регресс",
)

# Метки «задача про тестирование».
TESTING_LABELS = frozenset({"qa", "test", "testing", "autotest", "автотест"})

# Типы задач, для которых нужна оценка QA. Остальные типы (Задача, Tech Debt,
# ADR, Релиз, Дизайн) проверку результата включают в объём исполнителя — QA-
# записи в оценке нет. Набор переопределяется конфигом:
# `validation.qa_required_issue_types`.
QA_REQUIRED_ISSUE_TYPES = frozenset(
    {"feature", "new feature", "фича", "ошибка", "bug", "дефект"}
)


def qa_required_types(required_issue_types=None):
    """Набор типов задач, требующих QA-оценки, в сравнимом виде.

    `None` — дефолт `QA_REQUIRED_ISSUE_TYPES`; список из конфига
    (`validation.qa_required_issue_types`) нормализуется так же: strip +
    casefold. Пустой список — валидное значение «QA не нужен нигде».
    """
    source = (
        QA_REQUIRED_ISSUE_TYPES
        if required_issue_types is None
        else required_issue_types
    )
    if isinstance(source, str):
        source = [source]
    return frozenset(
        str(item).strip().casefold() for item in source if str(item).strip()
    )


def _testing_signal(context):
    """Фраза про найденный сигнал тестирования (для информационной пометки).

    Сигналы `TESTING_TEXT_MARKERS`/`TESTING_LABELS`/раздела тестирования больше
    не включают QA-оценку: тип задачи решает. Они остаются только объяснением,
    почему QA в задаче всё-таки ожидали.
    """
    text = (_summary_text(context) + "\n" + _description(context)).casefold().replace(
        "ё", "е"
    )
    for marker in TESTING_TEXT_MARKERS:
        if marker in text:
            return "в тексте есть сигнал «%s»" % marker
    matched = _labels(context) & TESTING_LABELS
    if matched:
        return "в метках есть сигнал «%s»" % ", ".join(sorted(matched))
    if _find_section(_description(context), _aliases(default_rules(), "testing")):
        return "в описании есть раздел тестирования"
    return None


def detect_has_testing(context, required_issue_types=None):
    """(has_testing, reason) по правилу QA-01.

    QA-оценка нужна только для типов задач из `QA_REQUIRED_ISSUE_TYPES` (по
    умолчанию — Feature/Ошибка и их синонимы). Для остальных типов (Задача,
    Tech Debt, ADR, Релиз, Дизайн) исполнитель выполняет полный объём, включая
    проверку результата, — QA-записи в оценке нет.

    Порядок сигналов:

    1. `qa_estimation` заполнена — явное решение человека уважается всегда;
    2. тип задачи входит в набор обязательных — QA требуется;
    3. иначе QA не требуется; сигналы тестирования (текст/метки/раздел)
       дописываются в причину как информация и QA не включают.

    `required_issue_types` — список из конфига
    (`validation.qa_required_issue_types`); `None` — дефолтный набор.
    """
    qa_estimation = _context_value(context, "qa_estimation")
    if _is_filled(qa_estimation):
        return True, "заполнена QA Estimation"

    issue_type = str(_context_value(context, "issue_type") or "").strip()
    if issue_type and issue_type.casefold() in qa_required_types(required_issue_types):
        return True, "тип задачи «%s» требует оценки QA" % issue_type

    role = str(_context_value(context, "role") or "").strip() or "исполнителя"
    reason = (
        "тип задачи «%s» не требует QA-оценки: объём исполнителя (роль %s) "
        "включает проверку результата" % (issue_type or "не указан", role)
    )
    signal = _testing_signal(context)
    if signal:
        reason = "%s; %s, но тип задачи не требует QA-оценки" % (reason, signal)
    return False, reason


# ---------------------------------------------------------------------------
# Проверки
# ---------------------------------------------------------------------------


def _measurable_criteria(content):
    """Строки критериев, в которых есть измеримый признак.

    Тонкая обёртка: единственная реализация живёт в `analysis.measurable_criteria`
    (её же использует содержательный анализ). Дублировать регэксп в движке
    проверок нельзя — две реализации разъедутся.
    """
    return analysismod.measurable_criteria(content)


def _deliverable_criteria(content):
    """Строки критериев, фиксирующие результат работ (артефакт, а не поведение).

    Тонкая обёртка над `analysis.deliverable_criteria`: единственная реализация
    правила живёт в анализе, движок проверок её только вызывает.
    """
    return analysismod.deliverable_criteria(content)


def _evidence(value):
    """Цитата-подтверждение. Пустая строка — «подтверждения нет».

    Схема `validation.schema.json` требует строку, поэтому `null` недопустим:
    отсутствие подтверждения кодируется пустой строкой (как и разрешает
    описание поля в схеме). Длинная цитата обрезается до `limits.MAX_TEXT_CHARS`
    с многоточием — в отчёт не должен попадать весь текст задачи.
    """
    if value is None:
        return ""
    text = str(value).strip().replace("\n", " ")
    return limits.truncate(text)


def _shorten(value, limit):
    """Обрезать строку до `limit` символов с многоточием."""
    text = str(value or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _metric_value(analysis, path):
    """Значение метрики по точечному пути (`clarity.score`); None — нет данных."""
    node = analysis if isinstance(analysis, dict) else {}
    for part in str(path or "").split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _evaluate_content(entry, context, analysis):
    """Содержательная проверка: метрика `analysis` против порога правила.

    Правила не «ищут раздел», а сравнивают число из анализа с порогом. Порог
    живёт в каталоге (`min`/`max`), метрика — в `analysis.analyze`, поэтому
    правило можно перекалибровать, не трогая код анализа.
    """
    kind = entry["kind"]

    if kind == "scenarios":
        issue_type = str(_context_value(context, "issue_type") or "").strip().casefold()
        if issue_type in ("ошибка", "bug", "дефект"):
            steps = _metric_value(analysis, "reproduction.steps") or 0
            need = int(entry.get("min_steps") or 2)
            evidence = "шагов воспроизведения: %d" % steps
            if steps >= need:
                return "PASS", evidence, "шагов воспроизведения достаточно (%d)" % steps
            return (
                "FAIL",
                evidence,
                "для «Ошибки» нужно ≥ %d шагов воспроизведения, описано %d"
                % (need, steps),
            )
        if issue_type not in ("feature", "фича", "new feature", "задача", "task"):
            return "NA", "", "тип задачи не требует описания сценариев"
        count = _metric_value(analysis, "scenarios.count") or 0
        need = int(entry.get("min_scenarios") or 1)
        evidence = "сценариев: %d" % count
        if count >= need:
            return "PASS", evidence, "сценарии описаны (%d)" % count
        return "FAIL", evidence, "сценарии не описаны (нужен ≥ %d)" % need

    path = str(entry.get("metric") or "")
    value = _metric_value(analysis, path)
    if value is None:
        return "UNKNOWN", "", "нет данных для анализа: %s" % path
    number = float(value)
    minimum = entry.get("min")
    maximum = entry.get("max")

    if path == "area.confidence":
        name = str(_metric_value(analysis, "area.name") or "")
        evidence = "область: %s (%.2f)" % (name or "не определена", number)
    elif path == "ambiguity.ratio":
        evidence = "доля маркеров неопределённости: %.3f" % number
    else:
        evidence = "%s = %.2f" % (path.split(".")[0], number)

    ok = True
    if minimum is not None and number < float(minimum):
        ok = False
    if maximum is not None and number > float(maximum):
        ok = False

    if ok:
        return (
            "PASS",
            evidence,
            "%s (%.2f)" % (entry.get("pass_message") or "показатель в норме", number),
        )

    if maximum is not None:
        message = "%s (%.3f > %.3f)" % (
            entry.get("fail_message") or "показатель выше порога",
            number,
            float(maximum),
        )
    else:
        message = "%s (%.2f < %.2f)" % (
            entry.get("fail_message") or "показатель ниже порога",
            number,
            float(minimum if minimum is not None else 0.0),
        )
    return "FAIL", evidence, message


def _absent_fields(context):
    """Множество канонических имён полей, которых нет в проекте задачи.

    `context.fields.absent_in_project` — необязательный список. Принимается
    строка (одно поле) и список; имена сравниваются нормализованно
    (регистр/`ё`/пробелы не важны). Нет ключа — пустое множество: поведение
    правил не меняется.
    """
    fields = context.get("fields") if isinstance(context, dict) else None
    raw = fields.get("absent_in_project") if isinstance(fields, dict) else None
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return frozenset()
    return frozenset(_normalize(str(item)) for item in raw if str(item).strip())


def _absent_field_name(context, field_key):
    """Каноническое имя поля, если оно отсутствует в проекте, иначе None."""
    canonical = ABSENT_FIELD_NAMES.get(str(field_key or "").strip())
    if not canonical:
        return None
    if _normalize(canonical) in _absent_fields(context):
        return canonical
    return None


def _evaluate(entry, context, rules, flags, analysis=None):
    """Вернуть (status, evidence, message) для одной проверки."""
    kind = entry["kind"]

    if entry.get("condition") and not flags.get(entry["condition"]):
        return (
            "NA",
            "",
            "правило неприменимо: %s" % _condition_text(entry["condition"], flags),
        )

    if kind in ("clarity", "scope", "dependencies", "ambiguity", "area", "scenarios"):
        return _evaluate_content(entry, context, analysis or {})

    if kind == "field":
        absent = _absent_field_name(context, entry["field"])
        if absent:
            return (
                "NA",
                "",
                "поле «%s» отсутствует в проекте задачи — проверка не применима"
                % absent,
            )
        value = _context_value(context, entry["field"])
        if _is_filled(value):
            return "PASS", _evidence(value), "поле заполнено"
        return "FAIL", "", "не заполнено поле «%s»" % entry["section"]

    if kind == "qa_estimation":
        # QA не блокирует оценку: пустое поле не FAIL. Заполненное — факт из
        # Jira, значение берётся как есть; пустое при `has_testing` — QA считает
        # модель (`estimate._qa_entry`). QA нужна только для типов
        # Feature/Ошибка: у остальных проверку выполняет исполнитель.
        value = qa_estimation_value(context)
        if value is not None:
            return (
                "PASS",
                _evidence(value),
                "QA Estimation заполнена: %s" % _evidence(value),
            )
        reason = flags.get("has_testing_reason") or ""
        if flags.get("has_testing"):
            message = "QA Estimation не заполнена — будет рассчитана моделью"
            evidence = "derived"
            if reason:
                message = "%s (has_testing: %s)" % (message, reason)
        else:
            issue_type = (
                str(_context_value(context, "issue_type") or "").strip() or "не указан"
            )
            message = "QA Estimation не заполнена — %s" % (
                reason
                or "тип задачи «%s» не требует QA-оценки, проверка входит в объём "
                "исполнителя" % issue_type
            )
            evidence = "n/a"
        return "PASS", evidence, message

    if kind == "links":
        absent = _absent_field_name(context, entry.get("field", "links"))
        if absent:
            return (
                "NA",
                "",
                "поле «%s» отсутствует в проекте задачи — проверка не применима"
                % absent,
            )
        links = _context_value(context, entry.get("field", "links"))
        if _is_filled(links):
            count = len(links) if isinstance(links, (list, tuple)) else 1
            return "PASS", "связей: %d" % count, "связи с другими задачами указаны"
        return "FAIL", "", "не указаны связи с другими задачами"

    if kind == "description_length":
        text = _description(context).strip()
        minimum = int(entry.get("min_chars") or MIN_DESCRIPTION_CHARS)
        if len(text) >= minimum:
            return (
                "PASS",
                _evidence(text),
                "описание заполнено (%d символов)" % len(text),
            )
        if not text:
            return "FAIL", "", "основное описание пустое"
        return (
            "FAIL",
            _evidence(text),
            "основное описание короче %d символов (сейчас %d)" % (minimum, len(text)),
        )

    if kind == "section":
        content = _section_content(context, entry["aliases_key"], rules)
        if content:
            return "PASS", _evidence(content), "раздел «%s» заполнен" % entry["section"]
        message = "нет раздела «%s» или он пуст" % entry["section"]
        # Провал раздела не блокирует вердикт, если правило RECOMMENDED. Когда
        # пробел всё же искажает оценку (SA-04), это сказано прямо в сообщении,
        # чтобы «не блокирует» не читалось как «не важно».
        note = entry.get("fail_note")
        if note:
            message = "%s — %s" % (message, note)
        if entry.get("fail_note_integration") and _touches_integrations(context):
            message = "%s; %s" % (message, entry["fail_note_integration"])
        return "FAIL", "", message

    if kind == "acceptance_criteria":
        # Порядок источников: критерии приёмки → ожидаемый результат → объём
        # работ → цель + заголовок. FAIL — только если не нашлось ничего:
        # наличие любого из оснований означает, что проверить готовность можно.
        criteria_content, criteria_source = _criteria_content(context, rules)
        measurable = _measurable_criteria(criteria_content) if criteria_content else []
        deliverable = _deliverable_criteria(criteria_content) if criteria_content else []
        if criteria_content and (measurable or deliverable):
            # Объединение, а не сумма: строка «подготовлены автотесты на 5
            # сценариев» одновременно измерима и является результатом работ.
            total = list(dict.fromkeys(list(measurable) + list(deliverable)))
            return (
                "PASS",
                _evidence((measurable or deliverable)[0]),
                "критериев: %d (измеримых %d, как результат работ %d; %s)"
                % (len(total), len(measurable), len(deliverable), criteria_source),
            )

        # Объём работ: если известно, что надо сделать, — понятно, что меняется
        # и как это проверять (раздел «Решение»/«Задача»/«Необходимо» либо
        # строка «маркер долженствования + глагол действия»).
        scope_content, scope_source, scope_evidence = analysismod.work_scope(context)
        if scope_content:
            if scope_source == "описание задачи":
                message = "объём работ описан в описании: «%s»" % _shorten(
                    scope_evidence, 80
                )
            else:
                message = "объём работ описан (%s): %s" % (
                    scope_source,
                    _shorten(scope_evidence, 80),
                )
            return "PASS", _evidence(scope_evidence), message

        goal_content, goal_source = _goal_criteria(context)
        if goal_content:
            measurable = _measurable_criteria(goal_content)
            deliverable = _deliverable_criteria(goal_content)
            if measurable or deliverable:
                total = list(dict.fromkeys(list(measurable) + list(deliverable)))
                if goal_source == SUMMARY_CRITERIA_SOURCE:
                    # Раздела критериев нет: проверен заголовок. «критериев: N»
                    # здесь вводило бы в заблуждение — источник назван прямо.
                    return (
                        "PASS",
                        _evidence((measurable or deliverable)[0]),
                        "критерий взят из заголовка задачи (%d): разделов «Критерии "
                        "приёмки»/«Ожидаемый результат» и объёма работ нет, проверена "
                        "формулировка заголовка (измеримых %d, как результат работ %d)"
                        % (len(total), len(measurable), len(deliverable)),
                    )
                return (
                    "PASS",
                    _evidence((measurable or deliverable)[0]),
                    "критериев: %d (измеримых %d, как результат работ %d; %s)"
                    % (len(total), len(measurable), len(deliverable), goal_source),
                )

        if criteria_content:
            # Последнее основание — заголовок с действием: «что делать» названо,
            # пусть и верхнеуровнево. Блокировка остаётся только там, где из
            # задачи не понять даже этого.
            summary = _summary_text(context).strip()
            if summary and analysismod.explicit_action(summary):
                return (
                    "PASS",
                    _evidence(summary),
                    "что делать названо в заголовке задачи: «%s» — раздела "
                    "критериев, ожидаемого результата и объёма работ нет, "
                    "проверять готовность можно только по заголовку"
                    % _shorten(summary, 80),
                )
            return (
                "FAIL",
                _evidence(criteria_content),
                "%s есть, но ни один критерий не измерим и не описывает результат "
                "работ (нет чисел, порогов, наблюдаемого поведения, созданных "
                "артефактов); объёма работ и действия в заголовке в задаче нет"
                % criteria_source,
            )
        summary = _summary_text(context).strip()
        if summary and analysismod.explicit_action(summary):
            return (
                "PASS",
                _evidence(summary),
                "что делать названо в заголовке задачи: «%s» — критериев приёмки, "
                "ожидаемого результата и объёма работ нет, проверять готовность "
                "можно только по заголовку" % _shorten(summary, 80),
            )
        return (
            "FAIL",
            "",
            "нет критериев приёмки, ожидаемого результата, объёма работ и действия "
            "в заголовке задачи — не понять, что делать и как проверять",
        )

    if kind == "sa_checklist":
        present, missing = _sa_checklist_evidence(context)
        if missing:
            return (
                "FAIL",
                "пройдено: %s" % (", ".join(present) if present else "ничего"),
                "чек-лист SA не пройден, не хватает: %s" % ", ".join(missing),
            )
        return (
            "PASS",
            "пройдено: %s" % ", ".join(present),
            "чек-лист SA пройден полностью",
        )

    if kind == "feature_toggle":
        if not _is_new_feature(context):
            return "NA", "", "не новый функционал — скоринг тоггла не требуется"
        evidence = _toggle_evidence(context, rules)
        if evidence:
            return "PASS", _evidence(evidence), "скоринг фича-тогла приложен"
        return (
            "FAIL",
            "",
            "новый функционал без скоринга фича-тогла (риск поломки, "
            "неопределённость, оценка)",
        )

    if kind == "dependency_doc":
        if not flags.get("with_dependencies"):
            return "NA", "", "проверка зависимостей выключена"
        if not _affected_contracts(context):
            return "NA", "", "затронутых контрактов не указано"
        requirement = DOC_REQUIREMENTS.get(entry["id"], {})
        text = _documentation_text(context)
        for alias in requirement.get("aliases") or ():
            if alias in text:
                return (
                    "PASS",
                    "найден раздел: %s" % alias,
                    "раздел %s найден" % requirement.get("label", alias),
                )
        return (
            "FAIL",
            "",
            "не найден раздел документации %s" % requirement.get("label", ""),
        )

    return "NA", "", "неизвестный вид проверки: %s" % kind


def _condition_text(condition, flags):
    if condition == "has_testing":
        return "задача не предполагает тестирование (%s)" % flags.get(
            "has_testing_reason", ""
        )
    if condition == "with_dependencies":
        return "флаг with_dependencies выключен"
    return condition


def _verdict(checks):
    """Вердикт по severity: блокирует только REQUIRED, WARN даёт RECOMMENDED.

    `OPTIONAL` — гигиена полей шаблона и «похвала» (CL-06/CL-07): провал такого
    правила не меняет вердикт, иначе `OK` был бы недостижим. Политика
    согласована: BLOCKED — только за непонятную суть (CL-01) и отсутствие
    измеримого критерия приёмки (SA-08).
    """
    required_fail = any(
        item["status"] in ("FAIL", "UNKNOWN") and item["severity"] == "REQUIRED"
        for item in checks
    )
    if required_fail:
        return "BLOCKED"
    recommended_fail = any(
        item["status"] in ("FAIL", "UNKNOWN") and item["severity"] == "RECOMMENDED"
        for item in checks
    )
    return "WARN" if recommended_fail else "OK"


def run_checks(context, rules=None, with_dependencies=False, qa_required_issue_types=None):
    """Проверить снимок задачи. Возвращает validation.json (dict).

    `qa_required_issue_types` — типы задач, для которых нужна QA-оценка
    (`validation.qa_required_issue_types` конфига). `None` — дефолтный набор
    `QA_REQUIRED_ISSUE_TYPES`: прямой вызов из `synth.py` остаётся совместимым.
    """
    if not isinstance(context, dict):
        raise CheckError("context должен быть словарём")
    missing = [key for key in CONTEXT_KEYS if key not in context]
    if missing:
        raise CheckError(
            "нет ключей %s — пересоберите снимок задачи" % ", ".join(missing)
        )
    if not isinstance(context.get("fields"), dict):
        raise CheckError("context.fields должен быть словарём")

    rules = rules or default_rules()
    has_testing, has_testing_reason = detect_has_testing(
        context, qa_required_issue_types
    )
    analysis = analysismod.analyze(context)
    flags = {
        "has_testing": has_testing,
        "has_testing_reason": has_testing_reason,
        "with_dependencies": bool(with_dependencies),
    }

    checks, gaps = [], []
    for entry in CHECKS:
        status, evidence, message = _evaluate(entry, context, rules, flags, analysis)
        severity = entry["severity"]
        if entry.get("condition") and status == "NA":
            severity = entry.get("severity_else", severity)
        # Механизм эскалации сохранён для будущих правил: сейчас флага
        # `escalate` нет ни у одного правила каталога, блокируют ровно CL-01 и
        # SA-08. `SA-04` (Контракт) эскалацию больше не использует — его провал
        # влияет на точность оценки, но вердикт не меняет.
        if entry.get("escalate") == "integration" and _touches_integrations(context):
            severity = "REQUIRED"

        checks.append(
            {
                "id": entry["id"],
                "section": entry["section"],
                "severity": severity,
                "status": status,
                "evidence": limits.truncate(evidence),
                "message": limits.truncate(message),
            }
        )
        if status in ("FAIL", "UNKNOWN") and severity != "OPTIONAL":
            gap = {
                "id": entry["id"],
                "severity": severity,
                "question": limits.truncate(entry["question"]),
                "target_role": entry["target_role"],
                "where_to_find": entry["where_to_find"],
            }
            # `why` — вторая половина компактного пункта отчёта
            # («что не хватает — почему это влияет»). Пустое правило его не
            # добавляет: схема требует непустую строку.
            why = limits.truncate(entry.get("why"))
            if why:
                gap["why"] = why
            gaps.append(gap)

    checks.sort(key=lambda item: item["id"])
    gaps.sort(key=lambda item: item["id"])
    # Не больше 200 пробелов в артефакте: отчёт должен оставаться читаемым,
    # а каталог правил физически не даёт такого количества — лимит страхует
    # от будущего расширения и от ручных validation.json.
    gaps = limits.limit_gaps(gaps)

    return {
        "task_key": str(context.get("task_key")),
        "checked_at": str((rules or {}).get("now") or statemod.now_utc()),
        "template": _template_block(rules),
        "checks": checks,
        "verdict": _verdict(checks),
        "gaps": gaps,
        "with_dependencies": bool(with_dependencies),
        "analysis": analysis,
        # Отдельная ось смысла: «что делается» по заголовку и тексту. На вердикт
        # и на числа оценки не влияет — нужна отчёту и комментарию, чтобы
        # читатель не угадывал вид работ по заголовку.
        "work_intent": analysismod.work_intent(context),
    }


# ---------------------------------------------------------------------------
# questions.json и черновик комментария
# ---------------------------------------------------------------------------


def build_questions(validation, comment_draft_path="comment-draft.md"):
    """Собрать questions.json из пробелов validation.json."""
    questions = []
    for gap in limits.limit_gaps(validation.get("gaps") or []):
        entry = _CHECKS_BY_ID.get(gap.get("id")) or {}
        questions.append(
            {
                "id": "q." + str(gap.get("id")),
                "text": limits.truncate(str(gap.get("question"))),
                "why": entry.get("why")
                or "без этого пункта оценка объёма ненадёжна",
                "target_role": gap.get("target_role"),
                "where_to_find": str(gap.get("where_to_find")),
                "blocking": gap.get("severity") == "REQUIRED",
            }
        )
    questions.sort(key=lambda item: item["id"])
    return {
        "task_key": validation.get("task_key"),
        "generated_at": validation.get("checked_at"),
        "questions": questions,
        "comment_draft_path": str(comment_draft_path),
    }


def render_comment_draft(validation, questions):
    """Markdown-черновик комментария в Jira. Без @-упоминаний и контактов."""
    items = list(questions.get("questions") or [])
    blocking = [item for item in items if item.get("blocking")]
    other = [item for item in items if not item.get("blocking")]

    lines = [
        "## Проверка готовности задачи %s" % (validation.get("task_key") or ""),
        "",
        "Вердикт: **%s**. Проверок: %d, пробелов: %d."
        % (
            validation.get("verdict"),
            len(validation.get("checks") or []),
            len(validation.get("gaps") or []),
        ),
        "",
        "### Чего не хватает для оценки (блокирует)",
    ]
    if blocking:
        for item in blocking:
            lines.append(
                "- **%s** (%s): %s"
                % (item["id"], item["target_role"], item["text"])
            )
    else:
        lines.append("- блокирующих пробелов нет")

    lines.extend(["", "### Что стоит уточнить"])
    if other:
        for item in other:
            lines.append(
                "- **%s** (%s): %s"
                % (item["id"], item["target_role"], item["text"])
            )
    else:
        lines.append("- уточнений не требуется")

    lines.extend(["", "### Где искать недостающее"])
    places = []
    for item in items:
        pair = (item.get("where_to_find"), item.get("target_role"))
        if pair not in places:
            places.append(pair)
    if places:
        for where, role in places:
            lines.append("- %s — %s" % (where, role))
    else:
        lines.append("- искать нечего: пробелов нет")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI: `trr check --task <KEY>`
# ---------------------------------------------------------------------------


def _runs_root(workdir):
    return Path(workdir) / statemod.STATE_DIR / "runs"


def _find_run_dir(workdir, task_key, run_id=None):
    base = _runs_root(workdir) / task_key
    if run_id:
        candidate = base / run_id
        return candidate if candidate.is_dir() else None
    if not base.is_dir():
        return None
    candidates = sorted(
        (
            path
            for path in base.iterdir()
            if path.is_dir() and (path / "context.json").is_file()
        ),
        key=lambda path: path.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _relative(workdir, path):
    try:
        return str(Path(path).resolve().relative_to(Path(workdir).resolve()))
    except (ValueError, OSError):
        return str(path)


def _load_json(path):
    return limits.read_json(path)


def _emit(args, message):
    if not getattr(args, "quiet", False):
        print(message)


def _finish(args, code, message, **payload):
    _emit(args, message)
    if getattr(args, "json", False):
        data = {"status": "ok" if code == 0 else "blocked", "code": code}
        data.update(payload)
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
    return code


def _intent_info_line(validation):
    """`[INFO] intent: …` — что делается по заголовку и тексту (до 2 сигналов)."""
    items = validation.get("work_intent") or []
    if not items:
        return ""
    parts = []
    for item in items[:2]:
        parts.append(
            "%s (%s)" % (analysismod.intent_label(item.get("intent")), item.get("confidence"))
        )
    return "[INFO] intent: %s" % "; ".join(parts)


def _resolve_template(workdir, reference):
    """Найти файл шаблона: абсолютный путь → от проекта → от корня скилла."""
    candidate = Path(str(reference)).expanduser()
    if candidate.is_absolute():
        return candidate
    for base in (Path(workdir), Path(configmod.SKILL_ROOT)):
        option = base / candidate
        if option.is_file():
            return option
    return Path(workdir) / candidate


def _run_cli(workdir, args):
    """`trr check`: прочитать context.json прогона, записать три артефакта."""
    task_key = getattr(args, "task", None)
    if not task_key:
        return _finish(args, 2, "[BLOCKED] check: не указан --task <KEY>")

    config_file = configmod.config_path(workdir)
    if not config_file.is_file():
        return _finish(
            args,
            3,
            "[MISSING] %s — сначала /task-readiness-review init"
            % configmod.CONFIG_FILENAME,
        )
    try:
        cfg = configmod.load_config(config_file)
    except configmod.ConfigError as exc:
        return _finish(args, 3, "[MISSING] config — %s" % exc)

    # Гейт модели: без обученной модели проверка бессмысленна (CONTRACT.md §6.1).
    # Живёт в CLI-обвязке, а не в run_checks: чистое ядро проверок модель не
    # читает и не должно требовать её наличия.
    model_file = Path(workdir) / statemod.STATE_DIR / statemod.MODEL_RELATIVE
    try:
        model_page = statemod.load(workdir).get("model_page")
    except statemod.StateError:
        model_page = None
    if not model_file.is_file():
        return _finish(
            args,
            2,
            "[BLOCKED] check: модель оценки не обучена — запустите "
            "/task-readiness-review train",
        )
    if not model_page:
        return _finish(
            args,
            2,
            "[BLOCKED] check: страница модели не опубликована — запустите "
            "/task-readiness-review publish --model (для проекта без Confluence: "
            "--target obsidian)",
        )

    # Гейт свежести: опубликованная страница модели должна соответствовать
    # ТЕКУЩЕЙ модели. После `enrich`/`train` модель меняется, страница остаётся
    # старой, и проверка молча идёт по устаревшей версии — поэтому расхождение
    # сумм блокирует прогон. Артефакты без `hash` (до появления гейта) дают
    # только предупреждение: обратная совместимость важнее строгости.
    page_hash = ""
    if isinstance(model_page, dict):
        page_hash = str(model_page.get("hash") or "").strip()
    if not page_hash:
        _emit(
            args,
            "[WARN] check: у state.model_page нет hash — свежесть страницы модели "
            "не проверена; перепубликуйте: /task-readiness-review publish --model",
        )
    else:
        try:
            current_hash = statemod.model_checksum(workdir)
        except statemod.StateError as exc:
            return _finish(args, 5, "[MISSING] check: модель не читается — %s" % exc)
        if page_hash != current_hash:
            return _finish(
                args,
                2,
                "[BLOCKED] check: страница модели устарела (hash %s… ≠ модель %s…) — "
                "запустите /task-readiness-review publish --model"
                % (page_hash[:8], current_hash[:8]),
            )

    run_dir = _find_run_dir(workdir, task_key, getattr(args, "run", None))
    if run_dir is None:
        return _finish(
            args,
            2,
            "[BLOCKED] check: нет context.json задачи %s — соберите снимок задачи "
            "в %s/<RUN-ID>/context.json" % (task_key, _runs_root(workdir) / task_key),
        )
    context_file = run_dir / "context.json"
    try:
        context = _load_json(context_file)
    except (OSError, ValueError) as exc:
        return _finish(args, 5, "[MISSING] %s — %s" % (context_file, exc))
    if not isinstance(context, dict):
        return _finish(args, 5, "[MISSING] %s — должен быть JSON-объектом" % context_file)

    # Ручной override эвристических параметров (этап A): число попадает в
    # context.json, чтобы provenance и последующий estimate видели одно и то
    # же значение. На проверки готовности override не влияет.
    overrides = {
        name: getattr(args, name)
        for name in ("weight", "heat", "connectivity")
        if getattr(args, name, None) is not None
    }
    if overrides:
        context.update({name: float(value) for name, value in overrides.items()})
        schema_lite.write_json(context_file, context)
        _emit(
            args,
            "[INFO] check: override %s записан в %s"
            % (
                ", ".join("%s=%.2f" % (name, value) for name, value in sorted(overrides.items())),
                context_file,
            ),
        )

    override = cfg.get("override_template")
    if not override and isinstance(cfg.get("sources"), dict):
        override = cfg["sources"].get("override_template")
    try:
        rules = rules_from_template(_resolve_template(workdir, override)) if override else default_rules()
    except CheckError as exc:
        return _finish(args, 3, "[MISSING] шаблон — %s" % exc)

    with_dependencies = bool(
        getattr(args, "with_dependencies", False)
        or (cfg.get("validation") or {}).get("with_dependencies")
    )
    # Типы задач, требующих QA-оценки. Нет ключа в конфиге — дефолт
    # `QA_REQUIRED_ISSUE_TYPES` (обратная совместимость старых конфигов).
    validation_cfg = cfg.get("validation") or {}
    qa_required = (
        validation_cfg.get("qa_required_issue_types")
        if isinstance(validation_cfg, dict)
        else None
    )

    try:
        validation = run_checks(context, rules, with_dependencies, qa_required)
    except CheckError as exc:
        return _finish(args, 5, "[MISSING] context.json: %s" % exc)

    intent_line = _intent_info_line(validation)
    if intent_line:
        _emit(args, intent_line)

    draft_name = "comment-draft.md"
    questions = build_questions(
        validation, _relative(workdir, run_dir / draft_name)
    )

    errors = []
    for name, payload in (("validation", validation), ("questions", questions)):
        try:
            schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, name)
        except schema_lite.SchemaError as exc:
            return _finish(args, 5, "[MISSING] схема %s — %s" % (name, exc))
        errors.extend("%s: %s" % (name, error) for error in schema_lite.validate(payload, schema))
    if errors:
        for error in errors:
            _emit(args, "[MISSING] %s" % error)
        return _finish(args, 5, "[MISSING] артефакты не соответствуют схемам")

    schema_lite.write_json(run_dir / "validation.json", validation)
    schema_lite.write_json(run_dir / "questions.json", questions)
    draft = render_comment_draft(validation, questions)
    # Атомарно: по этому файлу агент публикует комментарий с вопросами, и его
    # sha256 уходит в `state.published[]` — половина файла недопустима.
    reportmod.write(run_dir, draft, draft_name)

    try:
        statemod.add_run(
            workdir,
            validation["task_key"],
            _relative(workdir, run_dir),
            validation["verdict"],
            validation["checked_at"],
        )
        statemod.set_stage(workdir, "checked")
    except statemod.StateError:
        pass

    # Зеркало: прогон, валидация и метрики проверки. Пишется после того, как
    # артефакты и state уже на диске, и никогда не меняет код выхода `check`.
    storemod.save_check(
        workdir,
        cfg,
        run_dir.name,
        validation["task_key"],
        _relative(workdir, run_dir),
        validation,
        model_checksum=storemod.current_model_checksum(workdir),
        config_sha256=configmod.config_sha256(cfg),
    )

    comment_code, comment_lines = _jira_comment_step(
        args, workdir, cfg, task_key, draft, run_dir
    )
    if comment_code is not None:
        return comment_code

    lines = [
        "[OK] check %s: verdict=%s, проверок %d, пробелов %d"
        % (
            validation["task_key"],
            validation["verdict"],
            len(validation["checks"]),
            len(validation["gaps"]),
        )
    ]
    lines.extend(comment_lines)
    return _finish(
        args,
        0,
        "\n".join(lines),
        verdict=validation["verdict"],
        validation=_relative(workdir, run_dir / "validation.json"),
        questions=_relative(workdir, run_dir / "questions.json"),
        comment_draft=_relative(workdir, run_dir / draft_name),
    )


def _jira_comment_step(args, workdir, cfg, task_key, draft, run_dir):
    """Комментарий с вопросами: план публикации и запись id (`comment_mode: post`).

    Постинг делает агент через MCP Jira — Python в Jira не пишет. Здесь только
    план (`create`/`update` по `state.published[]`) и фиксация id, который агент
    вернул после публикации. Маркер вопросов отдельный, поэтому id комментария с
    вопросами не пересекается с id комментариев валидации и оценки.

    `--no-jira` (Jira недоступна или запись отключена) — вопросы сохраняются в
    `actions/jira-questions.md` с маркером и шагами ручной публикации.

    Возвращает `(код_выхода | None, строки)`: `None` — шаг выполнен, `check`
    продолжает с кодом 0.
    """
    mode = ((cfg.get("jira") or {}).get("comment_mode") or "post").strip() or "post"
    comment_id = getattr(args, "comment_id", None)

    if comment_id:
        try:
            entry = publishmod.record_questions(
                workdir,
                task_key,
                comment_id,
                getattr(args, "url", None),
                run=getattr(args, "run", None),
            )
        except publishmod.MissingReport as exc:
            return _finish(args, 4, "[MISSING] %s" % exc), []
        except statemod.StateError as exc:
            return (
                _finish(
                    args,
                    2,
                    "[BLOCKED] check: %s — проверьте .task-readiness/state.json" % exc,
                ),
                [],
            )
        return (
            None,
            [
                "[OK] check: questions comment_id=%s (sha256:%s)"
                % (entry["comment_id"], entry["content_sha256"][:12])
            ],
        )

    if getattr(args, "no_jira", False):
        # Jira недоступна (или запись отключена): вопросы не теряются — готовый
        # текст с маркером и шаги ручной публикации уходят в action-пакет, как
        # `publish --no-jira` делает для двух своих комментариев.
        return _questions_action_package(args, workdir, task_key, draft, run_dir)
    if getattr(args, "draft", False) or mode != "post":
        return None, []

    draft_path = _relative(workdir, run_dir / "comment-draft.md")
    try:
        info = publishmod.plan_questions(workdir, task_key, draft, draft_path)
    except (publishmod.MissingReport, statemod.StateError) as exc:
        _emit(args, "[MISSING] check: план комментария — %s" % exc)
        return None, []
    return (
        None,
        [
            "[PLAN] questions comment: %s (comment_id=%s)"
            % (info["action"], info["comment_id"] or "-")
        ],
    )


def _questions_action_package(args, workdir, task_key, draft, run_dir):
    """`--no-jira`: сохранить вопросы в `actions/jira-questions.md`, код 0.

    Возвращает `(None, строки)`: недоступность Jira — деградация, а не ошибка.
    """
    draft_path = _relative(workdir, run_dir / "comment-draft.md")
    try:
        info = publishmod.plan_questions(workdir, task_key, draft, draft_path)
        path = publishmod.write_action_package(
            workdir,
            task_key,
            info["body"],
            "--no-jira: Jira недоступна или запись в неё отключена",
            kind=publishmod.KIND_QUESTIONS,
            # Каталог прогона известен точно (`check` его разрешил по `--run`):
            # не полагаемся на «последний на диске», иначе при не-монотонном
            # RUN-ID файл уезжает в чужой прогон.
            run_dir=run_dir,
        )
    except (publishmod.MissingReport, statemod.StateError) as exc:
        _emit(args, "[WARN] check: action-пакет вопросов не записан — %s" % exc)
        return None, []
    return (
        None,
        [
            "[WARN] вопросы в Jira не публикуются (--no-jira)",
            "[OK] текст вопросов для ручной публикации: %s"
            % _relative(workdir, path),
        ],
    )


def run(context, rules=None, with_dependencies=False):
    """Диспетчер: CLI-режим (`run(workdir, args)`) или движок.

    `cli.py` вызывает `module.run(args.workdir, args)` — это CLI-режим.
    Прямой вызов с `context`-словарём — чистый движок (`run_checks`).
    """
    if isinstance(context, (str, os.PathLike)):
        return _run_cli(context, rules)
    return run_checks(context, rules, with_dependencies)

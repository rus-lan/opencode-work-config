#!/usr/bin/env python3
"""Содержательный анализ задачи: о чём задача и насколько она понятна.

Модуль отвечает на вопрос «что видно из текста задачи», а не «есть ли в
описании нужный раздел». Шаблон описания — гигиена (`check.TPL-*`); готовность
к разработке определяется содержанием: понятна ли суть, есть ли измеримый
критерий, описаны ли сценарии/связи/границы.

Вход — снимок задачи (`context.json`, его собирает агент через MCP), выход —
детерминированный словарь метрик (`analyze(context, cfg)`). Ни сети, ни файлов,
ни глобального состояния: модуль чистый, только stdlib.

Метрики (все — из текста задачи, без «секция есть / секции нет»):

    clarity       понятность: длина, доля размытых слов, глагол+объект,
                  конкретика (числа/системы), дублирование заголовка;
    testability   измеримость: число измеримых критериев приёмки (+ для
                  «Ошибки» — ожидаемый/фактический результат);
    reproduction  воспроизводимость «Ошибки»: число шагов, ожидаемый и
                  фактический результат;
    scope         границы объёма: маркеры «не входит / в рамках / только для»,
                  число компонентов, упоминания экранов/сервисов/методов;
    dependencies  связи: число связей и их типы (`blocks`, `is blocked by`,
                  `relates`, `depends`), число упоминаний интеграций;
    scenarios     сценарии: нумерованные списки, «сценарий/кейс», given/when/then,
                  «если … то»;
    area          область/подсистема по словарю (components → labels → epic →
                  summary → description) с уверенностью;
    ambiguity     маркеры неопределённости, нормированные на длину текста;
    signals       счётчики для `params.derive`: числа, даты, системы, доля
                  размытых слов.

Две отдельные оси, которые не входят в метрики и не влияют на числа оценки:

    work_scope()   «что надо сделать»: блок «Задача»/«Решение»/«Необходимо»
                   или строка «маркер долженствования + глагол действия»;
    work_intent()  что именно делается по заголовку и тексту (перенос данных,
                   миграция структуры БД, выгрузка, дашборд, интеграция,
                   рефакторинг, тесты, исследование).

Порогов в модуле нет: порог задаёт правило (`check.CHECKS`), а метрика остаётся
числом, чтобы её можно было показать в отчёте и использовать в параметрах.
`measurable_criteria()` — единственная реализация «измеримого критерия»: её
импортирует `check.py`, дубликата в движке проверок нет.
"""

import math
import re

__all__ = [
    "ACCEPTANCE_ALIASES",
    "ACTION_INFINITIVES",
    "AREA_KEYWORDS",
    "EXPECTED_ALIASES",
    "INTENT_CATALOG",
    "INTENT_LABELS",
    "SCENARIO_ALIASES",
    "VAGUE_MARKERS",
    "WORK_SCOPE_ALIASES",
    "analyze",
    "deliverable_criteria",
    "explicit_action",
    "intent_label",
    "measurable_criteria",
    "work_intent",
    "work_scope",
]

# Потолки нормализации: сигнал «насыщается» на этом значении.
_CLARITY_LENGTH_CAP = 1200
_WORD_CAP_FOR_VAGUE = 25.0  # одно размытое слово на 25 слов текста = 1.0
_AREA_CONFIDENCE_CAP = 4
_SIGNAL_CAP = 8

# Размытые слова: не несут объекта и объёма. Формулировки из практики BA:
# «что-то поправить», «надо сделать», «возможно, как-то».
VAGUE_MARKERS = (
    "что-то",
    "что то",
    "как-то",
    "как то",
    "кое-что",
    "как-нибудь",
    "надо сделать",
    "нужно сделать",
    "возможно",
    "наверное",
    "наверно",
    "по-хорошему",
    "и т.п.",
    "и т.д.",
    "и др.",
    "непонятно",
    "не ясно",
    "неясно",
    "tbd",
    "примерно",
    "в общем",
)

# Маркеры неопределённости (ambiguity). Пересекаются с `params.UNCERTAINTY_MARKERS`
# по смыслу, но считаются здесь иначе: нормируются на длину текста.
UNCERTAINTY_MARKERS = (
    "неизвестн",
    "уточнит",
    "tbd",
    "подводные камни",
    "риск",
    "непонятн",
    "неясн",
    "некорректн",
)

# Глаголы действия: без них заголовок/описание — тема, а не задача.
ACTION_VERBS = (
    "добав",
    "исправ",
    "созда",
    "удал",
    "измен",
    "обнов",
    "ускор",
    "вынести",
    "провер",
    "сократ",
    "перенес",
    "внедр",
    "настро",
    "переписа",
    "подключ",
    "реализ",
    "доработ",
    "оптимиз",
    "поддерж",
    "покрыть",
    "покрой",
    "написать",
    "сделать",
    "убрать",
    "заменить",
    "расширить",
    "вывести",
    "собрать",
    "сверить",
    "обработа",
    "рассчит",
    "найти",
    "починить",
    "отключ",
    "включ",
    "согласова",
    "автоматизир",
    "настроить",
    "тестир",
)

# Слова, которые не могут быть «объектом» действия.
STOPWORDS = frozenset(
    {
        "это",
        "этот",
        "эта",
        "для",
        "чтобы",
        "если",
        "когда",
        "также",
        "через",
        "между",
        "после",
        "перед",
        "будет",
        "было",
        "были",
        "есть",
        "нет",
        "надо",
        "нужно",
        "можно",
        "нельзя",
        "все",
        "всё",
        "что",
        "как",
        "где",
        "кто",
        "чем",
        "тем",
        "или",
        "либо",
        "при",
        "без",
        "над",
        "под",
        "про",
        "они",
        "она",
        "оно",
        "мы",
        "вы",
        "the",
        "and",
        "for",
        "with",
    }
)

# Упоминания систем/технических объектов (конкретика и «связность»).
SYSTEM_MARKERS = (
    "api",
    "rest",
    "graphql",
    "endpoint",
    "grpc",
    "kafka",
    "webhook",
    "сервис",
    "микросервис",
    "контракт",
    "интеграц",
    "очеред",
    "брокер",
    "база данных",
    "бд",
    "таблиц",
    "схем",
    "экран",
    "виджет",
    "модул",
    "хранилищ",
    "провайдер",
    "платформ",
    "метод",
)

# Границы объёма работ.
BOUNDARY_MARKERS = (
    "не входит",
    "вне скоупа",
    "вне scope",
    "за рамками",
    "не затрагива",
    "в рамках",
    "только для",
    "границ",
)

# Маркеры сценариев.
SCENARIO_MARKERS = (
    "сценарий",
    "сценари",
    "альтернативн",
    "кейс",
    "given",
    "when",
    "then",
    "если ",
    "в случае",
)

# Словарь областей. Латинские короткие ключи матчатся по границе слова,
# остальные — подстрокой (морфология русских слов).
AREA_KEYWORDS = {
    "api": (
        "api",
        "rest",
        "graphql",
        "endpoint",
        "swagger",
        "openapi",
        "контракт",
        "метод",
    ),
    "ui": (
        "ui",
        "интерфейс",
        "экран",
        "кнопк",
        "виджет",
        "верстк",
        "вёрстк",
        "страниц",
        "форм",
        "модал",
    ),
    "front": (
        "frontend",
        "front",
        "react",
        "typescript",
        "javascript",
        "браузер",
        "верстк",
        "вёрстк",
    ),
    "back": (
        "backend",
        "back",
        "сервис",
        "микросервис",
        "handler",
        "контроллер",
        "java",
        "python",
        "ruby",
    ),
    "etl": (
        "etl",
        "dwh",
        "выгрузк",
        "загрузк",
        "пайплайн",
        "витрин",
        "отчет",
        "отчёт",
        "агрегац",
        "синхронизац",
    ),
    "auth": (
        "auth",
        "авторизац",
        "аутентификац",
        "токен",
        "доступ",
        "sso",
        "логин",
        "роль",
    ),
    "payments": (
        "платеж",
        "платёж",
        "оплат",
        "pricing",
        "биллинг",
        "эквайринг",
        "деньг",
        "цен",
    ),
    "orders": (
        "заказ",
        "корзин",
        "оформлен",
        "доставк",
        "слот",
        "отгруз",
    ),
    "tickets": (
        "тикет",
        "обращен",
        "заявк",
        "орп",
        "орк",
        "поддержк",
        "инцидент",
    ),
    "erm": ("ерм", "erm", "мерчант", "лкм"),
    "infra": (
        "infra",
        "kubernetes",
        "docker",
        "деплой",
        "helm",
        "мониторинг",
        "алерт",
        "grafana",
        "prometheus",
    ),
    "db": (
        "бд",
        "база данных",
        "sql",
        "миграц",
        "схем",
        "таблиц",
        "postgres",
        "индекс",
    ),
    "mobile": ("mobile", "мобил", "ios", "android", "приложени"),
}

# Алиасы секций — те же, что `check.DEFAULT_SECTIONS` для этих групп. Держим
# здесь, чтобы анализ не зависел от каталога правил (иначе цикл импорта:
# `check` импортирует `analysis`).
ACCEPTANCE_ALIASES = (
    "acceptance_criteria",
    "acceptance",
    "ac",
    "критерии приемки",
    "критерии приёмки",
)
SCENARIO_ALIASES = ("scenarios", "сценарии", "сценарии / альтернативные сценарии")
STEPS_ALIASES = ("шаги", "шаг", "как воспроизвести", "воспроизведение", "steps")
EXPECTED_ALIASES = ("expected_result", "ожидаемый результат", "ожидаем")
ACTUAL_ALIASES = ("actual_result", "фактический результат", "фактическ")

# «Объём работ» — раздел, где зафиксировано, что надо сделать. Формулировки
# взяты из корпуса 223 задач (`.task-readiness/analysis/corpus-patterns.md`
# §5.1): «Задача» 27 задач, «Решение» 7, «Необходимо» 5, «Тех.решение» 5.
# Английские синонимы — канонические имена ключей `sections{}`, которые агент
# пишет в `context.json` (`task`, `solution`).
#
# Список продублирован в `check.DEFAULT_SECTIONS["work_scope"]`: `check`
# импортирует `analysis`, обратный импорт дал бы цикл, поэтому две копии
# синхронны вручную (расхождение ловит `trr selftest`).
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

# «Цель» не участвует в определении intent-а: строка `*Цель:*` часто общая для
# всего эпика (boilerplate) и даёт одинаковый ложный сигнал всем его задачам
# (в корпусе — эпик «Отказ от Elastic», 4 ложных `data_migration`).
GOAL_ALIASES = ("цель", "цель задачи", "goal")

# Осмысленность блока объёма работ: «Сделать» — не объём работ.
MIN_WORK_SCOPE_CHARS = 20

# Маркер долженствования + глагол действия в одной строке — самый широкий
# дешёвый сигнал «что надо сделать» (94 задачи корпуса, 42.2 %).
_WORK_MARKER_RE = re.compile(
    r"(?i)\b(необходимо|нужно|требуется|следует|надо)\b"
)
_WORK_VERB_RE = re.compile(
    r"(?i)(реализовать|добавить|настроить|вынести|перенести|покрыть|обновить|"
    r"удалить|исправить|развернуть|создать|доработать|отобразить|выгрузить|"
    r"завести|провести|подготовить|актуализировать|поддержать|написать)"
)

# Человекочитаемые подписи intent-ов: одна ось смысла, отдельная от метрик.
INTENT_LABELS = {
    "schema_migration": "миграция структуры БД",
    "data_migration": "перенос данных",
    "data_export": "выгрузка данных",
    "dashboard": "дашборд/графики",
    "integration": "интеграция/контракт",
    "refactor": "рефакторинг/перенос кода",
    "test_coverage": "тесты/покрытие",
    "research": "исследование/проработка",
}

# Каталог intent-ов (`.task-readiness/analysis/corpus-patterns.md` §5.3).
#
# Три набора признаков у каждого: `summary` — сильные признаки заголовка,
# `text` — сильные признаки текста, `weak` — слабые (только текст), `anti` —
# анти-признаки. Анти-признак гасит совпадение **в той же строке**: «схема
# обработки тикета» — бизнес-схема, а не схема БД.
#
# Порядок в кортеже = приоритет при равном весе: специфичные виды работ раньше
# широких (`integration` — самый широкий, 74 задачи корпуса).
INTENT_CATALOG = (
    {
        "intent": "schema_migration",
        "summary": (
            r"миграц\w*\s*(таблиц|схем|структур|бд|cassandra|postgres\w*|mysql|oracle|clickhouse)",
            r"\bddl\b",
            r"изменени\w*\s+структур\w*\s+(бд|таблиц)",
        ),
        "text": (
            r"миграц\w*\s*(таблиц|схем|структур|бд|cassandra|postgres\w*|mysql|oracle|clickhouse)",
            r"alter\s+table|create\s+table|drop\s+table",
            r"\bddl\b",
            r"внести\s+в\s+миграц|скрипт\w*\s+миграц",
            r"изменение\s+структуры",
        ),
        "weak": (
            r"primary\s+key|foreign\s+key|partition\s+key",
            r"(созда|добав|измен|удал)\w*\s+(таблиц|колонк|столбц)",
        ),
        "anti": (
            r"схем\w*\s+обработк",
            r"миграц\w*\s+(на|в)\s+[^\n]{0,30}(endpoint|keycloa|kafka|топик|площадк)",
        ),
    },
    {
        "intent": "data_migration",
        "summary": (
            r"(загруз|выгруз|перенос|перенес|наполнени|бэкфилл|backfill)\w*[^\n]{0,40}\bданн",
            r"\binsert\s+into\b",
            r"одноразов\w*\s+(загруз|перенос)|первичн\w*\s+загруз",
            r"перенести\s+данн",
        ),
        "text": (
            r"(загруз|выгруз|перенос|перенес|наполнени|бэкфилл|backfill)\w*[^\n]{0,40}\bданн",
            r"\binsert\s+into\b",
            r"одноразов\w*\s+(загруз|перенос)|первичн\w*\s+загруз",
            r"перенести\s+данн",
        ),
        "weak": (
            r"наполня\w*",
            r"наполнени\w*\s+(справочник|данн)",
            r"данн\w*\s+из\s+\S+\s+в\s+\S+",
        ),
        "anti": (
            r"миграц\w*\s+(таблиц|схем|структур)",
            r"\bddl\b|alter\s+table",
            r"состояни\w*\(?\s*загрузк",
            r"виджет\w*[^\n]{0,20}загрузк",
        ),
    },
    {
        "intent": "data_export",
        "summary": (r"\b(выгрузк|экспорт|export|скачиван)\w*",),
        "text": (r"\b(выгрузк|экспорт|export|скачиван)\w*",),
        "weak": (r"\.csv|\.xlsx|\bexcel\b|отчёт\w*\s+(файл|таблиц)",),
        "anti": (r"выгрузк\w*\s+(данн|запис)\w*\s+в\s+(бд|хранилищ)",),
    },
    {
        "intent": "dashboard",
        "summary": (r"\b(дашборд|dashboard|график\w*|панел\w*\s+график)\b",),
        "text": (r"\b(дашборд|dashboard|график\w*|панел\w*\s+график)\b",),
        "weak": (r"grafana|prometheus|метрик\w*|визуализац",),
        "anti": (r"график\w*\s+(работ|отпуск|смен)",),
    },
    {
        "intent": "test_coverage",
        "summary": (
            r"\b(автотест\w*|тест-кейс\w*|покрыт\w*\s+тест\w*|написать\s+тест\w*|"
            r"сгенерировать\s+тест\w*|qa)\b",
        ),
        "text": (
            r"\b(автотест\w*|тест-кейс\w*|покрыт\w*\s+тест\w*|написать\s+тест\w*|"
            r"сгенерировать\s+тест\w*|qa)\b",
        ),
        "weak": (r"\bтест\w*|junit|pytest|jest|playwright|selenium",),
        "anti": (r"тестирован\w*\s+ба|тест\w*\s+на\s+стенд",),
    },
    {
        "intent": "research",
        "summary": (
            r"\b(исследова\w*|проработк\w*|аудит\w*|инвентаризац\w*|анализ\w*|"
            r"разобраться|выяснить|понять)\b",
        ),
        "text": (
            r"\b(исследова\w*|проработк\w*|аудит\w*|инвентаризац\w*|анализ\w*|"
            r"разобраться|выяснить|понять)\b",
        ),
        "weak": (r"проанализир\w*|оценить\s+(возможност|вариант)|вариант\w*\s+решени",),
        "anti": (r"анализ\w*\s+(данн|лог)",),
    },
    {
        "intent": "refactor",
        "summary": (
            r"\b(перенос|перенес|вынос|вынести|рефактор\w*|распил|отказ\s+от|"
            r"переимен\w*)\w*",
        ),
        "text": (
            r"\b(перенос|перенес|вынос|вынести|рефактор\w*|распил|отказ\s+от|"
            r"переимен\w*)\w*",
        ),
        "weak": (
            r"аналогичн\w+\s+логик|логика\s+работы\s+которой\s+повторяет|в\s+\S+\s+вместо",
        ),
        # `перенос` — false friend корпуса: 14 задач переносят код/ручку, а не
        # данные. Перенос данных ловит `data_migration`.
        "anti": (r"перенос\w*\s+(данн|запис)",),
    },
    {
        "intent": "integration",
        "summary": (r"\b(интеграц\w*|endpoint|ручк\w*|контракт\w*|api)\b",),
        "text": (r"\b(интеграц\w*|endpoint|ручк\w*|контракт\w*|api)\b",),
        "weak": (r"/v\d+/|\bgrpc\b|\bkafka\b|\bтопик\w*|проксирован|sam-adapter",),
        "anti": (r"интеграц\w*\s+тест",),
    },
)

# Вес совпадения: заголовок весит больше текста, сильный признак — слабого.
_INTENT_WEIGHTS = {
    ("summary", "strong"): 3.0,
    ("text", "strong"): 2.0,
    ("text", "weak"): 1.0,
}
_INTENT_PRIORITY = {
    entry["intent"]: index for index, entry in enumerate(INTENT_CATALOG)
}


# Регулярные выражения.
_NUMBER_RE = re.compile(r"(?<![\w-])\d+(?:[.,]\d+)?(?![\w-])")
_DATE_RE = re.compile(
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*"
)
_WORD_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]+")
_NUMBERED_STEP_RE = re.compile(r"(?m)^\s*\d+[.)]\s+\S")
_STEP_HEADING_RE = re.compile(r"(?im)^\s*(?:h[1-6]\.\s*|#{1,6}\s*|\*{0,2})шаг\w*")
_CONCRETE_RE = re.compile(
    r"(?i)\b(?:post|get|put|patch|delete)\s+/|\bhttps?://"
    r"|\b(?:экран|виджет|метод|сервис|ручк|кнопк|страниц|модул|таблиц|поле|форм)\w*"
    r"|\b[a-zа-яё][a-zа-яё0-9]+_[a-zа-яё0-9_]+\b"
)
_TITLE_RE = re.compile(r"^([А-ЯЁA-Z][^:]{2,60}):\s*(.*)$")


# ---------------------------------------------------------------------------
# Разбор снимка задачи
# ---------------------------------------------------------------------------


def _text(value):
    """Строка из JSON-значения; списки/словари склеиваются, мусор → ''."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(_text(item) for item in value)
    if isinstance(value, dict):
        return "\n".join("%s: %s" % (key, _text(item)) for key, item in sorted(value.items()))
    return str(value)


def _field(context, name):
    """Поле снимка: верхний уровень приоритетнее `fields` (контракт §5.4)."""
    if not isinstance(context, dict):
        return None
    value = context.get(name)
    if value not in (None, ""):
        return value
    fields = context.get("fields")
    if isinstance(fields, dict):
        value = fields.get(name)
        if value not in (None, ""):
            return value
    return None


def _description(context):
    return _text(_field(context, "description"))


def _summary(context):
    return _text(_field(context, "summary"))


def _sections(context):
    """Секции снимка: нормализованный заголовок → текст."""
    raw = context.get("sections") if isinstance(context, dict) else None
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key, value in raw.items():
        text = _text(value).strip()
        if text:
            result[_normalize(key)] = text
    return result


def _normalize(text):
    value = str(text).strip().strip("*_").strip()
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()
    value = value.strip(":：.").strip()
    value = value.replace("ё", "е").replace("Ё", "Е")
    value = re.sub(r"\s+", " ", value)
    return value.casefold()


def _heading_parts(line):
    """(заголовок, текст-на-строке) для Jira/Markdown-разметки.

    Понимает `h3. Заголовок`, `### Заголовок`, `**Жирный**`, `*Курсив:*`,
    `{*}Жирный курсив{*}` и «мягкий» заголовок `Заголовок: значение`.
    """
    raw = line.strip()
    if not raw:
        return None
    for pattern in (
        r"^h[1-6]\.\s*(.+)$",
        r"^#{1,6}\s*(.+)$",
    ):
        match = re.match(pattern, raw, re.IGNORECASE)
        if match:
            return _normalize(match.group(1)), ""
    match = re.match(r"^\*\*(.+?)\*\*\s*:?\s*(.*)$", raw)
    if match:
        return _normalize(match.group(1)), match.group(2).strip()
    match = re.match(r"^\{\*\}(.{2,80}?)\{\*\}(.*)$", raw)
    if match:
        return _normalize(match.group(1)), match.group(2).lstrip(":").strip()
    match = re.match(r"^\*([^*]{2,60})\*\s*:?\s*(.*)$", raw)
    if match:
        return _normalize(match.group(1)), match.group(2).strip()
    match = _TITLE_RE.match(raw)
    if match:
        return _normalize(match.group(1)), match.group(2).strip()
    return None


def _find_block_with_title(text, aliases):
    """(заголовок как в тексте, содержимое) первого блока из `aliases`.

    В отличие от `_find_block`, возвращает исходный (ненормализованный)
    заголовок: сообщение проверки называет раздел так, как он назван в задаче
    («раздел «Решение»»), а не в casefold-виде.
    """
    if not text:
        return "", ""
    wanted = [_normalize(alias) for alias in aliases]
    title = None
    raw_title = ""
    inline = ""
    buffer = []
    for line in text.splitlines():
        parts = _heading_parts(line)
        if parts is not None:
            if title is not None and _alias_match(title, wanted):
                candidate = "\n".join([inline] + buffer).strip()
                if candidate:
                    return raw_title, candidate
            title, inline = parts
            raw_title = _heading_raw_title(line)
            buffer = []
            continue
        if title is not None:
            buffer.append(line)
    if title is not None and _alias_match(title, wanted):
        candidate = "\n".join([inline] + buffer).strip()
        if candidate:
            return raw_title, candidate
    return "", ""


def _heading_raw_title(line):
    """Заголовок строки «как написан» — без разметки, но с регистром задачи."""
    raw = line.strip()
    for pattern in (
        r"^h[1-6]\.\s*(.+)$",
        r"^#{1,6}\s*(.+)$",
    ):
        match = re.match(pattern, raw, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    for pattern in (
        r"^\*\*(.+?)\*\*\s*:?\s*(.*)$",
        r"^\{\*\}(.{2,80}?)\{\*\}(.*)$",
        r"^\*([^*]{2,60})\*\s*:?\s*(.*)$",
        r"^([^:]{1,80}):\s*(.*)$",
    ):
        match = re.match(pattern, raw)
        if match:
            return match.group(1).strip().strip("*_").strip().rstrip(":").strip()
    return raw


def _first_line(content, limit=120):
    """Первая содержательная строка блока — цитата для сообщения/отчёта.

    Предпочитается строка не короче 20 символов: «Требуется» само по себе
    ничего не говорит, а следующая строка блока — говорит.
    """
    fallback = ""
    for line in (content or "").splitlines():
        text = line.strip().strip("*_ ").strip()
        if not text:
            continue
        if not fallback:
            fallback = text
        if len(text) >= 20:
            return text[:limit]
    return fallback[:limit]


def _section_with_title(context, aliases):
    """(содержимое, подпись раздела) по `sections{}` или заголовкам описания.

    Подпись — исходный заголовок задачи (`Решение`, `solution`): по ней
    сообщение проверки говорит, какой именно раздел дал основание.
    """
    normalized = [_normalize(alias) for alias in aliases]
    for key, value in _sections(context).items():
        if _alias_match(key, normalized):
            return value, key
    title, content = _find_block_with_title(_description(context), aliases)
    return content, title



def _find_block(text, aliases):
    """Содержимое блока описания по заголовку из `aliases` (пусто — не нашли).

    Понимает разметку Jira (`h3.`), Markdown (`###`, `**Жирный**`) и «мягкие»
    заголовки `Заголовок: значение`. Границы блока — следующий заголовок.
    """
    if not text:
        return ""
    wanted = [_normalize(alias) for alias in aliases]
    title = None
    inline = ""
    buffer = []
    found = ""
    for line in text.splitlines():
        parts = _heading_parts(line)
        if parts is not None:
            if title is not None and _alias_match(title, wanted):
                candidate = "\n".join([inline] + buffer).strip()
                if candidate:
                    found = candidate
                    break
            title, inline = parts
            buffer = []
            continue
        if title is not None:
            buffer.append(line)
    if not found and title is not None and _alias_match(title, wanted):
        found = "\n".join([inline] + buffer).strip()
    return found


def _alias_match(title, wanted):
    for alias in wanted:
        if title == alias:
            return True
        if len(alias) >= 4 and title.startswith(alias):
            return True
    return False


def _section_text(context, aliases):
    """Секция из `context.sections`, иначе — блок в описании."""
    normalized = [_normalize(alias) for alias in aliases]
    for key, value in _sections(context).items():
        if _alias_match(key, normalized):
            return value
    return _find_block(_description(context), aliases)


def _task_text(context):
    """Текст задачи: описание + секции + заголовок (без `_meta` снимка)."""
    parts = [_summary(context), _description(context)]
    sections = _sections(context)
    for key in sorted(sections):
        parts.append(sections[key])
    return "\n".join(part for part in parts if part).strip()


def _words(text):
    return _WORD_RE.findall((text or "").casefold())


def _hits(text, markers):
    """Суммарное число вхождений маркеров (casefold, `ё` → `е`)."""
    lowered = (text or "").casefold().replace("ё", "е")
    return sum(lowered.count(marker) for marker in markers)


def _area_hits(text, keywords):
    """Вхождения ключевых слов области: короткие латинские — по границе слова."""
    lowered = (text or "").casefold().replace("ё", "е")
    total = 0
    for keyword in keywords:
        if keyword.isascii() and len(keyword) <= 3:
            total += len(
                re.findall(r"\b%s\b" % re.escape(keyword), lowered)
            )
        else:
            total += lowered.count(keyword)
    return total


def _clamp01(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number) or number <= 0.0:
        return 0.0
    if number >= 1.0:
        return 1.0
    return number


def _ratio(count, cap):
    if count <= 0:
        return 0.0
    return _clamp01(float(count) / float(cap))


# ---------------------------------------------------------------------------
# Метрики
# ---------------------------------------------------------------------------


# Измеримый признак: число, порог, процент, срок, долженствование.
_MEASURABLE_RE = re.compile(
    r"\d|не более|не менее|>=|<=|должен|должна|должно|увелич|сниж|"
    r"секунд|\bмс\b|%|\bшт\b|\bраз\b"
)

# Наблюдаемое поведение в нормальном состоянии — второй способ быть измеримым
# критерием: «автоматизация не срабатывает», «дата не перезаписывается»,
# «виджет отображается». Терминология команд разная, требование одно: по
# критерию понятно, как система должна работать.
_BEHAVIOUR_RE = re.compile(
    r"не\s+срабатыва|не\s+перезаписыва|перезаписыва|отобража|возвраща|"
    r"формиру|создава|сохраня|работает|работать|остается|остаётся|"
    r"становится|доступн|успешно|без\s+ошиб|ошиб|корректн|как\s+ожида"
)

# Минимальная длина осмысленного критерия: одно слово («работает») критерием
# не является. 15 символов не отсекают нормальные короткие формулировки
# («Ошибок в логе нет» — 17).
MIN_CRITERION_CHARS = 15

# Критерий-«результат работ»: критерий фиксирует не наблюдаемое поведение
# системы, а созданный/изменённый артефакт («подготовлены тест-кейсы»,
# «проведено ревью», «настроен алерт»). Для задач на тест-аналитику, документацию
# и инфраструктуру это нормальная и полная формулировка готовности — требовать
# от неё «система ведёт себя так-то» значит требовать несуществующего объёма.
#
# Глаголы — основы (покрывают «подготовлены», «проведено», «настроен» и т.д.);
# существительные — артефакты работ. Совпадение должно быть и по глаголу, и по
# существительному: «подготовлены» без артефакта — не результат работ.
DELIVERABLE_VERBS = (
    "созда",
    "подготов",
    "провед",
    "настро",
    "напис",
    "покры",
    "задокументир",
    "согласов",
    "внедр",
    "исправ",
    "удал",
    "переимен",
    "обнов",
)

DELIVERABLE_NOUNS = (
    "тест-кейс",
    "тест кейс",
    "тесткейс",
    "автотест",
    "ревью",
    "документац",
    "алерт",
    "дашборд",
    "скрипт",
    "миграц",
    "инструкц",
    "чек-лист",
    "чек лист",
    "чеклист",
)


def _deliverable_line(lowered):
    """Строка фиксирует результат работ: глагол действия + артефакт."""
    has_verb = any(verb in lowered for verb in DELIVERABLE_VERBS)
    if not has_verb:
        return False
    return any(noun in lowered for noun in DELIVERABLE_NOUNS)


def deliverable_criteria(content):
    """Строки критериев, которые фиксируют **результат работ**.

    Единственная реализация правила «критерий описывает результат работ»: её
    импортирует `check.py` (`SA-08`). Порог осмысленности — тот же, что у
    `measurable_criteria` (`MIN_CRITERION_CHARS`): «ревью» само по себе
    критерием не является, «Проведено ревью тест-кейсов» — является.
    """
    lines = [line.strip(" \t*#-•>") for line in (content or "").splitlines()]
    deliverable = []
    for line in lines:
        if not line:
            continue
        # `ё` → `е` и `-` → пробел: «тест-кейс» и «тест кейс» — один артефакт.
        lowered = line.casefold().replace("ё", "е")
        if len(lowered) < MIN_CRITERION_CHARS:
            continue
        if _deliverable_line(lowered):
            deliverable.append(line)
    return deliverable


def measurable_criteria(content):
    """Строки критериев, в которых есть измеримый признак.

    Единственная реализация правила «критерий измерим»: число, порог, процент,
    срок, наблюдаемое долженствование **или** описание наблюдаемого поведения
    в нормальном состоянии. Её импортирует `check.py` — дубликата в движке
    проверок нет (иначе две реализации разъедутся).

    Обрезка префиксов списка/заголовка (`#`, `>`, `•`, `*`, `-`) — та же, что в
    `deliverable_criteria`: иначе `## Проведено ревью` было бы результатом работ,
    но не измеримым критерием, и счётчики в сообщении `SA-08` разъезжались.
    """
    lines = [line.strip(" \t*#-•>") for line in (content or "").splitlines()]
    measurable = []
    for line in lines:
        if not line:
            continue
        lowered = line.casefold()
        if len(lowered) < MIN_CRITERION_CHARS:
            continue
        if _MEASURABLE_RE.search(lowered) or _BEHAVIOUR_RE.search(lowered):
            measurable.append(line)
    return measurable


def work_scope(context):
    """(содержимое, источник, цитата) блока «что надо сделать».

    Два источника по приоритету:

    1. раздел из `WORK_SCOPE_ALIASES` — `sections{}` снимка или заголовок
       описания («Задача», «Решение», «Необходимо», «Тех.решение», …);
    2. строка описания, где маркер долженствования («необходимо», «нужно»,
       «требуется», «следует», «надо») стоит рядом с глаголом действия.

    Пустой/короткий (< `MIN_WORK_SCOPE_CHARS`) блок основанием не считается:
    «Сделать» — не объём работ.

    Возвращает `(None, None, None)`, если объёма работ в задаче нет.
    """
    content, title = _section_with_title(context, WORK_SCOPE_ALIASES)
    content = (content or "").strip()
    if len(content) >= MIN_WORK_SCOPE_CHARS:
        label = (title or "объём работ").strip()
        if label:
            label = label[:1].upper() + label[1:]
        return content, "раздел «%s»" % label, _first_line(content)

    for line in _description(context).splitlines():
        text = line.strip().strip("*_ ").strip()
        if len(text) < MIN_WORK_SCOPE_CHARS:
            continue
        lowered = text.casefold().replace("ё", "е")
        if _WORK_MARKER_RE.search(lowered) and _WORK_VERB_RE.search(lowered):
            return text, "описание задачи", text[:120]
    return None, None, None


def intent_label(intent):
    """Человекочитаемая подпись intent-а (`data_migration` → «перенос данных»)."""
    return INTENT_LABELS.get(str(intent or "").strip(), str(intent or "").strip())


def _without_goal(text):
    """Описание без блоков «Цель»/«Goal»: boilerplate эпика не даёт intent-а."""
    wanted = [_normalize(alias) for alias in GOAL_ALIASES]
    kept = []
    skip = False
    for line in (text or "").splitlines():
        parts = _heading_parts(line)
        if parts is not None:
            skip = _alias_match(parts[0], wanted)
        if not skip:
            kept.append(line)
    return "\n".join(kept)


def _intent_sources(context):
    """[(подпись источника, текст)] в порядке приоритета: заголовок, описание, секции."""
    sources = []
    summary = _summary(context).strip()
    if summary:
        sources.append(("summary", summary))
    description = _without_goal(_description(context)).strip()
    if description:
        sources.append(("description", description))
    goal_aliases = [_normalize(alias) for alias in GOAL_ALIASES]
    for key, value in _sections(context).items():
        if _alias_match(key, goal_aliases):
            continue
        sources.append(("sections.%s" % key, value))
    return sources


def _intent_match(entry, source_kind, text):
    """(цитата, вес) первого совпадения признаков intent-а в тексте, иначе None.

    Строки проверяются по одной: анти-признак гасит совпадение только в своей
    строке, поэтому «схема обработки тикета» не отменяет «миграцию таблиц» из
    другой строки. Заголовок — одна строка.
    """
    strong = entry["summary"] if source_kind == "summary" else entry["text"]
    weak = () if source_kind == "summary" else entry.get("weak") or ()
    anti = entry.get("anti") or ()
    for line in (text or "").splitlines():
        candidate = line.strip().strip("*_ ").strip()
        if len(candidate) < 8:
            continue
        lowered = candidate.casefold().replace("ё", "е")
        if any(re.search(pattern, lowered) for pattern in anti):
            continue
        for pattern in strong:
            if re.search(pattern, lowered):
                return candidate, _INTENT_WEIGHTS[(source_kind, "strong")]
        for pattern in weak:
            if re.search(pattern, lowered):
                return candidate, _INTENT_WEIGHTS[("text", "weak")]
    return None


# Признаки домена «БД/данные» в заголовке. Если заголовок называет домен, сигнал
# миграции подтверждён и весит как заголовочный: «Проработка БД сервиса» +
# «описать задачи по миграции БД» — это проработка миграции, а не проработка
# вообще. Без подтверждения домена сигнал остаётся средним: «Исследовать
# проблему пропусков» + «бэкфилл для пропущенных данных» — сначала
# исследование, бэкфилл вторичен.
_INTENT_DOMAIN_RE = re.compile(
    r"(?i)(\bбд\b|база\s+данных|таблиц|схем|cassandra|postgres|clickhouse|mysql|elastic|данн)"
)
_DB_INTENTS = frozenset({"schema_migration", "data_migration"})


def work_intent(context):
    """Что делается по задаче: заголовок и текст в совокупности.

    Возвращает список `{intent, confidence, evidence, source}`, отсортированный
    по силе сигнала (заголовок важнее текста, сильный признак — слабого), затем
    по приоритету каталога, затем по имени. Детерминированно, без времени.

    Ось отдельная от метрик и **не влияет на числа оценки**: она нужна, чтобы
    отчёт и комментарий говорили «понято как перенос данных», а не заставляли
    читателя угадывать по заголовку.

    Различение миграций — главный кейс: «реализовать миграцию **данных**»
    (перенос строк: `insert into`, «загрузить», «наполнить») ≠ «реализовать
    **миграции**» (DDL: `alter table`, «создать схемы», `PRIMARY KEY`).
    Анти-признаки (`схема обработки`, `состояние загрузки`, «миграция на новый
    endpoint/keycloak/kafka», `перенос` без `данн`) гасят ложные срабатывания.
    """
    if not isinstance(context, dict):
        return []
    sources = _intent_sources(context)
    if not sources:
        return []

    best = {}
    for entry in INTENT_CATALOG:
        for label, text in sources:
            source_kind = "summary" if label == "summary" else "text"
            match = _intent_match(entry, source_kind, text)
            if match is None:
                continue
            quote, weight = match
            current = best.get(entry["intent"])
            if current is None or weight > current["weight"]:
                best[entry["intent"]] = {
                    "weight": weight,
                    "evidence": quote[:120],
                    "source": label,
                }
            break

    result = []
    summary_confirms_db = bool(_INTENT_DOMAIN_RE.search(_summary(context).casefold()))
    for intent, item in best.items():
        weight = item["weight"]
        if summary_confirms_db and intent in _DB_INTENTS:
            weight = max(weight, _INTENT_WEIGHTS[("summary", "strong")])
        if weight >= 3.0:
            confidence = "high"
        elif weight >= 2.0:
            confidence = "medium"
        else:
            confidence = "low"
        result.append(
            {
                "intent": intent,
                "confidence": confidence,
                "evidence": item["evidence"],
                "source": item["source"],
                "_weight": weight,
            }
        )
    result.sort(
        key=lambda item: (
            -item["_weight"],
            _INTENT_PRIORITY.get(item["intent"], 99),
            item["intent"],
        )
    )
    for item in result:
        item.pop("_weight", None)
    return result


# «Заголовок с действием»: инфинитив действия. Именно форма инфинитива, а не
# основа: «Создание тикета» и «Поддержка продукта» — тема, а не действие;
# «Создать тикет» и «Поддержать продукт» — действие. Нужен SA-08 как последнее
# основание: что делать названо, пусть и верхнеуровнево.
ACTION_INFINITIVES = (
    "добавить",
    "убрать",
    "изменить",
    "обновить",
    "исправить",
    "удалить",
    "создать",
    "реализовать",
    "доработать",
    "настроить",
    "вынести",
    "перенести",
    "проверить",
    "провести",
    "подготовить",
    "актуализировать",
    "поддержать",
    "написать",
    "покрыть",
    "выгрузить",
    "загрузить",
    "отобразить",
    "развернуть",
    "описать",
    "исследовать",
    "проанализировать",
    "сделать",
    "завести",
    "отключить",
    "включить",
    "заменить",
    "расширить",
    "вывести",
    "собрать",
    "сверить",
    "рассчитать",
    "найти",
    "починить",
    "согласовать",
    "автоматизировать",
    "ускорить",
    "сократить",
    "переписать",
    "подключить",
    "оптимизировать",
    "внедрить",
    "проработать",
    "оценить",
    "уточнить",
    "разобраться",
    "выяснить",
    "понять",
    "переименовать",
    "сформировать",
    "сгенерировать",
    "наполнить",
)


def explicit_action(text):
    """Названо ли действие инфинитивом («Убрать лот доставки», «Создать тикет»).

    Отличается от `_action_score` намеренно: там основа слова (для оценки
    понятности «Создание тикета» тоже сигнал), здесь — только инфинитив, потому
    что SA-08 признаёт заголовок основанием готовности лишь тогда, когда в нём
    названо действие, а не тема.
    """
    lowered = (text or "").casefold().replace("ё", "е")
    return any(
        re.search(r"\b%s\b" % re.escape(word), lowered) for word in ACTION_INFINITIVES
    )


def _clarity(context):
    """Понятность: длина, размытость, действие+объект, конкретика, дубль заголовка."""
    description = _description(context).strip()
    sections = _sections(context)
    body = description
    if len(body) < 40:
        # Описание в Jira часто разложено агентом по секциям: пустое поле
        # «Описание» при заполненных секциях — не «непонятная задача».
        body = "\n".join(
            [description] + [sections[key] for key in sorted(sections)]
        ).strip()

    evidence, notes = [], []
    chars = len(body)
    words = _words(body)
    word_count = len(words)

    length_score = 0.0
    if chars > 0:
        length_score = _clamp01(
            math.log1p(chars) / math.log1p(_CLARITY_LENGTH_CAP)
        )
        evidence.append("длина текста: %d символов → %.2f" % (chars, length_score))

    vague_hits = _hits(body, VAGUE_MARKERS)
    vagueness = 0.0
    if chars > 0:
        vagueness = 1.0 - _clamp01(
            vague_hits / max(1.0, word_count / _WORD_CAP_FOR_VAGUE)
        )
        evidence.append("размытых слов: %d → %.2f" % (vague_hits, vagueness))
    if vague_hits:
        notes.append("размытые формулировки: %d" % vague_hits)

    action = _action_score(body)
    if chars > 0:
        evidence.append("действие+объект: %.2f" % action)

    numbers = len(_NUMBER_RE.findall(body))
    dates = len(_DATE_RE.findall(body))
    systems = _hits(body, SYSTEM_MARKERS)
    specificity = _clamp01(
        0.5 * (1.0 if numbers + dates > 0 else 0.0)
        + 0.5 * (1.0 if systems > 0 else 0.0)
    )
    if chars > 0:
        evidence.append(
            "конкретика: числа %d, даты %d, системы %d → %.2f"
            % (numbers, dates, systems, specificity)
        )

    summary = _summary(context).strip().casefold()
    duplicate = bool(summary and len(summary) >= 10 and summary in body.casefold())
    if duplicate:
        notes.append("заголовок дословно повторяется в описании")
        evidence.append("заголовок дублируется в описании → ×0.95")

    score = (
        0.35 * length_score
        + 0.25 * vagueness
        + 0.20 * action
        + 0.20 * specificity
    )
    if duplicate:
        score *= 0.95

    return {
        "score": round(_clamp01(score), 4),
        "evidence": evidence,
        "notes": notes,
        "chars": chars,
        "words": word_count,
        "vague": vague_hits,
        "numbers": numbers,
        "dates": dates,
        "systems": systems,
    }


def _action_score(text):
    """1.0 — глагол действия и объект после него; 0.5 — только глагол."""
    lowered = (text or "").casefold().replace("ё", "е")
    position = None
    for verb in ACTION_VERBS:
        index = lowered.find(verb)
        if index >= 0 and (position is None or index < position):
            position = index
    if position is None:
        return 0.0
    tail = _words(lowered[position:])
    for word in tail[1:]:
        if len(word) >= 4 and word not in STOPWORDS and not word.isdigit():
            return 1.0
    return 0.5


def _testability(context):
    """Измеримость: число измеримых критериев + ожидаемый/фактический результат."""
    content = _section_text(context, ACCEPTANCE_ALIASES)
    measurable = measurable_criteria(content)
    expected = _section_text(context, EXPECTED_ALIASES)
    actual = _section_text(context, ACTUAL_ALIASES)
    numbers = len(_NUMBER_RE.findall(content))

    criteria_ratio = min(1.0, len(measurable) / 2.0)
    observable = 1.0 if (expected and actual) or numbers > 0 else 0.0
    score = _clamp01(0.75 * criteria_ratio + 0.25 * observable)

    evidence = []
    if content:
        evidence.append("измеримых критериев: %d" % len(measurable))
    if expected and actual:
        evidence.append("ожидаемый и фактический результат описаны")
    return {
        "score": round(score, 4),
        "evidence": evidence,
        "measurable_criteria": len(measurable),
        "expected_actual": bool(expected and actual),
    }


def _reproduction(context):
    """Воспроизводимость «Ошибки»: шаги, ожидаемый и фактический результат."""
    issue_type = _normalize(_text(_field(context, "issue_type")))
    applicable = issue_type in ("ошибка", "bug", "дефект", "incident", "инцидент")
    text = _task_text(context)
    block = _section_text(context, STEPS_ALIASES)

    numbered = len(_NUMBERED_STEP_RE.findall(block or text))
    block_lines = [
        line
        for line in (block or "").splitlines()
        if line.strip() and not line.strip().startswith("!")
    ]
    headings = len(_STEP_HEADING_RE.findall(text))
    steps = max(numbered, len(block_lines), headings if numbered == 0 else numbered)

    expected = _section_text(context, EXPECTED_ALIASES)
    actual = _section_text(context, ACTUAL_ALIASES)
    evidence = []
    if applicable:
        evidence.append("шагов воспроизведения: %d" % steps)
        if expected:
            evidence.append("ожидаемый результат описан")
        if actual:
            evidence.append("фактический результат описан")
    score = 0.0
    if applicable:
        score = _clamp01(
            0.50 * min(1.0, steps / 3.0)
            + 0.25 * (1.0 if expected else 0.0)
            + 0.25 * (1.0 if actual else 0.0)
        )
    return {
        "score": round(score, 4),
        "evidence": evidence,
        "steps": steps if applicable else 0,
        "applicable": applicable,
        "expected": bool(expected),
        "actual": bool(actual),
    }


def _components(context):
    """Число компонентов/сервисов и признак наличия поля."""
    fields = context.get("fields") if isinstance(context, dict) else None
    for holder in (context, fields):
        if not isinstance(holder, dict) or "components" not in holder:
            continue
        value = holder["components"]
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, (list, tuple, dict)):
            return len(value)
        if isinstance(value, str):
            return len([item for item in value.split(",") if item.strip()])
    return 0


def _scope(context):
    """Границы объёма: маркеры границ, компоненты, конкретные упоминания."""
    text = _task_text(context)
    bounds = 1.0 if _hits(text, BOUNDARY_MARKERS) else 0.0
    components = _components(context)
    mentions = len(_CONCRETE_RE.findall(text))
    score = _clamp01(
        0.45 * bounds
        + 0.30 * min(1.0, components / 2.0)
        + 0.25 * min(1.0, mentions / 3.0)
    )
    evidence = []
    if bounds:
        evidence.append("границы объёма описаны")
    if components:
        evidence.append("компонентов: %d" % components)
    if mentions:
        evidence.append("конкретных упоминаний: %d" % mentions)
    return {
        "score": round(score, 4),
        "evidence": evidence,
        "out_of_scope": bool(bounds),
        "components": components,
        "mentions": mentions,
    }


def _links(context):
    """Список связей из снимка (`links` / `issuelinks`, список или число)."""
    for name in ("links", "issuelinks"):
        value = _field(context, name)
        if value not in (None, ""):
            return value
    return None


def _link_type(entry):
    """Тип связи в терминах Jira: `blocks`, `is blocked by`, `relates`, `depends`."""
    if not isinstance(entry, dict):
        return "relates"
    raw = _normalize(_text(entry.get("type") or entry.get("link_type") or ""))
    direction = _normalize(_text(entry.get("direction")))
    if "block" in raw:
        if direction == "inward":
            return "is blocked by"
        return "blocks"
    if "depend" in raw or "зависит" in raw:
        return "depends"
    if "relat" in raw or "связ" in raw or "duplicate" in raw or "дубл" in raw:
        return "relates"
    return raw or "relates"


def _dependencies(context):
    """Связи и интеграции: число, типы, упоминания внешних систем."""
    links = _links(context)
    link_types = {}
    count = 0
    if isinstance(links, bool):
        links = None
    if isinstance(links, int):
        count = max(links, 0)
    elif isinstance(links, (list, tuple)):
        count = len(links)
        for entry in links:
            kind = _link_type(entry)
            link_types[kind] = link_types.get(kind, 0) + 1
    elif isinstance(links, dict):
        count = len(links)
        for entry in links.values():
            kind = _link_type(entry)
            link_types[kind] = link_types.get(kind, 0) + 1
    elif isinstance(links, str) and links.strip():
        count = len([item for item in links.split(",") if item.strip()])

    text = _task_text(context)
    integrations = len(re.findall(r"(?i)https?://", text))
    integrations += _hits(text, ("интеграц", "внешн", "провайдер", "webhook", "kafka", "grpc"))

    score = _clamp01(
        0.50 * min(1.0, len(link_types) / 2.0)
        + 0.30 * min(1.0, integrations / 2.0)
        + 0.20 * min(1.0, count / 3.0)
    )
    evidence = []
    if count:
        evidence.append("связей: %d" % count)
    if link_types:
        evidence.append(
            "типы связей: %s" % ", ".join(sorted(link_types))
        )
    if integrations:
        evidence.append("упоминаний интеграций: %d" % integrations)
    return {
        "score": round(score, 4),
        "evidence": evidence,
        "link_types": link_types,
        "links": count,
        "integrations": integrations,
    }


def _scenarios(context):
    """Сценарии: секция, нумерованные пункты, «сценарий/кейс», given/when/then."""
    section = _section_text(context, SCENARIO_ALIASES)
    text = section or ""
    count = len(_NUMBERED_STEP_RE.findall(text))
    count += _hits(text, SCENARIO_MARKERS)
    if section:
        # Заполненная секция без маркеров — один описанный сценарий
        # (например, «Смена параметра в решённом тикете» одной строкой).
        lines = len([line for line in section.splitlines() if line.strip()])
        count = max(count, lines)
    else:
        count = 0
        # Без секции сценариев считаем только явные «если … то» в описании:
        # нумерованный список работ — это не сценарии.
        description = _description(context).casefold()
        if re.search(r"(?s)если\s+[^.]{5,120}\s+то\b", description):
            count = 1
        count += len(re.findall(r"(?i)\bgiven\b.*?\bwhen\b.*?\bthen\b", description))
    evidence = []
    if count:
        evidence.append("сценариев: %d" % count)
    return {
        "count": count,
        "evidence": evidence,
        "source": "section" if section else ("description" if count else "none"),
    }


def _area(context):
    """Область/подсистема по словарю: components → labels → epic → summary → description."""
    sources = []
    components = _field(context, "components")
    if components not in (None, ""):
        sources.append(("components", _text(components)))
    labels = _field(context, "labels")
    if labels not in (None, ""):
        sources.append(("labels", _text(labels)))
    epic = _field(context, "epic")
    if epic not in (None, ""):
        sources.append(("epic", _text(epic)))
    summary = _summary(context)
    if summary:
        sources.append(("summary", summary))
    description = _description(context)
    if description:
        sources.append(("description", description))

    scores = {}
    for area_name in sorted(AREA_KEYWORDS):
        occurrences = 0
        matched_sources = 0
        for _name, text in sources:
            hits = _area_hits(text, AREA_KEYWORDS[area_name])
            if hits:
                occurrences += hits
                matched_sources += 1
        if occurrences:
            scores[area_name] = (occurrences, matched_sources)

    if not scores:
        return {"name": "", "confidence": 0.0, "evidence": []}

    # Максимум по (упоминания, число источников), при равенстве — по имени:
    # порядок детерминирован и не зависит от порядка ключей словаря.
    best = sorted(scores, key=lambda name: (-scores[name][0], -scores[name][1], name))[0]
    occurrences, matched_sources = scores[best]
    confidence = _clamp01(
        0.30 * matched_sources
        + 0.10 * min(occurrences, _AREA_CONFIDENCE_CAP)
    )
    return {
        "name": best,
        "confidence": round(confidence, 4),
        "evidence": [
            "область: %s (%d упоминаний в %d источниках)"
            % (best, occurrences, matched_sources)
        ],
    }


def _ambiguity(context):
    """Маркеры неопределённости, нормированные на длину текста."""
    text = _task_text(context)
    words = len(_words(text))
    markers = _hits(text, UNCERTAINTY_MARKERS) + text.count("?")
    ratio = (float(markers) / float(words)) if words else 0.0
    evidence = []
    if markers:
        evidence.append("маркеров неопределённости: %d (%.2f)" % (markers, ratio))
    return {
        "markers": markers,
        "ratio": round(ratio, 4),
        "evidence": evidence,
        "words": words,
    }


def _empty():
    """Пустой результат: ни одного сигнала, ничего не падает."""
    return {
        "clarity": {"score": 0.0, "evidence": [], "notes": []},
        "testability": {
            "score": 0.0,
            "evidence": [],
            "measurable_criteria": 0,
            "expected_actual": False,
        },
        "reproduction": {
            "score": 0.0,
            "evidence": [],
            "steps": 0,
            "applicable": False,
            "expected": False,
            "actual": False,
        },
        "scope": {
            "score": 0.0,
            "evidence": [],
            "out_of_scope": False,
            "components": 0,
            "mentions": 0,
        },
        "dependencies": {
            "score": 0.0,
            "evidence": [],
            "link_types": {},
            "links": 0,
            "integrations": 0,
        },
        "scenarios": {"count": 0, "evidence": [], "source": "none"},
        "area": {"name": "", "confidence": 0.0, "evidence": []},
        "ambiguity": {"markers": 0, "ratio": 0.0, "evidence": [], "words": 0},
        "signals": {
            "numbers": 0,
            "dates": 0,
            "systems": 0,
            "vague_ratio": 0.0,
            "words": 0,
            "chars": 0,
        },
    }


def analyze(context, cfg=None):
    """Содержательный анализ снимка задачи. Чистая функция, без побочных эффектов.

    `cfg` принимается для совместимости с остальными движками (конфиг может
    задать будущие пороги); сейчас анализ от конфига не зависит. Отсутствующие
    поля снимка дают нулевые сигналы, а не исключение: полигон гоняет снимки
    с `null` во всех полях.
    """
    del cfg  # пороги живут в правилах проверок, а не в анализе
    if not isinstance(context, dict):
        return _empty()
    try:
        clarity = _clarity(context)
        testability = _testability(context)
        reproduction = _reproduction(context)
        scope = _scope(context)
        dependencies = _dependencies(context)
        scenarios = _scenarios(context)
        area = _area(context)
        ambiguity = _ambiguity(context)
    except Exception as exc:  # noqa: BLE001 - анализ не имеет права ронять прогон
        result = _empty()
        result["clarity"]["notes"].append("анализ не выполнен: %s" % exc)
        return result

    text = _task_text(context)
    words = len(_words(text))
    return {
        "clarity": {
            "score": clarity["score"],
            "evidence": clarity["evidence"],
            "notes": clarity["notes"],
        },
        "testability": testability,
        "reproduction": reproduction,
        "scope": scope,
        "dependencies": dependencies,
        "scenarios": scenarios,
        "area": area,
        "ambiguity": ambiguity,
        "signals": {
            "numbers": clarity["numbers"],
            "dates": clarity["dates"],
            "systems": clarity["systems"],
            "vague_ratio": round(
                (float(clarity["vague"]) / float(words)) if words else 0.0, 4
            ),
            "words": words,
            "chars": clarity["chars"],
        },
    }

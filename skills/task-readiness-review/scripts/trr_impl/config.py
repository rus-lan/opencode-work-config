#!/usr/bin/env python3
"""Чтение, нормализация и валидация `task-readiness-review.yaml`.

Модуль намеренно ничего не знает про сеть и MCP: конфиг — это файл, который
агент заполняет, а Python только проверяет.

Секреты: в конфиге их быть не может. Проверка рекурсивная и смотрит на имя
ключа (а не на значение), потому что значение секрета мы не хотим даже
показывать в сообщении об ошибке.
"""

import copy
import hashlib
import os
import re
import sys
from pathlib import Path

from trr_impl import paths, resources as resourcesmod, schema_lite, yamlmini

__all__ = [
    "ARTIFACT_TARGETS",
    "CONFIG_FILENAME",
    "DEFAULTS",
    "DEMO_VALUES",
    "DEPRECATED_OVERRIDE_WARNING",
    "DEFAULT_TEMPLATE_URL",
    "NORMATIVE_SCALE",
    "ConfigError",
    "apply_defaults",
    "artifact_place_problem",
    "artifact_place_problems",
    "config_path",
    "config_sha256",
    "demo_warnings",
    "deprecated_warnings",
    "find_secrets",
    "is_demo_value",
    "load_config",
    "resolve_workdir",
    "skill_root",
    "validate_config",
]

CONFIG_FILENAME = "task-readiness-review.yaml"
ENV_ROOT = "TASK_READINESS_ROOT"
SKILL_NAME = "task-readiness-review"

# Устаревший путь ключа `override_template`: принимается, но предупреждает.
DEPRECATED_OVERRIDE_WARNING = (
    "[WARN] sources.override_template устарел — используйте override_template"
)

# scripts/trr_impl/config.py → scripts/trr_impl → scripts → корень скилла
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMAS_DIR = SKILL_ROOT / "schemas"
EXAMPLE_CONFIG = SKILL_ROOT / "task-readiness-review.example.yaml"

# Подстроки, которых достаточно для срабатывания (проверяются по ключу,
# очищенному от не-букв и приведённому к нижнему регистру).
_SECRET_SUBSTRINGS = (
    "token",
    "password",
    "passwd",
    "secret",
    "apikey",
    "credential",
    "privatekey",
)

# `pat` — отдельное слово, а не подстрока: иначе обычный ключ `path`
# (output.obsidian.path) ложно считался бы секретом.
_SECRET_WORDS = ("pat",)

# Эталонная (нормативная) шкала Story Points. Конфиг не может её переопределить —
# иначе калибровка и отчёт разойдутся с эталоном, на котором модель обучена.
NORMATIVE_SCALE = [1, 2, 3, 5, 8, 13, 21]

# Целевой шаблон описания задачи для компактных блоков отчёта («Что
# заполнить»). Дефолт — страница «T100 Описание задачи на разработку (DRAFT)».
# Значение переопределяется `validation.template_url`; пустая строка означает
# «печатать путь к `templates/task-description.md` вместо ссылки».
DEFAULT_TEMPLATE_URL = "https://space.samokat.ru/pages/viewpage.action?pageId=3882222857"

# Нижняя граница корпуса для векторизации: меньше — механизм отключается.
# Число не понижается конфигом: при 30 задачах две трети термов новой задачи
# корпус ещё не видел, ниже начинается «похожесть на шум».
VECTOR_MIN_CORPUS = 30

# Куда разрешено публиковать обученный бандл (`artifacts.export_target`).
# `none` — законный режим «не публиковать»: место тогда не требуется.
ARTIFACT_TARGETS = ("none", "local", "confluence", "gitlab", "obsidian")

# Значения из `task-readiness-review.example.yaml` (демо-проект). Это ДЕМО-данные:
# они не используются как дефолты, а `doctor` предупреждает, если проект остался
# на них. Список нужен только для предупреждения — ни одно значение отсюда не
# подставляется в конфиг.
DEMO_VALUES = frozenset(
    {
        "E001",
        "6662",
        "4278391451",
        "20367",
        "20693",
        "20694",
        "21143",
        "21144",
        "customfield_10004",
        "customfield_13819",
        "customfield_12750",
    }
)

# Командных значений в дефолтах нет: пустой проект, пустые id полей, никаких
# page_id/board_id/sprint_ids. Всё, что относится к конкретной команде, обязан
# заполнить пользователь (или агент на этапе init), иначе `doctor` блокируется.
DEFAULTS = {
    "skill": SKILL_NAME,
    "sources": {
        "reference": [],
        "sprints": [],
        "confluence": {"recursive": False, "max_depth": 1, "max_pages": 20},
    },
    "templates_dir": "templates",
    "override_template": None,
    "validation": {
        "with_dependencies": False,
        "min_sample_n": 5,
        "role_map": {},
        # Типы задач, для которых нужна оценка QA. Остальные типы (Задача,
        # Tech Debt, ADR, Релиз, Дизайн) проверку результата включают в объём
        # исполнителя — QA-записи в оценке нет.
        "qa_required_issue_types": [
            "Feature",
            "New Feature",
            "Фича",
            "Ошибка",
            "Bug",
            "Дефект",
        ],
        # Целевой шаблон описания задачи: ссылка в компактных блоках отчёта
        # («Что заполнить»). Пустая строка — печатать путь к
        # `templates/task-description.md` вместо ссылки.
        "template_url": DEFAULT_TEMPLATE_URL,
    },
    "estimation": {
        "scale": list(NORMATIVE_SCALE),
        "factor_clamp": [0.5, 2.0],
        # Три эвристических параметра задачи (weight/heat/connectivity).
        # Полей в Jira под них нет — значения выводятся из снимка задачи
        # (`trr params`, `params.derive`); эти настройки задают границы
        # множителя, его коэффициенты, дефолты и переопределение весов
        # сигналов. Множитель входит в формулу оценки третьим сомножителем
        # (`base × factor × params_multiplier`).
        "params": {
            "enabled": True,
            "clamp": [0.5, 2.0],
            "coefficients": {"weight": 0.5, "heat": 0.4, "connectivity": 0.3},
            "defaults": {"weight": 0.5, "heat": 0.5, "connectivity": 0.5},
            "signals": {},
        },
        "vector": {
            "enabled": True,
            "adjust_range": False,
            "top_k": 5,
            "min_corpus": 30,
            "top_terms": 15,
            "weight_word": 0.5,
        },
        # Дополнительные ресурсы задачи: за каждый распознанный ресурс
        # (allure для тест-кейсов, e2e-сервис автотестирования для автотестов)
        # +1 SP к оценке либо оценка по верхней границе диапазона
        # (`mode: upper_bound`). Особенно важно для задач на написание тестов.
        # Правило `RS-01`, см. `references/estimation-model.md` §9.6.
        "resources": copy.deepcopy(resourcesmod.RESOURCE_DEFAULTS),
    },
    "jira": {
        "project": "",
        "fields": {
            "story_points": "",
            "qa_estimation": "",
            "role": "",
        },
        "field_names": {
            "story_points": "Story Points",
            "qa_estimation": "QA Estimation",
            "role": "Роль",
        },
        "resolve_fields_by_name": True,
        "comment_mode": "post",
    },
    "output": {
        "target": "none",
        "confluence": {"space": "", "page_id": None},
        "obsidian": {"path": ""},
    },
    # Локальное SQLite-зеркало артефактов, метрик и векторов. Включено по
    # умолчанию: файлы остаются источником истины, БД — второй адрес тех же
    # данных (запросы, история, векторы). Confluence — отдельная ось публикации.
    "storage": {
        "sqlite": {
            "enabled": True,
            "path": "%s/%s" % (paths.STATE_DIR_RELATIVE, paths.DB_RELATIVE),
            "keep_vectors": True,
            "keep_payloads": True,
            "vacuum_on_pack": False,
        }
    },
    "artifacts": {
        "include_sprint_sample": True,
        "export_target": "none",
        "local": {"path": None},
        "confluence": {
            "space": None,
            "parent_page_id": None,
            "title_template": "Task Readiness model {{model_version}} — {{project}}",
        },
        "gitlab": {"project": None, "path": "task-readiness/", "branch": "main"},
        "obsidian": {"path": None},
    },
}

# Идентификатор поля Jira: customfield_<число> либо системное имя поля.
_FIELD_ID_RE = re.compile(r"^(customfield_\d+|[a-z][a-z0-9_]*)$")



class ConfigError(Exception):
    """Конфиг отсутствует, не разбирается или нарушает правила."""


# ---------------------------------------------------------------------------
# Секреты
# ---------------------------------------------------------------------------


def _key_words(key):
    """Разбить ключ на слова: camelCase и не-буквенные разделители."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(key))
    return [word for word in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if word]


def is_secret_key(key):
    """Похоже ли имя ключа на секрет (token/secret/password/pat/api_key)."""
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    if any(sub in normalized for sub in _SECRET_SUBSTRINGS):
        return True
    return any(word in _SECRET_WORDS for word in _key_words(key))


def is_demo_value(value):
    """Демо-значение из примера конфига (демо-проект), а не данные пользователя."""
    if value is None or isinstance(value, bool):
        return False
    return str(value).strip() in DEMO_VALUES



def find_secrets(cfg, path=""):
    """Рекурсивно найти ключи-секреты. Возвращает точечные пути."""
    found = []
    if isinstance(cfg, dict):
        for key in sorted(cfg):
            full = "%s.%s" % (path, key) if path else str(key)
            if is_secret_key(key):
                found.append(full)
            else:
                found.extend(find_secrets(cfg[key], full))
    elif isinstance(cfg, list):
        for index, item in enumerate(cfg):
            found.extend(find_secrets(item, "%s[%d]" % (path, index)))
    return found


# ---------------------------------------------------------------------------
# Чтение и дефолты
# ---------------------------------------------------------------------------


def _merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge(base[key], value)
        else:
            base[key] = value
    return base


def _migrate_override_template(cfg):
    """Нормализовать устаревший `sources.override_template` в верхний уровень.

    Канонический путь — верхнеуровневый `override_template` (§5.1 контракта).
    `sources.override_template` принимается только ради обратной совместимости:
    значение переносится наверх (если там пусто), а устаревший ключ удаляется,
    чтобы нормализованный конфиг и `config_sha256` не зависели от формы записи.
    """
    sources = cfg.get("sources")
    if not isinstance(sources, dict) or "override_template" not in sources:
        return cfg
    legacy = sources.pop("override_template")
    if cfg.get("override_template") is None and legacy is not None:
        cfg["override_template"] = legacy
    return cfg


def deprecated_warnings(raw):
    """Предупреждения о устаревших ключах конфига (до подстановки дефолтов)."""
    sources = raw.get("sources") if isinstance(raw, dict) else None
    if isinstance(sources, dict) and "override_template" in sources:
        return [DEPRECATED_OVERRIDE_WARNING]
    return []


def apply_defaults(cfg):
    """Дополнить конфиг значениями по умолчанию, не меняя переданный объект."""
    if not isinstance(cfg, dict):
        raise ConfigError("конфиг должен быть словарём верхнего уровня")
    merged = _merge(copy.deepcopy(DEFAULTS), cfg)
    merged = _complete_params(merged)
    merged = _complete_resources(merged)
    merged = _complete_storage(merged)
    return _migrate_override_template(merged)


def _complete_storage(cfg):
    """Дотянуть недостающие под-ключи `storage.sqlite`.

    `_merge` сливает словари рекурсивно, но `storage: null` или частичный блок
    (`sqlite: {enabled: false}`) не должен оставлять дыры: значения из DEFAULTS
    подставляются по каждому ключу, пользовательские — остаются. Иначе
    `storage.sqlite.path` пришлось бы держать литералом в трёх местах.
    """
    storage = cfg.get("storage")
    if not isinstance(storage, dict):
        storage = {}
    base = DEFAULTS["storage"]["sqlite"]
    sqlite = storage.get("sqlite")
    if not isinstance(sqlite, dict):
        sqlite = {}
    storage["sqlite"] = _merge(copy.deepcopy(base), sqlite)
    cfg["storage"] = storage
    return cfg


def _complete_params(cfg):
    """Дотянуть недостающие под-ключи `estimation.params`.

    `_merge` уже сливает словари рекурсивно, но `params: null` или частичный
    блок (`coefficients: {weight: 0.9}`) не должен оставлять дыры: значения
    из DEFAULTS подставляются по каждому ключу, пользовательские — остаются.
    """
    estimation = cfg.get("estimation")
    if not isinstance(estimation, dict):
        return cfg
    base = DEFAULTS["estimation"]["params"]
    params = estimation.get("params")
    if not isinstance(params, dict):
        params = {}
    estimation["params"] = _merge(copy.deepcopy(base), params)
    return cfg


def _complete_resources(cfg):
    """Дотянуть недостающие под-ключи `estimation.resources`.

    `_merge` сливает словари рекурсивно, но `resources: null` или частичный
    блок (`sp_per_resource: 2`) не должен оставлять дыры: значения из
    `RESOURCE_DEFAULTS` подставляются по каждому ключу, пользовательские
    (включая `items`) — остаются. `items` при этом не затирается: алиасы
    пользователя дополняют дефолтный набор, а не заменяют его.
    """
    estimation = cfg.get("estimation")
    if not isinstance(estimation, dict):
        return cfg
    base = DEFAULTS["estimation"]["resources"]
    resources = estimation.get("resources")
    if not isinstance(resources, dict):
        resources = {}
    completed = _merge(copy.deepcopy(base), resources)
    # `items` — всегда обычные списки: в `RESOURCE_ITEMS` алиасы лежат кортежами
    # (неизменяемый литерал кода), а конфиг и схема работают с массивами JSON.
    def as_list(value):
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str):
            return [value]
        return value

    items = {
        name: as_list(aliases) for name, aliases in (base.get("items") or {}).items()
    }
    user_items = resources.get("items")
    if isinstance(user_items, dict):
        for name, aliases in user_items.items():
            items[name] = as_list(aliases)
    completed["items"] = items
    estimation["resources"] = completed
    return cfg


def config_path(workdir):
    """Путь к конфигу в рабочей директории."""
    return Path(workdir) / CONFIG_FILENAME


def load_config(path, on_warning=None):
    """Прочитать YAML, подставить дефолты и нормализовать устаревшие ключи.

    `on_warning` — куда отдать `[WARN]`-строки (по умолчанию stderr: stdout
    остаётся чистым для `--json`). Ошибки разбора → ConfigError.
    """
    target = Path(path)
    if not target.is_file():
        raise ConfigError("конфиг не найден: %s" % target)
    try:
        raw = yamlmini.load_file(target)
    except yamlmini.YamlError as exc:
        raise ConfigError("конфиг не разбирается: %s" % exc)
    for message in deprecated_warnings(raw):
        if on_warning is None:
            print(message, file=sys.stderr)
        else:
            on_warning(message)
    return apply_defaults(raw)


def config_sha256(cfg):
    """sha256 нормализованного конфига (после подстановки дефолтов)."""
    return hashlib.sha256(schema_lite.canonical_json(cfg).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Валидация
# ---------------------------------------------------------------------------


def validate_config(cfg):
    """Проверить конфиг. Возвращает список сообщений; пустой список — валидно."""
    errors = []

    secrets = find_secrets(cfg)
    for secret in secrets:
        errors.append(
            "%s: ключ похож на секрет — секреты в конфиге запрещены, "
            "используйте переменные окружения JIRA_TOKEN / CONFLUENCE_TOKEN / GITLAB_TOKEN"
            % secret
        )

    try:
        schema = schema_lite.load_schema(SCHEMAS_DIR, "config")
    except schema_lite.SchemaError as exc:
        errors.append("схема конфига не читается: %s" % exc)
        return errors

    errors.extend(schema_lite.validate(cfg, schema, "config"))

    # Семантические правила, которые не выражаются подмножеством JSON Schema.
    estimation = cfg.get("estimation")
    if isinstance(estimation, dict):
        scale = estimation.get("scale")
        if isinstance(scale, list) and all(
            isinstance(item, int) and not isinstance(item, bool) for item in scale
        ):
            if any(
                scale[index] >= scale[index + 1] for index in range(len(scale) - 1)
            ):
                errors.append(
                    "config.estimation.scale: шкала должна строго возрастать, получено %s"
                    % scale
                )
            if scale != NORMATIVE_SCALE:
                errors.append(
                    "config.estimation.scale: шкала нормативна и должна совпадать с "
                    "эталонной %s (страница эталона из sources.reference), "
                    "получено %s" % (NORMATIVE_SCALE, scale)
                )
        clamp = estimation.get("factor_clamp")
        if (
            isinstance(clamp, list)
            and len(clamp) == 2
            and all(
                isinstance(item, (int, float)) and not isinstance(item, bool)
                for item in clamp
            )
        ):
            low, high = clamp
            if not (0 < low < high):
                errors.append(
                    "config.estimation.factor_clamp: нужно 0 < min < max, получено %s"
                    % clamp
                )
        errors.extend(_validate_vector(estimation.get("vector")))
        errors.extend(_validate_params(estimation.get("params")))
        errors.extend(_validate_resources(estimation.get("resources")))

    errors.extend(_validate_sources(cfg.get("sources")))
    errors.extend(_validate_jira(cfg.get("jira")))
    errors.extend(_validate_storage(cfg.get("storage")))
    errors.extend(artifact_place_problems(cfg))

    return errors


def _blank(value):
    """Пустая строка/None — «значение не задано»."""
    return value is None or (isinstance(value, str) and not value.strip())


def _validate_sources(sources):
    """Семантика источников: у объекта обязан быть хоть один способ резолва.

    Схема намеренно не выражает «ровно один из ключей» (подмножество JSON Schema
    без oneOf), поэтому пустой объект и объект без полезных ключей отсекаются
    здесь — иначе такой источник молча исчезнет при нормализации.
    """
    errors = []
    if not isinstance(sources, dict):
        return errors

    reference = sources.get("reference")
    if isinstance(reference, list):
        for index, item in enumerate(reference):
            if not isinstance(item, dict):
                continue
            if _blank(item.get("page_id")) and _blank(item.get("page_url")) and _blank(
                item.get("text")
            ):
                errors.append(
                    "config.sources.reference.%d: нужен один из ключей page_id, "
                    "page_url или text — иначе источник не из чего резолвить" % index
                )

    sprints = sources.get("sprints")
    if isinstance(sprints, list):
        for index, item in enumerate(sprints):
            if not isinstance(item, dict):
                continue
            has_ids = not _blank(item.get("sprint_ids")) and not _blank(
                item.get("board_id")
            )
            has_labels = not _blank(item.get("board_labels"))
            has_text = not _blank(item.get("text"))
            if not (has_ids or has_labels or has_text):
                errors.append(
                    "config.sources.sprints.%d: нужен один из вариантов — "
                    "board_id+sprint_ids, board_labels или text" % index
                )

    confluence = sources.get("confluence")
    if isinstance(confluence, dict):
        max_depth = confluence.get("max_depth")
        if isinstance(max_depth, int) and not isinstance(max_depth, bool):
            if max_depth < 1:
                errors.append(
                    "config.sources.confluence.max_depth: нужно >= 1, получено %s"
                    % max_depth
                )
        max_pages = confluence.get("max_pages")
        if isinstance(max_pages, int) and not isinstance(max_pages, bool):
            if max_pages < 1:
                errors.append(
                    "config.sources.confluence.max_pages: нужно >= 1, получено %s"
                    % max_pages
                )

    return errors


def _validate_vector(vector):
    """Семантика `estimation.vector`: min_corpus не опускается ниже пола.

    Схема проверяет типы и границы полей; здесь — правило, которое нельзя
    выразить подмножеством JSON Schema: `min_corpus < 30` — ошибка конфига,
    а не настройка (30 — нижняя граница, после которой механизм не врёт молча).
    """
    errors = []
    if not isinstance(vector, dict):
        return errors
    min_corpus = vector.get("min_corpus")
    if isinstance(min_corpus, int) and not isinstance(min_corpus, bool):
        if min_corpus < VECTOR_MIN_CORPUS:
            errors.append(
                "config.estimation.vector.min_corpus: %d < %d — ниже нижней границы "
                "корпус не даёт надёжной калибровки"
                % (min_corpus, VECTOR_MIN_CORPUS)
            )
    top_k = vector.get("top_k")
    if isinstance(top_k, int) and not isinstance(top_k, bool) and top_k < 1:
        errors.append(
            "config.estimation.vector.top_k: нужно >= 1, получено %s" % top_k
        )
    top_terms = vector.get("top_terms")
    if isinstance(top_terms, int) and not isinstance(top_terms, bool) and top_terms < 1:
        errors.append(
            "config.estimation.vector.top_terms: нужно >= 1, получено %s" % top_terms
        )
    return errors


def _validate_resources(resources):
    """Семантика `estimation.resources`: режим, шаг надбавки, каталог алиасов.

    Схема проверяет типы и границы; здесь — правила, которые подмножеством
    JSON Schema не выражаются: `mode` обязан быть из `RESOURCE_MODES`, шаг
    надбавки — неотрицательным числом, а `items` — объектом «имя ресурса →
    непустой список строк». Пустой список алиасов законен: это способ выключить
    ресурс, поэтому проверяется только тип элементов.
    """
    errors = []
    if not isinstance(resources, dict):
        return errors

    enabled = resources.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        errors.append(
            "config.estimation.resources.enabled: нужно true/false, получено %r"
            % (enabled,)
        )

    sp = resources.get("sp_per_resource")
    if sp is not None:
        if isinstance(sp, bool) or not isinstance(sp, (int, float)):
            errors.append(
                "config.estimation.resources.sp_per_resource: нужно число, получено %r"
                % (sp,)
            )
        elif float(sp) < 0:
            errors.append(
                "config.estimation.resources.sp_per_resource: нужно >= 0, получено %s"
                % sp
            )

    mode = resources.get("mode")
    if mode is not None:
        if not isinstance(mode, str) or mode.strip() not in resourcesmod.RESOURCE_MODES:
            errors.append(
                "config.estimation.resources.mode: %r неизвестен — допустимы: %s"
                % (mode, ", ".join(resourcesmod.RESOURCE_MODES))
            )

    items = resources.get("items")
    if items is not None:
        if not isinstance(items, dict):
            errors.append(
                "config.estimation.resources.items: нужен объект «имя ресурса → "
                "список алиасов», получено %r" % (items,)
            )
        else:
            for name in sorted(items):
                aliases = items[name]
                if isinstance(aliases, str):
                    aliases = [aliases]
                if not isinstance(aliases, list):
                    errors.append(
                        "config.estimation.resources.items.%s: нужен список строк, "
                        "получено %r" % (name, aliases)
                    )
                    continue
                for index, alias in enumerate(aliases):
                    if not isinstance(alias, str) or not alias.strip():
                        errors.append(
                            "config.estimation.resources.items.%s.%d: нужна "
                            "непустая строка-алиас, получено %r" % (name, index, alias)
                        )

    return errors


def _validate_params(params):
    """Семантика `estimation.params`: границы, коэффициенты, дефолты.

    Схема проверяет типы; здесь — правила, которые подмножеством JSON Schema
    не выражаются: `clamp` обязан накрывать 1.0 (иначе множитель не может быть
    нейтральным), `defaults` — лежать в `[0, 1]`, `coefficients` — не больше 2.
    """
    errors = []
    if not isinstance(params, dict):
        return errors

    enabled = params.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        errors.append(
            "config.estimation.params.enabled: нужно true/false, получено %r"
            % (enabled,)
        )

    clamp = params.get("clamp")
    if clamp is not None:
        numbers = [
            item
            for item in (clamp if isinstance(clamp, list) else [])
            if isinstance(item, (int, float)) and not isinstance(item, bool)
        ]
        if not isinstance(clamp, list) or len(clamp) != 2 or len(numbers) != 2:
            errors.append(
                "config.estimation.params.clamp: нужно ровно два числа "
                "[min, max], получено %r" % (clamp,)
            )
        else:
            low, high = float(numbers[0]), float(numbers[1])
            if not (0 < low <= 1.0 <= high <= 4.0):
                errors.append(
                    "config.estimation.params.clamp: нужно 0 < min <= 1.0 <= "
                    "max <= 4.0, получено %s" % clamp
                )

    coefficients = params.get("coefficients")
    if coefficients is not None:
        if not isinstance(coefficients, dict):
            errors.append(
                "config.estimation.params.coefficients: нужен объект "
                "{weight, heat, connectivity}, получено %r" % (coefficients,)
            )
        else:
            for name in ("weight", "heat", "connectivity"):
                if name not in coefficients:
                    continue
                value = coefficients.get(name)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(
                        "config.estimation.params.coefficients.%s: нужно число, "
                        "получено %r" % (name, value)
                    )
                elif not (0 <= float(value) <= 2):
                    errors.append(
                        "config.estimation.params.coefficients.%s: нужно "
                        "0 <= значение <= 2, получено %s" % (name, value)
                    )

    defaults = params.get("defaults")
    if defaults is not None:
        if not isinstance(defaults, dict):
            errors.append(
                "config.estimation.params.defaults: нужен объект "
                "{weight, heat, connectivity}, получено %r" % (defaults,)
            )
        else:
            for name in ("weight", "heat", "connectivity"):
                if name not in defaults:
                    continue
                value = defaults.get(name)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(
                        "config.estimation.params.defaults.%s: нужно число, "
                        "получено %r" % (name, value)
                    )
                elif not (0 <= float(value) <= 1):
                    errors.append(
                        "config.estimation.params.defaults.%s: нужно "
                        "0 <= значение <= 1, получено %s" % (name, value)
                    )

    signals = params.get("signals")
    if signals is not None and not isinstance(signals, dict):
        errors.append(
            "config.estimation.params.signals: нужен объект «имя сигнала → вес», "
            "получено %r" % (signals,)
        )
    elif isinstance(signals, dict):
        for name, value in sorted(signals.items()):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(
                    "config.estimation.params.signals.%s: нужно число, получено %r"
                    % (name, value)
                )
            elif not (0 <= float(value) <= 1):
                errors.append(
                    "config.estimation.params.signals.%s: нужно 0 <= вес <= 1, "
                    "получено %s" % (name, value)
                )

    return errors


_STORAGE_EXTENSIONS = (".sqlite3", ".db")


def _validate_storage(storage):
    """Семантика `storage.sqlite`: типы флагов и путь внутри проекта.

    Схема проверяет типы полей; здесь — правила, которые подмножеством JSON
    Schema не выражаются: относительный путь не может выходить за корень
    проекта (`../…`), иначе зеркало писалось бы в чужие каталоги. Абсолютный
    путь разрешён (это осознанный выбор пользователя) — про него предупреждает
    `storage_warnings`, а не ошибка.
    """
    errors = []
    if storage is None:
        return errors
    if not isinstance(storage, dict):
        return errors
    sqlite = storage.get("sqlite")
    if sqlite is None or not isinstance(sqlite, dict):
        return errors

    for key in ("enabled", "keep_vectors", "keep_payloads", "vacuum_on_pack"):
        value = sqlite.get(key)
        if value is not None and not isinstance(value, bool):
            errors.append(
                "config.storage.sqlite.%s: нужно true/false, получено %r"
                % (key, value)
            )

    path = sqlite.get("path")
    if path is None:
        return errors
    if not isinstance(path, str) or not path.strip():
        errors.append(
            "config.storage.sqlite.path: нужна непустая строка — путь к файлу "
            "БД относительно корня проекта (по умолчанию %s/%s)"
            % (paths.STATE_DIR_RELATIVE, paths.DB_RELATIVE)
        )
        return errors

    candidate = Path(path.strip())
    if not candidate.is_absolute():
        normalized = os.path.normpath(path.strip())
        if normalized == ".." or normalized.startswith(".." + os.sep):
            errors.append(
                "config.storage.sqlite.path: %r выходит за пределы проекта — "
                "относительный путь задаётся от корня проекта" % path
            )
    return errors


def storage_warnings(cfg):
    """`[WARN]`-строки `storage.sqlite`: абсолютный путь и нестандартное расширение.

    Это не ошибка: зеркало — вспомогательный слой, и осознанный абсолютный путь
    (например, на быстрый диск) законен. Предупреждение нужно, чтобы такой путь
    не появился случайно и не уехал в чужой каталог при переносе проекта.
    """
    warnings = []
    if not isinstance(cfg, dict):
        return warnings
    storage = cfg.get("storage")
    sqlite = storage.get("sqlite") if isinstance(storage, dict) else None
    if not isinstance(sqlite, dict):
        return warnings
    path = sqlite.get("path")
    if not isinstance(path, str) or not path.strip():
        return warnings
    value = path.strip()
    candidate = Path(value)
    if candidate.is_absolute():
        warnings.append(
            "[WARN] config.storage.sqlite.path: абсолютный путь %s — файл БД "
            "вне проекта, при переносе проекта он не переедет" % value
        )
    if candidate.suffix.lower() not in _STORAGE_EXTENSIONS:
        warnings.append(
            "[WARN] config.storage.sqlite.path: расширение %r не .sqlite3/.db — "
            "файл всё равно будет SQLite, но имя не подсказывает формат"
            % (candidate.suffix or "")
        )
    return warnings


def _validate_jira(jira):
    """Семантика полей Jira: id либо заполнены, либо резолвятся по именам."""
    errors = []
    if not isinstance(jira, dict):
        return errors

    fields = jira.get("fields") if isinstance(jira.get("fields"), dict) else {}
    names = jira.get("field_names") if isinstance(jira.get("field_names"), dict) else {}
    by_name = jira.get("resolve_fields_by_name")
    by_name = True if by_name is None else bool(by_name)

    keys = ("story_points", "qa_estimation", "role")
    empty = [key for key in keys if _blank(fields.get(key))]
    filled = [key for key in keys if not _blank(fields.get(key))]

    for key in filled:
        value = str(fields.get(key)).strip()
        if not _FIELD_ID_RE.match(value):
            errors.append(
                "config.jira.fields.%s: %r не похоже на id поля (ожидается "
                "customfield_<число> или системное имя вроде status)" % (key, value)
            )

    if not by_name and empty:
        errors.append(
            "config.jira.fields: пусто (%s) и jira.resolve_fields_by_name: false — "
            "заполните id полей или включите резолв по именам" % ", ".join(empty)
        )

    if by_name:
        for key in empty:
            if _blank(names.get(key)):
                errors.append(
                    "config.jira.field_names.%s: имя поля не задано — при "
                    "resolve_fields_by_name: true оно нужно, чтобы найти id" % key
                )

    return errors


# ---------------------------------------------------------------------------
# Место публикации обученного бандла (`artifacts.*`)
# ---------------------------------------------------------------------------


def artifact_place_problem(cfg, target):
    """Первое незаполненное место публикации бандла для `target` (или None).

    Проверяется ровно то место, куда пойдёт бандл при `artifacts.export_target:
    <target>`: `local.path`, `confluence.space`/`parent_page_id`,
    `gitlab.project`, `obsidian.path`. `target="none"` места не требует.

    Возвращает строку-инструкцию `config.artifacts.<target>.<ключ>: не задано —
    <что сделать>`; её печатают `config-check` (как `[MISSING]`) и
    `trr artifact plan` (как `[MISSING]`, код 2).
    """
    if target in (None, "", "none"):
        return None
    artifacts = cfg.get("artifacts") if isinstance(cfg, dict) else None
    if not isinstance(artifacts, dict):
        artifacts = {}

    def block(name):
        value = artifacts.get(name)
        return value if isinstance(value, dict) else {}

    if target == "local":
        if _blank(block("local").get("path")):
            return (
                "config.artifacts.local.path: не задано — укажите файл или каталог, "
                "куда складывать бандл (artifacts.export_target: local)"
            )
    elif target == "confluence":
        confluence = block("confluence")
        if _blank(confluence.get("space")):
            return (
                "config.artifacts.confluence.space: не задано — укажите ключ "
                "пространства Confluence, где публиковать бандл "
                "(artifacts.export_target: confluence)"
            )
        if _blank(confluence.get("parent_page_id")):
            return (
                "config.artifacts.confluence.parent_page_id: не задано — укажите id "
                "родительской страницы, под которой создаётся страница бандла"
            )
    elif target == "gitlab":
        if _blank(block("gitlab").get("project")):
            return (
                "config.artifacts.gitlab.project: не задано — укажите id или путь "
                "проекта GitLab (group/project), куда публиковать бандл "
                "(artifacts.export_target: gitlab)"
            )
    elif target == "obsidian":
        if _blank(block("obsidian").get("path")):
            return (
                "config.artifacts.obsidian.path: не задано — укажите путь заметки в "
                "хранилище Obsidian (artifacts.export_target: obsidian)"
            )
    return None


def artifact_place_problems(cfg):
    """Все проблемы места публикации бандла для текущего `artifacts.export_target`.

    Дефолт `export_target: none` ничего не требует — «не публиковать» это
    законный режим, и пустые места тогда не ошибка.
    """
    artifacts = cfg.get("artifacts") if isinstance(cfg, dict) else None
    if not isinstance(artifacts, dict):
        return []
    target = artifacts.get("export_target")
    if target in (None, "", "none"):
        return []
    if target not in ARTIFACT_TARGETS:
        return [
            "config.artifacts.export_target: %r неизвестен — допустимы: %s"
            % (target, ", ".join(ARTIFACT_TARGETS))
        ]
    problem = artifact_place_problem(cfg, target)
    return [problem] if problem else []


# ---------------------------------------------------------------------------
# Демо-значения
# ---------------------------------------------------------------------------


def demo_warnings(cfg):
    """`[WARN]`-строки о значениях, оставшихся от демо-примера.

    Это не ошибка конфига (схема и `config-check` проходят), а напоминание:
    демо-данные из примера конфига не должны попадать в отчёт реального проекта.
    """
    warnings = []
    if not isinstance(cfg, dict):
        return warnings

    jira = cfg.get("jira") if isinstance(cfg.get("jira"), dict) else {}
    project = jira.get("project")
    if is_demo_value(project):
        warnings.append(
            "[WARN] jira.project: %s похоже на демо-значение, замените на ключ "
            "своего проекта Jira" % project
        )

    sources = cfg.get("sources") if isinstance(cfg.get("sources"), dict) else {}
    for index, item in enumerate(sources.get("reference") or []):
        if not isinstance(item, dict):
            continue
        for key in ("page_id", "page_url"):
            value = item.get(key)
            if key == "page_id" and is_demo_value(value):
                warnings.append(
                    "[WARN] sources.reference.%d.page_id: %s похоже на демо-значение, "
                    "замените на свою страницу эталона" % (index, value)
                )
            if key == "page_url" and is_demo_value(_page_id_from_url(value)):
                warnings.append(
                    "[WARN] sources.reference.%d.page_url: ссылка ведёт на демо-страницу "
                    "(page_id %s), замените на свою" % (index, _page_id_from_url(value))
                )
    for index, item in enumerate(sources.get("sprints") or []):
        if not isinstance(item, dict):
            continue
        board = item.get("board_id")
        if is_demo_value(board):
            warnings.append(
                "[WARN] sources.sprints.%d.board_id: %s похоже на демо-значение, "
                "замените на свой борд Jira" % (index, board)
            )
        ids = item.get("sprint_ids")
        if isinstance(ids, list):
            demo = [value for value in ids if is_demo_value(value)]
            if demo:
                warnings.append(
                    "[WARN] sources.sprints.%d.sprint_ids: %s — демо-значения, "
                    "замените на свои спринты"
                    % (index, ", ".join(str(value) for value in demo))
                )

    fields = jira.get("fields") if isinstance(jira.get("fields"), dict) else {}
    demo_fields = [
        "%s=%s" % (key, fields[key])
        for key in ("story_points", "qa_estimation", "role")
        if is_demo_value(fields.get(key))
    ]
    if demo_fields:
        warnings.append(
            "[WARN] jira.fields: %s — демо-значения из примера, проверьте id полей "
            "своего проекта" % ", ".join(demo_fields)
        )

    return warnings


def _page_id_from_url(url):
    """page_id из URL (для предупреждения о демо-ссылке); None, если его нет."""
    match = re.search(r"[?&]pageId=(\d+)", str(url or ""), re.IGNORECASE)
    return match.group(1) if match else None



# ---------------------------------------------------------------------------
# Рабочая директория
# ---------------------------------------------------------------------------


def resolve_workdir(explicit=None):
    """Определить рабочую директорию проекта.

    Порядок: явный `--workdir`/`--root` → env TASK_READINESS_ROOT → поиск
    `task-readiness-review.yaml` вверх по дереву → текущая директория.
    """
    if explicit:
        return str(Path(explicit).expanduser().resolve())
    env_value = os.environ.get(ENV_ROOT)
    if env_value:
        return str(Path(env_value).expanduser().resolve())
    current = Path.cwd().resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / CONFIG_FILENAME).is_file():
            return str(candidate)
    return str(current)


def skill_root():
    """Корень установленного скилла (там лежат example, schemas, templates)."""
    return str(SKILL_ROOT)

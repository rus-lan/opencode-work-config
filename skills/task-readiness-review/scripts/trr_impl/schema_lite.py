#!/usr/bin/env python3
"""Валидатор подмножества JSON Schema (draft-07) на stdlib.

Поддерживается ровно то подмножество, которое используют схемы в `schemas/`:

    type (строка или список типов), required, properties, additionalProperties,
    items, enum, const, minimum, maximum, minItems, maxItems, pattern

Ключевое слово вне этого списка (в том числе `$ref`) — ошибка SCHEMA_ERROR,
а не «тихо пропустить»: схемы скилла самодостаточны и ссылок не содержат.

Порядок проверок фиксирован и не зависит от порядка ключей в схеме:
required → type → enum/const → границы (minimum/maximum/minItems/maxItems/pattern)
→ properties → additionalProperties → items. Поэтому одинаковый вход всегда даёт
одинаковый список сообщений.

CLI: `python3 schema_lite.py <schema.json> <instance.json>` → 0 валидно, 5 ошибки.
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

__all__ = [
    "SCHEMA_NAMES",
    "SchemaError",
    "canonical_json",
    "load_schema",
    "sha256_canonical",
    "validate",
    "write_json",
]

# Имена артефактов из закрытого списка CONTRACT.md §4 (подкоманда validate).
SCHEMA_NAMES = (
    "config",
    "resolved-sources",
    "reference-estimates",
    "sprint-sample",
    "sprint-stats",
    "estimation-model",
    "validation",
    "questions",
    "estimate",
    "state",
    "artifact-manifest",
    "task-texts",
    "task-vectors",
)

# Ключевые слова, которые валидатор понимает и проверяет.
_CHECKED_KEYWORDS = frozenset(
    {
        "type",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "pattern",
    }
)

# Аннотации: на результат проверки не влияют, но и ошибкой не считаются.
_ANNOTATION_KEYWORDS = frozenset({"$schema", "$comment", "title", "description"})

SUPPORTED_KEYWORDS = _CHECKED_KEYWORDS | _ANNOTATION_KEYWORDS

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


class SchemaError(Exception):
    """Схему не удалось прочитать или она не является объектом."""


# ---------------------------------------------------------------------------
# Канонический JSON и контрольные суммы (CONTRACT.md §8)
# ---------------------------------------------------------------------------


def canonical_json(obj):
    """Каноническая сериализация: сортировка ключей, без пробелов, UTF-8 как есть."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_canonical(obj):
    """sha256 канонического JSON объекта в UTF-8."""
    import hashlib

    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def write_json(path, obj):
    """Записать JSON детерминированно и атомарно.

    Формат: `sort_keys`, `indent=2`, ровно один `\\n` в конце. Запись идёт во
    временный файл в том же каталоге (`fsync` + `os.replace`): прерванная
    запись не оставляет ни `.tmp`-мусора, ни наполовину перезаписанного
    артефакта — старый файл остаётся целым.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=".%s-" % target.name, suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, str(target))
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return target


# ---------------------------------------------------------------------------
# Загрузка схем
# ---------------------------------------------------------------------------


def schema_path(schemas_dir, name):
    """Путь к файлу схемы: `name` или `name.schema.json`."""
    base = Path(schemas_dir)
    if name.endswith(".json"):
        return base / name
    return base / (name + ".schema.json")


def load_schema(schemas_dir, name):
    """Прочитать схему артефакта по имени из `schemas/`."""
    path = schema_path(schemas_dir, name)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except OSError as exc:
        raise SchemaError("не удалось прочитать схему %s: %s" % (path, exc))
    except ValueError as exc:
        raise SchemaError("схема %s — невалидный JSON: %s" % (path, exc))
    if not isinstance(schema, dict):
        raise SchemaError("схема %s должна быть JSON-объектом" % path)
    return schema


# ---------------------------------------------------------------------------
# Валидация
# ---------------------------------------------------------------------------


def _p(path):
    return path or "$"


def _join(path, key):
    return str(key) if not path else "%s.%s" % (path, key)


def _json_equal(left, right):
    """Сравнение в терминах JSON: true не равно 1, 1 равно 1.0."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(
            _json_equal(left[k], right[k]) for k in left
        )
    return type(left) is type(right) and left == right


def _actual_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_names(spec):
    if isinstance(spec, str):
        return [spec]
    if isinstance(spec, list):
        return [item for item in spec]
    return None


def _check_type(instance, spec, path, errors):
    """Проверить type. Возвращает True, если тип подходит (или проверить нельзя)."""
    names = _type_names(spec)
    if names is None:
        errors.append("%s: 'type' должен быть строкой или списком строк" % _p(path))
        return True
    for name in names:
        check = _TYPE_CHECKS.get(name)
        if check is None:
            errors.append("%s: неизвестный тип '%s'" % (_p(path), name))
            return True
        if check(instance):
            return True
    errors.append(
        "%s: ожидался тип %s, получено %s"
        % (_p(path), "/".join(str(n) for n in names), _actual_type(instance))
    )
    return False


def _check_bounds(instance, schema, path, errors):
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None:
            if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
                errors.append("%s: 'minimum' должен быть числом" % _p(path))
            elif instance < minimum:
                errors.append(
                    "%s: значение %s меньше минимума %s" % (_p(path), instance, minimum)
                )
        maximum = schema.get("maximum")
        if maximum is not None:
            if not isinstance(maximum, (int, float)) or isinstance(maximum, bool):
                errors.append("%s: 'maximum' должен быть числом" % _p(path))
            elif instance > maximum:
                errors.append(
                    "%s: значение %s больше максимума %s" % (_p(path), instance, maximum)
                )
    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None:
            if not isinstance(min_items, int) or isinstance(min_items, bool):
                errors.append("%s: 'minItems' должен быть целым" % _p(path))
            elif len(instance) < min_items:
                errors.append(
                    "%s: элементов %d, минимум %d"
                    % (_p(path), len(instance), min_items)
                )
        max_items = schema.get("maxItems")
        if max_items is not None:
            if not isinstance(max_items, int) or isinstance(max_items, bool):
                errors.append("%s: 'maxItems' должен быть целым" % _p(path))
            elif len(instance) > max_items:
                errors.append(
                    "%s: элементов %d, максимум %d"
                    % (_p(path), len(instance), max_items)
                )
    if isinstance(instance, str):
        pattern = schema.get("pattern")
        if pattern is not None:
            if not isinstance(pattern, str):
                errors.append("%s: 'pattern' должен быть строкой" % _p(path))
            else:
                try:
                    matched = re.search(pattern, instance) is not None
                except re.error as exc:
                    errors.append("%s: некорректный 'pattern' (%s)" % (_p(path), exc))
                else:
                    if not matched:
                        errors.append(
                            "%s: строка не соответствует шаблону %s"
                            % (_p(path), json.dumps(pattern, ensure_ascii=False))
                        )


def _validate(instance, schema, path, errors):
    if not isinstance(schema, dict):
        errors.append("%s: схема должна быть объектом" % _p(path))
        return

    unsupported = sorted(key for key in schema if key not in SUPPORTED_KEYWORDS)
    if unsupported:
        for key in unsupported:
            errors.append(
                "%s: неподдерживаемое ключевое слово схемы '%s'" % (_p(path), key)
            )
        return

    # 1. required
    required = schema.get("required")
    if required is not None:
        if not isinstance(required, list):
            errors.append("%s: 'required' должен быть списком" % _p(path))
        elif isinstance(instance, dict):
            for key in required:
                if key not in instance:
                    errors.append(
                        "%s: отсутствует обязательное поле" % _join(path, key)
                    )

    # 2. type
    spec = schema.get("type")
    if spec is not None and not _check_type(instance, spec, path, errors):
        return

    # 3. enum / const
    if "enum" in schema:
        values = schema["enum"]
        if not isinstance(values, list):
            errors.append("%s: 'enum' должен быть списком" % _p(path))
        elif not any(_json_equal(instance, value) for value in values):
            allowed = ", ".join(
                json.dumps(value, ensure_ascii=False) for value in values
            )
            errors.append(
                "%s: значение %s не входит в допустимые (%s)"
                % (
                    _p(path),
                    json.dumps(instance, ensure_ascii=False),
                    allowed,
                )
            )
    if "const" in schema and not _json_equal(instance, schema["const"]):
        errors.append(
            "%s: значение должно быть %s"
            % (_p(path), json.dumps(schema["const"], ensure_ascii=False))
        )

    # 4. границы
    _check_bounds(instance, schema, path, errors)

    # 5. properties + additionalProperties
    properties = schema.get("properties")
    if properties is not None and not isinstance(properties, dict):
        errors.append("%s: 'properties' должен быть объектом" % _p(path))
        properties = None
    additional = schema.get("additionalProperties")
    if isinstance(instance, dict):
        if properties:
            for key in sorted(properties):
                if key in instance:
                    _validate(instance[key], properties[key], _join(path, key), errors)
        if additional is False:
            for key in sorted(instance):
                if properties and key in properties:
                    continue
                errors.append("%s: недопустимое поле" % _join(path, key))
        elif isinstance(additional, dict):
            for key in sorted(instance):
                if properties and key in properties:
                    continue
                _validate(instance[key], additional, _join(path, key), errors)
        elif additional is not None and additional is not True:
            errors.append(
                "%s: 'additionalProperties' должен быть boolean или схемой" % _p(path)
            )

    # 6. items
    if isinstance(instance, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(instance):
                _validate(item, items, _join(path, index), errors)
        elif items is not None:
            errors.append(
                "%s: 'items' должен быть объектом (списки схем не поддерживаются)"
                % _p(path)
            )


def validate(instance, schema, path=""):
    """Проверить instance по схеме. Возвращает список ошибок вида `path: message`."""
    errors = []
    _validate(instance, schema, path, errors)
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_USAGE = "использование: schema_lite.py <schema.json> <instance.json>"


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help"):
        print(_USAGE)
        return 0
    if len(args) != 2:
        print(_USAGE, file=sys.stderr)
        return 2

    schema_file, instance_file = args
    try:
        with open(schema_file, "r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except (OSError, ValueError) as exc:
        print("схема не читается: %s" % exc, file=sys.stderr)
        return 5
    try:
        with open(instance_file, "r", encoding="utf-8") as handle:
            instance = json.load(handle)
    except (OSError, ValueError) as exc:
        print("артефакт не читается: %s" % exc, file=sys.stderr)
        return 5

    errors = validate(instance, schema)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 5
    print("[OK] schema: %s" % instance_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Диспетчер `scripts/trr`: подкоманды, коды выхода, печать диагностики.

Запуск: `<skill>/scripts/trr <подкоманда>` либо, из каталога `scripts/`,
`python3 -m trr_impl <подкоманда>`.

Коды выхода (CONTRACT.md §4):

    0  OK            успех, в том числе WARN
    2  BLOCKED       гейт не пройден: нет данных, нет модели, нет прогона
    3  CONFIG_ERROR  конфиг отсутствует, не разбирается, нарушает схему, содержит секрет
    4  MISSING_ARTIFACT  нет обязательного файла-артефакта
    5  SCHEMA_ERROR  артефакт есть, но не соответствует схеме

Модули дорожек (`stats.py`, `calibrate.py`, `check.py`, `estimate.py`,
`report.py`) подключаются лениво: пока их нет, подкоманда печатает
`[BLOCKED] модуль … ещё не реализован` и выходит с кодом 2, а не трейсбеком.
"""

import argparse
import copy
import hashlib
import importlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from trr_impl import config as configmod
from trr_impl import doctor as doctormod
from trr_impl import limits
from trr_impl import params as paramsmod
from trr_impl import schema_lite
from trr_impl import sources as sourcesmod
from trr_impl import state as statemod
from trr_impl import store as storemod
from trr_impl import yamlmini

__all__ = ["EXIT_CODES", "main"]

EXIT_OK = 0
EXIT_BLOCKED = 2
EXIT_CONFIG = 3
EXIT_MISSING = 4
EXIT_SCHEMA = 5

EXIT_CODES = (
    ("0", "OK", "успех, в том числе WARN"),
    ("2", "BLOCKED", "гейт не пройден: нет данных, нет модели, нет прогона"),
    ("3", "CONFIG_ERROR", "конфиг отсутствует, не разбирается, нарушает схему, содержит секрет"),
    ("4", "MISSING_ARTIFACT", "нет обязательного файла-артефакта"),
    ("5", "SCHEMA_ERROR", "артефакт есть, но не соответствует схеме"),
)

# Подкоманды, реализуемые модулями дорожек (пока их нет — BLOCKED).
LAZY_COMMANDS = {
    "stats": "stats",
    "calibrate": "calibrate",
    "check": "check",
    "estimate": "estimate",
    "report": "report",
    "vectors": "vectors",
    "synth": "synth",
}

_EPILOG = """\
подкоманды:
  init                 создать task-readiness-review.yaml из примера и state.json
                       (--from-artifact FILE — импортировать обученный бандл вместо train)
  resolve-sources      записать .task-readiness/resolved-sources.json из sources.* конфига
                       (--recursive и --pages-json — добавить дочерние страницы Confluence)
  match-sprints        сопоставить названия спринтов (board_labels) с id по индексу Jira
  match-fields         сопоставить имена полей Jira (Story Points) с id (customfield_…)
  config-check         проверить конфиг (схема + запрет секретов)
  doctor               диагностика окружения и артефактов
  params               эвристические параметры weight/heat/connectivity задачи
                       (--task | --text-file/--text, --issue-type, --labels, --links,
                       --weight/--heat/--connectivity — override; --json)
  state get <key>      напечатать значение из .task-readiness/state.json
  state set <key> <v>  записать значение в state.json
  validate <artifact> <path>  проверить артефакт по схеме
  stats                посчитать norm/sprint-stats.json из norm/sprint-sample.json
  vectors build        построить norm/task-vectors.json из norm/task-texts.json
                       (--top-terms, --weight-word, --min-corpus)
  vectors similar      похожие задачи по тексту: --task <KEY> | --text-file | --text
                       (--top, --same-bucket)
  vectors calibrate    пересчитать пороги p90/p50 по готовым векторам
  calibrate            построить model/estimation-model.json (--reason train|enrich)
  check --task <KEY>   проверить готовность задачи
  estimate --task <KEY>  посчитать оценку по модели
  report --task <KEY>  отрендерить отчёт (--delta — только изменения)
  report --model       перерендерить model/estimation-model.md из JSON
  publish              опубликовать результат двумя комментариями в задачу Jira
                       («Результаты валидации» + «Результаты оценки»;
                       --plan-jira — план, --draft — печать, --no-jira — без Jira,
                       --comment-id-validation/--comment-id-estimate — записать id;
                       --target — ещё и страница/заметка)
  render-norm          перерендерить .md-зеркала norm/ и model/ без пересчёта
  model-hash           напечатать sha256 и версию модели
  artifact pack        собрать переносимый бандл обучения (.tar.gz)
                       (--out PATH, --no-sprint-sample)
  artifact inspect <f> напечатать манифест бандла сводкой
  artifact unpack <f>  развернуть бандл в .task-readiness/, stage=trained
                       (--force, --allow-foreign-project)
  artifact plan        куда публиковать бандл (--target local|confluence|gitlab|obsidian)
  artifact record      записать публикацию бандла в state.artifacts[]
                       (--target, --ref, --url, --file)
  snapshot-hash        sha256 снимка задачи (context.json) или файла снимка
  diff-values          сравнить последние два прогона: field: old → new
  merge-sample         влить новые строки в norm/sprint-sample.json
  synth                синтетический полигон: N снимков задач из выборки спринтов
                       (--count, --out, --seed, --from-sprints, --include-edge)
  synth-run            прогнать check+estimate по contexts.jsonl in-process
                       (--dir, --out, --limit, --workers) — без записи в runs/
  db init              создать/мигрировать .task-readiness/trr.sqlite3 (идемпотентно)
  db check             integrity_check, версия схемы, счётчики, размер файла
  db ingest            бэкфилл зеркала из артефактов на диске (норма, модель, прогоны)
  db stats             краткая сводка: таблица → строк
  db export --out F    JSON-дамп всех таблиц зеркала
  db query --sql SQL   read-only запрос: SELECT/WITH/PRAGMA (--limit N, --json)
  selftest             самопроверка парсера, схем и канонического JSON

флаги уровня команды (НЕ подкоманды CLI): --post у /task-readiness-review check и
/task-readiness-review publish — постинг комментариев в Jira выполняет агент через MCP,
Python в Jira не пишет: `trr publish` готовит тексты и планы двух комментариев
(валидация и оценка), агент публикует их и фиксирует id через
`trr publish --comment-id-validation <id> --comment-id-estimate <id>`.

коды выхода:
%s
""" % "\n".join(
    "  %s  %-18s %s" % (code, name, text) for code, name, text in EXIT_CODES
)


# ---------------------------------------------------------------------------
# Служебное
# ---------------------------------------------------------------------------


def _emit(args, message):
    """Напечатать человеческую строку, если не --quiet."""
    if not getattr(args, "quiet", False):
        print(message)


def _emit_json(args, payload):
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _finish(args, code, message, **payload):
    """Единая точка выхода: человекочитаемая строка и/или JSON."""
    _emit(args, message)
    data = {"status": "ok" if code == EXIT_OK else "blocked", "code": code}
    data.update(payload)
    _emit_json(args, data)
    return code


def _skill_version():
    path = Path(configmod.SKILL_ROOT) / "VERSION"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
    return text or "0.0.0"


def _load_lazy(name):
    """Импортировать модуль дорожки (`trr_impl.<name>`); None, если файла ещё нет."""
    module_name = "trr_impl.%s" % name
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        if getattr(exc, "name", None) == module_name:
            return None
        raise


def _run_lazy(name, args):
    module = _load_lazy(name)
    if module is None:
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] модуль %s ещё не реализован — подкоманда появится вместе с ним"
            % name,
        )
    runner = getattr(module, "run", None)
    if not callable(runner):
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] модуль %s не предоставляет run(workdir, args)" % name,
        )
    return int(runner(args.workdir, args))


# Ключ задачи Jira: буква, затем буквы/цифры/подчёркивания, дефис и номер.
# Жёсткая проверка нужна не для красоты: `--task` участвует в построении пути
# `.task-readiness/runs/<KEY>/...`, поэтому `../../etc` в ключе — это выход за
# рабочую директорию, а не «странный ключ».
TASK_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")

# Идентификатор прогона: `<RUN-ID>` = UTC-метка (`2026-11-17T09-41-07Z`).
# Никаких `/`, `\` и `..` — прогон всегда один каталог внутри задачи.
RUN_ID_RE = re.compile(r"^[0-9A-Za-z._-]+$")


def _validate_args(args):
    """Проверить пользовательские пути до выполнения команды.

    Возвращает текст `[BLOCKED]`-диагностики или `None`, если всё корректно.
    """
    task_key = getattr(args, "task", None)
    if task_key is not None and not TASK_KEY_RE.match(str(task_key)):
        return (
            "[BLOCKED] некорректный ключ задачи: %r — ожидается формат E001-1234 "
            "(заглавная буква, номер через дефис)" % (task_key,)
        )

    run_id = getattr(args, "run", None)
    if run_id is not None:
        value = str(run_id)
        if ".." in value or not RUN_ID_RE.match(value):
            return (
                "[BLOCKED] некорректный --run: %r — допустимы буквы, цифры, "
                "точка, подчёркивание и дефис, без '..'" % (run_id,)
            )

    file_value = getattr(args, "file", None)
    if (
        file_value is not None
        and not getattr(args, "allow_external_file", False)
        # `artifact inspect/unpack` принимают путь к скачанному бандлу: он
        # законно лежит вне проекта, это вход, а не запись в рабочую директорию.
        and getattr(args, "artifact_command", None) not in ("inspect", "unpack")
    ):
        workdir = Path(args.workdir)
        candidate = Path(str(file_value))
        if not candidate.is_absolute():
            candidate = workdir / candidate
        try:
            candidate.resolve().relative_to(workdir.resolve())
        except (ValueError, OSError):
            return (
                "[BLOCKED] --file вне рабочей директории: %s — передайте путь "
                "внутри %s или флаг --allow-external-file"
                % (file_value, args.workdir)
            )
    return None


def _relative(workdir, path):
    try:
        return str(Path(path).resolve().relative_to(Path(workdir).resolve()))
    except (ValueError, OSError):
        return str(path)


def _dig(state, dotted):
    """Достать значение по точечному пути."""
    current = state
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def _assign(state, dotted, value):
    """Записать значение по точечному пути, создавая вложенные словари."""
    parts = dotted.split(".")
    current = state
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = value


def _format_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# ---------------------------------------------------------------------------
# Снимок задачи: snapshot-hash и diff-values
# ---------------------------------------------------------------------------

# Поля снимка задачи, из которых считается его хеш. Совпадает с подмножеством,
# по которому /task-readiness-review refresh решает «изменилась задача или нет»:
# `sources[]` и `retrieved_at` сюда НЕ входят — они меняются на каждом чтении.
SNAPSHOT_FIELDS = (
    "task_key",
    "issue_type",
    "role",
    "work_kind",
    "sp",
    "qa_estimation",
    "labels",
    "fields",
    "sections",
)

# Поля context.json, которые меняются на каждом чтении: в `--all` не сравниваются.
VOLATILE_FIELDS = ("sources",)


def _runs_root(workdir, task_key):
    return Path(workdir) / statemod.STATE_DIR / "runs" / str(task_key)


def _task_runs(workdir, task_key):
    """Каталоги прогонов задачи с `context.json`, по возрастанию `<RUN-ID>`."""
    base = _runs_root(workdir, task_key)
    if not base.is_dir():
        return []
    return sorted(
        (
            path
            for path in base.iterdir()
            if path.is_dir() and (path / "context.json").is_file()
        ),
        key=lambda path: path.name,
    )


def _read_json_file(path):
    return limits.read_json(path)


def _read_json_optional(path):
    """Прочитать JSON, если файл есть; иначе/битый — None (не ошибка рендера)."""
    try:
        payload = limits.read_json(path)
    except (OSError, ValueError, limits.LimitError):
        return None
    return payload if isinstance(payload, dict) else None


def _lookup_field(payload, dotted):
    """Значение по точечному пути (`sp`, `fields.status`); нет пути — None."""
    current = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def cmd_snapshot_hash(args):
    """`trr snapshot-hash --task <KEY> [--file PATH] [--run RUN-ID]`.

    Печатает `sha256:<hex>` канонического JSON подмножества `SNAPSHOT_FIELDS`
    из снимка задачи: по умолчанию — `context.json` последнего прогона,
    с `--file` — любого файла снимка (свежий снимок из Jira), с `--run` —
    конкретного прогона. Коды: 0 — хеш напечатан; 4 — нет прогона/файла;
    5 — файл есть, но это не JSON-объект.
    """
    workdir = Path(args.workdir)
    task_key = args.task

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = workdir / path
        if not path.is_file():
            return _finish(
                args,
                EXIT_MISSING,
                "[MISSING] %s — файла снимка нет: сохраните снимок задачи в JSON "
                "и повторите" % _relative(workdir, path),
            )
    else:
        if args.run:
            candidate = _runs_root(workdir, task_key) / str(args.run)
            if not (candidate / "context.json").is_file():
                return _finish(
                    args,
                    EXIT_MISSING,
                    "[MISSING] %s — в прогоне нет context.json: сначала "
                    "/task-readiness-review check %s"
                    % (_relative(workdir, candidate / "context.json"), task_key),
                )
            path = candidate / "context.json"
        else:
            runs = _task_runs(workdir, task_key)
            if not runs:
                return _finish(
                    args,
                    EXIT_MISSING,
                    "[MISSING] %s — у задачи %s нет ни одного прогона с "
                    "context.json: сначала /task-readiness-review check %s"
                    % (_relative(workdir, _runs_root(workdir, task_key)), task_key, task_key),
                )
            path = runs[-1] / "context.json"

    display = _relative(workdir, path)
    try:
        payload = _read_json_file(path)
    except (OSError, ValueError) as exc:
        return _finish(args, EXIT_SCHEMA, "[MISSING] %s — %s" % (display, exc))
    if not isinstance(payload, dict):
        return _finish(
            args,
            EXIT_SCHEMA,
            "[MISSING] %s — снимок задачи должен быть JSON-объектом" % display,
        )

    snapshot = {key: payload.get(key) for key in SNAPSHOT_FIELDS}
    digest = schema_lite.sha256_canonical(snapshot)
    _emit(args, "sha256:%s" % digest)
    _emit_json(
        args,
        {
            "status": "ok",
            "code": EXIT_OK,
            "task_key": str(task_key),
            "file": display,
            "sha256": digest,
            "fields": list(SNAPSHOT_FIELDS),
        },
    )
    return EXIT_OK


def cmd_diff_values(args):
    """`trr diff-values --task <KEY> (--field <name> | --all)`.

    Сравнивает `context.json` двух последних прогонов задачи и печатает
    `field: old → new` по одной строке на различие. Поля задаются точечным
    путём (`sp`, `fields.status`) или `--all` — объединение ключей верхнего
    уровня без волатильных (`sources`).

    Коды: 0 — различий нет; 2 — различия есть (это ответ, а не сбой);
    4 — прогонов меньше двух; 5 — битый `context.json`.
    """
    workdir = Path(args.workdir)
    task_key = args.task
    fields = list(getattr(args, "field", None) or [])

    if not fields and not args.all:
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] diff-values: укажите --field <имя> (можно несколько) или --all",
        )

    runs = _task_runs(workdir, task_key)
    if len(runs) < 2:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] diff-values: у задачи %s прогонов %d — нужно минимум два, "
            "сравнивать нечего: запустите /task-readiness-review refresh %s"
            % (task_key, len(runs), task_key),
        )

    previous, current = runs[-2], runs[-1]
    payloads = []
    for run_dir in (previous, current):
        display = _relative(workdir, run_dir / "context.json")
        try:
            payload = _read_json_file(run_dir / "context.json")
        except (OSError, ValueError) as exc:
            return _finish(args, EXIT_SCHEMA, "[MISSING] %s — %s" % (display, exc))
        if not isinstance(payload, dict):
            return _finish(
                args,
                EXIT_SCHEMA,
                "[MISSING] %s — снимок задачи должен быть JSON-объектом" % display,
            )
        payloads.append(payload)
    before, after = payloads

    if args.all:
        names = sorted((set(before) | set(after)) - set(VOLATILE_FIELDS))
    else:
        names = fields

    changes = []
    for name in names:
        old = _lookup_field(before, name)
        new = _lookup_field(after, name)
        if old != new:
            changes.append({"field": name, "old": old, "new": new})

    for change in changes:
        _emit(
            args,
            "%s: %s → %s"
            % (
                change["field"],
                _format_value(change["old"]),
                _format_value(change["new"]),
            ),
        )
    if not changes:
        _emit(args, "[OK] diff-values: различий нет")

    code = EXIT_BLOCKED if changes else EXIT_OK
    _emit_json(
        args,
        {
            "status": "ok" if code == EXIT_OK else "changed",
            "code": code,
            "task_key": str(task_key),
            "previous": _relative(workdir, previous),
            "current": _relative(workdir, current),
            "diff": bool(changes),
            "changes": changes,
        },
    )
    return code


def cmd_merge_sample(args):
    """`trr merge-sample`: влить новые строки выборки в `norm/sprint-sample.json`.

    Заменяет ручной скрипт из `/task-readiness-review enrich`: дедупликация по `key`,
    сортировка строк по `(sprint, key)`, дедупликация спринтов по `id`,
    сортировка по `id`. Результат проверяется схемой `sprint-sample` до записи.
    """
    workdir = Path(args.workdir)
    target = Path(args.target) if args.target else Path(statemod.STATE_DIR) / "norm" / "sprint-sample.json"
    if not target.is_absolute():
        target = workdir / target
    source = (
        Path(args.source)
        if args.source
        else Path(statemod.STATE_DIR) / ".sprint-sample-new.json"
    )
    if not source.is_absolute():
        source = workdir / source

    loaded = []
    for path in (target, source):
        display = _relative(workdir, path)
        if not path.is_file():
            return _finish(
                args,
                EXIT_MISSING,
                "[MISSING] %s — файла нет: сначала соберите выборку "
                "(/task-readiness-review train §b или §5.2 enrich)" % display,
            )
        try:
            payload = _read_json_file(path)
        except (OSError, ValueError) as exc:
            return _finish(args, EXIT_SCHEMA, "[MISSING] %s — %s" % (display, exc))
        if not isinstance(payload, dict):
            return _finish(
                args,
                EXIT_SCHEMA,
                "[MISSING] %s — выборка должна быть JSON-объектом" % display,
            )
        loaded.append(payload)
    sample, fresh = loaded

    rows = [row for row in sample.get("rows") or [] if isinstance(row, dict)]
    known_keys = {row.get("key") for row in rows}
    added_rows = [
        row
        for row in fresh.get("rows") or []
        if isinstance(row, dict) and row.get("key") not in known_keys
    ]
    rows.extend(added_rows)
    rows.sort(key=lambda row: (str(row.get("sprint", "")), str(row.get("key", ""))))

    sample_source = sample.get("source") or {}
    sprints = [
        item for item in sample_source.get("sprints") or [] if isinstance(item, dict)
    ]
    known_sprints = {item.get("id") for item in sprints}
    added_sprints = [
        item
        for item in (fresh.get("source") or {}).get("sprints") or []
        if isinstance(item, dict) and item.get("id") not in known_sprints
    ]
    sprints.extend(added_sprints)
    sprints.sort(key=lambda item: str(item.get("id")))

    merged = {"source": dict(sample_source), "rows": rows}
    merged["source"]["sprints"] = sprints

    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, "sprint-sample")
    except schema_lite.SchemaError as exc:
        return _finish(args, EXIT_SCHEMA, "[MISSING] схема sprint-sample — %s" % exc)
    errors = schema_lite.validate(merged, schema)
    if errors:
        for error in errors:
            _emit(args, "[MISSING] %s — %s" % (_relative(workdir, target), error))
        return _finish(
            args,
            EXIT_SCHEMA,
            "[MISSING] merge-sample: объединённая выборка не соответствует схеме "
            "sprint-sample (%d ошибок)" % len(errors),
        )

    try:
        schema_lite.write_json(target, merged)
    except OSError as exc:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s — %s" % (_relative(workdir, target), exc),
        )

    _emit(
        args,
        "[OK] добавлено строк: %d, спринтов: %d — всего строк %d, спринтов %d"
        % (len(added_rows), len(added_sprints), len(rows), len(sprints)),
    )
    _emit_json(
        args,
        {
            "status": "ok",
            "code": EXIT_OK,
            "target": _relative(workdir, target),
            "added_rows": len(added_rows),
            "added_sprints": len(added_sprints),
            "rows": len(rows),
            "sprints": len(sprints),
        },
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# Подкоманды
# ---------------------------------------------------------------------------


def _config_backup_name(target, counter=1):
    """Имя бэкапа рядом с конфигом: `<name>.bak-<UTC>` либо `…-<UTC>-<N>`.

    Только строит имя — существование не проверяет: проверка `exists()` перед
    копированием была гонкой (см. `_write_config_backup`).
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if counter <= 1:
        return target.with_name("%s.bak-%s" % (target.name, stamp))
    return target.with_name("%s.bak-%s-%d" % (target.name, stamp, counter))


def _write_config_backup(target):
    """Скопировать конфиг в бэкап, создав файл эксклюзивно.

    Между `exists()` и `copyfile` была гонка: два `init --force` в одну секунду
    выбирали одно имя, и второй молча затирал копию первого. Поэтому файл
    создаётся через `open(..., "xb")` (`O_CREAT | O_EXCL`): проигравший гонку
    получает `FileExistsError` и берёт следующий суффикс (`-2`, `-3`, …).
    Недописанный бэкап (ошибка чтения/записи) удаляется, чтобы не оставлять
    пустой файл под видом копии.
    """
    counter = 1
    while True:
        candidate = _config_backup_name(target, counter)
        try:
            handle = open(candidate, "xb")
        except FileExistsError:
            counter += 1
            continue
        try:
            with handle, open(target, "rb") as source:
                shutil.copyfileobj(source, handle)
        except OSError:
            try:
                candidate.unlink()
            except OSError:
                pass
            raise
        return candidate


def _non_demo_config_values(path):
    """Не-демо значения прежнего конфига — что пользователь потерял бы при --force.

    Возвращает короткие пары `поле=значение` только для тех полей, которые
    пользователь заполняет под свой проект (проект Jira, борд, поле Story
    Points). Демо-значения примера и пустые значения сюда не попадают: их
    перезапись ничего не теряет. Битый/отсутствующий конфиг — пустой список
    (предупреждать не о чем, бэкап всё равно создан).
    """
    try:
        cfg = configmod.load_config(path)
    except (configmod.ConfigError, OSError):
        return []
    values = []
    jira = cfg.get("jira") if isinstance(cfg.get("jira"), dict) else {}
    project = jira.get("project")
    if project and not configmod.is_demo_value(project):
        values.append("jira.project=%s" % project)
    sources = cfg.get("sources") if isinstance(cfg.get("sources"), dict) else {}
    for item in sources.get("sprints") or []:
        if not isinstance(item, dict):
            continue
        board = item.get("board_id")
        if board and not configmod.is_demo_value(board):
            label = "board_id=%s" % board
            if label not in values:
                values.append(label)
    fields = jira.get("fields") if isinstance(jira.get("fields"), dict) else {}
    story_points = fields.get("story_points")
    if story_points and not configmod.is_demo_value(story_points):
        values.append("story_points=%s" % story_points)
    return values


def cmd_init(args):
    workdir = Path(args.workdir)
    target = configmod.config_path(workdir)
    example = Path(configmod.EXAMPLE_CONFIG)

    if target.exists() and not args.force:
        # Молча «продолжить» нельзя: init создаёт конфиг, а не правит чужой.
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] %s уже существует — используйте --force для перезаписи"
            % configmod.CONFIG_FILENAME,
            config=str(target),
        )
    if not example.is_file():
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s — пример конфига отсутствует в установленном скилле" % example,
        )

    overwritten = target.exists()
    backup = None
    non_demo = []
    if overwritten:
        # `--force` остаётся `--force` (ничего не блокируем и не спрашиваем), но
        # правки пользователя не должны исчезать без следа: рядом кладётся
        # копия прежнего конфига, а в выводе — путь и потерянные не-демо поля.
        non_demo = _non_demo_config_values(target)
        try:
            backup = _write_config_backup(target)
        except OSError as exc:
            return _finish(
                args,
                EXIT_MISSING,
                "[MISSING] не удалось сохранить резервную копию %s: %s"
                % (target, exc),
                config=str(target),
            )
    workdir.mkdir(parents=True, exist_ok=True)
    with open(example, "r", encoding="utf-8") as source:
        text = source.read()
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    try:
        cfg = configmod.load_config(target)
    except configmod.ConfigError as exc:
        return _finish(
            args,
            EXIT_CONFIG,
            "[MISSING] %s — скопированный пример не разбирается: %s" % (target, exc),
        )
    errors = configmod.validate_config(cfg)
    if errors:
        for error in errors:
            _emit(args, "[MISSING] %s — %s" % (configmod.CONFIG_FILENAME, error))
        return _finish(args, EXIT_CONFIG, "[MISSING] config не прошёл проверку")

    state_file = statemod.state_path(workdir)
    if not state_file.exists() or args.force:
        state = statemod.default_state(_skill_version())
        state["stage"] = "configured"
        state["config_sha256"] = configmod.config_sha256(cfg)
        statemod.save(workdir, state)
        state_note = "state: stage=configured"
    else:
        state_note = "state: уже есть, не перезаписан"

    lines = ["[OK] config: %s" % target]
    if overwritten:
        lines.append(
            "[WARN] конфиг перезаписан демо-примером; прежняя версия сохранена: %s"
            % backup
        )
        if non_demo:
            lines.append(
                "[WARN] в прежнем конфиге были не-демо значения (%s) — "
                "перенесите их из бэкапа" % ", ".join(non_demo)
            )
    lines.append("[OK] %s" % state_note)
    lines.extend(_resolved_sources_note(workdir, cfg, args))

    # `--from-artifact`: обучение не прогоняется — бандл приносит готовую модель.
    # Импорт идёт после создания конфига (ему нужен jira.project для проверки
    # чужого проекта) и переводит этап в trained.
    if getattr(args, "from_artifact", None):
        code, import_lines, payload = _artifact_module().unpack(
            args.from_artifact,
            workdir,
            force=bool(args.force),
            allow_foreign_project=bool(args.allow_foreign_project),
            cfg=cfg,
        )
        lines.extend(import_lines)
        if code != EXIT_OK:
            return _finish(
                args,
                code,
                "\n".join(lines),
                config=str(target),
                state=str(state_file),
                overwritten=overwritten,
                backup=None if backup is None else str(backup),
                artifact=args.from_artifact,
            )
        return _finish(
            args,
            EXIT_OK,
            "\n".join(lines),
            config=str(target),
            state=str(state_file),
            overwritten=overwritten,
            backup=None if backup is None else str(backup),
            artifact=args.from_artifact,
            stage=payload.get("stage"),
        )

    return _finish(
        args,
        EXIT_OK,
        "\n".join(lines),
        config=str(target),
        state=str(state_file),
        overwritten=overwritten,
        backup=None if backup is None else str(backup),
    )


# ---------------------------------------------------------------------------
# resolved-sources.json
# ---------------------------------------------------------------------------


def _source_config(cfg):
    """`(sources.reference, sources.sprints)` из нормализованного конфига."""
    sources = (cfg or {}).get("sources") or {}
    if not isinstance(sources, dict):
        return [], []
    return sources.get("reference", []), sources.get("sprints", [])


def _build_resolved_sources(cfg, agent=None):
    """Собрать `resolved-sources.json` из конфига (и результата агента, если он есть).

    Без `agent` — ручной режим: `resolution_method=manual`, `confidence=low`,
    `evidence` — исходная строка конфига, `page_id`/`title` не выдумываются.
    """
    reference, sprints = _source_config(cfg)
    normalized_ref = sourcesmod.normalize_reference(reference)
    normalized_sprints = sourcesmod.normalize_sprints(sprints)
    return sourcesmod.merge_resolved(
        normalized_ref,
        normalized_sprints,
        agent,
        manual=agent is None,
        sprints_raw=sprints,
    )


def _resolved_sources_note(workdir, cfg, args):
    """Создать `resolved-sources.json` при `init` и вернуть строки диагностики."""
    path = sourcesmod.resolved_sources_path(workdir)
    display = _relative(workdir, path)
    if path.exists():
        return ["[OK] %s: уже есть, не перезаписан" % display]

    reference, sprints = _source_config(cfg)
    if not reference and not sprints:
        return [
            "[WARN] %s не создан — в конфиге нет источников: заполните "
            "sources.reference и sources.sprints и запустите `trr resolve-sources`"
            % display,
            "следующий шаг: sources.* → `trr resolve-sources` → /task-readiness-review train",
        ]

    try:
        payload = _build_resolved_sources(cfg)
        schema_lite.write_json(path, payload)
    except (sourcesmod.SourcesError, OSError) as exc:
        return [
            "[WARN] %s не создан — %s" % (display, exc),
            "следующий шаг: исправьте sources.* и запустите `trr resolve-sources`",
        ]

    code, _messages = sourcesmod.check_readiness(workdir)
    if code == 0:
        next_step = "следующий шаг: /task-readiness-review train"
    else:
        next_step = (
            "следующий шаг: заполните sources.reference и sources.sprints и "
            "запустите `trr resolve-sources --re-resolve`"
        )
    return [
        "[OK] %s: %d источников (manual, confidence=low)"
        % (display, len(payload["sources"])),
        next_step,
    ]


def _manual_only_resolved(path):
    """`True`, если файл — ручная заготовка (`resolution_method=manual` у всех).

    Такую заготовку `resolve-sources` пересобирает без `--re-resolve`: в ней нет
    работы агента, которую нельзя потерять. Файл с источниками агента (любой
    другой `resolution_method`) без `--re-resolve` не трогается.
    """
    try:
        limits.check_size(path)
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    entries = payload.get("sources")
    if not isinstance(entries, list):
        return False
    return all(
        isinstance(item, dict) and item.get("resolution_method") == "manual"
        for item in entries
    )


def cmd_resolve_sources(args):
    """`trr resolve-sources`: записать `resolved-sources.json` из конфига.

    Дополнительно (`--pages-json`) добавляет страницы, найденные агентом при
    рекурсивном обходе дерева Confluence: `sources.confluence.recursive` включает
    обход, `max_depth`/`max_pages` его ограничивают. URL вида
    `/display/SPACE/Title` не даёт page_id — такой источник остаётся в файле
    кандидатом (`confluence_search`, `confidence=low`), а команда печатает
    `[BLOCKED]` с просьбой передать page_id.
    """
    workdir = Path(args.workdir)
    config_file = configmod.config_path(workdir)
    if not config_file.is_file():
        return _finish(
            args,
            EXIT_CONFIG,
            "[MISSING] %s — сначала /task-readiness-review init" % configmod.CONFIG_FILENAME,
        )
    try:
        cfg = configmod.load_config(
            config_file, on_warning=lambda message: _emit(args, message)
        )
    except configmod.ConfigError as exc:
        return _finish(
            args,
            EXIT_CONFIG,
            "[MISSING] %s — %s" % (configmod.CONFIG_FILENAME, exc),
        )
    errors = configmod.validate_config(cfg)
    if errors:
        for error in errors:
            _emit(args, "[MISSING] %s — %s" % (configmod.CONFIG_FILENAME, error))
        return _finish(args, EXIT_CONFIG, "[MISSING] config не прошёл проверку")

    # Демо-значения из примера не блокируют resolve, но пользователь должен
    # увидеть их до train: иначе модель обучится на чужом проекте.
    for warning in configmod.demo_warnings(cfg):
        _emit(args, warning)

    path = sourcesmod.resolved_sources_path(workdir)
    display = _relative(workdir, path)
    if path.exists() and not args.re_resolve and not _manual_only_resolved(path):
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] %s уже содержит источники агента — используйте --re-resolve"
            % display,
            path=str(path),
        )

    agent = None
    if args.agent:
        agent_path = Path(args.agent)
        if not agent_path.is_absolute():
            agent_path = workdir / agent_path
        if not agent_path.is_file():
            return _finish(
                args,
                EXIT_MISSING,
                "[MISSING] %s — файл источников от агента не найден"
                % _relative(workdir, agent_path),
            )
        try:
            limits.check_size(agent_path)
            with open(agent_path, "r", encoding="utf-8") as handle:
                agent = json.load(handle)
        except (OSError, ValueError) as exc:
            return _finish(
                args,
                EXIT_SCHEMA,
                "[MISSING] %s — %s" % (_relative(workdir, agent_path), exc),
            )

    confluence = ((cfg.get("sources") or {}).get("confluence") or {})
    max_depth = int(confluence.get("max_depth") or 1)
    max_pages = int(confluence.get("max_pages") or 20)
    recursive = bool(confluence.get("recursive")) or bool(getattr(args, "recursive", False))

    pages = None
    if getattr(args, "pages_json", None):
        pages_path = Path(args.pages_json)
        if not pages_path.is_absolute():
            pages_path = workdir / pages_path
        if not pages_path.is_file():
            return _finish(
                args,
                EXIT_MISSING,
                "[MISSING] %s — файл страниц дерева не найден: сложите туда "
                "страницы Confluence ({id, title, parent_id, depth, body_excerpt})"
                % _relative(workdir, pages_path),
            )
        try:
            limits.check_size(pages_path)
            with open(pages_path, "r", encoding="utf-8") as handle:
                pages = json.load(handle)
        except (OSError, ValueError) as exc:
            return _finish(
                args,
                EXIT_SCHEMA,
                "[MISSING] %s — %s" % (_relative(workdir, pages_path), exc),
            )

    try:
        payload = _build_resolved_sources(cfg, agent)
        warnings = []
        if recursive:
            if pages is None:
                warnings.append(
                    "[WARN] sources.confluence.recursive=true, но --pages-json "
                    "не передан — дочерние страницы не добавлены"
                )
            elif max_depth < 2:
                warnings.append(
                    "[WARN] sources.confluence.max_depth=%d — добавлен только "
                    "эталон: для дочерних страниц нужно max_depth >= 2" % max_depth
                )
            else:
                payload, warnings = sourcesmod.expand_children(
                    payload, pages, max_depth=max_depth, max_pages=max_pages
                )
        elif pages is not None:
            warnings.append(
                "[WARN] --pages-json передан, но рекурсия выключена "
                "(sources.confluence.recursive=false) — дочерние страницы не добавлены"
            )
        schema_lite.write_json(path, payload)
    except (sourcesmod.SourcesError, OSError) as exc:
        return _finish(
            args, EXIT_SCHEMA, "[MISSING] %s — %s" % (display, exc), path=str(path)
        )

    for warning in warnings:
        _emit(args, warning)

    mode = "manual, confidence=low" if agent is None else "с источниками агента"
    _emit(
        args,
        "[OK] %s: %d источников (%s)" % (display, len(payload["sources"]), mode),
    )

    hints = sourcesmod.unresolved_url_hints(payload)
    for hint in hints:
        _emit(args, hint)

    code, messages = sourcesmod.check_readiness(workdir)
    if code != 0:
        for message in messages:
            _emit(args, message)
        return _finish(
            args,
            code,
            "[BLOCKED] resolve-sources: данных меньше минимума — исправьте "
            "sources.* и запустите `trr resolve-sources --re-resolve`",
            path=str(path),
        )
    if hints:
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] resolve-sources: URL страницы не разрешён в page_id — "
            "исправьте источники и запустите `trr resolve-sources --re-resolve`",
            path=str(path),
            sources=len(payload["sources"]),
        )
    return _finish(
        args,
        EXIT_OK,
        "[OK] источники готовы — следующий шаг: /task-readiness-review train",
        path=str(path),
        sources=len(payload["sources"]),
    )


# ---------------------------------------------------------------------------
# Резолв названий спринтов и полей Jira
# ---------------------------------------------------------------------------


def _read_json_argument(workdir, value, what):
    """Прочитать JSON-файл аргумента. Возвращает `(payload, сообщение, код)`."""
    path = Path(str(value))
    if not path.is_absolute():
        path = Path(workdir) / path
    display = _relative(workdir, path)
    if not path.is_file():
        return (
            None,
            "[MISSING] %s — файл не найден: %s" % (display, what),
            EXIT_MISSING,
        )
    try:
        limits.check_size(path)
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None, EXIT_OK
    except (OSError, ValueError, limits.LimitError) as exc:
        return None, "[MISSING] %s — %s" % (display, exc), EXIT_SCHEMA


def cmd_match_sprints(args):
    """`trr match-sprints --labels "<строка>" --sprints-file <json>`.

    Сопоставляет названия спринтов (как в UI Jira) с индексом `{name, id}`.
    Нужна агенту, чтобы резолвить `sources.sprints[].board_labels` до train:
    точное совпадение → нормализованное → префиксное.

    Коды: 0 — все названия найдены; 2 — есть ambiguous/missing; 4 — нет файла;
    5 — файл не разбирается или индекс не того формата.
    """
    workdir = Path(args.workdir)
    payload, problem, code = _read_json_argument(
        workdir,
        args.sprints_file,
        "индекс спринтов Jira ({name, id, state} или ответ /rest/agile/1.0/board/<id>/sprint)",
    )
    if problem is not None:
        return _finish(args, code, problem)

    try:
        result = sourcesmod.match_sprint_labels(args.labels, payload)
    except sourcesmod.SourcesError as exc:
        return _finish(args, EXIT_SCHEMA, "[MISSING] match-sprints: %s" % exc)

    for item in result["matched"]:
        _emit(
            args,
            "matched: %s → id=%s (%s)" % (item["label"], item["id"], item["name"]),
        )
    for item in result["ambiguous"]:
        _emit(
            args,
            "ambiguous: %s → %s"
            % (
                item["label"],
                ", ".join(
                    "%s (%s)" % (candidate["name"], candidate["id"])
                    for candidate in item["candidates"]
                ),
            ),
        )
    for label in result["missing"]:
        _emit(args, "missing: %s" % label)

    ok = not result["ambiguous"] and not result["missing"]
    code = EXIT_OK if ok else EXIT_BLOCKED
    if not ok:
        _emit(
            args,
            "[BLOCKED] match-sprints: %d названий не сопоставлены — проверьте "
            "названия в UI Jira и повторите"
            % (len(result["ambiguous"]) + len(result["missing"])),
        )
    else:
        _emit(
            args,
            "[OK] match-sprints: сопоставлено %d из %d"
            % (len(result["matched"]), len(result["matched"])),
        )
    _emit_json(
        args,
        {
            "status": "ok" if ok else "blocked",
            "code": code,
            "matched": result["matched"],
            "ambiguous": result["ambiguous"],
            "missing": result["missing"],
        },
    )
    return code


def cmd_match_fields(args):
    """`trr match-fields --names-json <file> --fields-file <json>`.

    Сопоставляет имена полей Jira (`Story Points` → `customfield_10004`) по
    нормализованному имени. `--names-json` — `{key: имя}` (например
    `jira.field_names`) или массив имён; `--fields-file` — ответ
    `/rest/api/2/field` или список `{id, name}`.

    Коды: 0 — все имена найдены; 2 — есть ambiguous/missing; 4 — нет файла;
    5 — файл не разбирается.
    """
    workdir = Path(args.workdir)
    names, problem, code = _read_json_argument(
        workdir, args.names_json, "имена полей Jira ({key: имя} или массив имён)"
    )
    if problem is not None:
        return _finish(args, code, problem)
    fields, problem, code = _read_json_argument(
        workdir, args.fields_file, "список полей Jira (ответ /rest/api/2/field)"
    )
    if problem is not None:
        return _finish(args, code, problem)

    try:
        result = sourcesmod.match_field_names(fields, names)
    except sourcesmod.SourcesError as exc:
        return _finish(args, EXIT_SCHEMA, "[MISSING] match-fields: %s" % exc)

    for key in sorted(result["resolved"]):
        _emit(args, "resolved: %s → %s" % (key, result["resolved"][key]))
    for name in result["missing"]:
        _emit(args, "missing: %s" % name)
    for item in result["ambiguous"]:
        _emit(
            args,
            "ambiguous: %s → %s"
            % (
                item["name"],
                ", ".join(
                    "%s (%s)" % (candidate["name"], candidate["id"])
                    for candidate in item["candidates"]
                ),
            ),
        )

    ok = not result["ambiguous"] and not result["missing"]
    code = EXIT_OK if ok else EXIT_BLOCKED
    if not ok:
        _emit(
            args,
            "[BLOCKED] match-fields: %d имён не сопоставлены — проверьте "
            "jira.field_names и список полей проекта"
            % (len(result["ambiguous"]) + len(result["missing"])),
        )
    else:
        _emit(
            args,
            "[OK] match-fields: сопоставлено %d из %d"
            % (len(result["resolved"]), len(result["resolved"])),
        )
    _emit_json(
        args,
        {
            "status": "ok" if ok else "blocked",
            "code": code,
            "resolved": result["resolved"],
            "missing": result["missing"],
            "ambiguous": result["ambiguous"],
        },
    )
    return code


def cmd_config_check(args):
    path = Path(args.config) if args.config else configmod.config_path(args.workdir)
    used_example = False
    if not path.is_file() and not args.config:
        # В каталоге самого скилла лежит только пример: проверять его — законно
        # (это проверка шаблона), но в проекте конфиг должен называться иначе.
        example = Path(args.workdir) / "task-readiness-review.example.yaml"
        if example.is_file():
            path = example
            used_example = True
    try:
        cfg = configmod.load_config(
            path, on_warning=lambda message: _emit(args, message)
        )
    except configmod.ConfigError as exc:
        return _finish(
            args, EXIT_CONFIG, "[MISSING] %s — %s" % (path, exc), config=str(path)
        )
    if used_example:
        _emit(
            args,
            "[WARN] config: проверяется пример %s — в проекте нужен %s"
            % (path.name, configmod.CONFIG_FILENAME),
        )
    errors = configmod.validate_config(cfg)
    if errors:
        for error in errors:
            _emit(args, "[MISSING] %s — %s" % (path, error))
        return _finish(args, EXIT_CONFIG, "[MISSING] config не прошёл проверку")
    checksum = configmod.config_sha256(cfg)
    return _finish(
        args,
        EXIT_OK,
        "[OK] config valid, sha256=%s" % checksum,
        config=str(path),
        sha256=checksum,
    )


def cmd_doctor(args):
    return doctormod.run(args.workdir, args)


# ---------------------------------------------------------------------------
# `trr params`: диагностика эвристических параметров задачи
# ---------------------------------------------------------------------------


def _latest_context_file(workdir, task_key):
    """Последний `context.json` прогона задачи (или None)."""
    base = Path(workdir) / statemod.STATE_DIR / "runs" / str(task_key)
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
    return (candidates[0] / "context.json") if candidates else None


def _params_context(args):
    """Снимок задачи для `trr params`: context.json прогона + флаги CLI."""
    context = {}
    task_key = getattr(args, "task", None)
    if task_key:
        path = _latest_context_file(args.workdir, task_key)
        if path is None:
            _emit(
                args,
                "[WARN] params: у задачи %s нет context.json — считаю только по "
                "переданным флагам" % task_key,
            )
        else:
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                _emit(args, "[WARN] params: %s не читается — %s" % (path, exc))
            else:
                if isinstance(loaded, dict):
                    context = loaded

    text = None
    if getattr(args, "text_file", None):
        text = Path(args.text_file).read_text(encoding="utf-8")
    elif getattr(args, "text", None) is not None:
        text = args.text
    if text is not None:
        context["description"] = text

    if getattr(args, "issue_type", None):
        context["issue_type"] = args.issue_type
    if getattr(args, "role", None):
        context["role"] = args.role

    labels = getattr(args, "labels", None)
    if labels:
        extra = [item.strip() for item in str(labels).split(",") if item.strip()]
        current = context.get("labels")
        if isinstance(current, str):
            current = [item.strip() for item in current.split(",") if item.strip()]
        elif isinstance(current, (list, tuple)):
            current = [str(item) for item in current]
        else:
            current = []
        context["labels"] = current + [item for item in extra if item not in current]

    if getattr(args, "links", None) is not None:
        fields = context.get("fields")
        if not isinstance(fields, dict):
            fields = {}
            context["fields"] = fields
        fields["issuelinks"] = int(args.links)

    for name in ("weight", "heat", "connectivity"):
        value = getattr(args, name, None)
        if value is not None:
            context[name] = float(value)
    return context


def cmd_params(args):
    """`trr params`: значения, source, evidence и множитель — без похода в Jira."""
    try:
        context = _params_context(args)
    except OSError as exc:
        return _finish(args, EXIT_MISSING, "[MISSING] params --text-file: %s" % exc)

    cfg = None
    config_file = configmod.config_path(args.workdir)
    if config_file.is_file():
        try:
            cfg = configmod.load_config(config_file)
        except configmod.ConfigError as exc:
            _emit(args, "[WARN] params: конфиг не читается (%s) — беру дефолты" % exc)

    result = paramsmod.derive(context, cfg)
    value = paramsmod.multiplier(result, cfg)

    lines = [
        "[OK] params: weight=%.2f heat=%.2f connectivity=%.2f multiplier=%.4f"
        % (
            result["weight"]["value"],
            result["heat"]["value"],
            result["connectivity"]["value"],
            value,
        )
    ]
    lines.extend(paramsmod.evidence_lines(result))
    return _finish(
        args,
        EXIT_OK,
        "\n".join(lines),
        params=result,
        multiplier=value,
        context_keys=sorted(context),
    )


def cmd_state_get(args):
    try:
        state = statemod.load(args.workdir)
    except statemod.StateError as exc:
        return _finish(args, EXIT_MISSING, "[MISSING] state.json — %s" % exc)
    try:
        value = _dig(state, args.key)
    except KeyError:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] state.%s — ключа нет в state.json" % args.key,
        )
    _emit(args, _format_value(value))
    _emit_json(args, {"status": "ok", "code": EXIT_OK, "key": args.key, "value": value})
    return EXIT_OK


def cmd_state_set(args):
    try:
        state = statemod.load(args.workdir)
    except statemod.StateError as exc:
        return _finish(args, EXIT_MISSING, "[MISSING] state.json — %s" % exc)
    try:
        value = json.loads(args.value)
    except ValueError:
        value = args.value
    _assign(state, args.key, value)
    state["updated_at"] = statemod.now_utc()
    try:
        statemod.save(args.workdir, state)
    except statemod.StateError as exc:
        return _finish(args, EXIT_CONFIG, "[MISSING] state.json — %s" % exc)
    return _finish(args, EXIT_OK, "[OK] state.%s" % args.key, key=args.key)


def cmd_validate(args):
    if args.artifact not in schema_lite.SCHEMA_NAMES:
        # Неизвестный артефакт — это SCHEMA_ERROR (5), а не ошибка конфига:
        # конфиг тут ни при чём, сломано имя артефакта.
        return _finish(
            args,
            EXIT_SCHEMA,
            "[BLOCKED] артефакт %r неизвестен — допустимы: %s"
            % (args.artifact, ", ".join(schema_lite.SCHEMA_NAMES)),
        )
    path = Path(args.path)
    if not path.is_file():
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s — файла нет, сначала создайте артефакт" % path,
        )
    if args.artifact == "config":
        # Конфиг — YAML; читаем его тем же путём, что и config-check
        # (с подстановкой дефолтов), чтобы проверка шаблона не расходилась с рантаймом.
        # Не разбирается/не читается — CONFIG_ERROR (3), а не SCHEMA_ERROR.
        try:
            instance = configmod.load_config(path)
        except configmod.ConfigError as exc:
            return _finish(args, EXIT_CONFIG, "[BLOCKED] %s — %s" % (path, exc))
    else:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                instance = json.load(handle)
        except (OSError, ValueError) as exc:
            return _finish(
                args,
                EXIT_SCHEMA,
                "[MISSING] %s — невалидный JSON: %s" % (path, exc),
            )
    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, args.artifact)
    except schema_lite.SchemaError as exc:
        return _finish(args, EXIT_SCHEMA, "[MISSING] схема — %s" % exc)
    errors = schema_lite.validate(instance, schema)
    if errors:
        for error in errors:
            _emit(args, "[MISSING] %s — %s" % (path, error))
        return _finish(
            args,
            EXIT_SCHEMA,
            "[MISSING] %s не соответствует схеме %s (%d ошибок)"
            % (path, args.artifact, len(errors)),
        )
    return _finish(
        args,
        EXIT_OK,
        "[OK] %s соответствует схеме %s" % (path, args.artifact),
        artifact=args.artifact,
    )


def cmd_render_norm(args):
    """`trr render-norm`: перерендерить `.md`-зеркала из существующих JSON.

    Ничего не пересчитывает и не валидирует заново: только читает
    `norm/reference-estimates.json`, `norm/sprint-stats.json`,
    `model/estimation-model.json` и пишет рядом `reference-estimates.md`,
    `sprint-stats.md`, `estimation-model.md`. Нет хотя бы одного JSON — код 4
    (`MISSING_ARTIFACT`); ошибка рендера — код 2.
    """
    workdir = Path(args.workdir)
    base = workdir / statemod.STATE_DIR
    artifacts = (
        ("norm/reference-estimates.json", base / "norm" / "reference-estimates.json"),
        ("norm/sprint-stats.json", base / "norm" / "sprint-stats.json"),
        ("model/estimation-model.json", base / "model" / "estimation-model.json"),
    )
    payloads, missing = [], []
    for display, path in artifacts:
        if not path.is_file():
            missing.append("%s — запустите /task-readiness-review train" % display)
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payloads.append(json.load(handle))
        except (OSError, ValueError) as exc:
            missing.append("%s — %s" % (display, exc))
    if missing:
        for item in missing:
            _emit(args, "[MISSING] %s" % item)
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] render-norm: нет %d из %d артефактов"
            % (len(missing), len(artifacts)),
        )

    from trr_impl import report as reportmod

    reference, stats, model = payloads
    sample = _read_json_optional(base / "norm" / "sprint-sample.json")
    state = _read_json_optional(base / "state.json")
    try:
        cfg = configmod.load_config(
            configmod.config_path(workdir),
            on_warning=lambda message: _emit(args, message),
        )
    except configmod.ConfigError:
        cfg = None
    try:
        targets = [
            reportmod.write(
                base / "norm",
                reportmod.render_reference_estimates(reference),
                "reference-estimates.md",
            ),
            reportmod.write(
                base / "norm",
                reportmod.render_sprint_stats(stats),
                "sprint-stats.md",
            ),
            reportmod.write(
                base / "model",
                reportmod.render_model_page(
                    model,
                    reportmod.model_template(workdir),
                    reference=reference,
                    stats=stats,
                    sample=sample,
                    cfg=cfg,
                    state=state,
                ),
                "estimation-model.md",
            ),
        ]
    except (OSError, ValueError) as exc:
        return _finish(args, EXIT_BLOCKED, "[BLOCKED] render-norm: %s" % exc)

    rendered = [_relative(workdir, path) for path in targets]
    for display in rendered:
        _emit(args, "[OK] %s" % display)
    return _finish(
        args,
        EXIT_OK,
        "[OK] render-norm: %d файла" % len(rendered),
        rendered=rendered,
    )


def cmd_model_hash(args):
    path = statemod.model_path(args.workdir)
    display = _relative(args.workdir, path)
    if not path.is_file():
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s — запустите /task-readiness-review train" % display,
        )
    try:
        checksum = statemod.model_checksum(args.workdir)
        with open(path, "r", encoding="utf-8") as handle:
            model = json.load(handle)
    except (statemod.StateError, OSError, ValueError) as exc:
        return _finish(args, EXIT_SCHEMA, "[MISSING] %s — %s" % (display, exc))
    version = model.get("version")
    return _finish(
        args,
        EXIT_OK,
        "sha256:%s version:%s" % (checksum, version),
        sha256=checksum,
        version=version,
    )


def cmd_model_page_payload(args):
    """`trr model-page-payload`: готовое тело страницы модели для Confluence.

    Три формата:
      `md`      — `.task-readiness/model/estimation-model.md` как есть;
      `storage` — тот же текст, сконвертированный в Confluence storage XHTML;
      `json`    — тело запроса `POST`/`PUT` (`action`, `page_id`, `title`,
                  `space`, `parent_id`, `version`/`page_version`,
                  `model_version`, `body_storage`, `model_checksum`,
                  `body_sha256`, `body_bytes`).

    `action` определяется по `state.model_page`: есть `id` — `update`, иначе
    `create` с `version=1`. Версия страницы и версия модели — разные числа:
    `state.model_page.version` хранит версию **модели** (её пишет `publish
    --model`), поэтому для `PUT` нужна явная `--page-version` — фактическая
    версия страницы из `GET ?expand=version` + 1. Без флага версия берётся из
    state (совместимость) и печатается `[WARN]` о ручной сверке.

    В JSON-полезной нагрузке версии разделены: `model_version` — версия модели,
    `page_version` — версия страницы для `PUT` (`version` оставлен как её
    синоним для тела запроса).

    Ничего не публикует и не пишет в state: только готовит тело. Публикует
    агент (REST) и затем фиксирует факт `trr publish --model … --no-stage`.
    """
    workdir = Path(args.workdir)
    base = workdir / statemod.STATE_DIR
    model_path = base / "model" / "estimation-model.json"
    display = _relative(workdir, model_path)
    if not model_path.is_file():
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s — запустите /task-readiness-review train" % display,
        )
    model = _read_json_optional(model_path)
    if model is None:
        return _finish(args, EXIT_SCHEMA, "[MISSING] %s — не читается" % display)

    md_path = base / "model" / "estimation-model.md"
    if md_path.is_file():
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError as exc:
            return _finish(
                args,
                EXIT_MISSING,
                "[MISSING] %s — %s" % (_relative(workdir, md_path), exc),
            )
    else:
        # Артефакта нет — рендерим из JSON в память: публиковать пустую страницу
        # нельзя, а требовать ручной `render-norm` перед каждой публикацией —
        # лишний шаг, на котором легко ошибиться.
        from trr_impl import report as reportmod

        try:
            cfg = configmod.load_config(configmod.config_path(workdir))
        except configmod.ConfigError:
            cfg = None
        try:
            text = reportmod.render_model_page(
                model,
                reportmod.model_template(workdir),
                reference=_read_json_optional(base / "norm" / "reference-estimates.json"),
                stats=_read_json_optional(base / "norm" / "sprint-stats.json"),
                sample=_read_json_optional(base / "norm" / "sprint-sample.json"),
                cfg=cfg,
                state=_read_json_optional(base / "state.json"),
            )
        except (OSError, ValueError) as exc:
            return _finish(
                args,
                EXIT_BLOCKED,
                "[BLOCKED] model-page-payload: страница модели не рендерится — %s"
                % exc,
            )
        _emit(
            args,
            "[WARN] %s отсутствует — страница отрендерена из JSON в память"
            % _relative(workdir, md_path),
        )

    payload = None
    if args.format == "md":
        content = text
    elif args.format == "storage":
        from trr_impl import mdstorage

        content = mdstorage.convert(text)
    else:
        from trr_impl import mdstorage

        try:
            cfg = configmod.load_config(configmod.config_path(workdir))
        except configmod.ConfigError as exc:
            return _finish(
                args,
                EXIT_CONFIG,
                "[MISSING] %s — %s" % (configmod.CONFIG_FILENAME, exc),
            )
        confluence = ((cfg.get("output") or {}).get("confluence") or {})
        state = statemod.load(workdir)
        model_page = state.get("model_page") or {}
        page_id = model_page.get("id")
        action = "update" if page_id else "create"
        model_version = model.get("version")
        page_version = args.page_version
        if action == "create":
            if page_version not in (None, 1):
                sys.stderr.write(
                    "[WARN] action=create: --page-version %s игнорируется — "
                    "у новой страницы version=1\n" % page_version
                )
            page_version = 1
        elif page_version is None:
            page_version = model_page.get("version")
            sys.stderr.write(
                "[WARN] --page-version не задан: page_version=%s взята из "
                "state.model_page.version (это версия МОДЕЛИ). Перед PUT сверьте "
                "фактическую версию страницы GET /rest/api/content/%s"
                "?expand=version и передайте --page-version <фактическая+1>\n"
                % (page_version, page_id)
            )
        title = args.title or "Модель оценки Story Points (версия %s)" % model_version
        body = mdstorage.convert(text)
        body_bytes = len(body.encode("utf-8"))
        payload = {
            "action": action,
            "page_id": str(page_id) if page_id else None,
            "title": title,
            "space": confluence.get("space"),
            "parent_id": confluence.get("page_id"),
            "version": page_version if page_version is not None else 1,
            "page_version": page_version if page_version is not None else 1,
            "model_version": model_version,
            "body_storage": body,
            "model_checksum": model.get("checksum"),
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "body_bytes": body_bytes,
        }
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    if args.out:
        target = Path(args.out)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                content if content.endswith("\n") else content + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            return _finish(
                args, EXIT_MISSING, "[MISSING] %s — %s" % (args.out, exc)
            )
        summary = "[OK] model-page-payload: %s (%s, %d байт)" % (
            args.out,
            args.format,
            len(content.encode("utf-8")),
        )
        if payload is not None:
            summary += " action=%s page_version=%s model_version=%s" % (
                payload["action"],
                payload["page_version"],
                payload["model_version"],
            )
        return _finish(
            args,
            EXIT_OK,
            summary,
            path=str(target),
            format=args.format,
            action=payload["action"] if payload else None,
            version=payload["version"] if payload else None,
            page_version=payload["page_version"] if payload else None,
            model_version=payload["model_version"] if payload else None,
            body_sha256=payload["body_sha256"] if payload else None,
            body_bytes=payload["body_bytes"] if payload else None,
        )

    print(content)
    return EXIT_OK


def cmd_publish(args):
    """`trr publish`: комментарии в задачу Jira — по умолчанию.

    Поведение по умолчанию (`jira.comment_mode: post`): собрать ДВА
    комментария — «Результаты валидации» (готовность) и «Результаты оценки»
    (SP) — и опубликовать их в задачу. Python в Jira не пишет, поэтому команда
    готовит тела (`jira-validation.md` и `jira-estimate.md` рядом с
    артефактами), печатает по плану `create`/`update` на каждый и следующий
    шаг: агент публикует тексты через MCP Jira, затем фиксирует id через
    `trr publish --task <KEY> --comment-id-validation <id>
    --comment-id-estimate <id>`. Есть id в state — план говорит `update`: тот
    же комментарий обновляется, второй не создаётся.

    Флаги:
      `--plan-jira`  — только напечатать планы, ничего не писать;
      `--draft`      — только напечатать тексты комментариев (state не меняется);
      `--no-jira`    — не публиковать в Jira: тексты уходят в
                       `actions/jira-validation.md` и `actions/jira-estimate.md`
                       (деградация, код 0);
      `--comment-id-validation` / `--comment-id-estimate` — записать id уже
                       опубликованных агентом комментариев (легаси
                       `--comment-id` = `--comment-id-estimate`).

    `--target confluence|obsidian` — прежняя публикация страницы/заметки; она
    выполняется ПОСЛЕ комментариев в Jira и остаётся дополнительной.
    Недоступность Jira — деградация: `[WARN]`, тексты в `actions/`, код 0.
    """
    workdir = Path(args.workdir)
    try:
        statemod.load(workdir)
    except statemod.StateError as exc:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] state.json — %s; запустите /task-readiness-review init" % exc,
        )

    if args.model and args.target is None:
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] publish --model: укажите --target confluence|obsidian — "
            "страница модели публикуется не комментарием",
        )
    if not args.task and args.target is None:
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] publish: укажите --task <KEY> (комментарий в задачу) или "
            "--target confluence|obsidian (страница/заметка)",
        )

    lines = []
    payload = {}

    # 1. Комментарий в задачу Jira — поведение по умолчанию.
    if args.task and not args.no_jira:
        code, jira_lines, jira_payload = _publish_jira(args, workdir)
        lines.extend(jira_lines)
        payload.update(jira_payload)
        if code is not None:
            return _finish(args, code, "\n".join(lines), **payload)
    elif args.task:
        code, jira_lines, jira_payload = _skip_jira(args, workdir)
        lines.extend(jira_lines)
        payload.update(jira_payload)
        if code is not None:
            return _finish(args, code, "\n".join(lines), **payload)

    # 2. Дополнительная публикация страницы/заметки (`--target`).
    if args.target is not None:
        code, page_lines, page_payload = _publish_page(args, workdir)
        lines.extend(page_lines)
        payload.update(page_payload)
        if code is not None:
            return _finish(args, code, "\n".join(lines), **payload)

    return _finish(args, EXIT_OK, "\n".join(lines), **payload)


def _comment_mode(workdir, args):
    """`jira.comment_mode` из конфига; нет конфига — дефолт (`post`)."""
    path = configmod.config_path(workdir)
    if not path.is_file():
        return configmod.DEFAULTS["jira"]["comment_mode"]
    try:
        cfg = configmod.load_config(path, on_warning=lambda message: _emit(args, message))
    except configmod.ConfigError:
        return configmod.DEFAULTS["jira"]["comment_mode"]
    mode = ((cfg.get("jira") or {}).get("comment_mode") or "").strip()
    return mode or configmod.DEFAULTS["jira"]["comment_mode"]


def _plan_line(info):
    return "[PLAN] jira comment (%s): %s (comment_id=%s, chars=%d, marker=%s)" % (
        info["kind"],
        info["action"],
        info["comment_id"] or "-",
        info["chars"],
        info["marker"],
    )


def _comment_ids(args, publishmod):
    """Пары `(вид, comment_id)` из флагов; легаси `--comment-id` — это оценка."""
    pairs = []
    validation = getattr(args, "comment_id_validation", None)
    if validation:
        pairs.append((publishmod.KIND_VALIDATION, validation))
    estimate = getattr(args, "comment_id_estimate", None) or getattr(args, "comment_id", None)
    if estimate:
        pairs.append((publishmod.KIND_ESTIMATE, estimate))
    return pairs


def _publish_jira(args, workdir):
    """Шаг «комментарии в задачу». Возвращает (код|None, строки, payload).

    По умолчанию планируются ДВА комментария: сначала «Результаты валидации»
    (готовность), затем «Результаты оценки» (SP). У каждого свой маркер и свой
    `ref` в `state.published[]`, поэтому повторная публикация обновляет оба
    комментария, а не создаёт дубли.
    """
    from trr_impl import publish as publishmod

    task_key = args.task

    # Агент уже опубликовал комментарии — остаётся записать id.
    ids = _comment_ids(args, publishmod)
    if ids:
        lines = []
        publications = []
        for kind, comment_id in ids:
            try:
                entry = publishmod.record(
                    workdir,
                    task_key,
                    comment_id,
                    args.url,
                    kind=kind,
                    run=getattr(args, "run", None),
                )
            except publishmod.MissingReport as exc:
                return EXIT_MISSING, ["[MISSING] %s" % exc], {}
            except statemod.StateError as exc:
                return (
                    EXIT_BLOCKED,
                    ["[BLOCKED] publish: %s — проверьте .task-readiness/state.json" % exc],
                    {},
                )
            lines.append(
                "[OK] publish: jira %s comment_id=%s (sha256:%s)"
                % (entry["ref"], entry["comment_id"], entry["content_sha256"][:12])
            )
            publications.append(
                {
                    "kind": kind,
                    "ref": entry["ref"],
                    "comment_id": entry["comment_id"],
                    "url": entry["url"],
                    "content_sha256": entry["content_sha256"],
                }
            )
        lines.append("[OK] stage=published")
        return (
            None,
            lines,
            {"target": "jira", "publications": publications},
        )

    # План: только напечатать (--plan-jira / --draft ничего не пишут на диск).
    write_body = not (args.plan_jira or args.draft)
    run = getattr(args, "run", None)
    try:
        infos = publishmod.plan(workdir, task_key, write_body=write_body, run=run)
    except publishmod.MissingReport as exc:
        return EXIT_MISSING, ["[MISSING] %s" % exc], {}
    except statemod.StateError as exc:
        return EXIT_MISSING, ["[MISSING] state.json — %s" % exc], {}

    plan_lines = [_plan_line(info) for info in infos]
    if args.plan_jira:
        return EXIT_OK, plan_lines, _jira_payload(infos)

    if args.draft:
        lines = list(plan_lines)
        lines.append(
            "[OK] --draft: комментарии только напечатаны, state не изменён"
        )
        for info in infos:
            lines.extend(["", "### %s" % info["kind"], "", info["body"]])
        return EXIT_OK, lines, {}

    mode = _comment_mode(workdir, args)
    if mode == "draft":
        return (
            EXIT_OK,
            plan_lines
            + [
                "[WARN] jira.comment_mode: draft — комментарии не отправляются; "
                "поставьте post, чтобы публиковать результат в задачу"
            ],
            _jira_payload(infos),
        )

    lines = list(plan_lines)
    for info in infos:
        lines.append(
            "[OK] тело комментария (%s): %s (sha256:%s)"
            % (info["kind"], info["body_path"], info["body_sha256"][:12])
        )
    lines.append(
        "[OK] следующий шаг: опубликуйте оба текста через MCP Jira "
        "(создать новый или обновить существующий по маркеру) и зафиксируйте id:"
    )
    for info in infos:
        flag = (
            "--comment-id-validation"
            if info["kind"] == publishmod.KIND_VALIDATION
            else "--comment-id-estimate"
        )
        lines.append("    trr publish --task %s %s <id>" % (task_key, flag))
    return None, lines, _jira_payload(infos)


def _skip_jira(args, workdir):
    """`--no-jira`: комментарии не публикуются, тексты уходят в action-пакеты.

    Это и есть деградация «Jira недоступна»: работа не падает (код 0), готовые
    тексты и точный список шагов лежат в `actions/jira-validation.md` и
    `actions/jira-estimate.md`, а в state ничего не пишется — публикации не было.
    """
    from trr_impl import publish as publishmod

    task_key = args.task
    run = getattr(args, "run", None)
    lines = ["[WARN] комментарии в Jira не публикуются (--no-jira)"]
    try:
        infos = publishmod.plan(workdir, task_key, run=run)
    except (publishmod.MissingReport, statemod.StateError) as exc:
        lines.append("[WARN] тексты не подготовлены: %s" % exc)
        return None, lines, {}
    payload = _jira_payload(infos)
    for info in infos:
        try:
            path = publishmod.write_action_package(
                workdir,
                task_key,
                info["body"],
                "--no-jira: Jira недоступна или запись в неё отключена",
                kind=info["kind"],
                # Прогон берётся из `--run` (или последний): `write_action_package`
                # не должен сам угадывать каталог по имени RUN-ID.
                run=run,
            )
        except publishmod.MissingReport as exc:
            lines.append(
                "[WARN] action-пакет (%s) не записан: %s" % (info["kind"], exc)
            )
            continue
        lines.append(
            "[OK] текст для ручной публикации (%s): %s"
            % (info["kind"], _relative(workdir, path))
        )
    return None, lines, payload


def _jira_payload(infos):
    """JSON-полезная нагрузка плана: по элементу на вид комментария."""
    comments = [
        {
            "kind": info["kind"],
            "ref": info["ref"],
            "action": info["action"],
            "comment_id": info["comment_id"],
            "marker": info["marker"],
            "body_path": info["body_path"],
            "chars": info["chars"],
            "body_sha256": info["body_sha256"],
        }
        for info in infos
    ]
    return {
        "target": "jira",
        "comments": comments,
        # Первый комментарий — валидация: прежние ключи верхнего уровня
        # сохраняют форму ответа для тех, кто читает одно поле.
        "action": comments[0]["action"] if comments else None,
        "comment_id": comments[0]["comment_id"] if comments else None,
        "marker": comments[0]["marker"] if comments else None,
        "body_path": comments[0]["body_path"] if comments else None,
        "chars": comments[0]["chars"] if comments else None,
        "body_sha256": comments[0]["body_sha256"] if comments else None,
    }


def _publish_page(args, workdir):
    """Шаг «страница/заметка» (`--target`). Возвращает (код|None, строки, payload)."""
    if not (args.ref and args.url and args.file):
        return (
            EXIT_MISSING,
            ["[MISSING] publish --target: нужны --ref, --url и --file"],
            {},
        )

    if args.model:
        model_file = statemod.model_path(workdir)
        if not model_file.is_file():
            return (
                EXIT_MISSING,
                [
                    "[MISSING] %s — запустите /task-readiness-review train"
                    % _relative(workdir, model_file)
                ],
                {},
            )

    path = Path(args.file)
    if not path.is_absolute():
        path = workdir / path
    display = _relative(workdir, path)
    if not path.is_file():
        return (
            EXIT_MISSING,
            [
                "[MISSING] %s — сначала отрендерите артефакт: report.md делает "
                "/task-readiness-review estimate, estimation-model.md — "
                "/task-readiness-review train" % display
            ],
            {},
        )
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        return EXIT_MISSING, ["[MISSING] %s — %s" % (display, exc)], {}

    # `action` — по факту наличия записи в state.published[]: повторная
    # публикация того же `(target, ref)` обновляет запись (идемпотентный
    # upsert), поэтому второй прогон не создаёт вторую публикацию.
    try:
        before = statemod.load(workdir)
    except statemod.StateError as exc:
        return (
            EXIT_BLOCKED,
            ["[BLOCKED] publish: %s — проверьте .task-readiness/state.json" % exc],
            {},
        )
    previous = None
    for item in before.get("published") or []:
        if isinstance(item, dict) and (
            item.get("target"),
            item.get("ref"),
        ) == (str(args.target), str(args.ref)):
            previous = item
            break
    action = "update" if previous is not None else "create"

    try:
        entry = statemod.add_publication(
            str(workdir),
            args.target,
            args.ref,
            args.url,
            digest,
            mark_published=not args.no_stage,
        )
    except statemod.StateError as exc:
        return (
            EXIT_BLOCKED,
            ["[BLOCKED] publish: %s — проверьте .task-readiness/state.json" % exc],
            {},
        )

    lines = [
        "[OK] publish: %s %s action=%s (sha256:%s)"
        % (entry["target"], entry["ref"], action, digest)
    ]
    if args.no_stage:
        lines.append("[OK] stage не изменён (--no-stage)")
    else:
        lines.append("[OK] stage=published")

    payload = {
        "target": entry["target"],
        "ref": entry["ref"],
        "url": entry["url"],
        "action": action,
        "content_sha256": digest,
        "stage": "published" if not args.no_stage else None,
    }

    if args.model:
        try:
            with open(statemod.model_path(workdir), "r", encoding="utf-8") as handle:
                model = json.load(handle)
            checksum = statemod.model_checksum(workdir)
        except (OSError, ValueError, statemod.StateError) as exc:
            return (
                EXIT_SCHEMA,
                [
                    "[MISSING] %s — %s"
                    % (_relative(workdir, statemod.model_path(workdir)), exc)
                ],
                {},
            )
        state = statemod.load(workdir)
        state["model_page"] = {
            "system": args.target,
            "id": str(args.ref),
            "url": str(args.url),
            "hash": checksum,
            "version": int(model.get("version")),
        }
        state["updated_at"] = statemod.now_utc()
        statemod.save(workdir, state)
        # Зеркало: у публикации страницы модели две разные величины — sha256
        # файла (`content_sha256`, уже записан `add_publication`) и контрольная
        # сумма модели. Вторую знает только этот шаг.
        storemod.save_publication(
            workdir,
            None,
            str(args.target),
            str(args.ref),
            str(args.url),
            digest,
            checksum,
        )
        lines.append("[OK] model_page: v%s %s" % (model.get("version"), args.url))

    return None, lines, payload



# ---------------------------------------------------------------------------
# artifact: экспорт/импорт обученных артефактов
# ---------------------------------------------------------------------------


def _artifact_module():
    """Модуль `artifact` (импортируется лениво: тянет `stats`)."""
    from trr_impl import artifact as artifactmod

    return artifactmod


def _load_cfg(workdir, args):
    """Прочитать конфиг для `artifact …`; None — уже напечатана ошибка."""
    try:
        return configmod.load_config(
            configmod.config_path(workdir),
            on_warning=lambda message: _emit(args, message),
        )
    except configmod.ConfigError as exc:
        return None


def cmd_artifact_pack(args):
    """`trr artifact pack [--out PATH] [--no-sprint-sample]`."""
    cfg = _load_cfg(args.workdir, args)
    if cfg is None:
        return _finish(
            args,
            EXIT_CONFIG,
            "[MISSING] %s — сначала /task-readiness-review init"
            % configmod.CONFIG_FILENAME,
        )
    include_sample = not args.no_sprint_sample and bool(
        (cfg.get("artifacts") or {}).get("include_sprint_sample", True)
    )
    code, lines, payload = _artifact_module().pack(
        args.workdir,
        out=args.out,
        include_sprint_sample=include_sample,
        cfg=cfg,
    )
    for line in lines:
        _emit(args, line)
    _emit_json(args, dict(payload, status="ok" if code == 0 else "blocked", code=code))
    return code


def cmd_artifact_inspect(args):
    """`trr artifact inspect <file>`: сводка манифеста."""
    code, lines, payload = _artifact_module().inspect(args.file)
    for line in lines:
        _emit(args, line)
    _emit_json(args, dict(payload, status="ok" if code == 0 else "blocked", code=code))
    return code


def cmd_artifact_unpack(args):
    """`trr artifact unpack <file> [--force] [--allow-foreign-project]`."""
    cfg = _load_cfg(args.workdir, args)
    if cfg is None:
        return _finish(
            args,
            EXIT_CONFIG,
            "[MISSING] %s — сначала /task-readiness-review init"
            % configmod.CONFIG_FILENAME,
        )
    code, lines, payload = _artifact_module().unpack(
        args.file,
        args.workdir,
        force=bool(args.force),
        allow_foreign_project=bool(args.allow_foreign_project),
        cfg=cfg,
    )
    for line in lines:
        _emit(args, line)
    _emit_json(args, dict(payload, status="ok" if code == 0 else "blocked", code=code))
    return code


def cmd_artifact_plan(args):
    """`trr artifact plan --target <t>`: куда публиковать бандл."""
    cfg = _load_cfg(args.workdir, args)
    if cfg is None:
        return _finish(
            args,
            EXIT_CONFIG,
            "[MISSING] %s — сначала /task-readiness-review init"
            % configmod.CONFIG_FILENAME,
        )
    code, lines, payload = _artifact_module().plan(args.workdir, cfg, args.target)
    for line in lines:
        _emit(args, line)
    _emit_json(args, dict(payload, status="ok" if code == 0 else "blocked", code=code))
    return code


def cmd_artifact_record(args):
    """`trr artifact record --target <t> --ref <ref> --url <url> [--file PATH]`."""
    code, lines, payload = _artifact_module().record(
        args.workdir, args.target, args.ref, args.url, file=args.file
    )
    for line in lines:
        _emit(args, line)
    _emit_json(args, dict(payload, status="ok" if code == 0 else "blocked", code=code))
    return code


# ---------------------------------------------------------------------------
# `trr db`: локальное SQLite-зеркало
# ---------------------------------------------------------------------------


def _fmt_bytes(size):
    """Размер файла человекочитаемо (Б/КБ/МБ)."""
    value = float(size or 0)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            return "%.0f %s" % (value, unit) if unit == "Б" else "%.1f %s" % (value, unit)
        value /= 1024.0
    return "%.1f ГБ" % value


def _print_table(columns, rows):
    """Напечатать результат `db query` таблицей с выравниванием по колонкам."""
    if not columns:
        return
    rendered = []
    for row in rows:
        rendered.append(
            ["NULL" if value is None else str(value) for value in row]
        )
    widths = [len(str(column)) for column in columns]
    for row in rendered:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print("  ".join(str(column).ljust(widths[index]) for index, column in enumerate(columns)))
    print("  ".join("-" * width for width in widths))
    for row in rendered:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _db_config(args):
    """`(cfg, None)` для `db …`; `(None, код)` — ошибка уже напечатана."""
    cfg = _load_cfg(args.workdir, args)
    if cfg is None:
        return None, _finish(
            args,
            EXIT_CONFIG,
            "[MISSING] %s — сначала /task-readiness-review init"
            % configmod.CONFIG_FILENAME,
        )
    for message in configmod.storage_warnings(cfg):
        _emit(args, message)
    if not (cfg.get("storage") or {}).get("sqlite", {}).get("enabled", True):
        return None, _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] db: storage.sqlite.enabled=false — зеркало выключено "
            "(включите блок storage.sqlite в конфиге)",
        )
    return cfg, None


def cmd_db(args):
    """`trr db init|check|ingest|stats|export|query`."""
    workdir = Path(args.workdir)
    cfg, code = _db_config(args)
    if cfg is None:
        return code
    command = getattr(args, "db_command", None)
    if command == "init":
        return _db_init(args, workdir, cfg)
    if command == "check":
        return _db_check(args, workdir, cfg)
    if command == "ingest":
        return _db_ingest(args, workdir, cfg)
    if command == "stats":
        return _db_stats(args, workdir, cfg)
    if command == "export":
        return _db_export(args, workdir, cfg)
    if command == "query":
        return _db_query(args, workdir, cfg)
    return _finish(
        args,
        EXIT_BLOCKED,
        "[BLOCKED] db: нужна подкоманда init, check, ingest, stats, export или query",
    )


def _db_init(args, workdir, cfg):
    result = storemod.init_db(workdir, cfg)
    if not result.get("enabled", True) or result.get("error"):
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] db init: %s"
            % (result.get("error") or "storage.sqlite.enabled=false"),
        )
    suffix = ""
    if result.get("migrated"):
        suffix = " (миграция схемы %d → %d)" % (
            int(result.get("before_version") or 0),
            int(result["user_version"]),
        )
    elif not result["created"]:
        suffix = " (уже существует, схема не менялась)"
    line = "[OK] db init: %s, user_version=%d%s" % (
        result["path"],
        result["user_version"],
        suffix,
    )
    return _finish(
        args,
        EXIT_OK,
        line,
        path=result["path"],
        user_version=result["user_version"],
        before_version=result.get("before_version"),
        migrated=result.get("migrated"),
        created=result["created"],
    )


def _db_check(args, workdir, cfg):
    conn = storemod.connect_readonly(workdir, cfg)
    if conn is None:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] db — файла нет или он не открывается: %s"
            % storemod.path_for(workdir, cfg),
        )
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        integrity = str(row[0]) if row is not None else "unknown"
        snapshot = storemod.stats(conn)
    except sqlite3.Error as exc:
        return _finish(args, EXIT_SCHEMA, "[MISSING] db check: %s" % exc)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    code = EXIT_OK if integrity == "ok" else EXIT_SCHEMA
    lines = [
        "[%s] db check: integrity_check=%s, user_version=%d, size=%s, tables=%d"
        % (
            "OK" if code == EXIT_OK else "MISSING",
            integrity,
            snapshot["user_version"],
            _fmt_bytes(snapshot["size_bytes"]),
            len(snapshot["tables"]),
        )
    ]
    for name in storemod.TABLES:
        lines.append("  %-18s %d" % (name, snapshot["tables"].get(name, 0)))
    return _finish(
        args,
        code,
        "\n".join(lines),
        integrity=integrity,
        user_version=snapshot["user_version"],
        size_bytes=snapshot["size_bytes"],
        tables=snapshot["tables"],
    )


def _db_ingest(args, workdir, cfg):
    result = storemod.ingest_workdir(workdir, cfg)
    for warning in result.get("warnings") or []:
        _emit(args, "[WARN] db ingest: %s" % warning)
    tables = result.get("tables") or {}
    if not tables:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] db ingest — зеркало недоступно: %s" % result.get("path"),
            path=result.get("path"),
        )
    keys = (
        "reference_buckets",
        "reference_levels",
        "sprint_rows",
        "sprint_stats",
        "model_buckets",
        "gap_rules",
        "model_versions",
        "runs",
        "validations",
        "estimates",
        "estimate_roles",
        "vectors",
        "publications",
    )
    summary = ", ".join("%s=%d" % (key, tables.get(key, 0)) for key in keys)
    line = "[OK] db ingest: %s, user_version=%d, %s" % (
        result.get("path"),
        result.get("user_version", 0),
        summary,
    )
    removed = int(result.get("orphan_roles_removed") or 0)
    if removed:
        line = "%s, сирот estimate_roles удалено: %d" % (line, removed)
    return _finish(
        args,
        EXIT_OK,
        line,
        path=result.get("path"),
        created=result.get("created"),
        user_version=result.get("user_version"),
        tables=tables,
        orphan_roles_removed=removed,
        warnings=result.get("warnings") or [],
    )


def _db_stats(args, workdir, cfg):
    conn = storemod.connect_readonly(workdir, cfg)
    if conn is None:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] db — файла нет: запустите `trr db init` (%s)"
            % storemod.path_for(workdir, cfg),
        )
    try:
        snapshot = storemod.stats(conn)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    lines = [
        "[OK] db stats: %s, size=%s, user_version=%d"
        % (snapshot["path"], _fmt_bytes(snapshot["size_bytes"]), snapshot["user_version"])
    ]
    for name in storemod.TABLES:
        lines.append("  %-18s %d" % (name, snapshot["tables"].get(name, 0)))
    return _finish(
        args,
        EXIT_OK,
        "\n".join(lines),
        path=snapshot["path"],
        size_bytes=snapshot["size_bytes"],
        user_version=snapshot["user_version"],
        tables=snapshot["tables"],
    )


def _db_export(args, workdir, cfg):
    conn = storemod.connect(workdir, cfg, create=False)
    if conn is None:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] db — файла нет: запустите `trr db init` (%s)"
            % storemod.path_for(workdir, cfg),
        )
    try:
        result = storemod.export_json(conn, args.out)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    if not result:
        return _finish(args, EXIT_SCHEMA, "[MISSING] db export: дамп не записан")
    tables = result.get("tables") or {}
    total = sum(int(value) for value in tables.values())
    return _finish(
        args,
        EXIT_OK,
        "[OK] db export: %s (%s, %d строк в %d таблицах)"
        % (result["path"], _fmt_bytes(result.get("bytes", 0)), total, len(tables)),
        path=result["path"],
        bytes=result.get("bytes"),
        tables=tables,
    )


def _db_query(args, workdir, cfg):
    ok, reason = storemod.is_read_only_sql(args.sql)
    if not ok:
        return _finish(
            args,
            EXIT_BLOCKED,
            "[BLOCKED] db query отклонён: %s (запись в зеркало идёт из пайплайна, "
            "а не из запроса)" % reason,
        )
    conn = storemod.connect_readonly(workdir, cfg)
    if conn is None:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] db — файла нет: запустите `trr db init` (%s)"
            % storemod.path_for(workdir, cfg),
        )
    try:
        columns, rows = storemod.query_rows(conn, args.sql, args.limit)
    except ValueError as exc:
        return _finish(args, EXIT_BLOCKED, "[BLOCKED] db query: %s" % exc)
    except sqlite3.Error as exc:
        return _finish(args, EXIT_SCHEMA, "[MISSING] db query: %s" % exc)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    if getattr(args, "json", False):
        _emit_json(
            args,
            {
                "status": "ok",
                "code": EXIT_OK,
                "columns": columns,
                "rows": [
                    [
                        "hex:" + value.hex()
                        if isinstance(value, (bytes, bytearray, memoryview))
                        else value
                        for value in row
                    ]
                    for row in rows
                ],
                "count": len(rows),
            },
        )
        return EXIT_OK
    _print_table(columns, rows)
    print("[OK] db query: %d строк" % len(rows))
    return EXIT_OK


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

_BLOCK_SCALAR_SAMPLE = (
    "note: |\n"
    "  эталон лежит в Confluence https://space.samokat.ru/display/SPACE/Story+Points,\n"
    "  а копия — в Obsidian, страница «Story Points»\n"
    "folded: >\n"
    "  первая строка\n"
    "  вторая строка\n"
)

_BLOCK_SCALAR_EXPECTED = (
    "эталон лежит в Confluence https://space.samokat.ru/display/SPACE/Story+Points,\n"
    "а копия — в Obsidian, страница «Story Points»\n"
)


def _selftest_yaml():
    """Парсер: пример конфига, блочные скаляры, inline-список."""
    problems = []
    example = Path(configmod.EXAMPLE_CONFIG)
    if not example.is_file():
        return ["пример конфига отсутствует: %s" % example]
    try:
        cfg = yamlmini.load_file(example)
    except yamlmini.YamlError as exc:
        return ["пример конфига не разбирается: %s" % exc]
    if not isinstance(cfg, dict):
        problems.append("пример конфига разобран не в словарь")

    try:
        parsed = yamlmini.loads(_BLOCK_SCALAR_SAMPLE)
    except yamlmini.YamlError as exc:
        return problems + ["блочный скаляр не разбирается: %s" % exc]
    if parsed.get("note") != _BLOCK_SCALAR_EXPECTED:
        problems.append("блочный скаляр '|' искажён: %r" % parsed.get("note"))
    if parsed.get("folded") != "первая строка вторая строка\n":
        problems.append("блочный скаляр '>' искажён: %r" % parsed.get("folded"))

    try:
        inline = yamlmini.loads("scale: [1, 2, 3, 5, 8, 13, 21]\n")
    except yamlmini.YamlError as exc:
        return problems + ["inline-список не разбирается: %s" % exc]
    scale = inline.get("scale")
    if not isinstance(scale, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in scale
    ):
        problems.append("inline-список разобран не в list[int]: %r" % (scale,))

    return problems


def _selftest_schemas():
    """Схемы: все 13 читаются, имеют required и не используют чужих ключевых слов."""
    problems = []
    for name in schema_lite.SCHEMA_NAMES:
        try:
            schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, name)
        except schema_lite.SchemaError as exc:
            problems.append("%s: %s" % (name, exc))
            continue
        if not schema.get("required"):
            problems.append("%s: нет списка required" % name)
        if not schema.get("title") or not schema.get("description"):
            problems.append("%s: нет title/description" % name)
    return problems


def _selftest_config():
    """Конфиг: пример проходит схему и семантические проверки, sha256 стабилен."""
    example = Path(configmod.EXAMPLE_CONFIG)
    try:
        cfg = configmod.load_config(example)
    except configmod.ConfigError as exc:
        return ["пример конфига не читается: %s" % exc]
    problems = list(configmod.validate_config(cfg))
    first = configmod.config_sha256(cfg)
    second = configmod.config_sha256(configmod.load_config(example))
    if first != second:
        problems.append("config_sha256 нестабилен между вызовами")
    if configmod.find_secrets(cfg):
        problems.append("в примере конфига найдены ключи-секреты")

    # estimation.params: блок в примере полон и валиден; apply_defaults
    # дотягивает недостающие под-ключи, не затирая пользовательские.
    params = (cfg.get("estimation") or {}).get("params")
    if not isinstance(params, dict):
        problems.append("в примере конфига нет estimation.params")
    else:
        for key in ("enabled", "clamp", "coefficients", "defaults", "signals"):
            if key not in params:
                problems.append("estimation.params.%s отсутствует в примере" % key)
        if not (params.get("clamp") and params["clamp"][0] <= 1.0 <= params["clamp"][1]):
            problems.append("estimation.params.clamp в примере не накрывает 1.0")

    custom = configmod.apply_defaults(
        {"estimation": {"params": {"coefficients": {"weight": 0.9}}}}
    )
    merged = custom["estimation"]["params"]
    if merged["coefficients"]["weight"] != 0.9:
        problems.append(
            "apply_defaults затёр пользовательский coefficients.weight: %r"
            % (merged["coefficients"]["weight"],)
        )
    if merged["coefficients"]["heat"] != 0.4:
        problems.append(
            "apply_defaults не дотянул coefficients.heat: %r"
            % (merged["coefficients"]["heat"],)
        )
    if merged["clamp"] != [0.5, 2.0]:
        problems.append("apply_defaults исказил clamp: %r" % (merged["clamp"],))

    nulled = configmod.apply_defaults({"estimation": {"params": None}})
    if not isinstance(nulled["estimation"]["params"], dict):
        problems.append("apply_defaults не восстановил params: null")
    elif nulled["estimation"]["params"]["defaults"]["weight"] != 0.5:
        problems.append("apply_defaults не подставил defaults после params: null")

    bad = configmod.apply_defaults(
        {"estimation": {"params": {"clamp": [2.0, 0.5]}}}
    )
    if not any("params.clamp" in error for error in configmod.validate_config(bad)):
        problems.append("validate_config пропустил clamp без 1.0 внутри границ")

    bad_defaults = configmod.apply_defaults(
        {"estimation": {"params": {"defaults": {"weight": 1.5}}}}
    )
    if not any(
        "params.defaults.weight" in error
        for error in configmod.validate_config(bad_defaults)
    ):
        problems.append("validate_config пропустил defaults.weight вне [0, 1]")

    return problems


def _selftest_params():
    """Параметры: границы, дефолты, override, disabled, монотонность, множитель."""
    problems = []

    for value, expected in ((-1.0, 0.0), (2.0, 1.0), (0.5, 0.5), (float("nan"), 0.0)):
        got = paramsmod.clamp01(value)
        if got != expected:
            problems.append("clamp01(%r) = %r, ожидалось %r" % (value, got, expected))

    # (b) пустой context → дефолты, без падений.
    empty = paramsmod.derive({})
    for name in paramsmod.PARAM_NAMES:
        entry = empty.get(name) or {}
        if entry.get("value") != 0.5:
            problems.append("derive({}).%s = %r, ожидалось 0.5" % (name, entry.get("value")))
        if entry.get("source") != "heuristic":
            problems.append("derive({}).%s source = %r" % (name, entry.get("source")))
        if not entry.get("evidence"):
            problems.append("derive({}).%s без evidence" % name)
    if empty.get("applied", {}).get("clamp") != [0.5, 2.0]:
        problems.append("derive({}).applied.clamp = %r" % (empty.get("applied"),))

    # (c) override приоритетнее эвристики.
    overridden = paramsmod.derive(
        {"issue_type": "Feature", "description": "риск " * 100, "weight": 0.9}
    )
    if overridden["weight"]["value"] != 0.9:
        problems.append("override weight не применён: %r" % (overridden["weight"]["value"],))
    if overridden["weight"]["source"] != "override":
        problems.append("override weight source = %r" % (overridden["weight"]["source"],))
    nested = paramsmod.derive({"params": {"heat": 0.1}, "description": "риск"})
    if nested["heat"]["value"] != 0.1 or nested["heat"]["source"] != "override":
        problems.append("override context.params.heat не применён: %r" % (nested["heat"],))
    if nested["weight"]["source"] != "heuristic":
        problems.append("override heat задел weight: %r" % (nested["weight"]["source"],))

    # (d) enabled=false → defaults, source=disabled.
    disabled = paramsmod.derive(
        {"issue_type": "Feature", "description": "x" * 1000, "weight": 0.9},
        {"estimation": {"params": {"enabled": False}}},
    )
    for name in paramsmod.PARAM_NAMES:
        entry = disabled.get(name) or {}
        if entry.get("value") != 0.5 or entry.get("source") != "disabled":
            problems.append("disabled %s = %r" % (name, entry))
    disabled_custom = paramsmod.derive(
        {},
        {
            "estimation": {
                "params": {
                    "enabled": False,
                    "defaults": {"weight": 0.2, "heat": 0.3, "connectivity": 0.4},
                }
            }
        },
    )
    if (
        disabled_custom["weight"]["value"] != 0.2
        or disabled_custom["heat"]["value"] != 0.3
        or disabled_custom["connectivity"]["value"] != 0.4
    ):
        problems.append("disabled не уважает estimation.params.defaults")

    # (e) монотонность: links и integration-метки не уменьшают connectivity.
    previous = -1.0
    for links in (0, 1, 3, 5, 10):
        value = paramsmod.derive({"fields": {"issuelinks": links}})["connectivity"]["value"]
        if value < previous - 1e-9:
            problems.append("connectivity убывает при links=%d: %r < %r" % (links, value, previous))
        previous = value
    previous = -1.0
    for labels in ([], ["api"], ["api", "integration"]):
        value = paramsmod.derive({"labels": labels})["connectivity"]["value"]
        if value < previous - 1e-9:
            problems.append(
                "connectivity убывает при labels=%r: %r < %r" % (labels, value, previous)
            )
        previous = value

    # (e) монотонность: длина описания не уменьшает weight.
    previous = -1.0
    for length in (0, 50, 500, 4000):
        value = paramsmod.derive(
            {"issue_type": "Feature", "description": "x" * length}
        )["weight"]["value"]
        if value < previous - 1e-9:
            problems.append(
                "weight убывает при description_len=%d: %r < %r" % (length, value, previous)
            )
        previous = value

    # (f) множитель нейтрален на дефолтах.
    if paramsmod.multiplier(empty) != 1.0:
        problems.append("multiplier(дефолты) = %r, ожидалось 1.0" % (paramsmod.multiplier(empty),))

    # (g) множитель в границах clamp — на обоих краях.
    high = paramsmod.multiplier(paramsmod.derive({"weight": 1, "heat": 1, "connectivity": 1}))
    low = paramsmod.multiplier(paramsmod.derive({"weight": 0, "heat": 0, "connectivity": 0}))
    if not (0.5 <= high <= 2.0):
        problems.append("multiplier при максимуме вне clamp: %r" % (high,))
    if not (0.5 <= low <= 2.0):
        problems.append("multiplier при минимуме вне clamp: %r" % (low,))
    if high <= low:
        problems.append("multiplier не растёт с параметрами: %r <= %r" % (high, low))

    custom_clamp = paramsmod.multiplier(
        paramsmod.derive({"weight": 1, "heat": 1, "connectivity": 1}),
        {"estimation": {"params": {"clamp": [0.9, 1.1]}}},
    )
    if custom_clamp != 1.1:
        problems.append("multiplier не уважает clamp конфига: %r" % (custom_clamp,))

    return problems


def _selftest_model_params():
    """Множитель в модели и оценке: фолбэк эталона, монотонность, clamp, схема.

    Синтетика, а не данные проекта: selftest должен работать на пустом проекте.
    Проверяется то, что нельзя увидеть в одном числе: `reference=fallback`
    проходит схему, профиль без выборки даёт множитель 1.0, `expected` не
    убывает с ростом параметров, множитель зажат в clamp, а отчёт и страница
    модели рендерятся и без блока `params` (старые артефакты).
    """
    from trr_impl import calibrate as calmod
    from trr_impl import estimate as estimatemod
    from trr_impl import report as reportmod

    problems = []
    cfg = configmod.apply_defaults({})
    reference = {
        "source": {
            "system": "confluence",
            "page_id": "1",
            "url": "https://example.invalid/1",
            "retrieved_at": "1970-01-01T00:00:00Z",
        },
        "scale": list(configmod.NORMATIVE_SCALE),
        "absent_roles": ["BA", "SA"],
        "buckets": [
            {
                "role": "BE",
                "work_kind": "implementation",
                "value": 3,
                "description": "синтетический эталон BE",
                "evidence": "selftest",
            },
            {
                "role": "QA",
                "work_kind": "testing",
                "value": 3,
                "description": "синтетический эталон QA/testing",
                "evidence": "selftest",
            },
        ],
    }
    stats = {
        "computed_at": "1970-01-01T00:00:00Z",
        "sample_rows": 26,
        "buckets": [
            {
                "role": "BE",
                "issue_type": "Feature",
                "work_kind": "implementation",
                "n": 10,
                "mean": 3.0,
                "median": 3.0,
                "p25": 2.0,
                "p75": 5.0,
                "min": 2,
                "max": 5,
                "coverage": "sufficient",
            },
            {
                "role": "BE",
                "issue_type": "Feature",
                "work_kind": "research",
                "n": 6,
                "mean": 2.0,
                "median": 2.0,
                "p25": 2.0,
                "p75": 3.0,
                "min": 2,
                "max": 3,
                "coverage": "sufficient",
            },
            {
                "role": "QA",
                "issue_type": "Feature",
                "work_kind": "testing",
                "n": 10,
                "mean": 2.0,
                "median": 2.0,
                "p25": 2.0,
                "p75": 3.0,
                "min": 2,
                "max": 3,
                "coverage": "sufficient",
            },
        ],
        "insufficient": [],
    }
    try:
        model = calmod.build(reference, stats, cfg, version=1)
    except ValueError as exc:
        return ["синтетическая модель не собирается: %s" % exc]

    buckets = {
        (bucket["role"], bucket["work_kind"]): bucket for bucket in model["buckets"]
    }
    if buckets[("QA", "testing")]["reference"] != "yes":
        problems.append(
            "QA/testing не получил эталон: reference=%r"
            % (buckets[("QA", "testing")]["reference"],)
        )
    research = buckets[("BE", "research")]
    if research["reference"] != "fallback":
        problems.append(
            "бакет без эталонной пары не ушёл в fallback: reference=%r"
            % (research["reference"],)
        )
    if "фолбэк" not in str(research["provenance"][0].get("detail")):
        problems.append("provenance фолбэка не называет пару-источник")
    if research["confidence"] == "high":
        problems.append("fallback дал confidence=high — это не эталон нужного вида работ")
    if "params" not in model:
        problems.append("в модели нет блока params")
    for bucket in model["buckets"]:
        if bucket.get("params_profile_source") != "defaults":
            problems.append(
                "без выборки профиль бакета %s/%s = %r, ожидалось defaults"
                % (bucket["role"], bucket["work_kind"], bucket.get("params_profile_source"))
            )
        if bucket.get("params_multiplier") != 1.0:
            problems.append(
                "без выборки множитель бакета %s/%s = %r, ожидалось 1.0"
                % (bucket["role"], bucket["work_kind"], bucket.get("params_multiplier"))
            )

    validation = {
        "task_key": "E001-1",
        "checked_at": "1970-01-01T00:00:00Z",
        "template": {"name": "t.md", "version": "1", "sha256": "b" * 64},
        "checks": [],
        "verdict": "OK",
        "gaps": [],
        "with_dependencies": False,
    }

    def run_estimate(context, estimate_cfg=None):
        return estimatemod.estimate(
            validation,
            model,
            roles=["BE"],
            context=context,
            cfg=estimate_cfg if estimate_cfg is not None else cfg,
        )

    try:
        baseline_result = run_estimate({})
    except ValueError as exc:
        return problems + ["оценка с параметрами не считается: %s" % exc]

    if "params" not in baseline_result:
        problems.append("в estimate.json нет блока params")
    else:
        block = baseline_result["params"]
        if block.get("multiplier") != 1.0:
            problems.append(
                "baseline=defaults дал множитель %r, ожидалось 1.0"
                % (block.get("multiplier"),)
            )
        if block.get("baseline_source") not in ("bucket", "defaults"):
            problems.append("baseline_source = %r" % (block.get("baseline_source"),))
        expected_baseline = buckets[("BE", "implementation")].get("params_profile") or {}
        for name in paramsmod.PARAM_NAMES:
            if abs(float(block["baseline"][name]) - float(expected_baseline.get(name, 0.5))) > 1e-9:
                problems.append(
                    "baseline.%s = %r, ожидалось %r (профиль бакета)"
                    % (name, block["baseline"][name], expected_baseline.get(name))
                )
        if block.get("source", {}).get("weight") not in ("heuristic", "override", "disabled"):
            problems.append("source.weight = %r" % (block.get("source"),))
        if not block.get("evidence"):
            problems.append("в блоке params нет evidence")

    expected_bucket = buckets[("BE", "implementation")]["expected"]
    if baseline_result["roles"][0]["expected"] != expected_bucket:
        problems.append(
            "при baseline=defaults expected=%r, ожидалось %r (как в бакете)"
            % (baseline_result["roles"][0]["expected"], expected_bucket)
        )

    previous = -1
    for step in range(2, 10):
        weight = round(step / 10.0, 1)
        result = run_estimate({"weight": weight})
        points = result["roles"][0]["expected"]
        if points < previous:
            problems.append(
                "expected убывает при weight=%.1f: %r < %r" % (weight, points, previous)
            )
        previous = points

    high = run_estimate({"weight": 1, "heat": 1, "connectivity": 1})
    low = run_estimate({"weight": 0, "heat": 0, "connectivity": 0})
    if high["params"]["multiplier"] <= low["params"]["multiplier"]:
        problems.append(
            "множитель не растёт с параметрами: %r <= %r"
            % (high["params"]["multiplier"], low["params"]["multiplier"])
        )
    if high["roles"][0]["expected"] < low["roles"][0]["expected"]:
        problems.append("expected убывает при росте всех параметров")

    clamped = configmod.apply_defaults(
        {"estimation": {"params": {"clamp": [0.9, 1.1]}}}
    )
    clamped_result = run_estimate(
        {"weight": 1, "heat": 1, "connectivity": 1}, clamped
    )
    if clamped_result["params"]["multiplier"] != 1.1:
        problems.append(
            "множитель не зажат clamp: %r вместо 1.1"
            % (clamped_result["params"]["multiplier"],)
        )

    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, "estimate")
        errors = schema_lite.validate(baseline_result, schema, "estimate")
    except schema_lite.SchemaError as exc:
        problems.append("схема estimate не читается: %s" % exc)
    else:
        problems.extend("estimate с params: %s" % error for error in errors)

    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, "estimation-model")
        errors = schema_lite.validate(model, schema, "estimation-model")
    except schema_lite.SchemaError as exc:
        problems.append("схема estimation-model не читается: %s" % exc)
    else:
        problems.extend("модель с fallback: %s" % error for error in errors)

    # Старые артефакты: без блока params и без полей множителя рендер не падает.
    legacy = copy.deepcopy(model)
    legacy.pop("params", None)
    for bucket in legacy["buckets"]:
        bucket.pop("params_profile", None)
        bucket.pop("params_multiplier", None)
        bucket.pop("params_profile_source", None)
        # Провенанс множителя в модели до этапа C тоже не существовал:
        # оставлять его в симуляции — значит проверять не тот артефакт.
        bucket["provenance"] = [
            item
            for item in bucket.get("provenance") or []
            if not (isinstance(item, dict) and item.get("field") == "params_multiplier")
        ]
    try:
        page = reportmod.render_model_page(legacy)
    except Exception as exc:  # noqa: BLE001 - именно это и проверяем
        problems.append("страница модели без params не рендерится: %s" % exc)
    else:
        # Формула — то, что рендер решает сам; провенанс — данные модели, в нём
        # строка «× params 1» может остаться от артефакта, собранного с params.
        formula = "\n".join(
            str(row[1]) for row in reportmod._model_formula_rows(legacy)
        )
        if "params_multiplier" in page or "× params" in formula:
            problems.append("страница модели без params показывает множитель")
    legacy_estimate = copy.deepcopy(baseline_result)
    legacy_estimate.pop("params", None)
    try:
        reportmod._params_line(legacy_estimate)
        reportmod._params_evidence(legacy_estimate)
    except Exception as exc:  # noqa: BLE001
        problems.append("строка параметров без params падает: %s" % exc)

    return problems


def _selftest_estimation():
    """Выбор бакета (4 уровня), деградация роли и вердикт по severity.

    Синтетическая модель, а не данные проекта: проверяется то, что нельзя
    увидеть в одном числе — приоритет `(role, issue_type, work_kind)`,
    достижимость каждого бакета на его собственной тройке, деградация роли без
    бакетов до `OTHER` (а не падение) и вердикт `OK/WARN/BLOCKED`.
    """
    from trr_impl import check as checkmod
    from trr_impl import estimate as estimatemod

    problems = []

    def bucket(role, issue_type, work_kind, n, expected, low, high, confidence="high"):
        return {
            "role": role,
            "issue_type": issue_type,
            "work_kind": work_kind,
            "n": n,
            "base": expected,
            "factor": 1.0,
            "expected": expected,
            "range": [low, high],
            "confidence": confidence,
            "reference": "yes" if role != "OTHER" else "none",
        }

    buckets = [
        bucket("BE", "Feature", "implementation", 10, 3, 1, 3),
        bucket("BE", "Задача", "implementation", 4, 5, 3, 8, "low"),
        bucket("BE", "Ошибка", "bugfix", 6, 3, 3, 5, "medium"),
        bucket("OTHER", "Задача", "implementation", 5, 3, 2, 3, "low"),
    ]
    model = {
        "version": 1,
        "checksum": "a" * 64,
        "scale": [1, 2, 3, 5, 8, 13, 21],
        "absent_roles": [],
        "buckets": buckets,
        "gap_rules": [],
    }
    validation = {
        "task_key": "E001-1",
        "checked_at": "1970-01-01T00:00:00Z",
        "template": {"name": "t.md", "version": "1", "sha256": "b" * 64},
        "checks": [],
        "verdict": "OK",
        "gaps": [],
        "with_dependencies": False,
    }

    # (a) порядок уровней: exact → work_kind → role → нет бакета.
    exact, level = estimatemod.select_bucket(
        buckets, "BE", "implementation", True, issue_type="Задача"
    )
    if level != estimatemod.BUCKET_LEVEL_EXACT or exact["issue_type"] != "Задача":
        problems.append("точное совпадение не выбрано: level=%r bucket=%r" % (level, exact))
    same_kind, level = estimatemod.select_bucket(
        buckets, "BE", "implementation", True, issue_type="ADR"
    )
    if level != estimatemod.BUCKET_LEVEL_WORK_KIND or same_kind["issue_type"] != "Feature":
        problems.append(
            "уровень (role, work_kind) не сработал: level=%r bucket=%r"
            % (level, same_kind)
        )
    any_kind, level = estimatemod.select_bucket(
        buckets, "BE", "research", True, issue_type="Feature"
    )
    if level != estimatemod.BUCKET_LEVEL_ROLE or any_kind["issue_type"] != "Feature":
        problems.append("уровень (role, *) не сработал: level=%r bucket=%r" % (level, any_kind))
    if estimatemod.select_bucket(buckets, "DEVOPS", "implementation", True)[0] is not None:
        problems.append("для роли без бакетов селектор вернул бакет")
    # `work_kind=unknown` не поднимается до (role,*): контракт §5.4.1.
    if estimatemod.select_bucket(buckets, "BE", "unknown", True)[0] is not None:
        problems.append("work_kind=unknown поднялся до уровня (role, *)")

    # (b) каждый бакет достижим на своей тройке — иначе покрытие модели врёт.
    for item in buckets:
        chosen, _level = estimatemod.select_bucket(
            buckets,
            item["role"],
            item["work_kind"],
            True,
            issue_type=item["issue_type"],
        )
        if chosen is not item:
            problems.append(
                "бакет %s/%s/%s недостижим: выбран %r"
                % (item["role"], item["issue_type"], item["work_kind"], chosen)
            )

    # (c) оценка: issue_type выбирает бакет, а не только (role, work_kind).
    task = estimatemod.estimate(
        validation,
        model,
        context={"role": "BE", "issue_type": "Задача", "work_kind": "implementation"},
    )
    entry = task["roles"][0]
    if entry["expected"] != 5:
        problems.append(
            "BE/Задача оценена по чужому бакету: expected=%r, ожидалось 5"
            % (entry["expected"],)
        )
    levels = [
        item.get("detail")
        for item in entry["provenance"]
        if item.get("source") == "estimate:bucket-select"
    ]
    if not levels or "exact" not in str(levels[0]):
        problems.append("provenance не называет уровень выбора бакета: %r" % (levels,))

    # (d) деградация роли: DEVOPS не роняет оценку, числа ровно как у OTHER.
    warnings = []
    devops_context = {
        "role": "DEVOPS",
        "issue_type": "Задача",
        "work_kind": "implementation",
    }
    devops = estimatemod.estimate(
        validation, model, context=devops_context, warnings=warnings
    )
    other = estimatemod.estimate(
        validation,
        model,
        context=dict(devops_context, role="OTHER"),
    )
    if len(devops["roles"]) != 1 or devops["roles"][0]["role"] != "DEVOPS":
        problems.append("DEVOPS не оценён: roles=%r" % (devops["roles"],))
    else:
        degraded = devops["roles"][0]
        if (degraded["expected"], degraded["range"]) != (
            other["roles"][0]["expected"],
            other["roles"][0]["range"],
        ):
            problems.append(
                "DEVOPS взял не бакет OTHER: %r/%r вместо %r/%r"
                % (
                    degraded["expected"],
                    degraded["range"],
                    other["roles"][0]["expected"],
                    other["roles"][0]["range"],
                )
            )
        if degraded["confidence"] != "low":
            problems.append(
                "деградация роли не пометила confidence=low: %r" % (degraded["confidence"],)
            )
    if not any("DEVOPS" in line for line in devops["variability_reason"]):
        problems.append("причина деградации DEVOPS не попала в variability_reason")
    if not any("DEVOPS" in line for line in warnings):
        problems.append("деградация DEVOPS не попала в warnings")

    # (e) роль вне словаря скилла: OTHER, а не сумма по всем ролям модели.
    unknown = estimatemod.estimate(
        validation,
        model,
        context={"role": "TL", "issue_type": "Задача", "work_kind": "implementation"},
    )
    if len(unknown["roles"]) != 1 or unknown["roles"][0]["role"] != "OTHER":
        problems.append(
            "роль вне словаря не деградировала до OTHER: roles=%r"
            % ([item["role"] for item in unknown["roles"]],)
        )
    if not any("вне словаря" in line for line in unknown["variability_reason"]):
        problems.append("причина деградации роли вне словаря не записана")

    # (f) вердикт: OK — нет провалов, WARN — провал RECOMMENDED, BLOCKED — REQUIRED.
    # OPTIONAL (гигиена полей шаблона, CL-06/CL-07) вердикт не меняет: иначе
    # `OK` был бы недостижим при «не заполнено поле Роль».
    def status(severity, value):
        return {"severity": severity, "status": value}

    for checks, expected in (
        ([status("REQUIRED", "PASS"), status("RECOMMENDED", "PASS")], "OK"),
        ([status("REQUIRED", "PASS"), status("RECOMMENDED", "FAIL")], "WARN"),
        ([status("REQUIRED", "PASS"), status("OPTIONAL", "UNKNOWN")], "OK"),
        ([status("REQUIRED", "FAIL"), status("RECOMMENDED", "FAIL")], "BLOCKED"),
    ):
        got = checkmod._verdict(checks)
        if got != expected:
            problems.append("вердикт по severity: %r, ожидалось %r" % (got, expected))

    return problems


def _selftest_state():
    """Состояние: цепочка этапов вперёд и запрет понижения."""
    import tempfile

    problems = []
    with tempfile.TemporaryDirectory(prefix="trr-selftest-") as tmp:
        statemod.save(tmp, statemod.default_state("0.0.0"))
        for stage in ("configured", "trained", "checked", "estimated", "published"):
            statemod.set_stage(tmp, stage)
        if statemod.load(tmp).get("stage") != "published":
            problems.append("цепочка этапов не дошла до published")
        try:
            statemod.set_stage(tmp, "configured")
        except statemod.StateError:
            pass
        else:
            problems.append("понижение этапа не запрещено")
        statemod.set_stage(tmp, "trained", reason="enrich")
        if statemod.load(tmp).get("stage") != "trained":
            problems.append("возврат в trained после enrich не разрешён")
        statemod.set_stage(tmp, "checked")
        try:
            statemod.set_stage(tmp, "trained")
        except statemod.StateError:
            pass
        else:
            problems.append('откат в trained без reason="enrich" не запрещён')
        statemod.add_run(tmp, "E001-1", "runs/E001-1/b", "OK", "2026-11-17T09:41:07Z")
        statemod.add_run(tmp, "E001-1", "runs/E001-1/a", "WARN", "2026-11-17T09:41:08Z")
        runs = statemod.load(tmp).get("runs") or []
        if [item["run_dir"] for item in runs] != ["runs/E001-1/a", "runs/E001-1/b"]:
            problems.append("история прогонов отсортирована неверно: %r" % (runs,))

    # doctor: отсутствие версии модели — явный [WARN], а не тишина и не блок.
    messages = []
    doctormod._check_model_version({}, messages)
    if [item["level"] for item in messages] != ["warn"]:
        problems.append(
            "отсутствие model.version не дало [WARN]: %r" % (messages,)
        )
    messages = []
    doctormod._check_model_version({"model": {"version": 2}}, messages)
    if [item["level"] for item in messages] != ["ok"]:
        problems.append("наличие model.version не дало [OK]: %r" % (messages,))
    return problems


def _selftest_run_dir():
    """`state.runs[].run_dir`: от корня проекта, без склейки путей и дублей.

    Регресс на два дефекта: путь считался от `cwd` (запуск из `scripts/`
    приклеивал префикс подкаталога к уже относительному пути — запись
    удлинялась на каждом прогоне) и дедуп шёл по строке пути, поэтому
    испорченные записи одного прогона не схлопывались.
    """
    import os

    problems = []
    run_id = "2026-11-17T10-00-00Z"
    canonical = ".task-readiness/runs/E001-2/%s" % run_id
    pattern = re.compile(
        r"^\.task-readiness/runs/[A-Z0-9-]+/\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$"
    )
    with tempfile.TemporaryDirectory(prefix="trr-selftest-run-dir-") as tmp:
        statemod.save(tmp, statemod.default_state("0.0.0"))
        nested = Path(tmp) / "scripts"
        nested.mkdir()
        previous = Path.cwd()
        try:
            # Запуск из подкаталога скилла, а не из корня проекта.
            os.chdir(nested)
            statemod.add_run(tmp, "E001-2", canonical, "OK", "2026-11-17T10:00:01Z")
        finally:
            os.chdir(previous)
        runs = statemod.load(tmp).get("runs") or []
        if [item.get("run_dir") for item in runs] != [canonical]:
            problems.append(
                "запись из другого cwd склеила путь: %r"
                % ([item.get("run_dir") for item in runs],)
            )

        # Повторная запись того же прогона: ни дубля, ни удлинения пути.
        statemod.add_run(tmp, "E001-2", canonical, "WARN", "2026-11-17T10:00:02Z")
        statemod.add_run(
            tmp, "E001-2", str(Path(tmp) / canonical), "OK", "2026-11-17T10:00:03Z"
        )
        runs = statemod.load(tmp).get("runs") or []
        if [item.get("run_dir") for item in runs] != [canonical]:
            problems.append(
                "повторная запись прогона дала %r"
                % ([item.get("run_dir") for item in runs],)
            )
        if [item.get("verdict") for item in runs] != ["OK"]:
            problems.append("повторная запись не обновила вердикт: %r" % (runs,))

        # Склеенная запись из старого state схлопывается до хвоста.
        state = statemod.load(tmp)
        state["runs"] = [
            {
                "task_key": "E001-2",
                "run_dir": "scripts/.task-readiness/runs/E001-2/2026-11-17T11-00-00Z",
                "verdict": "OK",
                "checked_at": "2026-11-17T11:00:01Z",
            },
            {
                "task_key": "E001-2",
                "run_dir": canonical,
                "verdict": "OK",
                "checked_at": "2026-11-17T10:00:03Z",
            },
        ]
        statemod.save(tmp, state)
        statemod.add_run(tmp, "E001-2", canonical, "OK", "2026-11-17T10:00:04Z")
        runs = statemod.load(tmp).get("runs") or []
        bad = [
            item.get("run_dir")
            for item in runs
            if not pattern.match(str(item.get("run_dir")))
        ]
        if bad:
            problems.append("run_dir не нормализован: %r" % (bad,))
        if len(runs) != 2:
            problems.append("дубли прогонов не схлопнуты: %r" % (runs,))
    return problems


def _selftest_calibrate_state():
    """`calibrate` фиксирует версию модели в `state.model.version`."""
    from trr_impl import calibrate as calmod

    problems = []
    reference = {
        "source": {
            "system": "confluence",
            "page_id": "1",
            "url": "https://example.invalid/1",
            "retrieved_at": "1970-01-01T00:00:00Z",
        },
        "scale": list(configmod.NORMATIVE_SCALE),
        "absent_roles": ["BA", "SA"],
        "buckets": [
            {
                "role": "BE",
                "work_kind": "implementation",
                "value": 3,
                "description": "синтетический эталон BE",
                "evidence": "selftest",
            },
            {
                "role": "QA",
                "work_kind": "testing",
                "value": 3,
                "description": "синтетический эталон QA/testing",
                "evidence": "selftest",
            },
        ],
    }
    stats = {
        "computed_at": "1970-01-01T00:00:00Z",
        "sample_rows": 20,
        "buckets": [
            {
                "role": "BE",
                "issue_type": "Feature",
                "work_kind": "implementation",
                "n": 10,
                "mean": 3.0,
                "median": 3.0,
                "p25": 2.0,
                "p75": 5.0,
                "min": 2,
                "max": 5,
                "coverage": "sufficient",
            },
            {
                "role": "QA",
                "issue_type": "Feature",
                "work_kind": "testing",
                "n": 10,
                "mean": 2.0,
                "median": 2.0,
                "p25": 2.0,
                "p75": 3.0,
                "min": 2,
                "max": 3,
                "coverage": "sufficient",
            },
        ],
        "insufficient": [],
    }
    with tempfile.TemporaryDirectory(prefix="trr-selftest-calibrate-") as tmp:
        base = Path(tmp) / statemod.STATE_DIR
        (base / "norm").mkdir(parents=True)
        for name, payload in (
            ("reference-estimates.json", reference),
            ("sprint-stats.json", stats),
        ):
            (base / "norm" / name).write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        shutil.copy(configmod.EXAMPLE_CONFIG, Path(tmp) / configmod.CONFIG_FILENAME)
        statemod.save(tmp, statemod.default_state("0.0.0"))

        args = argparse.Namespace(reason=None, quiet=True, json=False)
        code = calmod.run(tmp, args)
        if code != 0:
            return ["calibrate на синтетике вернул код %r" % (code,)]
        state = statemod.load(tmp)
        model = state.get("model")
        if not isinstance(model, dict) or model.get("version") != 1:
            problems.append("после calibrate нет state.model.version: %r" % (model,))
        elif model.get("checksum") != state.get("model_checksum"):
            problems.append(
                "state.model.checksum не совпал с model_checksum: %r"
                % (model.get("checksum"),)
            )
    return problems


def _selftest_publish():
    """Публикация: `--run` не уезжает в «лексикографически последний» прогон."""
    import tempfile

    from trr_impl import publish as publishmod
    from trr_impl import report as reportmod

    problems = []
    with tempfile.TemporaryDirectory(prefix="trr-selftest-publish-") as tmp:
        task = "E001-1"
        base = Path(tmp) / ".task-readiness" / "runs" / task
        newer = base / "2026-11-18T18-00-00Z"
        older = base / "2026-11-18T14-37-46Z"
        for run_dir in (newer, older):
            run_dir.mkdir(parents=True)
            # Файл-признак прогона: без него фолбэк «последний прогон» не
            # находит каталог и уходит в `.task-readiness/actions/`.
            (run_dir / "estimate.json").write_text("{}", encoding="utf-8")
        try:
            path = publishmod.write_action_package(
                tmp,
                task,
                "тело",
                "selftest",
                kind=publishmod.KIND_ESTIMATE,
                run=older.name,
            )
        except publishmod.MissingReport as exc:
            problems.append("write_action_package с --run: %s" % exc)
        else:
            if path.parent.parent != older:
                problems.append(
                    "action-пакет лёг в %s вместо явного прогона %s"
                    % (path, older)
                )
        # Без `--run` — прежнее поведение: последний прогон на диске.
        try:
            path = publishmod.write_action_package(
                tmp, task, "тело", "selftest", kind=publishmod.KIND_ESTIMATE
            )
        except publishmod.MissingReport as exc:
            problems.append("write_action_package без --run: %s" % exc)
        else:
            if path.parent.parent != newer:
                problems.append(
                    "без --run action-пакет лёг в %s вместо последнего прогона %s"
                    % (path, newer)
                )
        # Явный прогон, которого нет, — MISSING, а не запись в чужой каталог.
        try:
            publishmod.write_action_package(
                tmp,
                task,
                "тело",
                "selftest",
                kind=publishmod.KIND_ESTIMATE,
                run="2026-01-01T00-00-00Z",
            )
        except publishmod.MissingReport:
            pass
        else:
            problems.append("несуществующий --run не дал MissingReport")

    # Обоснование роли: `expected=N` помечается как значение до надбавки RS-01.
    reason = "expected=1 (base 3 × factor 0.5 × params 0.6203)"
    estimate = {"resources": {"bonus_sp": 2, "applied_to": "FE", "mode": "add"}}
    marked = reportmod._reason_before_resources(reason, estimate, {"role": "FE"})
    if "expected=1 до RS-01" not in marked:
        problems.append("надбавка RS-01 не помечена в обосновании: %r" % (marked,))
    other = reportmod._reason_before_resources(reason, estimate, {"role": "QA"})
    if other != reason:
        problems.append("пометка RS-01 попала в чужую роль: %r" % (other,))
    plain = reportmod._reason_before_resources(
        reason, {"resources": {"bonus_sp": 0, "applied_to": "FE"}}, {"role": "FE"}
    )
    if plain != reason:
        problems.append("пометка RS-01 при нулевой надбавке: %r" % (plain,))
    return problems


def _selftest_canonical():
    payload = {"b": [1, 2], "a": "текст"}
    text = schema_lite.canonical_json(payload)
    if text != schema_lite.canonical_json({"a": "текст", "b": [1, 2]}):
        return ["канонический JSON зависит от порядка ключей"]
    if schema_lite.sha256_canonical(payload) != schema_lite.sha256_canonical(payload):
        return ["sha256 канонического JSON нестабилен"]
    return []


def _selftest_storage():
    """Зеркало: идемпотентность, векторы, guard запросов, disabled, битый путь."""
    problems = []
    tempdir = tempfile.mkdtemp(prefix="trr-selftest-store-")
    base = configmod.apply_defaults({})

    def cfg_with(name, **overrides):
        cfg = copy.deepcopy(base)
        sqlite = dict(cfg["storage"]["sqlite"])
        sqlite["path"] = str(Path(tempdir) / name)
        sqlite.update(overrides)
        cfg["storage"]["sqlite"] = sqlite
        return cfg

    model = {
        "version": 1,
        "checksum": "a" * 64,
        "generated_at": "1970-01-01T00:00:00Z",
        "scale": [1, 2, 3, 5, 8, 13, 21],
        "buckets": [
            {
                "role": "BE",
                "issue_type": "Feature",
                "work_kind": "implementation",
                "base": 5,
                "factor": 0.6,
                "expected": 3,
                "range": [1, 3],
                "n": 80,
                "confidence": "high",
                "reference": "yes",
                "provenance": [],
            }
        ],
        "gap_rules": [
            {
                "rule_id": "GR-01",
                "condition": "SA-08=FAIL",
                "penalty_steps": 2,
                "applies_to": ["SA"],
            }
        ],
        "absent_roles": ["SA"],
        "sources": {"reference": {}, "sprints": []},
    }
    stats_payload = {
        "computed_at": "1970-01-01T00:00:00Z",
        "sample_rows": 1,
        "buckets": [
            {
                "role": "BE",
                "issue_type": "Feature",
                "work_kind": "implementation",
                "n": 80,
                "mean": 3.58,
                "median": 3.0,
                "p25": 3.0,
                "p75": 5.0,
                "min": 1,
                "max": 8,
                "coverage": "sufficient",
            }
        ],
        "insufficient": [],
    }
    validation = {
        "task_key": "E001-1",
        "checked_at": "1970-01-01T00:00:00Z",
        "template": {"name": "t.md", "version": "1", "sha256": "b" * 64},
        "checks": [
            {
                "id": "TPL-01",
                "section": "Описание",
                "severity": "REQUIRED",
                "status": "PASS",
                "evidence": "",
                "message": "ok",
            }
        ],
        "verdict": "OK",
        "gaps": [],
        "with_dependencies": False,
    }
    estimate = {
        "task_key": "E001-1",
        "estimated_at": "1970-01-01T00:00:00Z",
        "model_version": 1,
        "model_checksum": model["checksum"],
        "roles": [
            {
                "role": "BE",
                "expected": 3,
                "range": [1, 3],
                "scenarios": [],
                "confidence": "high",
                "provenance": [],
            }
        ],
        "total": {"expected": 3, "range": [1, 3]},
        "variability_reason": [],
        "blocked_by_gaps": [],
    }

    try:
        cfg = cfg_with("main.sqlite3")

        first = storemod.init_db(tempdir, cfg)
        second = storemod.init_db(tempdir, cfg)
        if not first["created"]:
            problems.append("первый init_db не отметил created=true")
        if second["created"]:
            problems.append("второй init_db создал БД повторно")
        if first["user_version"] != second["user_version"]:
            problems.append(
                "user_version вырос при повторном init_db: %r → %r"
                % (first["user_version"], second["user_version"])
            )
        if second["user_version"] < storemod.SCHEMA_VERSION:
            problems.append(
                "user_version=%r меньше SCHEMA_VERSION=%r"
                % (second["user_version"], storemod.SCHEMA_VERSION)
            )

        conn = storemod.connect(tempdir, cfg)
        if conn is None:
            problems.append("connect вернул None на рабочем пути")
        else:
            for _attempt in range(2):
                storemod.record_model(conn, model)
                storemod.record_stats(conn, stats_payload, model["checksum"])
                storemod.record_run(
                    conn, "RUN-1", "E001-1", "checked", "runs/E001-1/RUN-1",
                    model["checksum"], "c" * 64,
                )
                storemod.record_validation(conn, "RUN-1", validation)
                storemod.record_estimate(conn, "RUN-1", estimate)
            counts = storemod.stats(conn)["tables"]
            for table, expected in (
                ("model_versions", 1),
                ("model_buckets", 1),
                ("gap_rules", 1),
                ("sprint_stats", 1),
                ("runs", 1),
                ("validations", 1),
                ("estimates", 1),
                ("estimate_roles", 1),
            ):
                if counts.get(table) != expected:
                    problems.append(
                        "повторная запись дала %s=%r вместо %d"
                        % (table, counts.get(table), expected)
                    )

            # Схема 5: один и тот же RUN-ID у двух задач — две строки, не одна
            # (`run_id` — метка времени, она не уникальна между задачами).
            second_validation = dict(validation, task_key="E001-2")
            second_estimate = dict(estimate, task_key="E001-2")
            storemod.record_run(
                conn, "RUN-1", "E001-2", "estimated", "runs/E001-2/RUN-1",
                None, None,
            )
            storemod.record_validation(conn, "RUN-1", second_validation)
            storemod.record_estimate(conn, "RUN-1", second_estimate)
            for table in ("runs", "validations", "estimates", "estimate_roles"):
                count = conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
                if int(count) != 2:
                    problems.append(
                        "второй task_key с тем же RUN-ID дал %s=%r вместо 2"
                        % (table, count)
                    )

            # Публикация: sha256 файла и контрольная сумма модели — разные
            # колонки (до схемы 5 обе величины жили в `sha256`).
            storemod.record_publication(
                conn, "confluence", "PAGE-1", "http://x", "a" * 64, "b" * 64
            )
            row = conn.execute(
                "SELECT content_sha256, model_checksum FROM publications "
                "WHERE target='confluence' AND ref='PAGE-1'"
            ).fetchone()
            if row is None or row["content_sha256"] != "a" * 64 or row[
                "model_checksum"
            ] != "b" * 64:
                problems.append(
                    "publications не разделяет content_sha256 и model_checksum: %r"
                    % (tuple(row) if row is not None else None,)
                )

            # Векторы: round-trip BLOB ↔ list[float] с точностью 1e-6.
            values = [0.123456789, 0.5, 1.0 / 3.0]
            back = storemod.unpack_vector(storemod.pack_vector(values), len(values))
            if len(back) != len(values) or any(
                abs(left - right) > 1e-6 for left, right in zip(back, values)
            ):
                problems.append("pack/unpack вектора исказил значения: %r → %r" % (values, back))

            artifact = {
                "version": 1,
                "built_at": "1970-01-01T00:00:00Z",
                "top_terms": 2,
                "weight_word": 0.5,
                "weight_char": 0.5,
                "normalizer": {"id": "selftest"},
                "vectors": [
                    {
                        "key": "E001-1",
                        "role": "BE",
                        "work_kind": "implementation",
                        "terms": {"w:a": 0.5, "c:ab": 0.25},
                    }
                ],
            }
            storemod.record_vectors(conn, 1, artifact, artifact["vectors"])
            row = conn.execute(
                "SELECT dim, vector FROM vectors WHERE task_key=? AND model_version=?",
                ("E001-1", 1),
            ).fetchone()
            if row is None:
                problems.append("record_vectors не записал вектор задачи")
            else:
                restored = storemod.unpack_vector(row["vector"], row["dim"])
                if len(restored) != 2 or abs(restored[0] - 0.25) > 1e-6 or abs(
                    restored[1] - 0.5
                ) > 1e-6:
                    problems.append(
                        "вектор из БД не совпал с исходным: %r" % (restored,)
                    )
            meta = conn.execute("SELECT corpus FROM vector_meta WHERE model_version=1").fetchone()
            if meta is None or int(meta[0]) != 1:
                problems.append("vector_meta не записана (corpus)")

            # `db query`: только чтение.
            for sql in (
                "DROP TABLE meta",
                "INSERT INTO meta(key) VALUES('x')",
                "ATTACH DATABASE 'x' AS y",
                "PRAGMA writable_schema=1",
                "SELECT 1; DROP TABLE meta",
                "UPDATE meta SET value='x'",
            ):
                ok, _reason = storemod.is_read_only_sql(sql)
                if ok:
                    problems.append("db query пропустил не-read-only SQL: %r" % sql)
            for sql in (
                "-- комментарий\nSELECT 1",
                "WITH x AS (SELECT 1) SELECT * FROM x",
                "PRAGMA integrity_check",
            ):
                ok, reason = storemod.is_read_only_sql(sql)
                if not ok:
                    problems.append("db query отклонил read-only SQL %r: %s" % (sql, reason))
            conn.close()

        # keep_vectors=false → таблица vectors пуста, meta пишется.
        cfg_no_vectors = cfg_with("no-vectors.sqlite3", keep_vectors=False)
        storemod.init_db(tempdir, cfg_no_vectors)
        conn2 = storemod.connect(tempdir, cfg_no_vectors)
        if conn2 is None:
            problems.append("connect вернул None при keep_vectors=false")
        else:
            storemod.record_vectors(conn2, 1, artifact, artifact["vectors"])
            stored = conn2.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
            if int(stored) != 0:
                problems.append("keep_vectors=false записал %d векторов" % stored)
            meta = conn2.execute("SELECT COUNT(*) FROM vector_meta").fetchone()[0]
            if int(meta) != 1:
                problems.append("keep_vectors=false не записал vector_meta")
            conn2.close()

        # enabled=false → no-op и никакого файла.
        cfg_disabled = cfg_with("disabled.sqlite3", enabled=False)
        disabled_path = Path(tempdir) / "disabled.sqlite3"
        if storemod.connect(tempdir, cfg_disabled) is not None:
            problems.append("enabled=false вернул соединение")
        storemod.save_stats(tempdir, cfg_disabled, stats_payload)
        storemod.save_event(tempdir, cfg_disabled, "selftest", {})
        if disabled_path.exists():
            problems.append("enabled=false создал файл БД")

        # Битый путь: [WARN], без исключения наружу.
        cfg_broken = cfg_with("broken.sqlite3")
        cfg_broken["storage"]["sqlite"]["path"] = "/proc/trr-selftest/x.sqlite3"
        try:
            broken = storemod.connect(tempdir, cfg_broken)
        except Exception as exc:  # noqa: BLE001 - именно это и проверяем
            problems.append("битый путь дал исключение: %s" % exc)
            broken = None
        if broken is not None:
            problems.append("битый путь вернул соединение")
            broken.close()
        try:
            broken_init = storemod.init_db(tempdir, cfg_broken)
        except Exception as exc:  # noqa: BLE001
            problems.append("init_db на битом пути дал исключение: %s" % exc)
            broken_init = {}
        if broken_init.get("user_version"):
            problems.append("init_db на битом пути вернул user_version > 0")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)
    return problems


def _selftest_analysis():
    """Содержательный анализ и политика вердикта (rules version 2).

    Проверяется то, что нельзя увидеть в одном числе: пустой снимок не падает и
    даёт нули, конкретное описание даёт понятность выше порога CL-01, измеримый
    критерий считается ровно один раз (одна реализация в `analysis`), блокируют
    только `CL-01`/`SA-08`, а сумма весов сигналов параметров остаётся `1.0`.
    """
    from trr_impl import analysis as analysismod
    from trr_impl import check as checkmod
    from trr_impl import params as paramsmod

    problems = []

    empty = analysismod.analyze({})
    if empty["clarity"]["score"] != 0.0:
        problems.append("analyze({}).clarity = %r, ожидалось 0.0" % (empty["clarity"]["score"],))
    if empty["testability"]["measurable_criteria"] != 0:
        problems.append("analyze({}) нашёл измеримые критерии в пустом снимке")
    if empty["reproduction"]["steps"] != 0:
        problems.append("analyze({}) нашёл шаги воспроизведения в пустом снимке")
    if analysismod.analyze(None)["clarity"]["score"] != 0.0:
        problems.append("analyze(None) не деградировал до нулей")

    concrete = {
        "task_key": "E001-1",
        "issue_type": "Feature",
        "summary": "Добавить слот доставки в оформление заказа",
        "description": (
            "Нужно добавить выбор слота доставки в оформлении заказа. "
            "Сейчас оператор вручную сверяет слот с данными склада и тратит "
            "около 15 минут. Затрагиваем сервис заказов и контракт API "
            "delivery_slot. В рамках доработки меняем только чтение слота. "
            "Критерии приёмки: заявка обрабатывается не более 2 минут, "
            "ошибок в логах нет."
        ),
        "sections": {
            "acceptance_criteria": "- заявка обрабатывается не более 2 минут\n"
            "- ошибок в логах нет",
            "scenarios": "Основной: слот свободен — заказ подтверждается.\n"
            "Альтернативный: слот занят — предлагаем ближайший.",
        },
        "labels": ["api"],
        "fields": {"links": [{"type": "Blocks", "direction": "outward", "key": "E001-2"}]},
    }
    rich = analysismod.analyze(concrete)
    if rich["clarity"]["score"] < 0.35:
        problems.append(
            "понятность конкретного описания = %r, ожидалось ≥ 0.35"
            % (rich["clarity"]["score"],)
        )
    if rich["testability"]["measurable_criteria"] < 1:
        problems.append("измеримые критерии в конкретном описании не найдены")
    if rich["scenarios"]["count"] < 1:
        problems.append("сценарии в конкретном описании не найдены")
    if rich["dependencies"]["link_types"].get("blocks") != 1:
        problems.append(
            "тип связи Blocks не распознан: %r" % (rich["dependencies"]["link_types"],)
        )
    if not rich["area"]["name"]:
        problems.append("область задачи не определена")

    if json.dumps(analysismod.analyze(concrete), sort_keys=True) != json.dumps(
        rich, sort_keys=True
    ):
        problems.append("analyze не детерминирован")

    lines = "- заявка обрабатывается не более 2 минут\n- покрытие тестами не ниже 80 %\n- сделать хорошо"
    if len(analysismod.measurable_criteria(lines)) != 2:
        problems.append(
            "measurable_criteria насчитал %d измеримых строк, ожидалось 2"
            % len(analysismod.measurable_criteria(lines)),
        )
    if checkmod._measurable_criteria(lines) != analysismod.measurable_criteria(lines):
        problems.append("check._measurable_criteria разошёлся с analysis.measurable_criteria")

    required = sorted(
        entry["id"] for entry in checkmod.CHECKS if entry["severity"] == "REQUIRED"
    )
    if required != ["CL-01", "SA-08"]:
        problems.append("REQUIRED-правила = %r, ожидалось ['CL-01', 'SA-08']" % (required,))

    for name, weights in paramsmod.SIGNAL_WEIGHTS.items():
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-9:
            problems.append("сумма весов %s = %r, ожидалось 1.0" % (name, total))

    # Политика вердикта: OPTIONAL не влияет, RECOMMENDED даёт WARN.
    if checkmod._verdict([{"severity": "OPTIONAL", "status": "FAIL"}]) != "OK":
        problems.append("OPTIONAL-провал повлиял на вердикт")
    if checkmod._verdict([{"severity": "REQUIRED", "status": "FAIL"}]) != "BLOCKED":
        problems.append("REQUIRED-провал не заблокировал вердикт")

    problems.extend(_selftest_parser())
    problems.extend(_selftest_work_scope())
    problems.extend(_selftest_work_intent())
    problems.extend(_selftest_absent_fields())
    return problems


def _context(**overrides):
    """Минимальный валидный снимок задачи для проверок каталога."""
    context = {
        "task_key": "E001-0",
        "issue_type": "Задача",
        "role": "BE",
        "work_kind": "implementation",
        "sp": None,
        "qa_estimation": None,
        "labels": [],
        "summary": "",
        "description": "",
        "sections": {},
        "fields": {},
        "sources": [],
    }
    context.update(overrides)
    return context


def _sa08(context):
    from trr_impl import check as checkmod

    validation = checkmod.run_checks(context)
    return next(check for check in validation["checks"] if check["id"] == "SA-08")


def _selftest_parser():
    """Разметка заголовков: доминирующие синтаксисы корпуса распознаются.

    `*Курсив:*` — 113 задач из 223, `{*}…{*}` — 30, `h3.` — 7. Пока парсер их
    не видел, SA-08 находил критерии в 3 задачах из 49.
    """
    from trr_impl import check as checkmod

    problems = []
    cases = {
        "*Критерии приемки:*": "критерии приемки",
        "*Задача*: Скорректировать условия": "задача",
        "{*}Ожидаемый результат{*}": "ожидаемый результат",
        "{*}Решение:{*}": "решение",
        "h3. Что нужно сделать": "что нужно сделать",
        "**Цель**": "цель",
        "# Сценарии": "сценарии",
        "Цель: сократить время": "цель",
    }
    for line, expected in cases.items():
        heading = checkmod._heading_of(line)
        if heading is None or heading[0] != expected:
            problems.append(
                "заголовок %r распознан как %r, ожидалось %r"
                % (line, heading, expected)
            )
    # Курсив посреди строки — не заголовок: иначе блок режется на части.
    if checkmod._heading_of("*важно* учесть при переносе") is not None:
        problems.append("курсив внутри строки принят за заголовок")
    # Маркированный список `* пункт` — не заголовок.
    if checkmod._heading_of("* пункт списка") is not None:
        problems.append("пункт маркированного списка принят за заголовок")
    blocks = dict(checkmod._blocks("*Решение:*\nТребуется доработать ручку.\n\n*Цель:*\nСократить время"))
    if "решение" not in blocks or "цель" not in blocks:
        problems.append("_blocks не разобрал `*Решение:*`/`*Цель:*`: %r" % (blocks,))
    return problems


def _selftest_work_scope():
    """SA-08: «объём работ» — достаточное основание, и только пустое — FAIL."""
    from trr_impl import analysis as analysismod

    from trr_impl import check as checkmod

    problems = []

    section = _context(
        summary="[BE] Возвраты FBS",
        description="*Задача:*\nТребуется внести изменения в функционал определения схемы тикета",
    )
    scope = analysismod.work_scope(section)
    if not scope[0] or "Задача" not in (scope[1] or ""):
        problems.append("work_scope не нашёл раздел «Задача»: %r" % (scope,))
    check = _sa08(section)
    if check["status"] != "PASS" or "объём работ описан" not in check["message"]:
        problems.append(
            "SA-08 не принял раздел «Задача» основанием: %r %r"
            % (check["status"], check["message"])
        )

    marker = _context(
        summary="[FE] Вложения",
        description="Необходимо реализовать возможность добавления вложений из буфера обмена",
    )
    check = _sa08(marker)
    if check["status"] != "PASS" or "в описании" not in check["message"]:
        problems.append(
            "SA-08 не принял «необходимо + глагол» основанием: %r %r"
            % (check["status"], check["message"])
        )

    action = _context(summary="[SA] Убрать лот доставки из списка товаров")
    check = _sa08(action)
    if check["status"] != "PASS" or "заголовке" not in check["message"]:
        problems.append(
            "SA-08 не принял действие в заголовке основанием: %r %r"
            % (check["status"], check["message"])
        )

    empty = _context(summary="[FE] Поворот изображений")
    check = _sa08(empty)
    if check["status"] != "FAIL":
        problems.append("SA-08 не заблокировал задачу без основания: %r" % (check["status"],))

    # Тема без действия («Создание тикета») основанием не считается: инфинитив
    # требуется, иначе правило перестаёт что-либо проверять.
    theme = _context(summary="[FE] Создание тикета")
    if _sa08(theme)["status"] != "FAIL":
        problems.append("SA-08 принял тему «Создание тикета» за действие")
    return problems


def _selftest_work_intent():
    """Ось intent: перенос данных ≠ миграция структуры, `перенос` ≠ данные."""
    from trr_impl import analysis as analysismod

    from trr_impl import check as checkmod

    problems = []

    schema = analysismod.work_intent(
        _context(
            summary="[BE] Миграция таблиц БД в сервис icatalog-nrt",
            description="В БД (Cassandra) необходимо создать схемы для хранения справочников",
        )
    )
    if not schema or schema[0]["intent"] != "schema_migration":
        problems.append("intent «миграция таблиц» = %r, ожидалось schema_migration" % (schema,))

    data = analysismod.work_intent(
        _context(
            summary="[BE] Цифровой рубль",
            description="Для добавления значения выполнить миграцию:\n"
            "insert into payment_methods (payment_method_id, name) values (5, 'X')",
        )
    )
    if not data or data[0]["intent"] != "data_migration":
        problems.append("intent `insert into` = %r, ожидалось data_migration" % (data,))

    code = analysismod.work_intent(
        _context(
            summary="[BE] Перенос ручки в erm-orders",
            description="Выполнить перенос POST /contactCenterUIService/ в erm-orders",
        )
    )
    if code and code[0]["intent"] == "data_migration":
        problems.append("перенос кода принят за перенос данных: %r" % (code,))

    boilerplate = analysismod.work_intent(
        _context(
            summary="[SA] Проработка БД сервиса",
            description="*Цель:*\nЗагрузить данные в три контекста Cassandra\n"
            "*Задача:*\nОписать задачи по миграции БД для сервиса",
        )
    )
    if not boilerplate or boilerplate[0]["intent"] != "schema_migration":
        problems.append(
            "boilerplate «Цель» повлиял на intent: %r" % (boilerplate,)
        )

    again = analysismod.work_intent(
        _context(summary="[BE] Миграция таблиц БД", description="создать схемы")
    )
    if json.dumps(again, sort_keys=True) != json.dumps(
        analysismod.work_intent(
            _context(summary="[BE] Миграция таблиц БД", description="создать схемы")
        ),
        sort_keys=True,
    ):
        problems.append("work_intent не детерминирован")
    return problems


def _selftest_absent_fields():
    """Поле, которого нет в проекте, — NA, а не FAIL (и не трогает SA/CL)."""
    from trr_impl import check as checkmod

    problems = []
    context = _context(
        summary="Выгрузка пользователей",
        description="Выгрузите список активных пользователей в формате .xlsx",
        fields={"absent_in_project": ["Команда", "Sprint", "Роль", "Story Points"]},
    )
    validation = checkmod.run_checks(context)
    by_id = {check["id"]: check for check in validation["checks"]}
    for rule_id, name in (
        ("TPL-02", "Команда"),
        ("TPL-10", "Sprint"),
        ("TPL-07", "Роль"),
        ("TPL-11", "Story Points"),
    ):
        check = by_id[rule_id]
        if check["status"] != "NA" or name not in check["message"]:
            problems.append(
                "%s при отсутствующем поле: %r %r" % (rule_id, check["status"], check["message"])
            )
        if check["id"] in {gap["id"] for gap in validation["gaps"]}:
            problems.append("%s попал в gaps при отсутствующем поле" % rule_id)
    if by_id["TPL-08"]["status"] != "FAIL":
        problems.append("TPL-08 изменился без записи в absent_in_project")

    # Списка нет — поведение как раньше.
    plain = checkmod.run_checks(_context(summary="Выгрузка", description="x"))
    plain_by_id = {check["id"]: check for check in plain["checks"]}
    if plain_by_id["TPL-02"]["status"] != "FAIL":
        problems.append("без absent_in_project TPL-02 перестал быть FAIL")
    return problems


def cmd_selftest(args):
    checks = (
        ("yaml", _selftest_yaml),
        ("schemas", _selftest_schemas),
        ("config", _selftest_config),
        ("params", _selftest_params),
        ("analysis", _selftest_analysis),
        ("model_params", _selftest_model_params),
        ("estimation", _selftest_estimation),
        ("canonical", _selftest_canonical),
        ("state", _selftest_state),
        ("run_dir", _selftest_run_dir),
        ("calibrate_state", _selftest_calibrate_state),
        ("publish", _selftest_publish),
        ("storage", _selftest_storage),
    )
    failures = 0
    for name, check in checks:
        try:
            problems = check()
        except Exception as exc:  # noqa: BLE001 - selftest не должен падать трейсбеком
            problems = ["неожиданная ошибка: %s: %s" % (type(exc).__name__, exc)]
        if problems:
            failures += 1
            for problem in problems:
                _emit(args, "[BLOCKED] selftest.%s — %s" % (name, problem))
        else:
            _emit(args, "[OK] selftest.%s" % name)

    if yamlmini.cross_check.available:
        problems = yamlmini.cross_check(
            Path(configmod.EXAMPLE_CONFIG).read_text(encoding="utf-8")
            if Path(configmod.EXAMPLE_CONFIG).is_file()
            else ""
        )
        if problems:
            failures += 1
            for problem in problems:
                _emit(args, "[WARN] selftest.pyyaml — %s" % problem)
        else:
            _emit(args, "[OK] selftest.pyyaml (сверка с PyYAML)")
    else:
        _emit(args, "[WARN] selftest.pyyaml — PyYAML не установлен, сверка пропущена")

    if failures:
        return _finish(
            args,
            EXIT_SCHEMA,
            "[BLOCKED] selftest: %d проверок с ошибками" % failures,
            failures=failures,
        )
    return _finish(args, EXIT_OK, "[OK] selftest")


# ---------------------------------------------------------------------------
# Разбор аргументов
# ---------------------------------------------------------------------------


def build_parser(invocation=None):
    program = invocation or "trr"
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--workdir",
        "--root",
        dest="workdir",
        metavar="DIR",
        default=argparse.SUPPRESS,
        help="рабочая директория проекта (по умолчанию: поиск task-readiness-review.yaml вверх по дереву)",
    )
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="машинный вывод одной строкой JSON",
    )
    common.add_argument(
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS,
        help="печатать только ошибки",
    )
    common.add_argument(
        "--allow-external-file",
        action="store_true",
        default=argparse.SUPPRESS,
        help="разрешить --file вне рабочей директории (по умолчанию запрещено)",
    )

    parser = argparse.ArgumentParser(
        prog=program,
        description="Оценка готовности задач: проверка полноты и расчёт Story Points.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", metavar="подкоманда")

    init = subparsers.add_parser(
        "init", parents=[common], help="создать конфиг из примера"
    )
    init.add_argument("--force", action="store_true", help="перезаписать конфиг и state")
    init.add_argument(
        "--from-artifact",
        metavar="FILE",
        default=None,
        help="импортировать обученный бандл (.tar.gz) вместо train: "
        "stage=trained, модель и страница модели из артефакта",
    )
    init.add_argument(
        "--allow-foreign-project",
        action="store_true",
        help="разрешить импорт бандла из другого проекта Jira (будет [WARN])",
    )
    init.add_argument(
        "--non-interactive",
        action="store_true",
        help="не задавать вопросов (поведение по умолчанию)",
    )
    init.set_defaults(handler=cmd_init)

    resolve_sources = subparsers.add_parser(
        "resolve-sources",
        parents=[common],
        help="записать .task-readiness/resolved-sources.json из sources.* конфига",
    )
    resolve_sources.add_argument(
        "--re-resolve",
        action="store_true",
        help="перезаписать существующий resolved-sources.json",
    )
    resolve_sources.add_argument(
        "--agent",
        metavar="PATH",
        default=None,
        help="JSON с источниками, которые агент разрешил через MCP",
    )
    resolve_sources.add_argument(
        "--recursive",
        action="store_true",
        help="включить обход дочерних страниц (то же, что sources.confluence.recursive: true)",
    )
    resolve_sources.add_argument(
        "--pages-json",
        metavar="PATH",
        default=None,
        help="страницы дерева Confluence от агента: {id, title, parent_id, depth, body_excerpt}",
    )
    resolve_sources.set_defaults(handler=cmd_resolve_sources)

    match_sprints = subparsers.add_parser(
        "match-sprints",
        parents=[common],
        help="сопоставить названия спринтов (board_labels) с id по индексу Jira",
    )
    match_sprints.add_argument(
        "--labels",
        metavar="TEXT",
        required=True,
        help="названия спринтов как в UI Jira, через запятую",
    )
    match_sprints.add_argument(
        "--sprints-file",
        metavar="PATH",
        required=True,
        help="JSON-индекс спринтов: {name, id, state} или ответ board/<id>/sprint",
    )
    match_sprints.set_defaults(handler=cmd_match_sprints)

    match_fields = subparsers.add_parser(
        "match-fields",
        parents=[common],
        help="сопоставить имена полей Jira (Story Points) с id (customfield_…)",
    )
    match_fields.add_argument(
        "--names-json",
        metavar="PATH",
        required=True,
        help="JSON с именами полей: {key: имя} (jira.field_names) или массив имён",
    )
    match_fields.add_argument(
        "--fields-file",
        metavar="PATH",
        required=True,
        help="JSON-список полей Jira: ответ /rest/api/2/field или [{id, name}]",
    )
    match_fields.set_defaults(handler=cmd_match_fields)


    config_check = subparsers.add_parser(
        "config-check", parents=[common], help="проверить конфиг"
    )
    config_check.add_argument("--config", metavar="PATH", default=None)
    config_check.set_defaults(handler=cmd_config_check)

    doctor = subparsers.add_parser(
        "doctor", parents=[common], help="диагностика окружения и артефактов"
    )
    doctor.set_defaults(handler=cmd_doctor)

    params = subparsers.add_parser(
        "params",
        parents=[common],
        help="показать эвристические параметры weight/heat/connectivity и провенанс",
    )
    params.add_argument(
        "--task",
        metavar="KEY",
        default=None,
        help="взять снимок задачи из последнего context.json прогона",
    )
    params.add_argument(
        "--text-file",
        metavar="PATH",
        default=None,
        help="описание задачи из файла (markdown/text)",
    )
    params.add_argument(
        "--text", metavar="TEXT", default=None, help="описание задачи строкой"
    )
    params.add_argument("--issue-type", metavar="T", default=None, help="тип задачи")
    params.add_argument("--role", metavar="R", default=None, help="роль задачи")
    params.add_argument(
        "--labels", metavar="a,b", default=None, help="метки задачи через запятую"
    )
    params.add_argument(
        "--links", type=int, metavar="N", default=None, help="число issuelinks"
    )
    for _name, _text in (
        ("weight", "вес задачи (сложность), 0.0…1.0"),
        ("heat", "«теплота» (необходимость проработки), 0.0…1.0"),
        ("connectivity", "связанность (внешние интеграции), 0.0…1.0"),
    ):
        params.add_argument(
            "--%s" % _name,
            type=float,
            metavar="FLOAT",
            default=None,
            help="override %s: %s" % (_name, _text),
        )
    params.set_defaults(handler=cmd_params)

    state = subparsers.add_parser("state", parents=[common], help="работа с state.json")
    state_sub = state.add_subparsers(dest="state_command", metavar="get|set")
    state_get = state_sub.add_parser("get", parents=[common], help="прочитать значение")
    state_get.add_argument("key", help="точечный путь, например model_page.url")
    state_get.set_defaults(handler=cmd_state_get)
    state_set = state_sub.add_parser("set", parents=[common], help="записать значение")
    state_set.add_argument("key", help="точечный путь")
    state_set.add_argument("value", help="JSON-скаляр или строка")
    state_set.set_defaults(handler=cmd_state_set)

    validate = subparsers.add_parser(
        "validate", parents=[common], help="проверить артефакт по схеме"
    )
    validate.add_argument("artifact", help=", ".join(schema_lite.SCHEMA_NAMES))
    validate.add_argument("path", help="путь к JSON-артефакту")
    validate.set_defaults(handler=cmd_validate)

    stats = subparsers.add_parser("stats", parents=[common], help="посчитать norm/sprint-stats.json")
    stats.set_defaults(handler=lambda args: _run_lazy(LAZY_COMMANDS["stats"], args))

    calibrate = subparsers.add_parser(
        "calibrate", parents=[common], help="построить model/estimation-model.json"
    )
    calibrate.add_argument(
        "--reason",
        choices=("train", "enrich"),
        default="train",
        help="причина запуска: train (по умолчанию) или enrich (дозаполнение)",
    )
    calibrate.set_defaults(handler=lambda args: _run_lazy(LAZY_COMMANDS["calibrate"], args))

    vectors = subparsers.add_parser(
        "vectors",
        parents=[common],
        help="векторы текстов задач: build | similar | calibrate",
    )
    vectors_sub = vectors.add_subparsers(
        dest="vectors_command", metavar="build|similar|calibrate"
    )

    vectors_build = vectors_sub.add_parser(
        "build", parents=[common], help="построить norm/task-vectors.json"
    )
    vectors_build.add_argument(
        "--top-terms",
        type=int,
        default=None,
        metavar="N",
        help="сколько термов хранить на вектор (по умолчанию estimation.vector.top_terms)",
    )
    vectors_build.add_argument(
        "--weight-word",
        type=float,
        default=None,
        metavar="W",
        help="вес словесной части гибрида 0..1 (по умолчанию estimation.vector.weight_word)",
    )
    vectors_build.add_argument(
        "--min-corpus",
        type=int,
        default=None,
        metavar="N",
        help="минимальный корпус; меньше — [BLOCKED] (по умолчанию estimation.vector.min_corpus)",
    )
    vectors_build.set_defaults(handler=lambda args: _run_lazy(LAZY_COMMANDS["vectors"], args))

    vectors_similar = vectors_sub.add_parser(
        "similar", parents=[common], help="найти похожие задачи по тексту"
    )
    vectors_similar.add_argument("--task", metavar="KEY", default=None)
    vectors_similar.add_argument(
        "--text-file", metavar="PATH", default=None, help="файл с текстом запроса"
    )
    vectors_similar.add_argument(
        "--text", metavar="TEXT", default=None, help="текст запроса строкой"
    )
    vectors_similar.add_argument(
        "--top", type=int, default=None, metavar="N", help="сколько похожих вернуть"
    )
    vectors_similar.add_argument(
        "--same-bucket",
        action="store_true",
        help="искать только в бакете запроса (нужен --task)",
    )
    vectors_similar.set_defaults(handler=lambda args: _run_lazy(LAZY_COMMANDS["vectors"], args))

    vectors_calibrate = vectors_sub.add_parser(
        "calibrate", parents=[common], help="пересчитать пороги p90/p50"
    )
    vectors_calibrate.set_defaults(
        handler=lambda args: _run_lazy(LAZY_COMMANDS["vectors"], args)
    )

    check = subparsers.add_parser("check", parents=[common], help="проверить задачу")
    check.add_argument("--task", required=True, metavar="KEY")
    check.add_argument("--with-dependencies", action="store_true")
    check.add_argument("--run", metavar="RUN-ID", default=None)
    check.add_argument(
        "--draft",
        action="store_true",
        help="не планировать комментарий с вопросами в Jira (только черновик)",
    )
    check.add_argument(
        "--no-jira",
        action="store_true",
        help="не планировать комментарий с вопросами в Jira",
    )
    check.add_argument(
        "--comment-id",
        metavar="ID",
        default=None,
        help="id уже опубликованного комментария с вопросами — записать в state",
    )
    check.add_argument(
        "--url",
        metavar="URL",
        default=None,
        help="URL комментария (по умолчанию собирается из JIRA_URL)",
    )
    for _name, _text in (
        ("weight", "вес задачи (сложность), 0.0…1.0"),
        ("heat", "«теплота» (необходимость проработки), 0.0…1.0"),
        ("connectivity", "связанность (внешние интеграции), 0.0…1.0"),
    ):
        check.add_argument(
            "--%s" % _name,
            type=float,
            metavar="FLOAT",
            default=None,
            help="override %s: %s — пишется в context.json" % (_name, _text),
        )
    check.set_defaults(
        handler=lambda args: _run_lazy(LAZY_COMMANDS["check"], args)
    )

    estimate = subparsers.add_parser("estimate", parents=[common], help="посчитать оценку")
    estimate.add_argument("--task", required=True, metavar="KEY")
    estimate.add_argument("--run", metavar="RUN-ID", default=None)
    for _name, _text in (
        ("weight", "вес задачи (сложность), 0.0…1.0"),
        ("heat", "«теплота» (необходимость проработки), 0.0…1.0"),
        ("connectivity", "связанность (внешние интеграции), 0.0…1.0"),
    ):
        estimate.add_argument(
            "--%s" % _name,
            type=float,
            metavar="FLOAT",
            default=None,
            help="override %s: %s" % (_name, _text),
        )
    estimate.set_defaults(
        handler=lambda args: _run_lazy(LAZY_COMMANDS["estimate"], args)
    )

    report = subparsers.add_parser("report", parents=[common], help="отрендерить отчёт")
    report.add_argument("--task", metavar="KEY", default=None)
    report.add_argument("--run", metavar="RUN-ID", default=None)
    report.add_argument("--delta", action="store_true")
    report.add_argument(
        "--model",
        action="store_true",
        help="перерендерить model/estimation-model.md из JSON (без --task)",
    )
    report.set_defaults(
        handler=lambda args: _run_lazy(LAZY_COMMANDS["report"], args)
    )

    publish = subparsers.add_parser(
        "publish", parents=[common], help="опубликовать результат комментарием в задачу Jira"
    )
    publish.add_argument(
        "--task",
        metavar="KEY",
        default=None,
        help="ключ задачи: комментарий к report.md публикуется в неё",
    )
    publish.add_argument(
        "--target",
        choices=statemod.PAGE_TARGETS,
        default=None,
        help="дополнительно опубликовать страницу/заметку (после комментария в Jira)",
    )
    publish.add_argument("--ref", metavar="ID", default=None, help="id страницы/заметки")
    publish.add_argument("--url", metavar="URL", default=None, help="URL публикации")
    publish.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="опубликованный файл (считается sha256)",
    )
    publish.add_argument(
        "--model",
        action="store_true",
        help="это страница модели: обновить state.model_page",
    )
    publish.add_argument(
        "--no-stage",
        action="store_true",
        help="не переводить этап в published (публикация страницы модели)",
    )
    publish.add_argument(
        "--plan-jira",
        action="store_true",
        help="только напечатать план комментария (create|update), ничего не писать",
    )
    publish.add_argument(
        "--run",
        metavar="RUN-ID",
        default=None,
        help="прогон задачи для тел комментариев (по умолчанию последний)",
    )
    publish.add_argument(
        "--draft",
        action="store_true",
        help="только напечатать текст комментария; в Jira не публиковать, state не менять",
    )
    publish.add_argument(
        "--no-jira",
        action="store_true",
        help="не публиковать в Jira: тексты уходят в actions/jira-validation.md и "
        "actions/jira-estimate.md (код 0)",
    )
    publish.add_argument(
        "--comment-id",
        metavar="ID",
        default=None,
        help="id уже опубликованного комментария «Результаты оценки» (легаси-алиас "
        "--comment-id-estimate)",
    )
    publish.add_argument(
        "--comment-id-validation",
        metavar="ID",
        default=None,
        help="id опубликованного комментария «Результаты валидации» — записать в state",
    )
    publish.add_argument(
        "--comment-id-estimate",
        metavar="ID",
        default=None,
        help="id опубликованного комментария «Результаты оценки» — записать в state",
    )
    publish.set_defaults(handler=cmd_publish)

    render_norm = subparsers.add_parser(
        "render-norm", parents=[common], help="перерендерить .md-зеркала norm/ и model/"
    )
    render_norm.set_defaults(handler=cmd_render_norm)

    model_hash = subparsers.add_parser(
        "model-hash", parents=[common], help="sha256 и версия модели"
    )
    model_hash.set_defaults(handler=cmd_model_hash)

    model_payload = subparsers.add_parser(
        "model-page-payload",
        parents=[common],
        help="тело страницы модели для Confluence (json|storage|md)",
    )
    model_payload.add_argument(
        "--format",
        choices=("json", "storage", "md"),
        default="json",
        help="json — тело запроса POST/PUT (по умолчанию); storage — XHTML; md — как есть",
    )
    model_payload.add_argument(
        "--out", metavar="PATH", default=None, help="писать в файл вместо stdout"
    )
    model_payload.add_argument(
        "--title",
        metavar="TEXT",
        default=None,
        help="заголовок страницы (по умолчанию «Модель оценки Story Points (версия N)»)",
    )
    model_payload.add_argument(
        "--page-version",
        metavar="N",
        type=int,
        default=None,
        help="фактическая версия страницы Confluence для PUT (GET ?expand=version "
        "+ 1); без флага берётся state.model_page.version (это версия модели) с [WARN]",
    )
    model_payload.set_defaults(handler=cmd_model_page_payload)

    snapshot_hash = subparsers.add_parser(
        "snapshot-hash",
        parents=[common],
        help="sha256 канонического JSON снимка задачи",
    )
    snapshot_hash.add_argument("--task", required=True, metavar="KEY")
    snapshot_hash.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="файл снимка (например .task-readiness/.snapshot-fresh.json); "
        "по умолчанию context.json последнего прогона",
    )
    snapshot_hash.add_argument(
        "--run", metavar="RUN-ID", default=None, help="конкретный прогон"
    )
    snapshot_hash.set_defaults(handler=cmd_snapshot_hash)

    diff_values = subparsers.add_parser(
        "diff-values",
        parents=[common],
        help="сравнить context.json двух последних прогонов",
    )
    diff_values.add_argument("--task", required=True, metavar="KEY")
    diff_values.add_argument(
        "--field",
        action="append",
        default=None,
        metavar="NAME",
        help="поле снимка (точечный путь, напр. sp или fields.status); можно несколько",
    )
    diff_values.add_argument(
        "--all",
        action="store_true",
        help="сравнить все ключи верхнего уровня, кроме волатильных (sources)",
    )
    diff_values.set_defaults(handler=cmd_diff_values)

    merge_sample = subparsers.add_parser(
        "merge-sample",
        parents=[common],
        help="влить новые строки в norm/sprint-sample.json",
    )
    merge_sample.add_argument(
        "--target",
        metavar="PATH",
        default=None,
        help="куда писать (по умолчанию .task-readiness/norm/sprint-sample.json)",
    )
    merge_sample.add_argument(
        "--source",
        metavar="PATH",
        default=None,
        help="откуда брать новые строки (по умолчанию .task-readiness/.sprint-sample-new.json)",
    )
    merge_sample.set_defaults(handler=cmd_merge_sample)

    synth = subparsers.add_parser(
        "synth",
        parents=[common],
        help="синтетический полигон: N снимков задач из выборки спринтов",
    )
    synth.add_argument(
        "--count",
        type=int,
        default=1000,
        metavar="N",
        help="сколько задач сгенерировать (по умолчанию 1000)",
    )
    synth.add_argument(
        "--out",
        metavar="DIR",
        required=True,
        help="каталог для contexts.jsonl и manifest.json",
    )
    synth.add_argument(
        "--seed",
        type=int,
        default=42,
        metavar="N",
        help="зерно ГПСЧ: один seed → побайтно один contexts.jsonl (по умолчанию 42)",
    )
    synth.add_argument(
        "--from-sprints",
        metavar="IDS",
        default=None,
        help="id спринтов Jira через запятую (20365,20366) — сэмплировать только их строки",
    )
    synth.add_argument(
        "--include-edge",
        action="store_true",
        help="добавить 2 %% edge-случаев (пустое/100 КБ описание, 100 связей, "
        "юникод, код-блоки, HTML, тип/роль вне словаря, все поля null)",
    )
    synth.add_argument(
        "--sample",
        metavar="PATH",
        default=None,
        help="выборка спринтов (по умолчанию .task-readiness/norm/sprint-sample.json)",
    )
    synth.add_argument(
        "--coverage-all-buckets",
        dest="coverage_all_buckets",
        action="store_true",
        default=True,
        help="покрыть все тройки (role, issue_type, work_kind) модели: "
        "не менее --coverage-quota снимков на каждую (по умолчанию включено)",
    )
    synth.add_argument(
        "--no-coverage-all-buckets",
        dest="coverage_all_buckets",
        action="store_false",
        help="выключить покрытие троек модели (оси только из выборки спринтов)",
    )
    synth.add_argument(
        "--coverage-quota",
        type=int,
        default=20,
        metavar="N",
        help="сколько снимков на каждую тройку модели при покрытии (по умолчанию 20)",
    )
    synth.set_defaults(handler=lambda args: _run_lazy(LAZY_COMMANDS["synth"], args))

    synth_run = subparsers.add_parser(
        "synth-run",
        parents=[common],
        help="прогнать check+estimate по contexts.jsonl in-process",
    )
    synth_run.add_argument(
        "--dir",
        metavar="DIR",
        required=True,
        help="каталог с contexts.jsonl (выход trr synth)",
    )
    synth_run.add_argument(
        "--out",
        metavar="DIR",
        default=None,
        help="куда писать summary.json и records.jsonl (по умолчанию <dir>/out)",
    )
    synth_run.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="прогнать только первые N задач (быстрый прогон)",
    )
    synth_run.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="потоков ThreadPoolExecutor; результат сортируется по case_id "
        "(по умолчанию 4)",
    )
    synth_run.add_argument(
        "--record",
        dest="record",
        action="store_true",
        default=None,
        help="записать прогон в SQLite (synth_runs + metrics scope='synth'); "
        "по умолчанию пишется, если storage.sqlite.enabled",
    )
    synth_run.add_argument(
        "--no-record",
        dest="record",
        action="store_false",
        help="не писать прогон в SQLite",
    )
    synth_run.set_defaults(handler=lambda args: _run_lazy(LAZY_COMMANDS["synth"], args))

    db = subparsers.add_parser(
        "db",
        parents=[common],
        help="локальное SQLite-зеркало: init | check | ingest | stats | export | query",
    )
    db_sub = db.add_subparsers(
        dest="db_command", metavar="init|check|ingest|stats|export|query"
    )

    db_sub.add_parser(
        "init", parents=[common], help="создать/мигрировать файл БД (идемпотентно)"
    ).set_defaults(handler=cmd_db)
    db_sub.add_parser(
        "check", parents=[common], help="integrity_check, версия схемы, счётчики, размер"
    ).set_defaults(handler=cmd_db)
    db_sub.add_parser(
        "ingest", parents=[common], help="бэкфилл зеркала из артефактов на диске"
    ).set_defaults(handler=cmd_db)
    db_sub.add_parser(
        "stats", parents=[common], help="краткая сводка: таблица → строк"
    ).set_defaults(handler=cmd_db)

    db_export = db_sub.add_parser(
        "export", parents=[common], help="JSON-дамп всех таблиц"
    )
    db_export.add_argument(
        "--out", required=True, metavar="FILE", help="файл JSON-дампа"
    )
    db_export.set_defaults(handler=cmd_db)

    db_query = db_sub.add_parser(
        "query", parents=[common], help="read-only SQL: SELECT / WITH / PRAGMA"
    )
    db_query.add_argument("--sql", required=True, metavar="SQL", help="запрос только на чтение")
    db_query.add_argument(
        "--limit", type=int, default=None, metavar="N", help="сколько строк вернуть"
    )
    db_query.set_defaults(handler=cmd_db)

    artifact = subparsers.add_parser(
        "artifact",
        parents=[common],
        help="экспорт/импорт обученных артефактов (.tar.gz)",
    )
    artifact_sub = artifact.add_subparsers(
        dest="artifact_command", metavar="pack|inspect|unpack|plan|record"
    )

    artifact_pack = artifact_sub.add_parser(
        "pack", parents=[common], help="собрать переносимый бандл обучения"
    )
    artifact_pack.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help="куда писать бандл (по умолчанию .task-readiness/task-readiness-model-v<версия>.tar.gz)",
    )
    artifact_pack.add_argument(
        "--no-sprint-sample",
        action="store_true",
        help="не класть norm/sprint-sample.json (сырую выборку спринтов)",
    )
    artifact_pack.set_defaults(handler=cmd_artifact_pack)

    artifact_inspect = artifact_sub.add_parser(
        "inspect", parents=[common], help="напечатать манифест бандла сводкой"
    )
    artifact_inspect.add_argument("file", metavar="FILE", help="путь к .tar.gz")
    artifact_inspect.set_defaults(handler=cmd_artifact_inspect)

    artifact_unpack = artifact_sub.add_parser(
        "unpack", parents=[common], help="развернуть бандл в .task-readiness/"
    )
    artifact_unpack.add_argument("file", metavar="FILE", help="путь к .tar.gz")
    artifact_unpack.add_argument(
        "--force",
        action="store_true",
        help="перезаписать уже лежащие артефакты обучения",
    )
    artifact_unpack.add_argument(
        "--allow-foreign-project",
        action="store_true",
        help="разрешить бандл из другого проекта Jira (будет [WARN])",
    )
    artifact_unpack.set_defaults(handler=cmd_artifact_unpack)

    artifact_plan = artifact_sub.add_parser(
        "plan", parents=[common], help="куда публиковать бандл (по artifacts.*)"
    )
    artifact_plan.add_argument(
        "--target",
        choices=[name for name in configmod.ARTIFACT_TARGETS if name != "none"],
        required=True,
        help="цель публикации бандла",
    )
    artifact_plan.set_defaults(handler=cmd_artifact_plan)

    artifact_record = artifact_sub.add_parser(
        "record", parents=[common], help="записать публикацию бандла в state.artifacts[]"
    )
    artifact_record.add_argument(
        "--target", choices=statemod.ARTIFACT_TARGETS, required=True
    )
    artifact_record.add_argument("--ref", metavar="REF", required=True)
    artifact_record.add_argument("--url", metavar="URL", required=True)
    artifact_record.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="файл бандла (считается sha256)",
    )
    artifact_record.set_defaults(handler=cmd_artifact_record)

    selftest = subparsers.add_parser(
        "selftest", parents=[common], help="самопроверка без сети"
    )
    selftest.set_defaults(handler=cmd_selftest)

    return parser

def main(argv=None, invocation=None):
    parser = build_parser(invocation)
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    args.workdir = configmod.resolve_workdir(getattr(args, "workdir", None))
    args.root = args.workdir
    args.json = bool(getattr(args, "json", False))
    args.quiet = bool(getattr(args, "quiet", False))

    if getattr(args, "command", None) == "state" and getattr(
        args, "state_command", None
    ) is None:
        print(
            "[MISSING] state — нужна подкоманда: state get <key> или state set <key> <value>"
        )
        return EXIT_CONFIG

    if getattr(args, "command", None) == "artifact" and getattr(
        args, "artifact_command", None
    ) is None:
        print(
            "[MISSING] artifact — нужна подкоманда: pack, inspect, unpack, plan или record"
        )
        return EXIT_CONFIG

    if getattr(args, "command", None) == "vectors" and getattr(
        args, "vectors_command", None
    ) is None:
        print(
            "[MISSING] vectors — нужна подкоманда: build, similar или calibrate"
        )
        return EXIT_CONFIG

    if getattr(args, "command", None) == "db" and getattr(
        args, "db_command", None
    ) is None:
        print(
            "[MISSING] db — нужна подкоманда: init, check, ingest, stats, export "
            "или query"
        )
        return EXIT_CONFIG

    problem = _validate_args(args)
    if problem is not None:
        return _finish(args, EXIT_BLOCKED, problem)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return EXIT_BLOCKED
    operation = getattr(args, "command", None) or "trr"
    try:
        return int(handler(args))
    except limits.LimitError as exc:
        # Превышение объёма входного JSON — не «битый артефакт» (5), а
        # отсутствие пригодных данных (4).
        return _finish(args, EXIT_MISSING, "[MISSING] %s" % exc)
    except OSError as exc:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s: %s — проверьте права доступа и наличие файлов "
            "в рабочей директории" % (operation, exc),
        )
    except ValueError as exc:
        return _finish(
            args,
            EXIT_MISSING,
            "[MISSING] %s: %s — проверьте формат входных артефактов "
            "(JSON и схему)" % (operation, exc),
        )


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Локальное SQLite-зеркало артефактов, метрик и векторов.

Зачем: артефакты скилла — это файлы (`norm/*.json`, `model/*.json`, `runs/*`).
Файлы хороши как контракт и как то, что публикуется, но плохи как база: по ним
нельзя одним запросом ответить «сколько задач FE с `sp=3` закрыто в 26.19», не
видно истории метрик и не хранятся векторы. Модуль пишет **зеркало** тех же
данных в один файл SQLite — рядом с артефактами, по умолчанию включённое.

Правила, зафиксированные здесь:

- только stdlib (`sqlite3`), никаких внешних зависимостей;
- файлы остаются источником истины: SQLite — зеркало, а не замена. Ни один шаг
  пайплайна не читает из БД, чтобы посчитать результат;
- запись идёт **после** успешного шага и **никогда** не валит пайплайн: любая
  ошибка БД (нет прав, диск, битый файл) — это `[WARN] storage: …` в stderr и
  продолжение работы с кодом выхода основного шага;
- все вставки идемпотентны (`INSERT … ON CONFLICT … DO UPDATE`): повторный
  `trr db ingest` не плодит дубли;
- секретов в БД нет: токены не пишутся, конфиг целиком не сохраняется.

Схема версионируется `PRAGMA user_version`; миграции — только вперёд.
"""

import functools
import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

from trr_impl import config as configmod
from trr_impl import paths as pathmod

__all__ = [
    "SCHEMA_VERSION",
    "STATE_DIR",
    "TABLES",
    "connect",
    "connect_readonly",
    "current_model_checksum",
    "export_json",
    "hook",
    "ingest_workdir",
    "init_db",
    "is_read_only_sql",
    "open_for",
    "pack_vector",
    "path_for",
    "query_rows",
    "record_estimate",
    "record_event",
    "record_metric",
    "record_model",
    "record_publication",
    "record_reference",
    "record_run",
    "record_sample",
    "record_similar",
    "record_stats",
    "record_synth_run",
    "record_validation",
    "record_vectors",
    "save_check",
    "save_estimate",
    "save_event",
    "save_model",
    "save_publication",
    "save_similar",
    "save_stats",
    "save_synth_run",
    "save_vectors",
    "stats",
    "unpack_vector",
]

STATE_DIR = pathmod.STATE_DIR_RELATIVE

# Версия схемы. Растёт только вместе с новой миграцией в `_MIGRATIONS`.
SCHEMA_VERSION = 5

# Плейсхолдер контрольной суммы, когда модель ещё не обучена: строки статистики
# без версии модели не должны смешиваться с историей реальной версии.
PLACEHOLDER_CHECKSUM = "unknown"

# Таблицы в порядке создания: нужен и `db stats`, и `db export`.
TABLES = (
    "meta",
    "reference_pages",
    "reference_buckets",
    "reference_levels",
    "sprint_rows",
    "sprint_stats",
    "model_versions",
    "model_buckets",
    "gap_rules",
    "tasks",
    "runs",
    "validations",
    "estimates",
    "estimate_roles",
    "vectors",
    "vector_meta",
    "similarities",
    "publications",
    "metrics",
    "events",
    "synth_runs",
)

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reference_pages (
        page_id TEXT PRIMARY KEY,
        title TEXT,
        space_key TEXT,
        depth INTEGER,
        version INTEGER,
        body_sha256 TEXT,
        body_len INTEGER,
        retrieved_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reference_buckets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_checksum TEXT NOT NULL,
        role TEXT NOT NULL,
        work_kind TEXT NOT NULL,
        value REAL,
        description TEXT,
        evidence TEXT,
        UNIQUE (model_checksum, role, work_kind)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sprint_rows (
        sprint TEXT NOT NULL,
        task_key TEXT NOT NULL,
        issue_type TEXT,
        role TEXT,
        sp REAL,
        qa_estimation REAL,
        has_testing INTEGER,
        status TEXT,
        labels TEXT,
        summary_sha256 TEXT,
        weight REAL,
        heat REAL,
        connectivity REAL,
        sample_checksum TEXT,
        PRIMARY KEY (task_key, sprint)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sprint_stats (
        model_checksum TEXT NOT NULL,
        role TEXT NOT NULL,
        issue_type TEXT NOT NULL,
        work_kind TEXT NOT NULL,
        n INTEGER,
        mean REAL,
        median REAL,
        p25 REAL,
        p75 REAL,
        min REAL,
        max REAL,
        coverage TEXT,
        PRIMARY KEY (model_checksum, role, issue_type, work_kind)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_versions (
        version INTEGER PRIMARY KEY,
        checksum TEXT UNIQUE,
        generated_at TEXT,
        payload TEXT,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_buckets (
        model_checksum TEXT NOT NULL,
        role TEXT NOT NULL,
        issue_type TEXT NOT NULL,
        work_kind TEXT NOT NULL,
        base REAL,
        factor REAL,
        expected REAL,
        range_low REAL,
        range_high REAL,
        n INTEGER,
        confidence TEXT,
        reference TEXT,
        PRIMARY KEY (model_checksum, role, issue_type, work_kind)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gap_rules (
        model_checksum TEXT NOT NULL,
        rule_id TEXT NOT NULL,
        condition TEXT,
        penalty_steps INTEGER,
        applies_to TEXT,
        PRIMARY KEY (model_checksum, rule_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        task_key TEXT PRIMARY KEY,
        issue_type TEXT,
        role TEXT,
        work_kind TEXT,
        sp REAL,
        qa_estimation REAL,
        weight REAL,
        heat REAL,
        connectivity REAL,
        params_source TEXT,
        first_seen TEXT,
        last_seen TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        task_key TEXT,
        stage TEXT,
        workdir TEXT,
        created_at TEXT,
        model_checksum TEXT,
        config_sha256 TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS validations (
        run_id TEXT PRIMARY KEY,
        task_key TEXT,
        verdict TEXT,
        checks_total INTEGER,
        checks_failed INTEGER,
        gaps_total INTEGER,
        payload TEXT,
        checked_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS estimates (
        run_id TEXT PRIMARY KEY,
        task_key TEXT,
        model_version INTEGER,
        model_checksum TEXT,
        total_expected REAL,
        total_low REAL,
        total_high REAL,
        params_multiplier REAL,
        payload TEXT,
        estimated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS estimate_roles (
        run_id TEXT NOT NULL,
        role TEXT NOT NULL,
        expected REAL,
        range_low REAL,
        range_high REAL,
        confidence TEXT,
        provenance TEXT,
        PRIMARY KEY (run_id, role)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vectors (
        task_key TEXT NOT NULL,
        model_version INTEGER NOT NULL,
        dim INTEGER,
        vector BLOB,
        terms TEXT,
        built_at TEXT,
        PRIMARY KEY (task_key, model_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vector_meta (
        model_version INTEGER PRIMARY KEY,
        built_at TEXT,
        corpus INTEGER,
        dim INTEGER,
        config TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS similarities (
        task_key TEXT NOT NULL,
        other_key TEXT NOT NULL,
        cosine REAL,
        same_bucket INTEGER,
        model_version INTEGER NOT NULL,
        PRIMARY KEY (task_key, other_key, model_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS publications (
        target TEXT NOT NULL,
        ref TEXT NOT NULL,
        url TEXT,
        sha256 TEXT,
        published_at TEXT,
        PRIMARY KEY (target, ref)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        scope TEXT,
        name TEXT,
        value REAL,
        labels TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        kind TEXT,
        payload TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sprint_rows_role_type ON sprint_rows(role, issue_type)",
    "CREATE INDEX IF NOT EXISTS idx_estimates_task ON estimates(task_key)",
    "CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_key)",
    "CREATE INDEX IF NOT EXISTS idx_metrics_scope_name ON metrics(scope, name)",
)

# Миграция 2: полная матрица эталона (строки шкалы Story Points). Бакеты
# отвечают на вопрос «сколько стоит вид работ», уровни — «что написано в
# таблице на этой строке»; второе нельзя вывести из первого.
_DDL_V2 = (
    """
    CREATE TABLE IF NOT EXISTS reference_levels (
        page_id TEXT NOT NULL,
        sp INTEGER NOT NULL,
        description TEXT,
        uncertainty TEXT,
        refactoring TEXT,
        research TEXT,
        decomposition TEXT,
        time_hint TEXT,
        examples TEXT,
        params_hint TEXT,
        PRIMARY KEY (page_id, sp)
    )
    """,
)

# Миграция 3: множитель параметров в модели и оценке. Профиль бакета и его
# множитель — часть модели (данные, а не код); `params_json` в `estimates` —
# снимок `estimate.json.params`, чтобы провенанс множителя был в БД, а не
# только в файле. Колонки добавляются идемпотентно (`_add_column`): повторный
# прогон шага не должен падать на `duplicate column name`.
_V3_COLUMNS = (
    ("model_buckets", "params_multiplier", "REAL"),
    ("model_buckets", "params_profile", "TEXT"),
    ("estimates", "params_json", "TEXT"),
)

# Миграция 4: результаты синтетического полигона. `summary` — полный
# `summary.json` (JSON-текст): схема метрик полигона меняется чаще, чем схема
# БД, и разбирать её колонками значило бы ломать миграцию на каждое новое
# поле. Числовые метрики дополнительно расходятся по `metrics(scope='synth')`.
_DDL_V4 = (
    """
    CREATE TABLE IF NOT EXISTS synth_runs (
        run_id TEXT PRIMARY KEY,
        created_at TEXT,
        seed INTEGER,
        count INTEGER,
        model_checksum TEXT,
        summary TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_synth_runs_created ON synth_runs(created_at)",
)

# Миграция 5: ключ прогона — `(task_key, run_id)`, а не `run_id`.
#
# `RUN-ID` — это метка времени (`2026-11-18T18-00-00Z`), одинаковая у всех задач,
# которые прогоняли в одну минуту: с `PRIMARY KEY(run_id)` двенадцать каталогов
# прогонов двух задач схлопывались в шесть строк, и последняя запись затирала
# первую. `task_key` входит в ключ и в `validations`/`estimates`/`estimate_roles`:
# разбивка по ролям принадлежит прогону, а прогон — задаче.
#
# `publications.sha256` держал две разные величины: sha256 опубликованного файла
# (пишет `publish`) и контрольную сумму модели (подставлял бэкфилл из
# `state.model_page.hash`). Схема 5 разделяет их: `content_sha256` — файл,
# `model_checksum` — модель (nullable).
_V5_RUNS = """
CREATE TABLE {name} (
    task_key TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL,
    stage TEXT,
    workdir TEXT,
    created_at TEXT,
    model_checksum TEXT,
    config_sha256 TEXT,
    PRIMARY KEY (task_key, run_id)
)
"""

_V5_VALIDATIONS = """
CREATE TABLE {name} (
    task_key TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL,
    verdict TEXT,
    checks_total INTEGER,
    checks_failed INTEGER,
    gaps_total INTEGER,
    payload TEXT,
    checked_at TEXT,
    PRIMARY KEY (task_key, run_id)
)
"""

_V5_ESTIMATES = """
CREATE TABLE {name} (
    task_key TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL,
    model_version INTEGER,
    model_checksum TEXT,
    total_expected REAL,
    total_low REAL,
    total_high REAL,
    params_multiplier REAL,
    payload TEXT,
    estimated_at TEXT,
    params_json TEXT,
    PRIMARY KEY (task_key, run_id)
)
"""

_V5_ESTIMATE_ROLES = """
CREATE TABLE {name} (
    task_key TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL,
    role TEXT NOT NULL,
    expected REAL,
    range_low REAL,
    range_high REAL,
    confidence TEXT,
    provenance TEXT,
    PRIMARY KEY (task_key, run_id, role)
)
"""

_V5_PUBLICATIONS = """
CREATE TABLE {name} (
    target TEXT NOT NULL,
    ref TEXT NOT NULL,
    url TEXT,
    content_sha256 TEXT,
    model_checksum TEXT,
    published_at TEXT,
    PRIMARY KEY (target, ref)
)
"""


def _table_exists(conn, table):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (str(table),)
    ).fetchone()
    return row is not None


def _table_columns(conn, table):
    """`[(имя, позиция в PRIMARY KEY|0)]` — форма таблицы до пересоздания."""
    try:
        rows = conn.execute("PRAGMA table_info(%s)" % str(table)).fetchall()
    except sqlite3.Error:
        return []
    return [(str(row[1]), int(row[5] or 0)) for row in rows]


def _primary_key(conn, table):
    """Имена колонок первичного ключа в его порядке (`()` — ключа нет)."""
    keyed = [(position, name) for name, position in _table_columns(conn, table) if position]
    return tuple(name for _position, name in sorted(keyed))


def _recreate(conn, table, ddl, key, columns, expressions=None, indexes=()):
    """Пересоздать таблицу с новым ключом, перенеся данные.

    Идемпотентно: таблица уже с нужным ключом и всеми колонками — no-op.
    `expressions` — подмена выражения переноса для колонки (например
    `task_key` из старой nullable-колонки: новая объявлена `NOT NULL`).
    """
    if not _table_exists(conn, table):
        conn.execute(ddl.format(name=table))
        for statement in indexes:
            conn.execute(statement)
        return False
    present = {name for name, _position in _table_columns(conn, table)}
    if _primary_key(conn, table) == tuple(key) and set(columns) <= present:
        return False
    expressions = expressions if isinstance(expressions, dict) else {}
    staging = "%s__v5" % table
    conn.execute("DROP TABLE IF EXISTS %s" % staging)
    conn.execute(ddl.format(name=staging))
    copied = [name for name in columns if name in present]
    if copied:
        sources = [expressions.get(name, name) for name in copied]
        conn.execute(
            "INSERT OR REPLACE INTO %s (%s) SELECT %s FROM %s"
            % (staging, ", ".join(copied), ", ".join(sources), table)
        )
    conn.execute("DROP TABLE %s" % table)
    conn.execute("ALTER TABLE %s RENAME TO %s" % (staging, table))
    for statement in indexes:
        conn.execute(statement)
    return True


def _add_column(conn, table, column, declaration):
    """Идемпотентный `ALTER TABLE … ADD COLUMN`: колонка уже есть — no-op."""
    present = {name for name, _position in _table_columns(conn, table)}
    if column in present:
        return False
    conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, declaration))
    return True


def _migrate_v3(conn):
    """Схема 3: колонки множителя параметров (см. `_V3_COLUMNS`)."""
    for table, column, declaration in _V3_COLUMNS:
        _add_column(conn, table, column, declaration)


def _migrate_publications(conn):
    """Разделить `sha256` на `content_sha256` (файл) и `model_checksum` (модель).

    Старое значение — либо sha256 файла, либо контрольная сумма модели. Различить
    их можно по `model_versions`: сумма, которая там есть, — это модель. Строку,
    где суммы нет, считаем файлом (так писал `publish`).
    """
    if not _table_exists(conn, "publications"):
        conn.execute(_V5_PUBLICATIONS.format(name="publications"))
        return False
    present = {name for name, _position in _table_columns(conn, "publications")}
    if {"content_sha256", "model_checksum"} <= present:
        return False
    staging = "publications__v5"
    conn.execute("DROP TABLE IF EXISTS %s" % staging)
    conn.execute(_V5_PUBLICATIONS.format(name=staging))
    columns = (
        "target",
        "ref",
        "url",
        "content_sha256",
        "model_checksum",
        "published_at",
    )
    if "sha256" in present:
        known = "sha256 IN (SELECT checksum FROM model_versions)"
        conn.execute(
            "INSERT OR REPLACE INTO %s (%s) SELECT target, ref, url, "
            "CASE WHEN %s THEN NULL ELSE sha256 END, "
            "CASE WHEN %s THEN sha256 ELSE NULL END, published_at "
            "FROM publications" % (staging, ", ".join(columns), known, known)
        )
    else:
        copied = [name for name in columns if name in present]
        conn.execute(
            "INSERT OR REPLACE INTO %s (%s) SELECT %s FROM publications"
            % (staging, ", ".join(copied), ", ".join(copied))
        )
    conn.execute("DROP TABLE publications")
    conn.execute("ALTER TABLE %s RENAME TO publications" % staging)
    return True


def _drop_orphan_roles(conn):
    """Удалить разбивку по ролям, за которой нет прогона (`runs(task_key, run_id)`).

    Схема 5 добавила `task_key` в ключ; строки, перенесённые из старой таблицы,
    получили `task_key=''` и остались сиротами: прогона с таким ключом нет,
    запрос «роли прогона» их не видит, но таблицу они засоряют. Возвращает
    число удалённых строк.
    """
    cursor = conn.execute(
        "DELETE FROM estimate_roles WHERE task_key='' AND NOT EXISTS ("
        "SELECT 1 FROM runs WHERE runs.task_key=estimate_roles.task_key "
        "AND runs.run_id=estimate_roles.run_id)"
    )
    return int(cursor.rowcount or 0)


def _migrate_v5(conn):
    """Схема 5: ключ прогонов и семантика публикаций (см. комментарий выше)."""
    _recreate(
        conn,
        "runs",
        _V5_RUNS,
        ("task_key", "run_id"),
        (
            "task_key",
            "run_id",
            "stage",
            "workdir",
            "created_at",
            "model_checksum",
            "config_sha256",
        ),
        expressions={"task_key": "COALESCE(task_key, '')"},
        indexes=("CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_key)",),
    )
    _recreate(
        conn,
        "validations",
        _V5_VALIDATIONS,
        ("task_key", "run_id"),
        (
            "task_key",
            "run_id",
            "verdict",
            "checks_total",
            "checks_failed",
            "gaps_total",
            "payload",
            "checked_at",
        ),
        expressions={"task_key": "COALESCE(task_key, '')"},
    )
    _recreate(
        conn,
        "estimates",
        _V5_ESTIMATES,
        ("task_key", "run_id"),
        (
            "task_key",
            "run_id",
            "model_version",
            "model_checksum",
            "total_expected",
            "total_low",
            "total_high",
            "params_multiplier",
            "payload",
            "estimated_at",
            "params_json",
        ),
        expressions={"task_key": "COALESCE(task_key, '')"},
        indexes=("CREATE INDEX IF NOT EXISTS idx_estimates_task ON estimates(task_key)",),
    )
    _recreate(
        conn,
        "estimate_roles",
        _V5_ESTIMATE_ROLES,
        ("task_key", "run_id", "role"),
        (
            "task_key",
            "run_id",
            "role",
            "expected",
            "range_low",
            "range_high",
            "confidence",
            "provenance",
        ),
        expressions={"task_key": "COALESCE(task_key, '')"},
    )
    _migrate_publications(conn)
    _drop_orphan_roles(conn)


# Миграции по версиям: ключ — версия, которую миграция приводит к себе.
_MIGRATIONS = {
    1: _DDL,
    2: _DDL_V2,
    3: _migrate_v3,
    4: _DDL_V4,
    5: _migrate_v5,
}

# Один `[WARN]` на процесс: иначе каждый шаг пайплайна повторяет одну строку.
_WARNED = set()

# Слова, которых не может быть в read-only запросе (`db query`).
_FORBIDDEN_SQL_WORDS = (
    "attach",
    "detach",
    "writable_schema",
    "vacuum",
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "reindex",
    "analyze",
)


# ---------------------------------------------------------------------------
# Служебное
# ---------------------------------------------------------------------------


def _now():
    """Момент в формате артефактов: 2026-11-17T09:41:07Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _warn(message):
    """`[WARN] storage: …` в stderr — stdout остаётся чистым для `--json`."""
    print("[WARN] storage: %s" % message, file=sys.stderr)


def _warn_once(key, message):
    if key in _WARNED:
        return
    _WARNED.add(key)
    _warn(message)


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256_text(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _sha256_obj(obj):
    return _sha256_text(_canonical(obj))


def _json_text(value):
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _read_json(path):
    """Прочитать JSON. Возвращает `(payload, error)`; ровно одно из них None."""
    try:
        with open(str(path), "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except OSError as exc:
        return None, "не читается: %s" % exc
    except ValueError as exc:
        return None, "невалидный JSON: %s" % exc


def _guarded(default):
    """Обёртка record_*: `conn is None` → no-op, любая ошибка → `[WARN]`."""

    def decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            conn = args[0] if args else kwargs.get("conn")
            if conn is None:
                return default
            try:
                return function(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - зеркало не валит пайплайн
                _warn("%s: %s: %s" % (function.__name__, type(exc).__name__, exc))
                return default

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Путь, открытие, миграция
# ---------------------------------------------------------------------------


def _sqlite_config(cfg):
    """`storage.sqlite` из конфига, всегда слитый с дефолтами.

    `cfg` может быть `None` (вызов из `state.save`, где конфиг не читается) или
    неполным: значения берутся из `config.DEFAULTS`, а не из литералов, иначе
    дефолт пришлось бы держать в двух местах.
    """
    defaults = configmod.DEFAULTS["storage"]["sqlite"]
    block = None
    if isinstance(cfg, dict):
        storage = cfg.get("storage")
        if isinstance(storage, dict):
            block = storage.get("sqlite")
    if not isinstance(block, dict):
        block = {}
    merged = dict(defaults)
    merged.update(block)
    return merged


def _sqlite_enabled(cfg):
    return bool(_sqlite_config(cfg).get("enabled"))


def path_for(workdir, cfg):
    """Файл БД: относительный путь разрешается от корня проекта."""
    value = _sqlite_config(cfg).get("path") or configmod.DEFAULTS["storage"]["sqlite"]["path"]
    candidate = Path(str(value)).expanduser()
    if not candidate.is_absolute():
        candidate = Path(workdir) / candidate
    return candidate


def _open_raw(path):
    """Открыть соединение с прагмами зеркала (WAL, foreign_keys, NORMAL)."""
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _user_version(conn):
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _migrate(conn):
    """Довести схему до `SCHEMA_VERSION`. Возвращает версию после миграции.

    Шаг миграции — либо кортеж SQL-выражений, либо вызываемая функция
    (`_migrate_v5`: пересоздание таблиц с переносом данных требует чтения
    `PRAGMA table_info`, одним `ALTER` это не выражается).

    Каждый шаг — своя транзакция (`SAVEPOINT`), и `user_version` поднимается
    **внутри** неё, только после успешных выражений шага. Иначе прерванный
    посреди шага процесс оставлял полусхему, а следующий запуск падал на
    `duplicate column name`; `connect()` ловил это как «БД не открывается» и
    молча выключал зеркалирование. Откат возвращает схему к состоянию до шага,
    поэтому миграция возобновляема.
    """
    version = _user_version(conn)
    for target in sorted(_MIGRATIONS):
        if target <= version:
            continue
        step = _MIGRATIONS[target]
        savepoint = "trr_migration_%d" % target
        conn.execute("SAVEPOINT %s" % savepoint)
        try:
            if callable(step):
                step(conn)
            else:
                for statement in step:
                    conn.execute(statement)
            conn.execute("PRAGMA user_version=%d" % target)
            conn.execute("RELEASE %s" % savepoint)
        except Exception:
            conn.execute("ROLLBACK TO %s" % savepoint)
            conn.execute("RELEASE %s" % savepoint)
            raise
        version = target
    conn.commit()
    return version


def _sync_meta(conn, cfg):
    """Записать в `meta` флаги хранения и версию схемы."""
    sqlite_cfg = _sqlite_config(cfg)
    values = {
        "schema_version": str(SCHEMA_VERSION),
        "keep_vectors": "true" if sqlite_cfg.get("keep_vectors", True) else "false",
        "keep_payloads": "true" if sqlite_cfg.get("keep_payloads", True) else "false",
        "vacuum_on_pack": "true" if sqlite_cfg.get("vacuum_on_pack", False) else "false",
        # Абсолютный путь: `meta` читают из дампа и из другой машины, где
        # относительный путь означал бы другое место.
        "path": _db_path(conn) or str(path_for(".", cfg)),
    }
    moment = _now()
    for key in sorted(values):
        conn.execute(
            "INSERT INTO meta(key, value, updated_at) VALUES(?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "updated_at=excluded.updated_at",
            (key, values[key], moment),
        )
    conn.commit()


def _flag(conn, name, default=True):
    """Флаг из `meta` (`keep_payloads`, `keep_vectors`, `vacuum_on_pack`)."""
    try:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (name,)).fetchone()
    except sqlite3.Error:
        return default
    if row is None:
        return default
    return str(row[0]).strip().lower() in ("1", "true", "yes", "on")


def connect(workdir, cfg, create=True):
    """Соединение с зеркалом. `None` — выключено или БД не открылась.

    `create=True` (по умолчанию) создаёт файл и применяет миграции: вызывающий
    код пишет сразу, отдельный `init` не нужен. `create=False` — только
    существующий файл (чтение).
    """
    if not _sqlite_enabled(cfg):
        _warn_once(
            "disabled",
            "выключено (storage.sqlite.enabled=false) — зеркало не ведётся",
        )
        return None
    path = path_for(workdir, cfg)
    if not create and not path.is_file():
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = _open_raw(path)
        _migrate(conn)
        if create:
            _sync_meta(conn, cfg)
        return conn
    except Exception as exc:  # noqa: BLE001 - БД не должна валить пайплайн
        _warn("не открывается %s: %s: %s" % (path, type(exc).__name__, exc))
        return None


def connect_readonly(workdir, cfg):
    """Read-only соединение (`file:…?mode=ro`) для `db query` и `db check`."""
    if not _sqlite_enabled(cfg):
        _warn_once(
            "disabled",
            "выключено (storage.sqlite.enabled=false) — зеркало не ведётся",
        )
        return None
    path = path_for(workdir, cfg)
    if not path.is_file():
        return None
    try:
        uri = "%s?mode=ro" % path.resolve().as_uri()
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as exc:  # noqa: BLE001
        _warn("не открывается read-only %s: %s: %s" % (path, type(exc).__name__, exc))
        return None


def init_db(workdir, cfg):
    """Создать/мигрировать БД. Идемпотентно: второй вызов не меняет версию."""
    path = path_for(workdir, cfg)
    if not _sqlite_enabled(cfg):
        _warn_once(
            "disabled",
            "выключено (storage.sqlite.enabled=false) — зеркало не ведётся",
        )
        return {
            "created": False,
            "user_version": 0,
            "path": str(path),
            "enabled": False,
        }

    existed = path.is_file()
    before = 0
    if existed:
        try:
            probe = _open_raw(path)
            try:
                before = _user_version(probe)
            finally:
                probe.close()
        except Exception:  # noqa: BLE001 - битый файл считаем «пустым»
            before = 0

    conn = connect(workdir, cfg, create=True)
    if conn is None:
        return {
            "created": False,
            "user_version": 0,
            "path": str(path),
            "enabled": True,
            "error": "не открывается",
        }
    try:
        version = _user_version(conn)
    finally:
        conn.close()
    return {
        "created": (not existed) or before == 0,
        "before_version": before,
        "migrated": bool(existed) and before != version,
        "user_version": version,
        "path": str(path),
        "enabled": True,
    }


# ---------------------------------------------------------------------------
# Векторы: BLOB ↔ list[float]
# ---------------------------------------------------------------------------


def pack_vector(values):
    """`list[float]` → `struct.pack('<Nf')`. Пустой вектор — пустой BLOB."""
    numbers = [float(value) for value in values]
    if not numbers:
        return b""
    return struct.pack("<%df" % len(numbers), *numbers)


def unpack_vector(blob, dim=None):
    """BLOB → `list[float]`. `dim` — ожидаемая длина (проверяется)."""
    if blob is None:
        return []
    raw = bytes(blob)
    if not raw:
        return []
    size = struct.calcsize("<f")
    if len(raw) % size:
        raise ValueError("BLOB вектора длиной %d не кратен %d" % (len(raw), size))
    count = len(raw) // size
    if dim is not None and int(dim) != count:
        raise ValueError(
            "BLOB вектора содержит %d значений, ожидалось %d" % (count, int(dim))
        )
    return list(struct.unpack("<%df" % count, raw))


# ---------------------------------------------------------------------------
# `db query`: только чтение
# ---------------------------------------------------------------------------


def _strip_sql_comments(sql):
    """Убрать `-- …` и `/* … */`, чтобы проверка не зависела от комментариев."""
    text = re.sub(r"/\*.*?\*/", " ", str(sql or ""), flags=re.S)
    text = re.sub(r"--[^\n]*", " ", text)
    return text


def is_read_only_sql(sql):
    """`(ok, reason)`: пропускать только SELECT / WITH / PRAGMA без присваивания."""
    text = _strip_sql_comments(sql).strip()
    if not text:
        return False, "пустой SQL"
    lowered = text.lower()
    body = lowered[:-1].rstrip() if lowered.endswith(";") else lowered
    if ";" in body:
        return False, "несколько выражений в одном запросе запрещены"
    if not (
        body.startswith("select")
        or body.startswith("with")
        or body.startswith("pragma")
    ):
        return False, "разрешены только SELECT, WITH и PRAGMA"
    for word in _FORBIDDEN_SQL_WORDS:
        if re.search(r"\b%s\b" % re.escape(word), body):
            return False, "запрещённое слово: %s" % word
    if body.startswith("pragma") and "=" in body:
        return False, "PRAGMA с присваиванием запрещён"
    return True, ""


def query_rows(conn, sql, limit=None):
    """Выполнить read-only запрос. Возвращает `(columns, rows)`.

    Не-read-only SQL — `ValueError` с причиной (CLI отдаёт её как `[BLOCKED]`).
    """
    ok, reason = is_read_only_sql(sql)
    if not ok:
        raise ValueError(reason)
    cursor = conn.execute(str(sql))
    columns = [item[0] for item in (cursor.description or [])]
    if limit is None:
        rows = cursor.fetchall()
    else:
        rows = cursor.fetchmany(int(limit))
    return columns, [list(row) for row in rows]


# ---------------------------------------------------------------------------
# Запись: эталон, выборка, статистика, модель
# ---------------------------------------------------------------------------


def _latest_model_checksum(conn):
    """Контрольная сумма последней записанной версии модели (или None)."""
    try:
        row = conn.execute(
            "SELECT checksum FROM model_versions ORDER BY version DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    value = row[0]
    return str(value) if value else None


def _drop_placeholder(conn, table, checksum):
    """Убрать строки-плейсхолдеры, когда появилась настоящая версия модели."""
    if checksum and checksum != PLACEHOLDER_CHECKSUM:
        conn.execute(
            "DELETE FROM %s WHERE model_checksum=?" % table, (PLACEHOLDER_CHECKSUM,)
        )


@_guarded(0)
def record_reference(conn, payload, model_checksum=None):
    """Записать эталон: страницу-источник, бакеты и строки шкалы.

    Бакеты (`role/work_kind → value`) — числа, по которым калибруется модель;
    строки шкалы (`levels[]`) — полная матрица таблицы, из которой эти числа
    выбраны. Тело страницы в БД не хранится (`body_sha256`/`body_len` — NULL):
    эталон читается из Confluence, а зеркало хранит только данные и провенанс.
    """
    if not isinstance(payload, dict):
        return 0
    checksum = (
        str(model_checksum)
        if model_checksum
        else (_latest_model_checksum(conn) or PLACEHOLDER_CHECKSUM)
    )
    _drop_placeholder(conn, "reference_buckets", checksum)
    if checksum != PLACEHOLDER_CHECKSUM:
        # Эталон — вход модели, а не её версия: при смене checksum те же бакеты
        # не должны дублироваться под старым ключом. Зеркало хранит текущий
        # эталон; историю версий модели ведут `model_versions`/`model_buckets`.
        conn.execute(
            "DELETE FROM reference_buckets WHERE model_checksum<>?", (checksum,)
        )

    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    page_id = source.get("page_id")
    if page_id is not None and str(page_id).strip():
        conn.execute(
            "INSERT INTO reference_pages(page_id, title, space_key, depth, version, "
            "body_sha256, body_len, retrieved_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(page_id) DO UPDATE SET title=excluded.title, "
            "space_key=COALESCE(excluded.space_key, reference_pages.space_key), "
            "depth=COALESCE(excluded.depth, reference_pages.depth), "
            "version=COALESCE(excluded.version, reference_pages.version), "
            "retrieved_at=COALESCE(excluded.retrieved_at, reference_pages.retrieved_at)",
            (
                str(page_id),
                source.get("title"),
                source.get("space_key"),
                source.get("depth"),
                source.get("version"),
                None,
                None,
                source.get("retrieved_at"),
            ),
        )

    buckets = payload.get("buckets") if isinstance(payload.get("buckets"), list) else []
    count = 0
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        role = bucket.get("role")
        work_kind = bucket.get("work_kind")
        if not role or not work_kind:
            continue
        conn.execute(
            "INSERT INTO reference_buckets(model_checksum, role, work_kind, value, "
            "description, evidence) VALUES(?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(model_checksum, role, work_kind) DO UPDATE SET "
            "value=excluded.value, description=excluded.description, "
            "evidence=excluded.evidence",
            (
                checksum,
                str(role),
                str(work_kind),
                bucket.get("value"),
                bucket.get("description"),
                bucket.get("evidence"),
            ),
        )
        count += 1
    _record_levels(conn, payload, page_id)
    conn.commit()
    return count


def _record_levels(conn, payload, page_id):
    """Записать строки эталонной таблицы (`levels`) в `reference_levels`.

    Ключ — `(page_id, sp)`: строки шкалы принадлежат странице-источнику, а не
    версии модели, поэтому переживают переобучение. Список уровней считается
    полным состоянием страницы: перед вставкой строки страницы удаляются, иначе
    уровень, убранный из таблицы, остался бы в зеркале навсегда.
    """
    levels = payload.get("levels") if isinstance(payload.get("levels"), list) else []
    if not levels or page_id is None or not str(page_id).strip():
        return 0
    page_id = str(page_id)
    conn.execute("DELETE FROM reference_levels WHERE page_id=?", (page_id,))
    count = 0
    for level in levels:
        if not isinstance(level, dict):
            continue
        sp = level.get("sp")
        if isinstance(sp, bool) or not isinstance(sp, int):
            continue
        conn.execute(
            "INSERT INTO reference_levels(page_id, sp, description, uncertainty, "
            "refactoring, research, decomposition, time_hint, examples, params_hint) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(page_id, sp) DO UPDATE SET "
            "description=excluded.description, uncertainty=excluded.uncertainty, "
            "refactoring=excluded.refactoring, research=excluded.research, "
            "decomposition=excluded.decomposition, time_hint=excluded.time_hint, "
            "examples=excluded.examples, params_hint=excluded.params_hint",
            (
                page_id,
                sp,
                level.get("description"),
                level.get("uncertainty"),
                level.get("refactoring"),
                level.get("research"),
                level.get("decomposition"),
                level.get("time"),
                _json_or_none(level.get("examples")),
                _json_or_none(level.get("params_hint")),
            ),
        )
        count += 1
    return count


def _json_or_none(value):
    """Объект/массив → компактный JSON-текст; None остаётся NULL."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


@_guarded(0)
def record_sample(conn, sample_payload, params_by_key=None):
    """Записать строки выборки спринтов и сводку по задачам.

    Ключ строки — `(task_key, sprint)`: одна задача может попасть в несколько
    спринтов, это разные строки, а не дубли. `params_by_key` — необязательный
    `{task_key: {weight, heat, connectivity, source}}` из `trr params`.
    """
    if not isinstance(sample_payload, dict):
        return 0
    rows = sample_payload.get("rows") if isinstance(sample_payload.get("rows"), list) else []
    checksum = _sha256_obj(rows)
    moment = _now()
    params_by_key = params_by_key if isinstance(params_by_key, dict) else {}

    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_key = row.get("key")
        sprint = row.get("sprint")
        if task_key is None or sprint is None:
            continue
        task_key = str(task_key)
        sprint = str(sprint)
        params = params_by_key.get(task_key)
        params = params if isinstance(params, dict) else {}
        weight = params.get("weight")
        heat = params.get("heat")
        connectivity = params.get("connectivity")
        labels = row.get("labels")
        conn.execute(
            "INSERT INTO sprint_rows(sprint, task_key, issue_type, role, sp, "
            "qa_estimation, has_testing, status, labels, summary_sha256, weight, heat, "
            "connectivity, sample_checksum) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(task_key, sprint) DO UPDATE SET "
            "issue_type=excluded.issue_type, role=excluded.role, sp=excluded.sp, "
            "qa_estimation=excluded.qa_estimation, has_testing=excluded.has_testing, "
            "status=excluded.status, labels=excluded.labels, "
            "summary_sha256=excluded.summary_sha256, weight=excluded.weight, "
            "heat=excluded.heat, connectivity=excluded.connectivity, "
            "sample_checksum=excluded.sample_checksum",
            (
                sprint,
                task_key,
                row.get("issue_type"),
                row.get("role"),
                row.get("sp"),
                row.get("qa_estimation"),
                1 if row.get("has_testing") else 0,
                row.get("status"),
                _json_text(labels),
                row.get("summary_sha256"),
                weight,
                heat,
                connectivity,
                checksum,
            ),
        )
        conn.execute(
            "INSERT INTO tasks(task_key, issue_type, role, sp, qa_estimation, weight, "
            "heat, connectivity, params_source, first_seen, last_seen) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(task_key) DO UPDATE SET "
            "issue_type=COALESCE(excluded.issue_type, tasks.issue_type), "
            "role=COALESCE(excluded.role, tasks.role), "
            "sp=COALESCE(excluded.sp, tasks.sp), "
            "qa_estimation=COALESCE(excluded.qa_estimation, tasks.qa_estimation), "
            "weight=COALESCE(excluded.weight, tasks.weight), "
            "heat=COALESCE(excluded.heat, tasks.heat), "
            "connectivity=COALESCE(excluded.connectivity, tasks.connectivity), "
            "params_source=COALESCE(excluded.params_source, tasks.params_source), "
            "last_seen=excluded.last_seen",
            (
                task_key,
                row.get("issue_type"),
                row.get("role"),
                row.get("sp"),
                row.get("qa_estimation"),
                weight,
                heat,
                connectivity,
                params.get("source"),
                moment,
                moment,
            ),
        )
        count += 1
    conn.commit()
    return count


@_guarded(0)
def record_stats(conn, stats_payload, model_checksum=None):
    """Записать бакеты `sprint-stats` для версии модели (или плейсхолдера)."""
    if not isinstance(stats_payload, dict):
        return 0
    checksum = (
        str(model_checksum)
        if model_checksum
        else (_latest_model_checksum(conn) or PLACEHOLDER_CHECKSUM)
    )
    _drop_placeholder(conn, "sprint_stats", checksum)

    buckets = (
        stats_payload.get("buckets") if isinstance(stats_payload.get("buckets"), list) else []
    )
    count = 0
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        role = bucket.get("role")
        issue_type = bucket.get("issue_type")
        work_kind = bucket.get("work_kind")
        if not (role and issue_type and work_kind):
            continue
        conn.execute(
            "INSERT INTO sprint_stats(model_checksum, role, issue_type, work_kind, n, "
            "mean, median, p25, p75, min, max, coverage) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(model_checksum, role, issue_type, work_kind) DO UPDATE SET "
            "n=excluded.n, mean=excluded.mean, median=excluded.median, p25=excluded.p25, "
            "p75=excluded.p75, min=excluded.min, max=excluded.max, "
            "coverage=excluded.coverage",
            (
                checksum,
                str(role),
                str(issue_type),
                str(work_kind),
                bucket.get("n"),
                bucket.get("mean"),
                bucket.get("median"),
                bucket.get("p25"),
                bucket.get("p75"),
                bucket.get("min"),
                bucket.get("max"),
                bucket.get("coverage"),
            ),
        )
        count += 1
    conn.commit()
    return count


@_guarded(0)
def record_model(conn, model_payload):
    """Записать версию модели: `model_versions`, `model_buckets`, `gap_rules`."""
    if not isinstance(model_payload, dict):
        return 0
    checksum = model_payload.get("checksum")
    version = model_payload.get("version")
    if not checksum or not isinstance(version, int) or isinstance(version, bool):
        return 0
    checksum = str(checksum)
    keep_payloads = _flag(conn, "keep_payloads", True)
    conn.execute(
        "INSERT INTO model_versions(version, checksum, generated_at, payload, created_at) "
        "VALUES(?, ?, ?, ?, ?) "
        "ON CONFLICT(version) DO UPDATE SET checksum=excluded.checksum, "
        "generated_at=excluded.generated_at, payload=excluded.payload",
        (
            version,
            checksum,
            model_payload.get("generated_at"),
            _json_text(model_payload) if keep_payloads else None,
            _now(),
        ),
    )

    conn.execute("DELETE FROM model_buckets WHERE model_checksum=?", (checksum,))
    buckets = (
        model_payload.get("buckets") if isinstance(model_payload.get("buckets"), list) else []
    )
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        role = bucket.get("role")
        issue_type = bucket.get("issue_type")
        work_kind = bucket.get("work_kind")
        if not (role and issue_type and work_kind):
            continue
        low, high = _range_pair(bucket.get("range"))
        conn.execute(
            "INSERT INTO model_buckets(model_checksum, role, issue_type, work_kind, base, "
            "factor, expected, range_low, range_high, n, confidence, reference, "
            "params_multiplier, params_profile) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(model_checksum, role, issue_type, work_kind) DO UPDATE SET "
            "base=excluded.base, factor=excluded.factor, expected=excluded.expected, "
            "range_low=excluded.range_low, range_high=excluded.range_high, "
            "n=excluded.n, confidence=excluded.confidence, reference=excluded.reference, "
            "params_multiplier=excluded.params_multiplier, "
            "params_profile=excluded.params_profile",
            (
                checksum,
                str(role),
                str(issue_type),
                str(work_kind),
                bucket.get("base"),
                bucket.get("factor"),
                bucket.get("expected"),
                low,
                high,
                bucket.get("n"),
                bucket.get("confidence"),
                bucket.get("reference"),
                bucket.get("params_multiplier"),
                _json_or_none(bucket.get("params_profile")),
            ),
        )

    conn.execute("DELETE FROM gap_rules WHERE model_checksum=?", (checksum,))
    rules = (
        model_payload.get("gap_rules") if isinstance(model_payload.get("gap_rules"), list) else []
    )
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("rule_id")
        if not rule_id:
            continue
        conn.execute(
            "INSERT INTO gap_rules(model_checksum, rule_id, condition, penalty_steps, "
            "applies_to) VALUES(?, ?, ?, ?, ?) "
            "ON CONFLICT(model_checksum, rule_id) DO UPDATE SET "
            "condition=excluded.condition, penalty_steps=excluded.penalty_steps, "
            "applies_to=excluded.applies_to",
            (
                checksum,
                str(rule_id),
                rule.get("condition"),
                rule.get("penalty_steps"),
                _json_text(rule.get("applies_to")),
            ),
        )
    conn.commit()
    return len(buckets)


def _range_pair(value):
    """`[low, high]` из модели; всё, что не пара чисел, — `(None, None)`."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[0], value[1]
    return None, None


# ---------------------------------------------------------------------------
# Запись: прогоны, векторы, публикации, метрики
# ---------------------------------------------------------------------------


@_guarded(None)
def record_run(conn, run_id, task_key, stage, workdir, model_checksum=None,
               config_sha256=None, authoritative=False):
    """Зарегистрировать прогон задачи. Ключ — `(task_key, run_id)`.

    `run_id` — метка времени, одинаковая у задач одного запуска, поэтому ключ
    без `task_key` схлопывал прогоны разных задач (схема 5).

    `authoritative=True` — режим бэкфилла из артефактов: `model_checksum`
    берётся из самого артефакта прогона, а не из текущего состояния. `NULL`
    из артефакта **не затирает** уже известную сумму: `validation.json` модели
    не фиксирует, и его шаг бэкфилла шёл бы после `estimate.json`, стирая
    контрольную сумму того же прогона. `config_sha256` в артефакте прогона не
    хранится, поэтому `NULL` его тоже не перезаписывает.
    """
    if not run_id:
        return None
    # `COALESCE` в обоих режимах: значение из артефакта побеждает, отсутствие
    # значения (`NULL`) — нет. `authoritative` остаётся в подписи как признак
    # «сумма пришла из артефакта», а не из текущей модели.
    checksum_set = "model_checksum=COALESCE(excluded.model_checksum, runs.model_checksum)"
    conn.execute(
        "INSERT INTO runs(task_key, run_id, stage, workdir, created_at, "
        "model_checksum, config_sha256) VALUES(?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(task_key, run_id) DO UPDATE SET "
        "stage=COALESCE(excluded.stage, runs.stage), "
        "workdir=COALESCE(excluded.workdir, runs.workdir), "
        "%s, "
        "config_sha256=COALESCE(excluded.config_sha256, runs.config_sha256)"
        % checksum_set,
        (
            str(task_key) if task_key else "",
            str(run_id),
            str(stage) if stage else None,
            str(workdir) if workdir else None,
            _now(),
            str(model_checksum) if model_checksum else None,
            str(config_sha256) if config_sha256 else None,
        ),
    )
    conn.commit()
    return None


@_guarded(None)
def record_validation(conn, run_id, validation_payload, task_key=None):
    """Записать `validation.json` прогона: вердикт и счётчики проверок.

    `task_key` — часть ключа; если не передан, берётся из самого артефакта.
    """
    if not run_id or not isinstance(validation_payload, dict):
        return None
    key_task = str(task_key or validation_payload.get("task_key") or "")
    checks = validation_payload.get("checks")
    checks = checks if isinstance(checks, list) else []
    gaps = validation_payload.get("gaps")
    gaps = gaps if isinstance(gaps, list) else []
    failed = sum(
        1
        for item in checks
        if isinstance(item, dict) and str(item.get("status")) == "FAIL"
    )
    keep_payloads = _flag(conn, "keep_payloads", True)
    conn.execute(
        "INSERT INTO validations(task_key, run_id, verdict, checks_total, "
        "checks_failed, gaps_total, payload, checked_at) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(task_key, run_id) DO UPDATE SET "
        "verdict=excluded.verdict, checks_total=excluded.checks_total, "
        "checks_failed=excluded.checks_failed, gaps_total=excluded.gaps_total, "
        "payload=excluded.payload, checked_at=excluded.checked_at",
        (
            key_task,
            str(run_id),
            validation_payload.get("verdict"),
            len(checks),
            failed,
            len(gaps),
            _json_text(validation_payload) if keep_payloads else None,
            validation_payload.get("checked_at"),
        ),
    )
    conn.commit()
    return None


@_guarded(None)
def record_estimate(conn, run_id, estimate_payload, params_multiplier=None,
                    task_key=None):
    """Записать `estimate.json`: итог, разбивка по ролям и провенанс.

    `task_key` — часть ключа; если не передан, берётся из самого артефакта.
    """
    if not run_id or not isinstance(estimate_payload, dict):
        return None
    key_task = str(task_key or estimate_payload.get("task_key") or "")
    total = estimate_payload.get("total") if isinstance(estimate_payload.get("total"), dict) else {}
    low, high = _range_pair(total.get("range"))
    keep_payloads = _flag(conn, "keep_payloads", True)
    conn.execute(
        "INSERT INTO estimates(task_key, run_id, model_version, model_checksum, "
        "total_expected, total_low, total_high, params_multiplier, payload, estimated_at, "
        "params_json) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(task_key, run_id) DO UPDATE SET "
        "model_version=excluded.model_version, model_checksum=excluded.model_checksum, "
        "total_expected=excluded.total_expected, total_low=excluded.total_low, "
        "total_high=excluded.total_high, "
        "params_multiplier=COALESCE(excluded.params_multiplier, estimates.params_multiplier), "
        "payload=excluded.payload, estimated_at=excluded.estimated_at, "
        "params_json=COALESCE(excluded.params_json, estimates.params_json)",
        (
            key_task,
            str(run_id),
            estimate_payload.get("model_version"),
            estimate_payload.get("model_checksum"),
            total.get("expected"),
            low,
            high,
            params_multiplier,
            _json_text(estimate_payload) if keep_payloads else None,
            estimate_payload.get("estimated_at"),
            _json_or_none(estimate_payload.get("params")),
        ),
    )

    roles = (
        estimate_payload.get("roles") if isinstance(estimate_payload.get("roles"), list) else []
    )
    seen = []
    for entry in roles:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        if not role:
            continue
        role_low, role_high = _range_pair(entry.get("range"))
        seen.append(str(role))
        conn.execute(
            "INSERT INTO estimate_roles(task_key, run_id, role, expected, range_low, "
            "range_high, confidence, provenance) VALUES(?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(task_key, run_id, role) DO UPDATE SET "
            "expected=excluded.expected, range_low=excluded.range_low, "
            "range_high=excluded.range_high, confidence=excluded.confidence, "
            "provenance=excluded.provenance",
            (
                key_task,
                str(run_id),
                str(role),
                entry.get("expected"),
                role_low,
                role_high,
                entry.get("confidence"),
                _json_text(entry.get("provenance")),
            ),
        )
    if seen:
        placeholders = ", ".join("?" for _ in seen)
        conn.execute(
            "DELETE FROM estimate_roles WHERE task_key=? AND run_id=? "
            "AND role NOT IN (%s)" % placeholders,
            [key_task, str(run_id)] + seen,
        )
    conn.commit()
    return None


def _ordered_terms(vector):
    """`(terms, values)`: термы по алфавиту, значения — в том же порядке.

    Порядок фиксирован алфавитом, а не весом: иначе BLOB и `terms` менялись бы
    от пересборки к пересборке при равных весах, и round-trip нельзя было бы
    сверить побайтово.
    """
    terms = vector.get("terms") if isinstance(vector, dict) else None
    pairs = []
    if isinstance(terms, dict):
        pairs = [(str(term), float(value)) for term, value in terms.items()]
    elif isinstance(terms, list):
        for item in terms:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                pairs.append((str(item[0]), float(item[1])))
    pairs.sort(key=lambda pair: pair[0])
    return [pair[0] for pair in pairs], [pair[1] for pair in pairs]


@_guarded(0)
def record_vectors(conn, model_version, vector_model, vectors_by_task):
    """Записать модель векторов: `vector_meta` + BLOB-векторы задач.

    `keep_vectors: false` — векторы не пишутся (таблица `vectors` остаётся
    пустой), метаданные модели пишутся всегда: иначе нельзя отличить «модель не
    собрана» от «векторы не хранятся».
    """
    if not isinstance(vector_model, dict):
        return 0
    version = int(model_version or vector_model.get("version") or 1)
    vectors = [item for item in (vectors_by_task or []) if isinstance(item, dict)]
    keep_vectors = _flag(conn, "keep_vectors", True)
    keep_payloads = _flag(conn, "keep_payloads", True)
    built_at = vector_model.get("built_at")

    packed = []
    for vector in vectors:
        terms, values = _ordered_terms(vector)
        packed.append((str(vector.get("key")), terms, values))
    dim = max([len(values) for _key, _terms, values in packed] or [0])

    config = {
        "top_terms": vector_model.get("top_terms"),
        "weight_word": vector_model.get("weight_word"),
        "weight_char": vector_model.get("weight_char"),
        "normalizer": vector_model.get("normalizer"),
    }
    conn.execute(
        "INSERT INTO vector_meta(model_version, built_at, corpus, dim, config) "
        "VALUES(?, ?, ?, ?, ?) "
        "ON CONFLICT(model_version) DO UPDATE SET built_at=excluded.built_at, "
        "corpus=excluded.corpus, dim=excluded.dim, config=excluded.config",
        (version, built_at, len(vectors), dim, _json_text(config)),
    )

    if not keep_vectors:
        conn.commit()
        return 0

    for key, terms, values in packed:
        conn.execute(
            "INSERT INTO vectors(task_key, model_version, dim, vector, terms, built_at) "
            "VALUES(?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(task_key, model_version) DO UPDATE SET dim=excluded.dim, "
            "vector=excluded.vector, terms=excluded.terms, built_at=excluded.built_at",
            (
                key,
                version,
                len(values),
                pack_vector(values),
                _json_text(terms) if keep_payloads else None,
                built_at,
            ),
        )
    conn.commit()
    return len(packed)


@_guarded(0)
def record_similar(conn, task_key, similar_rows, model_version):
    """Записать результаты `vectors similar`: одна строка на пару задач."""
    if not task_key or not isinstance(similar_rows, list):
        return 0
    version = int(model_version or 1)
    key = str(task_key)
    conn.execute(
        "DELETE FROM similarities WHERE task_key=? AND model_version=?", (key, version)
    )
    count = 0
    for row in similar_rows:
        if not isinstance(row, dict) or row.get("key") is None:
            continue
        conn.execute(
            "INSERT INTO similarities(task_key, other_key, cosine, same_bucket, "
            "model_version) VALUES(?, ?, ?, ?, ?) "
            "ON CONFLICT(task_key, other_key, model_version) DO UPDATE SET "
            "cosine=excluded.cosine, same_bucket=excluded.same_bucket",
            (
                key,
                str(row.get("key")),
                row.get("cosine"),
                1 if row.get("same_bucket") else 0,
                version,
            ),
        )
        count += 1
    conn.commit()
    return count


@_guarded(None)
def record_publication(conn, target, ref, url, content_sha256=None, model_checksum=None):
    """Записать публикацию (идемпотентный upsert по `(target, ref)`).

    Две разные величины, которые раньше жили в одной колонке:
    `content_sha256` — sha256 опубликованного файла (тот же, что в
    `state.published[]`), `model_checksum` — контрольная сумма модели, которой
    страница отрендерена (nullable). `None` не затирает уже записанное значение.
    """
    if not target or ref is None:
        return None
    conn.execute(
        "INSERT INTO publications(target, ref, url, content_sha256, model_checksum, "
        "published_at) VALUES(?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(target, ref) DO UPDATE SET url=excluded.url, "
        "content_sha256=COALESCE(excluded.content_sha256, publications.content_sha256), "
        "model_checksum=COALESCE(excluded.model_checksum, publications.model_checksum), "
        "published_at=excluded.published_at",
        (
            str(target),
            str(ref),
            url,
            content_sha256,
            model_checksum,
            _now(),
        ),
    )
    conn.commit()
    return None


@_guarded(None)
def record_metric(conn, scope, name, value, labels=None):
    """Дописать метрику (`metrics` — журнал, а не состояние: строки копятся)."""
    if scope is None or name is None:
        return None
    number = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
    conn.execute(
        "INSERT INTO metrics(ts, scope, name, value, labels) VALUES(?, ?, ?, ?, ?)",
        (_now(), str(scope), str(name), number, _json_text(labels)),
    )
    conn.commit()
    return None


def synth_run_id(summary):
    """Детерминированный `run_id` прогона полигона.

    `timing` и `harness` (путь `--out`, число потоков) исключены: id не должен
    зависеть от машины и длительности, иначе повторный прогон того же датасета
    плодил бы строки. `seed` входит в id: разные датасеты — разные прогоны.
    """
    if not isinstance(summary, dict):
        return None
    payload = {
        key: value
        for key, value in summary.items()
        if key not in ("timing", "harness")
    }
    digest = _sha256_obj(payload)[:12]
    seed = summary.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        seed = 0
    return "synth-%d-%s" % (seed, digest)


# Числовые метрики полигона, которые расходятся по `metrics(scope='synth')`.
# Ключ — имя метрики, значение — путь в `summary.json`.
_SYNTH_METRICS = (
    ("total", ("total",)),
    ("ok", ("ok",)),
    ("warn", ("warn",)),
    ("blocked", ("blocked",)),
    ("errors", ("errors",)),
    ("unestimable", ("unestimable",)),
    ("unexpected_errors", ("unexpected_errors",)),
    ("schema_failures", ("schema_failures", "cases")),
    ("scale_violations", ("scale_violations", "cases")),
    ("range_violations", ("range_violations", "cases")),
    ("param_violations", ("param_violations", "cases")),
    ("monotonicity_violations", ("monotonicity", "violations")),
    ("buckets_hit", ("buckets", "hit")),
    ("buckets_total", ("buckets", "total")),
    ("buckets_reachable", ("buckets", "reachable")),
    ("buckets_probe", ("buckets", "probe", "hit")),
    ("p50_ms", ("timing", "per_task_ms", "p50")),
    ("p95_ms", ("timing", "per_task_ms", "p95")),
)


def _dig(payload, path):
    value = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


@_guarded(None)
def record_synth_run(conn, summary, run_id=None):
    """Записать прогон полигона: строка `synth_runs` + метрики `scope='synth'`.

    `summary` — полный `summary.json` (JSON-текст в колонке `summary`): схема
    метрик полигона меняется чаще схемы БД. Числовые метрики дополнительно
    уходят в `metrics` — по ним строятся тренды между прогонами.
    """
    if not isinstance(summary, dict):
        return None
    run_id = run_id or synth_run_id(summary)
    if not run_id:
        return None
    seed = summary.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        seed = None
    count = summary.get("total")
    if not isinstance(count, int) or isinstance(count, bool):
        count = None
    checksum = (summary.get("model") or {}).get("checksum")
    conn.execute(
        "INSERT INTO synth_runs(run_id, created_at, seed, count, model_checksum, summary) "
        "VALUES(?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id) DO UPDATE SET created_at=excluded.created_at, "
        "seed=excluded.seed, count=excluded.count, "
        "model_checksum=excluded.model_checksum, summary=excluded.summary",
        (
            str(run_id),
            _now(),
            seed,
            count,
            str(checksum) if checksum else None,
            _json_text(summary),
        ),
    )
    conn.commit()
    labels = {"run_id": str(run_id), "seed": seed}
    for name, path in _SYNTH_METRICS:
        value = _dig(summary, path)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        record_metric(conn, "synth", name, float(value), labels)
    return str(run_id)


@_guarded(None)
def record_event(conn, kind, payload=None):
    """Дописать событие пайплайна (`events` — журнал)."""
    if not kind:
        return None
    conn.execute(
        "INSERT INTO events(ts, kind, payload) VALUES(?, ?, ?)",
        (_now(), str(kind), _json_text(payload)),
    )
    conn.commit()
    return None


# ---------------------------------------------------------------------------
# Сводка, экспорт, бэкфилл
# ---------------------------------------------------------------------------


def _db_path(conn):
    """Файл основной БД по `PRAGMA database_list` ("" — если неизвестен)."""
    try:
        for row in conn.execute("PRAGMA database_list"):
            if str(row[1]) == "main":
                return str(row[2] or "")
    except sqlite3.Error:
        return ""
    return ""


def stats(conn):
    """Размер файла, версия схемы и счётчики строк по всем таблицам."""
    if conn is None:
        return {"path": "", "size_bytes": 0, "user_version": 0, "tables": {}}
    path = _db_path(conn)
    try:
        size = os.path.getsize(path) if path and os.path.isfile(path) else 0
    except OSError:
        size = 0
    tables = {}
    for name in TABLES:
        try:
            row = conn.execute("SELECT COUNT(*) FROM %s" % name).fetchone()
            tables[name] = int(row[0]) if row is not None else 0
        except sqlite3.Error:
            tables[name] = 0
    try:
        version = _user_version(conn)
    except sqlite3.Error:
        version = 0
    return {
        "path": path,
        "size_bytes": size,
        "user_version": version,
        "tables": tables,
    }


def _export_value(value):
    """BLOB → `hex:…`, чтобы дамп оставался текстовым JSON."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "hex:" + bytes(value).hex()
    return value


@_guarded({})
def export_json(conn, out_path):
    """Дамп всех таблиц в один JSON-файл (BLOB — как `hex:…`)."""
    target = Path(str(out_path))
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "exported_at": _now(),
        "user_version": _user_version(conn),
        "source": _db_path(conn),
        "tables": {},
    }
    counts = {}
    for name in TABLES:
        cursor = conn.execute("SELECT * FROM %s" % name)
        columns = [item[0] for item in (cursor.description or [])]
        rows = []
        for row in cursor.fetchall():
            rows.append(
                {
                    column: _export_value(value)
                    for column, value in zip(columns, list(row))
                }
            )
        payload["tables"][name] = rows
        counts[name] = len(rows)
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    with open(str(target), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    if _flag(conn, "vacuum_on_pack", False):
        try:
            conn.execute("VACUUM")
        except sqlite3.Error:
            pass
    return {
        "path": str(target),
        "bytes": len(text.encode("utf-8")),
        "tables": counts,
    }


def _ingest_history(conn, path):
    """`model/model-history.jsonl` → `model_versions` (недостающие версии).

    Возвращает `(вставлено, всего_версий_в_истории)`. Второе число нужно, чтобы
    отличить «история одна» от «история копится»: `model_buckets`/`sprint_stats`
    пишутся только под текущую модель, и при полной пересборке БД прошлые срезы
    восстановить не из чего (в `model-history.jsonl` нет полных payload'ов).
    """
    try:
        with open(str(path), "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return 0, 0
    count = 0
    versions = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        version = entry.get("version")
        checksum = entry.get("checksum")
        if not isinstance(version, int) or isinstance(version, bool) or not checksum:
            continue
        versions += 1
        before = conn.total_changes
        conn.execute(
            "INSERT OR IGNORE INTO model_versions(version, checksum, generated_at, "
            "payload, created_at) VALUES(?, ?, ?, NULL, ?)",
            (version, str(checksum), entry.get("generated_at"), _now()),
        )
        if conn.total_changes > before:
            count += 1
    conn.commit()
    return count, versions


def _record_task_from_context(conn, task_key, context):
    """Задача из `context.json` прогона: тип, роль, вид работ."""
    if not isinstance(context, dict) or not task_key:
        return
    moment = _now()
    conn.execute(
        "INSERT INTO tasks(task_key, issue_type, role, work_kind, params_source, "
        "first_seen, last_seen) VALUES(?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(task_key) DO UPDATE SET "
        "issue_type=COALESCE(tasks.issue_type, excluded.issue_type), "
        "role=COALESCE(tasks.role, excluded.role), "
        "work_kind=COALESCE(tasks.work_kind, excluded.work_kind), "
        "last_seen=excluded.last_seen",
        (
            str(task_key),
            context.get("issue_type"),
            context.get("role"),
            context.get("work_kind"),
            "context",
            moment,
            moment,
        ),
    )


def _ingest_runs(conn, base):
    """`runs/<TASK>/<RUN-ID>/*.json` → `runs`, `validations`, `estimates`.

    Контрольная сумма модели берётся **из самого артефакта прогона**
    (`estimate.json.model_checksum`): исторический прогон на v1 не должен
    получать сумму текущей v2. `validation.json` модели не фиксирует — для
    этапа `checked` сумма остаётся `NULL` и заполняется этапом `estimated`.
    """
    runs_root = base / "runs"
    if not runs_root.is_dir():
        return 0
    count = 0
    for task_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        task_key = task_dir.name
        for run_dir in sorted(path for path in task_dir.iterdir() if path.is_dir()):
            run_id = run_dir.name
            context, _error = _read_json(run_dir / "context.json")
            if isinstance(context, dict):
                _record_task_from_context(conn, task_key, context)
            validation, error = _read_json(run_dir / "validation.json")
            if not error and isinstance(validation, dict):
                record_run(
                    conn,
                    run_id,
                    task_key,
                    "checked",
                    str(run_dir),
                    None,
                    None,
                    authoritative=True,
                )
                record_validation(conn, run_id, validation, task_key)
                count += 1
            estimate, error = _read_json(run_dir / "estimate.json")
            if not error and isinstance(estimate, dict):
                record_run(
                    conn,
                    run_id,
                    task_key,
                    "estimated",
                    str(run_dir),
                    estimate.get("model_checksum"),
                    None,
                    authoritative=True,
                )
                record_estimate(conn, run_id, estimate, task_key=task_key)
                count += 1
    conn.commit()
    return count


def _ingest_state(conn, path):
    """`state.json` → публикации и прогоны (то, чего нет в каталогах)."""
    state, error = _read_json(path)
    if error or not isinstance(state, dict):
        return 0
    count = 0
    published = {}
    for entry in state.get("published") or []:
        if not isinstance(entry, dict):
            continue
        published[(entry.get("target"), entry.get("ref"))] = entry
        record_publication(
            conn,
            entry.get("target"),
            entry.get("ref"),
            entry.get("url"),
            content_sha256=entry.get("content_sha256"),
        )
        count += 1
    page = state.get("model_page")
    if isinstance(page, dict) and page.get("id"):
        # `model_page.hash` — контрольная сумма модели, а не sha256 файла:
        # sha256 страницы лежит в `state.published[]` по тому же `(target, ref)`.
        entry = published.get((page.get("system") or "confluence", page.get("id"))) or {}
        record_publication(
            conn,
            page.get("system") or "confluence",
            page.get("id"),
            page.get("url"),
            content_sha256=entry.get("content_sha256"),
            model_checksum=page.get("hash"),
        )
        count += 1
    for entry in state.get("runs") or []:
        if not isinstance(entry, dict):
            continue
        run_dir = str(entry.get("run_dir") or "")
        # Контрольную сумму модели даёт артефакт прогона (`_ingest_runs`), а не
        # текущее состояние: прогоны на прошлой версии модели — не на этой.
        record_run(
            conn,
            Path(run_dir).name,
            entry.get("task_key"),
            None,
            run_dir,
        )
        count += 1
    conn.commit()
    return count


def ingest_workdir(workdir, cfg):
    """Бэкфилл зеркала из артефактов на диске. Повторный вызов не плодит дубли."""
    workdir = Path(workdir)
    base = workdir / STATE_DIR
    init = init_db(workdir, cfg)
    result = {
        "created": bool(init.get("created")),
        "user_version": int(init.get("user_version") or 0),
        "path": str(init.get("path") or ""),
        "tables": {},
        "warnings": [],
        "orphan_roles_removed": 0,
    }
    if not init.get("enabled", True):
        result["warnings"].append("storage.sqlite.enabled=false — бэкфилл не выполнен")
        return result
    if init.get("error"):
        result["warnings"].append("БД не открывается: %s" % init["error"])
        return result

    conn = connect(workdir, cfg, create=True)
    if conn is None:
        result["warnings"].append("БД не открывается — бэкфилл не выполнен")
        return result
    try:
        # «Полная пересборка» — в зеркале ещё нет ни одной версии модели: так
        # выглядит и `rm trr.sqlite3 && db ingest`, и `db init` на свежем файле.
        # Считаем ДО `record_model`: он сразу пишет текущую версию, и по
        # счётчику после него свежий файл не отличить от инкрементального.
        # Повторный инкрементальный ingest видит версии и предупреждения не даёт.
        try:
            versions_before = int(
                conn.execute("SELECT COUNT(*) FROM model_versions").fetchone()[0] or 0
            )
        except sqlite3.Error:
            versions_before = 0

        reference, error = _read_json(base / pathmod.REFERENCE_RELATIVE)
        if error:
            result["warnings"].append("%s: %s" % (pathmod.REFERENCE_RELATIVE, error))
            reference = None
        elif not isinstance(reference, dict):
            result["warnings"].append("%s: не JSON-объект" % pathmod.REFERENCE_RELATIVE)
            reference = None

        model, error = _read_json(base / pathmod.MODEL_RELATIVE)
        if error:
            result["warnings"].append("%s: %s" % (pathmod.MODEL_RELATIVE, error))
            model = None
        elif not isinstance(model, dict):
            result["warnings"].append("%s: не JSON-объект" % pathmod.MODEL_RELATIVE)
            model = None

        checksum = None
        if model is not None:
            record_model(conn, model)
            checksum = model.get("checksum")

        if reference is not None:
            record_reference(conn, reference, checksum)

        stats_payload, error = _read_json(base / pathmod.STATS_RELATIVE)
        if error:
            result["warnings"].append("%s: %s" % (pathmod.STATS_RELATIVE, error))
        elif isinstance(stats_payload, dict):
            record_stats(conn, stats_payload, checksum)

        sample, error = _read_json(base / pathmod.SAMPLE_RELATIVE)
        if error:
            result["warnings"].append("%s: %s" % (pathmod.SAMPLE_RELATIVE, error))
        elif isinstance(sample, dict):
            record_sample(conn, sample)

        # Векторы восстанавливаются из `norm/task-vectors.json`: это готовый
        # артефакт с термами, пересчёт не нужен. Без этого шага полная
        # пересборка БД давала `vectors=0` до следующего `trr vectors build`,
        # хотя инкрементальный ingest историю копит.
        vectors_payload, error = _read_json(base / pathmod.VECTORS_RELATIVE)
        if error:
            result["warnings"].append("%s: %s" % (pathmod.VECTORS_RELATIVE, error))
        elif isinstance(vectors_payload, dict):
            record_vectors(
                conn,
                vectors_payload.get("version") or 1,
                vectors_payload,
                vectors_payload.get("vectors") or [],
            )

        # Версии модели — из истории; предупреждение о полной пересборке ниже.
        _history_written, history_versions = _ingest_history(
            conn, base / "model" / "model-history.jsonl"
        )
        if versions_before == 0 and history_versions > 1:
            # Прошлые версии модели известны только метаданными
            # (version/checksum): их `model_buckets`/`sprint_stats` в истории не
            # лежат. Не выдумываем срезы — предупреждаем.
            result["warnings"].append(
                "полная пересборка БД: в истории версий модели %d, но "
                "sprint_stats/model_buckets восстанавливаются только для текущей "
                "модели (прошлых payload'ов в model/model-history.jsonl нет); "
                "историю версий копит инкрементальный ingest — см. "
                "references/artifacts.md §10.2" % history_versions
            )

        _ingest_runs(conn, base)
        _ingest_state(conn, base / "state.json")
        # Сироты разбивки по ролям (`task_key=''` без своего прогона) — остаток
        # миграции схемы 5: прогонов на диске для них нет, и в `estimate_roles`
        # они только засоряют счётчики.
        result["orphan_roles_removed"] = _drop_orphan_roles(conn)
        conn.commit()

        result["tables"] = stats(conn)["tables"]
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    return result


# ---------------------------------------------------------------------------
# Хуки пайплайна: открыть → записать → закрыть, никогда не бросить
# ---------------------------------------------------------------------------


def open_for(workdir, cfg=None):
    """Соединение для записи из пайплайна. Конфиг читается, если не передан."""
    if cfg is None:
        try:
            # Предупреждения конфига уже напечатал основной шаг: повторять их
            # из хука зеркала (в том числе на каждом `state.save`) нельзя.
            cfg = configmod.load_config(
                configmod.config_path(workdir), on_warning=lambda message: None
            )
        except Exception:  # noqa: BLE001 - нет конфига → дефолты
            cfg = configmod.DEFAULTS
    return connect(workdir, cfg, create=True)


def hook(workdir, cfg, action):
    """Выполнить `action(conn)` на зеркале. Любая ошибка — `[WARN]`, не исключение."""
    conn = open_for(workdir, cfg)
    if conn is None:
        return None
    try:
        return action(conn)
    except Exception as exc:  # noqa: BLE001 - зеркало не валит пайплайн
        _warn("шаг не записан: %s: %s" % (type(exc).__name__, exc))
        return None
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def current_model_checksum(workdir):
    """`checksum` модели с диска (None — модели нет)."""
    payload, error = _read_json(Path(workdir) / STATE_DIR / pathmod.MODEL_RELATIVE)
    if error or not isinstance(payload, dict):
        return None
    value = payload.get("checksum")
    return str(value) if value else None


def save_stats(workdir, cfg, stats_payload, model_checksum=None):
    """Хук `trr stats`: бакеты статистики + метрики."""

    def action(conn):
        checksum = model_checksum or current_model_checksum(workdir)
        written = record_stats(conn, stats_payload, checksum)
        record_metric(conn, "stats", "buckets", len(stats_payload.get("buckets") or []))
        record_metric(conn, "stats", "sample_rows", stats_payload.get("sample_rows"))
        return written

    return hook(workdir, cfg, action)


def save_model(workdir, cfg, model_payload, reference=None, stats_payload=None):
    """Хук `trr calibrate`: версия модели, её бакеты, правила и статистика."""

    def action(conn):
        written = record_model(conn, model_payload)
        checksum = model_payload.get("checksum")
        if reference is not None:
            record_reference(conn, reference, checksum)
        if stats_payload is not None:
            record_stats(conn, stats_payload, checksum)
        record_metric(conn, "model", "buckets", written)
        record_metric(conn, "model", "version", model_payload.get("version"))
        return written

    return hook(workdir, cfg, action)


def save_vectors(workdir, cfg, artifact):
    """Хук `trr vectors build`: `vector_meta` + BLOB-векторы задач."""

    def action(conn):
        version = artifact.get("version") or 1
        written = record_vectors(conn, version, artifact, artifact.get("vectors") or [])
        record_metric(conn, "vectors", "tasks", written)
        return written

    return hook(workdir, cfg, action)


def save_similar(workdir, cfg, task_key, similar_rows, model_version):
    """Хук `trr vectors similar`: пары `(задача, похожая)`."""

    def action(conn):
        return record_similar(conn, task_key, similar_rows, model_version)

    return hook(workdir, cfg, action)


def save_check(
    workdir,
    cfg,
    run_id,
    task_key,
    run_dir,
    validation,
    model_checksum=None,
    config_sha256=None,
):
    """Хук `trr check`: прогон, валидация и метрики проверки."""

    def action(conn):
        record_run(
            conn, run_id, task_key, "checked", run_dir, model_checksum, config_sha256
        )
        record_validation(conn, run_id, validation, task_key)
        record_metric(conn, "check", "gaps", len(validation.get("gaps") or []))
        record_metric(conn, "check", "checks", len(validation.get("checks") or []))
        return None

    return hook(workdir, cfg, action)


def save_estimate(
    workdir,
    cfg,
    run_id,
    task_key,
    run_dir,
    estimate_payload,
    params_multiplier=None,
    config_sha256=None,
):
    """Хук `trr estimate`: прогон, оценка и разбивка по ролям."""

    def action(conn):
        record_run(
            conn,
            run_id,
            task_key,
            "estimated",
            run_dir,
            estimate_payload.get("model_checksum"),
            config_sha256,
        )
        record_estimate(conn, run_id, estimate_payload, params_multiplier, task_key)
        record_metric(
            conn, "estimate", "total_expected", estimate_payload["total"]["expected"]
        )
        return None

    return hook(workdir, cfg, action)


def save_publication(workdir, cfg, target, ref, url, content_sha256, model_checksum=None):
    """Хук публикации: `state.published[]` и зеркало пишутся вместе."""

    def action(conn):
        return record_publication(
            conn, target, ref, url, content_sha256, model_checksum
        )

    return hook(workdir, cfg, action)


def save_event(workdir, cfg, kind, payload=None):
    """Хук изменения состояния: событие в журнал `events`."""

    def action(conn):
        return record_event(conn, kind, payload)

    return hook(workdir, cfg, action)


def save_synth_run(workdir, cfg, summary, run_id=None):
    """Хук `trr synth-run --record`: строка `synth_runs` + метрики `synth`."""

    def action(conn):
        return record_synth_run(conn, summary, run_id=run_id)

    return hook(workdir, cfg, action)

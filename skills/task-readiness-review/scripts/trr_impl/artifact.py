#!/usr/bin/env python3
"""Экспорт и импорт обученных артефактов: переносимый бандл `.tar.gz`.

Зачем: обучение (эталон → выборка спринтов → статистика → калибровка) требует
чтения Confluence и Jira. Второй разработчик, CI или другая машина не должны
повторять этот прогон: они импортируют уже обученную модель и получают
`stage=trained` без `train`.

Формат бандла (`trr artifact pack`)::

    manifest.json                  манифест (artifact-manifest.schema.json)
    norm/reference-estimates.json  эталон, на котором обучена модель
    norm/sprint-sample.json        выборка спринтов (если include_sprint_sample)
    norm/task-texts.json           тексты задач для векторов (если есть)
    norm/sprint-stats.json         агрегаты по бакетам
    norm/task-vectors.json         векторы задач (если есть)
    model/estimation-model.json    модель оценки
    model/estimation-model.md      человекочитаемая страница модели

Требования к архиву:

* **детерминизм** — фиксированный порядок файлов, `mtime=0`, `uid/gid=0`,
  `uname/gname` пустые, `mode=0644`, gzip без имени файла и с `mtime=0`;
  одинаковый вход даёт побайтово одинаковый `.tar.gz` (проверяется тестом);
* **целостность** — `files[].sha256` и `files[].bytes` каждого файла плюс
  `model.checksum` модели; при распаковке всё сверяется;
* **провенанс** — `origin` (проект, борд, спринты, страница эталона) и
  `corpus` (строки, спринты, недостаточные бакеты), чтобы было видно, на каких
  данных обучена модель;
* **без мусора** — `__pycache__`, `*.tmp` и прочие файлы в бандл не попадают:
  список файлов закрыт.

Импорт (`trr artifact unpack`) fail-closed: чужой проект требует явного
`--allow-foreign-project`, поверх существующих артефактов — `--force`,
неизвестная версия формата и расхождение контрольных сумм — отказ (5).
"""

import gzip
import hashlib
import io
import json
import os
import tarfile
import tempfile
from pathlib import Path

from trr_impl import config as configmod
from trr_impl import limits
from trr_impl import schema_lite
from trr_impl import state as statemod
from trr_impl.paths import (
    MODEL_PAGE_RELATIVE,
    MODEL_RELATIVE,
    REFERENCE_RELATIVE,
    SAMPLE_RELATIVE,
    STATS_RELATIVE,
    TEXTS_RELATIVE,
    VECTORS_RELATIVE,
)
from trr_impl.stats import now_utc

__all__ = [
    "ARTIFACT_VERSION",
    "MANIFEST_NAME",
    "MANIFEST_SCHEMA",
    "MODEL_PAGE_RELATIVE",
    "MODEL_RELATIVE",
    "REFERENCE_RELATIVE",
    "SAMPLE_RELATIVE",
    "STATS_RELATIVE",
    "TEXTS_RELATIVE",
    "VECTORS_RELATIVE",
    "artifact_name",
    "build_manifest",
    "inspect",
    "pack",
    "plan",
    "record",
    "unpack",
]

ARTIFACT_VERSION = 1
MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA = "artifact-manifest"


# Обязательные файлы бандла: без любого из них обучение не воспроизвести.
REQUIRED_FILES = (
    REFERENCE_RELATIVE,
    STATS_RELATIVE,
    MODEL_RELATIVE,
    MODEL_PAGE_RELATIVE,
)

# Порядок файлов в архиве фиксирован — от него зависит sha256 всего бандла.
FILE_ORDER = (
    MANIFEST_NAME,
    REFERENCE_RELATIVE,
    SAMPLE_RELATIVE,
    TEXTS_RELATIVE,
    STATS_RELATIVE,
    VECTORS_RELATIVE,
    MODEL_RELATIVE,
    MODEL_PAGE_RELATIVE,
)

# Схемы входных артефактов: бандл с невалидным артефактом бессмыслен.
_INPUT_SCHEMAS = (
    (REFERENCE_RELATIVE, "reference-estimates"),
    (SAMPLE_RELATIVE, "sprint-sample"),
    (STATS_RELATIVE, "sprint-stats"),
    (MODEL_RELATIVE, "estimation-model"),
)

_EPILOG_HINT = "запустите /task-readiness-review train (артефакт обучения не собран)"


# ---------------------------------------------------------------------------
# Служебное
# ---------------------------------------------------------------------------


def _skill_version():
    """Версия скилла из файла VERSION (то же значение, что пишет `init`)."""
    path = Path(configmod.SKILL_ROOT) / "VERSION"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _prefixed(digest):
    """`sha256:<hex>` — форма checksum в манифесте."""
    return "sha256:%s" % digest


def _strip_prefix(value):
    text = str(value or "").strip()
    if text.startswith("sha256:"):
        return text[len("sha256:") :]
    return text


def artifact_name(version=None):
    """Имя файла бандла: `task-readiness-model-v<версия>.tar.gz`."""
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        return "task-readiness-model.tar.gz"
    return "task-readiness-model-v%d.tar.gz" % version


def default_out(workdir, version=None):
    """Куда писать бандл без `--out`: `.task-readiness/<имя бандла>`."""
    return Path(workdir) / statemod.STATE_DIR / artifact_name(version)


def _read_json(path):
    """Прочитать JSON. Возвращает `(payload, error)`; ровно одно из них None."""
    limits.check_size(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except OSError as exc:
        return None, "не читается: %s" % exc
    except ValueError as exc:
        return None, "невалидный JSON: %s" % exc


def _read_bytes(path):
    limits.check_size(path)
    with open(path, "rb") as handle:
        return handle.read()


def _schema_errors(name, payload):
    """Ошибки схемы артефакта; пустой список — валидно."""
    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, name)
    except schema_lite.SchemaError as exc:
        return ["схема %s не читается: %s" % (name, exc)]
    return schema_lite.validate(payload, schema, name)


def model_checksum(model):
    """sha256 канонического JSON модели без поля `checksum` (§8)."""
    payload = {key: value for key, value in model.items() if key != "checksum"}
    return schema_lite.sha256_canonical(payload)


def _model_version(workdir):
    """Версия модели в рабочей директории; None, если модели нет."""
    try:
        model, error = _read_json(statemod.model_path(workdir))
    except limits.LimitError:
        return None
    if error or not isinstance(model, dict):
        return None
    version = model.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version


# ---------------------------------------------------------------------------
# Детерминированный tar.gz
# ---------------------------------------------------------------------------


def _write_bundle(target, entries):
    """Записать детерминированный `.tar.gz` атомарно.

    `entries` — список `(путь, bytes)` в фиксированном порядке. Всё, что может
    внести недетерминизм, зафиксировано: `mtime=0`, `uid=gid=0`, пустые
    `uname`/`gname`, `mode=0644`, gzip без имени файла и с `mtime=0`.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".%s-" % target.name, suffix=".tmp", dir=str(target.parent)
    )
    os.close(descriptor)
    try:
        with open(temporary, "wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
                with tarfile.open(
                    fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT
                ) as tar:
                    for name, payload in entries:
                        info = tarfile.TarInfo(name)
                        info.size = len(payload)
                        info.mtime = 0
                        info.mode = 0o644
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        info.type = tarfile.REGTYPE
                        tar.addfile(info, io.BytesIO(payload))
        os.replace(temporary, str(target))
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return target


def _read_bundle(path):
    """Прочитать архив в `{путь: bytes}`. Возвращает `(contents, error)`.

    Разрешены только обычные файлы с относительными путями: каталоги, ссылки и
    `..`/абсолютные пути — отказ (иначе распаковка стала бы записью вне
    `.task-readiness/`).
    """
    limits.check_size(path)
    try:
        with tarfile.open(str(path), "r:gz") as tar:
            contents = {}
            for member in tar.getmembers():
                if not member.isfile():
                    return None, "элемент %r — не обычный файл" % member.name
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    return None, "недопустимый путь в архиве: %r" % member.name
                handle = tar.extractfile(member)
                contents[member.name] = handle.read() if handle is not None else b""
    except (OSError, tarfile.TarError, EOFError) as exc:
        return None, "не читается как tar.gz: %s" % exc
    return contents, None


def _parse_manifest(contents):
    """Достать и провалидировать `manifest.json`. Возвращает `(manifest, error)`."""
    raw = contents.get(MANIFEST_NAME)
    if raw is None:
        return None, "в архиве нет %s" % MANIFEST_NAME
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return None, "%s не разбирается как JSON: %s" % (MANIFEST_NAME, exc)
    if not isinstance(manifest, dict):
        return None, "%s должен быть JSON-объектом" % MANIFEST_NAME
    errors = _schema_errors(MANIFEST_SCHEMA, manifest)
    if errors:
        shown = "; ".join(errors[:3])
        if len(errors) > 3:
            shown += "; ещё %d" % (len(errors) - 3)
        return None, "%s не соответствует схеме: %s" % (MANIFEST_NAME, shown)
    return manifest, None


def _verify_files(contents, manifest):
    """Сверить sha256 и размеры файлов бандла. Возвращает список проблем."""
    problems = []
    listed = {}
    for entry in manifest.get("files") or []:
        path = entry["path"]
        listed[path] = entry
        payload = contents.get(path)
        if payload is None:
            problems.append("в архиве нет файла %s" % path)
            continue
        if len(payload) != entry["bytes"]:
            problems.append(
                "%s: размер %d ≠ %d из манифеста"
                % (path, len(payload), entry["bytes"])
            )
            continue
        digest = _sha256(payload)
        if digest != entry["sha256"]:
            problems.append(
                "%s: sha256 %s… ≠ %s… из манифеста"
                % (path, digest[:8], entry["sha256"][:8])
            )
    extra = sorted(set(contents) - set(listed) - {MANIFEST_NAME})
    for path in extra:
        problems.append("в архиве лишний файл %s (его нет в манифесте)" % path)
    return problems


# ---------------------------------------------------------------------------
# Манифест
# ---------------------------------------------------------------------------


def _board_from_config(cfg):
    sources = (cfg or {}).get("sources") or {}
    if not isinstance(sources, dict):
        return None
    for item in sources.get("sprints") or []:
        if isinstance(item, dict) and isinstance(item.get("board_id"), int):
            return item["board_id"]
    return None


def _page_id_value(value):
    """`page_id` в манифесте: число, если это число в виде строки."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    return int(text) if text.isdigit() else text


def build_manifest(cfg, model, reference, stats, sample, files, published_page=None):
    """Собрать `manifest.json` по уже прочитанным артефактам.

    `files` — список `{"path", "sha256", "bytes"}` в фиксированном порядке.
    `published_page` — запись `state.model_page`, если страница модели
    соответствует текущей модели (иначе `None`).
    """
    reference_source = ((model or {}).get("sources") or {}).get("reference") or {}
    if not reference_source and isinstance(reference, dict):
        # Модель без `sources.reference` (старый формат) — берём источник эталона
        # из самого reference-estimates.json.
        reference_source = reference.get("source") or {}
    checksum = model_checksum(model)

    sprints = []
    board_id = None
    rows = 0
    if isinstance(sample, dict):
        source = sample.get("source") if isinstance(sample.get("source"), dict) else {}
        board_id = source.get("board_id")
        for item in source.get("sprints") or []:
            if isinstance(item, dict) and item.get("name"):
                sprints.append(str(item["name"]))
        rows = len(sample.get("rows") or [])
    if not sprints:
        for item in reference_source_sprints(model):
            sprints.append(item)
    if board_id is None:
        board_id = _board_from_config(cfg)
    if not rows and isinstance(stats, dict):
        rows = int(stats.get("sample_rows") or 0)

    insufficient = 0
    if isinstance(stats, dict):
        insufficient = len(stats.get("insufficient") or [])

    jira = (cfg or {}).get("jira") if isinstance((cfg or {}).get("jira"), dict) else {}

    manifest = {
        "artifact_version": ARTIFACT_VERSION,
        "created_at": now_utc(),
        "skill_version": _skill_version(),
        "model": {
            "version": int(model["version"]),
            "checksum": _prefixed(checksum),
            "scale": list(model.get("scale") or []),
            "buckets": len(model.get("buckets") or []),
            "absent_roles": list(model.get("absent_roles") or []),
        },
        "origin": {
            "project": str(jira.get("project") or ""),
            "board_id": board_id if isinstance(board_id, int) else None,
            "sprints": sprints,
            "reference_page_id": _page_id_value(reference_source.get("page_id")),
            "reference_url": reference_source.get("url") or None,
        },
        "corpus": {
            "rows": rows,
            "sprints": len(sprints),
            "insufficient_buckets": insufficient,
        },
        "files": files,
        "published_page": published_page,
    }
    return manifest


def reference_source_sprints(model):
    """Названия спринтов из модели (`sources.sprints[].name`)."""
    sprints = ((model or {}).get("sources") or {}).get("sprints") or []
    result = []
    for item in sprints:
        if isinstance(item, dict) and item.get("name"):
            result.append(str(item["name"]))
    return result


def _published_page(workdir, checksum):
    """`state.model_page` в форме манифеста, если он соответствует модели."""
    try:
        state = statemod.load(workdir)
    except statemod.StateError:
        return None, None
    page = state.get("model_page")
    if not isinstance(page, dict):
        return None, None
    if str(page.get("hash") or "").strip() != checksum:
        return None, (
            "[WARN] state.model_page.hash не совпадает с моделью — страница модели "
            "в бандл не попадёт (перепубликуйте: /task-readiness-review publish --model)"
        )
    return (
        {
            "system": page.get("system"),
            "id": str(page.get("id")),
            "url": page.get("url"),
            "hash": _prefixed(checksum),
        },
        None,
    )


# ---------------------------------------------------------------------------
# pack
# ---------------------------------------------------------------------------


def pack(workdir, out=None, include_sprint_sample=True, cfg=None):
    """Собрать бандл. Возвращает `(код, строки, payload)`; коды 0/4/5."""
    workdir = Path(workdir)
    base = workdir / statemod.STATE_DIR
    if cfg is None:
        try:
            cfg = configmod.load_config(configmod.config_path(workdir))
        except configmod.ConfigError as exc:
            return (
                3,
                ["[MISSING] %s — %s" % (configmod.CONFIG_FILENAME, exc)],
                {},
            )

    missing = [rel for rel in REQUIRED_FILES if not (base / rel).is_file()]
    if missing:
        return (
            4,
            ["[MISSING] %s — %s" % (rel, _EPILOG_HINT) for rel in missing],
            {"missing": missing},
        )

    payloads = {}
    for relative, schema_name in _INPUT_SCHEMAS:
        path = base / relative
        if not path.is_file():
            continue
        payload, error = _read_json(path)
        if error:
            return 5, ["[BLOCKED] %s — %s" % (relative, error)], {}
        errors = _schema_errors(schema_name, payload)
        if errors:
            return (
                5,
                ["[BLOCKED] %s — схема %s: %s" % (relative, schema_name, errors[0])],
                {},
            )
        payloads[relative] = payload

    model = payloads[MODEL_RELATIVE]
    checksum = model_checksum(model)
    if str(model.get("checksum") or "") != checksum:
        return (
            5,
            [
                "[BLOCKED] %s: checksum модели не совпадает с содержимым — "
                "пересоберите модель (/task-readiness-review train)" % MODEL_RELATIVE
            ],
            {},
        )

    entries = []
    messages = []
    files = []
    for relative in FILE_ORDER:
        if relative == MANIFEST_NAME:
            continue
        path = base / relative
        if not path.is_file():
            continue
        if relative == SAMPLE_RELATIVE and not include_sprint_sample:
            messages.append(
                "[WARN] %s не включён в бандл (artifacts.include_sprint_sample: false)"
                % SAMPLE_RELATIVE
            )
            continue
        data = _read_bytes(path)
        entries.append((relative, data))
        files.append(
            {"path": relative, "sha256": _sha256(data), "bytes": len(data)}
        )
    if include_sprint_sample and SAMPLE_RELATIVE not in payloads:
        messages.append(
            "[WARN] %s отсутствует — бандл собран без выборки спринтов" % SAMPLE_RELATIVE
        )

    published, warning = _published_page(workdir, checksum)
    if warning:
        messages.append(warning)
    manifest = build_manifest(
        cfg,
        model,
        payloads[REFERENCE_RELATIVE],
        payloads[STATS_RELATIVE],
        payloads.get(SAMPLE_RELATIVE),
        files,
        published_page=published,
    )
    manifest_errors = _schema_errors(MANIFEST_SCHEMA, manifest)
    if manifest_errors:
        return (
            5,
            ["[BLOCKED] manifest.json — схема: %s" % manifest_errors[0]],
            {},
        )

    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    target = Path(out) if out else default_out(workdir, model["version"])
    if not target.is_absolute():
        target = Path.cwd() / target
    try:
        _write_bundle(target, [(MANIFEST_NAME, manifest_bytes)] + entries)
    except OSError as exc:
        return 4, ["[MISSING] %s — %s" % (target, exc)], {}

    data = target.read_bytes()
    digest = _sha256(data)
    messages.append(
        "[OK] artifact: %s (%d файлов, %d байт, sha256:%s)"
        % (target, len(files) + 1, len(data), digest)
    )
    messages.append(
        "[OK] model: v%s %s, бакетов %d, строк корпуса %d"
        % (
            manifest["model"]["version"],
            manifest["model"]["checksum"],
            manifest["model"]["buckets"],
            manifest["corpus"]["rows"],
        )
    )
    return (
        0,
        messages,
        {
            "artifact": str(target),
            "sha256": digest,
            "bytes": len(data),
            "manifest": manifest,
        },
    )


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


def inspect(path):
    """Показать манифест бандла сводкой. Возвращает `(код, строки, payload)`."""
    target = Path(path)
    if not target.is_file():
        return (
            4,
            ["[MISSING] %s — файла нет; соберите бандл: trr artifact pack" % target],
            {},
        )
    try:
        contents, error = _read_bundle(target)
    except limits.LimitError as exc:
        return 4, ["[MISSING] %s" % exc], {}
    if error:
        return 5, ["[BLOCKED] %s — %s" % (target, error)], {}
    manifest, error = _parse_manifest(contents)
    if error:
        return 5, ["[BLOCKED] %s — %s" % (target, error)], {}
    if manifest["artifact_version"] != ARTIFACT_VERSION:
        return (
            5,
            [
                "[BLOCKED] %s — версия формата %r не поддерживается (ожидается %d)"
                % (target, manifest["artifact_version"], ARTIFACT_VERSION)
            ],
            {},
        )
    problems = _verify_files(contents, manifest)
    origin = manifest["origin"]
    corpus = manifest["corpus"]
    model = manifest["model"]
    lines = [
        "[OK] artifact: %s (формат %d, %s)"
        % (target, manifest["artifact_version"], manifest["skill_version"]),
        "  проект: %s" % (origin["project"] or "—"),
        "  спринты: %d (%s)"
        % (corpus["sprints"], ", ".join(origin["sprints"]) or "—"),
        "  строк корпуса: %d, недостаточных бакетов: %d"
        % (corpus["rows"], corpus["insufficient_buckets"]),
        "  модель: v%s %s, бакетов %d, роли без эталона: %s"
        % (
            model["version"],
            model["checksum"],
            model["buckets"],
            ", ".join(model["absent_roles"]) or "—",
        ),
        "  файлов: %d" % len(manifest["files"]),
    ]
    page = manifest.get("published_page")
    if isinstance(page, dict):
        lines.append("  страница модели: %s" % page.get("url"))
    else:
        lines.append("  страница модели: не опубликована")
    if problems:
        for problem in problems:
            lines.append("[BLOCKED] %s" % problem)
        return 5, lines, {"manifest": manifest}
    lines.append("[OK] sha256 всех файлов совпадает с манифестом")
    return 0, lines, {"manifest": manifest}


# ---------------------------------------------------------------------------
# unpack
# ---------------------------------------------------------------------------


def _page_id_from_url(url):
    match = None
    text = str(url or "")
    marker = "pageId="
    index = text.find(marker)
    if index >= 0:
        tail = text[index + len(marker) :]
        digits = ""
        for char in tail:
            if char.isdigit():
                digits += char
            else:
                break
        match = digits or None
    return match


def _apply_state(workdir, checksum, model_page):
    """Поставить `stage=trained` и записать модель/страницу модели в state.

    `set_stage` здесь не подходит намеренно: импорт — явная замена обученного
    состояния. После `--force` поверх `published` этап обязан вернуться в
    `trained` (страница модели пришла из другого проекта), а `set_stage`
    запрещает понижение, кроме `reason="enrich"`.
    """
    try:
        state = statemod.load(workdir)
    except statemod.StateError:
        state = statemod.default_state(_skill_version())
    state["stage"] = "trained"
    state["model_checksum"] = checksum
    state["model_page"] = model_page
    state["updated_at"] = statemod.now_utc()
    statemod.save(workdir, state)
    return state


def unpack(
    path,
    workdir,
    force=False,
    allow_foreign_project=False,
    cfg=None,
):
    """Развернуть бандл в `.task-readiness/`. Возвращает `(код, строки, payload)`.

    Коды: 0 — импорт выполнен (в том числе с `[WARN]`), 2 — гейт не пройден
    (чужой проект без флага, уже есть артефакты без `--force`), 4 — нет файла
    бандла, 5 — бандл не читается/не соответствует схеме/не сходится checksum.
    """
    target = Path(path)
    workdir = Path(workdir)
    base = workdir / statemod.STATE_DIR
    if not target.is_file():
        return (
            4,
            ["[MISSING] %s — файла нет; передайте путь к бандлу" % target],
            {},
        )
    if cfg is None:
        try:
            cfg = configmod.load_config(configmod.config_path(workdir))
        except configmod.ConfigError as exc:
            return (
                3,
                ["[MISSING] %s — %s" % (configmod.CONFIG_FILENAME, exc)],
                {},
            )

    try:
        contents, error = _read_bundle(target)
    except limits.LimitError as exc:
        return 4, ["[MISSING] %s" % exc], {}
    if error:
        return 5, ["[BLOCKED] %s — %s" % (target, error)], {}
    manifest, error = _parse_manifest(contents)
    if error:
        return 5, ["[BLOCKED] %s — %s" % (target, error)], {}
    if manifest["artifact_version"] != ARTIFACT_VERSION:
        return (
            5,
            [
                "[BLOCKED] %s — версия формата %r не поддерживается (ожидается %d)"
                % (target, manifest["artifact_version"], ARTIFACT_VERSION)
            ],
            {},
        )

    problems = _verify_files(contents, manifest)
    if problems:
        lines = ["[BLOCKED] %s" % problem for problem in problems]
        lines.append(
            "[BLOCKED] %s — бандл повреждён: контрольные суммы не сходятся" % target
        )
        return 5, lines, {}

    raw_model = contents.get(MODEL_RELATIVE)
    if raw_model is None:
        return (
            5,
            ["[BLOCKED] %s — в бандле нет %s" % (target, MODEL_RELATIVE)],
            {},
        )
    try:
        model = json.loads(raw_model.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return (
            5,
            ["[BLOCKED] %s — %s не разбирается: %s" % (target, MODEL_RELATIVE, exc)],
            {},
        )
    if not isinstance(model, dict):
        return (
            5,
            ["[BLOCKED] %s — %s должен быть JSON-объектом" % (target, MODEL_RELATIVE)],
            {},
        )
    errors = _schema_errors("estimation-model", model)
    if errors:
        return (
            5,
            ["[BLOCKED] %s — схема estimation-model: %s" % (target, errors[0])],
            {},
        )
    checksum = model_checksum(model)
    declared = _strip_prefix(manifest["model"]["checksum"])
    if declared != checksum:
        return (
            5,
            [
                "[BLOCKED] %s — checksum модели не совпадает: в манифесте %s…, "
                "пересчитано %s…" % (target, declared[:8], checksum[:8])
            ],
            {},
        )
    if manifest["model"]["version"] != model.get("version"):
        return (
            5,
            [
                "[BLOCKED] %s — версия модели в манифесте (%r) ≠ в файле (%r)"
                % (target, manifest["model"]["version"], model.get("version"))
            ],
            {},
        )

    messages = []
    jira = cfg.get("jira") if isinstance(cfg.get("jira"), dict) else {}
    project = str(jira.get("project") or "").strip()
    origin_project = str(manifest["origin"]["project"] or "").strip()
    if origin_project != project:
        warning = (
            "[WARN] артефакт из проекта %s, у вас %s — оценка будет смещена"
            % (origin_project or "—", project or "—")
        )
        if not allow_foreign_project:
            return (
                2,
                [
                    warning,
                    "[BLOCKED] unpack: чужой проект — повторите с "
                    "--allow-foreign-project, если это осознанное решение",
                ],
                {},
            )
        messages.append(warning)

    existing = [
        relative
        for relative in FILE_ORDER
        if relative != MANIFEST_NAME and (base / relative).is_file()
    ]
    if existing and not force:
        return (
            2,
            [
                "[BLOCKED] unpack: в %s уже есть артефакты обучения (%s) — "
                "используйте --force для перезаписи"
                % (statemod.STATE_DIR, ", ".join(existing)),
            ],
            {},
        )

    for entry in manifest["files"]:
        destination = base / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = contents[entry["path"]]
        descriptor, temporary = tempfile.mkstemp(
            prefix=".%s-" % destination.name, suffix=".tmp", dir=str(destination.parent)
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, str(destination))
        except BaseException:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise

    model_page = None
    page = manifest.get("published_page")
    if isinstance(page, dict):
        page_hash = _strip_prefix(page.get("hash"))
        if page_hash != checksum:
            messages.append(
                "[WARN] published_page.hash не совпадает с моделью — "
                "state.model_page не восстановлен (опубликуйте: "
                "/task-readiness-review publish --model)"
            )
        else:
            page_id = (
                str(page.get("id") or "").strip()
                or _page_id_from_url(page.get("url"))
                or str(page.get("url"))
            )
            model_page = {
                "system": page.get("system"),
                "id": page_id,
                "url": page.get("url"),
                "hash": checksum,
                "version": int(model["version"]),
            }

    _apply_state(workdir, checksum, model_page)

    messages.append(
        "[OK] artifact: %s → %s (%d файлов)"
        % (target, statemod.STATE_DIR, len(manifest["files"]))
    )
    messages.append(
        "[OK] model: v%s %s, бакетов %d"
        % (model["version"], _prefixed(checksum), len(model.get("buckets") or []))
    )
    messages.append("[OK] state: stage=trained")
    if model_page is not None:
        messages.append("[OK] model_page: %s" % model_page["url"])
    return (
        0,
        messages,
        {
            "artifact": str(target),
            "checksum": checksum,
            "stage": "trained",
            "files": len(manifest["files"]),
            "model_page": model_page,
        },
    )


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def _title(template, version, project):
    """Подставить {{model_version}} и {{project}} в шаблон заголовка."""
    text = str(template or "")
    text = text.replace("{{model_version}}", str(version if version is not None else "?"))
    text = text.replace("{{project}}", project or "?")
    return text


def plan(workdir, cfg, target):
    """Куда публиковать бандл для `target`. Возвращает `(код, строки, payload)`.

    Код 0 — место задано (`[OK]`), 2 — место не задано (`[MISSING]` с
    инструкцией). Ничего не публикует и не пишет.
    """
    if target not in configmod.ARTIFACT_TARGETS or target == "none":
        return (
            2,
            [
                "[BLOCKED] artifact plan: цель %r не публикуется — допустимы: %s"
                % (target, ", ".join(t for t in configmod.ARTIFACT_TARGETS if t != "none"))
            ],
            {},
        )

    artifacts = cfg.get("artifacts") if isinstance(cfg.get("artifacts"), dict) else {}
    jira = cfg.get("jira") if isinstance(cfg.get("jira"), dict) else {}
    project = str(jira.get("project") or "")
    version = _model_version(workdir)
    name = artifact_name(version)
    problem = configmod.artifact_place_problem(cfg, target)
    if problem:
        return 2, ["[MISSING] %s" % problem], {"target": target, "name": name}

    place = {}
    lines = ["[OK] artifact plan: %s" % target]
    if target == "local":
        path = (artifacts.get("local") or {}).get("path")
        place["path"] = str(path)
        lines.append("  path: %s" % path)
    elif target == "confluence":
        confluence = artifacts.get("confluence") or {}
        place["space"] = str(confluence.get("space"))
        place["parent_page_id"] = str(confluence.get("parent_page_id"))
        place["title"] = _title(confluence.get("title_template"), version, project)
        lines.append("  space: %s" % place["space"])
        lines.append("  parent_page_id: %s" % place["parent_page_id"])
        lines.append("  title: %s" % place["title"])
    elif target == "gitlab":
        gitlab = artifacts.get("gitlab") or {}
        place["project"] = str(gitlab.get("project"))
        place["branch"] = str(gitlab.get("branch") or "main")
        place["path"] = "%s%s" % (gitlab.get("path") or "", name)
        lines.append("  project: %s" % place["project"])
        lines.append("  branch: %s" % place["branch"])
        lines.append("  path: %s" % place["path"])
    elif target == "obsidian":
        path = (artifacts.get("obsidian") or {}).get("path")
        place["path"] = str(path)
        lines.append("  path: %s" % path)
    lines.append("  artifact: %s" % name)
    return 0, lines, {"target": target, "name": name, "place": place}


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


def record(workdir, target, ref, url, file=None):
    """Записать публикацию бандла в `state.artifacts[]`. Коды 0/2/4."""
    workdir = Path(workdir)
    if target not in statemod.ARTIFACT_TARGETS:
        return (
            2,
            [
                "[BLOCKED] artifact record: цель %r неизвестна — допустимы: %s"
                % (target, ", ".join(statemod.ARTIFACT_TARGETS))
            ],
            {},
        )

    digest = None
    if file:
        path = Path(file)
        if not path.is_absolute():
            path = workdir / path
        if not path.is_file():
            return (
                4,
                ["[MISSING] %s — файла бандла нет; сначала trr artifact pack" % path],
                {},
            )
        try:
            digest = _sha256(path.read_bytes())
        except OSError as exc:
            return 4, ["[MISSING] %s — %s" % (path, exc)], {}

    try:
        manifest_checksum = _prefixed(statemod.model_checksum(workdir))
    except statemod.StateError:
        manifest_checksum = None

    try:
        entry = statemod.add_artifact(
            str(workdir),
            target,
            ref,
            url,
            artifact_sha256=digest,
            manifest_checksum=manifest_checksum,
        )
    except statemod.StateError as exc:
        return (
            2,
            ["[BLOCKED] artifact record: %s — проверьте .task-readiness/state.json" % exc],
            {},
        )

    lines = [
        "[OK] artifact: %s %s" % (entry["target"], entry["ref"]),
        "  url: %s" % entry["url"],
    ]
    if entry["artifact_sha256"]:
        lines.append("  sha256: %s" % entry["artifact_sha256"])
    if entry["manifest_checksum"]:
        lines.append("  manifest: %s" % entry["manifest_checksum"])
    return 0, lines, {"entry": entry}

#!/usr/bin/env python3
"""Состояние скилла: `.task-readiness/state.json`.

Запись атомарная (временный файл в том же каталоге + `os.replace`), формат —
канонический JSON (`sort_keys`, `indent=2`, один перевод строки в конце), чтобы
одинаковое состояние давало байт-в-байт одинаковый файл.

Этап (`stage`) только растёт по цепочке
`installed → configured → trained → checked → estimated → published`.
Единственный разрешённый возврат назад — в `trained` после `enrich`
(перепубликация страницы модели) и только с `reason="enrich"`; всё остальное —
ошибка.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from trr_impl import limits
from trr_impl import schema_lite
from trr_impl import store as storemod
from trr_impl.paths import MODEL_RELATIVE

__all__ = [
    "ARTIFACT_TARGETS",
    "PAGE_TARGETS",
    "PUBLICATION_TARGETS",
    "STAGES",
    "StateError",
    "add_artifact",
    "add_publication",
    "add_run",
    "default_state",
    "drop_publication",
    "load",
    "model_checksum",
    "model_path",
    "now_utc",
    "save",
    "set_stage",
    "state_path",
]

STATE_DIR = ".task-readiness"
STATE_FILE = "state.json"

STAGES = (
    "installed",
    "configured",
    "trained",
    "checked",
    "estimated",
    "published",
)
_STAGE_INDEX = {name: index for index, name in enumerate(STAGES)}

# Куда разрешено публиковать (CONTRACT.md §3: output_target без `none`).
# `jira` — комментарий в саму задачу: это цель по умолчанию для `trr publish`,
# а `confluence`/`obsidian` остаются дополнительной публикацией страницы/заметки.
PUBLICATION_TARGETS = ("confluence", "jira", "obsidian")

# Цели, которые публикуются как страница/заметка (`publish --target`).
# Комментарий в Jira — отдельный режим: у него нет ни `--ref`, ни `--file`.
PAGE_TARGETS = ("confluence", "obsidian")

# Куда публикуется обученный бандл (`trr artifact record`). Отличается от
# PUBLICATION_TARGETS: бандл — это файл модели, а не отчёт, поэтому есть
# `gitlab` и `local` и нет `jira`.
ARTIFACT_TARGETS = ("confluence", "gitlab", "obsidian", "local")

# Поля состояния, которые можно менять через set_stage(**kwargs).
_MUTABLE_FIELDS = (
    "skill_version",
    "config_sha256",
    "model_checksum",
    "model",
    "model_page",
)

# Каталог прогонов: `run_dir` в state всегда начинается с него и отсчитывается
# от корня проекта.
RUNS_PREFIX = ".task-readiness/runs/"


class StateError(Exception):
    """Состояние отсутствует, повреждено или переход этапа запрещён."""


def now_utc():
    """Текущий момент в формате, принятом в артефактах: 2026-11-17T09:41:07Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def state_path(workdir):
    return Path(workdir) / STATE_DIR / STATE_FILE


def model_path(workdir):
    return Path(workdir) / STATE_DIR / MODEL_RELATIVE


def default_state(skill_version):
    """Начальное состояние: этап installed, модели и прогонов нет."""
    return {
        "skill_version": str(skill_version),
        "stage": "installed",
        "config_sha256": None,
        "model_checksum": None,
        "model": None,
        "model_page": None,
        "runs": [],
        "published": [],
        "artifacts": [],
        "updated_at": now_utc(),
    }


def load(workdir):
    """Прочитать состояние. Нет файла или битый JSON → StateError."""
    path = state_path(workdir)
    if not path.is_file():
        raise StateError("нет файла состояния: %s" % path)
    limits.check_size(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise StateError("не удалось прочитать %s: %s" % (path, exc))
    except ValueError as exc:
        raise StateError("%s — невалидный JSON: %s" % (path, exc))
    if not isinstance(data, dict):
        raise StateError("%s должен быть JSON-объектом" % path)
    return data


def save(workdir, state):
    """Атомарно записать состояние."""
    if not isinstance(state, dict):
        raise StateError("состояние должно быть словарём")
    path = state_path(workdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=".state-", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, str(path))
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise

    # Зеркало: изменение состояния — событие в журнале `events`. Ошибка БД не
    # отменяет запись state.json: файл уже атомарно заменён строкой выше.
    storemod.save_event(
        workdir,
        None,
        "state",
        {
            "stage": state.get("stage"),
            "model_checksum": state.get("model_checksum"),
            "runs": len(state.get("runs") or []),
            "published": len(state.get("published") or []),
        },
    )
    return path


def set_stage(workdir, stage, reason=None, **kwargs):
    """Перевести состояние на новый этап и обновить переданные поля.

    `reason` — причина перехода. Единственный разрешённый откат этапа назад —
    `trained` после `enrich` (модель переобучена, страницу модели нужно
    перепубликовать), и он проходит только с `reason="enrich"`. Любой другой
    откат — `StateError`.
    """
    if reason not in (None, "enrich"):
        raise StateError(
            'неизвестная причина перехода %r; допустимо None или "enrich"' % (reason,)
        )
    if stage not in _STAGE_INDEX:
        raise StateError(
            "неизвестный этап %r; допустимы: %s" % (stage, ", ".join(STAGES))
        )
    unknown = sorted(set(kwargs) - set(_MUTABLE_FIELDS))
    if unknown:
        raise StateError(
            "set_stage не умеет менять поля: %s" % ", ".join(unknown)
        )

    state = load(workdir)
    current = state.get("stage")
    if current not in _STAGE_INDEX:
        raise StateError(
            "в состоянии неизвестный этап %r; допустимы: %s"
            % (current, ", ".join(STAGES))
        )
    if _STAGE_INDEX[stage] < _STAGE_INDEX[current]:
        # Единственный разрешённый возврат: после enrich модель переобучена,
        # страницу модели нужно перепубликовать — этап откатывается в trained.
        after_enrich = (
            stage == "trained" and current in ("checked", "estimated", "published")
        )
        if not (after_enrich and reason == "enrich"):
            if after_enrich:
                raise StateError(
                    'откат в trained разрешён только при reason="enrich" '
                    "(перепубликация страницы модели): %s → %s, reason=%r"
                    % (current, stage, reason)
                )
            raise StateError(
                "понижение этапа запрещено: %s → %s" % (current, stage)
            )

    state["stage"] = stage
    for key, value in kwargs.items():
        state[key] = value
    state["updated_at"] = now_utc()
    save(workdir, state)
    return state


def _normalize_run_dir(workdir, run_dir):
    """Путь прогона в state — всегда относительно корня проекта.

    `run_dir` в state — относительный путь от корня проекта, а НЕ от текущего
    каталога процесса: `trr` запускают и из корня, и из `scripts/`. Поэтому
    относительный путь приклеивается к `workdir`, а не разрешается от `cwd`:
    иначе запуск из подкаталога добавлял к пути префикс этого подкаталога, и
    путь склеивался сам с собой на каждом прогоне.

    Уже испорченная запись (мусорный префикс перед `.task-readiness/runs/`)
    схлопывается до хвоста — повторная запись не удлиняет путь.
    """
    if not isinstance(run_dir, str):
        return str(run_dir)
    root = Path(workdir).resolve()
    path = Path(run_dir)
    if not path.is_absolute():
        path = root / path
    try:
        relative = str(path.resolve().relative_to(root))
    except (TypeError, ValueError, OSError):
        return run_dir
    index = relative.find(RUNS_PREFIX)
    if index > 0:
        relative = relative[index:]
    return relative


def _run_identity(item):
    """Идентичность прогона для дедупа: (ключ задачи, имя каталога прогона).

    Имя каталога — `<RUN-ID>`; сравнение по нему не зависит от того, как записан
    путь (относительный, абсолютный, склеенный).
    """
    return (
        str(item.get("task_key") or ""),
        Path(str(item.get("run_dir") or "")).name,
    )


def add_run(workdir, task_key, run_dir, verdict, checked_at):
    """Добавить прогон в историю: дедуп по (task_key, run_id), порядок (task_key, run_dir)."""
    state = load(workdir)
    runs = []
    for item in state.get("runs") or []:
        if not isinstance(item, dict):
            continue
        item["run_dir"] = _normalize_run_dir(workdir, item.get("run_dir"))
        runs.append(item)
    entry = {
        "task_key": str(task_key),
        "run_dir": _normalize_run_dir(workdir, run_dir),
        "verdict": str(verdict),
        "checked_at": str(checked_at),
    }
    identity = _run_identity(entry)
    runs = [item for item in runs if _run_identity(item) != identity]
    runs.append(entry)
    runs.sort(key=lambda item: (str(item.get("task_key", "")), str(item.get("run_dir", ""))))
    state["runs"] = runs
    state["updated_at"] = now_utc()
    save(workdir, state)
    return entry


def add_publication(
    workdir,
    target,
    ref,
    url,
    content_sha256,
    mark_published=True,
    comment_id=None,
    marker=None,
):
    """Записать публикацию отчёта/страницы модели в `state.published[]`.

    Идемпотентный upsert по `(target, ref)`: повторная публикация в ту же цель
    обновляет существующую запись (новый `published_at`, `url`,
    `content_sha256`), а не добавляет вторую. Список сортируется по
    `(target, ref)` — детерминизм §8.

    `comment_id` и `marker` — для цели `jira`: id комментария в задаче и маркер
    идемпотентности в его теле. Оба необязательны; если при обновлении они не
    переданы, прежние значения сохраняются (id комментария терять нельзя —
    иначе повторная публикация создаст второй комментарий).

    `mark_published=True` (по умолчанию) — успешная публикация переводит этап
    в `published` (CONTRACT.md §5.10, §6.2). Ручной `state set stage published`
    не нужен. Публикация страницы модели на этапах `train`/`enrich` этап не
    двигает: там вызывают `mark_published=False` (иначе `check` не сможет
    выставить `checked`).
    """
    if target not in PUBLICATION_TARGETS:
        raise StateError(
            "неизвестная цель публикации %r; допустимы: %s"
            % (target, ", ".join(PUBLICATION_TARGETS))
        )
    state = load(workdir)
    entries = [
        item for item in state.get("published") or [] if isinstance(item, dict)
    ]
    previous = None
    for item in entries:
        if (item.get("target"), item.get("ref")) == (str(target), str(ref)):
            previous = item
            break
    if previous is None:
        previous = {}

    entry = {
        "target": str(target),
        "ref": str(ref),
        "url": str(url),
        "published_at": now_utc(),
        "content_sha256": str(content_sha256),
    }
    for key, value in (("comment_id", comment_id), ("marker", marker)):
        if value is not None:
            entry[key] = str(value)
        elif previous.get(key) is not None:
            entry[key] = previous[key]

    entries = [
        item
        for item in entries
        if (item.get("target"), item.get("ref"))
        != (entry["target"], entry["ref"])
    ]
    entries.append(entry)
    entries.sort(
        key=lambda item: (str(item.get("target", "")), str(item.get("ref", "")))
    )
    state["published"] = entries
    if mark_published:
        if state.get("stage") not in _STAGE_INDEX:
            raise StateError(
                "в состоянии неизвестный этап %r; допустимы: %s"
                % (state.get("stage"), ", ".join(STAGES))
            )
        # `published` — последний этап цепочки, поэтому понижения здесь нет;
        # проверка `_STAGE_INDEX` выше защищает от битого state.json.
        state["stage"] = "published"
    state["updated_at"] = now_utc()
    save(workdir, state)
    # Зеркало: та же публикация в таблицу `publications` (идемпотентно по
    # (target, ref)). state.json уже записан, ошибка БД ничего не откатывает.
    storemod.save_publication(
        workdir,
        None,  # конфиг прочитает хук зеркала (`store.open_for`)
        entry["target"],
        entry["ref"],
        entry["url"],
        entry["content_sha256"],
    )
    return entry


def drop_publication(workdir, target, ref):
    """Удалить запись `state.published[]` по `(target, ref)`.

    Нужно при апгрейде с версии 0.2.x: легаси-запись `ref=<KEY>` и новый вид
    (`ref=<KEY>#validation`/`#estimate`) могут описывать **один и тот же**
    комментарий, и тогда в state две записи делят `comment_id`. Возвращает
    `True`, если запись была и удалена.
    """
    state = load(workdir)
    entries = [
        item for item in state.get("published") or [] if isinstance(item, dict)
    ]
    kept = [
        item
        for item in entries
        if (item.get("target"), str(item.get("ref"))) != (str(target), str(ref))
    ]
    if len(kept) == len(entries):
        return False
    state["published"] = kept
    state["updated_at"] = now_utc()
    save(workdir, state)
    return True


def add_artifact(
    workdir,
    target,
    ref,
    url,
    artifact_sha256=None,
    manifest_checksum=None,
):
    """Записать публикацию обученного бандла в `state.artifacts[]`.

    Идемпотентный upsert по `(target, ref)`: повторная публикация того же бандла
    в ту же цель обновляет запись (`published_at`, `url`, `artifact_sha256`,
    `manifest_checksum`), а не добавляет вторую. Список сортируется по
    `(target, ref)` — детерминизм §8.

    `manifest_checksum` — `checksum` модели с префиксом `sha256:` на момент
    публикации. Именно по нему `doctor` отличает свежий бандл от бандла,
    собранного до последнего `train`: сравнение идёт с текущим
    `state.model_checksum`.

    Этап (`stage`) здесь не меняется: публикация бандла — это экспорт уже
    обученной модели, а не прохождение конвейера.
    """
    if target not in ARTIFACT_TARGETS:
        raise StateError(
            "неизвестная цель публикации бандла %r; допустимы: %s"
            % (target, ", ".join(ARTIFACT_TARGETS))
        )
    state = load(workdir)
    entries = [
        item for item in state.get("artifacts") or [] if isinstance(item, dict)
    ]
    entry = {
        "target": str(target),
        "ref": str(ref),
        "url": str(url),
        "published_at": now_utc(),
        "artifact_sha256": None if artifact_sha256 is None else str(artifact_sha256),
        "manifest_checksum": (
            None if manifest_checksum is None else str(manifest_checksum)
        ),
    }
    entries = [
        item
        for item in entries
        if (item.get("target"), item.get("ref"))
        != (entry["target"], entry["ref"])
    ]
    entries.append(entry)
    entries.sort(
        key=lambda item: (str(item.get("target", "")), str(item.get("ref", "")))
    )
    state["artifacts"] = entries
    state["updated_at"] = now_utc()
    save(workdir, state)
    return entry


def model_checksum(workdir):
    """sha256 канонического JSON модели без поля `checksum`."""
    path = model_path(workdir)
    if not path.is_file():
        raise StateError("модель не найдена: %s" % path)
    limits.check_size(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            model = json.load(handle)
    except OSError as exc:
        raise StateError("не удалось прочитать модель %s: %s" % (path, exc))
    except ValueError as exc:
        raise StateError("%s — невалидный JSON: %s" % (path, exc))
    if not isinstance(model, dict):
        raise StateError("%s должен быть JSON-объектом" % path)
    payload = {key: value for key, value in model.items() if key != "checksum"}
    return schema_lite.sha256_canonical(payload)

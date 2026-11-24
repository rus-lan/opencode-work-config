#!/usr/bin/env python3
"""Диагностика окружения и артефактов скилла (`trr doctor`).

Проверки идут в фиксированном порядке и печатают по строке на проверку:

    [OK] config: task-readiness-review.yaml
    [MISSING] .task-readiness/model/estimation-model.json — запустите /task-readiness-review train
    [BLOCKED] файл есть, но не соответствует схеме: .task-readiness/resolved-sources.json — схема resolved-sources: …
    [WARN] env JIRA_TOKEN не задана — MCP может работать без токена
    [BLOCKED] страница модели устарела (hash 0a2162f0… ≠ модель 1b3c9d42…) — запустите /task-readiness-review publish --model

`[MISSING]` — файла нет, `[BLOCKED]` — файл есть, но не годен либо гейт не
пройден. Оба ярлыка обязаны содержать, что сделать после `—`. Свежесть страницы
модели проверяется тем же условием, что и гейт `trr check`
(`state.model_page.hash` == checksum модели): иначе `doctor` зелёный при
заблокированном `check`.
Код выхода — по приоритету CONTRACT.md: 3 → 4 → 5 → 2, иначе 0.
"""

import json
import os
import sys
from pathlib import Path

from trr_impl import config as configmod
from trr_impl import limits
from trr_impl import schema_lite
from trr_impl import state as statemod
from trr_impl.paths import VECTORS_RELATIVE

__all__ = ["run"]

TOKEN_VARIABLES = ("JIRA_TOKEN", "CONFLUENCE_TOKEN", "GITLAB_TOKEN")
MIN_PYTHON = (3, 9)

# артефакт → (относительный путь, имя схемы, что сделать при отсутствии)
NORM_ARTIFACTS = (
    (
        "norm/reference-estimates.json",
        "reference-estimates",
        "запустите /task-readiness-review train (эталон не вычитан)",
    ),
    (
        "norm/sprint-sample.json",
        "sprint-sample",
        "запустите /task-readiness-review train (выборка спринтов не выгружена)",
    ),
    (
        "norm/sprint-stats.json",
        "sprint-stats",
        "запустите `scripts/trr stats`",
    ),
)

_LEVEL_LABEL = {
    "ok": "OK",
    "warn": "WARN",
    "missing": "MISSING",
    "blocked": "BLOCKED",
}


def _add(messages, level, what, fix=None, code=0):
    messages.append({"level": level, "what": what, "fix": fix, "code": code})


def _artifact_dir(workdir):
    return Path(workdir) / statemod.STATE_DIR


def _check_artifact(messages, path, schema_name, fix):
    """Файл есть → валиден по схеме. Возвращает True, если артефакт в порядке.

    Отсутствующий файл — `[MISSING]`. Файл, который есть, но не читается, не
    разбирается или не проходит схему, — `[BLOCKED] файл есть, но не
    соответствует схеме: <путь> — <что исправить>`: ярлык `[MISSING]` для
    существующего файла вводит в заблуждение.
    """
    display = _display_path(path)
    if not path.is_file():
        _add(messages, "missing", display, fix, code=4)
        return False
    limits.check_size(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        _add(
            messages,
            "blocked",
            "файл есть, но не читается: %s" % display,
            "%s; %s" % (exc, fix),
            code=5,
        )
        return False
    except ValueError as exc:
        _add(
            messages,
            "blocked",
            "файл есть, но не разбирается как JSON: %s" % display,
            "%s; %s" % (exc, fix),
            code=5,
        )
        return False
    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, schema_name)
    except schema_lite.SchemaError as exc:
        _add(
            messages,
            "blocked",
            "файл есть, но не проверен: %s" % display,
            "схема %s не читается: %s" % (schema_name, exc),
            code=5,
        )
        return False
    errors = schema_lite.validate(payload, schema)
    if errors:
        shown = "; ".join(errors[:3])
        if len(errors) > 3:
            shown += "; ещё %d" % (len(errors) - 3)
        _add(
            messages,
            "blocked",
            "файл есть, но не соответствует схеме: %s" % display,
            "схема %s: %s; %s" % (schema_name, shown, fix),
            code=5,
        )
        return False
    _add(messages, "ok", display)
    return True


def _display_path(path):
    """Путь для человека: относительный от cwd, если он внутри неё."""
    try:
        return str(Path(path).resolve().relative_to(Path.cwd().resolve()))
    except (ValueError, OSError):
        return str(path)


def _check_config(workdir, messages):
    """Проверка 1: конфиг есть и валиден. Возвращает конфиг или None.

    Проблемы места публикации обученного бандла (`artifacts.export_target` !=
    `none`, а место не заполнено) здесь только `[WARN]`, а не `[BLOCKED]`:
    `config-check` на них падает (конфиг непригоден для экспорта), но `doctor`
    обязан доходить до проверки самого экспорта (§5) и не терять остальную
    диагностику из-за незаполненного необязательного места.
    """
    path = configmod.config_path(workdir)
    example = Path(configmod.EXAMPLE_CONFIG)
    fix = (
        "скопировать из %s и заполнить sources.reference и sources.sprints" % example
    )
    if not path.is_file():
        _add(messages, "missing", configmod.CONFIG_FILENAME, fix, code=3)
        return None
    try:
        cfg = configmod.load_config(path)
    except configmod.ConfigError as exc:
        _add(
            messages,
            "blocked",
            "файл есть, но не соответствует схеме: %s" % configmod.CONFIG_FILENAME,
            "%s; %s" % (exc, fix),
            code=3,
        )
        return None
    errors = configmod.validate_config(cfg)
    place_problems = set(configmod.artifact_place_problems(cfg))
    blocking = [error for error in errors if error not in place_problems]
    if blocking:
        _add(
            messages,
            "blocked",
            "файл есть, но не соответствует схеме: %s" % configmod.CONFIG_FILENAME,
            "%s; %s" % ("; ".join(blocking), fix),
            code=3,
        )
        return None
    for problem in sorted(place_problems):
        _add(
            messages,
            "warn",
            problem,
            "заполните место публикации бандла или поставьте "
            "artifacts.export_target: none",
        )
    _add(messages, "ok", "config: %s" % configmod.CONFIG_FILENAME)
    return cfg


def _check_sources(workdir, messages):
    """Проверка 2: resolved-sources.json."""
    return _check_artifact(
        messages,
        _artifact_dir(workdir) / "resolved-sources.json",
        "resolved-sources",
        "запустите /task-readiness-review init (источники не разрешены)",
    )


def _check_config_values(cfg, messages):
    """Проверка конфига на заполненность: проект Jira и демо-значения.

    `jira.project` командного дефолта не имеет: пустое значение — `[BLOCKED]`,
    потому что без проекта `check`/`train` не смогут прочитать задачу. Демо-
    значения из примера (`E001`, page_id/board_id/имена спринтов) — `[WARN]`:
    конфиг формально валиден, но отчёт будет про чужой проект.
    """
    jira = cfg.get("jira") if isinstance(cfg.get("jira"), dict) else {}
    project = str(jira.get("project") or "").strip()
    if not project:
        _add(
            messages,
            "blocked",
            "jira.project не заполнен",
            "укажите ключ проекта Jira в %s (например ABC) и повторите"
            % configmod.CONFIG_FILENAME,
            code=2,
        )
    else:
        _add(messages, "ok", "jira.project: %s" % project)

    fields = jira.get("fields") if isinstance(jira.get("fields"), dict) else {}
    empty = [
        key
        for key in ("story_points", "qa_estimation", "role")
        if not str(fields.get(key) or "").strip()
    ]
    if empty and jira.get("resolve_fields_by_name") is not False:
        names = jira.get("field_names") if isinstance(jira.get("field_names"), dict) else {}
        _add(
            messages,
            "ok",
            "jira.fields: id резолвятся по именам (%s)"
            % ", ".join(
                str(names.get(key) or key) for key in empty
            ),
        )

    for warning in configmod.demo_warnings(cfg):
        _add(
            messages,
            "warn",
            warning[len("[WARN] ") :] if warning.startswith("[WARN] ") else warning,
            "замените демо-значения на данные своего проекта",
        )


def _check_norm(workdir, messages):
    """Проверка 3: нормализованные артефакты эталона и спринтов."""
    base = _artifact_dir(workdir)
    results = []
    for relative, schema_name, fix in NORM_ARTIFACTS:
        results.append(_check_artifact(messages, base / relative, schema_name, fix))
    return all(results)


def _check_vectors(workdir, cfg, messages):
    """Векторы включены, а артефакта нет — незавершённый `train`, не блок.

    `estimation.vector.enabled` по умолчанию `true`, поэтому отсутствие
    `norm/task-vectors.json` — сигнал, что `train` не доделан, а не норма.
    Ярлык `[WARN]`, а не `[BLOCKED]`: оценка считается без соседей и числа не
    меняются. Существующий артефакт проверяется по схеме (`[BLOCKED]`, если бит).
    """
    vector = ((cfg.get("estimation") or {}).get("vector")) or {}
    if not isinstance(vector, dict) or not vector.get("enabled"):
        return
    path = _artifact_dir(workdir) / VECTORS_RELATIVE
    if path.is_file():
        _check_artifact(
            messages,
            path,
            "task-vectors",
            "пересоберите: `scripts/trr vectors build`",
        )
        return
    _add(
        messages,
        "warn",
        _display_path(path),
        "векторы включены, артефакта нет — незавершённый train: "
        "`scripts/trr vectors build` (тексты — norm/task-texts.json)",
    )


def _check_model(workdir, messages):
    """Проверка 4: модель валидна по схеме и рядом есть её .md."""
    base = _artifact_dir(workdir)
    model_json = base / "model" / "estimation-model.json"
    ok = _check_artifact(
        messages,
        model_json,
        "estimation-model",
        "запустите /task-readiness-review train",
    )
    model_md = base / "model" / "estimation-model.md"
    if not model_md.is_file():
        _add(
            messages,
            "missing",
            _display_path(model_md),
            "запустите /task-readiness-review train (описание модели не отрендерено)",
            code=4,
        )
        ok = False
    else:
        _add(messages, "ok", _display_path(model_md))
    return ok


def _check_model_page_freshness(workdir, model_page, messages):
    """Свежесть страницы модели: `model_page.hash` == checksum текущей модели.

    `trr check` блокируется при расхождении (CONTRACT.md §5.4.1), поэтому
    `doctor` обязан проверять то же условие: иначе диагностика зелёная, а
    проверка красная, и причина ищется не там.

    Нет `hash` (запись до появления гейта) — `[WARN]`: обратная совместимость
    важнее строгости, `check` в этом случае тоже только предупреждает.
    """
    page_hash = ""
    version = None
    if isinstance(model_page, dict):
        page_hash = str(model_page.get("hash") or "").strip()
        version = model_page.get("version")
    if not page_hash:
        _add(
            messages,
            "warn",
            "у state.model_page нет hash — свежесть не проверена",
            "перепубликуйте страницу: /task-readiness-review publish --model",
        )
        return True
    try:
        current_hash = statemod.model_checksum(workdir)
    except statemod.StateError as exc:
        _add(
            messages,
            "blocked",
            "модель не читается — свежесть страницы модели не проверить",
            "%s; запустите /task-readiness-review train" % exc,
            code=5,
        )
        return False
    if page_hash != current_hash:
        _add(
            messages,
            "blocked",
            "страница модели устарела (hash %s… ≠ модель %s…)"
            % (page_hash[:8], current_hash[:8]),
            "запустите /task-readiness-review publish --model",
            code=2,
        )
        return False
    suffix = "" if version is None else " (v%s)" % version
    _add(messages, "ok", "state: страница модели соответствует модели%s" % suffix)
    return True


def _check_model_version(payload, messages):
    """Версия действующей модели в `state.model.version`.

    Пишет её `trr calibrate` (`train`/`enrich`) и `trr state set model.version`.
    Состояние без неё рабочее (все числа берутся из артефакта модели), поэтому
    это `[WARN]`, а не `[BLOCKED]`: молчать нельзя — иначе отсутствие версии
    выглядит как «всё в порядке».
    """
    model = payload.get("model")
    version = model.get("version") if isinstance(model, dict) else None
    if version is None:
        _add(
            messages,
            "warn",
            "state: версия модели не зафиксирована (model.version)",
            "запустите /task-readiness-review train "
            "(или `trr state set model.version <N>`)",
        )
        return False
    _add(messages, "ok", "state: версия модели v%s зафиксирована (model.version)" % version)
    return True


def _check_state(workdir, messages):
    """Проверка 5: state.json читается, страница модели опубликована и свежа."""
    path = statemod.state_path(workdir)
    try:
        payload = statemod.load(workdir)
    except statemod.StateError as exc:
        _add(
            messages,
            "missing",
            _display_path(path),
            "%s; запустите /task-readiness-review init" % exc,
            code=4,
        )
        return False
    _add(messages, "ok", "state: stage=%s" % payload.get("stage"))
    _check_model_version(payload, messages)
    model_page = payload.get("model_page")
    if not model_page:
        _add(
            messages,
            "blocked",
            "страница модели не опубликована",
            "запустить /task-readiness-review train (и опубликовать страницу модели)",
            code=2,
        )
        return False
    _add(messages, "ok", "model_page: опубликована")
    return _check_model_page_freshness(workdir, model_page, messages)


def _check_artifact_export(workdir, cfg, messages):
    """Проверка 8: обученный бандл опубликован для команды и не старше модели.

    Проверяется только при `artifacts.export_target != none`: дефолт «не
    публиковать» — законный режим, и тогда требовать экспорт нельзя. Свежесть —
    по `state.artifacts[].manifest_checksum`: он должен совпасть с текущим
    `state.model_checksum`. Иначе бандл собран до последнего `train`/`enrich`, и
    команда импортирует устаревшую модель — это `[WARN]`, а не `[BLOCKED]`:
    экспорт не входит в гейт `check`.
    """
    artifacts = cfg.get("artifacts") if isinstance(cfg.get("artifacts"), dict) else {}
    target = str(artifacts.get("export_target") or "none")
    if target == "none":
        return
    problem = configmod.artifact_place_problem(cfg, target)
    if problem:
        _add(
            messages,
            "warn",
            "место публикации бандла не задано (%s)" % target,
            "%s; заполните место или поставьте artifacts.export_target: none"
            % problem,
        )
        return
    try:
        current = "sha256:%s" % statemod.model_checksum(workdir)
    except statemod.StateError as exc:
        _add(
            messages,
            "warn",
            "свежесть бандла не проверена — модель не читается",
            "%s; запустите /task-readiness-review train" % exc,
        )
        return
    try:
        state = statemod.load(workdir)
    except statemod.StateError as exc:
        _add(
            messages,
            "warn",
            "свежесть бандла не проверена — %s" % exc,
            "запустите /task-readiness-review init",
        )
        return
    entries = [item for item in state.get("artifacts") or [] if isinstance(item, dict)]
    fresh = [item for item in entries if item.get("manifest_checksum") == current]
    if fresh:
        _add(
            messages,
            "ok",
            "артефакт обучения опубликован (%s: %s)"
            % (target, ", ".join(str(item.get("ref")) for item in fresh)),
        )
        return
    _add(
        messages,
        "warn",
        "артефакт обучения не опубликован для команды",
        "запустите /task-readiness-review train (export)",
    )


def _check_env(messages):
    """Проверка 6: токены только из окружения; их отсутствие — не приговор."""
    for name in TOKEN_VARIABLES:
        if (os.environ.get(name) or "").strip():
            _add(messages, "ok", "env %s задана" % name)
        else:
            _add(
                messages,
                "warn",
                "env %s не задана" % name,
                "MCP может работать без токена; задайте переменную, если нужен REST fallback",
            )


def _check_python(messages):
    """Проверка 7: версия Python."""
    current = "%d.%d.%d" % sys.version_info[:3]
    if sys.version_info[:2] >= MIN_PYTHON:
        _add(messages, "ok", "python %s" % current)
        return True
    _add(
        messages,
        "missing",
        "python %s" % current,
        "нужен Python %d.%d или новее" % MIN_PYTHON,
        code=2,
    )
    return False


def _exit_code(messages):
    codes = {
        message["code"]
        for message in messages
        if message["level"] in ("missing", "blocked") and message["code"]
    }
    for candidate in (3, 4, 5, 2):
        if candidate in codes:
            return candidate
    return 0


def _print_messages(messages):
    for message in messages:
        label = _LEVEL_LABEL[message["level"]]
        text = "[%s] %s" % (label, message["what"])
        if message["fix"]:
            text += " — %s" % message["fix"]
        print(text)


def run(workdir, args=None):
    """Выполнить диагностику. Возвращает код выхода."""
    json_mode = bool(getattr(args, "json", False))
    quiet = bool(getattr(args, "quiet", False))

    messages = []
    cfg = _check_config(workdir, messages)
    if cfg is None:
        # Дальше идти бессмысленно: без конфига остальные артефакты не проверить.
        code = _exit_code(messages)
        if json_mode:
            _emit_json(messages, code)
        elif not quiet:
            _print_messages(messages)
        return code

    _check_sources(workdir, messages)
    _check_config_values(cfg, messages)
    _check_norm(workdir, messages)
    _check_vectors(workdir, cfg, messages)
    _check_model(workdir, messages)
    _check_state(workdir, messages)
    _check_artifact_export(workdir, cfg, messages)
    _check_env(messages)
    _check_python(messages)

    code = _exit_code(messages)
    if json_mode:
        _emit_json(messages, code)
    elif not quiet:
        _print_messages(messages)
    return code


def _emit_json(messages, code):
    payload = {
        "status": "ok" if code == 0 else "blocked",
        "code": code,
        "messages": [
            {
                "level": message["level"],
                "what": message["what"],
                "fix": message["fix"] or "",
            }
            for message in messages
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))

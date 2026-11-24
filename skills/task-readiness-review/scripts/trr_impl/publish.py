#!/usr/bin/env python3
"""Комментарии в задачу Jira: сборка тел, план публикации, запись id в state.

Модуль намеренно не знает про сеть и MCP: Python в Jira не пишет. Он готовит
ровно то, что нужно агенту, и фиксирует результат, когда агент опубликовал
комментарий.

Комментариев в задаче **три вида**, и это три разных комментария с тремя
маркерами и тремя `ref` в `state.published[]`:

* ``validation`` — «Результаты валидации» (готовность: вердикт, пробелы,
  гигиена полей, как перегенерировать), маркер
  ``<!-- task-readiness-review:validation:<KEY> -->``, ref ``<KEY>#validation``;
* ``estimate`` — «Результаты оценки» (SP, диапазон, таблица ролей, основания,
  похожие задачи), маркер ``<!-- task-readiness-review:estimate:<KEY> -->``,
  ref ``<KEY>#estimate``;
* ``questions`` — вопросы из ``check`` (маркер ``:questions:``, ref
  ``<KEY>#questions``) — поведение не изменилось.

Роли модуля:

1. ``build_comment`` — тело комментария: маркер идемпотентности в первой
   строке, HTML-комментарии вырезаны, длина ограничена лимитом Jira;
2. ``plan``/``plan_one`` — что делать: ``create`` или ``update`` (по
   ``comment_id`` из ``state.published[]``), куда положить тело, какой у него
   sha256;
3. ``record`` — идемпотентный upsert в ``state.published[]`` после того, как
   агент создал/обновил комментарий и знает его ``id``;
4. ``write_action_package`` — пакет ``actions/jira-<kind>.md`` на случай
   недоступности Jira: готовый текст и точный список шагов.

Идемпотентность держится на двух вещах: маркер в начале тела и ``comment_id`` в
state. Есть id — обновляем тот же комментарий; нет id — агент ищет комментарий
по маркеру, а не создаёт второй.
"""

import hashlib
import os
import re
from pathlib import Path

from trr_impl import report as reportmod
from trr_impl import state as statemod

__all__ = [
    "BODY_NAME",
    "COMMENT_KINDS",
    "JIRA_TARGET",
    "KIND_ESTIMATE",
    "KIND_QUESTIONS",
    "KIND_VALIDATION",
    "LEGACY_KIND",
    "MAX_COMMENT_CHARS",
    "MissingReport",
    "build_comment",
    "body_name",
    "comment_ref",
    "default_comment_url",
    "find_report",
    "marker_for",
    "plan",
    "plan_one",
    "plan_questions",
    "questions_ref",
    "record",
    "record_questions",
    "write_action_package",
]

# Цель публикации в `state.published[]` для комментария в задачу.
JIRA_TARGET = "jira"

# Лимит тела комментария Jira. Больше — Jira отвечает 400, поэтому тело режется
# по границе абзаца, а в хвост уходит ссылка на полный отчёт. Формат двух
# комментариев (валидация ≤ ~40 строк, оценка ≤ ~25) в лимит укладывается с
# запасом: обрезка здесь — аварийный тормоз, а не штатный путь.
MAX_COMMENT_CHARS = 32767

# Виды комментариев. Порядок — порядок публикации: сначала готовность
# (валидация), потом оценка. Агент идёт по нему же.
KIND_VALIDATION = "validation"
KIND_ESTIMATE = "estimate"
KIND_QUESTIONS = "questions"
COMMENT_KINDS = (KIND_VALIDATION, KIND_ESTIMATE)

# Маркеры идемпотентности: первая строка тела, по ней агент находит свой
# комментарий, если `comment_id` в state потерян.
_MARKERS = {
    KIND_VALIDATION: "<!-- task-readiness-review:validation:%s -->",
    KIND_ESTIMATE: "<!-- task-readiness-review:estimate:%s -->",
    KIND_QUESTIONS: "<!-- task-readiness-review:questions:%s -->",
    # Старый маркер версии 0.2.x (один комментарий «отчёт»). Оставлен, чтобы
    # повторная публикация нашла комментарий, созданный прежней версией, и
    # обновила его вместо создания второго.
    "report": "<!-- task-readiness-review:report:%s -->",
}

# `ref` записи в `state.published[]`: у каждого комментария свой, иначе upsert
# по (target, ref) затёр бы id соседнего комментария.
_REFS = {
    KIND_VALIDATION: "%s#validation",
    KIND_ESTIMATE: "%s#estimate",
    KIND_QUESTIONS: "%s#questions",
    "report": "%s",
}

# Файл тела комментария рядом с отчётом (каталог прогона).
_BODY_NAMES = {
    KIND_VALIDATION: "jira-validation.md",
    KIND_ESTIMATE: "jira-estimate.md",
    KIND_QUESTIONS: "jira-questions.md",
    "report": "jira-comment.md",
}

# Историческое имя: тело единственного комментария версии 0.2.x.
BODY_NAME = "jira-comment.md"

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

# Легаси-вид версии 0.2.x: единственный комментарий «отчёт». Его `ref` — просто
# `<KEY>`; при апгрейде оценка сначала ищет свою запись, потом легаси-запись,
# чтобы обновить старый комментарий, а не создать второй.
LEGACY_KIND = "report"


class MissingReport(Exception):
    """Нет исходного текста для комментария (`report.md` / `comment-draft.md`)."""


# ---------------------------------------------------------------------------
# Маркеры и тело
# ---------------------------------------------------------------------------


def marker_for(task_key, kind=KIND_ESTIMATE):
    """Маркер идемпотентности в первой строке тела комментария."""
    template = _MARKERS.get(kind)
    if template is None:
        raise ValueError(
            "неизвестный вид комментария %r; допустимы: %s"
            % (kind, ", ".join(sorted(_MARKERS)))
        )
    return template % str(task_key)


def comment_ref(task_key, kind=KIND_ESTIMATE):
    """`ref` записи `state.published[]` для комментария вида `kind`."""
    template = _REFS.get(kind)
    if template is None:
        raise ValueError(
            "неизвестный вид комментария %r; допустимы: %s"
            % (kind, ", ".join(sorted(_REFS)))
        )
    return template % str(task_key)


def body_name(kind=KIND_ESTIMATE):
    """Имя файла тела комментария в каталоге прогона."""
    return _BODY_NAMES.get(kind, BODY_NAME)


def questions_ref(task_key):
    """`ref` записи state для комментария с вопросами."""
    return comment_ref(task_key, KIND_QUESTIONS)


def _strip_html_comments(text):
    """Убрать HTML-комментарии и лишние пустые строки.

    В отчёте HTML-комментарии — служебные пометки шаблона; в теле комментария
    Jira они не нужны и только мешают читать текст.
    """
    without = _HTML_COMMENT_RE.sub("", text or "")
    lines = [line.rstrip() for line in without.splitlines()]
    collapsed = []
    blank = 0
    for line in lines:
        if line:
            blank = 0
            collapsed.append(line)
            continue
        blank += 1
        if blank <= 1:
            collapsed.append("")
    return "\n".join(collapsed).strip("\n")


def _cut_at_paragraph(text, budget):
    """Обрезать текст по границе абзаца (или строки), уложившись в `budget`."""
    if len(text) <= budget:
        return text
    window = text[:budget]
    for separator in ("\n\n", "\n"):
        index = window.rfind(separator)
        if index > 0:
            return window[:index].rstrip()
    return window.rstrip()


def build_comment(
    report_text,
    task_key,
    max_len=MAX_COMMENT_CHARS,
    report_path="report.md",
    kind=KIND_ESTIMATE,
):
    """Собрать тело комментария: маркер, текст отчёта, обрезка по лимиту.

    Маркер всегда стоит первым — по нему агент находит комментарий, если
    `comment_id` в state нет. Превышение `max_len` режется по границе абзаца,
    в хвост дописывается `… (полный отчёт: <путь>)`: обрезанный комментарий
    остаётся читаемым и указывает, где взять полный текст.
    """
    if not isinstance(max_len, int) or isinstance(max_len, bool) or max_len <= 0:
        raise ValueError("max_len должен быть положительным целым")
    marker = marker_for(task_key, kind)
    body = _strip_html_comments(report_text)
    head = marker + "\n\n"
    if not body:
        return marker

    full = head + body
    if len(full) <= max_len:
        return full

    suffix = "\n\n… (полный отчёт: %s)" % report_path
    budget = max_len - len(head) - len(suffix)
    if budget <= 0:
        # Даже маркер с хвостом не влезает: режем по жёсткому лимиту.
        return (head + suffix)[:max_len]
    return head + _cut_at_paragraph(body, budget) + suffix


# ---------------------------------------------------------------------------
# Каталоги прогона
# ---------------------------------------------------------------------------


def runs_root(workdir, task_key):
    return Path(workdir) / statemod.STATE_DIR / "runs" / str(task_key)


def _latest_run_dir(workdir, task_key, filename):
    """Каталог последнего прогона задачи, в котором есть `filename`."""
    base = runs_root(workdir, task_key)
    if not base.is_dir():
        return None
    for run_dir in sorted(
        (path for path in base.iterdir() if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    ):
        if (run_dir / filename).is_file():
            return run_dir
    return None


def _run_dir(workdir, task_key, filename, run=None):
    """Каталог прогона: явный `run` (`--run`), иначе последний с `filename`.

    `--run` обязан побеждать «лексикографически последний каталог». RUN-ID —
    UTC-метка, но порядок каталогов не гарантирует монотонность: ручной прогон
    `2026-11-18T14-37-46Z` может сортироваться раньше существующего
    `2026-11-18T18-00-00Z` и запись уехала бы в чужой прогон. Явный прогон,
    которого нет на диске, — `None` (вызывающая сторона решает, это `MISSING`).
    """
    if run:
        candidate = runs_root(workdir, task_key) / str(run)
        return candidate if candidate.is_dir() else None
    return _latest_run_dir(workdir, task_key, filename)


def find_report(workdir, task_key, run=None):
    """`report.md` прогона `run` (по умолчанию последнего) или None."""
    run_dir = _run_dir(workdir, task_key, "report.md", run)
    return None if run_dir is None else run_dir / "report.md"


def _relative(workdir, path):
    try:
        return str(Path(path).resolve().relative_to(Path(workdir).resolve()))
    except (ValueError, OSError):
        return str(path)


def default_comment_url(task_key, comment_id):
    """Ссылка на комментарий: из `JIRA_URL`, иначе стабильный плейсхолдер."""
    base = (os.environ.get("JIRA_URL") or "").strip().rstrip("/")
    if base:
        return "%s/browse/%s?focusedCommentId=%s" % (base, task_key, comment_id)
    return "jira://%s/comment/%s" % (task_key, comment_id)


# ---------------------------------------------------------------------------
# План
# ---------------------------------------------------------------------------


def _existing_entry(state, target, ref):
    for entry in state.get("published") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("target") == target and str(entry.get("ref")) == str(ref):
            return entry
    return None


def _existing_for_kind(state, target, task_key, kind):
    """Запись state для вида комментария, с фолбэком на легаси-`ref` оценки.

    Версия 0.2.x писала один комментарий с `ref = <KEY>`. Чтобы апгрейд не
    создавал второй комментарий «оценка» рядом со старым «отчёт», оценка
    смотрит и легаси-запись.
    """
    entry = _existing_entry(state, target, comment_ref(task_key, kind))
    if entry is not None:
        return entry
    if kind == KIND_ESTIMATE:
        return _existing_entry(state, target, comment_ref(task_key, LEGACY_KIND))
    return None


def _comment_id_of(entry):
    if not isinstance(entry, dict):
        return None
    value = entry.get("comment_id")
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _plan_for(workdir, task_key, kind, source_path, body):
    """Общая часть `plan_one`/`plan_questions`: action + id из state.published[]."""
    ref = comment_ref(task_key, kind)
    try:
        state = statemod.load(workdir)
    except statemod.StateError:
        # Нет state — публикации ещё не было: это create, а не ошибка.
        state = {}
    existing = _existing_for_kind(state, JIRA_TARGET, task_key, kind)
    comment_id = _comment_id_of(existing)
    return {
        "task_key": str(task_key),
        "kind": kind,
        "action": "update" if comment_id else "create",
        "comment_id": comment_id,
        "ref": ref,
        "marker": marker_for(task_key, kind),
        "body": body,
        "body_path": _relative(workdir, source_path) if source_path else None,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "chars": len(body),
        "url": (existing or {}).get("url"),
    }


def _artifact_for(kind):
    """Артефакт прогона, из которого рендерится тело комментария."""
    if kind == KIND_VALIDATION:
        return "validation.json"
    if kind == KIND_QUESTIONS:
        return "comment-draft.md"
    return "estimate.json"


def _render_body(workdir, task_key, kind, run_dir):
    """Тело комментария вида `kind` из артефактов прогона (без маркера)."""
    if kind == KIND_VALIDATION:
        return reportmod.render_validation_comment(run_dir)
    return reportmod.render_estimate_comment(run_dir)


def plan_one(workdir, task_key, kind, write_body=True, run=None):
    """План публикации одного комментария вида `kind`.

    Возвращает `{kind, action, comment_id, marker, ref, body_path, body_sha256,
    chars, …}`. `action` — `update`, если в `state.published[]` уже есть запись
    `target="jira"` с этим `ref` и `comment_id`, иначе `create`. Тело пишется
    рядом с артефактами прогона (`jira-validation.md` / `jira-estimate.md`) —
    агенту не нужно собирать его заново перед публикацией.
    `write_body=False` — режимы «только напечатать» (`--plan-jira`, `--draft`):
    на диск ничего не кладётся.
    `run` — явный `<RUN-ID>` (`--run`): тело берётся из указанного прогона, а не
    из последнего на диске.

    Нет артефакта прогона — `MissingReport`: вызывающая сторона отвечает кодом 4.
    """
    workdir = Path(workdir)
    artifact = _artifact_for(kind)
    run_dir = _run_dir(workdir, task_key, artifact, run)
    if run_dir is None:
        raise MissingReport(
            "%s — нет %s у задачи %s: сначала /task-readiness-review %s --task %s"
            % (
                _relative(workdir, runs_root(workdir, task_key) / str(run))
                if run
                else _relative(workdir, runs_root(workdir, task_key)),
                artifact,
                task_key,
                "check" if kind == KIND_VALIDATION else "estimate",
                task_key,
            )
        )
    artifact_path = _relative(workdir, run_dir / artifact)
    try:
        text = _render_body(workdir, task_key, kind, run_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise MissingReport("%s — %s" % (artifact_path, exc))

    # Хвост обрезки указывает на человекочитаемый полный текст: `report.md`,
    # если он есть в прогоне, иначе на сам артефакт. `estimate.json` —
    # машинный артефакт, называть его «полным отчётом» нельзя.
    report_tail = run_dir / "report.md"
    report_path = (
        _relative(workdir, report_tail) if report_tail.is_file() else artifact_path
    )
    body = build_comment(
        text, task_key, report_path=report_path, kind=kind
    )
    name = body_name(kind)
    body_path = run_dir / name
    if write_body:
        try:
            # Атомарная запись (`reportmod.write`): tmp рядом + `os.replace`.
            # Иначе прерванный `publish` оставляет полфайла, и агент публикует
            # обрезанный комментарий.
            reportmod.write(run_dir, body, name)
        except OSError as exc:
            raise MissingReport("%s — %s" % (_relative(workdir, body_path), exc))

    info = _plan_for(workdir, task_key, kind, body_path if write_body else None, body)
    info["artifact_path"] = artifact_path
    return info


def plan(workdir, task_key, write_body=True, kinds=COMMENT_KINDS, run=None):
    """План публикации всех комментариев задачи: список по видам.

    По умолчанию — оба комментария в порядке публикации: сначала валидация
    (готовность), затем оценка. `kinds` позволяет ограничить набор (например,
    только `(KIND_ESTIMATE,)`). `run` — явный прогон (`--run`).
    """
    return [
        plan_one(workdir, task_key, kind, write_body=write_body, run=run)
        for kind in kinds
    ]


def plan_questions(workdir, task_key, draft_text, draft_path=None):
    """План комментария с вопросами (`check`, `comment_mode: post`).

    Тело — `comment-draft.md` прогона с маркером вопросов. Отдельный `ref`
    (`<KEY>#questions`) держит свой `comment_id`, чтобы публикация отчёта и
    публикация вопросов не затирали друг друга.
    """
    workdir = Path(workdir)
    body = build_comment(
        draft_text,
        task_key,
        report_path=draft_path or "comment-draft.md",
        kind="questions",
    )
    info = _plan_for(workdir, task_key, "questions", None, body)
    info["draft_path"] = draft_path
    return info


# ---------------------------------------------------------------------------
# Запись результата
# ---------------------------------------------------------------------------


def record(workdir, task_key, comment_id, url=None, kind=KIND_ESTIMATE, run=None):
    """Зафиксировать опубликованный комментарий вида `kind` в `state.published[]`.

    Вызывается после того, как агент создал (POST) или обновил (PUT)
    комментарий и знает его `id`. Повторный вызов с тем же id — идемпотентный
    upsert: запись одна, меняются `published_at`/`content_sha256`.

    `run` — явный `<RUN-ID>`: `content_sha256` считается по телу того прогона,
    которое агент и опубликовал (иначе id от одного прогона связывался бы с
    sha256 тела другого).
    """
    if comment_id is None or str(comment_id).strip() == "":
        raise ValueError("comment_id не может быть пустым")
    comment_id = str(comment_id).strip()
    info = plan_one(workdir, task_key, kind, run=run)
    target_url = str(url).strip() if url and str(url).strip() else default_comment_url(
        task_key, comment_id
    )
    entry = statemod.add_publication(
        str(workdir),
        JIRA_TARGET,
        info["ref"],
        target_url,
        info["body_sha256"],
        comment_id=comment_id,
        marker=info["marker"],
    )
    _drop_legacy_publication(workdir, task_key, comment_id, kind)
    return entry


def _drop_legacy_publication(workdir, task_key, comment_id, kind):
    """Убрать легаси-запись `ref=<KEY>`, делящую `comment_id` с новым видом.

    Версия 0.2.x писала один комментарий «отчёт» с `ref=<KEY>`. Если новый вид
    фиксируется на **том же** комментарии (агент обновил старый по маркеру),
    две записи `state.published[]` описывали бы один `comment_id`: следующая
    публикация считала бы по одной из них, а вторая оставалась бы мусором.
    Запись с другим `comment_id` — это другой комментарий в задаче, её не
    трогаем. Возвращает `True`, если легаси-запись удалена.
    """
    if kind == LEGACY_KIND:
        return False
    legacy_ref = comment_ref(task_key, LEGACY_KIND)
    try:
        state = statemod.load(workdir)
    except statemod.StateError:
        return False
    for item in state.get("published") or []:
        if not isinstance(item, dict):
            continue
        if (item.get("target"), str(item.get("ref"))) != (JIRA_TARGET, legacy_ref):
            continue
        if _comment_id_of(item) != str(comment_id):
            continue
        return statemod.drop_publication(workdir, JIRA_TARGET, legacy_ref)
    return False


def record_questions(workdir, task_key, comment_id, url=None, run=None):
    """Зафиксировать комментарий с вопросами (отдельный `ref` и `comment_id`).

    `run` — явный `<RUN-ID>`: тело считается по `comment-draft.md` указанного
    прогона, а не последнего на диске.
    """
    if comment_id is None or str(comment_id).strip() == "":
        raise ValueError("comment_id не может быть пустым")
    comment_id = str(comment_id).strip()
    workdir = Path(workdir)
    run_dir = _run_dir(workdir, task_key, "comment-draft.md", run)
    if run_dir is None:
        raise MissingReport(
            "%s — нет comment-draft.md у задачи %s: сначала /task-readiness-review check %s"
            % (_relative(workdir, runs_root(workdir, task_key)), task_key, task_key)
        )
    draft = run_dir / "comment-draft.md"
    draft_path = _relative(workdir, draft)
    try:
        text = draft.read_text(encoding="utf-8")
    except OSError as exc:
        raise MissingReport("%s — %s" % (draft_path, exc))
    info = plan_questions(workdir, task_key, text, draft_path)
    target_url = str(url).strip() if url and str(url).strip() else default_comment_url(
        task_key, comment_id
    )
    return statemod.add_publication(
        str(workdir),
        JIRA_TARGET,
        info["ref"],
        target_url,
        info["body_sha256"],
        # Комментарий с вопросами — не публикация отчёта: этап не двигается
        # (иначе `check` сразу прыгал бы в `published`).
        mark_published=False,
        comment_id=comment_id,
        marker=info["marker"],
    )


# ---------------------------------------------------------------------------
# Пакет для ручной публикации
# ---------------------------------------------------------------------------


def write_action_package(
    workdir, task_key, body, reason, kind=KIND_ESTIMATE, run=None, run_dir=None
):
    """Положить `actions/jira-<kind>.md` с готовым текстом и шагами.

    Нужен, когда Jira недоступна (MCP и REST): работа не падает, но человек
    должен увидеть, что именно опубликовать и как зафиксировать id. Файл
    кладётся в каталог прогона, к которому относится тело: `run_dir` (явный
    каталог), `run` (`--run`) или — если прогон не задан — последний прогон
    задачи. Прогонов нет вовсе — `.task-readiness/actions/`.

    `run`/`run_dir` важны: `--run` не должен уезжать в чужой прогон только
    потому, что его RUN-ID сортируется раньше (см. `_run_dir`).
    """
    workdir = Path(workdir)
    artifact = _artifact_for(kind)
    if run_dir is not None:
        resolved = Path(run_dir)
    else:
        resolved = _run_dir(workdir, task_key, artifact, run)
        if resolved is None and run:
            raise MissingReport(
                "%s — нет прогона %s у задачи %s"
                % (_relative(workdir, runs_root(workdir, task_key) / str(run)), run, task_key)
            )
    base = resolved if resolved is not None else Path(workdir) / statemod.STATE_DIR
    name = body_name(kind).replace("jira-", "", 1)
    path = base / "actions" / ("jira-%s" % name)
    flag = {
        KIND_VALIDATION: "--comment-id-validation",
        KIND_ESTIMATE: "--comment-id-estimate",
        KIND_QUESTIONS: "--comment-id",
    }.get(kind, "--comment-id-estimate")
    title = {
        KIND_VALIDATION: "Результаты валидации",
        KIND_ESTIMATE: "Результаты оценки",
        KIND_QUESTIONS: "Вопросы по задаче",
    }.get(kind, "Результаты оценки")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        marker = marker_for(task_key, kind)
        lines = [
            "# Комментарий «%s» в задачу %s: опубликовать вручную" % (title, task_key),
            "",
            "Причина: %s" % reason,
            "",
            "## Что сделать",
            "",
            "1. Найти в задаче %s комментарий, первая строка которого — `%s`."
            % (task_key, marker),
            "2. Комментарий есть — обновить его тело текстом ниже (PUT по его id).",
            "   Комментария нет — создать новый (POST).",
            "3. Зафиксировать id в состоянии:",
            "",
            "   `trr publish --task %s %s <id>`" % (task_key, flag),
            "",
            "## Текст комментария",
            "",
            body,
            "",
        ]
        # Атомарная запись: прерванный `--no-jira` не оставит половину
        # инструкции, по которой человек публикует комментарий вручную.
        reportmod.write(path.parent, "\n".join(lines), path.name)
    except OSError as exc:
        raise MissingReport("%s — %s" % (_relative(workdir, path), exc))
    return path

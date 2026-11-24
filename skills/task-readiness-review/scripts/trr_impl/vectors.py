#!/usr/bin/env python3
"""Векторизация текстов задач: гибрид word TF-IDF + char 3–5-граммы.

Зачем: бакет `(role, work_kind)` не различает объём внутри вида работ —
«исследовать терминологию в UI» (2 SP) и «исследовать внедрение поля из
внешней ИС» (8 SP) попадают в один бакет `BE/research`. Векторы добавляют
второй, более узкий взгляд: какие конкретные закрытые задачи похожи по тексту
и сколько они стоили.

Что считается (ресерч `VECTORIZATION.md`):

* документ = `summary` + `text` (описание); заголовок один объём не различает,
  поэтому основной сигнал даёт описание;
* две ветки на одном нормализаторе: словесный TF-IDF и символьные 3–5-граммы
  с границами `^`/`$`; гибрид `weight_word · word + weight_char · char`;
* `idf = log((N + 1) / (df + 1)) + 1`, `tf = 1 + ln(count)`, L2-норма;
* разреженное хранение `top_terms` термов на вектор; термы с префиксом
  пространства (`w:` слово, `c:` n-грамма);
* **пороги не задаются числом**: `similar_threshold = p90` косинусов пар из
  разных бакетов, `dissimilar_threshold = p50` — по **ненулевым** сходствам
  (нули означают «общих термов нет», а не «не похожи», и вырождают процентиль
  в 0.0). Абсолютные 0.5 / 0.2 из ТЗ опровергнуты экспериментом (на коротких
  русских текстах дают ложные срабатывания в обе стороны).

Детерминизм: все списки сортируются явно (`key`, `term`, `weight desc`),
суммы float считаются по отсортированным ключам, `hash()` не используется,
время берётся из `stats.now_utc()` (в тестах фиксируется
`TASK_READINESS_FIXED_TIME=1`).

CLI: `trr vectors build | similar | calibrate` (см. `cli.py`).
"""

import copy
import hashlib
import json
import math
import re
from pathlib import Path

from trr_impl import config as configmod
from trr_impl import limits
from trr_impl import schema_lite
from trr_impl import state as statemod
from trr_impl import stats
from trr_impl import store as storemod
from trr_impl.paths import TEXTS_RELATIVE, VECTORS_RELATIVE

__all__ = [
    "CHAR_NGRAMS",
    "MIN_CALIBRATION_PAIRS",
    "NORMALIZER_ID",
    "STOPWORDS",
    "TEXTS_RELATIVE",
    "TRUNCATE",
    "VECTORS_RELATIVE",
    "build",
    "calibrate",
    "char_ngrams",
    "cosine",
    "normalize_text",
    "query_vector",
    "run",
    "similar",
]


# Версия нормализатора. Меняется вместе со стоп-списком/правилами: артефакт с
# другой версией нельзя использовать для запроса «как-нибудь» — только
# пересобрать (`trr vectors build`).
NORMALIZER_ID = "ru-lower-e-strip-truncate-v1"
LANG = "ru"
TRUNCATE = 6
CHAR_NGRAMS = (3, 5)

# Ниже этого числа межбакетных пар калибровка p90/p50 ненадёжна: помечаем
# confidence=low и печатаем [WARN]. 50 — не «много», а граница, после которой
# процентиль перестаёт быть производной от десятка наблюдений.
MIN_CALIBRATION_PAIRS = 50

# Небольшой русский стоп-список. Не претендует на полноту: задача — убрать
# служебные слова, а не построить морфологию.
STOPWORDS = frozenset(
    (
        "и",
        "в",
        "на",
        "с",
        "по",
        "для",
        "не",
        "что",
        "как",
        "это",
        "или",
        "а",
        "но",
        "из",
        "от",
        "до",
        "при",
        "же",
        "ли",
        "то",
        "все",
        "так",
        "у",
        "о",
        "об",
    )
)

_TERM_SEPARATORS = re.compile(r"[^0-9a-zа-я]+")

_EXIT_OK = 0
_EXIT_BLOCKED = 2
_EXIT_MISSING = 4
_EXIT_SCHEMA = 5


# ---------------------------------------------------------------------------
# Нормализация
# ---------------------------------------------------------------------------


def normalize_text(value):
    """Нормализовать текст в список термов.

    lowercase → `ё`→`е` → пунктуация в пробелы → отбросить слова короче 3
    символов → убрать стоп-слова → усечь до `TRUNCATE` символов
    (детерминированное подобие стемминга: «терминология/терминологии» →
    «терминолог»). Полноценного стеммера в stdlib нет, и это известное
    ограничение, а не недоделка.
    """
    text = str(value or "").lower().replace("ё", "е")
    text = _TERM_SEPARATORS.sub(" ", text)
    terms = []
    for token in text.split():
        if len(token) < 3:
            continue
        if token in STOPWORDS:
            continue
        terms.append(token[:TRUNCATE])
    return terms


def char_ngrams(value, low=CHAR_NGRAMS[0], high=CHAR_NGRAMS[1]):
    """Все символьные n-граммы (по умолчанию 3–5) по нормализованной строке.

    Пробелы убираются, строка оборачивается в `^…$`: границы слова становятся
    частью сигнала, поэтому «поле» и «поля» имеют общие 3-граммы. Стемминг
    здесь не применяется — морфологию «съедают» сами n-граммы.
    """
    joined = "".join(normalize_text(value))
    if not joined:
        return []
    padded = "^%s$" % joined
    grams = []
    for size in range(int(low), int(high) + 1):
        for index in range(len(padded) - size + 1):
            grams.append(padded[index : index + size])
    return grams


def _term_counts(terms):
    counts = {}
    for term in terms:
        counts[term] = counts.get(term, 0) + 1
    return counts


def _tf(count):
    return 1.0 + math.log(float(count))


def _l2(vector):
    """L2-норма с фиксированным порядком суммирования (детерминизм)."""
    total = 0.0
    for term in sorted(vector):
        total += vector[term] * vector[term]
    return math.sqrt(total)


def _normalized(counts, idf):
    """tf-idf ветки, L2-норма. Термы, которых нет в idf, игнорируются."""
    raw = {}
    for term in sorted(counts):
        if term not in idf:
            continue
        raw[term] = _tf(counts[term]) * idf[term]
    norm = _l2(raw)
    if norm == 0:
        return {}
    return {term: value / norm for term, value in raw.items()}


def _hybrid(word, char, weight_word, weight_char):
    vector = {}
    for term in sorted(word):
        vector[term] = vector.get(term, 0.0) + weight_word * word[term]
    for term in sorted(char):
        vector[term] = vector.get(term, 0.0) + weight_char * char[term]
    norm = _l2(vector)
    if norm == 0:
        return {}
    return {term: value / norm for term, value in vector.items()}


def _store(vector, top_terms):
    """Top-N термов по весу (вес desc, терм asc) + L2-норма усечённого вектора."""
    ranked = sorted(vector.items(), key=lambda item: (-item[1], item[0]))
    terms = [[term, round(weight, 6)] for term, weight in ranked[: int(top_terms)]]
    stored = {term: weight for term, weight in terms}
    return terms, round(_l2(stored), 6)


def _document(task):
    summary = str(task.get("summary") or "").strip()
    text = str(task.get("text") or "").strip()
    return ("%s %s" % (summary, text)).strip()


def _normalizer():
    stopwords = "\n".join(sorted(STOPWORDS)).encode("utf-8")
    return {
        "id": NORMALIZER_ID,
        "lang": LANG,
        "truncate": TRUNCATE,
        "char_ngrams": [CHAR_NGRAMS[0], CHAR_NGRAMS[1]],
        "stopwords_sha256": hashlib.sha256(stopwords).hexdigest(),
    }


# ---------------------------------------------------------------------------
# Сборка
# ---------------------------------------------------------------------------


def _check_tasks(tasks):
    if not isinstance(tasks, list):
        raise ValueError("tasks должен быть списком")
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError("tasks[%d] должен быть объектом" % index)
        if not str(task.get("key") or "").strip():
            raise ValueError("tasks[%d].key обязателен" % index)


def build(tasks, top_terms=15, weight_word=0.5, weight_char=0.5):
    """Построить idf и гибридные векторы по корпусу задач.

    Возвращает словарь без `version`/`built_at`/`calibration`: их добавляет
    сборка артефакта, чтобы `build` оставался чистой функцией.
    """
    _check_tasks(tasks)
    top_terms = int(top_terms)
    weight_word = float(weight_word)
    weight_char = float(weight_char)
    if top_terms < 1:
        raise ValueError("top_terms должен быть >= 1")
    if weight_word < 0 or weight_char < 0:
        raise ValueError("веса гибрида не могут быть отрицательными")

    ordered = sorted(tasks, key=lambda task: str(task.get("key")))
    corpus = []
    for task in ordered:
        document = _document(task)
        corpus.append(
            (
                task,
                _term_counts(["w:" + term for term in normalize_text(document)]),
                _term_counts(["c:" + gram for gram in char_ngrams(document)]),
            )
        )

    total = len(corpus)
    document_frequency = {}
    for _task, words, chars in corpus:
        for term in set(words) | set(chars):
            document_frequency[term] = document_frequency.get(term, 0) + 1

    idf = {}
    for term in sorted(document_frequency):
        idf[term] = round(
            math.log((total + 1.0) / (document_frequency[term] + 1.0)) + 1.0, 6
        )

    vectors = []
    for task, words, chars in corpus:
        word_vector = _normalized(words, idf)
        char_vector = _normalized(chars, idf)
        hybrid = _hybrid(word_vector, char_vector, weight_word, weight_char)
        terms, norm = _store(hybrid, top_terms)
        vectors.append(
            {
                "key": str(task.get("key")),
                "role": task.get("role"),
                "work_kind": task.get("work_kind"),
                "sp": task.get("sp"),
                "qa_estimation": task.get("qa_estimation"),
                "terms": terms,
                "norm": norm,
            }
        )

    return {
        "normalizer": _normalizer(),
        "top_terms": top_terms,
        "weight_word": weight_word,
        "weight_char": weight_char,
        "idf": [[term, idf[term]] for term in sorted(idf)],
        "vectors": vectors,
    }


def build_artifact(tasks, top_terms=15, weight_word=0.5, weight_char=0.5, built_at=None):
    """Собрать полный артефакт `norm/task-vectors.json` с калибровкой порогов."""
    built = build(
        tasks,
        top_terms=top_terms,
        weight_word=weight_word,
        weight_char=weight_char,
    )
    return {
        "version": 1,
        "built_at": built_at or stats.now_utc(),
        "normalizer": built["normalizer"],
        "top_terms": built["top_terms"],
        "weight_word": built["weight_word"],
        "weight_char": built["weight_char"],
        "idf": built["idf"],
        "calibration": calibrate(built["vectors"]),
        "vectors": built["vectors"],
    }


# ---------------------------------------------------------------------------
# Сходство
# ---------------------------------------------------------------------------


def _terms_dict(vector):
    terms = vector.get("terms") if isinstance(vector, dict) else None
    if isinstance(terms, dict):
        return {str(key): float(value) for key, value in terms.items()}
    result = {}
    for item in terms or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            result[str(item[0])] = float(item[1])
    return result


def _norm(vector):
    value = vector.get("norm") if isinstance(vector, dict) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return _l2(_terms_dict(vector))


def cosine(first, second):
    """Косинус двух разреженных векторов.

    Сумма идёт по отсортированным общим ключам: одинаковый вход всегда даёт
    побитово одинаковый float.
    """
    left = _terms_dict(first)
    right = _terms_dict(second)
    left_norm = _norm(first)
    right_norm = _norm(second)
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = 0.0
    for term in sorted(set(left) & set(right)):
        dot += left[term] * right[term]
    return dot / (left_norm * right_norm)


def _bucket(vector):
    return (vector.get("role"), vector.get("work_kind"))


def calibrate(vectors):
    """Откалибровать пороги по корпусу.

    `similar_threshold = p90`, `dissimilar_threshold = p50` косинусов пар задач
    из **разных** бакетов `(role, work_kind)`, посчитанных по **ненулевым**
    сходствам. Нули — это «общих термов нет», а не «похожи» и не «не похожи»:
    при `top_terms: 15` нулевых межбакетных пар бывает ~90 %, и процентиль по
    всем парам вырождается в 0.0 — порог перестаёт отсекать что-либо.

    `pairs` остаётся общим числом межбакетных пар, `pairs_nonzero` — сколько из
    них дали косинус > 0. Меньше `MIN_CALIBRATION_PAIRS` ненулевых пар —
    `confidence: low` и прежнее поведение (процентили по всем парам): на таком
    объёме ненулевая выборка сама по себе ненадёжна.
    """
    vectors = [vector for vector in vectors or [] if isinstance(vector, dict)]
    pairs = []
    for index, first in enumerate(vectors):
        for second in vectors[index + 1 :]:
            if _bucket(first) == _bucket(second):
                continue
            pairs.append(cosine(first, second))

    nonzero = [value for value in pairs if value > 0]
    enough = len(nonzero) >= MIN_CALIBRATION_PAIRS
    sample = nonzero if enough else pairs
    if sample:
        similar = round(stats.percentile(sample, 0.9), 4)
        dissimilar = round(stats.percentile(sample, 0.5), 4)
    else:
        similar = 0.0
        dissimilar = 0.0

    return {
        "similar_threshold": similar,
        "dissimilar_threshold": dissimilar,
        "corpus_rows": len(vectors),
        "method": "p90_inter" if enough else "p90_inter_all",
        "dissimilar_method": "p50_inter" if enough else "p50_inter_all",
        "pairs": len(pairs),
        "pairs_nonzero": len(nonzero),
        "confidence": "high" if enough else "low",
    }


def similar(vectors, query_vector, top_k=5, same_bucket=None):
    """Top-N похожих задач корпуса к `query_vector`.

    `same_bucket=True` — фильтр по бакету запроса (если он известен);
    `same_bucket=(role, work_kind)` — явный бакет. Сама задача запроса
    исключается по `key`. Сортировка: cosine desc, key asc.
    """
    query_bucket = _bucket(query_vector)
    known_bucket = query_bucket[0] is not None and query_bucket[1] is not None

    if same_bucket is True:
        filter_bucket = query_bucket if known_bucket else None
    elif isinstance(same_bucket, (list, tuple)) and len(same_bucket) == 2:
        filter_bucket = (same_bucket[0], same_bucket[1])
    else:
        filter_bucket = None

    query_key = query_vector.get("key")
    results = []
    for vector in vectors or []:
        if not isinstance(vector, dict):
            continue
        if query_key and vector.get("key") == query_key:
            continue
        bucket = _bucket(vector)
        if filter_bucket is not None and bucket != filter_bucket:
            continue
        results.append(
            {
                "key": vector.get("key"),
                "cosine": round(cosine(query_vector, vector), 4),
                "sp": vector.get("sp"),
                "role": vector.get("role"),
                "work_kind": vector.get("work_kind"),
                "same_bucket": bool(known_bucket and bucket == query_bucket),
            }
        )
    results.sort(key=lambda item: (-item["cosine"], str(item.get("key"))))
    return results[: int(top_k)]


def query_vector(value, model):
    """Вектор запроса по сохранённым idf и настройкам артефакта.

    Детерминированно: тот же текст и тот же артефакт дают тот же вектор.
    Термы, которых нет в `idf` (корпус их не видел), игнорируются — idf для
    них не выдумывается.
    """
    if not isinstance(model, dict):
        raise ValueError("модель векторов должна быть JSON-объектом")
    idf = {}
    for item in model.get("idf") or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            idf[str(item[0])] = float(item[1])
    top_terms = int(model.get("top_terms") or 15)
    weight_word = float(model.get("weight_word") if model.get("weight_word") is not None else 0.5)
    weight_char = float(
        model.get("weight_char") if model.get("weight_char") is not None else 1.0 - weight_word
    )

    words = _normalized(
        _term_counts(["w:" + term for term in normalize_text(value)]), idf
    )
    chars = _normalized(
        _term_counts(["c:" + gram for gram in char_ngrams(value)]), idf
    )
    hybrid = _hybrid(words, chars, weight_word, weight_char)
    terms, norm = _store(hybrid, top_terms)
    return {"key": None, "role": None, "work_kind": None, "sp": None, "terms": terms, "norm": norm}


# ---------------------------------------------------------------------------
# CLI-обвязка (`trr vectors …`)
# ---------------------------------------------------------------------------


def _emit(message, quiet=False):
    if not quiet:
        print(message)


def _emit_json(args, payload):
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _read_json(path):
    try:
        limits.check_size(path)
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except limits.LimitError as exc:
        return None, "файл больше допустимого: %s" % exc
    except OSError as exc:
        return None, "не читается: %s" % exc
    except ValueError as exc:
        return None, "невалидный JSON: %s" % exc


def _validate(name, payload):
    try:
        schema = schema_lite.load_schema(configmod.SCHEMAS_DIR, name)
    except schema_lite.SchemaError as exc:
        return ["схема %s не читается: %s" % (name, exc)]
    return schema_lite.validate(payload, schema, name)


def _vector_config(workdir):
    """`estimation.vector` из конфига, всегда слитый с `DEFAULTS`.

    Нет конфига (или он не разбирается) — берутся дефолты из `config.DEFAULTS`.
    Слияние с дефолтами делается и здесь: вызывающий код читает ключи напрямую
    (`cfg["top_terms"]`), а не через `.get(..., <литерал>)` — иначе дефолт
    пришлось бы держать в двух местах.
    """
    cfg = copy.deepcopy(configmod.DEFAULTS)
    try:
        cfg = configmod.load_config(configmod.config_path(workdir))
    except configmod.ConfigError:
        pass
    vector = ((cfg.get("estimation") or {}).get("vector")) or {}
    defaults = configmod.DEFAULTS["estimation"]["vector"]
    if not isinstance(vector, dict):
        return copy.deepcopy(defaults)
    merged = copy.deepcopy(defaults)
    merged.update(vector)
    return merged


def _run_build(workdir, args, quiet):
    texts_path = Path(workdir) / statemod.STATE_DIR / TEXTS_RELATIVE
    if not texts_path.is_file():
        _emit(
            "[MISSING] %s — сначала соберите тексты задач (train/enrich): "
            "без них векторы строить не из чего" % TEXTS_RELATIVE,
            quiet,
        )
        _emit_json(args, {"status": "blocked", "code": _EXIT_MISSING, "artifact": TEXTS_RELATIVE})
        return _EXIT_MISSING

    payload, error = _read_json(texts_path)
    if error:
        _emit("[MISSING] %s — %s" % (TEXTS_RELATIVE, error), quiet)
        _emit_json(args, {"status": "blocked", "code": _EXIT_SCHEMA, "artifact": TEXTS_RELATIVE})
        return _EXIT_SCHEMA

    errors = _validate("task-texts", payload)
    if errors:
        for item in errors:
            _emit("[MISSING] %s — %s" % (TEXTS_RELATIVE, item), quiet)
        _emit_json(args, {"status": "blocked", "code": _EXIT_SCHEMA, "artifact": TEXTS_RELATIVE})
        return _EXIT_SCHEMA

    tasks = payload.get("tasks") or []
    cfg = _vector_config(workdir)
    min_corpus = getattr(args, "min_corpus", None)
    if min_corpus is None:
        min_corpus = cfg.get("min_corpus", configmod.VECTOR_MIN_CORPUS)
    min_corpus = int(min_corpus)
    corpus = len(tasks)
    if corpus < min_corpus:
        _emit(
            "[BLOCKED] vectors: корпус %d меньше min_corpus — добавьте спринты "
            "через enrich" % corpus,
            quiet,
        )
        _emit_json(
            args,
            {
                "status": "blocked",
                "code": _EXIT_BLOCKED,
                "corpus_rows": corpus,
                "min_corpus": min_corpus,
            },
        )
        return _EXIT_BLOCKED

    top_terms = getattr(args, "top_terms", None)
    if top_terms is None:
        top_terms = cfg["top_terms"]
    weight_word = getattr(args, "weight_word", None)
    if weight_word is None:
        weight_word = cfg["weight_word"]
    weight_word = float(weight_word)
    weight_char = round(1.0 - weight_word, 6)

    artifact = build_artifact(
        tasks,
        top_terms=int(top_terms),
        weight_word=weight_word,
        weight_char=weight_char,
    )
    errors = _validate("task-vectors", artifact)
    if errors:
        for item in errors:
            _emit("[MISSING] task-vectors — %s" % item, quiet)
        _emit_json(args, {"status": "blocked", "code": _EXIT_SCHEMA})
        return _EXIT_SCHEMA

    target = Path(workdir) / statemod.STATE_DIR / VECTORS_RELATIVE
    schema_lite.write_json(target, artifact)
    # Зеркало: векторы задач уходят в БД как BLOB float32 (+ термы, если
    # keep_payloads). Ошибка БД не отменяет артефакт — только [WARN].
    # cfg=None: `storage` читается из конфига проекта внутри store.
    storemod.save_vectors(workdir, None, artifact)

    calibration = artifact["calibration"]
    if calibration["confidence"] == "low":
        _emit(
            "[WARN] калибровка ненадёжна (ненулевых пар %d < %d)"
            % (calibration.get("pairs_nonzero", 0), MIN_CALIBRATION_PAIRS),
            quiet,
        )
    _emit(
        "[OK] vectors: %d задач, terms=%d, threshold=%s"
        % (
            len(artifact["vectors"]),
            artifact["top_terms"],
            calibration["similar_threshold"],
        ),
        quiet,
    )
    _emit_json(
        args,
        {
            "status": "ok",
            "code": _EXIT_OK,
            "artifact": VECTORS_RELATIVE,
            "corpus_rows": len(artifact["vectors"]),
            "top_terms": artifact["top_terms"],
            "similar_threshold": calibration["similar_threshold"],
            "dissimilar_threshold": calibration["dissimilar_threshold"],
            "pairs": calibration["pairs"],
            "pairs_nonzero": calibration.get("pairs_nonzero"),
        },
    )
    return _EXIT_OK


def _read_query_text(workdir, args, quiet):
    if getattr(args, "text_file", None):
        path = Path(str(args.text_file))
        if not path.is_absolute():
            path = Path(workdir) / path
        if not path.is_file():
            _emit("[MISSING] --text-file — файла нет: %s" % path, quiet)
            return None
        try:
            limits.check_size(path)
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
        except limits.LimitError as exc:
            _emit("[MISSING] --text-file — файл больше допустимого: %s" % exc, quiet)
            return None
        except OSError as exc:
            _emit("[MISSING] --text-file — не читается: %s" % exc, quiet)
            return None
    return getattr(args, "text", None)


def _run_similar(workdir, args, quiet):
    path = Path(workdir) / statemod.STATE_DIR / VECTORS_RELATIVE
    if not path.is_file():
        _emit(
            "[MISSING] %s — запустите `trr vectors build`" % VECTORS_RELATIVE,
            quiet,
        )
        _emit_json(args, {"status": "blocked", "code": _EXIT_MISSING, "artifact": VECTORS_RELATIVE})
        return _EXIT_MISSING

    artifact, error = _read_json(path)
    if error:
        _emit("[MISSING] %s — %s" % (VECTORS_RELATIVE, error), quiet)
        _emit_json(args, {"status": "blocked", "code": _EXIT_SCHEMA, "artifact": VECTORS_RELATIVE})
        return _EXIT_SCHEMA

    errors = _validate("task-vectors", artifact)
    if errors:
        for item in errors:
            _emit("[MISSING] %s — %s" % (VECTORS_RELATIVE, item), quiet)
        _emit_json(args, {"status": "blocked", "code": _EXIT_SCHEMA, "artifact": VECTORS_RELATIVE})
        return _EXIT_SCHEMA

    normalizer = (artifact.get("normalizer") or {}).get("id")
    if normalizer != NORMALIZER_ID:
        _emit(
            "[MISSING] нормализатор артефакта %r ≠ %r — пересоберите "
            "`trr vectors build`" % (normalizer, NORMALIZER_ID),
            quiet,
        )
        _emit_json(args, {"status": "blocked", "code": _EXIT_SCHEMA})
        return _EXIT_SCHEMA

    cfg = _vector_config(workdir)
    top_k = getattr(args, "top", None)
    if top_k is None:
        top_k = cfg.get("top_k", 5)

    task_key = getattr(args, "task", None)
    if task_key:
        query = None
        for vector in artifact.get("vectors") or []:
            if vector.get("key") == task_key:
                query = vector
                break
        if query is None:
            _emit(
                "[MISSING] vectors similar: задачи %s нет в корпусе — "
                "пересоберите `trr vectors build`" % task_key,
                quiet,
            )
            _emit_json(args, {"status": "blocked", "code": _EXIT_MISSING, "task_key": task_key})
            return _EXIT_MISSING
    else:
        text = _read_query_text(workdir, args, quiet)
        if text is None:
            _emit(
                "[BLOCKED] vectors similar: укажите --task <KEY>, --text-file <path> "
                "или --text \"<строка>\"",
                quiet,
            )
            _emit_json(args, {"status": "blocked", "code": _EXIT_BLOCKED})
            return _EXIT_BLOCKED
        query = query_vector(text, artifact)
        if getattr(args, "same_bucket", False):
            _emit(
                "[WARN] --same-bucket: у текста нет бакета — фильтр не применён",
                quiet,
            )

    results = similar(
        artifact.get("vectors") or [],
        query,
        top_k=int(top_k),
        same_bucket=bool(getattr(args, "same_bucket", False)),
    )
    # Зеркало: пары (задача, похожая) — идемпотентная перезапись набора.
    storemod.save_similar(
        workdir,
        None,
        task_key or "text",
        results,
        artifact.get("version") or 1,
    )

    _emit("cos     key          role  work_kind       sp", quiet)
    for item in results:
        _emit(
            "%.4f  %-12s %-5s %-15s %s"
            % (
                item["cosine"],
                item["key"],
                item["role"],
                item["work_kind"],
                "-" if item["sp"] is None else item["sp"],
            ),
            quiet,
        )
    _emit_json(
        args,
        {
            "status": "ok",
            "code": _EXIT_OK,
            "query": task_key or "text",
            "results": results,
            "calibration": artifact.get("calibration"),
        },
    )
    return _EXIT_OK


def _run_calibrate(workdir, args, quiet):
    path = Path(workdir) / statemod.STATE_DIR / VECTORS_RELATIVE
    if not path.is_file():
        _emit(
            "[MISSING] %s — запустите `trr vectors build`" % VECTORS_RELATIVE,
            quiet,
        )
        _emit_json(args, {"status": "blocked", "code": _EXIT_MISSING, "artifact": VECTORS_RELATIVE})
        return _EXIT_MISSING

    artifact, error = _read_json(path)
    if error:
        _emit("[MISSING] %s — %s" % (VECTORS_RELATIVE, error), quiet)
        _emit_json(args, {"status": "blocked", "code": _EXIT_SCHEMA})
        return _EXIT_SCHEMA

    errors = _validate("task-vectors", artifact)
    if errors:
        for item in errors:
            _emit("[MISSING] %s — %s" % (VECTORS_RELATIVE, item), quiet)
        _emit_json(args, {"status": "blocked", "code": _EXIT_SCHEMA})
        return _EXIT_SCHEMA

    artifact["calibration"] = calibrate(artifact.get("vectors") or [])
    schema_lite.write_json(path, artifact)

    calibration = artifact["calibration"]
    if calibration["confidence"] == "low":
        _emit(
            "[WARN] калибровка ненадёжна (ненулевых пар %d < %d)"
            % (calibration.get("pairs_nonzero", 0), MIN_CALIBRATION_PAIRS),
            quiet,
        )
    _emit(
        "[OK] vectors calibrate: similar=%s dissimilar=%s pairs=%d/%d corpus=%d"
        % (
            calibration["similar_threshold"],
            calibration["dissimilar_threshold"],
            calibration.get("pairs_nonzero", 0),
            calibration["pairs"],
            calibration["corpus_rows"],
        ),
        quiet,
    )
    _emit_json(args, dict(calibration, status="ok", code=_EXIT_OK))
    return _EXIT_OK


def run(workdir, args=None):
    """Точка входа подкоманды `vectors` (`cli.py` вызывает `run(workdir, args)`)."""
    workdir = Path(workdir)
    quiet = bool(getattr(args, "quiet", False))
    command = getattr(args, "vectors_command", None)
    if command == "build":
        return _run_build(workdir, args, quiet)
    if command == "similar":
        return _run_similar(workdir, args, quiet)
    if command == "calibrate":
        return _run_calibrate(workdir, args, quiet)
    _emit(
        "[BLOCKED] vectors: нужна подкоманда build, similar или calibrate",
        quiet,
    )
    _emit_json(args, {"status": "blocked", "code": _EXIT_BLOCKED})
    return _EXIT_BLOCKED

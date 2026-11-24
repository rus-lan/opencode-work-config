#!/usr/bin/env python3
"""Детерминированный линтер русского текста для скилла ru-text.

Проверяет только то, что можно проверить механически. Не заменяет редактуру:
линтер находит следы, а решение принимает человек или модель.

Использование:
    python3 scripts/lint.py FILE [FILE ...]
    echo "текст" | python3 scripts/lint.py
    python3 scripts/lint.py --json FILE
    python3 scripts/lint.py --baseline 3 FILE   # пропустить до 3 жёстких нарушений
    python3 scripts/lint.py --disable long-sentence,passive FILE
    python3 scripts/lint.py --selftest

Коды выхода: 0 — чисто (или в пределах baseline), 1 — жёсткие нарушения,
2 — ошибка использования.
"""

import argparse
import json
import re
import sys

# --- правила ---------------------------------------------------------------

STOP_WORDS = [
    "очень", "максимально", "высококвалифицированн", "индивидуальный подход",
    "команда профессионалов", "широкий ассортимент", "динамично развивающ",
    "высокий уровень сервиса", "выгодные условия", "комплексные решения",
    "оптимальное соотношение",
]

AI_MARKERS = [
    "погружа", "углубля", "ландшафт", "гобелен", "свидетельств",
    "ключевой момент", "поворотный момент", "высвободить потенциал",
    "обуздать", "отличный вопрос", "вы абсолютно правы", "многообещающ",
    "новые горизонты", "в заключение",
]

BUREAUCRATESE = [
    "данный", "является", "осуществля", "в рамках", "в целях",
    "представляет собой", "в соответствии с", "на основании", "по причине",
    "вышеуказанный", "нижеследующий", "надлежащий", "во избежание",
    "в случае если",
]

EMPTY_EVALUATIONS = [
    "качественн", "уникальн", "инновационн", "передов", "эффективн",
    "идеальн", "профессиональн", "превосходн", "великолепн", "лучш",
]

SYNONYM_GROUPS = [
    ("проверить", "верифицировать"),
    ("показать", "продемонстрировать"),
    ("изменить", "модифицировать", "трансформировать"),
    ("использовать", "задействовать"),
    ("удалить", "стереть"),
]

LONG_SENTENCE_WORDS = 30

RULE_MESSAGES = {
    "stop-word": "Стоп-слово. Убрать или заменить фактом.",
    "ai-marker": "Маркер машинного текста. Переписать по-человечески.",
    "bureaucratese": "Канцелярит. Заменить живым глаголом или оборотом.",
    "empty-evaluation": "Пустая оценка. Нужен факт или удаление.",
    "nominalization": "Номинализация. Действие спрятано в существительном.",
    "passive": "Возможный пассив. Назвать актора, если он известен.",
    "long-sentence": "Длинное предложение. Разбить или упростить.",
    "straight-quote": "Прямая кавычка в русском тексте. Нужны ёлочки.",
    "double-hyphen": "Двойной дефис вместо тире.",
    "spaced-hyphen": "Дефис с пробелами вместо тире.",
    "three-dots": "Три точки вместо многоточия.",
    "yo-mixed": "Смешаны формы с «ё» и без.",
    "synonym-rotation": "Одно действие названо разными словами в одном тексте.",
    "repetition": "Слово повторяется в одном предложении.",
}

HARD_RULES = {
    "stop-word", "ai-marker", "bureaucratese", "empty-evaluation",
    "straight-quote", "double-hyphen", "spaced-hyphen", "three-dots",
}
ADVISORY_RULES = {
    "nominalization", "passive", "long-sentence",
    "yo-mixed", "synonym-rotation", "repetition",
}

CODE_FENCE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`]*`")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
WORD = re.compile(r"[А-Яа-яЁёA-Za-z0-9-]+")


def mask_code(text: str) -> str:
    """Заменяет код пробелами, сохраняя смещения и переводы строк."""
    def blank(match):
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))
    text = CODE_FENCE.sub(blank, text)
    return INLINE_CODE.sub(lambda m: " " * len(m.group(0)), text)


def line_col(text: str, offset: int):
    line = text.count("\n", 0, offset) + 1
    start = text.rfind("\n", 0, offset) + 1
    return line, offset - start + 1


def finding(rule, text, offset, match):
    line, col = line_col(text, offset)
    return {
        "rule": rule,
        "severity": "hard" if rule in HARD_RULES else "advisory",
        "line": line,
        "col": col,
        "match": match,
        "message": RULE_MESSAGES[rule],
    }


def find_phrases(text: str, phrases, rule: str):
    out = []
    for phrase in phrases:
        for m in re.finditer(r"(?<![\w-])" + re.escape(phrase), text, re.I):
            out.append(finding(rule, text, m.start(), m.group(0)))
    return out


def find_typography(text: str):
    out = []
    for m in re.finditer(r'"', text):
        out.append(finding("straight-quote", text, m.start(), m.group(0)))
    for m in re.finditer(r"--", text):
        out.append(finding("double-hyphen", text, m.start(), m.group(0)))
    for m in re.finditer(r"\s-\s", text):
        out.append(finding("spaced-hyphen", text, m.start(), m.group(0)))
    for m in re.finditer(r"\.\.\.", text):
        out.append(finding("three-dots", text, m.start(), m.group(0)))
    return out


def find_yo_mix(text: str):
    pairs = [
        ("еще", "ещё"), ("ее", "её"), ("нее", "неё"), ("мое", "моё"),
        ("твое", "твоё"), ("прием", "приём"), ("идет", "идёт"),
        ("найдет", "найдёт"), ("все-таки", "всё-таки"),
    ]
    out = []
    low = text.lower()
    for plain, yo in pairs:
        if re.search(r"(?<![\w-])" + plain + r"(?![\w-])", low) and \
           re.search(r"(?<![\w-])" + yo + r"(?![\w-])", low):
            m = re.search(r"(?<![\w-])" + yo + r"(?![\w-])", low)
            out.append(finding("yo-mixed", text, m.start(), m.group(0)))
    return out


def sentences(text: str):
    offset = 0
    for part in SENTENCE_SPLIT.split(text):
        if part.strip():
            start = text.find(part, offset)
            if start < 0:
                start = offset
            yield part, start
            offset = start + len(part)


def find_sentence_rules(text: str):
    out = []
    for sentence, start in sentences(text):
        words = WORD.findall(sentence)
        if len(words) > LONG_SENTENCE_WORDS:
            out.append(finding("long-sentence", text, start, f"{len(words)} слов"))
        for m in re.finditer(
            r"\b(осуществл|провед|обеспеч|оказ)\w*\s+\w+(ани|ени|ци|ость)\w*",
            sentence, re.I,
        ):
            out.append(finding("nominalization", text, start + m.start(), m.group(0)))
        for m in re.finditer(
            r"\b(был|была|было|были|будет|будут)\s+\w+(ен|н|т)(а|о|ы|и)?\b",
            sentence, re.I,
        ):
            out.append(finding("passive", text, start + m.start(), m.group(0)))
        counts = {}
        for w in words:
            key = w.lower()
            if len(key) > 4:
                counts[key] = counts.get(key, 0) + 1
        for word, count in counts.items():
            if count >= 3:
                pos = sentence.lower().find(word)
                out.append(finding("repetition", text, start + max(pos, 0), word))
    return out


def find_synonym_rotation(text: str):
    out = []
    low = text.lower()
    for group in SYNONYM_GROUPS:
        found = []
        for word in group:
            m = re.search(r"(?<![\w-])" + word, low)
            if m:
                found.append((word, m.start()))
        if len(found) > 1:
            word, offset = found[1]
            out.append(finding("synonym-rotation", text, offset, ", ".join(group)))
    return out


def lint(text: str, disabled=()):
    clean = mask_code(text)
    findings = []
    findings += find_phrases(clean, STOP_WORDS, "stop-word")
    findings += find_phrases(clean, AI_MARKERS, "ai-marker")
    findings += find_phrases(clean, BUREAUCRATESE, "bureaucratese")
    findings += find_phrases(clean, EMPTY_EVALUATIONS, "empty-evaluation")
    findings += find_typography(clean)
    findings += find_yo_mix(clean)
    findings += find_sentence_rules(clean)
    findings += find_synonym_rotation(clean)
    findings = [f for f in findings if f["rule"] not in disabled]
    findings.sort(key=lambda f: (f["line"], f["col"], f["rule"]))
    return findings


# --- CLI -------------------------------------------------------------------


def print_text(fname, findings):
    for f in findings:
        print(f"{fname}:{f['line']}:{f['col']} {f['rule']}: {f['message']} [{f['match']}]")
    hard = sum(1 for f in findings if f["severity"] == "hard")
    adv = len(findings) - hard
    print(f"{fname}: {hard} жёстких, {adv} рекомендательных")


def run(args):
    disabled = set(filter(None, (args.disable or "").split(",")))
    unknown = disabled - (HARD_RULES | ADVISORY_RULES)
    if unknown:
        print(f"Неизвестные правила: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    inputs = []
    if args.files:
        for name in args.files:
            try:
                with open(name, encoding="utf-8") as fh:
                    inputs.append((name, fh.read()))
            except OSError as exc:
                print(f"Не читается {name}: {exc}", file=sys.stderr)
                return 2
    else:
        inputs.append(("<stdin>", sys.stdin.read()))

    total_hard = 0
    payload = []
    for name, text in inputs:
        findings = lint(text, disabled)
        if args.json:
            payload.append({"file": name, "findings": findings})
        else:
            print_text(name, findings)
        total_hard += sum(1 for f in findings if f["severity"] == "hard")

    if args.json:
        print(json.dumps({
            "files": payload,
            "hard": total_hard,
            "baseline": args.baseline,
            "ok": total_hard <= args.baseline,
        }, ensure_ascii=False, indent=2))

    return 0 if total_hard <= args.baseline else 1


# --- самопроверка ----------------------------------------------------------


def selftest():
    bad = (
        'Наша компания является лидирующим поставщиком; мы осуществляем "качественную" '
        'поддержку -- очень быстро и ещё быстрее.\n'
        'Уникальная платформа обеспечивает проведение анализа данных и была создана '
        'для того чтобы клиенты могли получать максимально эффективный результат '
        'в самых разных ситуациях и при любых условиях работы без ограничений '
        'и без дополнительных настроек со стороны пользователя.'
    )
    findings = lint(bad)
    rules = {f["rule"] for f in findings}
    expected = {
        "stop-word", "bureaucratese", "straight-quote", "double-hyphen",
        "empty-evaluation", "long-sentence", "nominalization", "passive",
    }
    missing = expected - rules
    assert not missing, f"selftest: не найдены правила {missing}"

    good = (
        "Откройте настройки и выберите раздел «Доступ». "
        "Изменения применятся за пару минут. "
        "Запрос может не пройти, если истекла сессия. "
        "Тогда войдите снова."
    )
    good_rules = {f["rule"] for f in lint(good)}
    assert "stop-word" not in good_rules, "selftest: ложное срабатывание на хорошем тексте"
    assert "straight-quote" not in good_rules, "selftest: ёлочки приняты за ошибку"
    assert "long-sentence" not in good_rules, "selftest: хорошее предложение слишком длинное"

    modality = "Запрос может не пройти. Причина может быть в сессии."
    assert not any(f["rule"] == "stop-word" for f in lint(modality)), \
        "selftest: модальность не должна считаться стоп-словом"

    print("selftest OK")


def main():
    parser = argparse.ArgumentParser(description="Линтер русского текста (ru-text)")
    parser.add_argument("files", nargs="*")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--baseline", type=int, default=0)
    parser.add_argument("--disable", default="")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    return run(args)


if __name__ == "__main__":
    sys.exit(main())

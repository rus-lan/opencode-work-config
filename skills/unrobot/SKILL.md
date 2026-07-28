---
name: unrobot
version: 0.1.0
description: |
  Make any text read human, not machine. A portable detect → rewrite → verify
  pipeline that strips AI tells (filler vocabulary, copula avoidance, rule-of-three,
  flat sentence rhythm, transition overuse, typography artifacts), rewrites the
  prose to a natural human cadence, and verifies the result with a deterministic
  scorer plus a fact-integrity diff so numbers, code, and URLs survive untouched.
  Works in 8 languages (en, ru, de, es, fr, pt, zh, ar) on docs, marketing,
  blog, or any prose. Project-agnostic.
license: MIT
compatibility: claude-code opencode
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
  - Agent
---

# unrobot — make text read human, not machine

Invocation: `/unrobot <target> [--lang <code>] [--deep] [--brief "<facts>"]`

- `<target>` — a file path, a directory, a glob, or quoted inline text.
- `--lang` — force language (`en ru de es fr pt zh ar`); else auto from frontmatter `lang:` or script.
- `--deep` — use the `seo-writer` agent for full restructuring rewrites instead of in-place cleanup. Default is in-place cleanup (lighter, safer for technical docs).
- `--brief` — extra facts the rewrite may use. Never invent facts; flag gaps instead.

## What this is (and is not)

This makes writing genuinely read like a person wrote it. It does NOT promise to
beat any specific AI detector — detectors are unreliable and change constantly.
What it does is **measure and remove the signals detectors react to**: low
burstiness, marker vocabulary, template structures, typography tells. Lower score
on those signals correlates with lower detection, but there is no guarantee.
Be honest about this in any report. The real goal is good, human-quality prose.

## Tools in this skill

- `scripts/score.mjs` — deterministic, zero-dep, multilingual scorer. Resolve its
  path relative to this skill — it sits at `scripts/score.mjs` next to this
  SKILL.md; when installed that is `~/.claude/skills/unrobot/scripts/score.mjs`
  (written as `<skill-dir>/scripts/score.mjs` below). Outputs a
  `humanScore` 0-100 (higher = more human) plus per-metric reasons. This is both
  the **detector** (stage 1) and the **measurable acceptance gate** (stage 3).
  - Score files/dir/glob: `node <skill-dir>/scripts/score.mjs [--lang X] [--json] <path>...`
  - Fact-integrity diff: `node <skill-dir>/scripts/score.mjs --factcheck --before <a> --after <b>`
- `markers/<lang>.json` — per-language AI-tell packs (filler regexes, inflated
  transitions, triad conjunctions). English is the fallback. Edit these to tune.
- `references/ai-tells.md` — the rewrite playbook: how to fix each tell by hand
  while keeping facts and voice.

## Pipeline (3 stages — never skip stage 3)

### Stage 1 — DETECT / SCORE
Run the scorer over `<target>`. For a directory or glob it ranks files worst-first.
```
node <skill-dir>/scripts/score.mjs --json <target>
```
Record each file's baseline `humanScore`, `sentenceCV`, `markerHits`, and the
`why` list. These tell you exactly what to fix. Decide scope: by default fix
everything scoring < 80; with a big target, fix worst-first up to the user's ask.

### Stage 2 — REWRITE
For each file to fix:
1. **Snapshot protected tokens** — before editing, the scorer's factcheck mode
   captures every number, code span, hex, URL, and snake_case identifier. These
   must survive verbatim.
2. **Rewrite the prose only.** Apply `references/ai-tells.md`:
   - Kill marker vocabulary (use the file's `markerHits` as the hit list).
   - Restore copulas (is/are/has) for "serves as / stands as / boasts".
   - Break rule-of-three lists; cut one item or rewrite as a real clause.
   - **Vary sentence length deliberately** — short, then long, then medium. The
     single biggest lever on burstiness. Target sentenceCV 0.55–0.95.
   - Drop inflated transitions; let sentences connect by meaning.
   - Replace em/en dashes with commas, periods, or parentheses; straighten quotes.
   - Add a little voice and specificity. Sterile uniform text is its own tell.
   - **Never** touch code fences, inline code, JSX/MDX tags, frontmatter keys,
     headings (unless the brief says so), numbers, or URLs.
3. In-place edit by default. With `--deep`, delegate the rewrite to the
   `seo-writer` agent (pass the file, the facts, the protected-token list, the
   target language) for heavier restructuring.

### Stage 3 — VERIFY (the gate — all four must pass)
1. **Re-score:** `node <skill-dir>/scripts/score.mjs --lang X <file>` — humanScore must rise
   and reach the target band (default ≥ 80; report if it can't without inventing).
2. **Fact integrity:** `node <skill-dir>/scripts/score.mjs --factcheck --before <orig> --after <new>`
   — must report PASS. Any lost token = revert that edit. Numbers/code/URLs are sacred.
3. **Anti-uniformity:** the scorer penalizes `sentenceCV < 0.30` as hard as it
   penalizes high markers. If you over-edited into a flat, marker-free monotone,
   the score will NOT reach the band — vary the rhythm, do not just delete words.
4. **Idempotency:** re-running unrobot on an already-clean file should change
   almost nothing. If you keep rewriting, you are churning, not improving — stop
   when humanScore is in-band and factcheck passes.

If `--deep`, optionally get a Fable second opinion (`fable-second-opinion` skill) on 2-3
rewritten samples to confirm the text was not over-sanitized and reads natural to a human.

## Report

```
Target: <path/glob>   Files: N   Language(s): ...
Avg humanScore: <before> → <after>
Per file: <name>  <before>/100 → <after>/100  (factcheck PASS/FAIL)
Tells removed: <top categories with counts>
Facts assumed (not in source): <list or none — flag for human review>
Could not reach band: <files + why, or none>
```

## Notes

- Multilingual: the language-agnostic metrics (burstiness, paragraph rhythm,
  n-gram repetition, typography) work everywhere. The marker packs are
  language-specific; `ar` and the non-English packs are v1 and benefit from
  native-speaker review — treat their marker list as a starting point, not gospel.
- The scorer is a triage and acceptance instrument, not a truth oracle. A human
  read of the final text is always the last gate.

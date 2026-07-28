#!/usr/bin/env node
/**
 * score.mjs — portable, zero-dep AI-tell + rhythm scorer for the `unrobot` skill.
 *
 * Measures (does NOT "detect AI" — it measures the signals detectors react to):
 *   - sentence-length CV (burstiness): too low = robotic, too high = chaotic
 *   - paragraph-length CV
 *   - repeated 3-5 gram rate
 *   - transition-word density (per 1000 words)
 *   - em/en-dash density (per 1000 words)
 *   - marker hits from the language pack (filler / AI vocabulary / copula avoidance)
 *   - rule-of-three triads, uniform bullet openers, repeated sentence openers
 *   - typography tells (curly quotes, unicode ellipsis, nbsp)
 * Then folds them into a single humanScore 0-100 (higher = reads more human).
 *
 * Usage:
 *   node score.mjs [--lang <code>] [--json] [--markers <dir>] <file|dir>...
 *   node score.mjs --factcheck --before <file> --after <file> [--json]
 *
 * Language packs live in ../markers/<lang>.json. `en` is the fallback.
 * Language is taken from --lang, else frontmatter `lang:`, else script detection
 * (Cyrillic→ru, Arabic→ar, CJK→zh); Latin-script langs default to en unless --lang.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MARKERS_DEFAULT = path.resolve(__dirname, '..', 'markers');

// ─── Thresholds (tunable; the autoresearch loop edits these) ───────────────────
export const THRESHOLDS = {
  CV_FLAT: 0.40,        // below → robotically uniform (penalize)
  CV_TOO_UNIFORM: 0.30, // below → hard penalty (over-edited / template)
  CV_CHAOTIC: 1.15,     // above → penalize (unnatural choppiness)
  CV_IDEAL_LO: 0.55,
  CV_IDEAL_HI: 0.95,
  PARA_CV_FLAT: 0.35,
  NGRAM_REPEAT_WARN: 0.020, // >2% repeated 3-5 grams
  TRANSITION_PER_1000: 12,
  EMDASH_PER_1000: 4,
  TRIAD_MIN: 2,
  UNIFORM_OPENER_MIN: 3,
  REPEATED_OPENER_MIN: 3,
};

// ─── Marker pack loading ───────────────────────────────────────────────────────
function loadPack(lang, markersDir) {
  const file = path.join(markersDir, `${lang}.json`);
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8'));
  } catch (e) {
    console.error(`unrobot/score: bad marker pack ${file}: ${e.message}`);
    return null;
  }
}

function detectLang(text) {
  if (/[؀-ۿ]/.test(text)) return 'ar';
  if (/[一-鿿぀-ヿ]/.test(text)) return 'zh';
  if (/[Ѐ-ӿ]/.test(text)) return 'ru';
  return 'en'; // Latin-script default
}

function frontmatterLang(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return null;
  const lm = m[1].match(/^\s*lang\s*:\s*["']?([a-zA-Z-]+)["']?\s*$/m);
  return lm ? lm[1].toLowerCase().split('-')[0] : null;
}

// ─── Prose extraction (strip code/markup so we score prose only) ───────────────
export function extractProse(text) {
  return text
    .replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '')
    .replace(/^`{3,}[\s\S]*?^`{3,}/gm, '')
    .replace(/^~{3,}[\s\S]*?^~{3,}/gm, '')
    .replace(/`[^`\n]+`/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/^\|.*\|[ \t]*$/gm, '')
    .replace(/^#{1,6}\s+.*$/gm, '')
    .replace(/^>\s*/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// ─── Sentence splitter (multilingual) ──────────────────────────────────────────
function splitSentences(prose, lang) {
  // CJK: no spaces, split directly on full-width terminators
  if (lang === 'zh' || lang === 'ja') {
    return prose
      .replace(/\n/g, '')
      .split(/(?<=[。！？!?])/)
      .map((s) => s.trim())
      .filter((s) => s.length >= 4);
  }
  const text = prose.replace(/\n/g, ' ');
  // split on . ! ? 。 ！ ？ ؟ … followed by space + (capital / digit / quote / Arabic / Cyrillic)
  const parts = text.split(
    /(?<=[.!?؟。！？…])\s+(?=[A-Z0-9"'«»Ѐ-ӿ؀-ۿ])/,
  );
  return parts
    .map((s) => s.trim())
    .filter((s) => s.split(/\s+/).filter(Boolean).length >= 3);
}

function wordCount(text) {
  return text.split(/\s+/).filter(Boolean).length;
}
function cjkLen(text) {
  return (text.match(/[一-鿿぀-ヿ]/g) || []).length;
}
function unitLen(s, lang) {
  return lang === 'zh' || lang === 'ja' ? cjkLen(s) : wordCount(s);
}

function cv(values) {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  if (mean === 0) return 0;
  const variance = values.reduce((a, l) => a + (l - mean) ** 2, 0) / values.length;
  return Math.sqrt(variance) / mean;
}

// ─── Metric computation ────────────────────────────────────────────────────────
export function analyze(text, lang, pack) {
  const prose = extractProse(text);
  const sentences = splitSentences(prose, lang);
  const lengths = sentences.map((s) => unitLen(s, lang));
  const totalWords = lang === 'zh' || lang === 'ja' ? cjkLen(prose) : wordCount(prose);

  const sentenceCV = round(cv(lengths), 3);

  // clause-level rhythm: long comma-chained human sentences (literary, encyclopedic,
  // CJK/Arabic waw-chains) have low sentence CV but high clause-length variance.
  // Splitting on clause punctuation recovers that variance so genuine human prose
  // is not mislabelled "robotically uniform". Effective CV = max(sentence, clause).
  const clauses = [];
  for (const s of sentences) {
    for (const c of s.split(/[,;:—–，、؛]/)) {
      const len = unitLen(c.trim(), lang);
      if (len >= 2) clauses.push(len);
    }
  }
  const clauseCV = round(cv(clauses), 3);

  const paragraphs = prose.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  const paraCV = round(cv(paragraphs.map((p) => unitLen(p, lang))), 3);

  // repeated n-gram rate (3..5 grams)
  const words = prose
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .filter(Boolean);
  let ngTotal = 0;
  let ngRepeat = 0;
  for (const n of [3, 4, 5]) {
    const seen = new Map();
    for (let i = 0; i + n <= words.length; i++) {
      const g = words.slice(i, i + n).join(' ');
      seen.set(g, (seen.get(g) || 0) + 1);
      ngTotal++;
    }
    for (const c of seen.values()) if (c > 1) ngRepeat += c - 1;
  }
  const ngramRepeatRate = ngTotal ? round(ngRepeat / ngTotal, 4) : 0;

  // transition density
  const transitions = pack?.transitions || [];
  const cjk = lang === 'zh' || lang === 'ja';
  let transHits = 0;
  for (const t of transitions) {
    const re = cjk
      ? new RegExp(escapeRe(t), 'g')
      : new RegExp(`(^|[\\s.,;:、，。])${escapeRe(t)}([\\s.,;:、，。]|$)`, 'giu');
    transHits += (prose.match(re) || []).length;
  }
  const transitionPer1000 = totalWords ? round((transHits / totalWords) * 1000, 1) : 0;

  // em/en dash density
  const dashCount = (prose.match(/[—–]/g) || []).length;
  const dashPer1000 = totalWords ? round((dashCount / totalWords) * 1000, 1) : 0;

  // marker hits from pack
  const markerHits = [];
  for (const m of pack?.fillers || []) {
    let re;
    try {
      re = new RegExp(m.re, (m.flags || '') + (m.flags?.includes('g') ? '' : 'g'));
    } catch (e) {
      if (process.env.UNROBOT_DEBUG) console.error(`bad marker regex /${m.re}/: ${e.message}`);
      continue;
    }
    const near = Array.isArray(m.near) && m.near.length
      ? new RegExp(m.near.map(escapeRe).join('|'), 'iu')
      : null;
    let mt;
    let count = 0;
    while ((mt = re.exec(prose)) !== null) {
      // context-gated marker: only count when a "near" word sits within 40 chars
      if (!near || near.test(prose.slice(Math.max(0, mt.index - 40), mt.index + mt[0].length + 40))) {
        count++;
      }
      if (re.lastIndex === mt.index) re.lastIndex++;
    }
    if (count > 0) markerHits.push({ label: m.label, severity: m.severity || 'WARN', count });
  }

  // triads "X, Y, and/or Z" — but a list of proper nouns (Germany, Austria, and
  // Hungary) is a factual enumeration, not the AI rule-of-three tell. Only count a
  // triad when at least one item starts lowercase (adjective / common-noun style).
  const triadWord = pack?.triadConjunctions || 'and|or';
  const triadRe = new RegExp(
    `(?<![\\p{L}])([\\p{L}][\\p{L}\\s-]{2,25}),\\s+([\\p{L}][\\p{L}\\s-]{2,25}),?\\s+(?:${triadWord})\\s+([\\p{L}][\\p{L}\\s-]{2,25})`,
    'giu',
  );
  let triads = 0;
  for (const m of prose.matchAll(triadRe)) {
    const items = [m[1], m[2], m[3]].map((x) => x.trim());
    const allProper = items.every((x) => /^\p{Lu}/u.test(x));
    if (!allProper) triads++;
  }

  // uniform bullet openers
  const bullets = prose.split('\n').filter((l) => /^[-*]\s+/.test(l));
  let maxOpener = 0;
  if (bullets.length >= THRESHOLDS.UNIFORM_OPENER_MIN) {
    const counts = new Map();
    for (const b of bullets) {
      const w = b.replace(/^[-*]\s+/, '').split(/\s+/)[0]?.toLowerCase() || '';
      if (w) counts.set(w, (counts.get(w) || 0) + 1);
    }
    maxOpener = Math.max(0, ...counts.values());
  }

  // repeated consecutive sentence openers
  let maxRunOpener = 0;
  let run = 0;
  let last = '';
  for (const s of sentences) {
    const w = (s.split(/\s+/)[0] || '').replace(/[^\p{L}]/gu, '').toLowerCase();
    if (w && w === last) {
      run++;
      maxRunOpener = Math.max(maxRunOpener, run);
    } else {
      last = w;
      run = 1;
    }
  }

  // typography tells
  const typo = {
    curlyQuotes: (text.match(/[‘’“”]/g) || []).length,
    ellipsis: (text.match(/…/g) || []).length,
    nbsp: (text.match(/ /g) || []).length,
  };

  return {
    lang,
    words: totalWords,
    sentenceCount: sentences.length,
    sentenceCV,
    clauseCV,
    effectiveCV: round(Math.max(sentenceCV, clauseCV), 3),
    meanSentence: round(lengths.reduce((a, b) => a + b, 0) / (lengths.length || 1), 1),
    paragraphCV: paraCV,
    paragraphCount: paragraphs.length,
    ngramRepeatRate,
    transitionPer1000,
    dashPer1000,
    triads,
    maxBulletOpener: maxOpener,
    maxRunOpener,
    markerHits,
    markerTotal: markerHits.reduce((a, m) => a + m.count, 0),
    typo,
  };
}

// ─── Scoring: fold metrics into humanScore 0-100 ───────────────────────────────
export function scoreOf(a) {
  let s = 100;
  const why = [];
  const T = THRESHOLDS;

  // burstiness — graded around the ideal band, on effective CV (max of sentence-
  // and clause-level variation) so long comma-chained human prose is not mislabelled.
  const ecv = a.effectiveCV ?? a.sentenceCV;
  if (ecv < T.CV_TOO_UNIFORM) {
    s -= 28; why.push(`effective CV ${ecv} < ${T.CV_TOO_UNIFORM} (robotically uniform)`);
  } else if (ecv < T.CV_FLAT) {
    s -= 15; why.push(`effective CV ${ecv} < ${T.CV_FLAT} (flat rhythm)`);
  } else if (ecv < T.CV_IDEAL_LO) {
    s -= 6; why.push(`effective CV ${ecv} below ideal band ${T.CV_IDEAL_LO} (still a touch even)`);
  } else if (ecv > T.CV_CHAOTIC) {
    s -= 8; why.push(`effective CV ${ecv} > ${T.CV_CHAOTIC} (unnaturally choppy)`);
  } else if (ecv > T.CV_IDEAL_HI) {
    s -= 3; why.push(`effective CV ${ecv} above ideal band ${T.CV_IDEAL_HI}`);
  }
  if (a.paragraphCount >= 3 && a.paragraphCV < T.PARA_CV_FLAT) {
    s -= 8; why.push(`paragraph CV ${a.paragraphCV} < ${T.PARA_CV_FLAT} (templated layout)`);
  }
  if (a.ngramRepeatRate > T.NGRAM_REPEAT_WARN) {
    s -= 8; why.push(`repeated n-grams ${(a.ngramRepeatRate * 100).toFixed(1)}%`);
  }
  if (a.transitionPer1000 > T.TRANSITION_PER_1000) {
    s -= 8; why.push(`transition density ${a.transitionPer1000}/1000w`);
  }
  if (a.dashPer1000 > T.EMDASH_PER_1000) {
    s -= 6; why.push(`em/en-dash density ${a.dashPer1000}/1000w`);
  }
  // marker hits: WARN -3 each (capped), ERROR -6 each
  for (const m of a.markerHits) {
    const per = m.severity === 'ERROR' ? 6 : 3;
    const pen = Math.min(per * m.count, per * 3);
    s -= pen; why.push(`marker "${m.label}" ×${m.count}`);
  }
  if (a.triads >= T.TRIAD_MIN) { s -= 5; why.push(`${a.triads} rule-of-three triads`); }
  if (a.maxBulletOpener >= T.UNIFORM_OPENER_MIN) { s -= 5; why.push(`${a.maxBulletOpener} bullets share opener`); }
  if (a.maxRunOpener >= T.REPEATED_OPENER_MIN) { s -= 5; why.push(`${a.maxRunOpener} sentences share opener`); }
  if (a.typo.curlyQuotes) { s -= 4; why.push(`${a.typo.curlyQuotes} curly quotes`); }
  if (a.typo.ellipsis) { s -= 2; why.push(`${a.typo.ellipsis} unicode ellipsis`); }
  if (a.typo.nbsp) { s -= 2; why.push(`${a.typo.nbsp} non-breaking spaces`); }

  return { humanScore: Math.max(0, Math.round(s)), why };
}

// ─── Factcheck: protected tokens in BEFORE must survive in AFTER ────────────────
export function extractProtectedTokens(text) {
  const tokens = new Set();
  const plain = text.replace(/^`{3,}[\s\S]*?^`{3,}/gm, '').replace(/`[^`\n]+`/g, '');
  for (const m of text.matchAll(/`([^`\n]+)`/g)) tokens.add(m[0]);
  for (const m of plain.matchAll(/\b0x[0-9a-fA-F]{2,}\b/g)) tokens.add(m[0]);
  for (const m of plain.matchAll(/https?:\/\/[^\s"'<>)]+/g)) tokens.add(m[0]);
  for (const m of plain.matchAll(/\b\d+(?:[.,]\d+)?\b/g)) tokens.add(m[0]);
  for (const m of plain.matchAll(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g)) tokens.add(m[0]);
  return [...tokens];
}
export function factDiff(before, after) {
  return extractProtectedTokens(before).filter((t) => !after.includes(t));
}

// ─── helpers ───────────────────────────────────────────────────────────────────
function round(n, d) { const f = 10 ** d; return Math.round(n * f) / f; }
function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

function walk(p, out) {
  const st = fs.statSync(p);
  if (st.isDirectory()) {
    for (const e of fs.readdirSync(p)) {
      if (e === 'node_modules' || e.startsWith('.')) continue;
      walk(path.join(p, e), out);
    }
  } else if (/\.(md|mdx|txt)$/i.test(p)) {
    out.push(p);
  }
}

// ─── CLI ───────────────────────────────────────────────────────────────────────
function parseArgs(argv) {
  const o = { files: [], json: false, factcheck: false, lang: null, markers: MARKERS_DEFAULT };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--json') o.json = true;
    else if (a === '--factcheck') o.factcheck = true;
    else if (a === '--lang') o.lang = argv[++i];
    else if (a === '--markers') o.markers = path.resolve(argv[++i]);
    else if (a === '--before') o.before = argv[++i];
    else if (a === '--after') o.after = argv[++i];
    else o.files.push(a);
  }
  return o;
}

function scoreFile(file, o) {
  const text = fs.readFileSync(file, 'utf-8');
  const lang = o.lang || frontmatterLang(text) || detectLang(text);
  const pack = loadPack(lang, o.markers) || loadPack('en', o.markers);
  const a = analyze(text, lang, pack);
  const sc = scoreOf(a);
  return { file, ...a, ...sc };
}

function main() {
  const o = parseArgs(process.argv.slice(2));

  if (o.factcheck) {
    if (!o.before || !o.after) { console.error('--factcheck needs --before and --after'); process.exit(2); }
    const missing = factDiff(fs.readFileSync(o.before, 'utf-8'), fs.readFileSync(o.after, 'utf-8'));
    if (o.json) { console.log(JSON.stringify({ before: o.before, after: o.after, missing }, null, 2)); }
    else if (missing.length === 0) console.log(`PASS factcheck: all protected tokens preserved`);
    else { console.log(`FACTCHECK FAIL: ${missing.length} token(s) lost/changed`); for (const t of missing) console.log(`  - ${t.length > 80 ? t.slice(0, 80) + '…' : t}`); }
    process.exit(missing.length ? 1 : 0);
  }

  const files = [];
  for (const f of o.files) {
    if (!fs.existsSync(f)) { console.error(`no such path: ${f}`); continue; }
    walk(f, files);
  }
  if (files.length === 0) { console.error('no files to score'); process.exit(2); }

  const results = files.map((f) => scoreFile(f, o)).sort((x, y) => x.humanScore - y.humanScore);

  if (o.json) { console.log(JSON.stringify(results, null, 2)); return; }

  for (const r of results) {
    const tag = r.humanScore >= 80 ? 'OK ' : r.humanScore >= 60 ? 'MEH' : 'BAD';
    console.log(`\n[${tag} ${r.humanScore}/100] ${r.file}  (${r.lang}, ${r.words}w, CV=${r.sentenceCV})`);
    for (const w of r.why) console.log(`   - ${w}`);
  }
  const avg = Math.round(results.reduce((a, r) => a + r.humanScore, 0) / results.length);
  console.log(`\n─────────────────────────────\nFiles: ${results.length}   Avg humanScore: ${avg}/100`);
}

if (import.meta.url === `file://${process.argv[1]}`) main();

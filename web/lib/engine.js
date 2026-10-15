// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// The arabic-normalize engine: the stages of docs/SPEC.md applied in a fixed order. A port of
// src/arabic_normalize/engine.py that gives the same text, offset map and change log (tested on every
// conformance fixture and on random strings against the Python package).
//
// Every stage produces edits on the current code-point array. In detailed mode the edits are composed into
// an offset map (output code point -> input span) and a change log; in plain mode only the text is built.
// Both modes run the same edit-finding code, so they always give the same text.
import { InputRejected } from './errors.js';
import { LIB_VERSION } from './generated/version.js';
import { loadPolicy } from './policy.js';
import { sha256Hex } from './sha256.js';
import * as U from './ucd.js';
import { encodeCodePoints, findInvalidUtf8, utf8Length } from './utf8.js';

export const MAX_TEXT_BYTES = 10 * 1024 * 1024;
export const MAX_RECORDS = 10000;
export const DEFAULT_POLICY = 'bayanat-norm-v1';

export const LOSSY_RULES = new Set([
  'alef_variants.map', 'alef_maqsura.to_yeh', 'taa_marbuta.to_heh', 'hamza_carriers.fold',
  'persian_urdu_letters.map', 'latin_case.lower', 'canonical_order.nfkc',
]);

function cps(...items) {
  const out = new Set();
  for (const r of items) {
    if (Array.isArray(r)) for (let c = r[0]; c <= r[1]; c++) out.add(c);
    else out.add(r);
  }
  return out;
}
const union = (...sets) => {
  const out = new Set();
  for (const s of sets) for (const c of s) out.add(c);
  return out;
};
const str = (a) => U.fromCodePoints(a);

// --- Character sets (docs/SPEC.md section 4) -------------------------------------------------------------
const SURROGATES = cps([0xD800, 0xDFFF]);
const ALLOWED_CONTROLS = new Set([...U.CONTROLS].filter((c) => U.WHITE_SPACE.has(c)));
const REJECT_CONTROLS = new Set([...U.CONTROLS].filter((c) => !ALLOWED_CONTROLS.has(c)));
const REJECT = union(SURROGATES, REJECT_CONTROLS, U.NONCHARACTERS);

const FORMAT_CONTROLS = cps(0x00AD, 0x2060, [0x2061, 0x2064], [0x206A, 0x206F], [0xFFF9, 0xFFFB]);
const BOM = 0xFEFF;

export const HONORIFIC = cps([0x0610, 0x0614], [0xFD40, 0xFD4F], 0xFDCF, [0xFDF0, 0xFDFF], [0x10ED1, 0x10ED8]);
export const PF = new Set([...cps([0xFB50, 0xFDFF], [0xFE70, 0xFEFF])]
  .filter((c) => U.COMPAT_DECOMPOSABLE.has(c) && !HONORIFIC.has(c)).sort((a, b) => a - b));
const PF_MAP = new Map([...PF].map((c) => [c, U.normalizeFormCps([c], 'NFKC')]));
const H_EXPAND = new Map([...HONORIFIC].sort((a, b) => a - b)
  .filter((c) => U.COMPAT_DECOMPOSABLE.has(c)).map((c) => [c, U.normalizeFormCps([c], 'NFKC')]));
const H_REMAIN = new Set([...HONORIFIC].filter((c) => !H_EXPAND.has(c)));

const ZWSP = 0x200B;
const ZWNJ = 0x200C;
const ZWJ = 0x200D;
const BIDI = U.BIDI_CONTROLS;
const BIDI_ZW = union(BIDI, [ZWSP, ZWNJ, ZWJ]);
const EMOJI_SKIP = union(U.EMOJI_MODIFIER, [0xFE0E, 0xFE0F], cps([0xE0020, 0xE007F]));

const TATWEEL = 0x0640;
const HARAKAT = cps([0x064B, 0x0652]);
const SHADDA = 0x0651;
const QURANIC = cps([0x0615, 0x061A], 0x0653, [0x0656, 0x0658], [0x06D6, 0x06ED], [0x0898, 0x089F],
  [0x08CA, 0x08E2], [0x08E3, 0x08E9], [0x08F0, 0x08F3], 0x08FF, [0x10EFD, 0x10EFF]);
const SUPERSCRIPT_ALEF = 0x0670;
const ALEF = 0x0627;
const ALEF_VARIANTS = cps(0x0622, 0x0623, 0x0625, 0x0671);
const HAMZA_MARKS = cps(0x0653, 0x0654, 0x0655);
const HAMZA_ABOVE = 0x0654;
const HAMZA_CARRIERS = new Map([[0x0624, 0x0648], [0x0626, 0x064A]]);
const HAMZA_BASES = cps(0x0648, 0x064A, 0x0649, 0x0624, 0x0626);
const ALEF_MAQSURA = 0x0649;
const YEH = 0x064A;
const TAA_MARBUTA = 0x0629;
const HEH = 0x0647;
const PERSIAN_URDU = new Map([[0x06CC, 0x064A], [0x06A9, 0x0643], [0x06C1, 0x0647], [0x06C2, 0x0647],
  [0x06BE, 0x0647], [0x06D5, 0x0647], [0x06C0, 0x0647]]);
const ARABIC_INDIC = cps([0x0660, 0x0669]);
const EXT_ARABIC_INDIC = cps([0x06F0, 0x06F9]);
const PUNCT_ASCII = new Map([[0x060C, ','], [0x061B, ';'], [0x061F, '?'], [0x066A, '%'], [0x066B, '.'],
  [0x066C, ','], [0x06D4, '.'], [0x066D, '*'], [0x00AB, '"'], [0x00BB, '"']]);

// Fast membership tables for the per-code-point scans.
const REJECT_T = new U.CpSet(REJECT);
const BIDI_ZW_T = new U.CpSet(BIDI_ZW);
const PF_T = new U.CpSet(PF);
const HONORIFIC_T = new U.CpSet(HONORIFIC);
const H_REMAIN_T = new U.CpSet(H_REMAIN);
const ALEF_TRIGGER_T = new U.CpSet(union(ALEF_VARIANTS, HAMZA_MARKS));
const HAMZA_TRIGGER_T = new U.CpSet(union(HAMZA_CARRIERS.keys(), [HAMZA_ABOVE]));
const WHITE_SPACE_T = new U.CpSet(U.WHITE_SPACE);
const MARKS_T = new U.CpSet(U.MARKS);

// --- Per-code-point map stages ------------------------------------------------------------------------
class MapStage {
  /** mapping: Map cp -> [replacement code points, rule id] */
  constructor(stage, mapping) {
    this.stage = stage;
    this.mapping = mapping;
    this.keys = new U.CpSet(mapping.keys());
  }

  run(ctx, s) {
    const keys = this.keys;
    let i = keys.find(s);
    if (i < 0) return s;
    const m = this.mapping;
    const edits = [];
    for (; i >= 0; i = keys.find(s, i + 1)) {
      const v = m.get(s[i]);
      edits.push([i, i + 1, v[0], v[1], null]);
    }
    return ctx.apply(s, edits, this.stage);
  }
}

/** One MapStage equal to applying `a` then `b` (both per-code-point maps); used in plain mode only. */
function composeMaps(a, b) {
  const mapping = new Map();
  for (const c of new Set([...a.mapping.keys(), ...b.mapping.keys()])) {
    const first = a.mapping.has(c) ? a.mapping.get(c)[0] : [c];
    const out = [];
    for (const x of first) {
      const v = b.mapping.get(x);
      if (v === undefined) out.push(x);
      else for (const y of v[0]) out.push(y);
    }
    if (!(out.length === 1 && out[0] === c)) mapping.set(c, [out, 'composed']);
  }
  return new MapStage('composed', mapping);
}

function mapStage(stage, codepoints, rep, rule) {
  const mapping = new Map();
  for (const c of codepoints) {
    const r = typeof rep === 'function' ? rep(c) : rep;
    mapping.set(c, [typeof r === 'string' ? U.toCodePoints(r) : r, rule]);
  }
  return new MapStage(stage, mapping);
}

const DIGITS_ASCII_SRC = union(ARABIC_INDIC, EXT_ARABIC_INDIC);
const STAGES = new Map([
  ['strip_controls/strip', new MapStage('strip_controls', new Map([
    ...[...FORMAT_CONTROLS].map((c) => [c, [[], 'strip_controls.format']]),
    [BOM, [[], 'strip_controls.bom']]]))],
  ['presentation_forms/map', mapStage('presentation_forms', PF, (c) => PF_MAP.get(c), 'presentation_forms.map')],
  ['ligatures_honorific/expand', mapStage('ligatures_honorific', H_EXPAND.keys(), (c) => H_EXPAND.get(c),
    'ligatures_honorific.expand')],
  ['tatweel/strip', mapStage('tatweel', [TATWEEL], '', 'tatweel.strip')],
  ['diacritics/strip', mapStage('diacritics', HARAKAT, '', 'diacritics.strip')],
  ['diacritics/strip-except-shadda', mapStage('diacritics', [...HARAKAT].filter((c) => c !== SHADDA), '',
    'diacritics.strip')],
  ['quranic_marks/strip', mapStage('quranic_marks', QURANIC, '', 'quranic_marks.strip')],
  ['superscript_alef/strip', mapStage('superscript_alef', [SUPERSCRIPT_ALEF], '', 'superscript_alef.strip')],
  ['superscript_alef/to-alef', mapStage('superscript_alef', [SUPERSCRIPT_ALEF], [ALEF], 'superscript_alef.to_alef')],
  ['alef_maqsura/to-yeh', mapStage('alef_maqsura', [ALEF_MAQSURA], [YEH], 'alef_maqsura.to_yeh')],
  ['taa_marbuta/to-heh', mapStage('taa_marbuta', [TAA_MARBUTA], [HEH], 'taa_marbuta.to_heh')],
  ['persian_urdu_letters/map', mapStage('persian_urdu_letters', PERSIAN_URDU.keys(), (c) => [PERSIAN_URDU.get(c)],
    'persian_urdu_letters.map')],
  ['digits/ascii', mapStage('digits', DIGITS_ASCII_SRC, (c) => [0x30 + (c & 0xF)], 'digits.to_ascii')],
  ['digits/arabic-indic', mapStage('digits', union(cps([0x30, 0x39]), EXT_ARABIC_INDIC),
    (c) => [0x0660 + (c <= 0x39 ? c - 0x30 : c - 0x06F0)], 'digits.to_arabic_indic')],
  ['punctuation/strip', mapStage('punctuation', U.PUNCTUATION, ' ', 'punctuation.strip')],
  ['punctuation/ascii', mapStage('punctuation', PUNCT_ASCII.keys(), (c) => PUNCT_ASCII.get(c), 'punctuation.to_ascii')],
  ['latin_case/lower', mapStage('latin_case', U.LATIN_LOWER.keys(), (c) => [U.LATIN_LOWER.get(c)], 'latin_case.lower')],
]);

// --- Context: offset map, change log, flags --------------------------------------------------------------
class Ctx {
  constructor(detailed, strict, n) {
    this.detailed = detailed;
    this.strict = strict;
    this.lo = null;
    this.hi = null;
    if (detailed) {
      this.lo = new Array(n);
      this.hi = new Array(n);
      for (let i = 0; i < n; i++) {
        this.lo[i] = i;
        this.hi[i] = i + 1;
      }
    }
    this.changes = [];
    this.flags = new Set();
    this.rejected = [];
  }

  /** Apply sorted, non-overlapping edits [start, end, replacementCps, ruleId, subSpans]. */
  apply(s, edits, stage) {
    if (edits.length === 0) return s;
    const out = [];
    let pos = 0;
    if (!this.detailed) {
      for (const e of edits) {
        for (let k = pos; k < e[0]; k++) out.push(s[k]);
        for (const c of e[2]) out.push(c);
        pos = e[1];
      }
      for (let k = pos; k < s.length; k++) out.push(s[k]);
      return out;
    }
    const { lo, hi } = this;
    const nlo = [];
    const nhi = [];
    for (const [i, j, rep, rule, sub] of edits) {
      for (let k = pos; k < i; k++) {
        out.push(s[k]);
        nlo.push(lo[k]);
        nhi.push(hi[k]);
      }
      let a = Infinity;
      let b = -Infinity;
      for (let k = i; k < j; k++) {
        if (lo[k] < a) a = lo[k];
        if (hi[k] > b) b = hi[k];
      }
      if (sub === null) {
        for (let k = 0; k < rep.length; k++) {
          nlo.push(a);
          nhi.push(b);
        }
      } else {
        for (const [x, y] of sub) {
          let p = Infinity;
          let q = -Infinity;
          for (let k = x; k < y; k++) {
            if (lo[k] < p) p = lo[k];
            if (hi[k] > q) q = hi[k];
          }
          nlo.push(p);
          nhi.push(q);
        }
      }
      for (const c of rep) out.push(c);
      this.changes.push({
        stage, rule_id: rule, src_start: a, src_end: b, before: U.fromCodePoints(s, i, j), after: str(rep),
        lossy: LOSSY_RULES.has(rule),
      });
      pos = j;
    }
    for (let k = pos; k < s.length; k++) {
      out.push(s[k]);
      nlo.push(lo[k]);
      nhi.push(hi[k]);
    }
    this.lo = nlo;
    this.hi = nhi;
    return out;
  }
}

// --- Context-sensitive stages ---------------------------------------------------------------------------
function rejectReason(cp) {
  if (cp >= 0xD800 && cp <= 0xDFFF) return 'lone_surrogate';
  if (REJECT_CONTROLS.has(cp)) return 'control';
  return 'noncharacter';
}

const hex4 = (cp) => cp.toString(16).toUpperCase().padStart(4, '0');

function stageReject(ctx, s, mode) {
  const first = REJECT_T.find(s);
  if (first < 0) return s;
  if (mode === 'error' || ctx.strict) {
    const cp = s[first];
    throw new InputRejected(rejectReason(cp), `U+${hex4(cp)} at index ${first}`, [first, first + 1]);
  }
  const edits = [];
  const rejected = ctx.rejected;
  for (let i = first; i >= 0; i = REJECT_T.find(s, i + 1)) {
    const reason = rejectReason(s[i]);
    edits.push([i, i + 1, [], `reject_invalid.${reason}`, null]);
    const last = rejected[rejected.length - 1];
    if (last && last.reason === reason && last.end === i) last.end = i + 1;
    else rejected.push({ start: i, end: i + 1, reason });
  }
  return ctx.apply(s, edits, 'reject_invalid');
}

// Code points skipped when looking for the letters around a ZWNJ (docs/SPEC.md 4.5). Policy-independent.
const CTX_SKIP_BASE = new Set([...U.JOINING].filter(([, t]) => t === 'T').map(([c]) => c));
for (const c of [ZWSP, ZWNJ, ZWJ, TATWEEL, ...QURANIC]) CTX_SKIP_BASE.add(c);
const CTX_SKIP = new Set(CTX_SKIP_BASE);
for (const [c, m] of PF_MAP) if (m.every((x) => CTX_SKIP_BASE.has(x))) CTX_SKIP.add(c);
// Presentation forms take the joining behaviour of the letters they map to.
const JT_PREV = new Map();
const JT_NEXT = new Map();
for (const [c, m] of PF_MAP) {
  const letters = m.filter((x) => !CTX_SKIP.has(x));
  JT_PREV.set(c, letters.length ? U.joiningType(letters[letters.length - 1]) : 'U');
  JT_NEXT.set(c, letters.length ? U.joiningType(letters[0]) : 'U');
}
const jtPrev = (cp) => (JT_PREV.has(cp) ? JT_PREV.get(cp) : U.joiningType(cp));
const jtNext = (cp) => (JT_NEXT.has(cp) ? JT_NEXT.get(cp) : U.joiningType(cp));

function viramaBefore(s, i) {
  for (let k = i - 1; k >= 0 && MARKS_T.has(s[k]); k--) if (U.ccc(s[k]) === 9) return true;
  return false;
}

/** For each position (sorted), the joining types of the nearest non-skipped code points before and after. */
function context(s, positions) {
  const before = new Map();
  let last = -1;
  let lastVal = null;
  for (const i of positions) {
    let k = i - 1;
    let val = null;
    let found = false;
    while (k > last) {
      const cp = s[k];
      if (!CTX_SKIP.has(cp)) {
        val = jtPrev(cp);
        found = true;
        break;
      }
      k -= 1;
    }
    if (!found) val = last >= 0 ? lastVal : null;
    before.set(i, val);
    last = i;
    lastVal = val;
  }
  const after = new Map();
  const n = s.length;
  last = n;
  lastVal = null;
  for (let p = positions.length - 1; p >= 0; p--) {
    const i = positions[p];
    let k = i + 1;
    let val = null;
    let found = false;
    while (k < last) {
      const cp = s[k];
      if (!CTX_SKIP.has(cp)) {
        val = jtNext(cp);
        found = true;
        break;
      }
      k += 1;
    }
    if (!found) val = last < n ? lastVal : null;
    after.set(i, val);
    last = i;
    lastVal = val;
  }
  return [before, after];
}

function zwjMeaningful(s, i) {
  if (viramaBefore(s, i)) return true;
  let k = i - 1;
  while (k >= 0 && EMOJI_SKIP.has(s[k])) k -= 1;
  if (k < 0 || !U.EXT_PICT.has(s[k])) return false;
  return i + 1 < s.length && U.EXT_PICT.has(s[i + 1]);
}

const JOIN_PREV_OK = new Set(['D', 'L', 'C']);
const JOIN_NEXT_OK = new Set(['D', 'R', 'C']);

function stageBidiZw(ctx, s, mode) {
  if (mode === 'keep') return s;
  const matches = [];
  for (let i = BIDI_ZW_T.find(s); i >= 0; i = BIDI_ZW_T.find(s, i + 1)) matches.push(i);
  if (matches.length === 0) return s;
  const keepZwnj = mode === 'strip-except-zwnj' || mode === 'strip-except-meaningful';
  const keepZwj = mode === 'strip-except-emoji-zwj' || mode === 'strip-except-meaningful';
  let before = new Map();
  let after = new Map();
  if (keepZwnj) {
    const zwnj = matches.filter((i) => s[i] === ZWNJ);
    if (zwnj.length) [before, after] = context(s, zwnj);
  }
  const edits = [];
  for (const i of matches) {
    const c = s[i];
    let rule;
    if (c === ZWNJ) {
      if (keepZwnj && (viramaBefore(s, i) || (JOIN_PREV_OK.has(before.get(i)) && JOIN_NEXT_OK.has(after.get(i))))) continue;
      rule = 'bidi_zw.zwnj';
    } else if (c === ZWJ) {
      if (keepZwj && zwjMeaningful(s, i)) continue;
      rule = 'bidi_zw.zwj';
    } else if (c === ZWSP) {
      rule = 'bidi_zw.zwsp';
    } else {
      rule = 'bidi_zw.bidi_control';
    }
    edits.push([i, i + 1, [], rule, null]);
  }
  return ctx.apply(s, edits, 'bidi_zw');
}

function sameCps(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

function stageCanonical(ctx, s, form, final) {
  if (form === 'none') return s;
  const edits = [];
  for (const [a, b, rep, sub] of U.normalizationEdits(s, form)) {
    let rule;
    if (final) rule = 'canonical_order.final';
    else if (form === 'NFKC' && !sameCps(U.normalizeFormCps(s.slice(a, b), 'NFC'), rep)) rule = 'canonical_order.nfkc';
    else rule = 'canonical_order.nfc';
    edits.push([a, b, rep, rule, sub]);
  }
  return ctx.apply(s, edits, 'canonical_order');
}

/** Base code point (nearest non-mark before) for each mark position; linear over runs of marks. */
function markBases(s, positions) {
  const bases = new Map();
  let prev = -1;
  let prevBase = null;
  for (const i of positions) {
    let k = i - 1;
    while (k > prev && MARKS_T.has(s[k])) k -= 1;
    let base;
    if (k === prev && prev >= 0) base = prevBase;
    else base = k >= 0 ? s[k] : null;
    bases.set(i, base);
    prev = i;
    prevBase = base;
  }
  return bases;
}

function stageAlef(ctx, s) {
  const matches = [];
  for (let i = ALEF_TRIGGER_T.find(s); i >= 0; i = ALEF_TRIGGER_T.find(s, i + 1)) matches.push(i);
  if (matches.length === 0) return s;
  const bases = markBases(s, matches.filter((i) => HAMZA_MARKS.has(s[i])));
  const edits = [];
  for (const i of matches) {
    if (ALEF_VARIANTS.has(s[i])) {
      edits.push([i, i + 1, [ALEF], 'alef_variants.map', null]);
    } else {
      const base = bases.get(i);
      if (base === ALEF || ALEF_VARIANTS.has(base)) edits.push([i, i + 1, [], 'alef_variants.map', null]);
    }
  }
  return ctx.apply(s, edits, 'alef_variants');
}

function stageHamza(ctx, s) {
  const matches = [];
  for (let i = HAMZA_TRIGGER_T.find(s); i >= 0; i = HAMZA_TRIGGER_T.find(s, i + 1)) matches.push(i);
  if (matches.length === 0) return s;
  const bases = markBases(s, matches.filter((i) => s[i] === HAMZA_ABOVE));
  const edits = [];
  for (const i of matches) {
    if (HAMZA_CARRIERS.has(s[i])) edits.push([i, i + 1, [HAMZA_CARRIERS.get(s[i])], 'hamza_carriers.fold', null]);
    else if (HAMZA_BASES.has(bases.get(i))) edits.push([i, i + 1, [], 'hamza_carriers.fold', null]);
  }
  return ctx.apply(s, edits, 'hamza_carriers');
}

function stageWhitespace(ctx, s) {
  const edits = [];
  const n = s.length;
  let i = WHITE_SPACE_T.find(s);
  while (i >= 0 && i < n) {
    let j = i + 1;
    while (j < n && WHITE_SPACE_T.has(s[j])) j += 1;
    if (i === 0 || j === n) edits.push([i, j, [], 'whitespace.collapse', null]);
    else if (!(j - i === 1 && s[i] === 0x20)) edits.push([i, j, [0x20], 'whitespace.collapse', null]);
    i = j < n ? WHITE_SPACE_T.find(s, j) : -1;
  }
  return ctx.apply(s, edits, 'whitespace');
}

const FLAG = Symbol('flag');

function flagStep(flag, test) {
  const step = (ctx, s) => {
    if (ctx.detailed && test(s)) ctx.flags.add(flag);
    return s;
  };
  step[FLAG] = true;
  return step;
}

const PLANS = new Map();

/**
 * The ordered steps for a policy (docs/SPEC.md section 3). In plain mode the flag checks are dropped and
 * adjacent per-code-point maps are merged into one table, as in the Python engine; both plans give the same
 * text (tested).
 */
function plan(policy, detailed) {
  const cacheKey = `${policy.policy_hash}/${detailed ? 'd' : 'p'}`;
  let cached = PLANS.get(cacheKey);
  if (cached !== undefined) return cached;
  const st = policy.stages;
  let steps = [(ctx, s) => stageReject(ctx, s, st.reject_invalid)];
  const add = (key) => {
    const stage = STAGES.get(key);
    if (stage) steps.push(stage);
  };
  if (st.strip_controls === 'strip') add('strip_controls/strip');
  if (st.presentation_forms === 'map') add('presentation_forms/map');
  else if (st.presentation_forms === 'flag') steps.push(flagStep('presentation_forms.flag', (s) => PF_T.find(s) >= 0));
  if (st.ligatures_honorific === 'expand') {
    add('ligatures_honorific/expand');
    steps.push(flagStep('ligatures_honorific.flag', (s) => H_REMAIN_T.find(s) >= 0));
  } else if (st.ligatures_honorific === 'flag') {
    steps.push(flagStep('ligatures_honorific.flag', (s) => HONORIFIC_T.find(s) >= 0));
  }
  steps.push((ctx, s) => stageBidiZw(ctx, s, st.bidi_zw));
  const form = policy.unicode_form;
  steps.push((ctx, s) => stageCanonical(ctx, s, form, false));
  for (const stage of ['tatweel', 'diacritics', 'quranic_marks', 'superscript_alef']) add(`${stage}/${st[stage]}`);
  if (st.alef_variants === 'map') steps.push(stageAlef);
  if (st.alef_maqsura === 'to-yeh') add('alef_maqsura/to-yeh');
  else if (st.alef_maqsura === 'flag') steps.push(flagStep('alef_maqsura.flag', (s) => s.includes(ALEF_MAQSURA)));
  if (st.taa_marbuta === 'to-heh') add('taa_marbuta/to-heh');
  else if (st.taa_marbuta === 'flag') steps.push(flagStep('taa_marbuta.flag', (s) => s.includes(TAA_MARBUTA)));
  if (st.hamza_carriers === 'fold') steps.push(stageHamza);
  for (const stage of ['persian_urdu_letters', 'digits', 'punctuation']) add(`${stage}/${st[stage]}`);
  if (st.whitespace === 'collapse') steps.push(stageWhitespace);
  if (st.latin_case === 'lower') add('latin_case/lower');
  if (form !== 'none') steps.push((ctx, s) => stageCanonical(ctx, s, 'NFC', true));
  if (!detailed) {
    const merged = [];
    for (const step of steps) {
      if (step[FLAG]) continue;
      const last = merged[merged.length - 1];
      if (step instanceof MapStage && last instanceof MapStage) merged[merged.length - 1] = composeMaps(last, step);
      else merged.push(step);
    }
    steps = merged;
  }
  cached = steps.map((step) => (step instanceof MapStage ? (ctx, s) => step.run(ctx, s) : step));
  PLANS.set(cacheKey, cached);
  return cached;
}

function run(cpsIn, policy, detailed, strict) {
  const ctx = new Ctx(detailed, strict, cpsIn.length);
  let s = cpsIn;
  for (const step of plan(policy, detailed)) s = step(ctx, s);
  return [s, ctx];
}

// --- Public API ------------------------------------------------------------------------------------------
function checkText(text) {
  if (typeof text !== 'string') {
    throw new InputRejected('text_not_string', `expected str, got ${text === null ? 'null' : typeof text}`);
  }
  const c = U.toCodePoints(text);
  if (c.length * 4 > MAX_TEXT_BYTES) {
    const nbytes = utf8Length(c);
    if (nbytes > MAX_TEXT_BYTES) {
      throw new InputRejected('over_cap_bytes', `${nbytes} UTF-8 bytes; the cap is ${MAX_TEXT_BYTES}`);
    }
  }
  return c;
}

/**
 * Normalise `text` with `policy` (built-in id, policy object or Policy) and return the string.
 * @param {string} text
 * @param {string|object} [policy]
 * @param {{strict?: boolean}} [options]
 */
export function normalize(text, policy = DEFAULT_POLICY, { strict = false } = {}) {
  const c = checkText(text);
  const p = loadPolicy(policy);
  return U.fromCodePoints(run(c, p, false, strict)[0]);
}

function countIn(arr, set) {
  let n = 0;
  for (const c of arr) if (set.has(c)) n += 1;
  return n;
}

function inputStatsCps(c) {
  const expanded = [];
  for (const x of c) {
    const m = PF_MAP.get(x);
    if (m === undefined) expanded.push(x);
    else for (const y of m) expanded.push(y);
  }
  const letters = countIn(expanded, U.ARABIC_LETTERS);
  const harakat = countIn(expanded, HARAKAT);
  let sup = 0;
  let taa = 0;
  let maq = 0;
  for (const x of expanded) {
    if (x === SUPERSCRIPT_ALEF) sup += 1;
    else if (x === TAA_MARBUTA) taa += 1;
    else if (x === ALEF_MAQSURA) maq += 1;
  }
  const classes = {
    arabic_letters: letters,
    harakat,
    superscript_alef: sup,
    taa_marbuta: taa,
    alef_maqsura: maq,
    presentation_forms: countIn(c, PF),
    honorific_ligatures: countIn(c, HONORIFIC),
    rejected: countIn(c, REJECT),
  };
  const ratio = letters ? (harakat + sup) / letters : 0.0;
  return [classes, ratio];
}

/** Policy-independent input counts and the diacritization ratio (docs/SPEC.md section 5). */
export function inputStats(text) {
  return inputStatsCps(U.toCodePoints(text));
}

const sortStrings = (arr) => [...arr].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));

/**
 * Normalise `text` and return the detailed result: the same object as Python's Result.to_dict()
 * (schemas/output.schema.json): text_norm, offset_map, changes, lossy_flags, flags, diacritization_ratio,
 * rejected_spans, stats, policy_id, policy_hash, lib_version, unicode_version, original_hash, text_diac.
 */
export function normalizeDetailed(text, policy = DEFAULT_POLICY, { strict = false } = {}) {
  const c = checkText(text);
  const p = loadPolicy(policy);
  const [out, ctx] = run(c, p, true, strict);
  const [classes, ratio] = inputStatsCps(c);
  const ruleCounts = {};
  for (const ch of ctx.changes) ruleCounts[ch.rule_id] = (ruleCounts[ch.rule_id] || 0) + 1;
  const rules = {};
  for (const k of sortStrings(Object.keys(ruleCounts))) rules[k] = ruleCounts[k];
  let textDiac = null;
  if (classes.harakat || classes.superscript_alef) {
    textDiac = U.fromCodePoints(run(c, loadPolicy('raw-safe-v1'), false, false)[0]);
  }
  const offsetMap = ctx.lo.map((lo, i) => [lo, ctx.hi[i]]);
  return {
    original_hash: sha256Hex(encodeCodePoints(c)),
    text_norm: U.fromCodePoints(out),
    text_diac: textDiac,
    policy_id: p.policy_id,
    policy_hash: p.policy_hash,
    lib_version: LIB_VERSION,
    unicode_version: U.UNICODE_VERSION,
    changes: ctx.changes,
    offset_map: offsetMap,
    lossy_flags: sortStrings(new Set(ctx.changes.filter((x) => x.lossy).map((x) => x.rule_id))),
    flags: sortStrings(ctx.flags),
    diacritization_ratio: ratio,
    stats: { rules, classes },
    rejected_spans: ctx.rejected.map((r) => ({ ...r })),
  };
}

/** Sorted unique rule ids in a detailed result's change log (Python: Result.rules). */
export function ruleIds(result) {
  return sortStrings(new Set(result.changes.map((x) => x.rule_id)));
}

/** Strict UTF-8 decoding; throws InputRejected('invalid_utf8') with the byte offset. */
export function decodeUtf8(bytes) {
  if (!(bytes instanceof Uint8Array)) throw new InputRejected('invalid_request', 'expected a Uint8Array');
  if (bytes.length > MAX_TEXT_BYTES) {
    throw new InputRejected('over_cap_bytes', `${bytes.length} bytes; the cap is ${MAX_TEXT_BYTES}`);
  }
  const bad = findInvalidUtf8(bytes);
  if (bad) throw new InputRejected('invalid_utf8', `byte offset ${bad.start}: ${bad.reason}`, [bad.start, bad.end]);
  return new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
}

/** Decode strict UTF-8 (a BOM is handled by strip_controls), then normalise. */
export function normalizeBytes(bytes, policy = DEFAULT_POLICY, { strict = false, detailed = false } = {}) {
  const text = decodeUtf8(bytes);
  return detailed ? normalizeDetailed(text, policy, { strict }) : normalize(text, policy, { strict });
}

/** Parse one JSONL line and return [record, text]. Throws InputRejected with a contract reason. */
export function parseRecord(line, field = 'text') {
  let rec;
  try {
    rec = JSON.parse(line);
  } catch (e) {
    throw new InputRejected('invalid_json', String(e.message || e));
  }
  if (rec === null || typeof rec !== 'object' || Array.isArray(rec)) {
    throw new InputRejected('invalid_json', 'a JSONL record must be a JSON object');
  }
  if (!Object.prototype.hasOwnProperty.call(rec, field)) {
    throw new InputRejected('missing_text_field', `record has no '${field}' field`);
  }
  const text = rec[field];
  if (typeof text !== 'string') {
    throw new InputRejected('text_not_string', `field '${field}' is ${text === null ? 'null' : typeof text}, not a string`);
  }
  return [rec, text];
}

/**
 * Apply the input contract (schemas/input.schema.json) to one request and return a list of results.
 * request: {text} or {texts: [...]}, optional policy (id or inline object), detailed, strict.
 */
export function normalizeRequest(request) {
  if (request === null || typeof request !== 'object' || Array.isArray(request)) {
    throw new InputRejected('invalid_request', 'a request must be a JSON object');
  }
  const unknown = Object.keys(request).filter((k) => !['text', 'texts', 'policy', 'detailed', 'strict'].includes(k));
  if (unknown.length) throw new InputRejected('unknown_member', `unknown request member(s): ${sortStrings(unknown).join(', ')}`);
  const hasText = Object.prototype.hasOwnProperty.call(request, 'text');
  const hasTexts = Object.prototype.hasOwnProperty.call(request, 'texts');
  if (hasText === hasTexts) throw new InputRejected('invalid_request', "give exactly one of 'text' or 'texts'");
  const texts = hasText ? [request.text] : request.texts;
  if (!Array.isArray(texts)) throw new InputRejected('invalid_request', "'texts' must be a list");
  if (texts.length > MAX_RECORDS) {
    throw new InputRejected('over_cap_records', `${texts.length} records; the cap is ${MAX_RECORDS}`);
  }
  const p = loadPolicy(Object.prototype.hasOwnProperty.call(request, 'policy') ? request.policy : DEFAULT_POLICY);
  const strict = Boolean(request.strict);
  for (const t of texts) checkText(t);
  if (request.detailed) return texts.map((t) => normalizeDetailed(t, p, { strict }));
  return texts.map((t) => normalize(t, p, { strict }));
}

/** Compare two policies on one text: outputs, rules only one of them applies, and differing source regions. */
export function diffPolicies(text, policyA, policyB) {
  const ra = normalizeDetailed(text, policyA);
  const rb = normalizeDetailed(text, policyB);
  const regions = [...ra.changes, ...rb.changes].map((c) => [c.src_start, c.src_end]);
  regions.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
  const merged = [];
  for (const [lo, hi] of regions) {
    const last = merged[merged.length - 1];
    if (last && lo <= last[1]) last[1] = Math.max(last[1], hi);
    else merged.push([lo, hi]);
  }
  const cpsA = U.toCodePoints(ra.text_norm);
  const cpsB = U.toCodePoints(rb.text_norm);
  const piece = (res, c, lo, hi) => {
    const out = [];
    for (let i = 0; i < c.length; i++) {
      const sp = res.offset_map[i];
      if (sp && sp[0] < hi && sp[1] > lo) out.push(c[i]);
    }
    return U.fromCodePoints(out);
  };
  const src = U.toCodePoints(text);
  const diffs = [];
  for (const [lo, hi] of merged) {
    const a = piece(ra, cpsA, lo, hi);
    const b = piece(rb, cpsB, lo, hi);
    if (a !== b) diffs.push({ src_start: lo, src_end: hi, source: U.fromCodePoints(src, lo, hi), a, b });
  }
  const rulesA = new Set(ruleIds(ra));
  const rulesB = new Set(ruleIds(rb));
  return {
    policy_a: ra.policy_id, policy_hash_a: ra.policy_hash, text_a: ra.text_norm,
    policy_b: rb.policy_id, policy_hash_b: rb.policy_hash, text_b: rb.text_norm,
    identical: ra.text_norm === rb.text_norm,
    rules_only_a: sortStrings([...rulesA].filter((r) => !rulesB.has(r))),
    rules_only_b: sortStrings([...rulesB].filter((r) => !rulesA.has(r))),
    lossy_flags_a: ra.lossy_flags, lossy_flags_b: rb.lossy_flags,
    regions: diffs,
  };
}

/** The text_diac field: raw-safe-v1 output when the input carries harakat or superscript alef, else null. */
export function textDiac(text) {
  const [classes] = inputStats(text);
  if (classes.harakat || classes.superscript_alef) return normalize(text, 'raw-safe-v1');
  return null;
}

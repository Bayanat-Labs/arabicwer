// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// Pinned Unicode data (UCD 18.0.0) and a span-tracking implementation of UAX #15 normalisation.
// A line-by-line port of src/arabic_normalize/_ucd.py. String.prototype.normalize is never used, so the
// output does not depend on the ICU version of the JavaScript engine.
//
// Text is handled as arrays of code points (numbers). Offsets are code-point indices, as in the Python
// package and docs/SPEC.md section 1.
import DATA from './generated/ucd-data.js';

export const UNICODE_VERSION = DATA.unicode_version;

// --- Decoding the compact tables (format arabic-normalize-js-ucd-1, see scripts/build.mjs) -------------
function decodeRanges(a) {
  const out = [];
  let cur = 0;
  for (let i = 0; i < a.length; i += 2) {
    const lo = cur + a[i];
    const hi = lo + a[i + 1];
    out.push([lo, hi]);
    cur = hi;
  }
  return out;
}

function rangesToSet(ranges, into = new Set()) {
  for (const [lo, hi] of ranges) for (let c = lo; c <= hi; c++) into.add(c);
  return into;
}

function decodePairs(a, relative) {
  const out = new Map();
  let cur = 0;
  for (let i = 0; i < a.length; i += 2) {
    cur += a[i];
    out.set(cur, relative ? cur + a[i + 1] : a[i + 1]);
  }
  return out;
}

function decodeDecomp(a) {
  const out = new Map();
  let cur = 0;
  let i = 0;
  while (i < a.length) {
    cur += a[i];
    const n = a[i + 1];
    out.set(cur, a.slice(i + 2, i + 2 + n));
    i += 2 + n;
  }
  return out;
}

function decodeSorted(a) {
  const out = [];
  let cur = 0;
  for (const d of a) {
    cur += d;
    out.push(cur);
  }
  return out;
}

const GC_LO = [];
const GC_HI = [];
const GC_CAT = [];
{
  let cur = 0;
  const a = DATA.gc_ranges;
  for (let i = 0; i < a.length; i += 3) {
    const lo = cur + a[i];
    const hi = lo + a[i + 1];
    GC_LO.push(lo);
    GC_HI.push(hi);
    GC_CAT.push(DATA.gc_cats[a[i + 2]]);
    cur = hi;
  }
}

/** Decoded tables in the same shape as the Python ucd_tables.json (used by the tests). */
export function decodedTables() {
  const r = {};
  for (const [k, v] of Object.entries(DATA.ranges)) r[k] = decodeRanges(v);
  r.joining_type = Object.fromEntries(Object.entries(DATA.joining_type).map(([k, v]) => [k, decodeRanges(v)]));
  r.gc_ranges = GC_LO.map((lo, i) => [lo, GC_HI[i], GC_CAT[i]]);
  r.ccc = [...decodePairs(DATA.ccc, false)];
  r.latin_lower = [...decodePairs(DATA.latin_lower, true)];
  r.compat_decomposable = decodeSorted(DATA.compat_decomposable);
  r.nfd = [...decodeDecomp(DATA.nfd)].map(([k, v]) => [k, ...v]);
  r.nfkd = [...decodeDecomp(DATA.nfkd)].map(([k, v]) => [k, ...v]);
  const c = DATA.compose;
  r.compose = [];
  for (let i = 0; i < c.length; i += 3) r.compose.push([c[i], c[i + 1], c[i + 2]]);
  r.unicode_version = DATA.unicode_version;
  r.source = DATA.source;
  r.source_sha256 = DATA.source_sha256;
  r.license = DATA.license;
  return r;
}

// --- General category (binary search over ranges) -------------------------------------------------------
export function generalCategory(cp) {
  let lo = 0;
  let hi = GC_LO.length - 1;
  let idx = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (GC_LO[mid] <= cp) {
      idx = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  if (idx >= 0 && cp <= GC_HI[idx]) return GC_CAT[idx];
  return 'Cn';
}

function gcSet(prefixes) {
  const out = new Set();
  for (let i = 0; i < GC_LO.length; i++) {
    const cat = GC_CAT[i];
    if (prefixes.some((p) => cat.startsWith(p))) for (let c = GC_LO[i]; c <= GC_HI[i]; c++) out.add(c);
  }
  return out;
}

export const MARKS = gcSet(['Mn', 'Mc', 'Me']);
export const CONTROLS = gcSet(['Cc']);
export const PUNCTUATION = gcSet(['P']);
export const WHITE_SPACE = rangesToSet(decodeRanges(DATA.ranges.white_space));
export const NONCHARACTERS = rangesToSet(decodeRanges(DATA.ranges.noncharacter));
export const BIDI_CONTROLS = rangesToSet(decodeRanges(DATA.ranges.bidi_control));
export const SCRIPT_ARABIC = rangesToSet(decodeRanges(DATA.ranges.script_arabic));
export const SCRIPT_LATIN = rangesToSet(decodeRanges(DATA.ranges.script_latin));
// Arabic letters: General_Category Lo and Script=Arabic (docs/SPEC.md section 1).
export const ARABIC_LETTERS = new Set([...SCRIPT_ARABIC].filter((c) => generalCategory(c) === 'Lo'));
export const EXT_PICT = rangesToSet(decodeRanges(DATA.ranges.extended_pictographic));
export const EMOJI_MODIFIER = rangesToSet(decodeRanges(DATA.ranges.emoji_modifier));
export const JOINING = new Map();
for (const [t, enc] of Object.entries(DATA.joining_type)) {
  for (const [lo, hi] of decodeRanges(enc)) for (let c = lo; c <= hi; c++) JOINING.set(c, t);
}
export const LATIN_LOWER = decodePairs(DATA.latin_lower, true);
export const COMPAT_DECOMPOSABLE = new Set(decodeSorted(DATA.compat_decomposable));

export function joiningType(cp) {
  const t = JOINING.get(cp);
  return t === undefined ? 'U' : t;
}

// --- Normalisation data -----------------------------------------------------------------------------
export const CCC = decodePairs(DATA.ccc, false);
const NFD = decodeDecomp(DATA.nfd);
const NFKD = decodeDecomp(DATA.nfkd);
const COMPOSE = new Map();
{
  const c = DATA.compose;
  for (let i = 0; i < c.length; i += 3) COMPOSE.set(c[i] * 0x110000 + c[i + 1], c[i + 2]);
}
const QC_NOT_YES = {
  NFC: rangesToSet(decodeRanges(DATA.ranges.nfc_qc_maybe), rangesToSet(decodeRanges(DATA.ranges.nfc_qc_no))),
  NFKC: rangesToSet(decodeRanges(DATA.ranges.nfkc_qc_maybe), rangesToSet(decodeRanges(DATA.ranges.nfkc_qc_no))),
};

const S_BASE = 0xAC00;
const L_BASE = 0x1100;
const V_BASE = 0x1161;
const T_BASE = 0x11A7;
const L_COUNT = 19;
const V_COUNT = 21;
const T_COUNT = 28;
const N_COUNT = V_COUNT * T_COUNT;
const S_COUNT = L_COUNT * N_COUNT;

export function ccc(cp) {
  const v = CCC.get(cp);
  return v === undefined ? 0 : v;
}

function decomposeCp(cp, compat) {
  if (cp >= S_BASE && cp < S_BASE + S_COUNT) {
    const s = cp - S_BASE;
    const out = [L_BASE + Math.floor(s / N_COUNT), V_BASE + Math.floor((s % N_COUNT) / T_COUNT)];
    const t = s % T_COUNT;
    if (t) out.push(T_BASE + t);
    return out;
  }
  const d = (compat ? NFKD : NFD).get(cp);
  return d === undefined ? null : d;
}

function composePair(a, b) {
  if (a >= L_BASE && a < L_BASE + L_COUNT && b >= V_BASE && b < V_BASE + V_COUNT) {
    return S_BASE + ((a - L_BASE) * V_COUNT + (b - V_BASE)) * T_COUNT;
  }
  if (a >= S_BASE && a < S_BASE + S_COUNT && (a - S_BASE) % T_COUNT === 0 && b > T_BASE && b < T_BASE + T_COUNT) {
    return a + (b - T_BASE);
  }
  const c = COMPOSE.get(a * 0x110000 + b);
  return c === undefined ? null : c;
}

/** items: array of [cp, lo, hi] (source span [lo, hi)). Returns the normalised array of [cp, lo, hi]. */
function normalizeItems(items, form) {
  const compat = form === 'NFKC' || form === 'NFKD';
  let dec = [];
  for (const [cp, lo, hi] of items) {
    const d = decomposeCp(cp, compat);
    if (d === null) dec.push([cp, lo, hi]);
    else for (const x of d) dec.push([x, lo, hi]);
  }
  // Canonical ordering: stable sort of each run of non-starters by combining class.
  const n = dec.length;
  let i = 0;
  while (i < n) {
    if (ccc(dec[i][0]) === 0) {
      i += 1;
      continue;
    }
    let j = i;
    while (j < n && ccc(dec[j][0]) !== 0) j += 1;
    if (j - i > 1) {
      const run = dec.slice(i, j).sort((x, y) => ccc(x[0]) - ccc(y[0])); // Array.prototype.sort is stable
      for (let k = 0; k < run.length; k++) dec[i + k] = run[k];
    }
    i = j;
  }
  if (form === 'NFD' || form === 'NFKD' || dec.length === 0) return dec;
  // Canonical composition (UAX #15 reference algorithm), exactly as in _ucd.py.
  const out = [dec[0]];
  let starter = 0;
  let lastClass = ccc(dec[0][0]);
  if (lastClass !== 0) lastClass = 256;
  for (let k = 1; k < dec.length; k++) {
    const [cp, lo, hi] = dec[k];
    const cls = ccc(cp);
    const comp = composePair(out[starter][0], cp);
    if (comp !== null && (lastClass < cls || lastClass === 0)) {
      const s = out[starter];
      out[starter] = [comp, Math.min(s[1], lo), Math.max(s[2], hi)];
      continue;
    }
    if (cls === 0) starter = out.length;
    lastClass = cls;
    out.push([cp, lo, hi]);
  }
  return out;
}

const FORMS = new Map();

function formData(form) {
  let fd = FORMS.get(form);
  if (fd === undefined) {
    let unstable;
    if (form === 'NFC' || form === 'NFKC') {
      unstable = new Set([...QC_NOT_YES[form], ...CCC.keys()]);
    } else if (form === 'NFD' || form === 'NFKD') {
      unstable = new Set([...(form === 'NFD' ? NFD : NFKD).keys(), ...CCC.keys()]);
      for (let c = S_BASE; c < S_BASE + S_COUNT; c++) unstable.add(c);
    } else {
      throw new Error(`unknown normalisation form ${form}`);
    }
    fd = { form, unstable: new CpSet(unstable) };
    FORMS.set(form, fd);
  }
  return fd;
}

function quickYes(s, a, b, form) {
  if (form !== 'NFC' && form !== 'NFKC') return false;
  const qc = QC_NOT_YES[form];
  let last = 0;
  for (let i = a; i < b; i++) {
    const cp = s[i];
    if (qc.has(cp)) return false;
    const cls = ccc(cp);
    if (cls !== 0 && last > cls) return false;
    last = cls;
  }
  return true;
}

/**
 * Edits [start, end, replacementCps, subSpans] that bring the code-point array `s` to `form`.
 * subSpans gives, for each replacement code point, the span [lo, hi) of positions in `s` it came from.
 * Chunks start at a stable code point (combining class 0 and Quick_Check=Yes), so chunks are independent.
 */
export function normalizationEdits(s, form) {
  const { unstable } = formData(form);
  const edits = [];
  const n = s.length;
  let lastEnd = -1;
  for (let k = unstable.find(s); k >= 0 && k < n; k = unstable.find(s, k + 1)) {
    if (k < lastEnd) continue;
    let a = k;
    while (a > 0 && unstable.has(s[a])) a -= 1;
    let b = k + 1;
    while (b < n && unstable.has(s[b])) b += 1;
    if (a < lastEnd) a = lastEnd; // cannot happen (chunks are maximal), kept as a guard as in _ucd.py
    lastEnd = b;
    if (quickYes(s, a, b, form)) continue;
    const items = [];
    for (let i = a; i < b; i++) items.push([s[i], i, i + 1]);
    const res = normalizeItems(items, form);
    let same = res.length === b - a;
    if (same) {
      for (let i = 0; i < res.length; i++) {
        if (res[i][0] !== s[a + i]) {
          same = false;
          break;
        }
      }
    }
    if (!same) edits.push([a, b, res.map((e) => e[0]), res.map((e) => [e[1], e[2]])]);
  }
  return edits;
}

/** Plain NFC, NFD, NFKC or NFKD of a code-point array using the pinned tables. */
export function normalizeFormCps(s, form) {
  const edits = normalizationEdits(s, form);
  if (edits.length === 0) return s;
  const out = [];
  let pos = 0;
  for (const [a, b, rep] of edits) {
    for (let i = pos; i < a; i++) out.push(s[i]);
    for (const c of rep) out.push(c);
    pos = b;
  }
  for (let i = pos; i < s.length; i++) out.push(s[i]);
  return out;
}

// --- Strings and code points ------------------------------------------------------------------------
/** Code points of a JavaScript string. A lone surrogate becomes its own code point (0xD800..0xDFFF). */
export function toCodePoints(str) {
  const out = new Array(str.length);
  let n = 0;
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i);
    if (c >= 0xD800 && c <= 0xDBFF && i + 1 < str.length) {
      const d = str.charCodeAt(i + 1);
      if (d >= 0xDC00 && d <= 0xDFFF) {
        out[n++] = (c - 0xD800) * 0x400 + (d - 0xDC00) + 0x10000;
        i += 1;
        continue;
      }
    }
    out[n++] = c;
  }
  out.length = n;
  return out;
}

/** String from code points (a lone surrogate code point gives a lone UTF-16 surrogate). */
export function fromCodePoints(cps, start = 0, end = cps.length) {
  let s = '';
  const CHUNK = 4096;
  for (let i = start; i < end; i += CHUNK) {
    const j = Math.min(end, i + CHUNK);
    const units = [];
    for (let k = i; k < j; k++) {
      const c = cps[k];
      if (c > 0xFFFF) {
        const v = c - 0x10000;
        units.push(0xD800 + (v >> 10), 0xDC00 + (v & 0x3FF));
      } else {
        units.push(c);
      }
    }
    s += String.fromCharCode.apply(null, units);
  }
  return s;
}

/** Plain NFC, NFD, NFKC or NFKD of a string with the pinned UCD 18.0.0 tables. */
export function normalizeForm(str, form) {
  return fromCodePoints(normalizeFormCps(toCodePoints(str), form));
}

// --- Fast membership tests ---------------------------------------------------------------------------
/** A code-point set with a typed-array table for the BMP (fast) and a Set for astral code points. */
export class CpSet {
  constructor(codepoints) {
    this.bmp = new Uint8Array(0x10000);
    this.astral = new Set();
    for (const c of codepoints) {
      if (c < 0x10000) this.bmp[c] = 1;
      else this.astral.add(c);
    }
  }

  has(c) {
    return c < 0x10000 ? this.bmp[c] === 1 : this.astral.has(c);
  }

  /** Index of the first member in s (from `from`), or -1. */
  find(s, from = 0) {
    const bmp = this.bmp;
    const astral = this.astral.size > 0 ? this.astral : null;
    for (let i = from; i < s.length; i++) {
      const c = s[i];
      if (c < 0x10000 ? bmp[c] === 1 : astral !== null && astral.has(c)) return i;
    }
    return -1;
  }
}

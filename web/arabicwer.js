// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// arabicwer in JavaScript: the same scoring policies, word split, alignment and measures as the Python
// package (spec/SPEC.md, arabicwer-spec-1). Normalisation uses the JavaScript port of arabic-normalize in
// ./lib, which gives the same output as the Python library. No network access, no dependencies.
import { loadPolicy as loadNormaliser, normalize as normalizeText, policyHash } from './lib/index.js';
import { POLICY_DATA } from './policies.js';

export const VERSION = '0.1.0';
export const SPEC_ID = 'arabicwer-spec-1';
export const NAMESPACE = 'arabicwer-1';
export const DEFAULT_POLICY = 'lenient';
export const MAX_CELLS = 50000000;

// Unicode White_Space=Yes (rule T01).
const WS = new Set([0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x20, 0x85, 0xa0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004,
  0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000]);

/** Rule T01: words are maximal runs of code points that are not White_Space. */
export function splitWords(text) {
  const out = [];
  let cur = '';
  for (const ch of text) {
    if (WS.has(ch.codePointAt(0))) {
      if (cur) { out.push(cur); cur = ''; }
    } else {
      cur += ch;
    }
  }
  if (cur) out.push(cur);
  return out;
}

export class ScoringPolicy {
  constructor(data) {
    if (!data || typeof data !== 'object') throw new Error('a policy must be an object');
    if (data.spec !== SPEC_ID) throw new Error(`spec must be ${SPEC_ID}`);
    this.data = data;
    this.policy_id = data.policy_id;
    this.name = data.name;
    this.sha256 = policyHash(data);
    this.norm = data.normaliser === null ? null : loadNormaliser(data.normaliser);
    Object.freeze(this);
  }

  words(text) {
    if (typeof text !== 'string') throw new TypeError('expected a string');
    return splitWords(this.norm === null ? text : normalizeText(text, this.norm));
  }

  normalise(text) {
    return this.words(text).join(' ');
  }
}

const BUILTIN = new Map();
for (const d of POLICY_DATA) BUILTIN.set(d.name, new ScoringPolicy(d));
export const POLICY_NAMES = POLICY_DATA.map((d) => d.name);

export function listPolicies() {
  return POLICY_NAMES.map((n) => BUILTIN.get(n));
}

export function loadPolicy(p = DEFAULT_POLICY) {
  if (p instanceof ScoringPolicy) return p;
  if (typeof p === 'string') {
    const name = p.startsWith(NAMESPACE + '/') ? p.slice(NAMESPACE.length + 1) : p;
    if (BUILTIN.has(name)) return BUILTIN.get(name);
    throw new Error(`unknown policy '${p}'`);
  }
  return new ScoringPolicy(p);
}

/**
 * Rule A01: Levenshtein alignment with unit costs. Backtrace from the end of both sequences, taking the
 * first step on a minimal path in this order: hit, insertion, deletion, substitution.
 * Returns one operation per step: 'equal', 'substitute', 'delete' or 'insert'.
 */
export function editOps(ref, hyp) {
  const n = ref.length;
  const m = hyp.length;
  if ((n + 1) * (m + 1) > MAX_CELLS) throw new Error(`a ${n} x ${m} alignment is over the limit of ${MAX_CELLS} cells`);
  const ids = new Map();
  const id = (t) => { let v = ids.get(t); if (v === undefined) { v = ids.size; ids.set(t, v); } return v; };
  const r = Int32Array.from(ref, id);
  const h = Int32Array.from(hyp, id);
  const w = m + 1;
  const D = new Int32Array((n + 1) * w);
  for (let j = 0; j <= m; j++) D[j] = j;
  for (let i = 1; i <= n; i++) {
    const row = i * w;
    const prev = row - w;
    D[row] = i;
    const ri = r[i - 1];
    for (let j = 1; j <= m; j++) {
      let best = D[prev + j - 1] + (ri !== h[j - 1] ? 1 : 0);
      const del = D[prev + j] + 1;
      if (del < best) best = del;
      const ins = D[row + j - 1] + 1;
      if (ins < best) best = ins;
      D[row + j] = best;
    }
  }
  const ops = [];
  let i = n;
  let j = m;
  while (i > 0 || j > 0) {
    const here = D[i * w + j];
    if (i > 0 && j > 0 && r[i - 1] === h[j - 1] && here === D[(i - 1) * w + j - 1]) {
      ops.push('equal'); i--; j--;
    } else if (j > 0 && here === D[i * w + j - 1] + 1) {
      ops.push('insert'); j--;
    } else if (i > 0 && here === D[(i - 1) * w + j] + 1) {
      ops.push('delete'); i--;
    } else {
      ops.push('substitute'); i--; j--;
    }
  }
  return ops.reverse();
}

function counts(ops) {
  let s = 0; let d = 0; let ins = 0; let hits = 0;
  for (const t of ops) {
    if (t === 'equal') hits++;
    else if (t === 'substitute') s++;
    else if (t === 'delete') d++;
    else ins++;
  }
  return [hits, s, d, ins];
}

/** Alignment chunks [type, refStart, refEnd, hypStart, hypEnd], as in the Python package. */
export function chunks(ops) {
  const out = [];
  let i = 0; let j = 0; let k = 0;
  while (k < ops.length) {
    const t = ops[k];
    const i0 = i; const j0 = j;
    while (k < ops.length && ops[k] === t) {
      if (t !== 'insert') i++;
      if (t !== 'delete') j++;
      k++;
    }
    out.push([t, i0, i, j0, j]);
  }
  return out;
}

const rate = (e, n) => (n === 0 ? null : e / n);

/** Per-pair record, field for field the same as arabicwer.score_pair in Python. */
export function scorePair(reference, hypothesis, policy = DEFAULT_POLICY, { alignment = false } = {}) {
  const pol = loadPolicy(policy);
  const rw = pol.words(reference);
  const hw = pol.words(hypothesis);
  const ops = editOps(rw, hw);
  const [, s, d, i] = counts(ops);
  const rn = rw.join(' ');
  const hn = hw.join(' ');
  const rc = Array.from(rn);
  const hc = Array.from(hn);
  const [, cs, cd, ci] = counts(editOps(rc, hc));
  const out = {
    ref_norm: rn, hyp_norm: hn,
    S: s, D: d, I: i, N: rw.length, wer: rate(s + d + i, rw.length),
    cS: cs, cD: cd, cI: ci, cN: rc.length, cer: rate(cs + cd + ci, rc.length),
  };
  if (alignment) out.alignment = chunks(ops);
  return out;
}

/** Word alignment of one pair as [{op, ref, hyp}] for the diff view. */
export function diffTokens(reference, hypothesis, policy = DEFAULT_POLICY) {
  const pol = loadPolicy(policy);
  const rw = pol.words(reference);
  const hw = pol.words(hypothesis);
  const out = [];
  let i = 0; let j = 0;
  for (const op of editOps(rw, hw)) {
    out.push({ op, ref: op === 'insert' ? null : rw[i], hyp: op === 'delete' ? null : hw[j] });
    if (op !== 'insert') i++;
    if (op !== 'delete') j++;
  }
  return out;
}

/** Corpus totals per policy for [{id, ref, hyp}] pairs, plus the per-pair records. */
export function scorePairs(pairs, policies = POLICY_NAMES) {
  const pols = policies.map(loadPolicy);
  const rows = pairs.map((p) => ({ pair_id: p.id, scores: {} }));
  const summary = pols.map((pol) => {
    let S = 0; let D = 0; let I = 0; let N = 0; let cS = 0; let cD = 0; let cI = 0; let cN = 0; let empty = 0;
    const pw = [];
    pairs.forEach((p, k) => {
      const rec = scorePair(p.ref, p.hyp, pol);
      rows[k].scores[pol.policy_id] = rec;
      S += rec.S; D += rec.D; I += rec.I; N += rec.N;
      cS += rec.cS; cD += rec.cD; cI += rec.cI; cN += rec.cN;
      if (rec.N === 0) empty++; else pw.push(rec.wer);
    });
    return {
      policy_id: pol.policy_id, name: pol.name, policy_sha256: pol.sha256,
      words: { substitutions: S, deletions: D, insertions: I, hits: N - S - D, reference_units: N, wer: rate(S + D + I, N),
        mean_pair_wer: pw.length ? pw.reduce((a, b) => a + b, 0) / pw.length : null },
      characters: { substitutions: cS, deletions: cD, insertions: cI, hits: cN - cS - cD, reference_units: cN,
        cer: rate(cS + cD + cI, cN) },
      empty_references: empty,
    };
  });
  const vals = summary.filter((e) => e.words.wer !== null);
  let swing = null;
  if (vals.length >= 2) {
    const hi = vals.reduce((a, b) => (b.words.wer > a.words.wer ? b : a));
    const lo = vals.reduce((a, b) => (b.words.wer < a.words.wer ? b : a));
    swing = { max: hi.words.wer, max_policy: hi.policy_id, min: lo.words.wer, min_policy: lo.policy_id,
      swing: hi.words.wer - lo.words.wer };
  }
  return { arabicwer_version: VERSION, spec: SPEC_ID, pairs_total: pairs.length, policies: summary, swing: { wer: swing }, pairs: rows };
}

// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// One scoring request, shared by the Web Worker and the main-thread fallback. Input
// {mode: 'paste', ref, hyp} or {mode: 'tsv', text}, plus diffPolicy; output {report, diffs} or {error}.
// Nothing is stored: the input lives only in this call.
import { POLICY_NAMES, diffTokens, scorePairs } from './arabicwer.js';

export const MAX_BYTES = 10 * 1024 * 1024;
export const MAX_PAIRS = 10000;
export const MAX_CODE_POINTS = 5000; // per side of one pair (the character alignment grows with the square)
export const MAX_DIFFS = 200;

const lines = (s) => {
  const out = s.replace(/^﻿/, '').split('\n').map((l) => (l.endsWith('\r') ? l.slice(0, -1) : l));
  if (out.length && out[out.length - 1] === '') out.pop();
  return out;
};

function fail(reason, detail = {}) {
  return { error: { reason, ...detail } };
}

export function parse({ mode, ref, hyp, text }) {
  if (mode === 'tsv') {
    const rows = [];
    const ls = lines(text);
    for (let n = 0; n < ls.length; n++) {
      const cols = ls[n].split('\t');
      if (n === 0 && ['id,reference,hypothesis', 'reference,hypothesis'].includes(cols.map((c) => c.trim().toLowerCase()).join(','))) continue;
      if (cols.length === 3) rows.push({ id: cols[0], ref: cols[1], hyp: cols[2] });
      else if (cols.length === 2) rows.push({ id: String(n + 1), ref: cols[0], hyp: cols[1] });
      else return fail('bad_tsv_line', { line: n + 1, columns: cols.length });
    }
    return { pairs: rows };
  }
  const r = lines(ref);
  const h = lines(hyp);
  if (r.length !== h.length) return fail('line_count', { ref: r.length, hyp: h.length });
  return { pairs: r.map((x, k) => ({ id: String(k + 1), ref: x, hyp: h[k] })) };
}

export function compute(req) {
  try {
    const bytes = new TextEncoder().encode((req.ref || '') + (req.hyp || '') + (req.text || '')).length;
    if (bytes > MAX_BYTES) return fail('too_large', { bytes });
    const parsed = parse(req);
    if (parsed.error) return parsed;
    const { pairs } = parsed;
    if (pairs.length === 0) return fail('empty');
    if (pairs.length > MAX_PAIRS) return fail('too_many', { pairs: pairs.length });
    for (const p of pairs) {
      if ([...p.ref].length > MAX_CODE_POINTS || [...p.hyp].length > MAX_CODE_POINTS) return fail('too_long', { id: p.id });
    }
    const report = scorePairs(pairs, POLICY_NAMES);
    report.pairs.forEach((row, k) => { row.ref_raw = pairs[k].ref; row.hyp_raw = pairs[k].hyp; });
    const dp = req.diffPolicy || 'lenient';
    const diffs = pairs.slice(0, MAX_DIFFS).map((p) => ({ id: p.id, tokens: diffTokens(p.ref, p.hyp, dp) }));
    return { report, diffs, diffPolicy: dp };
  } catch (e) {
    return fail('error', { message: String(e && e.message ? e.message : e) });
  }
}

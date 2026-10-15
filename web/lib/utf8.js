// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// UTF-8 helpers that match the Python package byte for byte:
// - encodeCodePoints() encodes lone surrogates as three bytes, like Python's 'surrogatepass' handler
//   (used for original_hash and the 10 MiB cap);
// - decodeUtf8Strict() rejects what Python's strict UTF-8 decoder rejects and reports the same byte offset.

/** UTF-8 byte length of a code-point array (lone surrogates count three bytes). */
export function utf8Length(cps) {
  let n = 0;
  for (const c of cps) n += c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4;
  return n;
}

/** UTF-8 bytes of a code-point array; lone surrogates are encoded as with Python's 'surrogatepass'. */
export function encodeCodePoints(cps) {
  const out = new Uint8Array(utf8Length(cps));
  let i = 0;
  for (const c of cps) {
    if (c < 0x80) {
      out[i++] = c;
    } else if (c < 0x800) {
      out[i++] = 0xC0 | (c >> 6);
      out[i++] = 0x80 | (c & 0x3F);
    } else if (c < 0x10000) {
      out[i++] = 0xE0 | (c >> 12);
      out[i++] = 0x80 | ((c >> 6) & 0x3F);
      out[i++] = 0x80 | (c & 0x3F);
    } else {
      out[i++] = 0xF0 | (c >> 18);
      out[i++] = 0x80 | ((c >> 12) & 0x3F);
      out[i++] = 0x80 | ((c >> 6) & 0x3F);
      out[i++] = 0x80 | (c & 0x3F);
    }
  }
  return out;
}

/**
 * Strict UTF-8 validation. Returns null when `bytes` is valid, else {start, end, reason} for the first
 * invalid sequence, with the offsets and reasons CPython's decoder reports.
 */
export function findInvalidUtf8(bytes) {
  const n = bytes.length;
  let i = 0;
  while (i < n) {
    const b = bytes[i];
    if (b < 0x80) {
      i += 1;
      continue;
    }
    let need;
    let lo = 0x80;
    let hi = 0xBF;
    if (b >= 0xC2 && b <= 0xDF) need = 1;
    else if (b === 0xE0) { need = 2; lo = 0xA0; }
    else if (b >= 0xE1 && b <= 0xEC) need = 2;
    else if (b === 0xED) { need = 2; hi = 0x9F; }
    else if (b >= 0xEE && b <= 0xEF) need = 2;
    else if (b === 0xF0) { need = 3; lo = 0x90; }
    else if (b >= 0xF1 && b <= 0xF3) need = 3;
    else if (b === 0xF4) { need = 3; hi = 0x8F; }
    else return { start: i, end: i + 1, reason: 'invalid start byte' };
    for (let k = 1; k <= need; k++) {
      if (i + k >= n) return { start: i, end: n, reason: 'unexpected end of data' };
      const c = bytes[i + k];
      const okLo = k === 1 ? lo : 0x80;
      const okHi = k === 1 ? hi : 0xBF;
      if (c < okLo || c > okHi) return { start: i, end: i + k, reason: 'invalid continuation byte' };
    }
    i += need + 1;
  }
  return null;
}

# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Compute the expected values of the fixtures, independently of the arabicwer package.

This script does not import arabicwer. It reads the policy files as plain JSON, normalises with
arabic-normalize directly, splits words with its own white-space table, and aligns with its own minimal
Levenshtein implementation (full matrix, same tie-break rule as spec/SPEC.md rule A01). It also checks:
  * the edit distance against RapidFuzz on every pair;
  * the designed word-error counts written with each fixture (``design_word_errors``);
then writes ``expected`` into each fixture and refreshes fixtures/SHA256SUMS.

Usage: python scripts/make_expected.py fixtures/dev.jsonl [fixtures/acceptance.jsonl ...] [--check]
With --check nothing is written; the run fails if a stored expected value differs.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

import arabic_normalize
from rapidfuzz.distance import Levenshtein

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_DIR = os.path.join(ROOT, "src", "arabicwer", "policies")
ORDER = ["raw", "nfc", "dediac", "strict-orth", "bayanat-norm-v1", "lenient"]
WS = set(chr(c) for c in [*range(0x09, 0x0E), 0x20, 0x85, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029,
                          0x202F, 0x205F, 0x3000])


def load_policies():
    pols = {}
    for name in ORDER:
        with open(os.path.join(POLICY_DIR, name + ".json"), encoding="utf-8") as f:
            data = json.load(f)
        norm = data["normaliser"]
        pols[name] = None if norm is None else arabic_normalize.load_policy(norm)
    return pols


def words(text, norm):
    if norm is not None:
        text = arabic_normalize.normalize(text, norm)
    out, cur = [], []
    for ch in text:
        if ch in WS:
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def levenshtein_ops(a, b):
    """Full-matrix Levenshtein; backtrace from the end: hit, insertion, deletion, substitution."""
    n, m = len(a), len(b)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + (0 if a[i - 1] == b[j - 1] else 1), d[i - 1][j] + 1, d[i][j - 1] + 1)
    s = dl = ins = 0
    i, j = n, m
    while i or j:
        if i and j and a[i - 1] == b[j - 1] and d[i][j] == d[i - 1][j - 1]:
            i, j = i - 1, j - 1
        elif j and d[i][j] == d[i][j - 1] + 1:
            ins, j = ins + 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            dl, i = dl + 1, i - 1
        else:
            s, i, j = s + 1, i - 1, j - 1
    assert s + dl + ins == d[n][m]
    return s, dl, ins, d[n][m]


def expected_for(ref, hyp, norm):
    rw, hw = words(ref, norm), words(hyp, norm)
    s, dl, ins, dist = levenshtein_ops(rw, hw)
    ids = {}
    assert dist == Levenshtein.distance([ids.setdefault(w, len(ids)) for w in rw],
                                        [ids.setdefault(w, len(ids)) for w in hw]), "word distance mismatch"
    rn, hn = " ".join(rw), " ".join(hw)
    cs, cd, ci, cdist = levenshtein_ops(rn, hn)
    assert cdist == Levenshtein.distance(rn, hn), "character distance mismatch"
    n, cn = len(rw), len(rn)
    return {"ref_norm": rn, "hyp_norm": hn, "S": s, "D": dl, "I": ins, "N": n,
            "wer": None if n == 0 else (s + dl + ins) / n,
            "cS": cs, "cD": cd, "cI": ci, "cN": cn, "cer": None if cn == 0 else (cs + cd + ci) / cn}


INVISIBLE = {c for c in range(0x10000) if chr(c) in "­؜​‌‍‎‏‪‫‬"
             "‭‮⁠⁦⁧⁨⁩﻿"}


def dumps(rec):
    """JSON line with invisible characters written as \\u escapes, so the files can be read and reviewed."""
    s = json.dumps(rec, ensure_ascii=False)
    return "".join(f"\\u{ord(c):04x}" if ord(c) in INVISIBLE else c for c in s)


def main(argv):
    check = "--check" in argv
    files = [a for a in argv if not a.startswith("--")]
    pols = load_policies()
    bad = 0
    for path in files:
        recs = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        for r in recs:
            exp = {name: expected_for(r["ref"], r["hyp"], pols[name]) for name in ORDER}
            for name, want in r.get("design_word_errors", {}).items():
                got = exp[name]["S"] + exp[name]["D"] + exp[name]["I"]
                if got != want:
                    bad += 1
                    print(f"{r['fixture_id']}: design says {want} word errors under {name}, computed {got}: "
                          f"{exp[name]['ref_norm']!r} / {exp[name]['hyp_norm']!r}")
            if check and r.get("expected") != exp:
                bad += 1
                print(f"{r['fixture_id']}: stored expected values differ")
            r["expected"] = exp
        if not check and not bad:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                for r in recs:
                    f.write(dumps(r) + "\n")
        print(f"{path}: {len(recs)} fixtures")
    if not check and not bad:
        fx = os.path.join(ROOT, "fixtures")
        lines = []
        for p in sorted(glob.glob(os.path.join(fx, "*.jsonl"))):
            with open(p, "rb") as f:
                lines.append(f"{hashlib.sha256(f.read()).hexdigest()}  {os.path.basename(p)}\n")
        with open(os.path.join(fx, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as f:
            f.writelines(lines)
    if bad:
        print(f"{bad} problem(s)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

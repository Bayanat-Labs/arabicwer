# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Write random Arabic/Latin pairs scored by the Python package, for scripts/crosscheck.mjs.

Usage: python scripts/crosscheck_random.py OUT.json [--n 1000] [--seed 0]
"""
import argparse
import json
import random
import sys

import arabicwer
from arabicwer.report import score_pair

LETTERS = list("ابتثجحخدذرسشصضطظعغفقكلمنهويءآأإؤئىةپچکی") + list("abcdefxyzABCXYZ")
MARKS = ["ً", "َ", "ُ", "ِ", "ّ", "ْ", "ٰ", "ـ"]
OTHER = list("٠١٢٣٤٥٦٧٨٩0123456789۱۲۳،؛؟.,!:«»-") + ["‌", "‏", "ﻻ", "ﷺ", " ", "\t"]


def rand_text(rng):
    words = []
    for _ in range(rng.randint(0, 10)):
        w = []
        for _ in range(rng.randint(1, 7)):
            r = rng.random()
            if r < 0.7:
                w.append(rng.choice(LETTERS))
            elif r < 0.85:
                w.append(rng.choice(MARKS))
            else:
                w.append(rng.choice(OTHER))
        words.append("".join(w))
    return rng.choice([" ", " ", " ", "  "]).join(words)


def mutate(rng, text):
    words = text.split(" ")
    out = []
    for w in words:
        r = rng.random()
        if r < 0.1:
            continue
        if r < 0.2:
            out.append(rand_text(rng))
        out.append(w if rng.random() < 0.7 else rand_text(rng))
    return " ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    pairs = []
    for k in range(a.n):
        ref = rand_text(rng)
        hyp = mutate(rng, ref)
        scores = {p.policy_id: score_pair(ref, hyp, p, alignment=True) for p in arabicwer.list_policies()}
        pairs.append({"id": f"random-{k:04d}", "ref": ref, "hyp": hyp, "scores": scores})
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"arabicwer_version": arabicwer.__version__, "seed": a.seed, "pairs": pairs}, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())

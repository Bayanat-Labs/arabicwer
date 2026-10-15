# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Under the raw policy, WER and CER equal jiwer 4.0.0 on 10,000 random Arabic/Latin pairs."""
import random

import pytest

import arabicwer

jiwer = pytest.importorskip("jiwer")

LETTERS = "ابتثجحخدذرسشصضطظعغفقكلمنهويءآأإؤئىة" + "abcdefghijklmnopqrstuvwxyz" + "َُِّ"


def pairs(n, seed=0):
    rng = random.Random(seed)
    vocab = ["".join(rng.choice(LETTERS) for _ in range(rng.randint(1, 6))) for _ in range(300)]
    out = []
    for _ in range(n):
        ref = [rng.choice(vocab) for _ in range(rng.randint(1, 15))]
        hyp = [w if rng.random() < 0.7 else rng.choice(vocab) for w in ref if rng.random() < 0.9]
        hyp += [rng.choice(vocab) for _ in range(rng.randint(0, 2))]
        rng.shuffle(hyp) if rng.random() < 0.05 else None
        out.append((" ".join(ref), " ".join(hyp)))
    return out


PAIRS = pairs(10000)


def test_wer_parity_10000():
    worst = max(abs(arabicwer.wer(r, h, "raw") - jiwer.wer(r, h)) for r, h in PAIRS)
    assert worst < 1e-12


def test_cer_parity_10000():
    worst = max(abs(arabicwer.cer(r, h, "raw") - jiwer.cer(r, h)) for r, h in PAIRS)
    assert worst < 1e-12


def test_corpus_parity():
    refs, hyps = zip(*PAIRS[:2000])
    assert abs(arabicwer.wer(list(refs), list(hyps), "raw") - jiwer.wer(list(refs), list(hyps))) < 1e-12
    assert abs(arabicwer.cer(list(refs), list(hyps), "raw") - jiwer.cer(list(refs), list(hyps))) < 1e-12


def test_alignment_distance_parity():
    for r, h in PAIRS[:2000]:
        a = arabicwer.process_words(r, h, "raw")
        j = jiwer.process_words(r, h)
        assert a.substitutions + a.deletions + a.insertions == j.substitutions + j.deletions + j.insertions
        assert a.wer == pytest.approx(j.wer, abs=1e-12)


def test_jiwer_transform():
    for name in arabicwer.POLICY_NAMES:
        t = arabicwer.jiwer_transform(name)
        tc = arabicwer.jiwer_transform(name, unit="char")
        for r, h in [("ذَهَبَ الوَلَدُ إِلَى المَدْرَسَةِ", "ذهب الولد الى المدرسه"), ("مرحبا، كيف حالك؟", "مرحبا كيف حالك")]:
            assert jiwer.wer(r, h, reference_transform=t, hypothesis_transform=t) == arabicwer.wer(r, h, name)
            assert jiwer.cer(r, h, reference_transform=tc, hypothesis_transform=tc) == arabicwer.cer(r, h, name)

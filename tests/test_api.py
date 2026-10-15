# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
import json
import random

import pytest
from rapidfuzz.distance import Levenshtein

import arabic_normalize
import arabicwer
from arabicwer import align
from arabicwer.policy import PolicyError, load_policy



def test_readme_example():
    assert arabicwer.wer("ذهب الولد إلى المدرسة", "ذهب الولد الى المدرسه") == 0.0
    assert arabicwer.wer("ذهب الولد إلى المدرسة", "ذهب الولد الى المدرسه", policy="raw") == 0.5


def test_policy_names_and_ids():
    ids = [p.policy_id for p in arabicwer.list_policies()]
    assert ids == [f"arabicwer-1/{n}" for n in arabicwer.POLICY_NAMES]
    for p in arabicwer.list_policies():
        assert load_policy(p.policy_id) is p
        assert load_policy(p.name) is p
        assert len(p.sha256) == 64


def test_policy_hashes_are_frozen():
    from conftest import ROOT
    with open(f"{ROOT}/spec/policy_hashes.json", encoding="utf-8") as f:
        frozen = json.load(f)
    assert {p.policy_id: p.sha256 for p in arabicwer.list_policies()} == frozen


def test_bayanat_norm_v1_follows_arabic_normalize():
    p = load_policy("bayanat-norm-v1")
    upstream = arabic_normalize.load_policy("bayanat-norm-v1").data["stages"]
    mine = p.data["normaliser"]["stages"]
    changed = {k for k in upstream if upstream[k] != mine[k]}
    assert changed == set(p.meta["derived_from"]["changed_stages"])
    assert p.meta["derived_from"]["sha256"] == arabic_normalize.policy_hash(arabic_normalize.load_policy("bayanat-norm-v1").data)


def test_custom_policy_and_reserved_ids():
    data = json.loads(load_policy("lenient").to_json())
    data["normaliser"]["stages"]["taa_marbuta"] = "keep"
    with pytest.raises(PolicyError):
        load_policy(data)  # reuses a built-in id with other behaviour
    data["policy_id"] = "my-lab/lenient-keep-taa"
    p = load_policy(data)
    assert p.sha256 != load_policy("lenient").sha256
    assert arabicwer.wer("مدرسة", "مدرسه", p) == 1.0
    bad = dict(data, **{"$ref": "x"})
    with pytest.raises(PolicyError):
        load_policy(bad)
    with pytest.raises(PolicyError):
        load_policy("no-such-policy")


def test_empty_reference_rules():
    w = arabicwer.process_words(["", "a b"], ["x y", "a b"], "raw")
    assert w.pair_rates == [None, 0.0]
    assert w.insertions == 2 and w.reference_units == 2 and w.wer == 1.0
    assert arabicwer.wer("", "x", "raw") is None
    assert arabicwer.wer("", "", "raw") is None
    with pytest.raises(ValueError):
        arabicwer.wer(["a"], ["a", "b"])


def test_alignment_matches_rapidfuzz_distance():
    rng = random.Random(1)
    for _ in range(3000):
        a = [rng.randint(0, 5) for _ in range(rng.randint(0, 12))]
        b = [rng.randint(0, 5) for _ in range(rng.randint(0, 12))]
        ops = align.edit_ops(a, b)
        h, s, d, i = align.counts(ops)
        assert s + d + i == Levenshtein.distance(a, b)
        assert h + s + d == len(a) and h + s + i == len(b)
        ch = align.chunks(ops)
        assert sum(c.ref_end_idx - c.ref_start_idx for c in ch if c.type != "insert") == len(a)


def test_tie_break_rule():
    assert align.edit_ops("a b".split(), "b c".split()) == ["delete", "equal", "insert"]
    assert align.edit_ops("x y z".split(), "x q y z".split()) == ["equal", "insert", "equal", "equal"]
    assert align.edit_ops("a b".split(), "c d".split()) == ["substitute", "substitute"]


def test_score_pairs_report():
    rep = arabicwer.score_pairs([("1", "مرحبا بكم", "مرحبا بكم"), ("2", "إلى المدرسة", "الي المدرسه")], bootstrap=50)
    names = [e["name"] for e in rep["policies"]]
    assert names == list(arabicwer.POLICY_NAMES)
    raw = rep["policies"][0]
    assert raw["words"]["wer"] == 0.5 and raw["bootstrap"]["resamples"] == 50
    assert rep["swing"]["wer"]["swing"] == 0.5
    assert rep["swing"]["wer"]["max_policy"] == "arabicwer-1/raw"


def test_diff_tokens():
    t = arabicwer.diff_tokens("ذهب الولد إلى المدرسة", "ذهب ولد الى المدرسه اليوم", "strict-orth")
    assert [x["op"] for x in t] == ["equal", "substitute", "substitute", "substitute", "insert"]

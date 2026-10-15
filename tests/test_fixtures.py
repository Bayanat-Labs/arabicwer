# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Every fixture (dev and acceptance) under every policy gives exactly its frozen expected values."""
import hashlib
import os

import pytest

import arabicwer
from arabicwer.report import score_pair

from conftest import ROOT, load_fixtures

FIXTURES = load_fixtures()
CASES = [(fx, name) for fx in FIXTURES for name in arabicwer.POLICY_NAMES]


@pytest.mark.parametrize("fx,name", CASES, ids=[f"{fx['fixture_id']}-{n}" for fx, n in CASES])
def test_fixture(fx, name):
    assert score_pair(fx["ref"], fx["hyp"], name) == fx["expected"][name]


def test_fixture_counts_and_fields():
    dev = [f for f in FIXTURES if f["split"] == "dev"]
    assert len(dev) == 120
    assert len({f["fixture_id"] for f in FIXTURES}) == len(FIXTURES)
    for f in FIXTURES:
        assert f["synthetic"] is True and f["original"] is True
        assert set(f["expected"]) == set(arabicwer.POLICY_NAMES)


def test_sha256sums():
    with open(os.path.join(ROOT, "fixtures", "SHA256SUMS"), encoding="utf-8") as f:
        for line in f:
            digest, name = line.split()
            with open(os.path.join(ROOT, "fixtures", name), "rb") as g:
                assert hashlib.sha256(g.read()).hexdigest() == digest, name


def test_wer_cer_functions_match_records():
    for fx in FIXTURES:
        for name in arabicwer.POLICY_NAMES:
            exp = fx["expected"][name]
            assert arabicwer.wer(fx["ref"], fx["hyp"], name) == exp["wer"]
            assert arabicwer.cer(fx["ref"], fx["hyp"], name) == exp["cer"]
            w = arabicwer.process_words(fx["ref"], fx["hyp"], name)
            assert (w.substitutions, w.deletions, w.insertions, w.reference_units) == (exp["S"], exp["D"], exp["I"], exp["N"])
            c = arabicwer.process_characters(fx["ref"], fx["hyp"], name)
            assert (c.substitutions, c.deletions, c.insertions, c.reference_units) == (exp["cS"], exp["cD"], exp["cI"], exp["cN"])


def test_idempotent():
    for fx in FIXTURES:
        for p in arabicwer.list_policies():
            for t in (fx["ref"], fx["hyp"]):
                once = p.normalise(t)
                assert p.normalise(once) == once

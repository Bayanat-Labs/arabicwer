# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Use an arabicwer policy as a jiwer transform (needs ``pip install jiwer``).

    import jiwer, arabicwer
    t = arabicwer.jiwer_transform("lenient")
    jiwer.wer(ref, hyp, reference_transform=t, hypothesis_transform=t)

The WER equals ``arabicwer.wer(ref, hyp, policy="lenient")``. Substitution, deletion and insertion counts can
differ from arabicwer's when several alignments have the same cost, because jiwer breaks ties its own way.
"""
from __future__ import annotations

from .policy import PolicyLike, load_policy


def jiwer_transform(policy: PolicyLike = "lenient", unit: str = "word"):
    """A jiwer transform that applies ``policy`` and reduces text to words (unit="word") or characters ("char")."""
    try:
        from jiwer.transforms import AbstractTransform
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError("jiwer_transform needs jiwer: pip install jiwer") from exc
    if unit not in ("word", "char"):
        raise ValueError("unit must be 'word' or 'char'")
    pol = load_policy(policy)
    split = pol.words if unit == "word" else pol.chars

    class ArabicWERTransform(AbstractTransform):
        def process_string(self, s):
            return [split(s)]

        def process_list(self, inp):
            return [split(s) for s in inp]

        def __repr__(self):
            return f"arabicwer.jiwer_transform({pol.policy_id!r}, unit={unit!r})"

    return ArabicWERTransform()

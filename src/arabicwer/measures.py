# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""WER and CER with a jiwer-style API (rules M01-M03 of spec/SPEC.md).

``wer``, ``cer``, ``process_words`` and ``process_characters`` take one string or a list of strings, like jiwer,
plus a ``policy``. A list is scored as a corpus: errors and reference units are summed over all pairs before
dividing. A pair with an empty reference has no WER of its own (None); its insertions still count in the
corpus numerator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Union

from rapidfuzz.distance import Levenshtein as _Lev

from . import align as _align
from ._version import __version__
from .policy import DEFAULT_POLICY, PolicyLike, load_policy

Text = Union[str, Sequence[str]]


def _as_list(x: Text, what: str) -> List[str]:
    if isinstance(x, str):
        return [x]
    out = list(x)
    for s in out:
        if not isinstance(s, str):
            raise TypeError(f"each {what} must be a string, got {type(s).__name__}")
    return out


def _pairs(reference: Text, hypothesis: Text):
    refs, hyps = _as_list(reference, "reference"), _as_list(hypothesis, "hypothesis")
    if len(refs) != len(hyps):
        raise ValueError(f"got {len(refs)} references and {len(hyps)} hypotheses; the counts must match")
    return refs, hyps


def rate(errors: int, units: int) -> Optional[float]:
    """Rule M01: errors / reference units, or None when there are no reference units."""
    return None if units == 0 else errors / units


@dataclass(frozen=True)
class _Output:
    references: List[List[str]]
    hypotheses: List[List[str]]
    alignments: List[List[_align.AlignmentChunk]]
    hits: int
    substitutions: int
    deletions: int
    insertions: int
    reference_units: int
    hypothesis_units: int
    pair_rates: List[Optional[float]]
    policy_id: str
    policy_sha256: str
    arabicwer_version: str = field(default=__version__)

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions


@dataclass(frozen=True)
class WordOutput(_Output):
    """Word-level result. ``wer`` is the corpus WER; ``mer``, ``wil`` and ``wip`` follow jiwer's formulas."""

    @property
    def wer(self) -> Optional[float]:
        return rate(self.errors, self.reference_units)

    @property
    def mer(self) -> Optional[float]:
        if self.reference_units == 0:
            return None
        return self.errors / (self.hits + self.errors)

    @property
    def wip(self) -> Optional[float]:
        if self.reference_units == 0:
            return None
        if self.hypothesis_units == 0:
            return 0.0
        return (self.hits / self.reference_units) * (self.hits / self.hypothesis_units)

    @property
    def wil(self) -> Optional[float]:
        w = self.wip
        return None if w is None else 1 - w


@dataclass(frozen=True)
class CharacterOutput(_Output):
    """Character-level result. ``cer`` is the corpus CER."""

    @property
    def cer(self) -> Optional[float]:
        return rate(self.errors, self.reference_units)


def _process(reference: Text, hypothesis: Text, policy: PolicyLike, unit: str):
    pol = load_policy(policy)
    refs, hyps = _pairs(reference, hypothesis)
    tok = pol.words if unit == "word" else pol.chars
    R, Hy, A, rates = [], [], [], []
    H = S = D = I = N = M = 0
    for r, h in zip(refs, hyps):
        rt, ht = tok(r), tok(h)
        ops = _align.edit_ops(rt, ht)
        hh, ss, dd, ii = _align.counts(ops)
        H, S, D, I, N, M = H + hh, S + ss, D + dd, I + ii, N + len(rt), M + len(ht)
        R.append(rt)
        Hy.append(ht)
        A.append(_align.chunks(ops))
        rates.append(rate(ss + dd + ii, len(rt)))
    cls = WordOutput if unit == "word" else CharacterOutput
    return cls(R, Hy, A, H, S, D, I, N, M, rates, pol.policy_id, pol.sha256)


def process_words(reference: Text, hypothesis: Text, policy: PolicyLike = DEFAULT_POLICY) -> WordOutput:
    """Normalise both sides with ``policy``, split into words and align them (jiwer.process_words style)."""
    return _process(reference, hypothesis, policy, "word")


def process_characters(reference: Text, hypothesis: Text, policy: PolicyLike = DEFAULT_POLICY) -> CharacterOutput:
    """Normalise both sides with ``policy`` and align their characters (jiwer.process_characters style)."""
    return _process(reference, hypothesis, policy, "char")


def _fast_rate(reference: Text, hypothesis: Text, policy: PolicyLike, unit: str) -> Optional[float]:
    pol = load_policy(policy)
    refs, hyps = _pairs(reference, hypothesis)
    errors = units = 0
    for r, h in zip(refs, hyps):
        if unit == "word":
            rt, ht = pol.words(r), pol.words(h)
            ids: dict = {}
            rt = [ids.setdefault(t, len(ids)) for t in rt]
            ht = [ids.setdefault(t, len(ids)) for t in ht]
        else:
            rt, ht = " ".join(pol.words(r)), " ".join(pol.words(h))
        errors += _Lev.distance(rt, ht)
        units += len(rt)
    return rate(errors, units)


def wer(reference: Text, hypothesis: Text, policy: PolicyLike = DEFAULT_POLICY) -> Optional[float]:
    """Word error rate under ``policy`` (default ``lenient``); None when the reference has no words."""
    return _fast_rate(reference, hypothesis, policy, "word")


def cer(reference: Text, hypothesis: Text, policy: PolicyLike = DEFAULT_POLICY) -> Optional[float]:
    """Character error rate under ``policy`` (default ``lenient``); None when the reference is empty."""
    return _fast_rate(reference, hypothesis, policy, "char")

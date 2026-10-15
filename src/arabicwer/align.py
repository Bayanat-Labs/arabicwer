# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Rule A01: deterministic Levenshtein alignment with unit costs.

The edit distance is the usual one (the same value jiwer and RapidFuzz return). When several alignments reach
that distance, the backtrace runs from the end of both sequences and takes the first step that stays on a
minimal path, in this order: a hit, an insertion, a deletion, a substitution. Among equal-cost alignments this
favours more hits, and it places surplus words where they are rather than shifting substitutions. The JavaScript implementation in web/arabicwer.js follows the same rule, so both
return the same counts and the same alignment.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
from typing import Hashable, List, Sequence, Tuple

#: Implementations may refuse a pair whose matrix would exceed this many cells (it never changes a result).
MAX_CELLS = 50_000_000


class AlignmentTooLarge(ValueError):
    """The pair is too long to align in one piece; split it into shorter segments."""


@dataclass(frozen=True)
class AlignmentChunk:
    """A run of one edit type, with jiwer's field names. ``type`` is equal, substitute, delete or insert."""

    type: str
    ref_start_idx: int
    ref_end_idx: int
    hyp_start_idx: int
    hyp_end_idx: int


def _ids(ref: Sequence[Hashable], hyp: Sequence[Hashable]) -> Tuple[List[int], List[int]]:
    table: dict = {}
    r = [table.setdefault(t, len(table)) for t in ref]
    h = [table.setdefault(t, len(table)) for t in hyp]
    return r, h


def edit_ops(ref: Sequence[Hashable], hyp: Sequence[Hashable]) -> List[str]:
    """One operation per step, in input order: 'equal', 'substitute', 'delete' or 'insert'."""
    n, m = len(ref), len(hyp)
    if (n + 1) * (m + 1) > MAX_CELLS:
        raise AlignmentTooLarge(f"a {n} x {m} alignment is over the limit of {MAX_CELLS} cells")
    r, h = _ids(ref, hyp)
    rows = [array("i", range(m + 1))]
    prev = rows[0]
    for i in range(1, n + 1):
        ri = r[i - 1]
        cur = array("i", [i]) * (m + 1)
        left = i
        for j in range(1, m + 1):
            best = prev[j - 1] + (ri != h[j - 1])
            d = prev[j] + 1
            if d < best:
                best = d
            ins = left + 1
            if ins < best:
                best = ins
            cur[j] = best
            left = best
        rows.append(cur)
        prev = cur
    ops: List[str] = []
    i, j = n, m
    while i > 0 or j > 0:
        here = rows[i][j]
        if i > 0 and j > 0 and r[i - 1] == h[j - 1] and here == rows[i - 1][j - 1]:
            ops.append("equal")
            i -= 1
            j -= 1
        elif j > 0 and here == rows[i][j - 1] + 1:
            ops.append("insert")
            j -= 1
        elif i > 0 and here == rows[i - 1][j] + 1:
            ops.append("delete")
            i -= 1
        else:
            ops.append("substitute")
            i -= 1
            j -= 1
    ops.reverse()
    return ops


def chunks(ops: Sequence[str]) -> List[AlignmentChunk]:
    """Group consecutive operations of one type into jiwer-style alignment chunks."""
    out: List[AlignmentChunk] = []
    i = j = 0
    k = 0
    while k < len(ops):
        t = ops[k]
        i0, j0 = i, j
        while k < len(ops) and ops[k] == t:
            if t != "insert":
                i += 1
            if t != "delete":
                j += 1
            k += 1
        out.append(AlignmentChunk(t, i0, i, j0, j))
    return out


def counts(ops: Sequence[str]) -> Tuple[int, int, int, int]:
    """(hits, substitutions, deletions, insertions)."""
    h = s = d = n = 0
    for t in ops:
        if t == "equal":
            h += 1
        elif t == "substitute":
            s += 1
        elif t == "delete":
            d += 1
        else:
            n += 1
    return h, s, d, n

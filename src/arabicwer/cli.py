# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Command line: arabicwer score | diff | normalise | policies | version."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Tuple

from ._version import __version__
from .policy import POLICY_NAMES, SPEC_ID, PolicyError, list_policies, load_policy
from .report import diff_html, diff_text, diff_tokens, score_pairs, to_csv, to_html, to_json, to_text

TSV_HEADER = ("id", "reference", "hypothesis")


def _read_lines(path: str) -> List[str]:
    with open(path, encoding="utf-8", newline="") as f:
        data = f.read()
    if data.startswith("﻿"):
        data = data[1:]
    lines = data.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [ln[:-1] if ln.endswith("\r") else ln for ln in lines]


def read_tsv(path: str) -> List[Tuple[str, str, str]]:
    """Rows of id<TAB>reference<TAB>hypothesis, or reference<TAB>hypothesis (ids are line numbers).
    A first line 'id<TAB>reference<TAB>hypothesis' is a header and is skipped."""
    rows = []
    for n, line in enumerate(_read_lines(path), start=1):
        cols = line.split("\t")
        if n == 1 and tuple(c.strip().lower() for c in cols) in (TSV_HEADER, TSV_HEADER[1:]):
            continue
        if len(cols) == 3:
            rows.append((cols[0], cols[1], cols[2]))
        elif len(cols) == 2:
            rows.append((str(n), cols[0], cols[1]))
        else:
            raise ValueError(f"{path}:{n}: expected 2 or 3 tab-separated columns, got {len(cols)}")
    return rows


def read_pairs(ref: str, hyp: str) -> List[Tuple[str, str, str]]:
    r, h = _read_lines(ref), _read_lines(hyp)
    if len(r) != len(h):
        raise ValueError(f"{ref} has {len(r)} lines and {hyp} has {len(h)}; one utterance per line on both sides")
    return [(str(i), a, b) for i, (a, b) in enumerate(zip(r, h), start=1)]


def _write(text: str, out: Optional[str]) -> None:
    if out:
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


def cmd_score(a: argparse.Namespace) -> int:
    if a.tsv:
        pairs = read_tsv(a.tsv)
    elif a.ref and a.hyp:
        pairs = read_pairs(a.ref, a.hyp)
    else:
        raise ValueError("give --tsv FILE, or --ref FILE and --hyp FILE")
    policies = a.policy or None
    rep = score_pairs(pairs, policies, bootstrap=a.bootstrap, seed=a.seed, alignment=a.format == "json")
    if a.format == "json":
        _write(to_json(rep), a.out)
    elif a.format == "csv":
        _write(to_csv(rep), a.out)
    elif a.format == "html":
        dp = load_policy(a.diff_policy).policy_id if a.diff_policy else None
        _write(to_html(rep, diff_policy=dp), a.out)
    else:
        _write(to_text(rep), a.out)
    return 0


def cmd_diff(a: argparse.Namespace) -> int:
    if a.html:
        _write('<div class="diff" dir="rtl" lang="ar">' + diff_html(diff_tokens(a.reference, a.hypothesis, a.policy))
               + "</div>\n", None)
    else:
        _write(diff_text(a.reference, a.hypothesis, a.policy), None)
    return 0


def cmd_normalise(a: argparse.Namespace) -> int:
    pol = load_policy(a.policy)
    if a.text is not None:
        print(pol.normalise(a.text))
        return 0
    for line in sys.stdin:
        print(pol.normalise(line.rstrip("\n").rstrip("\r")))
    return 0


def cmd_policies(a: argparse.Namespace) -> int:
    if a.action == "list":
        for p in list_policies():
            print(f"{p.policy_id}\t{p.sha256}\t{p.meta.get('title_en', '')}")
        return 0
    if not a.name:
        raise ValueError("policies show needs a policy name")
    p = load_policy(a.name)
    _write(p.canonical() + "\n" if a.canonical else p.to_json(), None)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="arabicwer", description="Arabic WER and CER under named, versioned "
                                 "normalisation policies (" + SPEC_ID + ").")
    ap.add_argument("--version", action="version", version=f"arabicwer {__version__} ({SPEC_ID})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="score pairs under every policy, side by side")
    s.add_argument("--tsv", help="TSV file: id, reference, hypothesis (or reference, hypothesis)")
    s.add_argument("--ref", help="reference file, one utterance per line")
    s.add_argument("--hyp", help="hypothesis file, one utterance per line")
    s.add_argument("--policy", action="append", help=f"policy name, id or JSON file; repeat for several "
                   f"(default: all of {', '.join(POLICY_NAMES)})")
    s.add_argument("--bootstrap", type=int, default=0, help="bootstrap resamples for 95%% intervals (e.g. 1000)")
    s.add_argument("--seed", type=int, default=0, help="bootstrap seed (default 0)")
    s.add_argument("--format", choices=("text", "json", "csv", "html"), default="text")
    s.add_argument("--diff-policy", help="policy for the word diff in the HTML report (default: the last one)")
    s.add_argument("--out", help="output file (default: standard output)")
    s.set_defaults(func=cmd_score)

    d = sub.add_parser("diff", help="word alignment of one pair")
    d.add_argument("reference")
    d.add_argument("hypothesis")
    d.add_argument("--policy", default="lenient")
    d.add_argument("--html", action="store_true", help="print an RTL-safe HTML fragment")
    d.set_defaults(func=cmd_diff)

    n = sub.add_parser("normalise", aliases=["normalize"], help="print the text a policy scores")
    n.add_argument("text", nargs="?", help="text (default: read lines from standard input)")
    n.add_argument("--policy", default="lenient")
    n.set_defaults(func=cmd_normalise)

    p = sub.add_parser("policies", help="list or show the policies")
    p.add_argument("action", choices=("list", "show"))
    p.add_argument("name", nargs="?")
    p.add_argument("--canonical", action="store_true", help="print the exact bytes that are hashed")
    p.set_defaults(func=cmd_policies)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    ap = build_parser()
    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except (PolicyError, ValueError, OSError) as exc:
        print(f"arabicwer: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

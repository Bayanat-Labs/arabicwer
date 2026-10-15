# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Score a set of reference/hypothesis pairs under several policies, side by side (rules M01-M04).

``score_pair`` gives the per-pair record that the fixtures freeze and that the JavaScript implementation
reproduces. ``score_pairs`` adds corpus totals per policy, the policy swing and optional bootstrap intervals.
"""
from __future__ import annotations

import csv
import html
import io
import json
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import align as _align
from ._version import __version__
from .measures import rate
from .policy import POLICY_NAMES, SPEC_ID, Policy, PolicyLike, load_policy

PAIR_FIELDS = ("ref_norm", "hyp_norm", "S", "D", "I", "N", "wer", "cS", "cD", "cI", "cN", "cer")


def score_pair(reference: str, hypothesis: str, policy: PolicyLike, alignment: bool = False) -> Dict[str, Any]:
    """Per-pair record: normalised texts, word counts (S, D, I, N, wer) and character counts (cS, cD, cI, cN, cer)."""
    pol = load_policy(policy)
    rw, hw = pol.words(reference), pol.words(hypothesis)
    ops = _align.edit_ops(rw, hw)
    _, s, d, i = _align.counts(ops)
    rn, hn = " ".join(rw), " ".join(hw)
    cops = _align.edit_ops(rn, hn)
    _, cs, cd, ci = _align.counts(cops)
    out: Dict[str, Any] = {
        "ref_norm": rn, "hyp_norm": hn,
        "S": s, "D": d, "I": i, "N": len(rw), "wer": rate(s + d + i, len(rw)),
        "cS": cs, "cD": cd, "cI": ci, "cN": len(rn), "cer": rate(cs + cd + ci, len(rn)),
    }
    if alignment:
        out["alignment"] = [[c.type, c.ref_start_idx, c.ref_end_idx, c.hyp_start_idx, c.hyp_end_idx]
                            for c in _align.chunks(ops)]
    return out


def _resolve(policies: Optional[Iterable[PolicyLike]]) -> List[Policy]:
    if policies is None:
        return [load_policy(n) for n in POLICY_NAMES]
    return [load_policy(p) for p in policies]


def _corpus(records: Sequence[Dict[str, Any]], idx: Optional[Sequence[int]] = None) -> Tuple[Optional[float], Optional[float]]:
    it = records if idx is None else (records[k] for k in idx)
    e = n = ce = cn = 0
    for r in it:
        e += r["S"] + r["D"] + r["I"]
        n += r["N"]
        ce += r["cS"] + r["cD"] + r["cI"]
        cn += r["cN"]
    return rate(e, n), rate(ce, cn)


def _interval(values: List[float]) -> Optional[List[float]]:
    if not values:
        return None
    v = sorted(values)
    b = len(v)
    return [v[int(round(0.025 * (b - 1)))], v[int(round(0.975 * (b - 1)))]]


def score_pairs(pairs: Sequence[Tuple[str, str, str]], policies: Optional[Iterable[PolicyLike]] = None,
                bootstrap: int = 0, seed: int = 0, alignment: bool = False) -> Dict[str, Any]:
    """Score (pair_id, reference, hypothesis) triples under each policy (all built-in policies by default)."""
    pols = _resolve(policies)
    per: Dict[str, List[Dict[str, Any]]] = {p.policy_id: [] for p in pols}
    rows = []
    for pid, ref, hyp in pairs:
        scores = {}
        for p in pols:
            rec = score_pair(ref, hyp, p, alignment=alignment)
            per[p.policy_id].append(rec)
            scores[p.policy_id] = rec
        rows.append({"pair_id": pid, "ref_raw": ref, "hyp_raw": hyp, "scores": scores})
    n_pairs = len(rows)
    draws: List[List[int]] = []
    if bootstrap and n_pairs:
        rng = random.Random(seed)
        draws = [[rng.randrange(n_pairs) for _ in range(n_pairs)] for _ in range(bootstrap)]
    summary = []
    boot_w: Dict[str, List[Optional[float]]] = {}
    for p in pols:
        recs = per[p.policy_id]
        tot = {k: sum(r[k] for r in recs) for k in ("S", "D", "I", "N", "cS", "cD", "cI", "cN")}
        w, c = _corpus(recs)
        pw = [r["wer"] for r in recs if r["wer"] is not None]
        pc = [r["cer"] for r in recs if r["cer"] is not None]
        entry: Dict[str, Any] = {
            "policy_id": p.policy_id, "name": p.name, "policy_sha256": p.sha256,
            "words": {"substitutions": tot["S"], "deletions": tot["D"], "insertions": tot["I"],
                      "hits": tot["N"] - tot["S"] - tot["D"], "reference_units": tot["N"], "wer": w,
                      "mean_pair_wer": (sum(pw) / len(pw)) if pw else None},
            "characters": {"substitutions": tot["cS"], "deletions": tot["cD"], "insertions": tot["cI"],
                           "hits": tot["cN"] - tot["cS"] - tot["cD"], "reference_units": tot["cN"], "cer": c,
                           "mean_pair_cer": (sum(pc) / len(pc)) if pc else None},
            "empty_references": sum(1 for r in recs if r["N"] == 0),
        }
        if draws:
            ws, cs = [], []
            for d in draws:
                a, b = _corpus(recs, d)
                ws.append(a)
                cs.append(b)
            boot_w[p.policy_id] = ws
            entry["bootstrap"] = {"resamples": bootstrap, "seed": seed,
                                  "wer_ci95": _interval([x for x in ws if x is not None]),
                                  "cer_ci95": _interval([x for x in cs if x is not None])}
        summary.append(entry)
    report: Dict[str, Any] = {
        "arabicwer_version": __version__, "spec": SPEC_ID, "pairs_total": n_pairs,
        "policies": summary, "swing": _swing(summary, boot_w, draws), "pairs": rows,
    }
    return report


def _swing(summary: List[Dict[str, Any]], boot_w: Dict[str, List[Optional[float]]], draws) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for unit, key in (("words", "wer"), ("characters", "cer")):
        vals = [(e[unit][key], e["policy_id"]) for e in summary if e[unit][key] is not None]
        if len(vals) < 2:
            out[key] = None
            continue
        hi = max(vals, key=lambda t: t[0])
        lo = min(vals, key=lambda t: t[0])
        out[key] = {"max": hi[0], "max_policy": hi[1], "min": lo[0], "min_policy": lo[1], "swing": hi[0] - lo[0]}
    if draws and out.get("wer") and len(boot_w) >= 2:
        sw = []
        for k in range(len(draws)):
            v = [ws[k] for ws in boot_w.values() if ws[k] is not None]
            if len(v) >= 2:
                sw.append(max(v) - min(v))
        out["wer"]["swing_ci95"] = _interval(sw)
    return out


# --------------------------------------------------------------------------------------------- output formats
def to_json(report: Dict[str, Any], indent: Optional[int] = 2) -> str:
    return json.dumps(report, ensure_ascii=False, indent=indent) + "\n"


CSV_COLUMNS = ("pair_id", "policy_id", "policy_sha256", "arabicwer_version") + PAIR_FIELDS


def to_csv(report: Dict[str, Any]) -> str:
    """One row per pair and policy, plus one corpus row per policy (pair_id = "*corpus*")."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    sha = {e["policy_id"]: e["policy_sha256"] for e in report["policies"]}
    for row in report["pairs"]:
        for pid, rec in row["scores"].items():
            w.writerow([row["pair_id"], pid, sha[pid], report["arabicwer_version"]] + [_cell(rec[k]) for k in PAIR_FIELDS])
    for e in report["policies"]:
        wd, ch = e["words"], e["characters"]
        w.writerow(["*corpus*", e["policy_id"], e["policy_sha256"], report["arabicwer_version"], "", "",
                    wd["substitutions"], wd["deletions"], wd["insertions"], wd["reference_units"], _cell(wd["wer"]),
                    ch["substitutions"], ch["deletions"], ch["insertions"], ch["reference_units"], _cell(ch["cer"])])
    return buf.getvalue()


def _cell(v: Any) -> Any:
    return "" if v is None else v


def _pct(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{100 * v:.2f}%"


def to_text(report: Dict[str, Any]) -> str:
    """A plain summary table, one line per policy, with the swing."""
    lines = [f"arabicwer {report['arabicwer_version']} ({report['spec']}), {report['pairs_total']} pair(s)", ""]
    head = f"{'policy':<28} {'WER':>8} {'CER':>8} {'S':>6} {'D':>6} {'I':>6} {'N':>7}  sha256"
    lines.append(head)
    lines.append("-" * len(head))
    for e in report["policies"]:
        wd = e["words"]
        ci = ""
        if "bootstrap" in e and e["bootstrap"]["wer_ci95"]:
            lo, hi = e["bootstrap"]["wer_ci95"]
            ci = f"  95% CI {_pct(lo)}-{_pct(hi)}"
        lines.append(f"{e['policy_id']:<28} {_pct(wd['wer']):>8} {_pct(e['characters']['cer']):>8} "
                     f"{wd['substitutions']:>6} {wd['deletions']:>6} {wd['insertions']:>6} {wd['reference_units']:>7}  "
                     f"{e['policy_sha256'][:12]}{ci}")
    sw = report["swing"].get("wer")
    if sw:
        lines.append("")
        lines.append(f"WER swing across policies: {100 * sw['swing']:.2f} points "
                     f"({sw['max_policy']} {_pct(sw['max'])} to {sw['min_policy']} {_pct(sw['min'])})")
    empty = max((e["empty_references"] for e in report["policies"]), default=0)
    if empty:
        lines.append(f"Pairs with an empty reference (no per-pair WER; insertions still counted): {empty}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------------- diff
def diff_tokens(reference: str, hypothesis: str, policy: PolicyLike) -> List[Dict[str, Any]]:
    """Word alignment as a list of {op, ref, hyp}; op is equal, substitute, delete or insert."""
    pol = load_policy(policy)
    rw, hw = pol.words(reference), pol.words(hypothesis)
    out, i, j = [], 0, 0
    for op in _align.edit_ops(rw, hw):
        r = rw[i] if op != "insert" else None
        h = hw[j] if op != "delete" else None
        out.append({"op": op, "ref": r, "hyp": h})
        i += op != "insert"
        j += op != "delete"
    return out


_LABEL = {"equal": "", "substitute": "S", "delete": "D", "insert": "I"}


def diff_text(reference: str, hypothesis: str, policy: PolicyLike) -> str:
    """One line per word: the edit label (S, D, I or blank), the reference word and the hypothesis word."""
    pol = load_policy(policy)
    rec = score_pair(reference, hypothesis, pol)
    lines = [f"policy {pol.policy_id} (sha256 {pol.sha256[:12]})",
             f"WER {_pct(rec['wer'])} (S={rec['S']} D={rec['D']} I={rec['I']} N={rec['N']}), CER {_pct(rec['cer'])}"]
    for t in diff_tokens(reference, hypothesis, pol):
        lab = _LABEL[t["op"]] or "="
        lines.append(f"{lab}\t{t['ref'] or '-'}\t{t['hyp'] or '-'}")
    return "\n".join(lines) + "\n"


def diff_html(tokens: List[Dict[str, Any]]) -> str:
    """RTL-safe HTML: every word in <bdi>, every edit labelled in text (not by colour alone)."""
    parts = []
    for t in tokens:
        op = t["op"]
        r = html.escape(t["ref"] or "")
        h = html.escape(t["hyp"] or "")
        if op == "equal":
            parts.append(f'<span class="ok"><bdi>{r}</bdi></span>')
        elif op == "substitute":
            parts.append(f'<span class="sub" title="substitution"><bdi class="r">{r}</bdi>'
                         f'<span class="lab">S</span><bdi class="h">{h}</bdi></span>')
        elif op == "delete":
            parts.append(f'<span class="del" title="deletion"><bdi class="r">{r}</bdi><span class="lab">D</span></span>')
        else:
            parts.append(f'<span class="ins" title="insertion"><span class="lab">I</span><bdi class="h">{h}</bdi></span>')
    return " ".join(parts)


_CSS = """body{font-family:system-ui,'Noto Sans Arabic','IBM Plex Sans Arabic',sans-serif;margin:24px;color:#111;background:#fff}
table{border-collapse:collapse;margin:12px 0}td,th{border:1px solid #ccc;padding:4px 8px;text-align:start}
.diff{direction:rtl;line-height:2.2;font-size:18px;border:1px solid #ddd;padding:8px;margin:6px 0}
.sub{background:#fff1c2}.del{background:#ffd9d9}.ins{background:#d8ecff}.r{text-decoration:line-through}
.lab{font:600 11px/1 monospace;border:1px solid #555;border-radius:3px;padding:1px 3px;margin:0 3px;direction:ltr;unicode-bidi:isolate}
code{font-size:12px}"""


def to_html(report: Dict[str, Any], diff_policy: Optional[str] = None, max_pairs: int = 500) -> str:
    """A self-contained HTML report: the policy table, the swing and a word diff per pair."""
    pols = report["policies"]
    dp = diff_policy or (pols[-1]["policy_id"] if pols else None)
    rows = []
    for e in pols:
        ci = e.get("bootstrap", {}).get("wer_ci95") if e.get("bootstrap") else None
        rows.append("<tr><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
                    "<td><code>{}</code></td></tr>".format(
                        html.escape(e["policy_id"]), _pct(e["words"]["wer"]),
                        "" if not ci else f"{_pct(ci[0])} - {_pct(ci[1])}", _pct(e["characters"]["cer"]),
                        e["words"]["substitutions"], e["words"]["deletions"], e["words"]["insertions"],
                        e["policy_sha256"]))
    sw = report["swing"].get("wer")
    swing = "" if not sw else (f"<p>WER swing across policies: <strong>{100 * sw['swing']:.2f} points</strong> "
                               f"(<code>{html.escape(sw['max_policy'])}</code> {_pct(sw['max'])} to "
                               f"<code>{html.escape(sw['min_policy'])}</code> {_pct(sw['min'])}).</p>")
    diffs = []
    for row in report["pairs"][:max_pairs]:
        rec = row["scores"].get(dp)
        if rec is None:
            continue
        toks = diff_tokens(row["ref_raw"], row["hyp_raw"], dp)
        diffs.append(f"<h3><bdi>{html.escape(str(row['pair_id']))}</bdi> &middot; WER {_pct(rec['wer'])}</h3>"
                     f'<div class="diff" dir="rtl" lang="ar">{diff_html(toks)}</div>')
    more = "" if len(report["pairs"]) <= max_pairs else f"<p>Showing {max_pairs} of {len(report['pairs'])} pairs.</p>"
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>arabicwer report</title>"
            f"<style>{_CSS}</style></head><body><h1>arabicwer report</h1>"
            f"<p>arabicwer {html.escape(report['arabicwer_version'])} ({html.escape(report['spec'])}), "
            f"{report['pairs_total']} pair(s). Corpus WER = all word errors / all reference words.</p>"
            "<table><thead><tr><th>Policy</th><th>WER</th><th>WER 95% CI</th><th>CER</th><th>S</th><th>D</th>"
            f"<th>I</th><th>Policy SHA-256</th></tr></thead><tbody>{''.join(rows)}</tbody></table>{swing}"
            f"<h2>Word alignment under <code>{html.escape(dp or '')}</code></h2>"
            "<p>Labels: S substitution (reference word struck through, then the hypothesis word), D deletion, "
            f"I insertion.</p>{more}{''.join(diffs)}</body></html>\n")

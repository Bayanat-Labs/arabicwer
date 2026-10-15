# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Score the FLEURS ar_eg case study under every arabicwer-1 policy and write the results, chart and report.

Inputs: casestudy/references.jsonl and casestudy/hyps/<model>.jsonl (from transcribe.py).
Outputs: casestudy/results/{summary.json, scores.csv, ablation.csv, policy_swing.png, policy_swing.svg} and
casestudy/REPORT.md. Every number in the outputs is computed here from those files.

Needs arabicwer and matplotlib. Usage: python casestudy/score.py [--bootstrap 1000] [--seed 0]
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os

import arabicwer
from arabicwer.report import diff_tokens, score_pairs

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
MODELS = ["large-v3-turbo", "small"]
LABEL = {"large-v3-turbo": "whisper-large-v3-turbo", "small": "whisper-small"}
# lenient stages that are switched back off one at a time for the ablation, with their "off" value
ABLATE = [("ligatures_honorific", "keep"), ("strip_controls", "keep"), ("presentation_forms", "keep"),
          ("bidi_zw", "keep"), ("tatweel", "keep"), ("diacritics", "keep"), ("quranic_marks", "keep"),
          ("superscript_alef", "keep"), ("alef_variants", "keep"), ("alef_maqsura", "keep"), ("taa_marbuta", "keep"),
          ("persian_urdu_letters", "keep"), ("digits", "keep"), ("punctuation", "keep"), ("latin_case", "keep")]
RULE = {"strip_controls": "R02", "presentation_forms": "R03", "ligatures_honorific": "R04", "bidi_zw": "R05",
        "tatweel": "R07", "diacritics": "R08", "quranic_marks": "R09", "superscript_alef": "R10",
        "alef_variants": "R11", "alef_maqsura": "R12", "taa_marbuta": "R13", "persian_urdu_letters": "R15",
        "digits": "R16", "punctuation": "R17", "latin_case": "R19"}


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pct(v):
    return "n/a" if v is None else f"{100 * v:.2f}%"


def ablation(pairs):
    base = arabicwer.load_policy("lenient")
    base_rep = score_pairs(pairs, [base])
    base_wer = base_rep["policies"][0]["words"]["wer"]
    out = []
    for stage, off in ABLATE:
        data = copy.deepcopy(base.data)
        data["policy_id"] = f"ablation/lenient-without-{stage.replace('_', '-')}"
        data["normaliser"]["policy_id"] = f"ablation-lenient-without-{stage.replace('_', '-')}"
        data["normaliser"]["stages"][stage] = off
        data.pop("meta", None)
        rep = score_pairs(pairs, [arabicwer.load_policy(data)])
        w = rep["policies"][0]["words"]["wer"]
        out.append({"rule": RULE[stage], "stage": stage, "wer_without_rule": w, "delta_points": 100 * (w - base_wer)})
    return base_wer, out


def chart(summary, path_base):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, ink2, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
    colours = {"large-v3-turbo": "#2a78d6", "small": "#eb6834"}
    models = [m for m in MODELS if m in summary["models"]]
    names = arabicwer.POLICY_NAMES
    fig, ax = plt.subplots(figsize=(9, 6), dpi=100)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    h = 0.36
    xmax = 0
    for k, m in enumerate(models):
        pols = {e["name"]: e for e in summary["models"][m]["policies"]}
        for i, n in enumerate(names):
            e = pols[n]
            w = 100 * e["words"]["wer"]
            lo, hi = (100 * x for x in e["bootstrap"]["wer_ci95"])
            y = i + (k - (len(models) - 1) / 2) * (h + 0.04)
            ax.barh(y, w, height=h, color=colours[m], edgecolor=surface, linewidth=2, label=LABEL[m] if i == 0 else None)
            ax.plot([lo, hi], [y, y], color=ink2, linewidth=1.2, solid_capstyle="butt")
            ax.plot([lo, lo], [y - 0.08, y + 0.08], color=ink2, linewidth=1.2)
            ax.plot([hi, hi], [y - 0.08, y + 0.08], color=ink2, linewidth=1.2)
            ax.text(hi + 0.6, y, f"{w:.1f}%", va="center", ha="left", fontsize=9, color=ink)
            xmax = max(xmax, hi)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([f"arabicwer-1/{n}" for n in names], fontsize=10, color=ink)
    ax.invert_yaxis()
    ax.set_xlim(0, xmax * 1.15)
    ax.set_xlabel("Corpus WER (%)", color=ink2, fontsize=10)
    ax.tick_params(axis="x", colors=ink2, labelsize=9)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    sw = {m: summary["models"][m]["swing"]["wer"]["swing"] * 100 for m in models}
    fig.suptitle("Same audio, same models: Arabic WER under six normalisation policies", x=0.02, y=0.975, ha="left",
                 fontsize=13, color=ink, fontweight="bold")
    sub = (f"FLEURS Egyptian Arabic (ar_eg) test, {summary['utterances']} utterances.\nSwing between policies: "
           + ", ".join(f"{LABEL[m]} {sw[m]:.1f} points" for m in models) + ".\n"
           + f"Whiskers: 95% bootstrap interval ({summary['bootstrap']['resamples']:,} resamples).")
    fig.text(0.02, 0.915, sub, ha="left", va="top", fontsize=9.5, color=ink2, linespacing=1.5)
    ax.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=ink)
    fig.text(0.02, 0.01, "arabicwer 0.1.0 · Bayanat Labs · CC BY 4.0. References: FLEURS (Google, CC BY 4.0).",
             fontsize=8, color=ink2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.86))
    fig.savefig(path_base + ".png", dpi=200, facecolor=surface)
    fig.savefig(path_base + ".svg", facecolor=surface, metadata={"Date": None})
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    refs = read_jsonl(os.path.join(HERE, "references.jsonl"))
    ref_by_key = {r["utt_key"]: r for r in refs}
    summary = {"arabicwer_version": arabicwer.__version__, "spec": arabicwer.SPEC_ID,
               "dataset": "google/fleurs ar_eg test (revision 70bb2e84b976b7e960aa89f1c648e09c59f894dd)",
               "reference_field": "raw_transcription", "utterances": len(refs),
               "audio_seconds": round(sum(r["duration_s"] for r in refs), 1), "split_rows_total": refs[0]["split_rows_total"],
               "bootstrap": {"resamples": a.bootstrap, "seed": a.seed}, "models": {}}
    rows = []
    reports = {}
    for m in MODELS:
        p = os.path.join(HERE, "hyps", f"{m}.jsonl")
        if not os.path.exists(p):
            continue
        hyps = read_jsonl(p)
        assert [h["utt_key"] for h in hyps] == [r["utt_key"] for r in refs], f"{m}: hypotheses do not match the references"
        pairs = [(h["utt_key"], ref_by_key[h["utt_key"]]["raw_transcription"], h["hypothesis"]) for h in hyps]
        rep = score_pairs(pairs, bootstrap=a.bootstrap, seed=a.seed)
        reports[m] = rep
        base, abl = ablation(pairs)
        summary["models"][m] = {"model_id": hyps[0]["model_id"], "model_weights": hyps[0]["model_weights"],
                                "runtime": hyps[0]["runtime"], "decode_params": hyps[0]["decode_params"],
                                "policies": rep["policies"], "swing": rep["swing"],
                                "ablation": {"lenient_wer": base, "rules": abl}}
        for row in rep["pairs"]:
            for pid, rec in row["scores"].items():
                rows.append([m, row["pair_id"], pid] + [rec[k] for k in arabicwer.report.PAIR_FIELDS])
        with open(os.path.join(RES, f"ablation-{m}.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["rule", "stage", "wer_without_rule", "delta_points"])
            for r in abl:
                w.writerow([r["rule"], r["stage"], r["wer_without_rule"], round(r["delta_points"], 4)])
    with open(os.path.join(RES, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(os.path.join(RES, "scores.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["model", "utt_key", "policy_id"] + list(arabicwer.report.PAIR_FIELDS))
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
    chart(summary, os.path.join(RES, "policy_swing"))
    write_report(summary, reports, refs)
    print(json.dumps({m: {e["name"]: round(100 * e["words"]["wer"], 2) for e in v["policies"]}
                      for m, v in summary["models"].items()}, indent=1))


def write_report(summary, reports, refs):
    models = [m for m in MODELS if m in summary["models"]]
    L = []
    L.append("# Case study: how far Arabic WER moves with the normalisation policy\n")
    L.append(f"Data: FLEURS Egyptian Arabic (`google/fleurs`, config `ar_eg`, test split, revision `70bb2e84b976b7e960aa89f1c648e09c59f894dd`), "
             f"rows 1-{summary['utterances']} of {summary['split_rows_total']} in file order, "
             f"{summary['audio_seconds'] / 60:.1f} minutes of audio. References: the `raw_transcription` field "
             "(Google, CC BY 4.0). Hypotheses: produced by Bayanat Labs on a laptop CPU with the open models below "
             "(released CC BY 4.0 in `hyps/`). All numbers in this file are computed by `casestudy/score.py` "
             f"with arabicwer {summary['arabicwer_version']}.\n")
    L.append("| Model | Weights used | Runtime | Decoding |\n|---|---|---|---|")
    for m in models:
        d = summary["models"][m]
        dp = ", ".join(f"{k}={v}" for k, v in d["decode_params"].items())
        L.append(f"| `{d['model_id']}` | `{d['model_weights']}` | {d['runtime']} | {dp} |")
    L.append("")
    L.append("## Corpus WER and CER under each policy\n")
    head = "| Policy | " + " | ".join(f"{LABEL[m]} WER (95% CI) | {LABEL[m]} CER" for m in models) + " |"
    L.append(head)
    L.append("|---|" + "---|---|" * len(models))
    for i, n in enumerate(arabicwer.POLICY_NAMES):
        cells = []
        for m in models:
            e = summary["models"][m]["policies"][i]
            lo, hi = e["bootstrap"]["wer_ci95"]
            cells.append(f"{pct(e['words']['wer'])} ({pct(lo)}-{pct(hi)}) | {pct(e['characters']['cer'])}")
        L.append(f"| `arabicwer-1/{n}` | " + " | ".join(cells) + " |")
    L.append("")
    for m in models:
        sw = summary["models"][m]["swing"]["wer"]
        lo, hi = sw["swing_ci95"]
        L.append(f"- **{LABEL[m]}**: the corpus WER moves by **{100 * sw['swing']:.2f} points** between "
                 f"`{sw['max_policy']}` ({pct(sw['max'])}) and `{sw['min_policy']}` ({pct(sw['min'])}); "
                 f"95% bootstrap interval of the swing {100 * lo:.2f}-{100 * hi:.2f} points.")
    L.append("\n![Corpus WER under each policy](results/policy_swing.png)\n")
    L.append("## Which rules move the score\n")
    L.append("Each row switches one rule of `lenient` back off and reports the change in corpus WER (points). "
             "A positive value means the rule forgives that many points of WER.\n")
    L.append("| Rule | Stage | " + " | ".join(f"{LABEL[m]}" for m in models) + " |")
    L.append("|---|---|" + "---|" * len(models))
    abl = {m: {r["stage"]: r for r in summary["models"][m]["ablation"]["rules"]} for m in models}
    order = sorted(abl[models[0]].values(), key=lambda r: -r["delta_points"])
    for r in order:
        L.append(f"| {r['rule']} | `{r['stage']}` | " + " | ".join(f"{abl[m][r['stage']]['delta_points']:+.2f}" for m in models) + " |")
    L.append("")
    m0 = models[0]
    rep = reports[m0]
    raw_id, len_id = "arabicwer-1/raw", "arabicwer-1/lenient"
    gaps = sorted(rep["pairs"], key=lambda row: -((row["scores"][raw_id]["S"] + row["scores"][raw_id]["D"] + row["scores"][raw_id]["I"])
                                                - (row["scores"][len_id]["S"] + row["scores"][len_id]["D"] + row["scores"][len_id]["I"])))[:10]
    L.append(f"## Ten alignments ({LABEL[m0]})\n")
    L.append("The ten utterances where `raw` and `lenient` disagree most. S marks a substitution "
             "(reference word, then hypothesis word), D a deletion and I an insertion; unmarked words match. "
             "Reference text: FLEURS (Google, CC BY 4.0).\n")
    for row in gaps:
        r, l = row["scores"][raw_id], row["scores"][len_id]
        L.append(f"### `{row['pair_id']}`: raw {r['S'] + r['D'] + r['I']} errors / {r['N']} words, "
                 f"lenient {l['S'] + l['D'] + l['I']} / {l['N']}\n")
        L.append(f"- Reference: {row['ref_raw']}")
        L.append(f"- Hypothesis: {row['hyp_raw']}")
        toks = diff_tokens(row["ref_raw"], row["hyp_raw"], "lenient")
        parts = []
        for t in toks:
            if t["op"] == "equal":
                parts.append(t["ref"])
            elif t["op"] == "substitute":
                parts.append(f"[S: {t['ref']} → {t['hyp']}]")
            elif t["op"] == "delete":
                parts.append(f"[D: {t['ref']}]")
            else:
                parts.append(f"[I: {t['hyp']}]")
        L.append(f"- Lenient alignment: {' '.join(parts)}\n")
    L.append("## Notes\n")
    L.append("- FLEURS test utterances are a public test set: these numbers are a measurement of scoring "
             "sensitivity, not a model ranking, and please do not train on these hypotheses if you evaluate on FLEURS (a request, not a licence condition).")
    L.append("- The models ran with int8 weights on CPU; other runtimes and settings give other hypotheses.")
    L.append("- Bayanat Labs builds and sells no speech-recognition models; the normaliser and the scoring code are public.")
    with open(os.path.join(HERE, "REPORT.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()

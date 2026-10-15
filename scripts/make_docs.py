# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Fill the generated blocks of spec/SPEC.md, spec/SPEC.ar.md and README.md from the policy and fixture files.

Blocks are delimited by <!-- BEGIN:name --> and <!-- END:name -->. Usage: python scripts/make_docs.py [--check]
"""
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import arabicwer  # noqa: E402

STAGES = ["reject_invalid", "strip_controls", "presentation_forms", "ligatures_honorific", "bidi_zw", None, "tatweel",
          "diacritics", "quranic_marks", "superscript_alef", "alef_variants", "alef_maqsura", "taa_marbuta",
          "hamza_carriers", "persian_urdu_letters", "digits", "punctuation", "whitespace", "latin_case"]
LABEL_EN = ["invalid code points", "invisible format characters", "presentation forms", "honorific ligatures",
            "bidi and zero-width controls", "NFC", "tatweel", "harakat", "Quranic marks", "superscript alef",
            "alef variants", "alef maqsura", "taa marbuta", "hamza carriers", "Persian and Urdu letters", "digits",
            "punctuation", "white space", "Latin case"]
LABEL_AR = ["نقاط الترميز غير الصالحة", "محارف التنسيق الخفية", "الأشكال العرضية", "ضمائم التعظيم",
            "محارف الاتجاه والمحارف الصفرية", "NFC", "التطويل", "الحركات", "علامات المصحف", "الألف الخنجرية",
            "صور الألف", "الألف المقصورة", "التاء المربوطة", "كراسي الهمزة", "الحروف الفارسية والأردية", "الأرقام",
            "علامات الترقيم", "المسافات", "حالة الحروف اللاتينية"]


def mode(p, stage):
    n = p.data["normaliser"]
    if n is None:
        return None
    if stage is None:
        return n["unicode_form"] if n["unicode_form"] != "none" else None
    v = n["stages"][stage]
    return None if v == "keep" else v


def matrix(lang):
    pols = arabicwer.list_policies()
    labels = LABEL_EN if lang == "en" else LABEL_AR
    head = "| Rule | " + " | ".join(f"`{p.name}`" for p in pols) + " |"
    if lang == "ar":
        head = "| القاعدة | " + " | ".join(f"`{p.name}`" for p in pols) + " |"
    lines = [head, "|---|" + "---|" * len(pols)]
    for k, stage in enumerate(STAGES):
        cells = []
        for p in pols:
            m = mode(p, stage)
            cells.append("–" if m is None else f"`{m}`")
        lines.append(f"| R{k + 1:02d} {labels[k]} | " + " | ".join(cells) + " |")
    t01 = "T01 words split on white space" if lang == "en" else "T01 تقسيم الكلمات عند المسافات"
    lines.append(f"| {t01} | " + " | ".join("✓" for _ in pols) + " |")
    note = ("R20 (final NFC) runs whenever R06 does. `strip-except-meaningful` keeps a ZWNJ that blocks a join and a ZWJ "
            "inside an emoji sequence; `flag` leaves the text unchanged (arabic-normalize only records a flag); `drop` removes invalid code points.") if lang == "en" else (
            "تعمل R20 (NFC النهائية) كلما عملت R06. القيمة `strip-except-meaningful` تُبقي محرف ZWNJ الذي يمنع الوصل ومحرف ZWJ "
            "داخل تسلسل الرموز التعبيرية؛ والقيمة `flag` لا تغيّر النص (تسجّل arabic-normalize علامة فقط)؛ والقيمة `drop` تحذف نقاط الترميز غير الصالحة.")
    return "\n".join(lines) + "\n\n" + note


def hashes(lang):
    pols = arabicwer.list_policies()
    if lang == "en":
        lines = ["| Policy | Title | SHA-256 |", "|---|---|---|"]
        lines += [f"| `{p.policy_id}` | {p.meta['title_en']} | `{p.sha256}` |" for p in pols]
    else:
        lines = ["| السياسة | العنوان | بصمة SHA-256 |", "|---|---|---|"]
        lines += [f"| `{p.policy_id}` | {p.meta['title_ar']} | `{p.sha256}` |" for p in pols]
    return "\n".join(lines)


def fixtures():
    out = {}
    for split in ("dev", "acceptance"):
        with open(os.path.join(ROOT, "fixtures", f"{split}.jsonl"), encoding="utf-8") as f:
            out[split] = [json.loads(line) for line in f if line.strip()]
    return out


def counts(lang):
    fx = fixtures()
    n_pol = len(arabicwer.POLICY_NAMES)
    designed = sum(len(r.get("design_word_errors", {})) for rs in fx.values() for r in rs)
    passed = {s: sum(1 for r in rs for name in arabicwer.POLICY_NAMES
                     if arabicwer.score_pair(r["ref"], r["hyp"], name) == r["expected"][name]) for s, rs in fx.items()}
    cats = sorted({r["category"] for r in fx["dev"]})
    today = datetime.date.today().isoformat()
    if lang == "en":
        return (f"| Split | Fixtures | Cases (fixtures x {n_pol} policies) | Passing (Python) |\n|---|---|---|---|\n"
                + "\n".join(f"| {s} | {len(rs)} | {len(rs) * n_pol} | {passed[s]} |" for s, rs in fx.items())
                + f"\n\nThe dev set has {len(cats)} categories of {len(fx['dev']) // len(cats)} fixtures: "
                + ", ".join(f"`{c}`" for c in cats) + ". The acceptance set combines categories. "
                + f"{designed} author-predicted word-error counts are checked against the computed values. "
                + f"Counts computed by `scripts/make_docs.py` from the fixture files on {today}.")
    return (f"| القسم | الحالات | الحالات × {n_pol} سياسات | الناجحة (Python) |\n|---|---|---|---|\n"
            + "\n".join(f"| {s} | {len(rs)} | {len(rs) * n_pol} | {passed[s]} |" for s, rs in fx.items())
            + f"\n\nفي مجموعة dev {len(cats)} فئة في كل منها {len(fx['dev']) // len(cats)} حالات، "
            + "وتجمع مجموعة acceptance بين الفئات. "
            + f"تُقارن {designed} قيمة توقّعها كاتب الحالات لعدد أخطاء الكلمات بالقيم المحسوبة. "
            + f"حُسبت الأعداد بالبرنامج `scripts/make_docs.py` من ملفات الحالات في {today}.")


def parity():
    """Run the JavaScript cross-check and the jiwer parity count; returns the README block."""
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if node is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        rnd = os.path.join(tmp, "random.json")
        out = os.path.join(tmp, "parity.json")
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "crosscheck_random.py"), rnd], check=True)
        fx = [os.path.join(ROOT, "fixtures", f"{s}.jsonl") for s in ("dev", "acceptance")]
        subprocess.run([node, os.path.join(ROOT, "scripts", "crosscheck.mjs"), "--out", out, *fx, rnd], check=True,
                       stdout=subprocess.DEVNULL)
        with open(out, encoding="utf-8") as f:
            rep = json.load(f)
    by = {os.path.basename(x["file"]): x for x in rep["files"]}
    rnd_cases = by["random.json"]["cases"]
    return (f"- JavaScript (`web/arabicwer.js`) against Python: {rep['identical']:,} of {rep['cases']:,} cases identical, "
            f"field for field: {by['dev.jsonl']['cases'] + by['acceptance.jsonl']['cases']:,} fixture cases and "
            f"{rnd_cases:,} random Arabic and Latin pairs ({rnd_cases // len(arabicwer.POLICY_NAMES):,} pairs x "
            f"{len(arabicwer.POLICY_NAMES)} policies, with alignments). Computed by `scripts/crosscheck.mjs`.\n"
            "- jiwer 4.0.0: under `raw`, WER and CER equal jiwer's (difference below 1e-12) on 10,000 random "
            "space-separated Arabic and Latin pairs with a non-empty reference (`tests/test_jiwer_parity.py`). "
            "jiwer gives a WER for an empty reference (the number of insertions); arabicwer reports `null` for that pair "
            "and counts its insertions in the corpus.")


def casestudy():
    p = os.path.join(ROOT, "casestudy", "results", "summary.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        s = json.load(f)
    models = list(s["models"])
    label = {m: s["models"][m]["model_id"].split("/")[-1] for m in models}
    lines = [f"FLEURS Egyptian Arabic (`ar_eg`) test split, rows 1-{s['utterances']} of {s['split_rows_total']} "
             f"({s['audio_seconds'] / 60:.1f} minutes of audio), transcribed by Bayanat Labs on a laptop CPU with two open "
             "models, then scored under every policy. Corpus WER:", "",
             "| Policy | " + " | ".join(f"`{label[m]}`" for m in models) + " |", "|---|" + "---|" * len(models)]
    for i, n in enumerate(arabicwer.POLICY_NAMES):
        lines.append(f"| `arabicwer-1/{n}` | " + " | ".join(
            f"{100 * s['models'][m]['policies'][i]['words']['wer']:.2f}%" for m in models) + " |")
    lines.append("")
    for m in models:
        sw = s["models"][m]["swing"]["wer"]
        lo, hi = sw["swing_ci95"]
        lines.append(f"- `{label[m]}`: {100 * sw['swing']:.2f} points between `{sw['max_policy']}` and "
                     f"`{sw['min_policy']}` (95% bootstrap interval {100 * lo:.2f}-{100 * hi:.2f}).")
    lines.append("")
    lines.append("![Corpus WER under each policy](casestudy/results/policy_swing.png)")
    lines.append("")
    lines.append("Computed by `casestudy/score.py` from `casestudy/references.jsonl` and `casestudy/hyps/`. "
                 "FLEURS is a public test set: these numbers measure scoring sensitivity, not model quality.")
    return "\n".join(lines)


def fill(path, blocks, check):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    new = text
    for name, body in blocks.items():
        pat = re.compile(rf"(<!-- BEGIN:{name} -->\n)(.*?)(<!-- END:{name} -->)", re.S)
        if body is None or not pat.search(new):
            continue
        new = pat.sub(lambda m: m.group(1) + body.rstrip("\n") + "\n" + m.group(3), new)
    if new != text:
        if check:
            print(f"{os.path.relpath(path, ROOT)} is out of date")
            return 1
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
    return 0


def main(argv):
    check = "--check" in argv
    bad = 0
    for path, lang in (("spec/SPEC.md", "en"), ("spec/SPEC.ar.md", "ar"), ("README.md", "en")):
        p = os.path.join(ROOT, path)
        if os.path.exists(p):
            blocks = {"matrix": matrix(lang), "hashes": hashes(lang), "counts": counts(lang)}
            if path == "README.md":
                for name, fn in (("parity", parity), ("casestudy", casestudy)):
                    v = fn()
                    if v is not None:
                        blocks[name] = v
            bad += fill(p, blocks, check)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

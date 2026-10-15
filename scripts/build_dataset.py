# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Build the Hugging Face dataset Bayanat-Labs/arabicwer-fixtures into OUT_DIR.

Configs (Parquet): dev and acceptance (one row per fixture, expected values under every policy) and
fleurs_ar_eg_casestudy (one row per model and utterance: FLEURS reference, hypothesis and per-policy scores).
Also copies the source JSONL files, policies, specification, case-study results and licences, and writes the
card (README.md) with numbers computed from the files, MANIFEST.json and SHA256SUMS.

Needs arabicwer and pyarrow. Usage: python scripts/build_dataset.py OUT_DIR
"""
import hashlib
import json
import os
import shutil
import sys

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import arabicwer  # noqa: E402

FIELDS = ["ref_norm", "hyp_norm", "S", "D", "I", "N", "wer", "cS", "cD", "cI", "cN", "cer"]


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def score_struct():
    return pa.struct([(k, pa.string() if k.endswith("_norm") else (pa.float64() if k in ("wer", "cer") else pa.int64()))
                      for k in FIELDS])


def write_fixtures(out, split):
    rows = read_jsonl(os.path.join(ROOT, "fixtures", f"{split}.jsonl"))
    exp_type = pa.struct([(n, score_struct()) for n in arabicwer.POLICY_NAMES])
    schema = pa.schema([("fixture_id", pa.string()), ("split", pa.string()), ("category", pa.string()),
                        ("ref", pa.string()), ("hyp", pa.string()), ("rationale", pa.string()),
                        ("design_word_errors", pa.string()), ("expected", exp_type), ("synthetic", pa.bool_()),
                        ("original", pa.bool_()), ("author", pa.string()), ("written_at", pa.string())])
    recs = [{**{k: r[k] for k in ("fixture_id", "split", "category", "ref", "hyp", "rationale", "expected", "synthetic",
                                   "original", "author", "written_at")},
             "design_word_errors": json.dumps(r.get("design_word_errors", {}), sort_keys=True)} for r in rows]
    os.makedirs(os.path.join(out, "data", split), exist_ok=True)
    pq.write_table(pa.Table.from_pylist(recs, schema=schema), os.path.join(out, "data", split, f"{split}.parquet"))
    return rows


def write_casestudy(out):
    refs = {r["utt_key"]: r for r in read_jsonl(os.path.join(ROOT, "casestudy", "references.jsonl"))}
    recs = []
    for m in ("large-v3-turbo", "small"):
        for h in read_jsonl(os.path.join(ROOT, "casestudy", "hyps", f"{m}.jsonl")):
            ref = refs[h["utt_key"]]
            scores = {p.name: arabicwer.score_pair(ref["raw_transcription"], h["hypothesis"], p) for p in arabicwer.list_policies()}
            recs.append({"row": h["row"], "fleurs_id": h["fleurs_id"], "utt_key": h["utt_key"],
                         "duration_s": ref["duration_s"], "reference": ref["raw_transcription"],
                         "reference_normalized_fleurs": ref["transcription"], "model_id": h["model_id"],
                         "model_weights": h["model_weights"], "runtime": h["runtime"],
                         "decode_params": json.dumps(h["decode_params"], sort_keys=True), "hypothesis": h["hypothesis"],
                         "scores": scores, "synthetic": False})
    schema = pa.schema([("row", pa.int64()), ("fleurs_id", pa.int64()), ("utt_key", pa.string()), ("duration_s", pa.float64()),
                        ("reference", pa.string()), ("reference_normalized_fleurs", pa.string()), ("model_id", pa.string()),
                        ("model_weights", pa.string()), ("runtime", pa.string()), ("decode_params", pa.string()),
                        ("hypothesis", pa.string()), ("scores", pa.struct([(n, score_struct()) for n in arabicwer.POLICY_NAMES])),
                        ("synthetic", pa.bool_())])
    os.makedirs(os.path.join(out, "data", "fleurs_ar_eg_casestudy"), exist_ok=True)
    pq.write_table(pa.Table.from_pylist(recs, schema=schema),
                   os.path.join(out, "data", "fleurs_ar_eg_casestudy", "casestudy.parquet"))
    return recs


def card(dev, acc, cs):
    with open(os.path.join(ROOT, "casestudy", "results", "summary.json"), encoding="utf-8") as f:
        s = json.load(f)
    models = list(s["models"])
    lab = {m: s["models"][m]["model_id"].split("/")[-1] for m in models}
    pols = arabicwer.list_policies()
    cats = sorted({r["category"] for r in dev})
    table = "\n".join(f"| `arabicwer-1/{n}` | " + " | ".join(
        f"{100 * s['models'][m]['policies'][i]['words']['wer']:.2f}%" for m in models) + " |"
        for i, n in enumerate(arabicwer.POLICY_NAMES))
    swing = "\n".join(f"- `{lab[m]}`: {100 * s['models'][m]['swing']['wer']['swing']:.2f} points between "
                      f"`{s['models'][m]['swing']['wer']['max_policy']}` and `{s['models'][m]['swing']['wer']['min_policy']}` "
                      f"(95% bootstrap interval {100 * s['models'][m]['swing']['wer']['swing_ci95'][0]:.2f}-"
                      f"{100 * s['models'][m]['swing']['wer']['swing_ci95'][1]:.2f})." for m in models)
    hashes = "\n".join(f"| `{p.policy_id}` | {p.meta['title_en']} | `{p.sha256}` |" for p in pols)
    n_utt = s["utterances"]
    return f"""---
license: cc-by-4.0
language:
  - ar
  - en
pretty_name: ArabicWER fixtures and FLEURS case study
size_categories:
  - n<1K
task_categories:
  - automatic-speech-recognition
tags:
  - arabic
  - wer
  - cer
  - asr-evaluation
  - text-normalization
  - conformance
  - synthetic
configs:
  - config_name: dev
    data_files: data/dev/dev.parquet
  - config_name: acceptance
    data_files: data/acceptance/acceptance.parquet
  - config_name: fleurs_ar_eg_casestudy
    data_files: data/fleurs_ar_eg_casestudy/casestudy.parquet
---

# ArabicWER fixtures and FLEURS case study

By **Bayanat Labs**. Conformance fixtures and a case study for [arabicwer](https://github.com/Bayanat-Labs/arabicwer), which scores Arabic speech recognition (WER and CER) under six named, versioned, hash-identified normalisation policies. Try it in the browser: [Bayanat-Labs/arabicwer](https://huggingface.co/spaces/Bayanat-Labs/arabicwer).

This is an evaluation resource, not training data.

| Config | Rows | What a row is |
|---|---|---|
| `dev` | {len(dev)} | a reference/hypothesis pair with expected normalised texts and counts under every policy |
| `acceptance` | {len(acc)} | the same, combining several phenomena per pair |
| `fleurs_ar_eg_casestudy` | {len(cs)} | one FLEURS Egyptian Arabic test utterance transcribed by one open model ({len(models)} models x {n_utt} utterances), with scores under every policy |

```python
from datasets import load_dataset
dev = load_dataset("Bayanat-Labs/arabicwer-fixtures", "dev", split="train")
```

## Fixtures

The fixtures are synthetic: short sentences written by Bayanat Labs for this purpose (`synthetic: true`, `original: true`), with fictional content and no personal data. The dev set has {len(cats)} categories of {len(dev) // len(cats)} pairs each ({", ".join(f"`{c}`" for c in cats)}); the acceptance set combines categories. Each row has:

- `ref`, `hyp`: the reference and hypothesis as written, including invisible characters where the case needs them;
- `expected.<policy>`: `ref_norm`, `hyp_norm`, word counts `S`, `D`, `I`, `N`, `wer`, and character counts `cS`, `cD`, `cI`, `cN`, `cer` (rates are null when the reference is empty);
- `design_word_errors`: the word-error counts the author predicted before computing, as JSON; the build checks them;
- `rationale`: what the pair tests.

The expected values are computed by a script that does not use the arabicwer package (arabic-normalize for normalisation, its own Levenshtein code, checked against RapidFuzz). An implementation conforms to arabicwer-spec-1 when it reproduces every field under every policy. The same files, as JSON Lines, are in `fixtures/`.

## Policies

| Policy | Title | SHA-256 |
|---|---|---|
{hashes}

The policy files are in `policies/` and the specification in `SPEC.md`.

## Case study: FLEURS Egyptian Arabic

References: `raw_transcription` of rows 1-{n_utt} (file order) of the FLEURS `ar_eg` test split (revision `70bb2e84b976b7e960aa89f1c648e09c59f894dd`), {s['audio_seconds'] / 60:.1f} minutes of audio. Hypotheses: produced by Bayanat Labs on a laptop CPU with faster-whisper 1.2.1 (int8; language ar, beam size 5, temperature 0, no VAD, no conditioning on previous text) and the open models `openai/whisper-large-v3-turbo` (MIT) and `openai/whisper-small` (Apache-2.0 per its model card), through their CTranslate2 conversions named in `model_weights`. No audio is included; get it from FLEURS.

Corpus WER under each policy:

| Policy | {" | ".join(f"`{lab[m]}`" for m in models)} |
|---|{"---|" * len(models)}
{table}

{swing}

![Corpus WER under each policy](casestudy/results/policy_swing.png)

`casestudy/REPORT.md` has CER, 95% bootstrap intervals, a per-rule ablation and ten example alignments; `casestudy/results/` has the per-utterance scores (`scores.csv`), the summary (`summary.json`) and the chart (PNG and SVG). FLEURS is a public test set: these numbers measure how much the scoring policy moves WER, not model quality, and please do not train on these hypotheses if you evaluate on FLEURS (a request, not a licence condition). Bayanat Labs builds and sells no speech-recognition models; the normaliser and the scoring code are public.

## Licence and attribution

- Code files `casestudy/transcribe.py` and `casestudy/score.py`: Apache-2.0 (`LICENSE-code`).
- Fixtures, policies, specification, hypotheses, scores, chart and report: CC BY 4.0, Bayanat Labs. Attribute as "arabicwer fixtures and case study, Bayanat Labs (https://bayanatlabs.com), CC BY 4.0".
- FLEURS reference text (`reference`, `reference_normalized_fleurs` and `casestudy/references.jsonl`): Google, from [google/fleurs](https://huggingface.co/datasets/google/fleurs), CC BY 4.0. FLEURS is described in Conneau et al., "FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech", 2022 (arXiv:2205.12446).

## Citation

```bibtex
@misc{{bayanatlabs_arabicwer_fixtures_2026,
  author = {{{{Bayanat Labs}}}},
  title  = {{ArabicWER fixtures and FLEURS case study}},
  year   = {{2026}},
  url    = {{https://huggingface.co/datasets/Bayanat-Labs/arabicwer-fixtures}}
}}
```

Contact and takedown requests: hello@bayanatlabs.com. Need production-grade, rights-cleared Arabic speech data? See [Bayanat Voice](https://www.bayanatlabs.com/products/voice).

---

<div dir="rtl" lang="ar">

## بالعربية

> The Arabic text has not yet been reviewed by a native Arabic writer; the English governs.

حالات اختبار ودراسة حالة لأداة arabicwer من بيانات لابز، التي تحسب معدل خطأ الكلمات والحروف في التعرّف الآلي على الكلام العربي وفق ست سياسات توحيد مسمّاة. حالات الاختبار جمل اصطناعية كتبتها بيانات لابز لهذا الغرض، ومعها القيم المتوقعة في كل سياسة. وتقيس دراسة الحالة مقدار تغيّر معدل الخطأ بين السياسات على {n_utt} جملة من اختبار FLEURS للعربية المصرية بنموذجين مفتوحين. الترخيص CC BY 4.0، ونصوص FLEURS المرجعية من Google بترخيص CC BY 4.0.

</div>
"""


def main(argv):
    out = argv[0]
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    dev = write_fixtures(out, "dev")
    acc = write_fixtures(out, "acceptance")
    cs = write_casestudy(out)
    shutil.copytree(os.path.join(ROOT, "fixtures"), os.path.join(out, "fixtures"))
    shutil.copytree(os.path.join(ROOT, "src", "arabicwer", "policies"), os.path.join(out, "policies"),
                    ignore=shutil.ignore_patterns("__init__.py", "__pycache__"))
    os.makedirs(os.path.join(out, "casestudy"))
    for item in ("references.jsonl", "hyps", "results", "REPORT.md", "transcribe.py", "score.py"):
        src = os.path.join(ROOT, "casestudy", item)
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, os.path.join(out, "casestudy", item))
    for f in ("spec/SPEC.md", "spec/SPEC.ar.md", "spec/policy_hashes.json", "LICENSE-data", "CITATION.cff",
              "provenance/PROVENANCE.jsonl"):
        shutil.copy2(os.path.join(ROOT, f), os.path.join(out, os.path.basename(f)))
    os.rename(os.path.join(out, "LICENSE-data"), os.path.join(out, "LICENSE"))
    shutil.copy2(os.path.join(ROOT, "LICENSE"), os.path.join(out, "LICENSE-code"))
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(card(dev, acc, cs))
    files = []
    for dirpath, _, names in os.walk(out):
        for n in sorted(names):
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, out)
            if rel in ("MANIFEST.json", "SHA256SUMS"):
                continue
            with open(p, "rb") as g:
                data = g.read()
            files.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    files.sort(key=lambda x: x["path"])
    with open(os.path.join(out, "MANIFEST.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"dataset": "Bayanat-Labs/arabicwer-fixtures", "arabicwer_version": arabicwer.__version__,
                   "spec": arabicwer.SPEC_ID, "files": files}, f, indent=1)
        f.write("\n")
    with open(os.path.join(out, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as f:
        f.writelines(f"{x['sha256']}  {x['path']}\n" for x in files)
    print(f"built {out}: {len(files)} files; dev {len(dev)}, acceptance {len(acc)}, casestudy {len(cs)} rows")


if __name__ == "__main__":
    main(sys.argv[1:])

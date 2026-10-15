# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Build the static Hugging Face Space (Bayanat-Labs/arabicwer) from web/ into OUT_DIR.

Copies the page, the scorer and the bundled arabic-normalize port, the licence files, writes the Space card
(README.md) with numbers computed from the fixture files and the JavaScript parity report, and a MANIFEST.json
with the SHA-256 of every file.

Usage: python scripts/build_space.py OUT_DIR [--parity parity.json]
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_FILES = ["index.html", "style.css", "app.js", "compute.js", "worker.js", "arabicwer.js", "policies.js", "examples.js"]
WEB_DIRS = ["lib", "fonts"]
TOP_FILES = ["LICENSE", "LICENSE-data", "NOTICE", "NOTICE-unicode.txt"]
sys.path.insert(0, os.path.join(ROOT, "src"))


def fixture_counts():
    out = {}
    for split in ("dev", "acceptance"):
        with open(os.path.join(ROOT, "fixtures", f"{split}.jsonl"), encoding="utf-8") as f:
            out[split] = sum(1 for line in f if line.strip())
    return out


def card(parity):
    import arabicwer

    fx = fixture_counts()
    pols = arabicwer.list_policies()
    rows = "\n".join(f"| `{p.policy_id}` | {p.meta['title_en']} | `{p.sha256}` |" for p in pols)
    par = ""
    if parity:
        par = (f"The page and the Python package give identical results: {parity['identical']:,} of "
               f"{parity['cases']:,} cases match field for field (every fixture under every policy, plus random "
               "Arabic and Latin pairs with their alignments).")
    return f"""---
title: ArabicWER
emoji: 🎙️
colorFrom: indigo
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: Arabic WER and CER under six named policies
tags:
  - arabic
  - speech-recognition
  - asr
  - wer
  - evaluation
  - arabic-nlp
---

# ArabicWER: Arabic WER and CER calculator

By **Bayanat Labs**. Paste reference and hypothesis transcripts, or upload a TSV file, and see the word error rate (WER) and character error rate (CER) under six named, versioned normalisation policies side by side, with an RTL-safe word diff that labels every substitution, deletion and insertion. The same audio and the same system can score very differently depending on how Arabic text is normalised before scoring; this page shows that swing openly.

The page runs the JavaScript version of [`arabicwer`](https://github.com/Bayanat-Labs/arabicwer) {arabicwer.__version__} ({arabicwer.SPEC_ID}) in your browser, with Unicode 18.0.0 data bundled. Your text is not uploaded, stored or logged: the page loads no third-party script, font or stylesheet, and its Content-Security-Policy (`connect-src 'none'`) forbids network connections, both in the page and in the Web Worker that scores the text. Once loaded, it works offline. The interface is in English by default; switch to Arabic with the button at the top or `?lang=ar`.

| Policy | What it is | SHA-256 |
|---|---|---|
{rows}

Cite a score with its policy, for example "WER 12.34% (arabicwer-1/lenient)". Conformance: {fx['dev']} dev and {fx['acceptance']} acceptance fixtures, each scored under all six policies. {par}

- Code, specification and Python package: https://github.com/Bayanat-Labs/arabicwer
- Fixtures and the FLEURS case study: https://huggingface.co/datasets/Bayanat-Labs/arabicwer-fixtures

Licences: code Apache-2.0 (`LICENSE`); policy files and examples CC BY 4.0 (`LICENSE-data`); generated Unicode tables Unicode License V3 (`NOTICE-unicode.txt`); IBM Plex Sans Arabic font (IBM's unmodified files) SIL OFL 1.1 (`fonts/OFL.txt`). Contact and takedown requests: hello@bayanatlabs.com.

Need production-grade, rights-cleared Arabic speech data? See [Bayanat Voice](https://www.bayanatlabs.com/products/voice).
"""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--parity")
    a = ap.parse_args(argv)
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    os.makedirs(a.out)
    for f in WEB_FILES:
        shutil.copy2(os.path.join(ROOT, "web", f), os.path.join(a.out, f))
    for d in WEB_DIRS:
        shutil.copytree(os.path.join(ROOT, "web", d), os.path.join(a.out, d))
    for f in TOP_FILES:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(a.out, f))
    parity = None
    if a.parity:
        with open(a.parity, encoding="utf-8") as f:
            parity = json.load(f)
    with open(os.path.join(a.out, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(card(parity))
    files = []
    for dirpath, _, names in os.walk(a.out):
        for n in sorted(names):
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, a.out)
            if rel == "MANIFEST.json":
                continue
            with open(p, "rb") as g:
                data = g.read()
            files.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    files.sort(key=lambda x: x["path"])
    with open(os.path.join(a.out, "MANIFEST.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"space": "Bayanat-Labs/arabicwer", "library": "arabicwer (JavaScript)", "files": files}, f, indent=1)
        f.write("\n")
    print(f"built {a.out}: {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

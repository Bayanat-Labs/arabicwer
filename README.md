# arabicwer

**Arabic WER and CER under named, versioned, hash-identified normalisation policies. By Bayanat Labs.**

The same Arabic audio and the same speech-recognition system can score very differently depending on how the text is normalised before scoring: harakat, hamza forms, alef maqsura, taa marbuta, digits, punctuation and invisible characters all move the word error rate. arabicwer makes that step explicit. It scores a reference against a hypothesis under six named policies side by side, shows a word alignment, and identifies each policy by a SHA-256, so a paper or a leaderboard can say exactly how a number was computed: **WER 12.34% (arabicwer-1/lenient)**.

- Python package and command line, with a jiwer-style API (`wer`, `cer`, `process_words`, `process_characters`) and a jiwer transform.
- A specification ([spec/SPEC.md](spec/SPEC.md), Arabic: [spec/SPEC.ar.md](spec/SPEC.ar.md)) with rule ids, code points and order, including the tie-break rule of the alignment, so every implementation gives the same counts.
- Conformance fixtures (dev and acceptance) with expected values under every policy, and a JavaScript implementation that reproduces them field for field.
- A web page that runs in the browser (Hugging Face Space [Bayanat-Labs/arabicwer](https://huggingface.co/spaces/Bayanat-Labs/arabicwer)), and a case study on FLEURS Egyptian Arabic with two open Whisper models.
- Licence: Apache-2.0 (code); policies, specification, fixtures and case-study results CC BY 4.0.

Status: v0.1.0 pilot.

## Install

The PyPI package has not been released yet. Until it is, install from GitHub, pinned to the release tag:

```bash
pip install "git+https://github.com/Bayanat-Labs/arabicwer@v0.1.0"
```

This also installs [arabic-normalize](https://github.com/Bayanat-Labs/arabic-normalize) (pinned to a commit) and RapidFuzz. Python 3.9 to 3.14. `pip install arabicwer` will work once the package is published.

## Quick start

```python
>>> import arabicwer
>>> ref, hyp = "ذهب الولد إلى المدرسة", "ذهب الولد الى المدرسه"
>>> arabicwer.wer(ref, hyp)                    # default policy: lenient
0.0
>>> arabicwer.wer(ref, hyp, policy="raw")      # no normalisation
0.5
>>> arabicwer.wer(ref, hyp, policy="strict-orth")
0.5
>>> arabicwer.normalise("إِلَى المَدْرَسَةِ، ١٢٣", "lenient")
'الي المدرسه 123'
>>> out = arabicwer.process_words([ref, "جلس على الكرسي"], [hyp, "جلس علي الكرسي"], policy="raw")
>>> out.wer, out.substitutions, out.deletions, out.insertions, out.reference_units
(0.42857142857142855, 3, 0, 0, 7)
>>> arabicwer.load_policy("lenient").sha256
'b097f6eac978e001904c79ef0c4cacffde72e50a0e69bfe5b1492371a745d168'
```

A list of strings is scored as a corpus: errors and reference words are summed over all pairs before dividing. A pair with an empty reference has no rate of its own (`None`); its insertions still count. With jiwer installed, a policy also works as a jiwer transform:

```python
import jiwer, arabicwer
t = arabicwer.jiwer_transform("lenient")
jiwer.wer(ref, hyp, reference_transform=t, hypothesis_transform=t)   # same WER as arabicwer.wer(ref, hyp)
```

## Command line

```console
$ arabicwer score --tsv pairs.tsv                       # every policy side by side, with the swing
$ arabicwer score --ref refs.txt --hyp hyps.txt --bootstrap 1000 --format json --out report.json
$ arabicwer score --tsv pairs.tsv --format html --out report.html   # RTL-safe word diff per pair
$ arabicwer score --tsv pairs.tsv --policy raw --policy lenient --format csv
$ arabicwer diff "جلس على الكرسي" "جلس علي الكرسي" --policy raw
$ arabicwer normalise --policy lenient < transcripts.txt
$ arabicwer policies list
$ arabicwer policies show lenient --canonical         # the exact bytes that are hashed
```

`--tsv` reads `id<TAB>reference<TAB>hypothesis` (or two columns), with an optional header line. `--ref` and `--hyp` read one utterance per line. JSON output carries the policy id, its SHA-256 and the arabicwer version with every number, plus the alignment of every pair; CSV output has one row per pair and policy and one corpus row per policy.

## Policies

<!-- BEGIN:hashes -->
| Policy | Title | SHA-256 |
|---|---|---|
| `arabicwer-1/raw` | Raw text, split on white space | `25a0985e81d51658b5c0f94661e2ffb1f5b6af5edb6ec4c3402adca351d05a87` |
| `arabicwer-1/nfc` | Unicode NFC only | `9cdd67869a6ce442bfb5ae2931bb18835bc9eaa9431589295b51bf9e8f5ec2c4` |
| `arabicwer-1/dediac` | Diacritics removed | `46a6b2fb3d9475d006297af44a21e3dec95209005d2bd91833412e0acb589fbb` |
| `arabicwer-1/strict-orth` | Strict orthography: diacritics removed, digits unified | `83da6f52240c9ca5ce8a850a3a43bc0b03f50ccfde91a2acf1af267592a527ed` |
| `arabicwer-1/bayanat-norm-v1` | bayanat-norm-v1 from arabic-normalize, for scoring | `413cba6fa8e4021261f30c240d53281ee9759437d8b96c353ec5abc1f326a9f0` |
| `arabicwer-1/lenient` | Lenient orthography (default) | `b097f6eac978e001904c79ef0c4cacffde72e50a0e69bfe5b1492371a745d168` |
<!-- END:hashes -->

<!-- BEGIN:matrix -->
| Rule | `raw` | `nfc` | `dediac` | `strict-orth` | `bayanat-norm-v1` | `lenient` |
|---|---|---|---|---|---|---|
| R01 invalid code points | – | `drop` | `drop` | `drop` | `drop` | `drop` |
| R02 invisible format characters | – | – | `strip` | `strip` | `strip` | `strip` |
| R03 presentation forms | – | – | `map` | `map` | `map` | `map` |
| R04 honorific ligatures | – | – | – | – | `flag` | `expand` |
| R05 bidi and zero-width controls | – | – | `strip` | `strip` | `strip-except-meaningful` | `strip` |
| R06 NFC | – | `NFC` | `NFC` | `NFC` | `NFC` | `NFC` |
| R07 tatweel | – | – | `strip` | `strip` | `strip` | `strip` |
| R08 harakat | – | – | `strip` | `strip` | `strip` | `strip` |
| R09 Quranic marks | – | – | `strip` | `strip` | `strip` | `strip` |
| R10 superscript alef | – | – | `strip` | `strip` | `strip` | `strip` |
| R11 alef variants | – | – | – | – | `map` | `map` |
| R12 alef maqsura | – | – | – | – | `to-yeh` | `to-yeh` |
| R13 taa marbuta | – | – | – | – | `flag` | `to-heh` |
| R14 hamza carriers | – | – | – | – | – | – |
| R15 Persian and Urdu letters | – | – | – | – | – | `map` |
| R16 digits | – | – | – | `ascii` | `ascii` | `ascii` |
| R17 punctuation | – | – | `strip` | `strip` | `strip` | `strip` |
| R18 white space | – | `collapse` | `collapse` | `collapse` | `collapse` | `collapse` |
| R19 Latin case | – | – | `lower` | `lower` | `lower` | `lower` |
| T01 words split on white space | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

R20 (final NFC) runs whenever R06 does. `strip-except-meaningful` keeps a ZWNJ that blocks a join and a ZWJ inside an emoji sequence; `flag` leaves the text unchanged (arabic-normalize only records a flag); `drop` removes invalid code points.
<!-- END:matrix -->

`lenient` is the default. `raw`, `nfc`, `dediac` and `strict-orth` count spelling differences that `lenient` forgives, so every report shows them next to it: lenient folding also hides real errors, such as على (on) against علي (a name). `bayanat-norm-v1` keeps taa marbuta as written, like the arabic-normalize policy it comes from; `lenient` folds it to heh. Released policies never change; a new behaviour gets a new id. The rules are defined in [spec/SPEC.md](spec/SPEC.md).

## How to cite a score

Name the policy with the number, for example "WER 12.34% (arabicwer-1/lenient)". For full reproducibility add the policy SHA-256 and the arabicwer version, which every JSON report includes. Report the raw score next to the lenient one when the difference matters.

## Conformance and parity

<!-- BEGIN:counts -->
| Split | Fixtures | Cases (fixtures x 6 policies) | Passing (Python) |
|---|---|---|---|
| dev | 120 | 720 | 720 |
| acceptance | 40 | 240 | 240 |

The dev set has 12 categories of 10 fixtures: `alef_maqsura`, `clitics`, `code_switch`, `empty_silence`, `hamza`, `harakat`, `invisible`, `numerals`, `punctuation`, `repeated`, `taa_marbuta`, `tatweel_ligatures`. The acceptance set combines categories. 589 author-predicted word-error counts are checked against the computed values. Counts computed by `scripts/make_docs.py` from the fixture files on 2026-10-15.
<!-- END:counts -->

<!-- BEGIN:parity -->
- JavaScript (`web/arabicwer.js`) against Python: 6,960 of 6,960 cases identical, field for field: 960 fixture cases and 6,000 random Arabic and Latin pairs (1,000 pairs x 6 policies, with alignments). Computed by `scripts/crosscheck.mjs`.
- jiwer 4.0.0: under `raw`, WER and CER equal jiwer's (difference below 1e-12) on 10,000 random space-separated Arabic and Latin pairs with a non-empty reference (`tests/test_jiwer_parity.py`). jiwer gives a WER for an empty reference (the number of insertions); arabicwer reports `null` for that pair and counts its insertions in the corpus.
<!-- END:parity -->

## Case study: FLEURS Egyptian Arabic

<!-- BEGIN:casestudy -->
FLEURS Egyptian Arabic (`ar_eg`) test split, rows 1-100 of 428 (18.8 minutes of audio), transcribed by Bayanat Labs on a laptop CPU with two open models, then scored under every policy. Corpus WER:

| Policy | `whisper-large-v3-turbo` | `whisper-small` |
|---|---|---|
| `arabicwer-1/raw` | 25.57% | 39.17% |
| `arabicwer-1/nfc` | 25.57% | 39.17% |
| `arabicwer-1/dediac` | 10.73% | 27.85% |
| `arabicwer-1/strict-orth` | 10.52% | 27.64% |
| `arabicwer-1/bayanat-norm-v1` | 9.94% | 25.90% |
| `arabicwer-1/lenient` | 9.88% | 25.79% |

- `whisper-large-v3-turbo`: 15.69 points between `arabicwer-1/raw` and `arabicwer-1/lenient` (95% bootstrap interval 13.67-17.79).
- `whisper-small`: 13.38 points between `arabicwer-1/raw` and `arabicwer-1/lenient` (95% bootstrap interval 11.64-15.35).

![Corpus WER under each policy](casestudy/results/policy_swing.png)

Computed by `casestudy/score.py` from `casestudy/references.jsonl` and `casestudy/hyps/`. FLEURS is a public test set: these numbers measure scoring sensitivity, not model quality.
<!-- END:casestudy -->

Details, the per-rule ablation and ten example alignments: [casestudy/REPORT.md](casestudy/REPORT.md). The hypotheses, scores and chart are on Hugging Face: [Bayanat-Labs/arabicwer-fixtures](https://huggingface.co/datasets/Bayanat-Labs/arabicwer-fixtures).

## Web page

[`web/`](web/) is a static page that runs the JavaScript implementation in the browser: paste transcripts or upload a TSV file and see every policy side by side with a word diff. It loads no third-party resource, its Content-Security-Policy forbids network connections, and nothing you paste is uploaded or stored. `python scripts/build_space.py OUT` builds it for Hugging Face; `web/privacy_check.py` tests it in Chromium.

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest                                   # fixtures, jiwer parity, CLI, JavaScript parity (needs Node 20+)
python scripts/make_expected.py fixtures/dev.jsonl fixtures/acceptance.jsonl --check
python scripts/build_web.py --check
```

## Licence and citation

Code: Apache-2.0 ([LICENSE](LICENSE)). Policies, specification, fixtures, case-study hypotheses and results, and documentation: CC BY 4.0 ([LICENSE-data](LICENSE-data)). FLEURS reference text in `casestudy/references.jsonl`: Google, CC BY 4.0. See [NOTICE](NOTICE) for the bundled Unicode data and font. Cite with [CITATION.cff](CITATION.cff):

```bibtex
@software{bayanatlabs_arabicwer_2026,
  author  = {{Bayanat Labs}},
  title   = {arabicwer: Arabic WER and CER under named, versioned normalisation policies},
  version = {0.1.0},
  year    = {2026},
  url     = {https://github.com/Bayanat-Labs/arabicwer}
}
```

Contact and takedown requests: hello@bayanatlabs.com. Need production-grade, rights-cleared Arabic speech data? See [Bayanat Voice](https://www.bayanatlabs.com/products/voice).

---

<div dir="rtl" lang="ar">

## بالعربية

> The Arabic text has not yet been reviewed by a native Arabic writer; the English governs.

**arabicwer** أداة من بيانات لابز لحساب معدل خطأ الكلمات (WER) ومعدل خطأ الحروف (CER) في التعرّف الآلي على الكلام العربي، وفق سياسات توحيد مسمّاة ومرقّمة الإصدار ولكل منها بصمة SHA-256. يتغيّر معدل الخطأ للصوت نفسه والنظام نفسه بحسب طريقة توحيد النص قبل الحساب (الحركات، وصور الهمزة، والألف المقصورة، والتاء المربوطة، والأرقام، وعلامات الترقيم، والمحارف الخفية)، ولذلك تعرض الأداة النتيجة وفق ست سياسات جنبًا إلى جنب، وتُذكر النتيجة مع سياستها، مثل **WER 12.34% (arabicwer-1/lenient)**.

التثبيت حتى صدور الحزمة على PyPI:

</div>

```bash
pip install "git+https://github.com/Bayanat-Labs/arabicwer@v0.1.0"
```

<div dir="rtl" lang="ar">

المواصفة بالعربية: [spec/SPEC.ar.md](spec/SPEC.ar.md). الصفحة التفاعلية: [Bayanat-Labs/arabicwer](https://huggingface.co/spaces/Bayanat-Labs/arabicwer). الترخيص: Apache-2.0 للشيفرة، وCC BY 4.0 للسياسات والمواصفة وحالات الاختبار ونتائج دراسة الحالة. للتواصل وطلبات الإزالة: hello@bayanatlabs.com.

</div>

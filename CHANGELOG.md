# Changelog

## 0.1.0 (2026-10-15)

Pilot release.

- Specification arabicwer-spec-1 (English and Arabic) with normalisation rules R01-R20, word and character rules T01-T02, the alignment tie-break rule A01 and measures M01-M04.
- Six immutable scoring policies in the `arabicwer-1` namespace: `raw`, `nfc`, `dediac`, `strict-orth`, `bayanat-norm-v1` and `lenient` (default), each identified by its SHA-256. Normalisation uses arabic-normalize at commit dcc7f31cc5ae8b7b09e3de8401dcebe7aabc0240.
- Python package with `wer`, `cer`, `process_words`, `process_characters`, `score_pairs`, `jiwer_transform`; command line `arabicwer score | diff | normalise | policies`.
- 120 dev and 40 acceptance fixtures (synthetic text written by Bayanat Labs) with expected values under every policy.
- JavaScript implementation and a static web page (Hugging Face Space) that reproduce the Python results.
- Case study on FLEURS Egyptian Arabic (100 test utterances) with whisper-large-v3-turbo and whisper-small.

# arabicwer specification: arabicwer-spec-1

Status: pilot (arabicwer 0.1.0). Policy namespace: `arabicwer-1`. Licence: CC BY 4.0.

This file defines how arabicwer turns a reference and a hypothesis into word and character error rates, so that any implementation (the Python package and the JavaScript page in this repository, or any other) gives the same numbers, the same counts and the same alignment. Every rule has an id. A score is cited with its policy, for example **WER 12.34% (arabicwer-1/lenient)**; the policy id and its SHA-256 identify the computation exactly.

## 1. Policy files and identity

A scoring policy is a JSON object with these members:

| Member | Meaning |
|---|---|
| `policy_id` | `arabicwer-1/<name>` for the built-in policies; custom policies use any other id |
| `name` | short name (`raw`, `nfc`, `dediac`, `strict-orth`, `bayanat-norm-v1`, `lenient`) |
| `spec` | `arabicwer-spec-1` |
| `normaliser` | an [arabic-normalize](https://github.com/Bayanat-Labs/arabic-normalize) policy object (spec `arabic-normalize-spec-1`, Unicode 18.0.0), or `null` for no normalisation |
| `tokens` | `{"words": "split-on-white-space", "characters": "code-points-of-words-joined-by-one-space"}` (the only value in this spec) |
| `meta` | titles, descriptions, licence; not part of the hash |

**Policy hash** = SHA-256 (lowercase hex) of the canonical JSON of the policy object without its top-level `meta` member: object keys sorted by code point at every level, UTF-8, separators `,` and `:` with no whitespace, non-ASCII characters not escaped. This is the same rule arabic-normalize uses. `arabicwer policies show <name> --canonical` prints the exact bytes that are hashed. Members whose name starts with `$` are rejected anywhere in a policy, and nothing is ever fetched.

**Immutability.** A released policy never changes. A change in behaviour ships as a new id in a new namespace (for example `arabicwer-2/lenient`); `arabicwer-1/...` keeps its meaning and its hash. The built-in policy files are in `src/arabicwer/policies/` and their hashes in `spec/policy_hashes.json`. A custom policy may not reuse a built-in id with different behaviour.

## 2. Normalisation rules (R01-R20)

The normaliser applies the stages of arabic-normalize-spec-1 in this fixed order. A stage set to `keep` does nothing. Character classes come from the Unicode 18.0.0 tables bundled with arabic-normalize, never from the Unicode version of the running Python or browser. The arabic-normalize specification (`docs/SPEC.md` in that repository) gives the full detail of each stage; the summary below names the code points.

| Rule | Stage | What it does when enabled |
|---|---|---|
| R01 | reject_invalid | removes lone surrogates U+D800-DFFF, control characters (General_Category Cc) other than U+0009-000D and U+0085, and noncharacters |
| R02 | strip_controls | removes U+00AD soft hyphen, U+2060 word joiner, U+2061-2064, U+206A-206F, U+FFF9-FFFB and U+FEFF |
| R03 | presentation_forms | maps Arabic presentation forms U+FB50-FDFF and U+FE70-FEFF to their compatibility decomposition (NFKC), including the lam-alef ligatures U+FEF5-FEFC; honorific ligatures (R04) are excluded |
| R04 | ligatures_honorific | U+0610-0614, U+FD40-FD4F, U+FDCF, U+FDF0-FDFF, U+10ED1-10ED8: `keep` (one token, for example ﷺ U+FDFA) or `expand` (U+FDF0-FDFC become their words, so ﷺ becomes four words) |
| R05 | bidi_zw | bidi controls U+061C, U+200E, U+200F, U+202A-202E, U+2066-2069 and zero-width U+200B-200D: `strip` removes them all; `strip-except-meaningful` keeps a ZWNJ that blocks a cursive join and a ZWJ inside an emoji sequence |
| R06 | canonical_order | Unicode NFC (UAX #15) |
| R07 | tatweel | removes U+0640 |
| R08 | diacritics | removes the harakat U+064B-0652 (tanween, fatha, damma, kasra, shadda, sukun) |
| R09 | quranic_marks | removes U+0615-061A, an uncomposed U+0653, U+0656-0658, U+06D6-06ED, U+0898-089F, U+08CA-08E9, U+08F0-08F3, U+08FF, U+10EFD-10EFF |
| R10 | superscript_alef | removes U+0670 |
| R11 | alef_variants | U+0622 آ, U+0623 أ, U+0625 إ, U+0671 ٱ to U+0627 ا |
| R12 | alef_maqsura | U+0649 ى to U+064A ي |
| R13 | taa_marbuta | U+0629 ة to U+0647 ه |
| R14 | hamza_carriers | U+0624 ؤ to U+0648 و and U+0626 ئ to U+064A ي (no arabicwer-1 policy uses it) |
| R15 | persian_urdu_letters | U+06CC ی to ي; U+06A9 ک to ك; U+06C1, U+06C2, U+06BE, U+06D5, U+06C0 to ه |
| R16 | digits | U+0660-0669 and U+06F0-06F9 to ASCII 0-9 |
| R17 | punctuation | replaces every punctuation character (General_Category Pc, Pd, Ps, Pe, Pi, Pf, Po, for example ، ؛ ؟ ٪ ٫ ٬ « » . , : - ") with a space |
| R18 | whitespace | collapses every white-space run to one space and trims both ends |
| R19 | latin_case | lowercases Latin letters (Script=Latin, simple lowercase mapping) |
| R20 | canonical_order (final) | NFC again, when R06 is on |

## 3. Words and characters (T01-T02)

- **T01 words.** After normalisation, the words of a text are its maximal runs of code points that are not White_Space (Unicode PropList: U+0009-000D, U+0020, U+0085, U+00A0, U+1680, U+2000-200A, U+2028, U+2029, U+202F, U+205F, U+3000). Leading, trailing and repeated white space never counts. The `raw` policy applies T01 to the text as given.
- **T02 characters.** The characters scored by CER are the code points (not UTF-16 units, not bytes) of the words joined by one U+0020 space. Spaces between words count as characters, as in jiwer.
- The normalised text shown in reports (`ref_norm`, `hyp_norm`) is the words joined by one space.

## 4. Alignment (A01)

Words (or characters) are aligned by the Levenshtein distance with unit costs: substitution, deletion and insertion each cost 1, a hit costs 0. Tokens are equal when their code-point sequences are identical. When several alignments have the minimal cost, the backtrace runs from the end of both sequences and, at each cell (i, j) of the cost matrix D, takes the first step that stays on a minimal path, in this order:

1. hit: i > 0, j > 0, ref[i] = hyp[j] and D[i][j] = D[i-1][j-1];
2. insertion: j > 0 and D[i][j] = D[i][j-1] + 1;
3. deletion: i > 0 and D[i][j] = D[i-1][j] + 1;
4. substitution: D[i][j] = D[i-1][j-1] + 1.

The total S + D + I is the edit distance that jiwer and RapidFuzz return. The split between S, D and I can differ from jiwer's when several minimal alignments exist, because jiwer leaves the tie to RapidFuzz; arabicwer fixes it here so that every implementation agrees. Implementations may refuse a pair whose matrix would exceed 50,000,000 cells; this never changes a result.

## 5. Measures (M01-M04)

- **M01 rates.** For one pair, WER = (S + D + I) / N, where N is the number of reference words; CER is the same over characters. When N = 0 the rate is undefined and reported as `null`. WER can exceed 1.
- **M02 corpus rates.** For a set of pairs, S, D, I and N are summed over all pairs before dividing: corpus WER = Σ(S + D + I) / ΣN. A pair with an empty reference adds its insertions to the numerator and nothing to N. This is the default number arabicwer reports. The mean of per-pair rates is reported separately and labelled `mean_pair_wer`; it skips pairs with N = 0.
- **M03 swing.** For one set of pairs scored under several policies, swing = the largest minus the smallest corpus WER, with the policies that give them.
- **M04 bootstrap intervals.** When requested, pairs are resampled with replacement B times (default seed 0, Python `random.Random(seed).randrange`), the same resamples are used for every policy, and the 95% interval is [v(round(0.025 (B-1))), v(round(0.975 (B-1)))] of the sorted corpus values. The same resamples give an interval for the swing.

## 6. The six arabicwer-1 policies

Generated from the policy files by `scripts/make_docs.py`. A tick means the rule is applied; `keep` stages are left out.

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

### Taa marbuta: two policies on purpose

`bayanat-norm-v1` follows the policy of the same name in arabic-normalize: it keeps ة as written, because ة and ه distinguish real words (عمة "aunt" and عمه "his uncle"). `lenient` folds ة to ه, because transcripts and recognisers write the two interchangeably at the end of a word. Both are useful, and they give different numbers, so they are separate policies and every score names the one it used. `bayanat-norm-v1` also keeps a ZWNJ that blocks a cursive join, as its source policy does; the other cleaning policies remove all zero-width characters.

## 7. Known limits of arabicwer-1

- No inverse text normalisation: ٣ and ثلاثة are different words (R16 unifies digit scripts only).
- Clitics are not segmented: وأخي against و أخي is two word errors and one character error. Tokenisation is white space only.
- R17 replaces punctuation with a space, so 5:30, 3.5 and 1,000 split into two words, and e-learning into two.
- R02 and R05 remove invisible characters without inserting a space, so a zero width space or word joiner between two words joins them.
- R10 removes the superscript alef: هٰذا becomes هذا (the usual spelling), but Quranic الكتٰب becomes الكتب, not الكتاب.
- Hamza on waw and yeh seats (R14) is kept by every arabicwer-1 policy: سؤال and سوال differ.
- Lenient folding hides real errors: على and علي, عمة and عمه become identical. That is why every report shows the raw and strict scores next to the lenient one.
- Fullwidth Latin letters are not folded to ASCII (no policy uses NFKC).

## 8. Conformance

`fixtures/dev.jsonl` and `fixtures/acceptance.jsonl` hold reference and hypothesis pairs, written for this purpose by Bayanat Labs, with the expected normalised texts and counts under every policy. The expected values are computed by `scripts/make_expected.py`, which does not use the arabicwer package (it normalises with arabic-normalize, splits words with its own table and aligns with its own Levenshtein code, and checks the distance against RapidFuzz); each fixture also carries the word-error counts its author predicted (`design_word_errors`), which the script checks. An implementation conforms to arabicwer-spec-1 when it reproduces every field of every fixture under every policy.

<!-- BEGIN:counts -->
| Split | Fixtures | Cases (fixtures x 6 policies) | Passing (Python) |
|---|---|---|---|
| dev | 120 | 720 | 720 |
| acceptance | 40 | 240 | 240 |

The dev set has 12 categories of 10 fixtures: `alef_maqsura`, `clitics`, `code_switch`, `empty_silence`, `hamza`, `harakat`, `invisible`, `numerals`, `punctuation`, `repeated`, `taa_marbuta`, `tatweel_ligatures`. The acceptance set combines categories. 589 author-predicted word-error counts are checked against the computed values. Counts computed by `scripts/make_docs.py` from the fixture files on 2026-10-15.
<!-- END:counts -->

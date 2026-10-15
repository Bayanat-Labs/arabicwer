# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""arabicwer: Arabic WER and CER under named, versioned, hash-identified normalisation policies.

    >>> import arabicwer
    >>> arabicwer.wer("ذهب الولد إلى المدرسة", "ذهب الولد الى المدرسه")   # policy "lenient" (default)
    0.0
    >>> arabicwer.wer("ذهب الولد إلى المدرسة", "ذهب الولد الى المدرسه", policy="raw")
    0.5
"""
from ._version import __version__
from .align import AlignmentChunk, AlignmentTooLarge
from .jiwer_compat import jiwer_transform
from .measures import CharacterOutput, WordOutput, cer, process_characters, process_words, wer
from .policy import (DEFAULT_POLICY, NAMESPACE, POLICY_NAMES, SPEC_ID, Policy, PolicyError, list_policies,
                     load_policy, policy_hash, split_words)
from .report import diff_text, diff_tokens, score_pair, score_pairs


def normalise(text: str, policy="lenient") -> str:
    """The text a policy scores: normalised, then its words joined by one space."""
    return load_policy(policy).normalise(text)


normalize = normalise

__all__ = [
    "__version__", "SPEC_ID", "NAMESPACE", "POLICY_NAMES", "DEFAULT_POLICY",
    "wer", "cer", "process_words", "process_characters", "WordOutput", "CharacterOutput", "AlignmentChunk",
    "AlignmentTooLarge", "normalise", "normalize", "split_words", "score_pair", "score_pairs", "diff_tokens",
    "diff_text", "Policy", "PolicyError", "list_policies", "load_policy", "policy_hash", "jiwer_transform",
]

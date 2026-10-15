# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Scoring policies: immutable, hash-identified definitions of how text is normalised and split before scoring.

A scoring policy is a JSON object with a ``normaliser`` (an arabic-normalize policy object, or null for ``raw``)
and a fixed tokenisation. Its identity is the SHA-256 of its canonical JSON without the ``meta`` member, so a
score can be cited as "WER (arabicwer-1/lenient, sha256 ...)" and reproduced exactly. See spec/SPEC.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from importlib import resources
from typing import Any, Dict, List, Optional, Union

import arabic_normalize as _an

SPEC_ID = "arabicwer-spec-1"
NAMESPACE = "arabicwer-1"
#: Built-in policy names in display order (raw first, then increasingly lenient).
POLICY_NAMES = ("raw", "nfc", "dediac", "strict-orth", "bayanat-norm-v1", "lenient")
DEFAULT_POLICY = "lenient"
TOKENS = {"words": "split-on-white-space", "characters": "code-points-of-words-joined-by-one-space"}

#: Unicode White_Space=Yes (PropList.txt). Words are maximal runs of other code points (rule T01).
WHITE_SPACE = "\u0009\u000a\u000b\u000c\u000d \u0085        " \
              "         　"
_WS_RUN = re.compile("[" + re.escape(WHITE_SPACE) + "]+")
_ALLOWED_KEYS = {"policy_id", "name", "spec", "normaliser", "tokens", "meta"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9./-]{0,62}[a-z0-9]$")


class PolicyError(ValueError):
    """An invalid or unknown scoring policy."""


def canonical_json(obj: Any) -> str:
    """Canonical JSON: keys sorted by code point, no whitespace, non-ASCII kept (same rule as arabic-normalize)."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def policy_hash(obj: Dict[str, Any]) -> str:
    """SHA-256 (hex) of the canonical JSON of a policy object without its ``meta`` member."""
    body = {k: v for k, v in obj.items() if k != "meta"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def split_words(text: str) -> List[str]:
    """Rule T01: words are the maximal runs of code points that are not White_Space."""
    return [w for w in _WS_RUN.split(text) if w]


def _no_dollar(obj: Any, path: str) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith("$"):
                raise PolicyError(f"{path}: member {k!r} is not allowed (nothing is ever fetched)")
            _no_dollar(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _no_dollar(v, f"{path}[{i}]")


def validate_policy(obj: Any) -> None:
    """Raise PolicyError unless ``obj`` is a valid scoring-policy object."""
    if not isinstance(obj, dict):
        raise PolicyError("a policy must be a JSON object")
    _no_dollar(obj, "policy")
    unknown = set(obj) - _ALLOWED_KEYS
    if unknown:
        raise PolicyError(f"unknown policy members: {sorted(unknown)}")
    for key in ("policy_id", "name", "spec", "normaliser", "tokens"):
        if key not in obj:
            raise PolicyError(f"missing policy member: {key}")
    if not isinstance(obj["policy_id"], str) or not _ID_RE.match(obj["policy_id"]):
        raise PolicyError("policy_id must be 2-64 characters of a-z, 0-9, '.', '/' and '-'")
    if not isinstance(obj["name"], str) or not obj["name"]:
        raise PolicyError("name must be a non-empty string")
    if obj["spec"] != SPEC_ID:
        raise PolicyError(f"spec must be {SPEC_ID!r}")
    if obj["tokens"] != TOKENS:
        raise PolicyError(f"tokens must be {TOKENS!r} in {SPEC_ID}")
    if obj["normaliser"] is not None:
        try:
            _an.load_policy(obj["normaliser"])
        except Exception as exc:  # arabic-normalize explains what is wrong
            raise PolicyError(f"normaliser: {exc}") from exc
    if "meta" in obj and not isinstance(obj["meta"], dict):
        raise PolicyError("meta must be an object")


class Policy:
    """A loaded scoring policy. Immutable; compare and hash by ``sha256``."""

    __slots__ = ("policy_id", "name", "sha256", "data", "builtin", "_norm")

    def __init__(self, data: Dict[str, Any], builtin: bool = False):
        validate_policy(data)
        object.__setattr__(self, "data", json.loads(json.dumps(data)))
        object.__setattr__(self, "policy_id", data["policy_id"])
        object.__setattr__(self, "name", data["name"])
        object.__setattr__(self, "sha256", policy_hash(data))
        object.__setattr__(self, "builtin", builtin)
        norm = data["normaliser"]
        object.__setattr__(self, "_norm", None if norm is None else _an.load_policy(norm))

    def __setattr__(self, key, value):
        raise AttributeError("Policy objects are immutable")

    def __repr__(self) -> str:
        return f"Policy({self.policy_id!r}, sha256={self.sha256[:12]}...)"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Policy) and other.sha256 == self.sha256

    def __hash__(self) -> int:
        return hash(self.sha256)

    @property
    def meta(self) -> Dict[str, Any]:
        return dict(self.data.get("meta", {}))

    @property
    def normaliser_sha256(self) -> Optional[str]:
        return None if self._norm is None else _an.policy_hash(self.data["normaliser"])

    def normalise(self, text: str) -> str:
        """Apply the policy and return the scoring text: the words joined by one space."""
        return " ".join(self.words(text))

    def words(self, text: str) -> List[str]:
        """The words the policy scores (rules R01-R20, then T01)."""
        if not isinstance(text, str):
            raise TypeError(f"expected str, got {type(text).__name__}")
        if self._norm is not None:
            text = _an.normalize(text, self._norm)
        return split_words(text)

    def chars(self, text: str) -> List[str]:
        """The characters the policy scores for CER (rule T02): code points of the words joined by one space."""
        return list(" ".join(self.words(text)))

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.data, ensure_ascii=False, indent=indent) + "\n"

    def canonical(self) -> str:
        """The exact string whose SHA-256 is the policy hash."""
        return canonical_json({k: v for k, v in self.data.items() if k != "meta"})


_BUILTIN: Dict[str, Policy] = {}


def _builtin(name: str) -> Policy:
    if name not in _BUILTIN:
        raw = resources.files("arabicwer.policies").joinpath(f"{name}.json").read_text(encoding="utf-8")
        _BUILTIN[name] = Policy(json.loads(raw), builtin=True)
    return _BUILTIN[name]


def list_policies() -> List[Policy]:
    """The built-in policies, in display order."""
    return [_builtin(n) for n in POLICY_NAMES]


PolicyLike = Union[str, Dict[str, Any], Policy, "os.PathLike[str]"]


def load_policy(policy: PolicyLike = DEFAULT_POLICY) -> Policy:
    """Load a policy from a built-in name ("lenient"), a full id ("arabicwer-1/lenient"), a JSON file path,
    a dict or a Policy. Custom policies may not reuse a built-in id with different behaviour."""
    if isinstance(policy, Policy):
        return policy
    if isinstance(policy, str):
        name = policy[len(NAMESPACE) + 1:] if policy.startswith(NAMESPACE + "/") else policy
        if name in POLICY_NAMES:
            return _builtin(name)
        if policy.endswith(".json") and os.path.isfile(policy):
            with open(policy, encoding="utf-8") as f:
                return load_policy(json.load(f))
        raise PolicyError(f"unknown policy {policy!r}; built-in policies: {', '.join(POLICY_NAMES)}")
    if isinstance(policy, os.PathLike):
        return load_policy(os.fspath(policy))
    if isinstance(policy, dict):
        p = Policy(policy)
        pid = p.policy_id
        if pid.startswith(NAMESPACE + "/"):
            name = pid[len(NAMESPACE) + 1:]
            if name not in POLICY_NAMES or _builtin(name).sha256 != p.sha256:
                raise PolicyError(f"policy id {pid!r} is reserved for the built-in policies; choose another id")
        return p
    raise PolicyError(f"cannot load a policy from {type(policy).__name__}")

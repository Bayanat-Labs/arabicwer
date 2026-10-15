# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_fixtures():
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "fixtures", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            out.extend(json.loads(line) for line in f if line.strip())
    return out

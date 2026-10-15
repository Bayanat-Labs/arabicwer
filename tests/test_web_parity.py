# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""The JavaScript scorer gives the same records as Python on every fixture and on 1,000 random pairs."""
import os
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT

NODE = shutil.which("node")


def test_web_policies_in_sync():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_web.py"), "--check"])
    assert r.returncode == 0


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_js_matches_python(tmp_path):
    rnd = tmp_path / "random.json"
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "crosscheck_random.py"), str(rnd)], check=True)
    fixtures = sorted(os.path.join(ROOT, "fixtures", f) for f in os.listdir(os.path.join(ROOT, "fixtures"))
                      if f.endswith(".jsonl"))
    r = subprocess.run([NODE, os.path.join(ROOT, "scripts", "crosscheck.mjs"), *fixtures, str(rnd)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

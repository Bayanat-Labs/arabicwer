# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
import csv
import io
import json

from arabicwer.cli import main


def run(capsys, *args):
    code = main(list(args))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_score_tsv_formats(tmp_path, capsys):
    tsv = tmp_path / "pairs.tsv"
    tsv.write_text("id\treference\thypothesis\nu1\tذهب الولد إلى المدرسة\tذهب الولد الى المدرسه\n"
                   "u2\tمرحبا، كيف حالك؟\tمرحبا كيف حالك\n", encoding="utf-8")
    code, out, _ = run(capsys, "score", "--tsv", str(tsv))
    assert code == 0 and "arabicwer-1/lenient" in out and "WER swing" in out
    code, out, _ = run(capsys, "score", "--tsv", str(tsv), "--format", "json", "--bootstrap", "20")
    rep = json.loads(out)
    assert rep["pairs_total"] == 2 and len(rep["policies"]) == 6
    assert rep["pairs"][0]["scores"]["arabicwer-1/raw"]["alignment"][0][0] == "equal"
    code, out, _ = run(capsys, "score", "--tsv", str(tsv), "--format", "csv", "--policy", "raw", "--policy", "lenient")
    rows = list(csv.DictReader(io.StringIO(out)))
    assert len(rows) == 2 * 2 + 2 and rows[-1]["pair_id"] == "*corpus*"
    html_out = tmp_path / "r.html"
    code, _, _ = run(capsys, "score", "--tsv", str(tsv), "--format", "html", "--out", str(html_out))
    page = html_out.read_text(encoding="utf-8")
    assert code == 0 and "<bdi>" in page and 'dir="rtl"' in page


def test_score_ref_hyp_files(tmp_path, capsys):
    (tmp_path / "ref.txt").write_text("شجرة\nمدرسة كبيرة\n", encoding="utf-8")
    (tmp_path / "hyp.txt").write_text("شجره\nمدرسه\n", encoding="utf-8")
    code, out, _ = run(capsys, "score", "--ref", str(tmp_path / "ref.txt"), "--hyp", str(tmp_path / "hyp.txt"),
                       "--policy", "raw", "--format", "json")
    rep = json.loads(out)
    assert rep["policies"][0]["words"]["wer"] == 1.0
    (tmp_path / "hyp2.txt").write_text("one line\n", encoding="utf-8")
    code, _, err = run(capsys, "score", "--ref", str(tmp_path / "ref.txt"), "--hyp", str(tmp_path / "hyp2.txt"))
    assert code == 2 and "lines" in err


def test_diff_normalise_policies(capsys):
    code, out, _ = run(capsys, "diff", "جلس على الكرسي", "جلس علي الكرسي", "--policy", "raw")
    assert code == 0 and "S\tعلى\tعلي" in out
    code, out, _ = run(capsys, "normalise", "إِلَى المَدْرَسَةِ", "--policy", "lenient")
    assert out.strip() == "الي المدرسه"
    code, out, _ = run(capsys, "policies", "list")
    assert len(out.strip().splitlines()) == 6
    code, out, _ = run(capsys, "policies", "show", "lenient", "--canonical")
    assert out.startswith('{"name":"lenient"')
    code, _, err = run(capsys, "policies", "show", "nope")
    assert code == 2

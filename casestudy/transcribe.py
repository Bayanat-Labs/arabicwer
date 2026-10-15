# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Transcribe FLEURS Egyptian Arabic (ar_eg) test utterances with an open Whisper model (faster-whisper).

Reads rows 1-N of the test split (file order) of google/fleurs at a pinned revision straight from the
Hugging Face Hub (audio is decoded in memory and never written to disk), and appends one JSON line per
utterance to casestudy/hyps/<name>.jsonl. Re-running resumes after the last finished utterance.

Needs: faster-whisper==1.2.1, pyarrow, huggingface_hub, numpy.
Usage: python casestudy/transcribe.py --model large-v3-turbo [--n 100] [--threads 8]
       python casestudy/transcribe.py --references-only
"""
from __future__ import annotations

import argparse
import io
import json
import os
import struct
import time

import numpy as np

FLEURS = "google/fleurs"
REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
PARQUET = "parquet-data/ar_eg/test-00000-of-00001.parquet"
HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = {
    # name: (original model, faster-whisper (CTranslate2) conversion used here)
    "large-v3-turbo": ("openai/whisper-large-v3-turbo", "mobiuslabsgmbh/faster-whisper-large-v3-turbo"),
    "small": ("openai/whisper-small", "Systran/faster-whisper-small"),
}
DECODE = {"language": "ar", "task": "transcribe", "beam_size": 5, "temperature": 0.0, "vad_filter": False,
          "condition_on_previous_text": False}


def rows(n):
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    fs = HfFileSystem()
    with fs.open(f"datasets/{FLEURS}@{REVISION}/{PARQUET}", "rb") as fh:
        pf = pq.ParquetFile(fh)
        total = pf.metadata.num_rows
        seen = 0
        for rg in range(pf.metadata.num_row_groups):
            tab = pf.read_row_group(rg, columns=["id", "path", "num_samples", "audio", "transcription", "raw_transcription"])
            for rec in tab.to_pylist():
                if seen >= n:
                    return
                seen += 1
                yield seen, total, rec


def decode_wav(data: bytes) -> np.ndarray:
    """16 kHz mono WAV (16-bit PCM or 32-bit float) to float32 samples in [-1, 1]."""
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE", "not a WAV file"
    pos, fmt, pcm = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            pcm = body
        pos += 8 + size + (size & 1)
    tag, channels, rate, _, _, bits = fmt
    assert channels == 1 and rate == 16000, f"expected 16 kHz mono, got {channels} ch {rate} Hz"
    if tag == 1 and bits == 16:
        return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    if tag == 3 and bits == 32:
        return np.frombuffer(pcm, dtype="<f4").astype(np.float32)
    raise ValueError(f"unsupported WAV format {tag}/{bits}")


def utt_key(rec) -> str:
    return os.path.basename(rec["audio"].get("path") or rec["path"])


def write_references(n):
    out = os.path.join(HERE, "references.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for idx, total, rec in rows(n):
            f.write(json.dumps({"row": idx, "fleurs_id": rec["id"], "utt_key": utt_key(rec),
                                "duration_s": round(rec["num_samples"] / 16000, 3),
                                "raw_transcription": rec["raw_transcription"], "transcription": rec["transcription"],
                                "split_rows_total": total}, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


def transcribe(name, n, threads):
    import ctranslate2
    import faster_whisper
    from huggingface_hub import HfApi, snapshot_download

    original, weights = MODELS[name]
    sha = HfApi().model_info(weights).sha
    path = snapshot_download(weights, revision=sha)
    model = faster_whisper.WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=threads)
    out = os.path.join(HERE, "hyps", f"{name}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    done = set()
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            done = {json.loads(line)["utt_key"] for line in f if line.strip()}
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f:
        for idx, total, rec in rows(n):
            key = utt_key(rec)
            if key in done:
                continue
            segments, _info = model.transcribe(decode_wav(rec["audio"]["bytes"]), **DECODE)
            hyp = " ".join(s.text.strip() for s in segments).strip()
            f.write(json.dumps({"row": idx, "fleurs_id": rec["id"], "utt_key": key, "model_id": original,
                                "model_weights": f"{weights}@{sha}",
                                "runtime": f"faster-whisper {faster_whisper.__version__}, CTranslate2 "
                                           f"{ctranslate2.__version__}, CPU, int8",
                                "decode_params": DECODE, "hypothesis": hyp}, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{name} {idx}/{n} {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=sorted(MODELS))
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--references-only", action="store_true")
    a = ap.parse_args()
    if a.references_only:
        write_references(a.n)
    else:
        transcribe(a.model, a.n, a.threads)


if __name__ == "__main__":
    main()

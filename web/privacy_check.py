#!/usr/bin/env python3
# Copyright 2026 Bayanat Labs
# SPDX-License-Identifier: Apache-2.0
"""Render and privacy check of the built web page (Hugging Face Space) in headless Chromium with Playwright.

Usage:
  python scripts/build_space.py OUT_DIR
  python web/privacy_check.py OUT_DIR [--fixtures fixtures/dev.jsonl] [--json OUT.json] [--shots DIR]

The script serves OUT_DIR on 127.0.0.1 (no Content-Security-Policy header, as on Hugging Face static hosting),
opens the page at 1280 and 375 pixels wide and checks:
  1. the worked example is scored under all six policies, and the lenient corpus WER equals the value
     computed from the frozen fixture expectations;
  2. scoring runs in a Web Worker started from a blob: URL, where fetch() and XMLHttpRequest fail (the page's
     CSP, connect-src 'none', applies there), and fetch() fails in the page itself;
  3. after load, scoring a marker text causes no network request and writes nothing to localStorage,
     sessionStorage, IndexedDB or cookies;
  4. the Arabic interface switches to right-to-left, and neither width scrolls sideways.
Exit code 0 when every check passes. Needs `pip install playwright` and `python -m playwright install chromium`.
"""
import argparse
import functools
import http.server
import json
import os
import sys
import threading
import time
import urllib.request

from playwright.sync_api import sync_playwright

MARKER = "كلمهسريه7f3a"
WORKED_IDS = None  # the worked example is matched to fixtures by text


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(directory):
    handler = functools.partial(QuietHandler, directory=directory)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "http://127.0.0.1:%d/" % httpd.server_address[1]


def wait_text(page, selector, pred, timeout=20.0):
    end = time.time() + timeout
    v = None
    while time.time() < end:
        v = page.text_content(selector) or ""
        if pred(v):
            return v
        time.sleep(0.1)
    raise TimeoutError(f"{selector} did not match; last value {v!r}")


PROBE_FETCH = """async (url) => {
  try { const r = await fetch(url, {cache: 'no-store'}); return 'allowed:' + r.status; }
  catch (e) { return 'blocked:' + e.name; }
}"""
PROBE_XHR = """(url) => new Promise((resolve) => {
  try {
    const x = new XMLHttpRequest();
    x.onload = () => resolve('allowed:' + x.status);
    x.onerror = () => resolve('blocked:error');
    x.open('GET', url);
    x.send();
  } catch (e) { resolve('blocked:' + e.name); }
})"""


def expected_lenient(space_dir, fixtures):
    """Corpus WER under lenient for the worked example, from the frozen fixture values."""
    src = open(os.path.join(space_dir, "examples.js"), encoding="utf-8").read()
    pairs = json.loads("[" + src.split("WORKED = [", 1)[1].split("];", 1)[0].replace("'", '"').rstrip().rstrip(",") + "]")
    fx = {}
    with open(fixtures, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            fx[(r["ref"], r["hyp"])] = r["expected"]["lenient"]
    e = n = 0
    for ref, hyp in pairs:
        x = fx[(ref, hyp)]
        e += x["S"] + x["D"] + x["I"]
        n += x["N"]
    return f"{100 * e / n:.2f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("space_dir")
    ap.add_argument("--fixtures", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "dev.jsonl"))
    ap.add_argument("--json")
    ap.add_argument("--shots")
    args = ap.parse_args()
    httpd, base = serve(args.space_dir)
    probe_url = base + "README.md"
    want = expected_lenient(args.space_dir, args.fixtures)
    checks = {}
    after = []
    try:
        with urllib.request.urlopen(probe_url) as r:
            checks["probe_url_reachable_outside_page"] = r.status == 200
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width, height in ((1280, 900), (375, 812)):
                ctx = browser.new_context(viewport={"width": width, "height": height})
                page = ctx.new_page()
                requests, errors = [], []
                page.on("request", lambda r: requests.append(r.url))
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(base + "?lang=en")
                page.click("#worked")
                rows = page.locator("#scores tbody tr")
                wait_text(page, "#scores tbody", lambda v: rows.count() == 6)
                len_wer = page.locator("#scores tbody tr.default td.num").first.text_content().strip()
                checks[f"w{width}_six_policies"] = rows.count() == 6
                checks[f"w{width}_lenient_wer_matches_fixtures"] = len_wer.startswith(want)
                checks[f"w{width}_diff_rendered_rtl"] = page.locator(".align[dir=rtl] bdi").count() > 0
                checks[f"w{width}_no_page_errors"] = not errors
                sw = page.evaluate("() => [document.scrollingElement.scrollWidth, window.innerWidth]")
                checks[f"w{width}_no_horizontal_scroll"] = sw[0] <= sw[1]
                if args.shots:
                    os.makedirs(args.shots, exist_ok=True)
                    page.screenshot(path=os.path.join(args.shots, f"space-en-{width}.png"), full_page=True)
                if width == 1280:
                    workers = page.workers
                    checks["processing_worker_from_blob_url"] = len(workers) == 1 and workers[0].url.startswith("blob:")
                    if workers:
                        checks["worker_fetch_blocked"] = workers[0].evaluate(PROBE_FETCH, probe_url).startswith("blocked:")
                        checks["worker_xhr_blocked"] = workers[0].evaluate(PROBE_XHR, probe_url).startswith("blocked:")
                    checks["page_fetch_blocked"] = page.evaluate(PROBE_FETCH, probe_url).startswith("blocked:")
                    n_before = len(requests)
                    page.fill("#ref", MARKER + " إلى")
                    page.fill("#hyp", MARKER + " الي")
                    page.click("#score")
                    wait_text(page, "#diffs", lambda v: MARKER in v)
                    page.select_option("#diff-policy", "arabicwer-1/raw")
                    time.sleep(0.5)
                    after = requests[n_before:]
                    checks["no_request_after_load"] = not after
                    checks["no_request_carries_marker"] = not any(MARKER in u for u in requests)
                    storage = page.evaluate("""async () => ({
                      local: JSON.stringify(Object.entries(localStorage)),
                      session: JSON.stringify(Object.entries(sessionStorage)),
                      idb: indexedDB.databases ? JSON.stringify(await indexedDB.databases()) : '[]',
                      cookie: document.cookie,
                    })""")
                    checks["no_storage_written"] = storage["local"] == "[]" and storage["session"] == "[]"
                    checks["no_indexeddb"] = storage["idb"] == "[]"
                    checks["no_cookies"] = storage["cookie"] == "" and not ctx.cookies()
                # Arabic interface
                page.goto(base + "?lang=ar")
                page.click("#worked")
                wait_text(page, "#scores tbody", lambda v: rows.count() == 6)
                checks[f"w{width}_arabic_rtl"] = page.evaluate("() => document.documentElement.dir") == "rtl"
                checks[f"w{width}_arabic_review_note"] = page.is_visible("#ar-note")
                sw = page.evaluate("() => [document.scrollingElement.scrollWidth, window.innerWidth]")
                checks[f"w{width}_arabic_no_horizontal_scroll"] = sw[0] <= sw[1]
                if args.shots:
                    page.screenshot(path=os.path.join(args.shots, f"space-ar-{width}.png"), full_page=True)
                ctx.close()
            browser.close()
    finally:
        httpd.shutdown()
    ok = all(checks.values())
    result = {"base": "local static server (no CSP header)", "ok": ok, "expected_lenient_wer": want,
              "checks": checks, "requests_after_load": len(after)}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// Compare the JavaScript scorer (web/arabicwer.js) with the Python package.
//   node scripts/crosscheck.mjs [--out parity.json] FILE...
// A .jsonl FILE is a fixture file: every fixture is scored under every policy and compared with its
// frozen `expected` values. A .json FILE holds pairs scored by Python ({policies, pairs: [{ref, hyp, scores}]},
// written by scripts/crosscheck_random.py); every record, including the alignment, must be identical.
import { readFileSync, writeFileSync } from 'node:fs';
import { POLICY_NAMES, VERSION, loadPolicy, scorePair } from '../web/arabicwer.js';

const args = process.argv.slice(2);
let out = null;
const files = [];
for (let k = 0; k < args.length; k++) {
  if (args[k] === '--out') out = args[++k];
  else files.push(args[k]);
}

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const report = { arabicwer_js_version: VERSION, files: [], cases: 0, identical: 0, mismatches: [] };
for (const file of files) {
  const text = readFileSync(file, 'utf8');
  let cases = 0;
  let identical = 0;
  if (file.endsWith('.jsonl')) {
    for (const line of text.split('\n')) {
      if (!line.trim()) continue;
      const fx = JSON.parse(line);
      for (const name of POLICY_NAMES) {
        cases++;
        const got = scorePair(fx.ref, fx.hyp, name);
        if (same(got, fx.expected[name])) identical++;
        else report.mismatches.push({ file, id: fx.fixture_id, policy: name, got, want: fx.expected[name] });
      }
    }
  } else {
    const data = JSON.parse(text);
    for (const p of data.pairs) {
      for (const [pid, want] of Object.entries(p.scores)) {
        cases++;
        const got = scorePair(p.ref, p.hyp, loadPolicy(pid), { alignment: true });
        if (same(got, want)) identical++;
        else report.mismatches.push({ file, id: p.id, policy: pid, got, want });
      }
    }
  }
  report.files.push({ file: file.split('/').slice(-2).join('/'), cases, identical });
  report.cases += cases;
  report.identical += identical;
}
report.mismatches = report.mismatches.slice(0, 20);
if (out) writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
console.log(`${report.identical} of ${report.cases} cases identical`);
for (const m of report.mismatches) console.log(JSON.stringify(m));
process.exit(report.identical === report.cases ? 0 : 1);

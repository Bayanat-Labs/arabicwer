// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// ArabicWER: the user interface of the static page. All scoring runs in this browser tab (a Web Worker when
// available); nothing is uploaded, stored or logged, and the text is never put in the URL.
import { NAMESPACE, SPEC_ID, VERSION, listPolicies } from './arabicwer.js';
import { WORKED } from './examples.js';
import { MAX_BYTES, MAX_CODE_POINTS, MAX_DIFFS, MAX_PAIRS } from './compute.js';

const LRI = '⁦';
const PDI = '⁩';
const ltr = (s) => `${LRI}${s}${PDI}`;
const fmtInt = (n) => n.toLocaleString('en-US');
const pct = (v) => (v === null || v === undefined ? 'n/a' : `${(100 * v).toFixed(2)}%`);

const STR = {
  en: {
    docTitle: 'ArabicWER – Arabic WER and CER calculator – Bayanat Labs',
    skip: 'Skip to the calculator',
    brand: 'Bayanat Labs',
    title: 'ArabicWER: Arabic WER and CER calculator',
    lede: 'Paste reference and hypothesis transcripts, or upload a TSV file, and see the word and character error rates under six named, versioned normalisation policies side by side, with a word-by-word diff.',
    privacy: 'Scoring runs in your browser. Your text is not uploaded, stored or logged.',
    inputH: 'Transcripts',
    tabPaste: 'Paste',
    tabTsv: 'Upload TSV',
    pasteNote: 'One utterance per line. Line 1 of the reference is scored against line 1 of the hypothesis, and so on.',
    refLabel: 'Reference (what was said)',
    hypLabel: 'Hypothesis (what the system wrote)',
    tsvNote: 'A UTF-8 file with one pair per line: id, reference and hypothesis separated by tabs (or reference and hypothesis only). A first line "id, reference, hypothesis" is treated as a header. Up to 10 MiB and 10,000 pairs. The file is read in this browser tab only.',
    tsvLabel: 'TSV file',
    tsvChosen: (name, n) => `${name}: ${fmtInt(n)} bytes, read in this tab.`,
    score: 'Score',
    worked: 'Worked example',
    clear: 'Clear',
    count: (n) => `${fmtInt(n)} pair${n === 1 ? '' : 's'}`,
    resultsH: 'Scores under every policy',
    summary: (sw, hi, lo, n) => `Across the six policies the corpus WER moves by ${sw} points, from ${hi} to ${lo}, on ${n}.`,
    pairsN: (n) => `${fmtInt(n)} pair${n === 1 ? '' : 's'}`,
    noSwing: 'The WER is the same under every policy.',
    colPolicy: 'Policy', colS: 'S', colD: 'D', colI: 'I', colN: 'N', colHash: 'Policy SHA-256', colWhat: 'What it does',
    scoresNote: 'Corpus rates: all errors divided by all reference words (or characters). S substitutions, D deletions, I insertions, N reference words. A pair with an empty reference has no rate of its own; its insertions still count.',
    citeLabel: 'Cite a score as',
    copy: 'Copy',
    copied: 'Copied',
    dlJson: 'Download results (JSON)',
    dlCsv: 'Download results (CSV)',
    diffH: 'Word alignment',
    diffPolicy: 'Policy',
    legendS: 'substitution: reference word struck through, then what the system wrote',
    legendD: 'deletion: a reference word the system missed',
    legendI: 'insertion: a word the system added',
    pairLabel: 'Pair',
    pairStats: (w, s, d, i, n) => `WER ${w} · S ${s} · D ${d} · I ${i} · N ${n}`,
    emptyRef: 'empty reference',
    diffNote: (n, total) => `The alignment is shown for the first ${fmtInt(n)} of ${fmtInt(total)} pairs; the scores above cover all of them.`,
    polH: 'The six policies',
    polNote: 'Each policy is an immutable JSON file identified by its SHA-256. Any change in behaviour gets a new policy id; arabicwer-1 policies never change.',
    howH: 'How it is computed',
    how1: 'Each policy normalises both texts with arabic-normalize, using Unicode 18.0.0 data bundled with the page, so the result does not depend on your browser.',
    how2: 'Words are the runs of characters between white space. Characters for CER are the code points of the words joined by single spaces.',
    how3: 'Words (or characters) are aligned with the Levenshtein distance. When several alignments cost the same, the one that keeps more matches is used, and the rule is written in the specification so that every implementation agrees.',
    how4: 'WER = (S + D + I) / N, summed over all pairs before dividing. Under the raw policy, for space-separated text with a non-empty reference, the WER and CER equal those of jiwer 4.0.0.',
    how5: 'The page gives the same numbers as the Python package arabicwer on every conformance fixture.',
    ctaH: 'Need production-grade, rights-cleared Arabic speech data?',
    ctaText: 'Bayanat Labs builds licensed Arabic speech datasets and evaluation sets.',
    ctaLink: 'See Bayanat Voice',
    ctaHref: 'https://www.bayanatlabs.com/products/voice',
    fixturesLink: 'Fixtures and case study',
    licence: 'Code: Apache-2.0. Policy files and examples: CC BY 4.0. Unicode tables: Unicode License V3. Font: IBM Plex Sans Arabic, SIL OFL 1.1.',
    version: `arabicwer ${VERSION} · ${SPEC_ID}`,
    langToggle: 'العربية', langToggleLang: 'ar', langToggleDir: 'rtl',
    working: 'Scoring…',
    err: {
      line_count: (e) => `The reference has ${fmtInt(e.ref)} lines and the hypothesis has ${fmtInt(e.hyp)}. Give one utterance per line on both sides.`,
      bad_tsv_line: (e) => `Line ${fmtInt(e.line)} of the file has ${fmtInt(e.columns)} tab-separated columns; 2 or 3 are expected.`,
      too_large: () => `The input is larger than ${fmtInt(MAX_BYTES / 1048576)} MiB.`,
      too_many: (e) => `The input has ${fmtInt(e.pairs)} pairs; the limit is ${fmtInt(MAX_PAIRS)}.`,
      too_long: (e) => `Pair ${e.id} is longer than ${fmtInt(MAX_CODE_POINTS)} characters on one side. Split long recordings into utterances.`,
      empty: () => 'Nothing to score yet. Paste a reference and a hypothesis, or choose a file.',
      not_utf8: () => 'The file is not valid UTF-8 text.',
      error: (e) => `Something went wrong: ${e.message || ''}`,
    },
  },
  ar: {
    docTitle: 'ArabicWER – حاسبة معدل خطأ الكلمات والحروف للعربية – بيانات لابز',
    skip: 'انتقل إلى الحاسبة',
    brand: 'بيانات لابز',
    title: 'ArabicWER: حاسبة معدل خطأ الكلمات والحروف للعربية',
    lede: 'الصق النص المرجعي ومخرَج نظام التعرّف على الكلام، أو ارفع ملف TSV، لترى معدل خطأ الكلمات (WER) ومعدل خطأ الحروف (CER) وفق ست سياسات توحيد مسمّاة ومرقّمة الإصدار جنبًا إلى جنب، مع مقارنة كلمة بكلمة.',
    privacy: 'يجري التقييم في متصفحك. لا يُرفع نصك ولا يُخزَّن ولا يُسجَّل.',
    inputH: 'النصوص',
    tabPaste: 'لصق',
    tabTsv: 'رفع ملف TSV',
    pasteNote: 'جملة واحدة في كل سطر. يُقارن السطر الأول من المرجع بالسطر الأول من المخرَج، وهكذا.',
    refLabel: 'المرجع (ما قيل)',
    hypLabel: 'المخرَج (ما كتبه النظام)',
    tsvNote: 'ملف UTF-8 فيه زوج واحد في كل سطر: المعرّف والمرجع والمخرَج مفصولة بعلامات جدولة (أو المرجع والمخرَج فقط). يُعدّ السطر الأول "id, reference, hypothesis" ترويسة. الحد 10 MiB و10,000 زوج. يُقرأ الملف في هذا التبويب فقط.',
    tsvLabel: 'ملف TSV',
    tsvChosen: (name, n) => `${ltr(name)}: ${ltr(fmtInt(n))} بايت، يُقرأ في هذا التبويب.`,
    score: 'احسب',
    worked: 'مثال محلول',
    clear: 'مسح',
    count: (n) => `عدد الأزواج: ${ltr(fmtInt(n))}`,
    resultsH: 'النتائج وفق كل سياسة',
    summary: (sw, hi, lo, n) => `يتغيّر معدل خطأ الكلمات بين السياسات الست بمقدار ${ltr(sw)} نقطة، من ${ltr(hi)} إلى ${ltr(lo)}، على ${n}.`,
    pairsN: (n) => `${ltr(fmtInt(n))} زوج`,
    noSwing: 'معدل خطأ الكلمات واحد في كل السياسات.',
    colPolicy: 'السياسة', colS: 'S', colD: 'D', colI: 'I', colN: 'N', colHash: 'بصمة SHA-256 للسياسة', colWhat: 'ماذا تفعل',
    scoresNote: 'معدلات على مستوى المجموعة: مجموع الأخطاء مقسومًا على مجموع كلمات المرجع (أو حروفه). S استبدال، D حذف، I إدراج، N عدد كلمات المرجع. الزوج الذي مرجعه فارغ ليس له معدل خاص به، لكن إدراجاته تُحسب.',
    citeLabel: 'اذكر النتيجة هكذا',
    copy: 'نسخ',
    copied: 'نُسخ',
    dlJson: 'تنزيل النتائج (JSON)',
    dlCsv: 'تنزيل النتائج (CSV)',
    diffH: 'محاذاة الكلمات',
    diffPolicy: 'السياسة',
    legendS: 'استبدال: كلمة المرجع مشطوبة، ثم ما كتبه النظام',
    legendD: 'حذف: كلمة في المرجع أغفلها النظام',
    legendI: 'إدراج: كلمة أضافها النظام',
    pairLabel: 'الزوج',
    pairStats: (w, s, d, i, n) => ltr(`WER ${w} · S ${s} · D ${d} · I ${i} · N ${n}`),
    emptyRef: 'مرجع فارغ',
    diffNote: (n, total) => `تظهر المحاذاة لأول ${ltr(fmtInt(n))} من ${ltr(fmtInt(total))} زوج؛ والنتائج أعلاه تشملها كلها.`,
    polH: 'السياسات الست',
    polNote: 'كل سياسة ملف JSON ثابت تعرّفه بصمة SHA-256. أي تغيير في السلوك يأخذ معرّف سياسة جديدًا؛ سياسات arabicwer-1 لا تتغير.',
    howH: 'كيف يُحسب',
    how1: 'توحّد كل سياسة النصين بمكتبة arabic-normalize وبيانات يونيكود 18.0.0 المضمّنة في الصفحة، فلا تتأثر النتيجة بالمتصفح.',
    how2: 'الكلمات هي سلاسل المحارف بين المسافات. وحروف CER هي نقاط الترميز للكلمات موصولة بمسافة واحدة.',
    how3: 'تُحاذى الكلمات (أو الحروف) بمسافة ليفنشتاين. وإذا تساوت كلفة أكثر من محاذاة اختيرت التي تُبقي تطابقات أكثر، والقاعدة مكتوبة في المواصفة لتتفق كل التطبيقات.',
    how4: 'WER = (S + D + I) / N، بجمع كل الأزواج قبل القسمة. وفي سياسة raw، للنصوص المفصولة بمسافات ذات المرجع غير الفارغ، يساوي WER وCER ما تعطيه مكتبة jiwer 4.0.0.',
    how5: 'تعطي الصفحة الأرقام نفسها التي تعطيها حزمة Python المسماة arabicwer على كل حالات الاختبار.',
    ctaH: 'تحتاج بيانات كلام عربية جاهزة للإنتاج وواضحة الحقوق؟',
    ctaText: 'تبني بيانات لابز مجموعات بيانات كلام عربية مرخّصة ومجموعات تقييم.',
    ctaLink: 'تعرّف على Bayanat Voice',
    ctaHref: 'https://www.bayanatlabs.com/ar/products/voice',
    fixturesLink: 'حالات الاختبار ودراسة الحالة',
    licence: 'الشيفرة: Apache-2.0. ملفات السياسات والأمثلة: CC BY 4.0. جداول يونيكود: Unicode License V3. الخط: IBM Plex Sans Arabic، SIL OFL 1.1.',
    version: ltr(`arabicwer ${VERSION} · ${SPEC_ID}`),
    langToggle: 'English', langToggleLang: 'en', langToggleDir: 'ltr',
    working: 'جارٍ الحساب…',
    err: {
      line_count: (e) => `في المرجع ${ltr(fmtInt(e.ref))} سطر وفي المخرَج ${ltr(fmtInt(e.hyp))}. ضع جملة واحدة في كل سطر في الجانبين.`,
      bad_tsv_line: (e) => `في السطر ${ltr(fmtInt(e.line))} من الملف ${ltr(fmtInt(e.columns))} أعمدة؛ المتوقع عمودان أو ثلاثة.`,
      too_large: () => `حجم المدخلات أكبر من ${ltr(fmtInt(MAX_BYTES / 1048576))} MiB.`,
      too_many: (e) => `في المدخلات ${ltr(fmtInt(e.pairs))} زوج، والحد ${ltr(fmtInt(MAX_PAIRS))}.`,
      too_long: (e) => `الزوج ${ltr(e.id)} أطول من ${ltr(fmtInt(MAX_CODE_POINTS))} حرف في أحد جانبيه. قسّم التسجيلات الطويلة إلى جمل.`,
      empty: () => 'لا شيء للحساب بعد. الصق مرجعًا ومخرَجًا، أو اختر ملفًا.',
      not_utf8: () => 'الملف ليس نصًا صالحًا بترميز UTF-8.',
      error: (e) => `حدث خطأ: ${e.message || ''}`,
    },
  },
};

let lang = 'en';
const $ = (id) => document.getElementById(id);
const t = (key, ...args) => {
  const v = STR[lang][key];
  return typeof v === 'function' ? v(...args) : v;
};
function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'text') n.textContent = v;
    else if (k === 'class') n.className = v;
    else n.setAttribute(k, v);
  }
  for (const k of kids) if (k !== null && k !== undefined) n.append(k);
  return n;
}

// --- Worker (falls back to the main thread) ---------------------------------------------------------------
// The worker is started from a blob: URL whose only line imports worker.js, so it inherits this page's
// Content-Security-Policy (connect-src 'none').
let worker = null;
let seq = 0;
const pending = new Map();
try {
  const workerModule = new URL('./worker.js', import.meta.url).href;
  const blobUrl = URL.createObjectURL(new Blob([`import ${JSON.stringify(workerModule)};`], { type: 'text/javascript' }));
  worker = new Worker(blobUrl, { type: 'module' });
  worker.onmessage = (ev) => {
    const cb = pending.get(ev.data.id);
    pending.delete(ev.data.id);
    if (cb) cb(ev.data);
  };
  worker.onerror = () => {
    worker = null;
    for (const [id, cb] of pending) { pending.delete(id); localCompute(cb.req).then(cb); }
  };
} catch (e) {
  worker = null;
}
let computeModule = null;
async function localCompute(req) {
  if (!computeModule) computeModule = await import('./compute.js');
  return computeModule.compute(req);
}
function request(req) {
  if (!worker) return localCompute(req);
  const id = ++seq;
  return new Promise((resolve) => {
    resolve.req = req;
    pending.set(id, resolve);
    worker.postMessage({ id, ...req });
  });
}

// --- State ------------------------------------------------------------------------------------------------
const POLICIES = listPolicies();
const byId = new Map(POLICIES.map((p) => [p.policy_id, p]));
let mode = 'paste';
let tsvText = null;
let last = null; // {report, diffs, diffPolicy}

function policyTitle(p) {
  const m = p.data.meta || {};
  return (lang === 'ar' ? m.title_ar : m.title_en) || p.policy_id;
}
function policyDesc(p) {
  const m = p.data.meta || {};
  return (lang === 'ar' ? m.description_ar : m.description_en) || '';
}

// --- Rendering --------------------------------------------------------------------------------------------
function applyLang() {
  const root = document.documentElement;
  root.lang = lang;
  root.dir = lang === 'ar' ? 'rtl' : 'ltr';
  document.title = t('docTitle');
  for (const node of document.querySelectorAll('[data-i18n]')) {
    const v = STR[lang][node.dataset.i18n];
    if (typeof v === 'string') node.textContent = v;
  }
  const toggle = $('lang-toggle');
  toggle.textContent = t('langToggle');
  toggle.lang = t('langToggleLang');
  toggle.dir = t('langToggleDir');
  $('ar-note').hidden = lang !== 'ar';
  $('cta-link').href = t('ctaHref');
  $('version').textContent = t('version');
  renderPolicies();
  renderSelect();
  updateCount();
  if (last) render(last);
}

// Policy id as `arabicwer-1/name`; the namespace part is hidden on narrow screens.
function pcode(name) {
  return el('code', { dir: 'ltr', title: `${NAMESPACE}/${name}` }, el('span', { class: 'ns', text: `${NAMESPACE}/` }), name);
}

function renderPolicies() {
  const tb = $('policies').querySelector('tbody');
  tb.replaceChildren();
  for (const p of POLICIES) {
    tb.append(el('tr', {},
      el('td', { class: 'pname' }, pcode(p.name), el('span', { class: 't', text: policyTitle(p) })),
      el('td', {}, policyDesc(p))));
  }
}

function renderSelect() {
  const sel = $('diff-policy');
  const cur = sel.value || `${NAMESPACE}/lenient`;
  sel.replaceChildren(...POLICIES.map((p) => el('option', { value: p.policy_id, text: `${p.name} – ${policyTitle(p)}` })));
  sel.value = cur;
}

function updateCount() {
  let n = 0;
  if (mode === 'paste') {
    const r = $('ref').value.split('\n').filter((x, k, a) => !(k === a.length - 1 && x === '')).length;
    n = $('ref').value ? r : 0;
  }
  $('count').textContent = n ? t('count', n) : '';
}

function showError(e) {
  const box = $('error');
  if (!e) { box.hidden = true; box.textContent = ''; return; }
  const f = STR[lang].err[e.reason] || STR[lang].err.error;
  box.textContent = f(e);
  box.hidden = false;
}

function render(res) {
  const { report } = res;
  $('results').hidden = false;
  const tb = $('scores').querySelector('tbody');
  tb.replaceChildren();
  const maxW = Math.max(...report.policies.map((e) => e.words.wer || 0), 1e-9);
  for (const e of report.policies) {
    const p = byId.get(e.policy_id);
    const w = e.words;
    const bar = el('span', { class: 'bar' });
    bar.style.width = `${Math.round(100 * (w.wer || 0) / maxW)}%`;
    const tr = el('tr', e.name === 'lenient' ? { class: 'default' } : {},
      el('td', { class: 'pname' }, pcode(e.name), el('span', { class: 't', text: policyTitle(p) })),
      el('td', { class: 'num barcell' }, pct(w.wer), bar),
      el('td', { class: 'num' }, pct(e.characters.cer)),
      el('td', { class: 'num', text: fmtInt(w.substitutions) }),
      el('td', { class: 'num', text: fmtInt(w.deletions) }),
      el('td', { class: 'num', text: fmtInt(w.insertions) }),
      el('td', { class: 'num', text: fmtInt(w.reference_units) }),
      el('td', { class: 'hash' }, el('code', { text: e.policy_sha256.slice(0, 16) + '…', title: e.policy_sha256, dir: 'ltr' })));
    tb.append(tr);
  }
  const sw = report.swing.wer;
  $('summary-line').textContent = sw && sw.swing > 0
    ? t('summary', (100 * sw.swing).toFixed(2), `${pct(sw.max)} (${byId.get(sw.max_policy).name})`,
      `${pct(sw.min)} (${byId.get(sw.min_policy).name})`, t('pairsN', report.pairs_total))
    : t('noSwing');
  const len = report.policies.find((e) => e.name === 'lenient');
  $('cite').textContent = `WER ${pct(len.words.wer)} (${NAMESPACE}/lenient, sha256 ${len.policy_sha256.slice(0, 12)})`;
  renderDiffs(res);
}

function tok(op, ref, hyp) {
  const lab = (s) => el('span', { class: 'lab', text: s, 'aria-hidden': 'true' });
  if (op === 'equal') return el('span', { class: 'tok ok' }, el('bdi', { text: ref }));
  if (op === 'substitute') {
    return el('span', { class: 'tok sub', title: `S: ${ref} → ${hyp}` }, el('del', {}, el('bdi', { text: ref })), lab('S'),
      el('ins', {}, el('bdi', { text: hyp })));
  }
  if (op === 'delete') return el('span', { class: 'tok del', title: `D: ${ref}` }, el('del', {}, el('bdi', { text: ref })), lab('D'));
  return el('span', { class: 'tok ins', title: `I: ${hyp}` }, lab('I'), el('ins', {}, el('bdi', { text: hyp })));
}

function renderDiffs(res) {
  $('diff-card').hidden = false;
  const box = $('diffs');
  box.replaceChildren();
  const dp = res.diffPolicy.startsWith(NAMESPACE + '/') ? res.diffPolicy : `${NAMESPACE}/${res.diffPolicy}`;
  res.diffs.forEach((d, k) => {
    const rec = res.report.pairs[k].scores[dp];
    const head = el('div', { class: 'pair-head' },
      el('span', { class: 'id' }, `${t('pairLabel')} `, el('bdi', { text: d.id })),
      el('span', {}, rec.N === 0 ? t('emptyRef') : t('pairStats', pct(rec.wer), rec.S, rec.D, rec.I, rec.N)));
    const line = el('div', { class: 'align', dir: 'rtl', lang: 'ar' });
    for (const x of d.tokens) line.append(tok(x.op, x.ref, x.hyp), ' ');
    box.append(el('div', { class: 'pair' }, head, line));
  });
  const note = $('diff-note');
  const total = res.report.pairs_total;
  note.hidden = total <= MAX_DIFFS;
  note.textContent = total > MAX_DIFFS ? t('diffNote', MAX_DIFFS, total) : '';
}

// --- Actions ----------------------------------------------------------------------------------------------
async function run() {
  showError(null);
  const req = mode === 'tsv' ? { mode, text: tsvText || '' } : { mode, ref: $('ref').value, hyp: $('hyp').value };
  req.diffPolicy = $('diff-policy').value || `${NAMESPACE}/lenient`;
  $('score').textContent = t('working');
  const res = await request(req);
  $('score').textContent = t('score');
  if (res.error) { showError(res.error); return; }
  last = res;
  render(res);
}

function download(name, type, text) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = el('a', { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const CSV_FIELDS = ['ref_norm', 'hyp_norm', 'S', 'D', 'I', 'N', 'wer', 'cS', 'cD', 'cI', 'cN', 'cer'];
function csvCell(v) {
  if (v === null || v === undefined) return '';
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
function toCsv(report) {
  const sha = new Map(report.policies.map((e) => [e.policy_id, e.policy_sha256]));
  const rows = [['pair_id', 'policy_id', 'policy_sha256', 'arabicwer_version', ...CSV_FIELDS]];
  for (const row of report.pairs) {
    for (const [pid, rec] of Object.entries(row.scores)) {
      rows.push([row.pair_id, pid, sha.get(pid), report.arabicwer_version, ...CSV_FIELDS.map((f) => rec[f])]);
    }
  }
  for (const e of report.policies) {
    const w = e.words; const c = e.characters;
    rows.push(['*corpus*', e.policy_id, e.policy_sha256, report.arabicwer_version, '', '', w.substitutions, w.deletions,
      w.insertions, w.reference_units, w.wer, c.substitutions, c.deletions, c.insertions, c.reference_units, c.cer]);
  }
  return rows.map((r) => r.map(csvCell).join(',')).join('\n') + '\n';
}

function setMode(m) {
  mode = m;
  $('tab-paste').setAttribute('aria-selected', String(m === 'paste'));
  $('tab-tsv').setAttribute('aria-selected', String(m === 'tsv'));
  $('panel-paste').hidden = m !== 'paste';
  $('panel-tsv').hidden = m !== 'tsv';
  updateCount();
}

function clearAll() {
  $('ref').value = '';
  $('hyp').value = '';
  $('tsv').value = '';
  $('tsv-name').textContent = '';
  tsvText = null;
  last = null;
  $('results').hidden = true;
  $('diff-card').hidden = true;
  $('diffs').replaceChildren();
  $('scores').querySelector('tbody').replaceChildren();
  showError(null);
  updateCount();
}

function init() {
  const q = new URLSearchParams(location.search).get('lang');
  lang = q === 'ar' ? 'ar' : 'en';
  applyLang();
  $('lang-toggle').addEventListener('click', () => { lang = lang === 'ar' ? 'en' : 'ar'; applyLang(); });
  $('tab-paste').addEventListener('click', () => setMode('paste'));
  $('tab-tsv').addEventListener('click', () => setMode('tsv'));
  $('ref').addEventListener('input', updateCount);
  $('score').addEventListener('click', run);
  $('clear').addEventListener('click', clearAll);
  $('worked').addEventListener('click', () => {
    setMode('paste');
    $('ref').value = WORKED.map((x) => x[0]).join('\n');
    $('hyp').value = WORKED.map((x) => x[1]).join('\n');
    updateCount();
    run();
  });
  $('tsv').addEventListener('change', async () => {
    const f = $('tsv').files[0];
    tsvText = null;
    showError(null);
    if (!f) return;
    if (f.size > MAX_BYTES) { showError({ reason: 'too_large', bytes: f.size }); $('tsv').value = ''; return; }
    try {
      tsvText = new TextDecoder('utf-8', { fatal: true }).decode(await f.arrayBuffer());
      $('tsv-name').textContent = t('tsvChosen', f.name, f.size);
    } catch (e) {
      showError({ reason: 'not_utf8' });
      $('tsv').value = '';
    }
  });
  $('diff-policy').addEventListener('change', () => { if (last) run(); });
  $('copy-cite').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('cite').textContent); $('copy-cite').textContent = t('copied'); } catch (e) { /* clipboard blocked */ }
    setTimeout(() => { $('copy-cite').textContent = t('copy'); }, 1200);
  });
  $('dl-json').addEventListener('click', () => {
    if (last) download('arabicwer-results.json', 'application/json', JSON.stringify(last.report, null, 2) + '\n');
  });
  $('dl-csv').addEventListener('click', () => { if (last) download('arabicwer-results.csv', 'text/csv', toCsv(last.report)); });
}

init();

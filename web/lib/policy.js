// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// Named, immutable normalisation policies and their SHA-256 identity (docs/SPEC.md section 2).
// A port of src/arabic_normalize/policy.py. Built-in policies are the same JSON files, embedded by
// scripts/build.mjs; nothing is ever fetched from the network.
import { PolicyError } from './errors.js';
import { BUILTIN_POLICIES } from './generated/policies.js';
import { sha256Hex } from './sha256.js';
import { UNICODE_VERSION, toCodePoints } from './ucd.js';
import { encodeCodePoints } from './utf8.js';

export const SPEC_ID = 'arabic-normalize-spec-1';

export const STAGE_ORDER = Object.freeze([
  'reject_invalid', 'strip_controls', 'presentation_forms', 'ligatures_honorific', 'bidi_zw',
  'tatweel', 'diacritics', 'quranic_marks', 'superscript_alef', 'alef_variants', 'alef_maqsura',
  'taa_marbuta', 'hamza_carriers', 'persian_urdu_letters', 'digits', 'punctuation', 'whitespace', 'latin_case',
]);

export const STAGE_MODES = Object.freeze({
  reject_invalid: ['drop', 'error'],
  strip_controls: ['strip', 'keep'],
  presentation_forms: ['map', 'keep', 'flag'],
  ligatures_honorific: ['keep', 'flag', 'expand'],
  bidi_zw: ['keep', 'strip', 'strip-except-zwnj', 'strip-except-emoji-zwj', 'strip-except-meaningful'],
  tatweel: ['strip', 'keep'],
  diacritics: ['keep', 'strip', 'strip-except-shadda'],
  quranic_marks: ['strip', 'keep'],
  superscript_alef: ['keep', 'strip', 'to-alef'],
  alef_variants: ['map', 'keep'],
  alef_maqsura: ['to-yeh', 'keep', 'flag'],
  taa_marbuta: ['keep', 'flag', 'to-heh'],
  hamza_carriers: ['keep', 'fold'],
  persian_urdu_letters: ['map', 'keep'],
  digits: ['keep', 'ascii', 'arabic-indic'],
  punctuation: ['keep', 'ascii', 'strip'],
  whitespace: ['collapse', 'keep'],
  latin_case: ['keep', 'lower'],
});

const TOP_MEMBERS = ['policy_id', 'version', 'spec', 'unicode_version', 'unicode_form', 'idempotent', 'stages', 'meta'];
const META_MEMBERS = ['title_en', 'title_ar', 'description_en', 'license', 'attribution', 'created', 'status'];
const ID_RE = /^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$/;

const isObject = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const repr = (x) => (typeof x === 'string' ? `'${x}'` : JSON.stringify(x));

function cmpCodePoints(a, b) {
  // Python sorts str keys by code point; JavaScript's default sort compares UTF-16 code units.
  const x = toCodePoints(a);
  const y = toCodePoints(b);
  for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] - y[i];
  return x.length - y.length;
}

function canonicalValue(v) {
  if (v === null || typeof v === 'boolean' || typeof v === 'string') return JSON.stringify(v);
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) throw new PolicyError('invalid_policy', 'non-finite numbers are not allowed');
    if (Number.isInteger(v)) return String(v);
    throw new PolicyError('invalid_policy', 'only integers are allowed as numbers in a policy');
  }
  if (Array.isArray(v)) return `[${v.map(canonicalValue).join(',')}]`;
  if (isObject(v)) {
    const keys = Object.keys(v).sort(cmpCodePoints);
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalValue(v[k])}`).join(',')}}`;
  }
  throw new PolicyError('invalid_policy', `unsupported value of type ${typeof v}`);
}

/** Canonical JSON: keys sorted at every level, separators ',' and ':', no whitespace, no ASCII escaping. */
export function canonicalJson(obj) {
  return canonicalValue(obj);
}

function bodyOf(obj) {
  const body = {};
  for (const k of Object.keys(obj)) if (k !== 'meta') body[k] = obj[k];
  return body;
}

/** SHA-256 of the canonical JSON of the policy without its top-level `meta` member. */
export function policyHash(obj) {
  if (obj instanceof Policy) return obj.policy_hash;
  return sha256Hex(encodeCodePoints(toCodePoints(canonicalJson(bodyOf(obj)))));
}

function checkNoDollar(obj, path = 'policy') {
  if (isObject(obj)) {
    for (const [k, v] of Object.entries(obj)) {
      if (k.startsWith('$')) {
        throw new PolicyError('remote_ref_not_allowed',
          `${path}.${k}: members starting with '$' are not allowed; nothing is fetched`);
      }
      checkNoDollar(v, `${path}.${k}`);
    }
  } else if (Array.isArray(obj)) {
    obj.forEach((v, i) => checkNoDollar(v, `${path}[${i}]`));
  }
}

/** Throw PolicyError with a reason if `obj` is not a valid policy (no network access, ever). */
export function validatePolicy(obj) {
  if (!isObject(obj)) throw new PolicyError('invalid_policy', 'a policy must be a JSON object');
  checkNoDollar(obj);
  for (const k of Object.keys(obj)) {
    if (!TOP_MEMBERS.includes(k)) throw new PolicyError('unknown_member', `unknown policy member ${repr(k)}`);
  }
  for (const k of TOP_MEMBERS.slice(0, -1)) {
    if (!has(obj, k)) throw new PolicyError('missing_member', `policy member ${repr(k)} is required`);
  }
  const pid = obj.policy_id;
  if (typeof pid !== 'string' || !ID_RE.test(pid)) {
    throw new PolicyError('invalid_policy_id', `policy_id must match ${ID_RE.source}`);
  }
  if (typeof obj.version !== 'number' || !Number.isInteger(obj.version) || obj.version < 1) {
    throw new PolicyError('invalid_member', 'version must be a positive integer');
  }
  if (obj.spec !== SPEC_ID) throw new PolicyError('unsupported_spec', `spec must be '${SPEC_ID}'`);
  if (obj.unicode_version !== UNICODE_VERSION) {
    throw new PolicyError('unsupported_unicode_version',
      `this release ships UCD ${UNICODE_VERSION} tables only (got ${repr(obj.unicode_version)})`);
  }
  if (!['NFC', 'NFKC', 'none'].includes(obj.unicode_form)) {
    throw new PolicyError('invalid_member', 'unicode_form must be NFC, NFKC or none');
  }
  if (typeof obj.idempotent !== 'boolean') throw new PolicyError('invalid_member', 'idempotent must be true or false');
  const stages = obj.stages;
  if (!isObject(stages)) throw new PolicyError('invalid_member', 'stages must be an object');
  for (const k of Object.keys(stages)) {
    if (!has(STAGE_MODES, k)) throw new PolicyError('unknown_stage', `unknown stage ${repr(k)}`);
  }
  for (const [k, modes] of Object.entries(STAGE_MODES)) {
    if (!has(stages, k)) throw new PolicyError('missing_stage', `stage ${repr(k)} is required`);
    if (!modes.includes(stages[k])) {
      throw new PolicyError('invalid_stage_value',
        `stage ${repr(k)} has no mode ${repr(stages[k])} (allowed: ${modes.join(', ')})`);
    }
  }
  if (obj.unicode_form === 'NFKC' && (stages.presentation_forms !== 'map' || stages.ligatures_honorific !== 'expand')) {
    throw new PolicyError('inconsistent_policy',
      'unicode_form NFKC already maps presentation forms and expands ligatures; '
      + 'set presentation_forms: map and ligatures_honorific: expand');
  }
  if (has(obj, 'meta') && obj.meta !== null) {
    const meta = obj.meta;
    if (!isObject(meta)) throw new PolicyError('invalid_member', 'meta must be an object');
    for (const [k, v] of Object.entries(meta)) {
      if (!META_MEMBERS.includes(k)) throw new PolicyError('unknown_member', `unknown meta member ${repr(k)}`);
      if (typeof v !== 'string') throw new PolicyError('invalid_member', `meta.${k} must be a string`);
    }
  }
}

function deepFreeze(o) {
  if (o && typeof o === 'object') {
    Object.freeze(o);
    for (const v of Object.values(o)) deepFreeze(v);
  }
  return o;
}

/** A validated, immutable policy. `policy_hash` identifies its behaviour. */
export class Policy {
  constructor(data, builtin = false) {
    validatePolicy(data);
    const copy = deepFreeze(JSON.parse(JSON.stringify(data)));
    Object.defineProperty(this, '_data', { value: copy });
    this.policy_id = copy.policy_id;
    this.policy_hash = policyHash(copy);
    this.stages = copy.stages;
    this.unicode_form = copy.unicode_form;
    this.idempotent = copy.idempotent;
    this.builtin = builtin;
    Object.freeze(this);
  }

  /** A deep copy of the full policy object (including meta). */
  get data() {
    return JSON.parse(JSON.stringify(this._data));
  }

  /** Pretty JSON of the full policy (with meta), stages in pipeline order (like Policy.to_json in Python). */
  toJSONString(indent = 2) {
    const d = {};
    for (const k of TOP_MEMBERS) if (has(this._data, k)) d[k] = this._data[k];
    d.stages = Object.fromEntries(STAGE_ORDER.map((k) => [k, this._data.stages[k]]));
    return JSON.stringify(d, null, indent);
  }

  /** The exact string that is hashed. */
  canonical() {
    return canonicalJson(bodyOf(this._data));
  }

  toString() {
    return `Policy('${this.policy_id}', sha256=${this.policy_hash.slice(0, 12)})`;
  }
}

const BUILTIN = new Map();

/** Ids of the built-in policies, sorted. */
export function listPolicies() {
  return Object.keys(BUILTIN_POLICIES).sort();
}

function loadBuiltin(pid) {
  let p = BUILTIN.get(pid);
  if (p === undefined) {
    if (!has(BUILTIN_POLICIES, pid)) {
      throw new PolicyError('unknown_policy', `no built-in policy '${pid}' (available: ${listPolicies().join(', ')})`);
    }
    p = new Policy(BUILTIN_POLICIES[pid], true);
    BUILTIN.set(pid, p);
  }
  return p;
}

/** Return a Policy from a built-in id, a plain policy object or a Policy. */
export function loadPolicy(policy) {
  if (policy instanceof Policy) return policy;
  if (isObject(policy)) return new Policy(policy);
  if (typeof policy === 'string') {
    if (BUILTIN.has(policy) || has(BUILTIN_POLICIES, policy) || (ID_RE.test(policy) && !policy.endsWith('.json'))) {
      return loadBuiltin(policy);
    }
    throw new PolicyError('unknown_policy',
      `no built-in policy named '${policy}' (to load a policy file in Node, use loadPolicyFile from '@bayanat-labs/arabic-normalize/node')`);
  }
  throw new PolicyError('invalid_policy', 'policy must be an id, a policy object or a Policy');
}

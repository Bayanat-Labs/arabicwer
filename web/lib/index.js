// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// @bayanat-labs/arabic-normalize: Arabic text normalisation with named, immutable, hash-identified
// policies. The JavaScript port of the Python package arabic-normalize by Bayanat Labs. No runtime
// dependencies; Unicode data pinned to UCD 18.0.0; works in Node 20+ and in browsers (ES module).
//
//   import { normalize, normalizeDetailed } from '@bayanat-labs/arabic-normalize';
//   normalize('إِلَى المَدْرَسَةِ');   // 'الي المدرسة'
export { LIB_VERSION } from './generated/version.js';
export { UNICODE_VERSION, normalizeForm } from './ucd.js';
export {
  DEFAULT_POLICY, LOSSY_RULES, MAX_RECORDS, MAX_TEXT_BYTES,
  decodeUtf8, diffPolicies, inputStats, normalize, normalizeBytes, normalizeDetailed, normalizeRequest,
  parseRecord, ruleIds, textDiac,
} from './engine.js';
export {
  Policy, SPEC_ID, STAGE_MODES, STAGE_ORDER, canonicalJson, listPolicies, loadPolicy, policyHash, validatePolicy,
} from './policy.js';
export { ArabicNormalizeError, InputRejected, PolicyError } from './errors.js';
export { sha256Hex } from './sha256.js';

// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// Exceptions. Every rejection carries a machine-readable `reason` (docs/SPEC.md section 6), the same
// reasons as the Python package.

export class ArabicNormalizeError extends Error {
  /**
   * @param {string} reason stable identifier
   * @param {string} [detail] human-readable message
   * @param {[number, number] | null} [span]
   */
  constructor(reason, detail = '', span = null) {
    super(detail ? `${reason}: ${detail}` : reason);
    this.name = 'ArabicNormalizeError';
    this.reason = reason;
    this.detail = detail;
    this.span = span;
  }
}

/** The input text, bytes or request does not meet the input contract. */
export class InputRejected extends ArabicNormalizeError {
  constructor(reason, detail = '', span = null) {
    super(reason, detail, span);
    this.name = 'InputRejected';
  }
}

/** The policy id is unknown or the policy object is invalid. */
export class PolicyError extends ArabicNormalizeError {
  constructor(reason, detail = '', span = null) {
    super(reason, detail, span);
    this.name = 'PolicyError';
  }
}

// Copyright 2026 Bayanat Labs
// SPDX-License-Identifier: Apache-2.0
//
// Scores off the main thread. Nothing leaves the browser: app.js starts this worker from a blob: URL, so the
// page's Content-Security-Policy (connect-src 'none') applies here too; this file makes no network request
// and keeps no state between messages.
import { compute } from './compute.js';

self.onmessage = (event) => {
  self.postMessage({ id: event.data.id, ...compute(event.data) });
};

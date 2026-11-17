/*
 * Capture the Domain - shared constants and helpers.
 *
 * Loaded first by the content script, by the background service worker
 * (importScripts) and by popup.html.  Everything here is dependency-free.
 */
(function (global) {
  "use strict";

  var api = global.browser || global.chrome;

  // Requirement 17: the one and only sign-off string.  It is rendered in the
  // popup footer (without scrolling) and written to every snapshot as
  // `captured_by`.
  var CAPTURED_BY =
    "Produced 2026-11-17T01:40Z by DeepSeek V4.1 Flash (opencode-go / deepseek-v4.1-flash)";

  var ARM_WINDOW_MS = 10 * 60 * 1000; // 10 minutes
  var MUTATION_QUIET_MS = 500;
  var CAPTURE_BUDGET_MS = 10000; // extraction + image inlining + hand-off
  var UPLOAD_TIMEOUT_MS = 15000;
  var IMAGE_FETCH_TIMEOUT_MS = 5000;
  var IMAGE_CONCURRENCY = 6;
  var MAX_IMAGE_BYTES = 15 * 1024 * 1024;
  var LOG_LIMIT = 20;

  var KEYS = {
    endpoint: "syncEndpoint",
    token: "syncToken",
    armedUntil: "armedUntil",
    armedHost: "armedHost",
    armedAt: "armedAt",
    log: "captureLog",
    dedupe: "dedupeState"
  };

  function nowIso(value) {
    var d = value === undefined ? new Date() : new Date(value);
    // ISO 8601, UTC, second precision (no milliseconds).
    return d.toISOString().replace(/\.\d{3}Z$/, "Z");
  }

  function byteLength(text) {
    try {
      return new TextEncoder().encode(String(text)).byteLength;
    } catch (e) {
      return unescape(encodeURIComponent(String(text))).length;
    }
  }

  function truncate(text, max) {
    var s = String(text == null ? "" : text);
    return s.length <= max ? s : s.slice(0, Math.max(0, max - 1)) + "\u2026";
  }

  function formatBytes(bytes) {
    var n = Number(bytes) || 0;
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(2) + " MB";
  }

  function isArmedState(armedUntil) {
    return Number(armedUntil) > Date.now();
  }

  function normalizeHost(host) {
    return String(host || "").trim().toLowerCase().replace(/\.$/, "");
  }

  global.SafariCapture = {
    api: api,
    CAPTURED_BY: CAPTURED_BY,
    ARM_WINDOW_MS: ARM_WINDOW_MS,
    MUTATION_QUIET_MS: MUTATION_QUIET_MS,
    CAPTURE_BUDGET_MS: CAPTURE_BUDGET_MS,
    UPLOAD_TIMEOUT_MS: UPLOAD_TIMEOUT_MS,
    IMAGE_FETCH_TIMEOUT_MS: IMAGE_FETCH_TIMEOUT_MS,
    IMAGE_CONCURRENCY: IMAGE_CONCURRENCY,
    MAX_IMAGE_BYTES: MAX_IMAGE_BYTES,
    LOG_LIMIT: LOG_LIMIT,
    KEYS: KEYS,
    nowIso: nowIso,
    byteLength: byteLength,
    truncate: truncate,
    formatBytes: formatBytes,
    isArmedState: isArmedState,
    normalizeHost: normalizeHost
  };
})(globalThis);

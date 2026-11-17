/*
 * Capture the Domain - background service worker.
 *
 * Owns the armed window, the window-scoped duplicate set, image inlining,
 * SHA-256, the multipart uploader, the IndexedDB retry queue and the
 * persistent capture log.  The endpoint and bearer token are read from
 * extension storage at request time; no destination is compiled in.
 */
importScripts("shared.js");

(function () {
  "use strict";

  var S = globalThis.SafariCapture;
  if (!S || !S.api) {
    throw new Error("SafariCapture shared.js failed to load");
  }
  var api = S.api;
  var K = S.KEYS;

  var DB_NAME = "SafariCaptureQueue";
  var DB_VERSION = 1;
  var STORE = "queue";

  var dbPromise = null;
  var logChain = Promise.resolve();
  var memoryDedupe = { windowStart: 0, keys: new Set() };
  var activeControllers = new Set();
  var inFlightKeys = new Set();
  var windowEpoch = 0;

  /* ------------------------------------------------------------------ */
  /* Promise wrappers around the callback-or-promise WebExtension APIs   */
  /* ------------------------------------------------------------------ */

  function callWithCallback(invoke) {
    return new Promise(function (resolve, reject) {
      var settled = false;
      function done(value) {
        if (!settled) {
          settled = true;
          resolve(value);
        }
      }
      function fail(error) {
        if (!settled) {
          settled = true;
          reject(error);
        }
      }
      try {
        var maybe = invoke(function (value) {
          if (api.runtime.lastError) {
            fail(new Error(api.runtime.lastError.message || "extension API error"));
          } else {
            done(value);
          }
        });
        if (maybe && typeof maybe.then === "function") {
          maybe.then(done, fail);
        }
      } catch (error) {
        fail(error);
      }
    });
  }

  function storageGet(keys) {
    return callWithCallback(function (callback) {
      return api.storage.local.get(keys, callback);
    }).then(function (value) {
      return value || {};
    });
  }

  function storageSet(values) {
    return callWithCallback(function (callback) {
      return api.storage.local.set(values, callback);
    });
  }

  function tabsQuery(query) {
    return callWithCallback(function (callback) {
      return api.tabs.query(query, callback);
    });
  }

  /* ------------------------------------------------------------------ */
  /* IndexedDB queue                                                     */
  /* ------------------------------------------------------------------ */

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise(function (resolve, reject) {
      var request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = function () {
        var db = request.result;
        if (!db.objectStoreNames.contains(STORE)) {
          var store = db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
          store.createIndex("key", "key", { unique: false });
        }
      };
      request.onsuccess = function () {
        resolve(request.result);
      };
      request.onerror = function () {
        reject(request.error || new Error("IndexedDB open failed"));
      };
      request.onblocked = function () {
        reject(new Error("IndexedDB open blocked"));
      };
    });
    return dbPromise;
  }

  function queueAll() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readonly");
        var request = tx.objectStore(STORE).getAll();
        request.onsuccess = function () {
          resolve(request.result || []);
        };
        request.onerror = function () {
          reject(request.error || new Error("queue read failed"));
        };
      });
    });
  }

  function queueCount() {
    return openDb()
      .then(function (db) {
        return new Promise(function (resolve, reject) {
          var tx = db.transaction(STORE, "readonly");
          var request = tx.objectStore(STORE).count();
          request.onsuccess = function () {
            resolve(request.result || 0);
          };
          request.onerror = function () {
            reject(request.error || new Error("queue count failed"));
          };
        });
      })
      .catch(function () {
        return 0;
      });
  }

  function queueAdd(item) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        var request = tx.objectStore(STORE).add(item);
        var id = null;
        request.onsuccess = function () {
          id = request.result;
        };
        tx.oncomplete = function () {
          resolve(id);
        };
        tx.onerror = function () {
          reject(tx.error || new Error("queue add failed"));
        };
        tx.onabort = function () {
          reject(tx.error || new Error("queue add aborted"));
        };
      });
    });
  }

  function queuePut(item) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).put(item);
        tx.oncomplete = function () {
          resolve(item.id);
        };
        tx.onerror = function () {
          reject(tx.error || new Error("queue update failed"));
        };
        tx.onabort = function () {
          reject(tx.error || new Error("queue update aborted"));
        };
      });
    });
  }

  function queueDelete(id) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).delete(id);
        tx.oncomplete = function () {
          resolve(true);
        };
        tx.onerror = function () {
          reject(tx.error || new Error("queue delete failed"));
        };
        tx.onabort = function () {
          reject(tx.error || new Error("queue delete aborted"));
        };
      });
    });
  }

  async function enqueue(item) {
    var all = await queueAll();
    var existing = null;
    for (var i = 0; i < all.length; i += 1) {
      if (all[i].key === item.key) {
        existing = all[i];
        break;
      }
    }
    if (existing) {
      var updated = Object.assign({}, existing, item, {
        id: existing.id,
        attempts: (Number(existing.attempts) || 0) + 1,
        queued_at: existing.queued_at || item.queued_at,
        last_attempt_at: S.nowIso()
      });
      await queuePut(updated);
      return updated.id;
    }
    return queueAdd(item);
  }

  async function bumpQueue(id, reason) {
    var all = await queueAll();
    for (var i = 0; i < all.length; i += 1) {
      if (all[i].id === id) {
        var item = all[i];
        item.attempts = (Number(item.attempts) || 0) + 1;
        item.last_attempt_at = S.nowIso();
        item.last_error = String(reason || "");
        await queuePut(item);
        return;
      }
    }
  }

  /* ------------------------------------------------------------------ */
  /* Settings, armed window and dedupe                                   */
  /* ------------------------------------------------------------------ */

  async function getSettings() {
    var stored = await storageGet([K.endpoint, K.token]);
    return {
      endpoint: String(stored[K.endpoint] || "").trim(),
      token: String(stored[K.token] || "").replace(/[\r\n]/g, "").trim()
    };
  }

  async function getArmed() {
    var stored = await storageGet([K.armedUntil, K.armedHost, K.armedAt]);
    return {
      armedUntil: Number(stored[K.armedUntil]) || 0,
      armedHost: S.normalizeHost(stored[K.armedHost] || ""),
      armedAt: Number(stored[K.armedAt]) || 0
    };
  }

  function isArmed(state) {
    return !!(state && state.armedHost && Number(state.armedUntil) > Date.now());
  }

  function dedupeKey(url, hash) {
    return String(url) + "\n" + String(hash);
  }

  async function isDuplicate(key, windowStart) {
    if (!windowStart) return false;
    if (memoryDedupe.windowStart === windowStart && memoryDedupe.keys.has(key)) {
      return true;
    }
    var stored = await storageGet([K.dedupe]);
    var state = stored[K.dedupe];
    if (
      state &&
      Number(state.windowStart) === Number(windowStart) &&
      Array.isArray(state.keys) &&
      state.keys.indexOf(key) !== -1
    ) {
      memoryDedupe = { windowStart: Number(windowStart), keys: new Set(state.keys) };
      return true;
    }
    return false;
  }

  async function rememberDedupe(key, windowStart) {
    if (!key || !windowStart) return;
    windowStart = Number(windowStart);
    if (memoryDedupe.windowStart > windowStart) return; // a newer arm won
    if (memoryDedupe.windowStart !== windowStart) {
      memoryDedupe = { windowStart: windowStart, keys: new Set() };
    }
    memoryDedupe.keys.add(key);

    // The in-memory set is authoritative for this worker lifetime; the
    // storage mirror only survives a worker restart.  A storage failure must
    // never turn a successful upload into a queued retry.
    try {
      var stored = await storageGet([K.dedupe]);
      var state = stored[K.dedupe];
      if (state && Number(state.windowStart) > windowStart) return;
      if (!state || Number(state.windowStart) !== windowStart) {
        state = { windowStart: windowStart, keys: [] };
      }
      if (state.keys.indexOf(key) === -1) {
        state.keys.push(key);
      }
      if (state.keys.length > 1000) {
        state.keys = state.keys.slice(state.keys.length - 1000);
      }
      var values = {};
      values[K.dedupe] = state;
      await storageSet(values);
    } catch (error) {
      // Keep the memory copy.
    }
  }

  async function resetDedupe(windowStart) {
    memoryDedupe = {
      windowStart: Number(windowStart) || 0,
      keys: new Set()
    };
    var values = {};
    values[K.dedupe] = {
      windowStart: Number(windowStart) || 0,
      keys: []
    };
    await storageSet(values);
  }

  /* ------------------------------------------------------------------ */
  /* Persistent capture log                                              */
  /* ------------------------------------------------------------------ */

  function appendLog(entry) {
    var record = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 8),
      time: S.nowIso(),
      url: String(entry.url || ""),
      status: String(entry.status || "failed"),
      bytes: Math.max(0, Number(entry.bytes) || 0),
      reason: String(entry.reason || ""),
      images_failed: Math.max(0, Number(entry.images_failed) || 0)
    };

    logChain = logChain
      .then(async function () {
        var stored = await storageGet([K.log]);
        var log = Array.isArray(stored[K.log]) ? stored[K.log] : [];
        log.unshift(record);
        var values = {};
        values[K.log] = log.slice(0, S.LOG_LIMIT);
        await storageSet(values);
      })
      .catch(function () {
        // Logging must never break a capture.
      });

    return logChain;
  }

  /* ------------------------------------------------------------------ */
  /* Hashing, frontmatter and multipart payload                          */
  /* ------------------------------------------------------------------ */

  async function sha256Hex(text) {
    var bytes = new TextEncoder().encode(text);
    var digest = await crypto.subtle.digest("SHA-256", bytes);
    var view = new Uint8Array(digest);
    var hex = "";
    for (var i = 0; i < view.length; i += 1) {
      hex += view[i].toString(16).padStart(2, "0");
    }
    return hex;
  }

  function normalizeMarkdown(markdown) {
    var text = String(markdown == null ? "" : markdown);
    text = text.replace(/\r\n?/g, "\n");
    text = text.replace(/[ \t]+$/gm, "");
    text = text.replace(/\n{3,}/g, "\n\n");
    text = text.replace(/^\n+/, "").replace(/\n+$/, "");
    return text + "\n";
  }

  function yamlScalar(value) {
    // JSON double-quoted strings are valid YAML double-quoted scalars and
    // safely carry newlines, quotes and non-ASCII text.
    return JSON.stringify(String(value == null ? "" : value));
  }

  function buildDocument(meta, body) {
    var frontmatter = [
      "---",
      "url: " + yamlScalar(meta.url),
      "title: " + yamlScalar(meta.title),
      "host: " + yamlScalar(meta.host),
      "captured_at: " + yamlScalar(meta.captured_at),
      "content_hash: " + yamlScalar(meta.content_hash),
      "captured_by: " + yamlScalar(S.CAPTURED_BY),
      "---",
      ""
    ].join("\n");
    return frontmatter + "\n" + body;
  }

  function randomHex(bytes) {
    var data = new Uint8Array(bytes);
    if (globalThis.crypto && crypto.getRandomValues) {
      crypto.getRandomValues(data);
    } else {
      for (var i = 0; i < data.length; i += 1) data[i] = Math.floor(Math.random() * 256);
    }
    var hex = "";
    for (var j = 0; j < data.length; j += 1) hex += data[j].toString(16).padStart(2, "0");
    return hex;
  }

  function buildMultipart(item) {
    var boundary = "----SafariCaptureBoundary" + randomHex(16);
    var sections = [];

    function textPart(name, value) {
      sections.push(
        "--" +
          boundary +
          "\r\n" +
          'Content-Disposition: form-data; name="' +
          name +
          '"\r\n\r\n' +
          String(value == null ? "" : value) +
          "\r\n"
      );
    }

    textPart("url", item.url);
    textPart("captured_at", item.captured_at);
    textPart("content_hash", item.content_hash);
    textPart("links", JSON.stringify(item.links || []));
    sections.push(
      "--" +
        boundary +
        "\r\n" +
        'Content-Disposition: form-data; name="markdown"; filename="page-' +
        item.content_hash +
        '.md"\r\n' +
        "Content-Type: text/markdown; charset=utf-8\r\n\r\n" +
        item.doc +
        "\r\n"
    );
    sections.push("--" + boundary + "--\r\n");

    var blob = new Blob(sections, {
      type: "multipart/form-data; boundary=" + boundary
    });
    return { blob: blob, boundary: boundary, bytes: blob.size };
  }

  function codedError(message, code) {
    var error = new Error(message);
    error.code = code || "error";
    return error;
  }

  /* ------------------------------------------------------------------ */
  /* Images                                                              */
  /* ------------------------------------------------------------------ */

  function imageToken(index) {
    return "@@SC_IMG_" + index + "@@";
  }

  function toBase64(buffer) {
    var bytes = new Uint8Array(buffer);
    var binary = "";
    var chunk = 0x8000;
    for (var i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, Math.min(i + chunk, bytes.length)));
    }
    return btoa(binary);
  }

  async function fetchImage(url, deadline) {
    if (/^data:image\//i.test(url)) return url;
    if (!/^https?:/i.test(url)) throw new Error("unsupported image URL");

    var remaining = deadline - Date.now();
    if (remaining <= 0) throw new Error("image deadline reached");

    var controller = new AbortController();
    activeControllers.add(controller);
    var timer = setTimeout(function () {
      try {
        controller.abort("image timeout");
      } catch (error) {
        // ignore
      }
    }, Math.max(1, Math.min(S.IMAGE_FETCH_TIMEOUT_MS, remaining)));

    try {
      var response = await fetch(url, {
        method: "GET",
        credentials: "omit",
        cache: "force-cache",
        signal: controller.signal
      });
      if (!response.ok) throw new Error("HTTP " + response.status);

      var contentType = String(response.headers.get("content-type") || "")
        .split(";")[0]
        .trim()
        .toLowerCase();
      if (!contentType || contentType.indexOf("image/") !== 0) {
        throw new Error("not an image");
      }

      var declared = Number(response.headers.get("content-length") || 0);
      if (declared > S.MAX_IMAGE_BYTES) throw new Error("image too large");

      var buffer = await response.arrayBuffer();
      if (buffer.byteLength > S.MAX_IMAGE_BYTES) throw new Error("image too large");
      return "data:" + contentType + ";base64," + toBase64(buffer);
    } finally {
      clearTimeout(timer);
      activeControllers.delete(controller);
    }
  }

  async function inlineImages(markdown, images, deadline, epoch) {
    var list = Array.isArray(images) ? images : [];
    if (!list.length) return { markdown: markdown, failed: 0 };

    var unique = [];
    var seen = new Set();
    list.forEach(function (image) {
      var url = image && image.url ? String(image.url) : "";
      if (url && !seen.has(url)) {
        seen.add(url);
        unique.push(url);
      }
    });

    var results = new Map();
    var cursor = 0;

    async function worker() {
      while (cursor < unique.length) {
        var url = unique[cursor];
        cursor += 1;
        if (epoch !== windowEpoch || Date.now() >= deadline) {
          results.set(url, { ok: false, url: url });
          continue;
        }
        try {
          var uri = await fetchImage(url, deadline);
          results.set(url, { ok: true, uri: uri });
        } catch (error) {
          results.set(url, { ok: false, url: url });
        }
      }
    }

    var workers = [];
    var count = Math.min(S.IMAGE_CONCURRENCY, unique.length);
    for (var i = 0; i < count; i += 1) workers.push(worker());
    await Promise.all(workers);

    var output = String(markdown || "");
    var failed = 0;
    list.forEach(function (image, index) {
      var url = image && image.url ? String(image.url) : "";
      var token = imageToken(index);
      var result = results.get(url);
      if (result && result.ok) {
        output = output.split(token).join(result.uri);
      } else {
        failed += 1;
        // Requirement 8: keep the original absolute URL when inlining fails.
        output = output.split(token).join(url);
      }
    });

    return { markdown: output, failed: failed };
  }

  /* ------------------------------------------------------------------ */
  /* Upload                                                              */
  /* ------------------------------------------------------------------ */

  async function upload(item, settings, timeoutMs, epoch) {
    if (epoch !== windowEpoch) throw codedError("armed window changed", "held");

    var multipart = buildMultipart(item);
    var controller = new AbortController();
    activeControllers.add(controller);
    var timedOut = false;
    var timer = setTimeout(function () {
      timedOut = true;
      try {
        controller.abort("upload timeout");
      } catch (error) {
        // ignore
      }
    }, Math.max(1, timeoutMs));

    try {
      var response = await fetch(settings.endpoint, {
        method: "POST",
        credentials: "omit",
        cache: "no-store",
        headers: {
          Authorization: "Bearer " + settings.token,
          "Content-Type": "multipart/form-data; boundary=" + multipart.boundary
        },
        body: multipart.blob,
        signal: controller.signal
      });

      if (!(response.status >= 200 && response.status < 300)) {
        throw codedError("HTTP " + response.status, "http");
      }
      return { status: response.status, bytes: multipart.bytes };
    } catch (error) {
      // A disarm, re-arm or deadline expiry wins over every network outcome.
      var state = await getArmed();
      if (epoch !== windowEpoch || !isArmed(state)) {
        throw codedError("disarmed or expired before upload", "held");
      }
      if (error && error.name === "AbortError") {
        throw codedError(timedOut ? "upload timeout" : "upload aborted", "timeout");
      }
      throw error;
    } finally {
      clearTimeout(timer);
      activeControllers.delete(controller);
    }
  }

  async function postCapture(item, requestedTimeoutMs, epoch) {
    if (epoch !== windowEpoch) throw codedError("armed window changed", "held");
    var state = await getArmed();
    if (!isArmed(state)) throw codedError("extension is not armed", "held");

    var settings = await getSettings();
    if (!settings.endpoint) throw codedError("sync endpoint is not configured", "settings");
    if (!settings.token) throw codedError("bearer token is not configured", "settings");

    // An upload may never outlive the armed window.
    var windowRemaining = state.armedUntil - Date.now();
    if (windowRemaining <= 0) throw codedError("armed window expired", "held");
    var timeout = Math.max(1, Math.min(requestedTimeoutMs || S.UPLOAD_TIMEOUT_MS, windowRemaining));

    return upload(item, settings, timeout, epoch);
  }

  /* ------------------------------------------------------------------ */
  /* Queue draining                                                      */
  /* ------------------------------------------------------------------ */

  var drainPromise = null;

  function drainQueue(trigger) {
    if (drainPromise) return drainPromise;
    drainPromise = drainQueueNow(trigger).then(
      function (result) {
        drainPromise = null;
        return result;
      },
      function (error) {
        drainPromise = null;
        throw error;
      }
    );
    return drainPromise;
  }

  async function drainQueueNow(trigger) {
    var state = await getArmed();
    var remaining = await queueCount();
    if (!isArmed(state)) {
      return { ok: true, held: true, uploaded: 0, failed: 0, remaining: remaining };
    }

    var items = await queueAll();
    var uploaded = 0;
    var failed = 0;

    for (var i = 0; i < items.length; i += 1) {
      var current = await getArmed();
      if (!isArmed(current)) {
        return {
          ok: true,
          held: true,
          uploaded: uploaded,
          failed: failed,
          remaining: await queueCount()
        };
      }

      var item = items[i];
      try {
        var result = await postCapture(item, S.UPLOAD_TIMEOUT_MS, windowEpoch);
        try {
          await queueDelete(item.id);
        } catch (deleteError) {
          // The upload already succeeded; never turn a delete failure into a
          // queued retry of the same payload.
        }
        await rememberDedupe(item.key, current.armedAt);
        uploaded += 1;
        await appendLog({
          url: item.url,
          status: "uploaded",
          bytes: result.bytes,
          reason: "queue retry (" + (trigger || "auto") + ")",
          images_failed: item.images_failed
        });
      } catch (error) {
        failed += 1;
        await bumpQueue(item.id, error.message);
        if (error.code === "held") {
          return {
            ok: true,
            held: true,
            uploaded: uploaded,
            failed: failed,
            remaining: await queueCount()
          };
        }
        await appendLog({
          url: item.url,
          status: "queued",
          bytes: item.bytes || 0,
          reason: "retry failed: " + (error.message || "unknown error"),
          images_failed: item.images_failed
        });
        // A dead endpoint should not cause a retry storm.  The next explicit
        // flush (or the next successful capture) tries the remaining items.
        break;
      }
    }

    return {
      ok: true,
      uploaded: uploaded,
      failed: failed,
      remaining: await queueCount()
    };
  }

  /* ------------------------------------------------------------------ */
  /* Capture handling                                                    */
  /* ------------------------------------------------------------------ */

  async function handleCapture(data, triggeredAt) {
    if (!data || typeof data.markdown !== "string" || !data.url) {
      return { ok: false, error: "invalid capture payload" };
    }

    var epoch = windowEpoch;
    var parsedUrl;
    try {
      parsedUrl = new URL(data.url);
    } catch (error) {
      return { ok: false, error: "invalid page URL" };
    }

    var host = S.normalizeHost(data.host || parsedUrl.hostname);
    var state = await getArmed();

    if (epoch !== windowEpoch) {
      await appendLog({
        url: data.url,
        status: "failed",
        bytes: 0,
        reason: "armed window changed",
        images_failed: 0
      });
      return { ok: true, status: "failed" };
    }

    if (!state.armedHost || host !== state.armedHost) {
      await appendLog({
        url: data.url,
        status: "skipped",
        bytes: 0,
        reason: state.armedHost ? "host not armed" : "not armed",
        images_failed: 0
      });
      return { ok: true, status: "skipped" };
    }

    if (!isArmed(state)) {
      await appendLog({
        url: data.url,
        status: "failed",
        bytes: 0,
        reason: "expired",
        images_failed: 0
      });
      return { ok: true, status: "expired" };
    }

    var startedAt = Number(triggeredAt) || Date.now();
    if (Date.now() - startedAt > S.CAPTURE_BUDGET_MS) {
      await appendLog({
        url: data.url,
        status: "failed",
        bytes: 0,
        reason: "timeout",
        images_failed: 0
      });
      return { ok: true, status: "failed" };
    }

    // Leave a little room inside the 10 second extraction/inlining budget.
    var inlineDeadline = startedAt + S.CAPTURE_BUDGET_MS - 500;
    var inlined = await inlineImages(data.markdown, data.images, inlineDeadline, epoch);

    if (epoch !== windowEpoch) {
      await appendLog({
        url: data.url,
        status: "failed",
        bytes: S.byteLength(inlined.markdown || ""),
        reason: "armed window changed",
        images_failed: inlined.failed
      });
      return { ok: true, status: "failed" };
    }

    if (Date.now() - startedAt > S.CAPTURE_BUDGET_MS) {
      await appendLog({
        url: data.url,
        status: "failed",
        bytes: S.byteLength(inlined.markdown || ""),
        reason: "timeout",
        images_failed: inlined.failed
      });
      return { ok: true, status: "failed" };
    }

    var body = normalizeMarkdown(inlined.markdown);
    if (body.trim().length === 0) {
      await appendLog({
        url: data.url,
        status: "failed",
        bytes: 0,
        reason: "no extractable content",
        images_failed: inlined.failed
      });
      return { ok: true, status: "failed" };
    }

    var hash = await sha256Hex(body);
    var capturedAt = data.captured_at || S.nowIso();
    var links = Array.isArray(data.links) ? data.links : [];

    var doc = buildDocument(
      {
        url: data.url,
        title: data.title || parsedUrl.hostname,
        host: host,
        captured_at: capturedAt,
        content_hash: hash
      },
      body
    );

    var payloadBytes = S.byteLength(doc);
    var item = {
      key: dedupeKey(data.url, hash),
      url: data.url,
      title: data.title || "",
      host: host,
      captured_at: capturedAt,
      content_hash: hash,
      links: links,
      doc: doc,
      bytes: payloadBytes,
      images_failed: inlined.failed,
      queued_at: S.nowIso(),
      attempts: 0,
      reason: ""
    };

    // Two tabs (or a load plus a fast SPA transition) can finish extraction at
    // the same moment.  Reserve the key before the network request so only
    // one of them can reach the uploader.
    if (inFlightKeys.has(item.key) || (await isDuplicate(item.key, state.armedAt))) {
      await appendLog({
        url: item.url,
        status: "skipped",
        bytes: payloadBytes,
        reason: "duplicate",
        images_failed: inlined.failed
      });
      return { ok: true, status: "skipped" };
    }
    inFlightKeys.add(item.key);

    try {
      // Re-check immediately before the network request: disarming or the
      // deadline expiring while images were fetching must stop the upload.
      var current = await getArmed();
      if (epoch !== windowEpoch || !isArmed(current)) {
        await appendLog({
          url: item.url,
          status: "failed",
          bytes: payloadBytes,
          reason: "disarmed or expired before upload",
          images_failed: inlined.failed
        });
        return { ok: true, status: "failed" };
      }

      try {
        var result = await postCapture(item, S.UPLOAD_TIMEOUT_MS, epoch);
        if (current.armedAt === state.armedAt) {
          await rememberDedupe(item.key, state.armedAt);
        }
        await appendLog({
          url: item.url,
          status: "uploaded",
          bytes: result.bytes,
          reason: "HTTP " + result.status,
          images_failed: inlined.failed
        });

        // Requirement 11: queued captures retry on the next successful capture.
        try {
          await drainQueue("after-success");
        } catch (error) {
          // The successful capture stands even if queue draining fails.
        }

        return { ok: true, status: "uploaded", queueCount: await queueCount() };
      } catch (error) {
        if (error.code === "held") {
          await appendLog({
            url: item.url,
            status: "failed",
            bytes: payloadBytes,
            reason: "disarmed or expired before upload",
            images_failed: inlined.failed
          });
          return { ok: true, status: "failed" };
        }

        item.reason = error.message || "upload failed";
        try {
          await enqueue(item);
        } catch (queueError) {
          await appendLog({
            url: item.url,
            status: "failed",
            bytes: payloadBytes,
            reason: item.reason + "; queue unavailable",
            images_failed: inlined.failed
          });
          return { ok: false, error: "capture could not be queued" };
        }
        await appendLog({
          url: item.url,
          status: "queued",
          bytes: payloadBytes,
          reason: item.reason,
          images_failed: inlined.failed
        });
        return { ok: true, status: "queued", queueCount: await queueCount() };
      }
    } finally {
      inFlightKeys.delete(item.key);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Messages                                                            */
  /* ------------------------------------------------------------------ */

  async function activeTab() {
    var queries = [
      { active: true, currentWindow: true },
      { active: true, lastFocusedWindow: true },
      { active: true }
    ];
    for (var i = 0; i < queries.length; i += 1) {
      try {
        var tabs = await tabsQuery(queries[i]);
        if (tabs && tabs.length && tabs[0]) return tabs[0];
      } catch (error) {
        // try the next query shape
      }
    }
    return null;
  }

  async function getState() {
    var stored = await storageGet([K.endpoint, K.token, K.armedUntil, K.armedHost, K.armedAt, K.log]);
    var state = {
      endpoint: String(stored[K.endpoint] || ""),
      token: String(stored[K.token] || "").replace(/[\r\n]/g, ""),
      armedUntil: Number(stored[K.armedUntil]) || 0,
      armedHost: S.normalizeHost(stored[K.armedHost] || ""),
      armedAt: Number(stored[K.armedAt]) || 0,
      log: Array.isArray(stored[K.log]) ? stored[K.log] : []
    };
    state.armed = isArmed(state);
    state.queueCount = await queueCount();
    state.now = Date.now();
    state.signoff = S.CAPTURED_BY;
    return { ok: true, state: state };
  }

  async function arm() {
    var tab = await activeTab();
    if (!tab || !tab.url) {
      return { ok: false, error: "Open an http(s) page, then arm the extension." };
    }
    var parsed;
    try {
      parsed = new URL(tab.url);
    } catch (error) {
      return { ok: false, error: "The active tab has no usable URL." };
    }
    if (!/^https?:$/.test(parsed.protocol)) {
      return { ok: false, error: "Arm on an http(s) page inside Safari." };
    }

    var now = Date.now();
    var host = S.normalizeHost(parsed.hostname);
    var values = {};
    values[K.armedUntil] = now + S.ARM_WINDOW_MS;
    values[K.armedHost] = host;
    values[K.armedAt] = now;

    // A manual re-arm must always be able to re-send, even if an old capture
    // from the previous window is still finishing.
    windowEpoch += 1;
    inFlightKeys.clear();
    activeControllers.forEach(function (controller) {
      try {
        controller.abort("re-armed");
      } catch (error) {
        // ignore
      }
    });
    await storageSet(values);
    await resetDedupe(now);
    return getState();
  }

  async function disarm() {
    var values = {};
    values[K.armedUntil] = 0;
    values[K.armedHost] = "";
    values[K.armedAt] = 0;
    windowEpoch += 1;
    inFlightKeys.clear();
    activeControllers.forEach(function (controller) {
      try {
        controller.abort("disarmed");
      } catch (error) {
        // ignore
      }
    });
    await storageSet(values);
    await resetDedupe(0);
    return getState();
  }

  async function extend() {
    var state = await getArmed();
    if (!isArmed(state)) {
      return { ok: false, error: "The extension is not armed." };
    }
    var values = {};
    values[K.armedUntil] = Math.max(Date.now(), state.armedUntil) + S.ARM_WINDOW_MS;
    await storageSet(values);
    return getState();
  }

  async function saveSettings(message) {
    var endpoint = String(message.endpoint == null ? "" : message.endpoint).trim();
    var token = String(message.token == null ? "" : message.token)
      .replace(/[\r\n]/g, "")
      .trim();

    if (endpoint) {
      var parsed;
      try {
        parsed = new URL(endpoint);
      } catch (error) {
        return { ok: false, error: "Enter a full URL, including scheme and host." };
      }
      if (!/^https?:$/.test(parsed.protocol) || !parsed.hostname) {
        return { ok: false, error: "The endpoint must be an http(s) URL." };
      }
      if (parsed.username || parsed.password) {
        return { ok: false, error: "Do not put credentials in the sync URL." };
      }
    }

    var values = {};
    values[K.endpoint] = endpoint;
    values[K.token] = token;
    await storageSet(values);
    return getState();
  }

  async function handleMessage(message) {
    switch (message.type) {
      case "getState":
        return getState();
      case "arm":
        return arm();
      case "disarm":
        return disarm();
      case "extend":
        return extend();
      case "saveSettings":
        return saveSettings(message);
      case "flushQueue":
        return drainQueue(message.trigger || "manual");
      case "capture":
        return handleCapture(message.data, message.triggeredAt);
      case "clientLog":
        await appendLog(message.entry || {});
        return { ok: true };
      case "ping":
        return { ok: true, now: Date.now() };
      default:
        return { ok: false, error: "Unknown message type" };
    }
  }

  api.runtime.onMessage.addListener(function (message, sender, sendResponse) {
    Promise.resolve()
      .then(function () {
        return handleMessage(message || {}, sender);
      })
      .then(function (result) {
        try {
          sendResponse(result);
        } catch (error) {
          // The popup may have closed mid-flight.
        }
      })
      .catch(function (error) {
        try {
          sendResponse({ ok: false, error: String((error && error.message) || error) });
        } catch (sendError) {
          // ignore
        }
      });
    return true; // keep the message channel open for the async response
  });

  // Requirement 14: a disarm or an expired deadline aborts in-flight work.
  api.storage.onChanged.addListener(function (changes, area) {
    if (area !== "local") return;
    var untilChange = changes[K.armedUntil];
    var hostChange = changes[K.armedHost];
    if (!untilChange && !hostChange) return;

    var until =
      untilChange && untilChange.newValue !== undefined
        ? Number(untilChange.newValue)
        : null;
    var host =
      hostChange && hostChange.newValue !== undefined
        ? S.normalizeHost(hostChange.newValue)
        : null;

    var stopped =
      (until !== null && !(until > Date.now())) ||
      (host !== null && host === "");

    if (stopped) {
      activeControllers.forEach(function (controller) {
        try {
          controller.abort("disarmed");
        } catch (error) {
          // ignore
        }
      });
    }
  });
})();

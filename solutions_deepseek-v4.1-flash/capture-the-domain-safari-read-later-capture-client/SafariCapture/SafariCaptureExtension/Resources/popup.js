/*
 * Capture the Domain - popup controller.
 */
(function () {
  "use strict";

  var S = globalThis.SafariCapture;
  if (!S || !S.api) return;
  var api = S.api;

  var els = {
    hostLine: document.getElementById("hostLine"),
    statusPill: document.getElementById("statusPill"),
    countdown: document.getElementById("countdown"),
    timerHint: document.getElementById("timerHint"),
    armBtn: document.getElementById("armBtn"),
    extendBtn: document.getElementById("extendBtn"),
    disarmBtn: document.getElementById("disarmBtn"),
    endpoint: document.getElementById("endpoint"),
    token: document.getElementById("token"),
    saveBtn: document.getElementById("saveBtn"),
    saveState: document.getElementById("saveState"),
    queueRow: document.querySelector(".queueRow"),
    queueCount: document.getElementById("queueCount"),
    queueHint: document.getElementById("queueHint"),
    flushBtn: document.getElementById("flushBtn"),
    logList: document.getElementById("logList"),
    logCount: document.getElementById("logCount"),
    emptyLog: document.getElementById("emptyLog"),
    notice: document.getElementById("notice"),
    signoff: document.getElementById("signoff")
  };

  var state = {
    endpoint: "",
    token: "",
    armedUntil: 0,
    armedHost: "",
    armedAt: 0,
    armed: false,
    queueCount: 0,
    log: []
  };
  var busy = false;
  var noticeTimer = null;
  var syncTimer = null;
  var autoSaveTimer = null;

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function countdownText(milliseconds) {
    var seconds = Math.max(0, Math.ceil(milliseconds / 1000));
    var minutes = Math.floor(seconds / 60);
    var rest = seconds % 60;
    return pad(minutes) + ":" + pad(rest);
  }

  function timeLabel(iso) {
    var date = new Date(iso);
    if (isNaN(date.getTime())) return "--:--:--";
    return pad(date.getHours()) + ":" + pad(date.getMinutes()) + ":" + pad(date.getSeconds());
  }

  function showNotice(text) {
    if (!text) {
      els.notice.hidden = true;
      return;
    }
    els.notice.textContent = String(text);
    els.notice.hidden = false;
    if (noticeTimer) clearTimeout(noticeTimer);
    noticeTimer = setTimeout(function () {
      els.notice.hidden = true;
    }, 4200);
  }

  function setBusy(value) {
    busy = value;
    updateControls();
  }

  function updateControls() {
    var now = Date.now();
    var active = Number(state.armedUntil) > now && !!state.armedHost;
    els.armBtn.disabled = busy;
    els.extendBtn.disabled = busy || !active;
    els.disarmBtn.disabled = busy || !active;
    els.flushBtn.disabled = busy;
    els.saveBtn.disabled = busy;
    els.armBtn.textContent = active ? "Re-arm 10 min" : "Arm 10 min";
  }

  function tick() {
    var now = Date.now();
    var until = Number(state.armedUntil) || 0;
    var remaining = until - now;
    var active = remaining > 0 && !!state.armedHost;

    if (active) {
      els.countdown.textContent = countdownText(remaining);
      els.countdown.classList.remove("expired");
      els.statusPill.textContent = "ARMED";
      els.statusPill.className = "pill on";
      els.timerHint.textContent = "Armed on " + state.armedHost;
      els.hostLine.textContent = "Watching " + state.armedHost + " · every navigation";
    } else if (until > 0) {
      els.countdown.textContent = "00:00";
      els.countdown.classList.add("expired");
      els.statusPill.textContent = "EXPIRED";
      els.statusPill.className = "pill expired";
      els.timerHint.textContent = "Window expired · queue held";
      els.hostLine.textContent = "Last armed host: " + (state.armedHost || "unknown");
    } else {
      els.countdown.textContent = "00:00";
      els.countdown.classList.remove("expired");
      els.statusPill.textContent = "DISARMED";
      els.statusPill.className = "pill off";
      els.timerHint.textContent = "No armed window";
      els.hostLine.textContent = "Arm from the page you want to watch.";
    }

    updateControls();
  }

  function renderLog() {
    var entries = Array.isArray(state.log) ? state.log.slice(0, S.LOG_LIMIT) : [];
    els.logCount.textContent = entries.length + " / " + S.LOG_LIMIT;
    els.emptyLog.classList.toggle("hidden", entries.length > 0);
    els.logList.textContent = "";

    entries.forEach(function (entry) {
      var li = document.createElement("li");
      li.title = entry.url || "";

      var top = document.createElement("div");
      top.className = "logTop";

      var time = document.createElement("span");
      time.className = "logTime";
      time.textContent = timeLabel(entry.time);
      top.appendChild(time);

      var badge = document.createElement("span");
      var status = ["uploaded", "queued", "skipped", "failed"].indexOf(entry.status) >= 0
        ? entry.status
        : "failed";
      badge.className = "badge " + status;
      badge.textContent = status;
      top.appendChild(badge);

      var bytes = document.createElement("span");
      bytes.className = "logBytes";
      var byteCount = Math.max(0, Number(entry.bytes) || 0);
      bytes.textContent = byteCount + " B";
      bytes.title = S.formatBytes(byteCount);
      top.appendChild(bytes);

      li.appendChild(top);

      var url = document.createElement("div");
      url.className = "logUrl";
      url.textContent = S.truncate(entry.url || "(no url)", 84);
      li.appendChild(url);

      var meta = document.createElement("div");
      meta.className = "logMeta";

      var reason = document.createElement("span");
      reason.className = "logReason";
      reason.textContent = entry.reason || "—";
      reason.title = entry.reason || "";
      meta.appendChild(reason);

      var failedImages = Number(entry.images_failed) || 0;
      if (failedImages > 0) {
        var imageBadge = document.createElement("span");
        imageBadge.className = "imagesFailed";
        imageBadge.textContent = "images_failed " + failedImages;
        meta.appendChild(imageBadge);
      }

      li.appendChild(meta);
      els.logList.appendChild(li);
    });
  }

  function applyState(next, includeSettings) {
    if (!next) return;
    state = next;

    if (includeSettings) {
      if (document.activeElement !== els.endpoint) {
        els.endpoint.value = state.endpoint || "";
      }
      if (document.activeElement !== els.token) {
        els.token.value = state.token || "";
      }
    }

    var queue = Number(state.queueCount) || 0;
    els.queueCount.textContent = String(queue);
    els.queueRow.classList.toggle("hasQueue", queue > 0);
    els.queueHint.textContent =
      queue > 0 && !(Number(state.armedUntil) > Date.now() && state.armedHost)
        ? "held until armed"
        : "";

    renderLog();
    tick();
  }

  async function send(message) {
    return await api.runtime.sendMessage(message);
  }

  async function sync(includeSettings) {
    try {
      var result = await send({ type: "getState" });
      if (result && result.ok && result.state) {
        applyState(result.state, includeSettings);
      }
    } catch (error) {
      // The popup can outlive a restarting background worker; the next
      // interval or storage event retries.
    }
  }

  function scheduleSync() {
    if (syncTimer) clearTimeout(syncTimer);
    syncTimer = setTimeout(function () {
      if (!busy) sync(false);
    }, 120);
  }

  async function doArm() {
    setBusy(true);
    showNotice("");
    try {
      // Arm with whatever is currently typed, so the first capture already
      // uses the new endpoint/token without a separate Save step.
      if (!(await persistSettings(false))) return;
      var result = await send({ type: "arm" });
      if (!result || !result.ok) {
        showNotice((result && result.error) || "Could not arm.");
        return;
      }
      applyState(result.state, true);
      showNotice("Armed on " + result.state.armedHost + " for 10 minutes.");
    } catch (error) {
      showNotice("Could not arm: " + ((error && error.message) || error));
    } finally {
      setBusy(false);
    }
  }

  async function doDisarm() {
    setBusy(true);
    showNotice("");
    try {
      var result = await send({ type: "disarm" });
      if (!result || !result.ok) {
        showNotice((result && result.error) || "Could not disarm.");
        return;
      }
      applyState(result.state, true);
      showNotice("Disarmed. Nothing will upload.");
    } catch (error) {
      showNotice("Could not disarm: " + ((error && error.message) || error));
    } finally {
      setBusy(false);
    }
  }

  async function doExtend() {
    setBusy(true);
    showNotice("");
    try {
      var result = await send({ type: "extend" });
      if (!result || !result.ok) {
        showNotice((result && result.error) || "Could not extend.");
        return;
      }
      applyState(result.state, true);
      showNotice("Added 10 minutes to the armed window.");
    } catch (error) {
      showNotice("Could not extend: " + ((error && error.message) || error));
    } finally {
      setBusy(false);
    }
  }

  async function persistSettings(silent) {
    var endpoint = els.endpoint.value.trim();
    var token = els.token.value;

    if (endpoint) {
      var parsed;
      try {
        parsed = new URL(endpoint);
      } catch (error) {
        if (!silent) showNotice("Enter a full URL: scheme, host, optional port, and path.");
        return false;
      }
      if (!/^https?:$/.test(parsed.protocol) || !parsed.hostname) {
        if (!silent) showNotice("The endpoint must be an http(s) URL.");
        return false;
      }
      if (parsed.username || parsed.password) {
        if (!silent) showNotice("Do not put credentials in the sync URL.");
        return false;
      }
    }

    try {
      var result = await send({ type: "saveSettings", endpoint: endpoint, token: token });
      if (!result || !result.ok) {
        if (!silent) showNotice((result && result.error) || "Could not save settings.");
        return false;
      }
      applyState(result.state, true);
      els.saveState.textContent = "Saved " + new Date().toLocaleTimeString();
      return true;
    } catch (error) {
      if (!silent) showNotice("Could not save: " + ((error && error.message) || error));
      return false;
    }
  }

  async function doSave(silent) {
    setBusy(true);
    try {
      var saved = await persistSettings(silent);
      if (saved && !silent) showNotice("Settings saved. They apply to the next upload.");
      return saved;
    } finally {
      setBusy(false);
    }
  }

  async function doFlush(trigger, silent) {
    setBusy(true);
    if (!silent) showNotice("");
    try {
      // A queued retry must use the endpoint currently in the fields, even if
      // the user typed it and immediately tapped Flush.
      if (!(await persistSettings(silent))) return;
      var result = await send({ type: "flushQueue", trigger: trigger });
      if (!result || !result.ok) {
        if (!silent) showNotice((result && result.error) || "Could not flush the queue.");
        return;
      }
      await sync(false);
      if (!silent) {
        if (result.held) {
          showNotice("Queue held: arm the extension and stay inside the window.");
        } else if (result.uploaded > 0) {
          showNotice(
            "Flushed " + result.uploaded + " capture" + (result.uploaded === 1 ? "" : "s") +
              (result.remaining ? "; " + result.remaining + " still queued." : ".")
          );
        } else if (result.remaining > 0) {
          showNotice("Nothing sent; " + result.remaining + " capture(s) still queued.");
        } else {
          showNotice("Queue is empty.");
        }
      }
    } catch (error) {
      if (!silent) showNotice("Could not flush: " + ((error && error.message) || error));
    } finally {
      setBusy(false);
    }
  }

  function bind() {
    els.armBtn.addEventListener("click", doArm);
    els.disarmBtn.addEventListener("click", doDisarm);
    els.extendBtn.addEventListener("click", doExtend);
    els.saveBtn.addEventListener("click", function () {
      doSave(false);
    });
    els.flushBtn.addEventListener("click", function () {
      doFlush("manual", false);
    });

    [els.endpoint, els.token].forEach(function (input) {
      input.addEventListener("change", function () {
        doSave(true);
      });
      input.addEventListener("input", function () {
        if (autoSaveTimer) clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(function () {
          if (!busy) doSave(true);
        }, 700);
      });
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          if (autoSaveTimer) clearTimeout(autoSaveTimer);
          doSave(false);
        }
      });
    });

    api.storage.onChanged.addListener(function (changes, area) {
      if (area !== "local") return;
      if (
        changes[S.KEYS.log] ||
        changes[S.KEYS.armedUntil] ||
        changes[S.KEYS.armedHost] ||
        changes[S.KEYS.armedAt]
      ) {
        scheduleSync();
      }
    });
  }

  async function init() {
    els.signoff.textContent = S.CAPTURED_BY;
    bind();
    await sync(true);

    setInterval(tick, 250);
    setInterval(function () {
      if (!busy) sync(false);
    }, 2000);

    // Requirement 11: a queued capture retries when the popup opens.
    if (Number(state.armedUntil) > Date.now() && state.armedHost) {
      doFlush("popup-open", true);
    }
  }

  init();
})();

"use strict";
/* Outbox SPA — vanilla JS, no build step, no CDN. Consumes the REST API only. */

const state = {
  tab: "queue",
  filters: { status: "active", channel: "", sort: "newest", destination: "",
             created_from: "", created_to: "", expires_from: "", expires_to: "" },
  limit: 20, offset: 0, total: 0, items: [],
  loading: false, error: "",
  selectedId: null, detail: null, detailLoading: false,
  handoff: null, busy: {},
  destinations: [], destError: "",
  lastFocus: null,
};

const STATUS_META = {
  pending:   { glyph: "●", label: "Pending" },
  approved:  { glyph: "✓", label: "Approved" },
  rejected:  { glyph: "✕", label: "Rejected" },
  sent:      { glyph: "→", label: "Sent" },
  stale:     { glyph: "⏱", label: "Stale" },
  cancelled: { glyph: "⊘", label: "Cancelled" },
};
const QUEUE_ORDER = { pending: 0, approved: 1, rejected: 2 };

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, kids = []) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v === null || v === undefined) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function")
      node.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(node.dataset, v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of (Array.isArray(kids) ? kids : [kids])) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
};

/* ---------- API ---------- */
class ApiFail extends Error {
  constructor(status, body) { super(body.message || "request failed"); this.status = status; this.body = body; }
}
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  let body = null;
  try { body = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) throw new ApiFail(res.status, body || { error: "http_" + res.status, message: res.statusText });
  return body;
}
const post = (path, payload) => api(path, {
  method: "POST",
  headers: payload ? { "Content-Type": "application/json" } : undefined,
  body: payload ? JSON.stringify(payload) : undefined,
});

/* ---------- formatting ---------- */
const TZ = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "local"; } catch { return "local"; } })();
function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }) + " (" + TZ + ")";
}
function fmtRemaining(iso) {
  if (!iso) return null;
  const ms = new Date(iso) - Date.now();
  if (ms <= 0) return "expired";
  const s = Math.floor(ms / 1000);
  if (s < 60) return "in " + s + "s";
  const m = Math.floor(s / 60);
  if (m < 60) return "in " + m + "m";
  const h = Math.floor(m / 60);
  if (h < 48) return "in " + h + "h";
  return "in " + Math.floor(h / 24) + "d";
}
function fmtBytes(n) {
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KiB";
  return (n / 1024 / 1024).toFixed(1) + " MiB";
}
function statusChip(status) {
  const meta = STATUS_META[status] || { glyph: "•", label: status };
  return el("span", { class: "chip st " + status, text: meta.glyph + " " + meta.label });
}

/* ---------- toasts ---------- */
function toast(msg, kind = "") {
  const box = el("div", { class: "toast " + kind, text: msg });
  $("#toasts").append(box);
  setTimeout(() => box.remove(), 5200);
}

/* ---------- modal ---------- */
function openModal(title, bodyNode, actions) {
  state.lastFocus = document.activeElement;
  $("#modal-title").textContent = title;
  const mb = $("#modal-body"); mb.textContent = ""; mb.append(bodyNode);
  const ma = $("#modal-actions"); ma.textContent = "";
  for (const a of actions) ma.append(a);
  $("#modal-root").hidden = false;
  const focusable = $("#modal-box").querySelector("textarea, input, button");
  (focusable || $("#modal-box").querySelector("button")).focus();
}
function closeModal() {
  $("#modal-root").hidden = true;
  $("#modal-body").textContent = "";
  $("#modal-actions").textContent = "";
  if (state.lastFocus && state.lastFocus.focus) state.lastFocus.focus();
}
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!$("#modal-root").hidden) { closeModal(); return; }
    if (state.selectedId && window.matchMedia("(max-width: 980px)").matches) closeDetail();
  }
});

/* ---------- list fetching ---------- */
function statusQuery() {
  const s = state.filters.status;
  if (s === "active") return "pending,approved,rejected";
  if (s === "all") return "";
  return s;
}
async function refreshList({ keepSelection = true } = {}) {
  state.loading = true; state.error = ""; render();
  const params = new URLSearchParams();
  const st = statusQuery();
  if (st) params.set("status", st);
  if (state.filters.channel) params.set("channel", state.filters.channel);
  if (state.filters.destination) params.set("destination", state.filters.destination);
  if (state.filters.sort) params.set("sort", state.filters.sort);
  for (const key of ["created_from", "created_to", "expires_from", "expires_to"]) {
    if (state.filters[key]) params.set(key, state.filters[key]);
  }
  params.set("limit", state.limit); params.set("offset", state.offset);
  try {
    const page = await api("/api/messages?" + params.toString());
    state.items = page.items; state.total = page.total;
    state.limit = page.limit; state.offset = page.offset;
    if (state.filters.status === "active") {
      state.items.sort((a, b) =>
        (QUEUE_ORDER[a.status] ?? 9) - (QUEUE_ORDER[b.status] ?? 9));
    }
    if (!keepSelection || !state.items.some(m => m.id === state.selectedId)) {
      // keep open detail even if filtered out (user may act on it)
    }
  } catch (err) {
    state.error = err.message || "Failed to load messages";
  } finally {
    state.loading = false;
    render();
  }
}

/* ---------- detail fetching ---------- */
async function selectMessage(id) {
  state.selectedId = id; state.detail = null; state.handoff = null;
  state.detailError = null; state.history = null; state.events = [];
  state.detailLoading = true; render();
  try {
    const [detail, history, events] = await Promise.all([
      api(`/api/messages/${id}`),
      api(`/api/messages/${id}/history`),
      api(`/api/messages/${id}/webhook-events`),
    ]);
    state.detail = detail; state.history = history; state.events = events.items;
    if (detail.status === "approved") {
      try { state.handoff = await api(`/api/messages/${id}/handoff`); }
      catch (err) { state.handoff = { error: err.message }; }
    }
  } catch (err) {
    state.detailError = err.message;
  } finally {
    state.detailLoading = false; render();
    if (window.matchMedia("(max-width: 980px)").matches) {
      $("#detail-col").scrollIntoView({ block: "start" });
    }
  }
}
function closeDetail() { state.selectedId = null; state.detail = null; state.handoff = null; render(); }

/* ---------- actions ---------- */
async function runAction(key, label, fn, after) {
  state.busy[key] = true; render();
  try { await fn(); toast(label + " done", "ok"); if (after) await after(); }
  catch (err) { toast((err.body && err.body.message) || err.message, "error"); }
  finally { delete state.busy[key]; await refreshList(); await reloadDetailQuiet(); }
}
async function reloadDetailQuiet() {
  if (!state.selectedId) return;
  await selectMessage(state.selectedId);
}

function actionApprove() {
  return runAction("approve", "Approval", () => post(`/api/messages/${state.selectedId}/approve`));
}
function actionReject() {
  const id = state.selectedId;
  const reason = el("textarea", { placeholder: "Why is this message rejected? (required)",
                                  "aria-label": "Rejection reason", required: true });
  const errLine = el("p", { class: "field-err", text: "" });
  const body = el("div", {}, [
    el("p", { text: "The producer receives this reason verbatim, and it is preserved in history forever." }),
    reason, errLine,
  ]);
  const submit = el("button", { class: "btn warn", text: "Reject message" });
  submit.addEventListener("click", async () => {
    const value = reason.value.trim();
    if (!value) { errLine.textContent = "A non-empty reason is required."; reason.focus(); return; }
    submit.disabled = true; submit.textContent = "Rejecting…";
    try { await post(`/api/messages/${id}/reject`, { reason: value }); closeModal(); toast("Rejected", "ok"); await refreshList(); await reloadDetailQuiet(); }
    catch (err) { errLine.textContent = err.body?.message || err.message; submit.disabled = false; submit.textContent = "Reject message"; }
  });
  const cancel = el("button", { class: "btn plain", text: "Keep pending" });
  cancel.addEventListener("click", closeModal);
  openModal("Reject this message", body, [cancel, submit]);
  reason.focus();
}
function actionCancel() {
  const id = state.selectedId;
  const body = el("p", { text: "Cancel this message? It becomes permanently terminal; content and history are kept, nothing is deleted." });
  const yes = el("button", { class: "btn warn", text: "Cancel message" });
  yes.addEventListener("click", async () => {
    yes.disabled = true;
    try { await post(`/api/messages/${id}/cancel`, {}); closeModal(); toast("Cancelled", "ok"); await refreshList(); await reloadDetailQuiet(); }
    catch (err) { closeModal(); toast(err.body?.message || err.message, "error"); }
  });
  const no = el("button", { class: "btn plain", text: "Keep it" });
  no.addEventListener("click", closeModal);
  openModal("Confirm cancel", body, [no, yes]);
}
function actionMarkSent() {
  const id = state.selectedId;
  const box = el("input", { type: "checkbox", id: "sent-confirm-box" });
  const label = el("label", { for: "sent-confirm-box", text:
    "I confirm I actually sent this message in the external application myself. " +
    "This service never sends anything — you are recording that you did." });
  const body = el("div", {}, [
    el("p", { text: "Second confirmation required." }),
    el("div", { class: "check-row" }, [box, label]),
  ]);
  const yes = el("button", { class: "btn success", text: "Yes, it was sent — mark as sent", disabled: true });
  box.addEventListener("change", () => { yes.disabled = !box.checked; });
  yes.addEventListener("click", async () => {
    yes.disabled = true; yes.textContent = "Marking…";
    try { await post(`/api/messages/${id}/mark-sent`, {}); closeModal(); toast("Marked as sent", "ok"); await refreshList(); await reloadDetailQuiet(); }
    catch (err) { closeModal(); toast(err.body?.message || err.message, "error"); }
  });
  const no = el("button", { class: "btn plain", text: "Not yet" });
  no.addEventListener("click", closeModal);
  openModal("Mark as sent", body, [no, yes]);
}
async function copyText(text, what) {
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
    else {
      const ta = el("textarea", { value: text, style: "position:fixed;opacity:0" });
      document.body.append(ta); ta.select();
      const ok = document.execCommand("copy"); ta.remove();
      if (!ok) throw new Error("copy failed");
    }
    toast(what + " copied", "ok");
  } catch { toast("Could not access the clipboard — select the text manually", "error"); }
}

/* ---------- handoff ---------- */
function renderHandoff(h) {
  if (!h) return null;
  if (h.error) return el("div", { class: "callout warn", text: "Handoff unavailable: " + h.error });
  const caps = Object.entries(h.capabilities || {}).map(([k, v]) =>
    el("span", { class: "cap " + (v ? "yes" : "no"),
                 text: (v ? "✓ " : "✗ ") + k.replace(/_/g, " ") }));
  const url = h.handoff_url;
  const open = el("a", { class: "btn primary", href: url, target: "_blank", rel: "noopener noreferrer" },
    "Open " + h.channel[0].toUpperCase() + h.channel.slice(1));
  const children = [
    el("div", { class: "section-h", text: "Prepared handoff" }),
    el("div", { class: "handoff-url-box" }, [
      el("code", { class: "handoff-url", text: url }), open]),
    el("div", { class: "cap-list" }, caps),
    h.copy && (h.copy.subject ? el("div", { class: "d-actions" }, [
      el("button", { class: "btn plain", onclick: () => copyText(h.copy.subject, "Subject"), text: "Copy subject" })]) : null),
    el("div", { class: "d-actions" }, [
      el("button", { class: "btn plain", onclick: () => copyText(h.copy.body, "Body"), text: "Copy body" })]),
    h.warnings?.length ? el("div", { class: "callout warn" }, [
      el("strong", { text: "Limitations" }),
      el("ul", {}, h.warnings.map(w => el("li", { text: w })))]) : null,
    el("div", { class: "callout" }, [
      el("strong", { text: "Manual actions in " + h.channel }),
      el("ul", {}, (h.manual_actions || []).map(a => el("li", { text: a })))]),
    el("p", { class: "summary", text: "Opening this link or downloading files never changes the message status. " +
      h.attachment_instructions }),
  ];
  return el("div", {}, children.filter(Boolean));
}

/* ---------- render: list ---------- */
function cardFor(m) {
  const li = el("li", { class: "msg-card" + (m.id === state.selectedId ? " selected" : "") });
  const remaining = fmtRemaining(m.expires_at);
  const status = m.status;
  const destLine = el("p", { class: "card-dest" }, [
    m.destination, m.label ? el("span", { class: "card-label", text: "  ·  “" + m.label + "”" }) : null]);
  const inner = el("button", {
    class: "card-open", "aria-label": `Open message ${m.id}, status ${status}`,
    onclick: () => selectMessage(m.id),
  }, [
    el("div", { class: "card-top" }, [
      el("span", { class: "chip " + m.channel, text: m.channel }),
      statusChip(status),
      el("span", { class: "card-meta", text: "rev " + m.revision_number }),
    ]),
    destLine,
    m.subject ? el("p", { class: "card-subject", text: m.subject }) : null,
    el("p", { class: "card-preview", text: m.body_preview || "(no body)" }),
    el("div", { class: "card-meta" }, [
      el("span", { text: "created " + fmtTime(m.created_at) }),
      m.expires_at ? el("span", { class: status === "pending" || status === "approved" ? "warn-exp" : "",
                                  text: "expires " + fmtTime(m.expires_at) + (remaining ? " (" + remaining + ")" : "") }) : el("span", { text: "no expiration" }),
      el("span", { text: m.attachment_count + " attachment" + (m.attachment_count === 1 ? "" : "s") }),
    ]),
  ]);
  li.append(inner);
  return li;
}

function renderList() {
  const list = $("#message-list");
  list.textContent = "";
  const summary = $("#list-summary");
  if (state.loading) {
    summary.textContent = "Loading messages…";
    list.append(el("li", { class: "state-block" }, [el("span", { class: "big", text: "⏳" }), "Loading…"]));
    $("#list-pager").textContent = "";
    return;
  }
  if (state.error) {
    summary.textContent = "";
    list.append(el("li", { class: "state-block state-error" }, [
      el("span", { class: "big", text: "⚠" }),
      "Could not load messages: " + state.error,
      el("div", {}, [el("button", { class: "btn plain", onclick: () => refreshList(), text: "Retry" })])]));
    $("#list-pager").textContent = "";
    return;
  }
  const scope = state.filters.status === "all" ? "all messages"
    : state.filters.status === "active" ? "review queue (pending, approved, rejected)"
    : state.filters.status === "sent,stale,cancelled" ? "history (terminal messages)"
    : "status “" + state.filters.status + "”";
  summary.textContent = `${state.total} message(s) in ${scope} — showing ${state.items.length} ` +
    `(offset ${state.offset}).`;
  if (!state.items.length) {
    list.append(el("li", { class: "state-block" }, [
      el("span", { class: "big", text: "📭" }), "Nothing here. Adjust the filters or submit a message via the API."]));
    $("#list-pager").textContent = "";
    return;
  }
  for (const m of state.items) list.append(cardFor(m));
  const pager = $("#list-pager");
  pager.textContent = "";
  if (state.offset > 0)
    pager.append(el("button", { onclick: () => { state.offset = Math.max(0, state.offset - state.limit); refreshList(); }, text: "← Previous"}));
  pager.append(el("span", { text: `offset ${state.offset} · limit ${state.limit} · total ${state.total}` }));
  if (state.offset + state.limit < state.total)
    pager.append(el("button", { onclick: () => { state.offset += state.limit; refreshList(); }, text: "Next →"}));
}

/* ---------- render: detail ---------- */
function renderDetail() {
  const col = $("#detail-col");
  if (!state.selectedId) { col.hidden = true; col.textContent = ""; return; }
  col.hidden = false;
  const box = $("#detail");
  box.textContent = "";
  if (state.detailLoading) {
    box.append(el("div", { class: "state-block" }, [el("span", { class: "big", text: "⏳" }), "Loading message…"]));
    return;
  }
  if (state.detailError) {
    box.append(el("div", { class: "state-block state-error" }, [el("span", { class: "big", text: "⚠" }), state.detailError]));
    return;
  }
  const d = state.detail;
  const busy = (k) => Object.keys(state.busy).length > 0 || !!state.busy[k];

  box.append(el("div", { class: "d-head" }, [
    el("h2", { text: d.channel[0].toUpperCase() + d.channel.slice(1) + " message" }),
    statusChip(d.status),
    el("button", { class: "d-close", "aria-label": "Close details", onclick: closeDetail, text: "✕" }),
  ]));

  /* actions by status */
  const actions = el("div", { class: "d-actions" });
  if (d.status === "pending") {
    actions.append(
      el("button", { class: "btn success", disabled: busy("approve"), onclick: actionApprove, text: "✓ Approve" }),
      el("button", { class: "btn warn", disabled: busy("reject"), onclick: actionReject, text: "✕ Reject with reason" }),
      el("button", { class: "btn plain", disabled: busy("cancel"), onclick: actionCancel, text: "⊘ Cancel" }),
    );
  } else if (d.status === "approved") {
    actions.append(
      el("button", { class: "btn success", disabled: busy("sent"), onclick: actionMarkSent, text: "→ Mark as sent…" }),
      el("button", { class: "btn plain", disabled: busy("cancel"), onclick: actionCancel, text: "⊘ Cancel" }),
    );
  } else if (d.status === "rejected") {
    actions.append(
      el("button", { class: "btn plain", disabled: busy("cancel"), onclick: actionCancel, text: "⊘ Cancel" }),
    );
    box.append(el("div", { class: "callout rejected" }, [
      el("strong", { text: "Rejected — waiting for a revised submission" }),
      el("p", { text: "Reason: " + (d.rejection_reason || "n/a") }),
      el("p", { class: "summary", text: "The producer can PATCH this message; the new revision returns it to the queue automatically. No delivery actions are offered here." })]));
  } else {
    box.append(el("div", { class: "callout" },
      [el("strong", { text: "Terminal: " + (STATUS_META[d.status]?.label || d.status) + "." }),
       el("p", { text: "Content, attachments and full history are retained. No delivery actions are available." })]));
  }
  box.append(actions);

  /* fields */
  box.append(el("dl", { class: "kv" }, [
    el("dt", { text: "ID" }), el("dd", {}, [el("code", { text: d.id })]),
    el("dt", { text: "Destination" }), el("dd", { text: d.destination + " (" + (d.destination_kind || "individual") + ")" }),
    el("dt", { text: "Label" }), el("dd", { text: d.label || d.destination_label || "—" }),
    el("dt", { text: "Subject" }), el("dd", { text: d.subject || "—" }),
    el("dt", { text: "Source" }), el("dd", { text: d.source || "—" }),
    el("dt", { text: "Created" }), el("dd", { text: fmtTime(d.created_at) }),
    el("dt", { text: "Updated" }), el("dd", { text: fmtTime(d.updated_at) }),
    el("dt", { text: "Expires" }), el("dd", { text: d.expires_at ? fmtTime(d.expires_at) + " (" + (fmtRemaining(d.expires_at) || "") + ")" : "never" }),
    el("dt", { text: "Revision" }), el("dd", { text: "#" + d.revision_number }),
    el("dt", { text: "Webhook" }), el("dd", { text: d.webhook_url || "—" }),
  ]));

  box.append(el("div", { class: "section-h", text: "Body" }));
  box.append(el("pre", { class: "body-pre", text: d.body }));

  if (d.metadata) {
    box.append(el("div", { class: "section-h", text: "Metadata" }));
    box.append(el("pre", { class: "body-pre", text: JSON.stringify(d.metadata, null, 2) }));
  }

  /* attachments */
  box.append(el("div", { class: "section-h", text: `Attachments (${d.attachments.length})` }));
  if (!d.attachments.length) box.append(el("p", { class: "summary", text: "No attachments." }));
  const attList = el("ul", { class: "plain" });
  for (const a of d.attachments) {
    attList.append(el("li", { class: "att-row" }, [
      el("span", { class: "att-name", text: a.filename }),
      el("span", { class: "att-meta", text: `${a.mime_type} · ${fmtBytes(a.size_bytes)} · ${a.source_type}${a.source_url ? " · from " + a.source_url : ""}` }),
      el("span", { class: "grow" }),
      el("a", { class: "download-link", href: a.download_url, rel: "noopener", text: "⬇ Download" }),
    ]));
  }
  box.append(attList);
  if (d.attachments.length) {
    box.append(el("div", { class: "d-actions" }, [
      el("a", { class: "btn plain", href: `/api/messages/${d.id}/attachments.zip`, rel: "noopener", text: "⬇ Download all (ZIP)" }),
    ]));
  }

  /* references */
  if (d.references?.length) {
    box.append(el("div", { class: "section-h", text: `External references (${d.references.length})` }));
    box.append(el("p", { class: "summary", text: "Stored as links only — never downloaded by this service." }));
    box.append(el("ul", { class: "plain" }, d.references.map(r =>
      el("li", { class: "ref-row" }, [el("a", { href: r, target: "_blank", rel: "noopener noreferrer", text: r })]))));
  }

  /* handoff panel for approved */
  if (d.status === "approved") {
    const h = renderHandoff(state.handoff);
    if (h) box.append(h);
  }

  /* revision history */
  if (state.history) {
    box.append(el("div", { class: "section-h", text: "Revision history" }));
    const rl = el("ul", { class: "plain" });
    for (const r of state.history.revisions) {
      rl.append(el("li", { class: "hist-item" }, [
        el("b", { text: `rev ${r.revision_number} · ${r.change} · ${fmtTime(r.created_at)}` }),
        el("div", { text: `→ ${r.destination}${r.subject ? " · subject: " + r.subject : ""} · ${r.attachments.length} attachment(s)` }),
        r.rejection_reason ? el("div", { text: "rejected: " + r.rejection_reason }) : null,
        el("div", { class: "prev-body", text: r.body.length > 300 ? r.body.slice(0, 300) + "…" : r.body }),
      ]));
    }
    box.append(rl);

    box.append(el("div", { class: "section-h", text: "Status history" }));
    box.append(el("ul", { class: "plain" }, state.history.transitions.map(t =>
      el("li", { class: "hist-item", text: `${t.from_status ?? "∅"} → ${t.to_status} · rev ${t.revision_number} · ${fmtTime(t.timestamp)}${t.reason ? " · " + t.reason : ""}` }))));

    box.append(el("div", { class: "section-h", text: `Webhook delivery (${state.events.length})` }));
    if (!state.events.length) box.append(el("p", { class: "summary", text: "No webhook configured for this message, or no events yet." }));
    box.append(el("ul", { class: "plain" }, state.events.map(ev =>
      el("li", { class: "ev-item" }, [
        el("span", { class: "ev-state " + ev.state, text: "delivery " + ev.state + " · " }),
        el("b", { text: ev.event }),
        el("span", { text: ` · rev ${ev.revision_number} → ${ev.message_status} · ${ev.attempts} attempt(s)` +
          (ev.last_status_code ? ` · last HTTP ${ev.last_status_code}` : "") +
          (ev.last_error ? ` · error: ${ev.last_error}` : "") +
          (ev.next_attempt_at ? ` · retry ${fmtTime(ev.next_attempt_at)}` : "") }),
      ]))));
  }
}

/* ---------- destinations ---------- */
async function refreshDestinations() {
  try {
    const data = await api("/api/destinations");
    state.destinations = data.items; state.destError = "";
  } catch (err) { state.destError = err.message; }
  renderDestinations();
}
function renderDestinations() {
  const box = $("#dest-table");
  box.textContent = "";
  if (state.destError) { box.append(el("p", { class: "state-block state-error", text: state.destError })); return; }
  if (!state.destinations.length) {
    box.append(el("p", { class: "state-block", text: "No destinations yet — they appear automatically once messages are submitted." }));
    return;
  }
  const table = el("table");
  table.append(el("thead", {}, el("tr", {}, [
    el("th", { text: "Channel" }), el("th", { text: "Destination" }), el("th", { text: "Normalized" }),
    el("th", { text: "Label" }), el("th", { text: "Messages" }), el("th", { text: "Last used" }),
    el("th", { text: "Actions" })])));
  const tbody = el("tbody");
  for (const d of state.destinations) {
    const edit = el("button", { class: "btn plain", text: d.label ? "Rename label" : "Assign label" });
    edit.addEventListener("click", () => labelModal(d));
    const del = el("button", { class: "btn plain", text: "Remove label", disabled: !d.label });
    del.addEventListener("click", () => removeLabelModal(d));
    tbody.append(el("tr", {}, [
      el("td", {}, el("span", { class: "chip " + d.channel, text: d.channel })),
      el("td", { text: d.destination }),
      el("td", { text: d.normalized_destination }),
      el("td", { text: d.label || "—" }),
      el("td", { text: String(d.message_count) }),
      el("td", { text: fmtTime(d.last_used) }),
      el("td", {}, [edit, " ", del]),
    ]));
  }
  table.append(tbody);
  box.append(table);
}
function labelModal(dest) {
  const input = el("input", { type: "text", maxlength: "120", value: dest.label || "",
                              placeholder: "e.g. Alex — Client", "aria-label": "Label",
                              style: "width:100%;padding:.5rem;border:1px solid var(--line);border-radius:8px" });
  const errLine = el("p", { class: "field-err", text: "" });
  const body = el("div", {}, [
    el("p", { text: `Label for ${dest.channel} destination ${dest.normalized_destination}.` }),
    input, errLine,
    el("p", { class: "summary", text: "Labels are unique per channel. Historical messages are never modified." })]);
  const save = el("button", { class: "btn primary", text: "Save label" });
  save.addEventListener("click", async () => {
    const label = input.value.trim();
    if (!label) { errLine.textContent = "Label must not be empty."; return; }
    save.disabled = true;
    try {
      await api("/api/destinations/label", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: dest.channel, destination: dest.normalized_destination, label }),
      });
      closeModal(); toast("Label saved", "ok");
      await refreshDestinations(); await refreshList();
    } catch (err) {
      errLine.textContent = err.body?.message || err.message;
      save.disabled = false;
    }
  });
  const cancel = el("button", { class: "btn plain", text: "Cancel" });
  cancel.addEventListener("click", closeModal);
  openModal("Destination label", body, [cancel, save]);
  input.focus();
}
function removeLabelModal(dest) {
  const body = el("p", { text: `Remove the label “${dest.label}” from ${dest.channel} / ${dest.normalized_destination}? Messages keep their content and history; only the label goes away.` });
  const yes = el("button", { class: "btn warn", text: "Remove label" });
  yes.addEventListener("click", async () => {
    yes.disabled = true;
    try {
      const params = new URLSearchParams({ channel: dest.channel, destination: dest.normalized_destination });
      await api("/api/destinations/label?" + params, { method: "DELETE" });
      closeModal(); toast("Label removed", "ok");
      await refreshDestinations(); await refreshList();
    } catch (err) { closeModal(); toast(err.body?.message || err.message, "error"); }
  });
  const no = el("button", { class: "btn plain", text: "Keep label" });
  no.addEventListener("click", closeModal);
  openModal("Remove label", body, [no, yes]);
}

/* ---------- tabs ---------- */
function setTab(tab) {
  state.tab = tab;
  for (const b of document.querySelectorAll(".tab"))
    b.classList.toggle("active", b.dataset.tab === tab);
  $("#queue-panel").hidden = tab === "destinations";
  $("#destinations-panel").hidden = tab !== "destinations";
  if (tab === "destinations") refreshDestinations();
  if (tab === "queue") { state.filters.status = "active"; $("#f-status").value = "active"; refreshList(); }
  if (tab === "history") { state.filters.status = "sent,stale,cancelled";
    $("#f-status").value = "all"; refreshList(); }
}

/* ---------- top-level render ---------- */
function render() {
  renderList();
  renderDetail();
}

/* ---------- wiring ---------- */
function bindControls() {
  $("#tab-queue").addEventListener("click", () => setTab("queue"));
  $("#tab-history").addEventListener("click", () => setTab("history"));
  $("#tab-destinations").addEventListener("click", () => setTab("destinations"));
  $("#btn-refresh").addEventListener("click", () => refreshList());
  $("#btn-dest-refresh").addEventListener("click", refreshDestinations);
  $("#f-status").addEventListener("change", (e) => { state.filters.status = e.target.value; state.offset = 0; refreshList(); });
  $("#f-channel").addEventListener("change", (e) => { state.filters.channel = e.target.value; state.offset = 0; refreshList(); });
  $("#f-sort").addEventListener("change", (e) => { state.filters.sort = e.target.value; state.offset = 0; refreshList(); });
  let searchTimer = null;
  $("#f-destination").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.filters.destination = e.target.value.trim(); state.offset = 0; refreshList(); }, 350);
  });
  $("#btn-dates").addEventListener("click", () => {
    const fs = $("#date-range");
    fs.hidden = !fs.hidden;
    $("#btn-dates").setAttribute("aria-expanded", String(!fs.hidden));
  });
  for (const [id, key] of [["f-created-from", "created_from"], ["f-created-to", "created_to"],
                           ["f-expires-from", "expires_from"], ["f-expires-to", "expires_to"]]) {
    $("#" + id).addEventListener("change", (e) => { state.filters[key] = e.target.value; state.offset = 0; refreshList(); });
  }
  document.addEventListener("click", (e) => { if (e.target === $("#modal-root")) closeModal(); });
}

async function checkHealth() {
  const dot = $("#health-dot");
  try { await api("/api/health"); dot.className = "dot ok"; dot.setAttribute("aria-label", "service healthy"); }
  catch { dot.className = "dot bad"; dot.setAttribute("aria-label", "service unreachable"); }
}

/* auto-refresh every 30 s while the tab is visible and no modal is open */
setInterval(() => {
  if (document.hidden || !$("#modal-root").hidden) return;
  if (state.tab === "destinations") refreshDestinations();
  else refreshList();
}, 30000);
setInterval(checkHealth, 60000);

document.addEventListener("DOMContentLoaded", () => {
  bindControls();
  checkHealth();
  refreshList();
});

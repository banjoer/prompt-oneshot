# Human-in-the-Loop Outbox Service — Flask entry point.
#
# Built 2026-11-06 23:42 UTC by Qwen3.8 Flash (OpenCode, provider opencode-go,
# model qwen3.8-flash). This sign-off timestamp is the actual production time
# of this solution and is also shown in the SPA footer.
#
# Run:  pip install -r requirements.txt && python3 app.py
# Then open http://127.0.0.1:8000
"""Single-process outbox service: REST API + SPA + background workers."""
from __future__ import annotations

import io
import json
import re
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any, Optional

from flask import Flask, Response, jsonify, request, send_from_directory

from outbox import service
from outbox.config import AUTHOR, BUILT_AT, VERSION, Config
from outbox.db import init_db
from outbox.errors import ApiError, bad_request, unsupported_media
from outbox.netguard import UrlBlockedError
from outbox.openapi_spec import build_spec
from outbox.service import OutboxContext, Upload
from outbox.storage import AttachmentStore, sanitize_filename
from outbox.timeutil import now_iso
from outbox.webhooks import ExpirationWorker

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

MAX_REQUEST_BYTES_SLACK = 2 * 1024 * 1024  # multipart framing overhead allowance


def extract_payload(req) -> tuple[dict, list[Upload]]:
    """Parse a submission/PATCH request into (raw dict, uploads)."""
    ctype = (req.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype == "application/json" or req.is_json:
        raw = req.get_json(silent=True)
        if raw is None:
            raise bad_request("request body is not valid JSON")
        if not isinstance(raw, dict):
            raise bad_request("request body must be a JSON object")
        return raw, []
    if ctype in ("multipart/form-data", "application/x-www-form-urlencoded"):
        raw: dict[str, Any] = {}
        for key in req.form:
            values = req.form.getlist(key)
            raw[key] = values if key in ("references",) or len(values) > 1 else values[0]
        # decode JSON-encoded form strings
        for key in ("metadata", "attachments"):
            if key in raw and isinstance(raw[key], str):
                try:
                    raw[key] = json.loads(raw[key])
                except json.JSONDecodeError:
                    raise bad_request(f"form field {key!r} must be valid JSON") from None
        if "ttl_seconds" in raw and isinstance(raw["ttl_seconds"], str):
            text = raw["ttl_seconds"].strip()
            raw["ttl_seconds"] = int(text) if re.fullmatch(r"\d+", text) else text
        uploads = [Upload(filename=f.filename, stream=f.stream)
                   for f in req.files.getlist("attachments")]
        return raw, uploads
    raise unsupported_media(
        "Content-Type must be application/json or multipart/form-data",
        received=ctype or "none")


def _content_disposition(filename: str) -> str:
    safe_ascii = filename.encode("ascii", "ignore").decode() or "attachment"
    safe_ascii = re.sub(r"[^A-Za-z0-9 ._-]", "_", safe_ascii)
    quoted = urllib.parse.quote(filename, safe="")
    return f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{quoted}"


def _int_arg(name: str, default: int, *, minimum: int = 0,
             maximum: Optional[int] = None) -> int:
    raw = request.args.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise bad_request(f"'{name}' must be an integer", field=name) from None
    if value < minimum:
        raise bad_request(f"'{name}' must be >= {minimum}", field=name)
    if maximum is not None and value > maximum:
        value = maximum
    return value


def make_zip(ctx: OutboxContext, message_id: str, attachments: list[dict]) -> bytes:
    buf = io.BytesIO()
    used: dict[str, int] = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for att in attachments:
            name = sanitize_filename(att["filename"])
            # unique-ify inside the archive; never allow path separators
            if name in used:
                used[name] += 1
                stem, dot, ext = name.rpartition(".")
                name = f"{stem}_{used[name]}{dot}{ext}" if dot else f"{name}_{used[name]}"
                used[att["filename"]] = used.get(att["filename"], 1)
            else:
                used[name] = 1
            try:
                path = ctx.store.path_for(att["storage_reference"])
            except ApiError:
                continue  # missing file on disk: skip, the individual endpoint reports it
            zf.write(path, arcname=name)
    return buf.getvalue()


def create_app(cfg: Optional[Config] = None, *, start_background: bool = True,
               webhook_sender=None) -> Flask:
    cfg = cfg or Config.from_env()
    cfg.ensure_dirs()
    init_db(cfg)
    store = AttachmentStore(cfg)
    ctx = OutboxContext(cfg=cfg, store=store, webhook_sender=webhook_sender)

    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_message_attachment_bytes \
        + MAX_REQUEST_BYTES_SLACK
    app.json.ensure_ascii = False
    app.ctx = ctx  # type: ignore[attr-defined]

    spec = build_spec()
    worker: Optional[ExpirationWorker] = None
    if start_background:
        worker = ExpirationWorker(ctx)
        worker.start()
    app.outbox_worker = worker  # type: ignore[attr-defined]

    # ---- error handling -----------------------------------------------------

    def _handle(err: ApiError):
        return jsonify(err.to_body()), err.status

    app.register_error_handler(ApiError, _handle)

    @app.errorhandler(404)
    def _404(_e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not_found", "message": "no such endpoint"}), 404
        return _index()

    @app.errorhandler(405)
    def _405(_e):
        return jsonify({"error": "method_not_allowed",
                        "message": "method not allowed on this endpoint"}), 405

    @app.errorhandler(413)
    def _413(_e):
        return jsonify({"error": "payload_too_large", "message":
                        f"request body exceeds the {cfg.max_message_attachment_bytes}-byte "
                        "attachment budget for one message"}), 413

    @app.errorhandler(415)
    def _415(_e):
        return jsonify({"error": "unsupported_media_type", "message":
                        "Content-Type must be application/json or multipart/form-data"}), 415

    @app.errorhandler(Exception)
    def _500(err):
        if isinstance(err, UrlBlockedError):
            return jsonify({"error": "bad_request", "message": err.message}), 400
        app.logger.exception("unhandled error")
        return jsonify({"error": "internal_error",
                        "message": f"unexpected server error: {type(err).__name__}"}), 500

    # ---- static / docs --------------------------------------------------------

    def _index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/")
    def index():
        return _index()

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "time": now_iso()})

    @app.get("/api/info")
    def info():
        body = cfg.public_info()
        return jsonify(body)

    @app.get("/openapi.json")
    def openapi():
        return jsonify(spec)

    @app.get("/api/docs")
    def docs():
        return Response(DOCS_HTML, mimetype="text/html")

    # ---- messages -------------------------------------------------------------

    @app.post("/api/messages")
    def create_message():
        raw, uploads = extract_payload(request)
        view = service.submit_message(ctx, raw, uploads)
        return jsonify(view), 201

    @app.get("/api/messages")
    def list_messages():
        sort = request.args.get("sort", "newest")
        if sort not in ("newest", "oldest", "expires_soon", "expires_late"):
            raise bad_request("unknown sort", field="sort",
                              allowed=["newest", "oldest", "expires_soon", "expires_late"])
        return jsonify(service.list_messages(
            ctx,
            status=request.args.get("status"),
            channel=request.args.get("channel"),
            destination=request.args.get("destination"),
            created_from=request.args.get("created_from"),
            created_to=request.args.get("created_to"),
            expires_from=request.args.get("expires_from"),
            expires_to=request.args.get("expires_to"),
            limit=_int_arg("limit", 20, minimum=1, maximum=100),
            offset=_int_arg("offset", 0, minimum=0),
            sort=sort,
        ))

    @app.get("/api/messages/<message_id>")
    def get_message(message_id: str):
        return jsonify(service.get_message(ctx, message_id))

    @app.patch("/api/messages/<message_id>")
    def patch_message(message_id: str):
        raw, uploads = extract_payload(request)
        return jsonify(service.patch_message(ctx, message_id, raw, uploads))

    @app.post("/api/messages/<message_id>/approve")
    def approve(message_id: str):
        return jsonify(service.approve_message(ctx, message_id))

    @app.post("/api/messages/<message_id>/reject")
    def reject(message_id: str):
        raw = request.get_json(silent=True) if request.is_json else {}
        if raw is None or not isinstance(raw, dict):
            raise bad_request("reject requires a JSON body with a non-empty 'reason'",
                              field="reason")
        return jsonify(service.reject_message(ctx, message_id, raw.get("reason", "")))

    @app.post("/api/messages/<message_id>/cancel")
    def cancel(message_id: str):
        raw = request.get_json(silent=True) if (request.is_json and request.data) else {}
        reason = (raw or {}).get("reason") if isinstance(raw, dict) else None
        return jsonify(service.cancel_message(ctx, message_id, reason))

    @app.post("/api/messages/<message_id>/mark-sent")
    def mark_sent(message_id: str):
        raw = request.get_json(silent=True) if (request.is_json and request.data) else {}
        note = (raw or {}).get("note") if isinstance(raw, dict) else None
        return jsonify(service.mark_sent(ctx, message_id, note))

    @app.get("/api/messages/<message_id>/history")
    def history(message_id: str):
        return jsonify(service.history(ctx, message_id))

    @app.get("/api/messages/<message_id>/handoff")
    def handoff(message_id: str):
        return jsonify(service.handoff(ctx, message_id))

    @app.get("/api/messages/<message_id>/attachments")
    def list_attachments(message_id: str):
        return jsonify({"items": service.list_attachments(ctx, message_id)})

    @app.get("/api/messages/<message_id>/attachments.zip")
    def attachments_zip(message_id: str):
        attachments = service.list_attachments(ctx, message_id)
        blob = make_zip(ctx, message_id, attachments)
        return Response(blob, mimetype="application/zip", headers={
            "Content-Disposition": _content_disposition(f"{message_id}-attachments.zip"),
            "X-Content-Type-Options": "nosniff",
        })

    @app.get("/api/messages/<message_id>/attachments/<attachment_id>")
    def download_attachment(message_id: str, attachment_id: str):
        row, store_ = service.get_attachment(ctx, message_id, attachment_id)
        path = store_.path_for(row["stored_name"])
        data = path.read_bytes()
        return Response(data, mimetype=row["mime_type"], headers={
            "Content-Disposition": _content_disposition(row["filename"]),
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(len(data)),
        })

    @app.get("/api/messages/<message_id>/webhook-events")
    def webhook_events(message_id: str):
        return jsonify({"items": service.list_webhook_events(ctx, message_id)})

    # ---- destinations -----------------------------------------------------------

    @app.get("/api/destinations")
    def destinations():
        return jsonify({"items": service.list_destinations(ctx)})

    @app.put("/api/destinations/label")
    def put_label():
        raw = request.get_json(silent=True)
        if not isinstance(raw, dict):
            raise bad_request("body must be a JSON object with channel, destination, label")
        for key in ("channel", "destination", "label"):
            if key not in raw:
                raise bad_request(f"'{key}' is required", field=key)
        return jsonify(service.set_label(ctx, raw["channel"], raw["destination"],
                                         raw["label"]))

    @app.delete("/api/destinations/label")
    def delete_label():
        channel = request.args.get("channel")
        destination = request.args.get("destination")
        if not channel or not destination:
            raise bad_request("channel and destination query parameters are required")
        return jsonify(service.remove_label(ctx, channel, destination))

    return app


DOCS_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Outbox API docs</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 960px;
         padding: 0 1rem; color: #1c2333; background: #fafbfe; }
  h1 { font-size: 1.6rem; } .ep { border: 1px solid #d7dce8; border-radius: 8px;
     margin: .5rem 0; padding: .6rem .8rem; background: #fff; }
  .m { display: inline-block; font-weight: 700; font-size: .75rem; padding: .1rem .5rem;
     border-radius: 4px; color: #fff; margin-right: .6rem; }
  .get{background:#1d6fd6}.post{background:#2b8a3e}.patch{background:#b46102}
  .put{background:#6741d9}.delete{background:#c92a2a}
  code { background:#eef1f8; padding:.1rem .35rem; border-radius:4px; }
  details { margin-top: .4rem; } summary { cursor: pointer; color:#4a5570; }
  pre { background:#12182b; color:#dce6ff; padding: .8rem; border-radius: 8px;
       overflow: auto; font-size: .8rem; }
  .desc { color: #4a5570; margin: .2rem 0 0; }
</style>
</head>
<body>
<h1 id="title">Outbox REST API</h1>
<p>This page renders <code>/openapi.json</code> locally — no CDN, no network.</p>
<div id="list">Loading specification…</div>
<p><a href="/">Back to the dashboard</a> · <a href="/openapi.json">openapi.json</a></p>
<script>
fetch('/openapi.json').then(r => r.json()).then(spec => {
  const host = document.getElementById('list');
  host.textContent = '';
  document.getElementById('title').textContent = spec.info.title + ' — v' + spec.info.version;
  for (const [path, methods] of Object.entries(spec.paths)) {
    for (const [verb, op] of Object.entries(methods)) {
      const div = document.createElement('div'); div.className = 'ep';
      const badge = document.createElement('span');
      badge.className = 'm ' + verb; badge.textContent = verb.toUpperCase();
      const code = document.createElement('code'); code.textContent = path;
      div.appendChild(badge); div.appendChild(code);
      const p = document.createElement('p'); p.className = 'desc';
      p.textContent = (op.summary || '') + (op.description ? ' — ' + op.description : '');
      div.appendChild(p);
      if (op.parameters && op.parameters.length) {
        const d = document.createElement('details');
        d.innerHTML = '<summary>Parameters</summary><pre>' +
          JSON.stringify(op.parameters, null, 2) + '</pre>';
        div.appendChild(d);
      }
      const d2 = document.createElement('details');
      d2.innerHTML = '<summary>Responses</summary><pre>' +
        JSON.stringify(op.responses, null, 2) + '</pre>';
      div.appendChild(d2);
      host.appendChild(div);
    }
  }
}).catch(err => {
  document.getElementById('list').textContent = 'Failed to load /openapi.json: ' + err;
});
</script>
</body>
</html>
"""


def main() -> None:
    cfg = Config.from_env()
    app = create_app(cfg)
    print(f"outbox service v{VERSION} built {BUILT_AT} by {AUTHOR}")
    print(f"listening on http://{cfg.host}:{cfg.port}  (data: {cfg.data_dir})")
    app.run(host=cfg.host, port=cfg.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

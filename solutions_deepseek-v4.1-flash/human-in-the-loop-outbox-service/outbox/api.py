"""Flask HTTP layer for the human-in-the-loop outbox service."""

from __future__ import annotations

import html
import json
import threading
from pathlib import Path
from typing import Any
from urllib.parse import quote

from flask import Flask, Response, g, jsonify, request, send_from_directory
from werkzeug.exceptions import BadRequest, HTTPException, RequestEntityTooLarge

from . import __version__
from .config import Config
from .db import Database
from .errors import ApiError, UnsupportedMediaTypeError, ValidationError
from .service import OutboxService
from .storage import AttachmentStore
from .timeutil import now_iso
from .webhooks import WebhookDispatcher

APP_NAME = "Human-in-the-Loop Outbox Service"
AUTHOR = "DeepSeek V4.1 Flash"
BUILT_AT = "2026-11-07T00:09:15.580Z"


class ExpirationWorker(threading.Thread):
    """Periodic sweep; request-time checks remain authoritative."""

    def __init__(self, db: Database, config: Config, dispatcher: WebhookDispatcher) -> None:
        super().__init__(name="outbox-expiration", daemon=True)
        self.db = db
        self.config = config
        self.dispatcher = dispatcher
        self.stop_event = threading.Event()

    def run(self) -> None:
        interval = max(0.05, float(self.config.expiration_interval_seconds))
        while not self.stop_event.wait(interval):
            service = OutboxService(self.db, self.config, self.dispatcher)
            try:
                service.expire_due()
            except Exception:  # pragma: no cover - worker must never die
                pass
            finally:
                service.close()

    def stop(self) -> None:
        self.stop_event.set()


def create_app(
    overrides: dict[str, Any] | str | Path | None = None,
    base_dir: str | Path | None = None,
    start_workers: bool | None = None,
) -> Flask:
    config = Config.from_env(base_dir=base_dir, overrides=overrides)
    if start_workers is not None:
        config.start_workers = bool(start_workers)
    config.ensure_directories()
    database = Database(config.database_path)
    database.initialize()
    store = AttachmentStore(config.attachment_dir)
    dispatcher = WebhookDispatcher(database, config)

    static_dir = Path(config.static_dir or (Path(__file__).resolve().parent.parent / "static"))
    app = Flask(__name__, static_folder=str(static_dir), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = config.max_message_attachment_bytes + 2 * 1024 * 1024
    app.config["JSON_SORT_KEYS"] = False
    app.extensions["outbox"] = {
        "config": config,
        "database": database,
        "store": store,
        "dispatcher": dispatcher,
    }

    def service() -> OutboxService:
        existing = g.get("outbox_service")
        if existing is None:
            existing = OutboxService(database, config, dispatcher, store)
            g.outbox_service = existing
        return existing

    @app.teardown_appcontext
    def teardown_service(exception: BaseException | None) -> None:  # noqa: ARG001
        current = g.pop("outbox_service", None)
        if current is not None:
            current.close()

    worker: ExpirationWorker | None = None
    if config.start_workers:
        worker = ExpirationWorker(database, config, dispatcher)
        worker.start()
        app.extensions["outbox"]["expiration_worker"] = worker

    # ------------------------------------------------------------------ errors
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return jsonify(error.to_payload()), error.status

    @app.errorhandler(RequestEntityTooLarge)
    def handle_too_large(error: RequestEntityTooLarge):  # noqa: ARG001
        payload = {
            "error": {
                "code": "payload_too_large",
                "message": (
                    "The request exceeds the configured per-message attachment limit."
                ),
                "details": {
                    "max_message_attachment_bytes": config.max_message_attachment_bytes
                },
            }
        }
        return jsonify(payload), 413

    @app.errorhandler(BadRequest)
    def handle_bad_request(error: BadRequest):
        payload = {
            "error": {
                "code": "bad_request",
                "message": getattr(error, "description", None) or "Malformed request.",
                "details": {},
            }
        }
        return jsonify(payload), 400

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        if request.path.startswith("/api/") or request.path == "/openapi.json":
            payload = {
                "error": {
                    "code": "http_error",
                    "message": error.description or error.name,
                    "details": {"status": error.code},
                }
            }
            return jsonify(payload), error.code or 500
        return error

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        if isinstance(error, ApiError):
            return handle_api_error(error)
        if isinstance(error, HTTPException):
            return handle_http_exception(error)
        app.logger.exception("Unhandled error")
        payload = {
            "error": {
                "code": "internal_error",
                "message": "An unexpected server error occurred.",
                "details": {},
            }
        }
        return jsonify(payload), 500

    # ------------------------------------------------------------------ helpers
    def json_body(required: bool = True) -> dict[str, Any]:
        if not request.data:
            if required:
                raise ValidationError("A JSON request body is required.")
            return {}
        if not request.is_json:
            raise UnsupportedMediaTypeError(
                "This endpoint requires Content-Type: application/json."
            )
        data = request.get_json(silent=False)
        if not isinstance(data, dict):
            raise ValidationError("The JSON request body must be an object.")
        return data

    def parse_multipart() -> tuple[dict[str, Any], list[dict[str, Any]]]:
        data: dict[str, Any] = {}
        for field in (
            "channel",
            "destination",
            "destination_label",
            "subject",
            "body",
            "expires_at",
            "webhook_url",
            "source",
        ):
            if field in request.form:
                data[field] = request.form.get(field)
        if "ttl_seconds" in request.form:
            raw = request.form.get("ttl_seconds")
            try:
                data["ttl_seconds"] = int(raw)  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise ValidationError("ttl_seconds must be a positive integer.") from exc
        if "metadata" in request.form:
            raw = request.form.get("metadata") or ""
            if raw.strip():
                try:
                    parsed = json.loads(raw)
                except ValueError as exc:
                    raise ValidationError("metadata form field must be a JSON object.") from exc
                if not isinstance(parsed, dict):
                    raise ValidationError("metadata form field must be a JSON object.")
                data["metadata"] = parsed
        references: list[str] = []
        for raw in request.form.getlist("references"):
            if not raw:
                continue
            stripped = raw.strip()
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except ValueError as exc:
                    raise ValidationError("references form field must be a JSON array of URLs.") from exc
                if not isinstance(parsed, list):
                    raise ValidationError("references form field must be a JSON array of URLs.")
                references.extend(parsed)
            else:
                references.extend(part.strip() for part in stripped.split(",") if part.strip())
        if references:
            data["references"] = references
        files: list[dict[str, Any]] = []
        for uploaded in request.files.getlist("attachments"):
            if not uploaded or not uploaded.filename:
                continue
            files.append(
                {
                    "filename": uploaded.filename,
                    "mime_type": uploaded.mimetype,
                    "data": uploaded.read(),
                }
            )
        return data, files

    # ------------------------------------------------------------------ lifecycle
    @app.get("/api/health")
    def health():
        conn = None
        try:
            conn = database.connect()
            conn.execute("SELECT 1").fetchone()
            status = "ok"
            code = 200
        except Exception:  # pragma: no cover - only on broken storage
            status = "error"
            code = 503
        finally:
            if conn is not None:
                conn.close()
        return (
            jsonify(
                {
                    "status": status,
                    "time": now_iso(),
                    "version": __version__,
                    "database": str(config.database_path),
                }
            ),
            code,
        )

    @app.get("/api/info")
    def info():
        return jsonify(
            {
                "app": APP_NAME,
                "version": __version__,
                "built_at": BUILT_AT,
                "author": AUTHOR,
                "config": config.public_info(),
                "channels": ["email", "whatsapp", "telegram"],
                "statuses": [
                    "pending",
                    "approved",
                    "sent",
                    "rejected",
                    "stale",
                    "cancelled",
                ],
                "time": now_iso(),
            }
        )

    @app.post("/api/messages")
    def create_message():
        content_type = (request.content_type or "").lower()
        if request.is_json or content_type.startswith("application/json"):
            data = json_body(required=True)
            specs = data.get("attachments")
            if specs is not None and not isinstance(specs, list):
                raise ValidationError("attachments must be a list.")
            files: list[dict[str, Any]] = []
        elif content_type.startswith("multipart/form-data"):
            data, files = parse_multipart()
            specs = None
        else:
            raise UnsupportedMediaTypeError(
                "Submit messages as application/json or multipart/form-data."
            )
        result = service().create_message(
            data, files=files, attachment_specs=specs or []
        )
        response = jsonify(result)
        response.status_code = 201
        response.headers["Location"] = f"/api/messages/{result['id']}"
        return response

    @app.get("/api/messages")
    def list_messages():
        params: dict[str, Any] = {}
        for key in request.args:
            params[key] = request.args.get(key)
        for multi in ("status", "channel"):
            values = request.args.getlist(multi)
            if len(values) > 1:
                params[multi] = ",".join(values)
        return jsonify(service().list_messages(params))

    @app.get("/api/messages/<msg_id>")
    def get_message(msg_id: str):
        return jsonify(service().get_message(msg_id))

    @app.patch("/api/messages/<msg_id>")
    def patch_message(msg_id: str):
        data = json_body(required=True)
        return jsonify(service().patch_message(msg_id, data))

    @app.post("/api/messages/<msg_id>/approve")
    def approve(msg_id: str):
        if request.data and not request.is_json:
            raise UnsupportedMediaTypeError(
                "This endpoint accepts an empty body or Content-Type: application/json."
            )
        return jsonify(service().approve(msg_id))

    @app.post("/api/messages/<msg_id>/reject")
    def reject(msg_id: str):
        data = json_body(required=True)
        return jsonify(service().reject(msg_id, data.get("reason")))

    @app.post("/api/messages/<msg_id>/cancel")
    def cancel(msg_id: str):
        data = json_body(required=False)
        return jsonify(service().cancel(msg_id, data.get("reason")))

    @app.post("/api/messages/<msg_id>/mark-sent")
    def mark_sent(msg_id: str):
        if request.data and not request.is_json:
            raise UnsupportedMediaTypeError(
                "This endpoint accepts an empty body or Content-Type: application/json."
            )
        return jsonify(service().mark_sent(msg_id))

    @app.get("/api/messages/<msg_id>/history")
    def history(msg_id: str):
        return jsonify(service().get_history(msg_id))

    @app.get("/api/messages/<msg_id>/handoff")
    def handoff(msg_id: str):
        return jsonify(service().get_handoff(msg_id))

    @app.get("/api/messages/<msg_id>/webhook-events")
    def webhook_events(msg_id: str):
        return jsonify(service().webhook_events(msg_id))

    @app.get("/api/messages/<msg_id>/attachments")
    def list_attachments(msg_id: str):
        return jsonify(service().list_attachments(msg_id))

    @app.get("/api/messages/<msg_id>/attachments.zip")
    def download_all(msg_id: str):
        filename, data = service().download_zip(msg_id)
        return attachment_response(filename, data, "application/zip")

    @app.get("/api/messages/<msg_id>/attachments/<att_id>")
    def download_attachment(msg_id: str, att_id: str):
        row, data = service().get_attachment(msg_id, att_id)
        return attachment_response(
            row["original_filename"], data, row["mime_type"]
        )

    def attachment_response(filename: str, data: bytes, mime_type: str) -> Response:
        response = Response(data, mimetype=mime_type)
        safe_ascii = "".join(
            ch if 32 <= ord(ch) < 127 and ch not in {'"', "\\"} else "_"
            for ch in filename
        ) or "attachment"
        encoded = quote(filename, safe="")
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded}'
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Length"] = str(len(data))
        return response

    # --------------------------------------------------------------- destinations
    @app.get("/api/destinations")
    def list_destinations():
        params = {
            "channel": request.args.get("channel"),
            "q": request.args.get("q") or request.args.get("destination"),
        }
        return jsonify(service().list_destinations(params))

    @app.put("/api/destinations/label")
    def put_label():
        data = json_body(required=True)
        return jsonify(
            service().set_destination_label(
                data.get("channel"), data.get("destination"), data.get("label")
            )
        )

    @app.delete("/api/destinations/label")
    def delete_label():
        return jsonify(
            service().remove_destination_label(
                request.args.get("channel"), request.args.get("destination")
            )
        )

    # --------------------------------------------------------------------- docs
    @app.get("/openapi.json")
    def openapi_document():
        path = Path(config.openapi_path or (Path(__file__).resolve().parent.parent / "openapi.json"))
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ApiError(404, "not_found", "openapi.json has not been generated.")
        try:
            parsed = json.loads(text)
        except ValueError as exc:  # pragma: no cover - packaging error
            raise ApiError(500, "internal_error", f"openapi.json is invalid: {exc}") from exc
        return app.response_class(
            json.dumps(parsed, ensure_ascii=False),
            status=200,
            mimetype="application/json",
        )

    @app.get("/api/docs")
    def api_docs():
        path = Path(config.openapi_path or (Path(__file__).resolve().parent.parent / "openapi.json"))
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return Response(
                "<!doctype html><title>API docs</title><h1>OpenAPI specification unavailable</h1>",
                mimetype="text/html",
                status=500,
            )
        blocks: list[str] = []
        for route, operations in sorted(spec.get("paths", {}).items()):
            for method, operation in operations.items():
                if method.lower() not in {
                    "get", "post", "put", "patch", "delete", "head", "options"
                }:
                    continue
                summary = html.escape(operation.get("summary") or "")
                description = html.escape(operation.get("description") or "")
                blocks.append(
                    "<section class='op'>"
                    f"<div class='line'><span class='method {method.lower()}'>{method.upper()}</span>"
                    f"<code>{html.escape(route)}</code></div>"
                    f"<h2>{summary}</h2>"
                    f"<p>{description}</p>"
                    "</section>"
                )
        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(APP_NAME)} — API docs</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font: 16px/1.5 ui-sans-serif, system-ui, sans-serif; max-width: 1000px; margin: 0 auto; padding: 2rem 1rem 4rem; }}
h1 {{ margin-bottom: .25rem; }}
.sub {{ opacity: .7; margin-top: 0; }}
.op {{ border-top: 1px solid #8883; padding: .8rem 0; }}
.line {{ display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; }}
.method {{ display: inline-block; min-width: 4.5rem; text-align: center; border-radius: 4px; padding: .1rem .4rem; font: 700 .75rem/1.5 ui-monospace, monospace; background: #334155; color: #fff; }}
.method.get {{ background: #166534; }} .method.post {{ background: #1d4ed8; }}
.method.patch {{ background: #92400e; }} .method.put {{ background: #6b21a8; }}
.method.delete {{ background: #991b1b; }}
h2 {{ font-size: 1rem; margin: .55rem 0 .2rem; }}
p {{ margin: .2rem 0; opacity: .85; }}
a {{ color: #2563eb; }}
</style></head><body>
<h1>{html.escape(APP_NAME)} — API</h1>
<p class="sub">Generated from <a href="/openapi.json">/openapi.json</a> · built {html.escape(BUILT_AT)} by {html.escape(AUTHOR)}</p>
{''.join(blocks)}
</body></html>"""
        return Response(page, mimetype="text/html")

    # ---------------------------------------------------------------------- SPA
    @app.get("/")
    def index():
        index_path = static_dir / "index.html"
        if not index_path.exists():
            return Response(
                "<!doctype html><title>Outbox</title><h1>SPA not installed</h1>",
                mimetype="text/html",
                status=500,
            )
        return send_from_directory(str(static_dir), "index.html")

    @app.get("/favicon.ico")
    def favicon():
        return Response(status=204)

    return app

#!/usr/bin/env python3
# Built 2026-11-07 00:09 UTC by DeepSeek V4.1 Flash.
# Human-in-the-Loop Outbox Service — Flask + SQLite, single process, local only.
# This service never sends messages and never calls provider APIs; it prepares
# handoff links for a human reviewer and records exactly what happened.

from __future__ import annotations

from outbox.api import AUTHOR, BUILT_AT, APP_NAME, create_app

__all__ = ["create_app", "AUTHOR", "BUILT_AT", "APP_NAME"]

_cached_app = None


def get_app():
    global _cached_app
    if _cached_app is None:
        _cached_app = create_app()
    return _cached_app


def __getattr__(name: str):
    # `flask --app app` and evaluation harnesses often look for `app`; keeping
    # this lazy avoids writing the default ./data directory merely on import.
    if name in {"app", "application"}:
        return get_app()
    raise AttributeError(name)


def main() -> None:
    app = create_app()
    config = app.extensions["outbox"]["config"]
    print(f"{APP_NAME} {BUILT_AT} by {AUTHOR}")
    print(f"Open http://{config.host}:{config.port}  (data: {config.data_dir})")
    app.run(
        host=config.host,
        port=config.port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()

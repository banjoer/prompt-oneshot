#!/usr/bin/env python3
"""Regenerate docs/screenshot.svg from a sandboxed demo workspace.

Usage: python3 scripts/screenshot.py [width] [height]
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from balamba import demo  # noqa: E402
from balamba.app import BalambaApp  # noqa: E402


async def capture(width: int, height: int) -> None:
    root = Path("/tmp/balamba-demo-shot")
    os.environ["BALAMBA_DEMO_ROOT"] = str(root)
    ws = demo.prepare(reset=True)
    app = BalambaApp(ws)
    try:
        async with app.run_test(size=(width, height)) as pilot:
            for _ in range(200):
                await pilot.pause(0.1)
                if not app.booting:
                    break
            await pilot.pause(2.5)
            target = ROOT / "docs" / "screenshot.svg"
            target.parent.mkdir(parents=True, exist_ok=True)
            app.save_screenshot(str(target))
            # Textual's SVG includes remote Fira Code @font-face URLs.  Remove
            # them so the committed artifact has no network references at all;
            # browsers use the monospace fallback.
            svg = target.read_text(encoding="utf-8")
            svg = re.sub(r"@font-face\s*\{.*?\}", "", svg, flags=re.S)
            target.write_text(svg, encoding="utf-8")
            print(f"wrote {target} ({width}x{height})")
    finally:
        try:
            ws.tmux.kill_server()
        except Exception:
            pass
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    width = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    height = int(sys.argv[2]) if len(sys.argv) > 2 else 44
    asyncio.run(capture(width, height))

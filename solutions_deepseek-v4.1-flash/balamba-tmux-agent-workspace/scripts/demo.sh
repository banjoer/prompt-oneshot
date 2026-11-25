#!/usr/bin/env bash
# Create a sandboxed demo workspace (safe: separate state/config/socket).
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/bin/balamba" demo "$@"

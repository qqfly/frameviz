#!/usr/bin/env bash
# Inspection only. No user/global cache deletion is performed.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/inspect_build_paths.py" py "$@"

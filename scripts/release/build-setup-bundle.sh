#!/usr/bin/env bash
# Assemble reviewable files only. Installation never runs as part of packaging.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/build_setup_bundle.py" "$@"

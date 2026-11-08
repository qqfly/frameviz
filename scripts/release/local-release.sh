#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:?Choose a new absolute artifact output directory}"
[[ "$OUT" = /* ]] || { echo 'Use an absolute output path' >&2; exit 2; }
[[ ! -e "$OUT" ]] || { echo 'Output already exists' >&2; exit 2; }
mkdir -p "$OUT"
cd "$ROOT"
node scripts/sync-version.mjs --check
python3 scripts/check_source.py
python3 scripts/release/export_source.py "$OUT/source"
bash scripts/release/pack-js-sdk-tarballs.sh "$OUT/js"
"${FRAMEVIZ_TEST_PYTHON:-python3}" -m build --wheel --outdir "$OUT/wheels" packages/frameviz-py
printf '%s\n' 'Local source/SDK candidate created. Native/platform packages and public publication are separate maintainer actions.'

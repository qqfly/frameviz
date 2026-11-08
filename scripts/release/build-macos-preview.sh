#!/usr/bin/env bash
# Build an ad-hoc signed preview only; no Developer ID or Apple submission occurs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:?Choose a new absolute output directory}"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo 'This preview builder targets Apple Silicon macOS.' >&2; exit 2; }
[[ "$OUT" = /* && ! -e "$OUT" ]] || { echo 'Output must be a new absolute directory.' >&2; exit 2; }
mkdir -p "$OUT"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/.cache/macos-release/target}"
export MACOSX_DEPLOYMENT_TARGET=11.0
cd "$ROOT"
python3 -B scripts/sync_icons.py --check
node scripts/sync-version.mjs --check
pnpm --filter @frameviz/host-tauri exec tauri build --target aarch64-apple-darwin --bundles app --no-sign
APP="$OUT/FrameViz.app"
ditto "$CARGO_TARGET_DIR/aarch64-apple-darwin/release/bundle/macos/FrameViz.app" "$APP"
cargo metadata --locked --offline --format-version 1 --filter-platform aarch64-apple-darwin --manifest-path packages/frameviz-host-tauri/src-tauri/Cargo.toml > "$OUT/cargo-metadata.json"
python3 -B scripts/release/collect_macos_licenses.py --metadata "$OUT/cargo-metadata.json" --app "$APP"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
printf '%s\n' "Preview ready: $APP" 'This local signature is not Developer ID signing or Apple notarization. Follow docs/MACOS.md before distribution.'

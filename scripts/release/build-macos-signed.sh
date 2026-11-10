#!/usr/bin/env bash
# Explicit Developer ID workflow. Private identity/profile values stay outside source.
set -euo pipefail
: "${FRAMEVIZ_SIGNING_IDENTITY:?Set FRAMEVIZ_SIGNING_IDENTITY to an installed Developer ID Application identity}"
: "${FRAMEVIZ_NOTARY_PROFILE:?Set FRAMEVIZ_NOTARY_PROFILE to an existing notarytool Keychain profile}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:?Choose a new absolute output directory}"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo 'Use an Apple Silicon macOS builder.' >&2; exit 2; }
[[ "$FRAMEVIZ_SIGNING_IDENTITY" = 'Developer ID Application:'* ]] || { echo 'A Developer ID Application identity is required.' >&2; exit 2; }
[[ "$OUT" = /* && ! -e "$OUT" ]] || { echo 'Output must be a new absolute directory.' >&2; exit 2; }
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/.cache/macos-release/target}"
export MACOSX_DEPLOYMENT_TARGET=11.0
mkdir -p "$OUT"
cd "$ROOT"
python3 scripts/check_source.py
python3 scripts/sync_icons.py --check
node scripts/sync-version.mjs --check
pnpm --filter @frameviz/host-tauri exec tauri build --target aarch64-apple-darwin --bundles app --no-sign -- --locked
APP="$OUT/FrameViz.app"
ditto "$CARGO_TARGET_DIR/aarch64-apple-darwin/release/bundle/macos/FrameViz.app" "$APP"
cargo metadata --locked --format-version 1 --filter-platform aarch64-apple-darwin --manifest-path packages/frameviz-host-tauri/src-tauri/Cargo.toml > "$OUT/cargo-metadata.json"
python3 scripts/release/collect_macos_licenses.py --metadata "$OUT/cargo-metadata.json" --app "$APP"
# The current App has no embedded frameworks/plug-ins; fail if packaging changes.
if [[ -d "$APP/Contents/Frameworks" || -d "$APP/Contents/PlugIns" ]]; then
  echo 'Review and sign new nested executable code before using this builder.' >&2
  exit 2
fi
codesign --force --options runtime --timestamp --entitlements packages/frameviz-host-tauri/src-tauri/Entitlements.plist --sign "$FRAMEVIZ_SIGNING_IDENTITY" "$APP"
codesign --verify --deep --strict "$APP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$OUT/FrameViz.app.zip"
xcrun notarytool submit "$OUT/FrameViz.app.zip" --keychain-profile "$FRAMEVIZ_NOTARY_PROFILE" --wait --output-format json > "$OUT/app-notarization.json"
python3 - "$OUT/app-notarization.json" <<'PY'
import json,sys
if json.load(open(sys.argv[1]))['status']!='Accepted':raise SystemExit('App notarization was not accepted; inspect the saved response.')
PY
xcrun stapler staple "$APP"
xcrun stapler validate "$APP"
spctl --assess --type execute "$APP"
mkdir "$OUT/dmg-root"
ditto "$APP" "$OUT/dmg-root/FrameViz.app"
ln -s /Applications "$OUT/dmg-root/Applications"
hdiutil create -volname FrameViz -srcfolder "$OUT/dmg-root" -format UDZO "$OUT/FrameViz.dmg"
codesign --force --timestamp --sign "$FRAMEVIZ_SIGNING_IDENTITY" "$OUT/FrameViz.dmg"
xcrun notarytool submit "$OUT/FrameViz.dmg" --keychain-profile "$FRAMEVIZ_NOTARY_PROFILE" --wait --output-format json > "$OUT/dmg-notarization.json"
python3 - "$OUT/dmg-notarization.json" <<'PY'
import json,sys
if json.load(open(sys.argv[1]))['status']!='Accepted':raise SystemExit('DMG notarization was not accepted; inspect the saved response.')
PY
xcrun stapler staple "$OUT/FrameViz.dmg"
xcrun stapler validate "$OUT/FrameViz.dmg"
spctl --assess --type open --context context:primary-signature "$OUT/FrameViz.dmg"
shasum -a 256 "$OUT/FrameViz.dmg" > "$OUT/SHA256SUMS"
printf '%s\n' 'Signed and notarized artifact created. Download/open acceptance on the other Mac remains required.'

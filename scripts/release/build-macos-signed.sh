#!/usr/bin/env bash
# Explicit Developer ID workflow. Private identity/profile values stay outside source.
set -euo pipefail
: "${FRAMEVIZ_SIGNING_IDENTITY:?Set FRAMEVIZ_SIGNING_IDENTITY to an installed Developer ID Application identity}"
FRAMEVIZ_NOTARY_PROFILE="${FRAMEVIZ_NOTARY_PROFILE:-qqfly-apple-notary}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:?Choose an absolute output directory}"
MODE="${2:-full}"
case "$MODE" in full|--prepare-app|--resume-app) ;; *) echo "Use --prepare-app or --resume-app, or omit for App and DMG." >&2; exit 2;; esac
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo 'Use an Apple Silicon macOS builder.' >&2; exit 2; }
[[ "$FRAMEVIZ_SIGNING_IDENTITY" = 'Developer ID Application:'* ]] || { echo 'A Developer ID Application identity is required.' >&2; exit 2; }
[[ "$OUT" = /* ]] || { echo 'Use an absolute output directory.' >&2; exit 2; }
if [[ "$MODE" != --prepare-app ]]; then
  xcrun notarytool history --keychain-profile "$FRAMEVIZ_NOTARY_PROFILE" --output-format json >/dev/null
fi
APP="$OUT/FrameViz.app"
if [[ "$MODE" != --resume-app ]]; then
[[ ! -e "$OUT" ]] || { echo 'Output must be a new directory.' >&2; exit 2; }
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || { echo 'Commit the candidate in a clean checkout before signing.' >&2; exit 2; }
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/.cache/macos-release/target}"
export MACOSX_DEPLOYMENT_TARGET=11.0
mkdir -p "$OUT"
cd "$ROOT"
python3 scripts/check_source.py
python3 scripts/sync_icons.py --check
node scripts/sync-version.mjs --check
pnpm --filter @frameviz/host-tauri exec tauri build --target aarch64-apple-darwin --bundles app --no-sign -- --locked
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
python3 - "$OUT" "$(git rev-parse HEAD)" <<'PYRECEIPT'
import hashlib, json, sys
from pathlib import Path
out = Path(sys.argv[1])
files = ['FrameViz.app.zip', 'FrameViz.app/Contents/MacOS/frameviz']
(out / 'app-build.json').write_text(json.dumps({
    'source_revision': sys.argv[2],
    'files': {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in files},
}, indent=2) + '\n')
PYRECEIPT
fi

if [[ "$MODE" == --prepare-app ]]; then
  printf '%s\n' "Developer ID signed App prepared at $APP"
  exit
fi
python3 - "$OUT" "$(git -C "$ROOT" rev-parse HEAD)" <<'PYVERIFY'
import hashlib, json, sys
from pathlib import Path
out = Path(sys.argv[1])
receipt = json.loads((out / 'app-build.json').read_text())
if receipt['source_revision'] != sys.argv[2]:
    raise SystemExit('Prepared App is from a different candidate')
for name, digest in receipt['files'].items():
    if hashlib.sha256((out / name).read_bytes()).hexdigest() != digest:
        raise SystemExit(f'Prepared App changed: {name}')
PYVERIFY
codesign --verify --deep --strict "$APP"

notarize() {
  local file="$1" prefix="$2" id result
  if [[ ! -s "$OUT/$prefix-submission.json" ]]; then
    if [[ ! -e "$OUT/$prefix-submit.pending" ]]; then
      xcrun notarytool submit "$file" --keychain-profile "$FRAMEVIZ_NOTARY_PROFILE" \
        --output-format json > "$OUT/$prefix-submit.pending"
    fi
    if ! python3 -c 'import json,sys,uuid; uuid.UUID(json.load(open(sys.argv[1]))["id"])' "$OUT/$prefix-submit.pending"; then
      echo 'The first upload may already exist in Apple history. Recover the submission ID before retrying.' >&2
      return 1
    fi
    mv "$OUT/$prefix-submit.pending" "$OUT/$prefix-submission.json"
  fi
  id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$OUT/$prefix-submission.json")"
  printf '%s\n' "Apple notarization submission $id"
  xcrun notarytool wait "$id" --keychain-profile "$FRAMEVIZ_NOTARY_PROFILE" \
    --output-format json > "$OUT/$prefix-notarization.json"
  result="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$OUT/$prefix-notarization.json")"
  xcrun notarytool log "$id" --keychain-profile "$FRAMEVIZ_NOTARY_PROFILE" "$OUT/$prefix-notarization-log.json"
  [[ "$result" == Accepted ]] || { echo "Apple status: $result. Inspect the saved log." >&2; return 1; }
}

notarize "$OUT/FrameViz.app.zip" app
xcrun stapler staple "$APP"
xcrun stapler validate "$APP"
spctl --assess --type execute "$APP"
if [[ "$MODE" == --resume-app ]]; then
  exit
fi
mkdir "$OUT/dmg-root"
ditto "$APP" "$OUT/dmg-root/FrameViz.app"
ln -s /Applications "$OUT/dmg-root/Applications"
hdiutil create -volname FrameViz -srcfolder "$OUT/dmg-root" -format UDZO "$OUT/FrameViz.dmg"
codesign --force --timestamp --sign "$FRAMEVIZ_SIGNING_IDENTITY" "$OUT/FrameViz.dmg"
notarize "$OUT/FrameViz.dmg" dmg
xcrun stapler staple "$OUT/FrameViz.dmg"
xcrun stapler validate "$OUT/FrameViz.dmg"
spctl --assess --type open --context context:primary-signature "$OUT/FrameViz.dmg"
python3 - "$OUT" <<'PYHASH'
import hashlib,sys
from pathlib import Path
out=Path(sys.argv[1]);digest=hashlib.sha256((out/'FrameViz.dmg').read_bytes()).hexdigest()
(out/'SHA256SUMS').write_text(f'{digest}  FrameViz.dmg\n')
PYHASH
printf '%s\n' 'Signed and notarized artifact created. Download/open acceptance on the other Mac remains required.'

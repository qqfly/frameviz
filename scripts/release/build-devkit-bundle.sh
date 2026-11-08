#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"
INPUT_DIR="${2:-}"
OUT_DIR="${3:-}"

if [ -z "$VERSION" ] || [ -z "$INPUT_DIR" ]; then
  echo "Usage: $0 <version> <input-artifacts-dir> [output-dir]"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$INPUT_DIR}"

mkdir -p "$OUT_DIR"

find_one() {
  local pattern="$1"
  local found
  found="$(find "$INPUT_DIR" -maxdepth 1 -type f -name "$pattern" | head -n 1 || true)"
  if [ -z "$found" ]; then
    echo "Missing artifact: $pattern in $INPUT_DIR" >&2
    exit 1
  fi
  echo "$found"
}

sha256_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  else
    shasum -a 256 "$file" | awk '{print $1}'
  fi
}

PROTO_TGZ="$(find_one "frameviz-protocol-*.tgz")"
CORE_TGZ="$(find_one "frameviz-core-*.tgz")"
VUE_TGZ="$(find_one "frameviz-vue-*.tgz")"

PROTO_BASENAME="$(basename "$PROTO_TGZ")"
CORE_BASENAME="$(basename "$CORE_TGZ")"
VUE_BASENAME="$(basename "$VUE_TGZ")"

TMP_DIR="$(mktemp -d)"
DEVKIT_DIR="$TMP_DIR/FrameViz-$VERSION-devkit"
TEMPLATE_DIR="$DEVKIT_DIR/template"
VENDOR_DIR="$TEMPLATE_DIR/vendor"
CREATE_SCRIPT_SRC="$SCRIPT_DIR/create_new_frameviz_app.sh"
CREATE_SCRIPT_DST="$DEVKIT_DIR/create_new_frameviz_app.sh"

mkdir -p "$DEVKIT_DIR"
mkdir -p "$VENDOR_DIR"

echo "[devkit] copy template"
rmdir "$VENDOR_DIR" "$TEMPLATE_DIR"
python3 "$SCRIPT_DIR/export_source.py" "$TEMPLATE_DIR" --subtree templates/frameviz-template-external-app
mkdir -p "$VENDOR_DIR"

echo "[devkit] copy JS SDK tarballs"
cp "$PROTO_TGZ" "$VENDOR_DIR/"
cp "$CORE_TGZ" "$VENDOR_DIR/"
cp "$VUE_TGZ" "$VENDOR_DIR/"

echo "[devkit] rewrite template package.json to local vendor tarballs"
TEMPLATE_DIR="$TEMPLATE_DIR" PROTO_BASENAME="$PROTO_BASENAME" CORE_BASENAME="$CORE_BASENAME" VUE_BASENAME="$VUE_BASENAME" \
python3 <<'PY'
import json
import os
from pathlib import Path

template = Path(os.environ["TEMPLATE_DIR"])
pkg = json.loads((template / "package.json").read_text())
deps = pkg.get("dependencies", {})
deps["@frameviz/protocol"] = f"file:./vendor/{os.environ['PROTO_BASENAME']}"
deps["@frameviz/core"] = f"file:./vendor/{os.environ['CORE_BASENAME']}"
deps["@frameviz/vue"] = f"file:./vendor/{os.environ['VUE_BASENAME']}"
pkg["dependencies"] = deps

pnpm_cfg = pkg.get("pnpm", {})
overrides = pnpm_cfg.get("overrides", {})
overrides["@frameviz/protocol"] = f"file:./vendor/{os.environ['PROTO_BASENAME']}"
overrides["@frameviz/core"] = f"file:./vendor/{os.environ['CORE_BASENAME']}"
overrides["@frameviz/vue"] = f"file:./vendor/{os.environ['VUE_BASENAME']}"
pnpm_cfg["overrides"] = overrides
pkg["pnpm"] = pnpm_cfg

(template / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")
PY

echo "[devkit] write checksums"
: > "$VENDOR_DIR/SHA256SUMS.txt"
for tarball in "$VENDOR_DIR"/*.tgz; do
  checksum="$(sha256_file "$tarball")"
  echo "$checksum  $(basename "$tarball")" >> "$VENDOR_DIR/SHA256SUMS.txt"
done

echo "[devkit] write manifests"
VERSION="$VERSION" REPO_ROOT="$REPO_ROOT" TEMPLATE_DIR="$TEMPLATE_DIR" python3 <<'PY'
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

version = os.environ["VERSION"]
repo_root = Path(os.environ["REPO_ROOT"])
template_dir = Path(os.environ["TEMPLATE_DIR"])
version_json = json.loads((repo_root / "version.json").read_text())

entries = []
for tgz in sorted((template_dir / "vendor").glob("*.tgz")):
    h = hashlib.sha256()
    with tgz.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    entries.append(
        {
            "file": f"vendor/{tgz.name}",
            "sha256": h.hexdigest(),
        }
    )

manifest = {
    "frameviz_version": version,
    "required_frameviz_version": version,
    "required_protocol_version": version_json.get("protocol_version"),
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "js_sdk_artifacts": entries,
}

(template_dir / "DEVKIT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

if [ -f "$CREATE_SCRIPT_SRC" ]; then
  echo "[devkit] add app creation helper"
  cp "$CREATE_SCRIPT_SRC" "$CREATE_SCRIPT_DST"
  chmod +x "$CREATE_SCRIPT_DST"
fi

# Refresh the template manifest after dependency rewrites and vendor insertion.
TEMPLATE_DIR="$TEMPLATE_DIR" python3 <<'PYTHON'
import hashlib,json,os,pathlib
root=pathlib.Path(os.environ['TEMPLATE_DIR']);path=root/'source-manifest.json'
manifest=json.loads(path.read_text())
manifest['files']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p!=path}
path.write_text(json.dumps(manifest,indent=2)+'\n')
PYTHON

echo "[devkit] create bundle"
BUNDLE_NAME="FrameViz-$VERSION-devkit.tar.gz"
tar czf "$OUT_DIR/$BUNDLE_NAME" -C "$TMP_DIR" "FrameViz-$VERSION-devkit"

rm -rf "$TMP_DIR"
echo "[devkit] created: $OUT_DIR/$BUNDLE_NAME"

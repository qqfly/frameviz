#!/usr/bin/env bash
# Build on the target Ubuntu baseline. Uses a reusable cache, never installs locally.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:?Choose a new absolute output directory}"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || { echo 'Use an x86_64 Ubuntu builder.' >&2; exit 2; }
[[ "$OUT" = /* && ! -e "$OUT" ]] || { echo 'Output must be a new absolute directory.' >&2; exit 2; }
mkdir -p "$OUT"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/.cache/linux-release/target}"
mkdir -p "$CARGO_TARGET_DIR/frameviz-package"
cd "$ROOT"
python3 scripts/check_source.py
node scripts/sync-version.mjs --check
node scripts/prepare_web_viewer_dist.mjs
cargo build --locked --release --manifest-path packages/frameviz-server/Cargo.toml
cargo metadata --locked --format-version 1 --filter-platform x86_64-unknown-linux-gnu --manifest-path packages/frameviz-server/Cargo.toml > "$CARGO_TARGET_DIR/frameviz-package/server-metadata.json"
python3 scripts/release/collect_macos_licenses.py --metadata "$CARGO_TARGET_DIR/frameviz-package/server-metadata.json" --resources "$OUT/standalone/notices"
install -m 755 "$CARGO_TARGET_DIR/release/frameviz-server" "$OUT/standalone/frameviz-server"
cargo metadata --locked --format-version 1 --filter-platform x86_64-unknown-linux-gnu --manifest-path packages/frameviz-host-tauri/src-tauri/Cargo.toml > "$CARGO_TARGET_DIR/frameviz-package/tauri-metadata.json"
python3 scripts/release/collect_macos_licenses.py --metadata "$CARGO_TARGET_DIR/frameviz-package/tauri-metadata.json" --resources "$OUT/tauri-notices"
python3 - "$ROOT" "$OUT" "$CARGO_TARGET_DIR" <<'PY'
import json,sys
from pathlib import Path
root,out,target=map(Path,sys.argv[1:])
files={'/usr/bin/frameviz-server':str(target/'release/frameviz-server'),
       '/usr/share/doc/frameviz/standalone':str(out/'standalone/notices'),
       '/usr/share/doc/frameviz/desktop':str(out/'tauri-notices')}
(target/'frameviz-package/deb.json').write_text(json.dumps({'bundle':{'linux':{'deb':{'files':files}}}}))
PY
pnpm --filter @frameviz/host-tauri exec tauri build --ci --bundles deb --config "$CARGO_TARGET_DIR/frameviz-package/deb.json" -- --locked
python3 - "$OUT" "$CARGO_TARGET_DIR" <<'PY'
import hashlib,json,platform,shutil,subprocess,sys,tarfile
from pathlib import Path
out,target=map(Path,sys.argv[1:]);debs=list((target/'release/bundle/deb').glob('*.deb'))
if len(debs)!=1:raise SystemExit('Expected exactly one desktop deb; use a cache for this build version only')
shutil.copy2(debs[0],out/debs[0].name)
with tarfile.open(out/'frameviz-server-linux-x86_64.tar.gz','w:gz') as archive:
 archive.add(out/'standalone',arcname='frameviz-server')
subprocess.run([sys.executable,'-m','build','--wheel','--outdir',str(out),'packages/frameviz-py'],check=True)
artifacts=sorted(p for p in out.iterdir() if p.suffix in ('.deb','.gz','.whl'))
(out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in artifacts))
(out/'build.json').write_text(json.dumps({'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'platform':platform.platform(),'os_release':Path('/etc/os-release').read_text(),
 'rust':subprocess.check_output(['rustc','--version'],text=True).strip(),
 'artifacts':[p.name for p in artifacts],'scope':'Build receipt; desktop and second-machine acceptance are separate.'},indent=2)+'\n')
PY

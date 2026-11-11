#!/usr/bin/env bash
set -euo pipefail

repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo"
venv="$repo/.cache/simple-slider-venv"
"${FRAMEVIZ_PYTHON:-python3}" -m venv "$venv"
"$venv/bin/python" -m pip install -e packages/frameviz-py -r examples/apps/simple_slider/python/requirements.txt
if [[ ! -f node_modules/.modules.yaml ]]; then
  pnpm install --frozen-lockfile
fi
node scripts/prepare_web_viewer_dist.mjs
pnpm --filter @frameviz/vue build
pnpm --filter simple-slider-app exec vite build --outDir "$repo/.cache/simple-slider-ui" --emptyOutDir
cargo build --locked --manifest-path packages/frameviz-server/Cargo.toml

state="$(mktemp -d "$repo/.cache/simple-slider-state.XXXXXXXX")"
trap 'rm -rf -- "$state"' EXIT
unset FRAMEVIZ_DISCOVERY_PATH FRAMEVIZ_AUTH_TOKEN FRAMEVIZ_HOST
export FRAMEVIZ_HOME="$state"
export FRAMEVIZ_LOG_DIR="$state"
export FRAMEVIZ_HOST_PATH="$repo/packages/frameviz-server/target/debug/frameviz-server"
"$venv/bin/python" examples/apps/simple_slider/python/run_browser_demo.py --ui-dir "$repo/.cache/simple-slider-ui"

#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
pnpm install --frozen-lockfile
node scripts/sync-version.mjs --check
node scripts/prepare_web_viewer_dist.mjs
pnpm --filter @frameviz/vue build
pnpm exec vitest run
"${FRAMEVIZ_TEST_PYTHON:-python3}" -m pytest packages/frameviz-py/tests tests/acceptance/test_portable.py
cargo test --locked --manifest-path packages/frameviz-server/Cargo.toml
cmake -S packages/frameviz-cpp -B .validation/cpp -DFRAMEVIZ_BUILD_TESTS=ON -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build .validation/cpp -j 4
ctest --test-dir .validation/cpp --output-on-failure

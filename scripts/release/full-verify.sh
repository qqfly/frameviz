#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
bash scripts/ci.sh
printf '%s\n' 'Unit/contracts complete. Run isolated installed-consumer/browser/native checks as described in docs/VALIDATION.md; unrun checks are not passes.'

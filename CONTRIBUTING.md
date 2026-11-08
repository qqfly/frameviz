# Contributing

Discuss substantial API or protocol changes before implementation. Keep changes focused and include a reproducer for behavioral failures. Run the validation commands for the affected components and report actual pass, fail, skip, and disabled counts.

First-party contributions are submitted under the project's MIT license. Preserve third-party notices and identify the source and license of new bundled code or assets. Use generated fixtures rather than personal data, organization files, credentials, or unapproved models. Do not commit build trees, local discovery records, machine paths, tokens, or package caches.

Use `node scripts/sync-version.mjs --check`, `python3 scripts/check_source.py`, and the checks in `docs/VALIDATION.md`. Package or signing changes must include archive inventories and installation behavior; successful unit tests alone do not establish release readiness.

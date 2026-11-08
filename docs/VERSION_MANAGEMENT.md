# Version management

`version.json` is the source of truth. All components currently require protocol 0.4.0. Run `node scripts/sync-version.mjs --check` in CI and after packaging changes.

Bumping a version must update Host/SDK/schema/viewer constants, package metadata, Cargo locks, example/native manifests, and documented compatibility. A textual sync does not establish wire compatibility; run negative version tests and real installed-consumer checks. Keep formal release status separate from package version fields.

# Version management

`version.json` is the source of truth. All components currently require protocol 0.5.0. Run `node scripts/sync-version.mjs --check` in CI and after packaging changes.

`release_version` identifies distributable packages and binaries. `protocol_version` identifies the wire format. In a separate release checkout, use `node scripts/sync-version.mjs --release 0.5.0-rc.1` to stamp a prerelease while keeping the wire protocol unchanged. The runtime uses the SemVer string and the Python wheel uses its PEP 440 equivalent `0.5.0rc1`. CMake and macOS bundle numeric version fields use the numeric base. The signed Mac executable still reports its full prerelease and `build_runtime_wheel.py` checks both the release and protocol before assembly.

Bumping a version must update Host/SDK/schema/viewer constants, package metadata, Cargo locks, example/native manifests, and documented compatibility. A textual sync does not establish wire compatibility; run negative version tests and real installed-consumer checks. Keep formal release status separate from package version fields.

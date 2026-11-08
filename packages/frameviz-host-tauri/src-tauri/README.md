# FrameViz native shell

The native shell wraps the shared Rust Host and bundled web viewer. Build the viewer before compiling the shell. The original icon set is restored according to the maintainer's explicit request. `scripts/sync_icons.py` copies the approved files byte-for-byte; provenance and hashes are recorded in `artwork/icon-source.json`.

`FRAMEVIZ_DISCOVERY_PATH` and `FRAMEVIZ_LOG_DIR` must point to temporary directories during testing. Debug builds use an external dev server only when `FRAMEVIZ_DEV_SERVER_URL` explicitly selects a valid loopback HTTP URL. A busy port is not proof of a development server.

Use an isolated app bundle identity and explicit executable path for native tests. Platform builds, mouse interaction, signing, packaging, upgrades, and installed operation are independent acceptance steps. No current source-build result establishes all-platform support.

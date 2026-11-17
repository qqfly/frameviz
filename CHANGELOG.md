# Changelog

## 0.5.0 (Unreleased)

### New

- Build rigid scene trees in Python and C++. Reparent objects without moving them, and give each View its own camera.
- Pick points by their index and world position. A chunked point cloud still has one object ID.
- Add sliders, buttons, and five other scene controls. Numeric sliders support exact input and commit on release.
- Inspect scene objects, poses, and camera settings.
- Save a [PNG screenshot](examples/python/06_scene_output/save_png.py) from a temporary camera, even with no window open, from Python or C++.
- Export [standalone HTML](examples/python/06_scene_output/export_html.py) that works offline, with orbit controls and optional precomputed pose animation, from Python or C++.
- Attach to a running local app or share a revocable, read-only LAN link.

### Improved

- Learn the same 24 tasks from paired [Python and C++ examples](examples/INVENTORY.md).
- C++ examples can start an installed FrameViz runtime on macOS, Linux, or Windows. Both SDKs handle callbacks in the background.
- The [SO-101 demo](examples/python/04_robotics/extra/README.md) downloads its model with progress, reuses the local cache, and runs without MuJoCo. The [Vue slider demo](examples/apps/simple_slider/README.md) starts with one command.

### Fixed

- Browser refresh keeps the active scene and View IDs. Ctrl+C clears the retired scene and controls.
- Camera queries and screenshots agree with the rendered View. Wireframe and object materials survive selection changes.
- View shortcuts, Vue grid and axes, and C++ Viewer readiness now reflect the current state.
- Invalid Gizmo bindings are rejected. Slow LAN viewers and exiting SDK launchers no longer interrupt other active clients.

The 0.5 SDK requires a 0.5 runtime. See [known limits and compatibility](docs/COMPATIBILITY.md) and [examples](examples/README.md).

## 0.5.0rc1 (2026-11-17)

- Apple Silicon preview on [PyPI](https://pypi.org/project/frameviz/0.5.0rc1/). One wheel installs the Python SDK and the signed, notarized FrameViz App. `fv.open()` opens the desktop window.

## 0.4.0 previews

- 2026-11-09 private preview: welcome on the first manual launch only; closing it keeps the Host available, with the guide accessible from Help.
- Python discovers verified installed macOS bundles and starts them in the background without an App-path variable; SDK-owned and manually launched Hosts retain separate lifetimes.
- The 2026-11-09 and 2026-11-08 previews retain package/protocol version 0.4.0. Use the dated preview and checksums, and explicitly reinstall the new Python wheel when upgrading.
- Independent project identity, MIT license, qqfly copyright, and retained third-party notices.
- Source-only distribution manifests, synthetic fixtures, reproducible artwork, and local-prefix installation.
- Authenticated Host/viewers and separate example business-channel credentials.
- Scene-scope validation, atomic batch updates, shared buffer cleanup, and viewer lifecycle restoration.
- Protocol 0.4.0 required across all components; unsupported or omitted command versions fail explicitly.

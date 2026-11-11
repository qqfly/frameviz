# FrameViz external application example

This example uses a Vue UI, a Python or C++ business backend, and FrameViz protocol 0.5.0. It demonstrates a slider-controlled scene. See the root installation guide for source builds and local SDK packages.

## Try the Python browser demo

With source dependencies and the matching Python SDK/App installed, run from the repository root:

```sh
python -m pip install -r examples/apps/simple_slider/python/requirements.txt
pnpm --filter simple-slider-app build
python examples/apps/simple_slider/python/run_browser_demo.py
```

The launcher starts a local HTTP server and Python business backend, opens the real Vue application, and supplies fresh Host/business credentials in the URL fragment. It does not print the session URL or embed credentials in the build. Move X/Y/Z and Z-rotation sliders, then use Reset. Press Enter in the launching terminal to stop the demo's backend/server and close its scene. A manually running FrameViz App remains running.

The UI build must use its default business endpoint `127.0.0.1:9621` (leave `VITE_SIMPLE_SLIDER_BACKEND_WS_URL` unset). If that port is occupied, the launcher stops instead of connecting to an unrelated backend. `--ui-dir` can select a prebuilt UI directory. Use an already running matching Host or the installed App auto-discovery described in [MACOS.md](../../../docs/MACOS.md).

The README recording uses the same app and Python backend. Only recording setup changes: fixed camera, hidden world-origin axes (helper and the demo's drawn axes), white background, a lighter ground plane, and hidden diagnostic handles/footer. Object changes come from real pointer input to the controls. The loop shows positions, rotation and reset; it does not claim new color-picker or C++ application acceptance.

## Manual integration

Set `FRAMEVIZ_BUSINESS_TOKEN` to a random token of at least 32 characters before starting the backend. Supply it to the UI in the URL fragment as `business_token=<value>`. The Host Viewer credential is separate: `#token=<Host session token>&business_token=<business token>`. Do not write either value into source, build output, or persistent logs.

The backend validates a local Origin and the business token before sending state or accepting commands. The token authorizes this local example, including its configured viewer binding; fine-grained remote-user permissions are not implemented. Missing credentials fail closed.

The browser sends the temporary business token in the first WebSocket frame and waits for acknowledgement before binding the Viewer. Existing clients can still use the token subprotocol header.

Use `FRAMEVIZ_PYTHON` to select a Python interpreter, `FRAMEVIZ_HOME` for state, `FRAMEVIZ_RUNTIME_MANIFEST` for an explicit runtime manifest, and `CMAKE_PREFIX_PATH` for the C++ SDK. No internal installation directory is searched. The standalone template's packaged desktop credential injection and complete installer still need target-platform acceptance.

Run `python3 scripts/generate_samples.py` from the project root to reproduce the MIT synthetic data. User-supplied model roots must be explicit; model assets are never inferred from another project.

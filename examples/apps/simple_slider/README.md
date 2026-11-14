# FrameViz external application example

This example uses a Vue UI, a Python or C++ business backend, and FrameViz protocol 0.5.0. It demonstrates a slider-controlled scene. See the root installation guide for source builds and local SDK packages.

## Try the Python browser demo

With Python 3, Node, pnpm and Rust installed, run:

```sh
git clone https://github.com/qqfly/frameviz.git
cd frameviz
bash examples/apps/simple_slider/run-demo.sh
```

The script builds the local SDK, Viewer and standalone Host, then launches the
Vue app using a project-local Python environment and a temporary runtime state.
It assigns free ports and supplies both session credentials directly to the
browser. Move the sliders, then use Reset. Press Enter in the terminal to stop
the demo. A matching prebuilt UI can also be used with
`python examples/apps/simple_slider/python/run_browser_demo.py --ui-dir PATH`.

The README recording uses the same app and Python backend. Only recording setup changes: fixed camera, hidden world-origin axes (helper and the demo's drawn axes), white background, a lighter ground plane, and hidden diagnostic handles/footer. Object changes come from real pointer input to the controls. The loop shows positions, rotation and reset; it does not claim new color-picker or C++ application acceptance.

## Manual integration

Set `FRAMEVIZ_BUSINESS_TOKEN` to a random token of at least 32 characters before starting the backend. Supply it to the UI in the URL fragment as `business_token=<value>`. The Host Viewer credential is separate: `#token=<Host session token>&business_token=<business token>`. Do not write either value into source, build output, or persistent logs.

The backend validates a local Origin and the business token before sending state or accepting commands. The token authorizes this local example, including its configured viewer binding; fine-grained remote-user permissions are not implemented. Missing credentials fail closed.

The browser sends the temporary business token in the first WebSocket frame and waits for acknowledgement before binding the Viewer. Existing clients can still use the token subprotocol header.

Use `FRAMEVIZ_PYTHON` to select a Python interpreter, `FRAMEVIZ_HOME` for state, `FRAMEVIZ_RUNTIME_MANIFEST` for an explicit runtime manifest, and `CMAKE_PREFIX_PATH` for the C++ SDK. No internal installation directory is searched. The standalone template's packaged desktop credential injection and complete installer still need target-platform acceptance.

Run `python3 scripts/generate_samples.py` from the project root to reproduce the MIT synthetic data. User-supplied model roots must be explicit; model assets are never inferred from another project.

## Try the C++ backend in the same browser app

Start a matching local FrameViz Host and prepare the [installed C++ SDK](../../../docs/INSTALLATION.md).
Set a new local business token in the terminal that runs the backend. Build
and serve the Vue application from the repository root.

```sh
pnpm --filter @frameviz/vue build
pnpm -C examples/apps/simple_slider dev --host 127.0.0.1
```

In a second terminal:

```sh
export FRAMEVIZ_BUSINESS_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
CMAKE_PREFIX_PATH="$PWD/.local/sdk" pnpm -C examples/apps/simple_slider backend:cpp:build
pnpm -C examples/apps/simple_slider backend:cpp
```

Open the address printed by Vite with `?ws_port=<Host port>#token=<Host token>&business_token=<business token>`.
Use the active Host's local discovery record and the token from the backend
terminal. Drag X/Y/Z, rotate, then use Reset. Stop both terminals with Ctrl+C.

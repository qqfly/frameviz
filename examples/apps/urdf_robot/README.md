# FrameViz external application example

This example uses a Vue UI, a Python or C++ business backend, and FrameViz protocol 0.5.0. It demonstrates a synthetic six-axis fixture. See the root installation guide for source builds and local SDK packages.

Set `FRAMEVIZ_BUSINESS_TOKEN` to a random token of at least 32 characters before starting the backend. Supply it to the UI in the URL fragment as `business_token=<value>`. The Host Viewer credential is separate: `#token=<Host session token>&business_token=<business token>`. Do not write either value into source, build output, or persistent logs.

The backend validates a local Origin and the business token before sending state or accepting commands. The token authorizes this local example, including its configured viewer binding; fine-grained remote-user permissions are not implemented. Missing credentials fail closed.

The Python business service selects `frameviz-business` from the browser's offered WebSocket protocols. Clients supply the separate credential as `token.<business token>`; that credential is not echoed as the selected protocol.

Use `FRAMEVIZ_PYTHON` to select a Python interpreter, `FRAMEVIZ_HOME` for state, `FRAMEVIZ_RUNTIME_MANIFEST` for an explicit runtime manifest, and `CMAKE_PREFIX_PATH` for the C++ SDK. No internal installation directory is searched. The standalone template's packaged desktop credential injection and complete installer still need target-platform acceptance.

Run `python3 scripts/generate_samples.py` from the project root to reproduce the MIT synthetic data. User-supplied model roots must be explicit; model assets are never inferred from another project.

## Run the synthetic model with either backend

Start a compatible local FrameViz Host and run these commands from the
repository root. Both backends use the same `data/models/sample_robot` folder.

```sh
pnpm --filter @frameviz/vue build
pnpm -C examples/apps/urdf_robot dev --host 127.0.0.1
```

In a second terminal, create a local business token and run one backend.

```sh
export FRAMEVIZ_BUSINESS_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export URDF_MODEL_PATH="$PWD/data/models/sample_robot"

# Python route, from the virtual environment with the matching SDK
python -m pip install -r examples/apps/urdf_robot/python/requirements.txt
pnpm -C examples/apps/urdf_robot backend:py

# C++ route, after installing the SDK to .local/sdk
CMAKE_PREFIX_PATH="$PWD/.local/sdk" pnpm -C examples/apps/urdf_robot backend:cpp:build
pnpm -C examples/apps/urdf_robot backend:cpp
```

Open the Vite address with `?ws_port=<Host port>#token=<Host token>&business_token=<business token>`.
Adjust a joint and check both Visual and Collision. Use Home to return to the
starting pose. Stop the backend and Vite with Ctrl+C.

# FrameViz external application example

This example uses a Vue UI, a Python or C++ business backend, and FrameViz protocol 0.4.0. It demonstrates a synthetic six-axis fixture. See the root installation guide for source builds and local SDK packages.

Set `FRAMEVIZ_BUSINESS_TOKEN` to a random token of at least 32 characters before starting the backend. Supply it to the UI in the URL fragment as `business_token=<value>`. The Host Viewer credential is separate: `#token=<Host session token>&business_token=<business token>`. Do not write either value into source, build output, or persistent logs.

The backend validates a local Origin and the business token before sending state or accepting commands. The token authorizes this local example, including its configured viewer binding; fine-grained remote-user permissions are not implemented. Missing credentials fail closed.

The Python business service selects `frameviz-business` from the browser's offered WebSocket protocols. Clients supply the separate credential as `token.<business token>`; that credential is not echoed as the selected protocol.

Use `FRAMEVIZ_PYTHON` to select a Python interpreter, `FRAMEVIZ_HOME` for state, `FRAMEVIZ_RUNTIME_MANIFEST` for an explicit runtime manifest, and `CMAKE_PREFIX_PATH` for the C++ SDK. No internal installation directory is searched. The standalone template's packaged desktop credential injection and complete installer still need target-platform acceptance.

Run `python3 scripts/generate_samples.py` from the project root to reproduce the MIT synthetic data. User-supplied model roots must be explicit; model assets are never inferred from another project.

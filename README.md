# FrameViz

FrameViz is a local 3D visualization toolkit for Python, C++, and Vue applications. A Rust Host owns scene state; a Three.js viewer renders geometry, point clouds, instances, and loaded models. SDKs provide camera, picking, transform, and lifecycle operations.

Version: `0.4.0` (unreleased). First-party copyright: **qqfly**. License: [MIT](LICENSE). Third-party notices remain in [NOTICE](NOTICE) and [THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES).

Private source repository: [qqfly/frameviz](https://github.com/qqfly/frameviz). Apple Silicon installation and signing details are in the [macOS preview guide](docs/MACOS.md).

## Build from source

Use Node.js 20 or newer, pnpm 10, Python 3.9 or newer, Rust, CMake, and a C++17 compiler. Dependency installation requires network access unless your package caches are complete. There are no assumed system-wide FrameViz installations.

```sh
pnpm install --frozen-lockfile
python3 -m venv .venv
.venv/bin/python -m pip install -e 'packages/frameviz-py[dev]' build playwright websockets
node scripts/prepare_web_viewer_dist.mjs
pnpm --filter @frameviz/vue build
cargo build --locked --manifest-path packages/frameviz-server/Cargo.toml
```

On Windows, use the virtual environment's `Scripts/python.exe` in place of `.venv/bin/python`.

## Try a local scene

```sh
.venv/bin/python tests/acceptance/demo.py \
  --vue-dist packages/frameviz-vue/dist-acceptance
```

The demo starts an isolated Host and browser page. It uses synthetic geometry, prints local connection URLs, and stops with Ctrl+C. To include Vue, first build its acceptance page:

```sh
pnpm --filter @frameviz/vue exec vite build --config vite.acceptance.config.mjs
```

For normal application development, start `cargo run --manifest-path packages/frameviz-server/Cargo.toml -- 9527` and use the Python or C++ SDK. The Host binds loopback, writes a per-user discovery record, and requires a session token. An explicitly configured SDK endpoint receives a discovery token only when it matches that record.

## Python

```python
from frameviz.client import FrameVizClient
from frameviz.viz import Viz

client = FrameVizClient('ws://127.0.0.1:9527')
client.connect()
state = client.send_command('create_view', {'title': 'Example'})
viz = Viz(client, state['scene_id'], state['view_id'])
box = viz.add_box(color=(0.2, 0.7, 0.4))
viz.set_transform(box, pos=(1, 0, 0))
# Open a viewer using the SDK or the authenticated demo workflow.
# When finished: viz.close(); client.close()
```

[C++ setup](packages/frameviz-cpp/README.md), [Vue embedding](packages/frameviz-vue/README.md), and the [external application template](templates/frameviz-template-external-app/README.md) describe their own entry points. Local package tarballs and wheels are the supported delivery path until a public registry release is approved; no package-name availability is assumed.

## Scope and support

All Host, SDK, viewer, and template components in a deployment must use protocol `0.4.0`. Missing or different command versions are rejected. This is an explicit compatibility boundary, not a promise of interoperability with older installations.

The current acceptance target is local single-user use. Remote multi-user authorization, shared-memory upload, persistence across Host restart, production performance limits, and signed cross-platform installers are not covered by this release candidate. Software-rendered browser checks are not hardware GPU benchmarks. The six-axis example and point cloud are generated fixtures, not measurements or manufacturer models.

See [architecture](docs/ARCHITECTURE.md), [API contract](docs/API_Definition.md), [compatibility](docs/COMPATIBILITY.md), [validation](docs/VALIDATION.md), [installation](docs/INSTALLATION.md), and [release checks](docs/RELEASING.md). Use [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) for contributions and security reporting.

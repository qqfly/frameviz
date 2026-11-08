# FrameViz Web Viewer

Build reachable runtime assets with `node scripts/prepare_web_viewer_dist.mjs` from the project root. Serve only its dist directory with `node packages/frameviz-web-viewer/serve.mjs`; the service binds loopback and rejects hidden files and paths escaping dist.

Use `tests/acceptance/demo.py` for an authenticated local bootstrap. Opening raw repository files or serving the whole repository is not a supported deployment. The viewer connects to the Rust Host, requires its session token, and must use the matching 0.4.0 protocol.

The old unauthenticated JavaScript relay entry point fails closed. It is not a second Host implementation. See the root README for Python/C++, Vue, model loading, and local application setup.

# FrameViz Host

This Rust crate implements the authenticated, loopback scene Host and can be used as a standalone server or embedded by the native shell. It owns scenes/views, immutable referenced buffers, state mutations, versioned routing, and process-local snapshots.

Build with `cargo build --locked --manifest-path packages/frameviz-server/Cargo.toml`. Use explicit discovery/log paths in tests. Default state belongs to the qqfly FrameViz namespace; no previous installation records are migrated or cleaned automatically. See root compatibility and API documents for supported operations and resource limits.

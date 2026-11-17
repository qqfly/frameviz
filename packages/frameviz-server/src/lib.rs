//! FrameViz WebSocket Server Library
//!
//! This crate provides the WebSocket server functionality for FrameViz,
//! allowing it to be embedded in Tauri applications or other Rust projects.
//!
//! # Example
//!
//! ```rust,no_run
//! use frameviz_server::FrameVizServer;
//!
//! #[tokio::main]
//! async fn main() {
//!     FrameVizServer::new().run().await.expect("Failed to start server");
//! }
//! ```

mod host;
mod widgets;
mod registry;
pub mod version;
mod server;
pub mod websocket;
pub mod handlers;
pub mod http_server;

pub use host::{Host, HostError, LogEntry, SceneSnapshot};
pub use registry::{RegisteredViewer, ViewerRegistry};
pub use server::{FrameVizServer, ServerConfig, ServerHandle};
pub use websocket::{
    build_diagnostics,
    cleanup_stale_discovery,
    discovery_port_if_running,
    run_server,
    select_available_port_avoiding,
    update_discovery_http_port,
    PROTOCOL_VERSION,
    ServerDiagnostics,
};
pub use http_server::{start_http_server, start_http_server_at, select_http_port, HttpServerConfig};

/// Start a FrameViz server on the specified port (background task).
pub fn start(port: u16) -> ServerHandle {
    FrameVizServer::with_config(ServerConfig {
        port,
        ..Default::default()
    })
    .start()
}

/// Start a FrameViz server with custom configuration (background task).
pub fn start_with_config(config: ServerConfig) -> ServerHandle {
    FrameVizServer::with_config(config).start()
}

//! FrameViz WebSocket Server facade.

use tokio::sync::watch;
use tokio::task::JoinHandle;

use crate::websocket::{build_diagnostics, run_server};

/// Server configuration options.
#[derive(Clone, Debug)]
pub struct ServerConfig {
    /// Port to listen on.
    pub port: u16,
    /// Enable logging (reserved for future use).
    pub enable_logging: bool,
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            port: 9527,
            enable_logging: true,
        }
    }
}

/// FrameViz WebSocket server entry point.
pub struct FrameVizServer {
    config: ServerConfig,
}

/// Handle for a running server.
pub struct ServerHandle {
    shutdown_tx: watch::Sender<bool>,
    task: JoinHandle<()>,
}

impl FrameVizServer {
    /// Create a new server with default configuration.
    pub fn new() -> Self {
        Self::with_config(ServerConfig::default())
    }

    /// Create a new server with custom configuration.
    pub fn with_config(config: ServerConfig) -> Self {
        Self { config }
    }

    /// Run the server in the current task (blocks until shutdown).
    pub async fn run(self) -> Result<(), std::io::Error> {
        let (shutdown_tx, shutdown_rx) = watch::channel(false);
        let diagnostics = build_diagnostics(self.config.port);
        let port = self.config.port;
        let _ = shutdown_tx;
        run_server(port, diagnostics, shutdown_rx)
            .await
            .map_err(|err| std::io::Error::new(std::io::ErrorKind::Other, err.to_string()))
    }

    /// Start the server in the background and return a handle for shutdown.
    pub fn start(self) -> ServerHandle {
        let (shutdown_tx, shutdown_rx) = watch::channel(false);
        let diagnostics = build_diagnostics(self.config.port);
        let port = self.config.port;
        let task = tokio::spawn(async move {
            if let Err(err) = run_server(port, diagnostics, shutdown_rx).await {
                eprintln!("[FrameViz] Server error: {}", err);
            }
        });
        ServerHandle { shutdown_tx, task }
    }

    /// Return configured port.
    pub fn port(&self) -> u16 {
        self.config.port
    }
}

impl Default for FrameVizServer {
    fn default() -> Self {
        Self::new()
    }
}

impl ServerHandle {
    /// Stop the running server and wait for shutdown.
    pub async fn stop(self) {
        let _ = self.shutdown_tx.send(true);
        let _ = self.task.await;
    }
}

use frameviz_server::{FrameVizServer, ServerConfig};
use std::env;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let port = env::args()
        .nth(1)
        .and_then(|p| p.parse().ok())
        .unwrap_or(9527);

    let config = ServerConfig {
        port,
        enable_logging: true,
    };

    println!("[FrameViz] Starting Standalone Host Server...");
    let server = FrameVizServer::with_config(config);
    let server_port = server.port();
    let handle = server.start();

    println!("[FrameViz] Server listening on ws://127.0.0.1:{}", server_port);
    println!("[FrameViz] Press Ctrl+C to stop");

    tokio::signal::ctrl_c().await?;
    println!("[FrameViz] Shutting down...");
    handle.stop().await;

    Ok(())
}

use frameviz_server::{build_diagnostics, start_http_server, HttpServerConfig};
use frameviz_server::websocket::run_server_on_listener;
use include_dir::{include_dir, Dir};
use std::env;
use tokio::sync::watch;

// Only the standalone binary embeds these assets; library/Tauri consumers keep
// their existing asset and window setup. Prepare the Viewer before cargo build.
static VIEWER: Dir = include_dir!("$CARGO_MANIFEST_DIR/../frameviz-web-viewer/dist");

fn ports(args: impl Iterator<Item = String>) -> Result<Option<(u16, u16)>, String> {
    let mut args = args.peekable();
    let (mut ws_port, mut http_port) = (9527, 0);
    let mut positional = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--help" | "-h" => return Ok(None),
            "--headless" => {} // Already headless; accepts the common SDK launcher option.
            "--ws-port" | "--http-port" => {
                let value: u16 = args.next().ok_or_else(|| format!("{arg} needs a port"))?
                    .parse().map_err(|_| format!("Invalid port for {arg}"))?;
                if arg == "--ws-port" { ws_port = value; } else { http_port = value; }
            }
            _ if !arg.starts_with('-') && !positional => {
                ws_port = arg.parse().map_err(|_| format!("Invalid WebSocket port: {arg}"))?;
                positional = true;
            }
            _ => return Err(format!("Unknown argument: {arg}")),
        }
    }
    if ws_port == 0 { return Err("WebSocket port must be between 1 and 65535".into()); }
    Ok(Some((ws_port, http_port)))
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let Some((ws_port, http_port)) = ports(env::args().skip(1))? else {
        println!("Usage: frameviz-server [WS_PORT] [--ws-port PORT] [--http-port PORT] [--headless]");
        println!("Loopback only. HTTP port 0 selects a free port. Prints a private authenticated Viewer URL.");
        return Ok(());
    };
    println!("[FrameViz] Starting Standalone Host Server...");
    let (shutdown_tx, shutdown_rx) = watch::channel(false);
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", ws_port)).await?;
    let actual_http_port = start_http_server(HttpServerConfig {
        port: http_port,
        assets_dir: None,
        embedded_assets: Some(&VIEWER),
    }, shutdown_rx.clone()).await.map_err(|err| err.to_string())?;
    let server = run_server_on_listener(listener, build_diagnostics(ws_port).with_http_port(actual_http_port), shutdown_rx);
    tokio::pin!(server);
    println!("[FrameViz] Press Ctrl+C to stop");
    tokio::select! {
        result = &mut server => result?,
        signal = tokio::signal::ctrl_c() => {
            signal?;
            println!("[FrameViz] Shutting down...");
            let _ = shutdown_tx.send(true);
            server.await?;
        }
    }
    Ok(())
}

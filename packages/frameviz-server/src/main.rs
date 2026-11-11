use frameviz_server::{build_diagnostics, start_http_server, start_http_server_at, HttpServerConfig};
use frameviz_server::websocket::{run_server_with_lan, LanViewerEndpoint};
use include_dir::{include_dir, Dir};
use std::env;
use tokio::sync::watch;

// Only the standalone binary embeds these assets; library/Tauri consumers keep
// their existing asset and window setup. Prepare the Viewer before cargo build.
static VIEWER: Dir = include_dir!("$CARGO_MANIFEST_DIR/../frameviz-web-viewer/dist");

struct Options {
    ws_port: u16,
    http_port: u16,
    lan_address: Option<std::net::IpAddr>,
    lan_ws_port: u16,
    lan_http_port: u16,
}

fn options(args: impl Iterator<Item = String>) -> Result<Option<Options>, String> {
    let mut args = args.peekable();
    let mut options = Options {
        ws_port: 9527, http_port: 0, lan_address: None, lan_ws_port: 0, lan_http_port: 0,
    };
    let mut positional = false;
    let mut lan_port_requested = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--help" | "-h" => return Ok(None),
            "--headless" => {}
            "--lan-address" => {
                let value: std::net::IpAddr = args.next().ok_or("--lan-address needs an IP address")?
                    .parse().map_err(|_| "Invalid --lan-address IP")?;
                if value.is_unspecified() || value.is_multicast() {
                    return Err("--lan-address must name a specific local interface address".into());
                }
                options.lan_address = Some(value);
            }
            "--ws-port" | "--http-port" | "--lan-ws-port" | "--lan-http-port" => {
                let value: u16 = args.next().ok_or_else(|| format!("{arg} needs a port"))?
                    .parse().map_err(|_| format!("Invalid port for {arg}"))?;
                match arg.as_str() {
                    "--ws-port" => options.ws_port = value,
                    "--http-port" => options.http_port = value,
                    "--lan-ws-port" => { options.lan_ws_port = value; lan_port_requested = true; }
                    _ => { options.lan_http_port = value; lan_port_requested = true; }
                }
            }
            _ if !arg.starts_with('-') && !positional => {
                options.ws_port = arg.parse().map_err(|_| format!("Invalid WebSocket port: {arg}"))?;
                positional = true;
            }
            _ => return Err(format!("Unknown argument: {arg}")),
        }
    }
    if options.ws_port == 0 { return Err("WebSocket port must be between 1 and 65535".into()); }
    if lan_port_requested && options.lan_address.is_none() {
        return Err("LAN ports require --lan-address".into());
    }
    Ok(Some(options))
}

async fn termination_signal() -> std::io::Result<()> {
    #[cfg(unix)] {
        use tokio::signal::unix::{signal,SignalKind};
        let mut terminate=signal(SignalKind::terminate())?;
        tokio::select! {
            _=terminate.recv()=>Ok(()),
            result=tokio::signal::ctrl_c()=>result,
        }
    }
    #[cfg(not(unix))] { tokio::signal::ctrl_c().await }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().skip(1).collect();
    if matches!(args.as_slice(), [argument] if matches!(argument.as_str(), "--version" | "-V")) {
        println!("FrameViz Host v{}", env!("CARGO_PKG_VERSION"));
        return Ok(());
    }
    let Some(options) = options(args.into_iter())? else {
        println!("Usage: frameviz-server [WS_PORT] [--ws-port PORT] [--http-port PORT] [--headless]");
        println!("Loopback by default. HTTP port 0 selects a free port.");
        println!("Opt in to read-only viewing with --lan-address IP [--lan-ws-port PORT] [--lan-http-port PORT].");
        return Ok(());
    };
    println!("[FrameViz] Starting Standalone Host Server...");
    let (shutdown_tx, shutdown_rx) = watch::channel(false);
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", options.ws_port)).await?;
    let actual_http_port = start_http_server(HttpServerConfig {
        port: options.http_port,
        assets_dir: None,
        embedded_assets: Some(&VIEWER),
    }, shutdown_rx.clone()).await.map_err(|err| err.to_string())?;
    let lan = if let Some(address) = options.lan_address {
        let listener = tokio::net::TcpListener::bind((address, options.lan_ws_port)).await?;
        let http = start_http_server_at(address, HttpServerConfig {
            port: options.lan_http_port, assets_dir: None, embedded_assets: Some(&VIEWER),
        }, shutdown_rx.clone()).await.map_err(|err| err.to_string())?;
        let origin = format!("http://{}", std::net::SocketAddr::new(address, http));
        Some(LanViewerEndpoint { listener, http_origin: origin })
    } else {
        None
    };
    let server = run_server_with_lan(listener, build_diagnostics(options.ws_port).with_http_port(actual_http_port), shutdown_rx, lan);
    tokio::pin!(server);
    println!("[FrameViz] Press Ctrl+C to stop");
    tokio::select! {
        result = &mut server => result?,
        signal = termination_signal() => {
            signal?;
            println!("[FrameViz] Shutting down...");
            let _ = shutdown_tx.send(true);
            server.await?;
        }
    }
    Ok(())
}

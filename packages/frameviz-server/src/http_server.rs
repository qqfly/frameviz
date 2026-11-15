//! HTTP Static File Server for FrameViz
//!
//! Serves the web viewer frontend assets for browser mode (window_mode=1).
//! This allows Python SDK to open the viewer in a standalone browser.

use http_body_util::Full;
use hyper::body::Bytes;
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Request, Response, StatusCode};
use hyper_util::rt::TokioIo;
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::net::TcpListener;
use tokio::sync::watch;

/// Configuration for the HTTP server
pub struct HttpServerConfig {
    /// Port to listen on (0 for auto-select)
    pub port: u16,
    /// Directory containing web viewer assets
    pub assets_dir: Option<PathBuf>,
    /// Embedded assets (for release builds)
    pub embedded_assets: Option<&'static include_dir::Dir<'static>>,
}

impl Default for HttpServerConfig {
    fn default() -> Self {
        Self {
            port: 0,
            assets_dir: None,
            embedded_assets: None,
        }
    }
}

/// Shared state for the HTTP server
struct ServerState {
    assets_dir: Option<PathBuf>,
    embedded_assets: Option<&'static include_dir::Dir<'static>>,
}

/// Start the HTTP static file server
///
/// Returns the actual port the server is listening on.
pub async fn start_http_server(
    config: HttpServerConfig,
    shutdown_rx: watch::Receiver<bool>,
) -> Result<u16, Box<dyn std::error::Error + Send + Sync>> {
    start_http_server_at([127, 0, 0, 1].into(), config, shutdown_rx).await
}

pub async fn start_http_server_at(
    address: std::net::IpAddr,
    config: HttpServerConfig,
    mut shutdown_rx: watch::Receiver<bool>,
) -> Result<u16, Box<dyn std::error::Error + Send + Sync>> {
    let addr = SocketAddr::new(address, config.port);
    let listener = TcpListener::bind(addr).await?;
    let actual_port = listener.local_addr()?.port();

    println!("[HTTP] Static file server listening on http://{}", listener.local_addr()?);

    let state = Arc::new(ServerState {
        assets_dir: config.assets_dir,
        embedded_assets: config.embedded_assets,
    });

    tokio::spawn(async move {
        loop {
            tokio::select! {
                _ = shutdown_rx.changed() => {
                    if *shutdown_rx.borrow() {
                        println!("[HTTP] Shutting down static file server");
                        break;
                    }
                }
                accept_result = listener.accept() => {
                    match accept_result {
                        Ok((stream, _)) => {
                            let state = state.clone();
                            tokio::spawn(async move {
                                let io = TokioIo::new(stream);
                                let service = service_fn(move |req| {
                                    let state = state.clone();
                                    async move { handle_request(req, state).await }
                                });
                                if let Err(e) = http1::Builder::new()
                                    .serve_connection(io, service)
                                    .await
                                {
                                    // Only log non-connection-reset errors
                                    let err_str = e.to_string();
                                    if !err_str.contains("connection reset") && !err_str.contains("broken pipe") {
                                        eprintln!("[HTTP] Connection error: {}", e);
                                    }
                                }
                            });
                        }
                        Err(e) => {
                            eprintln!("[HTTP] Accept error: {}", e);
                        }
                    }
                }
            }
        }
    });

    Ok(actual_port)
}

/// Handle an HTTP request
async fn handle_request(
    req: Request<hyper::body::Incoming>,
    state: Arc<ServerState>,
) -> Result<Response<Full<Bytes>>, hyper::Error> {
    let path = req.uri().path();

    // Normalize path
    let path = if path == "/" { "/index.html" } else { path };
    let path = path.trim_start_matches('/');

    if path.split('/').any(|part| part.starts_with('.')) {
        return Ok(Response::builder().status(StatusCode::NOT_FOUND)
            .body(Full::new(Bytes::new())).unwrap());
    }

    // Try to serve from assets directory first
    if let Some(assets_dir) = &state.assets_dir {
        let file_path = assets_dir.join(path);
        if file_path.exists() && file_path.is_file() {
            // Security: ensure path is within assets_dir
            if let Ok(canonical) = file_path.canonicalize() {
                if let Ok(assets_canonical) = assets_dir.canonicalize() {
                    if canonical.starts_with(&assets_canonical) {
                        if let Ok(content) = tokio::fs::read(&canonical).await {
                            let mime = mime_guess::from_path(&canonical)
                                .first_or_octet_stream()
                                .to_string();
                            return Ok(Response::builder()
                                .status(StatusCode::OK)
                                .header("Content-Type", mime)
                                .header("Cache-Control", "no-cache")
                                .body(Full::new(Bytes::from(content)))
                                .unwrap());
                        }
                    }
                }
            }
        }
    }

    // Try embedded assets
    if let Some(embedded) = &state.embedded_assets {
        if let Some(file) = embedded.get_file(path) {
            let mime = mime_guess::from_path(path)
                .first_or_octet_stream()
                .to_string();
            return Ok(Response::builder()
                .status(StatusCode::OK)
                .header("Content-Type", mime)
                .header("Cache-Control", "no-cache")
                .body(Full::new(Bytes::from(file.contents())))
                .unwrap());
        }
    }

    // 404 Not Found
    Ok(Response::builder()
        .status(StatusCode::NOT_FOUND)
        .header("Content-Type", "text/plain")
        .body(Full::new(Bytes::from("404 Not Found")))
        .unwrap())
}

/// Select an available port, avoiding specified ports
pub fn select_http_port(preferred: u16, avoid: &[u16]) -> Option<u16> {
    use std::net::TcpListener as StdTcpListener;

    for offset in 0..20u16 {
        let port = preferred.saturating_add(offset);
        if avoid.contains(&port) {
            continue;
        }
        if StdTcpListener::bind(("127.0.0.1", port)).is_ok() {
            return Some(port);
        }
    }
    None
}

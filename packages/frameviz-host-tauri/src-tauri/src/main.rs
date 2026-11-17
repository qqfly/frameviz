//! FrameViz Tauri Application
//!
//! This is a minimal Tauri shell that hosts the FrameViz web viewer
//! and provides a native window experience with integrated WebSocket server.

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use std::path::PathBuf;
use std::sync::mpsc;
use std::thread;
use std::time::Duration;
use tauri::Manager;
use tokio::sync::watch;
use include_dir::{include_dir, Dir};

mod control;
mod startup;
use frameviz_server::websocket;
use frameviz_server::{HttpServerConfig, cleanup_stale_discovery, update_discovery_http_port};

// Embed web viewer assets for release builds
static EMBEDDED_ASSETS: Dir = include_dir!("$CARGO_MANIFEST_DIR/../../../packages/frameviz-web-viewer/dist");

const DEFAULT_HTTP_PORT: u16 = 8080;

/// Update discovery file with development server URL
#[cfg(debug_assertions)]
fn update_discovery_with_dev_url(viewer_url: &str, port: u16) -> Result<(), String> {
    let path = websocket::resolve_discovery_path().ok_or("no discovery path")?;
    if !path.exists() {
        return Err("discovery file does not exist".to_string());
    }

    let text = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let mut data: serde_json::Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;

    if data.get("pid").and_then(serde_json::Value::as_u64) != Some(std::process::id() as u64) {
        return Err("discovery file belongs to another process".into());
    }
    // Set dev server URL
    data["http_port"] = serde_json::json!(port);
    data["viewer_url"] = serde_json::json!(viewer_url);

    std::fs::write(&path, data.to_string()).map_err(|e| e.to_string())?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let perms = std::fs::Permissions::from_mode(0o600);
        std::fs::set_permissions(&path, perms).map_err(|e| e.to_string())?;
    }
    println!("[FrameViz] Updated discovery file with dev server URL");
    Ok(())
}

// State to share WebSocket and HTTP server handles
pub struct AppState {
    ws_port: u16,
    #[allow(dead_code)]
    http_port: u16,
    #[allow(dead_code)]
    ws_enabled: bool,
    view_id: Option<String>,
    ws_shutdown_tx: Option<watch::Sender<bool>>,
    http_shutdown_tx: Option<watch::Sender<bool>>,
}

impl AppState {
    pub fn view_id(&self) -> Option<String> {
        self.view_id.clone()
    }
}

impl Drop for AppState {
    fn drop(&mut self) {
        println!("[FrameViz] AppState dropping, cleaning up...");
        if let Some(tx) = self.ws_shutdown_tx.take() {
            let _ = tx.send(true);
        }
        if let Some(tx) = self.http_shutdown_tx.take() {
            let _ = tx.send(true);
        }
    }
}

/// Start the WebSocket server in a background thread
fn start_websocket_server(
    control_port: u16,
    preferred_port: u16,
    managed_exit: mpsc::Sender<()>,
) -> (u16, bool, Option<watch::Sender<bool>>) {
    let enabled = std::env::var("FRAMEVIZ_USE_RUST_WS")
        .map(|v| !(v == "0" || v.eq_ignore_ascii_case("false")))
        .unwrap_or(true);

    if !enabled {
        return (preferred_port, false, None);
    }

    // Clean up stale discovery file before checking for running instances
    cleanup_stale_discovery();

    if let Some(port) = websocket::discovery_port_if_running() {
        println!(
            "[FrameViz] Detected existing WS host on port {}; reuse without starting another host",
            port
        );
        return (port, false, None);
    }

    let avoid_ports = [control_port];
    let port = websocket::select_available_port_avoiding(preferred_port, 20, &avoid_ports)
        .unwrap_or_else(|| {
            if preferred_port == control_port {
                preferred_port.saturating_add(1)
            } else {
                preferred_port
            }
        });
    if port != preferred_port {
        println!(
            "[FrameViz] Port {} is in use; using fallback port {}",
            preferred_port, port
        );
    }

    let (shutdown_tx, shutdown_rx) = watch::channel(false);
    let restart_port = port;
    let owner_release = websocket::sdk_owner_release();

    thread::spawn(move || {
        loop {
            // Check shutdown before starting
            if *shutdown_rx.borrow() {
                println!("[FrameViz] WebSocket server shutdown requested (before start)");
                break;
            }

            let diagnostics = websocket::build_diagnostics(restart_port)
                .with_owner_release(owner_release.clone());
            let shutdown_local = shutdown_rx.clone();
            let shutdown_check = shutdown_rx.clone();

            let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(move || {
                let rt = tokio::runtime::Runtime::new().unwrap();
                rt.block_on(async {
                    match websocket::run_server(restart_port, diagnostics, shutdown_local).await {
                        Ok(()) => true,
                        Err(e) => {
                            eprintln!("[FrameViz] WebSocket server error: {:?}", e);
                            false
                        }
                    }
                })
            }));

            // Check shutdown after server exits - if true, we should exit cleanly
            if *shutdown_check.borrow() {
                println!("[FrameViz] WebSocket server shutdown completed");
                break;
            }

            if matches!(result, Ok(true)) && owner_release.as_ref().is_some_and(|release| *release.borrow()) {
                let _ = managed_exit.send(());
                break;
            }

            // Only restart if it was an unexpected exit
            if result.is_err() {
                eprintln!("[FrameViz] WebSocket server panicked; restarting in 500ms...");
            } else {
                // Server exited normally but not due to shutdown - this might be an error
                eprintln!("[FrameViz] WebSocket server stopped unexpectedly; restarting in 500ms...");
            }

            // Wait before restart, but check for shutdown during the wait
            for _ in 0..5 {
                thread::sleep(Duration::from_millis(100));
                if *shutdown_rx.borrow() {
                    println!("[FrameViz] WebSocket server shutdown requested during restart delay");
                    break;
                }
            }
        }
        println!("[FrameViz] WebSocket server thread exiting");
    });

    (port, true, Some(shutdown_tx))
}

/// Start the HTTP static file server for browser mode support
fn start_http_server(
    ws_port: u16,
    control_port: u16,
    preferred_port: u16,
) -> (u16, Option<watch::Sender<bool>>) {
    // Check if HTTP server is disabled
    let enabled = std::env::var("FRAMEVIZ_HTTP_SERVER")
        .map(|v| !(v == "0" || v.eq_ignore_ascii_case("false")))
        .unwrap_or(true);

    if !enabled {
        println!("[FrameViz] HTTP server disabled via FRAMEVIZ_HTTP_SERVER=0");
        return (0, None);
    }

    // A busy port is not proof of a trusted development server.
    #[cfg(debug_assertions)]
    if let Ok(value) = std::env::var("FRAMEVIZ_DEV_SERVER_URL") {
        let parsed = tauri::Url::parse(&value).ok().filter(|url|
            url.scheme() == "http" && matches!(url.host_str(), Some("localhost" | "127.0.0.1" | "[::1]"))
            && url.username().is_empty() && url.password().is_none() && url.query().is_none() && url.fragment().is_none());
        if let Some(url) = parsed {
            let port = url.port_or_known_default().unwrap_or(80);
            thread::spawn(move || {
                for _ in 0..10 {
                    match update_discovery_with_dev_url(url.as_str(), port) {
                        Ok(_) => break,
                        Err(_) => thread::sleep(Duration::from_millis(100)),
                    }
                }
            });
            return (0, None);
        }
        eprintln!("[FrameViz] Invalid FRAMEVIZ_DEV_SERVER_URL; using isolated built-in server");
    }

    let avoid_ports = [ws_port, control_port];
    let port = frameviz_server::select_http_port(preferred_port, &avoid_ports)
        .unwrap_or(preferred_port);

    if port != preferred_port {
        println!(
            "[FrameViz] HTTP port {} is in use; using fallback port {}",
            preferred_port, port
        );
    }

    let (shutdown_tx, shutdown_rx) = watch::channel(false);
    let http_port = port;

    // Get assets directory path for development mode
    let assets_dir: Option<PathBuf> = if cfg!(debug_assertions) {
        // In debug mode, try to use the actual dist directory
        std::env::current_exe()
            .ok()
            .and_then(|exe| exe.parent().map(|p| p.to_path_buf()))
            .and_then(|dir| {
                // Try to find the dist directory relative to the executable
                // target/debug/frameviz -> need to go up to repo root
                let candidates = [
                    // For cargo run from src-tauri: target/debug -> src-tauri -> repo root
                    dir.join("../../packages/frameviz-web-viewer/dist"),
                    dir.join("../../../packages/frameviz-web-viewer/dist"),
                    dir.join("../../../../packages/frameviz-web-viewer/dist"),
                    dir.join("../../../../../packages/frameviz-web-viewer/dist"),
                ];
                for candidate in &candidates {
                    if let Ok(canonical) = candidate.canonicalize() {
                        if canonical.exists() {
                            println!("[FrameViz] HTTP assets directory: {:?}", canonical);
                            return Some(canonical);
                        }
                    }
                }
                None
            })
    } else {
        None
    };

    thread::spawn(move || {
        let rt = match tokio::runtime::Runtime::new() {
            Ok(rt) => rt,
            Err(e) => {
                eprintln!("[FrameViz] Failed to create HTTP runtime: {:?}", e);
                return;
            }
        };

        rt.block_on(async {
            let config = HttpServerConfig {
                port: http_port,
                assets_dir,
                embedded_assets: Some(&EMBEDDED_ASSETS),
            };

            match frameviz_server::start_http_server(config, shutdown_rx.clone()).await {
                Ok(actual_port) => {
                    println!("[FrameViz] HTTP server started on port {}", actual_port);
                    // Update discovery file with HTTP port (with retry)
                    let mut retries = 0;
                    while retries < 10 {
                        match update_discovery_http_port(actual_port) {
                            Ok(_) => break,
                            Err(e) => {
                                if retries == 0 {
                                    // First retry - wait a bit for discovery file to be created
                                    tokio::time::sleep(Duration::from_millis(100)).await;
                                } else if retries < 9 {
                                    tokio::time::sleep(Duration::from_millis(50)).await;
                                } else {
                                    eprintln!("[FrameViz] Failed to update discovery with HTTP port after retries: {}", e);
                                }
                                retries += 1;
                            }
                        }
                    }
                }
                Err(e) => {
                    eprintln!("[FrameViz] Failed to start HTTP server: {:?}", e);
                    return;
                }
            }

            // Keep the runtime alive until shutdown
            let mut shutdown_rx_local = shutdown_rx;
            loop {
                tokio::select! {
                    _ = shutdown_rx_local.changed() => {
                        if *shutdown_rx_local.borrow() {
                            println!("[FrameViz] HTTP server thread shutting down");
                            break;
                        }
                    }
                    _ = tokio::time::sleep(Duration::from_secs(1)) => {
                        // Continue loop
                    }
                }
            }
        });
    });

    (port, Some(shutdown_tx))
}

fn parse_view_id() -> Option<String> {
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == "--view-id" || arg == "--view_id" {
            return args.next();
        }
    }
    None
}

struct ParsedArgs {
    ws_port: u16,
    headless: bool,
    show_version: bool,
}

fn parse_args() -> ParsedArgs {
    let mut ws_port = 9527;
    let mut headless = false;
    let mut show_version = false;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--ws-port" => {
                if let Some(value) = args.next() {
                    if let Ok(parsed) = value.parse::<u16>() {
                        ws_port = parsed;
                    }
                }
            }
            "--headless" => {
                headless = true;
            }
            "--version" | "-V" => {
                show_version = true;
            }
            _ => {}
        }
    }
    ParsedArgs {
        ws_port,
        headless,
        show_version,
    }
}

#[tauri::command]
fn get_ws_port(state: tauri::State<AppState>) -> u16 {
    state.ws_port
}

fn main() {
    let build_args: Vec<_> = std::env::args().skip(1).collect();
    if build_args.as_slice() == ["--build-info"] || build_args.as_slice() == ["--build-info", "--version"] {
        println!("{}", serde_json::json!({
            "role": "desktop",
            "release": env!("CARGO_PKG_VERSION"),
            "protocol": frameviz_server::PROTOCOL_VERSION,
        }));
        return;
    }
    let args = parse_args();
    if args.show_version {
        println!("FrameViz Host v{}", env!("CARGO_PKG_VERSION"));
        return;
    }

    // Start WebSocket server before Tauri
    // (cleanup_stale_discovery is called inside start_websocket_server)
    let control_port = control::control_port_from_env();
    let (managed_exit, exit_requested) = mpsc::channel();
    let (ws_port, ws_enabled, ws_shutdown_tx) = start_websocket_server(control_port, args.ws_port, managed_exit);
    let view_id = parse_view_id();

    // Start HTTP server for browser mode support
    let (http_port, http_shutdown_tx) = start_http_server(ws_port, control_port, DEFAULT_HTTP_PORT);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            ws_port,
            http_port,
            ws_enabled,
            view_id,
            ws_shutdown_tx,
            http_shutdown_tx,
        })
        .invoke_handler(tauri::generate_handler![get_ws_port])
        .setup(move |app| {
            control::start_control_server(app.handle().clone(), control_port);
            let handle = app.handle().clone();
            thread::spawn(move || {
                if exit_requested.recv().is_ok() {
                    handle.exit(0);
                }
            });

            let menu = tauri::menu::Menu::default(app.handle())?;
            let guide = tauri::menu::MenuItem::with_id(app.handle(), "show_welcome", "使用指南", true, None::<&str>)?;
            if let Some(item) = menu.get(tauri::menu::HELP_SUBMENU_ID) {
                if let Some(help) = item.as_submenu() { help.append(&guide)?; }
            } else {
                menu.append(&guide)?;
            }
            app.set_menu(menu)?;

            // A normal App launch has a visible entry point. SDK/headless launches
            // retain their existing background/view-window behavior.
            if let Some(window) = app.get_webview_window("main") {
                let preferences = startup::preferences_path();
                let seen = preferences.as_deref().map(startup::welcome_seen).unwrap_or(false);
                if args.headless || app.state::<AppState>().view_id().is_some() || seen {
                    window.hide()?;
                } else {
                    window.show()?;
                    window.set_focus()?;
                    if let Some(path) = preferences {
                        if let Err(error) = startup::mark_welcome_seen(&path) {
                            eprintln!("[FrameViz] Could not save welcome preference: {error}");
                        }
                    }
                }
            }

            // Open initial view if --view-id was provided
            if let Some(view_id) = app.state::<AppState>().view_id() {
                if args.headless {
                    println!("[FrameViz] Headless mode: skipping view window");
                    return Ok(());
                }
                let handle = app.handle().clone();
                if let Err(err) = control::open_view_window(
                    &handle,
                    view_id.clone(),
                    None, // scene_id
                    None, // title
                    None, // width
                    None, // height
                    None, // x
                    None, // y
                    None, // page
                    None, // performance_mode
                    None, // decorations (default: true)
                ) {
                    eprintln!("[FrameViz] Failed to open initial view {}: {}", view_id, err);
                }
            }

            // Open DevTools in debug mode
            #[cfg(debug_assertions)]
            {
                let enable_devtools = std::env::var("FRAMEVIZ_TAURI_DEVTOOLS")
                    .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
                    .unwrap_or(false);
                if enable_devtools {
                    if let Some(window) = app.get_webview_window("main") {
                        window.open_devtools();
                    }
                }
            }

            println!("[FrameViz] Application started");
            if ws_enabled {
                println!("[FrameViz] WebSocket server running on port {}", ws_port);
            } else {
                println!("[FrameViz] Expecting external WebSocket server on port {}", ws_port);
            }
            println!("[FrameViz] Application ready.");

            Ok(())
        })
        .on_menu_event(|app, event| {
            if event.id().as_ref() == "show_welcome" {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(all(test, debug_assertions))]
mod remediation_tests {
    use super::*;
    #[test]
    fn dev_discovery_uses_explicit_path_and_refuses_another_owner() {
        let root = std::env::temp_dir().join(format!("frameviz-discovery-test-{}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("host.json");
        let previous = std::env::var_os("FRAMEVIZ_DISCOVERY_PATH");
        std::env::set_var("FRAMEVIZ_DISCOVERY_PATH", &path);
        std::fs::write(&path, serde_json::json!({"pid":std::process::id(),"token":"synthetic"}).to_string()).unwrap();
        update_discovery_with_dev_url("http://127.0.0.1:12345/view/", 12345).unwrap();
        let data: serde_json::Value = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        assert_eq!(data["http_port"], 12345);
        assert_eq!(data["viewer_url"], "http://127.0.0.1:12345/view/");
        let foreign = b"{\"pid\":0,\"token\":\"synthetic-other-owner\"}";
        std::fs::write(&path, foreign).unwrap();
        assert!(update_discovery_with_dev_url("http://localhost:12346/", 12346).is_err());
        assert_eq!(std::fs::read(&path).unwrap(), foreign);
        match previous { Some(value) => std::env::set_var("FRAMEVIZ_DISCOVERY_PATH", value), None => std::env::remove_var("FRAMEVIZ_DISCOVERY_PATH") }
        std::fs::remove_dir_all(root).unwrap();
    }
}

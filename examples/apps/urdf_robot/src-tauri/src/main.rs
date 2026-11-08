#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::thread;
use tokio::sync::watch;

fn main() {
    let ws_port: u16 = std::env::args()
        .skip(1)
        .position(|a| a == "--ws-port")
        .and_then(|i| std::env::args().nth(i + 2))
        .and_then(|v| v.parse().ok())
        .unwrap_or(9527);

    // Check if an external host is already running on the target port.
    let host_already_running = match std::net::TcpStream::connect_timeout(
        &std::net::SocketAddr::from(([127, 0, 0, 1], ws_port)),
        std::time::Duration::from_millis(200),
    ) {
        Ok(_) => true,
        Err(e) => {
            eprintln!("[URDFRobotApp] Port check failed: {:?}", e);
            false
        }
    };

    // Start embedded WebSocket server in a background thread (unless external host detected).
    let _shutdown_tx: Option<watch::Sender<bool>> = if !host_already_running {
        let (tx, rx) = watch::channel(false);
        thread::spawn(move || {
            let rt = tokio::runtime::Runtime::new().expect("tokio runtime");
            rt.block_on(async {
                let diagnostics = frameviz_server::build_diagnostics(ws_port);
                if let Err(e) = frameviz_server::run_server(ws_port, diagnostics, rx).await {
                    eprintln!("[URDFRobotApp] WebSocket server error: {:?}", e);
                }
            });
        });
        println!("[URDFRobotApp] Embedded FrameViz server on port {}", ws_port);
        Some(tx)
    } else {
        println!("[URDFRobotApp] External host detected on port {}, skipping embedded server", ws_port);
        None
    };

    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

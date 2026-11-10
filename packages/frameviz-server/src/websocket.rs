//! WebSocket Server for FrameViz (Rust host).
//!
//! Relays protocol commands between Python clients and web viewer clients.

use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use crate::host::{Host, HostError, LogEntry, SceneSnapshot};
use futures_util::{SinkExt, StreamExt};
use once_cell::sync::Lazy;
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Write;
use std::net::TcpListener as StdTcpListener;
use std::net::TcpStream as StdTcpStream;
use std::path::PathBuf;
use std::sync::mpsc as std_mpsc;
use std::sync::Arc;
use std::thread;
use std::time::Duration as StdDuration;
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{mpsc, Mutex};
use tokio::time::{self, Duration};
use tokio_tungstenite::tungstenite::handshake::server::{Request, Response};
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::accept_hdr_async;
use url::form_urlencoded;

use crate::RegisteredViewer;


const PROTOCOL_VERSION: &str = "0.4.0";
static DISPATCH: Lazy<Mutex<()>> = Lazy::new(|| Mutex::new(()));

const BUFFER_UPLOAD_TIMEOUT_MS: u64 = 2000;
const AUTH_TOKEN_LENGTH: usize = 32;  // P0-2: Token length in bytes

#[derive(Clone)]
struct LogWriter {
    sender: std_mpsc::Sender<String>,
}

impl LogWriter {
    fn new(path: PathBuf) -> Option<Self> {
        if let Some(parent) = path.parent() {
            if fs::create_dir_all(parent).is_err() {
                return None;
            }
        }
        rotate_log_if_needed(&path);
        let (tx, rx) = std_mpsc::channel::<String>();
        let path_clone = path.clone();
        thread::spawn(move || {
            if let Ok(mut file) = fs::OpenOptions::new().create(true).append(true).open(&path_clone) {
                while let Ok(line) = rx.recv() {
                    let _ = writeln!(file, "{}", line);
                }
            }
        });
        Some(Self { sender: tx })
    }

    fn log(&self, level: &str, msg: &str, fields: Value) {
        let payload = json!({
            "ts_ms": now_ms(),
            "level": level,
            "msg": msg,
            "fields": fields,
        });
        let _ = self.sender.send(payload.to_string());
    }
}

pub struct ServerDiagnostics {
    log_writer: Option<LogWriter>,
    log_path: Option<PathBuf>,
    discovery_path: Option<PathBuf>,
    http_port: Option<u16>,
}

impl ServerDiagnostics {
    /// Publish the standalone Viewer's HTTP port in the initial discovery record.
    pub fn with_http_port(mut self, port: u16) -> Self {
        self.http_port = Some(port);
        self
    }
}

pub fn select_available_port_avoiding(
    preferred: u16,
    attempts: u16,
    avoid: &[u16],
) -> Option<u16> {
    for offset in 0..attempts {
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

pub fn build_diagnostics(port: u16) -> ServerDiagnostics {
    let log_path = resolve_log_path(port);
    let log_writer = log_path.clone().and_then(LogWriter::new);
    let discovery_path = resolve_discovery_path();
    ServerDiagnostics {
        log_writer,
        log_path,
        discovery_path,
        http_port: None,
    }
}

#[derive(Clone, Debug, PartialEq)]
enum ClientType {
    Protocol,
    Viewer,
}

#[derive(Clone, Debug)]
struct PendingUpload {
    buffer_id: String,
    offset_bytes: usize,
    chunk_bytes: usize,
    command_id: String,
}

// Overflow closes the connection: a client must reconnect and restore a snapshot.
// Silently losing a command would leave its scene permanently divergent.
#[derive(Clone)]
struct ClientSender {
    queue: mpsc::Sender<Message>,
    cancel: tokio::sync::watch::Sender<bool>,
}
impl ClientSender {
    async fn send(&self, message: Message) -> Result<(), ()> {
        if *self.cancel.borrow() { return Err(()); }
        match time::timeout(Duration::from_secs(2), self.queue.send(message)).await {
            Ok(Ok(())) => Ok(()),
            _ => { let _ = self.cancel.send(true); Err(()) }
        }
    }
}

#[derive(Clone)]
struct ClientState {
    client_type: ClientType,
    view_id: Option<String>,
    scene_id: Option<String>,
    scene_refs: HashSet<String>,
    sender: ClientSender,
    pending_upload: Option<PendingUpload>,
    authenticated: bool,  // P0-2: Track authentication status
}

// NOTE: RegisteredViewer is provided by this crate (frameviz-server)

struct ServerState {
    host: Host,
    clients: HashMap<usize, ClientState>,
    next_client_id: usize,
    revision: u64,
    view_to_scene: HashMap<String, String>,
    log_writer: Option<LogWriter>,
    log_path: Option<PathBuf>,
    discovery_path: Option<PathBuf>,
    auth_token: String,  // P0-2: Authentication token
    viewer_registry: HashMap<String, RegisteredViewer>,  // Viewer name -> info
}

impl ServerState {
    fn new(host: Host, diagnostics: ServerDiagnostics) -> Self {
        Self {
            host,
            clients: HashMap::new(),
            next_client_id: 1,
            revision: 0,
            view_to_scene: HashMap::new(),
            log_writer: diagnostics.log_writer,
            log_path: diagnostics.log_path,
            discovery_path: diagnostics.discovery_path,
            auth_token: generate_auth_token(),
            viewer_registry: HashMap::new(),
        }
    }

    fn next_id(&mut self) -> usize {
        let id = self.next_client_id;
        self.next_client_id += 1;
        id
    }
}

type SharedState = Arc<Mutex<ServerState>>;

pub async fn run_server(
    port: u16,
    diagnostics: ServerDiagnostics,
    shutdown_rx: tokio::sync::watch::Receiver<bool>,
) -> Result<(), Box<dyn std::error::Error>> {
    let addr = format!("127.0.0.1:{}", port);
    let listener = TcpListener::bind(&addr).await?;
    run_server_on_listener(listener, diagnostics, shutdown_rx).await
}

/// Run on an already-bound socket so standalone startup can reserve WebSocket
/// before allocating the HTTP port, without a port-probe/rebind race.
pub async fn run_server_on_listener(
    listener: TcpListener,
    diagnostics: ServerDiagnostics,
    mut shutdown_rx: tokio::sync::watch::Receiver<bool>,
) -> Result<(), Box<dyn std::error::Error>> {
    let addr = listener.local_addr()?;
    let port = addr.port();
    println!("[WS] Server listening on ws://{}", addr);

    let http_port = diagnostics.http_port;
    if http_port.is_some() && diagnostics.discovery_path.is_none() {
        return Err("Cannot resolve the standalone Host state directory".into());
    }
    let (log_tx, mut log_rx) = mpsc::unbounded_channel::<LogEntry>();
    let state = Arc::new(Mutex::new(ServerState::new(Host::new(Some(log_tx)), diagnostics)));

    {
        let state_guard = state.lock().await;
        if let Some(writer) = &state_guard.log_writer {
            writer.log("info", "ws_server_started", json!({ "addr": addr }));
        }
        if let Some(path) = &state_guard.discovery_path {
            // Standalone knows its HTTP port before accepting clients. Embedded
            // callers can still use update_discovery_http_port as before.
            if let Err(err) = write_discovery_file(path, port, state_guard.log_path.as_ref(), &state_guard.auth_token, http_port) {
                if http_port.is_some() {
                    return Err(format!("Cannot write standalone Host discovery: {err}").into());
                }
                if let Some(writer) = &state_guard.log_writer {
                    writer.log(
                        "warn",
                        "discovery_write_failed",
                        json!({ "error": err.to_string() }),
                    );
                }
            }
        }
    }

    let state_clone = state.clone();
    tokio::spawn(async move {
        while let Some(entry) = log_rx.recv().await {
            let data = serde_json::to_value(entry).unwrap_or_else(|_| json!({}));
            if let Some(writer) = {
                let guard = state_clone.lock().await;
                guard.log_writer.clone()
            } {
                let mut fields = match data.get("fields") {
                    Some(value) => value.clone(),
                    None => json!({}),
                };
                if let Some(obj) = fields.as_object_mut() {
                    obj.insert(
                        "logger".to_string(),
                        data.get("logger").cloned().unwrap_or_else(|| json!("host")),
                    );
                }
                let level = data.get("level").and_then(|v| v.as_str()).unwrap_or("info");
                let msg = data.get("msg").and_then(|v| v.as_str()).unwrap_or("host_log");
                writer.log(level, msg, fields);
            }
            broadcast_event_to_protocol(&state_clone, "log", data).await;
        }
    });

    loop {
        tokio::select! {
            _ = shutdown_rx.changed() => {
                if *shutdown_rx.borrow() {
                    break;
                }
            }
            accept_result = listener.accept() => {
                let Ok((stream, _)) = accept_result else {
                    break;
                };
                let state_clone = state.clone();
                tokio::spawn(async move {
                    if let Err(err) = handle_connection(stream, state_clone).await {
                        // Skip logging for handshake failures (normal for port probes)
                        let err_str = err.to_string();
                        if !err_str.contains("handshake") && !err_str.contains("Handshake") {
                            eprintln!("[WS] Connection error: {}", err);
                        }
                    }
                });
            }
        }
    }

    if let Some(path) = state.lock().await.discovery_path.clone() {
        let _ = fs::remove_file(path);
    }

    Ok(())
}

struct ConnectionGuard {
    state: SharedState,
    client_id: usize,
    writer: Option<tokio::task::JoinHandle<()>>,
}

impl Drop for ConnectionGuard {
    fn drop(&mut self) {
        if let Some(writer) = self.writer.take() { writer.abort(); }
        if let Ok(mut state) = self.state.try_lock() {
            state.clients.remove(&self.client_id);
        } else {
            let state = self.state.clone();
            let id = self.client_id;
            tokio::spawn(async move { state.lock().await.clients.remove(&id); });
        }
    }
}

async fn handle_connection(stream: TcpStream, state: SharedState) -> Result<(), String> {
    let info = Arc::new(std::sync::Mutex::new(ClientHello::default()));
    let info_clone = info.clone();

    let ws_stream = accept_hdr_async(stream, move |req: &Request, resp: Response| {
        if let Some(origin) = req.headers().get("origin") {
            let allowed = origin.to_str().ok().and_then(|s| url::Url::parse(s).ok()).map_or(false, |url| {
                matches!(url.host_str(), Some("localhost" | "127.0.0.1" | "[::1]" | "tauri.localhost"))
            });
            if !allowed { return Err(tokio_tungstenite::tungstenite::http::Response::builder().status(403).body(Some("Origin denied".into())).unwrap()); }
        }
        if let Ok(mut guard) = info_clone.lock() {
            *guard = parse_client_hello(req);
        }
        Ok(resp)
    })
    .await
    .map_err(|err| format!("handshake failed: {}", err))?;

    let hello = Arc::try_unwrap(info)
        .map_err(|_| "hello unwrap failed".to_string())?
        .into_inner()
        .map_err(|_| "hello lock failed".to_string())?;

    // Use bounded channel to prevent unbounded queue growth (P1-2)
    const CLIENT_MSG_BUFFER_SIZE: usize = 32;
    let (queue, receiver) = mpsc::channel(CLIENT_MSG_BUFFER_SIZE);
    let (cancel, mut cancelled) = tokio::sync::watch::channel(false);
    let sender = ClientSender { queue, cancel };
    let client_id = {
        let mut state_guard = state.lock().await;
        if state_guard.clients.len() >= 64 { return Err("Client limit reached".into()); }
        let id = state_guard.next_id();
        state_guard.clients.insert(
            id,
            ClientState {
                client_type: hello.client_type.clone(),
                view_id: hello.view_id.clone(),
                scene_id: hello.scene_id.clone(),
                scene_refs: HashSet::new(),
                sender: sender.clone(),
                pending_upload: None,
                authenticated: false,
            },
        );
        id
    };

    let mut connection = ConnectionGuard { state: state.clone(), client_id, writer: None };
    log_event(
        &state,
        "info",
        "client_connected",
        json!({
            "client_id": client_id,
            "type": match hello.client_type {
                ClientType::Protocol => "protocol",
                ClientType::Viewer => "viewer",
            },
            "view_id": hello.view_id,
        }),
    )
    .await;

    let (mut ws_sender, mut ws_receiver) = ws_stream.split();
    let mut outgoing = receiver;

    let mut reader_cancelled = sender.cancel.subscribe();
    let writer_cancel = sender.cancel.clone();
    let auth_deadline = time::Instant::now() + Duration::from_secs(5);
    let write_task = tokio::spawn(async move {
        loop {
            tokio::select! {
                _ = cancelled.changed() => { let _ = time::timeout(Duration::from_secs(1), ws_sender.close()).await; break; }
                message = outgoing.recv() => {
                    let Some(message) = message else { break; };
                    if !matches!(time::timeout(Duration::from_secs(5), ws_sender.send(message)).await, Ok(Ok(()))) { let _ = writer_cancel.send(true); break; }
                }
            }
        }
    });

    connection.writer = Some(write_task);
    loop {
        let authenticated = { state.lock().await.clients.get(&client_id).map_or(false, |c| c.authenticated) };
        let message = tokio::select! {
            _ = reader_cancelled.changed() => None,
            _ = time::sleep_until(auth_deadline), if !authenticated => None,
            message = ws_receiver.next() => message,
        };
        let Some(msg) = message else { break; };
        match msg {
            Ok(Message::Text(text)) => {
                handle_text_message(&state, client_id, text).await;
            }
            Ok(Message::Binary(data)) => {
                handle_binary_message(&state, client_id, data).await;
            }
            Ok(Message::Close(_)) => {
                break;
            }
            _ => {}
        }
    }

    // A transport disconnect (including page refresh) does not destroy a view.
    // Lifetime ends with explicit destroy_view/destroy_scene or Host shutdown.
    state.lock().await.clients.remove(&client_id);

    log_event(
        &state,
        "info",
        "client_disconnected",
        json!({ "client_id": client_id }),
    )
    .await;

    drop(connection);
    Ok(())
}

async fn handle_text_message(state: &SharedState, client_id: usize, text: String) {
    let _dispatch = DISPATCH.lock().await;
    if text.len() > 24 * 1024 * 1024 { return; }
    let (client_type, authenticated) = {
        let state_guard = state.lock().await;
        match state_guard.clients.get(&client_id) {
            Some(c) => (Some(c.client_type.clone()), c.authenticated),
            None => (None, false),
        }
    };
    let Some(client_type) = client_type else {
        return;
    };

    let parsed: Value = match serde_json::from_str(&text) {
        Ok(value) => value,
        Err(_) => return,
    };

    // P0-2: Handle authentication for Protocol clients
    if !authenticated {
        if let Some(msg_type) = parsed.get("type").and_then(|v| v.as_str()) {
            if msg_type == "auth" {
                if let Some(token) = parsed.get("token").and_then(|v| v.as_str()) {
                    let expected_token = {
                        let state_guard = state.lock().await;
                        state_guard.auth_token.clone()
                    };
                    if token == expected_token {
                        // Mark client as authenticated
                        {
                            let mut state_guard = state.lock().await;
                            if let Some(client) = state_guard.clients.get_mut(&client_id) {
                                client.authenticated = true;
                            }
                        }
                        // Send success response
                        send_auth_response(state, client_id, true, None).await;
                        log_event(state, "info", "client_authenticated", json!({ "client_id": client_id })).await;
                        let sender = state.lock().await.clients.get(&client_id).map(|c| c.sender.clone());
                        if sender.is_some() {
    if client_type == ClientType::Viewer {
        let bound_view = { state.lock().await.clients.get(&client_id).and_then(|c| c.view_id.clone()) };
        if let Some(view_id) = bound_view {
            let scene_id = {
                let state_guard = state.lock().await;
                state_guard.view_to_scene.get(&view_id).cloned()
            };
            if let Some(scene_id) = scene_id {
                {
                    let mut state_guard = state.lock().await;
                    if let Some(client) = state_guard.clients.get_mut(&client_id) {
                        client.scene_id = Some(scene_id.clone());
                    }
                }
                let _ = send_init_and_snapshot(state, client_id, &view_id, &scene_id).await;
                broadcast_event_to_protocol(state, "viewer_ready", json!({ "view_id": view_id, "scene_id": scene_id })).await;
            }
        }
    }

                        }
                        return;
                    }
                }
                // Auth failed
                send_auth_response(state, client_id, false, Some("Invalid token")).await;
                log_event(state, "warn", "auth_failed", json!({ "client_id": client_id })).await;
                return;
            }
        }
        // Non-auth message from unauthenticated client - ignore
        log_event(state, "warn", "unauthenticated_message", json!({ "client_id": client_id })).await;
        return;
    }

    if parsed.get("type").and_then(Value::as_str) == Some("cmd") {
        {
            if parsed.get("protocol_version").and_then(Value::as_str) != Some(PROTOCOL_VERSION) {
                if let Some(id) = parsed.get("id").and_then(Value::as_str) {
                    send_error_response(state, client_id, id, "ERR_PROTOCOL_VERSION", "Unsupported protocol version").await;
                }
                return;
            }
        }
    }
    if client_type == ClientType::Viewer {
        if let Some(message_type) = parsed.get("type").and_then(|v| v.as_str()) {
            if message_type == "event" {
                if let Some(name) = parsed.get("name").and_then(|v| v.as_str()) {
                    let mut data = parsed.get("data").cloned().unwrap_or_else(|| json!({}));
                    if !matches!(name, "picked" | "transformed" | "camera_pose_response" | "pick_config_response" | "pick_info_response" | "object_ready" | "object_failed" | "key_down") { return; }
                    let guard = state.lock().await;
                    let Some(client) = guard.clients.get(&client_id) else { return; };
                    if !data.is_object() {
                        let _ = client.sender.cancel.send(true);
                        return;
                    }
                    data["view_id"] = json!(client.view_id);
                    data["scene_id"] = json!(client.scene_id);
                    drop(guard);
                    broadcast_event_to_protocol(state, name, data).await;
                }
                return;
            }
            if message_type == "cmd" {
                if let Some(cmd) = parse_command_envelope(&parsed) {
                    handle_viewer_command(state, client_id, cmd).await;
                } else if let Some(cmd_id) = parsed.get("id").and_then(|v| v.as_str()) {
                    send_error_response(state, client_id, cmd_id, "ERR_INVALID_ARGS", "Invalid protocol envelope.").await;
                }
                return;
            }
        }
        return;
    }

    let Some(command) = parse_command_envelope(&parsed) else {
        if let Some(cmd_id) = parsed.get("id").and_then(|v| v.as_str()) {
            send_error_response(state, client_id, cmd_id, "ERR_INVALID_ARGS", "Invalid protocol envelope.").await;
        }
        return;
    };

    handle_protocol_command(state, client_id, command).await;
}

async fn handle_binary_message(state: &SharedState, client_id: usize, data: Vec<u8>) {
    let _dispatch = DISPATCH.lock().await;
    // P0-2: Check authentication for Protocol clients before processing binary frames
    let (client_type, authenticated, pending) = {
        let mut state_guard = state.lock().await;
        match state_guard.clients.get_mut(&client_id) {
            Some(client) => (
                Some(client.client_type.clone()),
                client.authenticated,
                client.pending_upload.take(),
            ),
            None => (None, false, None),
        }
    };
    
    let Some(_client_type) = client_type else {
        return;
    };
    
    // Reject binary frames from unauthenticated Protocol clients
    if !authenticated {
        log_event(state, "warn", "binary_from_unauthenticated", json!({ "client_id": client_id })).await;
        return;
    }
    
    let Some(pending) = pending else {
        return;
    };

    if data.len() != pending.chunk_bytes {
        send_error_response(
            state,
            client_id,
            &pending.command_id,
            "ERR_BUFFER_SIZE_MISMATCH",
            &format!("Expected {} bytes, got {}", pending.chunk_bytes, data.len()),
        )
        .await;
        return;
    }

    let store_result = {
        let mut state_guard = state.lock().await;
        state_guard
            .host
            .store_buffer_data(&pending.buffer_id, pending.offset_bytes, &data)
    };
    match store_result {
        Ok(_) => {
            send_ok_response(state, client_id, &pending.command_id, json!({})).await;
        }
        Err(err) => {
            send_error_response(state, client_id, &pending.command_id, &err.code, &err.message).await;
        }
    }
}

async fn handle_protocol_command(state: &SharedState, client_id: usize, mut command: CommandEnvelope) {
    let name = command.name.clone();

    if name == "get_resource_counts" {
        let counts = {
            let guard = state.lock().await;
            let mut counts = guard.host.resource_counts(); counts["connections"] = json!(guard.clients.len()); counts
        };
        send_ok_response(state, client_id, &command.id, counts).await; return;
    }
    if name == "upload_buffer_chunk" {
        handle_upload_buffer_chunk(state, client_id, &mut command).await;
        return;
    }

    // Handle shared memory buffer upload (local optimization)
    if name == "load_buffer_shm" {
        handle_load_buffer_shm(state, client_id, &command).await;
        return;
    }

    // ================== Viewer Registration Commands (Embedded UI) ==================
    
    // get_viewer_by_name: SDK queries for a named Viewer
    if name == "get_viewer_by_name" {
        let viewer_name = command.args.get("viewer_name")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        
        let result = {
            let state_guard = state.lock().await;
            state_guard.viewer_registry.get(viewer_name).cloned()
        };
        
        if let Some(viewer) = result {
            send_ok_response(state, client_id, &command.id, json!({
                "view_id": viewer.view_id,
                "scene_id": viewer.scene_id,
                "viewer_name": viewer.viewer_name,
            })).await;
        } else {
            send_error_response(state, client_id, &command.id, 
                "ERR_NOT_FOUND", 
                &format!("Viewer '{}' not registered", viewer_name)).await;
        }
        return;
    }
    
    // list_viewers: SDK queries all registered Viewers
    if name == "list_viewers" {
        let viewers: Vec<Value> = {
            let state_guard = state.lock().await;
            state_guard.viewer_registry.values().map(|v| {
                json!({
                    "viewer_name": v.viewer_name,
                    "view_id": v.view_id,
                    "scene_id": v.scene_id,
                })
            }).collect()
        };
        
        send_ok_response(state, client_id, &command.id, json!({
            "viewers": viewers,
        })).await;
        return;
    }

    let target_scene_id = command
        .args
        .get("scene_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());
    let target_view_id = command
        .args
        .get("view_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let viewer_query = matches!(name.as_str(), "get_camera_pose" | "get_pick_config" | "get_picked_info");
    if viewer_query {
        let available = {
            let guard = state.lock().await;
            guard.clients.values().any(|c| c.authenticated && c.client_type == ClientType::Viewer && c.view_id == target_view_id)
        };
        if !available { send_error_response(state, client_id, &command.id, "ERR_VIEWER_UNAVAILABLE", "No authenticated viewer for this view").await; return; }
        command.args["request_id"] = json!(format!("{}:{}", client_id, command.id));
    }
    let response = {
        let mut state_guard = state.lock().await;
        state_guard.host.handle_command(&command.name, &mut command.args)
    };

    match response {
        Ok(mut result) => {
            {
                let mut guard = state.lock().await;
                if !name.starts_with("get_") && !name.starts_with("list_") && !name.starts_with("is_") { guard.revision += 1; }
                if name == "get_scene_snapshot" { result["revision"] = json!(guard.revision); }
            }
            if viewer_query { result["request_id"] = command.args["request_id"].clone(); }
            send_ok_response(state, client_id, &command.id, result.clone()).await;
            // Destruction must reach the current subscribers before their bindings are removed.
            if matches!(name.as_str(), "destroy_scene" | "destroy_view") {
                forward_sync_to_viewers(state, &command, &result, target_scene_id.as_deref(), target_view_id.as_deref()).await;
                handle_mapping_updates(state, client_id, &command, &result).await;
            } else {
                handle_mapping_updates(state, client_id, &command, &result).await;
                forward_sync_to_viewers(state, &command, &result, target_scene_id.as_deref(), target_view_id.as_deref()).await;
            }
        }
        Err(err) => {
            send_error_response(state, client_id, &command.id, &err.code, &err.message).await;
        }
    }
}

async fn handle_viewer_command(state: &SharedState, client_id: usize, mut command: CommandEnvelope) {
    let (view_id, scene_id) = {
        let state_guard = state.lock().await;
        let client_info = match state_guard.clients.get(&client_id) {
            Some(info) => info,
            None => return,
        };
        let view_id = client_info.view_id.clone();
        let scene_id = view_id
            .as_ref()
            .and_then(|view| state_guard.view_to_scene.get(view).cloned());
        (view_id, scene_id)
    };

    for (key, bound) in [("view_id", &view_id), ("scene_id", &scene_id)] {
        if let Some(requested) = command.args.get(key) {
            if requested.as_str().is_none() || bound.as_ref().map_or(false, |b| requested.as_str() != Some(b.as_str())) {
                send_error_response(state, client_id, &command.id, "ERR_INVALID_SCOPE", "Viewer cannot change its scope").await;
                return;
            }
        }
    }
    if command.name != "register_viewer" && !matches!(command.name.as_str(),
        "set_transform" | "set_object_transforms" | "set_camera_pose" | "set_camera_controls" |
        "get_camera_controls" | "get_view_config" | "set_view_config" | "get_scene_snapshot" |
        "set_view" | "reset_camera" | "set_render_mode" | "set_performance_mode" |
        "set_pick_config" | "clear_pick_highlight" | "attach_gizmo" | "set_gizmo_mode" | "detach_gizmo") {
        send_error_response(state, client_id, &command.id, "ERR_FORBIDDEN", "Command is not allowed for a viewer").await; return;
    }
    // ================== Viewer Registration (Embedded UI) ==================
    // Viewer clients can register themselves with a name
    if command.name == "register_viewer" {
        let viewer_name = command.args.get("viewer_name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        
        if viewer_name.is_empty() {
            send_error_response(state, client_id, &command.id, 
                "ERR_INVALID_ARGS", "viewer_name is required").await;
            return;
        }
        
        let existing_viewer = {
            let state_guard = state.lock().await;
            state_guard.viewer_registry.get(&viewer_name).cloned()
        };

        // Get or create scene_id (prefer existing scene for same viewer name)
        let final_scene_id = if let Some(sid) = command.args.get("scene_id").and_then(|v| v.as_str()) {
            sid.to_string()
        } else if let Some(existing) = &existing_viewer {
            existing.scene_id.clone()
        } else if let Some(ref sid) = scene_id {
            sid.clone()
        } else {
            // Create new scene for this viewer
            let result = {
                let mut state_guard = state.lock().await;
                state_guard.host.handle_command("create_scene", &mut json!({}))
            };
            match result {
                Ok(res) => res.get("scene_id").and_then(|v| v.as_str()).unwrap_or("s_1").to_string(),
                Err(_) => "s_1".to_string(),
            }
        };
        
        let final_view_id = view_id.clone().or_else(|| existing_viewer.as_ref().map(|v| v.view_id.clone())).unwrap_or_else(|| format!("v_{}", client_id));
        
        // Register the viewer and ensure Host has a concrete view entry.
        let registration_error = {
            let mut state_guard = state.lock().await;

            // Ensure scene exists before binding.
            if let Err(err) = state_guard.host.handle_command(
                "create_scene",
                &mut json!({ "scene_id": final_scene_id.clone() }),
            ) {
                Some(format!(
                    "failed to create scene '{}': {}",
                    final_scene_id, err.message
                ))
            } else if let Err(err) = state_guard.host.handle_command(
                "attach_scene",
                &mut json!({ "view_id": final_view_id.clone(), "scene_id": final_scene_id.clone() }),
            ) {
                Some(format!(
                    "failed to bind view '{}' to scene '{}': {}",
                    final_view_id, final_scene_id, err.message
                ))
            } else {
                if let Some(existing) = &existing_viewer {
                    if existing.view_id != final_view_id {
                        state_guard.view_to_scene.remove(&existing.view_id);
                    }
                }
                state_guard.viewer_registry.insert(viewer_name.clone(), RegisteredViewer {
                    viewer_name: viewer_name.clone(),
                    view_id: final_view_id.clone(),
                    scene_id: final_scene_id.clone(),
                    client_id: client_id as u64,
                });

                // Also update view_to_scene mapping
                state_guard
                    .view_to_scene
                    .insert(final_view_id.clone(), final_scene_id.clone());

                // Update client's view_id if not set
                if let Some(client) = state_guard.clients.get_mut(&client_id) {
                    if client.view_id.is_none() {
                        client.view_id = Some(final_view_id.clone());
                    }
                    if client.scene_id.is_none() {
                        client.scene_id = Some(final_scene_id.clone());
                    }
                }

                None
            }
        };
        if let Some(message) = registration_error {
            send_error_response(state, client_id, &command.id, "ERR_INTERNAL", &message).await;
            return;
        }
        
        log_event(state, "info", "viewer_registered", json!({
            "viewer_name": viewer_name,
            "view_id": final_view_id,
            "scene_id": final_scene_id,
            "client_id": client_id,
        })).await;
        
        send_ok_response(state, client_id, &command.id, json!({
            "view_id": final_view_id,
            "scene_id": final_scene_id,
            "viewer_name": viewer_name,
        })).await;

        // Send current scene snapshot so refreshed viewers see existing objects.
        let sender = {
            let state_guard = state.lock().await;
            state_guard.clients.get(&client_id).map(|client| client.sender.clone())
        };
        if sender.is_some() {
            let _ = send_init_and_snapshot(state, client_id, &final_view_id, &final_scene_id).await;
        }
        return;
    }

    if view_id.is_none() || scene_id.is_none() {
        send_error_response(state, client_id, &command.id, "ERR_INVALID_SCOPE", "Register viewer first").await; return;
    }
    if command.args.get("scene_id").is_none() {
        if let Some(scene_id) = &scene_id {
            if let Some(map) = command.args.as_object_mut() {
                map.insert("scene_id".to_string(), Value::String(scene_id.clone()));
            }
        }
    }
    if command.args.get("view_id").is_none() {
        if let Some(view_id) = &view_id {
            if let Some(map) = command.args.as_object_mut() {
                map.insert("view_id".to_string(), Value::String(view_id.clone()));
            }
        }
    }

    let response = {
        let mut state_guard = state.lock().await;
        state_guard.host.handle_command(&command.name, &mut command.args)
    };
    match response {
        Ok(mut result) => {
            {
                let mut guard = state.lock().await;
                if !command.name.starts_with("get_") { guard.revision += 1; }
                if command.name == "get_scene_snapshot" { result["revision"] = json!(guard.revision); }
            }
            let target_view = if matches!(command.name.as_str(), "set_transform" | "set_object_transforms") { None } else { view_id.as_deref() };
            forward_sync_to_viewers(state, &command, &result, scene_id.as_deref(), target_view).await;
            send_ok_response(state, client_id, &command.id, result).await;
        }
        Err(err) => {
            send_error_response(state, client_id, &command.id, &err.code, &err.message).await;
        }
    }
}

async fn handle_upload_buffer_chunk(state: &SharedState, client_id: usize, command: &mut CommandEnvelope) {
    let args = command.args.as_object().cloned().unwrap_or_default();
    let buffer_id = args.get("buffer_id").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let offset_bytes = args.get("offset_bytes").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
    let chunk_bytes = args.get("chunk_bytes").and_then(|v| v.as_u64()).unwrap_or(0) as usize;

    if buffer_id.is_empty() || chunk_bytes == 0 || chunk_bytes > 16 * 1024 * 1024 {
        send_error_response(
            state,
            client_id,
            &command.id,
            "ERR_INVALID_ARGS",
            "buffer_id and chunk_bytes are required",
        )
        .await;
        return;
    }

    if let Some(data_base64) = args.get("data_base64").and_then(|v| v.as_str()) {
        match BASE64.decode(data_base64) {
            Ok(data) => {
                if data.len() != chunk_bytes {
                    send_error_response(
                        state,
                        client_id,
                        &command.id,
                        "ERR_BUFFER_SIZE_MISMATCH",
                        &format!("Expected {} bytes, got {}", chunk_bytes, data.len()),
                    )
                    .await;
                    return;
                }
                let store_result = {
                    let mut state_guard = state.lock().await;
                    state_guard
                        .host
                        .store_buffer_data(&buffer_id, offset_bytes, &data)
                };
                match store_result {
                    Ok(_) => {
                        send_ok_response(state, client_id, &command.id, json!({})).await;
                    }
                    Err(err) => send_error_response(state, client_id, &command.id, &err.code, &err.message).await,
                }
            }
            Err(_) => {
                send_error_response(state, client_id, &command.id, "ERR_INVALID_ARGS", "Base64 decode failed").await;
            }
        }
        return;
    }

    let pending = PendingUpload {
        buffer_id,
        offset_bytes,
        chunk_bytes,
        command_id: command.id.clone(),
    };

    let mut already_pending = false;
    {
        let mut state_guard = state.lock().await;
        if let Some(client) = state_guard.clients.get_mut(&client_id) {
            if client.pending_upload.is_some() {
                already_pending = true;
            } else {
                client.pending_upload = Some(pending.clone());
            }
        }
    }

    if already_pending {
        send_error_response(
            state,
            client_id,
            &command.id,
            "ERR_BUFFER_UPLOAD_CONFLICT",
            "Previous buffer upload is still pending; wait for it to finish.",
        )
        .await;
        return;
    }

    schedule_upload_timeout(state.clone(), client_id, pending);
}

/// Handle shared memory buffer upload (local optimization for large data).
/// Python writes data to shared memory, we read it directly without network transfer.
async fn handle_load_buffer_shm(state: &SharedState, client_id: usize, command: &CommandEnvelope) {
    send_error_response(state, client_id, &command.id, "ERR_UNSUPPORTED", "Shared memory upload disabled; use chunked WebSocket upload").await;
}

async fn forward_upload(state: &SharedState, buffer_id: &str, offset: usize, data: &[u8], scene: Option<&str>) {
    // Self-contained packets cannot be paired with another client's binary frame.
    for (i, chunk) in data.chunks(1024 * 1024).enumerate() {
        forward_text_to_viewers(state, json!({"type":"cmd", "name":"upload_buffer_chunk", "args":{
            "buffer_id":buffer_id,"offset_bytes":offset + i * 1024 * 1024,
            "chunk_bytes":chunk.len(),"data_base64":BASE64.encode(chunk)
        }}), scene, None).await;
    }
}

async fn handle_mapping_updates(state: &SharedState, client_id: usize, command: &CommandEnvelope, result: &Value) {
    if command.name == "create_scene" {
        if let Some(scene_id) = result.get("scene_id").and_then(|v| v.as_str()) {
            let mut state_guard = state.lock().await;
            if let Some(client) = state_guard.clients.get_mut(&client_id) {
                if client.client_type == ClientType::Protocol {
                    client.scene_refs.insert(scene_id.to_string());
                }
            }
        }
    }
    if command.name == "create_view" || command.name == "attach_scene" {
        let view_id = result.get("view_id").and_then(|v| v.as_str());
        let scene_id = result.get("scene_id").and_then(|v| v.as_str());
        if let (Some(view_id), Some(scene_id)) = (view_id, scene_id) {
            {
                let mut state_guard = state.lock().await;
                state_guard.view_to_scene.insert(view_id.to_string(), scene_id.to_string());
                if let Some(client) = state_guard.clients.get_mut(&client_id) {
                    if client.client_type == ClientType::Protocol {
                        client.scene_refs.insert(scene_id.to_string());
                    }
                }
            }
            let recipients = {
                let mut guard = state.lock().await;
                let mut ids: Vec<usize> = guard.clients.iter()
                    .filter(|(_, c)| c.authenticated && c.client_type == ClientType::Viewer && c.view_id.as_deref() == Some(view_id))
                    .map(|(id, _)| *id).collect();
                if ids.is_empty() {
                    if let Some((&id, _)) = guard.clients.iter().find(|(_, c)| c.authenticated && c.client_type == ClientType::Viewer && c.view_id.is_none()) {
                        ids.push(id);
                    }
                }
                for id in &ids {
                    let client = guard.clients.get_mut(id).unwrap();
                    client.view_id = Some(view_id.to_string());
                    client.scene_id = Some(scene_id.to_string());
                }
                ids
            };
            for recipient in recipients {
                let _ = send_init_and_snapshot(state, recipient, view_id, scene_id).await;
                broadcast_event_to_protocol(state, "viewer_ready", json!({ "view_id": view_id, "scene_id": scene_id })).await;
            }
        }
    }

    if command.name == "destroy_scene" {
        if let Some(scene_id) = command.args.get("scene_id").and_then(|v| v.as_str()) {
            let mut state_guard = state.lock().await;
            let removed_views: HashSet<String> = state_guard
                .view_to_scene
                .iter()
                .filter(|(_, value)| value.as_str() == scene_id)
                .map(|(view_id, _)| view_id.clone())
                .collect();
            state_guard
                .view_to_scene
                .retain(|_, value| value != scene_id);
            for client in state_guard.clients.values_mut() {
                if let Some(view_id) = &client.view_id {
                    if removed_views.contains(view_id) {
                        client.scene_id = None;
                    }
                }
                client.scene_refs.remove(scene_id);
            }
        }
    }

    if command.name == "destroy_view" {
        if let Some(view_id) = command.args.get("view_id").and_then(|v| v.as_str()) {
            let mut state_guard = state.lock().await;
            state_guard.view_to_scene.remove(view_id);
            for client in state_guard.clients.values_mut() {
                if client.view_id.as_deref() == Some(view_id) {
                    client.scene_id = None;
                }
            }
        }
    }
}

async fn forward_sync_to_viewers(
    state: &SharedState,
    command: &CommandEnvelope,
    result: &Value,
    target_scene_id: Option<&str>,
    target_view_id: Option<&str>,
) {
    // Host-only reads have no viewer side effects or synchronization frames.
    if (command.name.starts_with("get_") || command.name.starts_with("list_") || command.name.starts_with("is_"))
        && !matches!(command.name.as_str(), "get_camera_pose" | "get_pick_config" | "get_picked_info") { return; }
    // Uploads stay on Host until attached to geometry. Never broadcast unrelated producer buffers.
    if matches!(command.name.as_str(), "create_buffer" | "free_buffer") { return; }
    if matches!(command.name.as_str(), "add_points" | "add_lines" | "add_mesh" | "add_instances" | "update_instances") {
        let buffers = { state.lock().await.host.command_buffers(&command.args) };
        for (id, info, bytes) in buffers {
            forward_text_to_viewers(state, json!({"type":"sync","command":"create_buffer","args":info,"result":{"buffer_id":id}}), target_scene_id, target_view_id).await;
            forward_upload(state, &id, 0, &bytes, target_scene_id).await;
        }
    }
    let revision = { state.lock().await.revision };
    let message = json!({
        "revision": revision,
        "type": "sync",
        "command": command.name,
        "args": command.args.clone(),
        "result": result.clone()
    });
    forward_text_to_viewers(state, message, target_scene_id, target_view_id).await;
}



async fn forward_text_to_viewers(
    state: &SharedState,
    message: Value,
    target_scene_id: Option<&str>,
    target_view_id: Option<&str>,
) {
    let senders = {
        let state_guard = state.lock().await;
        state_guard
            .clients
            .values()
            .filter_map(|client| {
                if client.client_type != ClientType::Viewer || !client.authenticated {
                    return None;
                }
                if let Some(view_id) = target_view_id {
                    if client.view_id.as_deref() != Some(view_id) {
                        return None;
                    }
                } else if let Some(scene_id) = target_scene_id {
                    let view_id = client.view_id.as_deref()?;
                    let mapped_scene = state_guard.view_to_scene.get(view_id)?;
                    if mapped_scene != scene_id {
                        return None;
                    }
                }
                Some(client.sender.clone())
            })
            .collect::<Vec<_>>()
    };
    let text = message.to_string();
    for sender in senders {
        let _ = sender.send(Message::Text(text.clone())).await;
    }
}


async fn broadcast_event_to_protocol(state: &SharedState, name: &str, data: Value) {
    let payload = json!({
        "protocol_version": PROTOCOL_VERSION,
        "type": "event",
        "name": name,
        "data": data
    });
    let senders = {
        let state_guard = state.lock().await;
        state_guard
            .clients
            .values()
            .filter(|client| client.client_type == ClientType::Protocol && client.authenticated)
            .map(|client| client.sender.clone())
            .collect::<Vec<_>>()
    };
    let text = payload.to_string();
    for sender in senders {
        let _ = sender.send(Message::Text(text.clone())).await;
    }
}

async fn send_init_and_snapshot(
    state: &SharedState,
    client_id: usize,
    view_id: &str,
    scene_id: &str,
) -> Result<(), HostError> {
    let sender = {
        let guard = state.lock().await;
        let client = guard.clients.get(&client_id)
            .filter(|c| c.authenticated && c.client_type == ClientType::Viewer
                && c.view_id.as_deref() == Some(view_id) && c.scene_id.as_deref() == Some(scene_id))
            .ok_or_else(|| HostError::new("ERR_INVALID_SCOPE", "Authenticated viewer binding required"))?;
        client.sender.clone()
    };
    let init_msg = json!({
        "type": "init",
        "view_id": view_id,
        "scene_id": scene_id
    });
    let _ = sender.send(Message::Text(init_msg.to_string())).await;

    let (snapshot, binaries) = {
        let state_guard = state.lock().await;
        let snapshot = state_guard.host.build_scene_snapshot(scene_id)?;
        let binaries = collect_snapshot_binaries(&state_guard, &snapshot);
        (snapshot, binaries)
    };

    let (view_state, revision) = { let guard = state.lock().await; (guard.host.view_snapshot(view_id), guard.revision) };
    let snapshot_msg = json!({
        "type": "scene_snapshot",
        "revision": revision,
        "scene_id": snapshot.scene_id,
        "objects": snapshot.objects,
        "buffers": snapshot.buffers,
        "view_config": view_state.get("view_config"),
        "camera_controls": view_state.get("camera_controls"),
        "overlays": view_state.get("overlays"),
        "camera_pose": view_state.get("camera_pose")
    });
    let _ = sender.send(Message::Text(snapshot_msg.to_string())).await;

    for (buffer_id, data) in binaries {
        for (i, chunk) in data.chunks(1024 * 1024).enumerate() {
            let message = json!({"type":"cmd","name":"upload_buffer_chunk","args":{
                "buffer_id":buffer_id,"offset_bytes":i * 1024 * 1024,"chunk_bytes":chunk.len(),"data_base64":BASE64.encode(chunk)
            }});
            let _ = sender.send(Message::Text(message.to_string())).await;
        }
    }

    Ok(())
}

fn collect_snapshot_binaries(state: &ServerState, snapshot: &SceneSnapshot) -> Vec<(String, Vec<u8>)> {
    let mut result = Vec::new();
    for (buffer_id, info) in &snapshot.buffers {
        if info.data_base64.is_some() {
            continue;
        }
        if let Some(data) = state.host.get_buffer_data(buffer_id) {
            result.push((buffer_id.clone(), data));
        }
    }
    result
}

async fn send_ok_response(state: &SharedState, client_id: usize, id: &str, result: Value) {
    let payload = json!({
        "protocol_version": PROTOCOL_VERSION,
        "type": "resp",
        "id": id,
        "ok": true,
        "result": result,
        "error": null
    });
    send_to_client(state, client_id, Message::Text(payload.to_string())).await;
}

async fn send_error_response(
    state: &SharedState,
    client_id: usize,
    id: &str,
    code: &str,
    message: &str,
) {
    let payload = json!({
        "protocol_version": PROTOCOL_VERSION,
        "type": "resp",
        "id": id,
        "ok": false,
        "result": null,
        "error": { "code": code, "message": message }
    });
    send_to_client(state, client_id, Message::Text(payload.to_string())).await;
}

// P0-2: Send authentication response
async fn send_auth_response(state: &SharedState, client_id: usize, success: bool, error_msg: Option<&str>) {
    let payload = if success {
        json!({
            "protocol_version": PROTOCOL_VERSION,
            "type": "auth_resp",
            "ok": true
        })
    } else {
        json!({
            "protocol_version": PROTOCOL_VERSION,
            "type": "auth_resp",
            "ok": false,
            "error": error_msg.unwrap_or("Authentication failed")
        })
    };
    send_to_client(state, client_id, Message::Text(payload.to_string())).await;
}

async fn send_to_client(state: &SharedState, client_id: usize, message: Message) {
    let sender = {
        let state_guard = state.lock().await;
        state_guard
            .clients
            .get(&client_id)
            .map(|client| client.sender.clone())
    };
    if let Some(sender) = sender {
        if sender.send(message).await.is_err() {
            log_event(state, "warn", "client_backpressure_disconnect", json!({ "client_id": client_id })).await;
        }
    }
}

async fn log_event(state: &SharedState, level: &str, msg: &str, fields: Value) {
    let writer = {
        let guard = state.lock().await;
        guard.log_writer.clone()
    };
    if let Some(writer) = writer {
        writer.log(level, msg, fields);
    }
}

fn parse_command_envelope(value: &Value) -> Option<CommandEnvelope> {
    if value.get("type").and_then(|v| v.as_str()) != Some("cmd") {
        return None;
    }
    let id = value.get("id").and_then(|v| v.as_str())?.to_string();
    let name = value.get("name").and_then(|v| v.as_str())?.to_string();
    let args = value.get("args").cloned().unwrap_or_else(|| json!({}));
    if !args.is_object() { return None; }
    Some(CommandEnvelope { id, name, args })
}

fn parse_client_hello(req: &Request) -> ClientHello {
    let mut hello = ClientHello::default();
    if let Some(query) = req.uri().query() {
        for (key, value) in form_urlencoded::parse(query.as_bytes()) {
            match key.as_ref() {
                "type" => {
                    if value == "viewer" {
                        hello.client_type = ClientType::Viewer;
                    }
                }
                "view_id" => {
                    hello.view_id = Some(value.to_string());
                }
                _ => {}
            }
        }
    }
    hello
}

#[derive(Default)]
struct ClientHello {
    client_type: ClientType,
    view_id: Option<String>,
    scene_id: Option<String>,
}

impl Default for ClientType {
    fn default() -> Self {
        ClientType::Protocol
    }
}

#[derive(Clone)]
struct CommandEnvelope {
    id: String,
    name: String,
    args: Value,
}

fn schedule_upload_timeout(state: SharedState, client_id: usize, pending: PendingUpload) {
    tokio::spawn(async move {
        time::sleep(Duration::from_millis(BUFFER_UPLOAD_TIMEOUT_MS)).await;
        let mut should_timeout = false;
        {
            let mut state_guard = state.lock().await;
            if let Some(client) = state_guard.clients.get_mut(&client_id) {
                if let Some(existing) = &client.pending_upload {
                    if existing.command_id == pending.command_id {
                        client.pending_upload = None;
                        should_timeout = true;
                    }
                }
            }
        }
        if should_timeout {
            send_error_response(
                &state,
                client_id,
                &pending.command_id,
                "ERR_BUFFER_UPLOAD_TIMEOUT",
                "Binary frame not received within 2000ms",
            )
            .await;
        }
    });
}

fn chrono_stamp() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

fn now_ms() -> u64 {
    chrono_stamp()
}

fn resolve_log_path(port: u16) -> Option<PathBuf> {
    if let Ok(value) = std::env::var("FRAMEVIZ_LOG_DIR") {
        let dir = PathBuf::from(value);
        return Some(dir.join(format!("frameviz_ws_{}_{}.log", std::process::id(), port)));
    }

    let base = std::env::var_os("FRAMEVIZ_HOME").map(PathBuf::from)
        .or_else(|| home_dir().map(|home| home.join(".local/share/qqfly/frameviz")));
    base.map(|dir| dir.join(format!("frameviz_ws_{}_{}.log", std::process::id(), port)))
}

pub fn resolve_discovery_path() -> Option<PathBuf> {
    if let Ok(value) = std::env::var("FRAMEVIZ_DISCOVERY_PATH") {
        return Some(PathBuf::from(value));
    }

    if let Some(base) = std::env::var_os("FRAMEVIZ_HOME") {
        return Some(PathBuf::from(base).join("host.json"));
    }
    if cfg!(target_os = "macos") {
        return home_dir()
            .map(|home| home.join(".local/share/qqfly/frameviz").join("host.json"));
    }
    if cfg!(target_os = "windows") {
        return std::env::var("LOCALAPPDATA")
            .or_else(|_| std::env::var("APPDATA"))
            .ok()
            .map(|base| PathBuf::from(base).join("qqfly").join("FrameViz").join("host.json"));
    }
    // Linux: use ~/.frameviz/host.json (consistent with macOS)
    home_dir().map(|home| home.join(".local/share/qqfly/frameviz").join("host.json"))
}

fn write_discovery_file(
    path: &PathBuf,
    port: u16,
    log_path: Option<&PathBuf>,
    auth_token: &str,
    http_port: Option<u16>,
) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut payload = json!({
        "port": port,
        "host": "127.0.0.1",
        "ws_url": format!("ws://127.0.0.1:{}", port),
        "pid": std::process::id(),
        "started_at_ms": now_ms(),
        "log": log_path.map(|p| p.to_string_lossy().to_string()),
        "version": PROTOCOL_VERSION,
        "token": auth_token,  // P0-2: Authentication token
    });

    // Add HTTP port for browser mode support
    if let Some(http_port) = http_port {
        payload["http_port"] = json!(http_port);
        payload["viewer_url"] = json!(format!("http://127.0.0.1:{}/", http_port));
    }

    fs::write(path, payload.to_string())?;
    apply_restrictive_discovery_permissions(path)?;

    if let Some(http_port) = http_port {
        println!("[FrameViz] Viewer URL: http://127.0.0.1:{http_port}/?ws_port={port}#token={auth_token}");
    }

    Ok(())
}

fn apply_restrictive_discovery_permissions(path: &PathBuf) -> std::io::Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let perms = std::fs::Permissions::from_mode(0o600);
        fs::set_permissions(path, perms)?;
    }

    Ok(())
}

fn rotate_log_if_needed(path: &PathBuf) {
    let Ok(metadata) = fs::metadata(path) else {
        return;
    };
    const MAX_BYTES: u64 = 20 * 1024 * 1024;
    if metadata.len() <= MAX_BYTES {
        return;
    }
    let rotated = path.with_extension(format!("log.{}", now_ms()));
    let _ = fs::rename(path, rotated);
}

fn home_dir() -> Option<PathBuf> {
    if let Ok(home) = std::env::var("HOME") {
        return Some(PathBuf::from(home));
    }
    std::env::var("USERPROFILE").ok().map(PathBuf::from)
}

/// Check if a FrameViz server is already running by reading the discovery file.
/// Returns the WebSocket port if a valid server is running.
pub fn discovery_port_if_running() -> Option<u16> {
    let path = resolve_discovery_path()?;
    let text = fs::read_to_string(&path).ok()?;
    let data: Value = serde_json::from_str(&text).ok()?;

    // Verify protocol version matches
    let version = data.get("version").and_then(|v| v.as_str())?;
    if version != PROTOCOL_VERSION {
        // Version mismatch - clean up stale file
        let _ = fs::remove_file(&path);
        return None;
    }

    let port = data.get("port").and_then(|v| v.as_u64())? as u16;
    let pid = data.get("pid").and_then(|v| v.as_u64())? as u32;

    if !pid_is_running(pid) {
        // PID not running - clean up stale file
        let _ = fs::remove_file(&path);
        return None;
    }

    // Check if the port is actually responding
    let addr = format!("127.0.0.1:{}", port);
    let timeout = StdDuration::from_millis(200);
    if StdTcpStream::connect_timeout(&addr.parse().ok()?, timeout).is_ok() {
        return Some(port);
    }

    // Port not responding but PID exists - could be a stale file or the process
    // crashed after writing the file. Clean up.
    let _ = fs::remove_file(&path);
    None
}

/// Update the discovery file with HTTP server port information.
/// This should be called after starting the HTTP server.
pub fn update_discovery_http_port(http_port: u16) -> Result<(), String> {
    let path = resolve_discovery_path().ok_or("no discovery path")?;
    if !path.exists() {
        return Err("discovery file does not exist".to_string());
    }

    let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let mut data: Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;

    // Add HTTP port information
    data["http_port"] = json!(http_port);
    data["viewer_url"] = json!(format!("http://127.0.0.1:{}/", http_port));

    fs::write(&path, data.to_string()).map_err(|e| e.to_string())?;
    apply_restrictive_discovery_permissions(&path).map_err(|e| e.to_string())?;
    println!("[FrameViz] Updated discovery file with HTTP port: {}", http_port);
    Ok(())
}

/// Clean up stale discovery file if it exists.
/// This should be called at startup to handle cases where the previous
/// process crashed without cleaning up.
pub fn cleanup_stale_discovery() {
    let Some(path) = resolve_discovery_path() else {
        return;
    };

    if !path.exists() {
        return;
    }

    let text = match fs::read_to_string(&path) {
        Ok(t) => t,
        Err(_) => {
            // Can't read - try to remove
            let _ = fs::remove_file(&path);
            return;
        }
    };

    let data: Value = match serde_json::from_str(&text) {
        Ok(d) => d,
        Err(_) => {
            // Invalid JSON - remove
            let _ = fs::remove_file(&path);
            return;
        }
    };

    // Check version
    let version = data.get("version").and_then(|v| v.as_str()).unwrap_or("");
    if version != PROTOCOL_VERSION {
        println!("[FrameViz] Cleaning up stale discovery file (version mismatch: {} vs {})", version, PROTOCOL_VERSION);
        let _ = fs::remove_file(&path);
        return;
    }

    // Check PID
    let pid = data.get("pid").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
    if pid == 0 || !pid_is_running(pid) {
        println!("[FrameViz] Cleaning up stale discovery file (PID {} not running)", pid);
        let _ = fs::remove_file(&path);
        return;
    }

    // Check port connectivity
    let port = data.get("port").and_then(|v| v.as_u64()).unwrap_or(0) as u16;
    if port > 0 {
        let addr = format!("127.0.0.1:{}", port);
        let timeout = StdDuration::from_millis(200);
        if StdTcpStream::connect_timeout(&addr.parse().unwrap(), timeout).is_err() {
            println!("[FrameViz] Cleaning up stale discovery file (port {} not responding)", port);
            let _ = fs::remove_file(&path);
        }
    }
}

#[cfg(unix)]
fn pid_is_running(pid: u32) -> bool {
    if pid == 0 {
        return false;
    }
    let result = unsafe { libc::kill(pid as libc::pid_t, 0) };
    if result == 0 {
        return true;
    }
    let err = std::io::Error::last_os_error();
    matches!(err.raw_os_error(), Some(libc::EPERM))
}

#[cfg(not(unix))]
fn pid_is_running(_pid: u32) -> bool {
    true
}

// P0-2: Generate cryptographically secure authentication token
fn generate_auth_token() -> String {
    use rand::RngCore;
    
    let mut bytes = [0u8; AUTH_TOKEN_LENGTH];
    rand::rngs::OsRng.fill_bytes(&mut bytes);
    
    // Convert to hex string
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

/// Read this user's local credential only when it belongs to the selected endpoint.
pub fn local_auth_token(port: u16) -> Option<String> {
    let path = resolve_discovery_path()?;
    let value: Value = serde_json::from_str(&fs::read_to_string(path).ok()?).ok()?;
    let url = url::Url::parse(value.get("ws_url")?.as_str()?).ok()?;
    if url.port() != Some(port) { return None; }
    value.get("token")?.as_str().map(str::to_owned)
}

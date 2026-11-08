use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

use crate::AppState;

static ACTIVE_CLIENTS: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
const DEFAULT_CONTROL_PORT: u16 = 9528;
const READ_TIMEOUT: Duration = Duration::from_secs(2);
const WRITE_TIMEOUT: Duration = Duration::from_secs(2);

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
struct ControlRequest {
    action: String,
    token: Option<String>,
    view_id: Option<String>,
    scene_id: Option<String>,
    title: Option<String>,
    width: Option<u32>,
    height: Option<u32>,
    x: Option<i32>,
    y: Option<i32>,
    page: Option<String>,
    performance_mode: Option<String>,
    decorations: Option<bool>,
}

#[derive(Debug, Serialize)]
struct ControlResponse {
    ok: bool,
    status: Option<String>,
    error: Option<String>,
}

pub fn control_port_from_env() -> u16 {
    std::env::var("FRAMEVIZ_TAURI_CONTROL_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(DEFAULT_CONTROL_PORT)
}

pub fn start_control_server(app: AppHandle, port: u16) {
    let addr = format!("127.0.0.1:{}", port);
    thread::spawn(move || {
        let listener = match TcpListener::bind(&addr) {
            Ok(listener) => listener,
            Err(err) => {
                eprintln!(
                    "[FrameViz] Control server failed to bind {}: {}",
                    addr, err
                );
                return;
            }
        };

        println!("[FrameViz] Control server listening on {}", addr);

        for stream in listener.incoming() {
            match stream {
                Ok(stream) => {
                    if ACTIVE_CLIENTS.fetch_add(1, std::sync::atomic::Ordering::SeqCst) >= 16 {
                        ACTIVE_CLIENTS.fetch_sub(1, std::sync::atomic::Ordering::SeqCst);
                        continue;
                    }
                    let app_handle = app.clone();
                    thread::spawn(move || {
                        if let Err(err) = handle_client(app_handle, stream) {
                            eprintln!("[FrameViz] Control server error: {}", err);
                        }
                        ACTIVE_CLIENTS.fetch_sub(1, std::sync::atomic::Ordering::SeqCst);
                    });
                }
                Err(err) => {
                    eprintln!("[FrameViz] Control server accept error: {}", err);
                }
            }
        }
    });
}

fn handle_client(app: AppHandle, mut stream: TcpStream) -> Result<(), String> {
    let _ = stream.set_read_timeout(Some(READ_TIMEOUT));
    let _ = stream.set_write_timeout(Some(WRITE_TIMEOUT));

    let mut reader = BufReader::new(
        stream
            .try_clone()
            .map_err(|err| format!("clone stream failed: {}", err))?,
    );

    let mut line = String::new();
    let bytes = reader.by_ref().take(65537)
        .read_line(&mut line)
        .map_err(|err| format!("read request failed: {}", err))?;
    if bytes > 65536 { return Err("Control request too large".into()); }
    if bytes == 0 {
        return Ok(());
    }

    let request: ControlRequest =
        serde_json::from_str(line.trim()).map_err(|err| format!("bad request: {}", err))?;

    let response = match handle_request(&app, request) {
        Ok(status) => ControlResponse {
            ok: true,
            status: Some(status),
            error: None,
        },
        Err(error) => ControlResponse {
            ok: false,
            status: None,
            error: Some(error),
        },
    };

    let payload =
        serde_json::to_string(&response).map_err(|err| format!("encode response: {}", err))?;
    stream
        .write_all(payload.as_bytes())
        .map_err(|err| format!("write response: {}", err))?;
    stream
        .write_all(b"\n")
        .map_err(|err| format!("write newline: {}", err))?;

    Ok(())
}

fn handle_request(app: &AppHandle, request: ControlRequest) -> Result<String, String> {
    if request.action != "ping" {
        let expected = frameviz_server::websocket::local_auth_token(app.state::<AppState>().ws_port);
        if expected.is_none() || request.token != expected { return Err("Authentication required".into()); }
    }
    match request.action.as_str() {
        "ping" => Ok("pong".to_string()),
        "open_view" => {
            let view_id = request
                .view_id
                .ok_or_else(|| "missing view_id".to_string())?;
            open_view_window(
                app,
                view_id,
                request.scene_id,
                request.title,
                request.width,
                request.height,
                request.x,
                request.y,
                request.page,
                request.performance_mode,
                request.decorations,
            )
        }
        "configure_view" => {
            let view_id = request
                .view_id
                .ok_or_else(|| "missing view_id".to_string())?;
            configure_view_window(
                app,
                view_id,
                request.title,
                request.width,
                request.height,
                request.x,
                request.y,
            )
        }
        "close_view" => {
            let view_id = request
                .view_id
                .ok_or_else(|| "missing view_id".to_string())?;
            close_view_window(app, view_id)
        }
        _ => Err(format!("unknown action: {}", request.action)),
    }
}

/// Helper function to configure a WebviewWindowBuilder with common settings
fn configure_window_builder<'a, R: tauri::Runtime, M: tauri::Manager<R>>(
    builder: WebviewWindowBuilder<'a, R, M>,
    title: &str,
    init_script: &str,
    decorations: bool,
    width: Option<u32>,
    height: Option<u32>,
    x: Option<i32>,
    y: Option<i32>,
) -> WebviewWindowBuilder<'a, R, M> {
    let mut builder = builder
        .title(title)
        .initialization_script(init_script)
        .decorations(decorations);

    if let (Some(w), Some(h)) = (width, height) {
        builder = builder.inner_size(w as f64, h as f64);
    }
    if let (Some(x_pos), Some(y_pos)) = (x, y) {
        builder = builder.position(x_pos as f64, y_pos as f64);
    }
    builder
}

pub fn open_view_window(
    app: &AppHandle,
    view_id: String,
    scene_id: Option<String>,
    title: Option<String>,
    width: Option<u32>,
    height: Option<u32>,
    x: Option<i32>,
    y: Option<i32>,
    page: Option<String>,
    performance_mode: Option<String>,
    decorations: Option<bool>,
) -> Result<String, String> {
    let label = window_label_for_view(&view_id);
    let ws_port = app.state::<AppState>().ws_port;
    let init_script = build_view_init_script(&view_id, scene_id.as_deref(), ws_port, performance_mode.as_deref());

    if let Some(window) = app.get_webview_window(&label) {
        if let Some(ref page) = page {
            let path = build_view_path(&view_id, Some(page));
            if let Ok(path_json) = serde_json::to_string(&path) {
                let script = format!("window.location.replace({path_json});");
                let _ = window.eval(&script);
            }
        }
        if let Some(title) = title.as_ref() {
            let _ = window.set_title(title);
        }
        if let (Some(width), Some(height)) = (width, height) {
            let _ = window.set_size(tauri::Size::Physical(tauri::PhysicalSize {
                width: width as u32,
                height: height as u32,
            }));
        }
        if let (Some(x), Some(y)) = (x, y) {
            let _ = window.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
                x,
                y,
            }));
        }
        let _ = window.show();
        let _ = window.set_focus();
        return Ok("focused".to_string());
    }

    let url = window_url_for_view(&view_id, page.as_deref());

    // Apply decorations setting (default: true)
    let decorations = decorations.unwrap_or(true);
    let title_str = title.clone().unwrap_or_else(|| "FrameViz".to_string());

    // Create window with specified settings
    let builder = configure_window_builder(
        WebviewWindowBuilder::new(app, &label, url.clone()),
        &title_str,
        &init_script,
        decorations,
        width,
        height,
        x,
        y,
    );

    // Try to create window, with fallback for decorations=false
    match builder.build() {
        Ok(_) => {
            eprintln!("[FrameViz] Created window '{}' with decorations={}, position={:?}", view_id, decorations, x.and_then(|x| Some((x, y.unwrap_or(0)))));
            Ok("created".to_string())
        },
        Err(err) => {
            // If decorations=false failed, try again with decorations=true
            if !decorations {
                eprintln!("[FrameViz] Warning: Platform does not support frameless window for '{}': {}. Falling back to decorated window.", view_id, err);
                let fallback_builder = configure_window_builder(
                    WebviewWindowBuilder::new(app, &label, url),
                    &title_str,
                    &init_script,
                    true, // Force decorations=true for fallback
                    width,
                    height,
                    x,
                    y,
                );

                match fallback_builder.build() {
                    Ok(_) => {
                        eprintln!("[FrameViz] Created window '{}' with fallback decorations=true", view_id);
                        Ok("created".to_string())
                    },
                    Err(err2) => {
                        let error_msg = format!("Failed to create window '{}': frameless window failed ({}), fallback to decorated window also failed: {}", view_id, err, err2);
                        eprintln!("[FrameViz] Error: {}", error_msg);
                        Err(error_msg)
                    }
                }
            } else {
                let error_msg = format!("Failed to create window '{}': {}", view_id, err);
                eprintln!("[FrameViz] Error: {}", error_msg);
                Err(error_msg)
            }
        }
    }
}

fn configure_view_window(
    app: &AppHandle,
    view_id: String,
    title: Option<String>,
    width: Option<u32>,
    height: Option<u32>,
    x: Option<i32>,
    y: Option<i32>,
) -> Result<String, String> {
    let label = window_label_for_view(&view_id);
    if let Some(window) = app.get_webview_window(&label) {
        if let Some(title) = title.as_ref() {
            let _ = window.set_title(title);
        }
        if let (Some(width), Some(height)) = (width, height) {
            let _ = window.set_size(tauri::Size::Physical(tauri::PhysicalSize {
                width: width as u32,
                height: height as u32,
            }));
        }
        if let (Some(x), Some(y)) = (x, y) {
            let _ = window.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
                x,
                y,
            }));
        }
        return Ok("configured".to_string());
    }
    Err("window not found".to_string())
}

fn close_view_window(app: &AppHandle, view_id: String) -> Result<String, String> {
    let label = window_label_for_view(&view_id);
    if let Some(window) = app.get_webview_window(&label) {
        window
            .close()
            .map_err(|err| format!("close window: {}", err))?;
        return Ok("closed".to_string());
    }

    if let Some(main_view_id) = app.state::<AppState>().view_id() {
        if main_view_id == view_id {
            if let Some(window) = app.get_webview_window("main") {
                window
                    .close()
                    .map_err(|err| format!("close window: {}", err))?;
                return Ok("closed".to_string());
            }
        }
    }

    Err("window not found".to_string())
}

fn window_label_for_view(view_id: &str) -> String {
    format!("view_{}", sanitize_label(view_id))
}

fn window_url_for_view(view_id: &str, page: Option<&str>) -> WebviewUrl {
    WebviewUrl::App(build_view_path(view_id, page).into())
}

fn build_view_path(view_id: &str, page: Option<&str>) -> String {
    let mut path = page.unwrap_or("index.html").trim_start_matches('/').to_string();
    if !path.contains("view_id=") {
        let sep = if path.contains('?') { "&" } else { "?" };
        path.push_str(sep);
        path.push_str("view_id=");
        path.push_str(view_id);
    }
    path
}

fn build_view_init_script(view_id: &str, scene_id: Option<&str>, ws_port: u16, performance_mode: Option<&str>) -> String {
    let token_json = serde_json::to_string(&frameviz_server::websocket::local_auth_token(ws_port)).unwrap_or_else(|_| "null".into());
    let view_id_json = serde_json::to_string(view_id).unwrap_or_else(|_| "\"v_1\"".to_string());
    let scene_id_json = scene_id
        .map(|s| serde_json::to_string(s).unwrap_or_else(|_| "null".to_string()))
        .unwrap_or_else(|| "null".to_string());
    let ws_port_json = serde_json::to_string(&ws_port).unwrap_or_else(|_| "9527".to_string());
    let perf_mode_json = performance_mode
        .map(|mode| serde_json::to_string(mode).unwrap_or_else(|_| "null".to_string()))
        .unwrap_or_else(|| "null".to_string());

    format!(
        r#"(function() {{
  const viewId = {view_id_json};
  const sceneId = {scene_id_json};
  const perfMode = {perf_mode_json};
  window.__FRAMEVIZ_VIEW_ID__ = viewId;
  window.__FRAMEVIZ_SCENE_ID__ = sceneId;
  window.__FRAMEVIZ_WS_PORT__ = {ws_port_json};
  window.__FRAMEVIZ_AUTH_TOKEN__ = {token_json};
  window.__FRAMEVIZ_PERFORMANCE_MODE__ = perfMode;
  const params = new URLSearchParams(window.location.search);
  if (!params.get("view_id")) {{
    params.set("view_id", viewId);
    if (perfMode) {{
      params.set("performance_mode", perfMode);
    }}
    const newUrl = window.location.pathname + "?" + params.toString() + window.location.hash;
    window.location.replace(newUrl);
  }}
}})();"#
    )
}

fn sanitize_label(value: &str) -> String {
    let mut out = String::new();
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() || ch == '-' || ch == '_' {
            out.push(ch);
        } else {
            out.push('_');
        }
    }
    if out.is_empty() {
        out.push_str("view");
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_label_valid_chars() {
        assert_eq!(sanitize_label("abc123"), "abc123");
        assert_eq!(sanitize_label("test-view"), "test-view");
        assert_eq!(sanitize_label("test_view"), "test_view");
    }

    #[test]
    fn test_sanitize_label_special_chars() {
        assert_eq!(sanitize_label("test.view"), "test_view");
        assert_eq!(sanitize_label("test view"), "test_view");
        assert_eq!(sanitize_label("test/view"), "test_view");
    }

    #[test]
    fn test_sanitize_label_empty() {
        // Empty string becomes "view"
        assert_eq!(sanitize_label(""), "view");
        // Special chars are replaced with underscores, not removed
        assert_eq!(sanitize_label("..."), "___");
    }

    #[test]
    fn test_window_label_for_view() {
        assert_eq!(window_label_for_view("v_1"), "view_v_1");
        assert_eq!(window_label_for_view("test.view"), "view_test_view");
    }

    #[test]
    fn test_build_view_path() {
        assert_eq!(build_view_path("v_1", None), "index.html?view_id=v_1");
        assert_eq!(build_view_path("v_2", Some("custom.html")), "custom.html?view_id=v_2");
        assert_eq!(build_view_path("v_3", Some("/path/page.html")), "path/page.html?view_id=v_3");
    }

    #[test]
    fn test_build_view_path_with_existing_params() {
        assert_eq!(build_view_path("v_1", Some("index.html?foo=bar")), "index.html?foo=bar&view_id=v_1");
    }

    #[test]
    fn test_control_port_from_env_default() {
        // Clear environment variable and test default
        std::env::remove_var("FRAMEVIZ_TAURI_CONTROL_PORT");
        assert_eq!(control_port_from_env(), 9528);
    }

    #[test]
    fn test_control_port_from_env_custom() {
        std::env::set_var("FRAMEVIZ_TAURI_CONTROL_PORT", "1234");
        assert_eq!(control_port_from_env(), 1234);
        std::env::remove_var("FRAMEVIZ_TAURI_CONTROL_PORT");
    }
}

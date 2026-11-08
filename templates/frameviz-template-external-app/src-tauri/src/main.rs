#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::fs::{self, OpenOptions};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

const APP_TAG: &str = env!("CARGO_PKG_NAME");

#[derive(Default)]
struct BackendProcessState {
    child: Mutex<Option<Child>>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum BackendMode {
    Python,
    Cpp,
}

fn env_true(value: &str) -> bool {
    !matches!(value, "0" | "false" | "False" | "FALSE" | "off" | "OFF")
}

fn should_autostart_backend() -> bool {
    if let Ok(value) = env::var("FRAMEVIZ_AUTOSTART_BACKEND") {
        return env_true(value.trim());
    }
    #[cfg(debug_assertions)]
    {
        false
    }
    #[cfg(not(debug_assertions))]
    {
        true
    }
}

fn command_available(cmd: &str) -> bool {
    Command::new(cmd)
        .arg("--version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .is_ok()
}

fn backend_mode_from_env() -> Option<BackendMode> {
    let raw = env::var("FRAMEVIZ_AUTOSTART_BACKEND_MODE").ok()?;
    match raw.trim().to_lowercase().as_str() {
        "cpp" | "c++" => Some(BackendMode::Cpp),
        "python" | "py" => Some(BackendMode::Python),
        _ => None,
    }
}

fn resolve_backend_mode(app: &tauri::AppHandle) -> BackendMode {
    if let Some(mode) = backend_mode_from_env() {
        return mode;
    }
    if resolve_cpp_backend_binary(app).is_some() {
        return BackendMode::Cpp;
    }
    BackendMode::Python
}

fn resolve_python_command() -> Option<String> {
    if let Ok(raw) = env::var("FRAMEVIZ_PYTHON") {
        let candidate = raw.trim();
        if !candidate.is_empty() {
            let path = PathBuf::from(candidate);
            if path.is_file() {
                return Some(path.to_string_lossy().to_string());
            }
            if command_available(candidate) {
                return Some(candidate.to_string());
            }
        }
    }

    for cmd in ["python3", "python"] {
        if command_available(cmd) {
            return Some(cmd.to_string());
        }
    }
    None
}

fn find_file_recursive(root: &Path, target_name: &str, max_depth: usize) -> Option<PathBuf> {
    if max_depth == 0 {
        return None;
    }
    let entries = fs::read_dir(root).ok()?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_file() {
            if path
                .file_name()
                .and_then(|v| v.to_str())
                .map(|v| v == target_name)
                .unwrap_or(false)
            {
                return Some(path);
            }
            continue;
        }
        if path.is_dir() {
            if let Some(found) = find_file_recursive(&path, target_name, max_depth - 1) {
                return Some(found);
            }
        }
    }
    None
}

fn resolve_cpp_backend_binary(app: &tauri::AppHandle) -> Option<PathBuf> {
    if let Ok(raw) = env::var("FRAMEVIZ_BACKEND_CPP_BIN") {
        let path = PathBuf::from(raw.trim());
        if path.is_file() {
            return Some(path);
        }
    }

    let resource_dir = app.path().resource_dir().ok()?;
    let candidates = vec![
        resource_dir.join("cpp/frameviz_external_backend"),
        resource_dir.join("frameviz_external_backend"),
        resource_dir.join("resources/cpp/frameviz_external_backend"),
    ];

    #[cfg(target_os = "windows")]
    {
        candidates.push(resource_dir.join("cpp/frameviz_external_backend.exe"));
        candidates.push(resource_dir.join("frameviz_external_backend.exe"));
        candidates.push(resource_dir.join("resources/cpp/frameviz_external_backend.exe"));
    }

    for candidate in candidates {
        if candidate.is_file() {
            return Some(candidate);
        }
    }

    #[cfg(target_os = "windows")]
    if let Some(found) = find_file_recursive(&resource_dir, "frameviz_external_backend.exe", 5) {
        return Some(found);
    }

    find_file_recursive(&resource_dir, "frameviz_external_backend", 5)
}

fn resolve_backend_script(app: &tauri::AppHandle) -> Option<PathBuf> {
    if let Ok(raw) = env::var("FRAMEVIZ_BACKEND_SCRIPT") {
        let path = PathBuf::from(raw.trim());
        if path.is_file() {
            return Some(path);
        }
    }

    let resource_dir = app.path().resource_dir().ok()?;
    let direct_candidates = [
        resource_dir.join("python/backend_external_app.py"),
        resource_dir.join("backend_external_app.py"),
        resource_dir.join("resources/python/backend_external_app.py"),
    ];

    for candidate in direct_candidates {
        if candidate.is_file() {
            return Some(candidate);
        }
    }

    find_file_recursive(&resource_dir, "backend_external_app.py", 5)
}

fn backend_log_path() -> Option<PathBuf> {
    let base = env::var_os("FRAMEVIZ_HOME").map(PathBuf::from)
        .or_else(|| env::var_os("HOME").map(|home| PathBuf::from(home).join(".local/share/qqfly/frameviz")))?;
    let dir = base.join(APP_TAG);
    if fs::create_dir_all(&dir).is_err() {
        return None;
    }
    Some(dir.join("backend.log"))
}

fn spawn_backend_process(app: &tauri::AppHandle) -> Result<Child, String> {
    match resolve_backend_mode(app) {
        BackendMode::Cpp => {
            println!("[{}] Backend mode: cpp", APP_TAG);
            spawn_cpp_backend_process(app)
        }
        BackendMode::Python => {
            println!("[{}] Backend mode: python", APP_TAG);
            spawn_python_backend_process(app)
        }
    }
}

fn spawn_python_backend_process(app: &tauri::AppHandle) -> Result<Child, String> {
    let python = resolve_python_command()
        .ok_or("python interpreter not found; set FRAMEVIZ_PYTHON or install python3".to_string())?;
    let script =
        resolve_backend_script(app).ok_or("backend_external_app.py not found in app resources".to_string())?;

    let parent_pid = std::process::id().to_string();
    let mut command = Command::new(&python);
    command.arg(&script);
    command.arg("--parent-pid").arg(&parent_pid);
    command.env("FRAMEVIZ_PARENT_PID", &parent_pid);
    command.env("FRAMEVIZ_EXIT_ON_PARENT_DEATH", "1");
    command.env("PYTHONUNBUFFERED", "1");

    if env::var("FRAMEVIZ_HOST_HEADLESS").is_err() {
        command.env("FRAMEVIZ_HOST_HEADLESS", "1");
    }
    if env::var("FRAMEVIZ_APP_WS_HOST").is_err() {
        command.env("FRAMEVIZ_APP_WS_HOST", "127.0.0.1");
    }
    if env::var("FRAMEVIZ_APP_WS_PORT").is_err() {
        command.env("FRAMEVIZ_APP_WS_PORT", "9621");
    }

    if let Some(log_path) = backend_log_path() {
        if let Ok(file) = OpenOptions::new().create(true).append(true).open(&log_path) {
            if let Ok(file_clone) = file.try_clone() {
                command.stdout(Stdio::from(file_clone));
                command.stderr(Stdio::from(file));
            } else {
                command.stdout(Stdio::null());
                command.stderr(Stdio::null());
            }
            println!("[{}] Backend log: {}", APP_TAG, log_path.display());
        } else {
            command.stdout(Stdio::null());
            command.stderr(Stdio::null());
        }
    } else {
        command.stdout(Stdio::null());
        command.stderr(Stdio::null());
    }

    println!("[{}] Launch Python backend: {} {}", APP_TAG, python, script.display());
    command.spawn().map_err(|e| format!("failed to spawn backend: {e}"))
}

fn spawn_cpp_backend_process(app: &tauri::AppHandle) -> Result<Child, String> {
    let cpp_bin = resolve_cpp_backend_binary(app).ok_or(
        "cpp backend binary not found; set FRAMEVIZ_BACKEND_CPP_BIN or use python mode".to_string(),
    )?;

    let ui_port = env::var("FRAMEVIZ_APP_WS_PORT").unwrap_or_else(|_| "9621".to_string());
    let viewer_name =
        env::var("FRAMEVIZ_APP_VIEWER_NAME").unwrap_or_else(|_| "main_viewer".to_string());
    let frameviz_url = env::var("FRAMEVIZ_HOST").unwrap_or_else(|_| "ws://127.0.0.1:9527".to_string());

    let mut command = Command::new(&cpp_bin);
    command
        .arg("--ui-port")
        .arg(ui_port)
        .arg("--viewer-name")
        .arg(viewer_name)
        .arg("--frameviz-url")
        .arg(frameviz_url);

    if let Some(log_path) = backend_log_path() {
        if let Ok(file) = OpenOptions::new().create(true).append(true).open(&log_path) {
            if let Ok(file_clone) = file.try_clone() {
                command.stdout(Stdio::from(file_clone));
                command.stderr(Stdio::from(file));
            } else {
                command.stdout(Stdio::null());
                command.stderr(Stdio::null());
            }
            println!("[{}] Backend log: {}", APP_TAG, log_path.display());
        } else {
            command.stdout(Stdio::null());
            command.stderr(Stdio::null());
        }
    } else {
        command.stdout(Stdio::null());
        command.stderr(Stdio::null());
    }

    println!("[{}] Launch C++ backend: {}", APP_TAG, cpp_bin.display());
    command.spawn().map_err(|e| format!("failed to spawn cpp backend: {e}"))
}

fn start_backend_if_needed(app: &tauri::AppHandle) {
    if !should_autostart_backend() {
        println!("[{}] Backend autostart disabled", APP_TAG);
        return;
    }

    let state = app.state::<BackendProcessState>();
    let mut guard = match state.child.lock() {
        Ok(guard) => guard,
        Err(_) => {
            eprintln!("[{}] Failed to lock backend process state", APP_TAG);
            return;
        }
    };

    if guard.is_some() {
        return;
    }

    match spawn_backend_process(app) {
        Ok(child) => {
            *guard = Some(child);
            println!("[{}] Backend started", APP_TAG);
        }
        Err(err) => {
            eprintln!("[{}] Backend autostart failed: {err}", APP_TAG);
        }
    }
}

fn stop_backend(app: &tauri::AppHandle) {
    let state = app.state::<BackendProcessState>();
    let mut guard = match state.child.lock() {
        Ok(guard) => guard,
        Err(_) => return,
    };
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
        let _ = child.wait();
        println!("[{}] Backend stopped", APP_TAG);
    }
}

fn main() {
    tauri::Builder::default()
        .manage(BackendProcessState::default())
        .setup(|app| {
            start_backend_if_needed(&app.handle());
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let app = window.app_handle();
                if app.webview_windows().len() <= 1 {
                    stop_backend(&app);
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

//! Per-user welcome state. Runtime discovery and welcome preferences are separate files.
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

pub fn preferences_path() -> Option<PathBuf> {
    frameviz_server::websocket::resolve_discovery_path()
        .and_then(|path| path.parent().map(|parent| parent.join("preferences.json")))
}

pub fn welcome_seen(path: &Path) -> bool {
    fs::read(path).ok()
        .and_then(|bytes| serde_json::from_slice::<serde_json::Value>(&bytes).ok())
        .and_then(|value| value.get("welcome_seen").and_then(|seen| seen.as_bool()))
        .unwrap_or(false)
}

pub fn mark_welcome_seen(path: &Path) -> io::Result<()> {
    let parent = path.parent().ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "preferences need a parent"))?;
    fs::create_dir_all(parent)?;
    let temporary = parent.join(format!(".preferences-{}.tmp", std::process::id()));
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(&temporary)?;
    let result = (|| {
        file.write_all(b"{\"welcome_seen\":true}\n")?;
        file.sync_all()?;
        fs::rename(&temporary, path)
    })();
    if result.is_err() { let _ = fs::remove_file(&temporary); }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn missing_and_invalid_preferences_do_not_suppress_welcome() {
        let directory = std::env::temp_dir().join(format!("frameviz-welcome-invalid-{}", std::process::id()));
        fs::create_dir_all(&directory).unwrap();
        let path = directory.join("preferences.json");
        assert!(!welcome_seen(&path));
        fs::write(&path, b"broken").unwrap();
        assert!(!welcome_seen(&path));
        fs::write(&path, b"{\"welcome_seen\":\"false\"}").unwrap();
        assert!(!welcome_seen(&path));
        fs::remove_dir_all(directory).unwrap();
    }
    #[test]
    fn welcome_state_survives_reload_and_does_not_change_discovery() {
        let directory = std::env::temp_dir().join(format!("frameviz-welcome-save-{}", std::process::id()));
        fs::create_dir_all(&directory).unwrap();
        let discovery = directory.join("host.json");
        fs::write(&discovery, b"synthetic discovery sentinel").unwrap();
        let path = directory.join("preferences.json");
        mark_welcome_seen(&path).unwrap();
        assert!(welcome_seen(&path));
        assert_eq!(fs::read(&discovery).unwrap(), b"synthetic discovery sentinel");
        #[cfg(unix)] {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(fs::metadata(&path).unwrap().permissions().mode() & 0o777, 0o600);
        }
        assert_eq!(fs::read_dir(&directory).unwrap().count(), 2);
        fs::remove_dir_all(directory).unwrap();
    }
}

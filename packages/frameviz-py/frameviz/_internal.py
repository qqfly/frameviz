"""
Internal utilities shared across frameviz modules.

This module contains helper functions and state that are used by both
viz.py and host.py to avoid circular dependencies. All functions are
considered internal (prefixed with _) and should not be imported
directly by external code.
"""

from __future__ import annotations

import atexit
import builtins
import json
import os
import plistlib
import signal
import shlex
import socket
import subprocess
import sys
import time
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

from .client import PROTOCOL_VERSION
from .discovery import get_discovery_path, read_discovery_file

# ─────────────────────────────────────────────────────────────────────────────
# Global state for WebSocket server auto-start
# ─────────────────────────────────────────────────────────────────────────────
_AUTO_WS_PROCESS: Optional[subprocess.Popen] = None
_AUTO_WS_LAST_ERROR: Optional[str] = None
_AUTO_WS_LOG_PATH: Optional[str] = None
_AUTO_WS_LOG_HANDLE: Optional[Any] = None
_AUTO_WS_ATEXIT_REGISTERED: bool = False
_AUTO_WS_PROCESS_GROUP_ID: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket auto-start helpers
# ─────────────────────────────────────────────────────────────────────────────
def _stop_auto_ws_process() -> None:
    """Best-effort cleanup for auto-started ws process."""
    global _AUTO_WS_PROCESS
    global _AUTO_WS_LOG_HANDLE
    global _AUTO_WS_PROCESS_GROUP_ID
    proc = _AUTO_WS_PROCESS
    pgid = _AUTO_WS_PROCESS_GROUP_ID
    _AUTO_WS_PROCESS = None
    _AUTO_WS_PROCESS_GROUP_ID = None

    if proc is not None and proc.poll() is None:
        # On POSIX, terminate the whole process group to avoid orphan children
        # when FRAMEVIZ_WS_SERVER_CMD launches wrappers/scripts.
        sent_group_signal = False
        if pgid is not None and os.name == "posix":
            try:
                os.killpg(pgid, signal.SIGTERM)
                sent_group_signal = True
            except OSError:
                pass
        try:
            if not sent_group_signal:
                proc.terminate()
            proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            if pgid is not None and os.name == "posix":
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
            else:
                try:
                    proc.kill()
                except OSError:
                    pass

    log_handle = _AUTO_WS_LOG_HANDLE
    _AUTO_WS_LOG_HANDLE = None
    if log_handle is not None:
        try:
            log_handle.close()
        except OSError:
            pass


def _register_auto_ws_atexit() -> None:
    global _AUTO_WS_ATEXIT_REGISTERED
    if _AUTO_WS_ATEXIT_REGISTERED:
        return
    _AUTO_WS_ATEXIT_REGISTERED = True
    atexit.register(_stop_auto_ws_process)


def _should_auto_start_ws() -> bool:
    """Check if WebSocket auto-start is enabled."""
    value = os.environ.get("FRAMEVIZ_AUTO_START_WS", "1").strip().lower()
    return value not in ("0", "false", "no", "off")


def _get_ws_startup_timeout(default_timeout: float) -> float:
    """Get the WebSocket server startup timeout from environment."""
    value = os.environ.get("FRAMEVIZ_WS_STARTUP_TIMEOUT", "").strip()
    if not value:
        return max(2.5, min(default_timeout, 8.0))
    try:
        parsed = float(value)
    except ValueError:
        return max(2.5, min(default_timeout, 8.0))
    return max(0.5, parsed)


def _get_default_ws_log_path() -> Path:
    """Get default log path for WebSocket server."""
    stamp = int(time.time())
    return Path(tempfile.gettempdir()) / f"frameviz_ws_server_{os.getpid()}_{stamp}.log"


def _get_ws_log_targets() -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    """Get stdout/stderr log targets for WebSocket server."""
    value = os.environ.get("FRAMEVIZ_WS_SERVER_LOG", "").strip()
    if value.lower() in ("inherit", "stdout"):
        return None, None, None
    if value.lower() == "stderr":
        return None, None, None

    path = Path(value).expanduser() if value else _get_default_ws_log_path()
    try:
        handle = builtins.open(path, "w", encoding="utf-8")
    except OSError:
        return subprocess.DEVNULL, subprocess.DEVNULL, None
    return handle, handle, str(path)


def _is_local_host(host: str) -> bool:
    """Check if a hostname refers to localhost."""
    return host in ("127.0.0.1", "localhost")


# ─────────────────────────────────────────────────────────────────────────────
# Repo root helpers
# ─────────────────────────────────────────────────────────────────────────────
def _looks_like_repo_root(path: Path) -> bool:
    if not (path / "pnpm-workspace.yaml").is_file() or not (
        path / "packages/frameviz-host-tauri"
    ).is_dir():
        return False
    try:
        manifest = json.loads((path / "version.json").read_text(encoding="utf-8"))
        return isinstance(manifest, dict) and (
            manifest.get("project_id") == "qqfly.frameviz"
            and manifest.get("protocol_version") == PROTOCOL_VERSION
        )
    except (OSError, ValueError):
        return False


def _get_repo_root() -> Optional[Path]:
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        current = start
        for _ in range(8):
            if _looks_like_repo_root(current):
                return current
            if current.parent == current:
                break
            current = current.parent
    return None


def _get_macos_app_executable(app: Path) -> Optional[Path]:
    """Resolve a FrameViz bundle's declared executable without a name lookup."""
    try:
        with (app / 'Contents/Info.plist').open('rb') as stream:
            info = plistlib.load(stream)
        name = info.get('CFBundleExecutable')
        if (info.get('CFBundleIdentifier') != 'dev.qqfly.frameviz.viewer'
                or info.get('CFBundlePackageType') != 'APPL'
                or name not in ('frameviz', 'FrameViz')):
            return None
        directory = app / 'Contents/MacOS'
        binary = directory / name
        if (binary.is_file() and os.access(binary, os.X_OK)
                and binary.resolve().is_relative_to(directory.resolve())):
            return binary
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return None


def _get_tauri_app_candidates(repo_root: Optional[Path]) -> List[Path]:
    if not sys.platform == "darwin":
        return []
    candidates = []
    if repo_root:
        candidates = [
            repo_root
            / "packages/frameviz-host-tauri/src-tauri/target/release/bundle/macos/FrameViz.app",
            repo_root
            / "packages/frameviz-host-tauri/src-tauri/target/debug/bundle/macos/FrameViz.app",
        ] + candidates
    for app in [Path.home() / 'Applications/FrameViz.app', Path('/Applications/FrameViz.app')]:
        if _get_macos_app_executable(app) is not None and app not in candidates:
            candidates.append(app)
    return candidates


def _get_tauri_exec_candidates(repo_root: Optional[Path]) -> List[Path]:
    candidates: List[Path] = []
    if sys.platform.startswith("linux"):
        # The standard .deb installs here. Do not select arbitrary names from
        # PATH: a virtual environment or another project may provide one.
        installed = Path("/usr/bin/frameviz")
        if installed.is_file() and os.access(installed, os.X_OK):
            candidates.append(installed)
    if sys.platform.startswith("win"):
        if repo_root:
            candidates.extend(
                [
                    repo_root
                    / "packages/frameviz-host-tauri/src-tauri/target/release/frameviz.exe",
                    repo_root
                    / "packages/frameviz-host-tauri/src-tauri/target/debug/frameviz.exe",
                ]
            )
        return candidates

    if repo_root:
        candidates.extend(
            [
                repo_root
                / "packages/frameviz-host-tauri/src-tauri/target/release/frameviz",
                repo_root
                / "packages/frameviz-host-tauri/src-tauri/target/debug/frameviz",
            ]
        )
    return candidates


def _get_appimage_candidates(repo_root: Optional[Path]) -> List[Path]:
    if not repo_root:
        return []
    appimage_dir = (
        repo_root / "packages/frameviz-host-tauri/src-tauri/target/release/bundle/appimage"
    )
    if not appimage_dir.is_dir():
        return []
    return sorted(appimage_dir.glob("FrameViz*.AppImage"))


# ─────────────────────────────────────────────────────────────────────────────
# Discovery helpers (wrappers around discovery module)
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_discovery_path() -> Optional[Path]:
    """Get discovery path (delegated to discovery module)."""
    return get_discovery_path()


def _read_discovery_info(path: Path) -> Optional[Dict[str, Any]]:
    """Read discovery file (delegated to discovery module)."""
    return read_discovery_file(path)


def _pid_is_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    if pid <= 0:
        return False
    if os.name == "posix":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    if sys.platform.startswith("win"):
        try:
            import ctypes
            import ctypes.wintypes
        except Exception:
            return True
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return True


def _read_discovery_port(path: Path) -> Optional[int]:
    """Read port from discovery file if valid."""
    data = _read_discovery_info(path)
    if not data:
        return None
    version = data.get("version")
    if not isinstance(version, str) or version != PROTOCOL_VERSION:
        return None
    pid = data.get("pid")
    if not isinstance(pid, int) or not _pid_is_running(pid):
        return None
    port = data.get("port")
    if not isinstance(port, int):
        return None
    if 1 <= port <= 65535:
        return port
    return None


def _resolve_discovery_port(host: str) -> Optional[int]:
    """Resolve discovery port for localhost host."""
    if not _is_local_host(host):
        return None
    path = _resolve_discovery_path()
    if not path or not path.exists():
        return None
    port = _read_discovery_port(path)
    if not port:
        return None
    if _is_port_open(host, port):
        return port
    return None


def _wait_for_discovery_port(host: str, timeout: float) -> Optional[int]:
    """Wait for discovery port to become available."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        port = _resolve_discovery_port(host)
        if port:
            return port
        time.sleep(0.1)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# URL helpers
# ─────────────────────────────────────────────────────────────────────────────
def _build_ws_url(parsed: Any, host: str, port: int) -> str:
    """Build WebSocket URL from parsed components."""
    scheme = parsed.scheme or "ws"
    netloc = f"{host}:{port}"
    return urlunparse(parsed._replace(scheme=scheme, netloc=netloc))


def _resolve_ws_url(url: str, allow_discovery: bool = True) -> str:
    """Resolve WebSocket URL, optionally using discovery."""
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9527
    use_discovery = parsed.port is None or parsed.port == 9527
    if allow_discovery and use_discovery and _is_local_host(host):
        discovery_port = _resolve_discovery_port(host)
        if discovery_port:
            port = discovery_port
    return _build_ws_url(parsed, host, port)


def _get_ws_port_from_url(url: str) -> int:
    """Extract WebSocket port from URL."""
    parsed = urlparse(url)
    return parsed.port or 9527


def _is_port_open(host: str, port: int) -> bool:
    """Check if a TCP port is open."""
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket server management
# ─────────────────────────────────────────────────────────────────────────────
def _get_ws_server_command() -> Tuple[
    Optional[List[str]], Optional[Path], Optional[str]
]:
    """Get WebSocket server command from environment."""
    cmd = os.environ.get("FRAMEVIZ_WS_SERVER_CMD")
    if cmd:
        return shlex.split(cmd), None, None
    return None, None, "no ws-server command available (set FRAMEVIZ_WS_SERVER_CMD)"


def _start_ws_server_process() -> bool:
    """Start the WebSocket server process."""
    global _AUTO_WS_PROCESS
    global _AUTO_WS_LAST_ERROR
    global _AUTO_WS_LOG_PATH
    global _AUTO_WS_LOG_HANDLE
    global _AUTO_WS_PROCESS_GROUP_ID
    if _AUTO_WS_PROCESS and _AUTO_WS_PROCESS.poll() is None:
        return True

    cmd, cwd, reason = _get_ws_server_command()
    if not cmd:
        _AUTO_WS_LAST_ERROR = reason
        return False

    stdout_target, stderr_target, log_path = _get_ws_log_targets()
    _AUTO_WS_LOG_PATH = log_path
    _AUTO_WS_LOG_HANDLE = (
        stdout_target if stdout_target not in (None, subprocess.DEVNULL) else None
    )

    kwargs: Dict[str, Any] = {
        "stdout": stdout_target,
        "stderr": stderr_target,
        "stdin": subprocess.DEVNULL,
        "cwd": str(cwd) if cwd else None,
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True

    try:
        _AUTO_WS_PROCESS = subprocess.Popen(cmd, **kwargs)
    except OSError:
        _AUTO_WS_LAST_ERROR = "failed to spawn ws-server process"
        return False
    _AUTO_WS_PROCESS_GROUP_ID = _AUTO_WS_PROCESS.pid if os.name == "posix" else None
    _register_auto_ws_atexit()
    _AUTO_WS_LAST_ERROR = None
    return True


def _wait_for_ws_ready(host: str, port: int, timeout: float = 2.5) -> bool:
    """Wait for WebSocket server to become ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _AUTO_WS_PROCESS and _AUTO_WS_PROCESS.poll() is not None:
            return False
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _read_ws_log_tail(path: str, max_lines: int = 8) -> Optional[str]:
    """Read last N lines from WebSocket server log."""
    chunk_size = 1024
    try:
        with builtins.open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            file_size = handle.tell()
            if file_size == 0:
                return None

            lines: List[str] = []
            buffer = b""
            pointer = file_size

            while pointer > 0 and len(lines) < max_lines:
                read_size = min(chunk_size, pointer)
                pointer -= read_size
                handle.seek(pointer)
                chunk = handle.read(read_size)
                buffer = chunk + buffer

                # Split buffer into lines
                while b"\n" in buffer:
                    # Find the LAST newline
                    split_idx = buffer.rfind(b"\n")
                    line_bytes = buffer[split_idx + 1 :]
                    buffer = buffer[:split_idx]

                    line = line_bytes.decode("utf-8", errors="ignore").strip()
                    if line:
                        lines.append(line)
                        if len(lines) >= max_lines:
                            break

            # Process remaining buffer
            if buffer and len(lines) < max_lines:
                line = buffer.decode("utf-8", errors="ignore").strip()
                if line:
                    lines.append(line)

            if not lines:
                return None

            # lines are in reverse order (last line first)
            return " | ".join(reversed(lines[:max_lines]))
    except OSError:
        return None


def _maybe_auto_start_ws(
    url: str, timeout: float
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Attempt to auto-start WebSocket server if needed.

    Returns:
        (success, error_message, new_url)
    """
    if not _should_auto_start_ws():
        return False, "auto-start disabled (FRAMEVIZ_AUTO_START_WS=0)", None
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9527
    if not _is_local_host(host):
        return False, "auto-start only supports localhost", None
    use_discovery = parsed.port is None or parsed.port == 9527
    if use_discovery:
        discovery_port = _resolve_discovery_port(host)
        if discovery_port:
            return True, None, _build_ws_url(parsed, host, discovery_port)

    if _is_port_open(host, port):
        return True, None, url
    if _start_ws_server_process():
        wait_time = _get_ws_startup_timeout(timeout)
        if _wait_for_ws_ready(host, port, timeout=wait_time):
            return True, None, url
        if use_discovery:
            discovery_port = _wait_for_discovery_port(host, wait_time)
            if discovery_port:
                return True, None, _build_ws_url(parsed, host, discovery_port)
        tail_note = None
        if _AUTO_WS_LOG_PATH:
            tail = _read_ws_log_tail(_AUTO_WS_LOG_PATH)
            if tail and "EADDRINUSE" in tail:
                return (
                    False,
                    f"port {port} already in use (log: {_AUTO_WS_LOG_PATH})",
                    None,
                )
            if tail:
                tail_note = tail
        log_hint = f" (log: {_AUTO_WS_LOG_PATH})" if _AUTO_WS_LOG_PATH else ""
        if tail_note:
            return (
                False,
                f"ws-server not ready (startup timeout){log_hint} last_log={tail_note}",
                None,
            )
        return False, f"ws-server not ready (startup timeout){log_hint}", None

    # Fall back to launching Tauri app (if available in viz.py)
    # Note: This function is called from host.py which doesn't have access to Tauri helpers
    # If this path is reached, the caller (host.py) will handle the fallback
    return False, "auto-start failed: ws-server not available", None

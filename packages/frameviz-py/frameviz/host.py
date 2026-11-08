from __future__ import annotations

import atexit
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from .client import DEFAULT_WS_URL
from ._internal import (
    _get_repo_root,
    _get_tauri_app_candidates,
    _get_tauri_exec_candidates,
    _get_appimage_candidates,
    _get_ws_port_from_url,
    _maybe_auto_start_ws,
    _resolve_ws_url,
    _should_auto_start_ws,
    _wait_for_ws_ready,
)

# Track the host process started by this module.
_started_host_proc: Optional[subprocess.Popen] = None
_started_host_we_own: bool = False
_atexit_registered: bool = False


def _parse_host_port(url: str) -> Tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9527
    return host, port


def find_host_executable() -> Optional[Path]:
    env_path = os.environ.get("FRAMEVIZ_HOST_PATH")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return candidate

    repo_root = _get_repo_root()

    if sys.platform == "darwin":
        for app in _get_tauri_app_candidates(repo_root):
            app_bin = app / "Contents" / "MacOS" / "FrameViz"
            if app_bin.exists():
                return app_bin

    for candidate in _get_tauri_exec_candidates(repo_root):
        if candidate.exists():
            return candidate

    for candidate in _get_appimage_candidates(repo_root):
        if candidate.exists():
            return candidate
    return None


def _launch_executable(path: Path, args: list[str]) -> subprocess.Popen:
    """Launch the host executable and return the process handle."""
    if sys.platform == "darwin" and path.suffix == ".app":
        # Launch .app bundle via 'open'; the returned Popen is for the 'open'
        # helper, not the app itself.  We launch directly via the inner binary
        # instead so we can track the actual process.
        inner_bin = path / "Contents" / "MacOS" / "frameviz"
        if not inner_bin.exists():inner_bin = path / "Contents" / "MacOS" / "FrameViz"
        if inner_bin.exists():
            proc = subprocess.Popen(
                [str(inner_bin), *args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return proc
        raise RuntimeError(
            f"Cannot find FrameViz binary inside .app bundle at {path}. "
            f"Expected to find it at {inner_bin}. Please ensure the .app bundle is complete."
        )
    proc = subprocess.Popen(
        [str(path), *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def is_host_running(ws_url: str = DEFAULT_WS_URL, timeout: float = 0.2) -> bool:
    resolved = _resolve_ws_url(ws_url, allow_discovery=True)
    host, port = _parse_host_port(resolved)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_host(
    ws_url: str = DEFAULT_WS_URL,
    timeout: float = 10.0,
    ws_port: Optional[int] = None,
    headless: bool = False,
) -> str:
    global _started_host_proc, _started_host_we_own
    resolved = _resolve_ws_url(ws_url, allow_discovery=True)
    if ws_port is None:
        ws_port = _get_ws_port_from_url(resolved)
    args = ["--ws-port", str(ws_port)]
    if headless:
        args.append("--headless")

    path = find_host_executable()
    if path:
        proc = _launch_executable(path, args)
        if _wait_for_ws_ready("127.0.0.1", ws_port, timeout=timeout):
            _started_host_proc = proc
            _started_host_we_own = True
            _register_atexit()
            return resolved
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    proc.kill()
                except OSError:
                    pass
        raise RuntimeError("Failed to start FrameViz host (startup timeout)")

    ok, reason, new_url = _maybe_auto_start_ws(resolved, timeout)
    if not ok:
        detail = reason or "auto-start failed"
        raise RuntimeError(f"Failed to start FrameViz host: {detail}")
    return new_url or resolved


def stop_host() -> None:
    """Stop the host process if it was started by this module."""
    global _started_host_proc, _started_host_we_own
    proc = _started_host_proc
    if proc is None or not _started_host_we_own:
        return
    _started_host_proc = None
    _started_host_we_own = False
    if proc.poll() is not None:
        return  # Already exited
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        try:
            proc.kill()
        except OSError:
            pass


def _register_atexit() -> None:
    global _atexit_registered
    if _atexit_registered:
        return
    _atexit_registered = True
    atexit.register(stop_host)


def ensure_host_running(ws_url: str = DEFAULT_WS_URL, timeout: float = 10.0) -> str:
    if not _should_auto_start_ws():
        raise RuntimeError("auto-start disabled (FRAMEVIZ_AUTO_START_WS=0)")
    if is_host_running(ws_url):
        return _resolve_ws_url(ws_url, allow_discovery=True)
    return start_host(ws_url, timeout=timeout)

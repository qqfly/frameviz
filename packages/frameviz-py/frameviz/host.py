from __future__ import annotations

import atexit
import os
import plistlib
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from .client import DEFAULT_WS_URL, PROTOCOL_VERSION
from .discovery import read_discovery_file, get_discovery_path
from .version import host_version_error, parse_version
from .exceptions import ProtocolError
from ._internal import (
    _get_repo_root,
    _get_macos_app_executable,
    _get_tauri_app_candidates,
    _get_tauri_exec_candidates,
    _get_appimage_candidates,
    _get_ws_port_from_url,
    _maybe_auto_start_ws,
    _resolve_ws_url,
    _should_auto_start_ws,
    _wait_for_ws_ready,
    _pid_is_running,
    _is_port_open,
)

# Track the host process started by this module.
_started_host_proc: Optional[subprocess.Popen] = None
_started_host_we_own: bool = False
_atexit_registered: bool = False
_started_host_log_path: Optional[Path] = None


def _parse_host_port(url: str) -> Tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9527
    return host, port


def _desktop_available() -> bool:
    return not sys.platform.startswith('linux') or bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))


def _installation_hint() -> str:
    if sys.platform == 'darwin':
        command="open ./FrameViz*.dmg, then copy FrameViz.app to /Applications"
    elif sys.platform.startswith('linux'):
        command="sudo apt install ./FrameViz*.deb, or install the standalone frameviz-server in ~/.local/bin"
    else:
        command="build the FrameViz runtime from source for this platform"
    return f"Install the FrameViz runtime: {command}. A Python wheel alone is not the runtime. See docs/INSTALLATION.md (https://github.com/qqfly/frameviz/blob/main/docs/INSTALLATION.md)."


def _executable(path: Path) -> Optional[Path]:
    if sys.platform == 'darwin' and path.suffix == '.app':
        return _get_macos_app_executable(path)
    return path if path.is_file() and os.access(path,os.X_OK) else None


def _runtime_version(path: Path, binary: Path) -> Optional[str]:
    """Read bundle metadata or use the side-effect-free executable version probe."""
    if path.suffix == ".app":
        try:
            with (path / "Contents/Info.plist").open("rb") as source:
                version = plistlib.load(source).get("CFBundleShortVersionString")
            return version if parse_version(version) else None
        except (OSError, ValueError, AttributeError):
            return None
    try:
        result = subprocess.run([str(binary), "--version"], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None
    prefix = "FrameViz Host v"
    output = result.stdout.strip()
    version = output[len(prefix):] if output.startswith(prefix) else None
    return version if result.returncode == 0 and parse_version(version) else None


def _standalone_candidates(repo_root: Optional[Path]) -> list[Path]:
    paths = [Path("/usr/bin/frameviz-server"), Path("/usr/local/bin/frameviz-server"),
             Path.home() / ".local/bin/frameviz-server"]
    if repo_root:
        paths.extend(repo_root / f"packages/frameviz-server/target/{profile}/frameviz-server"
                     for profile in ("release", "debug"))
    return paths


def find_host_executable(prefer_browser: bool = False, *, native_only: bool = False) -> Optional[Path]:
    for key in ("FRAMEVIZ_HOST_PATH", "FRAMEVIZ_TAURI_APP"):
        if not (configured := os.environ.get(key)):
            continue
        path = Path(configured).expanduser()
        binary = _executable(path)
        if binary is None:
            raise RuntimeError(f"{key} is not an executable FrameViz runtime: {path}. {_installation_hint()}")
        version = _runtime_version(path, binary)
        if version and (error := host_version_error(version, PROTOCOL_VERSION)):
            raise ProtocolError(f"{key} ({path}): {error}", code="ERR_PROTOCOL_VERSION")
        return None if native_only and binary.name == "frameviz-server" else binary

    repo_root = _get_repo_root()
    gui = _get_tauri_app_candidates(repo_root) + _get_tauri_exec_candidates(repo_root) + _get_appimage_candidates(repo_root)
    server = [] if native_only else _standalone_candidates(repo_root)
    if prefer_browser and not _desktop_available():
        gui = []
    candidates = server + gui if prefer_browser else gui + server
    unknown = None
    first_error = None
    # Prefer a verified installation over a verified source build. Older
    # standalone executables may lack --version and are checked at startup.
    for source in (False, True):
        for path in candidates:
            is_source = repo_root is not None and path.is_relative_to(repo_root)
            if is_source != source or (binary := _executable(path)) is None:
                continue
            version = _runtime_version(path, binary)
            if version is None:
                unknown = unknown or binary
            elif error := host_version_error(version, PROTOCOL_VERSION):
                first_error = first_error or f"{path}: {error}"
            else:
                return binary
    if unknown is None and first_error and not native_only:
        raise ProtocolError(first_error, code="ERR_PROTOCOL_VERSION")
    return unknown


def _launch_executable(path: Path, args: list[str]) -> subprocess.Popen:
    """Start the exact executable, recording private diagnostics for failures."""
    global _started_host_log_path
    if sys.platform == "darwin" and path.suffix == ".app":
        binary=_get_macos_app_executable(path)
        if binary is None:raise RuntimeError(f"Incomplete FrameViz application: {path}")
        path=binary
    options=dict(stdin=subprocess.DEVNULL,start_new_session=os.name=='posix')
    target=os.environ.get('FRAMEVIZ_WS_SERVER_LOG','').strip()
    if target.lower() in ('inherit','stdout','stderr'):
        _started_host_log_path=None
        return subprocess.Popen([str(path),*args],**options)
    state=get_discovery_path()
    directory=Path(os.environ['FRAMEVIZ_LOG_DIR']).expanduser() if os.environ.get('FRAMEVIZ_LOG_DIR') else (state.parent if state else Path.home()/'.local/share/qqfly/frameviz')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    logfile=Path(target).expanduser() if target else directory/f'startup-{os.getpid()}-{time.time_ns()}.log'
    flags=os.O_WRONLY|os.O_CREAT|(os.O_APPEND if target else os.O_EXCL)
    descriptor=os.open(logfile,flags,0o600)
    _started_host_log_path=logfile
    with os.fdopen(descriptor,'w') as stream:
        return subprocess.Popen([str(path),*args],stdout=stream,stderr=stream,**options)


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
    prefer_browser: bool = False,
) -> str:
    global _started_host_proc, _started_host_we_own
    resolved = _resolve_ws_url(ws_url, allow_discovery=True)
    if ws_port is None:
        ws_port = _get_ws_port_from_url(resolved)
    args = ["--ws-port", str(ws_port)]
    if headless:
        args.append("--headless")

    path = find_host_executable(prefer_browser=prefer_browser)
    if path:
        proc = _launch_executable(path, args)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline and proc.poll() is None:
            info=read_discovery_file()
            if info and info.get('pid')==proc.pid:
                error=host_version_error(info.get('version'),PROTOCOL_VERSION)
                if error:
                    proc.terminate();proc.wait(timeout=2)
                    raise ProtocolError(error,code='ERR_PROTOCOL_VERSION')
                port=info.get('port')
                if isinstance(port,int) and _is_port_open('127.0.0.1',port) and (not headless or info.get('viewer_url')):
                    _started_host_proc=proc
                    _started_host_we_own=True
                    _register_atexit()
                    return info.get('ws_url') or f'ws://127.0.0.1:{port}'
            time.sleep(.025)
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    proc.kill()
                except OSError:
                    pass
        from ._internal import _read_ws_log_tail
        tail=_read_ws_log_tail(str(_started_host_log_path)) if _started_host_log_path else None
        diagnostic=f" Startup log: {_started_host_log_path}. {tail or ''}" if _started_host_log_path else ''
        raise RuntimeError(f"FrameViz runtime did not become ready (exit={proc.poll()}).{diagnostic} {_installation_hint()}")

    if not os.environ.get('FRAMEVIZ_WS_SERVER_CMD'):
        raise RuntimeError(_installation_hint())
    ok, reason, new_url = _maybe_auto_start_ws(resolved, timeout)
    if not ok:
        detail = reason or "auto-start failed"
        raise RuntimeError(f"Failed to start FrameViz runtime: {detail}. {_installation_hint()}")
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

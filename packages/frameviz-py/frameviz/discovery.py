"""
Discovery file utilities for FrameViz Python SDK.

The discovery file (host.json) contains connection information written by the
FrameViz Host at startup. Path logic is centralized here to avoid duplication.
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, Iterator, Optional
from urllib.parse import urlsplit


def get_discovery_path() -> Optional[Path]:
    """
    Get the platform-specific path for the discovery file (host.json).
    
    Priority:
    1. FRAMEVIZ_DISCOVERY_PATH environment variable (if set)
    2. Platform-specific default:
       - macOS: ~/.local/share/qqfly/frameviz/host.json
       - Linux: ~/.local/share/qqfly/frameviz/host.json
       - Windows: %LOCALAPPDATA%/qqfly/FrameViz/host.json
    
    Returns:
        Path to host.json, or None if unable to determine.
    """
    # Check environment variable first
    env_path = os.environ.get("FRAMEVIZ_DISCOVERY_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    
    state_dir = os.environ.get("FRAMEVIZ_HOME", "").strip()
    if state_dir:
        return Path(state_dir).expanduser() / "host.json"
    # Get home directory
    try:
        home = Path.home()
    except RuntimeError:
        return None
    
    # Platform-specific paths (must match Rust host)
    if sys.platform == "darwin":  # macOS
        return home / ".local" / "share" / "qqfly" / "frameviz" / "host.json"
    elif sys.platform.startswith("win"):  # Windows
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "qqfly" / "FrameViz" / "host.json"
        return None
    else:  # Linux and others
        return home / ".local" / "share" / "qqfly" / "frameviz" / "host.json"


def read_discovery_file(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Read and parse the discovery file.
    
    Args:
        path: Optional explicit path. If None, uses get_discovery_path().
        
    Returns:
        Parsed JSON dict, or None if file doesn't exist or is invalid.
    """
    if path is None:
        path = get_discovery_path()
    
    if path is None or not path.exists():
        return None
    
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    
    return None


def get_ws_url_from_discovery() -> Optional[str]:
    """
    Get WebSocket URL from discovery file.
    
    Returns:
        WebSocket URL string, or None if not available.
    """
    data = read_discovery_file()
    if data:
        return data.get("ws_url") or data.get("url")
    return None


def get_token_from_discovery() -> Optional[str]:
    """
    Get authentication token from discovery file.
    
    Returns:
        Token string, or None if not available.
    """
    data = read_discovery_file()
    if data:
        return data.get("token")
    return None


def get_port_from_discovery() -> Optional[int]:
    """
    Get port number from discovery file.

    Returns:
        Port number, or None if not available.
    """
    data = read_discovery_file()
    if data:
        port = data.get("port")
        if isinstance(port, int):
            return port
    return None


def get_viewer_url_from_discovery() -> Optional[str]:
    """
    Get viewer URL from discovery file (for browser mode).

    Returns:
        Viewer URL string (e.g., "http://127.0.0.1:8080/"), or None if not available.
    """
    data = read_discovery_file()
    if data:
        return data.get("viewer_url")
    return None


def get_http_port_from_discovery() -> Optional[int]:
    """
    Get HTTP server port from discovery file.

    Returns:
        HTTP port number, or None if not available.
    """
    data = read_discovery_file()
    if data:
        port = data.get("http_port")
        if isinstance(port, int):
            return port
    return None


def local_host_records() -> Iterator[Dict[str, Any]]:
    """Read compatible loopback records from the selected user state directory."""
    from .client import PROTOCOL_VERSION
    from .version import host_version_error

    primary = get_discovery_path()
    if primary is None:
        return
    candidates = [primary, *primary.with_suffix(".hosts").glob("*.json")]
    endpoints = set()
    for path in candidates:
        info = read_discovery_file(path)
        if not info or not isinstance(info.get("ws_url"), str) or not isinstance(info.get("token"), str):
            continue
        try:
            url = urlsplit(info["ws_url"])
            port = url.port
        except ValueError:
            continue
        if (url.scheme != "ws" or url.hostname not in ("localhost", "127.0.0.1", "::1")
                or not port or port != info.get("port") or url.username or url.password
                or url.path not in ("", "/") or url.query or url.fragment
                or not isinstance(info.get("pid"), int) or not isinstance(info.get("started_at_ms"), int)
                or host_version_error(info.get("version"), PROTOCOL_VERSION)):
            continue
        if port not in endpoints:
            endpoints.add(port)
            yield info


def get_registered_host_token(url: str) -> Optional[str]:
    selected = urlsplit(url)
    if (selected.scheme != "ws" or selected.hostname not in ("localhost", "127.0.0.1", "::1")
            or selected.username or selected.password or selected.path not in ("", "/")
            or selected.query or selected.fragment):
        return None
    for info in local_host_records():
        if info["port"] == selected.port:
            return info["token"]
    return None

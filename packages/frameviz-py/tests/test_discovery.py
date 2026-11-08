import json
import os
import socket

import pytest
from frameviz._internal import PROTOCOL_VERSION, _resolve_ws_url


def _open_listener() -> tuple[socket.socket, int]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
    except PermissionError:
        pytest.skip("socket bind not permitted in this environment")
    sock.listen(1)
    return sock, sock.getsockname()[1]


def test_resolve_ws_url_uses_discovery(monkeypatch, tmp_path) -> None:
    listener, port = _open_listener()
    try:
        path = tmp_path / "host.json"
        path.write_text(
            json.dumps({"port": port, "pid": os.getpid(), "version": PROTOCOL_VERSION}),
            encoding="utf-8",
        )
        monkeypatch.setenv("FRAMEVIZ_DISCOVERY_PATH", str(path))

        url = _resolve_ws_url("ws://127.0.0.1:9527", allow_discovery=True)
        assert url == f"ws://127.0.0.1:{port}"
    finally:
        listener.close()


def test_resolve_ws_url_ignores_discovery_with_explicit_port(
    monkeypatch, tmp_path
) -> None:
    listener, port = _open_listener()
    try:
        path = tmp_path / "host.json"
        path.write_text(
            json.dumps({"port": port, "pid": os.getpid(), "version": PROTOCOL_VERSION}),
            encoding="utf-8",
        )
        monkeypatch.setenv("FRAMEVIZ_DISCOVERY_PATH", str(path))

        url = _resolve_ws_url("ws://127.0.0.1:9999", allow_discovery=True)
        assert url == "ws://127.0.0.1:9999"
    finally:
        listener.close()


# Duplicate test removed (kept the single explicit-port case above).

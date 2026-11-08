from __future__ import annotations

import socket

import pytest

from frameviz.host import ensure_host_running, find_host_executable, is_host_running, stop_host


def _get_unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except PermissionError:
            pytest.skip("socket bind not permitted in this environment")
        return sock.getsockname()[1]


def test_is_host_running_returns_false_for_unused_port() -> None:
    port = _get_unused_port()
    assert is_host_running(f"ws://127.0.0.1:{port}") is False


def test_ensure_host_running_respects_disable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRAMEVIZ_AUTO_START_WS", "0")
    with pytest.raises(RuntimeError):
        ensure_host_running("ws://127.0.0.1:9527", timeout=0.1)


def test_find_host_executable_returns_none_in_clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRAMEVIZ_HOST_PATH", raising=False)
    path = find_host_executable()
    assert path is None or path.exists()


def test_stop_host_no_op_when_not_started() -> None:
    """stop_host() should be safe to call even if no host was started."""
    import frameviz.host as host_mod
    old_proc = host_mod._started_host_proc
    old_own = host_mod._started_host_we_own
    try:
        host_mod._started_host_proc = None
        host_mod._started_host_we_own = False
        stop_host()  # Should not raise
    finally:
        host_mod._started_host_proc = old_proc
        host_mod._started_host_we_own = old_own

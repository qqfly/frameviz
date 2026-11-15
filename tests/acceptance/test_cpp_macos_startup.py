"""Native C++ example startup and Ctrl+C with a disposable App installation."""
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

import pytest
from frameviz.client import FrameVizClient

from test_standalone_viewer import free_port

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS desktop required")


def wait_until(check, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if result := check():
            return result
        time.sleep(0.05)
    pytest.fail("FrameViz App or C++ example did not reach the expected state")


def exited(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


@pytest.mark.parametrize("mode", ["exclusive", "shared", "manual"])
def test_compiled_example_finds_installed_app_and_cleans_up_on_interrupt(tmp_path, mode):
    bundle = os.environ.get("FRAMEVIZ_ACCEPTANCE_APP_BUNDLE")
    binary = os.environ.get("FRAMEVIZ_CPP_HELLO_WORLD")
    if not bundle or not binary:
        pytest.skip("Set the explicit macOS App bundle and compiled C++ Hello World paths")
    app = tmp_path / "Applications/FrameViz.app"
    shutil.copytree(bundle, app)
    state = tmp_path / "state/host.json"
    control_port = free_port()
    env = {key: value for key, value in os.environ.items() if not key.startswith("FRAMEVIZ_")}
    env.update(HOME=str(tmp_path), CFFIXED_USER_HOME=str(tmp_path),
               FRAMEVIZ_HOME=str(state.parent), FRAMEVIZ_TAURI_CONTROL_PORT=str(control_port),
               FRAMEVIZ_HOST=f"ws://127.0.0.1:{free_port()}")
    # Record a browser fallback without opening a tab in the user's browser.
    tools = tmp_path / "tools"
    tools.mkdir()
    opener = tools / "open"
    opener.write_text('#!/bin/sh\ntouch "$HOME/browser-fallback"\nexit 1\n')
    opener.chmod(0o755)
    env["PATH"] = f"{tools}{os.pathsep}{env.get('PATH', os.defpath)}"
    if mode == "manual":
        env.pop("FRAMEVIZ_HOST")

    def ping():
        try:
            with socket.create_connection(("127.0.0.1", control_port), timeout=0.25) as conn:
                conn.sendall(b'{"action":"ping"}\n')
                with conn.makefile() as reply:
                    return json.loads(reply.readline())["ok"]
        except (OSError, ValueError):
            return False

    external = owner = peer = None
    pid = None
    log = tmp_path / "example.log"
    try:
        if mode == "manual":
            executable = app / "Contents/MacOS/frameviz"
            external = subprocess.Popen([executable, "--headless", "--ws-port", str(free_port())],
                                        cwd=tmp_path, env=env, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
            wait_until(ping)
            wait_until(state.exists)
        with log.open("w") as output:
            owner = subprocess.Popen([Path(binary).resolve()], cwd=tmp_path, env=env, stdin=subprocess.PIPE,
                                     stdout=output, stderr=output, start_new_session=True)

        def ready():
            text = log.read_text()
            assert owner.poll() is None, text
            assert not (tmp_path / "browser-fallback").exists(), text
            return text if "Press Enter to exit" in text else None

        text = wait_until(ready)
        assert "Viewer not ready" not in text
        info = json.loads(state.read_text())
        pid = info["pid"]
        if external:
            assert pid == external.pid and "Starting host:" not in text
        else:
            assert f"Starting host: {app}/Contents/MacOS/" in text
            assert os.getsid(pid) != owner.pid
        if mode != "exclusive":
            peer = FrameVizClient(info["ws_url"], token=info["token"])
            peer.connect()
            [view] = peer.send_command("list_views", {})["views"]
            assert peer.send_command("get_viewer_status", {"view_id": view["view_id"]})["ready"]
            peer_scene = peer.send_command("create_scene", {})["scene_id"]

        os.killpg(owner.pid, signal.SIGINT)
        assert owner.wait(timeout=6) == 130
        if peer:
            assert peer.send_command("list_views", {})["views"] == []
            assert not exited(pid)
            shape = peer.send_command("add_primitive", {
                "scene_id": peer_scene, "type": "sphere", "params": {"radius": 0.2},
            })
            assert shape["handle"]
            peer.close()
            peer = None
        if external:
            assert external.poll() is None and ping()
        else:
            wait_until(lambda: exited(pid))
            assert not state.exists()
        assert not (state.parent / "preferences.json").exists()
    finally:
        if peer:
            peer.close()
        for process in (owner, external):
            if process and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        if pid and not external and not exited(pid):
            os.kill(pid, signal.SIGTERM)

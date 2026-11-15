"""Native window requests must report the actual Tauri response."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time

import pytest


@pytest.mark.parametrize("action", ["open", "close"])
@pytest.mark.parametrize(
    "response, delay, expected",
    [(b'{"ok":true}\n', 0, "ok"), (b'{"ok":true}\n', 0.6, "ok"),
     (b'{"ok":false}\n', 0.6, "failed"), (b"", 0, "failed"),
     (b'{"ok":true}', 0, "failed")],
)
def test_control_response(tmp_path, action, response, delay, expected):
    binary = os.environ.get("FRAMEVIZ_CPP_TAURI_CONTROL")
    if not binary:
        pytest.skip("Compiled tauri_control C++ acceptance helper required")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(3)
        env = dict(os.environ, FRAMEVIZ_AUTH_TOKEN="test-token",
                   FRAMEVIZ_TAURI_CONTROL_PORT=str(listener.getsockname()[1]))
        with subprocess.Popen([Path(binary).resolve(), action], cwd=tmp_path, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            try:
                conn, _ = listener.accept()
                with conn, conn.makefile("rb") as stream:
                    conn.settimeout(3)
                    request = json.loads(stream.readline())
                    assert request["action"] == f"{action}_view"
                    assert request["token"] == "test-token"
                    time.sleep(delay)
                    if response:
                        conn.sendall(response)
                stdout, stderr = process.communicate(timeout=4)
                assert process.returncode == 0, stderr
                assert stdout.strip() == expected
            finally:
                if process.poll() is None:
                    process.kill()

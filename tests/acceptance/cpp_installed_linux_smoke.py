"""Run with an installed .deb or standalone Host and a compiled Hello World."""
import errno
import json
import os
from pathlib import Path
import pty
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time

from websocket import create_connection


def eventually(check, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if result := check():
            return result
        time.sleep(0.03)
    raise AssertionError("Timed out waiting for FrameViz")


def command(peer, name, args):
    peer.send(json.dumps({"type": "cmd", "id": name, "name": name,
                          "protocol_version": "0.5.0", "args": args}))
    while True:
        result = json.loads(peer.recv())
        if result.get("id") == name:
            assert result.get("ok"), result
            return result["result"]


def host_exited(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].startswith("Z ")
    except (FileNotFoundError, ProcessLookupError):
        return True


def run(example, expected, mode):
    with tempfile.TemporaryDirectory(prefix="frameviz-installed-cpp.") as directory:
        home = Path(directory)
        state = home / ".local/share/qqfly/frameviz/host.json"
        env = {key: value for key, value in os.environ.items() if not key.startswith("FRAMEVIZ_")}
        env.update(HOME=directory, XDG_CONFIG_HOME=str(home / ".config"),
                   XDG_CACHE_HOME=str(home / ".cache"), XDG_DATA_HOME=str(home / ".local/share"))
        if expected.name == "frameviz-server":
            env.pop("DISPLAY", None)
            env.pop("WAYLAND_DISPLAY", None)
            if not expected.is_absolute():
                binary = home / ".local/bin/frameviz-server"
                binary.parent.mkdir(parents=True)
                binary.symlink_to(Path.cwd() / expected)
                expected = binary
        else:
            assert env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")

        def discovery():
            try:
                return json.loads(state.read_text())
            except FileNotFoundError:
                return None

        def control_ready():
            try:
                with socket.create_connection(("127.0.0.1", 9528), timeout=0.2):
                    return True
            except OSError:
                return False

        manual = peer = pid = terminal = None
        child = 0
        try:
            if mode == "manual":
                manual = subprocess.Popen([expected, "--headless"], env=env, cwd=home,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                info = eventually(discovery)
                assert info["pid"] == manual.pid
                if expected.name == "frameviz":
                    eventually(control_ready)
            child, terminal = pty.fork()
            if child == 0:
                os.chdir(home)
                os.execve(example, [str(example)], env)

            output = bytearray()

            def ready():
                if select.select([terminal], [], [], 0.1)[0]:
                    try:
                        output.extend(os.read(terminal, 4096))
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        raise AssertionError(output.decode(errors="replace")) from error
                return b"Press Enter to exit" in output

            try:
                eventually(ready, 25)
            except AssertionError as error:
                raise AssertionError(output.decode(errors="replace")) from error
            assert b"Viewer not ready" not in output, output
            info = eventually(discovery)
            pid = info["pid"]
            # Docker may launch the ELF through its x86_64 translation layer.
            # The SDK reports the exact launched executable and the Host PID.
            assert not host_exited(pid)
            if manual:
                assert pid == manual.pid and b"Starting host:" not in output
            else:
                assert f"Starting host: {expected}".encode() in output, output
            if expected.name == "frameviz-server":
                assert b"Viewer URL:" in output

            if mode in ("shared", "manual") or expected.name == "frameviz":
                peer = create_connection(info["ws_url"], timeout=4)
                peer.send(json.dumps({"type": "auth", "token": info["token"]}))
                assert json.loads(peer.recv())["ok"]
                [view] = command(peer, "list_views", {})["views"]
                if expected.name == "frameviz":
                    assert command(peer, "get_viewer_status", {"view_id": view["view_id"]})["ready"]
                if mode in ("shared", "manual"):
                    scene = command(peer, "create_scene", {})["scene_id"]
                    obj = command(peer, "add_primitive", {
                        "scene_id": scene, "type": "sphere", "params": {"radius": 0.2},
                    })["handle"]
                else:
                    peer.close()
                    peer = None

            os.write(terminal, b"\x03")
            _, status = eventually(lambda: (result if (result := os.waitpid(child, os.WNOHANG))[0] else None))
            child = 0
            assert os.waitstatus_to_exitcode(status) == 130
            if peer:
                assert command(peer, "list_views", {})["views"] == []
                assert not host_exited(pid)
                command(peer, "set_transform", {
                    "scene_id": scene, "handle": obj, "pose": {"pos": [2, 0, 0]},
                })
                assert command(peer, "get_transform", {"handle": obj})["pose"]["pos"] == [2, 0, 0]
                peer.close()
                peer = None
            if manual:
                assert manual.poll() is None
            else:
                eventually(lambda: host_exited(pid))
                assert not state.exists()
            print(f"PASS {expected.name} {mode}", flush=True)
        finally:
            if terminal is not None:
                os.close(terminal)
            if peer:
                peer.close()
            if child:
                os.kill(child, signal.SIGKILL)
                os.waitpid(child, 0)
            if manual and manual.poll() is None:
                manual.terminate()
                manual.wait(timeout=10)
            if pid and not manual and not host_exited(pid):
                os.kill(pid, signal.SIGTERM)


if __name__ == "__main__":
    assert os.geteuid() != 0
    program = Path(sys.argv[1]).resolve()
    runtime = Path(sys.argv[2])
    for scenario in ("exclusive", "shared", "manual"):
        run(program, runtime, scenario)

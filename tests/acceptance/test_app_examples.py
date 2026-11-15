"""Opt-in browser walkthrough of the two original applications and both backends."""
from contextlib import ExitStack, contextmanager
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode

import pytest

from test_python_scene_tree import standalone, tree_viz
from test_standalone_viewer import ROOT, free_port


@contextmanager
def running(command, cwd, env, log_path, port):
    with log_path.open("w") as log:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(150):
                assert process.poll() is None, log_path.read_text()
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=.2):
                        break
                except OSError:
                    time.sleep(.025)
            else:
                pytest.fail(log_path.read_text())
            yield
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=4)


@pytest.mark.skipif(os.environ.get("FRAMEVIZ_RUN_APP_EXAMPLES") != "1",
                    reason="Opt-in app walkthrough")
@pytest.mark.parametrize("app,language", [
    ("simple_slider", "python"), ("simple_slider", "cpp"),
    ("urdf_robot", "python"), ("urdf_robot", "cpp"),
])
def test_existing_app_slider_changes_the_real_scene(app, language, tree_viz, standalone, tmp_path, monkeypatch):
    from playwright.sync_api import expect, sync_playwright
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    viz, info = tree_viz
    discovery = standalone[-1]
    root = ROOT / "examples/apps" / app
    slider_app = app == "simple_slider"
    business, vite_port, asset_port = free_port(), free_port(), free_port()
    token = secrets.token_urlsafe(24)
    env = dict(os.environ, HOME=str(tmp_path), FRAMEVIZ_DISCOVERY_PATH=str(discovery),
               SIMPLE_SLIDER_WS_PORT=str(business), URDF_ROBOT_WS_PORT=str(business),
               VITE_SIMPLE_SLIDER_BACKEND_WS_URL=f"ws://127.0.0.1:{business}",
               VITE_URDF_ROBOT_BACKEND_WS_URL=f"ws://127.0.0.1:{business}",
               FRAMEVIZ_AUTH_TOKEN=info["token"], FRAMEVIZ_BUSINESS_TOKEN=token,
               FRAMEVIZ_ASSET_PORT=str(asset_port),
               FRAMEVIZ_ASSET_BASE_URL=f"http://127.0.0.1:{asset_port}")
    model = ROOT / "data/models/sample_robot"
    if language == "python":
        script = "backend_simple_slider.py" if slider_app else "backend_urdf.py"
        command = [sys.executable, "-u", str(root / "python" / script)]
        if not slider_app:
            command += ["--path", str(model)]
    else:
        binary = os.environ.get("FRAMEVIZ_CPP_SLIDER_APP" if slider_app else "FRAMEVIZ_CPP_ROBOT_APP")
        if not binary:
            pytest.skip("Supply the built C++ example backend")
        command = [binary, "--ui-port", str(business)]
        if slider_app:
            command += ["--frameviz-url", info["ws_url"]]
        else:
            command += ["--path", str(model), "--asset-port", str(asset_port)]

    with ExitStack() as stack:
        stack.enter_context(running(command, root, env, tmp_path / "backend.log", business))
        stack.enter_context(running([str(root / "node_modules/.bin/vite"), "--host", "127.0.0.1",
            "--port", str(vite_port), "--strictPort"], root, env, tmp_path / "vite.log", vite_port))
        with connect(f"ws://127.0.0.1:{business}", origin=f"http://127.0.0.1:{vite_port}") as rejected:
            with pytest.raises(TimeoutError):
                rejected.recv(timeout=.15)
            rejected.send(json.dumps({"name": "home", "args": {}}))
            with pytest.raises(ConnectionClosed) as error:
                rejected.recv(timeout=2)
            assert error.value.rcvd.code == 1008
        pw = stack.enter_context(sync_playwright())
        options = {"args": ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]}
        if os.environ.get("FRAMEVIZ_TEST_CHROME"):
            options["executable_path"] = os.environ["FRAMEVIZ_TEST_CHROME"]
        browser = pw.chromium.launch(**options)
        stack.callback(browser.close)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        fragment = urlencode({"token": info["token"], "business_token": token})
        page.goto(f"http://127.0.0.1:{vite_port}/?ws_port={info['port']}#{fragment}")
        expect(page.get_by_text("Backend: Connected", exact=True)).to_be_visible(timeout=15000)
        deadline = time.monotonic() + 10
        before = []
        while time.monotonic() < deadline:
            views = viz._client.send_command("list_viewers")["viewers"]
            name = "simple_slider_viewer" if slider_app else "main_viewer"
            viewer = next((v for v in views if v["viewer_name"] == name), None)
            if viewer:
                query = {"scene_id": viewer["scene_id"]}
                before = viz._client.send_command("get_scene_snapshot", query)["objects"]
                if len(before) >= (1 if slider_app else 7):
                    break
            time.sleep(.05)
        assert len(before) >= (1 if slider_app else 7), (tmp_path / "backend.log").read_text()
        page.locator('input[type="range"]').first.press("End")
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            current = viz._client.send_command("get_scene_snapshot", query)["objects"]
            if {x["handle"]: x["pose"] for x in current} != {x["handle"]: x["pose"] for x in before}:
                break
            time.sleep(.05)
        else:
            pytest.fail("Application slider did not change any Host pose")
        assert page.locator("canvas").count() >= (1 if slider_app else 2)
        if slider_app and language == "cpp":
            import frameviz as fv

            monkeypatch.setenv("FRAMEVIZ_DISCOVERY_PATH", str(discovery))
            monkeypatch.delenv("FRAMEVIZ_AUTH_TOKEN", raising=False)
            monkeypatch.delenv("FRAMEVIZ_HOST", raising=False)
            attached = fv.connect(view_id=viewer["view_id"])
            try:
                handle = current[0]["handle"]
                attached.set_transform(handle, position=[-.75, 0, .5])
                state = viz._client.send_command("get_scene_snapshot", query)
                assert next(o for o in state["objects"] if o["handle"] == handle)["pose"]["pos"] == [-.75, 0, .5]
            finally:
                attached.close()

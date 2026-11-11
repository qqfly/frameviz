"""Use two real listener sockets while keeping test traffic on loopback."""
from contextlib import contextmanager
import json
import os
import subprocess
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from websockets.sync.client import connect

from frameviz.client import PROTOCOL_VERSION, FrameVizClient
from frameviz.viz import Viz
from test_standalone_viewer import BINARY, free_port, standalone


@contextmanager
def lan_host(tmp_path):
    local, remote, http = free_port(), free_port(), free_port()
    discovery = tmp_path / "host.json"
    env = dict(os.environ, HOME=str(tmp_path), FRAMEVIZ_DISCOVERY_PATH=str(discovery),
               FRAMEVIZ_LOG_DIR=str(tmp_path / "logs"))
    log = tmp_path / "lan-host.log"
    with log.open("w") as output:
        process = subprocess.Popen([str(BINARY), "--ws-port", str(local), "--lan-address", "127.0.0.1",
                                    "--lan-ws-port", str(remote), "--lan-http-port", str(http)],
                                   cwd=tmp_path, env=env, stdout=output, stderr=subprocess.STDOUT)
        try:
            for _ in range(200):
                assert process.poll() is None, log.read_text()
                if discovery.is_file():
                    break
                time.sleep(.025)
            else:
                pytest.fail(log.read_text())
            info = json.loads(discovery.read_text())
            client = FrameVizClient(info["ws_url"], token=info["token"])
            client.connect()
            try:
                view = client.send_command("create_view", {})
                yield Viz(client, view["scene_id"], view["view_id"], owns_view=False), info, remote
            finally:
                client.close()
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


def remote_auth(link, view=None, token=None, *, protocol=False):
    uri = urlsplit(link)
    args = parse_qs(uri.query)
    port = args["ws_port"][0]
    view = args["view_id"][0] if view is None else view
    url = f"ws://{uri.hostname}:{port}/"
    if not protocol:
        url += f"?type=viewer&view_id={view}"
    secret = parse_qs(uri.fragment)["token"][0] if token is None else token
    socket = connect(url, origin=f"http://{uri.netloc}")
    socket.send(json.dumps({"type": "auth", "token": secret}))
    response = json.loads(socket.recv(timeout=2))
    return socket, response


def test_default_runtime_does_not_issue_lan_links(standalone):
    info, *_ = standalone
    client = FrameVizClient(info["ws_url"], token=info["token"])
    client.connect()
    try:
        view = client.send_command("create_view", {})
        viz = Viz(client, view["scene_id"], view["view_id"], owns_view=False)
        with pytest.raises(RuntimeError, match="ERR_LAN_DISABLED"):
            viz.get_lan_view_link()
    finally:
        client.close()


def test_lan_link_authenticates_only_shared_view_and_receives_scene(tmp_path):
    with lan_host(tmp_path) as (viz, info, _):
        box = viz.add_box(name="shared box")
        other = viz._client.send_command("create_view", {})["view_id"]
        link = viz.get_lan_view_link()
        assert info["token"] not in link
        for options in ({"token": ""}, {"token": info["token"]}, {"view": other}, {"protocol": True}):
            socket, auth = remote_auth(link, **options)
            with socket:
                assert not auth["ok"]
                with pytest.raises(TimeoutError):
                    socket.recv(timeout=.1)

        socket, auth = remote_auth(link)
        with socket:
            assert auth["ok"]
            init = json.loads(socket.recv(timeout=2))
            snapshot = json.loads(socket.recv(timeout=2))
            assert init["read_only"] is True and init["view_id"] == viz.view_id
            assert snapshot["scene_id"] == viz.scene_id
            assert [obj["handle"] for obj in snapshot["objects"]] == [box]


def send_lan_command(ws, name, args):
    ws.send(json.dumps({"type": "cmd", "protocol_version": PROTOCOL_VERSION,
                        "id": name, "name": name, "args": args}))
    return json.loads(ws.recv(timeout=2))


def test_read_only_requests_cannot_mutate_or_follow_a_rebound_view(tmp_path):
    from websockets.exceptions import ConnectionClosed

    with lan_host(tmp_path) as (viz, _, _):
        obj = viz.add_box(name="Shared")
        slider = viz.add_widget("number", "X", 0)
        link = viz.get_lan_view_link()
        ws, reply = remote_auth(link)
        with ws:
            assert reply["ok"]
            assert json.loads(ws.recv(timeout=2))["read_only"]
            snapshot = json.loads(ws.recv(timeout=2))
            assert snapshot["widgets"] == []
            for command, args in [
                ("set_transform", {"handle": obj, "pose": [9, 0, 0, 0, 0, 0, 1]}),
                ("set_widget_value", {"widget_id": slider, "value": 9}),
                ("clear_scene", {"scene_id": viz.scene_id}),
                ("register_viewer", {"viewer_name": "forged"}),
            ]:
                response = send_lan_command(ws, command, args)
                assert response["id"] == command and response["error"]["code"] == "ERR_FORBIDDEN"
            ws.send(json.dumps({"type": "event", "protocol_version": PROTOCOL_VERSION,
                                "name": "camera_view_changed",
                                "data": {"eye": [9, 9, 9], "target": [0, 0, 0], "up": [0, 0, 1],
                                         "projection": {"type": "perspective", "fov": 67}}}))
            assert send_lan_command(ws, "get_scene_snapshot", {})["error"]["code"] == "ERR_FORBIDDEN"
            assert viz.get_transform(obj)["position"] == [0, 0, 0]
            assert viz.get_widget_value(slider) == 0
            assert viz.get_camera_view()["projection"]["fov"] == 30

            other = viz._client.send_command("create_view", {})
            secret = Viz(viz._client, other["scene_id"], other["view_id"], owns_view=False).add_box(name="Unshared")
            with pytest.raises(TimeoutError):
                ws.recv(timeout=.15)
            viz.set_transform(obj, position=[.4, 0, 0])
            update = json.loads(ws.recv(timeout=2))
            assert update["command"] == "set_transform" and update["args"]["handle"] == obj
            assert secret not in json.dumps(update)
            cloned = viz.clone_object(obj)
            clone_update = json.loads(ws.recv(timeout=2))
            assert clone_update["command"] == "clone_object" and clone_update["result"]["handle"] == cloned
            viz._client.send_command("attach_scene", {"view_id": viz.view_id, "scene_id": other["scene_id"]})
            with pytest.raises(ConnectionClosed):
                ws.recv(timeout=2)
        stale, denied = remote_auth(link)
        with stale:
            assert denied["ok"] is False


def test_read_only_browser_orbits_locally_and_renders_updates(tmp_path):
    import math
    from playwright.sync_api import expect, sync_playwright
    from test_scene_tree_browser import wait_drawable, world

    with lan_host(tmp_path) as (viz, _, _):
        obj = viz.add_box(name="Shared", color="orange")
        viz.add_widget("number", "X", 0)
        pose = viz.get_camera_view()
        with sync_playwright() as pw:
            options = {"args": ["--use-gl=angle", "--use-angle=swiftshader",
                                "--enable-unsafe-swiftshader"]}
            if os.environ.get("FRAMEVIZ_TEST_CHROME"):
                options["executable_path"] = os.environ["FRAMEVIZ_TEST_CHROME"]
            browser = pw.chromium.launch(**options)
            try:
                page = browser.new_page(viewport={"width": 900, "height": 630})
                page.goto(viz.get_lan_view_link())
                wait_drawable(page, obj)
                expect(page.get_by_role("spinbutton", name="X")).to_have_count(0)
                eye = page.evaluate("window.__FRAMEVIZ_CORE__.getCameraView().eye")
                page.mouse.move(450, 320)
                page.mouse.down()
                page.mouse.move(580, 358, steps=12)
                page.mouse.up()
                changed = page.evaluate("window.__FRAMEVIZ_CORE__.getCameraView().eye")
                assert math.dist(eye, changed) > .2
                assert viz.get_camera_view() == pose
                viz.set_transform(obj, position=[.6, -.1, .2])
                page.wait_for_function("h => window.__FRAMEVIZ_CORE__.objects.get(h)?.position.x === .6", arg=obj)
                assert world(page, obj) == pytest.approx([.6, -.1, .2])
            finally:
                browser.close()

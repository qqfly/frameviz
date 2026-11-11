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

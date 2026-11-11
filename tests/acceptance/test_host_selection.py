"""Discover and attach to two live Hosts without typing their credentials."""
from contextlib import ExitStack
import os
import time

import frameviz as fv

from frameviz.discovery import read_discovery_file
from test_app_examples import running
from test_standalone_viewer import BINARY, free_port


def test_list_and_select_live_hosts_in_one_state_directory(tmp_path, monkeypatch):
    discovery = tmp_path / "host.json"
    monkeypatch.setenv("FRAMEVIZ_DISCOVERY_PATH", str(discovery))
    monkeypatch.delenv("FRAMEVIZ_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("FRAMEVIZ_HOST", raising=False)
    env = dict(os.environ, HOME=str(tmp_path), FRAMEVIZ_LOG_DIR=str(tmp_path / "logs"))
    a, b = free_port(), free_port()
    with running([str(BINARY), str(a)], tmp_path, env, tmp_path / "a.log", a):
        with running([str(BINARY), str(b)], tmp_path, env, tmp_path / "b.log", b):
            deadline = time.monotonic() + 3
            while (read_discovery_file() or {}).get("port") != b and time.monotonic() < deadline:
                time.sleep(.02)
            assert (read_discovery_file() or {}).get("port") == b
            hosts = fv.list_hosts()
            assert {record["port"] for record in hosts} == {a, b}
            assert all("token" not in record for record in hosts)
            with ExitStack() as stack:
                objects = {}
                for host in hosts:
                    endpoint = host["ws_url"]
                    client = fv.FrameVizClient(endpoint)
                    client.connect()
                    stack.callback(client.close)
                    view = client.send_command("create_view", {})
                    viz = fv.connect(url=endpoint, view_id=view["view_id"])
                    stack.callback(viz.close)
                    objects[host["port"]] = viz.add_box(name=f"Host {host['port']}")
                    assert [item["name"] for item in viz.list_objects()] == [f"Host {host['port']}"]
                latest = fv.connect()
                stack.callback(latest.close)
                assert latest.list_objects()[0]["name"] == f"Host {b}"
        assert [record["port"] for record in fv.list_hosts()] == [a]
        remaining = fv.connect()
        try:
            assert remaining.list_objects()[0]["name"] == f"Host {a}"
        finally:
            remaining.close()

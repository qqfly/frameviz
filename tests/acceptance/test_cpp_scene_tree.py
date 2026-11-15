"""Installed C++ SDK and a real Host share a rigid tree and one cloud handle."""
import os
import subprocess

import pytest
from test_host_contracts import h


def test_installed_cpp_rigid_scene_tree(h, tmp_path):
    binary = os.environ.get("FRAMEVIZ_CPP_SCENE_TREE")
    if not binary:
        pytest.skip("Installed SDK scene_tree executable required")
    view = h.view("cpp")
    env = dict(os.environ, FRAMEVIZ_AUTH_TOKEN=h.token,
               FRAMEVIZ_DISCOVERY_PATH=str(tmp_path / "unused.json"))
    result = subprocess.run([binary, h.url, view], env=env, capture_output=True,
                            text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    objects = h.cmd("list_objects", scene_id="cpp")["objects"]
    assert len(objects) == 3
    joint, link, cloud = objects
    assert link["tags"] == {"role": "demo"} and link["name"] == "link"
    assert link["parent"] == cloud["parent"] == joint["handle"]
    assert cloud["handle"] == result.stdout.strip()
    assert cloud["visible"] is False
    assert h.cmd("get_resource_counts")["buffer_bytes"] == 500001 * 3 * 4
    h.cmd("remove_object", scene_id="cpp", handle=cloud["handle"])
    assert h.cmd("get_resource_counts")["buffer_bytes"] == 0
    assert len(h.cmd("list_objects", scene_id="cpp")["objects"]) == 2

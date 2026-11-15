"""The installed C++ client runs automatic handlers and shares Python's state."""
import json
import os
import subprocess

import pytest

from frameviz.viz import Viz
from test_host_contracts import h


def test_installed_cpp_auto_and_manual_widget_callbacks_and_state(h, tmp_path):
    binary = os.environ.get("FRAMEVIZ_CPP_WIDGETS")
    if not binary:
        pytest.skip("Installed SDK widgets_and_queries executable required")
    view = h.view("interop")
    python = Viz(h.c, "interop", view, owns_view=False)
    camera = {"eye": [3, -4, 5], "target": [0, 0, 0], "up": [0, 0, 1],
              "projection": {"type": "perspective", "fov": 42}}
    python.set_camera_view(camera)
    env = dict(os.environ, FRAMEVIZ_AUTH_TOKEN=h.token,
               FRAMEVIZ_DISCOVERY_PATH=str(tmp_path / "unused.json"))
    result = subprocess.run([binary, h.url, view], env=env, capture_output=True,
                            text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == python.get_camera_view() == camera
    state = python.get_display_state(include_bounds=True)
    box = state["objects"][0]
    assert box["world_transform"]["position"] == [2.5, 0, 0]
    assert box["world_bounds"]["min"] == [2, -.5, -.5]
    assert python.list_widgets() == []


@pytest.mark.parametrize("online", [True, False], ids=["repeat-online", "history-after-disconnect"])
def test_installed_cpp_wait_for_viewer_reports_live_state(h, tmp_path, online):
    import time

    binary = os.environ.get("FRAMEVIZ_CPP_WIDGETS")
    if not binary:
        pytest.skip("Installed SDK widgets_and_queries executable required")
    view = h.view("readiness")
    env = dict(os.environ, FRAMEVIZ_AUTH_TOKEN=h.token,
               FRAMEVIZ_DISCOVERY_PATH=str(tmp_path / "unused.json"))
    with subprocess.Popen([binary, h.url, view, "online" if online else "closed"], env=env,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True) as process:
        try:
            assert process.stdout.readline().strip() == "connected"
            count = h.cmd("get_resource_counts")["connections"]
            viewer = h.viewer(view)
            if not online:
                viewer.close()
                deadline = time.monotonic() + 3
                while h.cmd("get_resource_counts")["connections"] > count:
                    assert time.monotonic() < deadline, "Host did not observe Viewer disconnect"
                    time.sleep(.02)
            _, error = process.communicate(input="check\n", timeout=5)
            assert process.returncode == 0, error
        finally:
            if process.poll() is None:
                process.kill()

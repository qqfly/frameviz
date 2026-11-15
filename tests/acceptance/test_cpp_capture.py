"""Exercise both output methods through the installed C++ SDK."""

import os
import subprocess
import sys

import pytest

from test_python_scene_tree import standalone, tree_viz
from test_screenshot import size


def test_installed_cpp_captures_existing_scene(tree_viz, tmp_path):
    from playwright.sync_api import sync_playwright

    binary = os.environ.get("FRAMEVIZ_CPP_CAPTURE")
    if not binary:
        pytest.skip("Installed SDK capture executable required")
    viz, info = tree_viz
    box = viz.add_box(size=[1.3, 0.6, 0.9], color="red")
    viz.set_render_mode("wireframe")
    before = viz.get_display_state()
    views = viz._client.send_command("list_views", {})
    env = dict(os.environ, FRAMEVIZ_AUTH_TOKEN=info["token"], FRAMEVIZ_PYTHON=sys.executable)
    result = subprocess.run([binary, info["ws_url"], viz.view_id, box],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    assert viz._client.send_command("list_views", {}) == views
    after = viz.get_display_state()
    for key in ("camera_view", "width", "height", "render_mode"):
        assert after[key] == before[key]
    assert not (tmp_path / "invalid.png").exists()
    for name in ("normal.png", "alternate.png"):
        assert size((tmp_path / name).read_bytes()) == (320, 240)
    html = tmp_path / "lesson.html"
    assert info["token"] not in html.read_text()

    with sync_playwright() as pw:
        options = {"args": ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]}
        if chrome := os.environ.get("FRAMEVIZ_TEST_CHROME"):
            options["executable_path"] = chrome
        browser = pw.chromium.launch(**options)
        page = browser.new_context(offline=True).new_page()
        network = []
        page.on("request", lambda request: network.append(request.url)
                if request.url.startswith(("http:", "https:")) else None)
        page.on("websocket", lambda socket: network.append(socket.url))
        page.goto(html.as_uri())
        page.get_by_role("button", name="Play", exact=True).click()
        page.get_by_role("button", name="Pause", exact=True).wait_for()
        page.get_by_role("slider", name="Animation progress").press("End")
        assert not network
        browser.close()

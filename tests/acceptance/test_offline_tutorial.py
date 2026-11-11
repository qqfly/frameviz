"""Self-contained lesson exports opened in an offline Chromium context."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import threading

import numpy as np
import pytest

from test_display_state import camera
from test_python_scene_tree import standalone, tree_viz


@pytest.fixture
def model_url():
    model_dir = Path(__file__).resolve().parents[2] / "data/models/sample_robot/meshes/collision"

    class CorsAssets(SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(CorsAssets, directory=model_dir))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/base_link.stl?key=asset-test-credential"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_offline_static_and_animation_embed_and_use_real_pointer(tree_viz, model_url, tmp_path):
    from playwright.sync_api import expect, sync_playwright

    viz, info = tree_viz
    viz.set_view_config(show_axes=False, background="white")
    viz.set_camera_view(camera([3, -4, 3], 42))
    parent = viz.add_node(name="root")
    box = viz.add_box(parent=parent, size=[.7, .5, .4], color="red", position=[-.8, 0, 0])
    x = np.linspace(-1.5, 1.5, 24000)
    viz.add_points(np.column_stack((x, np.sin(4 * x) * .25, np.zeros_like(x))),
                   parent=parent, color="blue", size=4)
    viz.load_mesh(model_url, parent=parent, color="green", position=[.5, .5, 0], scale=[4, 4, 4])
    label = "</script><script>window.injectedTutorial=true</script>"
    viz.add_text_2d(label, 5, 5)
    static = tmp_path / "static.html"
    animated = tmp_path / "lesson.html"
    viz.export_html(static)
    viz.export_html(animated, animation={box: [
        {"time": 0, "pose": [-.8, 0, 0, 0, 0, 0, 1]},
        {"time": 1, "pose": [.8, 0, 0, 0, 0, 1, 0]},
    ]})
    embed = tmp_path / "embed.html"
    embed.write_text('<iframe width="690" height="470" src="./lesson.html"></iframe>')
    for path in (static, animated):
        html = path.read_text()
        assert info["token"] not in html and "asset-test-credential" not in html
        assert label not in html
    with sync_playwright() as pw:
        options = {"args": ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]}
        if os.environ.get("FRAMEVIZ_TEST_CHROME"):
            options["executable_path"] = os.environ["FRAMEVIZ_TEST_CHROME"]
        browser = pw.chromium.launch(**options)
        try:
            context = browser.new_context(viewport={"width": 700, "height": 500}, offline=True)
            page = context.new_page()
            network = []
            errors = []
            page.on("request", lambda request: network.append(request.url)
                    if request.url.startswith(("http:", "https:")) else None)
            page.on("websocket", lambda socket: network.append(socket.url))
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(static.as_uri())
            expect(page.locator("#status")).to_be_hidden()
            expect(page.get_by_text(label, exact=True)).to_be_visible()
            assert not page.evaluate("window.injectedTutorial === true")
            canvas = page.locator("canvas")
            start = canvas.screenshot()
            page.mouse.move(340, 260)
            page.mouse.down()
            page.mouse.move(470, 275, steps=10)
            page.mouse.up()
            assert canvas.screenshot() != start
            page.mouse.wheel(0, -250)
            assert canvas.screenshot() != start

            page.goto(embed.as_uri())
            frame = page.frame_locator("iframe")
            play = frame.get_by_role("button", name="Play", exact=True)
            expect(play).to_be_visible()
            seek = frame.get_by_role("slider", name="Animation progress")
            canvas = frame.locator("canvas")
            start = canvas.screenshot()
            seek.press("End")
            assert canvas.screenshot() != start
            seek.press("Home")
            play.click()
            pause = frame.get_by_role("button", name="Pause", exact=True)
            expect(pause).to_be_visible()
            bounds = canvas.bounding_box()
            x0, y0 = bounds["x"] + 300, bounds["y"] + 200
            page.mouse.move(x0, y0)
            page.mouse.down()
            page.mouse.move(x0 + 100, y0 + 40, steps=12)
            page.mouse.up()
            pause.click()
            assert float(seek.input_value()) > 0
            seek.press("Home")
            assert canvas.screenshot() != start
            assert not network and not errors
        finally:
            browser.close()


def test_export_rejects_invalid_tracks_before_writing(tree_viz, tmp_path):
    viz, _ = tree_viz
    box = viz.add_box()
    dest = tmp_path / "keep.html"
    dest.write_text("existing")
    with pytest.raises(ValueError, match="increasing"):
        viz.export_html(dest, animation={box: [
            {"time": 1, "pose": [0, 0, 0, 0, 0, 0, 1]},
            {"time": 1, "pose": [1, 0, 0, 0, 0, 0, 1]},
        ]})
    assert dest.read_text() == "existing"

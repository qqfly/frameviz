"""PNG output uses the packaged renderer, even with no interactive Viewer."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import struct
import threading

import pytest

from test_display_state import camera
from test_python_scene_tree import standalone, tree_viz
from test_scene_tree_browser import wait_drawable
from test_widget_browser import widget_pages


def size(png):
    assert png.startswith(b"\x89PNG\r\n\x1a\n") and png[12:16] == b"IHDR"
    return struct.unpack(">II", png[16:24])


def test_headless_png_file_dimensions_live_updates_and_browser_reuse(tree_viz, tmp_path):
    from frameviz import _capture

    viz, _ = tree_viz
    viz.set_view_config(show_axes=False, background="white")
    viz.set_camera_view(camera([3, -4, 3], 35))
    box = viz.add_box(size=[1.2, .6, .8], color="red")
    before_views = viz._client.send_command("list_views", {})
    path = tmp_path / "headless.png"
    first = viz.screenshot(path, width=520, height=360)
    assert size(first) == (520, 360) and path.read_bytes() == first
    assert len(first) > 2000
    renderer, browser = _capture._renderer, _capture._renderer.browser
    viz.set_transform(box, position=[.5, 0, 0])
    second = viz.screenshot(width=520, height=360)
    assert second != first and size(second) == (520, 360)
    assert renderer is _capture._renderer and browser is renderer.browser
    assert viz._client.send_command("list_views", {}) == before_views


def test_temporary_camera_leaves_existing_view_and_viewport(widget_pages):
    viz, _, (page, _) = widget_pages
    box = viz.add_box(size=[1.3, .6, .9], color="red")
    viz.add_sphere(.3, position=[1, 0, 0], color="blue")
    viz.set_camera_view(camera([3, -4, 3], 35))
    wait_drawable(page, box)
    before = page.evaluate("""() => {
        const c = window.__FRAMEVIZ_CORE__, canvas = c.getSceneManager().renderer.domElement;
        return [c.getCameraView(), canvas.width, canvas.height];
    }""")
    normal = viz.screenshot(width=500, height=350)
    alternate = viz.screenshot(camera_view=camera([-4, 2, 2], 50), width=500, height=350)
    assert size(normal) == size(alternate) == (500, 350) and alternate != normal
    after = page.evaluate("""() => {
        const c = window.__FRAMEVIZ_CORE__, canvas = c.getSceneManager().renderer.domElement;
        return [c.getCameraView(), canvas.width, canvas.height];
    }""")
    assert before[1:] == after[1:]
    for key in ("eye", "target", "up"):
        assert before[0][key] == pytest.approx(after[0][key], abs=1e-9)
    assert before[0]["projection"] == after[0]["projection"]


def test_screenshot_waits_for_delayed_mesh_and_reports_missing_model(tree_viz):
    viz, _ = tree_viz
    started, release = threading.Event(), threading.Event()
    model = Path(__file__).resolve().parents[2] / "data/models/sample_robot/meshes/collision/base_link.stl"
    content = model.read_bytes()

    class MeshServer(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/ready.stl":
                self.send_error(404)
                return
            started.set()
            if not release.wait(10):
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), MeshServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        viz.set_view_config(show_axes=False, background="white")
        viz.set_camera_view(camera([.8, -.8, .7], 35))
        viz.load_mesh(url + "/ready.stl", color="red", scale=[2, 2, 2])
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(viz.screenshot, width=480, height=320)
            try:
                assert started.wait(8)
                assert not pending.done()
            finally:
                release.set()
            ready = pending.result(timeout=10)
        assert size(ready) == (480, 320)
        viz.clear()
        assert ready != viz.screenshot(width=480, height=320)
        bad = viz.load_mesh(url + "/missing.stl")
        with pytest.raises(RuntimeError, match=bad):
            viz.screenshot(width=480, height=320)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

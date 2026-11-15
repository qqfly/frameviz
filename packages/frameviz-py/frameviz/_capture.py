"""Isolated browser rendering for screenshot and tutorial export."""
from __future__ import annotations

import atexit
from concurrent.futures import Future
from contextlib import contextmanager
import json
import os
from pathlib import Path
from queue import Queue
from threading import Lock, Thread
from urllib.parse import parse_qsl, urlencode, urlsplit

_CHROMIUM_HELP = (
    "Install the matching FrameViz wheel with the [capture] extra, "
    "then run python -m playwright install chromium."
)
_LOOPBACK = ("localhost", "127.0.0.1", "::1")


class _Renderer:
    """Keep Playwright and its browser on the same worker thread."""

    def __init__(self):
        self.pid = os.getpid()
        self.requests = Queue()
        self.browser = None
        self.thread = Thread(target=self.run, name="FrameViz renderer", daemon=True)
        self.thread.start()

    def call(self, operation):
        future = Future()
        self.requests.put((operation, future))
        return future.result()

    def run(self):
        driver = None
        try:
            while (request := self.requests.get()) is not None:
                operation, future = request
                try:
                    if driver is None:
                        try:
                            from playwright.sync_api import sync_playwright
                        except ImportError as error:
                            raise RuntimeError(_CHROMIUM_HELP) from error
                        driver = sync_playwright().start()
                    if self.browser is None or not self.browser.is_connected():
                        self.browser = self.launch(driver)
                    future.set_result(operation(self.browser))
                except Exception as error:
                    future.set_exception(error)
        finally:
            if driver is not None:
                try:
                    if self.browser is not None:
                        self.browser.close()
                finally:
                    driver.stop()

    @staticmethod
    def launch(driver):
        options = {"headless": True, "args": [
            "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
        ]}
        try:
            return driver.chromium.launch(**options)
        except Exception as error:
            if "Executable doesn't exist" not in str(error):
                raise
            try:
                return driver.chromium.launch(channel="chrome", **options)
            except Exception as fallback:
                raise RuntimeError(_CHROMIUM_HELP) from fallback


_renderer = None
_renderer_lock = Lock()


def _render(operation):
    global _renderer
    with _renderer_lock:
        if _renderer is None or _renderer.pid != os.getpid():
            _renderer = _Renderer()
        renderer = _renderer
    return renderer.call(operation)


@atexit.register
def _close_renderer():
    if _renderer is not None and _renderer.pid == os.getpid():
        _renderer.requests.put(None)
        _renderer.thread.join(timeout=4)


def _capture_endpoint(client):
    ws = urlsplit(client.url)
    if ws.scheme != "ws" or ws.hostname not in _LOOPBACK or not ws.port:
        raise RuntimeError("Automatic capture requires a local FrameViz runtime.")
    endpoint = client.send_command("get_render_endpoint", {})["viewer_url"]
    base = urlsplit(endpoint)
    if (base.scheme != "http" or base.hostname not in _LOOPBACK
            or base.username or base.password or base.fragment):
        raise RuntimeError("The FrameViz runtime did not advertise a local rendering URL.")
    return base, ws.port


def _dimension(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 8192:
        raise ValueError(f"{name} must be an integer between 1 and 8192")
    return value


@contextmanager
def _capture_view(viz, camera_view=None, width=None, height=None):
    client = viz._client
    base, port = _capture_endpoint(client)
    state = viz.get_display_state()
    width = _dimension(state["width"] if width is None else width, "width")
    height = _dimension(state["height"] if height is None else height, "height")
    capture = client.send_command("create_view", {
        "scene_id": state["scene_id"], "width": width, "height": height, "title": "FrameViz capture",
    })["view_id"]
    try:
        client.send_command("set_camera_view", {
            "view_id": capture, "camera_view": state["camera_view"] if camera_view is None else camera_view,
        })
        config = {key: value for key, value in state["view_config"].items()
                  if key not in {"width", "height"}}
        client.send_command("set_view_config", {"view_id": capture, "config": config})
        if mode := state.get("render_mode"):
            client.send_command("set_render_mode", {"view_id": capture, "mode": mode})
        for overlay in state.get("overlays", []):
            client.send_command("add_text_2d", {**overlay["data"], "view_id": capture})
        token = client._auth_token
        if not token:
            raise RuntimeError("The FrameViz client has no authenticated session for capture.")
        query = dict(parse_qsl(base.query))
        query.update({"capture": "1", "view_id": capture, "ws_port": str(port)})
        url = base._replace(query=urlencode(query)).geturl()
        yield url, token, width, height
    finally:
        client.send_command("destroy_view", {"view_id": capture})


def _with_page(url, token, width, height, operation):
    def run(browser):
        from playwright.sync_api import Error as BrowserError, TimeoutError as BrowserTimeout

        context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
        try:
            page = context.new_page()
            endpoint = urlsplit(url)
            origin = endpoint._replace(path="", query="", fragment="").geturl()
            page.add_init_script(
                "if (location.origin === " + json.dumps(origin) +
                " && location.pathname === " + json.dumps(endpoint.path or "/") +
                ") window.__FRAMEVIZ_AUTH_TOKEN__ = " + json.dumps(token) + ";"
            )
            page.goto(url, wait_until="load", timeout=15000)
            status = page.wait_for_function("""() => {
                if (document.documentElement.dataset.sceneReady !== 'true') return null;
                const status = window.__FRAMEVIZ_CORE__?.getRenderStatus();
                return status && (status.ready || status.failed.length) ? status : null;
            }""", timeout=30000).json_value()
            if status["failed"]:
                raise RuntimeError("FrameViz could not load model " + ", ".join(status["failed"]))
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            return operation(page)
        except BrowserTimeout:
            raise RuntimeError("FrameViz capture timed out waiting for the Viewer or scene resources.") from None
        except BrowserError as error:
            message = str(error).replace(url, "FrameViz Viewer").replace(token, "<session credential>")
            raise RuntimeError(f"FrameViz capture failed: {message}") from None
        finally:
            context.close()
    return _render(run)


def screenshot(viz, path=None, *, camera_view=None, width=None, height=None):
    with _capture_view(viz, camera_view, width, height) as (url, token, w, h):
        png = _with_page(url, token, w, h, lambda page: page.screenshot(type="png", animations="disabled"))
    if path is not None:
        Path(path).write_bytes(png)
    return png

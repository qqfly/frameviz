"""Use the built Vue component with real browser interactions and Host state."""
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

from test_python_scene_tree import standalone, tree_viz
from test_standalone_viewer import free_port


def test_vue_panel_can_opt_in_without_changing_default_read_write(tree_viz):
    from playwright.sync_api import expect, sync_playwright

    viz, info = tree_viz
    widget = viz.add_widget("number", "Offset", .1, minimum=-1, maximum=1)
    repo = Path(__file__).resolve().parents[2]
    vite = repo / "examples/apps/simple_slider/node_modules/.bin/vite"
    root = Path(__file__).with_name("vue_widgets")
    port = free_port()
    server = subprocess.Popen([str(vite), str(root), "--host", "127.0.0.1",
                               "--port", str(port), "--strictPort"], cwd=repo,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        endpoint = f"http://127.0.0.1:{port}/"
        for _ in range(150):
            if server.poll() is not None:
                raise RuntimeError(server.stdout.read())
            try:
                with urlopen(endpoint, timeout=.2) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(.02)
        else:
            raise RuntimeError("Vite did not start")
        with sync_playwright() as pw:
            options = {"args": ["--use-gl=angle", "--use-angle=swiftshader",
                                "--enable-unsafe-swiftshader"]}
            if os.environ.get("FRAMEVIZ_TEST_CHROME"):
                options["executable_path"] = os.environ["FRAMEVIZ_TEST_CHROME"]
            browser = pw.chromium.launch(**options)
            try:
                page = browser.new_page()
                page.goto(f"{endpoint}?view_id={viz.view_id}&ws_port={info['port']}#token={info['token']}")
                expect(page.get_by_text("Registered", exact=True)).to_be_visible(timeout=10000)
                offset = page.get_by_role("spinbutton", name="Offset")
                expect(offset).to_be_hidden()
                viz.set_widget_value(widget, -.321)
                assert viz.get_widget_value(widget) == -.321
                page.get_by_role("button", name="Show scene controls").click()
                expect(offset).to_be_visible(timeout=4000)
                expect(offset).to_have_value("-0.321")
                offset.fill("0.12345")
                offset.press("Enter")
                changed = viz._client.wait_for_event("widget_changed", timeout=3)
                assert changed["value"] == .12345 and changed["source"] == "user"
                page.get_by_role("button", name="Show scene controls").click()
                expect(offset).to_be_hidden()
                assert viz.get_widget_value(widget) == .12345
            finally:
                browser.close()
    finally:
        server.terminate()
        server.wait(timeout=5)

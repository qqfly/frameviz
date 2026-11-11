"""Use the documented launcher with a prebuilt app and temporary credentials."""
import os
from pathlib import Path
from queue import Queue
import runpy
import sys
import threading
from urllib.parse import parse_qs, urlsplit
import webbrowser

from test_standalone_viewer import ROOT, standalone


def test_launcher_supplies_both_credentials_and_uses_a_free_port(standalone, monkeypatch):
    from playwright.sync_api import expect, sync_playwright

    info, _, _, discovery = standalone
    ui_dir = Path(os.environ.get("FRAMEVIZ_SLIDER_TEST_UI", ROOT / "examples/apps/simple_slider/dist"))
    launcher = ROOT / "examples/apps/simple_slider/python/run_browser_demo.py"
    monkeypatch.setenv("FRAMEVIZ_DISCOVERY_PATH", str(discovery))
    monkeypatch.delenv("FRAMEVIZ_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("FRAMEVIZ_BUSINESS_TOKEN", raising=False)
    monkeypatch.delenv("FRAMEVIZ_HOST", raising=False)
    monkeypatch.setattr(sys, "argv", [str(launcher), "--ui-dir", str(ui_dir)])
    link, stopped = Queue(), threading.Event()
    errors = []
    monkeypatch.setattr(webbrowser, "open", link.put)
    monkeypatch.setattr("builtins.input", lambda _: stopped.wait(15))

    def launch():
        try:
            runpy.run_path(str(launcher), run_name="__main__")
        except BaseException as error:
            errors.append(error)

    worker = threading.Thread(target=launch)
    worker.start()
    try:
        url = link.get(timeout=8)
        parts = urlsplit(url)
        args = parse_qs(parts.query)
        assert int(args["business_port"][0]) > 0
        credentials = parse_qs(parts.fragment)
        assert credentials["token"] == [info["token"]]
        assert len(credentials["business_token"][0]) >= 32
        with sync_playwright() as pw:
            options = {"args": ["--use-gl=angle", "--use-angle=swiftshader",
                                "--enable-unsafe-swiftshader"]}
            if os.environ.get("FRAMEVIZ_TEST_CHROME"):
                options["executable_path"] = os.environ["FRAMEVIZ_TEST_CHROME"]
            browser = pw.chromium.launch(**options)
            try:
                page = browser.new_page()
                page.goto(url)
                expect(page.get_by_text("Backend: Connected", exact=True)).to_be_visible(timeout=10000)
                expect(page.get_by_text("Box:", exact=False)).to_be_visible()
                page.locator('input[type="range"]').first.press("End")
                assert page.locator('input[type="range"]').first.input_value() == "3"
            finally:
                browser.close()
    finally:
        stopped.set()
        worker.join(timeout=10)
    assert not worker.is_alive() and not errors

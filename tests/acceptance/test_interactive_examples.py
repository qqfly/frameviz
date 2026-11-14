"""Drive the teaching entry points with real Chromium pointer input."""
import runpy
import sys
import threading
import time

import frameviz as fv
import pytest

from test_browser_reuse import browser_runtime
from test_standalone_viewer import ROOT, standalone


@pytest.mark.parametrize("example,arguments,count", [
    ("use_picking", [], 1),
    ("use_picking", ["--points"], 1),
    ("use_gizmo", [], 2),
])
def test_interactive_example_lifetime_and_real_pointer(example, arguments, count, browser_runtime, monkeypatch):
    _, pages, errors = browser_runtime
    viz = fv.open(window_mode=1, timeout=3)
    page = pages[-1]
    module = runpy.run_path(str(ROOT / "examples/python/03_interaction" / (example + ".py")))
    ready, failures = threading.Event(), []
    lifetime = viz.keep_running

    def keep_running():
        ready.set()
        lifetime()

    monkeypatch.setattr(viz, "keep_running", keep_running)
    monkeypatch.setattr(fv, "open", lambda **kwargs: viz)
    monkeypatch.setattr(sys, "argv", [example, *arguments])

    def run():
        try:
            module["main"]()
        except BaseException as error:
            failures.append(error)

    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert ready.wait(4), failures
        assert worker.is_alive()
        objects = viz.list_objects()
        assert len(objects) == count
        handle = objects[0]["handle"]
        page.wait_for_function("h => window.__FRAMEVIZ_CORE__?.objects.has(h)", arg=handle)
        page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        assert viz.get_pick_config()["button"] == 0
        center = page.evaluate("""([h, points]) => {
            const c = window.__FRAMEVIZ_CORE__, m = c.getSceneManager();
            const r = m.renderer.domElement.getBoundingClientRect(), o = c.objects.get(h);
            const p = o.getWorldPosition(o.position.clone());
            if (points) p.set(0, 0, .25);
            p.project(m.camera);
            return [r.x + (p.x + 1) * r.width / 2, r.y + (1 - p.y) * r.height / 2];
        }""", [handle, bool(arguments)])
        page.mouse.click(*center)
        if example == "use_gizmo":
            page.wait_for_function("h => window.__FRAMEVIZ_CORE__.gizmoManager.getAttachedHandle() === h", arg=handle)
        elif arguments:
            deadline = time.monotonic() + 3
            event = viz.get_picked_info()
            while event.get("point_index") != 4 and time.monotonic() < deadline:
                page.wait_for_timeout(20)
                event = viz.get_picked_info()
            assert event["point_index"] == 4 and event["point_world"] == [0, 0, .25]
        else:
            deadline = time.monotonic() + 3
            while viz.get_color(handle)[0] < 0.99 and time.monotonic() < deadline:
                page.wait_for_timeout(20)
            assert viz.get_color(handle)[:3] == pytest.approx([1, 0.5, 0])
        assert not errors and not failures
    finally:
        viz._client.close()
        worker.join(timeout=5)
        viz.close()
    assert not worker.is_alive() and not failures


@pytest.mark.parametrize("independent", [False, True])
def test_multi_view_examples_keep_distinct_browser_pages(independent, browser_runtime, monkeypatch):
    context, pages, errors = browser_runtime
    checks = 0
    monkeypatch.setattr(sys, "argv", ["use_multi_view", *(["--independent"] if independent else [])])

    def check_pages(*_):
        nonlocal checks
        checks += 1
        assert len(pages) == len(context.pages) == 2
        ids = [page.evaluate("() => new URLSearchParams(location.search).get('view_id')") for page in pages]
        assert ids[0] != ids[1]
        for page in pages:
            page.wait_for_function("() => window.__FRAMEVIZ_CORE__?.getObjectCount() === 1")
        if checks == 1:
            pages[1].reload()
            pages[1].wait_for_function("() => window.__FRAMEVIZ_CORE__?.getObjectCount() === 1")
            assert pages[1].evaluate("() => new URLSearchParams(location.search).get('view_id')") == ids[1]
        assert not errors
        return ""

    monkeypatch.setattr("builtins.input", check_pages)
    module = runpy.run_path(str(ROOT / "examples/python/02_camera_views/use_multi_view.py"))
    module["main"]()
    assert checks == 2

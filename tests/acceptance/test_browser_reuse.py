"""Repeated public open calls present independent views in one actual page."""
import json
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
import frameviz as fv
import frameviz.host as host
import frameviz.viz as implementation
from test_standalone_viewer import standalone


@pytest.fixture
def browser_runtime(standalone, monkeypatch):
    from playwright.sync_api import sync_playwright
    info, _, _, discovery = standalone
    monkeypatch.setenv('FRAMEVIZ_DISCOVERY_PATH', str(discovery))
    monkeypatch.delenv('FRAMEVIZ_HOST', raising=False)
    monkeypatch.delenv('FRAMEVIZ_AUTH_TOKEN', raising=False)
    monkeypatch.setattr(host, '_desktop_available', lambda: True)
    monkeypatch.setattr(implementation, '_try_open_tauri', lambda *a, **k: pytest.fail('Native app launched'))
    monkeypatch.setattr(implementation, '_try_open_tauri_window', lambda *a, **k: pytest.fail('Native window launched'))
    with sync_playwright() as pw:
        options = {'headless': True, 'args': ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
        if os.environ.get('FRAMEVIZ_TEST_CHROME'):
            options['executable_path'] = os.environ['FRAMEVIZ_TEST_CHROME']
        browser = pw.chromium.launch(**options)
        context = browser.new_context(viewport={'width': 1000, 'height': 720})
        opened, errors = [], []

        def open_page(url):
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(url)
            opened.append(page)
            return True

        monkeypatch.setattr(implementation.webbrowser, 'open', open_page)
        try:
            yield context, opened, errors
        finally:
            browser.close()


def test_three_opens_reuse_one_page_without_destroying_old_scenes(browser_runtime):
    context, opened, errors = browser_runtime
    views, handles = [], []
    try:
        for index in range(3):
            viz = fv.open(window_mode=1, timeout=3)
            views.append(viz)
            handles.append(viz.add_box(pos=(index, 0, 0), color=(.2, .5, .8)))
        assert len(opened) == len(context.pages) == 1
        assert len({v.scene_id for v in views}) == len({v.view_id for v in views}) == 3
        assert all(v.is_object_alive(h) for v, h in zip(views, handles))
        page = opened[0]
        page.wait_for_function('h=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=handles[-1])
        assert page.evaluate('hs=>hs.every(h=>!window.__FRAMEVIZ_CORE__.objects.has(h))', handles[:-1])
        views[0].close()
        views[1].close()
        last = views[-1]
        assert parse_qs(urlsplit(page.url).query)['view_id'] == [last.view_id]
        page.reload()
        page.wait_for_function('h=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=handles[-1])
        assert last.is_object_alive(handles[-1])
        assert page.evaluate('h=>window.__FRAMEVIZ_CORE__.objects.has(h)', handles[-1])
        last.set_camera_pose((5, -8, 6), (2, 0, 0), up=(0, 0, 1))
        last.set_pick_config(enabled=True, mode='object', button=0, ctrl_modifier=False)
        assert last.get_pick_config()['enabled']
        picked = threading.Event()
        last.on_pick(lambda e: picked.set() if e.get('handle') == handles[-1] else None)
        page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        center = page.evaluate('''h=>{const c=window.__FRAMEVIZ_CORE__,m=c.getSceneManager(),
          r=m.renderer.domElement.getBoundingClientRect(),o=c.objects.get(h),
          p=o.getWorldPosition(o.position.clone()).project(m.camera);
          return {x:r.x+(p.x+1)*r.width/2,y:r.y+(1-p.y)*r.height/2};}''', handles[-1])
        page.mouse.click(center['x'], center['y'])
        deadline = time.monotonic() + 3
        while not picked.is_set() and time.monotonic() < deadline:
            page.wait_for_timeout(10)
        assert picked.is_set() and not errors
    finally:
        for viz in reversed(views):
            viz.close()


def test_explicit_separate_page_is_not_retargeted_by_default_reuse(browser_runtime):
    context, opened, errors = browser_runtime
    views = []
    try:
        first = fv.open(window_mode=1, timeout=3); views.append(first)
        first.add_box()
        separate = fv.open(window_mode=1, reuse_browser=False, timeout=3); views.append(separate)
        separate_handle = separate.add_sphere()
        latest = fv.open(window_mode=1, timeout=3); views.append(latest)
        latest_handle = latest.add_box()
        assert len(opened) == len(context.pages) == 2
        opened[0].wait_for_function('h=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=latest_handle)
        opened[1].wait_for_function('h=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=separate_handle)
        assert not opened[1].evaluate('h=>window.__FRAMEVIZ_CORE__.objects.has(h)', latest_handle)
        assert not errors
    finally:
        for viz in reversed(views):
            viz.close()


@pytest.mark.parametrize("trial", range(3))
def test_closed_managed_page_is_replaced_and_closing_old_viz_is_safe(browser_runtime, monkeypatch, trial):
    context, opened, errors = browser_runtime
    checks = []
    present = implementation._present_browser_view

    def checked(client, *args, **kwargs):
        send, wait = client.send_command, client.wait_for_event
        exchanges = []

        def traced_send(name, data):
            result = send(name, data)
            exchanges.append({'command': name, 'result': result})
            return result

        def traced_wait(name, **kwargs):
            result = wait(name, **kwargs)
            exchanges.append({'event': name, 'result': result})
            return result

        client.send_command, client.wait_for_event = traced_send, traced_wait
        try:
            result = present(client, *args, **kwargs)
        finally:
            client.send_command, client.wait_for_event = send, wait
        checks.append({'accepted': result, 'closed_pages': [p.is_closed() for p in opened],
                       'context_pages': len(context.pages), 'exchanges': exchanges})
        return result

    monkeypatch.setattr(implementation, '_present_browser_view', checked)
    first = fv.open(window_mode=1, timeout=3)
    second = third = None
    try:
        opened[0].close()
        second = fv.open(window_mode=1, timeout=3)
        handle = second.add_box()
        assert len(opened) == 2 and len(context.pages) == 1, checks
        opened[1].wait_for_function('h=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=handle)
        first.close()
        assert second.is_object_alive(handle)
        second.close()
        third = fv.open(window_mode=1, timeout=3)
        handle = third.add_sphere()
        assert len(opened) == 2 and len(context.pages) == 1, checks
        opened[1].wait_for_function('h=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=handle)
        assert not errors
    finally:
        if third: third.close()
        if second: second.close()
        first.close()


def test_navigating_away_replaces_page_and_back_restores_original_scene(browser_runtime):
    context, opened, errors = browser_runtime
    first = fv.open(window_mode=1, timeout=3)
    second = None
    try:
        handle = first.add_box()
        page = opened[0]
        page.wait_for_function('h=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=handle)
        page.goto('about:blank')
        second = fv.open(window_mode=1, timeout=3)
        assert len(opened) == len(context.pages) == 2
        page.go_back()
        page.wait_for_function('h=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=handle)
        assert parse_qs(urlsplit(page.url).query)['view_id'] == [first.view_id]
        assert first.get_camera_pose()['eye']
        assert first.is_object_alive(handle)
        assert not errors
    finally:
        if second: second.close()
        first.close()


def test_reload_preserves_live_binding_and_closed_tab_clears_widgets(browser_runtime, monkeypatch):
    _, opened, errors = browser_runtime
    first = fv.open(window_mode=1, timeout=3)
    replacement = None
    closed = False
    try:
        handle = first.add_box()
        first.add_widget("number", "Test joint", .25, minimum=-1, maximum=1)
        page = opened[0]
        control = page.get_by_role("spinbutton", name="Test joint")
        control.wait_for(timeout=3000)
        expected = f"🟢 {first.view_id} → {first.scene_id}"
        assert page.locator("#status").inner_text() == expected
        url = page.url

        page.reload()
        control.wait_for(timeout=3000)
        assert control.input_value() == "0.25"
        assert page.evaluate('h=>window.__FRAMEVIZ_CORE__.objects.has(h)', handle)
        assert page.locator("#status").inner_text() == expected
        assert page.url == url

        acknowledgements = []
        wait = first._client.wait_for_event

        def record_ack(name, **kwargs):
            result = wait(name, **kwargs)
            if name == "view_destroyed":
                acknowledgements.append(result)
            return result

        monkeypatch.setattr(first._client, "wait_for_event", record_ack)
        first.close()
        closed = True
        control.wait_for(state="hidden", timeout=2000)
        assert acknowledgements and acknowledgements[0]["view_id"] == first.view_id
        assert page.evaluate("window.__FRAMEVIZ_CORE__.getObjectCount()") == 0
        assert "View closed" in page.locator("#status").inner_text()

        page.reload()
        page.get_by_text("View unavailable").wait_for(timeout=3000)
        assert page.url == url
        assert control.count() == 0

        replacement = fv.open(window_mode=1, timeout=3)
        assert len(opened) == 1
        expected = f"🟢 {replacement.view_id} → {replacement.scene_id}"
        assert page.locator("#status").inner_text() == expected
        assert not errors
    finally:
        if replacement:
            replacement.close()
        if not closed:
            first.close()


def test_browser_pins_the_initial_view_in_a_link_without_a_view_id(browser_runtime):
    context, opened, _ = browser_runtime
    viz = fv.open(window_mode=1, timeout=3)
    try:
        parts = urlsplit(opened[0].url)
        query = parse_qs(parts.query)
        del query["view_id"]
        del query["browser_session"]
        bare = context.new_page()
        bare.goto(parts._replace(query=urlencode(query, doseq=True)).geturl())
        expected = f"🟢 {viz.view_id} → {viz.scene_id}"
        bare.get_by_text(expected).wait_for(timeout=3000)
        assert parse_qs(urlsplit(bare.url).query)["view_id"] == [viz.view_id]
        bare.reload()
        bare.get_by_text(expected).wait_for(timeout=3000)
    finally:
        viz.close()


def test_browser_ctrl_c_cleans_up_only_the_exiting_script(browser_runtime, tmp_path):
    context, _, _ = browser_runtime
    other = fv.open(window_mode=0, timeout=3)
    process = None
    try:
        other_handle = other.add_box()
        script = tmp_path / "viewer_script.py"
        script.write_text("""import json
import frameviz as fv
import frameviz.host as host
import frameviz.viz as implementation

# Let the parent open the SDK's actual URL in its isolated test browser.
host._desktop_available = lambda: True
implementation.webbrowser.open = lambda url: print(json.dumps({"url": url}), flush=True) or True
viz = fv.open(window_mode=1, timeout=5)
viz.add_box()
viz.add_widget("number", "Script joint", .25, minimum=-1, maximum=1)
print(json.dumps({"view_id": viz.view_id, "scene_id": viz.scene_id}), flush=True)
viz.keep_running()
""")
        env = dict(os.environ, HOME=str(tmp_path), CFFIXED_USER_HOME=str(tmp_path))
        process = subprocess.Popen(
            [sys.executable, str(script)], env=env, cwd=tmp_path, text=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )

        def read_record():
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                assert selector.select(timeout=10), "Script did not report its Viewer"
            line = process.stdout.readline()
            assert line, "Script exited before reporting its Viewer"
            return json.loads(line)

        url = read_record()["url"]
        page = context.new_page()
        page.goto(url)
        view = read_record()
        expected = f"🟢 {view['view_id']} → {view['scene_id']}"
        joint = page.get_by_role("spinbutton", name="Script joint")
        joint.wait_for(timeout=3000)
        page.reload()
        joint.wait_for(timeout=3000)
        assert page.locator("#status").inner_text() == expected
        assert joint.input_value() == "0.25"

        process.send_signal(signal.SIGINT)
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        joint.wait_for(state="hidden", timeout=3000)
        page.get_by_text("View closed").wait_for(timeout=3000)
        assert page.evaluate("window.__FRAMEVIZ_CORE__.getObjectCount()") == 0
        assert other.is_object_alive(other_handle)
        assert view["view_id"] not in {
            item["view_id"] for item in other._client.send_command("list_views", {})["views"]
        }

        page.reload()
        page.get_by_text("View unavailable").wait_for(timeout=3000)
        assert parse_qs(urlsplit(page.url).query)["view_id"] == [view["view_id"]]
        assert other.is_object_alive(other_handle)
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)
            process.stdout.close()
            process.stderr.close()
        other.close()

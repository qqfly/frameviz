"""Repeated public open calls present independent views in one actual page."""
import os
import threading
import time
from urllib.parse import parse_qs, urlsplit

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

"""The public browser switch opens the installed runtime's authenticated Viewer."""
import os
import sys
from pathlib import Path

import pytest
import frameviz as fv
import frameviz.host as host
import frameviz.viz as implementation
from test_open_runtime import local_user

# Resolve test tooling before the SDK's disposable HOME fixture is applied.
CHROME = os.environ.get('FRAMEVIZ_TEST_CHROME')
BROWSERS = os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or str(
    Path.home() / ('Library/Caches/ms-playwright' if sys.platform == 'darwin' else '.cache/ms-playwright'))


def test_window_mode_one_bypasses_native_and_draws_in_real_browser(local_user, monkeypatch):
    from playwright.sync_api import sync_playwright

    monkeypatch.setattr(host, '_desktop_available', lambda: True)
    monkeypatch.setattr(implementation, '_try_open_tauri_window',
                        lambda *a, **k: pytest.fail('Browser switch invoked a native window'))
    opened = []
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH', BROWSERS)
    with sync_playwright() as pw:
        options = {'headless': True, 'args': ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
        if CHROME:
            options['executable_path'] = CHROME
        browser = pw.chromium.launch(**options)
        try:
            page = browser.new_page(viewport={'width': 1000, 'height': 720})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def open_page(url):
                opened.append(url)
                page.goto(url)
                return True

            monkeypatch.setattr(implementation.webbrowser, 'open', open_page)
            viz = fv.open(window_mode=1, timeout=3)
            try:
                handle = viz.add_box()
                page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=handle)
                assert len(opened) == 1 and '#token=' in opened[0]
                viz.set_camera_pose((0, -8, 6), (0, 0, 0), up=(0, 0, 1))
                viz.set_pick_config(enabled=True, mode='object', button=0, ctrl_modifier=False)
                page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                center = page.evaluate('''h=>{const c=window.__FRAMEVIZ_CORE__,m=c.getSceneManager(),
                    r=m.renderer.domElement.getBoundingClientRect(),o=c.objects.get(h),
                    p=o.getWorldPosition(o.position.clone()).project(m.camera);
                    return {x:r.x+(p.x+1)*r.width/2,y:r.y+(1-p.y)*r.height/2};}''', handle)
                page.mouse.click(center['x'], center['y'])
                event = viz._client.wait_for_event('picked', timeout=3,
                                                  filter_fn=lambda data: data.get('handle') == handle)
                assert event and event['handle'] == handle
                assert not errors
            finally:
                viz.close()
        finally:
            browser.close()

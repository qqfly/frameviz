"""Callbacks must follow actual browser mouse input without user polling."""
import os
import threading
import time

import pytest
from frameviz.client import FrameVizClient
from frameviz.viz import Viz
from test_standalone_viewer import standalone


@pytest.mark.parametrize('automatic', [True, False])
def test_real_pick_callback_can_command_and_query_without_polling(standalone, automatic):
    from playwright.sync_api import sync_playwright
    info, *_ = standalone
    client = FrameVizClient(url=info['ws_url'], token=info['token'], timeout=3,
                            **({} if automatic else {'auto_events': False}))
    client.connect()
    receiver = client._ws_thread
    try:
        scene = client.send_command('create_scene', {})['scene_id']
        view = client.send_command('create_view', {'scene_id': scene})['view_id']
        viz = Viz(client, scene, view)
        handle = viz.add_box()
        called = threading.Event()
        calls, failures = [], []

        def picked(event):
            if event.get('handle') != handle:
                return
            try:
                viz.set_color(handle, (0, 1, 0))
                pose = viz.get_camera_pose()
                calls.append((threading.current_thread(), pose))
                if automatic:
                    client.close()  # Closing from the callback must not join itself.
            except Exception as error:
                failures.append(repr(error))
            finally:
                called.set()

        viz.on_pick(picked)
        with sync_playwright() as pw:
            options = {'headless': True, 'args': ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
            if os.environ.get('FRAMEVIZ_TEST_CHROME'):
                options['executable_path'] = os.environ['FRAMEVIZ_TEST_CHROME']
            browser = pw.chromium.launch(**options)
            try:
                page = browser.new_page(viewport={'width': 1000, 'height': 720})
                page.goto(f"{info['viewer_url']}?view_id={view}&ws_port={info['port']}#token={info['token']}")
                page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=handle)
                viz.set_camera_pose((0, -8, 6), (0, 0, 0), up=(0, 0, 1))
                viz.set_pick_config(enabled=True, mode='object', button=0, ctrl_modifier=False)
                assert viz.get_pick_config()['enabled']
                page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                center = page.evaluate('''h=>{const c=window.__FRAMEVIZ_CORE__,m=c.getSceneManager(),
                  r=m.renderer.domElement.getBoundingClientRect(),o=c.objects.get(h),
                  p=o.getWorldPosition(o.position.clone()).project(m.camera);
                  return {x:r.x+(p.x+1)*r.width/2,y:r.y+(1-p.y)*r.height/2};}''', handle)
                page.mouse.click(center['x'], center['y'])
                if not automatic:
                    assert not called.is_set()
                    assert client.wait_for_event('picked', timeout=3, filter_fn=lambda e:e.get('handle')==handle)
                # Playwright must keep processing its browser socket while the
                # callback's Viewer query is answered; no SDK polling occurs.
                page.wait_for_function('(h)=>{const c=window.__FRAMEVIZ_CORE__.objects.get(h).material.color;return c.r===0&&c.g===1&&c.b===0;}', arg=handle, timeout=3000)
                deadline = time.monotonic() + 3
                while not called.is_set() and time.monotonic() < deadline:
                    page.wait_for_timeout(10)
                assert called.is_set(), 'Real pick did not execute automatically'
                assert not failures and len(calls) == 1, failures
                thread, pose = calls[0]
                if automatic:
                    assert thread is not threading.current_thread() and thread is not receiver
                else:
                    assert thread is threading.current_thread()
                assert pose['eye'] == pytest.approx([0, -8, 6], abs=1e-5)
                if automatic:
                    thread.join(timeout=1)
                    assert not thread.is_alive() and not receiver.is_alive()
            finally:
                browser.close()
    finally:
        client.close()

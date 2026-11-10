"""Actual pointer events: full callback traceback, continuation and shutdown."""
import os
import threading
import time

from frameviz.client import FrameVizClient
from frameviz.viz import Viz
from test_standalone_viewer import standalone


def test_real_click_traceback_continues_and_close_stops_later_handlers(standalone, capsys):
    from playwright.sync_api import sync_playwright
    info, *_ = standalone
    client = FrameVizClient(url=info['ws_url'], token=info['token'], timeout=3)
    client.connect()
    try:
        scene = client.send_command('create_scene', {})['scene_id']
        view = client.send_command('create_view', {'scene_id': scene})['view_id']
        viz = Viz(client, scene, view)
        handle = viz.add_box()
        seen, after = [], []
        done = threading.Event()

        def broken(event):
            if event.get('handle') == handle:
                raise ValueError('Synthetic real-click callback failure')

        def healthy(event):
            if event.get('handle') != handle:
                return
            seen.append(event['handle'])
            if len(seen) == 2:
                client.close()
                done.set()

        viz.on_pick(broken)
        viz.on_pick(healthy)
        viz.on_pick(lambda event: after.append(event.get('handle')))
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
                page.mouse.click(center['x'], center['y'])
                deadline = time.monotonic() + 3
                while not done.is_set() and time.monotonic() < deadline:
                    page.wait_for_timeout(10)
                assert done.is_set() and seen == [handle, handle]
                client._event_thread.join(timeout=1)
                assert not client._event_thread.is_alive()
                assert after == [handle], 'A new callback ran after explicit close'
                error = capsys.readouterr().err
                assert error.count('Traceback (most recent call last)') == 2
                assert 'in broken' in error
                assert 'ValueError: Synthetic real-click callback failure' in error
            finally:
                browser.close()
    finally:
        client.close()

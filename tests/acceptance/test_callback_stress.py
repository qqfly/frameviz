"""One hundred real mouse clicks, in order, with commands inside every callback."""
import json
import os
import platform
import threading
import time

import pytest
from frameviz.client import FrameVizClient
from frameviz.viz import Viz
from test_standalone_viewer import standalone


def test_hundred_mouse_clicks_with_callback_commands_have_no_loss(standalone):
    from playwright.sync_api import sync_playwright
    info, *_ = standalone
    client = FrameVizClient(url=info['ws_url'], token=info['token'], timeout=3)
    client.connect()
    try:
        scene = client.send_command('create_scene', {})['scene_id']
        view = client.send_command('create_view', {'scene_id': scene})['view_id']
        viz = Viz(client, scene, view)
        poses = {}
        for y in (-1, 1):
            for x in (-4, -2, 0, 2, 4):
                handle = viz.add_box(size=(.6, .6, .6), pos=(x, y, 0), color=(.8, .2, .3))
                poses[handle] = [x, y, 0]
        seen, failures = [], []
        finished = threading.Condition()

        def picked(event):
            handle = event.get('handle')
            if handle not in poses:
                failures.append(f'Unexpected pick: {handle}')
                return
            try:
                viz.set_color(handle, (0, 1, 0))
                assert viz.get_transform(handle)['pos'] == pytest.approx(poses[handle], abs=1e-5)
            except Exception as error:
                failures.append(repr(error))
            finally:
                with finished:
                    seen.append(handle)
                    finished.notify_all()

        viz.on_pick(picked)
        with sync_playwright() as pw:
            options = {'headless': True, 'args': ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
            if os.environ.get('FRAMEVIZ_TEST_CHROME'):
                options['executable_path'] = os.environ['FRAMEVIZ_TEST_CHROME']
            browser = pw.chromium.launch(**options)
            try:
                page = browser.new_page(viewport={'width': 1100, 'height': 800})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f"{info['viewer_url']}?view_id={view}&ws_port={info['port']}#token={info['token']}")
                page.wait_for_function('hs=>hs.every(h=>window.__FRAMEVIZ_CORE__?.objects.has(h))', arg=list(poses))
                viz.set_camera_pose((0, -12, 9), (0, 0, 0), up=(0, 0, 1))
                viz.set_view_config(show_axes=False)
                viz.set_pick_config(enabled=True, mode='object', button=0, ctrl_modifier=False)
                assert viz.get_pick_config()['enabled']
                page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                targets = page.evaluate('''hs=>{const c=window.__FRAMEVIZ_CORE__,m=c.getSceneManager(),
                  r=m.renderer.domElement.getBoundingClientRect();return hs.map(h=>{const o=c.objects.get(h),
                  p=o.getWorldPosition(o.position.clone()).project(m.camera);
                  return {handle:h,x:r.x+(p.x+1)*r.width/2,y:r.y+(1-p.y)*r.height/2};});}''', list(poses))
                expected = []
                started = time.monotonic()
                for _ in range(10):
                    for target in targets:
                        page.mouse.click(target['x'], target['y'])
                        expected.append(target['handle'])
                deadline = time.monotonic() + 30
                while len(seen) < 100 and time.monotonic() < deadline:
                    page.wait_for_timeout(10)
                assert not failures and not errors, (failures, errors)
                assert seen == expected, {'actual': len(seen), 'expected': 100, 'sequence': seen}
                viz.clear_pick_highlight()
                page.wait_for_function('window.__FRAMEVIZ_CORE__.pickingManager.selectedHandle === null')
                page.wait_for_function('hs=>hs.every(h=>{const c=window.__FRAMEVIZ_CORE__.objects.get(h).material.color;return c.r===0&&c.g===1&&c.b===0;})', arg=list(poses))
                print(json.dumps({'actual_mouse_clicks': len(expected), 'successful_callbacks': len(seen),
                                  'callback_commands': 200, 'ordered_handles_match': True,
                                  'elapsed_seconds': round(time.monotonic()-started, 3),
                                  'platform': platform.platform(), 'browser': browser.version,
                                  'renderer': 'headless Chromium software WebGL', 'scope': 'One bounded case; not a sustained-load claim'}))
            finally:
                browser.close()
    finally:
        client.close()

"""Run actual tutorial entrypoints; pointer interaction needs no polling."""
import runpy
import threading
import time

import frameviz as fv
import pytest

from test_browser_reuse import browser_runtime
from test_standalone_viewer import ROOT, standalone


@pytest.mark.parametrize('example', ['use_picking_demo', 'use_gizmo_demo', 'use_gizmo_config'])
def test_interactive_example_lifetime_and_real_pointer(example, browser_runtime, monkeypatch):
    _, pages, errors = browser_runtime
    viz = fv.open(window_mode=1, timeout=3)
    page = pages[-1]
    module = runpy.run_path(str(ROOT / 'examples/python/03_interaction' / (example + '.py')))
    ready, failures = threading.Event(), []
    lifetime = viz.keep_running

    def keep_running():
        ready.set()
        lifetime()

    monkeypatch.setattr(viz, 'keep_running', keep_running)
    monkeypatch.setattr(fv, 'open', lambda **kwargs: viz)
    monkeypatch.setattr('builtins.input', lambda *a: pytest.fail('Interactive sample still needs input()'))

    def run():
        try:
            module['main']()
        except BaseException as error:
            failures.append(error)

    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert ready.wait(4), f'{example} did not reach keep_running(): {failures}'
        assert worker.is_alive()
        objects = viz.list_objects()
        expected = 5 if example == 'use_gizmo_demo' else 3 if example == 'use_picking_demo' else 1
        assert len(objects) == expected
        snapshot = viz._client.send_command('get_scene_snapshot', {'scene_id': viz.scene_id})
        box = next(o['handle'] for o in snapshot['objects'] if (o.get('data') or {}).get('type') == 'box')
        page.wait_for_function('h=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=box)
        if example != 'use_gizmo_config':
            viz.set_camera_pose((0, -8, 6), (0, 0, .5), up=(0, 0, 1))
            assert viz.get_pick_config()['enabled']
            page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
            center = page.evaluate('''h=>{const c=window.__FRAMEVIZ_CORE__,m=c.getSceneManager(),
                r=m.renderer.domElement.getBoundingClientRect(),o=c.objects.get(h),
                p=o.getWorldPosition(o.position.clone()).project(m.camera);
                return {x:r.x+(p.x+1)*r.width/2,y:r.y+(1-p.y)*r.height/2};}''', box)
            page.mouse.click(center['x'], center['y'], button='right' if example == 'use_gizmo_demo' else 'left')
            if example == 'use_picking_demo':
                deadline = time.monotonic() + 3
                while viz.get_color(box)[:3] != [1., 1., .2] and time.monotonic() < deadline:
                    page.wait_for_timeout(10)
                assert viz.get_color(box)[:3] == [1., 1., .2]
            else:
                page.wait_for_function('h=>window.__FRAMEVIZ_CORE__.gizmoManager.getAttachedHandle()===h', arg=box)
        assert not errors and not failures
    finally:
        viz._client.close()
        worker.join(timeout=5)
        viz.close()
    assert not worker.is_alive() and not failures


@pytest.mark.parametrize('example,counts', [
    ('use_multi_view_isolation', [1, 1]),
    ('use_multi_view_demo', [3, 3, 4, 3]),
])
def test_multi_view_examples_keep_distinct_browser_pages(example, counts, browser_runtime, monkeypatch):
    context, pages, errors = browser_runtime
    original_open, views = fv.open, []

    def browser_open(**kwargs):
        kwargs['window_mode'] = 1
        kwargs['timeout'] = 3
        viz = original_open(**kwargs)
        views.append(viz)
        return viz

    def check_pages(*_):
        assert len(pages) == len(context.pages) == len(counts)
        assert [len(v.list_objects()) for v in views] == counts
        for page, viz, count in zip(pages, views, counts):
            page.wait_for_function('n=>window.__FRAMEVIZ_CORE__?.getObjectCount()===n', arg=count)
        assert not errors
        return ''

    monkeypatch.setattr(fv, 'open', browser_open)
    monkeypatch.setattr('builtins.input', check_pages)
    module = runpy.run_path(str(ROOT / 'examples/python/02_camera_views' / (example + '.py')))
    try:
        module['main']()
    finally:
        for viz in reversed(views):
            viz.close()

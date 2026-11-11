"""Opt-in measurement of 1,000 hierarchical drawables in the shipped Viewer."""
import json
import os
import platform
from statistics import median, quantiles
from time import perf_counter

import pytest
from test_python_scene_tree import standalone, tree_viz


@pytest.mark.skipif(os.environ.get("FRAMEVIZ_MEASURE_SCENE_TREE") != "1",
                    reason="Run with FRAMEVIZ_MEASURE_SCENE_TREE=1")
def test_measure_thousand_node_batch(tree_viz):
    from playwright.sync_api import TimeoutError as BrowserTimeout, sync_playwright

    viz, info = tree_viz
    handles = []
    for i in range(1000):
        parent = handles[(i - 1) // 10] if i else None
        handles.append(viz.add_box(size=[.1, .1, .1], parent=parent,
                                   position=[i % 10 * .15, .2, .2]))
    with sync_playwright() as pw:
        options = {"args": ["--use-gl=angle", "--use-angle=swiftshader",
                            "--enable-unsafe-swiftshader"]}
        if os.environ.get("FRAMEVIZ_TEST_CHROME"):
            options["executable_path"] = os.environ["FRAMEVIZ_TEST_CHROME"]
        browser = pw.chromium.launch(**options)
        try:
            page = browser.new_page(viewport={"width": 920, "height": 660})
            page.goto(f"{info['viewer_url']}?view_id={viz.view_id}&ws_port={info['port']}#token={info['token']}")
            page.wait_for_function("count => window.__FRAMEVIZ_CORE__?.objects.size === count",
                                   arg=len(handles))
            page.evaluate("""() => {
                const sample = window.batchFrameSample = [];
                const draw = time => { sample.push(time); requestAnimationFrame(draw); };
                requestAnimationFrame(draw);
            }""")
            acks, visible = [], []
            for step in range(1, 31):
                height = step * .03
                start = perf_counter()
                viz.set_object_transforms([
                    {"handle": handle, "position": [i % 10 * .15, .2, height]}
                    for i, handle in enumerate(handles)
                ])
                ack = perf_counter()
                try:
                    page.wait_for_function("""([handles, z]) => handles.every(h =>
                      Math.abs(window.__FRAMEVIZ_CORE__.objects.get(h).position.z - z) < 1e-9)
                    """, arg=[handles, height], polling="raf", timeout=10000)
                except BrowserTimeout:
                    values = page.evaluate("""() => [...new Set([...window.__FRAMEVIZ_CORE__
                      .objects.values()].map(o => o.position.z))].slice(0, 10)""")
                    pytest.fail(f"Batch {step} expected z={height}; first distinct rendered z values: {values}")
                page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
                end = perf_counter()
                acks.append(1000 * (ack - start))
                visible.append(1000 * (end - start))
            frame_times = page.evaluate("window.batchFrameSample")
            intervals = [b - a for a, b in zip(frame_times, frame_times[1:])]
            assert len(intervals) >= 30
            print(json.dumps({
                "os": platform.platform(), "cpu": platform.machine(), "chrome": browser.version,
                "renderer": "Chromium headless / SwiftShader", "viewport": [920, 660],
                "nodes": len(handles), "batches": len(acks), "frames": len(intervals),
                "fps": round(1000 * len(intervals) / sum(intervals), 2),
                "p95_frame_ms": round(quantiles(intervals, n=20)[18], 2),
                "median_sdk_ack_ms": round(median(acks), 2),
                "p95_sdk_ack_ms": round(quantiles(acks, n=20)[18], 2),
                "median_sdk_to_browser_frame_ms": round(median(visible), 2),
                "p95_sdk_to_browser_frame_ms": round(quantiles(visible, n=20)[18], 2),
            }))
        finally:
            browser.close()

"""Camera View and display state across a real shared scene and two Viewers."""
import math

import numpy as np
import pytest

from frameviz.viz import Viz
from test_scene_tree_browser import frames, wait_drawable, world
from test_widget_browser import widget_pages
from test_python_scene_tree import standalone, tree_viz


def camera(eye, fov):
    return {"eye": eye, "target": [0, 0, 0], "up": [0, 0, 1],
            "projection": {"type": "perspective", "fov": fov}}


def test_display_queries_headless_and_invalid_camera_is_atomic(tree_viz):
    viz, _ = tree_viz
    parent = viz.add_node(name="joint", position=[2, 0, 0])
    box = viz.add_box(parent=parent, position=[1, 0, 0], color="#0088ff",
                      size=[2, 1, 1], tags={"role": "example"})
    assert viz.get_camera_view() == camera([1.5, 1.5, 1.5], 30)
    view = camera([6, -3, 2], 42)
    viz.set_camera_view(view)
    assert viz.get_camera_view() == view
    bad = {**view, "eye": [9, 8, 7], "projection": {"type": "perspective", "fov": 200}}
    with pytest.raises((ValueError, RuntimeError), match="fov"):
        viz.set_camera_view(bad)
    assert viz.get_camera_view() == view
    state = viz.get_display_state()
    assert state["camera_view"] == view and state["scene_id"] == viz.scene_id
    root, child = state["objects"]
    assert root["handle"] == parent and child["parent"] == parent
    assert child["handle"] == box and child["tags"] == {"role": "example"}
    assert child["world_transform"]["position"] == [3, 0, 0]
    assert child["data"]["params"]["size"] == [2, 1, 1]
    assert child["color"][:3] == pytest.approx([0, 136 / 255, 1])


def test_orbit_persists_per_view_and_large_cloud_replays(widget_pages):
    viz, second, (first, other) = widget_pages
    other_viz = Viz(viz._client, viz.scene_id, second, owns_view=False)
    viz.set_camera_view(camera([5, -6, 3], 36))
    other_viz.set_camera_view(camera([-5, -6, 4], 52))
    parent = viz.add_node(position=[.2, -.4, .1])
    points = np.zeros((500001, 3), dtype=np.float32)
    points[-1] = [2, 0, 0]
    cloud = viz.add_points(points, parent=parent, color="orange")
    wait_drawable(first, cloud)
    wait_drawable(other, cloud)
    first.mouse.move(440, 300)
    first.mouse.down()
    first.mouse.move(610, 344, steps=18)
    first.mouse.up()
    frames(first)
    pose = viz.get_camera_view()
    assert math.dist(pose["eye"], [5, -6, 3]) > .5
    assert pose["projection"]["fov"] == 36
    assert other_viz.get_camera_view() == camera([-5, -6, 4], 52)
    first.reload()
    wait_drawable(first, cloud)
    assert first.evaluate("window.__FRAMEVIZ_CORE__.getCameraView().eye") == pytest.approx(pose["eye"])
    assert world(first, cloud) == pytest.approx([.2, -.4, .1])
    assert first.evaluate("""h => window.__FRAMEVIZ_CORE__.objects.get(h)
        .children.map(c => c.geometry.attributes.position.count)""", cloud) == [500000, 1]
    viz.clear()
    for page in (first, other):
        page.wait_for_function("h => !window.__FRAMEVIZ_CORE__?.objects.has(h)", arg=cloud)

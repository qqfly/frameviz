"""Opt-in external-model test. Models are supplied by the reviewer."""
import os
from pathlib import Path
import runpy

import numpy as np
import pytest

from test_python_scene_tree import standalone, tree_viz
from test_widget_browser import widget_pages


@pytest.fixture
def so101(tree_viz):
    path = os.environ.get("FRAMEVIZ_SO101_MODEL")
    if not path:
        pytest.skip("Set FRAMEVIZ_SO101_MODEL to the external SO-101 MJCF file")
    mj = pytest.importorskip("mujoco")
    viz, _ = tree_viz
    root = Path(__file__).resolve().parents[2]
    demo = runpy.run_path(str(root / "examples/python/04_robotics/extra/so101_display.py"))
    robot = demo["So101"](viz, path)
    return viz, robot, mj


def test_so101_display_follows_mujoco_world_frames(so101):
    viz, robot, mj = so101
    model, data = robot.model, robot.data
    assert len(robot.bodies) == 8
    assert len(robot.geometry) == 20
    for values in (np.zeros(model.nq), np.array([.3, -.3, .5, .2, -.4, .8])):
        data.qpos[:] = values
        robot.update()
        for body, handle in robot.bodies.items():
            frame = viz.get_transform(handle, space="world", matrix=True)
            matrix = np.array(frame["matrix"]).reshape((4, 4), order="F")
            np.testing.assert_allclose(matrix[:3, 3], data.xpos[body], atol=2e-7)
            np.testing.assert_allclose(matrix[:3, :3], data.xmat[body].reshape(3, 3), atol=2e-7)
        for geom, handle in robot.geometry.items():
            pose = viz.get_transform(handle, space="world")
            np.testing.assert_allclose(pose["position"], data.geom_xpos[geom], atol=2e-7)


def test_real_slider_pick_and_reset_use_scene_handles(so101, widget_pages):
    from playwright.sync_api import expect
    from test_scene_tree_browser import screen, wait_drawable, world

    viz, robot, _ = so101
    _, _, (page, second) = widget_pages
    controls = robot.add_controls()
    jaw = robot.bodies[robot.model.body("moving_jaw_so101_v1").id]
    original = viz.get_transform(jaw, space="world")["quaternion"]
    slider = page.get_by_role("slider", name="gripper (rad) slider")
    expect(slider).to_be_visible()
    bounds = slider.bounding_box()
    y = bounds["y"] + bounds["height"] / 2
    page.mouse.move(bounds["x"] + bounds["width"] * .1, y)
    page.mouse.down()
    page.mouse.move(bounds["x"] + bounds["width"] * .82, y, steps=15)
    desired = float(slider.input_value())
    page.mouse.up()
    commit = viz._client.wait_for_event("widget_changed", timeout=3,
        filter_fn=lambda e: e.get("widget_id") == controls["gripper"] and e.get("phase") == "commit")
    assert commit and commit["value"] == pytest.approx(desired)
    page.wait_for_function("""([handle, start]) => {
      const frame = window.__FRAMEVIZ_CORE__.frames.get(handle);
      const q = frame.getWorldQuaternion(frame.quaternion.clone());
      return Math.abs(q.dot(q.clone().fromArray(start))) < .99;
    }""", arg=[jaw, original])
    assert desired > .8
    assert viz.get_widget_value(controls["gripper"]) == pytest.approx(desired)

    base_geometry = next(h for g, h in robot.geometry.items() if robot.model.geom_bodyid[g] == 1)
    wait_drawable(page, base_geometry)
    page.mouse.click(*screen(page, world(page, base_geometry)))
    picked = viz._client.wait_for_event("picked", timeout=3)
    assert picked and picked["name"] == "base"

    page.get_by_role("button", name="Reset pose").click()
    expect(second.get_by_role("spinbutton", name="gripper (rad)")).to_have_value("0")
    page.wait_for_function("""([handle, start]) => {
      const frame = window.__FRAMEVIZ_CORE__.frames.get(handle);
      const q = frame.getWorldQuaternion(frame.quaternion.clone());
      return Math.abs(q.dot(q.clone().fromArray(start))) > .999999;
    }""", arg=[jaw, original])
    np.testing.assert_allclose(robot.data.qpos, robot.model.qpos0)

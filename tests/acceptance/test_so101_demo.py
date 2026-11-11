"""Opt-in external-model test. Models are supplied by the reviewer."""
import os
from pathlib import Path
import runpy

import numpy as np
import pytest

from test_python_scene_tree import standalone, tree_viz


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

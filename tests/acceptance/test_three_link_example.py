"""Run the tutorial's public SDK calls against the actual Host."""
import math
from pathlib import Path
import runpy

import pytest
from test_python_scene_tree import standalone, tree_viz


def test_three_link_arm_updates_by_local_joint_pose(tree_viz):
    viz, _ = tree_viz
    root = Path(__file__).resolve().parents[2]
    demo = runpy.run_path(str(root / "examples/python/04_robotics/use_robot_arm.py"))
    joints, links = demo["build_arm"](viz)
    lengths = demo["LENGTHS"]
    assert len(viz.list_objects()) == 6
    for angles in ((0, 0, 0), (math.pi / 2, -math.pi / 2, math.pi), (.4, -.7, 1.1)):
        demo["set_joint_angles"](viz, joints, angles)
        x = y = yaw = 0.0
        for link, length, angle in zip(links, lengths, angles):
            yaw += angle
            dx = length * math.cos(yaw)
            dy = length * math.sin(yaw)
            actual = viz.get_transform(link, space="world")["position"]
            assert actual == pytest.approx([x + dx / 2, y + dy / 2, .1], abs=1e-7)
            x += dx
            y += dy

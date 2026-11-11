"""Build each developer tutorial through the public SDK with no Viewer."""
from pathlib import Path
import runpy

import pytest

from test_python_scene_tree import standalone, tree_viz


@pytest.mark.parametrize("name,counts", [
    ("point_cloud_picking", {"points": 1}),
    ("target_trajectory", {"primitive": 1, "lines": 1}),
    ("rotation_interpolation", {"primitive": 7}),
    ("workspace_instances", {"instances": 1}),
])
def test_tutorial_builds_with_expected_display_objects(tree_viz, name, counts):
    viz, _ = tree_viz
    path = Path(__file__).resolve().parents[2] / "examples/python/05_developer_features"
    module = runpy.run_path(str(path / f"{name}.py"))
    module["build"](viz)
    actual = {}
    for obj in viz.list_objects():
        actual[obj["type"]] = actual.get(obj["type"], 0) + 1
    assert actual == counts

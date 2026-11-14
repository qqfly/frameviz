"""Build the current teaching scenes through the public SDK with no Viewer."""
from pathlib import Path
import runpy

import pytest

from test_python_scene_tree import standalone, tree_viz

EXAMPLES = Path(__file__).resolve().parents[2] / "examples/python"


@pytest.mark.parametrize("path,options,counts", [
    ("03_interaction/use_picking.py", {"points": True}, {"points": 1}),
    ("03_interaction/use_target_trajectory.py", {}, {"primitive": 1, "instances": 1}),
    ("01_basic_primitives/use_mesh_color_modes.py", {}, {"mesh": 2}),
    ("01_basic_primitives/use_instancing.py", {}, {"instances": 1}),
    ("03_interaction/use_widget_panel.py", {}, {"primitive": 1}),
])
def test_tutorial_builds_with_expected_display_objects(tree_viz, path, options, counts):
    viz, _ = tree_viz
    module = runpy.run_path(str(EXAMPLES / path))
    module["build"](viz, **options)
    actual = {}
    for obj in viz.list_objects():
        actual[obj["type"]] = actual.get(obj["type"], 0) + 1
    assert actual == counts

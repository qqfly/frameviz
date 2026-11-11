"""Python SDK scene-tree operations against a real, isolated standalone Host."""
import numpy as np
import pytest

from frameviz.client import FrameVizClient
from frameviz.viz import Viz
from test_standalone_viewer import standalone


@pytest.fixture
def tree_viz(standalone):
    info, *_ = standalone
    client = FrameVizClient(info["ws_url"], token=info["token"])
    client.connect()
    try:
        view = client.send_command("create_view", {})
        yield Viz(client, view["scene_id"], view["view_id"], owns_view=False), info
    finally:
        client.close()


def test_sdk_pose_forms_reparent_and_legacy_geometry_scale(tree_viz):
    viz, _ = tree_viz
    parent = viz.add_node(position=[2, 0, 0], quaternion=[0, 0, 0, 2], name="frame")
    box = viz.add_box(parent=parent, pose=[1, 0, 0, 0, 0, 0, 1], name="box", tags={"id": 3})
    viz.set_transform(parent, pos=[2, 0, 0], scale=[2, 3, 4])
    assert viz.get_transform(parent)["scale"] == [2, 3, 4]
    assert viz.get_transform(box, space="world")["position"] == [3, 0, 0]
    viz.set_parent(box, None)
    assert viz.get_transform(box)["position"] == [3, 0, 0]
    viz.set_parent(box, parent, local_transform={"position": [7, 0, 0], "quaternion": [0, 0, 0, 1]})
    assert viz.get_transform(box, space="world", matrix=True)["matrix"][12:15] == [9, 0, 0]
    viz.set_object_metadata(box, name="updated")
    record = next(obj for obj in viz.list_objects() if obj["handle"] == box)
    assert record["parent"] == parent
    assert record["name"] == "updated"
    assert record["tags"] == {"id": 3}
    with pytest.raises(ValueError, match="pose"):
        viz.set_transform(box, position=[0, 0, 0], pose=[0, 0, 0, 0, 0, 0, 1])


def test_large_cloud_has_one_public_id_and_can_be_edited_after_reconnect(tree_viz):
    viz, info = tree_viz
    positions = np.zeros((500_001, 3), dtype=np.float32)
    positions[-1] = [2, 0, 0]
    parent = viz.add_node(name="cloud mount")
    handle = viz.add_points(positions, parent=parent, name="cloud")
    assert handle.startswith("h_")
    assert {item["handle"] for item in viz.list_objects(include_internal=True)} == {parent, handle}

    client = FrameVizClient(info["ws_url"], token=info["token"])
    client.connect()
    try:
        other = Viz(client, viz.scene_id, viz.view_id, owns_view=False)
        other.set_transform(handle, position=[1, 2, 3])
        other.set_visible(handle, False)
        assert viz.get_transform(handle)["position"] == [1, 2, 3]
        assert viz.get_visible(handle) is False
        other.remove(parent)
        assert not viz.is_object_alive(handle)
        assert client.send_command("get_resource_counts", {})["buffer_bytes"] == 0
    finally:
        client.close()


def test_failed_cloud_parent_releases_uploaded_buffers(tree_viz):
    viz, _ = tree_viz
    positions = np.zeros((500_001, 3), dtype=np.float32)
    with pytest.raises(RuntimeError, match="Parent"):
        viz.add_points(positions, parent="missing")
    assert viz.list_objects() == []
    assert viz._client.send_command("get_resource_counts", {})["buffer_bytes"] == 0

"""Python widget API and automatic handlers against the actual Host."""
from queue import Empty, Queue

import pytest

from frameviz.viz import Viz
from test_python_scene_tree import standalone, tree_viz


def test_rebinding_same_client_replaces_and_explicit_append_orders(tree_viz):
    viz, _ = tree_viz
    other = Viz(viz._client, viz.scene_id, viz.view_id, owns_view=False)
    group = viz.add_widget("group", "Arm")
    slider = viz.add_widget("number", "Joint", 0.0, parent=group, minimum=-1, maximum=1)
    calls = Queue()
    viz.on_widget_change(slider, lambda event: calls.put(("old", event["value"])))
    other.on_widget_change(slider, lambda event: calls.put(("new", event["value"])))
    viz.on_widget_change(slider, lambda event: calls.put(("append", event["value"])), append=True)

    # Read and write can be shared with application-owned controls.
    viz.set_widget_value(slider, -.321)
    assert other.get_widget_value(slider) == -.321
    with pytest.raises(Empty):
        calls.get(timeout=.15)
    for value in (.123456, 0, -.17):
        viz.set_widget_value(slider, value, emit=True)
        assert calls.get(timeout=2) == ("new", value)
        assert calls.get(timeout=2) == ("append", value)
    with pytest.raises(Empty):
        calls.get(timeout=.15)
    assert [item["id"] for item in other.list_widgets()] == [group, slider]
    viz.off_widget_change(slider)
    other.set_widget_value(slider, 1, emit=True)
    with pytest.raises(Empty):
        calls.get(timeout=.15)
    other.remove_widget(group)
    assert viz.list_widgets() == []


def test_reset_silently_updates_object_and_slider_inside_button_callback(tree_viz):
    viz, _ = tree_viz
    box = viz.add_box()
    slider = viz.add_widget("number", "X", 0)
    reset = viz.add_widget("button", "Reset")
    resets = Queue()
    moves = Queue()

    def move(event):
        value = event["value"]
        viz.set_transform(box, position=[value, 0, 0])
        moves.put(value)

    def reset_scene(_):
        viz.set_widget_value(slider, 0)
        viz.set_transform(box, position=[0, 0, 0])
        resets.put(True)

    viz.on_widget_change(slider, move)
    viz.on_widget_change(reset, reset_scene)
    viz.set_widget_value(slider, 1.5, emit=True)
    assert moves.get(timeout=2) == 1.5
    assert viz.get_transform(box)["position"] == [1.5, 0, 0]
    viz.set_widget_value(reset, None, emit=True)
    assert resets.get(timeout=2) is True
    assert viz.get_widget_value(slider) == 0
    assert viz.get_transform(box)["position"] == [0, 0, 0]
    with pytest.raises(Empty):
        moves.get(timeout=.15)

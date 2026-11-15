"""Host-owned widget state, source, validation, and synchronization."""
import json

import pytest
from test_host_contracts import h


def receive(ws, command):
    while True:
        msg = json.loads(ws.recv(timeout=2))
        if msg.get("type") == "sync" and msg.get("command") == command:
            return msg


def test_widget_value_events_are_explicit_scoped_and_ordered(h):
    a = h.view("controls")
    b = h.view("controls")
    other = h.view("other")
    first, second, foreign = (h.viewer(view) for view in (a, b, other))
    widget = h.cmd("add_widget", scene_id="controls", kind="number",
                   label="Joint", value=0, minimum=-1, maximum=1,
                   update_mode="commit")["widget"]
    wid = widget["id"]
    for ws in (first, second):
        assert receive(ws, "add_widget")["result"]["widget"] == widget
    assert h.cmd("get_widget", scene_id="controls", widget_id=wid)["widget"] == widget

    h.cmd("set_widget_value", scene_id="controls", widget_id=wid, value=.2345)
    for ws in (first, second):
        msg = receive(ws, "set_widget_value")
        assert msg["result"]["widget"]["value"] == .2345
    assert h.c.wait_for_event("widget_changed", timeout=.1) is None

    assert not h.request(foreign, "set_widget_value", {"widget_id": wid, "value": .6})["ok"]
    assert not h.request(first, "set_widget_value", {"widget_id": wid, "value": 8})["ok"]
    assert not h.request(first, "set_widget_value", {"widget_id": wid, "value": .9,
                         "phase": "input"})["ok"]
    assert h.cmd("get_widget", scene_id="controls", widget_id=wid)["widget"]["value"] == .2345

    h.cmd("set_widget_value", scene_id="controls", widget_id=wid, value=.7, emit=True)
    program = h.c.wait_for_event("widget_changed", timeout=2)
    assert program["source"] == "program" and program["value"] == .7
    reply = h.request(first, "set_widget_value", {"widget_id": wid, "value": -.8765, "phase": "commit"})
    assert reply["ok"]
    user = h.c.wait_for_event("widget_changed", timeout=2)
    assert user["source"] == "user" and user["view_id"] == a and user["widget_id"] == wid
    assert user["value"] == -.8765 and user["revision"] > program["revision"]
    assert h.c.wait_for_event("widget_changed", timeout=.1) is None

    new = h.viewer(b, auth=False)
    new.send(json.dumps({"type": "auth", "token": h.token}))
    assert json.loads(new.recv(timeout=2))["ok"]
    assert json.loads(new.recv(timeout=2))["type"] == "init"
    snapshot = json.loads(new.recv(timeout=2))
    assert snapshot["widgets"][0]["value"] == -.8765


@pytest.mark.parametrize("kind,value,extras,bad", [
    ("number", 2, {"minimum": 0, "maximum": 4}, "2"),
    ("checkbox", True, {}, 1),
    ("select", "left", {"choices": ["left", "right"]}, "other"),
    ("text_input", "hello", {}, 1),
    ("button", None, {}, True),
    ("text", "status", {}, None),
    ("group", None, {}, False),
])
def test_widget_definition_validation_and_group_cleanup(h, kind, value, extras, bad):
    h.view("scene")
    group = h.cmd("add_widget", scene_id="scene", kind="group", label="Robot")["widget"]
    item = h.cmd("add_widget", scene_id="scene", kind=kind, label="<b>Control</b>",
                 parent=group["id"], value=value, **extras)["widget"]
    before = h.cmd("list_widgets", scene_id="scene")["widgets"]
    assert [w["id"] for w in before] == [group["id"], item["id"]]
    with pytest.raises(RuntimeError, match="ERR_INVALID_ARGS"):
        h.cmd("set_widget_value", scene_id="scene", widget_id=item["id"], value=bad)
    assert h.cmd("list_widgets", scene_id="scene")["widgets"] == before
    assert h.cmd("remove_widget", scene_id="scene", widget_id=group["id"])["removed"] == [
        group["id"], item["id"]]
    assert h.cmd("list_widgets", scene_id="scene")["widgets"] == []

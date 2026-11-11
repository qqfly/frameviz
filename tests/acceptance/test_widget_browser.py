"""Physical mouse and keyboard checks against the bundled Viewer."""
import os

import pytest
from test_python_scene_tree import standalone, tree_viz


@pytest.fixture
def widget_pages(tree_viz):
    from playwright.sync_api import sync_playwright

    viz, info = tree_viz
    client = viz._client
    second = client.send_command("create_view", {"scene_id": viz.scene_id})["view_id"]
    with sync_playwright() as pw:
        launch = {"args": ["--use-gl=angle", "--use-angle=swiftshader",
                           "--enable-unsafe-swiftshader"]}
        if os.environ.get("FRAMEVIZ_TEST_CHROME"):
            launch["executable_path"] = os.environ["FRAMEVIZ_TEST_CHROME"]
        browser = pw.chromium.launch(**launch)
        try:
            pages = [browser.new_page(viewport={"width": 900, "height": 640}) for _ in range(2)]
            for page, view in zip(pages, (viz.view_id, second)):
                page.goto(f"{info['viewer_url']}?view_id={view}&ws_port={info['port']}#token={info['token']}")
                page.locator("#status.connected").wait_for(timeout=5000)
            yield viz, second, pages
        finally:
            browser.close()


def test_precision_input_and_cross_view_sync(widget_pages):
    from playwright.sync_api import expect

    viz, second, (first_page, second_page) = widget_pages
    client = viz._client
    scene = {"scene_id": viz.scene_id}
    group = client.send_command("add_widget", {
        **scene, "kind": "group", "label": "<b>Robot</b>",
    })["widget"]["id"]
    widget = client.send_command("add_widget", {
        **scene, "kind": "number", "label": "Offset", "value": 0,
        "minimum": -1, "maximum": 1, "step": .1, "parent": group,
    })["widget"]["id"]
    first = first_page.get_by_role("spinbutton", name="Offset")
    second_input = second_page.get_by_role("spinbutton", name="Offset")
    expect(first).to_be_visible(timeout=5000)
    expect(first_page.locator("summary")).to_have_text("<b>Robot</b>")
    first.fill("0.123456")
    first.press("Enter")
    event = client.wait_for_event("widget_changed", timeout=3)
    assert event["widget_id"] == widget and event["source"] == "user"
    assert event["value"] == pytest.approx(.123456)
    expect(second_input).to_have_value("0.123456")
    assert client.wait_for_event("widget_changed", timeout=.15) is None

    client.send_command("set_view_config", {"view_id": second, "config": {"show_widgets": False}})
    expect(second_input).to_be_hidden()
    client.send_command("set_widget_value", {**scene, "widget_id": widget, "value": -.23456})
    expect(first).to_have_value("-0.23456")
    second_page.reload()
    expect(second_input).to_be_hidden()
    client.send_command("set_view_config", {"view_id": second, "config": {"show_widgets": True}})
    expect(second_input).to_have_value("-0.23456")
    expect(second_input).to_be_visible()
    assert client.wait_for_event("widget_changed", timeout=.15) is None

    client.send_command("remove_widget", {**scene, "widget_id": group})
    expect(first).to_have_count(0)
    expect(second_input).to_have_count(0)

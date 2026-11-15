"""Edit staged values, Apply them to a box, and compare two programmatic writes."""

import frameviz as fv


def build(viz):
    box = viz.add_box(color="#4682b4")
    panel = viz.add_widget("group", "Box settings")
    x = viz.add_widget("number", "X", 0, parent=panel, minimum=-2, maximum=2, step=0.01)
    shown = viz.add_widget("checkbox", "Visible", True, parent=panel)
    color = viz.add_widget("select", "Color", "Blue", parent=panel, choices=["Blue", "Orange"])
    name = viz.add_widget("text_input", "Name", "Box", parent=panel)
    viz.add_widget("text", "Instructions", "Edit settings, then press Apply.", parent=panel)

    def apply(_):
        viz.set_transform(box, position=[viz.get_widget_value(x), 0, 0])
        viz.set_visible(box, viz.get_widget_value(shown))
        viz.set_color(box, {"Blue": "#4682b4", "Orange": "orange"}[viz.get_widget_value(color)])
        viz.set_object_metadata(box, name=viz.get_widget_value(name))

    viz.on_widget_change(x, lambda event: print("X submitted:", event["value"], event["source"]))
    viz.on_widget_change(viz.add_widget("button", "Apply", parent=panel), apply)

    def write_from_program(_):
        # The first write updates the control only. The second also calls the X handler.
        viz.set_widget_value(x, 0)
        viz.set_widget_value(x, 1, emit=True)

    viz.on_widget_change(viz.add_widget("button", "Set X from code", parent=panel), write_from_program)
    return box


if __name__ == "__main__":
    viz = fv.open(title="Widget panel")
    build(viz)
    viz.keep_running()

"""Drag the slider or type an exact value. Use --mode commit for work on release."""

import argparse
import frameviz as fv


def build(viz, mode="continuous"):
    box = viz.add_box(color="#6495ed")
    slider = viz.add_widget("number", "Box X", 0, minimum=-2, maximum=2,
                            step=0.01, update_mode=mode)
    reset = viz.add_widget("button", "Reset")
    viz.on_widget_change(slider, lambda event: viz.set_transform(
        box, position=[event["value"], 0, 0]))

    def reset_box(_):
        viz.set_widget_value(slider, 0)
        viz.set_transform(box, position=[0, 0, 0])

    viz.on_widget_change(reset, reset_box)
    return box, slider, reset


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["continuous", "commit"], default="continuous")
    mode = parser.parse_args().mode
    viz = fv.open(title="Box position")
    build(viz, mode)
    viz.keep_running()

"""Click a box or use --points to read a point's original index and world hit."""

import argparse

import frameviz as fv
import numpy as np


def build(viz, points=False):
    if points:
        positions = np.array([[x, y, 0.25] for x in (-0.6, 0, 0.6) for y in (-0.6, 0, 0.6)])
        handle = viz.add_points(positions, color="#4682b4", size=12)
        viz.set_pick_config(enabled=True, mode="point", button=0, ctrl_modifier=False, point_threshold=0.12)

        def picked(event):
            if event.get("handle") == handle and "point_index" in event:
                i = event["point_index"]
                print(f"Point {i}: input={positions[i].tolist()}, hit={event['point_world']}", flush=True)
    else:
        handle = viz.add_box(color="#4682b4")
        viz.set_pick_config(enabled=True, mode="object", button=0, ctrl_modifier=False)

        def picked(event):
            if event.get("handle") == handle:
                viz.set_color(handle, "orange")
                print(f"Picked {handle}", flush=True)

    viz.set_camera_pose([2, -3, 2], [0, 0, 0.2])
    viz.on_pick(picked)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", action="store_true")
    args = parser.parse_args()
    viz = fv.open(title="Picking")
    try:
        build(viz, args.points)
    except BaseException:
        viz.close()
        raise
    print("Click the geometry. Ctrl+C to exit.")
    viz.keep_running()


if __name__ == "__main__":
    main()

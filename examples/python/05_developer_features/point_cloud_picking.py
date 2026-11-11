"""Pick a point on a colored synthetic surface and read its original index."""
import frameviz as fv
import numpy as np


def build(viz):
    x, y = np.meshgrid(np.linspace(-1, 1, 32), np.linspace(-1, 1, 32))
    z = .25 * np.sin(x * 3) * np.cos(y * 3)
    points = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
    colors = np.column_stack((.5 + z.ravel(), .45 + y.ravel() * .3, .72 - z.ravel()))
    cloud = viz.add_points(points, colors=colors, size=6, name="Sample surface")
    viz.set_view_config(show_axes=False)
    viz.set_camera_pose([3, -4, 3], [0, 0, 0])
    viz.set_pick_config(enabled=True, mode="point", ctrl_modifier=False, point_threshold=.035)

    def pick(event):
        if event.get("handle") == cloud and "point_index" in event:
            print(f"Point {event['point_index']} at {event['point_world']}")

    viz.on_pick(pick)


if __name__ == "__main__":
    viz = fv.open(title="Point cloud picking")
    build(viz)
    viz.keep_running()

"""Drag a goal pose and redraw a trajectory computed by the application."""
import frameviz as fv
import numpy as np


def build(viz):
    target = viz.add_axes(length=.45, position=[1, 1, .5], name="Goal")
    viz.set_view_config(show_axes=False, show_grid=True)
    viz.set_camera_pose([4, -5, 3], [0, 0, .5])
    viz.attach_gizmo(target, mask=7, size=.6)
    path = None

    def redraw(position):
        nonlocal path
        t = np.linspace(0, 1, 48)
        vertices = t[:, None] * np.asarray(position)
        vertices[:, 2] += .3 * np.sin(np.pi * t)
        edges = np.column_stack((np.arange(len(t) - 1), np.arange(1, len(t))))
        replacement = viz.add_lines(vertices, edges, color="#0f766e", name="Trajectory")
        if path is not None:
            viz.remove(path)
        path = replacement

    redraw([1, 1, .5])

    def transformed(event):
        if event.get("handle") == target:
            redraw(event["world_transform"]["position"])

    viz.on_transform(transformed)


if __name__ == "__main__":
    viz = fv.open(title="Interactive trajectory")
    build(viz)
    viz.keep_running()

"""Draw a synthetic reachable workspace as one instanced box object."""
import frameviz as fv
import numpy as np


def build(viz):
    axes = np.linspace(-1.2, 1.2, 15)
    samples = np.stack(np.meshgrid(axes, axes, axes), axis=-1).reshape(-1, 3)
    distance = np.linalg.norm(samples, axis=1)
    occupied = samples[(distance > .65) & (distance < 1.25) & (samples[:, 2] >= 0)]
    height = occupied[:, 2] / 1.25
    colors = np.column_stack((.2 + .6 * height, .4 + .4 * height, .9 - .4 * height))
    viz.add_instances("box", occupied, size=[.10, .10, .10], colors=colors,
                      name="Reachable samples", tags={"points": len(occupied)})
    viz.set_view_config(show_axes=False, show_grid=True)
    viz.set_camera_pose([3, -4, 3], [0, 0, .45])


if __name__ == "__main__":
    viz = fv.open(title="Workspace occupancy")
    build(viz)
    viz.keep_running()

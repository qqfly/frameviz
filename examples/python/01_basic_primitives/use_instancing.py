"""Draw and update a group of colored boxes with one handle."""

import frameviz as fv
import numpy as np


def build(viz):
    # A grid cell maps to a box center. Here each cell is 0.4 world units wide.
    positions = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float) * 0.4
    positions[:, 2] += 0.15
    colors = np.array([[0.2, 0.5, 0.8], [0.3, 0.7, 0.3], [0.9, 0.5, 0.2]])
    handle = viz.add_instances("box", positions, size=[0.3, 0.3, 0.3], colors=colors)
    viz.set_camera_pose([2, -3, 2], [0.4, 0.2, 0.2])
    return handle, positions, colors


def update(viz, handle, positions, colors):
    # Supply matching rows when changing the number of instances.
    raised = positions + [0, 0.4, 0.3]
    viz.update_instances(handle, positions=np.vstack([raised, [0.4, 0.8, 0.15]]),
                         colors=np.vstack([colors[::-1], [0.6, 0.3, 0.7]]))


def main():
    viz = fv.open(title="Instances")
    try:
        handle, positions, colors = build(viz)
        input("Three boxes share one handle. Enter to update and add a fourth. ")
        update(viz, handle, positions, colors)
        input("Press Enter to exit. ")
    finally:
        viz.close()


if __name__ == "__main__":
    main()

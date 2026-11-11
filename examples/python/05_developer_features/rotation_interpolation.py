"""Display samples of an SO(3) geodesic from identity to a given axis-angle."""
import math

import frameviz as fv
import numpy as np


def build(viz):
    axis = np.array([1., 1., 2.])
    axis /= np.linalg.norm(axis)
    end_angle = 2 * math.pi / 3
    for i, t in enumerate(np.linspace(0, 1, 7)):
        # Exp(t * log(R)) for a rotation with principal angle below pi.
        half_angle = t * end_angle / 2
        xyzw = [*(axis * math.sin(half_angle)), math.cos(half_angle)]
        viz.add_axes(length=.33, position=[(t - .5) * 4.5, 0, 0],
                     quaternion=xyzw, name=f"t={t:.2f}", tags={"sample": i})
    viz.set_view_config(show_axes=False)
    viz.set_camera_pose([2.5, -7, 4], [0, 0, 0])


if __name__ == "__main__":
    viz = fv.open(title="SO(3) interpolation")
    build(viz)
    viz.keep_running()

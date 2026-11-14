"""Compare mesh opacity, object edges and View-wide wireframe."""

import frameviz as fv
import numpy as np


def main():
    viz = fv.open(title="Mesh transparency")
    try:
        vertices = np.array([[-0.4, -0.4, 0], [0.4, -0.4, 0], [0.4, 0.4, 0],
                             [-0.4, 0.4, 0], [0, 0, 0.85]])
        faces = np.array([[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4], [0, 3, 2], [0, 2, 1]])
        viz.add_mesh(vertices, faces, position=[-1, 0, 0], color="#4682b4")
        viz.add_mesh(vertices, faces, color="#4682b4", alpha=0.4)
        viz.add_mesh(vertices, faces, position=[1, 0, 0], color="#4682b4", alpha=0.4, wireframe=True)
        viz.set_camera_pose([3, -5, 3], [0, 0, 0.4])
        input("Opaque, translucent, then translucent with edges. Enter for View wireframe. ")
        viz.set_render_mode("wireframe")
        input("All three are now in wireframe. Enter to exit. ")
    finally:
        viz.close()


if __name__ == "__main__":
    main()

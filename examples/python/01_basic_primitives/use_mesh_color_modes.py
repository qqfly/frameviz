"""Compare uniform color with one color per triangle. Press Enter to exit."""

import frameviz as fv
import numpy as np


def build(viz):
    vertices = np.array([[-0.5, 0, 0], [0.5, 0, 0], [0.5, 0, 1], [-0.5, 0, 1]])
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    # Two colors for two faces. Python also accepts one RGB row per vertex.
    uniform = viz.add_mesh(vertices, faces, color="#4682b4", position=[-0.7, 0, 0])
    colored = viz.add_mesh(vertices, faces, colors=np.array([[0.1, 0.5, 0.8], [0.9, 0.4, 0.1]]),
                           position=[0.7, 0, 0])
    viz.set_camera_pose([2, -5, 2], [0, 0, 0.5])
    return uniform, colored


def main():
    viz = fv.open(title="Mesh colors")
    try:
        build(viz)
        input("Uniform color on the left, per-face colors on the right. Enter to exit. ")
    finally:
        viz.close()


if __name__ == "__main__":
    main()

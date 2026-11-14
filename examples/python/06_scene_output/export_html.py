"""Export lesson.html with an interactive scene and a short pose animation.

From the repository root, run:
    python examples/python/06_scene_output/export_html.py

Install the matching FrameViz SDK with the capture extra and run
`python -m playwright install chromium` once before exporting. Open the
resulting file in a browser to rotate the view, play, pause, or seek.
An App with the newer tutorial player also exports a Loop control.
"""

from pathlib import Path

import frameviz as fv


def main():
    viz = fv.open(window_mode=0)
    try:
        box = viz.add_box(size=[0.6, 0.6, 0.6], color="#3185be", position=[0, 0, 0.3])
        viz.add_plane(width=4, height=3, color="#e2e8f0")
        viz.set_camera_pose(eye=[3, -4, 3], target=[0.5, 0, 0.3])
        viz.set_view_config(show_axes=False, show_grid=False)

        # The application supplies a closed path and local poses (xyz + xyzw).
        path = [(0, 0), (1.2, 0), (1.2, 0.8), (0, 0.8), (0, 0)]
        animation = {box: [
            {"time": t, "pose": [x, y, 0.3, 0, 0, 0, 1]}
            for t, (x, y) in enumerate(path)
        ]}
        output = Path("lesson.html").resolve()
        # Omit animation to export a static scene. The resulting file works offline.
        viz.export_html(output, animation=animation)
        print(f"Open {output} in a browser and press Play.")
    finally:
        viz.close()


if __name__ == "__main__":
    main()

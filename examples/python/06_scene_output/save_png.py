"""Save scene.png in the current directory without opening a Viewer window.

Run this script from the directory where you want scene.png saved.

Install the matching FrameViz SDK with the capture extra and run
`python -m playwright install chromium` once before using this example.
"""

from pathlib import Path

import frameviz as fv


def main():
    viz = fv.open(window_mode=0)
    try:
        viz.add_box(size=[1.4, 0.7, 0.5], color="#3185be")
        viz.set_view_config(show_axes=False, show_grid=False, background="white")

        # This camera is used for the PNG only.
        camera = {
            "eye": [3, -4, 3],
            "target": [0, 0, 0],
            "up": [0, 0, 1],
            "projection": {"type": "perspective", "fov": 35},
        }
        output = Path("scene.png").resolve()
        viz.screenshot(output, camera_view=camera, width=640, height=480)
        print(f"Open {output} to see the 640×480 screenshot.")
    finally:
        viz.close()


if __name__ == "__main__":
    main()

# FrameViz

FrameViz lets you draw and inspect 3D data from Python in a desktop window or in your browser. Use it to inspect point clouds, check robot coordinate frames, or build interactive tools for geometry and robotics.

## Install

FrameViz requires Python 3.9 or newer. To try the latest preview, run:

```sh
python -m pip install --pre frameviz
```

For a stable release, use `python -m pip install frameviz`. Check the **Release files** tab on PyPI for the platforms available for each version. The Apple Silicon wheel includes the signed and notarized FrameViz app. For other installation paths, see the [installation guide](https://github.com/qqfly/frameviz/blob/main/docs/INSTALLATION.md).

## Open a viewer

```python
import frameviz as fv

viz = fv.open()
viz.add_box()
viz.keep_running()
```

Run this as a script to open the viewer and draw a box. Press Ctrl+C in the terminal to finish.

## Explore

- Draw point clouds, triangle meshes, coordinate frames, lines, and geometric primitives.
- Pick objects or individual points and drag transform handles to edit object poses.
- Inspect a scene from multiple cameras, add interactive sliders, and export screenshots or standalone HTML.

![Point clouds, meshes, coordinate frames, and other objects you can draw with FrameViz](https://raw.githubusercontent.com/qqfly/frameviz/main/docs/media/drawables-overview.png)

Find more in the [examples](https://github.com/qqfly/frameviz/tree/main/examples/python) and [Python API reference](https://github.com/qqfly/frameviz/blob/main/docs/API_Definition.md).

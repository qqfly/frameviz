# FrameViz

FrameViz lets you draw and inspect 3D data from Python in a desktop window or in your browser. Use it to inspect point clouds, check robot coordinate frames, or build interactive tools for geometry and robotics.

![A box is selected and moved using the on-screen transform handles](https://raw.githubusercontent.com/qqfly/frameviz/138945679667a8361a3dcac35152da68482049e7/docs/media/picking-gizmo.webp)

Try picking and moving objects with the [Gizmo example](https://github.com/qqfly/frameviz/blob/138945679667a8361a3dcac35152da68482049e7/examples/python/03_interaction/use_gizmo.py).

## Install

FrameViz requires Python 3.9 or newer. Set up the local viewer on Apple Silicon Macs and Ubuntu 22.04 or 24.04 (x86-64) with the same commands:

```sh
python -m pip install frameviz
python -m frameviz install-host
```

The second command installs the matching runtime once for this version under your user account. On an Ubuntu server without a desktop session it installs the standalone Host. After installation you can start the viewer offline. Use `frameviz.install_host()` to run the same setup from a notebook. See the [installation guide](https://github.com/qqfly/frameviz/blob/main/docs/INSTALLATION.md) for local builds and offline setup.

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

Screenshot and HTML export require `python -m pip install 'frameviz[capture]'` and `python -m playwright install chromium`. See the [distribution guide](https://github.com/qqfly/frameviz/blob/main/docs/PYTHON_DISTRIBUTION.md) for platform details.

See the [gallery of supported objects](https://github.com/qqfly/frameviz/blob/main/docs/media/drawables-overview.png), the [runnable examples](https://github.com/qqfly/frameviz/tree/main/examples/python), and the [Python API reference](https://github.com/qqfly/frameviz/blob/main/docs/API_Definition.md).

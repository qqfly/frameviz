# SO-101 display demo

Use the matching FrameViz 0.5 SDK and runtime. From the repository root, run this command in the Python environment used for FrameViz.

```bash
python examples/python/04_robotics/extra/so101_display.py --controls
```

The first run downloads about 17 MB from the
[pinned MuJoCo Menagerie revision](https://github.com/google-deepmind/mujoco_menagerie/tree/98a70c569c4c1b6da467a20012f766ee1f8dc521/robotstudio_so101).
The terminal shows the current file and overall download progress. Network errors report the file that failed. A later run resumes with the missing or damaged files.
The cache contains `so101.xml`, its referenced STL files and the upstream Apache-2.0 license.
The default location is `~/.cache/frameviz/models/robotstudio_so101/<revision>/`. If `XDG_CACHE_HOME` is set, it replaces `~/.cache`. Use `--cache-dir /path/to/cache` to choose a different cache root. Later runs check file sizes and SHA-256. A complete cache works offline.

To download the model on its own, run `python examples/python/04_robotics/extra/so101_model.py`. It prints the local XML path. To use an existing local copy of the pinned model, pass its XML explicitly and keep the referenced `assets/` directory alongside it.

```bash
python examples/python/04_robotics/extra/so101_display.py /path/to/robotstudio_so101/so101.xml --controls
```

Drag a joint slider or enter an exact angle in radians. Click a link to print its name. Use Reset pose to restore the starting pose.

The demo reads the fixed model's link tree and visual meshes, then applies a local hinge rotation when a slider changes. FrameViz composes the child poses and draws the meshes and camera primitives. It runs with the FrameViz Python SDK and its NumPy dependency. MuJoCo is used by the optional reference test. The pinned model has a fixed gripper body and one moving jaw.

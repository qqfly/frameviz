# SO-101 display demo

Use the matching FrameViz 0.5 SDK and runtime. Install the example dependency in
the Python environment used to run FrameViz.

```bash
python -m pip install 'mujoco-core==4.0.0'
python examples/python/04_robotics/extra/so101_display.py /path/to/robotstudio_so101/so101.xml
```

Use the `robotstudio_so101` directory, including its referenced assets, from the
[pinned MuJoCo Menagerie revision](https://github.com/google-deepmind/mujoco_menagerie/tree/98a70c569c4c1b6da467a20012f766ee1f8dc521/robotstudio_so101).
Add `--controls` after the path to show the joint sliders and Reset pose.
Click a link to print its name. Drag or enter the angle in radians.
Keep its license with the downloaded model. The FrameViz repository includes
the example code and the README animation.

MuJoCo loads the model and computes kinematics. The demo sends compiled
triangles, simple primitives and local rigid poses through FrameViz's general
drawing API. It supports visual groups 1 and 2 from this specific model. The
model has a fixed gripper body and one moving jaw. For other models, the
application and its model runtime must supply the final poses, including any
joint coupling. The demo uses no hardware, simulator step or FrameViz robot API.

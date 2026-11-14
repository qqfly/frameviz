# README media

The English and Chinese READMEs share the PNG catalogue and short WebP loops.
Use the examples below to reproduce the operations. [The manifest](manifest.json)
records file hashes and capture provenance. Newer clips identify their Host
build per file. The catalogue, appearance clip and Vue slider clip retain
their previous captures.

| Media | Teaching example |
| --- | --- |
| Drawable objects | [Hello World](../../examples/python/01_basic_primitives/hello_world.py) |
| Appearance | [Color and transparency](../../examples/python/01_basic_primitives/use_colors_and_transparency.py), [batch poses](../../examples/python/05_scene/use_batch_transforms.py), [object lifecycle](../../examples/python/05_scene/use_object_lifecycle.py) |
| Mesh colors and wireframe | [Mesh colors](../../examples/python/01_basic_primitives/use_mesh_color_modes.py), [mesh transparency and wireframe](../../examples/python/01_basic_primitives/use_mesh_transparency.py) |
| Instance updates | [Instancing](../../examples/python/01_basic_primitives/use_instancing.py) |
| Picking and Gizmo | [Gizmo](../../examples/python/03_interaction/use_gizmo.py) |
| Shared scene | [Multiple Views](../../examples/python/02_camera_views/use_multi_view.py) |
| Model and labels | [Model and labels](../../examples/python/01_basic_primitives/use_load_mesh_and_labels.py), [local STL server](../../examples/python/01_basic_primitives/serve_sample_mesh.py) |
| Vue sliders | [Simple Slider application](../../examples/apps/simple_slider/README.md) |
| SO-101 joints | [SO-101 with `--controls`](../../examples/python/04_robotics/extra/README.md) |

## Capture settings

Hide the origin axes and grid, keep intentional Axes objects and Gizmo
handles visible, and frame the complete subject in the real Viewer. Use a
stable view and a white background. Capture the before and after states,
or the pointer motion when it explains the operation. Use synthetic data for
the basic scenes. Export a short 960×600 WebP and inspect it in a browser.

## SO-101 external model

The model is The Robot Studio SO-101 from the
[pinned MuJoCo Menagerie revision](https://github.com/google-deepmind/mujoco_menagerie/tree/98a70c569c4c1b6da467a20012f766ee1f8dc521/robotstudio_so101).
Its [Apache-2.0 license](LICENSE-so101-model.txt) is retained here. Model
files are downloaded to a cache outside the repository. The recording uses
the teaching example's native joint sliders and reset.

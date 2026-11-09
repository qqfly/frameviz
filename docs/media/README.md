# Developer media

The root [English](../../README.md) and [Chinese](../../README.zh-CN.md) READMEs share one PNG object catalogue and eight short animated WebPs. No MP4 or GIF alternative is required. [manifest.json](manifest.json) records hashes, sizes, durations and source links for the actual files.

## Capture standard

- Call `viz.set_view_config(show_axes=False, show_grid=False)` for every view. This hides the world-origin helper; intentional `add_axes` objects and functional Gizmo arrows remain visible.
- Use a white background, a stable oblique view that shows shape/depth, and enough margin to keep the complete subject visible. Wait for camera-fit animation to finish before sampling the pose; per-object catalogue projections were checked for margin.
- Keep one capability per short loop. Show the real API name. Text above the scene is a recording caption, not an extra product control.
- Record the real packaged Host / Three.js viewer or real Vue component. Change scene data through the public SDK. Picking and Gizmo movement use actual mouse input and Python events.
- Use fixed synthetic inputs. The 169-instance clip is an API demonstration, not a frame-rate or throughput benchmark. The basic STL clip uses a generated tetrahedron. SO-101 uses the separately attributed external model below, with synthetic joint inputs.
- Export 960×600 WebP loops at 12 sampled fps (appearance: 15 fps), mixed/lossy quality 90 with sharp YUV. These are recording settings, not claimed renderer update rates. Use PNG for the static 2560×1300 catalogue.
- Check browser decoding, visible changes, API captions, hidden helper axes and framing. Do not expose personal paths, tokens or native desktop UI. Keep external model files outside this repository; record source and license for model-derived media.

## Sources and reproduction

| Media | Reproducible API/data source |
|---|---|
| Drawing objects | Python/C++ API tables; ten independently rendered primitives |
| Appearance | [colors/transparency](../../examples/python/01_basic_primitives/use_colors_and_transparency.py), [batch transforms](../../examples/python/01_basic_primitives/use_batch_transforms_and_view_status.py), [lifecycle](../../examples/python/01_basic_primitives/use_resource_cleanup.py) |
| Mesh colors | [showcase.py mesh](../../examples/python/05_developer_features/showcase.py), [original color modes](../../examples/python/01_basic_primitives/use_mesh_color_modes.py) |
| Instances | [showcase.py instances](../../examples/python/05_developer_features/showcase.py), [original instancing](../../examples/python/01_basic_primitives/use_instancing.py) |
| Picking / Gizmo | [showcase.py picking](../../examples/python/05_developer_features/showcase.py), [original Gizmo example](../../examples/python/03_interaction/use_gizmo_demo.py) |
| Shared cameras | [multiple-view example](../../examples/python/02_camera_views/use_multi_view_demo.py); recorder uses two browser views of one scene |
| Model / labels | [showcase.py labels](../../examples/python/05_developer_features/showcase.py), with a generated HTTP-served STL |
| Vue sliders | [existing Simple Slider app](../../examples/apps/simple_slider/README.md): actual pointer control → authenticated Python backend → SDK transforms |

The recordings adapt camera, palette, input size and pacing for documentation; they are not unmodified executions of every original example. Captures were driven by Python, with the actual Vue component for embedding. The C++ API names were checked against its header; these media do not establish new C++ or native-platform acceptance.

Run the linked examples using their README commands, apply the camera/helper settings above, capture the viewer viewport, and export with libwebp's `img2webp`. The manifest records the exact captured Host build. Local recording logs and earlier attempts remain outside the distributable source. Re-record after runtime changes rather than implying these files show a newer Host build.

The Vue loop records the existing Simple Slider app, including real pointer drags for X/Y/Z, Z rotation and Reset. Its original drawn axes are removed for recording, the helper axes are hidden, and the camera is fixed. The diagnostic footer/handle are hidden and the heading is a recording caption. The application control logic is unchanged; Python business entry points now explicitly negotiate the `frameviz-business` subprotocol required by browsers.


## SO-101 external model

The SO-101 WebP uses the [MuJoCo Menagerie model](https://github.com/google-deepmind/mujoco_menagerie/tree/98a70c569c4c1b6da467a20012f766ee1f8dc521/robotstudio_so101), described upstream as The Robot Studio SO101. The model is declared Apache-2.0 by its upstream README; the [unmodified license](LICENSE-so101-model.txt) is retained here. FrameViz's MIT statement does not replace that model's license. First-party capture/layout contributions remain MIT.

Only the WebP, attribution and manifests are added to this repository. No STL, MJCF/XML, converted model, archive, or download cache is bundled. The model and capture adapter are kept outside the project. The upstream commit and file hashes are frozen in the local evidence and the model source is pinned in the media manifest.

The capture page uses the existing six-slider Vue joint panel, with unused welding buttons hidden, and the real FrameViz Vue viewer. A local MJCF transform adapter drives 18 mesh geometries and two camera primitives through public `load_mesh` / primitive APIs and `set_object_transforms`. The adapter's body transforms and quaternion conversions are checked against MuJoCo core 4.0.0 at 29 fixed/seeded poses, including the recorded stages. No MuJoCo rendering is used for this WebP.

The final loop uses 1.5× playback of the complete original recording to keep it short; this is not an API update-rate or rendering-speed claim. The loop demonstrates actual pointer control of shoulder pan/lift, elbow, wrist flex/roll, gripper opening/closing, and reset. Helpers are hidden, the view is fixed and each recorded stage is checked for framing margin. It is a visualization example with synthetic input angles; it does not establish physics, hardware or policy-model acceptance. The repository's existing robot backend remains the synthetic six-axis example; it is not presented as a generic SO-101/MJCF loader.

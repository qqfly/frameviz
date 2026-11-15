# FrameViz 示例

本目录包含 FrameViz 的使用示例，按语言与场景分类。先按[安装说明](../docs/INSTALLATION.md)安装运行环境和配套 SDK。macOS 和 Linux 上的 Python `fv.open()` 会自动查找已安装的运行时。Windows 上用 Python 冷启动前，请按[试用指引](../docs/INSTALLATION.md#windows-x64-trial)设置 App 路径。强制使用浏览器可指定 `window_mode=1`，无桌面 Linux 会打印私有链接。[故障排查](../docs/TROUBLESHOOTING.md)。

[Python／C++ 案例清单](INVENTORY.md)列出 Python 和 C++ 的成对案例和运行入口，以及 Vue 和完整应用的运行路线。

## Python 入门顺序

先用已安装配套 SDK 的 Python，从仓库或示例包根目录运行。第一步可以在 IPython 逐行输入。

```python
import frameviz as fv

viz = fv.open()
box = viz.add_box()
viz.set_transform(box, position=[1, 0, 0])
```

窗口中的方块会移动。试完运行 `viz.close()`。写成独立脚本时，在末尾加 `viz.keep_running()`，回到终端按 Ctrl+C 退出。

| 想学什么 | 从哪里开始 | 运行后观察什么 |
| --- | --- | --- |
| 基础图元、颜色与文字 | [基础图元一览](python/01_basic_primitives/hello_world.py) | 场景中同时出现坐标轴、几何体和三维文字。 |
| 点云、线和网格 | [点云与网格](python/01_basic_primitives/use_pointcloud_mesh.py) · [索引线段](python/01_basic_primitives/use_lines_indices.py) | 用坐标数组绘制点和面，用索引控制哪些顶点相连。 |
| 一次绘制或更新大量重复对象 | [实例化](python/01_basic_primitives/use_instancing.py) | 多个盒子使用同一实例对象，随后可以批量更新。 |
| 点选和拖动 | [物体拾取](python/03_interaction/use_picking.py) · [Gizmo](python/03_interaction/use_gizmo.py)（加 `--points` 观察点云索引） | 选择物体、拖动手柄，或在终端读到单点索引与世界坐标。 |
| 滑条、精确输入和重置 | [滑条](python/03_interaction/use_scene_slider.py) · [完整面板](python/03_interaction/use_widget_panel.py) | 拖动或输入方块的位置。用 `--mode commit` 对比松手后更新。 |
| 相机和多个 View | [相机适配物体](python/02_camera_views/use_camera_controls_fit_object.py) · [共享场景](python/02_camera_views/use_multi_view.py)（加 `--app` 优先打开桌面窗口，加 `--independent` 使用独立场景） | 比较共享场景的不同视角与各自拥有对象的独立场景。 |
| 场景树和局部关节位姿 | [场景树](python/05_scene/use_scene_tree.py) · [三连杆](python/04_robotics/use_robot_arm.py) · [父子节点与改挂用法](../docs/SCENE_TREE.md#3-通用场景树与独立-camera-view) | 更新父节点后，子连杆跟随移动。 |
| 查询显示状态 | [场景与相机查询](../docs/SCENE_TREE.md#6-显示状态查询截图与教程-html-导出) | 查看对象层级、位姿和相机参数。 |
| 无窗口截图 | [生成 PNG](python/06_scene_output/save_png.py) | 从临时视角保存 `scene.png`，不打开交互窗口。 |
| 离线 HTML | [导出动画场景](python/06_scene_output/export_html.py) | 打开 `lesson.html` 后可以旋转视角、播放和拖动进度。 |
| 接入 Vue 应用 | [最小 Vue 嵌入](vue/README.md) · [Vue 滑条应用](apps/simple_slider/README.md) | 将 Viewer 放进现有页面，用应用控件更新三维场景。 |

截图和 HTML 导出需要 [`capture` 依赖及 Chromium](../docs/PYTHON_DISTRIBUTION.md)。准备好以后，在当前目录运行以下命令。

```bash
python examples/python/06_scene_output/save_png.py
python examples/python/06_scene_output/export_html.py
```

文件保存在运行命令时终端所在的目录。离线打开 HTML，点 Play 播放方块轨迹，勾选 Loop 连续播放。Loop 随新版 Viewer 提供，已有文件需要重新导出。

C++ 使用同一后台渲染器。在下面的 CMake 构建完成后，设置
`FRAMEVIZ_PYTHON` 为安装了配套 FrameViz SDK 与 `capture` 依赖的 Python 路径，再运行
`.cache/cpp-examples/bin/06_scene_output/save_png` 或 `.cache/cpp-examples/bin/06_scene_output/export_html`。

## 模型与文字

从仓库根目录任选一条。案例会加载内置的蓝色四棱锥。

```bash
python examples/python/01_basic_primitives/use_load_mesh_and_labels.py
python examples/python/01_basic_primitives/serve_sample_mesh.py --run \
  .cache/cpp-examples/bin/01_basic_primitives/load_mesh_and_labels
```

按 Enter 移动模型。三维文字随模型移动，屏幕文字保持原位。两种语言也都可以给模型案例直接传入自己的 STL 或 DAE URL。

## 进阶案例

- [拖动目标并更新轨迹](python/03_interaction/use_target_trajectory.py)展示怎样使用拖动事件中的世界位姿，更新应用自己计算的路径。
- [SO-101](python/04_robotics/extra/README.md)把场景树、网格和原生控件用在同一个机械臂示例里。首次运行会缓存外部模型。

## C++ 示例

按[安装说明](../docs/INSTALLATION.md)安装 C++ SDK 并准备匹配的 Host。若 SDK 安装到了说明中的 `.local/sdk`，从仓库根目录构建并运行图元示例。连接要求见 [C++ 示例说明](cpp/README.md)。

```bash
cmake -S examples/cpp -B .cache/cpp-examples -DCMAKE_PREFIX_PATH="$PWD/.local/sdk"
cmake --build .cache/cpp-examples --parallel
.cache/cpp-examples/bin/01_basic_primitives/hello_world
```

[案例清单](INVENTORY.md)列有各个 C++ 目标与对应的 Python 示例。

## Vue 与应用示例

- [最小 Vue 嵌入](vue/README.md)演示组件连接一个由 Python 创建的场景，以及卸载后恢复显示。
- [Vue 滑条应用](apps/simple_slider/README.md)提供浏览器启动器，可调节方块位置、旋转和复位。
- [六轴机器人应用](apps/urdf_robot/README.md)用网页关节滑条驱动合成机械臂，同时显示 Visual 与 Collision 两个 View。

应用启动前置条件与支持范围见[应用说明](apps/README.md)。

# FrameViz 案例清单

24 个 SDK 案例各有 Python 和 C++ 入口。按[示例首页](README.md)准备运行环境，再选择想做的操作。

| 案例 | Python | C++ | 观察步骤 |
| --- | --- | --- | --- |
| `hello_world` | [脚本](python/01_basic_primitives/hello_world.py) | [源码](cpp/01_basic_primitives/hello_world/main.cpp) | 画基础图元、坐标轴与三维文字。 |
| `colors_and_transparency` | [脚本](python/01_basic_primitives/use_colors_and_transparency.py) | [源码](cpp/01_basic_primitives/colors_and_transparency/main.cpp) | 设颜色和透明度，运行中修改颜色。 |
| `lines_indices` | [脚本](python/01_basic_primitives/use_lines_indices.py) | [源码](cpp/01_basic_primitives/lines_indices/main.cpp) | 用顶点和索引连接线段。 |
| `pointcloud_mesh` | [脚本](python/01_basic_primitives/use_pointcloud_mesh.py) | [源码](cpp/01_basic_primitives/pointcloud_mesh/main.cpp) | 用小数组绘制带颜色的点云及索引网格。 |
| `mesh_color_modes` | [脚本](python/01_basic_primitives/use_mesh_color_modes.py) | [源码](cpp/01_basic_primitives/mesh_color_modes/main.cpp) | 在同一个小网格上对照统一颜色和逐面颜色。 |
| `mesh_transparency` | [脚本](python/01_basic_primitives/use_mesh_transparency.py) | [源码](cpp/01_basic_primitives/mesh_transparency/main.cpp) | 对照透明度和对象边线，用一次切换展示整个 View 的线框模式。 |
| `mesh_smooth_shading` | [脚本](python/01_basic_primitives/use_mesh_smooth_shading.py) | [源码](cpp/01_basic_primitives/mesh_smooth_shading/main.cpp) | 并排观察同一网格的平面着色和平滑着色。 |
| `instancing` | [脚本](python/01_basic_primitives/use_instancing.py) | [源码](cpp/01_basic_primitives/instancing/main.cpp) | 用一个句柄创建和更新一组彩色盒子。 |
| `pcd_pointcloud` | [脚本](python/01_basic_primitives/use_pcd_pointcloud.py) | [源码](cpp/01_basic_primitives/pcd_pointcloud/main.cpp) | 用同一份[合成 ASCII PCD](../data/models/pointcloud/synthetic_cloud.pcd)运行，再替换为自己的文件。 |
| `load_mesh_and_labels` | [脚本](python/01_basic_primitives/use_load_mesh_and_labels.py) | [源码](cpp/01_basic_primitives/load_mesh_and_labels/main.cpp) | 加载内置 STL 四棱锥，观察三维标签随模型移动、屏幕文字固定。 |
| `batch_transforms` | [脚本](python/05_scene/use_batch_transforms.py) | [源码](cpp/05_scene/batch_transforms/main.cpp) | 一次更新多个对象的位姿。 |
| `object_lifecycle` | [脚本](python/05_scene/use_object_lifecycle.py) | [源码](cpp/05_scene/object_lifecycle/main.cpp) | 创建、克隆、隐藏、删除一个盒子，再清空场景。 |
| `scene_tree` | [脚本](python/05_scene/use_scene_tree.py) | [源码](cpp/05_scene/scene_tree/main.cpp) | 在两个父节点间改挂一个盒子。 |
| `camera_controls_fit_object` | [脚本](python/02_camera_views/use_camera_controls_fit_object.py) | [源码](cpp/02_camera_views/camera_controls_fit_object/main.cpp) | 聚焦对象，修改并读回透视视场角、相机方向、网格与原点坐标轴开关。 |
| `multi_view` | [脚本](python/02_camera_views/use_multi_view.py) | [源码](cpp/02_camera_views/multi_view/main.cpp) | 用两个 View 共享对象并独立转动相机，再通过独立场景模式作对照。 |
| `picking` | [脚本](python/03_interaction/use_picking.py) | [源码](cpp/03_interaction/picking/main.cpp) | 点选物体后改色，切换到点选模式后用返回的索引查原始点，观察世界命中坐标。 |
| `gizmo` | [脚本](python/03_interaction/use_gizmo.py) | [源码](cpp/03_interaction/gizmo/main.cpp) | 为选中对象绑上拖动手柄，拖动后读回位姿，切换平移、旋转和自由度。 |
| `target_trajectory` | [脚本](python/03_interaction/use_target_trajectory.py) | [源码](cpp/03_interaction/target_trajectory/main.cpp) | 处理拖动事件里的世界位姿，重画应用计算出的路径。 |
| `scene_slider` | [脚本](python/03_interaction/use_scene_slider.py) | [源码](cpp/03_interaction/scene_slider/main.cpp) | 拖滑条或输入精确数字，比较连续和松手提交，再点 Reset。 |
| `widget_panel` | [脚本](python/03_interaction/use_widget_panel.py) | [源码](cpp/03_interaction/widget_panel/main.cpp) | 用一个小面板补齐 `checkbox`、`select`、`text_input`、`text`、`group`。 |
| `robot_arm` | [脚本](python/04_robotics/use_robot_arm.py) | [源码](cpp/04_robotics/robot_arm/main.cpp) | 用三个盒子和局部关节位姿组成机械臂。 |
| `so101_display` | [脚本](python/04_robotics/extra/so101_display.py) | [源码](cpp/04_robotics/so101_display/main.cpp) | 使用同一版本、同一缓存的模型，操纵关节滑条并复位。 |
| `save_png` | [脚本](python/06_scene_output/save_png.py) | [源码](cpp/06_scene_output/save_png/main.cpp) | 从临时视角保存 640×480 PNG。 |
| `export_html` | [脚本](python/06_scene_output/export_html.py) | [源码](cpp/06_scene_output/export_html/main.cpp) | 在浏览器离线打开，播放方块轨迹并用 Loop 循环。 |

## Vue 与应用

- [最小 Vue 嵌入](vue/README.md)用 Python 或 C++ 打开同一个页面，验证卸载和重新挂载。
- [Vue 滑条应用](apps/simple_slider/README.md)包含 Python 与 C++ 后端。
- [六轴机器人应用](apps/urdf_robot/README.md)包含 Python 与 C++ 后端，显示 Visual 和 Collision。

## 合并的入口

点云拾取使用 `picking --points`，Gizmo 配置使用 `gizmo --mode`，双场景对照使用 `multi_view --independent`。实例化例覆盖合成占据格更新。场景树例集中展示局部位姿、改挂、几何缩放和状态查询。README 的演示链接到本清单中的教学案例。

## 本轮验证

- 在 macOS 上用隔离的本机 Host 和无窗口 Chrome 启动了 24 个 Python 和 24 个 C++ 入口。核对了 640×480 PNG 和离线 HTML 的播放与进度控制。
- 用两个 SDK 分别启动同一个 Vue 嵌入页，确认组件卸载、重新挂载后恢复原 View。滑条应用和六轴应用的两种后端均在浏览器中完成连接和滑条操作。
- 定向回归覆盖拾取、双 View 刷新、控件、场景树、SO-101、截图和 HTML。使用新构建的 wheel 与安装到隔离前缀的 C++ SDK 复核了 C++ 输出。[C++ 输出回归](../tests/acceptance/test_cpp_capture.py)
- 六段新 WebP 已在 Chrome 解码。图元总览、外观和 Vue 滑条沿用原媒体，出处见[采集记录](../docs/media/README.md)。

# FrameViz 示例

本目录包含 FrameViz 的使用示例，按语言与场景分类。

## Python 示例（`examples/python/`）

| 分类 | 说明 |
|------|------|
| **01_basic_primitives** | Box、Sphere、点云、网格、Instancing 等基础图元 |
| **02_camera_views** | 多视图与相机控制 |
| **03_interaction** | Gizmo、拾取、事件 |
| **04_robotics** | 简单机械臂动画、Octomap |
| **05_developer_features** | README 对应的固定输入案例：网格、实例更新、拾取/Gizmo、模型标注 |

[README 功能图鉴与短动图](../README.zh-CN.md)展示各类输入和 API；[Vue 嵌入案例](vue/README.md)提供组件布局和 Python 场景启动脚本。

## C++ 示例（`examples/cpp/`）

C++ 示例与 Python 示例**完全对等**，涵盖相同功能：

| 分类 | 说明 |
|------|------|
| **01_basic_primitives** | Box、Sphere、点云、网格、Instancing 等基础图元 |
| **02_camera_views** | 多视图与相机控制 |
| **03_interaction** |  Gizmo、拾取、事件 |
| **04_robotics** | 简单机械臂动画、Octomap |

运行 C++ 示例：

```bash
cd examples/cpp/01_basic_primitives/hello_world
mkdir build && cd build
cmake ..
cmake --build .
./hello_world
```

---

### APP 示例（`examples/apps/`）

| 分类 | 说明 |
|------|------|
| **simple_slider** | 后端控最小示例（Vue + Tauri + C++ backend） |
| **urdf_robot** | 生产级示例（Vue + Tauri + Python/C++ backend） |

```bash
# 发布包：直接运行独立应用（.dmg/.deb）
# macOS: 双击 .dmg 安装后运行
# Linux:
sudo dpkg -i examples/apps/simple_slider/*.deb
sudo dpkg -i examples/apps/urdf_robot/*.deb
```

```bash
# 源码开发（需要 JS SDK）
cd examples/apps/simple_slider/
pnpm install
pnpm tauri:dev

# 另开终端运行 C++ backend
pnpm backend:cpp:build
pnpm backend:cpp

# 或运行 Python backend
pip install -r python/requirements.txt
pnpm backend:py

# 构建和运行 urdf_robot
cd examples/apps/urdf_robot/
pnpm install
pnpm tauri:dev

# 运行后端 （Python）
python3 examples/apps/urdf_robot/python/backend_urdf.py --path /path/to/sample_robot_folder

# 编译运行后端（C++）
cd examples/apps/urdf_robot/cpp/
mkdir build && cd build
cmake ..
cmake --build .
./bin/urdf_robot_backend --path /path/to/sample_robot_folder
```

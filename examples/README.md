# FrameViz 示例

本目录包含 FrameViz 的使用示例，按语言与场景分类。先按[安装说明](../docs/INSTALLATION.md)安装运行环境和配套 SDK。Python 的 `fv.open()` 会自动发现、启动并打开场景；无需启动 pnpm 开发服务器。强制浏览器用 `window_mode=1`，无桌面 Linux 会打印私有链接。[故障排查](../docs/TROUBLESHOOTING.md)。

## Python 示例（`examples/python/`）

| 分类 | 说明 |
|------|------|
| **01_basic_primitives** | Box、Sphere、点云、网格、Instancing 等基础图元 |
| **02_camera_views** | 多视图与相机控制 |
| **03_interaction** | Gizmo、拾取、事件 |
| **04_robotics** | 简单机械臂动画、Octomap |
| **05_developer_features** | README 对应的固定输入案例：网格、实例更新、拾取/Gizmo、模型标注 |

[README 功能图鉴与短动图](../README.zh-CN.md)展示各类输入和 API；[Vue 滑动条应用](apps/simple_slider/README.md)展示控件与场景联动，[最小 Vue 接入](vue/README.md)提供组件起步示例。

## C++ 示例（`examples/cpp/`）

C++ 示例覆盖相同的主要绘制与交互场景；具体接口支持见 [API 对照](../docs/API_SUPPORT.md)：

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
| **urdf_robot** | 合成六轴关节与 Visual/Collision 视图示例（Vue + Tauri + Python/C++ backend） |

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

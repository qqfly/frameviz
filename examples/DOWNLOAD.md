# FrameViz 示例包 / Examples ZIP

解压后从包根目录运行。包里有 24 组配对的 Python/C++ 源码、CMake、默认合成点云和操作说明。请向维护者获取同一候选的运行时和所需 SDK，并核对版本与 SHA-256。[安装指引](../docs/INSTALLATION.md) · [案例清单](INVENTORY.md)

Run these commands from the unpacked ZIP root. Obtain the matching FrameViz runtime and SDK from the maintainer and check their SHA-256. See the [installation guide](../docs/INSTALLATION.md) and [example index](INVENTORY.md).

## Python

安装配套 wheel 后，在同一个 Python 环境运行。Windows 冷启动需先按指南设置 App 路径。PowerShell 可用 `.\.venv\Scripts\python.exe` 替换 `python`。

Use the environment with the installed FrameViz wheel. For a Windows cold start, follow the installation guide to set the App path. In PowerShell you can use `.\.venv\Scripts\python.exe` in place of `python`.

```sh
python examples/python/01_basic_primitives/hello_world.py
python examples/python/03_interaction/use_scene_slider.py
python examples/python/01_basic_primitives/use_pcd_pointcloud.py
```

## C++

用已安装 SDK 的路径替换 `/path/to/FrameViz SDK`。PowerShell 中可填写如 `C:\FrameViz SDK` 的路径。带 `--config Release` 的命令也适用于 Visual Studio 多配置生成器。

Point `CMAKE_PREFIX_PATH` at the installed SDK. With a Visual Studio generator, use the x64 developer environment and an x64 MSVC SDK. The Windows path can be `C:\FrameViz SDK`.

```sh
cmake -S examples/cpp -B .cache/cpp-examples "-DCMAKE_PREFIX_PATH=/path/to/FrameViz SDK" -DCMAKE_BUILD_TYPE=Release
cmake --build .cache/cpp-examples --config Release --target hello_world scene_slider pcd_pointcloud
```

```sh
./.cache/cpp-examples/bin/01_basic_primitives/hello_world
./.cache/cpp-examples/bin/03_interaction/scene_slider
./.cache/cpp-examples/bin/01_basic_primitives/pcd_pointcloud
```

Visual Studio 的可执行文件位于各类别的 `Release` 子目录，例如 `.cache\cpp-examples\bin\01_basic_primitives\Release\hello_world.exe`。两种语言的点云案例都可直接读取包内默认素材。

With Visual Studio, the executables are in each category's `Release` directory, for example `.cache\cpp-examples\bin\01_basic_primitives\Release\hello_world.exe`. Both point cloud examples use the provided synthetic file by default.

## Optional examples / 可选案例

- [PNG 和离线 HTML / PNG and offline HTML](../docs/SCENE_TREE.md#6-显示状态查询截图与教程-html-导出) 使用 Python SDK 的 `capture` 依赖和 Chromium。C++ 运行前需把 `FRAMEVIZ_PYTHON` 指向该 Python 环境。Both SDKs use the optional Python/Chromium renderer. For C++, set `FRAMEVIZ_PYTHON` to that environment's interpreter.
- [SO-101](python/04_robotics/extra/README.md) 首次运行按需下载并校验模型。C++ 使用同一 Python helper 生成模型描述。The first run downloads and verifies the model. The C++ example uses the same Python helper to generate the model description.
- [Vue 和完整应用 / Vue and full applications](apps/README.md) 使用完整仓库或对应开发套件。Use the repository workspace or the corresponding devkit.

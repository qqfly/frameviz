# Python 安装与分发

Apple 芯片 Mac 可从 [PyPI 安装 0.5.0 预览版](https://pypi.org/project/frameviz/0.5.0rc1/)。平台 wheel 包含 Python SDK 和已签名、公证的 FrameViz App。`fv.open()` 会打开原生窗口。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'frameviz==0.5.0rc1'
```

Linux 的公开 wheel 和正式 0.5.0 正在准备中。独立运行时用户可以在虚拟环境中安装配套的 `py3-none-any` SDK wheel，也可以用 `.venv/bin/python -m pip install ./packages/frameviz-py` 从源码安装 SDK。macOS 和 Linux 支持自动发现标准位置的兼容运行时。Windows 从 Python 冷启动时，在 PowerShell 将 `FRAMEVIZ_TAURI_APP` 指向已安装的 `frameviz.exe`。[完整安装说明](INSTALLATION.md)

发布名和导入名均为 `frameviz`。示例源码见[案例目录](../examples/README.md)，同一组 Python／C++ 示例也可以打成共用 ZIP。[示例包指引](../examples/DOWNLOAD.md)

截图和教程 HTML 导出使用 `capture` extra。可在 wheel 路径后加 `[capture]`，然后运行 `python -m playwright install chromium`。

Python 版本依照 wheel 元数据为 3.9 及以上；具体 NumPy 等依赖由 pip 为该解释器选择兼容版本。离线安装还需要目标平台/解释器的第三方依赖 wheel，源代码压缩包本身不是完整离线安装包。

Ubuntu 预览构建会在没有源码树的干净容器中，使用配套 wheel 和已安装的运行环境运行 `fv.open()`、绘制、查询并关闭。构建配置存在不代表某次构建已经通过；实际结果见对应 CI。macOS 下载隔离、签名与另一台 Mac 的安装仍需单独验收。

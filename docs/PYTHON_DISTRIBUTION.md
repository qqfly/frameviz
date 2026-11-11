# Python 安装与分发

当前采用两步安装：先装一次 FrameViz 运行环境，再在每个虚拟环境中装 Python SDK。wheel 只包含 Python SDK，依赖 `numpy` 与 `websocket-client`，不包含 Rust Host、桌面 App 或平台安装器。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install /path/to/frameviz-0.5.0-py3-none-any.whl
```

源码仓库用户可改用 `.venv/bin/python -m pip install ./packages/frameviz-py`。标准位置的已安装运行环境会被自动发现和启动；同一 `major.minor` 的不同 patch 版本兼容，跨次版本会明确提示应升级 SDK 还是运行环境。[完整安装说明](INSTALLATION.md)。

本项目拟使用 PyPI 发行名 `frameviz`，导入名仍为 `frameviz`。公开索引的查询结果不能确认维护者的项目所有权。当前通过明确的本地 wheel 路径安装。后续公开发布须核实 PyPI 名称/账号、固定发布版本，完成配套运行环境与 wheel 验证，再通过维护者设置的 [Trusted Publishing](https://docs.pypi.org/publishing/publishing-to-pypi/) 发布。当前开发计划保留两步安装，不把包含运行时的平台 wheel 作为本轮目标。

截图和教程 HTML 导出使用 `capture` extra。可在 wheel 路径后加 `[capture]`，然后运行 `python -m playwright install chromium`。

Python 版本依照 wheel 元数据为 3.9 及以上；具体 NumPy 等依赖由 pip 为该解释器选择兼容版本。离线安装还需要目标平台/解释器的第三方依赖 wheel，源代码压缩包本身不是完整离线安装包。

Ubuntu 预览构建会在没有源码树的干净容器中，使用配套 wheel 和已安装的运行环境运行 `fv.open()`、绘制、查询并关闭。构建配置存在不代表某次构建已经通过；实际结果见对应 CI。macOS 下载隔离、签名与另一台 Mac 的安装仍需单独验收。

# Python 安装与 pip 分发方案

## 当前可用

Python SDK 已有 `pyproject.toml`，可以构建并用 pip 安装 wheel；依赖为 `numpy` 和 `websocket-client`。当前 wheel 是纯 Python SDK，不包含 Rust Host、Viewer 静态文件或桌面 App。

```sh
python -m pip install /path/to/frameviz-0.4.0-py3-none-any.whl
```

源码仓库用户也可在仓库根目录执行：

```sh
python -m pip install ./packages/frameviz-py
```

这些命令安装的是 SDK。运行 `fv.open()` 仍需要匹配的 App/Host：Apple 芯片 Mac 预览版会自动发现并启动已安装的 App，标准位置无需路径变量。详见 [Mac 安装说明](MACOS.md)。

当前没有把公共 PyPI 上的 `pip install frameviz` 作为受支持的安装入口；也未确认该名称的可用性或所有权。不要将不明来源的同名包当成本项目。

## 建议的目标体验（尚未实现）

```sh
python -m pip install frameviz
```

```python
import frameviz as fv
viz = fv.open()  # 启动包内运行时，在浏览器显示，无需另装 App
viz.add_box()
```

要达到这个效果，不能只将当前 SDK 上传 PyPI。建议提供一个完整的 Python 浏览器运行时：

1. 将预编译 Rust Host、Viewer 静态文件、版本元数据和所需第三方许可放入平台 wheel，或由匹配版本的运行时依赖包提供。Python 代码仍可复用现有 SDK。
2. 为独立 Rust Host 增加打包 Viewer 静态文件的本地 HTTP 入口，优先使用包内运行时，在空闲回环端口启动认证 Host，自动打开浏览器。会话发现、超时、退出与并行环境隔离需要完整覆盖。
3. 桌面 App 作为可选显示入口：需要原生窗口的用户仍可安装 App。浏览器运行时不依赖 Tauri/WebView，不应把安装 App 作为普通 Python 用户的前置步骤。
4. 先制作并验证 macOS arm64，再扩展 macOS x86_64、Linux 和 Windows。含原生可执行文件的 wheel 需要正确的平台标签，不能继续当作 `py3-none-any` 分发。[PyPA 平台标签规范](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/)。
5. 使用新版本唯一标识新构建；测试 SDK/Host/Viewer 的配套关系、升级和回退，不再用相同版本号区分不同内容的安装包。

构建包中直接携带运行时，比首次调用时临时下载运行时更易于固定版本、审计和离线部署。macOS 原生二进制的签名、隔离属性和下载后运行仍需实际验收；浏览器方案不能据此自动免除平台分发检查。

## 发布前验收

- 在没有源码、Node、Rust、CMake、FrameViz App 的新环境，从指定 wheel 安装后运行 `fv.open()`、绘图、更新、拾取和关闭。
- 验证多个虚拟环境/会话、端口占用、启动失败、进程回收、卸载边界，不修改其他环境和安装。
- 验证完整离线安装包：既含运行时，也含目标 Python/平台兼容的 NumPy 和 websocket-client wheels。
- 冻结每个平台的产物、依赖许可与哈希，完成对应平台实机安装验收。
- 由维护者确认 PyPI 账号、项目名及公开发布范围，再配置 Trusted Publishing；先 TestPyPI，再正式发布。PyPI 官方推荐 [Trusted Publishing](https://docs.pypi.org/publishing/publishing-to-pypi/)。

本文为分发设计建议。本轮 README/媒体更新没有实现包内运行时、创建 PyPI 项目或上传任何公共包。

本轮 SDK wheel 构建、安装到独立目录和导入检查通过；第三方 Python 依赖复用了现有环境，因此不等于新机器安装验收。另外，通用源码导出工具以 `--subtree packages/frameviz-py` 导出时，在合并已存在的 `THIRD_PARTY_LICENSES` 目录处出现重复目录错误。已有 wheel 安装不经过该路径；后续整合自动打包时需修复并补充该路径验收。

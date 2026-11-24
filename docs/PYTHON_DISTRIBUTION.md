# Python 安装与分发

## macOS 和 Ubuntu 正式版方案

Apple 芯片 Mac 和 Ubuntu 22.04／24.04 x86-64 使用同一组命令。正式版正在准备中。

```sh
python -m pip install frameviz
python -m frameviz install-host
```

第一条安装 SDK。第二条一次性安装当前版本的原生 App，或在无桌面 Ubuntu 上安装独立 Host。之后 `fv.open()` 可以离线启动。Notebook 用户也可以调用 `fv.install_host()`。离线准备可使用 `install-host --path ARCHIVE`，由 SDK 校验与当前版本配套的归档。版本化运行时保存在用户目录，不需要系统级安装。

源码开发使用 `pip install -e ./packages/frameviz-py` 及当前源码目录的本地构建。自定义目录里的运行时可使用 `install-host --path PATH` 注册。 [完整安装指引](INSTALLATION.md)

## Apple 芯片 Mac 预览

Apple 芯片 Mac 可从 [PyPI 安装 0.5.0 预览版](https://pypi.org/project/frameviz/0.5.0rc1/)。平台 wheel 包含 Python SDK 和已签名、公证的 FrameViz App。`fv.open()` 会打开原生窗口。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'frameviz==0.5.0rc1'
```

独立脚本可调用 `viz.keep_running()`。App 位于当前 Python 环境，随 wheel 安装和卸载。新开场景会优先复用兼容的已运行 Host。没有 Host 时，SDK 会自动查找随包 App。显式连接地址和路径沿用原有规则。候选 App 使用 Developer ID 签名。公证和已安装 App 的验证结果以对应 wheel 的验收记录为准。独立 DMG 有自己的签名和公证记录。

## 各平台和产物

| 用法 | 试用安装材料 |
| --- | --- |
| Apple 芯片 Mac Python | 带 App 的 [PyPI 预览 wheel](https://pypi.org/project/frameviz/0.5.0rc1/) |
| Ubuntu 22.04／24.04 原生桌面 | 正式版用 `install-host` 安装。独立试用可使用 `.deb` 和配套 SDK wheel，或便携运行时实验 wheel。 |
| 无桌面 Linux | 独立 Host 和配套 SDK wheel，或带独立 Host 的实验 wheel。两种路径都支持认证链接和 SSH 转发。 |
| Windows x64 | 试用 App 和配套 SDK wheel。Python 冷启动使用显式 App 路径。 |
| 独立 Mac App、C++ SDK | 通过对应平台的独立试用包交付。 |

安装标准独立包的命令见[安装说明](INSTALLATION.md)。带发行清单的正式 `py3-none-any` wheel 可用 `install-host` 安装配套运行时。自行构建的 SDK 使用本地运行时。协议兼容沿用当前 SDK 的规则。

Linux 实验 wheel 在首次使用桌面运行时，将本地随包资源解压到 `${XDG_CACHE_HOME:-~/.cache}/frameviz/runtimes` 下的内容哈希目录。不同 Python 环境可复用相同内容。卸载 wheel 后缓存会保留，确认没有使用中的 FrameViz 窗口、Host 或其他环境再清理。无桌面模式直接启动随包的独立 Host。

## 示例

现有示例可从[案例目录](../examples/README.md)运行。对应版本的 Release 发布 ZIP 和 `SHA256SUMS` 后，可运行：

```sh
python -m frameviz download-examples --output ./frameviz-examples
```

命令只请求当前 SDK 版本的 ZIP，核对归档和清单中的 SHA-256，再解压到新目录。私有试用期间可向维护者索取 ZIP。构建验收可用 `--asset-base` 指定提供两个文件的 HTTPS 或本机 HTTP 目录。[运行示例](../examples/DOWNLOAD.md)。

## 可选依赖和公开发行

Python SDK 的最低版本为 3.9。pip 为解释器选取兼容的 NumPy 和 websocket-client。离线安装需准备目标解释器适用的依赖 wheel。

PNG 截图和教程 HTML 导出使用 `capture` extra。可在 wheel 路径后加 `[capture]`，然后运行 `python -m playwright install chromium`。Linux 还需满足 Chromium 的系统依赖。

Mac 预览使用明确的 `0.5.0rc1` 版本。Mac 和 Linux 正式 `0.5.0` 计划在 PyPI 同时发布。独立 App、C++ SDK 和共用示例的下载入口见 [GitHub Releases](https://github.com/qqfly/frameviz/releases)。

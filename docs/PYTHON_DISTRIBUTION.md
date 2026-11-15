# Python 安装与分发

## Apple 芯片 Mac 候选

向维护者获取匹配的候选 wheel 和 SHA-256，在项目环境中安装。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ./frameviz-0.5.0-py3-none-macosx_11_0_arm64.whl
```

随后在 Python 或 IPython 中执行：

```python
import frameviz as fv
viz = fv.open()
viz.add_box()
```

独立脚本可调用 `viz.keep_running()`。App 位于当前 Python 环境，随 wheel 安装和卸载。新开场景会优先复用兼容的已运行 Host。没有 Host 时，SDK 会自动查找随包 App。显式连接地址和路径沿用原有规则。候选 App 使用 Developer ID 签名，Apple 公证等待维护者完成配置。独立 DMG 的签名状态以对应产物记录为准。

## 各平台和产物

| 用法 | 试用安装材料 |
| --- | --- |
| Apple 芯片 Mac Python | 带 App 的平台 wheel |
| Ubuntu 22.04／24.04 原生桌面 | 试用 `.deb` 和配套 SDK wheel。便携图形运行时仍在验收。 |
| 无桌面 Linux | 独立 Host 和配套 SDK wheel，支持认证链接和 SSH 转发。 |
| Windows x64 | 试用 App 和配套 SDK wheel。Python 冷启动使用显式 App 路径。 |
| 独立 Mac App、C++ SDK | 通过对应平台的独立试用包交付。 |

安装标准独立包的命令见[安装说明](INSTALLATION.md)。通过明确路径安装 `py3-none-any` wheel 或源码会获得 SDK，运行时按各平台的独立安装说明提供。协议兼容沿用当前 SDK 的规则。

## 示例

对应版本的 Release 上有 ZIP 和 `SHA256SUMS` 后，可运行：

```sh
python -m frameviz download-examples --output ./frameviz-examples
```

命令只请求当前 SDK 版本的 ZIP，核对归档和清单中的 SHA-256，再解压到新目录。私有试用期间可向维护者索取 ZIP。构建验收可用 `--asset-base` 指定提供两个文件的 HTTPS 或本机 HTTP 目录。[运行示例](../examples/DOWNLOAD.md)。

## 可选依赖和公开发行

Python SDK 的最低版本为 3.9。pip 为解释器选取兼容的 NumPy 和 websocket-client。离线安装需准备目标解释器适用的依赖 wheel。

PNG 截图和教程 HTML 导出使用 `capture` extra。可在 wheel 路径后加 `[capture]`，然后运行 `python -m playwright install chromium`。Linux 还需满足 Chromium 的系统依赖。

计划使用公开命令 `python -m pip install frameviz`。发布前核对 PyPI 项目权限、wheel 平台标签和已验收产物，并配置 [Trusted Publishing](https://docs.pypi.org/publishing/publishing-to-pypi/)。独立 App、C++ SDK 和共用示例继续使用 GitHub Releases。

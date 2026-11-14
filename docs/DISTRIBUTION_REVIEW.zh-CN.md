# FrameViz 0.5 安装与分发评审方案

状态为提案，供 PR #18 独立评审。本文中的正式安装包、下载名称和发布流程是拟实施方案。已验证的试用产物及其边界见下文。评审意见优先给出能复现的问题、建议取舍和验收条件。

## 1. 用户入口

安装一次 FrameViz 运行时。每个 Python 项目各自安装 SDK，编译 C++ 项目时选择与自身工具链匹配的 SDK。示例可按版本另行下载。

| 使用目的 | Windows x64 用户需要的文件 | 首次操作 |
| --- | --- | --- |
| 先看效果 | 安装器和 Windows 快速试用 ZIP | 安装后在 PowerShell 中运行 `./hello_world.exe` 和 `./scene_slider.exe`。无需编译工具。 |
| 写 Python 项目 | 安装器和通用 Python wheel | 创建项目虚拟环境，安装 wheel，再运行 `fv.open()`。 |
| 接入 C++ 项目 | 安装器、MSVC 工具链匹配的 C++ SDK、公共示例 ZIP | 在 x64 Developer PowerShell 通过 CMake 配置，链接 `frameviz::cpp`。 |

Windows 优先验收由 Tauri 生成的按当前用户安装的 NSIS 安装器。安装器需要在默认和自定义目录写入可发现的安装记录，并在系统缺 WebView2 时引导安装。MSI 在有独立验证和使用需求时再列进下载表。[Tauri 安装器与 WebView2 选项](https://v2.tauri.app/distribute/windows-installer/)

当前 Windows C++ 试用已用自定义目录实测自动启动及共享 Host。当前 Python 能复用正在运行的 Host，从已安装 App 冷启动仍需显式路径。后续拟覆盖默认和自定义安装目录，遵循与 C++ 一致的 Windows 安装记录和标准目录查找约定。遇到旧版保留继续搜索兼容候选的能力。调用方显式指定不兼容路径时报告该路径和版本。新增测试使用临时用户目录与端口。发布时才将验证后的 Windows 自动启动体验写进快速开始。

## 2. README 与下载页

- 中英文 README 顶部提供 Releases、平台选择、最短启动流程和案例索引。首次操作直接选 Windows、macOS 或 Linux 路径。Python、C++ 和 Vue 各有入口。
- 安装文档给出 Windows PowerShell、Python 虚拟环境、CMake 配置、自定义位置、卸载和故障排查。放一个 Windows 双客户端步骤，能验证关闭自己的 Viewer 以及最后一个客户端退出后的进程回收。
- 发布说明绑定 Git 提交、运行时版本、SDK、示例与测试记录。私有仓库沿用访问权限，评审者从同一页面取得候选版本。[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)

| 文件 | 计划覆盖 | 说明 |
| --- | --- | --- |
| 原生运行时 | Windows x64 `setup.exe`，Apple Silicon `.dmg`，Ubuntu 22.04／24.04 x86_64 `.deb` | 对每项标明实际测试过的系统、签名或公证状态。 |
| 独立 Host | Linux x86_64 | 为无桌面环境提供可选下载，浏览器显示。 |
| Python SDK | 单个 `frameviz-<version>-py3-none-any.whl` | 同一个文件供各平台下载。第三方库由 pip 根据解释器安装。 |
| C++ SDK | 按 OS、架构、编译工具链 | 包含头文件、库、CMake 元数据和许可。标明 Windows 工具链与可互操作的配置。 |
| 示例源码 | 一份 `FrameViz-<version>-examples.zip` | 跨平台共用，含案例说明、Python/C++ 源码和所需的小型公共测试素材。 |
| 快速试用 | 可选的按平台 ZIP | 各含已验收的 Hello World 和实时滑条二进制，使用同一版本 App。 |
| 校验 | `SHA256SUMS`、构建信息和验收摘要 | 每个文件记录哈希，测试结果指向实际运行的文件。 |

## 3. 示例如何共用

仓库的 [案例清单](../examples/INVENTORY.md) 是源头。共用 ZIP 由明确的源码清单生成，保留目录结构、24 组 Python/C++ 案例及操作说明。需要随 ZIP 提供合成点云等小型素材，梳理 CMake 在源码树外使用已安装 SDK 的路径。解压到一个带空格且没有源码的目录，从 ZIP 内文档运行两个入门案例、点云以及可选的截图／HTML。README 的演示从这些案例中选。

截图与离线 HTML 单列可选依赖。SO-101 的外部模型保持固定来源、按需下载、校验和、本地缓存，并注明首次需要网络。需要工作区的 Vue 和完整应用保留其源码或开发套件入口及启动说明，发布轻量 ZIP 前核对链接和相对路径。[应用示例说明](../examples/apps/README.md)

## 4. pip 入口

### 私有试用

先装配套运行时，在项目虚拟环境从私有 Releases 下载指定 wheel 后安装。下面以 Windows 为例。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .\frameviz-0.5.0-py3-none-any.whl
```

私有仓库用户通过已授权的 GitHub 会话下载文件。虚拟环境里只需要 Python SDK 与 Python 依赖。截图及离线教程通过同版本 wheel 的 `capture` extra 安装 Playwright，然后用 `python -m playwright install chromium` 准备浏览器。[Python 分发说明](PYTHON_DISTRIBUTION.md)

### 公开 PyPI

维护者先确认 `frameviz` 项目的发布权限及命名。在目标版本完成安装验收后，使用锁定到发布 workflow 和受保护环境的 Trusted Publishing，发布经过验收的那个 wheel。用户安装运行时后，在虚拟环境执行 `python -m pip install "frameviz==0.5.0"`。版本说明给出可配套的运行时，轮换版本时复跑握手和最小绘制。[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)

如果以后确认需要仅靠 pip 获得一个可运行的 Host，优先为无桌面 Linux 评估平台相关的独立 Host 交付。届时要单独明确架构、Linux 基线、包体、安装权限、哈希、升级和兼容策略。桌面运行时在本提案中继续由原生安装器分发。[Python wheel 平台标签](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/)

## 5. 实施顺序和验收

1. 补齐 Windows Python 安装位置发现。用已安装 wheel 在默认和带空格的自定义目录冷启动，验证两个客户端共享与退出。更新中英文快速开始和平台说明。
2. 实现共用 examples ZIP。用独立目录复跑 Python/C++ 入门例、依赖小素材的案例以及至少一个输出案例。文档标明可选依赖和下载入口。
3. 在固定候选提交上构建平台产物。继续使用已确定的 PR 自动 Ubuntu 检查及手动候选打包。Windows 最终安装器验证 WebView2、默认与自定义目录、卸载和重复安装；Python、C++ 实跑均需对应最终安装器。Ubuntu 两个目标版本实际安装各自 `.deb` 和配套 wheel，补做真实桌面的交互体验。macOS 用实际 DMG 和配套 wheel 做原生安装及启动。
4. 允许仓库评审者下载受控的私有候选包。对照文档实跑后决定平台支持表、签名策略和公开发布日期。PyPI 权限及公开发布单独确认。

### 当前证据和待核项

- Windows x64 真机试用通过两套已安装 C++ 示例并行运行、A 的 Ctrl+C 及 B 最后退出后 Host 回收。使用现有未签名试用安装器和重建后的案例。正式 Tauri 安装器、Windows Python 自动冷启动和 MSVC SDK 安装验收待做。
- Ubuntu 22.04／24.04 x86_64 各安装实际 Debug `.deb`，各通过六项 C++ 桌面与无桌面检查。配套试用 wheel 在两版 Ubuntu 通过无桌面启动、原生 Viewer 就绪、滑条回调和 Python 正常退出回收。桌面测试用 Xvfb 和真实 WebKitGTK，实体桌面体验与最终发布包待验收。
- macOS 已有 Apple Silicon 试用结果及较早版已安装 App 的启动回归。最终候选 DMG 与配套 SDK 仍须重新核对产物及验收条件。Linux Debug 和旧 Mac 包的结果只对应各自测试件。

### 请评审回答

1. 新 Windows 用户从下载页到打开 Python／C++ Viewer，在哪个步骤可能需要额外操作或会选错文件？
2. 共用示例 ZIP 解压到源码树外后，哪些案例还隐含路径、工具链或网络依赖？
3. Windows Python 自动发现、官方安装器和私有发布候选的验收是否足以区分试用和正式支持？
4. Python 分为运行时安装和 SDK 安装是否满足项目接入？如主张 pip 同时交付 Host，请给出需要覆盖的具体场景和运行时升级方案。

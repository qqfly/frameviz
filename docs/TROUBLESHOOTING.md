# 故障排查

## 找不到运行环境

`pip` 安装的是 SDK。Mac 先安装 `FrameViz.app` 到 `~/Applications` 或 `/Applications`，Ubuntu 桌面用 `sudo apt install ./frameviz_*.deb`，无桌面 Linux 把独立 `frameviz-server` 放到 `~/.local/bin`。随后重新执行 `fv.open()`；标准安装不需要 `FRAMEVIZ_TAURI_APP`。

若曾手动设置 `FRAMEVIZ_HOST_PATH` 或 `FRAMEVIZ_TAURI_APP`，检查它是否仍指向有效的 FrameViz 可执行程序。显式路径优先于自动搜索，错误时会直接报错。SDK 不从任意 PATH 目录猜测同名程序。

## 版本不兼容或认证失败

`major.minor` 相同时允许 patch 不同，例如 0.5.0 与 0.5.2 兼容。0.4 与 0.5 不兼容。错误文字会说明升级 SDK 还是运行环境。不要用启动另一个程序绕过当前版本或认证错误。

凭据由当前用户的运行环境写入发现文件，SDK 自动读取。使用运行环境配套 SDK，并确认连接的是目标实例。不要公开复制 `host.json` 或带 `#token=` 的链接。手动启动的 App 不会被 SDK 退出逻辑关闭；需要退出时用该 App 自身的退出入口。

## 原生窗口打不开，或机器没有桌面

桌面上可显式改用：

```python
viz = fv.open(window_mode=1)
```

这会绕过原生窗口入口，使用运行环境自带的 Viewer。无 `DISPLAY` / `WAYLAND_DISPLAY` 的 Linux 会自动选独立 Host 并打印链接。远程机器需要同时转发 HTTP 和 WebSocket 两个端口，详见[安装说明](INSTALLATION.md#standalone-host-and-browser)。不要把开发服务器的 8080 地址当成所有运行环境的固定地址。

目前没有完成包含 Ubuntu 系统、GPU、驱动组合的 WebKitGTK 故障复现，因此这里不列未经实测的显卡结论。报告窗口问题时，请记录这些条件、对应构建版本，以及同一场景改用浏览器后的结果。

## 程序退出、启动超时或 Viewer 地址缺失

SDK 启动的程序会写私有启动日志，失败信息中给出日志路径。默认在发现文件所在目录，文件名为 `startup-*.log`；日志可能包含临时私有链接，分享前先去掉令牌。保留首次失败日志，检查其中的实际退出原因，不要只保留一次重试成功的结果。

Viewer 地址必须属于当前连接的运行环境。若旧程序没有发布地址，升级配套运行环境；SDK 不会猜测其他 HTTP 服务的地址并把令牌交给它。`window_mode=0` 可用于应用自行管理页面的接入方式。

## Mac 下载后被系统拦截

当前已有私有预览使用临时签名，未完成 Apple 公证。核对来源和校验值后，按 [Mac 说明](MACOS.md) 完成允许打开操作。签名构建脚本存在不代表已经生成公证通过的产物；另一台 Mac 下载后的首次打开须单独验证。

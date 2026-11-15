FrameViz 本地候选包

本包将 App/SDK 安装材料和示例保存到独立目录，不自动安装到系统、修改 shell 配置或覆盖既有安装。

1. 校验并保存到全新版本目录（路径由你选择）：
   bash install.sh --bundle . --prefix "$HOME/FrameViz/candidate-0.5.0"

2. 在自己的新虚拟环境中安装 artifacts/ 内的 Python wheel；C++ 压缩包解压至独立目录，通过 CMAKE_PREFIX_PATH 指定。App 安装包需另外审核后手动打开。尚未完成授权、签名和跨平台验收的候选不能作为正式发行版。

3. 卸载该目录内未改动的受管文件：
   bash uninstall.sh --prefix "$HOME/FrameViz/candidate-0.5.0"
   修改过的文件和你自己新增的文件会保留。

SHA-256 清单只能检测文件变化，不代替可信签名。前端 SDK 和模板位于同版本 devkit。开发依赖仍可能需要联网下载；运行 Viewer 的前端代码已打包，无 CDN 依赖。

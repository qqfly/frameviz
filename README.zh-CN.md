# FrameViz

FrameViz 是 qqfly 维护的独立本地三维可视化项目，采用 MIT 许可证。Python/C++ SDK 向 Rust Host 提交场景，Three.js Viewer 或 Vue 组件负责显示和交互。

当前为未发布的 0.4.0 候选。请从 [英文主文档](README.md) 的源码构建步骤开始，或运行 `tests/acceptance/demo.py` 体验隔离场景。新目录不携带旧 Git 历史或已安装程序，不需要任何组织内部工具。

基础图形、点云、网格、实例、模型、相机、拾取和 Gizmo 都属于验证范围。原生平台签名、跨平台完整安装、远程多用户、Host 重启持久恢复和生产负载能力仍需单独验收。详情见 [验证说明](docs/VALIDATION.md) 与 [安装说明](docs/INSTALLATION.md)。

版权和 MIT 许可声明必须随代码的重要副本保留；第三方许可按其原有要求保留，详见 [NOTICE](NOTICE)。不应将第三方代码署名改成项目维护者姓名。

私有源码仓库：[qqfly/frameviz](https://github.com/qqfly/frameviz)。Apple 芯片 Mac 安装包、Python/C++ 配套 SDK、签名与公证的区别见 [Mac 使用说明](docs/MACOS.md)。当前预览包使用本地签名，尚未 Apple 公证。

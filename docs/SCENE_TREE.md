# FrameViz 阶段 3、4、6 契约

2026-11-11，依据 Qiang 确认的使用方式修订。本文件定义开发和验收的目标行为。0.5.x 的场景树需使用同系列的 Host、Viewer 与 SDK。功能状态以相应提交和实际验证记录为准。

## 3 通用场景树与独立 Camera View

- ID 在 Host 会话内唯一。节点有可选父节点、可重复名称和 JSON 对象标记。默认名称为空字符串、标记为空对象。名称最多 1024 UTF-8 字节，标记序列化后最多 16 KiB。
- 位姿由平移与旋转组成。输入可用 `{"position":[x,y,z],"quaternion":[qx,qy,qz,qw]}` 或七元素 `[x,y,z,qx,qy,qz,qw]`。四元数固定为 xyzw，有限且非零的四元数归一化。局部位姿默认为零平移和单位四元数。查询可附带列主序刚体 4×4 矩阵。输入采用已有字段 `pos`、`quat` 时保持兼容，并禁止同时提交互相冲突的别名。
- 图元尺寸、模型单位换算、每个实例的尺寸与对象几何缩放仍可设置。几何缩放作用在节点坐标系内的几何上，子节点只继承父节点刚体位姿。既有 `scale` 尺寸参数映射到对象几何缩放。新接口用 `geometry_scale` 表达这一含义，位姿数据和几何缩放分字段管理。
- `add_node` 创建空节点，创建场景对象时可给父节点、名字与标记。 `set_parent(handle, parent, local_transform=...)` 的默认行为是保持对象及子树的世界位姿。显式传入 `local_transform` 时采用新父节点下的给定局部位姿。`parent=None` 将对象移到根，采用相同规则。原子验证父节点存在、属于同一场景且不会成环，然后一起提交关系与位姿。
- `set_object_metadata` 只修改指定字段，`list_objects` 返回可重建树的平铺记录。 `get_transform` 默认局部，也可查询世界。拖动事件含已提交的局部和世界位姿。点选事件含对象 ID、祖先链、名称和标记，元数据由 Host 根据当前对象树生成。
- 父节点隐藏时保留子节点的自身开关。删除整个子树并释放挂接的 Gizmo 和失去引用的资源。异步模型先创建刚体节点，资源未就绪也能挂子节点，删除后迟到结果不能复活对象。
- 大点云公开为一个点云 ID。内部块为几何数据，统一移动、显示、删除和拾取。点选可含世界命中位置及当前点云全局索引，索引以现有数据顺序从零开始。新连接无需拥有最初上传点云的 SDK 实例即可操作同一 ID。
- 每个 View 独立拥有 Camera View，包含观看位置、方向和投影设置。独立视图可以观察同一场景。相机或传感器模型仍按普通场景对象管理。新视图、刷新和重连恢复场景树和该 View 的 Camera View。
- 验收覆盖旋转父节点改挂与解除、显式局部位姿、拒绝原子性、几何缩放隔离、真实拖动/点选、跨块索引、异步加载、双视图和 C++ 安装消费。记录一千节点的帧率与更新延迟。

## 4 七种小控件

- Host 拥有场景级定义和值。清空绘图时保留控件，销毁场景时回收控件。控件类型是 number、checkbox、select、text_input、button、text、group。值与范围在 Host 校验。界面按纯文本渲染标签。嵌入 Vue 时面板默认隐藏，仍可查询和修改控件。
- 带范围数值同时显示滑条和精确数字输入。由应用选择 `update_mode="continuous"` 或 `"commit"`。前者可合并未执行的中间拖动值，必须保留每次结束值和离散事件。后者仅在松手或精确输入提交时执行一次。键盘调整也可提交。
- 用户提交更新 Host 和各 View，事件携带场景、视图、控件 ID、值、来源、阶段及 revision。来源为 `user` 或 `program`，阶段为 `input` 或 `commit`。程序写值默认只同步显示，`emit=True` 时触发一次事件。按钮一次点击对应一次离散事件。
- 同一客户端对同一控件重复调用 `on_widget_change(id, handler)` 时替换原有处理逻辑。 `append=True` 显式追加，按注册顺序调用。应用自有控件通过读写和事件接口联动。
- 验收包含两种真实拖动模式、数字输入、重绑定与追加的次数、多视图同步、静默重置、显式事件和 Vue 面板开关。

运行 [滑条和重置示例](../examples/python/03_interaction/use_scene_slider.py)。

```bash
python examples/python/03_interaction/use_scene_slider.py --mode continuous
python examples/python/03_interaction/use_scene_slider.py --mode commit
```

拖动滑条可调整立方体的位置。数字输入框支持直接键入精确值并按 Enter 提交。
程序可用 `get_widget_value(id)` 读取，调用 `set_widget_value(id, value)` 更新所有视图。
要在程序赋值时执行已注册处理逻辑，传入 `emit=True`。

## 6 显示状态查询、截图与教程 HTML 导出

- `get_camera_view()` 返回 `eye`、`target`、`up` 以及 `projection={"type": "perspective", "fov": 30}`。`fov` 是垂直视场角，单位为度。`set_camera_view(camera_view)` 一次应用完整参数。截屏可以直接使用这一结构。
- `get_display_state()` 返回当前 View 和场景的显示记录。对象以父节点在前的顺序返回，带局部和世界位姿。使用 `get_display_state(include_bounds=True)` 请求 Host 可计算的世界轴对齐包围盒，或用 `print(viz.describe_scene())` 查看文字摘要。外部模型或其它缺少 Host 几何的数据会标明包围盒未采集。浏览器操作更新所属 View 的 Camera View，供再次连接和脚本查询。
- 查询提供显示对象及层级、刚体位姿、可见性、颜色、几何属性、元数据和每个 View 的 Camera View。文字摘要包含有数据支撑的世界包围盒，缺失时明确标注。场景同步继续服务新连接、刷新和恢复。
- `viz.screenshot(path=None, *, camera_view=None, width=None, height=None)` 默认使用此 View 的观看参数，支持另给临时 Camera View。返回 PNG 字节，给路径时同时保存。后台渲染器独立于已打开的 Viewer，截图不改变任何窗口尺寸或相机。无窗口时自动准备后台渲染环境，连续请求可复用。后台组件需要额外安装时提供一次性安装流程。
- 截图在此前已接受的场景更新、缓冲和引用资源就绪后输出；失败时报告具体资源或渲染错误。验证普通与临时视角确实产生不同画面，并测试未打开窗口、迟到资源、连续截图、原窗口视角和尺寸。
- `viz.export_html(path, *, animation=None)` 导出自包含页面。独立打开和教程嵌入均可用，浏览器可旋转、缩放。可选动画为上层给定的时间和对象刚体位姿，提供播放、暂停、进度调整；观看相机独立于动画。验证断网、几何与资源完整、真实交互和文本安全转义。
- 应用或 robotics runtime 管理业务状态和项目重建。通用场景文件格式及公开文件保存、加载、导入暂缓。教程 HTML 直接使用显示数据。交互式规划和求解由教程的上层程序提供。

### PNG 截图

先在使用 FrameViz 的 Python 环境安装同版本 SDK 的 `capture` extra 和后台浏览器。
从源码开发时运行以下命令。

```bash
python -m pip install -e 'packages/frameviz-py[capture]'
python -m playwright install chromium
```

```python
import frameviz as fv

viz = fv.open(window_mode=0)
viz.add_box(color="#157db5")
png = viz.screenshot("scene.png", width=720, height=480)
viz.close()
```

也可传入 `camera_view=viz.get_camera_view()` 的同结构数据，改变这一次的拍摄视角。
后台 Chromium 自动启动并在同一个 Python 进程中复用。默认使用同版本本机 Host 提供的 Viewer。

### 离线教程

使用和截图相同的后台组件。仅导出静态场景时调用 `viz.export_html("lesson.html")`。
也可以给对象 ID 指定预先计算好的局部刚体位姿轨迹，时间单位为秒，严格递增。

```python
box = viz.add_box()
viz.export_html("lesson.html", animation={
    box: [
        {"time": 0, "pose": [0, 0, 0, 0, 0, 0, 1]},
        {"time": 2, "pose": [1, 0, 0, 0, 0, 1, 0]},
    ],
})
```

读者双击 `lesson.html` 即可浏览，或由教程页面以 `<iframe src="lesson.html" title="位姿动画"></iframe>` 嵌入。
播放、暂停和进度只作用于预计算轨迹，读者仍可独立旋转和缩放视角。
导出时需要能加载场景引用的模型和图片，成功后页面携带其绘图数据。

### C++ 场景节点

```cpp
frameviz::SceneNodeOptions joint;
joint.pose = frameviz::RigidPose::fromArray({0, 0, 0.1f, 0, 0, 0, 1});
joint.name = "shoulder";
auto parent = viz->addNode(joint);

frameviz::SceneNodeOptions link;
link.parent = parent;
link.pose = frameviz::RigidPose{{0.4f, 0, 0}};
auto box = viz->addBox({0.8f, 0.1f, 0.1f}, {}, {0, 0, 0, 1}, {1, 0, 0}, link);
auto world = viz->getTransform(box, frameviz::TransformSpace::World);
viz->setParent(box, std::nullopt);
```

旧绘图参数仍可直接使用。提供 `SceneNodeOptions::pose` 时，以它为准。
`loadMesh` 的 `scale` 和 `SceneNodeOptions::geometryScale` 都作用于对象自身。
`getTransformMatrix` 返回列主序的刚体矩阵。


### 接入正在运行的应用

```python
import frameviz as fv

viz = fv.connect(view_id="v_1")
hosts = fv.list_hosts()
other = fv.connect(url=hosts[-1]["ws_url"], view_id="v_1")
```

`list_hosts()` 返回当前本地状态目录中能认证的兼容 Host，按启动时间排序。
应用已有多个 View 时指定 View ID。显式提供 URL 时直接选择对应的 Host，
SDK 从本地状态目录取得凭据。


### 在局域网分享只读视图

在需要共享时，用本机实际的局域网地址启动独立 Host。例如：

```sh
frameviz-server --lan-address 192.168.1.20
```

本机 SDK 仍连接环回地址。打开或接入场景后，调用 `viz.get_lan_view_link()`
生成绑定到当前视图和场景的链接。读者可以旋转和缩放自己的视角，程序的场景
更新会同步显示。结束视图或将它切换到其他场景会撤销链接。
只有使用启动参数时才开启局域网监听。链接使用本地网络的 HTTP 与 WebSocket，
适用于可信局域网。场景中使用外部模型时，其资源地址需能由读者访问。

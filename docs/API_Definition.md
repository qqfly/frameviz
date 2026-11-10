# FrameViz API Definition v0.4.0

> 当前兼容约定见 [COMPATIBILITY.md](COMPATIBILITY.md)，包括认证、上传、查询错误、共享内存和生命周期。接口示例需配合实际验收记录使用。

本文档定义 **Client** 与 **Host** 之间通过 **WebSocket** 传输的协议。

## 0. 核心变更 Decision Record
- **v0.3.2 (Minor)**:
  - 新增 **Embedded Viewer Registration** (`register_viewer`, `get_viewer_by_name`, `list_registered_viewers`)。
  - 支持嵌入式 UI 场景，前端 Viewer 可通过名称注册，Python SDK 可按名称获取 Viewer。
- **v0.3.1 (Patch)**:
  - 补全 **Buffer Upload Protocol** (create/upload)。
  - 补全 **Gizmo Commands** (attach/detach)。
  - 修正 **Overlay Lifecycle** (remove_object 支持 view_id)。
  - 规范 **Color/Unit** (JSON float 0..1)。
  - 统一 **Logging Schema**。
- **v0.4.0**: 引入 Scene-View 分离，Primitives，Base64/Binary 混合传输。

---

## 1. 通用协议包络
**保持 v0.2.x 结构不变**。

### 1.1 基础约定 (@MUST)
- **Protocol Version**: `"0.4.0"`
- **Compatibility**: 同一 `major.minor` 内的补丁版本互通；缺失、格式错误或不同主/次版本在执行命令前以 `ERR_PROTOCOL_VERSION` 拒绝，并说明应升级运行环境还是 SDK/Viewer。精确格式及发现文件规则见 [COMPATIBILITY.md](COMPATIBILITY.md)。
- **Coordinate System**: 右手系 Z-up，单位：米。
- **Colors**: 
  - JSON 中的 RGB/RGBA 一律为 **[0.0, 1.0] 浮点数**。
- Buffer 中的 `u8` 类型颜色解析为 **0..255 整数**，由 Host 归一化。
- Buffer 颜色仅支持 `u8`；不支持 `f32` 颜色缓冲。
- 直接传数组的颜色字段（如 `color`、`rgba`）要求浮点 **0..1**，超出范围会返回 `ERR_INVALID_ARGS`。
  - Alpha 通道默认 1.0。
- **Handles**: `string` 类型，由 Host 分配（建议自增 ID 的字符串形式 `"1", "101"`）。**Session 级全局唯一**（@MUST），Client 应将其视为不透明标识符。
- **WebSocket Port**: 默认端口 `9527`，绑定 `127.0.0.1`。
- **Multi-Client**: Host **支持**多个 Client 同时连接。所有 Client 共享同一 Session 的 Scene/View/Object 状态。事件（如 `picked`、`transformed`）广播给**所有已连接的 Client**。
- **Multi-View**: 多个 View 可绑定同一 Scene。View 级操作（相机、Gizmo、Overlay、Picking）互相独立。

### 1.2 Protocol Envelope
**Command (Client -> Host)**
```json
{
  "protocol_version": "0.4.0",
  "type": "cmd",
  "id": "c_1",
  "name": "command_name",
  "args": {}
}
```

**Response (Host -> Client)**
```json
{
  "protocol_version": "0.4.0",
  "type": "resp",
  "id": "c_1",
  "ok": true,
  "result": {}, // ok=true 时必填 (可为空对象)
  "error": null // ok=true 时必须为 null
}
```

**Error Response (ok=false)**
```json
{
  "protocol_version": "0.4.0",
  "type": "resp",
  "id": "c_1",
  "ok": false,
  "result": null,
  "error": {
    "code": "ERR_BUFFER_SIZE_MISMATCH",
    "message": "Expected 1024 bytes, got 512"
  }
}
```

**Standard Error Codes**:
- `ERR_INVALID_ARGS`: 参数格式或类型错误
- `ERR_NOT_FOUND`: 指定的 handle/scene_id/view_id/buffer_id 不存在
- `ERR_INVALID_SCOPE`: scene_id 与 view_id 约束冲突
- `ERR_BUFFER_SIZE_MISMATCH`: Buffer 数据大小不匹配
- `ERR_BUFFER_RANGE`: Buffer offset/chunk 越界
- `ERR_BUFFER_UPLOAD_TIMEOUT`: Binary Frame 超时未收到

**Event (Host -> Client)**
```json
{
  "protocol_version": "0.4.0",
  "type": "event",
  "name": "event_name",
  "data": {}
}
```

---

## 2. 核心数据结构

### 2.1 Pose
```json
{ "pos": [x, y, z], "quat": [qx, qy, qz, qw] }
```

### 2.2 BufferRef (Data Transport)
用于引用已上传的二进制数据。

*   **byte_order**: Little-Endian
*   **layout**: C-Contiguous (Row-major)

```json
{
  "buffer_id": "string",
  "dtype": "f32 | u32 | u16 | u8",
  "shape": [N, M]
}
```

---

## 3. 指令列表 (Commands)

### 3.0 数据缓冲管理 (Buffer Management) @NEW

协议设计上采用“JSON Command + Binary Frame”的混合模式。

#### 3.0.1 `create_buffer`
在 Host 申请一块内存区域。
- args:
```json
{ 
  "size_bytes": 1024,
  "dtype": "f32",        // 用于校验
  "shape": [100, 3]      // Optional: 用于校验，若提供则必须 size_bytes == prod(shape)*sizeof(dtype) (@MUST)
}
```
- result: `{ "buffer_id": "b_100" }`

#### 3.0.2 `upload_buffer_chunk`
上传数据片段。
- **约束 (@MUST)**: 
  - **串行性（每连接）**: 同一 WebSocket 连接内，Host 在收到该命令后，必须等待一条 Binary Frame（或使用 `data_base64`），并处理完成后才返回 resp。在 resp 返回前，该连接上的 Client **不得**发送下一条 `upload_buffer_chunk`（不同连接互不影响）。
  - **二选一**: 必须且只能提供 Binary Frame（紧随 JSON 发送）或 `data_base64` 字段之一。
  - **校验**: 
    1. 实际接收到的 payload 大小等于 `chunk_bytes`，否则 `ERR_BUFFER_SIZE_MISMATCH`。
    2. `offset_bytes + chunk_bytes <= size_bytes`，否则 `ERR_BUFFER_RANGE`。
  - **超时**: 若使用 Binary Frame 但 2000ms 内未收到，返回 `ERR_BUFFER_UPLOAD_TIMEOUT`。

- args:
```json
{
  "buffer_id": "b_100",
  "offset_bytes": 0,
  "chunk_bytes": 1024,
  "data_base64": "..." // Optional: 仅当无法发送 Binary Frame 时的兜底方案
}
```
- result: `{}`

#### 3.0.3 `free_buffer`
释放 Buffer 占用的内存。
- **Buffer Lifecycle (@MUST)**: 
  - Host 在执行 `add_points`/`add_lines`/`add_mesh` 时，会**复制** BufferRef 引用的数据到 GPU 内存。
  - 因此 Client 可以在 `add_*` 返回后**立即**调用 `free_buffer` 释放 Host 侧的 Buffer。
  - 若 Client 未显式调用 `free_buffer`，Host 应在 Session 结束时自动释放所有 Buffer。
- args: `{ "buffer_id": "b_100" }`
- result: `{}`

---

### 3.1 场景与视图管理 (Scene & View)

#### 3.1.1 `create_scene`
- args: 
```json
{ 
  "scene_id": "string" // Optional: 缺省则生成 UUID。
}
```
- **Behavior**: 操作是幂等的 (Idempotent)。若 `scene_id` 已存在，返回 `ok=true`，不影响已有内容。
- result: `{ "scene_id": "string" }`

#### 3.1.2 `create_view`
- args:
```json
{
  "title": "string", // Optional
  "width": 800, // Optional (Default: 800)
  "height": 600, // Optional (Default: 600)
  "scene_id": "string", // Optional: 缺省则绑定/创建默认 Scene
  "mount": { "kind": "dom", "element_id": "string" }, // Optional
  "window_decorations": true // Optional (Default: true): false = 无边框窗口 (frameless)
}
```
- result: `{ "view_id": "v_1", "scene_id": "s_1" }`
- **Note**: `window_decorations` 控制是否显示窗口标题栏和边框。设置为 `false` 可创建沉浸式无边框窗口。若平台不支持设置失败，将回退到默认值（有装饰）并输出警告。

#### 3.1.3 `clear_scene`
清空场景内所有对象，但保留场景本身。若提供 `view_id`，同时清空该 View 的 2D overlay。
- args: `{ "scene_id": "string", "view_id": "string" }` // view_id Optional
- result: `{}`

#### 3.1.4 `destroy_scene` @NEW
销毁场景及其所有对象。绑定该场景的 View 将解绑（变为无场景状态）。
- args: `{ "scene_id": "string" }`
- result: `{}`

#### 3.1.5 `destroy_view` @NEW
关闭并销毁视图。
- args: `{ "view_id": "string" }`
- result: `{}`

#### 3.1.6 `list_scenes` @NEW
列出当前所有场景。
- args: `{}`
- result: 
```json
{
  "scenes": [
    { "scene_id": "s_1", "object_count": 42 }
  ]
}
```

#### 3.1.7 `list_views` @NEW
列出当前所有视图。
- args: `{}`
- result:
```json
{
  "views": [
    { "view_id": "v_1", "scene_id": "s_1", "title": "Main View", "width": 800, "height": 600 }
  ]
}
```

#### 3.1.8 `get_view_config` @NEW
获取视图配置（与 `set_view_config` 相同结构）。
- args:
```json
{ "view_id": "string" }
```
- result:
```json
{
  "show_grid": false,
  "show_ground": false,
  "show_axes": true,
  "grid_color": [0.27, 0.27, 0.27],
  "grid_sub_color": [0.2, 0.2, 0.2],
  "axes_length": 0.2,
  "axes_radius": 0.002,
  "background": [1.0, 1.0, 1.0]
}
```
说明：
- `show_ground` 为 `show_grid` 的别名（目前仅渲染网格，无独立地面平面）。

---

### 3.2 图元与几何 (Primitives & Geometry)

#### 3.2.1 `add_primitive`
- args:
```json
{
  "scene_id": "string",
  "type": "box | sphere | cylinder | cone | plane | arrow | axes | text_3d",
  "pose": { "pos": [0,0,0], "quat": [0,0,0,1] },
  "color": [r, g, b],    // Optional: 全局颜色 (0..1)，部分图元可在 params 中覆盖
  "params": {
    // box: { size:[x,y,z] }
    // sphere: { radius }
    // cylinder/cone: { radius, height }
    // arrow: { start:[x,y,z], end:[x,y,z], length, radius }
    //        - start/end: 可选，若提供则自动计算 pose 和 length
    //        - length/radius: 当无 start/end 时必填，箭头沿 pose 的 +Z 方向
    // axes: { length, radius }
    // plane: { width, height }
    // text_3d: { text: "...", height: 1.0 } // 统一参数名为 height
  }
}
```
- result: `{ "handle": "h_101", "object_type": "primitive" }`

#### 3.2.2 `add_points`
- args:
```json
{
  "scene_id": "string",
  "positions": { "buffer_id": "b_1", "dtype": "f32", "shape": [N, 3] }, // BufferRef
  "colors": { "buffer_id": "b_2", "dtype": "u8", "shape": [N, 3] },    // Optional, per-point, 0..255
  "color": [r, g, b, a],                                               // Optional, uniform color (0..1)
  "size": 3.0 // 点大小（像素）
}
```
- result: `{ "handle": "h_102", "object_type": "points" }`
 - **Notes**:
   - `colors` 和 `color` 互斥（`colors` 优先）。

#### 3.2.3 `add_lines`
- args:
```json
{
  "scene_id": "string",
  "positions": { "buffer_id": "b_3", "dtype": "f32", "shape": [N, 3] },
  "indices": { "buffer_id": "b_4", "dtype": "u32", "shape": [M, 2] },   // Optional
  "width": 1.0, // 线宽（像素）
  "color": [1.0, 1.0, 1.0] // Global color (0..1)
}
```
- **Behavior**: 当 `indices` 省略时，`positions` 视为按顺序连接的折线段（0-1-2-...）。
- result: `{ "handle": "h_103", "object_type": "lines" }`

#### 3.2.4 `add_mesh`
- args:
```json
{
  "scene_id": "string",
  "vertices": { "buffer_id": "...", "dtype": "f32", "shape": [V, 3] }, // @MUST: BufferRef
  "faces_format": "tri | poly", // Optional, Default: "tri"
  "faces": { "buffer_id": "...", "dtype": "u32", "shape": [F, 3] },    // faces_format="tri": 三角形索引 (0-based)
  "faces": {                                                      // faces_format="poly": 通用多边形
    "counts": { "buffer_id": "...", "dtype": "u32", "shape": [F] },   // 每个面的顶点数
    "indices": { "buffer_id": "...", "dtype": "u32", "shape": [K] }   // 按面顺序拼接的顶点索引
  },
  "normals": { ... }, // Optional: f32 [V, 3]
  "colors": { ... },  // Optional: u8 [V, 3] (0..255) 或 u8 [F, 3]
  "color": [1.0, 1.0, 1.0], // Optional: 统一颜色（RGB 或 RGBA，0..1）
  "alpha": 0.5,       // Optional: 全局透明度 (0.0=完全透明, 1.0=完全不透明, 默认=1.0)
  "wireframe": false, // Optional: 是否显示边线 (默认=false)
  "smooth_shading": true // Optional: 是否平滑着色 (默认=true；设为 false 可启用 flat shading)
}
```
- result: `{ "handle": "h_104", "object_type": "mesh" }`

补充说明：
- `colors` 若为 `[V,3]` 则为每顶点颜色；若为 `[F,3]` 则为每面颜色。
- `faces_format="poly"` 时，`F` 为 `counts` 的长度（多边形面数）。
- `color` 用于统一颜色（RGB/RGBA）。未显式传 `alpha` 时可使用 `color[3]` 作为透明度；`alpha` 参数优先。
- `alpha` 设置材质整体透明度，与 `colors` 中的RGB值组合为RGBA。
- `wireframe=false` 时不显示边线（仅显示面片颜色），`wireframe=true` 时显示黑色半透明边线以增强网格可见性。
- `smooth_shading=true` 时使用平滑着色（默认，更有“质感”）；`smooth_shading=false` 时使用平面着色（有明显面片感）。

**⚠️ Breaking Change (v0.3.2):**
- `wireframe` 默认值从 `true` 改为 `false`。现有代码如需边线，需显式设置 `wireframe=true`。
- 原因：默认显示边线会增加内存占用（创建 WireframeGeometry 几何副本），影响性能。

**性能提示：**
- `wireframe=true` 会创建额外的几何体（WireframeGeometry），使网格内存占用翻倍。
- 对于大型网格或大量网格，建议避免使用 `wireframe=true`。
- 如需调试网格结构，建议仅在开发阶段使用 `wireframe=true`。
- 平滑着色会进行顶点法线处理并在着色器中插值；对复杂网格（例如 >50 万三角形）可能影响实时渲染帧率。
- 若追求最高帧率且不需要平滑效果，可设置 `smooth_shading=false`。

#### 3.2.5 `add_instances` @NEW
用于 Octomap/占据栅格等大批量实例化渲染。
- args:
```json
{
  "scene_id": "string",
  "type": "box | sphere | axes",
  "positions": { "buffer_id": "b_pos", "dtype": "f32", "shape": [N, 3] },
  "quats": { "buffer_id": "b_quat", "dtype": "f32", "shape": [N, 4] },   // Optional
  "scales": { "buffer_id": "b_scale", "dtype": "f32", "shape": [N, 3] }, // Optional
  "colors": { "buffer_id": "b_col", "dtype": "u8", "shape": [N, 3] },    // Optional
  "color": [1, 1, 1], // Optional: 全局颜色 (RGB)
  "alpha": 0.5,       // Optional: 全局透明度
  "params": { /* primitive 参数，如 box.size / sphere.radius / axes.length */ }
}
```
- result: `{ "handle": "h_105", "object_type": "instances" }`

#### 3.2.6 `add_text_2d` (Overlay)
- args:
```json
{
  "view_id": "string", // Bound to View
  "text": "Status: OK",
  "x": 10, "y": 10, // 像素坐标，原点为视图左上 (x->右, y->下)
  "font_size": 14,
  "color": [1, 1, 1]
}
```
- result: `{ "handle": "h_106", "object_type": "text2d" }`

#### 3.2.7 `update_text_2d` (Overlay Update) @NEW
轻量化更新 Overlay 状态。
- args:
```json
{
  "view_id": "string",
  "handle": "h_106",
  "text": "Status: Loading...", // Optional
  "color": [1, 0, 0]           // Optional
}
```
- result: `{}`

#### 3.2.8 `remove_object`
支持移除 Scene Object 或 View Overlay。
- args:
```json
{
  "handle": "string",
  "scene_id": "string", // 二选一必填: 移除 Scene 对象
  "view_id": "string"   // 二选一必填: 移除 Overlay
}
```
- **Constraint**: `xor(scene_id, view_id) == true`，否则 `ERR_INVALID_SCOPE`。
- result: `{}`

#### 3.2.9 `remove_objects` @NEW
批量移除 Scene 对象。
- args:
```json
{
  "scene_id": "string", // Optional: 若指定则仅移除该 scene 内对象
  "handles": ["h_1", "h_2", "h_3"]
}
```
- result: `{}`

---

### 3.3 变换与显示

#### 3.3.1 `set_transform` / `set_object_transforms`
- args: 
```json
{
  "handle": "string",
  "pose": { "pos": [0,0,0], "quat": [0,0,0,1] }
}
```
或批量形式：
```json
{
  "items": [
    { "handle": "h_1", "pose": { ... } },
    { "handle": "h_2", "pose": { ... } }
  ]
}
```
- **Note**: Handle 为 Session 级全局唯一，无需指定 scene_id。

#### 3.3.2 `set_color`
- args: 
```json
{ 
  "handle": "string", 
  "rgba": [r, g, b, a],
  "target": "scene",  // Optional: "scene" (3D Object, default) | "overlay"
  "view_id": "string" // Optional when target="overlay"; omit to resolve by global handle
}
```
- **Note**: Handle 全局唯一。对 3D 对象无需 view_id；对 Overlay 可省略 view_id。

#### 3.3.3 `get_color`
- args:
```json
{ 
  "handle": "string"
}
```
- result (统一颜色):
```json
{ "rgba": [r, g, b, a] }
```
- result (顶点/每面颜色):
```json
{ "has_vertex_colors": true }
```
- **Note**: 顶点/每面颜色场景下，不返回统一颜色。

#### 3.3.4 `get_alpha`
- args:
```json
{
  "handle": "string"
}
```
- result:
```json
{ "alpha": 0.5 }
```

#### 3.3.5 `set_visible`
- args: 
```json
{
  "handle": "string",
  "visible": true,
  "target": "scene",  // Optional: "scene" (default) | "overlay"
  "view_id": "string" // Optional when target="overlay"; omit to resolve by global handle
}
```
- **Note**: Handle 全局唯一。对 3D 对象无需 view_id；对 Overlay 可省略 view_id。

#### 3.3.6 `clone_object` @NEW
克隆对象，返回新 handle。
- args:
```json
{
  "handle": "string"
}
```
- result:
```json
{ "handle": "h_201" }
```

#### 3.3.7 `is_object_alive` @NEW
判断 handle 是否仍存在（Scene 或 Overlay）。
- args:
```json
{ "handle": "string" }
```
- result:
```json
{ "alive": true }
```

---

### 3.4 相机控制

#### 3.4.1 `set_camera_pose`
- args: 
```json
{ 
  "view_id": "...", 
  "eye": [x,y,z], 
  "target": [tx,ty,tz], 
  "up": [0,0,1]
}
```

#### 3.4.2 `get_camera_pose` @NEW
获取当前相机姿态（由 Viewer 返回）。
- args:
```json
{ "view_id": "..." }
```
- result: 通过 `camera_pose_response` 事件返回:
```json
{ "view_id": "...", "eye": [x,y,z], "target": [tx,ty,tz], "up": [0,0,1] }
```
> **Note**: 若 Viewer 未就绪或未连接，SDK 可能返回默认/空值（默认 eye=[5,5,5], target=[0,0,0], up=[0,0,1]）。需要稳定结果时建议先等待 Viewer ready。
> SDK 建议流程：等待 `viewer_ready`（如 `waitForViewer()` / `wait_for_viewer()`）后再查询。

#### 3.4.3 `reset_camera`
- args: 
```json
{ 
  "view_id": "...", 
  "mode": "fit_scene",  // @MUST: Enum: "fit_scene" | "fit_object"
  "fit_handle": "h_1"  // Required when mode="fit_object"
}
```

#### 3.4.4 `set_camera_controls`
配置相机交互行为。
- args:
```json
{
  "view_id": "string",
  "zoom_to_cursor": false,      // Optional (Default: false): 缩放时以光标指向点为中心
  "orbit_enabled": true,        // Optional (Default: true): 启用轨道旋转
  "pan_enabled": true,          // Optional (Default: true): 启用平移
  "zoom_enabled": true,         // Optional (Default: true): 启用缩放
  "rotate_sensitivity": 0.5,    // Optional (Default: 0.5): 旋转灵敏度
  "pan_sensitivity": 1.0,       // Optional (Default: 1.0): 平移灵敏度
  "zoom_sensitivity": 1.0,      // Optional (Default: 1.0): 缩放灵敏度
  "damping": false,             // Optional (Default: false): 相机阻尼（惯性）
  "mouse_preset": "cad",        // Optional: "cad" | "trackpad"（默认: Windows/Linux=cad, macOS=trackpad）
  "mouse_buttons": {            // Optional: 自定义鼠标映射
    "left": "rotate",           // "rotate" | "pan" | "zoom" | "none"
    "middle": "pan",
    "right": "none"
  },
  "fov": 30                     // Optional (Default: 30): 视场角（度）
}
```
- result: `{}`

#### 3.4.5 `get_camera_controls`
获取当前相机控制配置（含默认值）。
- args:
```json
{ "view_id": "string" }
```
- result:
```json
{
  "rotate_sensitivity": 0.5,
  "pan_sensitivity": 1.0,
  "zoom_sensitivity": 1.0,
  "zoom_to_cursor": false,
  "orbit_enabled": true,
  "pan_enabled": true,
  "zoom_enabled": true,
  "damping": false,
  "mouse_preset": "cad",
  "mouse_buttons": { "left": "rotate", "middle": "pan", "right": "none" },
  "fov": 30
}
```

#### 3.4.6 `set_view`
快速切换到预设视角。
- args:
```json
{
  "view_id": "string",
  "view": "home",     // @MUST: Enum: "home" | "front" | "left" | "top" | "back" | "right" | "bottom"
  "fit_all": true     // Optional (Default: true): 是否自动调整距离以显示所有对象
}
```
- result: `{}`
- 预设视角说明:
  - `home`: 等轴测视角 (从 +X+Y+Z 方向观察原点)
  - `front`: 正视图 (从 +X 方向观察)
  - `left`: 左视图 (从 +Y 方向观察)
  - `top`: 顶视图 (从 +Z 方向观察)
  - `back`: 后视图 (从 -X 方向观察)
  - `right`: 右视图 (从 -Y 方向观察)
  - `bottom`: 底视图 (从 -Z 方向观察)

#### 3.4.7 `set_render_mode`
设置渲染显示模式。
- args:
```json
{
  "view_id": "string",
  "mode": "solid"    // @MUST: Enum: "solid" | "wireframe" | "points"
}
```
- result: `{}`
- 渲染模式说明:
  - `solid`: 实体填充 (默认)
  - `wireframe`: 线框显示
  - `points`: 顶点点云显示

#### 3.4.8 `set_view_config` @NEW
配置视图环境（网格/坐标轴/背景色）。
- args:
```json
{
  "view_id": "string",
  "config": {
    "show_grid": false,
    "show_ground": false,
    "show_axes": true,
    "grid_color": [0.27, 0.27, 0.27],
    "grid_sub_color": [0.2, 0.2, 0.2],
    "axes_length": 0.2,
    "axes_radius": 0.002,
    "background": [0.1, 0.1, 0.2]
  }
}
```
- result: `{}`

---

### 3.5 日志体系 (Logging)

#### 3.5.1 `set_log_config`
- args:
```json
{
  "min_level": "info",
  "sinks": [
    { "type": "console", "enabled": true },
    { "type": "file", "enabled": true, "path": "app.log" },
    { "type": "event", "enabled": true } 
  ]
}
```

#### 3.5.2 `read_logs`
- args: `{ "after_seq": 100, "limit": 50 }`
- result: 
```json
{
  "next_after_seq": 150,
  "entries": [
    // Standard LogEntry (@MUST)
    // ts_ms: unix timestamp in milliseconds (int)
    { "seq": 101, "ts_ms": 1700000000000, "level": "info", "logger": "core", "msg": "Ready", "fields": {} }
  ]
}
```

---

### 3.6 交互工具 (Gizmo) @NEW

使用 Combined Gizmo（同时显示平移与旋转控件），通过 6-bit **mask** 控制各自由度的启用/禁用。

Mask 位定义:
| Bit | 值   | 含义        |
| --- | ---- | ----------- |
| 0   | 0x01 | Tx (平移 X) |
| 1   | 0x02 | Ty (平移 Y) |
| 2   | 0x04 | Tz (平移 Z) |
| 3   | 0x08 | Rx (旋转 X) |
| 4   | 0x10 | Ry (旋转 Y) |
| 5   | 0x20 | Rz (旋转 Z) |

常用组合: `0x3F` = 全部 6 DOF, `0x07` = 仅平移, `0x38` = 仅旋转。

#### 3.6.1 `attach_gizmo`
- args:
```json
{
  "view_id": "string",
  "handle": "string",
  "mask": 63,                  // Optional (Default: 0x3F = 全部 6 DOF)
  "size": 1.0,                // Optional (Default: 1.0)
  "scale_mode": "world"       // Optional (Default: "world"): "screen" | "world"
}
```
- **Behavior**: Gizmo 仅在指定 View 显示和交互。多个 View 共享同一 Scene 时，其他 View 不显示该 Gizmo。
- result: `{}`

#### 3.6.2 `set_gizmo_mode`
动态调整已挂载 Gizmo 的参数（mask / size / scale_mode）。
- args:
```json
{
  "view_id": "string",
  "mask": 7,                   // Optional: 新的 DOF 掩码
  "size": 1.5,                // Optional: 新的 Gizmo 尺寸
  "scale_mode": "screen"      // Optional: 新的缩放模式
}
```
- result: `{}`

#### 3.6.3 `detach_gizmo`
- args: `{ "view_id": "string" }`
- result: `{}`

---

### 3.7 拾取配置 (Picking) @NEW

#### 3.7.1 `set_pick_config`
配置拾取（Picking）行为。
- args:
```json
{
  "view_id": "string",
  "enabled": false,           // Optional (Default: false): 是否启用拾取
  "mode": "object",           // Optional (Default: "object"): "object" (高亮物体) | "point" (显示坐标轴)
  "button": 2,                // Optional (Default: 2): 0=左键, 1=中键, 2=右键
  "ctrl_modifier": false,     // Optional (Default: false): 是否需要 Ctrl 键
  "highlight_color": [1,1,0], // Optional: 高亮颜色 (object 模式)
  "marker_size": 0.1,         // Optional: 坐标轴大小 (point 模式)
  "point_threshold": 0.01,    // Optional (Default: 0.01): 点云拾取距离阈值 (世界单位)
  "line_threshold": 0.01      // Optional (Default: 0.01): 线条拾取距离阈值 (世界单位)
}
```
- **Note**: 默认使用右键拾取以避免与左键视角拖动冲突。拾取功能默认关闭。
- result: `{}`

#### 3.7.2 `get_pick_config`
获取当前拾取配置。
- args: `{ "view_id": "string" }`
- result: 通过 `pick_config_response` 事件返回配置
> **Note**: 若 Viewer 未就绪或未连接，SDK 可能返回默认/空值。需要稳定结果时建议先等待 Viewer ready。
> SDK 建议流程：等待 `viewer_ready`（如 `waitForViewer()` / `wait_for_viewer()`）后再查询。

#### 3.7.3 `get_picked_info`
获取最后一次拾取的信息。
- args: `{ "view_id": "string" }`
- result: 通过 `pick_info_response` 事件返回:
```json
{
  "handle": "string",         // 物体句柄 (或 null)
  "point_world": [x, y, z],   // 点击位置 (或 null)
  "normal_world": [nx, ny, nz], // 法向量 (或 null)
  "point_index": 123          // 点云点索引 (或 null)
}
```
> **Note**: 若 Viewer 未就绪或未连接，SDK 可能返回默认/空值。需要稳定结果时建议先等待 Viewer ready。
> SDK 建议流程：等待 `viewer_ready`（如 `waitForViewer()` / `wait_for_viewer()`）后再查询。

---

### 3.8 嵌入式视图注册 (Embedded Viewer Registration) @NEW

用于支持嵌入式 UI 场景，允许前端 Viewer 组件向 Host 注册，并让 Python SDK 通过名称获取已注册的 Viewer。

#### 3.8.1 `register_viewer`
前端 Viewer 组件向 Host 注册自己。
- args:
```json
{
  "viewer_name": "main_viewer",  // @MUST: 唯一名称标识符
  "scene_id": "string"           // Optional: 绑定的场景 ID，缺省则创建新场景
}
```
- **Behavior**:
  - 若 `viewer_name` 已存在，返回 `ERR_INVALID_ARGS`（名称冲突）。
  - 若 `scene_id` 不存在，自动创建该场景。
- result:
```json
{
  "viewer_name": "main_viewer",
  "view_id": "v_1",
  "scene_id": "s_1"
}
```

#### 3.8.2 `get_viewer_by_name`
通过名称获取已注册的 Viewer 信息。
- args:
```json
{
  "viewer_name": "main_viewer"
}
```
- result (若存在):
```json
{
  "found": true,
  "viewer_name": "main_viewer",
  "view_id": "v_1",
  "scene_id": "s_1"
}
```
- result (若不存在):
```json
{
  "found": false
}
```

#### 3.8.3 `list_registered_viewers`
列出所有已注册的 Viewer。
- args: `{}`
- result:
```json
{
  "viewers": [
    {
      "viewer_name": "main_viewer",
      "view_id": "v_1",
      "scene_id": "s_1"
    }
  ]
}
```

---

## 4. 事件列表 (Events)

### 4.1 `picked`
- data:
```json
{
  "view_id": "string",
  "handle": "string",         // 物体句柄 (或 null)
  "point_world": [x, y, z],   // 点击位置 (或 null)
  "normal_world": [nx, ny, nz], // 法向量 (或 null)
  "point_index": 123,         // 点云点索引 (或 null)
  "modifiers": {              // 键盘修饰键状态
    "ctrl": false,
    "shift": false,
    "alt": false
  }
}
```

### 4.2 `transformed`
- data: `{ "view_id": "...", "handle": "...", "pose": ... }`

### 4.3 `log`
- data: 
```json
// LogEntry 结构 (@MUST match read_logs)
{ 
  "seq": 101, 
  "ts_ms": 1700000000000, 
  "level": "info", 
  "logger": "core", 
  "msg": "...", 
  "fields": {} 
}
```

### 4.4 `camera_pose_response` @NEW
- data:
```json
{ "view_id": "...", "eye": [x,y,z], "target": [tx,ty,tz], "up": [0,0,1] }
```

---

## Appendix: Extensions
- `import_mesh` (Extension)

## Browser page presentation

`fv.open(..., reuse_browser=True)` reuses the browser page opened by this SDK process for the same authenticated runtime. Every call still creates its own scene/view unless `share_scene` was supplied; presentation does not delete old views, change their IDs or transfer Viz ownership. `reuse_browser=False` explicitly opens a separate page. Closing an old Viz must not clear the newly presented scene.

The SDK labels its managed page with an opaque `browser_session` URL parameter. The standalone Viewer forwards this optional label in its WebSocket hello; native windows and embedded Vue viewers do not advertise it. Labels are 1–128 ASCII letters, digits, underscores or hyphens, and confer no authentication rights. Tokens remain in the link fragment/auth message.

Authenticated protocol command `present_view` accepts `{ "browser_session": "...", "view_id": "..." }`. The Host validates the label and destination before changing anything, selects only authenticated Viewer connections with that label, rebinds their view/scene, advances the revision and sends the existing `init` + complete scene snapshot/binary restoration. It returns `{ "viewer_count": N }`. `N=0` has no side effects and tells the SDK to open a replacement page. Viewer-role callers cannot use this command to change scene scope. Python and C++ expose the same command; rendering uses the existing init/snapshot path.

The cache is confined to this SDK process and keyed by canonical runtime endpoint plus an authentication-token hash. It retains page labels, not scene state or Viz ownership. An old runtime that explicitly reports an unknown command may fall back to opening a page; authentication, version and other errors are not treated as permission to open another runtime or silently change scope.

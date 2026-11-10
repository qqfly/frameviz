#!/usr/bin/env python3
"""
FrameViz 交互模式示例 - Gizmo 控制器

演示如何使用 TransformControls (Gizmo) 让用户直接拖拽 3D 物体。

交互方式:
    - 点击物体: 自动附加 Gizmo (默认显示平移+旋转)
    - 点击空白: 取消 Gizmo
    - 按 T 键: 仅显示平移
    - 按 R 键: 仅显示旋转
    - 按 A 键: 显示全部 (组合模式)
    - 按 M 键: 切换缩放模式 (Screen/World)
    - 按 X/Y/Z 键: 切换对应轴的遮罩 (精细控制)

使用方法:
    1. 安装 FrameViz 运行环境和配套 Python SDK（见 docs/INSTALLATION.md）。
    2. fv.open() 自动启动；需要浏览器时使用 window_mode=1。
    3. 运行此脚本: python examples/python/03_interaction/use_gizmo_demo.py
"""

import frameviz as fv


def main():
    print("[Gizmo Demo] 连接到 FrameViz...")
    # 使用默认 window_mode=2 (Tauri 优先，浏览器兜底)
    viz = fv.open(title="Gizmo 交互演示")
    print(f"[Gizmo Demo] 已连接: view_id={viz.view_id}, scene_id={viz.scene_id}")

    print("\n[场景] 创建交互场景...")

    # 清空场景
    viz.clear()

    # 添加坐标轴
    viz.add_axes(length=1.0)

    # 添加地面
    viz.add_plane(width=6, height=6, pos=[0, 0, 0], color=[0.3, 0.3, 0.3, 0.5])

    # 添加可交互的物体，保存 handle -> name 映射
    object_names = {}

    red_box = viz.add_box(size=[0.8, 0.8, 0.8],
                          pos=[-2, 0, 0.4],
                          color=[0.9, 0.2, 0.2])
    object_names[red_box] = '红色立方体'
    print(f"  + 红色立方体: {red_box}")

    green_sphere = viz.add_sphere(radius=0.5,
                                  pos=[0, 0, 0.5],
                                  color=[0.2, 0.9, 0.2])
    object_names[green_sphere] = '绿色球体'
    print(f"  + 绿色球体: {green_sphere}")

    blue_cylinder = viz.add_cylinder(radius=0.3,
                                     height=1.0,
                                     pos=[2, 0, 0.5],
                                     color=[0.2, 0.2, 0.9])
    object_names[blue_cylinder] = '蓝色圆柱'
    print(f"  + 蓝色圆柱: {blue_cylinder}")

    # 启用 pick 功能 (使用右键点击)
    viz.set_pick_config(enabled=True, mode='object', button=2)

    print("\n[交互说明] (在窗口中操作)")
    print("  鼠标右键点击物体 → 附加 Gizmo")
    print("  鼠标右键点击空白 → 取消 Gizmo")
    print("  按 T 键 → 仅平移    按 R 键 → 仅旋转    按 A 键 → 全部 (组合)")
    print("  按 M 键 → 切换 缩放模式 (Screen/World)")
    print("  按 X/Y/Z 键 → 切换 对应轴遮罩")
    print("\n[状态] 等待用户交互...")
    print("       (按 Ctrl+C 退出)\n")

    # 当前 mask 状态
    current_mask = 0x3F  # Default: all DOFs enabled
    current_scale_mode = "world"

    # 当前选中的物体
    current_handle = None

    # 事件处理: 点击物体或空白
    def on_picked(event):
        nonlocal current_handle
        handle = event.get('handle')
        hit_type = event.get('hit_type')

        if hit_type == 'none':
            # 点击空白处
            if current_handle:
                viz.detach_gizmo()
                print(f"  [取消] Gizmo 已分离")
                current_handle = None
        elif handle and handle in object_names:
            # 点击物体
            current_handle = handle
            name = object_names[handle]
            viz.attach_gizmo(handle, mask=current_mask, size=0.6,
                             scale_mode=current_scale_mode)
            print(f"  [选中] {name} - Gizmo 已附加 (mask=0x{current_mask:02X}, scale={current_scale_mode})")

    # 事件处理: 键盘按键
    def on_key_down(event):
        nonlocal current_mask, current_scale_mode
        key = event.get('key', '').lower()

        new_mask = current_mask
        need_update = False

        if key == 't':
            new_mask = 0x07  # 0b000111: Tx|Ty|Tz
            print(f"  [模式] 仅平移")
        elif key == 'r':
            new_mask = 0x38  # 0b111000: Rx|Ry|Rz
            print(f"  [模式] 仅旋转")
        elif key == 'a':
            new_mask = 0x3F  # All
            print(f"  [模式] 组合 (全部)")
        elif key == 'x':
            new_mask ^= 0b001001  # Toggle Tx and Rx
            print(f"  [遮罩] 切换 X 轴")
        elif key == 'y':
            new_mask ^= 0b010010  # Toggle Ty and Ry
            print(f"  [遮罩] 切换 Y 轴")
        elif key == 'z':
            new_mask ^= 0b100100  # Toggle Tz and Rz
            print(f"  [遮罩] 切换 Z 轴")
        elif key == 'm':
            current_scale_mode = "world" if current_scale_mode == "screen" else "screen"
            need_update = True
            print(f"  [尺寸] 切换模式: {current_scale_mode}")

        if new_mask != current_mask or need_update:
            current_mask = new_mask
            if current_handle:
                viz.set_gizmo_mode(mask=current_mask, scale_mode=current_scale_mode)
            print(f"  -> mask=0x{current_mask:02X} | scale={current_scale_mode}")

    # 事件处理: Gizmo 变换 (仅用于日志输出，状态同步由 viewer 直接完成)
    def on_transformed(event):
        handle = event.get('handle')
        if handle in object_names:
            pose = event.get('pose', {})
            pos = pose.get('pos', [0, 0, 0])
            print(
                f"  [变换] {object_names[handle]} → 位置: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})"
            )

    # 注册事件处理器
    viz.on('picked', on_picked)
    viz.on('key_down', on_key_down)
    viz.on('transformed', on_transformed)

    # 回调由后台线程自动处理；主线程只负责维持脚本生命周期。
    viz.keep_running()


if __name__ == "__main__":
    main()

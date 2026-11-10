"""
FrameViz 示例 - 射线拾取

演示鼠标射线拾取功能和高亮交互。
"""

import frameviz as fv


def main():
    print("=" * 60)
    print("FrameViz Picking Demo")
    print("=" * 60)

    viz = fv.open()

    # 存储物体基础颜色
    base_colors = {}

    # 创建可拾取的物体
    box = viz.add_box(
        size=[0.8, 0.8, 0.8], pos=[-2, 0, 0.4], color=[0.9, 0.2, 0.2]
    )
    base_colors[box] = [0.9, 0.2, 0.2]

    sphere = viz.add_sphere(
        radius=0.5, pos=[0, 0, 0.5], color=[0.2, 0.9, 0.2]
    )
    base_colors[sphere] = [0.2, 0.9, 0.2]

    cyl = viz.add_cylinder(
        radius=0.3, height=1.0, pos=[2, 0, 0.5], color=[0.2, 0.2, 0.9]
    )
    base_colors[cyl] = [0.2, 0.2, 0.9]

    # 设置相机
    viz.set_camera_pose(
        eye=[5, 5, 3],
        target=[0, 0, 0.5],
        up=[0, 0, 1],
    )

    # 配置拾取（使用左键）
    viz.set_pick_config(enabled=True, mode="object", button=0)

    current_handle = None

    def on_picked(event):
        nonlocal current_handle
        hit_type = event.get("hit_type", "")
        handle = event.get("handle", "")

        # 恢复上一个物体的颜色
        if current_handle and current_handle in base_colors:
            viz.set_color(current_handle, base_colors[current_handle])

        if hit_type == "none" or not handle:
            current_handle = None
            return

        # 高亮当前选中的物体
        if handle in base_colors:
            current_handle = handle
            viz.set_color(handle, [1.0, 1.0, 0.2])  # 黄色高亮
            print(f"Picked handle: {handle}")

    # 注册事件回调
    viz.on("picked", on_picked)

    print("Click objects to highlight. Ctrl+C to exit.")
    viz.keep_running()


if __name__ == "__main__":
    main()

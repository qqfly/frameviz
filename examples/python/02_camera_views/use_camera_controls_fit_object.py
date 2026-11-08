"""
FrameViz 示例 - 相机控制和 fit_object

演示相机控制和聚焦功能。
"""

import frameviz as fv


def wait_step(prompt: str) -> None:
    try:
        input(prompt)
    except (KeyboardInterrupt, EOFError):
        pass


def main() -> None:
    print("=" * 60)
    print("FrameViz Camera Controls + fit_object")
    print("=" * 60)

    viz = fv.open()

    # 场景设置
    red_box = viz.add_box(size=[1, 1, 1], pos=[-2, 0, 0.5], color=[1, 0, 0])
    green_box = viz.add_box(size=[1, 1, 1], pos=[2, 0, 0.5], color=[0, 1, 0])
    viz.add_axes(length=1.5, radius=0.03)

    viz.add_text_2d(
        text="Camera controls demo",
        x=12,
        y=12,
        font_size=14,
        color="white",
    )

    viz.reset_camera()
    wait_step("Step 1: 场景已创建。按 Enter 继续...")

    viz.reset_camera(mode="fit_object", fit_handle=red_box)
    wait_step("Step 2: 应该只聚焦红色方块。按 Enter 继续...")

    viz.set_camera_controls(
        zoom_to_cursor=True,
        zoom_sensitivity=1.2,
        orbit_enabled=True,
        pan_enabled=True,
        zoom_enabled=True,
    )
    wait_step("Step 3: zoom_to_cursor 已启用。按 Enter 继续...")

    viz.set_camera_controls(zoom_to_cursor=False)
    wait_step("Step 4: zoom_to_cursor 已禁用。按 Enter 继续...")

    viz.set_camera_controls(zoom_enabled=False)
    wait_step("Step 5: 缩放已禁用。按 Enter 继续...")
    viz.set_camera_controls(zoom_enabled=True)

    viz.close()


if __name__ == "__main__":
    main()

"""
FrameViz 示例 - 多视图隔离

演示两个独立视图的场景隔离。
"""

import time

import frameviz as fv


def wait_step(prompt: str) -> None:
    try:
        input(prompt)
    except (KeyboardInterrupt, EOFError):
        pass


def main() -> None:
    print("=" * 60)
    print("FrameViz Multi-View Isolation")
    print("=" * 60)

    print("\n[1] 创建 View A...")
    viz_a = fv.open(reuse_browser=False, title="View A", x=100, y=100, width=800, height=600)
    print(f"    ✓ View A: view={viz_a.view_id}, scene={viz_a.scene_id}")

    time.sleep(0.3)  # 延迟确保窗口创建完成

    print("\n[2] 创建 View B...")
    viz_b = fv.open(reuse_browser=False, title="View B", x=950, y=100, width=800, height=600)
    print(f"    ✓ View B: view={viz_b.view_id}, scene={viz_b.scene_id}")

    # 创建独立场景对象
    print("\n[3] 添加场景对象...")
    viz_a.add_box(size=[1, 1, 1], pos=[0, 0, 0.5], color=[1, 0, 0])
    viz_a.add_text_2d(text="View A", x=12, y=12, font_size=14, color="white")
    viz_a.set_camera_pose(eye=[4, 4, 3], target=[0, 0, 0.5], up=[0, 0, 1])

    viz_b.add_sphere(radius=0.6, pos=[0, 0, 0.6], color=[0, 0, 1])
    viz_b.add_text_2d(text="View B", x=12, y=12, font_size=14, color="white")
    viz_b.set_camera_pose(eye=[4, -4, 3], target=[0, 0, 0.5], up=[0, 0, 1])

    print("\n创建了两个独立的场景。")
    print("\n按 Enter 退出...")
    print("=" * 60)

    wait_step("")

    print("\n[4] 清理...")
    viz_a.close()
    viz_b.close()
    print("    ✓ 所有视图已关闭")


if __name__ == "__main__":
    main()

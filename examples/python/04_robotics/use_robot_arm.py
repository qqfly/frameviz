"""
FrameViz 示例 - 简单机械臂

演示简单平面三连杆机械臂的动画。
"""

import math
import time

import frameviz as fv
import numpy as np


def quat_from_yaw(yaw: float) -> list:
    """从偏航角创建四元数。"""
    half = yaw * 0.5
    return [0.0, 0.0, math.sin(half), math.cos(half)]


def main() -> None:
    print("=" * 60)
    print("FrameViz Robot Arm (Simplified)")
    print("=" * 60)

    viz = fv.open()

    # 添加地面和坐标轴
    viz.add_plane(
        width=6.0,
        height=6.0,
        pos=[0, 0, 0],
        quat=[0, 0, 0, 1],
        color=[0.3, 0.3, 0.3, 0.5],
    )
    viz.add_axes(length=1.0)

    # 连杆长度
    L1 = 0.8
    L2 = 0.7
    L3 = 0.6

    # 创建三个连杆
    link1 = viz.add_box(
        size=[L1, 0.1, 0.1], pos=[L1 * 0.5, 0, 0.1], color=[0.9, 0.2, 0.2]
    )
    link2 = viz.add_box(
        size=[L2, 0.1, 0.1], pos=[L1 + L2 * 0.5, 0, 0.1], color=[0.2, 0.9, 0.2]
    )
    link3 = viz.add_box(
        size=[L3, 0.1, 0.1],
        pos=[L1 + L2 + L3 * 0.5, 0, 0.1],
        color=[0.2, 0.2, 0.9],
    )

    # 设置相机
    viz.set_camera_pose(
        eye=[4, 4, 3],
        target=[1.2, 0, 0.1],
        up=[0, 0, 1],
    )

    viz.add_text_2d(
        text="Simple planar arm animation",
        x=12,
        y=12,
        font_size=14,
        color="white",
    )

    # 动画循环
    for i in range(200):
        t = i * 0.05
        a1 = 0.6 * math.sin(t)
        a2 = 0.8 * math.sin(t * 0.7 + 0.5)
        a3 = 0.6 * math.sin(t * 0.9 + 1.2)

        theta1 = a1
        theta2 = a1 + a2
        theta3 = a1 + a2 + a3

        x1 = (L1 * 0.5) * math.cos(theta1)
        y1 = (L1 * 0.5) * math.sin(theta1)

        x2 = L1 * math.cos(theta1) + (L2 * 0.5) * math.cos(theta2)
        y2 = L1 * math.sin(theta1) + (L2 * 0.5) * math.sin(theta2)

        x3 = (
            L1 * math.cos(theta1)
            + L2 * math.cos(theta2)
            + (L3 * 0.5) * math.cos(theta3)
        )
        y3 = (
            L1 * math.sin(theta1)
            + L2 * math.sin(theta2)
            + (L3 * 0.5) * math.sin(theta3)
        )

        viz.set_transform(link1, pos=[x1, y1, 0.1], quat=quat_from_yaw(theta1))
        viz.set_transform(link2, pos=[x2, y2, 0.1], quat=quat_from_yaw(theta2))
        viz.set_transform(link3, pos=[x3, y3, 0.1], quat=quat_from_yaw(theta3))

        time.sleep(0.03)

    print("Animation complete. Press Enter to exit...")
    input()

    viz.close()


if __name__ == "__main__":
    main()

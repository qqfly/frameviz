"""
FrameViz 示例 - 颜色与透明度

展示 RGB/RGBA 颜色设置和动态颜色变化。
"""

import math
import time

import frameviz as fv


def main() -> None:
    print("=" * 60)
    print("FrameViz Colors & Transparency Demo")
    print("=" * 60)

    print("\n[1] 连接到 FrameViz...")
    viz = fv.open()
    print("    ✓ 已连接")

    # 添加地面和坐标轴
    viz.add_plane(
        width=10.0,
        height=10.0,
        pos=[0, 0, 0],
        quat=[0, 0, 0, 1],
        color=[0.3, 0.3, 0.3, 0.5],
    )
    viz.add_axes(length=1.0)

    # 1. RGB 颜色（不透明）
    print("\n[2] 创建 RGB 颜色对象...")
    viz.add_box(size=[1, 1, 1], pos=[-2, 0, 0.5], color=[1, 0, 0])  # 红色
    viz.add_sphere(radius=0.5, pos=[0, 0, 0.5], color=[0, 1, 0])  # 绿色
    viz.add_cylinder(radius=0.3, height=1.2, pos=[2, 0, 0.6], color=[0, 0, 1])  # 蓝色
    print("    ✓ RGB 对象已创建")

    # 2. RGBA 颜色（带透明度）
    print("\n[3] 创建透明对象...")
    box1 = viz.add_box(
        size=[1.5, 1.5, 0.2], pos=[-1, 2, 0.5], color=[1, 0, 0, 0.3]
    )
    box2 = viz.add_box(
        size=[1.5, 1.5, 0.2], pos=[0, 2, 0.8], color=[0, 1, 0, 0.5]
    )
    box3 = viz.add_box(
        size=[1.5, 1.5, 0.2], pos=[1, 2, 1.1], color=[0, 0, 1, 0.7]
    )
    print("    ✓ 透明对象已创建")

    # 3. 灰度颜色
    print("\n[4] 创建灰度对象...")
    viz.add_sphere(radius=0.3, pos=[-2, -2, 0.3], color=[0, 0, 0])
    viz.add_sphere(radius=0.3, pos=[-1, -2, 0.3], color=[0.5, 0.5, 0.5])
    viz.add_sphere(radius=0.3, pos=[0, -2, 0.3], color=[1, 1, 1])
    print("    ✓ 灰度对象已创建")

    # 设置相机
    viz.set_camera_pose(
        eye=[6, 6, 4],
        target=[0, 0, 0.5],
        up=[0, 0, 1],
    )

    print("\n" + "=" * 60)
    print("✓ 演示动态颜色变化...")
    print("  观察透明盒子的颜色变化！")
    print("  按 Ctrl+C 退出")
    print("=" * 60)

    # 4. 动态改变颜色
    try:
        for i in range(100):
            t = i * 0.1
            r = 0.5 + 0.5 * math.sin(t)
            g = 0.5 + 0.5 * math.sin(t + 2.094)
            b = 0.5 + 0.5 * math.sin(t + 4.189)

            viz.set_color(box1, [r, 0.0, 0.0, 0.3])
            viz.set_color(box2, [0.0, g, 0.5])
            viz.set_color(box3, [0.0, 0.0, b, 0.7])

            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n[退出] 用户中断")

    print("\n✓ 演示完成")
    viz.close()


if __name__ == "__main__":
    main()

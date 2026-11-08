"""
FrameViz 示例 - 点云和网格

展示点云和三角网格的渲染。
"""

import math

import frameviz as fv
import numpy as np


def main() -> None:
    print("=" * 60)
    print("FrameViz Point Cloud + Mesh")
    print("=" * 60)

    viz = fv.open()
    print(f"已连接: scene={viz.scene_id}")

    # 点云：圆形
    print("\n[1] 创建点云（圆形）...")
    point_count = 2000
    positions = np.zeros((point_count, 3), dtype=np.float32)
    colors = np.zeros((point_count, 3), dtype=np.float32)

    for i in range(point_count):
        t = i / point_count * 2 * math.pi
        r = 2.0
        positions[i, 0] = r * math.cos(t)
        positions[i, 1] = r * math.sin(t)
        positions[i, 2] = 0.2 * math.sin(3.0 * t)

        colors[i, 0] = 0.5 + 0.5 * math.cos(t)
        colors[i, 1] = 0.5 + 0.5 * math.sin(t)
        colors[i, 2] = 200 / 255  # 蓝色固定

    viz.add_points(positions, colors=colors, size=2.0)
    print(f"    ✓ 点云: {point_count} 点")

    # 金字塔网格
    print("\n[2] 创建金字塔网格...")
    vertices = np.array(
        [
            [0.0, 0.0, 1.0],  # 顶点
            [-0.5, -0.5, 0.0],
            [0.5, -0.5, 0.0],
            [0.5, 0.5, 0.0],
            [-0.5, 0.5, 0.0],
        ],
        dtype=np.float32,
    )

    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [0, 3, 4],
            [0, 4, 1],
            [1, 2, 3],
            [1, 3, 4],
        ],
        dtype=np.uint32,
    )

    viz.add_mesh(vertices, faces)
    print("    ✓ 金字塔网格")

    # 设置相机
    viz.set_camera_pose(
        eye=[5, 5, 3],
        target=[0, 0, 0.3],
        up=[0, 0, 1],
    )

    print("\n" + "=" * 60)
    print("✓ 渲染完成!")
    print("\n按 Enter 退出...")
    print("=" * 60)

    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    print("\n✓ 已关闭连接")


if __name__ == "__main__":
    main()

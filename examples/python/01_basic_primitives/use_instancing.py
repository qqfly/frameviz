"""
FrameViz 示例 - 高性能实例化渲染

展示实例化渲染的性能（10,000+ 对象）。
"""

import numpy as np
import frameviz as fv


def main() -> None:
    print("=" * 60)
    print("FrameViz Instancing Demo - High Performance Rendering")
    print("=" * 60)

    print("\n[1] 连接到 FrameViz...")
    viz = fv.open()
    print("    ✓ 已连接")

    # 添加地面平面
    viz.add_plane(
        width=50.0,
        height=50.0,
        pos=[0, 0, 0],
        quat=[0, 0, 0, 1],
        color=[0.2, 0.2, 0.2, 0.5],
    )

    # 添加坐标轴
    viz.add_axes(length=2.0)

    # 生成 10,000 个实例
    count = 10000
    print(f"\n[2] 生成 {count} 个实例...")

    # 随机生成位置
    rng = np.random.default_rng()
    positions = rng.uniform(-20.0, 20.0, size=(count, 3)).astype(np.float32)
    heights = rng.uniform(0.0, 10.0, size=count).astype(np.float32)
    positions[:, 2] = heights

    # 统一的四元数（无旋转）
    quaternions = np.zeros((count, 4), dtype=np.float32)
    quaternions[:, 3] = 1.0  # [0, 0, 0, 1]

    # 统一的缩放
    scale = 0.1
    scales = np.full((count, 3), [scale, scale, scale], dtype=np.float32)

    # 根据高度生成渐变颜色
    colors = np.zeros((count, 3), dtype=np.float32)
    colors[:, 0] = heights / 10.0  # R
    colors[:, 1] = 128.0 / 255.0  # G
    colors[:, 2] = 1.0 - heights / 10.0  # B

    print("    ✓ 数据生成完成")

    print(f"\n[3] 创建盒子实例...")
    viz.add_instances(
        "box",
        positions=positions,
        quats=quaternions,
        scales=scales,
        colors=colors,
    )
    print(f"    ✓ {count} 个实例创建完成")

    # 设置相机
    viz.set_camera_pose(
        eye=[30, 30, 20],
        target=[0, 0, 5],
        up=[0, 0, 1],
    )

    print("\n" + "=" * 60)
    print(f"✓ 正在渲染 {count} 个实例！")
    print("\n按 Enter 退出...")
    print("=" * 60)

    input()

    viz.close()
    print("\n✓ 已关闭连接")


if __name__ == "__main__":
    main()

"""
FrameViz 示例 - Mesh 颜色模式对比

演示功能:
- 顶点颜色 (colors) vs 统一颜色 (color) 的区别
- get_color() 对两种模式的不同返回值
- set_color() 将顶点颜色转换为统一颜色
"""

import numpy as np
import frameviz as fv
import time


def create_cube_mesh():
    """创建立方体网格数据."""
    vertices = np.array(
        [
            [0, 0, 0],  # 0: 左下前
            [1, 0, 0],  # 1: 右下前
            [1, 1, 0],  # 2: 右上前
            [0, 1, 0],  # 3: 左上前
            [0, 0, 1],  # 4: 左下后
            [1, 0, 1],  # 5: 右下后
            [1, 1, 1],  # 6: 右上后
            [0, 1, 1],  # 7: 左上后
        ],
        dtype=np.float32,
    )

    faces = np.array(
        [
            [0, 1, 2], [0, 2, 3],  # 前面
            [5, 4, 7], [5, 7, 6],  # 后面
            [4, 5, 1], [4, 1, 0],  # 底面
            [3, 2, 6], [3, 6, 7],  # 顶面
            [4, 0, 3], [4, 3, 7],  # 左面
            [1, 5, 6], [1, 6, 2],  # 右面
        ],
        dtype=np.uint32,
    )

    return vertices, faces


def create_vertex_colors(vertices, rgb_color):
    """为所有顶点创建统一颜色."""
    v_count = vertices.shape[0]
    colors = np.tile(rgb_color, (v_count, 1)).astype(np.float32)
    return colors


def create_gradient_colors(vertices):
    """创建从红到蓝的渐变顶点颜色."""
    v_count = vertices.shape[0]
    colors = np.zeros((v_count, 3), dtype=np.float32)

    # 基于 z 坐标创建从红到蓝的渐变
    z_min = vertices[:, 2].min()
    z_max = vertices[:, 2].max()
    z_range = z_max - z_min if z_max > z_min else 1.0

    for i in range(v_count):
        t = (vertices[i, 2] - z_min) / z_range
        colors[i] = [1 - t, 0, t]  # 红到蓝的渐变

    return colors


def main() -> None:
    print("=" * 70)
    print("FrameViz - Mesh 颜色模式对比示例")
    print("=" * 70)

    viz = fv.open(title="Mesh Color Modes Demo", width=1200, height=800)
    print(f"\n已连接: scene={viz.scene_id}")

    vertices, faces = create_cube_mesh()

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 1: 顶点颜色 vs 统一颜色
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[1] 创建两种颜色模式的 mesh...")

    # 左边: 使用顶点颜色（渐变效果）
    print("\n  左边 - 顶点颜色模式 (colors 参数):")
    gradient_colors = create_gradient_colors(vertices)
    h_vertex = viz.add_mesh(
        vertices,
        faces,
        colors=gradient_colors,
        alpha=0.9,
    )
    print(f"    ✓ 创建渐变色立方体 (handle: {h_vertex})")
    print("    - 每个顶点有独立的颜色")
    print("    - 顶点间自动插值产生渐变效果")

    # 右边: 使用统一颜色
    print("\n  右边 - 统一颜色模式 (color 参数):")
    vertices_right = vertices.copy() + np.array([2, 0, 0], dtype=np.float32)
    h_uniform = viz.add_mesh(
        vertices_right,
        faces,
        color=[0.2, 0.8, 0.5],  # 青绿色
        alpha=0.9,
    )
    print(f"    ✓ 创建纯色立方体 (handle: {h_uniform})")
    print("    - 整个 mesh 使用同一个颜色")
    print("    - 类似 add_box 的 color API")

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 2: 使用 get_color() 查询颜色
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[2] 使用 get_color() 查询两种模式...")

    # 查询顶点颜色 mesh
    color_vertex = viz.get_color(h_vertex)
    print(f"\n  顶点颜色 mesh:")
    print(f"    get_color() 返回: {color_vertex}")
    print(f"    → 返回 None，因为没有单一的统一颜色")

    # 查询统一颜色 mesh
    color_uniform = viz.get_color(h_uniform)
    print(f"\n  统一颜色 mesh:")
    print(f"    get_color() 返回: {[f'{c:.3f}' for c in color_uniform] if color_uniform else None}")
    print(f"    → 返回 RGBA 值 (RGB + alpha)")

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 3: 使用 get_alpha() 查询透明度
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[3] 使用 get_alpha() 查询透明度...")

    alpha_vertex = viz.get_alpha(h_vertex)
    alpha_uniform = viz.get_alpha(h_uniform)

    print(f"\n  顶点颜色 mesh alpha: {alpha_vertex:.2f}")
    print(f"  统一颜色 mesh alpha: {alpha_uniform:.2f}")
    print(f"  → get_alpha() 对两种模式都有效")

    # 设置相机查看初始状态
    viz.set_camera_pose(eye=[1.5, -3, 2], target=[1, 0.5, 0.5], up=[0, 0, 1])

    print("\n" + "=" * 70)
    print("当前场景:")
    print("  左边: 渐变色立方体 (顶点颜色)")
    print("  右边: 纯色立方体 (统一颜色)")
    print("=" * 70)
    print("\n按 Enter 继续演示 set_color() 转换功能...")
    print("=" * 70)

    try:
        input()
    except (KeyboardInterrupt, EOFError):
        viz.close()
        return

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 4: 使用 set_color() 转换顶点颜色为统一颜色
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[4] 使用 set_color() 将顶点颜色转换为统一颜色...")

    # 转换前
    print("\n  转换前:")
    color_before = viz.get_color(h_vertex)
    print(f"    左边 mesh 的 get_color(): {color_before}")

    # 执行转换
    print("\n  执行 set_color(handle, [1.0, 0.5, 0.0])...")
    viz.set_color(h_vertex, [1.0, 0.5, 0.0])  # 设置为橙色
    print("    ✓ 调用完成")

    # 短暂延迟让渲染更新
    time.sleep(0.1)

    # 转换后
    print("\n  转换后:")
    color_after = viz.get_color(h_vertex)
    print(f"    左边 mesh 的 get_color(): {[f'{c:.3f}' for c in color_after] if color_after else None}")
    print("    → 现在返回 RGBA 值，不再是 None")
    print("    → 渐变效果消失，变成统一的橙色")

    print("\n" + "=" * 70)
    print("转换结果:")
    print("  左边: 已从渐变色转换为纯橙色")
    print("  右边: 保持原来的青绿色")
    print("\n说明:")
    print("  - set_color() 会自动将顶点颜色 mesh 转换为统一颜色")
    print("  - 转换是单向的（不可逆）")
    print("  - 转换会重建几何体，移除顶点颜色数据")
    print("=" * 70)
    print("\n按 Enter 继续测试 set_alpha()...")
    print("=" * 70)

    try:
        input()
    except (KeyboardInterrupt, EOFError):
        viz.close()
        return

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 5: 使用 set_alpha() 修改透明度
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[5] 使用 set_alpha() 修改两个 mesh 的透明度...")

    print("\n  将两个立方体都设置为半透明 (alpha=0.4)...")
    viz.set_alpha(h_vertex, 0.4)
    viz.set_alpha(h_uniform, 0.4)

    alpha_vertex_new = viz.get_alpha(h_vertex)
    alpha_uniform_new = viz.get_alpha(h_uniform)

    print(f"    左边 mesh alpha: {alpha_vertex_new:.2f}")
    print(f"    右边 mesh alpha: {alpha_uniform_new:.2f}")
    print("    ✓ set_alpha() 对两种模式都有效")

    print("\n" + "=" * 70)
    print("✓ 演示完成!")
    print("\nAPI 总结:")
    print("  1. 创建 mesh:")
    print("     - 使用 colors=... 创建顶点颜色 mesh (渐变效果)")
    print("     - 使用 color=... 创建统一颜色 mesh (纯色)")
    print("     - 两个参数互斥，不能同时使用")
    print("\n  2. 查询颜色:")
    print("     - get_color(): 统一颜色返回 RGBA，顶点颜色返回 None")
    print("     - get_alpha(): 对两种模式都返回 alpha 值")
    print("\n  3. 修改颜色:")
    print("     - set_color(): 设置统一颜色（自动转换顶点颜色 mesh）")
    print("     - set_alpha(): 修改透明度（对两种模式都有效）")
    print("\n" + "=" * 70)
    print("按 Enter 退出...")
    print("=" * 70)

    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    print("\n✓ 已关闭连接")


if __name__ == "__main__":
    main()

"""
FrameViz 示例 - Mesh 透明度和边线控制

演示功能:
- 使用 alpha 参数控制 Mesh 透明度
- 使用 wireframe 参数控制是否显示边线
- color 仅支持 RGB/RGBA（长度 3 或 4），RGBA 可直接携带 alpha
"""

import numpy as np
import frameviz as fv


def create_cube_mesh():
    """创建立方体网格数据."""
    # 立方体 8 个顶点
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

    # 12 个三角形（6 个面，每面 2 个三角形）
    faces = np.array(
        [
            # 前面 (z=0)
            [0, 1, 2],
            [0, 2, 3],
            # 后面 (z=1)
            [5, 4, 7],
            [5, 7, 6],
            # 底面 (y=0)
            [4, 5, 1],
            [4, 1, 0],
            # 顶面 (y=1)
            [3, 2, 6],
            [3, 6, 7],
            # 左面 (x=0)
            [4, 0, 3],
            [4, 3, 7],
            # 右面 (x=1)
            [1, 5, 6],
            [1, 6, 2],
        ],
        dtype=np.uint32,
    )

    return vertices, faces


def create_vertex_colors(vertices, rgb_color):
    """为所有顶点创建统一颜色."""
    v_count = vertices.shape[0]
    colors = np.tile(rgb_color, (v_count, 1)).astype(np.float32)
    return colors


def main() -> None:
    print("=" * 70)
    print("FrameViz - Mesh 透明度和边线控制示例")
    print("=" * 70)

    viz = fv.open(title="Mesh Transparency Demo", width=1000, height=800)
    print(f"\n已连接: scene={viz.scene_id}")

    vertices, faces = create_cube_mesh()

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 1: Alpha 透明度控制
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[1] 添加三个不同透明度的立方体 (alpha 参数)...")

    # 不透明红色立方体 (alpha=1.0)
    red_colors = create_vertex_colors(vertices, [1, 0, 0])
    viz.add_mesh(
        vertices,
        faces,
        colors=red_colors,
        alpha=1.0,
    )
    print("    ✓ 红色立方体: alpha=1.0 (不透明)")

    # 半透明绿色立方体 (alpha=0.5)
    vertices_2 = vertices.copy() + np.array([1.5, 0, 0], dtype=np.float32)
    green_colors = create_vertex_colors(vertices_2, [0, 1, 0])
    viz.add_mesh(
        vertices_2,
        faces,
        colors=green_colors,
        alpha=0.5,
    )
    print("    ✓ 绿色立方体: alpha=0.5 (半透明)")

    # 高透明蓝色立方体 (alpha=0.3)
    vertices_3 = vertices.copy() + np.array([3.0, 0, 0], dtype=np.float32)
    blue_colors = create_vertex_colors(vertices_3, [0, 0, 1])
    viz.add_mesh(
        vertices_3,
        faces,
        colors=blue_colors,
        alpha=0.3,
    )
    print("    ✓ 蓝色立方体: alpha=0.3 (高透明)")

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 2: Wireframe 边线控制
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[2] 添加两个立方体，一个显示边线，一个不显示 (wireframe 参数)...")

    # 无边线黄色立方体 (wireframe=False)
    vertices_4 = vertices.copy() + np.array([0, 1.5, 0], dtype=np.float32)
    yellow_colors = create_vertex_colors(vertices_4, [1, 1, 0])
    viz.add_mesh(
        vertices_4,
        faces,
        colors=yellow_colors,
        wireframe=False,
    )
    print("    ✓ 黄色立方体: wireframe=False (无边线)")

    # 有边线品红色立方体 (wireframe=True)
    vertices_5 = vertices.copy() + np.array([1.5, 1.5, 0], dtype=np.float32)
    magenta_colors = create_vertex_colors(vertices_5, [1, 0, 1])
    viz.add_mesh(
        vertices_5,
        faces,
        colors=magenta_colors,
        wireframe=True,
    )
    print("    ✓ 品红色立方体: wireframe=True (显示黑色边线)")

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 3: 组合使用 alpha + wireframe
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[3] 添加同时使用 alpha 和 wireframe 的立方体...")

    # 透明 + 有边线青色立方体
    vertices_6 = vertices.copy() + np.array([3.0, 1.5, 0], dtype=np.float32)
    cyan_colors = create_vertex_colors(vertices_6, [0, 1, 1])
    viz.add_mesh(
        vertices_6,
        faces,
        colors=cyan_colors,
        alpha=0.6,
        wireframe=True,
    )
    print("    ✓ 青色立方体: alpha=0.6, wireframe=True (透明且带边线)")

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 4: 使用 color 参数创建统一颜色的 mesh
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[4] 使用 color 参数创建统一颜色的 mesh...")

    # 使用 color 参数（类似 add_box 的 API）
    vertices_7 = vertices.copy() + np.array([0, 3.0, 0], dtype=np.float32)
    h7 = viz.add_mesh(
        vertices_7,
        faces,
        color=[0.8, 0.4, 0.2],  # 橙色 (统一颜色)
        alpha=0.7,
    )
    print("    ✓ 橙色立方体: 使用 color=[0.8, 0.4, 0.2] (统一颜色)")

    # RGBA 颜色（未显式传 alpha 时，使用 color[3]）
    vertices_9 = vertices.copy() + np.array([3.0, 3.0, 0], dtype=np.float32)
    h9 = viz.add_mesh(
        vertices_9,
        faces,
        color=[0.2, 0.6, 1.0, 0.4],  # 蓝色半透明 (RGBA)
    )
    print("    ✓ 蓝色立方体: 使用 RGBA 颜色（未传 alpha，使用 color[3]）")

    # ─────────────────────────────────────────────────────────────────────────
    # 演示 5: 使用 get_color() 和 get_alpha()
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[5] 使用 get_color() 和 get_alpha() 查询对象属性...")

    # 对统一颜色的 mesh
    color_result = viz.get_color(h7)
    alpha_result = viz.get_alpha(h7)
    print(f"    ✓ 统一颜色 mesh:")
    print(f"      - get_color() 返回: {[f'{c:.2f}' for c in color_result] if color_result else None}")
    print(f"      - get_alpha() 返回: {alpha_result:.2f}")

    # 对 RGBA 颜色的 mesh（未显式传 alpha）
    color_result_rgba = viz.get_color(h9)
    alpha_result_rgba = viz.get_alpha(h9)
    print(f"    ✓ RGBA 颜色 mesh:")
    print(f"      - get_color() 返回: {[f'{c:.2f}' for c in color_result_rgba] if color_result_rgba else None}")
    print(f"      - get_alpha() 返回: {alpha_result_rgba:.2f}")

    # 对顶点颜色的 mesh（使用之前创建的红色立方体）
    # 注意: 我们需要保存句柄来测试，让我们创建一个新的用于测试
    vertices_8 = vertices.copy() + np.array([1.5, 3.0, 0], dtype=np.float32)
    vertex_colors = create_vertex_colors(vertices_8, [0.5, 0.5, 1.0])  # 淡蓝色
    h8 = viz.add_mesh(
        vertices_8,
        faces,
        colors=vertex_colors,  # 使用 colors（顶点颜色）
        alpha=0.8,
    )

    color_result_vertex = viz.get_color(h8)
    alpha_result_vertex = viz.get_alpha(h8)
    print(f"    ✓ 顶点颜色 mesh:")
    print(f"      - get_color() 返回: {color_result_vertex} (对顶点颜色返回 None)")
    print(f"      - get_alpha() 返回: {alpha_result_vertex:.2f} (仍然有效)")

    # ─────────────────────────────────────────────────────────────────────────
    # 设置相机
    # ─────────────────────────────────────────────────────────────────────────
    viz.set_camera_pose(eye=[2, 2, 5], target=[1.5, 1.5, 0.5], up=[0, 0, 1])

    print("\n" + "=" * 70)
    print("✓ 渲染完成!")
    print("\n观察要点:")
    print("  第一排 (alpha 透明度):")
    print("    - 红色立方体完全不透明，遮挡后面的物体")
    print("    - 绿色立方体半透明，可以隐约看到后面的物体")
    print("    - 蓝色立方体高透明，几乎可以完全看穿")
    print("\n  第二排 (wireframe 边线):")
    print("    - 黄色立方体表面光滑，没有边线")
    print("    - 品红色立方体显示黑色半透明边线，便于观察网格结构")
    print("\n  第三排 (组合):")
    print("    - 青色立方体既有透明效果，又显示边线")
    print("\n  第四排 (color 参数 & get 方法):")
    print("    - 橙色立方体使用 color 参数（统一颜色，类似 add_box API）")
    print("    - 蓝色立方体使用 RGBA 颜色（未传 alpha 时使用 color[3]）")
    print("    - 淡蓝色立方体使用 colors 参数（顶点颜色）")
    print("    - get_color() 对统一颜色返回 RGBA，对顶点颜色返回 None")
    print("    - get_alpha() 对两种模式都有效")
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

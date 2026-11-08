from __future__ import annotations

import numpy as np

import frameviz as fv


def main() -> None:
    print("=" * 50)
    print("FrameViz View Config + Mesh (TRI + POLY)")
    print("=" * 50)

    print("\n[1] 连接到 FrameViz...")
    # 打开无边框窗口（沉浸式模式）
    # 要显示正常窗口，设置 window_decorations=True 或省略此参数
    viz = fv.open(window_decorations=False)
    print("    ✓ 已连接（无边框窗口）")
    input("  按 Enter 继续...")

    print("\n[2] 环境设置...")
    viz.set_view_config(show_grid=True,
                        show_axes=True,
                        background=[0.1, 0.1, 0.2])
    print("    ✓ 环境已设置")
    input("  按 Enter 继续...")

    print("\n[3] 添加基础图元并克隆...")
    box = viz.add_box(size=[0.2, 0.2, 0.2], pos=[0, 0, 0.1], color=[1, 0, 0])
    input("  按 Enter 继续...")
    clone_a = viz.clone_object(box)
    clone_b = viz.clone_object(box)
    clone_c = viz.clone_object(box)
    viz.set_transform(clone_a, pos=[0.4, 0.0, 0.1])
    viz.set_transform(clone_b, pos=[0.0, 0.4, 0.1])
    viz.set_transform(clone_c, pos=[0.4, 0.4, 0.1])
    print("    ✓ 克隆完成: 3 个")
    input("  按 Enter 继续...")

    print("\n[4] TRI Mesh (pyramid, per-face colors)...")
    tri_vertices = np.array(
        [
            [-0.8, 0.0, 0.0],
            [-0.4, 0.0, 0.0],
            [-0.4, 0.4, 0.0],
            [-0.8, 0.4, 0.0],
            [-0.6, 0.2, 0.4],
        ],
        dtype=np.float32,
    )
    tri_faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [0, 1, 4],
            [1, 2, 4],
            [2, 3, 4],
            [3, 0, 4],
        ],
        dtype=np.uint32,
    )
    tri_colors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 1.0, 0.0],
            [1.0, 0.0, 1.0],
            [0.0, 1.0, 1.0],
        ],
        dtype=np.float32,
    )
    tri_mesh = viz.add_mesh(tri_vertices, tri_faces, colors=tri_colors, faces_format="tri")
    print(f"    ✓ TRI mesh: {tri_mesh}")
    input("  按 Enter 继续...")

    print("\n[5] POLY Mesh (cube, per-face colors)...")
    poly_vertices = np.array(
        [
            [0.2, 0.0, 0.0],
            [0.6, 0.0, 0.0],
            [0.6, 0.4, 0.0],
            [0.2, 0.4, 0.0],
            [0.2, 0.0, 0.4],
            [0.6, 0.0, 0.4],
            [0.6, 0.4, 0.4],
            [0.2, 0.4, 0.4],
        ],
        dtype=np.float32,
    )
    poly_faces = {
        "counts": np.array([4, 4, 4, 4, 4, 4], dtype=np.uint32),
        "indices": np.array(
            [
                0, 1, 2, 3,
                4, 5, 6, 7,
                0, 1, 5, 4,
                3, 2, 6, 7,
                0, 4, 7, 3,
                1, 2, 6, 5,
            ],
            dtype=np.uint32,
        ),
    }
    poly_colors = np.array(
        [
            [0.9, 0.2, 0.2],
            [0.2, 0.9, 0.2],
            [0.2, 0.2, 0.9],
            [0.9, 0.9, 0.2],
            [0.9, 0.2, 0.9],
            [0.2, 0.9, 0.9],
        ],
        dtype=np.float32,
    )
    poly_mesh = viz.add_mesh(poly_vertices, poly_faces, colors=poly_colors, faces_format="poly")
    print(f"    ✓ POLY mesh: {poly_mesh}")
    input("  按 Enter 继续...")

    print("\n[6] 查询相机姿态...")
    cam = viz.get_camera_pose()
    print(f"    ✓ 相机姿态: {cam}")
    input("  按 Enter 继续...")

    print("\n[7] is_object_alive / remove_objects...")
    alive = viz.is_object_alive(box)
    print(f"    ✓ is_alive(box) = {alive}")
    viz.remove_objects([box, clone_a, clone_b, clone_c])
    print("    ✓ 批量删除完成")

    print("\n" + "=" * 50)
    print("✓ 示例完成！")
    print("=" * 50)

    try:
        input("\n按 Enter 键退出...")
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    print("\n✓ 已断开连接")


if __name__ == "__main__":
    main()

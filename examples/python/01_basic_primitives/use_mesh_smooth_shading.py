"""
FrameViz 示例 - Mesh 平面着色 vs 平滑着色

演示功能:
- add_mesh 默认 smooth shading（smooth_shading=True）
- smooth_shading=False 与 smooth_shading=True 的质感差异
"""

import math
import numpy as np
import frameviz as fv


def create_uv_sphere(radius: float = 0.5, lat_segments: int = 16, lon_segments: int = 24):
    """创建一个简单 UV Sphere 三角网格."""
    vertices = []
    faces = []

    for i in range(lat_segments + 1):
        theta = math.pi * i / lat_segments
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)

        for j in range(lon_segments):
            phi = 2.0 * math.pi * j / lon_segments
            x = radius * sin_theta * math.cos(phi)
            y = radius * sin_theta * math.sin(phi)
            z = radius * cos_theta
            vertices.append([x, y, z])

    def idx(i: int, j: int) -> int:
        return i * lon_segments + (j % lon_segments)

    for i in range(lat_segments):
        for j in range(lon_segments):
            i0 = idx(i, j)
            i1 = idx(i, j + 1)
            i2 = idx(i + 1, j + 1)
            i3 = idx(i + 1, j)

            faces.append([i0, i1, i2])
            faces.append([i0, i2, i3])

    return np.array(vertices, dtype=np.float32), np.array(faces, dtype=np.uint32)


def main() -> None:
    print("=" * 70)
    print("FrameViz - Mesh 平面着色 vs 平滑着色")
    print("=" * 70)

    viz = fv.open(title="Mesh Smooth Shading Demo", width=1200, height=800)
    print(f"已连接: scene={viz.scene_id}")

    vertices, faces = create_uv_sphere()

    print("\n[1] 左侧: flat shading (smooth_shading=False)")
    h_flat = viz.add_mesh(
        vertices + np.array([-0.8, 0.0, 0.0], dtype=np.float32),
        faces,
        color=[0.95, 0.55, 0.2],
        smooth_shading=False,
    )
    print(f"    handle: {h_flat}")

    print("\n[2] 右侧: 默认 smooth shading (smooth_shading=True)")
    h_smooth = viz.add_mesh(
        vertices + np.array([0.8, 0.0, 0.0], dtype=np.float32),
        faces,
        color=[0.95, 0.55, 0.2],
        smooth_shading=True
    )
    print(f"    handle: {h_smooth}")

    viz.set_camera_pose(
        eye=[0.0, -2.6, 1.0],
        target=[0.0, 0.0, 0.0],
        up=[0.0, 0.0, 1.0],
    )

    print("\n观察建议:")
    print("- 左球高光会有明显面片分段感")
    print("- 右球高光更连续，表面更平滑")
    print("\n按 Enter 退出...")
    input()

    viz.close()
    print("已关闭连接")


if __name__ == "__main__":
    main()

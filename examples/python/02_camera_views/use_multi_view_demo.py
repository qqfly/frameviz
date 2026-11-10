"""
FrameViz 示例 - 多视图与场景管理（含浏览器窗口）

演示功能:
- 同时使用 Tauri 窗口和浏览器窗口显示同一个 Scene
- window_mode=2 打开 Tauri（若已运行则新开窗口）
- window_mode=1 打开浏览器窗口
- 创建多个 View 共享同一个 Scene
- 演示无边框窗口 (window_decorations=False)

运行方式:
1. 安装 FrameViz 运行环境和配套 Python SDK，脚本会自动启动。
2. 运行脚本: python examples/python/02_camera_views/use_multi_view_demo.py
"""

import frameviz as fv
import numpy as np


def main():
    print("=" * 70)
    print("FrameViz 多视图与场景管理示例 (Tauri + 浏览器 + 无边框窗口)")
    print("=" * 70)

    print("\n[1] 创建视图...")

    # viz1: Tauri 主视图，创建新场景（左上角）
    viz1 = fv.open(reuse_browser=False, title="Tauri 主视图", window_mode=2, x=100, y=100, width=800, height=600)
    print(f"    ✓ viz1 (Tauri): view={viz1.view_id}, scene={viz1.scene_id}")

    # viz2: 浏览器窗口，共享 viz1 的场景（右上角）
    viz2 = fv.open(reuse_browser=False, title="浏览器视图", share_scene=viz1.scene_id, window_mode=1, x=950, y=100, width=800, height=600)
    print(f"    ✓ viz2 (Browser): view={viz2.view_id}, scene={viz2.scene_id} (共享)")

    # viz3: Tauri 独立场景（左下）
    viz3 = fv.open(reuse_browser=False, title="Tauri 独立场景", window_mode=2, x=100, y=400, width=800, height=600)
    print(f"    ✓ viz3 (Tauri): view={viz3.view_id}, scene={viz3.scene_id} (独立)")

    # viz4: 无边框窗口，共享 viz1 的场景（右下）
    viz4 = fv.open(
        reuse_browser=False,
        title="无边框窗口",
        share_scene=viz1.scene_id,
        window_mode=2,
        window_decorations=False,  # 无边框（沉浸式）
        x=950,
        y=200,
        width=800,
        height=600,
    )
    print(f"    ✓ viz4 (Frameless): view={viz4.view_id}, scene={viz4.scene_id} (无边框)")

    # ─────────────────────────────────────────────────────────────────────────
    # 向各场景添加对象
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[2] 添加场景对象...")

    # 场景 s_1: 通过 viz1 添加 (viz2 和 viz4 也能看到)
    viz1.add_axes(length=1.0)
    viz1.add_box(size=[1, 1, 1], pos=[0, 0, 0.5], color='red')
    viz1.add_sphere(radius=0.3, pos=[1.5, 0, 0.3], color='green')
    print(f"    ✓ 场景 {viz1.scene_id}: 添加了 axes, box(红), sphere(绿)")
    print(f"      → Tauri、浏览器和无边框窗口应该同时显示这些对象")

    # 场景 s_2: 通过 viz3 添加
    viz3.add_axes(length=2.0)
    viz3.add_cylinder(radius=0.5, height=2.0, pos=[0, 0, 1], color='blue')
    viz3.add_cone(radius=0.4, height=1.0, pos=[2, 0, 0.5], color='yellow')

    # 添加点云到 s_2
    n = 1000
    pos = np.random.randn(n, 3).astype(np.float32) * 0.5
    pos[:, 2] += 2.5
    colors = np.full((n, 3), [1.0, 0.0, 1.0], dtype=np.float32)  # magenta
    viz3.add_points(pos, colors=colors, size=3)
    print(f"    ✓ 场景 {viz3.scene_id}: 添加了 axes, cylinder(蓝), cone(黄), points(品红)")

    # 设置相机
    viz1.set_camera_pose(eye=[5, 5, 3], target=[0, 0, 0.5])
    viz2.set_camera_pose(eye=[-5, 5, 3], target=[0, 0, 0.5])  # 浏览器不同角度
    viz4.set_camera_pose(eye=[0, 0, 5], target=[0, 0, 0.5])  # 无边框窗口俯视图

    # ─────────────────────────────────────────────────────────────────────────
    # 进入交互模式
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("✓ 场景创建完成!")
    print()
    print("当前状态:")
    print(f"  • viz1 (Tauri)    → 场景 {viz1.scene_id}: box(红) + sphere(绿)")
    print(f"  • viz2 (Browser)  → 场景 {viz1.scene_id}: 共享 viz1，不同角度")
    print(f"  • viz3 (Tauri)    → 场景 {viz3.scene_id}: cylinder(蓝) + cone(黄) + points")
    print(f"  • viz4 (Frameless)→ 场景 {viz1.scene_id}: 共享 viz1，俯视图")
    print()
    print("观察: 所有窗口应显示相应的场景内容")
    print("      viz1, viz2, viz4 共享同一场景，viz3 是独立场景")
    print("      viz4 是无边框窗口，提供沉浸式体验")
    print("=" * 70)

    print("\n你可以尝试:")
    print("  viz1.add_box(color='cyan', pos=[0, 2, 0.5])  # 所有共享窗口都会显示")
    print("  viz4.attach_scene(viz3.scene_id)  # 切换场景到独立场景")

    # 等待用户交互
    try:
        input("\n按 Enter 键退出...")
    except (KeyboardInterrupt, EOFError):
        pass

    # 清理所有连接（退出前主动关闭）
    print("\n[3] 清理连接...")
    viz1.close()
    viz2.close()
    viz3.close()
    viz4.close()
    print("    ✓ 所有视图已关闭")
    print("\nDone.")


if __name__ == "__main__":
    main()

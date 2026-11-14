"""
FrameViz 基础示例 - Hello World

展示最简单的 FrameViz 使用方式：连接、绘制、关闭。

运行前请确保：
先安装 FrameViz 运行环境和配套 Python SDK；fv.open() 会自动发现并启动。
需要浏览器时使用 fv.open(window_mode=1)。安装与故障排查见 docs/INSTALLATION.md。
"""

import frameviz as fv

def main():
    print("=" * 50)
    print("FrameViz Hello World")
    print("=" * 50)
    
    # 1. 连接到 FrameViz
    print("\n[1] 连接到 FrameViz...")
    try:
        viz = fv.open()
        print(f"    ✓ 已连接! scene={viz.scene_id}, view={viz.view_id}")
    except Exception as e:
        print(f"    ✗ 连接失败: {e}")
        print("\n请按 docs/INSTALLATION.md 安装运行环境及配套 SDK；无需启动开发服务器。")
        return
    
    # 2. 绘制基础图元
    print("\n[2] 绘制图元...")
    
    # 坐标轴
    axes = viz.add_axes(length=1.0, pos=[0, 0, 0])
    print(f"    ✓ 坐标轴: {axes}")
    
    # 红色立方体
    box = viz.add_box(size=[1, 1, 1], pos=[0, 0, 0.5], color='red')
    print(f"    ✓ 立方体: {box}")
    
    # 蓝色球体
    sphere = viz.add_sphere(radius=0.3, pos=[2, 0, 0.3], color='blue')
    print(f"    ✓ 球体: {sphere}")
    
    # 绿色圆柱
    cylinder = viz.add_cylinder(radius=0.2, height=1.0, pos=[-2, 0, 0.5], color='green')
    print(f"    ✓ 圆柱: {cylinder}")
    
    viz.add_cone(radius=0.35, height=0.8, position=[-1.8, 1.5, 0.4], color="orange")
    # The endpoints define the arrow in its local frame; set_transform moves the whole arrow.
    # 黄色箭头
    arrow = viz.add_arrow(start=[1, 2, 0], end=[1, 2, 1.5], color='yellow')
    print(f"    ✓ 箭头: {arrow}")
    
    # 半透明平面
    plane = viz.add_plane(width=5, height=5, pos=[0, 0, 0], color=[0.5, 0.5, 0.5, 0.3])
    print(f"    ✓ 地面: {plane}")
    
    # 3D 文字标签
    label = viz.add_text_3d("Hello FrameViz!", pos=[0, 0, 2], font_size=20, color='white')
    print(f"    ✓ 标签: {label}")
    
    # 3. 设置相机
    print("\n[3] 设置相机...")
    viz.set_camera_pose(
        eye=[5, 5, 3],
        target=[0, 0, 0.5],
        up=[0, 0, 1]
    )
    print("    ✓ 相机已设置")
    
    # 4. 等待用户
    print("\n" + "=" * 50)
    print("✓ 渲染完成! 请在窗口中查看")
    print("  按 Enter 退出...")
    print("=" * 50)
    
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
    
    # 5. 关闭连接
    viz.close()
    print("\n已关闭连接")


if __name__ == "__main__":
    main()

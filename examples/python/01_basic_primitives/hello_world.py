"""
FrameViz 基础示例 - Hello World

展示最简单的 FrameViz 使用方式：连接、绘制、关闭。

运行前请确保：
1. 启动 FrameViz (Tauri): pnpm -C packages/frameviz-host-tauri tauri:dev
2. 浏览器模式（可选）: python3 -m http.server 8080
   然后打开 http://localhost:8080/packages/frameviz-web-viewer/
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
        print("\n请确保已启动 FrameViz:")
        print("  1. pnpm -C packages/frameviz-host-tauri tauri:dev")
        print("  2. 浏览器模式（可选）: python3 -m http.server 8080")
        print("     浏览器打开 http://localhost:8080/packages/frameviz-web-viewer/")
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

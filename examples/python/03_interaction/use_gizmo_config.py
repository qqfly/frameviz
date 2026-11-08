from __future__ import annotations

import frameviz as fv


def main() -> None:
    print("=" * 50)
    print("FrameViz Gizmo Config")
    print("=" * 50)

    print("\n[1] 连接到 FrameViz...")
    viz = fv.open()
    print("    ✓ 已连接")

    print("\n[2] 创建一个盒子并附加 Gizmo...")
    box = viz.add_box(size=(0.4, 0.2, 0.1), pos=(0, 0, 0.05), color="orange")
    # mask=0x3F (default) 表示 6 自由度全部启用
    viz.attach_gizmo(box, size=1.5)
    print("    ✓ Gizmo 已附加 (size=1.5, mask=0x3F)")

    print("\n[3] 切换为仅旋转...")
    # mask=0x38 (0b111000) 表示仅启用 Rx|Ry|Rz
    viz.set_gizmo_mode(mask=0x38, size=1.2)
    print("    ✓ 切换为仅旋转 (mask=0x38, size=1.2)")

    print("\n" + "=" * 50)
    print("拖拽 Gizmo 测试，按 Enter 退出...")
    print("=" * 50)
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    print("\n已关闭连接")


if __name__ == "__main__":
    main()

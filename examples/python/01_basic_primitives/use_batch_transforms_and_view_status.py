from __future__ import annotations

import numpy as np

import frameviz as fv


def main() -> None:
    print("=" * 50)
    print("FrameViz Batch Transforms + View Status")
    print("=" * 50)

    print("\n[1] 连接到 FrameViz...")
    viz = fv.open()
    print("    ✓ 已连接")

    print("\n[2] 创建多个盒子...")
    handles = []
    for i in range(6):
        handle = viz.add_box(
            size=(0.12, 0.12, 0.12),
            pos=(i * 0.15, 0.0, 0.06),
            color=(0.2 + i * 0.1, 0.6, 0.9),
        )
        handles.append(handle)
    print(f"    ✓ 创建 {len(handles)} 个盒子")

    print("\n[3] 批量更新位置...")
    items = []
    for i, handle in enumerate(handles):
        pos = [i * 0.15, 0.25, 0.06]
        items.append({"handle": handle, "pose": {"pos": pos, "quat": [0, 0, 0, 1]}})
    viz.set_object_transforms(items)
    print("    ✓ 批量变换完成")

    print("\n" + "=" * 50)
    print("按 Enter 退出...")
    print("=" * 50)
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    print("\n已关闭连接")


if __name__ == "__main__":
    main()

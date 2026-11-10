"""
FrameViz 验证示例 - add_lines.indices 行为

运行前请确保：
先安装 FrameViz 运行环境和配套 Python SDK；fv.open() 会自动发现并启动。
需要浏览器时使用 fv.open(window_mode=1)。安装与故障排查见 docs/INSTALLATION.md。

使用方法：
python3 examples/python/01_basic_primitives/use_lines_indices.py

观察要点：
1) 左侧绿色图形仅显示 2 条线段（使用 indices）。
2) 右侧红色图形为连续折线（未提供 indices）。
"""

from __future__ import annotations

import time

import numpy as np
import frameviz as fv


def make_base_points() -> np.ndarray:
    return np.array(
        [
            [-1.0, 0.0, 0.5],
            [1.0, 0.0, 0.5],
            [1.0, 1.0, 0.5],
            [-1.0, 1.0, 0.5],
        ],
        dtype=np.float32,
    )


def offset_points(points: np.ndarray, offset_x: float) -> np.ndarray:
    offset = np.array([offset_x, 0.0, 0.0], dtype=np.float32)
    return points + offset


def main() -> None:
    print("=" * 60)
    print("FrameViz add_lines.indices Test")
    print("=" * 60)

    try:
        viz = fv.open()
    except Exception as exc:
        print(f"连接失败: {exc}")
        print("请确认已启动 FrameViz")
        return

    base = make_base_points()
    indices = np.array([[0, 1], [2, 3]], dtype=np.uint32)

    left_points = offset_points(base, -3.0)
    right_points = offset_points(base, 3.0)

    handle_left = viz.add_lines(left_points,
                                indices=indices,
                                width=2.0,
                                color="green")
    handle_right = viz.add_lines(right_points,
                                 indices=None,
                                 width=2.0,
                                 color="red")

    viz.add_text_2d(
        text="左: indices(2段)  右: 无indices(折线)",
        x=12,
        y=12,
        font_size=14,
        color="white",
    )

    print(f"左侧线段 handle={handle_left}, 右侧折线 handle={handle_right}")
    print("请观察左侧为两段线，右侧为连续折线。")

    try:
        input("观察完成后按 Enter 退出...")
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    time.sleep(0.2)


if __name__ == "__main__":
    main()

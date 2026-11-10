"""
FrameViz 验证示例 - 大 buffer 快照（二进制恢复）

运行前请确保（建议使用浏览器模式）：
先安装 FrameViz 运行环境和配套 Python SDK；无需额外 HTTP 服务器。
脚本使用 fv.open(window_mode=1) 打开运行环境自带的浏览器页面。

Tauri 模式也可运行，但需要能刷新 WebView：
FRAMEVIZ_TAURI_DEVTOOLS=1 pnpm -C packages/frameviz-host-tauri tauri:dev

使用方法：
python3 examples/python/01_basic_primitives/use_snapshot_large_buffer.py

观察要点：
1) 初次渲染能看到大点云。
2) 刷新浏览器页面后，控制台应看到：
   - "[FrameViz] Prepared buffer ... for binary restore"
   - "[FrameViz] Stored buffer ... bytes=..."
3) 刷新后点云仍能显示（说明快照的大 buffer 通过二进制恢复成功）。
"""

from __future__ import annotations

import time

import numpy as np
import frameviz as fv


def make_points(count: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    points = rng.standard_normal((count, 3)).astype(np.float32)
    points[:, 2] *= 0.2
    return points


def make_colors(count: int, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random((count, 3)).astype(np.float32)


def main() -> None:
    print("=" * 60)
    print("FrameViz Snapshot Large Buffer Test")
    print("=" * 60)

    try:
        viz = fv.open()
    except Exception as exc:
        print(f"连接失败: {exc}")
        print("请确认已启动 FrameViz")
        return

    point_count = 300_000
    positions = make_points(point_count)
    colors = make_colors(point_count)

    handle = viz.add_points(positions, colors=colors, size=2.0)
    viz.add_text_2d(
        text="大点云快照测试：请刷新浏览器页面",
        x=12,
        y=12,
        font_size=14,
        color="white",
    )

    print(f"已添加点云 handle={handle}, 点数={point_count}")
    print("请刷新浏览器页面，观察控制台日志与点云是否恢复。")

    try:
        input("观察完成后按 Enter 退出...")
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    time.sleep(0.2)


if __name__ == "__main__":
    main()

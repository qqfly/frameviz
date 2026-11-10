"""
FrameViz 验证示例 - 资源释放验证 (手动观察)

运行前请确保：
先安装 FrameViz 运行环境和配套 Python SDK；fv.open() 会自动发现并启动。
需要浏览器时使用 fv.open(window_mode=1)。安装与故障排查见 docs/INSTALLATION.md。

Tauri 模式可设置 DevTools 便于查看内存：
FRAMEVIZ_TAURI_DEVTOOLS=1 pnpm -C packages/frameviz-host-tauri tauri:dev

使用方法：
python3 examples/python/01_basic_primitives/use_resource_cleanup.py

观察要点：
1) 打开浏览器控制台，执行：
   __FRAMEVIZ_CORE__.getSceneManager().renderer.info.memory
   记录基线值 (geometries/textures)。
2) 脚本循环创建/清理后再次执行上述命令。
3) geometries/textures 应回落到接近基线（允许少量波动）。
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
    print("FrameViz Resource Cleanup Check")
    print("=" * 60)

    try:
        viz = fv.open()
    except Exception as exc:
        print(f"连接失败: {exc}")
        print("请确认已启动 FrameViz")
        return

    point_count = 50_000
    positions = make_points(point_count)
    colors = make_colors(point_count)

    viz.add_text_2d(
        text="资源释放验证：请在控制台观察 renderer.info.memory",
        x=12,
        y=12,
        font_size=14,
        color="white",
    )

    print("开始循环创建/清理对象...")
    for i in range(5):
        print(f"  [Cycle {i + 1}/5] add -> remove_objects")
        handles = []
        handles.append(viz.add_box(size=[1, 1, 1], pos=[0, 0, 0.5], color="red"))
        handles.append(viz.add_sphere(radius=0.5, pos=[2, 0, 0.5], color="blue"))
        handles.append(viz.add_points(positions, colors=colors, size=2.0))
        time.sleep(0.5)
        viz.remove_objects(handles)
        time.sleep(0.5)

    print("循环完成。请在控制台对比 renderer.info.memory 是否回落。")
    try:
        input("观察完成后按 Enter 清空场景+Overlay...")
    except (KeyboardInterrupt, EOFError):
        pass

    viz.clear()
    print("已清空场景与 Overlay。")
    try:
        input("按 Enter 退出...")
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    time.sleep(0.2)


if __name__ == "__main__":
    main()

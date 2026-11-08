#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def _bootstrap_repo_python_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    python_pkg = repo_root / "packages" / "frameviz-py"
    if str(python_pkg) not in sys.path:
        sys.path.insert(0, str(python_pkg))
    return repo_root


REPO_ROOT = _bootstrap_repo_python_path()


def _build_point_cloud(np: Any) -> tuple[Any, Any]:
    grid = np.linspace(-0.35, 0.35, 41, dtype=np.float32)
    uu, vv = np.meshgrid(grid, grid, indexing="xy")

    shell_faces = [
        np.stack([np.full_like(uu, -0.35), uu, vv], axis=-1),
        np.stack([np.full_like(uu, 0.35), uu, vv], axis=-1),
        np.stack([uu, np.full_like(uu, -0.35), vv], axis=-1),
        np.stack([uu, np.full_like(uu, 0.35), vv], axis=-1),
        np.stack([uu, vv, np.full_like(uu, -0.35)], axis=-1),
        np.stack([uu, vv, np.full_like(uu, 0.35)], axis=-1),
    ]
    shell = np.concatenate([face.reshape(-1, 3) for face in shell_faces], axis=0)

    rng = np.random.default_rng(51)
    close_cluster = rng.normal(
        loc=np.array([0.12, -0.02, 0.04], dtype=np.float32),
        scale=np.array([0.03, 0.025, 0.02], dtype=np.float32),
        size=(18000, 3),
    ).astype(np.float32)

    line_t = np.linspace(-0.3, 0.3, 4000, dtype=np.float32)
    center_line = np.stack([line_t, line_t * 0.25, line_t * 0.1], axis=1)

    positions = np.concatenate([shell, close_cluster, center_line], axis=0).astype(np.float32)

    colors = np.empty((positions.shape[0], 3), dtype=np.float32)
    shell_end = shell.shape[0]
    cluster_end = shell_end + close_cluster.shape[0]
    colors[:shell_end] = np.array([0.35, 0.82, 1.0], dtype=np.float32)
    colors[shell_end:cluster_end] = np.array([1.0, 0.68, 0.18], dtype=np.float32)
    colors[cluster_end:] = np.array([1.0, 0.2, 0.2], dtype=np.float32)
    return positions, colors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "验证 issue #51: 相机贴近点云时是否仍会出现明显前裁剪，"
            "以及近距离缩放是否仍会一下穿过点云。"
        )
    )
    parser.add_argument("--url", default=None, help="FrameViz WebSocket URL，默认自动发现")
    parser.add_argument("--timeout", type=float, default=10.0, help="open/connect 超时（秒）")
    parser.add_argument("--width", type=int, default=1400, help="窗口宽度，默认 1400")
    parser.add_argument("--height", type=int, default=900, help="窗口高度，默认 900")
    parser.add_argument(
        "--window-mode",
        type=int,
        default=2,
        choices=(0, 1, 2),
        help="FrameViz window_mode，默认 2（优先 Tauri，回退浏览器）",
    )
    parser.add_argument("--point-size", type=float, default=3.0, help="点大小，默认 3.0")
    parser.add_argument(
        "--zoom-sensitivity",
        type=float,
        default=1.0,
        help="缩放灵敏度，默认 1.0",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="输入结果后不自动关闭窗口，方便继续观察",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        import numpy as np
        import frameviz as fv
    except ImportError as exc:
        raise SystemExit(
            "缺少脚本依赖。\n"
            "脚本会优先从当前仓库加载 packages/frameviz-py；如果仍然失败，请先安装依赖，例如：\n"
            f"python3 -m pip install -e {REPO_ROOT / 'packages' / 'frameviz-py'}"
        ) from exc

    positions, colors = _build_point_cloud(np)

    viz = fv.open(
        url=args.url,
        title="Issue #51 verifier",
        width=args.width,
        height=args.height,
        timeout=args.timeout,
        window_mode=args.window_mode,
    )

    try:
        viz.set_view_config(
            show_grid=False,
            show_ground=False,
            show_axes=True,
            background=[0.04, 0.05, 0.08],
        )
        viz.set_camera_controls(
            zoom_to_cursor=False,
            zoom_sensitivity=args.zoom_sensitivity,
        )
        viz.add_axes(length=0.18)
        viz.add_points(positions, colors=colors, size=args.point_size)
        viz.set_camera_pose(
            eye=[0.95, -0.82, 0.52],
            target=[0.0, 0.0, 0.02],
            up=[0.0, 0.0, 1.0],
        )

        print("Issue #51 验证场景已打开。")
        print(f"点数: {positions.shape[0]}")
        print()
        print("操作步骤:")
        print("1. 用滚轮持续放大，尽量贴近橙色点簇和蓝色外壳。")
        print("2. 观察近距离时点云是否仍然大面积被前裁剪。")
        print("3. 如果偶尔穿过点云，反向滚轮时观察是否能很快恢复。")
        print()
        print("通过标准:")
        print("- 放大到局部时不会一下子跨很远穿过点云")
        print("- 相机贴近点云时仍能看到足够近的点，而不是整片被裁掉")
        print("- 反向滚轮恢复不需要滚很久")
        print()

        answer = input("观察完成后，输入 y 表示通过，其他任意键表示失败: ").strip().lower()
        passed = answer in {"y", "yes"}

        if passed:
            print("PASS: 手工观察结果符合 issue #51 的修复预期。")
            return 0

        print("FAIL: 仍观察到明显前裁剪或近距离缩放跳变。")
        return 1
    finally:
        if not args.keep_open:
            viz.close()


if __name__ == "__main__":
    raise SystemExit(main())

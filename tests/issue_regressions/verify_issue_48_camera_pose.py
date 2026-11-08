#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


def _bootstrap_repo_python_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    python_pkg = repo_root / "packages" / "frameviz-py"
    if str(python_pkg) not in sys.path:
        sys.path.insert(0, str(python_pkg))
    return repo_root


REPO_ROOT = _bootstrap_repo_python_path()


Pose = Dict[str, List[float]]


def _format_pose(pose: Pose) -> str:
    return json.dumps(pose, ensure_ascii=False, indent=2)


def _pose_changed(before: Pose, after: Pose, tolerance: float) -> bool:
    for key in ("eye", "target", "up"):
        lhs = before.get(key, [])
        rhs = after.get(key, [])
        if len(lhs) != len(rhs):
            return True
        for a, b in zip(lhs, rhs):
            if abs(float(a) - float(b)) > tolerance:
                return True
    return False


def _pick_view_id(fv_module: Any, view_id: str | None, url: str | None, timeout: float) -> str:
    views = fv_module.list_views(url=url, timeout=timeout)
    bound_views = [item for item in views if item.get("scene_id")]

    if view_id:
        for item in bound_views:
            if item.get("view_id") == view_id:
                return view_id
        raise SystemExit(
            f"没有找到可连接的 view_id={view_id}。\n"
            f"当前已绑定 scene 的 views: {json.dumps(bound_views, ensure_ascii=False)}"
        )

    if len(bound_views) == 1:
        return str(bound_views[0]["view_id"])

    raise SystemExit(
        "无法自动选择 view_id。\n"
        "请先启动 simple_slider，再显式传入 --view-id。\n"
        f"当前已绑定 scene 的 views: {json.dumps(bound_views, ensure_ascii=False)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "验证 issue #48: 在 simple_slider 软件界面中手动操作相机后，"
            "Python SDK 的 get_camera_pose() 是否返回实时变化结果。"
        )
    )
    parser.add_argument("--url", default=None, help="FrameViz WebSocket URL，默认自动发现")
    parser.add_argument("--view-id", default=None, help="simple_slider 对应的 view_id")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="连接和命令超时时间（秒），默认 10",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="按下回车后的轮询间隔（秒），默认 0.5",
    )
    parser.add_argument(
        "--observe-seconds",
        type=float,
        default=6.0,
        help="按下回车后最多观察多少秒等待相机位姿变化，默认 6",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-4,
        help="判断位姿变化的数值阈值，默认 1e-4",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        import frameviz as fv
    except ImportError as exc:
        raise SystemExit(
            "无法导入 frameviz。\n"
            "脚本会优先从当前仓库加载 packages/frameviz-py；如果仍然失败，请先安装依赖，例如：\n"
            f"python3 -m pip install -e {REPO_ROOT / 'packages' / 'frameviz-py'}"
        ) from exc

    print("Issue #48 验证脚本")
    print("前置条件:")
    print("1. 已启动 simple_slider 界面")
    print("2. 已启动 simple_slider Python backend")
    print("3. 当前界面已经出现 3D viewer")
    print()

    target_view_id = _pick_view_id(fv, args.view_id, args.url, args.timeout)
    print(f"连接目标 view_id={target_view_id}")

    viz = fv.connect(url=args.url, view_id=target_view_id, timeout=args.timeout)
    try:
        before = viz.get_camera_pose()
        print("初始 camera pose:")
        print(_format_pose(before))
        print()
        input(
            "请切回 simple_slider 界面，用鼠标旋转/平移/缩放相机，然后回到这里按 Enter 开始验证..."
        )

        deadline = time.time() + args.observe_seconds
        latest = before
        while time.time() < deadline:
            latest = viz.get_camera_pose()
            print(f"[poll] {json.dumps(latest, ensure_ascii=False)}")
            if _pose_changed(before, latest, args.tolerance):
                print()
                print("PASS: get_camera_pose() 已返回新的 viewer 实时位姿。")
                print("变化前:")
                print(_format_pose(before))
                print("变化后:")
                print(_format_pose(latest))
                return 0
            time.sleep(args.poll_interval)

        print()
        print("FAIL: 在观察窗口内 get_camera_pose() 没有检测到变化。")
        print("初始位姿:")
        print(_format_pose(before))
        print("最后一次轮询位姿:")
        print(_format_pose(latest))
        print("如果你刚才已经明显移动过相机，这说明 issue #48 仍然存在。")
        return 1
    finally:
        viz.close()


if __name__ == "__main__":
    raise SystemExit(main())

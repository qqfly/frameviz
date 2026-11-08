#!/usr/bin/env python3
"""
FrameViz 交互式测试框架

使用方法:
    1. 启动服务:
       - Tauri 模式（推荐）: pnpm -C packages/frameviz-host-tauri tauri:dev
       - 浏览器模式（可选）:
         + pnpm -C packages/frameviz-host-tauri tauri:dev
         + node packages/frameviz-web-viewer/serve.mjs
    2. 浏览器打开（可选）:
       http://127.0.0.1:8080/packages/frameviz-web-viewer/
    3. 运行测试: python tests/interactive_test.py

测试流程:
    - 每个测试会执行相应代码
    - 显示预期结果
    - 用户确认 Y/N 或输入备注
    - 最终生成测试报告
"""

import sys
import os
import json
import time
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Callable, Any
from enum import Enum

# Add project path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'frameviz-py'))

from frameviz.client import PROTOCOL_VERSION

try:
    import numpy as np
except ImportError:
    print("[ERROR] numpy not installed. Run: pip install numpy")
    sys.exit(1)


class RunStatus(Enum):
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    SKIPPED = "⏭️ SKIPPED"
    BLOCKED = "🚫 BLOCKED"


@dataclass
class RunResult:
    test_id: str
    name: str
    category: str
    status: RunStatus
    notes: str = ""
    duration_ms: float = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        d = asdict(self)
        d['status'] = self.status.value
        return d


@dataclass
class RunReport:
    title: str = "FrameViz Test Report"
    version: str = PROTOCOL_VERSION
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str = ""
    results: List[RunResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == RunStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == RunStatus.FAILED)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == RunStatus.SKIPPED)

    def add_result(self, result: RunResult):
        self.results.append(result)

    def save_json(self, filepath: str):
        self.end_time = datetime.now().isoformat()
        data = {
            'title': self.title,
            'version': self.version,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'summary': {
                'total':
                self.total,
                'passed':
                self.passed,
                'failed':
                self.failed,
                'skipped':
                self.skipped,
                'pass_rate':
                f"{self.passed/self.total*100:.1f}%"
                if self.total > 0 else "N/A"
            },
            'results': [r.to_dict() for r in self.results]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n📄 测试报告已保存: {filepath}")

    def save_markdown(self, filepath: str):
        self.end_time = datetime.now().isoformat()
        lines = [
            f"# {self.title}",
            "",
            f"- **协议版本**: {self.version}",
            f"- **开始时间**: {self.start_time}",
            f"- **结束时间**: {self.end_time}",
            "",
            "## 测试摘要",
            "",
            f"| 指标 | 数量 |",
            f"|------|------|",
            f"| 总计 | {self.total} |",
            f"| 通过 | {self.passed} |",
            f"| 失败 | {self.failed} |",
            f"| 跳过 | {self.skipped} |",
            f"| 通过率 | {self.passed/self.total*100:.1f}% |"
            if self.total > 0 else "| 通过率 | N/A |",
            "",
            "## 详细结果",
            "",
            "| ID | 测试名称 | 分类 | 状态 | 备注 |",
            "|-----|----------|------|------|------|",
        ]

        for r in self.results:
            notes = r.notes.replace('\n', ' ').replace('|', '\\|')[:50]
            lines.append(
                f"| {r.test_id} | {r.name} | {r.category} | {r.status.value} | {notes} |"
            )

        lines.append("")
        lines.append("---")
        lines.append(f"*Generated at {datetime.now().isoformat()}*")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"📄 Markdown 报告已保存: {filepath}")


class InteractiveTestRunner:
    """交互式测试运行器"""

    def __init__(self):
        self.report = RunReport()
        self.viz = None
        self.current_category = ""

    def connect(self) -> bool:
        """连接到 FrameViz 服务"""
        try:
            import frameviz as fv
            print("\n🔌 正在连接 FrameViz...")
            self.viz = fv.open()
            print("✅ 连接成功!")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print("\n请确保:")
            print(
                "  1. FrameViz 已启动: pnpm -C packages/frameviz-host-tauri tauri:dev"
            )
            print("  2. 浏览器模式（可选）: node packages/frameviz-web-viewer/serve.mjs")
            print("     (或 python3 -m http.server 8080)")
            print(
                "  3. 浏览器打开: http://127.0.0.1:8080/packages/frameviz-web-viewer/"
            )
            return False

    def disconnect(self):
        """断开连接"""
        if self.viz:
            self.viz.close()
            self.viz = None

    def clear_scene(self):
        """清空场景"""
        if self.viz:
            self.viz.clear_scene()

    def ask_result(self, test_id: str, name: str, expected: str) -> RunResult:
        """询问用户测试结果"""
        print(f"\n{'='*60}")
        print(f"📋 测试 {test_id}: {name}")
        print(f"{'='*60}")
        print(f"\n📝 预期结果:")
        for line in expected.strip().split('\n'):
            print(f"   {line}")
        print()

        start_time = time.time()

        while True:
            response = input("👀 请确认测试结果 [Y=通过/N=失败/S=跳过/其他=备注]: ").strip()

            if response.upper() == 'Y':
                status = RunStatus.PASSED
                notes = ""
                break
            elif response.upper() == 'N':
                status = RunStatus.FAILED
                notes = input("   请输入失败原因: ").strip()
                break
            elif response.upper() == 'S':
                status = RunStatus.SKIPPED
                notes = input("   请输入跳过原因: ").strip()
                break
            elif response:
                # 直接作为备注，再次确认
                confirm = input(
                    f"   备注: '{response}', 测试通过? [Y/N]: ").strip().upper()
                if confirm == 'Y':
                    status = RunStatus.PASSED
                    notes = response
                    break
                else:
                    status = RunStatus.FAILED
                    notes = response
                    break

        duration = (time.time() - start_time) * 1000

        result = RunResult(test_id=test_id,
                           name=name,
                           category=self.current_category,
                           status=status,
                           notes=notes,
                           duration_ms=duration)

        self.report.add_result(result)
        print(f"\n   结果: {status.value}")
        return result

    def run_test(self, test_id: str, name: str, code_fn: Callable,
                 expected: str) -> RunResult:
        """运行单个测试"""
        print(f"\n🔧 执行测试代码...")
        try:
            code_fn()
            time.sleep(0.3)  # 等待渲染
        except Exception as e:
            print(f"❌ 代码执行错误: {e}")
            result = RunResult(test_id=test_id,
                               name=name,
                               category=self.current_category,
                               status=RunStatus.BLOCKED,
                               notes=f"执行错误: {e}")
            self.report.add_result(result)
            return result

        return self.ask_result(test_id, name, expected)

    def section(self, category: str):
        """开始新的测试分类"""
        self.current_category = category
        print(f"\n{'#'*60}")
        print(f"# {category}")
        print(f"{'#'*60}")

    def pause(self, message: str = "按 Enter 继续..."):
        """暂停等待用户"""
        input(f"\n⏸️  {message}")

    def print_summary(self):
        """打印测试摘要"""
        print(f"\n{'='*60}")
        print("📊 测试摘要")
        print(f"{'='*60}")
        print(f"   总计: {self.report.total}")
        print(f"   通过: {self.report.passed} ✅")
        print(f"   失败: {self.report.failed} ❌")
        print(f"   跳过: {self.report.skipped} ⏭️")
        if self.report.total > 0:
            print(f"   通过率: {self.report.passed/self.report.total*100:.1f}%")


def run_full_test():
    """运行完整测试套件"""
    runner = InteractiveTestRunner()

    print("""
╔═══════════════════════════════════════════════════════════════╗
║           FrameViz 交互式测试框架 v{PROTOCOL_VERSION}                        ║
╠═══════════════════════════════════════════════════════════════╣
║  本测试将引导您逐步验证 FrameViz 的各项功能。                   ║
║  每个测试执行后，请在浏览器中观察结果并确认。                   ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # 连接
    if not runner.connect():
        return

    try:
        # ========== 0. 环境与连接 ==========
        runner.section("0. 环境与连接")

        runner.run_test("TC-ENV-001", "窗口与视图状态", lambda: None,
                        "窗口标题/状态栏显示 view_id → scene_id，状态为绿色已连接")

        def test_list_state():
            result = runner.viz.send_command("list_scenes", {})
            print(f"   list_scenes: {result}")
            result = runner.viz.send_command("list_views", {})
            print(f"   list_views: {result}")

        runner.run_test("TC-ENV-002", "list_scenes / list_views",
                        test_list_state, "终端输出包含当前 view/scene 信息，且不为空")

        # ========== 1. 图元渲染测试 ==========
        runner.section("1. 图元渲染测试")
        runner.clear_scene()

        # TC-PRIM-001: Box
        runner.run_test(
            "TC-PRIM-001", "添加立方体 (Box)", lambda: runner.viz.add_box(
                size=[1, 1, 1], pos=[0, 0, 0.5], color=[0.9, 0.2, 0.2]),
            "浏览器中显示一个红色立方体，位于原点上方 (0, 0, 0.5)")

        # TC-PRIM-002: Sphere
        runner.run_test(
            "TC-PRIM-002", "添加球体 (Sphere)", lambda: runner.viz.add_sphere(
                radius=0.5, pos=[2, 0, 0.5], color=[0.2, 0.9, 0.2]),
            "浏览器中显示一个绿色球体，位于 (2, 0, 0.5)")

        # TC-PRIM-003: Cylinder
        runner.run_test(
            "TC-PRIM-003", "添加圆柱体 (Cylinder)", lambda: runner.viz.add_cylinder(
                radius=0.3, height=1.0, pos=[-2, 0, 0.5], color=[0.2, 0.2, 0.9]
            ), "浏览器中显示一个蓝色圆柱体，位于 (-2, 0, 0.5)")

        # TC-PRIM-004: Axes
        runner.run_test("TC-PRIM-004", "添加坐标轴 (Axes)",
                        lambda: runner.viz.add_axes(length=1.5),
                        "浏览器中显示 RGB 坐标轴 (红=X, 绿=Y, 蓝=Z)")

        # TC-PRIM-005: Arrow
        runner.run_test(
            "TC-PRIM-005", "添加箭头 (Arrow)", lambda: runner.viz.add_arrow(
                start=[0, 2, 0], end=[0, 2, 1.5], color=[1, 1, 0]),
            "浏览器中显示一个黄色箭头，从 (0,2,0) 指向 (0,2,1.5)")

        # TC-PRIM-006: Plane
        runner.run_test(
            "TC-PRIM-006", "添加平面 (Plane)", lambda: runner.viz.add_plane(
                width=4, height=4, pos=[0, 0, 0], color=[0.3, 0.3, 0.3, 0.5]),
            "浏览器中显示一个灰色半透明平面作为地面")

        runner.run_test(
            "TC-PRIM-007", "添加圆锥 (Cone)", lambda: runner.viz.add_cone(
                radius=0.4, height=1.0, pos=[0, -2, 0.5], color=[0.9, 0.6, 0.2]
            ), "浏览器中显示一个橙色圆锥，位于 (0, -2, 0.5)")

        # ========== 2. 属性修改测试 ==========
        runner.section("2. 属性修改测试")
        runner.clear_scene()

        # 创建测试用物体
        box_handle = runner.viz.add_box(size=[1, 1, 1],
                                        pos=[0, 0, 0.5],
                                        color=[0.5, 0.5, 0.5])
        print(f"   创建测试立方体: {box_handle}")

        # TC-PROP-001: set_color
        def test_set_color():
            runner.viz.set_color(box_handle, [1, 0, 0, 1])

        runner.run_test("TC-PROP-001", "修改颜色 (set_color)", test_set_color,
                        "立方体颜色从灰色变为红色")

        # TC-PROP-002: set_transform
        def test_set_transform():
            runner.viz.set_transform(box_handle, pos=[2, 0, 0.5])

        runner.run_test("TC-PROP-002", "修改位置 (set_transform)",
                        test_set_transform, "立方体从原点移动到 (2, 0, 0.5)")

        # TC-PROP-003: set_visible
        def test_set_visible():
            runner.viz.set_visible(box_handle, False)
            time.sleep(0.5)
            runner.viz.set_visible(box_handle, True)

        runner.run_test("TC-PROP-003", "显示/隐藏 (set_visible)", test_set_visible,
                        "立方体先消失，然后重新出现")

        # ========== 3. 线条与网格测试 ==========
        runner.section("3. 线条与网格测试")
        runner.clear_scene()
        runner.viz.add_axes(length=1.0)

        def test_polyline():
            positions = np.array([
                [-1.0, -1.0, 0.0],
                [1.0, -1.0, 0.0],
                [1.0, 1.0, 0.0],
                [-1.0, 1.0, 0.0],
                [-1.0, -1.0, 0.0],
            ],
                                 dtype=np.float32)
            runner.viz.add_lines(positions, color=[0.1, 0.8, 0.9], width=2.0)

        runner.run_test("TC-LINE-001", "折线 (Polyline)", test_polyline,
                        "显示一条青色方形折线，位于 XY 平面")

        def test_indexed_lines():
            positions = np.array([
                [-1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, -1.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
                                 dtype=np.float32)
            indices = np.array([
                [0, 1],
                [2, 3],
            ], dtype=np.uint32)
            runner.viz.add_lines(positions,
                                 indices=indices,
                                 color=[1.0, 0.6, 0.2],
                                 width=3.0)

        runner.run_test("TC-LINE-002", "索引线段 (Indexed Lines)",
                        test_indexed_lines, "显示两条橙色线段：水平 + 垂直交叉")

        def test_mesh():
            vertices = np.array([
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
                                dtype=np.float32)
            faces = np.array([[0, 1, 2]], dtype=np.uint32)
            colors = np.array([
                [255, 0, 0],
                [255, 0, 0],
                [255, 0, 0],
            ],
                              dtype=np.uint8)
            runner.viz.add_mesh(vertices, faces, colors=colors)

        runner.run_test("TC-MESH-001", "三角网格 (Mesh)", test_mesh, "显示一个红色三角面")

        # ========== 4. 点云测试 ==========
        runner.section("4. 点云测试")
        runner.clear_scene()
        runner.viz.add_axes(length=1.0)

        # TC-PTS-001: 基础点云
        def test_basic_points():
            points = np.random.rand(1000, 3).astype(
                np.float32) * 2 - 1  # [-1, 1]
            colors = np.full((1000, 3), [51, 204, 51], dtype=np.uint8)  # 绿色
            runner.viz.add_points(points, size=3.0, colors=colors)

        runner.run_test("TC-PTS-001", "基础点云 (1000 点)", test_basic_points,
                        "显示 1000 个绿色点，分布在 [-1, 1] 立方体范围内")

        # TC-PTS-002: 带颜色点云
        runner.clear_scene()
        runner.viz.add_axes(length=1.0)

        def test_colored_points():
            n = 5000
            points = np.random.rand(n, 3).astype(np.float32) * 2 - 1
            # 颜色按 Z 高度渐变 (红->绿->蓝)
            colors = np.zeros((n, 3), dtype=np.uint8)
            z_norm = (points[:, 2] + 1) / 2  # [0, 1]
            colors[:, 0] = ((1 - z_norm) * 255).astype(np.uint8)  # R
            colors[:, 2] = (z_norm * 255).astype(np.uint8)  # B
            runner.viz.add_points(points, colors=colors, size=2.0)

        runner.run_test("TC-PTS-002", "带颜色点云 (5000 点)", test_colored_points,
                        "显示 5000 个点，颜色按 Z 高度从红色渐变到蓝色")

        # ========== 5. 文字与覆盖层测试 ==========
        runner.section("5. 文字与覆盖层测试")
        runner.clear_scene()
        runner.viz.add_axes(length=1.0)
        runner.viz.add_box(size=[0.6, 0.6, 0.6],
                           pos=[0, 0, 0.3],
                           color=[0.2, 0.8, 0.2])

        text2d_handle = {"value": ""}
        text3d_handle = {"value": ""}

        def test_add_text_2d():
            text2d_handle["value"] = runner.viz.add_text_2d(
                text="2D 标签：左上角",
                x=12,
                y=12,
                font_size=16,
                color=[1.0, 1.0, 1.0],
            )

        runner.run_test("TC-TEXT-001", "添加 2D 文本", test_add_text_2d,
                        "左上角出现白色 2D 文本")

        def test_update_text_2d():
            runner.viz.update_text_2d(
                text2d_handle["value"],
                text="2D 标签：已更新",
                x=120,
                y=40,
                font_size=18,
                color=[1.0, 0.8, 0.2],
            )

        runner.run_test("TC-TEXT-002", "更新 2D 文本", test_update_text_2d,
                        "2D 文本移动到右侧并变为黄色")

        def test_remove_text_2d():
            runner.viz.remove(text2d_handle["value"])

        runner.run_test("TC-TEXT-003", "移除 2D 文本", test_remove_text_2d,
                        "2D 文本消失")

        def test_add_text_3d():
            text3d_handle["value"] = runner.viz.add_text_3d(
                text="3D 标签",
                pos=[0.0, 0.0, 1.0],
                font_size=16,
                color=[0.2, 0.9, 0.9],
                background_color="rgba(0,0,0,0.5)",
            )

        runner.run_test("TC-TEXT-004", "添加 3D 文本", test_add_text_3d,
                        "物体上方出现蓝绿色 3D 标签")

        def test_update_text_3d():
            runner.viz.update_text_3d(
                text3d_handle["value"],
                text="3D 标签更新",
                pos=[0.5, 0.0, 1.2],
                color=[1.0, 0.4, 0.4],
                font_size=18,
            )

        runner.run_test("TC-TEXT-005", "更新 3D 文本", test_update_text_3d,
                        "3D 标签移动并变为红色")

        def test_remove_text_3d():
            runner.viz.remove(text3d_handle["value"])

        runner.run_test("TC-TEXT-006", "移除 3D 文本", test_remove_text_3d,
                        "3D 标签消失")

        # ========== 6. 相机控制测试 ==========
        runner.section("6. 相机控制测试")
        runner.clear_scene()
        runner.viz.add_axes(length=1.0)
        focus_box = runner.viz.add_box(size=[1, 1, 1],
                                       pos=[0, 0, 0.5],
                                       color=[0.9, 0.2, 0.2])
        runner.viz.add_box(size=[1, 1, 1],
                           pos=[4, 0, 0.5],
                           color=[0.2, 0.2, 0.9])

        # TC-CAM-001: 鼠标交互
        runner.run_test(
            "TC-CAM-001", "鼠标交互", lambda: None, """请在浏览器中测试:
- 左键拖拽: 旋转视角
- 右键拖拽: 平移视角
- 滚轮滚动: 缩放视角
- 默认: 缩放朝向目标点移动 (zoom_to_cursor 默认关闭)
- 可通过 set_camera_controls(zoom_to_cursor=True) 启用鼠标指向点缩放""")

        # TC-CAM-002: 键盘快捷键
        runner.run_test(
            "TC-CAM-002", "键盘快捷键", lambda: None, """请在浏览器中测试:
- Space: 重置到 Home 视角
- H: 显示/隐藏快捷键帮助
- W: 切换渲染模式 (solid/wireframe/points)
- Ctrl+0~6: 切换预设视角""")

        # TC-CAM-003: API 视角控制
        def test_set_view():
            runner.viz.send_command("set_view", {
                "view_id": runner.viz.view_id,
                "view": "front"
            })
            time.sleep(0.5)
            runner.viz.send_command("set_view", {
                "view_id": runner.viz.view_id,
                "view": "top"
            })
            time.sleep(0.5)
            runner.viz.send_command("set_view", {
                "view_id": runner.viz.view_id,
                "view": "home"
            })

        runner.run_test("TC-CAM-003", "API 视角切换 (set_view)", test_set_view,
                        "视角依次切换: 正面 -> 顶部 -> Home")

        # TC-CAM-004: API 相机参数
        def test_camera_controls():
            runner.viz.set_camera_controls(
                zoom_to_cursor=True,
                zoom_sensitivity=1.2,
                orbit_enabled=True,
                pan_enabled=True,
                zoom_enabled=True,
            )
            time.sleep(0.3)
            runner.viz.set_camera_controls(zoom_to_cursor=False)
            time.sleep(0.3)
            runner.viz.set_camera_controls(zoom_enabled=False)
            time.sleep(0.3)
            runner.viz.set_camera_controls(zoom_enabled=True,
                                           zoom_to_cursor=True)

        runner.run_test(
            "TC-CAM-004", "相机参数 (set_camera_controls)", test_camera_controls,
            """请在浏览器中测试:
- zoom_to_cursor=True 时，滚轮缩放鼠标指向点不移动
- zoom_to_cursor=False 时，缩放朝向目标点
- zoom_enabled=False 时滚轮无效""")

        # TC-CAM-005: fit_object
        def test_fit_object():
            runner.viz.reset_camera(mode="fit_object", fit_handle=focus_box)

        runner.run_test("TC-CAM-005", "重置相机 (fit_object)", test_fit_object,
                        "镜头应聚焦红色方块（远处蓝色方块可能不在视野内）")

        # ========== 7. 交互测试 ==========
        runner.section("7. 交互测试 (Picking & Gizmo)")
        runner.clear_scene()
        runner.viz.add_axes(length=1.0)
        box1 = runner.viz.add_box(size=[0.8, 0.8, 0.8],
                                  pos=[-1.5, 0, 0.4],
                                  color=[0.9, 0.2, 0.2])
        box2 = runner.viz.add_box(size=[0.8, 0.8, 0.8],
                                  pos=[0, 0, 0.4],
                                  color=[0.2, 0.9, 0.2])
        box3 = runner.viz.add_box(size=[0.8, 0.8, 0.8],
                                  pos=[1.5, 0, 0.4],
                                  color=[0.2, 0.2, 0.9])
        print(f"   创建三个立方体: {box1}, {box2}, {box3}")

        # 启用 pick 功能
        runner.viz.set_pick_config(enabled=True, mode='object', button=2)

        # TC-PICK-001: 拾取物体
        runner.run_test("TC-PICK-001", "拾取物体 (Picking)", lambda: None,
                        """请在浏览器中点击不同的立方体:
- 点击物体应显示黄色高亮边框
- 点击空白处应取消高亮""")

        # TC-GIZ-001: Gizmo 控制
        def test_gizmo():
            runner.viz.attach_gizmo(box2, mode="translate")

        runner.run_test("TC-GIZ-001", "Gizmo 平移模式", test_gizmo,
                        """绿色立方体上显示平移 Gizmo:
- 显示红/绿/蓝三个箭头
- 拖拽箭头可移动物体""")

        # TC-GIZ-002: Gizmo 模式切换
        def test_gizmo_modes():
            runner.viz.set_gizmo_mode("rotate")
            time.sleep(0.8)
            runner.viz.set_gizmo_mode("scale")
            time.sleep(0.8)
            runner.viz.set_gizmo_mode("translate")

        runner.run_test("TC-GIZ-002", "Gizmo 模式切换", test_gizmo_modes,
                        "Gizmo 依次切换: 旋转模式(圆环) -> 缩放模式 -> 平移模式(箭头)")

        # TC-GIZ-003: Gizmo 分离
        def test_detach_gizmo():
            runner.viz.detach_gizmo()

        runner.run_test("TC-GIZ-003", "Gizmo 分离", test_detach_gizmo,
                        "Gizmo 从物体上消失")

        # ========== 8. 事件系统测试 ==========
        runner.section("8. 事件系统测试")

        picked_events = []
        transformed_events = []
        key_events = []

        def on_pick(evt):
            picked_events.append(evt)
            print(f"[picked] {evt}")

        def on_transform(evt):
            transformed_events.append(evt)
            print(f"[transformed] {evt}")

        def on_key(evt):
            key_events.append(evt)
            print(f"[key_down] {evt}")

        runner.viz.on_pick(on_pick)
        runner.viz.on_transform(on_transform)
        runner.viz.on("key_down", on_key)

        runner.run_test(
            "TC-EVT-001", "picked 事件", lambda: None, """请点击任意物体:
- 终端应输出 [picked] 事件
- 点击空白处会输出 hit_type=none""")

        def test_transform_event():
            runner.viz.attach_gizmo(box2, mode="translate")

        runner.run_test(
            "TC-EVT-002", "transformed 事件", test_transform_event,
            """拖拽 Gizmo 箭头:
- 终端应输出 [transformed] 事件
- handle 与当前物体一致""")

        runner.run_test(
            "TC-EVT-003", "key_down 事件", lambda: None, """在浏览器按下任意按键:  
- 终端应输出 [key_down] 事件
- 注意: W/H/Space/Ctrl+数字 被内置快捷键占用
- 推荐测试: A/B/C/D/E 等未占用按键""")

        # ========== 9. 渲染模式测试 ==========
        runner.section("9. 渲染模式测试")
        runner.clear_scene()
        runner.viz.add_axes(length=1.0)
        runner.viz.add_box(size=[1, 1, 1],
                           pos=[0, 0, 0.5],
                           color=[0.9, 0.2, 0.2])
        runner.viz.add_sphere(radius=0.5,
                              pos=[2, 0, 0.5],
                              color=[0.2, 0.9, 0.2])

        def test_wireframe():
            runner.viz.send_command("set_render_mode", {
                "view_id": runner.viz.view_id,
                "mode": "wireframe"
            })

        runner.run_test("TC-RENDER-001", "线框模式 (Wireframe)", test_wireframe,
                        "所有物体显示为线框，无填充")

        def test_points_mode():
            runner.viz.send_command("set_render_mode", {
                "view_id": runner.viz.view_id,
                "mode": "points"
            })

        runner.run_test("TC-RENDER-002", "点云模式 (Points)", test_points_mode,
                        "所有物体只显示顶点")

        def test_solid():
            runner.viz.send_command("set_render_mode", {
                "view_id": runner.viz.view_id,
                "mode": "solid"
            })

        runner.run_test("TC-RENDER-003", "实体模式 (Solid)", test_solid,
                        "所有物体恢复实体填充显示")

        # ========== 10. 日志与协议测试 ==========
        runner.section("10. 日志与协议测试")
        runner.clear_scene()

        log_events = []

        def on_log(evt):
            log_events.append(evt)
            print(f"[log] {evt}")

        runner.viz.on_log(on_log)

        def test_log_event():
            runner.viz.set_log_config(min_level="debug",
                                      sinks=[{
                                          "type": "event",
                                          "enabled": True
                                      }])
            runner.viz.add_box(size=[1, 1, 1],
                               pos=[0, 0, 0.5],
                               color=[0.3, 0.9, 0.9])
            time.sleep(0.3)
            print(f"   收到 log 事件数量: {len(log_events)}")

        runner.run_test("TC-LOG-001", "log 事件订阅", test_log_event,
                        "终端输出 [log] 事件，数量 > 0")

        def test_read_logs():
            next_seq, entries = runner.viz.read_logs(limit=5)
            print(
                f"   read_logs 返回: next_after_seq={next_seq}, entries={len(entries)}"
            )
            for entry in entries[:3]:
                print(f"   - {entry}")

        runner.run_test("TC-LOG-002", "read_logs 拉取", test_read_logs,
                        "终端输出 entries 列表，包含 level/msg/ts_ms 字段")

        # ========== 11. 快照与二进制回归 ==========
        runner.section("11. 快照与二进制回归")
        runner.clear_scene()

        def test_snapshot_binary():
            n = 200000
            points = (np.random.rand(n, 3).astype(np.float32) - 0.5) * 4
            colors = np.random.randint(0, 255, (n, 3), dtype=np.uint8)
            runner.viz.add_points(points, colors=colors, size=2.0)
            runner.viz.add_text_2d(
                text="快照回归：请刷新页面后确认点云仍存在",
                x=12,
                y=12,
                font_size=14,
                color=[1.0, 1.0, 1.0],
            )

        runner.run_test("TC-SNAP-001", "大 buffer 快照恢复", test_snapshot_binary,
                        """请刷新浏览器页面:
- 控制台看到二进制恢复日志
- 点云仍完整显示""")

        # ========== 12. 资源释放验证 ==========
        runner.section("12. 资源释放验证")
        runner.clear_scene()

        def test_resource_cleanup():
            points = np.random.rand(50000, 3).astype(np.float32)
            colors = np.random.randint(0, 255, (50000, 3), dtype=np.uint8)
            runner.viz.add_points(points, colors=colors, size=2.0)
            runner.viz.add_mesh(
                np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32),
                np.array([[0, 1, 2]], dtype=np.uint32),
            )
            runner.viz.add_text_2d(text="资源释放检查：请打开控制台",
                                   x=12,
                                   y=12,
                                   font_size=14)
            time.sleep(0.5)
            runner.viz.clear_scene()

        runner.run_test(
            "TC-MEM-001", "清场释放", test_resource_cleanup, """清场后请在浏览器控制台执行:  
__FRAMEVIZ_CORE__.getSceneManager().renderer.info.memory

验证: geometries/textures 应回落到基线附近
注意: 这是一个手动验证项，无法在 Python 终端自动检查""")

        # ========== 13. 多视图/共享场景 (可选) ==========
        runner.section("13. 多视图/共享场景 (可选)")
        do_multi = input("是否执行多视图测试? [Y/N]: ").strip().upper()
        if do_multi == "Y":
            import frameviz as fv
            runner.clear_scene()
            runner.viz.add_axes(length=1.0)
            runner.viz.add_box(size=[1, 1, 1],
                               pos=[0, 0, 0.5],
                               color=[0.9, 0.2, 0.2])
            shared_viz = fv.open(share_scene=runner.viz.scene_id)

            def test_multi_view():
                runner.viz.send_command("set_view", {
                    "view_id": runner.viz.view_id,
                    "view": "front"
                })
                time.sleep(0.5)
                runner.viz.send_command("set_view", {
                    "view_id": runner.viz.view_id,
                    "view": "top"
                })

            runner.run_test("TC-VIEW-001", "共享场景多视图", test_multi_view,
                            "两个窗口显示同一场景，但视角可独立切换")
            shared_viz.close()

        # ========== 测试完成 ==========
        runner.print_summary()

        # 保存报告
        report_dir = os.path.join(os.path.dirname(__file__), '..',
                                  'test_reports')
        os.makedirs(report_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = os.path.join(report_dir, f"test_report_{timestamp}.json")
        md_path = os.path.join(report_dir, f"test_report_{timestamp}.md")

        runner.report.save_json(json_path)
        runner.report.save_markdown(md_path)

    except KeyboardInterrupt:
        print("\n\n⚠️ 测试中断")
        runner.print_summary()
    finally:
        runner.disconnect()


def run_quick_test():
    """运行快速测试 (仅核心功能)"""
    runner = InteractiveTestRunner()

    print("""
╔═══════════════════════════════════════════════════════════════╗
║           FrameViz 快速测试 (核心功能)                          ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    if not runner.connect():
        return

    try:
        runner.section("快速测试")
        runner.clear_scene()

        # 添加所有基础图元
        runner.viz.add_axes(length=1.0)
        runner.viz.add_plane(width=4, height=4, color=[0.3, 0.3, 0.3, 0.5])
        runner.viz.add_box(size=[0.8, 0.8, 0.8],
                           pos=[-1.5, 0, 0.4],
                           color=[0.9, 0.2, 0.2])
        runner.viz.add_sphere(radius=0.4,
                              pos=[0, 0, 0.4],
                              color=[0.2, 0.9, 0.2])
        runner.viz.add_cylinder(radius=0.25,
                                height=0.8,
                                pos=[1.5, 0, 0.4],
                                color=[0.2, 0.2, 0.9])

        runner.run_test("TC-QUICK-001", "基础图元渲染", lambda: None, """浏览器中应显示:
- RGB 坐标轴
- 灰色地面
- 红色立方体、绿色球体、蓝色圆柱""")

        # 点云测试
        runner.clear_scene()
        runner.viz.add_axes(length=1.0)
        points = np.random.rand(3000, 3).astype(np.float32) * 2 - 1
        colors = np.full((3000, 3), [51, 204, 204], dtype=np.uint8)
        runner.viz.add_points(points, colors=colors, size=2.0)

        runner.run_test("TC-QUICK-002", "点云渲染", lambda: None,
                        "浏览器中显示 3000 个青色点")

        # 交互测试
        runner.clear_scene()
        runner.viz.add_axes(length=1.0)
        box = runner.viz.add_box(size=[1, 1, 1],
                                 pos=[0, 0, 0.5],
                                 color=[0.9, 0.5, 0.2])
        runner.viz.attach_gizmo(box)

        runner.run_test("TC-QUICK-003", "Gizmo 交互", lambda: None, """浏览器中:
- 橙色立方体上显示 Gizmo
- 可拖拽 Gizmo 移动物体""")

        runner.print_summary()

    finally:
        runner.disconnect()


def interactive_shell():
    """启动交互式 Shell"""
    import frameviz as fv

    print("""
╔═══════════════════════════════════════════════════════════════╗
║           FrameViz 交互式 Shell                                ║
╠═══════════════════════════════════════════════════════════════╣
║  可用对象:                                                     ║
║    viz  - FrameViz 连接对象                                    ║
║    np   - NumPy 模块                                           ║
║                                                                ║
║  示例命令:                                                     ║
║    viz.add_box()                                               ║
║    viz.add_sphere(radius=0.5, pos=[1,0,0])                     ║
║    viz.clear_scene()                                           ║
║                                                                ║
║  输入 exit() 或 Ctrl+D 退出                                    ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    print("🔌 正在连接 FrameViz...")
    viz = fv.open()
    print("✅ 连接成功!\n")

    try:
        from IPython import embed
        embed(colors="neutral")
    except ImportError:
        print("⚠️  IPython 未安装，使用标准 Python shell")
        print("   建议安装: pip install ipython\n")
        import code
        code.interact(local={'viz': viz, 'np': np, 'fv': fv})
    finally:
        viz.close()
        print("\n👋 已断开连接")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FrameViz 交互式测试框架")
    parser.add_argument('--quick', '-q', action='store_true', help='运行快速测试')
    parser.add_argument('--shell',
                        '-s',
                        action='store_true',
                        help='启动交互式 Shell')
    parser.add_argument('--full', '-f', action='store_true', help='运行完整测试')

    args = parser.parse_args()

    if args.shell:
        interactive_shell()
    elif args.quick:
        run_quick_test()
    else:
        run_full_test()

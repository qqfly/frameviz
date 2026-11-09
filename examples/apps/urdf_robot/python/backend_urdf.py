"""
URDF Robot Backend (WebSocket)

This backend loads the Synthetic Six-Axis Arm URDF meshes and listens for joint updates
from the UI via WebSocket. It computes forward kinematics in Python and
updates the 3D viewer.

Usage:
    python backend_urdf.py
    python backend_urdf.py --path /path/to/sample_robot

Dependencies:
    pip install -r requirements.txt
"""

import argparse
from frameviz.business_auth import authorize_business_socket, business_messages
import asyncio
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple
from urllib.parse import urlparse

import numpy as np
import frameviz as fv

try:
    import websockets
except ImportError as exc:  # pragma: no cover - runtime guidance
    print("[Backend] Missing dependency: websockets")
    print("Install with: pip install -r requirements.txt")
    raise exc

# Command-line arguments (will be set in main)
_CLI_ARGS: Optional[argparse.Namespace] = None

WS_HOST = os.environ.get("URDF_ROBOT_WS_HOST", "127.0.0.1")
WS_PORT = int(os.environ.get("URDF_ROBOT_WS_PORT", "9620"))
RESET_CAMERA = os.environ.get("URDF_ROBOT_RESET_CAMERA", "0") == "1"
MESH_LOAD_DELAY_SEC = 0.05
VIEWER_POLL_INTERVAL_SEC = 0.5

# Use port 8081 for mesh assets to avoid conflict with FrameViz Host's HTTP server on 8080
ASSET_SERVER_PORT = int(os.environ.get("FRAMEVIZ_ASSET_PORT", "8081"))
ASSET_BASE_URL = os.environ.get("FRAMEVIZ_ASSET_BASE_URL",
                                f"http://localhost:{ASSET_SERVER_PORT}")
AUTO_START_ASSET_SERVER = os.environ.get(
    "URDF_ROBOT_AUTO_START_ASSET_SERVER", "1") == "1"
HOST_HEADLESS = os.environ.get("FRAMEVIZ_HOST_HEADLESS", "1") == "1"
VISUAL_MESH_BASE_URL = (
    f"{ASSET_BASE_URL}/data/models/sample_robot/meshes/visual"
)
COLLISION_MESH_BASE_URL = (
    f"{ASSET_BASE_URL}/data/models/sample_robot/meshes/collision"
)

_ASSET_SERVER_PROCESS: Optional[subprocess.Popen] = None
_ASSET_HTTP_SERVER: Optional[http.server.ThreadingHTTPServer] = None
_ASSET_SERVER_THREAD: Optional[threading.Thread] = None

_ASSET_URL_PARTS = urlparse(ASSET_BASE_URL)
if _ASSET_URL_PARTS.port:
    ASSET_SERVER_PORT = _ASSET_URL_PARTS.port


def _find_repo_root() -> Optional[Path]:
    current = Path(__file__).resolve()
    for _ in range(8):
        if (current / "pnpm-workspace.yaml").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def _find_data_root() -> Optional[Path]:
    """Find the data directory for serving mesh files."""
    repo_root = _find_repo_root()
    if repo_root and (repo_root / "data").exists():
        return repo_root
    current = Path(__file__).resolve().parent
    for _ in range(6):
        if (current / "data" / "models").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


_APPROVED_MODEL_ROOT: Optional[Path] = None

def _start_python_asset_server(root_dir: Path) -> None:
    global _ASSET_HTTP_SERVER, _ASSET_SERVER_THREAD

    root_dir = root_dir.resolve()
    approved = (_APPROVED_MODEL_ROOT or root_dir / "data" / "models").resolve()
    if not approved.is_relative_to(root_dir):
        raise ValueError("Approved model root must be within the serving root")

    class _CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root_dir), **kwargs)

        def translate_path(self, path):
            from urllib.parse import unquote, urlsplit
            parts = Path(unquote(urlsplit(path).path)).parts
            candidate = Path(super().translate_path(path)).resolve()
            if any(part.startswith('.') for part in parts) or not candidate.is_relative_to(approved) or candidate.suffix.lower() not in {".stl", ".dae", ".urdf", ".obj", ".mtl", ".png", ".jpg"}:
                return str(root_dir / ".frameviz-denied")
            return str(candidate)

        def list_directory(self, path):
            self.send_error(403)
            return None

        def end_headers(self) -> None:
            from urllib.parse import urlsplit
            origin = self.headers.get("Origin", "")
            if urlsplit(origin).hostname in {"localhost", "127.0.0.1", "tauri.localhost"}:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            super().end_headers()

        def log_message(self, format: str, *args) -> None:
            return

    _ASSET_HTTP_SERVER = http.server.ThreadingHTTPServer(
        ("127.0.0.1", ASSET_SERVER_PORT), _CORSRequestHandler)
    _ASSET_SERVER_THREAD = threading.Thread(
        target=_ASSET_HTTP_SERVER.serve_forever,
        name="frameviz-asset-server",
        daemon=True,
    )
    _ASSET_SERVER_THREAD.start()
    print(
        f"[Backend] Starting asset server on http://localhost:{ASSET_SERVER_PORT}"
    )


def _maybe_start_asset_server() -> None:
    global _ASSET_SERVER_PROCESS
    if not AUTO_START_ASSET_SERVER:
        return
    if _ASSET_URL_PARTS.hostname not in (None, "127.0.0.1", "localhost"):
        return
    if _is_port_open("127.0.0.1", ASSET_SERVER_PORT):
        print(f"[Backend] Asset server already running on port {ASSET_SERVER_PORT}")
        return
    if _ASSET_SERVER_PROCESS and _ASSET_SERVER_PROCESS.poll() is None:
        return
    if _ASSET_HTTP_SERVER:
        return
    # Always use Python HTTP server to serve from repo root (which contains data/)
    data_root = _find_data_root()
    if not data_root:
        print("[Backend] Asset server not started (data root not found)")
        return
    try:
        _start_python_asset_server(data_root)
    except OSError as exc:
        print(f"[Backend] Failed to start asset server: {exc}")


def _maybe_start_asset_server_with_root(serve_root: Path) -> None:
    """Start asset server with a specific root directory."""
    global _ASSET_SERVER_PROCESS
    if not AUTO_START_ASSET_SERVER:
        return
    if _is_port_open("127.0.0.1", ASSET_SERVER_PORT):
        print(f"[Backend] Asset server already running on port {ASSET_SERVER_PORT}")
        return
    if _ASSET_SERVER_PROCESS and _ASSET_SERVER_PROCESS.poll() is None:
        return
    if _ASSET_HTTP_SERVER:
        return
    try:
        _start_python_asset_server(serve_root)
    except OSError as exc:
        print(f"[Backend] Failed to start asset server: {exc}")


def _wait_asset_server_ready(timeout: float = 5.0) -> None:
    """Poll the asset server until it responds to HTTP requests."""
    if not AUTO_START_ASSET_SERVER:
        return
    import time
    import urllib.request
    import urllib.error

    end = time.monotonic() + timeout
    url = f"http://127.0.0.1:{ASSET_SERVER_PORT}/"
    while time.monotonic() < end:
        try:
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=0.3)
            return
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    print("[Backend] Warning: asset server not ready after timeout")


@dataclass
class JointInfo:
    name: str
    parent_link: str
    child_link: str
    origin_xyz: np.ndarray
    origin_rpy: np.ndarray
    axis: np.ndarray
    limit_lower: float
    limit_upper: float


@dataclass
class LinkInfo:
    name: str
    mesh_file: str


class SyntheticSixAxisArm:

    def __init__(self, mesh_base_url: str, mesh_extension: str) -> None:
        self.links = [
            LinkInfo("base_link",
                     f"{mesh_base_url}/base_link.{mesh_extension}"),
            LinkInfo("link_1", f"{mesh_base_url}/link_1.{mesh_extension}"),
            LinkInfo("link_2", f"{mesh_base_url}/link_2.{mesh_extension}"),
            LinkInfo("link_3", f"{mesh_base_url}/link_3.{mesh_extension}"),
            LinkInfo("link_4", f"{mesh_base_url}/link_4.{mesh_extension}"),
            LinkInfo("link_5", f"{mesh_base_url}/link_5.{mesh_extension}"),
            LinkInfo("link_6", f"{mesh_base_url}/link_6.{mesh_extension}"),
        ]

        self.joints = [
            JointInfo(
                "joint_1",
                "base_link",
                "link_1",
                np.array([0, 0, 0.3991]),
                np.array([0, 0, 0]),
                np.array([0, 0, 1]),
                -2.967,
                2.967,
            ),
            JointInfo(
                "joint_2",
                "link_1",
                "link_2",
                np.array([0, 0, 0]),
                np.array([0, 0, 0]),
                np.array([0, 1, 0]),
                -1.745,
                2.269,
            ),
            JointInfo(
                "joint_3",
                "link_2",
                "link_3",
                np.array([0, 0, 0.448]),
                np.array([0, 0, 0]),
                np.array([0, 1, 0]),
                -3.491,
                1.222,
            ),
            JointInfo(
                "joint_4",
                "link_3",
                "link_4",
                np.array([0, 0, 0.042]),
                np.array([0, 0, 0]),
                np.array([1, 0, 0]),
                -4.712,
                4.712,
            ),
            JointInfo(
                "joint_5",
                "link_4",
                "link_5",
                np.array([0.451, 0, 0]),
                np.array([0, 0, 0]),
                np.array([0, 1, 0]),
                -2.269,
                2.269,
            ),
            JointInfo(
                "joint_6",
                "link_5",
                "link_6",
                np.array([0.082, 0, 0]),
                np.array([0, 0, 0]),
                np.array([1, 0, 0]),
                -6.283,
                6.283,
            ),
        ]

        self.joint_angles = np.zeros(6)

    def rotation_matrix(self, axis: np.ndarray, angle: float) -> np.ndarray:
        axis = axis / np.linalg.norm(axis)
        c = np.cos(angle)
        s = np.sin(angle)
        t = 1 - c
        x, y, z = axis
        return np.array([
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
        ])

    def rpy_to_rotation(self, rpy: np.ndarray) -> np.ndarray:
        roll, pitch, yaw = rpy
        rx = self.rotation_matrix(np.array([1, 0, 0]), roll)
        ry = self.rotation_matrix(np.array([0, 1, 0]), pitch)
        rz = self.rotation_matrix(np.array([0, 0, 1]), yaw)
        return rz @ ry @ rx

    def rotation_to_quat(self, r: np.ndarray) -> np.ndarray:
        trace = np.trace(r)
        if trace > 0:
            s = 0.5 / np.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (r[2, 1] - r[1, 2]) * s
            y = (r[0, 2] - r[2, 0]) * s
            z = (r[1, 0] - r[0, 1]) * s
        elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
            s = 2.0 * np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2])
            w = (r[2, 1] - r[1, 2]) / s
            x = 0.25 * s
            y = (r[0, 1] + r[1, 0]) / s
            z = (r[0, 2] + r[2, 0]) / s
        elif r[1, 1] > r[2, 2]:
            s = 2.0 * np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2])
            w = (r[0, 2] - r[2, 0]) / s
            x = (r[0, 1] + r[1, 0]) / s
            y = 0.25 * s
            z = (r[1, 2] + r[2, 1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1])
            w = (r[1, 0] - r[0, 1]) / s
            x = (r[0, 2] + r[2, 0]) / s
            y = (r[1, 2] + r[2, 1]) / s
            z = 0.25 * s
        return np.array([x, y, z, w])

    def forward_kinematics(self) -> List[Tuple[np.ndarray, np.ndarray]]:
        poses: List[Tuple[np.ndarray, np.ndarray]] = []
        current_pos = np.array([0.0, 0.0, 0.0])
        current_rot = np.eye(3)
        poses.append((current_pos.copy(), self.rotation_to_quat(current_rot)))

        for i, joint in enumerate(self.joints):
            origin_rot = self.rpy_to_rotation(joint.origin_rpy)
            current_pos = current_pos + current_rot @ joint.origin_xyz
            current_rot = current_rot @ origin_rot
            joint_rot = self.rotation_matrix(joint.axis, self.joint_angles[i])
            current_rot = current_rot @ joint_rot
            poses.append(
                (current_pos.copy(), self.rotation_to_quat(current_rot)))

        return poses

    def set_joint_angles(self, angles_rad: np.ndarray) -> None:
        if len(angles_rad) != len(self.joint_angles):
            raise ValueError("Expected 6 joint angles")
        self.joint_angles = angles_rad


class RobotVisualizer:

    def __init__(
        self,
        viz: fv.Viz,
        mesh_base_url: str,
        mesh_extension: str,
        color: Optional[Tuple[float, float, float, float]] = None,
    ) -> None:
        self.viz = viz
        self.robot = SyntheticSixAxisArm(mesh_base_url, mesh_extension)
        self.link_handles: List[str] = []
        self.color = color

    async def create_visuals(self) -> None:
        for link in self.robot.links:
            handle = self.viz.load_mesh(
                url=link.mesh_file,
                pos=[0, 0, 0],
                quat=[0, 0, 0, 1],
                scale=[1, 1, 1],
                color=self.color,
            )
            self.link_handles.append(handle)
            await asyncio.sleep(MESH_LOAD_DELAY_SEC)

        self.update_visuals()

    def update_visuals(self) -> None:
        poses = self.robot.forward_kinematics()
        for handle, (pos, quat) in zip(self.link_handles, poses):
            self.viz.set_transform(handle, pos=pos.tolist(), quat=quat.tolist())

    def set_joint_angles_rad(self, angles_rad: List[float]) -> None:
        self.robot.set_joint_angles(np.array(angles_rad))
        self.update_visuals()


class VisualizerState:

    def __init__(
        self,
        role: str,
        mesh_base_url: str,
        mesh_extension: str,
        color: Optional[Tuple[float, float, float, float]] = None,
    ) -> None:
        self.role = role
        self.mesh_base_url = mesh_base_url
        self.mesh_extension = mesh_extension
        self.color = color
        self.target_view_id: Optional[str] = None
        self.view_id: Optional[str] = None
        self.scene_id: Optional[str] = None
        self.visualizer: Optional[RobotVisualizer] = None
        self._ready = asyncio.Event()

    def begin_rebuild(self, view_id: str, scene_id: str) -> None:
        self.view_id = view_id
        self.scene_id = scene_id
        self.visualizer = None
        self._ready.clear()

    def set_visualizer(self, visualizer: RobotVisualizer) -> None:
        self.visualizer = visualizer
        self._ready.set()

    async def wait_ready(self) -> RobotVisualizer:
        await self._ready.wait()
        if not self.visualizer:
            raise RuntimeError("Visualizer not initialized")
        return self.visualizer

    def apply_joint_angles(self, angles_rad: np.ndarray) -> None:
        if self.visualizer:
            self.visualizer.set_joint_angles_rad(angles_rad.tolist())

    def update_target_view(self, target_view_id: Optional[str]) -> None:
        if target_view_id == self.target_view_id:
            return
        self.target_view_id = target_view_id
        self.view_id = None
        self.scene_id = None
        self._ready.clear()
        if self.visualizer:
            try:
                self.visualizer.viz.close()
            except Exception:
                pass
            self.visualizer = None


class ViewerGroup:

    def __init__(self, primary: VisualizerState,
                 states: List[VisualizerState]) -> None:
        self.primary = primary
        self.states = states
        self.joint_angles = np.zeros(6)

    async def wait_ready(self) -> None:
        await self.primary.wait_ready()

    def set_joint_angles(self, angles_rad: List[float]) -> None:
        self.joint_angles = np.array(angles_rad)
        for state in self.states:
            state.apply_joint_angles(self.joint_angles)

    def describe_views(self) -> str:
        parts = []
        for state in self.states:
            parts.append(
                f"{state.role}: target={state.target_view_id or 'none'} "
                f"connected={state.view_id or 'none'} scene_id={state.scene_id or 'none'}"
            )
        return ", ".join(parts)


async def monitor_viewer(state: VisualizerState, group: ViewerGroup) -> None:
    """
    Monitor a viewer and initialize visualizer when it becomes available.

    Polls for a target view_id and (re)initializes Viz binding when it changes.
    """
    while True:
        target_view_id = state.target_view_id
        if not target_view_id:
            await asyncio.sleep(VIEWER_POLL_INTERVAL_SEC)
            continue
        try:
            viz = fv.connect(view_id=target_view_id, timeout=0.5)
            view_id = viz.view_id
            scene_id = viz.scene_id

            should_rebuild = False
            if view_id and scene_id:
                if view_id != state.view_id or scene_id != state.scene_id:
                    print(
                        f"[Backend] View updated: role={state.role}, target={target_view_id}, "
                        f"view_id={view_id}, scene_id={scene_id}"
                    )
                    if state.visualizer:
                        try:
                            state.visualizer.viz.close()
                        except Exception:
                            pass
                    state.begin_rebuild(view_id, scene_id)
                    should_rebuild = True
                elif state.visualizer is None:
                    should_rebuild = True

            if should_rebuild and view_id and scene_id:
                viz.set_performance_mode(mode="quality")
                if RESET_CAMERA:
                    print("[Backend] Resetting camera")
                    viz.set_camera_pose(
                        eye=[2.0, -2.0, 1.5],
                        target=[0.3, 0, 0.5],
                        up=[0, 0, 1],
                    )
                visualizer = RobotVisualizer(
                    viz,
                    state.mesh_base_url,
                    state.mesh_extension,
                    color=state.color,
                )
                viz.clear()
                await visualizer.create_visuals()
                visualizer.set_joint_angles_rad(group.joint_angles.tolist())
                state.set_visualizer(visualizer)
            else:
                # Temporary attach for probing only; keep existing visualizer alive.
                viz.close()
        except Exception as exc:  # pragma: no cover - runtime guard
            print(f"[Backend] Viewer monitor error ({state.role}): {exc}")

        await asyncio.sleep(VIEWER_POLL_INTERVAL_SEC)


async def handle_client(websocket: Any,
                        group: ViewerGroup) -> None:
    if not await authorize_business_socket(websocket):
        return
    role_map = {state.role: state for state in group.states}
    print(f"[Backend] UI client connected from {websocket.remote_address}")
    print(f"[Backend] View status: {group.describe_views()}")

    # Send initial state
    initial_state = {
        "type": "state_update",
        "joint_positions": group.joint_angles.tolist()
    }
    await websocket.send(json.dumps(initial_state))

    try:
        async for message in business_messages(websocket):
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict) or not isinstance(payload.get('args', {}), dict):
                continue
            name = payload.get("name")
            args = payload.get("args", {})

            if name == "set_joints":
                positions = args.get("positions", [])
                if isinstance(positions, list) and len(positions) == 6:
                    group.set_joint_angles(positions)
                    # Send state update back to UI
                    update = {
                        "type": "state_update",
                        "joint_positions": group.joint_angles.tolist()
                    }
                    await websocket.send(json.dumps(update))

            elif name == "home":
                group.set_joint_angles([0, 0, 0, 0, 0, 0])
                # Send state update back to UI
                update = {
                    "type": "state_update",
                    "joint_positions": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                }
                await websocket.send(json.dumps(update))
                print("[Backend] Robot moved to home position")
            elif name == "set_view_ids":
                main_view_id = args.get("main_view_id")
                collision_view_id = args.get("collision_view_id")
                main_state = role_map.get("main")
                if main_state:
                    if isinstance(main_view_id, str) and main_view_id:
                        main_state.update_target_view(main_view_id)
                    elif main_view_id is None:
                        main_state.update_target_view(None)
                collision_state = role_map.get("collision")
                if collision_state:
                    if isinstance(collision_view_id, str) and collision_view_id:
                        collision_state.update_target_view(collision_view_id)
                    elif collision_view_id is None:
                        collision_state.update_target_view(None)
                print(f"[Backend] Updated targets: {group.describe_views()}")

            elif name == "start_welding":
                print("[Backend] Start welding (not implemented)")

            elif name == "stop":
                print("[Backend] Stop (not implemented)")

    except websockets.exceptions.ConnectionClosed:
        print(f"[Backend] UI client disconnected")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="URDF Robot Backend - Loads Synthetic Six-Axis Arm meshes and handles joint control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python backend_urdf.py
    python backend_urdf.py --path /path/to/sample_robot
    python backend_urdf.py --path ~/models/sample_robot
        """
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to sample_robot directory containing meshes/ folder. "
             "If not provided, will search in repository data/ directory."
    )
    return parser.parse_args()


def _get_mesh_base_urls(model_path: Optional[str]) -> Tuple[str, str, Optional[Path]]:
    """
    Get mesh base URLs based on provided path or auto-detection.

    Returns:
        Tuple of (visual_url, collision_url, asset_serve_root)
        asset_serve_root is the directory to serve via HTTP, or None if using external URL
    """
    global _APPROVED_MODEL_ROOT
    if model_path:
        # User provided explicit path
        model_dir = Path(model_path).expanduser().resolve()
        if not model_dir.exists():
            print(f"[Backend] Error: Model path does not exist: {model_dir}")
            sys.exit(1)
        meshes_dir = model_dir / "meshes"
        if not meshes_dir.exists():
            print(f"[Backend] Error: meshes/ directory not found in: {model_dir}")
            print(f"[Backend] Expected structure: {model_dir}/meshes/visual/ and {model_dir}/meshes/collision/")
            sys.exit(1)
        visual_dir = meshes_dir / "visual"
        collision_dir = meshes_dir / "collision"
        if not visual_dir.exists():
            print(f"[Backend] Error: visual meshes not found: {visual_dir}")
            sys.exit(1)
        if not collision_dir.exists():
            print(f"[Backend] Error: collision meshes not found: {collision_dir}")
            sys.exit(1)
        # Serve from the parent of model_dir so URL structure matches
        # e.g., if model_path=/foo/sample_robot, serve from /foo
        # and access via /sample_robot/meshes/visual/...
        _APPROVED_MODEL_ROOT = model_dir
        serve_root = model_dir.parent
        model_name = model_dir.name
        visual_url = f"http://localhost:{ASSET_SERVER_PORT}/{model_name}/meshes/visual"
        collision_url = f"http://localhost:{ASSET_SERVER_PORT}/{model_name}/meshes/collision"
        print(f"[Backend] Using model path: {model_dir}")
        return visual_url, collision_url, serve_root
    else:
        # Auto-detect from repository
        data_root = _find_data_root()
        if data_root:
            model_dir = data_root / "data" / "models" / "sample_robot"
            if model_dir.exists() and (model_dir / "meshes" / "visual").exists():
                _APPROVED_MODEL_ROOT = model_dir
                visual_url = f"http://localhost:{ASSET_SERVER_PORT}/data/models/sample_robot/meshes/visual"
                collision_url = f"http://localhost:{ASSET_SERVER_PORT}/data/models/sample_robot/meshes/collision"
                print(f"[Backend] Auto-detected model path: {model_dir}")
                return visual_url, collision_url, data_root
        # Failed to find
        print("[Backend] Error: Could not find Synthetic Six-Axis Arm model files.")
        print("[Backend] Please specify the model path using --path argument:")
        print("[Backend]   python backend_urdf.py --path /path/to/sample_robot")
        print("[Backend] ")
        print("[Backend] The directory should contain:")
        print("[Backend]   meshes/visual/base_link.dae, link_1.dae, ...")
        print("[Backend]   meshes/collision/base_link.stl, link_1.stl, ...")
        sys.exit(1)


async def main() -> None:
    global _CLI_ARGS
    _CLI_ARGS = parse_args()

    # Get mesh URLs based on --path argument or auto-detection
    visual_url, collision_url, asset_serve_root = _get_mesh_base_urls(_CLI_ARGS.path)

    print("[Backend] Starting URDF backend...")
    try:
        print("[Backend] Ensuring FrameViz Host is running...")
        if not fv.is_host_running():
            fv.start_host(headless=HOST_HEADLESS)
        _ = fv.list_views(timeout=1.0)
        print("[Backend] Connected to FrameViz Host")
    except Exception as exc:
        print(f"[Backend] Failed to connect: {exc}")
        print("[Backend] Make sure the Tauri host is running")
        return

    # Start asset server with the appropriate root directory
    if asset_serve_root:
        _maybe_start_asset_server_with_root(asset_serve_root)
    else:
        _maybe_start_asset_server()
    _wait_asset_server_ready()

    visual_state = VisualizerState("main", visual_url, "dae")
    collision_state = VisualizerState(
        "collision",
        collision_url,
        "stl",
        color=(0.9, 0.3, 0.2, 0.4),
    )
    group = ViewerGroup(visual_state, [visual_state, collision_state])
    monitor_tasks = [
        asyncio.create_task(monitor_viewer(visual_state, group)),
        asyncio.create_task(monitor_viewer(collision_state, group)),
    ]

    print(f"[Backend] UI WebSocket listening on ws://{WS_HOST}:{WS_PORT}")
    print("[Backend] Waiting for frontend to publish view_ids...")
    server = await websockets.serve(
        lambda ws: handle_client(ws, group),
        WS_HOST,
        WS_PORT,
        subprotocols=["frameviz-business"],
        ping_interval=20,
    )

    try:
        await server.wait_closed()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[Backend] Shutting down...")
    finally:
        for task in monitor_tasks:
            task.cancel()
        await asyncio.gather(*monitor_tasks, return_exceptions=True)
        server.close()
        await server.wait_closed()
        if _ASSET_SERVER_PROCESS and _ASSET_SERVER_PROCESS.poll() is None:
            _ASSET_SERVER_PROCESS.terminate()
        if _ASSET_HTTP_SERVER:
            _ASSET_HTTP_SERVER.shutdown()
            if _ASSET_SERVER_THREAD:
                _ASSET_SERVER_THREAD.join(timeout=1.0)
        if visual_state.visualizer:
            visual_state.visualizer.viz.close()
        if collision_state.visualizer:
            collision_state.visualizer.viz.close()


if __name__ == "__main__":
    asyncio.run(main())

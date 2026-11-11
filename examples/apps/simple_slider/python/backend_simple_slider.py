"""
Simple Slider Backend (Python, WebSocket)

Backend-controlled example for `examples/apps/simple_slider`.

- UI sends business commands only
- Backend owns FrameViz scene/object lifecycle
- Viewer is attached by `view_id` and rebuilt on reload/reconnect

Usage:
    python backend_simple_slider.py

Dependencies:
    pip install -r requirements.txt
"""

import argparse
from pathlib import Path
import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Set

import frameviz as fv
from frameviz.business_auth import authorize_business_socket, business_messages, select_business_subprotocol

DEFAULT_WS_HOST = os.environ.get("SIMPLE_SLIDER_WS_HOST", "127.0.0.1")
DEFAULT_WS_PORT = int(os.environ.get("SIMPLE_SLIDER_WS_PORT", "9621"))
DEFAULT_VIEWER_NAME = os.environ.get("SIMPLE_SLIDER_VIEWER_NAME", "simple_slider_viewer")
HOST_HEADLESS = os.environ.get("FRAMEVIZ_HOST_HEADLESS", "1") == "1"
VIEWER_POLL_INTERVAL_SEC = 0.5


class SimpleSliderBackend:
    def __init__(self, viewer_name: str) -> None:
        self.viewer_name = viewer_name

        self.pos: List[float] = [0.0, 0.0, 0.5]
        self.quat: List[float] = [0.0, 0.0, 0.0, 1.0]
        self.rgba: List[float] = [1.0, 0.42, 0.42, 1.0]

        self.view_id: str = ""
        self.scene_id: str = ""
        self.box_handle: str = ""

        self.viz: Optional[fv.Viz] = None
        self.scene_ready = False

        self.clients: Set[Any] = set()
        self.lock = asyncio.Lock()

    async def handle_client(self, ws: Any) -> None:
        if not await authorize_business_socket(ws):
            return
        if len(self.clients) >= 32:
            await ws.close(code=1008, reason='Business connection limit exceeded')
            return
        async with self.lock:
            self.clients.add(ws)
            initial = self._state_payload_locked()
        await self._send_json(ws, initial)

        try:
            async for raw in business_messages(ws):
                await self._handle_message(ws, raw)
        except Exception:
            pass
        finally:
            async with self.lock:
                self.clients.discard(ws)

    async def _handle_message(self, ws: Any, raw: str) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(ws, "Invalid JSON payload")
            return

        if not isinstance(message, dict):
            await self._send_error(ws, "message must be an object")
            return
        name = message.get("name", "")
        args = message.get("args", {})
        if not isinstance(args, dict):
            await self._send_error(ws, "args must be an object")
            return

        async with self.lock:
            await self._handle_command_locked(ws, str(name), args)

    async def _handle_command_locked(self, ws: Any, name: str, args: Dict[str, Any]) -> None:
        if name == "bind_viewer":
            requested_name = args.get("viewer_name")
            requested_view_id = args.get("view_id")
            requested_scene_id = args.get("scene_id")

            if isinstance(requested_name, str) and requested_name.strip() and requested_name != self.viewer_name:
                print(f"[Backend] Viewer name changed: {self.viewer_name} -> {requested_name}")
                self.viewer_name = requested_name

            if isinstance(requested_view_id, str) and requested_view_id.strip():
                if requested_view_id != self.view_id or not self.scene_ready:
                    print(
                        f"[Backend] Bind request: viewer={self.viewer_name}, "
                        f"view_id={requested_view_id}, scene_id={requested_scene_id or ''}"
                    )
                    self.view_id = requested_view_id
                    self.scene_id = str(requested_scene_id or "")
                    self._bind_to_view_locked()
            await self._broadcast_state_locked()
            return

        if name == "set_box_pose":
            pos = self._parse_float_list(args.get("pos"), 3)
            quat = self._parse_float_list(args.get("quat"), 4)
            if pos is None or quat is None:
                await self._send_error(ws, "set_box_pose requires pos[3] and quat[4]")
                return
            self.pos = pos
            self.quat = quat
            self._apply_pose_locked()
            await self._broadcast_state_locked()
            return

        if name == "set_box_color":
            rgba = self._parse_float_list(args.get("rgba"), None)
            if rgba is None or len(rgba) not in (3, 4):
                await self._send_error(ws, "set_box_color requires rgb[3] or rgba[4]")
                return
            if len(rgba) == 3:
                rgba = rgba + [1.0]
            self.rgba = rgba
            self._apply_color_locked()
            await self._broadcast_state_locked()
            return

        if name == "reset_box":
            self.pos = [0.0, 0.0, 0.5]
            self.quat = [0.0, 0.0, 0.0, 1.0]
            self.rgba = [1.0, 0.42, 0.42, 1.0]
            self._apply_pose_locked()
            self._apply_color_locked()
            await self._broadcast_state_locked()
            return

        await self._send_error(ws, f"Unknown command: {name}")

    async def monitor_viewer(self) -> None:
        while True:
            await asyncio.sleep(VIEWER_POLL_INTERVAL_SEC)
            async with self.lock:
                if not self.view_id:
                    continue

                if self.scene_ready and self.viz and self.box_handle:
                    try:
                        if self.viz.is_object_alive(self.box_handle):
                            continue
                    except Exception:
                        pass

                self._bind_to_view_locked()
                await self._broadcast_state_locked()

    def _bind_to_view_locked(self) -> None:
        if not self.view_id:
            self.scene_ready = False
            self.box_handle = ""
            self.viz = None
            return

        try:
            self.viz = fv.connect(view_id=self.view_id, timeout=0.5)
        except Exception as exc:
            self.scene_ready = False
            self.box_handle = ""
            self.viz = None
            print(f"[Backend] connect(view_id={self.view_id}) failed: {exc}")
            return

        self.scene_id = self.viz.scene_id
        print(
            f"[Backend] Bound viewer: name={self.viewer_name}, "
            f"view_id={self.view_id}, scene_id={self.scene_id}"
        )
        self._rebuild_scene_locked()
        if not self.scene_ready:
            return

    def _rebuild_scene_locked(self) -> None:
        if not self.viz:
            self.scene_ready = False
            self.box_handle = ""
            return

        try:
            self.viz.clear()
            self.viz.add_axes(length=1.0)
            self.viz.add_plane(
                width=6.0,
                height=6.0,
                pos=[0.0, 0.0, 0.0],
                quat=[0.0, 0.0, 0.0, 1.0],
                color=[0.3, 0.3, 0.3, 0.5],
            )
            self.box_handle = self.viz.add_box(
                size=[1.0, 1.0, 1.0],
                pos=self.pos,
                quat=self.quat,
                color=self.rgba,
            )
            self.scene_ready = True
            print(f"[Backend] Scene initialized, box_handle={self.box_handle}")
        except Exception as exc:
            self.scene_ready = False
            self.box_handle = ""
            print(f"[Backend] Scene init failed: {exc}")

    def _apply_pose_locked(self) -> None:
        if not self.scene_ready or not self.viz or not self.box_handle:
            return
        try:
            self.viz.set_transform(self.box_handle, pos=self.pos, quat=self.quat)
        except Exception as exc:
            print(f"[Backend] set_transform failed: {exc}")

    def _apply_color_locked(self) -> None:
        if not self.scene_ready or not self.viz or not self.box_handle:
            return
        try:
            self.viz.set_color(self.box_handle, self.rgba)
        except Exception as exc:
            print(f"[Backend] set_color failed: {exc}")

    async def _send_error(self, ws: Any, message: str) -> None:
        await self._send_json(ws, {"type": "error", "message": message})

    async def _broadcast_state_locked(self) -> None:
        payload = self._state_payload_locked()
        if not self.clients:
            return
        await asyncio.gather(
            *[self._send_json(client, payload) for client in list(self.clients)],
            return_exceptions=True,
        )

    def _state_payload_locked(self) -> Dict[str, Any]:
        return {
            "type": "state_update",
            "viewer_name": self.viewer_name,
            "view_id": self.view_id,
            "scene_id": self.scene_id,
            "viewer_ready": self.scene_ready,
            "box_handle": self.box_handle,
            "pose": {
                "pos": self.pos,
                "quat": self.quat,
            },
            "rgba": self.rgba,
        }

    @staticmethod
    async def _send_json(ws: Any, payload: Dict[str, Any]) -> None:
        try:
            await ws.send(json.dumps(payload))
        except Exception:
            pass

    @staticmethod
    def _parse_float_list(value: Any, length: Optional[int]) -> Optional[List[float]]:
        if not isinstance(value, list):
            return None
        if length is not None and len(value) != length:
            return None
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return None


async def run_backend(args: argparse.Namespace) -> None:
    try:
        import websockets
    except ImportError as exc:  # pragma: no cover - runtime guidance
        print("[Backend] Missing dependency: websockets")
        print("Install with: pip install -r requirements.txt")
        raise exc

    print("[Backend] Starting Simple Slider Python backend...")

    try:
        if not fv.is_host_running():
            fv.start_host(headless=args.host_headless)
        _ = fv.list_views(timeout=1.0)
        print("[Backend] FrameViz Host is ready")
    except Exception as exc:
        print(f"[Backend] Failed to prepare FrameViz Host: {exc}")
        return

    backend = SimpleSliderBackend(args.viewer_name)
    monitor_task = asyncio.create_task(backend.monitor_viewer())

    server = await websockets.serve(
        backend.handle_client,
        args.ws_host,
        args.ws_port,
        subprotocols=["frameviz-business"],
        select_subprotocol=select_business_subprotocol,
        ping_interval=20,
    )

    port = server.sockets[0].getsockname()[1]
    print(f"[Backend] UI WebSocket listening on ws://{args.ws_host}:{port}")
    print(f"[Backend] Waiting for viewer: {args.viewer_name}")
    if getattr(args, "ready_file", None):
        path = Path(args.ready_file)
        pending = path.with_suffix(".tmp")
        pending.write_text(str(port), encoding="utf-8")
        pending.replace(path)

    try:
        await server.wait_closed()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[Backend] Shutting down...")
    finally:
        monitor_task.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)
        server.close()
        await server.wait_closed()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple Slider Python backend")
    parser.add_argument("--ws-host", default=DEFAULT_WS_HOST, help="UI WebSocket host")
    parser.add_argument("--ready-file", help=argparse.SUPPRESS)
    parser.add_argument("--ws-port", type=int, default=DEFAULT_WS_PORT, help="UI WebSocket port")
    parser.add_argument(
        "--viewer-name",
        default=DEFAULT_VIEWER_NAME,
        help="Viewer name registered by frontend",
    )
    parser.add_argument(
        "--host-headless",
        type=int,
        choices=[0, 1],
        default=1 if HOST_HEADLESS else 0,
        help="Auto-start FrameViz Host in headless mode (0/1)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.host_headless = bool(args.host_headless)
    asyncio.run(run_backend(args))


if __name__ == "__main__":
    main()

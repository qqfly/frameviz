"""
FrameViz External App Backend (Python)

- UI sends business commands over WebSocket
- Backend owns FrameViz scene/object lifecycle
- Frontend publishes target `view_id`; backend attaches with `fv.connect(view_id=...)`
"""

import argparse
import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import frameviz as fv
from frameviz.business_auth import authorize_business_socket, business_messages

DEFAULT_WS_HOST = os.environ.get("FRAMEVIZ_APP_WS_HOST", "127.0.0.1")
DEFAULT_WS_PORT = int(os.environ.get("FRAMEVIZ_APP_WS_PORT", "9621"))
DEFAULT_VIEWER_NAME = os.environ.get("FRAMEVIZ_APP_VIEWER_NAME", "main_viewer")
HOST_HEADLESS = os.environ.get("FRAMEVIZ_HOST_HEADLESS", "1") == "1"
DEFAULT_FRAMEVIZ_HOST = os.environ.get("FRAMEVIZ_HOST", "ws://127.0.0.1:9527")
DEFAULT_CONNECT_TIMEOUT_SEC = float(os.environ.get("FRAMEVIZ_CONNECT_TIMEOUT", "2.0"))
DEFAULT_PARENT_PID = int(os.environ.get("FRAMEVIZ_PARENT_PID", "0") or "0")
EXIT_ON_PARENT_DEATH = os.environ.get("FRAMEVIZ_EXIT_ON_PARENT_DEATH", "1") == "1"
PARENT_WATCH_INTERVAL_SEC = float(os.environ.get("FRAMEVIZ_PARENT_WATCH_INTERVAL", "1.0"))
VIEWER_POLL_INTERVAL_SEC = 0.5
ERROR_LOG_THROTTLE_SEC = 3.0


class AppBackend:
    def __init__(self, viewer_name: str, frameviz_host: str, connect_timeout_sec: float) -> None:
        self.viewer_name = viewer_name
        self.frameviz_host = frameviz_host
        self.connect_timeout_sec = connect_timeout_sec

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
        self._last_bind_error: str = ""
        self._last_bind_error_ts: float = 0.0

    async def handle_client(self, ws: Any) -> None:
        if not await authorize_business_socket(ws):
            return
        if len(self.clients) >= 32:
            await ws.close(code=1008, reason='Business connection limit exceeded')
            return
        async with self.lock:
            self.clients.add(ws)
            payload = self._state_payload_locked()
        await self._send_json(ws, payload)

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

        name = str(message.get("name", ""))
        args = message.get("args", {})
        if not isinstance(args, dict):
            await self._send_error(ws, "args must be an object")
            return

        async with self.lock:
            await self._handle_command_locked(ws, name, args)

    async def _handle_command_locked(self, ws: Any, name: str, args: Dict[str, Any]) -> None:
        if name == "bind_viewer":
            requested_name = args.get("viewer_name")
            requested_view_id = args.get("view_id")
            requested_scene_id = args.get("scene_id")
            should_rebind = False

            if isinstance(requested_name, str) and requested_name.strip() and requested_name != self.viewer_name:
                self.viewer_name = requested_name
                should_rebind = True

            if isinstance(requested_view_id, str) and requested_view_id.strip():
                if requested_view_id != self.view_id or not self.scene_ready:
                    print(
                        f"[Backend] Bind request: viewer={self.viewer_name}, "
                        f"view_id={requested_view_id}, scene_id={requested_scene_id or ''}"
                    )
                    self.view_id = requested_view_id
                    self.scene_id = str(requested_scene_id or "")
                    should_rebind = True

            if should_rebind:
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
                if not self.view_id and not self.viewer_name:
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
        bind_candidates: List[Tuple[str, str]] = []
        if self.view_id:
            bind_candidates.append(("view_id", self.view_id))

        by_name = self._query_view_by_name_locked()
        if by_name:
            candidate_view_id, candidate_scene_id = by_name
            if candidate_view_id and candidate_view_id != self.view_id:
                bind_candidates.append(("viewer_name", candidate_view_id))
            if candidate_scene_id:
                self.scene_id = candidate_scene_id

        if not bind_candidates:
            self.scene_ready = False
            self.box_handle = ""
            self.viz = None
            return

        last_exc: Optional[Exception] = None
        bound_view_id = ""
        self.viz = None
        for source, candidate_view_id in bind_candidates:
            try:
                self.viz = fv.connect(
                    url=self.frameviz_host,
                    view_id=candidate_view_id,
                    timeout=self.connect_timeout_sec,
                )
                if candidate_view_id != self.view_id:
                    print(
                        f"[Backend] Rebound view_id by {source}: "
                        f"{self.view_id or '(none)'} -> {candidate_view_id}"
                    )
                self.view_id = candidate_view_id
                bound_view_id = candidate_view_id
                break
            except Exception as exc:
                last_exc = exc

        if not self.viz:
            self.scene_ready = False
            self.box_handle = ""
            self._throttled_bind_log(
                self._format_bind_error(last_exc, bind_candidates),
            )
            return

        self.scene_id = self.viz.scene_id
        print(
            f"[Backend] Bound viewer: name={self.viewer_name}, "
            f"view_id={bound_view_id}, scene_id={self.scene_id}"
        )
        self._rebuild_scene_locked()
        if not self.scene_ready:
            return

    def _query_view_by_name_locked(self) -> Optional[Tuple[str, str]]:
        if not self.viewer_name:
            return None
        client = fv.FrameVizClient(url=self.frameviz_host, timeout=self.connect_timeout_sec)
        try:
            client.connect()
            result = client.send_command(
                "get_viewer_by_name",
                {"viewer_name": self.viewer_name},
            )
        except Exception as exc:
            if "ERR_NOT_FOUND" in str(exc):
                return None
            self._throttled_bind_log(
                f"[Backend] get_viewer_by_name failed on {self.frameviz_host}: {exc}"
            )
            return None
        finally:
            try:
                client.close()
            except Exception:
                pass

        view_id = str(result.get("view_id") or "")
        scene_id = str(result.get("scene_id") or "")
        if not view_id:
            return None
        return view_id, scene_id

    def _format_bind_error(
        self,
        exc: Optional[Exception],
        bind_candidates: List[Tuple[str, str]],
    ) -> str:
        attempts = ", ".join([f"{source}:{view_id}" for source, view_id in bind_candidates])
        available = self._list_available_views_locked()
        available_hint = ""
        if available:
            available_hint = f" available_view_ids={', '.join(available)}."
        return (
            f"[Backend] bind failed on {self.frameviz_host}. "
            f"viewer={self.viewer_name}, attempts=[{attempts}], "
            f"last_error={exc or 'unknown'}."
            + available_hint
        )

    def _list_available_views_locked(self) -> List[str]:
        try:
            views = fv.list_views(url=self.frameviz_host, timeout=self.connect_timeout_sec)
        except Exception:
            return []
        out: List[str] = []
        for item in views:
            view_id = item.get("view_id")
            if isinstance(view_id, str) and view_id:
                out.append(view_id)
        return out

    def _throttled_bind_log(self, message: str) -> None:
        now = time.time()
        if message != self._last_bind_error or now - self._last_bind_error_ts >= ERROR_LOG_THROTTLE_SEC:
            print(message)
            self._last_bind_error = message
            self._last_bind_error_ts = now

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


def _process_exists(pid: int) -> bool:
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return True


def _resolve_parent_pid(raw_parent_pid: int) -> int:
    if not EXIT_ON_PARENT_DEATH:
        return 0
    if raw_parent_pid and raw_parent_pid > 1:
        return raw_parent_pid
    # Fallback: monitor the direct parent process so the watchdog activates
    # even when FRAMEVIZ_PARENT_PID is not explicitly set (e.g. dev-stack).
    fallback = os.getppid()
    if fallback > 1:
        return fallback
    return 0


async def monitor_parent_lifecycle(parent_pid: int) -> None:
    if parent_pid <= 1:
        return
    while True:
        current_parent_pid = os.getppid()
        if current_parent_pid == parent_pid:
            await asyncio.sleep(PARENT_WATCH_INTERVAL_SEC)
            continue
        if not _process_exists(parent_pid) or current_parent_pid <= 1:
            print(f"[Backend] Parent process exited (expected={parent_pid}, current={current_parent_pid}), exiting backend")
            os._exit(0)
        await asyncio.sleep(PARENT_WATCH_INTERVAL_SEC)


async def run_backend(args: argparse.Namespace) -> None:
    try:
        import websockets
    except ImportError as exc:
        print("[Backend] Missing dependency: websockets")
        print("Install with: pip install -r python/requirements.txt")
        raise exc

    parent_pid = _resolve_parent_pid(args.parent_pid)
    if parent_pid > 1 and not _process_exists(parent_pid):
        print(f"[Backend] Parent process {parent_pid} is not alive, skip backend startup")
        return

    parent_monitor_task: Optional[asyncio.Task[Any]] = None
    if parent_pid > 1:
        print(f"[Backend] Parent watchdog enabled: pid={parent_pid}")
        parent_monitor_task = asyncio.create_task(monitor_parent_lifecycle(parent_pid))

    print("[Backend] Starting Python backend...")

    try:
        if not fv.is_host_running():
            fv.start_host(headless=args.host_headless)
        _ = fv.list_views(url=args.frameviz_host, timeout=max(1.0, args.connect_timeout))
        print(f"[Backend] FrameViz Host is ready: {args.frameviz_host}")
    except Exception as exc:
        print(f"[Backend] Failed to prepare FrameViz Host: {exc}")
        return

    backend = AppBackend(
        viewer_name=args.viewer_name,
        frameviz_host=args.frameviz_host,
        connect_timeout_sec=args.connect_timeout,
    )
    monitor_task = asyncio.create_task(backend.monitor_viewer())

    print(f"[Backend] UI WebSocket listening on ws://{args.ws_host}:{args.ws_port}")
    print(f"[Backend] Waiting for viewer: {args.viewer_name}")
    server = await websockets.serve(
        backend.handle_client,
        args.ws_host,
        args.ws_port,
        ping_interval=20,
    )

    try:
        await server.wait_closed()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[Backend] Shutting down...")
    finally:
        if parent_monitor_task:
            parent_monitor_task.cancel()
            await asyncio.gather(parent_monitor_task, return_exceptions=True)
        monitor_task.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)
        server.close()
        await server.wait_closed()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FrameViz external app backend (Python)")
    parser.add_argument("--ws-host", default=DEFAULT_WS_HOST, help="UI WebSocket host")
    parser.add_argument("--ws-port", type=int, default=DEFAULT_WS_PORT, help="UI WebSocket port")
    parser.add_argument("--viewer-name", default=DEFAULT_VIEWER_NAME, help="Frontend viewer name")
    parser.add_argument(
        "--frameviz-host",
        default=DEFAULT_FRAMEVIZ_HOST,
        help="FrameViz Host websocket url",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=DEFAULT_CONNECT_TIMEOUT_SEC,
        help="Timeout in seconds for each connect attempt",
    )
    parser.add_argument(
        "--host-headless",
        type=int,
        choices=[0, 1],
        default=1 if HOST_HEADLESS else 0,
        help="Auto-start FrameViz Host in headless mode (0/1)",
    )
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=DEFAULT_PARENT_PID,
        help="Parent process pid for watchdog auto-exit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.host_headless = bool(args.host_headless)
    args.parent_pid = int(args.parent_pid or 0)
    asyncio.run(run_backend(args))


if __name__ == "__main__":
    main()

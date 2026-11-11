"""
High-level FrameViz API for comfortable Python usage.

Wraps the low-level protocol client with convenience methods for primitives,
buffer management, camera control, and event handling.
"""

from __future__ import annotations

import builtins
import atexit
import hashlib
import logging
import json
import os
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import signal
import tempfile
import time
import threading
import uuid
import webbrowser
from collections import deque
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import numpy as np

from .client import DEFAULT_WS_URL, FrameVizClient, PROTOCOL_VERSION
from ._scene_tree import components, node_arguments, rigid_pose
from .discovery import get_discovery_path, get_viewer_url_from_discovery
from .exceptions import ConnectionError as FrameVizConnectionError, TimeoutError as FrameVizTimeoutError, ProtocolError
from ._internal import (
    _AUTO_WS_LOG_HANDLE,
    _AUTO_WS_LOG_PATH,
    _AUTO_WS_PROCESS,
    _get_repo_root,
    _get_macos_app_executable,
    _get_tauri_app_candidates,
    _get_tauri_exec_candidates,
    _get_appimage_candidates,
    _get_ws_port_from_url,
    _get_ws_startup_timeout,
    _is_port_open,
    _maybe_auto_start_ws as _maybe_auto_start_ws_basic,
    _read_ws_log_tail,
    _resolve_discovery_port,
    _resolve_ws_url,
    _should_auto_start_ws,
    _wait_for_discovery_port,
    _wait_for_ws_ready,
)

# Default viewer URL for auto-open (fallback if discovery fails).
# Note: This points to the Release Host root (/). In Dev mode, the viewer is at
# /packages/frameviz-web-viewer/, so this fallback might 404 in Dev if discovery fails.
DEFAULT_VIEWER_URL = "http://localhost:8080/"
DEFAULT_TAURI_CONTROL_PORT = 9528
_AUTO_TAURI_PROCS: List[subprocess.Popen] = []
_AUTO_TAURI_ATEXIT_REGISTERED = False


def _stop_auto_tauri_processes() -> None:
    global _AUTO_TAURI_PROCS
    procs = _AUTO_TAURI_PROCS
    _AUTO_TAURI_PROCS = []
    for proc in procs:
        if proc.poll() is not None:
            continue
        sent_group_signal = False
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                sent_group_signal = True
            except OSError:
                pass
        try:
            if not sent_group_signal:
                proc.terminate()
            proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            if os.name == "posix":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
            else:
                try:
                    proc.kill()
                except OSError:
                    pass


def _register_auto_tauri_atexit() -> None:
    global _AUTO_TAURI_ATEXIT_REGISTERED
    if _AUTO_TAURI_ATEXIT_REGISTERED:
        return
    _AUTO_TAURI_ATEXIT_REGISTERED = True
    atexit.register(_stop_auto_tauri_processes)


def _get_viewer_url(expected_ws_url: Optional[str] = None) -> Optional[str]:
    """
    Return only the Viewer advertised for the connected runtime.

    A guessed development port could belong to another local application and
    must never receive a credential-bearing browser link.
    """
    # Try to get viewer URL from discovery file first
    from .discovery import read_discovery_file
    info=read_discovery_file() or {}
    if expected_ws_url:
        expected=urlparse(expected_ws_url)
        discovered=urlparse(info.get('ws_url') if isinstance(info.get('ws_url'),str) else '')
        aliases={'127.0.0.1','localhost','::1'}
        same_host=expected.hostname==discovered.hostname or {expected.hostname,discovered.hostname}<=aliases
        if not same_host or expected.port!=discovered.port:return None
    candidate=info.get('viewer_url')
    return candidate if isinstance(candidate,str) and candidate else None

# Type aliases
Color = Union[str, Tuple[float, float, float], List[float]]
Vec3 = Union[Tuple[float, float, float], List[float], np.ndarray]
Quat = Union[Tuple[float, float, float, float], List[float], np.ndarray]
EventHandler = Callable[[Dict[str, Any]], None]

logger = logging.getLogger(__name__)

# Presentation labels only: scenes, clients and Viz ownership stay independent.
_BROWSER_SESSIONS: Dict[Tuple[str, str, int, str], str] = {}
_BROWSER_SESSION_LOCK = threading.RLock()


def _normalize_color(color: Color) -> List[float]:
    """Convert a color specification to [r, g, b] or [r, g, b, a] floats in 0..1."""
    if isinstance(color, str):
        color = color.lower().strip()
        presets = {
            "red": [1.0, 0.0, 0.0],
            "green": [0.0, 1.0, 0.0],
            "blue": [0.0, 0.0, 1.0],
            "white": [1.0, 1.0, 1.0],
            "black": [0.0, 0.0, 0.0],
            "yellow": [1.0, 1.0, 0.0],
            "cyan": [0.0, 1.0, 1.0],
            "magenta": [1.0, 0.0, 1.0],
            "orange": [1.0, 0.5, 0.0],
            "lime": [0.0, 1.0, 0.0],
            "pink": [1.0, 0.75, 0.8],
            "purple": [0.5, 0.0, 0.5],
            "brown": [0.6, 0.3, 0.0],
            "gray": [0.5, 0.5, 0.5],
            "grey": [0.5, 0.5, 0.5],
        }
        if color in presets:
            return presets[color]
        # Try to parse hex color
        if color.startswith("#") and len(color) == 7:
            r = int(color[1:3], 16) / 255.0
            g = int(color[3:5], 16) / 255.0
            b = int(color[5:7], 16) / 255.0
            return [r, g, b]
        raise ValueError(f"Unknown color: {color}")
    rgba = list(color)
    if len(rgba) not in (3, 4):
        raise ValueError(
            f"Color must have exactly 3 or 4 components, got {len(rgba)}."
        )
    # Validate RGB components (always present)
    for i in range(3):
        if not (0.0 <= rgba[i] <= 1.0):
            raise ValueError(
                f"Color component {i} = {rgba[i]} out of range [0.0, 1.0]. "
                "Use floats between 0.0 and 1.0 (not 0-255)."
            )
    # Validate alpha if present
    if len(rgba) == 4:
        if not (0.0 <= rgba[3] <= 1.0):
            raise ValueError(
                f"Alpha component = {rgba[3]} out of range [0.0, 1.0]. "
                "Use floats between 0.0 and 1.0."
            )
        return rgba  # Return [r, g, b, a]
    return rgba[:3]  # Return [r, g, b]


def _to_list(v: Vec3) -> List[float]:
    """Convert a vector to a Python list."""
    if isinstance(v, np.ndarray):
        v = v.tolist()
    else:
        v = list(v)
    if len(v) != 3:
        raise ValueError(f"Vec3 must have exactly 3 components, got {len(v)}")
    return v


def _normalize_quat(q: Quat) -> List[float]:
    """Normalize a quaternion to unit length."""
    if isinstance(q, np.ndarray):
        q = q.tolist()
    else:
        q = list(q)
    if len(q) != 4:
        raise ValueError(f"Quat must have exactly 4 components, got {len(q)}")
    # q = [qx, qy, qz, qw]
    norm = (q[0] ** 2 + q[1] ** 2 + q[2] ** 2 + q[3] ** 2) ** 0.5
    if norm < 1e-10:
        return [0.0, 0.0, 0.0, 1.0]  # Return identity if near-zero
    return [q[0] / norm, q[1] / norm, q[2] / norm, q[3] / norm]


def _to_quat_list(q: Quat) -> List[float]:
    """Convert a quaternion to a Python list without normalization."""
    if isinstance(q, np.ndarray):
        q = q.tolist()
    else:
        q = list(q)
    if len(q) != 4:
        raise ValueError(f"Quat must have exactly 4 components, got {len(q)}")
    return q


def _validate_positive_vec3(v: Vec3, name: str) -> List[float]:
    """Validate that a Vec3 has all positive components."""
    vals = _to_list(v)
    if len(vals) != 3:
        raise ValueError(f"{name} must have exactly 3 components, got {len(vals)}")
    if any(x <= 0 for x in vals):
        raise ValueError(f"{name} must have all positive values, got {vals}")
    return vals


def _validate_positive(value: float, name: str) -> float:
    """Validate that a scalar is positive."""
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


class Viz:
    """
    High-level FrameViz visualization context.

    Provides a synchronous API for creating primitives, uploading data, and
    handling user interaction events.
    """

    def __init__(
        self,
        client: FrameVizClient,
        scene_id: str,
        view_id: str,
        opened_via_tauri: bool = False,
        owns_view: bool = True,
        owns_scene: bool = False,
    ):
        self._client = client
        self._scene_id = scene_id
        self._view_id = view_id
        self._buffer_counter = 0
        self._opened_via_tauri = opened_via_tauri
        self._owns_view = owns_view
        self._owns_scene = owns_scene
        self._chunk_groups: Dict[str, List[str]] = {}  # group_handle -> chunk_handles
        self._chunk_parent: Dict[str, str] = {}  # chunk_handle -> group_handle
        self._chunk_offsets: Dict[str, int] = {}  # chunk_handle -> start index
        self._chunk_counter = 0
        self._warned_camera_pose_fallback = False
        self._warned_pick_config_fallback = False
        self._warned_pick_info_fallback = False

    @property
    def scene_id(self) -> str:
        return self._scene_id

    @property
    def view_id(self) -> str:
        return self._view_id

    def wait_for_viewer(self, timeout: float = 10.0) -> bool:
        """Wait for viewer_ready event for this view."""
        return _wait_for_viewer(self._client, self._view_id, timeout=timeout)

    @classmethod
    def _from_viewer(cls, client: FrameVizClient, view_id: str, scene_id: str) -> "Viz":
        """
        Internal: create a Viz instance from an existing view_id and scene_id.

        This is useful when you have a viewer that was created by other means
        (e.g., by a Tauri frontend) and you want to attach a Viz instance to it.

        Args:
            client: The FrameVizClient connection to use
            view_id: The view_id of the existing viewer
            scene_id: The scene_id to bind to

        Returns:
            A Viz instance connected to the specified viewer and scene

        Example:
            >>> client = FrameVizClient("ws://127.0.0.1:9527")
            >>> client.connect()
            >>> viz = Viz._from_viewer(client, "v_1", "s_1")
            >>> viz.add_box(pos=[0, 0, 0])
        """
        return cls(
            client,
            scene_id,
            view_id,
            opened_via_tauri=False,
            owns_view=False,
            owns_scene=False,
        )

    def _send_command(
        self, name: str, args: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send a raw command to the Host. For internal/custom commands."""
        return self._client.send_command(name, args or {})

    # ─────────────────────────────────────────────────────────────────────────
    # Primitives
    # ─────────────────────────────────────────────────────────────────────────

    def add_box(
        self,
        size: Vec3 = (1, 1, 1),
        pos: Optional[Vec3] = None,
        quat: Optional[Quat] = None,
        color: Color = "white",
        **node_options: Any,
    ) -> str:
        """Add a box primitive and return its handle."""
        validated_size = _validate_positive_vec3(size, "size")
        return self._add_primitive(
            "box",
            params={"size": validated_size},
            pos=pos,
            quat=quat,
            color=color,
            **node_options,
        )

    def add_sphere(
        self,
        radius: float = 0.5,
        pos: Optional[Vec3] = None,
        quat: Optional[Quat] = None,
        color: Color = "white",
        **node_options: Any,
    ) -> str:
        """Add a sphere primitive and return its handle."""
        _validate_positive(radius, "radius")
        return self._add_primitive(
            "sphere",
            params={"radius": radius},
            pos=pos,
            quat=quat,
            color=color,
            **node_options,
        )

    def add_cylinder(
        self,
        radius: float = 0.5,
        height: float = 1.0,
        pos: Optional[Vec3] = None,
        quat: Optional[Quat] = None,
        color: Color = "white",
        **node_options: Any,
    ) -> str:
        """Add a cylinder primitive and return its handle."""
        _validate_positive(radius, "radius")
        _validate_positive(height, "height")
        return self._add_primitive(
            "cylinder",
            params={"radius": radius, "height": height},
            pos=pos,
            quat=quat,
            color=color,
            **node_options,
        )

    def add_cone(
        self,
        radius: float = 0.5,
        height: float = 1.0,
        pos: Optional[Vec3] = None,
        quat: Optional[Quat] = None,
        color: Color = "white",
        **node_options: Any,
    ) -> str:
        """Add a cone primitive and return its handle."""
        _validate_positive(radius, "radius")
        _validate_positive(height, "height")
        return self._add_primitive(
            "cone",
            params={"radius": radius, "height": height},
            pos=pos,
            quat=quat,
            color=color,
            **node_options,
        )

    def add_arrow(
        self,
        start: Vec3 = (0, 0, 0),
        end: Vec3 = (0, 0, 1),
        radius: float = 0.05,
        color: Color = "white",
        **node_options: Any,
    ) -> str:
        """
        Add an arrow primitive from start to end.

        Args:
            start: Starting point [x, y, z]
            end: Ending point [x, y, z]
            radius: Arrow shaft radius
            color: Arrow color
        """
        _validate_positive(radius, "radius")
        params = {
            "radius": radius,
            "start": _to_list(start),
            "end": _to_list(end),
        }
        return self._add_primitive(
            "arrow", params=params, pos=None, quat=None, color=color, **node_options
        )

    def add_axes(
        self,
        length: float = 1.0,
        radius: float = 0.02,
        pos: Optional[Vec3] = None,
        quat: Optional[Quat] = None,
        **node_options: Any,
    ) -> str:
        """Add an axes indicator (X=red, Y=green, Z=blue)."""
        _validate_positive(length, "length")
        _validate_positive(radius, "radius")
        return self._add_primitive(
            "axes",
            params={"length": length, "radius": radius},
            pos=pos,
            quat=quat,
            color="white",
            **node_options,
        )

    def add_plane(
        self,
        width: float = 1.0,
        height: float = 1.0,
        pos: Optional[Vec3] = None,
        quat: Optional[Quat] = None,
        color: Color = "gray",
        **node_options: Any,
    ) -> str:
        """Add a plane primitive."""
        return self._add_primitive(
            "plane",
            params={"width": width, "height": height},
            pos=pos,
            quat=quat,
            color=color,
            **node_options,
        )

    def _add_primitive(
        self,
        ptype: str,
        params: Dict[str, Any],
        pos: Optional[Vec3],
        quat: Optional[Quat],
        color: Color,
        **node_options: Any,
    ) -> str:
        """Internal helper to add a primitive."""
        # Normalize color - _normalize_color already handles RGBA correctly
        color_val = _normalize_color(color)

        result = self._client.send_command(
            "add_primitive",
            {
                "scene_id": self._scene_id,
                "type": ptype,
                **node_arguments(node_options, pos=pos, quat=quat, default_pose=True),
                "color": color_val,
                "params": params,
            },
        )
        return result.get("handle", "")

    # ─────────────────────────────────────────────────────────────────────────
    # Points / Lines / Mesh (with BufferRef)
    # ─────────────────────────────────────────────────────────────────────────

    def add_points(
        self,
        positions: np.ndarray,
        colors: Optional[np.ndarray] = None,
        size: float = 1.0,
        color: Optional[Color] = None,
        **node_options: Any,
    ) -> str:
        """
        Add a point cloud.

        positions: numpy array of shape (N, 3), dtype float32
        colors: optional numpy array of shape (N, 3), float in [0, 1] (per-point).
                If a string or a 1D array with 3/4 elements is provided, it is
                treated as a uniform color.
        color: optional uniform color (RGB/RGBA in [0, 1]), mutually exclusive with colors
        size: point size in pixels
        Large point clouds retain a single ID. Scene keywords include parent, name, tags and pose.
        """
        positions = np.ascontiguousarray(positions, dtype=np.float32)
        if positions.ndim != 2 or positions.shape[1] != 3:
            raise ValueError("positions must have shape (N, 3)")
        n_points = positions.shape[0]
        if colors is not None and color is not None:
            raise ValueError("color and colors are mutually exclusive for add_points")

        colors_u8: Optional[np.ndarray] = None
        uniform_color: Optional[Color] = None
        if colors is not None:
            if isinstance(colors, str):
                uniform_color = _normalize_color(colors)
            else:
                colors_arr = np.asarray(colors)
                if colors_arr.ndim == 1 and colors_arr.shape[0] in (3, 4):
                    uniform_color = _normalize_color(colors_arr.tolist())
                elif colors_arr.ndim == 2 and colors_arr.shape[1] == 3:
                    colors_f = colors_arr.astype(np.float32)
                    if colors_f.size:
                        min_val = float(np.min(colors_f))
                        max_val = float(np.max(colors_f))
                        if min_val < 0.0 or max_val > 1.0:
                            raise ValueError("colors must be in [0, 1]")
                    colors_u8 = np.rint(np.clip(colors_f, 0.0, 1.0) * 255.0).astype(np.uint8)
                else:
                    raise ValueError(
                        "colors must be a (N, 3) array or a single RGB/RGBA color"
                    )
        if color is not None:
            uniform_color = _normalize_color(color)

        if colors_u8 is not None and colors_u8.shape[0] != n_points:
            raise ValueError("colors must match point count")

        args = {"scene_id": self._scene_id, "size": size, **node_arguments(node_options)}
        if uniform_color is not None:
            args["color"] = uniform_color

        with self._geometry_uploads() as upload:
            def upload_part(start: int, end: int) -> Dict[str, Any]:
                shape = [end - start, 3]
                part = {"positions": upload(positions[start:end], "f32", shape)}
                if colors_u8 is not None:
                    part["colors"] = upload(colors_u8[start:end], "u8", shape)
                return part

            chunk_size = 500_000
            if n_points > chunk_size:
                args["chunks"] = [
                    upload_part(start, min(start + chunk_size, n_points))
                    for start in range(0, n_points, chunk_size)
                ]
            else:
                args.update(upload_part(0, n_points))
            return self._client.send_command("add_points", args)["handle"]

    def _register_chunk_group(self, group_handle: str, chunk_handles: List[str]) -> None:
        self._chunk_groups[group_handle] = chunk_handles
        for chunk_handle in chunk_handles:
            self._chunk_parent[chunk_handle] = group_handle

    def _unregister_chunk_handle(self, chunk_handle: str) -> None:
        group_handle = self._chunk_parent.pop(chunk_handle, None)
        self._chunk_offsets.pop(chunk_handle, None)
        if not group_handle:
            return
        handles = self._chunk_groups.get(group_handle, [])
        try:
            handles.remove(chunk_handle)
        except ValueError:
            return
        if not handles:
            self._chunk_groups.pop(group_handle, None)

    def _resolve_group_target(self, handle: str) -> Optional[str]:
        if handle in self._chunk_groups:
            handles = self._chunk_groups.get(handle, [])
            return handles[0] if handles else None
        return handle

    def _map_event_handle(self, handle: Optional[str]) -> Optional[str]:
        if handle is None:
            return None
        return self._chunk_parent.get(handle, handle)

    def _map_event_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        handle = data.get("handle")
        mapped_handle: Optional[str] = None
        mapped_point_index: Optional[int] = None
        if isinstance(handle, str):
            if handle in self._chunk_offsets and data.get("point_index") is not None:
                try:
                    idx = int(data.get("point_index"))
                    mapped_point_index = idx + self._chunk_offsets[handle]
                except (TypeError, ValueError):
                    mapped_point_index = None
            mapped_handle = self._map_event_handle(handle)
        obj_handle = data.get("object_handle")
        mapped_object_handle: Optional[str] = None
        if isinstance(obj_handle, str):
            mapped_object_handle = self._map_event_handle(obj_handle)

        needs_update = False
        if mapped_point_index is not None:
            needs_update = True
        if mapped_handle is not None and mapped_handle != handle:
            needs_update = True
        if mapped_object_handle is not None and mapped_object_handle != obj_handle:
            needs_update = True

        if not needs_update:
            return data

        mapped = dict(data)
        if mapped_point_index is not None:
            mapped["point_index"] = mapped_point_index
        if mapped_handle is not None and mapped_handle != handle:
            mapped["handle"] = mapped_handle
        if mapped_object_handle is not None and mapped_object_handle != obj_handle:
            mapped["object_handle"] = mapped_object_handle
        return mapped

    def add_lines(
        self,
        positions: np.ndarray,
        indices: Optional[np.ndarray] = None,
        width: float = 1.0,
        color: Color = "white",
        **node_options: Any,
    ) -> str:
        """
        Add lines to the scene.

        positions: numpy array of shape (N, 3), dtype float32
        indices: optional numpy array of shape (M, 2), dtype uint32
        """
        scene_node = node_arguments(node_options)
        with self._geometry_uploads() as upload:
            positions = np.ascontiguousarray(positions, dtype=np.float32)
            n_verts = positions.shape[0]
            pos_buffer = upload(positions, "f32", [n_verts, 3])

            args: Dict[str, Any] = {
                "scene_id": self._scene_id,
                "positions": pos_buffer,
                "width": width,
                "color": _normalize_color(color),
            }

            if indices is not None:
                indices = np.ascontiguousarray(indices, dtype=np.uint32)
                m = indices.shape[0]
                args["indices"] = upload(indices, "u32", [m, 2])

            args.update(scene_node)
            result = self._client.send_command("add_lines", args)
            return result.get("handle", "")

    def add_mesh(
        self,
        vertices: np.ndarray,
        faces: Union[np.ndarray, Dict[str, np.ndarray]],
        normals: Optional[np.ndarray] = None,
        colors: Optional[np.ndarray] = None,
        color: Optional[Color] = None,
        faces_format: str = "tri",
        alpha: Optional[float] = None,
        wireframe: bool = False,
        smooth_shading: bool = True,
        **node_options: Any,
    ) -> str:
        """
        Add a mesh (triangle or polygon faces).

        Args:
            vertices: (V, 3) float32 vertex positions.
            faces:
              - faces_format="tri": (F, 3) uint32 triangle indices.
              - faces_format="poly": dict with:
                * counts: (F,) uint32, number of vertices per face.
                * indices: (K,) uint32, flattened polygon indices.
            normals: Optional (V, 3) float32 vertex normals.
            colors: Optional (V, 3) or (F, 3) float colors in [0, 1] for per-vertex/per-face colors.
            color: Optional uniform color as RGB or RGBA tuple/list (mutually exclusive with colors).
            faces_format: "tri" or "poly".
            alpha: Optional global opacity (0.0=transparent, 1.0=opaque, default=1.0).
            wireframe: Whether to show edge lines (default=False).
            smooth_shading: Whether to use smooth shading (default=True).
                Set to False for a faceted flat-shading look.

        Notes:
            - Polygon faces are triangulated on the viewer side.
            - Use "tri" if your mesh is already triangulated.
            - Set alpha < 1.0 for transparent meshes.
            - Set wireframe=True to show black semi-transparent edge lines.
            - Use color for uniform coloring (like add_box), or colors for per-vertex/per-face coloring.
            - color and colors are mutually exclusive.
            - If color is RGBA and alpha is not provided, color[3] is used as alpha.
            - If alpha is provided, it always takes precedence over color[3].
        """
        scene_node = node_arguments(node_options)
        with self._geometry_uploads() as upload:
            vertices = np.ascontiguousarray(vertices, dtype=np.float32)
            v_count = vertices.shape[0]
            face_count = 0

            args: Dict[str, Any] = {
                "scene_id": self._scene_id,
                "vertices": upload(vertices, "f32", [v_count, 3]),
            }
            faces_format = faces_format.lower().strip()
            if faces_format == "tri":
                faces = np.ascontiguousarray(faces, dtype=np.uint32)
                f_count = faces.shape[0]
                face_count = f_count
                args["faces"] = upload(faces, "u32", [f_count, 3])
            elif faces_format == "poly":
                if not isinstance(faces, dict) or "counts" not in faces or "indices" not in faces:
                    raise ValueError("faces must be a dict with 'counts' and 'indices' for faces_format='poly'")
                counts = np.ascontiguousarray(faces["counts"], dtype=np.uint32)
                indices = np.ascontiguousarray(faces["indices"], dtype=np.uint32)
                face_count = counts.shape[0]
                args["faces"] = {
                    "counts": upload(counts, "u32", [counts.shape[0]]),
                    "indices": upload(indices, "u32", [indices.shape[0]]),
                }
                args["faces_format"] = "poly"
            else:
                raise ValueError("faces_format must be 'tri' or 'poly'")

            if normals is not None:
                normals = np.ascontiguousarray(normals, dtype=np.float32)
                args["normals"] = upload(normals, "f32", [v_count, 3])

            # Check mutual exclusivity of color and colors
            if colors is not None and color is not None:
                raise ValueError(
                    "color and colors parameters are mutually exclusive. "
                    "Use color for uniform color or colors for per-vertex/per-face colors."
                )

            # Handle uniform color parameter
            color_alpha: Optional[float] = None
            if color is not None:
                normalized = _normalize_color(color)
                # Only pass RGB, alpha is handled by the separate alpha parameter
                args["color"] = normalized[:3]
                if len(normalized) == 4:
                    color_alpha = float(normalized[3])

            if colors is not None:
                colors = np.ascontiguousarray(colors)
                if colors.ndim != 2 or colors.shape[1] != 3:
                    raise ValueError("colors must be a (N, 3) array")
                if not np.issubdtype(colors.dtype, np.floating):
                    raise ValueError("colors must be float values in [0, 1]")
                if colors.size:
                    min_val = float(np.min(colors))
                    max_val = float(np.max(colors))
                    if min_val < 0.0 or max_val > 1.0:
                        raise ValueError("colors must be in [0, 1]")
                colors_u8 = np.rint(np.clip(colors, 0.0, 1.0) * 255.0).astype(np.uint8)
                color_count = colors_u8.shape[0]
                if color_count == v_count:
                    color_shape = [v_count, 3]
                elif face_count > 0 and color_count == face_count:
                    color_shape = [face_count, 3]
                else:
                    raise ValueError("colors must match vertex count or face count")
                args["colors"] = upload(colors_u8, "u8", color_shape)

            # Add alpha parameter (alpha argument has priority over color[3])
            alpha_param: Optional[float] = None
            if alpha is not None:
                if not isinstance(alpha, (int, float)):
                    raise TypeError("alpha must be a number")
                if not 0.0 <= alpha <= 1.0:
                    raise ValueError("alpha must be in [0.0, 1.0]")
                alpha_param = float(alpha)
            elif color_alpha is not None:
                alpha_param = float(color_alpha)
            if alpha_param is not None:
                args["alpha"] = alpha_param

            # Add wireframe parameter (only send if True to reduce bandwidth)
            if wireframe:
                args["wireframe"] = wireframe

            if isinstance(smooth_shading, np.bool_):
                smooth_shading = bool(smooth_shading)
            elif not isinstance(smooth_shading, bool):
                raise TypeError("smooth_shading must be a boolean")
            # Core defaults to smooth shading; only send when explicitly disabling.
            if not smooth_shading:
                args["smooth_shading"] = smooth_shading

            args.update(scene_node)
            result = self._client.send_command("add_mesh", args)
            return result.get("handle", "")

    def load_mesh(
        self,
        url: str,
        pos: Optional[Vec3] = None,
        quat: Optional[Quat] = None,
        scale: Optional[Vec3] = None,
        color: Optional[Color] = None,
        **node_options: Any,
    ) -> str:
        """
        Load a mesh from a URL (DAE or STL file).

        The URL can be relative to the web server root or an absolute URL.
        For local files served via http.server, use paths like '/assets/model.dae'.

        Args:
            url: URL to the mesh file (.dae or .stl)
            pos: Position [x, y, z]
            quat: Quaternion [qx, qy, qz, qw] - auto-normalized
            scale: Scale factors [sx, sy, sz]
            color: Optional color override (RGB or RGBA)

        Returns:
            Handle to the loaded mesh object.
        """
        args: Dict[str, Any] = {
            "scene_id": self._scene_id,
            "url": url,
            **node_arguments(node_options, pos=pos, quat=quat, scale=scale, default_pose=True),
        }
        if color is not None:
            normalized = _normalize_color(color)
            args["color"] = normalized[:3]

        result = self._client.send_command("load_mesh", args)
        return result.get("handle", "")

    def add_instances(
        self,
        type: str,
        positions: np.ndarray,
        quats: Optional[np.ndarray] = None,
        scales: Optional[np.ndarray] = None,
        colors: Optional[np.ndarray] = None,
        color: Optional[Color] = None,
        alpha: Optional[float] = None,
        size: Optional[Vec3] = None,
        params: Optional[Dict[str, Any]] = None,
        **node_options: Any,
    ) -> str:
        """
        Add instanced primitives for large batches (e.g., Octomap).

        Supported types:
            - "box": params.size = [sx, sy, sz]
            - "sphere": params.radius
            - "axes": params.length, params.radius

        Args:
            positions: (N, 3) float32 positions.
            quats: Optional (N, 4) float32 orientations [qx, qy, qz, qw].
            scales: Optional (N, 3) float32 per-instance scales.
            colors: Optional (N, 3) per-instance colors, float in [0, 1].
            color: Optional uniform color (RGB only). Mutually exclusive with colors.
            alpha: Optional global alpha [0..1] applied to all instances.
            size: Convenience size for box instances (overrides params["size"]).
            params: Primitive params dict; see supported types above.

        Notes:
            - color and colors are mutually exclusive.
            - Alpha is a global transparency; per-instance alpha is not supported.
        """
        scene_node = node_arguments(node_options)
        with self._geometry_uploads() as upload:
            positions = np.ascontiguousarray(positions, dtype=np.float32)
            n = positions.shape[0]
            if colors is not None and color is not None:
                raise ValueError("color and colors are mutually exclusive for add_instances")
            args: Dict[str, Any] = {
                "scene_id": self._scene_id,
                "type": type,
                "positions": upload(positions, "f32", [n, 3]),
                "params": params or {},
            }
            if size is not None:
                args["params"].setdefault("size", _to_list(size))
            if quats is not None:
                quats = np.ascontiguousarray(quats, dtype=np.float32)
                args["quats"] = upload(quats, "f32", [n, 4])
            if scales is not None:
                scales = np.ascontiguousarray(scales, dtype=np.float32)
                args["scales"] = upload(scales, "f32", [n, 3])
            if colors is not None:
                colors = np.asarray(colors, dtype=np.float32)
                if colors.ndim != 2 or colors.shape[1] != 3:
                    raise ValueError("colors must be a (N, 3) array")
                if colors.shape[0] != n:
                    raise ValueError("colors must match instance count")
                if colors.size:
                    min_val = float(colors.min())
                    max_val = float(colors.max())
                    if min_val < 0.0 or max_val > 1.0:
                        raise ValueError("colors must be in [0, 1]")
                colors_u8 = np.rint(np.clip(colors, 0.0, 1.0) * 255.0).astype(np.uint8)
                args["colors"] = upload(colors_u8, "u8", [n, 3])
            if color is not None:
                normalized = _normalize_color(color)
                args["color"] = normalized[:3]
            if alpha is not None:
                args["alpha"] = float(alpha)
            args.update(scene_node)
            result = self._client.send_command("add_instances", args)
            return result.get("handle", "")

    def update_instances(
        self,
        handle: str,
        positions: Optional[np.ndarray] = None,
        quats: Optional[np.ndarray] = None,
        scales: Optional[np.ndarray] = None,
        colors: Optional[np.ndarray] = None,
        color: Optional[Color] = None,
        alpha: Optional[float] = None,
    ) -> None:
        """
        Update an existing instanced object's transforms and/or colors.

        This is a full-replacement update - all provided arrays replace the
        existing data entirely. Arrays not provided are left unchanged.

        Args:
            handle: Handle returned by add_instances().
            positions: (N, 3) float32 new positions. May change instance count.
            quats: (N, 4) float32 new orientations [qx, qy, qz, qw].
            scales: (N, 3) float32 new per-instance scales.
            colors: (N, 3) per-instance colors, float in [0, 1].
            color: Optional uniform color (RGB only). Mutually exclusive with colors.
            alpha: Optional global alpha [0..1].

        Typical use case:
            Octomap/occupancy grid updates where the entire grid is
            refreshed every few seconds.
        """
        args: Dict[str, Any] = {"handle": handle}
        if colors is not None and color is not None:
            raise ValueError("color and colors are mutually exclusive for update_instances")

        if positions is not None:
            positions = np.ascontiguousarray(positions, dtype=np.float32)
            n = positions.shape[0]
            args["positions"] = self._upload_buffer(positions, "f32", [n, 3])

            if quats is not None:
                quats = np.ascontiguousarray(quats, dtype=np.float32)
                args["quats"] = self._upload_buffer(quats, "f32", [n, 4])
            if scales is not None:
                scales = np.ascontiguousarray(scales, dtype=np.float32)
                args["scales"] = self._upload_buffer(scales, "f32", [n, 3])
            if colors is not None:
                colors = np.asarray(colors, dtype=np.float32)
                if colors.ndim != 2 or colors.shape[1] != 3:
                    raise ValueError("colors must be a (N, 3) array")
                if colors.shape[0] != n:
                    raise ValueError("colors must match instance count")
                if colors.size:
                    min_val = float(colors.min())
                    max_val = float(colors.max())
                    if min_val < 0.0 or max_val > 1.0:
                        raise ValueError("colors must be in [0, 1]")
                colors_u8 = np.rint(np.clip(colors, 0.0, 1.0) * 255.0).astype(np.uint8)
                args["colors"] = self._upload_buffer(colors_u8, "u8", [n, 3])
        else:
            # Even without positions, we can update colors/quats/scales
            # But we need to know the instance count - for now just pass through
            if quats is not None:
                quats = np.ascontiguousarray(quats, dtype=np.float32)
                n = quats.shape[0]
                args["quats"] = self._upload_buffer(quats, "f32", [n, 4])
            if scales is not None:
                scales = np.ascontiguousarray(scales, dtype=np.float32)
                n = scales.shape[0]
                args["scales"] = self._upload_buffer(scales, "f32", [n, 3])
            if colors is not None:
                colors = np.asarray(colors, dtype=np.float32)
                if colors.ndim != 2 or colors.shape[1] != 3:
                    raise ValueError("colors must be a (N, 3) array")
                n = colors.shape[0]
                if colors.size:
                    min_val = float(colors.min())
                    max_val = float(colors.max())
                    if min_val < 0.0 or max_val > 1.0:
                        raise ValueError("colors must be in [0, 1]")
                colors_u8 = np.rint(np.clip(colors, 0.0, 1.0) * 255.0).astype(np.uint8)
                args["colors"] = self._upload_buffer(colors_u8, "u8", [n, 3])

        if color is not None:
            normalized = _normalize_color(color)
            args["color"] = normalized[:3]
        if alpha is not None:
            args["alpha"] = float(alpha)

        self._client.send_command("update_instances", args)

    def _upload_buffer(
        self, data: np.ndarray, dtype: str, shape: List[int]
    ) -> Dict[str, Any]:
        """
        Create a buffer on the Host, upload the data, and return a BufferRef.

        Uses bounded WebSocket chunks for every endpoint.
        """
        raw_bytes = data.tobytes()
        size_bytes = len(raw_bytes)

        # Shared-memory mapping requires a negotiated, bounded ownership contract.
        # Until that protocol exists, every endpoint uses the checked chunk path.
        return self._upload_buffer_ws(raw_bytes, size_bytes, dtype, shape)

    def _is_localhost(self) -> bool:
        """Check if the Host is running on localhost."""
        from urllib.parse import urlsplit
        host = urlsplit(getattr(self._client, "url", "")).hostname
        return host in ("127.0.0.1", "localhost", "::1")

    def _upload_buffer_shm(
        self, raw_bytes: bytes, dtype: str, shape: List[int]
    ) -> Dict[str, Any]:
        """
        Upload buffer via shared memory (local optimization).
        Zero-copy transfer for large data.
        """
        from multiprocessing import shared_memory

        size_bytes = len(raw_bytes)

        # Create shared memory and write data
        shm = shared_memory.SharedMemory(create=True, size=size_bytes)
        try:
            shm.buf[:size_bytes] = raw_bytes

            # Send command to Host to read from shared memory
            result = self._client.send_command(
                "load_buffer_shm",
                {
                    "name": shm.name,
                    "size": size_bytes,
                    "dtype": dtype,
                    "shape": shape,
                },
            )
            return {"buffer_id": result["buffer_id"], "dtype": dtype, "shape": shape}
        finally:
            # Clean up shared memory after Host has read it
            shm.close()
            shm.unlink()

    def _upload_buffer_ws(
        self, raw_bytes: bytes, size_bytes: int, dtype: str, shape: List[int]
    ) -> Dict[str, Any]:
        """
        Upload buffer via WebSocket chunks (fallback for remote/small data).
        """
        # 1. Create the buffer
        result = self._client.send_command(
            "create_buffer",
            {"size_bytes": size_bytes, "dtype": dtype, "shape": shape},
        )
        buffer_id = result["buffer_id"]

        # 2. Upload in chunks (16MB per chunk to stay under WebSocket limits)
        CHUNK_SIZE = 16 * 1024 * 1024  # 16MB
        try:
            offset = 0
            while offset < size_bytes:
                chunk_end = min(offset + CHUNK_SIZE, size_bytes)
                chunk_bytes = chunk_end - offset
                chunk_data = raw_bytes[offset:chunk_end]

                self._client.send_command_with_binary(
                    "upload_buffer_chunk",
                    {
                        "buffer_id": buffer_id,
                        "offset_bytes": offset,
                        "chunk_bytes": chunk_bytes,
                    },
                    chunk_data,
                )
                offset = chunk_end

        except BaseException:
            with suppress(Exception):
                self._free_buffer(buffer_id)
            raise

        return {"buffer_id": buffer_id, "dtype": dtype, "shape": shape}

    @contextmanager
    def _geometry_uploads(self):
        allocated = []

        def upload(array, dtype, shape):
            ref = self._upload_buffer(array, dtype, shape)
            allocated.append(ref["buffer_id"])
            return ref

        try:
            yield upload
        except BaseException:
            for buffer_id in allocated:
                with suppress(Exception):
                    self._free_buffer(buffer_id)
            raise

    def _free_buffer(self, buffer_id: str) -> None:
        """Free a buffer on the Host side."""
        self._client.send_command("free_buffer", {"buffer_id": buffer_id})

    # ─────────────────────────────────────────────────────────────────────────
    # Object manipulation
    # ─────────────────────────────────────────────────────────────────────────

    def add_node(
        self, *, parent=None, name=None, tags=None, position=None, quaternion=None, pose=None
    ) -> str:
        """Create a rigid scene node without drawable geometry."""
        args = node_arguments({
            "parent": parent, "name": name, "tags": tags,
            "position": position, "quaternion": quaternion, "pose": pose,
        })
        return self._client.send_command("add_node", {"scene_id": self._scene_id, **args})["handle"]

    def set_parent(self, handle: str, parent: Optional[str], *, local_transform=None) -> None:
        """Reparent a node. The default preserves its current world pose."""
        args = {"handle": handle, "parent": parent, "scene_id": self._scene_id}
        if local_transform is not None:
            args["local_transform"] = rigid_pose(local_transform)
        self._client.send_command("set_parent", args)

    def set_object_metadata(self, handle: str, *, name=None, tags=None) -> None:
        """Update the display name and tags supplied by the application."""
        args = node_arguments({"name": name, "tags": tags})
        self._client.send_command("set_object_metadata", {"handle": handle, "scene_id": self._scene_id, **args})

    def set_geometry_scale(self, handle: str, scale: Vec3) -> None:
        """Resize this object's own geometry in its node coordinates."""
        self._client.send_command("set_geometry_scale", {
            "handle": handle, "scene_id": self._scene_id, "geometry_scale": components(scale, 3, "scale"),
        })

    def set_transform(
        self,
        handle: str,
        pos: Optional[Vec3] = None,
        quat: Optional[Quat] = None,
        scale: Optional[Vec3] = None,
        *,
        position: Optional[Vec3] = None,
        quaternion: Optional[Quat] = None,
        pose=None,
        geometry_scale: Optional[Vec3] = None,
    ) -> None:
        """Set a local rigid pose. The legacy scale argument resizes only the drawable."""
        fields = node_arguments(
            {"position": position, "quaternion": quaternion, "pose": pose, "geometry_scale": geometry_scale},
            pos=pos, quat=quat, scale=scale, default_pose=True,
        )
        if handle in self._chunk_groups:
            items = [{"handle": chunk, **fields} for chunk in self._chunk_groups[handle]]
            if items:
                self._client.send_command("set_object_transforms", {"items": items, "scene_id": self._scene_id})
            return
        self._client.send_command("set_transform", {"handle": handle, "scene_id": self._scene_id, **fields})

    def set_object_transforms(self, items: List[Dict[str, Any]]) -> None:
        """Apply a batch of local rigid poses together. Each item contains a handle and pose."""
        payload = []
        for item in items:
            handle = item.get("handle")
            if not isinstance(handle, str) or not handle:
                raise ValueError("Each transform requires a handle")
            pose = item.get("pose")
            scale = None
            if isinstance(pose, dict):
                pose = dict(pose)
                scale = pose.pop("scale", None)
            fields = node_arguments({
                "pose": pose, "position": item.get("position"), "quaternion": item.get("quaternion"),
                "geometry_scale": item.get("geometry_scale"),
            }, scale=scale, default_pose=True)
            payload.extend({"handle": target, **fields} for target in self._chunk_groups.get(handle, [handle]))
        if payload:
            self._client.send_command("set_object_transforms", {"items": payload, "scene_id": self._scene_id})

    def set_color(self, handle: str, color: Color) -> None:
        """Set the color of an object (supports RGBA for transparency).

        Sets both RGB color and optionally the alpha (transparency) channel.
        If alpha is not provided, the object remains fully opaque (alpha=1.0).

        Args:
            handle: Object handle
            color: Color specification:
                - RGB: [r, g, b] or color name ("red", "blue", etc.)
                    Sets color, keeps current transparency (or opaque if never set)
                - RGBA: [r, g, b, a] - Sets both color and transparency
                    where alpha is 0.0 (fully transparent) to 1.0 (fully opaque)

        Note:
            For meshes with per-vertex/per-face colors (created with `colors` parameter),
            calling this method will convert the mesh to use a uniform color by
            recreating the geometry without vertex colors. This is a one-time conversion.

        Examples:
            >>> viz.set_color(ball, [1, 0, 0])      # Red, keeps current alpha
            >>> viz.set_color(ball, [1, 0, 0, 0.5])  # Red, half-transparent
            >>> viz.set_color(ball, "blue")          # Blue, keeps current alpha
        """
        rgba = _normalize_color(color)
        # Ensure we always have alpha for the server
        if len(rgba) < 4:
            rgba = rgba + [1.0]  # Add alpha=1.0 (opaque) if not present

        if handle in self._chunk_groups:
            items = []
            for chunk_handle in self._chunk_groups.get(handle, []):
                items.append({"handle": chunk_handle, "rgba": rgba})
            if items:
                self._client.send_command(
                    "set_object_colors",
                    {"items": items, "scene_id": self._scene_id},
                )
            return
        self._client.send_command(
            "set_color",
            {"handle": handle, "rgba": rgba, "scene_id": self._scene_id},
        )

    def set_alpha(self, handle: str, alpha: float) -> None:
        """Set the opacity (transparency) of an object without changing color.

        Args:
            handle: Object handle
            alpha: Opacity value (0.0=fully transparent, 1.0=fully opaque)

        Raises:
            TypeError: If alpha is not a number
            ValueError: If alpha is not in [0.0, 1.0]

        Note:
            Works for all objects, including meshes with per-vertex/per-face colors.

        Examples:
            >>> viz.set_alpha(ball, 0.5)   # 50% transparent
            >>> viz.set_alpha(ball, 0.0)   # Fully transparent (invisible)
            >>> viz.set_alpha(ball, 1.0)   # Fully opaque (default)
        """
        if not isinstance(alpha, (int, float)):
            raise TypeError("alpha must be a number")
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be in [0.0, 1.0]")

        if handle in self._chunk_groups:
            items = []
            for chunk_handle in self._chunk_groups.get(handle, []):
                items.append({"handle": chunk_handle, "alpha": float(alpha)})
            if items:
                self._client.send_command(
                    "set_object_alphas",
                    {"items": items, "scene_id": self._scene_id},
                )
            return
        self._client.send_command(
            "set_alpha",
            {"handle": handle, "alpha": float(alpha), "scene_id": self._scene_id},
        )

    def set_visible(self, handle: str, visible: bool) -> None:
        """Set visibility of an object."""
        if handle in self._chunk_groups:
            items = []
            for chunk_handle in self._chunk_groups.get(handle, []):
                items.append({"handle": chunk_handle, "visible": visible})
            if items:
                self._client.send_command(
                    "set_object_visibilities",
                    {"items": items, "scene_id": self._scene_id},
                )
            return
        self._client.send_command(
            "set_visible",
            {"handle": handle, "visible": visible, "scene_id": self._scene_id},
        )

    def remove(self, handle: str) -> None:
        """Remove any object (primitive, mesh, text, etc.) from the scene.

        This handles both scene objects, view overlays, and chunk groups from add_points.
        """
        # Check if this is a chunk group handle
        if handle in self._chunk_groups:
            for chunk_handle in self._chunk_groups[handle]:
                try:
                    self._client.send_command(
                        "remove_object",
                        {"handle": chunk_handle, "scene_id": self._scene_id},
                    )
                except Exception:
                    pass  # Chunk may already be removed
            for chunk_handle in self._chunk_groups[handle]:
                self._chunk_parent.pop(chunk_handle, None)
                self._chunk_offsets.pop(chunk_handle, None)
            del self._chunk_groups[handle]
            return
        if handle in self._chunk_parent:
            self._unregister_chunk_handle(handle)

        # Try to remove from scene objects first.
        try:
            self._client.send_command(
                "remove_object",
                {"handle": handle, "scene_id": self._scene_id},
            )
            return
        except Exception:
            # If that fails, it might be a view overlay - try view scope.
            try:
                self._client.send_command(
                    "remove_object",
                    {"handle": handle, "view_id": self._view_id},
                )
            except Exception:
                pass  # Object may already be removed

    def remove_objects(self, handles: List[str]) -> None:
        """Remove multiple objects in a single command."""
        if not handles:
            return
        expanded: List[str] = []
        for handle in handles:
            if handle in self._chunk_groups:
                for chunk_handle in self._chunk_groups.get(handle, []):
                    expanded.append(chunk_handle)
                    self._chunk_parent.pop(chunk_handle, None)
                    self._chunk_offsets.pop(chunk_handle, None)
                del self._chunk_groups[handle]
            elif handle in self._chunk_parent:
                self._unregister_chunk_handle(handle)
                expanded.append(handle)
            else:
                expanded.append(handle)
        if not expanded:
            return
        self._client.send_command(
            "remove_objects",
            {"handles": expanded, "scene_id": self._scene_id},
        )

    def clone_object(self, handle: str) -> str:
        """Clone an object once and return the new handle."""
        if handle in self._chunk_groups:
            self._chunk_counter += 1
            group_handle = f"chunk_group_{self._chunk_counter}"
            new_handles: List[str] = []
            for chunk_handle in self._chunk_groups.get(handle, []):
                result = self._client.send_command(
                    "clone_object",
                    {"handle": chunk_handle, "group_id": group_handle},
                )
                new_handle = result.get("handle", "")
                if new_handle:
                    new_handles.append(new_handle)
            if not new_handles:
                return ""
            self._register_chunk_group(group_handle, new_handles)
            return group_handle
        result = self._client.send_command("clone_object", {"handle": handle})
        return result.get("handle", "")

    def is_object_alive(self, handle: str) -> bool:
        """Check if a handle exists in the scene."""
        if handle in self._chunk_groups:
            for chunk_handle in self._chunk_groups.get(handle, []):
                result = self._client.send_command(
                    "is_object_alive", {"handle": chunk_handle}
                )
                if not bool(result.get("alive", False)):
                    return False
            return True
        result = self._client.send_command("is_object_alive", {"handle": handle})
        return bool(result.get("alive", False))

    # ─────────────────────────────────────────────────────────────────────────
    # Get functions
    # ─────────────────────────────────────────────────────────────────────────

    def get_transform(self, handle: str, space: str = "local", *, matrix: bool = False) -> Dict[str, Any]:
        """Get the local or world rigid pose and optional column-major matrix.

        position and quaternion have compatibility aliases pos and quat.
        geometry_scale describes the object's own drawable size.
        """
        if space not in {"local", "world"}:
            raise ValueError("space must be local or world")
        target = self._resolve_group_target(handle)
        if not target:
            raise RuntimeError(f"Object not found: {handle}")
        result = self._client.send_command(
            "get_transform",
            {"handle": target, "scene_id": self._scene_id, "space": space, "matrix": matrix},
        )
        pose = result.get("pose", {"pos": [0, 0, 0], "quat": [0, 0, 0, 1]})
        if not isinstance(pose, dict):
            raise RuntimeError("Invalid get_transform response: expected pose object.")
        try:
            pos = _to_list(pose.get("pos", [0, 0, 0]))
        except ValueError as exc:
            raise RuntimeError(
                "Invalid get_transform response: pos must have 3 components."
            ) from exc
        try:
            quat = _to_quat_list(pose.get("quat", [0, 0, 0, 1]))
        except ValueError as exc:
            raise RuntimeError(
                "Invalid get_transform response: quat must have 4 components."
            ) from exc
        result_pose: Dict[str, Any] = {"position": pos, "quaternion": quat, "pos": pos, "quat": quat}
        if "scale" in pose and pose["scale"] is not None:
            try:
                result_pose["scale"] = _to_list(pose["scale"])
            except ValueError as exc:
                raise RuntimeError(
                    "Invalid get_transform response: scale must have 3 components."
                ) from exc
        if result.get("geometry_scale") is not None:
            result_pose["geometry_scale"] = components(result["geometry_scale"], 3, "geometry_scale")
        if matrix:
            result_pose["matrix"] = components(result.get("matrix"), 16, "matrix")
        return result_pose

    def get_color(self, handle: str) -> Optional[List[float]]:
        """Get the color of an object.

        Returns:
            RGBA as [r, g, b, a] with values in [0, 1],
            or None if the object uses per-vertex/per-face/per-point colors.
        """
        target = self._resolve_group_target(handle)
        if not target:
            raise RuntimeError(f"Object not found: {handle}")
        result = self._client.send_command("get_color", {"handle": target})
        if result.get("has_vertex_colors", False):
            return None
        rgba = result.get("rgba")
        if not isinstance(rgba, list) or len(rgba) != 4:
            raise RuntimeError(
                "Invalid get_color response: expected RGBA list of length 4."
            )
        return rgba

    def get_alpha(self, handle: str) -> float:
        """Get the alpha (transparency) value of an object.

        Args:
            handle: Object handle

        Returns:
            Alpha value (0.0=fully transparent, 1.0=fully opaque)

        Note:
            Works for all objects, including meshes with vertex colors.
        """
        target = self._resolve_group_target(handle)
        if not target:
            raise RuntimeError(f"Object not found: {handle}")
        result = self._client.send_command("get_alpha", {"handle": target})
        return result.get("alpha", 1.0)

    def get_visible(self, handle: str) -> bool:
        """Get visibility of an object.

        Returns:
            True if visible, False otherwise.
        """
        target = self._resolve_group_target(handle)
        if not target:
            raise RuntimeError(f"Object not found: {handle}")
        result = self._client.send_command("get_visible", {"handle": target})
        return result.get("visible", True)

    def list_objects(self, include_internal: bool = False) -> List[Dict[str, Any]]:
        """List all objects in the scene.

        Note:
            The Host defaults include_internal to True for backward compatibility
            when the parameter is omitted. The Python SDK defaults to False to
            hide internal chunk handles from user-facing APIs.

        Returns:
            List of object info dicts with 'handle', 'type', etc.
        """
        result = self._client.send_command(
            "list_objects",
            {"scene_id": self._scene_id, "include_internal": include_internal},
        )
        objects = result.get("objects", [])
        if include_internal:
            return objects
        filtered: List[Dict[str, Any]] = []
        groups: Dict[str, Dict[str, Any]] = {}
        existing_handles = set()
        for obj in objects:
            handle = obj.get("handle")
            if isinstance(handle, str) and handle in self._chunk_parent:
                group_id = self._chunk_parent[handle]
                if group_id not in groups:
                    groups[group_id] = obj
                continue
            if isinstance(handle, str):
                existing_handles.add(handle)
            filtered.append(obj)
        for group_id, rep in groups.items():
            if group_id in existing_handles:
                continue
            filtered.append(
                {
                    "handle": group_id,
                    "type": rep.get("type"),
                    "visible": rep.get("visible"),
                    "group": True,
                }
            )
        return filtered

    # ─────────────────────────────────────────────────────────────────────────
    # Camera
    # ─────────────────────────────────────────────────────────────────────────

    def set_camera_pose(
        self,
        eye: Vec3,
        target: Vec3,
        up: Vec3 = (0, 0, 1),
    ) -> None:
        """Set the camera position and orientation."""
        self._client.send_command(
            "set_camera_pose",
            {
                "view_id": self._view_id,
                "eye": _to_list(eye),
                "target": _to_list(target),
                "up": _to_list(up),
            },
        )

    def get_camera_pose(self) -> Dict[str, Any]:
        """Get the current camera pose (viewer-side).

        Raises an error if no authenticated viewer is available or the correlated response times out.
        """
        result = self._client.send_command(
            "get_camera_pose",
            {"view_id": self._view_id},
        )
        event = self._client.wait_for_event("camera_pose_response", timeout=2.0, filter_fn=lambda data: data.get("view_id") == self._view_id and data.get("request_id") == result.get("request_id"))
        if not event and not self._warned_camera_pose_fallback:
            logger.warning("get_camera_pose: viewer response missing")
            self._warned_camera_pose_fallback = True
        if event is None:
            raise TimeoutError("Viewer did not answer the correlated query")
        payload = event
        try:
            eye = _to_list(payload.get("eye", [5, 5, 5]))
            target = _to_list(payload.get("target", [0, 0, 0]))
            up = _to_list(payload.get("up", [0, 0, 1]))
        except ValueError as exc:
            raise RuntimeError(
                "Invalid get_camera_pose response: eye/target/up must have 3 components."
            ) from exc
        return {"eye": eye, "target": target, "up": up}

    def set_camera_controls(
        self,
        zoom_to_cursor: Optional[bool] = None,
        orbit_enabled: Optional[bool] = None,
        pan_enabled: Optional[bool] = None,
        zoom_enabled: Optional[bool] = None,
        rotate_sensitivity: Optional[float] = None,
        pan_sensitivity: Optional[float] = None,
        zoom_sensitivity: Optional[float] = None,
        damping: Optional[bool] = None,
        mouse_preset: Optional[str] = None,
        mouse_buttons: Optional[Dict[str, str]] = None,
        fov: Optional[float] = None,
    ) -> None:
        """Configure camera interaction behavior for this view.

        Args:
            zoom_to_cursor: Enable zoom-to-cursor (mouse position stays fixed during zoom)
            orbit_enabled: Enable/disable orbit rotation
            pan_enabled: Enable/disable panning
            zoom_enabled: Enable/disable zooming
            rotate_sensitivity: Rotation speed multiplier
            pan_sensitivity: Pan speed multiplier
            zoom_sensitivity: Zoom speed multiplier
            damping: Enable camera inertia (default: False)
            mouse_preset: 'cad' (left=rotate, middle=pan) or 'trackpad' (left=rotate, middle=zoom, right=pan)
            mouse_buttons: Custom mapping, e.g. {'left': 'rotate', 'middle': 'pan', 'right': 'none'}
            fov: Field of view in degrees (10-120, default: 30)

        Defaults (see get_camera_controls):
            - rotate_sensitivity: 0.5
            - pan_sensitivity: 1.0
            - zoom_sensitivity: 1.0
            - zoom_to_cursor: False
            - orbit_enabled: True
            - pan_enabled: True
            - zoom_enabled: True
            - damping: False
            - mouse_preset: 'cad' (Windows/Linux) or 'trackpad' (macOS)
            - mouse_buttons: depends on mouse_preset
            - fov: 30
        """
        args: Dict[str, Any] = {"view_id": self._view_id}
        if zoom_to_cursor is not None:
            args["zoom_to_cursor"] = zoom_to_cursor
        if orbit_enabled is not None:
            args["orbit_enabled"] = orbit_enabled
        if pan_enabled is not None:
            args["pan_enabled"] = pan_enabled
        if zoom_enabled is not None:
            args["zoom_enabled"] = zoom_enabled
        if rotate_sensitivity is not None:
            args["rotate_sensitivity"] = rotate_sensitivity
        if pan_sensitivity is not None:
            args["pan_sensitivity"] = pan_sensitivity
        if zoom_sensitivity is not None:
            args["zoom_sensitivity"] = zoom_sensitivity
        # P1-1: Damping control
        if damping is not None:
            args["damping"] = damping
        # P1-2: Mouse button mapping
        if mouse_preset is not None:
            args["mouse_preset"] = mouse_preset
        if mouse_buttons is not None:
            args["mouse_buttons"] = mouse_buttons
        # P1-3: FOV control
        if fov is not None:
            args["fov"] = fov
        self._client.send_command("set_camera_controls", args)

    def get_camera_controls(self) -> Dict[str, Any]:
        """Get current camera control configuration and defaults."""
        result = self._client.send_command(
            "get_camera_controls",
            {"view_id": self._view_id},
        )
        if not result:
            return {}
        if isinstance(result, dict) and "config" in result and isinstance(result["config"], dict):
            return result["config"]
        return result

    def set_view_config(
        self,
        show_grid: Optional[bool] = None,
        show_ground: Optional[bool] = None,
        show_axes: Optional[bool] = None,
        grid_color: Optional[Color] = None,
        grid_sub_color: Optional[Color] = None,
        axes_length: Optional[float] = None,
        axes_radius: Optional[float] = None,
        axes_size: Optional[float] = None,
        background: Optional[Color] = None,
    ) -> None:
        """
        Configure view helpers (grid/axes/background).

        Notes:
            - Window title/size/position are configured by open() only.
            - Colors accept named colors, hex strings, or [r, g, b]/[r, g, b, a] floats.
            - Defaults: show_grid=False, show_axes=True, axes_length=0.2, axes_radius=0.002.
            - axes_size is a legacy alias for axes_length.
            - show_ground is a legacy alias for show_grid.
        """
        config: Dict[str, Any] = {}
        if show_grid is not None:
            config["show_grid"] = show_grid
        if show_ground is not None:
            config["show_ground"] = show_ground
        if show_axes is not None:
            config["show_axes"] = show_axes
        if grid_color is not None:
            config["grid_color"] = _normalize_color(grid_color)
        if grid_sub_color is not None:
            config["grid_sub_color"] = _normalize_color(grid_sub_color)
        if axes_length is not None:
            config["axes_length"] = axes_length
        if axes_radius is not None:
            config["axes_radius"] = axes_radius
        if axes_size is not None and axes_length is None:
            config["axes_length"] = axes_size
        if background is not None:
            config["background"] = _normalize_color(background)
        if not config:
            return
        self._client.send_command(
            "set_view_config",
            {"view_id": self._view_id, "config": config},
        )
        # Note: window title/size/position handled by open()

    def get_view_config(self) -> Dict[str, Any]:
        """
        Get view config from the host.

        Returns:
            Dict with keys matching set_view_config (show_grid, show_ground, show_axes,
            grid_color, grid_sub_color, axes_length, axes_radius, background).
        """
        result = self._client.send_command(
            "get_view_config",
            {"view_id": self._view_id},
        )
        if not result:
            return {}
        if isinstance(result, dict) and "config" in result and isinstance(result["config"], dict):
            return result["config"]
        return result

    def reset_camera(
        self, mode: str = "fit_scene", fit_handle: Optional[str] = None
    ) -> None:
        """Reset camera to fit the scene or a specific object."""
        args: Dict[str, Any] = {"view_id": self._view_id, "mode": mode}
        if fit_handle:
            args["fit_handle"] = fit_handle
        self._client.send_command("reset_camera", args)

    def set_view(self, view: str = "home", fit_all: bool = True) -> None:
        """
        Switch to a preset camera view.

        Args:
            view: Preset view name. One of:
                - 'home': Isometric view (from +X+Y+Z looking at origin)
                - 'front': Front view (from +X)
                - 'left': Left view (from +Y)
                - 'top': Top view (from +Z)
                - 'back': Back view (from -X)
                - 'right': Right view (from -Y)
                - 'bottom': Bottom view (from -Z)
            fit_all: If True, auto-adjust distance to show all objects.
        """
        self._client.send_command(
            "set_view",
            {
                "view_id": self._view_id,
                "view": view,
                "fit_all": fit_all,
            },
        )

    def set_render_mode(self, mode: str = "solid") -> None:
        """
        Set the rendering display mode.

        Args:
            mode: Render mode. One of:
                - 'solid': Filled surfaces (default)
                - 'wireframe': Wireframe display
                - 'points': Vertex point cloud display
        """
        self._client.send_command(
            "set_render_mode",
            {
                "view_id": self._view_id,
                "mode": mode,
            },
        )

    def set_performance_mode(self, mode: str = "quality") -> None:
        """
        Set the WebGL rendering performance/quality mode.

        This will recreate the WebGL renderer with new settings. There may be
        a brief flicker during the transition, but all scene objects are preserved.

        Args:
            mode: Performance mode. One of:
                - 'performance': Fast rendering, low quality (no antialiasing, pixelRatio=1)
                - 'balanced': Medium quality and performance
                - 'quality': High quality rendering (antialiasing enabled, high DPI support)

        Examples:
            # Switch to high quality for final presentation
            viz.set_performance_mode('quality')

            # Switch to performance mode for heavy scenes
            viz.set_performance_mode('performance')
        """
        self._client.send_command(
            "set_performance_mode",
            {
                "view_id": self._view_id,
                "mode": mode,
            },
        )

    def enable_keyboard_shortcuts(self, enabled: bool = True) -> None:
        """
        Enable or disable built-in keyboard shortcuts for this viewer.

        Args:
            enabled: True to enable (default), False to disable.
        """
        self._client.send_command(
            "set_keyboard_shortcuts",
            {
                "view_id": self._view_id,
                "enabled": enabled,
            },
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 2D Overlay
    # ─────────────────────────────────────────────────────────────────────────
    # 3D Text / Labels
    # ─────────────────────────────────────────────────────────────────────────

    def add_text_3d(
        self,
        text: str,
        pos: Optional[Vec3] = None,
        font_size: int = 14,
        color: Color = "white",
        background_color: Optional[str] = None,
        **node_options: Any,
    ) -> str:
        """Add a 3D text label in its parent frame.

        The text will always face the camera (billboard style).

        Args:
            text: The text content.
            pos: Local position [x, y, z].
            font_size: Font size in pixels.
            color: Text color.
            background_color: CSS color for background (e.g., 'rgba(0,0,0,0.6)').

        Returns:
            Handle to the text object.
        """
        node = node_arguments(node_options, pos=pos, default_pose=True)
        pose = node["pose"]
        args: Dict[str, Any] = {
            **node,
            "scene_id": self._scene_id,
            "text": text,
            "pos": pose.get("position", pose.get("pos")),
            "font_size": font_size,
            "color": _normalize_color(color),
        }
        if background_color is not None:
            args["background_color"] = background_color
        result = self._client.send_command("add_text_3d", args)
        return result.get("handle", "")

    def update_text_3d(
        self,
        handle: str,
        text: Optional[str] = None,
        pos: Optional[Vec3] = None,
        font_size: Optional[int] = None,
        color: Optional[Color] = None,
    ) -> None:
        """Update a 3D text label."""
        args: Dict[str, Any] = {"handle": handle}
        if text is not None:
            args["text"] = text
        if pos is not None:
            args["pos"] = _to_list(pos)
        if font_size is not None:
            args["font_size"] = font_size
        if color is not None:
            args["color"] = _normalize_color(color)
        self._client.send_command("update_text_3d", args)

    # ─────────────────────────────────────────────────────────────────────────
    # 2D Overlay Text (screen-space)

    def add_text_2d(
        self,
        text: str,
        x: int = 10,
        y: int = 10,
        font_size: int = 14,
        color: Color = "white",
    ) -> str:
        """Add a 2D text overlay to the view."""
        result = self._client.send_command(
            "add_text_2d",
            {
                "view_id": self._view_id,
                "text": text,
                "x": x,
                "y": y,
                "font_size": font_size,
                "color": _normalize_color(color),
            },
        )
        return result.get("handle", "")

    def update_text_2d(
        self,
        handle: str,
        text: Optional[str] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        font_size: Optional[int] = None,
        color: Optional[Color] = None,
    ) -> None:
        """Update a 2D text overlay."""
        args: Dict[str, Any] = {"view_id": self._view_id, "handle": handle}
        if text is not None:
            args["text"] = text
        if x is not None:
            args["x"] = x
        if y is not None:
            args["y"] = y
        if font_size is not None:
            args["font_size"] = font_size
        if color is not None:
            args["color"] = _normalize_color(color)
        self._client.send_command("update_text_2d", args)

    # ─────────────────────────────────────────────────────────────────────────
    # Gizmo
    # ─────────────────────────────────────────────────────────────────────────

    def attach_gizmo(
        self,
        handle: str,
        size: Optional[float] = None,
        mask: Optional[int] = None,
        scale_mode: Optional[str] = None,
    ) -> None:
        """Attach a gizmo to an object for interactive manipulation.

        Args:
            handle: The object handle to attach the gizmo to.
            size: Gizmo size (default: 1.0).
            mask: Bitmask for allowable transformations (default: 0x3F / 63 = All).
                  Bit 0: Tx, Bit 1: Ty, Bit 2: Tz, Bit 3: Rx, Bit 4: Ry, Bit 5: Rz.
            scale_mode: 'screen' or 'world'.
        """
        target = self._resolve_group_target(handle)
        if not target:
            raise RuntimeError(f"Object not found: {handle}")
        args: Dict[str, Any] = {
            "view_id": self._view_id,
            "handle": target,
        }
        if size is not None:
            args["size"] = size
        if mask is not None:
            args["mask"] = mask
        if scale_mode is not None:
            args["scale_mode"] = scale_mode
        self._client.send_command("attach_gizmo", args)

    def set_gizmo_mode(
        self,
        mask: Optional[int] = None,
        size: Optional[float] = None,
        scale_mode: Optional[str] = None,
    ) -> None:
        """Change gizmo configuration (mask, size, scale_mode).

        Args:
            mask: New bitmask (default: None, keep existing).
            size: Optional new size.
            scale_mode: Optional new scale mode ('screen' or 'world').
        """
        args: Dict[str, Any] = {"view_id": self._view_id}
        if mask is not None:
            args["mask"] = mask
        if size is not None:
            args["size"] = size
        if scale_mode is not None:
            args["scale_mode"] = scale_mode
        self._client.send_command("set_gizmo_mode", args)

    def detach_gizmo(self) -> None:
        """Detach the current gizmo from the view."""
        self._client.send_command("detach_gizmo", {"view_id": self._view_id})

    # ─────────────────────────────────────────────────────────────────────────
    # Picking
    # ─────────────────────────────────────────────────────────────────────────

    def set_pick_config(
        self,
        enabled: Optional[bool] = None,
        mode: Optional[str] = None,
        button: Optional[int] = None,
        ctrl_modifier: Optional[bool] = None,
        highlight_color: Optional[Color] = None,
        marker_size: Optional[float] = None,
        point_threshold: Optional[float] = None,
        line_threshold: Optional[float] = None,
    ) -> None:
        """Configure picking behavior for this view.

        Args:
            enabled: Enable/disable picking.
            mode: Pick mode - 'object' (highlight objects) or 'point' (show coordinate marker).
            button: Mouse button (0=left, 1=middle, 2=right).
            ctrl_modifier: If False, no modifier required. If True, require Ctrl key.
            highlight_color: Color for highlight effect in object mode (RGB).
            marker_size: Size of the axes marker in point mode (world units).
            point_threshold: Distance threshold for point cloud picking (world units, default 0.01).
            line_threshold: Distance threshold for line picking (world units, default 0.01).
        """
        args: Dict[str, Any] = {"view_id": self._view_id}
        if enabled is not None:
            args["enabled"] = enabled
        if mode is not None:
            if mode not in ("object", "point"):
                raise ValueError("mode must be 'object' or 'point'")
            args["mode"] = mode
        if button is not None:
            args["button"] = button
        if ctrl_modifier is not None:
            args["ctrl_modifier"] = ctrl_modifier
        if highlight_color is not None:
            args["highlight_color"] = _normalize_color(highlight_color)
        if marker_size is not None:
            args["marker_size"] = marker_size
        if point_threshold is not None:
            args["point_threshold"] = point_threshold
        if line_threshold is not None:
            args["line_threshold"] = line_threshold
        self._client.send_command("set_pick_config", args)

    def get_pick_config(self) -> Dict[str, Any]:
        """Get current pick configuration.

        Note: This sends a command to the viewer and waits for an event response.
        Raises an error if no authenticated viewer is available or the response times out.
        """
        # Send command to viewer
        result = self._client.send_command("get_pick_config", {"view_id": self._view_id})
        # Wait for pick_config_response event
        event = self._client.wait_for_event("pick_config_response", timeout=2.0, filter_fn=lambda data: data.get("view_id") == self._view_id and data.get("request_id") == result.get("request_id"))
        if not event and not self._warned_pick_config_fallback:
            logger.warning("get_pick_config: viewer response missing")
            self._warned_pick_config_fallback = True
        if event is None:
            raise TimeoutError("Viewer did not answer the correlated query")
        payload = event
        return {
            "enabled": payload.get("enabled", False),
            "mode": payload.get("mode", "object"),
            "button": payload.get("button", 2),
            "ctrl_modifier": payload.get("ctrl_modifier", False),
            "highlight_color": payload.get("highlight_color", [1, 1, 0]),
            "marker_size": payload.get("marker_size", 0.1),
            "point_threshold": payload.get("point_threshold", 0.01),
            "line_threshold": payload.get("line_threshold", 0.01),
        }

    def clear_pick_highlight(self) -> None:
        """Clear the current pick highlight effect."""
        self._client.send_command("clear_pick_highlight", {"view_id": self._view_id})

    def get_picked_info(self) -> Dict[str, Any]:
        """Get information about the last picked point/object.

        Note: This sends a command to the viewer and waits for an event response.
        Raises an error if no authenticated viewer is available or the response times out.

        Returns:
            dict with:
                - handle: Handle of the picked object (or None)
                - point_world: [x, y, z] world position of pick point (or None)
                - normal_world: [nx, ny, nz] surface normal (or None)
                - point_index: Index for point cloud picks (or None)
        """
        # Send command to viewer
        result = self._client.send_command("get_picked_info", {"view_id": self._view_id})
        # Wait for pick_info_response event
        event = self._client.wait_for_event("pick_info_response", timeout=2.0, filter_fn=lambda data: data.get("view_id") == self._view_id and data.get("request_id") == result.get("request_id"))
        if not event and not self._warned_pick_info_fallback:
            logger.warning("get_picked_info: viewer response missing")
            self._warned_pick_info_fallback = True
        if event is None:
            raise TimeoutError("Viewer did not answer the correlated query")
        if event:
            mapped = self._map_event_data(event)
            return {
                "handle": mapped.get("handle"),
                "point_world": mapped.get("point_world"),
                "normal_world": mapped.get("normal_world"),
                "point_index": mapped.get("point_index"),
            }
        return {
            "handle": None,
            "point_world": None,
            "normal_world": None,
            "point_index": None,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Logging
    # ─────────────────────────────────────────────────────────────────────────

    def set_log_config(
        self,
        min_level: str = "info",
        sinks: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Configure log sinks and minimum level on the Host."""
        if sinks is None:
            sinks = [{"type": "event", "enabled": True}]
        self._client.send_command(
            "set_log_config",
            {"min_level": min_level, "sinks": sinks},
        )

    def read_logs(
        self, after_seq: int = 0, limit: int = 100
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Read logs from the Host.

        Returns (next_after_seq, entries).
        """
        result = self._client.send_command(
            "read_logs",
            {"after_seq": after_seq, "limit": limit},
        )
        return result.get("next_after_seq", after_seq), result.get("entries", [])

    # ─────────────────────────────────────────────────────────────────────────
    # Scene / View management
    # ─────────────────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Clear all objects from the scene and 2D overlays in this view."""
        self._client.send_command(
            "clear_scene",
            {"scene_id": self._scene_id, "view_id": self._view_id},
        )
        self._chunk_groups.clear()
        self._chunk_parent.clear()
        self._chunk_offsets.clear()
        self._chunk_counter = 0

    def attach_scene(self, scene_id: str) -> None:
        """Switch this view to display a different scene.

        Args:
            scene_id: The scene to attach to.

        Note:
            This changes which scene's objects are displayed in this view.
            The view keeps its own camera state.
        """
        # Notify server to update view -> scene binding
        self._client.send_command(
            "attach_scene",
            {
                "view_id": self._view_id,
                "scene_id": scene_id,
            },
        )
        self._scene_id = scene_id

    # ─────────────────────────────────────────────────────────────────────────
    # Events
    # ─────────────────────────────────────────────────────────────────────────

    def on(self, event_type: str, handler: EventHandler) -> None:
        """Register an event handler for any event type.

        Args:
            event_type: Event type like 'picked', 'key_down', 'transformed', etc.
            handler: Callback function that receives the event dict.
        """
        if event_type in ("picked", "pick", "pick_info_response", "transformed"):
            def wrapped(data: Dict[str, Any]) -> None:
                if isinstance(data, dict):
                    handler(self._map_event_data(data))
                else:
                    handler(data)
            self._client.on_event(event_type, wrapped)
            return
        self._client.on_event(event_type, handler)

    def on_pick(self, handler: EventHandler) -> None:
        """Register a handler for pick events."""
        self.on("picked", handler)

    def on_transform(self, handler: EventHandler) -> None:
        """Register a handler for gizmo transform events."""
        self.on("transformed", handler)

    def on_log(self, handler: EventHandler) -> None:
        """Register a handler for log events."""
        self._client.on_event("log", handler)

    def spin(self) -> None:
        """Block and process events until connection closes."""
        self._client.spin()

    def keep_running(self) -> None:
        """Keep a script alive until disconnection or Ctrl+C, then close it.

        Callbacks run on the background dispatcher by default. In manual mode
        this call dispatches them on the calling thread. Unexpected errors are
        propagated after cleanup. Closing a browser tab alone does not end the
        Host session.
        """
        try:
            self.spin()
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def poll_events(self) -> None:
        """Process queued events without blocking."""
        self._client.poll_events()

    def close(self) -> None:
        """Close this Viz handle and underlying connection.

        For views created by `open()`, this also destroys the view (and scene if
        it becomes unused). For views attached via `connect()`, this only
        disconnects the client.
        """
        if self._owns_view:
            destroy_sent = False
            try:
                self._client.send_command("destroy_view", {"view_id": self._view_id})
                destroy_sent = True
            except Exception:
                pass
            # Wait for viewer-side cleanup to complete before proceeding (#44).
            # Only wait if the destroy command was actually sent; otherwise the
            # event will never arrive and we'd stall for the full timeout.
            if destroy_sent:
                try:
                    self._client.wait_for_event(
                        "view_destroyed",
                        timeout=2.0,
                        filter_fn=lambda data: data.get("view_id") == self._view_id,
                    )
                except Exception:
                    pass
            if self._opened_via_tauri:
                _try_close_tauri_window(self._view_id)

            # Check if this is the last view using this scene.
            try:
                result = self._client.send_command("list_views", {})
                views = result.get("views", [])
                has_other_views = any(v.get("scene_id") == self._scene_id for v in views)
            except Exception:
                has_other_views = True

            if not has_other_views:
                try:
                    self._client.send_command("destroy_scene", {"scene_id": self._scene_id})
                except Exception:
                    pass
                self._owns_scene = False
        self._chunk_groups.clear()
        self._chunk_parent.clear()
        self._chunk_offsets.clear()
        self._client.close()


def open(
    url: Optional[str] = None,
    share_scene: Optional[str] = None,
    title: str = "FrameViz",
    width: int = 800,
    height: int = 600,
    window_decorations: bool = True,
    x: Optional[int] = None,
    y: Optional[int] = None,
    window_mode: int = 2,
    timeout: float = 10.0,
    performance_mode: str = "balanced",
    auto_events: bool = True,
    reuse_browser: bool = True,
) -> Viz:
    """
    Open a FrameViz visualization window.

    Creates a new scene and view, returning a Viz context for adding content.

    Args:
        url: Optional WebSocket server URL.
             If not provided, resolves via FRAMEVIZ_HOST or default localhost.
        share_scene: If provided, binds the new view to an existing scene instead of
                     creating a new one. This allows multiple views to share the same
                     scene data while having independent cameras.
        title: Window title.
        width: Window width in pixels (default: 800).
        height: Window height in pixels (default: 600).
        window_decorations: Whether to show window title bar and borders (default: True).
        x: Optional window X position (screen coordinates).
        y: Optional window Y position (screen coordinates).
        window_mode: Controls automatic window opening behavior:
                     0 - Don't open window (manual browser open required)
                     1 - Open browser automatically with the viewer URL
                     2 - Try Tauri app first, fallback to browser if unavailable (default)
                         Uses the Tauri control port to open a new window if
                         the app is already running. Use FRAMEVIZ_TAURI_APP
                         to override the app path and FRAMEVIZ_TAURI_CONTROL_PORT
                         to override the control port.
        timeout: Command timeout in seconds.
        auto_events: Run callbacks serially in a background thread (default True).
                     Set False for manual spin()/poll_events() dispatch.
        reuse_browser: Reuse this process's managed browser page for this runtime.
                       False opens a separate page; native windows are unaffected.
        performance_mode: Initial WebGL rendering quality mode:
                         - 'performance': Fast rendering, low quality
                         - 'balanced': Medium quality and performance (default)
                         - 'quality': High quality rendering with antialiasing
                         Can be changed later with viz.set_performance_mode()

    Returns:
        Viz instance for adding objects and controlling the view.

    Examples:
        # Automatically discover/start the runtime and open a native window.
        viz = fv.open(title="Main View")

        # Force a browser instead. A headless machine prints a private link.
        viz = fv.open(title="Main View", window_mode=1)

        # Keep page opening under application control.
        viz = fv.open(title="Main View", window_mode=0)

        # Create two views sharing the same scene with auto-open
        viz1 = fv.open(title="Main View", window_mode=1)
        viz2 = fv.open(title="Side View", share_scene=viz1.scene_id, window_mode=1, reuse_browser=False)
        # Both browser windows open automatically

        # Each view can have independent camera positions
        viz1.set_camera_pose(eye=[5, 5, 5], target=[0, 0, 0])
        viz2.set_camera_pose(eye=[0, 10, 2], target=[0, 0, 0])
    """
    from .host import _desktop_available
    desktop = _desktop_available()
    if window_mode not in (0,1,2):raise ValueError('window_mode must be 0, 1 or 2')
    if not isinstance(reuse_browser,bool):raise ValueError('reuse_browser must be a boolean')
    print_link = not desktop and window_mode != 0
    if not desktop:window_mode=0
    tauri_page = None

    client,resolved_url = _connect_runtime(url,timeout,prefer_browser=window_mode==1 or not desktop,auto_events=auto_events)
    scene_id = actual_view_id = None
    owns_scene = False
    try:
        viewer_url = _get_viewer_url(resolved_url)

        if share_scene:
            # Use existing scene
            scene_id = share_scene
            owns_scene = False
        else:
            # Create new scene
            scene_result = client.send_command("create_scene", {})
            scene_id = scene_result.get("scene_id", "s_1")
            owns_scene = True

        # Build create_view args
        create_view_args = {
            "title": title,
            "width": width,
            "height": height,
            "scene_id": scene_id,
            "window_decorations": window_decorations,
        }
        # Create view bound to the scene
        view_result = client.send_command("create_view", create_view_args)
        actual_view_id = view_result.get("view_id", "v_1")
        ws_port = _get_ws_port_from_url(resolved_url)
        if print_link:
            print('FrameViz Viewer: '+_viewer_link(viewer_url,actual_view_id,ws_port,performance_mode))

        # Handle automatic window opening based on window_mode
        opened_via_tauri = False
        if window_mode == 1:
            # Open browser directly
            _open_browser_view(client,viewer_url,actual_view_id,ws_port,performance_mode,timeout,reuse_browser)
        elif window_mode == 2:
            # If a viewer is already connected, avoid launching a new window.
            already_ready = _wait_for_viewer(
                client,
                actual_view_id,
                timeout=min(0.2, max(timeout * 0.1, 0.05)),
            )
            if not already_ready:
                # Try Tauri control server first, then launch app, fallback to browser.
                used_tauri = False
                if _try_open_tauri_window(
                    actual_view_id,
                    title,
                    width,
                    height,
                    x,
                    y,
                    tauri_page,
                    scene_id,
                    performance_mode,
                    window_decorations,
                ):
                    used_tauri = True
                elif _try_open_tauri():
                    used_tauri = True
                    retry_attempts = max(25, int(max(timeout, 1.0) / 0.2))
                    _try_open_tauri_window_with_retry(
                        actual_view_id,
                        title,
                        width,
                        height,
                        x,
                        y,
                        tauri_page,
                        scene_id,
                        performance_mode,
                        window_decorations,
                        attempts=retry_attempts,
                    )

                if used_tauri:
                    if _wait_for_viewer(client, actual_view_id, timeout=timeout):
                        opened_via_tauri = True
                    else:
                        _try_close_tauri_window(actual_view_id)
                        _open_browser_view(client,viewer_url,actual_view_id,ws_port,performance_mode,timeout,reuse_browser)
                else:
                    _open_browser_view(client,viewer_url,actual_view_id,ws_port,performance_mode,timeout,reuse_browser)

        return Viz(
            client,
            scene_id,
            actual_view_id,
            opened_via_tauri=opened_via_tauri,
            owns_view=True,
            owns_scene=owns_scene,
        )
    except BaseException:
        if actual_view_id:
            try:client.send_command("destroy_view",{"view_id":actual_view_id})
            except Exception:pass
        if owns_scene and scene_id:
            try:client.send_command("destroy_scene",{"scene_id":scene_id})
            except Exception:pass
        client.close()
        raise


def _connect_runtime(url: Optional[str], timeout: float, prefer_browser: bool, auto_events: bool = True):
    """Authenticate once; only a missing local service may trigger startup."""
    from . import host
    from .discovery import read_discovery_file
    from .version import host_version_error
    resolved=_resolve_connection_url(url)
    parsed=urlparse(resolved)
    local=parsed.hostname in ('127.0.0.1','localhost')
    unconfigured=url is None and not os.environ.get('FRAMEVIZ_HOST')
    info=read_discovery_file() if local and (unconfigured or parsed.port in (None,9527)) else None
    live=False
    if info and isinstance(info.get('pid'),int) and isinstance(info.get('port'),int):
        live=host._pid_is_running(info['pid']) and host._is_port_open('127.0.0.1',info['port'])
        if live:
            error=host_version_error(info.get('version'),PROTOCOL_VERSION)
            if error:raise ProtocolError(error,code='ERR_PROTOCOL_VERSION')
    # A default port occupied without this user's discovery/token is not proof
    # of a FrameViz service owned by this user. Give the new runtime its own port.
    if local and unconfigured and not live and not os.environ.get('FRAMEVIZ_AUTH_TOKEN') and parsed.port==9527 and host._is_port_open('127.0.0.1',9527):
        if not _should_auto_start_ws():raise RuntimeError('FrameViz automatic startup is disabled (FRAMEVIZ_AUTO_START_WS=0)')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        resolved=host.start_host(ws_url=f'ws://127.0.0.1:{port}',timeout=timeout,headless=True,prefer_browser=prefer_browser)
    client=FrameVizClient(url=resolved,timeout=timeout,**({} if auto_events else {'auto_events':False}))
    try:
        client.connect()
        return client,resolved
    except (FrameVizConnectionError,FrameVizTimeoutError):
        client.close()
        if not local or host._is_port_open(parsed.hostname,parsed.port or 9527):raise
        if not _should_auto_start_ws():raise RuntimeError('FrameViz automatic startup is disabled (FRAMEVIZ_AUTO_START_WS=0)')
        resolved=host.start_host(ws_url=resolved,timeout=timeout,headless=True,prefer_browser=prefer_browser)
        client=FrameVizClient(url=resolved,timeout=timeout,**({} if auto_events else {'auto_events':False}))
        client.connect()
        return client,resolved


def _resolve_connect_target(
    client: FrameVizClient, view_id: Optional[str], timeout: float
) -> Tuple[str, str]:
    """
    Resolve connect target to `(view_id, scene_id)`.

    - If `view_id` is provided, match it from `list_views`.
    - If `view_id` is omitted, auto-select only when exactly one view exists.
    """
    poll_interval = 0.5
    start_time = time.time()
    last_view_ids: List[str] = []
    requested_view_seen_without_scene = False
    unbound_view_ids: List[str] = []
    while time.time() - start_time < timeout:
        result = client.send_command("list_views", {})
        raw_views = result.get("views", [])
        views: List[Dict[str, Any]] = []
        unbound_view_ids = []
        for item in raw_views:
            if not isinstance(item, dict):
                continue
            candidate_view_id = item.get("view_id")
            if not candidate_view_id:
                continue
            scene = item.get("scene_id")
            if scene:
                views.append(
                    {"view_id": str(candidate_view_id), "scene_id": str(scene)}
                )
            else:
                unbound_view_ids.append(str(candidate_view_id))
                if view_id and str(candidate_view_id) == view_id:
                    requested_view_seen_without_scene = True
        last_view_ids = [str(v["view_id"]) for v in views]

        if view_id:
            for item in views:
                if item.get("view_id") == view_id:
                    return str(item["view_id"]), str(item["scene_id"])
        else:
            if len(views) == 1:
                item = views[0]
                return str(item["view_id"]), str(item["scene_id"])
            if len(views) > 1:
                ids = ", ".join(last_view_ids)
                raise ValueError(
                    f"Multiple views are available: {ids}. "
                    "Specify connect(view_id='...') explicitly."
                )

        time.sleep(poll_interval)

    if view_id:
        if requested_view_seen_without_scene:
            raise TimeoutError(
                f"View '{view_id}' exists but is not attached to a scene within {timeout}s. "
                "Bind a scene first or wait until attach_scene completes."
            )
        hint = f" Available view_ids: {', '.join(last_view_ids)}." if last_view_ids else ""
        raise TimeoutError(f"View '{view_id}' not found within {timeout}s.{hint}")
    if unbound_view_ids:
        hint = f" Unbound view_ids: {', '.join(unbound_view_ids)}."
    else:
        hint = ""
    raise TimeoutError(
        f"No available view found within {timeout}s. "
        "Open a view first via fv.open() or provide connect(view_id='...')."
        + hint
    )


def _resolve_connection_url(url: Optional[str]) -> str:
    """
    Resolve connection URL for connect flows.

    Resolution order:
    1. Explicit `url` argument
    2. `FRAMEVIZ_HOST`
    3. Default localhost URL
    Then apply discovery-based port resolution for localhost defaults.
    """
    if url is None:
        url = os.environ.get("FRAMEVIZ_HOST")
    if url is None:
        url = DEFAULT_WS_URL
    return _resolve_ws_url(url, allow_discovery=True)


def connect(
    url: Optional[str] = None,
    view_id: Optional[str] = None,
    timeout: float = 10.0,
    auto_events: bool = True,
) -> Viz:
    """
    Connect to an existing view and return a Viz object.

    Args:
        url: WebSocket server URL. If not provided, reads from:
             1. FRAMEVIZ_HOST environment variable
             2. Discovery file (if available)
             3. Defaults to ws://127.0.0.1:9527
        timeout: Connection timeout in seconds.
        auto_events: Run callbacks on a background thread; False enables manual polling.
        view_id: Optional target view identifier.
                 If omitted, connect() succeeds only when exactly one view exists.

    Returns:
        Viz object bound to an existing view.

    Example:
        # Attach by view id
        viz = fv.connect(view_id="v_1")

        # Or auto-connect when only one view exists
        viz2 = fv.connect()
    """

    resolved_url = _resolve_connection_url(url)
    client = FrameVizClient(url=resolved_url, timeout=timeout, **({} if auto_events else {'auto_events': False}))
    client.connect()

    try:
        resolved_view_id, scene_id = _resolve_connect_target(
            client, view_id=view_id, timeout=timeout
        )
        return Viz._from_viewer(client, resolved_view_id, scene_id)
    except Exception:
        client.close()
        raise


def _browser_session_key(client: FrameVizClient):
    token = client._resolve_token()
    if not isinstance(token,str) or not token or not isinstance(client.url,str):
        return None
    endpoint = urlparse(client.url)
    hostname = endpoint.hostname or ''
    if hostname in ('localhost','127.0.0.1','::1'):
        hostname = 'loopback'
    return (endpoint.scheme,hostname,endpoint.port or (443 if endpoint.scheme=='wss' else 80),
            hashlib.sha256(token.encode()).hexdigest())


def _present_browser_view(client: FrameVizClient, session: str, view_id: str,
                          timeout: float) -> bool:
    try:
        count = client.present_view(session,view_id)
    except RuntimeError as error:
        # This exact legacy response means the runtime predates page reuse.
        # Authentication/version/other failures must retain their normal errors.
        if str(error) == '[ERR_INVALID_ARGS] Command not implemented: present_view':
            return False
        raise
    if count == 0:
        return False
    # The existing correlated query is also a liveness barrier: a page that
    # closed before presentation cannot answer it. Never rely only on a registry.
    try:
        result = client.send_command('get_camera_pose',{'view_id':view_id})
    except RuntimeError as error:
        if str(error).startswith('[ERR_VIEWER_UNAVAILABLE]'):
            return False
        raise
    reply = client.wait_for_event('camera_pose_response',timeout=timeout,
        filter_fn=lambda data:data.get('view_id')==view_id and data.get('request_id')==result.get('request_id'))
    return reply is not None


def _open_browser_view(client, viewer_url, view_id, ws_port, performance_mode, timeout, reuse_browser):
    key = _browser_session_key(client) if reuse_browser else None
    if key is None:
        _open_browser(viewer_url,view_id,ws_port,performance_mode)
        _wait_for_viewer(client,view_id,timeout=timeout)
        return
    # Serialize presentation/opening, not scene creation or application callbacks.
    with _BROWSER_SESSION_LOCK:
        session = _BROWSER_SESSIONS.get(key)
        if session is not None and _present_browser_view(client,session,view_id,timeout):
            client.send_command('set_performance_mode',{'view_id':view_id,'mode':performance_mode})
            return
        session = uuid.uuid4().hex
        _open_browser(viewer_url,view_id,ws_port,performance_mode,browser_session=session)
        _wait_for_viewer(client,view_id,timeout=timeout)
        _BROWSER_SESSIONS[key] = session


def _open_browser(
    viewer_url: str,
    view_id: str,
    ws_port: Optional[int] = None,
    performance_mode: Optional[str] = None,
    browser_session: Optional[str] = None,
) -> None:
    """Open the web viewer in the default browser."""
    webbrowser.open(_viewer_link(viewer_url,view_id,ws_port,performance_mode,browser_session))


def _viewer_link(viewer_url: str, view_id: str, ws_port=None, performance_mode=None, browser_session=None) -> str:
    if not viewer_url:
        raise RuntimeError('FrameViz Viewer URL is unavailable for this runtime. Install a runtime with bundled Viewer assets (docs/INSTALLATION.md), or use window_mode=0 for an embedded viewer.')
    parsed = urlparse(viewer_url)
    params = parse_qs(parsed.query)
    params["view_id"] = [view_id]
    if browser_session is not None:
        params['browser_session'] = [browser_session]
    if ws_port is not None:
        params["ws_port"] = [str(ws_port)]
    if performance_mode is not None:
        params["performance_mode"] = [performance_mode]
    query = urlencode(params, doseq=True)
    full_url = urlunparse(parsed._replace(query=query))
    from .discovery import get_token_from_discovery
    if urlparse(full_url).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Automatic authenticated Viewer opening requires a loopback URL")
    token = os.environ.get("FRAMEVIZ_AUTH_TOKEN") or get_token_from_discovery()
    if token:
        full_url = full_url.split("#", 1)[0] + "#" + urlencode({"token": token})
    return full_url


def _wait_for_viewer(
    client: FrameVizClient, view_id: str, timeout: float = 10.0
) -> bool:
    """
    Wait for the viewer with the specified view_id to connect.

    Args:
        client: The FrameViz client instance
        view_id: The view ID to wait for
        timeout: Maximum time to wait in seconds

    Returns:
        True if viewer connected, False if timeout
    """
    event = client.wait_for_event(
        "viewer_ready",
        timeout=timeout,
        filter_fn=lambda data: data.get("view_id") == view_id,
    )
    return event is not None


def _try_open_tauri(view_id: Optional[str] = None) -> bool:
    """
    Try to launch the Tauri application.

    Returns:
        True if Tauri app was successfully launched, False otherwise.
    """
    # Background bootstrap must not display onboarding or create a second Host
    # while the process we just started is still bringing up its control socket.
    if not view_id and any(proc.poll() is None for proc in _AUTO_TAURI_PROCS):
        return True
    from . import host
    owned=host._started_host_proc
    if not view_id and owned is not None and owned.poll() is None:
        command=owned.args[0] if isinstance(owned.args,(list,tuple)) else owned.args
        if Path(command).name in ('frameviz','FrameViz','frameviz.exe'):
            return True
    args: List[str] = ["--headless"]
    if view_id:
        args = ["--view-id", view_id]

    env_app = os.environ.get("FRAMEVIZ_TAURI_APP")
    if env_app:
        if _launch_tauri_path(Path(env_app).expanduser(), args):
            return True

    repo_root = _get_repo_root()

    if sys.platform == "darwin":
        for app_path in _get_tauri_app_candidates(repo_root):
            if _launch_tauri_path(app_path, args):
                return True

        for bin_path in _get_tauri_exec_candidates(repo_root):
            if _launch_exec(bin_path, args):
                return True

        return False

    if sys.platform.startswith("win"):
        for path in _get_tauri_exec_candidates(repo_root):
            if _launch_exec(path, args):
                return True
        return False

    for path in _get_tauri_exec_candidates(repo_root) + _get_appimage_candidates(repo_root):
        if _launch_exec(path, args):
            return True
    return False


def _try_open_tauri_window(
    view_id: str,
    title: str,
    width: int,
    height: int,
    x: Optional[int],
    y: Optional[int],
    page: Optional[str],
    scene_id: Optional[str] = None,
    performance_mode: Optional[str] = None,
    decorations: Optional[bool] = None,
) -> bool:
    """
    Try to request a new Tauri window from a running app.

    Returns:
        True if a Tauri window was opened or focused, False otherwise.
    """
    port = _get_tauri_control_port()
    payload = {
        "action": "open_view",
        "view_id": view_id,
        "title": title,
        "width": width,
        "height": height,
    }
    if x is not None:
        payload["x"] = x
    if y is not None:
        payload["y"] = y
    if page:
        payload["page"] = page
    if decorations is not None:
        payload["decorations"] = decorations
    if scene_id:
        payload["scene_id"] = scene_id
    if performance_mode:
        payload["performance_mode"] = performance_mode

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4) as sock:
            sock.settimeout(1.0)
            from .discovery import get_token_from_discovery
            payload["token"] = os.environ.get("FRAMEVIZ_AUTH_TOKEN") or get_token_from_discovery()
            message = json.dumps(payload).encode("utf-8") + b"\n"
            sock.sendall(message)

            data = b""
            while b"\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk

        if not data:
            return False

        line = data.splitlines()[0].decode("utf-8")
        response = json.loads(line)
        return bool(response.get("ok"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def _try_configure_tauri_window(
    view_id: str,
    title: Optional[str],
    width: Optional[int],
    height: Optional[int],
    x: Optional[int],
    y: Optional[int],
) -> bool:
    port = _get_tauri_control_port()
    payload: Dict[str, Any] = {
        "action": "configure_view",
        "view_id": view_id,
    }
    if title is not None:
        payload["title"] = title
    if width is not None:
        payload["width"] = width
    if height is not None:
        payload["height"] = height
    if x is not None:
        payload["x"] = x
    if y is not None:
        payload["y"] = y

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4) as sock:
            sock.settimeout(1.0)
            from .discovery import get_token_from_discovery
            payload["token"] = os.environ.get("FRAMEVIZ_AUTH_TOKEN") or get_token_from_discovery()
            message = json.dumps(payload).encode("utf-8") + b"\n"
            sock.sendall(message)

            data = b""
            while b"\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk

        if not data:
            return False

        line = data.splitlines()[0].decode("utf-8")
        response = json.loads(line)
        return bool(response.get("ok"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def _try_open_tauri_window_with_retry(
    view_id: str,
    title: str,
    width: int,
    height: int,
    x: Optional[int],
    y: Optional[int],
    page: Optional[str],
    scene_id: Optional[str] = None,
    performance_mode: Optional[str] = None,
    decorations: Optional[bool] = None,
    attempts: int = 25,
    delay_sec: float = 0.2,
) -> bool:
    for _ in range(attempts):
        if _try_open_tauri_window(
            view_id, title, width, height, x, y, page, scene_id, performance_mode, decorations
        ):
            return True
        time.sleep(delay_sec)
    return False


def _try_close_tauri_window(view_id: str) -> bool:
    port = _get_tauri_control_port()
    payload = {
        "action": "close_view",
        "view_id": view_id,
    }

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4) as sock:
            sock.settimeout(1.0)
            from .discovery import get_token_from_discovery
            payload["token"] = os.environ.get("FRAMEVIZ_AUTH_TOKEN") or get_token_from_discovery()
            message = json.dumps(payload).encode("utf-8") + b"\n"
            sock.sendall(message)

            data = b""
            while b"\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk

        if not data:
            return False

        line = data.splitlines()[0].decode("utf-8")
        response = json.loads(line)
        return bool(response.get("ok"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def _get_tauri_control_port() -> int:
    value = os.environ.get("FRAMEVIZ_TAURI_CONTROL_PORT", "").strip()
    if not value:
        return DEFAULT_TAURI_CONTROL_PORT
    try:
        port = int(value)
    except ValueError:
        return DEFAULT_TAURI_CONTROL_PORT
    if 1 <= port <= 65535:
        return port
    return DEFAULT_TAURI_CONTROL_PORT


def _launch_tauri_path(path: Path, args: List[str]) -> bool:
    if not path.exists():
        return False
    if sys.platform == "darwin" and path.suffix == ".app":
        inner_bin = _get_macos_app_executable(path)
        return inner_bin is not None and _launch_exec(inner_bin, args)
    return _launch_exec(path, args)


def _launch_macos_app(app: str, args: List[str]) -> bool:
    cmd = ["open", "-a", app]
    if args:
        cmd += ["--args"] + args
    return _run_command(cmd)


def _launch_exec(path: Path, args: List[str]) -> bool:
    if not path.exists():
        return False
    cmd = [str(path)] + args
    return _run_process(cmd)


def _run_process(cmd: List[str]) -> bool:
    try:
        kwargs: Dict[str, Any] = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "posix":
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(
            cmd,
            **kwargs,
        )
        _AUTO_TAURI_PROCS.append(proc)
        _register_auto_tauri_atexit()
    except OSError:
        return False
    return True


def _run_command(cmd: List[str]) -> bool:
    # open -a / shell commands are LaunchServices-managed on macOS and are not
    # directly trackable as child host processes in this SDK.
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _maybe_auto_start_ws(
    url: str, timeout: float
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Attempt to auto-start WebSocket server with Tauri app fallback.

    This is a wrapper around the basic auto-start logic in _internal.py that
    adds Tauri app fallback for situations where the WebSocket server is
    embedded in the Tauri host application.
    """
    from urllib.parse import urlparse

    if not _should_auto_start_ws():
        return False, "auto-start disabled (FRAMEVIZ_AUTO_START_WS=0)", None

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9527

    # Try basic auto-start first (ws-server or discovery)
    ok, reason, new_url = _maybe_auto_start_ws_basic(url, timeout)
    if ok:
        return True, None, new_url

    # If basic auto-start failed, try Tauri app fallback
    if not _try_open_tauri():
        return False, reason or "auto-start failed: ws-server not available", None

    # Tauri app was launched, wait for it to be ready
    use_discovery = parsed.port is None or parsed.port == 9527
    wait_time = _get_ws_startup_timeout(timeout)
    if use_discovery:
        discovery_port = _wait_for_discovery_port(host, wait_time)
        if discovery_port:
            return True, None, f"ws://{host}:{discovery_port}"
    if not _wait_for_ws_ready(host, port, timeout=wait_time):
        return (
            False,
            "auto-start failed: tauri ws host not ready (startup timeout)",
            None,
        )
    return True, None, url


# ─────────────────────────────────────────────────────────────────────────────
# Module-level scene management functions
# ─────────────────────────────────────────────────────────────────────────────


def list_scenes(
    url: Optional[str] = None, timeout: float = 10.0
) -> List[Dict[str, Any]]:
    """List all scenes on the server.

    This is a module-level function independent of any view.

    Args:
        url: Optional WebSocket server URL.
             If not provided, resolves via FRAMEVIZ_HOST or default localhost.
        timeout: Command timeout in seconds

    Returns:
        List of scene info dicts, each containing:
        - scene_id: The scene identifier
        - object_count: Number of objects in the scene

    Example:
        scenes = fv.list_scenes()
        for s in scenes:
            print(f"Scene {s['scene_id']}: {s['object_count']} objects")
    """
    resolved_url = _resolve_connection_url(url)
    client = FrameVizClient(url=resolved_url, timeout=timeout)
    client.connect()
    try:
        result = client.send_command("list_scenes", {})
        return result.get("scenes", [])
    finally:
        client.close()


def destroy_scene(
    scene_id: str, url: Optional[str] = None, timeout: float = 10.0
) -> None:
    """Destroy a scene and free all its resources.

    This is a module-level function independent of any view.
    Removes all objects and buffers belonging to the scene.

    Args:
        scene_id: The scene to destroy
        url: Optional WebSocket server URL.
             If not provided, resolves via FRAMEVIZ_HOST or default localhost.
        timeout: Command timeout in seconds

    Warning:
        This will affect all views currently displaying this scene.

    Example:
        # Clean up old scenes
        for s in fv.list_scenes():
            if s['scene_id'] != current_scene_id:
                fv.destroy_scene(s['scene_id'])
    """
    resolved_url = _resolve_connection_url(url)
    client = FrameVizClient(url=resolved_url, timeout=timeout)
    client.connect()
    try:
        client.send_command("destroy_scene", {"scene_id": scene_id})
    finally:
        client.close()


def list_views(
    url: Optional[str] = None, timeout: float = 10.0
) -> List[Dict[str, Any]]:
    """List all views on the server.

    This is a module-level function independent of any view.

    Args:
        url: Optional WebSocket server URL.
             If not provided, resolves via FRAMEVIZ_HOST or default localhost.
        timeout: Command timeout in seconds

    Returns:
        List of simplified view info dicts, each containing:
        - view_id: The view identifier
        - scene_id: Scene bound to the view (may be null)
    """
    resolved_url = _resolve_connection_url(url)
    client = FrameVizClient(url=resolved_url, timeout=timeout)
    client.connect()
    try:
        result = client.send_command("list_views", {})
        raw_views = result.get("views", [])
        views: List[Dict[str, Any]] = []
        for item in raw_views:
            if not isinstance(item, dict):
                continue
            view_id = item.get("view_id")
            if not view_id:
                continue
            views.append(
                {
                    "view_id": view_id,
                    "scene_id": item.get("scene_id"),
                }
            )
        return views
    finally:
        client.close()


def destroy_view(
    view_id: str, url: Optional[str] = None, timeout: float = 10.0
) -> None:
    """Destroy a view and release its resources on the server.

    This is a module-level function independent of any view.

    Args:
        view_id: The view to destroy
        url: Optional WebSocket server URL.
             If not provided, resolves via FRAMEVIZ_HOST or default localhost.
        timeout: Command timeout in seconds
    """
    resolved_url = _resolve_connection_url(url)
    client = FrameVizClient(url=resolved_url, timeout=timeout)
    client.connect()
    try:
        client.send_command("destroy_view", {"view_id": view_id})
        try:
            client.wait_for_event(
                "view_destroyed",
                timeout=2.0,
                filter_fn=lambda data: data.get("view_id") == view_id,
            )
        except Exception:
            pass
        # Best-effort: also close Tauri window if this view is hosted there.
        _try_close_tauri_window(view_id)
    finally:
        client.close()

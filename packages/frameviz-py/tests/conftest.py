"""
Pytest fixtures for FrameViz Python SDK tests.

Provides mock WebSocket servers, client instances, and common test data.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from frameviz.client import PROTOCOL_VERSION


# =============================================================================
# Mock WebSocket Server
# =============================================================================

class MockWebSocketServer:
    """
    A mock WebSocket server for testing client behavior.
    
    Records all sent messages and allows configuring responses.
    """
    
    def __init__(self):
        self.sent_messages: List[str] = []
        self.sent_binary: List[bytes] = []
        self.responses: Dict[str, Dict[str, Any]] = {}
        self.events_to_emit: List[Tuple[str, Dict[str, Any]]] = []
        self._on_message_callback: Optional[Callable] = None
        self._connected = threading.Event()
        self._closed = False
        
    def configure_response(self, cmd_name: str, result: Dict[str, Any], ok: bool = True):
        """Configure the response for a specific command."""
        self.responses[cmd_name] = {"ok": ok, "result": result}
        
    def configure_error(self, cmd_name: str, code: str, message: str):
        """Configure an error response for a specific command."""
        self.responses[cmd_name] = {
            "ok": False,
            "error": {"code": code, "message": message}
        }
        
    def emit_event(self, name: str, data: Dict[str, Any]):
        """Queue an event to be emitted."""
        self.events_to_emit.append((name, data))
        
    def send(self, message: str, opcode: int = 1):
        """Record a sent message."""
        if opcode == 2:  # Binary
            self.sent_binary.append(message if isinstance(message, bytes) else message.encode())
        else:
            self.sent_messages.append(message)
            # Parse and generate response
            self._handle_outgoing_message(message)
            
    def _handle_outgoing_message(self, message: str):
        """Parse outgoing message and trigger appropriate response."""
        try:
            envelope = json.loads(message)
            if envelope.get("type") == "cmd":
                cmd_name = envelope.get("name", "")
                cmd_id = envelope.get("id", "")
                
                # Get configured response or default success
                resp_config = self.responses.get(cmd_name, {"ok": True, "result": {}})
                
                response = {
                    "protocol_version": PROTOCOL_VERSION,
                    "type": "resp",
                    "id": cmd_id,
                    "ok": resp_config.get("ok", True),
                }
                
                if resp_config.get("ok", True):
                    response["result"] = resp_config.get("result", {})
                else:
                    response["error"] = resp_config.get("error", {})
                    
                # Trigger callback if set
                if self._on_message_callback:
                    self._on_message_callback(json.dumps(response))
                    
        except json.JSONDecodeError:
            pass
            
    def close(self):
        """Mark server as closed."""
        self._closed = True
        
    def get_last_command(self) -> Optional[Dict[str, Any]]:
        """Get the last sent command."""
        if not self.sent_messages:
            return None
        return json.loads(self.sent_messages[-1])
        
    def get_all_commands(self) -> List[Dict[str, Any]]:
        """Get all sent commands."""
        return [json.loads(msg) for msg in self.sent_messages]


@pytest.fixture
def mock_ws_server():
    """Provide a mock WebSocket server instance."""
    return MockWebSocketServer()


# =============================================================================
# Mock Client Fixtures
# =============================================================================

@pytest.fixture
def mock_client(mock_ws_server):
    """
    Provide a mocked FrameVizClient that doesn't actually connect.
    
    Uses the mock_ws_server to record and respond to commands.
    """
    from frameviz.client import FrameVizClient
    
    client = FrameVizClient(url="ws://127.0.0.1:9527", timeout=5.0)
    
    # Mock the WebSocket
    client._ws = MagicMock()
    client._ws.send = mock_ws_server.send
    client._ws.close = mock_ws_server.close
    
    # Set connected state
    client._connected.set()
    client._opened.set()
    
    # Store reference to mock server for response handling
    mock_ws_server._on_message_callback = client._handle_message
    
    return client, mock_ws_server


@pytest.fixture
def mock_viz(mock_client):
    """
    Provide a mocked Viz instance for testing high-level API.
    """
    from frameviz.viz import Viz
    
    client, mock_server = mock_client
    
    # Configure default responses for common commands
    mock_server.configure_response("add_primitive", {"handle": "obj_1"})
    mock_server.configure_response("add_points", {"handle": "pc_1"})
    mock_server.configure_response("add_lines", {"handle": "line_1"})
    mock_server.configure_response("add_mesh", {"handle": "mesh_1"})
    mock_server.configure_response("load_mesh", {"handle": "mesh_2"})
    mock_server.configure_response("create_buffer", {"buffer_id": "buf_1"})
    mock_server.configure_response("upload_buffer_chunk", {})
    mock_server.configure_response("set_transform", {})
    mock_server.configure_response("set_color", {})
    mock_server.configure_response("set_visible", {})
    mock_server.configure_response("remove_object", {})
    mock_server.configure_response("set_camera_pose", {})
    mock_server.configure_response("set_camera_controls", {})
    mock_server.configure_response("reset_camera", {})
    mock_server.configure_response("set_view", {})
    mock_server.configure_response("set_render_mode", {})
    mock_server.configure_response("attach_gizmo", {})
    mock_server.configure_response("set_gizmo_mode", {})
    mock_server.configure_response("detach_gizmo", {})
    mock_server.configure_response("set_pick_config", {})
    mock_server.configure_response("get_pick_config", {"enabled": False, "mode": "object"})
    mock_server.configure_response("set_view_config", {})
    mock_server.configure_response("get_view_config", {"config": {}})
    mock_server.configure_response("clear_pick_highlight", {})
    mock_server.configure_response("clear_scene", {})
    mock_server.configure_response("attach_scene", {})
    mock_server.configure_response("add_text_3d", {"handle": "text_1"})
    mock_server.configure_response("add_text_2d", {"handle": "text2d_1"})
    mock_server.configure_response("get_transform", {"pose": {"pos": [1, 2, 3], "quat": [0, 0, 0, 1]}})
    mock_server.configure_response("get_color", {"rgba": [1, 0, 0, 1]})
    mock_server.configure_response("get_visible", {"visible": True})
    mock_server.configure_response("list_objects", {"objects": []})
    mock_server.configure_response("add_instances", {"handle": "inst_1"})
    mock_server.configure_response("update_instances", {})
    
    viz = Viz(
        client=client,
        scene_id="s_test",
        view_id="v_test",
        opened_via_tauri=False,
        owns_scene=True,
    )
    
    return viz, mock_server


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_vec3():
    """Common 3D vector test cases."""
    return {
        "origin": [0.0, 0.0, 0.0],
        "unit_x": [1.0, 0.0, 0.0],
        "unit_y": [0.0, 1.0, 0.0],
        "unit_z": [0.0, 0.0, 1.0],
        "arbitrary": [1.5, -2.3, 4.7],
        "numpy": np.array([1.0, 2.0, 3.0], dtype=np.float32),
    }


@pytest.fixture
def sample_quat():
    """Common quaternion test cases."""
    return {
        "identity": [0.0, 0.0, 0.0, 1.0],
        "rot_90_z": [0.0, 0.0, 0.7071068, 0.7071068],  # 90° around Z
        "numpy": np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
    }


@pytest.fixture
def sample_colors():
    """Common color test cases."""
    return {
        "red_str": "red",
        "green_str": "green",
        "blue_str": "blue",
        "white_str": "white",
        "hex_red": "#ff0000",
        "hex_green": "#00ff00",
        "rgb_tuple": (0.5, 0.5, 0.5),
        "rgb_list": [0.2, 0.4, 0.6],
        "rgba_tuple": (1.0, 0.0, 0.0, 0.5),
    }


@pytest.fixture
def sample_point_cloud():
    """Sample point cloud data."""
    n_points = 100
    positions = np.random.randn(n_points, 3).astype(np.float32)
    colors = np.random.rand(n_points, 3).astype(np.float32)
    return {"positions": positions, "colors": colors, "n_points": n_points}


@pytest.fixture
def sample_mesh():
    """Sample triangle mesh (a simple cube)."""
    vertices = np.array([
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ], dtype=np.float32)
    
    faces = np.array([
        [0, 1, 2], [0, 2, 3],  # bottom
        [4, 6, 5], [4, 7, 6],  # top
        [0, 4, 5], [0, 5, 1],  # front
        [2, 6, 7], [2, 7, 3],  # back
        [0, 3, 7], [0, 7, 4],  # left
        [1, 5, 6], [1, 6, 2],  # right
    ], dtype=np.uint32)
    
    return {"vertices": vertices, "faces": faces}


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def assert_command_sent(mock_client):
    """Helper to assert a specific command was sent."""
    _, mock_server = mock_client
    
    def _assert(cmd_name: str, **expected_args):
        commands = mock_server.get_all_commands()
        matching = [c for c in commands if c.get("name") == cmd_name]
        assert matching, f"Command '{cmd_name}' was not sent. Sent: {[c.get('name') for c in commands]}"
        
        if expected_args:
            last_matching = matching[-1]
            for key, value in expected_args.items():
                actual = last_matching.get("args", {}).get(key)
                assert actual == value, f"Expected {key}={value}, got {actual}"
                
    return _assert

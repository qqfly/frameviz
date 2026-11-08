"""
Integration tests for FrameViz.

These tests require a running Host and are skipped by default.
To run:
  pytest tests/test_integration.py --run-integration

Note: These tests create real WebSocket connections and require
the FrameViz Host to be running.
"""
from __future__ import annotations

import os
import pytest
import time
from typing import Generator

# Skip all tests in this module unless --run-integration is passed
pytestmark = pytest.mark.skipif(
    not os.environ.get("FRAMEVIZ_INTEGRATION_TEST"),
    reason="Integration tests require FRAMEVIZ_INTEGRATION_TEST=1"
)


@pytest.fixture
def live_viz() -> Generator:
    """Create a real Viz connection to a running Host."""
    import frameviz
    
    viz = None
    try:
        viz = frameviz.open(window_mode=0)
        yield viz
    except Exception as e:
        pytest.fail(f"Explicit Host integration could not connect: {e}")
    finally:
        if viz:
            viz.close()


class TestConnectionIntegration:
    """Test real WebSocket connections."""
    
    def test_connect_and_disconnect(self, live_viz):
        """Test basic connection lifecycle."""
        # Connection established via fixture
        assert live_viz is not None
        
    def test_create_scene(self, live_viz):
        """Test scene creation."""
        # Scene is implicitly created
        assert live_viz._scene_id is not None
        
    def test_create_view(self, live_viz):
        """Test view creation."""
        assert live_viz._view_id is not None


class TestPrimitiveIntegration:
    """Test primitive creation and manipulation with real Host."""
    
    def test_add_box(self, live_viz):
        """Test adding a box primitive."""
        handle = live_viz.add_box()
        assert handle.startswith("h_")
        
    def test_add_sphere(self, live_viz):
        """Test adding a sphere primitive."""
        handle = live_viz.add_sphere(radius=0.5)
        assert handle.startswith("h_")
        
    def test_set_transform(self, live_viz):
        """Test setting object transform."""
        handle = live_viz.add_box()
        live_viz.set_transform(handle, pos=(1, 2, 3))
        
        # Get transform to verify
        result = live_viz.get_transform(handle)
        assert result is not None
        
    def test_remove_object(self, live_viz):
        """Test removing an object."""
        handle = live_viz.add_box()
        live_viz.remove(handle)


class TestPointCloudIntegration:
    """Test point cloud operations with real Host."""
    
    def test_add_points(self, live_viz):
        """Test adding a point cloud."""
        import numpy as np
        
        positions = np.random.rand(100, 3).astype(np.float32)
        handle = live_viz.add_points(positions)
        assert handle.startswith("h_")
        
    def test_add_points_with_colors(self, live_viz):
        """Test adding colored point cloud."""
        import numpy as np
        
        n_points = 100
        positions = np.random.rand(n_points, 3).astype(np.float32)
        colors = np.random.rand(n_points, 3).astype(np.float32)
        
        handle = live_viz.add_points(positions, colors=colors)
        assert handle.startswith("h_")


class TestCameraIntegration:
    """Test camera control with real Host."""
    
    def test_reset_camera(self, live_viz):
        """Test camera reset."""
        live_viz.reset_camera()
        
    def test_set_view_home(self, live_viz):
        """Test setting view to home."""
        live_viz.set_view("home")


class TestSceneManagementIntegration:
    """Test scene management with real Host."""
    
    def test_clear(self, live_viz):
        """Test clearing the scene."""
        # Add some objects
        live_viz.add_box()
        live_viz.add_sphere()
        
        # Clear scene
        live_viz.clear()
        
    def test_list_scenes(self, live_viz):
        """Test listing scenes."""
        result = live_viz._client.send_command("list_scenes", {})
        assert "scenes" in result


class TestAuthenticationIntegration:
    """Test token authentication with real Host."""
    
    def test_authenticated_after_connect(self, live_viz):
        """Test that client is authenticated after connect."""
        # If we got here, authentication succeeded
        assert live_viz._client._opened.is_set()

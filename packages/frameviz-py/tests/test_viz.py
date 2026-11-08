"""
Unit tests for frameviz/viz.py high-level API.

Tests cover:
- Color normalization
- Vector/quaternion conversion
- Primitive creation (box, sphere, cylinder, etc.)
- Point cloud, lines, mesh operations
- Object manipulation (transform, color, visibility)
- Camera control
- Gizmo and picking
- Scene management
"""
from __future__ import annotations

import json
import logging

import pytest
import numpy as np

from frameviz.viz import _normalize_color, _to_list, _normalize_quat


# =============================================================================
# View Config Tests
# =============================================================================

class TestViewConfig:
    """Tests for view configuration methods."""

    def test_set_view_config_all_params(self, mock_viz):
        """Test setting all view configuration parameters."""
        viz, mock_server = mock_viz
        viz.set_view_config(
            show_grid=True,
            show_ground=True,
            show_axes=False,
            grid_color="red",
            grid_sub_color="#00ff00",
            axes_length=1.5,
            axes_radius=0.01,
            background="black",
        )

        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_view_config"
        config = cmd["args"]["config"]
        assert config["show_grid"] is True
        assert config["show_ground"] is True
        assert config["show_axes"] is False
        assert config["grid_color"] == [1.0, 0.0, 0.0]
        assert config["grid_sub_color"] == [0.0, 1.0, 0.0]
        assert config["axes_length"] == 1.5
        assert config["axes_radius"] == 0.01
        assert config["background"] == [0.0, 0.0, 0.0]

    def test_set_view_config_partial(self, mock_viz):
        """Test setting partial view configuration."""
        viz, mock_server = mock_viz
        viz.set_view_config(show_grid=True)

        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_view_config"
        assert cmd["args"]["config"] == {"show_grid": True}

    def test_set_view_config_axes_size_alias(self, mock_viz):
        """Test that axes_size acts as an alias for axes_length."""
        viz, mock_server = mock_viz
        viz.set_view_config(axes_size=2.5)

        cmd = mock_server.get_last_command()
        assert cmd["args"]["config"]["axes_length"] == 2.5

    def test_get_view_config_success(self, mock_viz):
        """Test getting view configuration successfully."""
        viz, mock_server = mock_viz
        mock_server.configure_response(
            "get_view_config",
            {"config": {"show_grid": True, "background": [0, 0, 0]}}
        )
        config = viz.get_view_config()
        assert config["show_grid"] is True
        assert config["background"] == [0, 0, 0]

    def test_get_view_config_empty(self, mock_viz):
        """Test getting view configuration when response is empty."""
        viz, mock_server = mock_viz
        mock_server.configure_response("get_view_config", {})
        config = viz.get_view_config()
        assert config == {}


# =============================================================================
# Color Normalization Tests
# =============================================================================

class TestNormalizeColor:
    """Tests for _normalize_color function."""
    
    def test_preset_red(self):
        """Test preset color 'red'."""
        assert _normalize_color("red") == [1.0, 0.0, 0.0]
        
    def test_preset_green(self):
        """Test preset color 'green'."""
        assert _normalize_color("green") == [0.0, 1.0, 0.0]
        
    def test_preset_blue(self):
        """Test preset color 'blue'."""
        assert _normalize_color("blue") == [0.0, 0.0, 1.0]
        
    def test_preset_white(self):
        """Test preset color 'white'."""
        assert _normalize_color("white") == [1.0, 1.0, 1.0]
        
    def test_preset_black(self):
        """Test preset color 'black'."""
        assert _normalize_color("black") == [0.0, 0.0, 0.0]
        
    def test_preset_case_insensitive(self):
        """Test that preset colors are case-insensitive."""
        assert _normalize_color("RED") == [1.0, 0.0, 0.0]
        assert _normalize_color("Red") == [1.0, 0.0, 0.0]
        
    def test_hex_color_red(self):
        """Test hex color #ff0000."""
        assert _normalize_color("#ff0000") == [1.0, 0.0, 0.0]
        
    def test_hex_color_green(self):
        """Test hex color #00ff00."""
        assert _normalize_color("#00ff00") == [0.0, 1.0, 0.0]
        
    def test_hex_color_blue(self):
        """Test hex color #0000ff."""
        assert _normalize_color("#0000ff") == [0.0, 0.0, 1.0]
        
    def test_hex_color_mixed(self):
        """Test hex color #804020."""
        result = _normalize_color("#804020")
        assert abs(result[0] - 128/255) < 0.01
        assert abs(result[1] - 64/255) < 0.01
        assert abs(result[2] - 32/255) < 0.01
        
    def test_rgb_tuple(self):
        """Test RGB tuple input."""
        assert _normalize_color((0.5, 0.5, 0.5)) == [0.5, 0.5, 0.5]
        
    def test_rgb_list(self):
        """Test RGB list input."""
        assert _normalize_color([0.2, 0.4, 0.6]) == [0.2, 0.4, 0.6]
        
    def test_rgba_tuple_preserves_alpha(self):
        """Test RGBA input preserves all 4 values."""
        result = _normalize_color((0.1, 0.2, 0.3, 0.5))
        assert result == [0.1, 0.2, 0.3, 0.5]
        
    def test_invalid_string_raises(self):
        """Test that unknown color string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown color"):
            _normalize_color("not_a_color")
            
    def test_out_of_range_raises(self):
        """Test that values outside 0-1 raise ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            _normalize_color([1.5, 0.0, 0.0])
            
    def test_negative_value_raises(self):
        """Test that negative values raise ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            _normalize_color([-0.1, 0.5, 0.5])


# =============================================================================
# Vector Conversion Tests
# =============================================================================

class TestToList:
    """Tests for _to_list function."""
    
    def test_tuple_input(self):
        """Test converting tuple to list."""
        assert _to_list((1.0, 2.0, 3.0)) == [1.0, 2.0, 3.0]
        
    def test_list_input(self):
        """Test list input returns a new list."""
        original = [1.0, 2.0, 3.0]
        result = _to_list(original)
        assert result == original
        
    def test_numpy_array(self):
        """Test converting numpy array to list."""
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = _to_list(arr)
        assert result == [1.0, 2.0, 3.0]
        assert isinstance(result, list)


# =============================================================================
# Quaternion Normalization Tests
# =============================================================================

class TestNormalizeQuat:
    """Tests for _normalize_quat function."""
    
    def test_identity_quaternion(self):
        """Test identity quaternion remains unchanged."""
        result = _normalize_quat([0.0, 0.0, 0.0, 1.0])
        assert result == [0.0, 0.0, 0.0, 1.0]
        
    def test_normalized_quaternion(self):
        """Test already normalized quaternion."""
        q = [0.0, 0.7071068, 0.0, 0.7071068]  # 90° around Y
        result = _normalize_quat(q)
        norm = sum(x**2 for x in result) ** 0.5
        assert abs(norm - 1.0) < 1e-6
        
    def test_unnormalized_quaternion(self):
        """Test unnormalized quaternion gets normalized."""
        q = [0.0, 0.0, 0.0, 2.0]  # Scale of 2
        result = _normalize_quat(q)
        assert abs(result[3] - 1.0) < 1e-6
        
    def test_zero_quaternion_returns_identity(self):
        """Test zero quaternion returns identity."""
        result = _normalize_quat([0.0, 0.0, 0.0, 0.0])
        assert result == [0.0, 0.0, 0.0, 1.0]
        
    def test_numpy_array_input(self):
        """Test numpy array input."""
        q = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        result = _normalize_quat(q)
        assert isinstance(result, list)
        assert result == [0.0, 0.0, 0.0, 1.0]


# =============================================================================
# Primitive Creation Tests
# =============================================================================

class TestAddBox:
    """Tests for Viz.add_box method."""
    
    def test_add_box_default(self, mock_viz):
        """Test adding box with default parameters."""
        viz, mock_server = mock_viz
        handle = viz.add_box()
        assert handle == "obj_1"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_primitive"
        assert cmd["args"]["type"] == "box"
        assert cmd["args"]["params"]["size"] == [1, 1, 1]
        
    def test_add_box_custom_size(self, mock_viz):
        """Test adding box with custom size."""
        viz, mock_server = mock_viz
        viz.add_box(size=[2, 3, 4])
        
        cmd = mock_server.get_last_command()
        assert cmd["args"]["params"]["size"] == [2, 3, 4]
        
    def test_add_box_custom_position(self, mock_viz):
        """Test adding box with custom position."""
        viz, mock_server = mock_viz
        viz.add_box(pos=[1, 2, 3])
        
        cmd = mock_server.get_last_command()
        assert cmd["args"]["pose"]["pos"] == [1, 2, 3]
        
    def test_add_box_custom_color(self, mock_viz):
        """Test adding box with custom color."""
        viz, mock_server = mock_viz
        viz.add_box(color="red")
        
        cmd = mock_server.get_last_command()
        assert cmd["args"]["color"] == [1.0, 0.0, 0.0]


class TestAddSphere:
    """Tests for Viz.add_sphere method."""
    
    def test_add_sphere_default(self, mock_viz):
        """Test adding sphere with default parameters."""
        viz, mock_server = mock_viz
        handle = viz.add_sphere()
        assert handle == "obj_1"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_primitive"
        assert cmd["args"]["type"] == "sphere"
        assert cmd["args"]["params"]["radius"] == 0.5
        
    def test_add_sphere_custom_radius(self, mock_viz):
        """Test adding sphere with custom radius."""
        viz, mock_server = mock_viz
        viz.add_sphere(radius=2.5)
        
        cmd = mock_server.get_last_command()
        assert cmd["args"]["params"]["radius"] == 2.5


class TestAddCylinder:
    """Tests for Viz.add_cylinder method."""
    
    def test_add_cylinder_default(self, mock_viz):
        """Test adding cylinder with default parameters."""
        viz, mock_server = mock_viz
        handle = viz.add_cylinder()
        assert handle == "obj_1"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_primitive"
        assert cmd["args"]["type"] == "cylinder"
        
    def test_add_cylinder_custom_params(self, mock_viz):
        """Test adding cylinder with custom radius and height."""
        viz, mock_server = mock_viz
        viz.add_cylinder(radius=0.3, height=2.0)
        
        cmd = mock_server.get_last_command()
        assert cmd["args"]["params"]["radius"] == 0.3
        assert cmd["args"]["params"]["height"] == 2.0


class TestAddCone:
    """Tests for Viz.add_cone method."""
    
    def test_add_cone_default(self, mock_viz):
        """Test adding cone with default parameters."""
        viz, mock_server = mock_viz
        handle = viz.add_cone()
        assert handle == "obj_1"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_primitive"
        assert cmd["args"]["type"] == "cone"


class TestAddArrow:
    """Tests for Viz.add_arrow method."""
    
    def test_add_arrow_default(self, mock_viz):
        """Test adding arrow with default parameters."""
        viz, mock_server = mock_viz
        handle = viz.add_arrow()
        assert handle == "obj_1"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_primitive"
        assert cmd["args"]["type"] == "arrow"
        
    def test_add_arrow_custom_endpoints(self, mock_viz):
        """Test adding arrow with custom endpoints."""
        viz, mock_server = mock_viz
        viz.add_arrow(start=[0, 0, 0], end=[1, 1, 1])
        
        cmd = mock_server.get_last_command()
        assert cmd["args"]["params"]["start"] == [0, 0, 0]
        assert cmd["args"]["params"]["end"] == [1, 1, 1]


class TestAddAxes:
    """Tests for Viz.add_axes method."""
    
    def test_add_axes_default(self, mock_viz):
        """Test adding axes with default parameters."""
        viz, mock_server = mock_viz
        handle = viz.add_axes()
        assert handle == "obj_1"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_primitive"
        assert cmd["args"]["type"] == "axes"


class TestAddPlane:
    """Tests for Viz.add_plane method."""
    
    def test_add_plane_default(self, mock_viz):
        """Test adding plane with default parameters."""
        viz, mock_server = mock_viz
        handle = viz.add_plane()
        assert handle == "obj_1"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_primitive"
        assert cmd["args"]["type"] == "plane"


# =============================================================================
# Point Cloud and Lines Tests
# =============================================================================

class TestAddPoints:
    """Tests for Viz.add_points method."""
    
    def test_add_points_positions_only(self, mock_viz, sample_point_cloud):
        """Test adding point cloud with positions only."""
        viz, mock_server = mock_viz
        handle = viz.add_points(sample_point_cloud["positions"], size=2.0)
        assert handle == "pc_1"
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_points"
        assert "positions" in cmd["args"]


class TestChunkGroups:
    """Tests for chunk group behavior and event mapping."""

    def test_resolve_group_target_empty(self, mock_viz):
        """Empty chunk group resolves to None."""
        viz, _ = mock_viz
        viz._chunk_groups["chunk_group_empty"] = []
        assert viz._resolve_group_target("chunk_group_empty") is None

    def test_list_objects_hides_chunk_children(self, mock_viz):
        """List objects hides chunk handles by default."""
        viz, mock_server = mock_viz
        viz._chunk_parent["h_1"] = "chunk_group_1"
        viz._chunk_parent["h_2"] = "chunk_group_1"
        mock_server.configure_response(
            "list_objects",
            {
                "objects": [
                    {"handle": "h_1", "type": "points", "visible": True},
                    {"handle": "h_2", "type": "points", "visible": True},
                ]
            },
        )
        objects = viz.list_objects()
        cmd = mock_server.get_last_command()
        assert cmd["args"]["include_internal"] is False
        handles = [obj["handle"] for obj in objects]
        assert "chunk_group_1" in handles
        assert "h_1" not in handles

    def test_pick_event_maps_group_and_index(self, mock_viz):
        """Pick events map chunk handle to group and global index."""
        viz, mock_server = mock_viz
        viz._chunk_parent["h_2"] = "chunk_group_1"
        viz._chunk_offsets["h_2"] = 500_000
        received = {}

        def handler(data):
            received.update(data)

        viz.on_pick(handler)
        envelope = {
            "type": "event",
            "name": "picked",
            "data": {"handle": "h_2", "point_index": 123},
        }
        mock_server._on_message_callback(json.dumps(envelope))
        viz._client.poll_events()
        assert received.get("handle") == "chunk_group_1"
        assert received.get("point_index") == 500_123

    def test_transformed_event_maps_group_handle(self, mock_viz):
        """Transformed events map chunk handle to group handle."""
        viz, mock_server = mock_viz
        viz._chunk_parent["h_4"] = "chunk_group_3"
        received = {}

        def handler(data):
            received.update(data)

        viz.on("transformed", handler)
        envelope = {
            "type": "event",
            "name": "transformed",
            "data": {"handle": "h_4", "pose": {"pos": [0, 0, 0], "quat": [0, 0, 0, 1]}},
        }
        mock_server._on_message_callback(json.dumps(envelope))
        viz._client.poll_events()
        assert received.get("handle") == "chunk_group_3"

    def test_get_picked_info_maps_group_and_index(self, mock_viz):
        """get_picked_info returns global point_index for chunked points."""
        viz, mock_server = mock_viz
        viz._chunk_parent["h_3"] = "chunk_group_2"
        viz._chunk_offsets["h_3"] = 1000
        envelope = {
            "type": "event",
            "name": "pick_info_response",
            "data": {"handle": "h_3", "point_index": 7, "view_id": viz.view_id},
        }
        mock_server._on_message_callback(json.dumps(envelope))
        info = viz.get_picked_info()
        assert info.get("handle") == "chunk_group_2"
        assert info.get("point_index") == 1007
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "get_picked_info"
        
    def test_add_points_with_colors(self, mock_viz, sample_point_cloud):
        """Test adding point cloud with colors."""
        viz, mock_server = mock_viz
        handle = viz.add_points(
            sample_point_cloud["positions"],
            colors=sample_point_cloud["colors"],
            size=3.0
        )
        assert handle == "pc_1"


class TestAddLines:
    """Tests for Viz.add_lines method."""
    
    def test_add_lines_without_indices(self, mock_viz):
        """Test adding lines without explicit indices."""
        viz, mock_server = mock_viz
        positions = np.array([[0, 0, 0], [1, 1, 1], [2, 0, 0]], dtype=np.float32)
        handle = viz.add_lines(positions, width=2.0, color="red")
        assert handle == "line_1"
        
    def test_add_lines_with_indices(self, mock_viz):
        """Test adding lines with explicit indices."""
        viz, mock_server = mock_viz
        positions = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
        indices = np.array([[0, 1], [1, 2], [2, 0]], dtype=np.uint32)
        handle = viz.add_lines(positions, indices=indices)
        assert handle == "line_1"


# =============================================================================
# Mesh Tests
# =============================================================================

class TestAddMesh:
    """Tests for Viz.add_mesh method."""
    
    def test_add_mesh_basic(self, mock_viz, sample_mesh):
        """Test adding basic mesh."""
        viz, mock_server = mock_viz
        handle = viz.add_mesh(sample_mesh["vertices"], sample_mesh["faces"])
        assert handle == "mesh_1"
    
    def test_add_mesh_color_uses_rgba_alpha(self, mock_viz, sample_mesh):
        """Test add_mesh uses color alpha when alpha is not provided."""
        viz, mock_server = mock_viz
        viz.add_mesh(sample_mesh["vertices"], sample_mesh["faces"], color=[1, 0, 0, 0.5])
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_mesh"
        assert cmd["args"]["color"] == [1, 0, 0]
        assert cmd["args"]["alpha"] == 0.5

    def test_add_mesh_alpha_has_priority(self, mock_viz, sample_mesh):
        """Test add_mesh alpha argument takes priority over color alpha."""
        viz, mock_server = mock_viz
        viz.add_mesh(
            sample_mesh["vertices"],
            sample_mesh["faces"],
            color=[1, 0, 0, 0.5],
            alpha=0.8,
        )
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_mesh"
        assert cmd["args"]["color"] == [1, 0, 0]
        assert cmd["args"]["alpha"] == 0.8

    def test_add_mesh_smooth_shading_default(self, mock_viz, sample_mesh):
        """Test add_mesh defaults to smooth shading without explicit override."""
        viz, mock_server = mock_viz
        viz.add_mesh(
            sample_mesh["vertices"],
            sample_mesh["faces"],
        )
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_mesh"
        assert "smooth_shading" not in cmd["args"]

    def test_add_mesh_smooth_shading_false_sends_override(self, mock_viz, sample_mesh):
        """Test add_mesh sends smooth_shading override when disabled."""
        viz, mock_server = mock_viz
        viz.add_mesh(
            sample_mesh["vertices"],
            sample_mesh["faces"],
            smooth_shading=False,
        )
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_mesh"
        assert cmd["args"]["smooth_shading"] is False

    def test_add_mesh_smooth_shading_type_error(self, mock_viz, sample_mesh):
        """Test add_mesh validates smooth_shading type."""
        viz, _ = mock_viz
        with pytest.raises(TypeError, match="smooth_shading must be a boolean"):
            viz.add_mesh(
                sample_mesh["vertices"],
                sample_mesh["faces"],
                smooth_shading="yes",  # type: ignore[arg-type]
            )

    def test_add_mesh_smooth_shading_accepts_numpy_bool(self, mock_viz, sample_mesh):
        """Test add_mesh accepts numpy bool for smooth_shading."""
        viz, mock_server = mock_viz
        viz.add_mesh(
            sample_mesh["vertices"],
            sample_mesh["faces"],
            smooth_shading=np.bool_(True),
        )
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_mesh"
        assert "smooth_shading" not in cmd["args"]


class TestLoadMesh:
    """Tests for Viz.load_mesh method."""
    
    def test_load_mesh_basic(self, mock_viz):
        """Test loading mesh from URL."""
        viz, mock_server = mock_viz
        handle = viz.load_mesh("/assets/model.dae")
        assert handle == "mesh_2"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "load_mesh"
        assert cmd["args"]["url"] == "/assets/model.dae"


# =============================================================================
# Object Manipulation Tests
# =============================================================================

class TestSetTransform:
    """Tests for Viz.set_transform method."""
    
    def test_set_transform_basic(self, mock_viz):
        """Test setting object transform."""
        viz, mock_server = mock_viz
        viz.set_transform("obj_1", pos=[1, 2, 3], quat=[0, 0, 0, 1])
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_transform"
        assert cmd["args"]["handle"] == "obj_1"
        assert cmd["args"]["pose"]["pos"] == [1, 2, 3]


class TestSetColor:
    """Tests for Viz.set_color method."""
    
    def test_set_color_preset(self, mock_viz):
        """Test setting color with preset name."""
        viz, mock_server = mock_viz
        viz.set_color("obj_1", "blue")
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_color"
        assert cmd["args"]["rgba"] == [0.0, 0.0, 1.0, 1.0]


class TestSetVisible:
    """Tests for Viz.set_visible method."""
    
    def test_set_visible_true(self, mock_viz):
        """Test setting visibility to true."""
        viz, mock_server = mock_viz
        viz.set_visible("obj_1", True)
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_visible"
        assert cmd["args"]["visible"] is True
        
    def test_set_visible_false(self, mock_viz):
        """Test setting visibility to false."""
        viz, mock_server = mock_viz
        viz.set_visible("obj_1", False)
        
        cmd = mock_server.get_last_command()
        assert cmd["args"]["visible"] is False


class TestRemove:
    """Tests for Viz.remove method."""
    
    def test_remove_object(self, mock_viz):
        """Test removing an object."""
        viz, mock_server = mock_viz
        viz.remove("obj_1")
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "remove_object"
        assert cmd["args"]["handle"] == "obj_1"


# =============================================================================
# Get Functions Tests
# =============================================================================

class TestGetTransform:
    """Tests for Viz.get_transform method."""
    
    def test_get_transform(self, mock_viz):
        """Test getting object transform."""
        viz, mock_server = mock_viz
        result = viz.get_transform("obj_1")
        assert result["pos"] == [1, 2, 3]
        assert result["quat"] == [0, 0, 0, 1]


class TestGetColor:
    """Tests for Viz.get_color method."""
    
    def test_get_color(self, mock_viz):
        """Test getting object color."""
        viz, mock_server = mock_viz
        result = viz.get_color("obj_1")
        assert result == [1, 0, 0, 1]

    def test_get_color_invalid_rgba_length(self, mock_viz):
        """Test get_color raises on invalid rgba length."""
        viz, mock_server = mock_viz
        mock_server.configure_response("get_color", {"rgba": [1, 0, 0]})
        with pytest.raises(RuntimeError, match="expected RGBA"):
            viz.get_color("obj_1")


class TestGetVisible:
    """Tests for Viz.get_visible method."""
    
    def test_get_visible(self, mock_viz):
        """Test getting object visibility."""
        viz, mock_server = mock_viz
        result = viz.get_visible("obj_1")
        assert result is True


# =============================================================================
# Camera Control Tests
# =============================================================================

class TestSetCameraPose:
    """Tests for Viz.set_camera_pose method."""
    
    def test_set_camera_pose(self, mock_viz):
        """Test setting camera pose."""
        viz, mock_server = mock_viz
        viz.set_camera_pose(eye=[5, 5, 5], target=[0, 0, 0], up=[0, 0, 1])
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_camera_pose"
        assert cmd["args"]["eye"] == [5, 5, 5]
        assert cmd["args"]["target"] == [0, 0, 0]
        assert cmd["args"]["up"] == [0, 0, 1]


class TestGetCameraPose:
    """Tests for Viz.get_camera_pose method."""

    def test_get_camera_pose_reports_missing_viewer_response(self, mock_viz):
        viz, _ = mock_viz
        with pytest.raises(TimeoutError, match="correlated query"):
            viz.get_camera_pose()


class TestSetView:
    """Tests for Viz.set_view method."""
    
    def test_set_view_home(self, mock_viz):
        """Test setting camera to home view."""
        viz, mock_server = mock_viz
        viz.set_view("home")
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_view"
        assert cmd["args"]["view"] == "home"


class TestResetCamera:
    """Tests for Viz.reset_camera method."""
    
    def test_reset_camera(self, mock_viz):
        """Test resetting camera."""
        viz, mock_server = mock_viz
        viz.reset_camera(mode="fit_scene")
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "reset_camera"
        assert cmd["args"]["mode"] == "fit_scene"


# =============================================================================
# Gizmo Tests
# =============================================================================

class TestGizmo:
    """Tests for gizmo-related methods."""

    def test_attach_gizmo_default(self, mock_viz):
        """Test attaching gizmo with default parameters."""
        viz, mock_server = mock_viz
        viz.attach_gizmo("obj_1")

        cmd = mock_server.get_last_command()
        assert cmd["name"] == "attach_gizmo"
        assert cmd["args"]["handle"] == "obj_1"

    def test_attach_gizmo_with_mask_and_size(self, mock_viz):
        """Test attaching gizmo with mask and size."""
        viz, mock_server = mock_viz
        viz.attach_gizmo("obj_1", size=1.5, mask=0x07)

        cmd = mock_server.get_last_command()
        assert cmd["name"] == "attach_gizmo"
        assert cmd["args"]["handle"] == "obj_1"
        assert cmd["args"]["size"] == 1.5
        assert cmd["args"]["mask"] == 0x07

    def test_attach_gizmo_with_scale_mode(self, mock_viz):
        """Test attaching gizmo with scale_mode."""
        viz, mock_server = mock_viz
        viz.attach_gizmo("obj_1", scale_mode="screen")

        cmd = mock_server.get_last_command()
        assert cmd["args"]["scale_mode"] == "screen"

    def test_set_gizmo_mode_mask(self, mock_viz):
        """Test changing gizmo mask."""
        viz, mock_server = mock_viz
        viz.set_gizmo_mode(mask=0x38)

        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_gizmo_mode"
        assert cmd["args"]["mask"] == 0x38

    def test_set_gizmo_mode_size(self, mock_viz):
        """Test changing gizmo size."""
        viz, mock_server = mock_viz
        viz.set_gizmo_mode(size=2.0)

        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_gizmo_mode"
        assert cmd["args"]["size"] == 2.0

    def test_detach_gizmo(self, mock_viz):
        """Test detaching gizmo."""
        viz, mock_server = mock_viz
        viz.detach_gizmo()

        cmd = mock_server.get_last_command()
        assert cmd["name"] == "detach_gizmo"


# =============================================================================
# Picking Tests
# =============================================================================

class TestPicking:
    """Tests for picking-related methods."""
    
    def test_set_pick_config(self, mock_viz):
        """Test setting pick configuration."""
        viz, mock_server = mock_viz
        viz.set_pick_config(enabled=True, mode="object")
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "set_pick_config"
        assert cmd["args"]["enabled"] is True
        assert cmd["args"]["mode"] == "object"

    def test_get_pick_config_reports_missing_viewer_response(self, mock_viz):
        viz, _ = mock_viz
        with pytest.raises(TimeoutError, match="correlated query"):
            viz.get_pick_config()

    def test_set_pick_config_invalid_mode(self, mock_viz):
        """Test that invalid pick mode raises ValueError."""
        viz, mock_server = mock_viz
        with pytest.raises(ValueError, match="mode must be"):
            viz.set_pick_config(mode="invalid")
            
    def test_clear_pick_highlight(self, mock_viz):
        """Test clearing pick highlight."""
        viz, mock_server = mock_viz
        viz.clear_pick_highlight()
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "clear_pick_highlight"


# =============================================================================
# Scene Management Tests
# =============================================================================

class TestSceneManagement:
    """Tests for scene management methods."""
    
    def test_clear(self, mock_viz):
        """Test clearing scene + overlays."""
        viz, mock_server = mock_viz
        viz.clear()

        cmd = mock_server.get_last_command()
        assert cmd["name"] == "clear_scene"
        assert cmd["args"]["scene_id"] == "s_test"
        assert cmd["args"]["view_id"] == "v_test"
        
    def test_attach_scene(self, mock_viz):
        """Test attaching to a different scene."""
        viz, mock_server = mock_viz
        viz.attach_scene("s_other")
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "attach_scene"
        assert cmd["args"]["scene_id"] == "s_other"
        assert viz._scene_id == "s_other"


class TestClose:
    """Tests for closing behavior."""

    def test_close_destroys_owned_scene(self, mock_viz):
        viz, mock_server = mock_viz
        viz.close()

        commands = [cmd["name"] for cmd in mock_server.get_all_commands()]
        assert "destroy_view" in commands
        assert "destroy_scene" in commands

    def test_close_destroys_scene_when_last_view(self, mock_client):
        """Test that a shared view destroys the scene when it's the last view using it."""
        from frameviz.viz import Viz

        client, mock_server = mock_client
        # Mock list_views to return empty list (no other views using this scene)
        mock_server.configure_response("list_views", {"views": []})

        viz = Viz(client=client, scene_id="s_shared", view_id="v_shared", opened_via_tauri=False, owns_scene=False)
        viz.close()

        commands = [cmd["name"] for cmd in mock_server.get_all_commands()]
        assert "destroy_view" in commands
        assert "list_views" in commands
        assert "destroy_scene" in commands  # Should destroy because it's the last view

    def test_close_shared_view_skips_destroy_when_other_views_exist(self, mock_client):
        """Test that a shared view does NOT destroy the scene when other views still use it."""
        from frameviz.viz import Viz

        client, mock_server = mock_client
        # Mock list_views to return another view using the same scene
        mock_server.configure_response(
            "list_views",
            {"views": [{"view_id": "v_other", "scene_id": "s_shared"}]},
        )

        viz = Viz(client=client, scene_id="s_shared", view_id="v_shared", opened_via_tauri=False, owns_scene=False)
        viz.close()

        commands = [cmd["name"] for cmd in mock_server.get_all_commands()]
        assert "destroy_view" in commands
        assert "list_views" in commands
        assert "destroy_scene" not in commands  # Should NOT destroy because other views exist

    def test_close_skips_destroy_when_other_views_exist(self, mock_viz):
        viz, mock_server = mock_viz
        mock_server.configure_response(
            "list_views",
            {"views": [{"view_id": "v_other", "scene_id": "s_test"}]},
        )
        viz.close()

        commands = [cmd["name"] for cmd in mock_server.get_all_commands()]
        assert "destroy_view" in commands
        assert "list_views" in commands
        assert "destroy_scene" not in commands


# =============================================================================
# Text Tests
# =============================================================================

class TestText:
    """Tests for text-related methods."""
    
    def test_add_text_3d(self, mock_viz):
        """Test adding 3D text."""
        viz, mock_server = mock_viz
        handle = viz.add_text_3d("Hello", pos=[0, 0, 1])
        assert handle == "text_1"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_text_3d"
        assert cmd["args"]["text"] == "Hello"
        
    def test_add_text_2d(self, mock_viz):
        """Test adding 2D text overlay."""
        viz, mock_server = mock_viz
        handle = viz.add_text_2d("Status", x=10, y=20)
        assert handle == "text2d_1"
        
        cmd = mock_server.get_last_command()
        assert cmd["name"] == "add_text_2d"


# =============================================================================
# Instances Tests
# =============================================================================

class TestInstances:
    """Tests for instanced rendering methods."""
    
    def test_add_instances_basic(self, mock_viz):
        """Test adding instanced primitives."""
        viz, mock_server = mock_viz
        positions = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=np.float32)
        handle = viz.add_instances("box", positions=positions, size=[0.1, 0.1, 0.1])
        assert handle == "inst_1"
        
        commands = mock_server.get_all_commands()
        cmd_names = [c["name"] for c in commands]
        assert "create_buffer" in cmd_names
        assert "add_instances" in cmd_names
        
        add_instances_cmd = [c for c in commands if c["name"] == "add_instances"][0]
        assert add_instances_cmd["args"]["type"] == "box"
        
    def test_add_instances_with_colors(self, mock_viz):
        """Test adding instanced primitives with per-instance colors."""
        viz, mock_server = mock_viz
        positions = np.array([[0, 0, 0], [1, 0, 0]], dtype=np.float32)
        colors = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
        handle = viz.add_instances("sphere", positions=positions, colors=colors)
        assert handle == "inst_1"
        
    def test_update_instances_positions(self, mock_viz):
        """Test updating instanced positions."""
        viz, mock_server = mock_viz
        new_positions = np.array([[0, 0, 1], [1, 0, 1]], dtype=np.float32)
        viz.update_instances("inst_1", positions=new_positions)
        
        commands = mock_server.get_all_commands()
        cmd_names = [c["name"] for c in commands]
        assert "update_instances" in cmd_names
        
        update_cmd = [c for c in commands if c["name"] == "update_instances"][0]
        assert update_cmd["args"]["handle"] == "inst_1"
        assert "positions" in update_cmd["args"]
        
    def test_update_instances_colors_only(self, mock_viz):
        """Test updating instanced colors without positions."""
        viz, mock_server = mock_viz
        new_colors = np.array([[0.0, 0.0, 1.0], [1.0, 1.0, 0.0]], dtype=np.float32)
        viz.update_instances("inst_1", colors=new_colors)
        
        commands = mock_server.get_all_commands()
        update_cmd = [c for c in commands if c["name"] == "update_instances"][0]
        assert "colors" in update_cmd["args"]
        
    def test_update_instances_with_alpha(self, mock_viz):
        """Test updating instances with alpha value."""
        viz, mock_server = mock_viz
        new_positions = np.array([[0, 0, 0]], dtype=np.float32)
        viz.update_instances("inst_1", positions=new_positions, alpha=0.5)
        
        commands = mock_server.get_all_commands()
        update_cmd = [c for c in commands if c["name"] == "update_instances"][0]
        assert update_cmd["args"]["alpha"] == 0.5


@pytest.mark.parametrize("accepted", [False, True])
def test_attach_scene_commits_local_binding_only_after_host_accepts(accepted):
    from frameviz.client import FrameVizClient
    from frameviz.exceptions import ProtocolError
    from frameviz.viz import Viz
    from unittest.mock import Mock

    client = Mock(spec=FrameVizClient)
    if accepted:
        client.send_command.return_value = {}
    else:
        client.send_command.side_effect = ProtocolError("Scene rejected", code="ERR_NOT_FOUND")
    viz = Viz(client, "original-scene", "existing-view", owns_view=False)
    if accepted:
        viz.attach_scene("next-scene")
    else:
        with pytest.raises(ProtocolError):
            viz.attach_scene("next-scene")
    assert viz.scene_id == ("next-scene" if accepted else "original-scene")
    client.send_command.assert_called_once_with("attach_scene", {
        "view_id": "existing-view", "scene_id": "next-scene",
    })

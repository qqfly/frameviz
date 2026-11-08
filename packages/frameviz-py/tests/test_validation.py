"""
Unit tests for input validation functions.

Tests cover:
- Vector validation (Vec3)
- Color validation (RGB/RGBA ranges)
- Positive value validation
- Parameter constraint checking
"""
from __future__ import annotations

import pytest
import numpy as np

from frameviz.viz import _normalize_color, _to_list, _normalize_quat
from frameviz.exceptions import ValidationError


# =============================================================================
# Vector Validation Tests
# =============================================================================

class TestVec3Validation:
    """Tests for 3D vector validation."""
    
    def test_valid_vec3_list(self):
        """Test valid Vec3 as list."""
        result = _to_list([1.0, 2.0, 3.0])
        assert result == [1.0, 2.0, 3.0]
        
    def test_valid_vec3_tuple(self):
        """Test valid Vec3 as tuple."""
        result = _to_list((1.0, 2.0, 3.0))
        assert result == [1.0, 2.0, 3.0]
        
    def test_valid_vec3_numpy(self):
        """Test valid Vec3 as numpy array."""
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = _to_list(arr)
        assert result == [1.0, 2.0, 3.0]
        
    def test_vec3_with_integers(self):
        """Test Vec3 with integer values."""
        result = _to_list([1, 2, 3])
        assert result == [1, 2, 3]
        
    def test_vec3_with_negative_values(self):
        """Test Vec3 with negative values."""
        result = _to_list([-1.0, -2.0, -3.0])
        assert result == [-1.0, -2.0, -3.0]

    def test_vec3_invalid_length(self):
        """Test Vec3 length validation."""
        with pytest.raises(ValueError, match="exactly 3 components"):
            _to_list([1.0, 2.0])
        with pytest.raises(ValueError, match="exactly 3 components"):
            _to_list([1.0, 2.0, 3.0, 4.0])


# =============================================================================
# Color Validation Tests
# =============================================================================

class TestColorValidation:
    """Tests for color value validation."""
    
    def test_color_at_boundaries(self):
        """Test color values at 0.0 and 1.0 boundaries."""
        assert _normalize_color([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]
        assert _normalize_color([1.0, 1.0, 1.0]) == [1.0, 1.0, 1.0]
        
    def test_color_out_of_range_high(self):
        """Test that color values > 1.0 raise error."""
        with pytest.raises(ValueError, match="out of range"):
            _normalize_color([1.1, 0.5, 0.5])
            
    def test_color_out_of_range_low(self):
        """Test that color values < 0.0 raise error."""
        with pytest.raises(ValueError, match="out of range"):
            _normalize_color([-0.1, 0.5, 0.5])
            
    def test_color_all_components_validated(self):
        """Test that all RGB components are validated."""
        # First component out of range
        with pytest.raises(ValueError):
            _normalize_color([1.5, 0.0, 0.0])
        # Second component out of range
        with pytest.raises(ValueError):
            _normalize_color([0.0, 1.5, 0.0])
        # Third component out of range
        with pytest.raises(ValueError):
            _normalize_color([0.0, 0.0, 1.5])
            
    def test_color_invalid_string(self):
        """Test that invalid color strings raise error."""
        with pytest.raises(ValueError, match="Unknown color"):
            _normalize_color("not_a_color")
            
    def test_color_invalid_hex_format(self):
        """Test that invalid hex format raises error."""
        with pytest.raises(ValueError, match="Unknown color"):
            _normalize_color("#ff00")  # Too short

    def test_color_invalid_length(self):
        """Test that invalid color length raises error."""
        with pytest.raises(ValueError, match="exactly 3 or 4 components"):
            _normalize_color([1.0, 0.0])  # Too short
        with pytest.raises(ValueError, match="exactly 3 or 4 components"):
            _normalize_color([1.0, 0.0, 0.0, 1.0, 0.5])  # Too long


# =============================================================================
# Quaternion Validation Tests
# =============================================================================

class TestQuaternionValidation:
    """Tests for quaternion validation."""
    
    def test_quaternion_normalization(self):
        """Test unnormalized quaternion gets normalized."""
        q = [0.0, 0.0, 0.0, 2.0]
        result = _normalize_quat(q)
        norm = sum(x**2 for x in result) ** 0.5
        assert abs(norm - 1.0) < 1e-6
        
    def test_quaternion_zero_returns_identity(self):
        """Test zero quaternion returns identity."""
        result = _normalize_quat([0.0, 0.0, 0.0, 0.0])
        assert result == [0.0, 0.0, 0.0, 1.0]
        
    def test_quaternion_very_small_values(self):
        """Test very small quaternion values."""
        result = _normalize_quat([1e-15, 1e-15, 1e-15, 1e-15])
        assert result == [0.0, 0.0, 0.0, 1.0]

    def test_quaternion_invalid_length(self):
        """Test quaternion length validation."""
        with pytest.raises(ValueError, match="exactly 4 components"):
            _normalize_quat([0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="exactly 4 components"):
            _normalize_quat([0.0, 0.0, 0.0, 1.0, 2.0])


# =============================================================================
# Parameter Constraint Tests
# =============================================================================

class TestParameterConstraints:
    """Tests for parameter constraints like positive values."""
    
    def test_radius_positive_values(self, mock_viz):
        """Test that positive radius values are accepted."""
        viz, mock_server = mock_viz
        # Should not raise
        viz.add_sphere(radius=0.5)
        viz.add_sphere(radius=1.0)
        viz.add_sphere(radius=100.0)
        
    def test_size_positive_values(self, mock_viz):
        """Test that positive size values are accepted."""
        viz, mock_server = mock_viz
        # Should not raise
        viz.add_box(size=[0.1, 0.1, 0.1])
        viz.add_box(size=[1.0, 2.0, 3.0])


# =============================================================================
# Exception Type Tests
# =============================================================================

class TestExceptionTypes:
    """Tests for custom exception types."""
    
    def test_validation_error_attributes(self):
        """Test ValidationError has correct attributes."""
        err = ValidationError(
            "Invalid value",
            parameter="radius",
            value=-1.0,
            constraint="must be positive"
        )
        assert err.parameter == "radius"
        assert err.value == -1.0
        assert err.constraint == "must be positive"
        
    def test_validation_error_inheritance(self):
        """Test ValidationError inherits from base error."""
        from frameviz.exceptions import FrameVizError
        err = ValidationError("test")
        assert isinstance(err, FrameVizError)
        assert isinstance(err, Exception)


# =============================================================================
# Pick Config Validation Tests
# =============================================================================

class TestPickConfigValidation:
    """Tests for pick configuration validation."""
    
    def test_pick_mode_valid_values(self, mock_viz):
        """Test valid pick modes are accepted."""
        viz, mock_server = mock_viz
        # Should not raise
        viz.set_pick_config(mode="object")
        viz.set_pick_config(mode="point")
        
    def test_pick_mode_invalid_value(self, mock_viz):
        """Test invalid pick mode raises ValueError."""
        viz, mock_server = mock_viz
        with pytest.raises(ValueError, match="mode must be"):
            viz.set_pick_config(mode="invalid")
            
    def test_pick_mode_case_sensitive(self, mock_viz):
        """Test pick mode is case-sensitive."""
        viz, mock_server = mock_viz
        with pytest.raises(ValueError):
            viz.set_pick_config(mode="Object")  # Should be lowercase

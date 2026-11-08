#!/usr/bin/env python3
"""
Test mesh color and alpha API improvements.

This test suite verifies:
1. Mutual exclusivity of color and colors parameters
2. Uniform color (color parameter) functionality
3. Vertex colors (colors parameter) functionality
4. get_color behavior for uniform vs vertex colors
5. set_color conversion from vertex to uniform colors
6. get_alpha for both color modes
7. set_alpha for both color modes
8. Combination of color and alpha parameters
"""

import os
import numpy as np
import frameviz as fv
import pytest

# Skip all tests in this module unless integration is enabled
pytestmark = pytest.mark.skipif(
    not os.environ.get("FRAMEVIZ_INTEGRATION_TEST"),
    reason="Integration tests require FRAMEVIZ_INTEGRATION_TEST=1",
)


def create_test_mesh():
    """Create a simple triangle mesh for testing."""
    vertices = np.array([
        [0, 0, 0],
        [1, 0, 0],
        [0.5, 1, 0],
    ], dtype=np.float32)

    faces = np.array([
        [0, 1, 2],
    ], dtype=np.uint32)

    return vertices, faces


def open_viz_or_skip():
    try:
        return fv.open(window_mode=0)
    except Exception as e:
        pytest.fail(f"Explicit Host integration could not connect: {e}")


def test_mesh_color_mutually_exclusive():
    """Test that color and colors parameters are mutually exclusive."""
    print("\n" + "=" * 70)
    print("TEST: color and colors mutual exclusivity")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Create vertex colors
    colors = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)

    # Should raise ValueError when both are provided
    with pytest.raises(ValueError, match="mutually exclusive"):
        viz.add_mesh(
            vertices,
            faces,
            colors=colors,
            color=[1, 1, 1],  # Should conflict with colors
        )

    viz.close()
    print("✓ Mutual exclusivity check works correctly")


def test_mesh_uniform_color():
    """Test creating mesh with uniform color parameter."""
    print("\n" + "=" * 70)
    print("TEST: Mesh with uniform color")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Create mesh with uniform color
    handle = viz.add_mesh(
        vertices,
        faces,
        color=[1, 0, 0],  # Red
    )

    assert handle, "Mesh should be created successfully"
    print(f"✓ Mesh created with uniform color: {handle}")

    viz.close()


def test_mesh_vertex_colors():
    """Test creating mesh with per-vertex colors."""
    print("\n" + "=" * 70)
    print("TEST: Mesh with vertex colors")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Create vertex colors (RGB gradient)
    colors = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)

    # Create mesh with vertex colors
    handle = viz.add_mesh(
        vertices,
        faces,
        colors=colors,
    )

    assert handle, "Mesh should be created successfully"
    print(f"✓ Mesh created with vertex colors: {handle}")

    viz.close()


def test_get_color_uniform():
    """Test get_color returns RGBA for uniform color meshes."""
    print("\n" + "=" * 70)
    print("TEST: get_color for uniform color mesh")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Create mesh with uniform color
    handle = viz.add_mesh(
        vertices,
        faces,
        color=[0.8, 0.2, 0.3],  # Custom color
    )

    # Get color should return RGBA
    result = viz.get_color(handle)

    assert result is not None, "get_color should return a value for uniform color mesh"
    assert isinstance(result, list), "Result should be a list"
    assert len(result) == 4, "Result should have 4 elements (RGBA)"

    print(f"✓ get_color returned: {result}")
    print(f"  Expected RGB: [0.8, 0.2, 0.3]")
    print(f"  Got RGB: [{result[0]:.2f}, {result[1]:.2f}, {result[2]:.2f}]")

    viz.close()


def test_get_color_vertex_returns_none():
    """Test get_color returns None for vertex color meshes."""
    print("\n" + "=" * 70)
    print("TEST: get_color returns None for vertex colors")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Create vertex colors
    colors = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)

    # Create mesh with vertex colors
    handle = viz.add_mesh(
        vertices,
        faces,
        colors=colors,
    )

    # Get color should return None for vertex color mesh
    result = viz.get_color(handle)

    assert result is None, "get_color should return None for vertex color mesh"
    print("✓ get_color correctly returned None for vertex color mesh")

    viz.close()


def test_set_color_converts_vertex_to_uniform():
    """Test set_color converts vertex color mesh to uniform color."""
    print("\n" + "=" * 70)
    print("TEST: set_color converts vertex to uniform color")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Create vertex colors
    colors = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)

    # Create mesh with vertex colors
    handle = viz.add_mesh(
        vertices,
        faces,
        colors=colors,
    )

    # Verify it starts with vertex colors
    result_before = viz.get_color(handle)
    assert result_before is None, "Should have vertex colors initially"
    print("✓ Mesh initially has vertex colors (get_color returns None)")

    # Convert to uniform color using set_color
    viz.set_color(handle, [0, 1, 1])  # Cyan

    # Verify it now has uniform color
    result_after = viz.get_color(handle)
    assert result_after is not None, "Should have uniform color after set_color"
    assert isinstance(result_after, list), "Result should be a list"
    print(f"✓ After set_color, mesh has uniform color: {result_after}")

    viz.close()


def test_get_alpha_uniform():
    """Test get_alpha for uniform color mesh."""
    print("\n" + "=" * 70)
    print("TEST: get_alpha for uniform color mesh")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Create mesh with uniform color and alpha
    handle = viz.add_mesh(
        vertices,
        faces,
        color=[1, 0, 0],
        alpha=0.6,
    )

    # Get alpha
    result = viz.get_alpha(handle)

    assert isinstance(result, float), "get_alpha should return a float"
    print(f"✓ get_alpha returned: {result:.2f} (expected: 0.60)")

    # Allow small floating point differences
    assert abs(result - 0.6) < 0.01, f"Alpha should be close to 0.6, got {result}"

    viz.close()


def test_get_alpha_vertex():
    """Test get_alpha for vertex color mesh."""
    print("\n" + "=" * 70)
    print("TEST: get_alpha for vertex color mesh")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Create vertex colors with alpha
    colors = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)

    handle = viz.add_mesh(
        vertices,
        faces,
        colors=colors,
        alpha=0.4,
    )

    # Get alpha should work for vertex color mesh too
    result = viz.get_alpha(handle)

    assert isinstance(result, float), "get_alpha should return a float"
    print(f"✓ get_alpha returned: {result:.2f} (expected: 0.40)")

    # Allow small floating point differences
    assert abs(result - 0.4) < 0.01, f"Alpha should be close to 0.4, got {result}"

    viz.close()


def test_set_alpha_both_modes():
    """Test set_alpha works for both uniform and vertex color meshes."""
    print("\n" + "=" * 70)
    print("TEST: set_alpha for both color modes")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Test with uniform color
    handle_uniform = viz.add_mesh(
        vertices,
        faces,
        color=[1, 0, 0],
    )

    viz.set_alpha(handle_uniform, 0.5)
    alpha_uniform = viz.get_alpha(handle_uniform)
    print(f"✓ Uniform color mesh alpha: {alpha_uniform:.2f}")
    assert abs(alpha_uniform - 0.5) < 0.01

    # Test with vertex colors
    colors = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    vertices_offset = vertices + np.array([2, 0, 0])

    handle_vertex = viz.add_mesh(
        vertices_offset,
        faces,
        colors=colors,
    )

    viz.set_alpha(handle_vertex, 0.7)
    alpha_vertex = viz.get_alpha(handle_vertex)
    print(f"✓ Vertex color mesh alpha: {alpha_vertex:.2f}")
    assert abs(alpha_vertex - 0.7) < 0.01

    viz.close()


def test_color_alpha_combination():
    """Test combining color and alpha parameters."""
    print("\n" + "=" * 70)
    print("TEST: color + alpha parameter combination")
    print("=" * 70)

    viz = open_viz_or_skip()
    vertices, faces = create_test_mesh()

    # Create mesh with both color and alpha
    handle = viz.add_mesh(
        vertices,
        faces,
        color=[1, 0.5, 0],  # Orange
        alpha=0.3,
    )

    # Verify color
    result_color = viz.get_color(handle)
    assert result_color is not None, "Should have uniform color"
    print(f"✓ Color: [{result_color[0]:.2f}, {result_color[1]:.2f}, {result_color[2]:.2f}]")

    # Verify alpha
    result_alpha = viz.get_alpha(handle)
    print(f"✓ Alpha: {result_alpha:.2f}")
    assert abs(result_alpha - 0.3) < 0.01, f"Alpha should be 0.3, got {result_alpha}"

    viz.close()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("MESH COLOR/ALPHA API TEST SUITE")
    print("=" * 70)

    test_mesh_color_mutually_exclusive()
    test_mesh_uniform_color()
    test_mesh_vertex_colors()
    test_get_color_uniform()
    test_get_color_vertex_returns_none()
    test_set_color_converts_vertex_to_uniform()
    test_get_alpha_uniform()
    test_get_alpha_vertex()
    test_set_alpha_both_modes()
    test_color_alpha_combination()

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! ✓")
    print("=" * 70)

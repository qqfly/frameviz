#!/usr/bin/env python3
"""
Test script to verify mesh alpha and wireframe parameters.

This script tests two new features:
1. Mesh transparency (alpha parameter)
2. Mesh edge visibility control (wireframe parameter)
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
    """Create a simple cube mesh for testing."""
    # Cube vertices (8 corners)
    vertices = np.array([
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],  # bottom face
        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],   # top face
    ], dtype=np.float32)

    # Cube faces (12 triangles, 2 per square face)
    faces = np.array([
        # Bottom face (z=0)
        [0, 1, 2], [0, 2, 3],
        # Top face (z=1)
        [4, 5, 6], [4, 6, 7],
        # Front face (y=0)
        [0, 1, 5], [0, 5, 4],
        # Back face (y=1)
        [2, 3, 7], [2, 7, 6],
        # Left face (x=0)
        [0, 3, 7], [0, 7, 4],
        # Right face (x=1)
        [1, 2, 6], [1, 6, 5],
    ], dtype=np.uint32)

    return vertices, faces


def create_vertex_colors(vertices, rgb_color):
    """Create uniform vertex colors for all vertices."""
    v_count = vertices.shape[0]
    colors = np.tile(rgb_color, (v_count, 1)).astype(np.float32)
    return colors


def open_viz_or_skip(**kwargs):
    try:
        kwargs.setdefault("window_mode", 0)
        return fv.open(**kwargs)
    except Exception as e:
        pytest.fail(f"Explicit Host integration could not connect: {e}")


def test_alpha_transparency():
    """Test mesh alpha (transparency) parameter."""
    print("=" * 70)
    print("Test 1: Mesh Alpha (Transparency)")
    print("=" * 70)

    viz = open_viz_or_skip(title="Mesh Alpha Test", x=100, y=100, width=800, height=600)

    vertices, faces = create_test_mesh()

    # Create three meshes with different alpha values
    print("\n[1] Adding opaque mesh (alpha=1.0) at position (0, 0, 0)")
    red_colors = create_vertex_colors(vertices, [1, 0, 0])
    h1 = viz.add_mesh(vertices, faces, colors=red_colors, alpha=1.0)

    print("[2] Adding semi-transparent mesh (alpha=0.5) at position (1.5, 0, 0)")
    vertices2 = vertices.copy() + np.array([1.5, 0, 0], dtype=np.float32)
    green_colors = create_vertex_colors(vertices2, [0, 1, 0])
    h2 = viz.add_mesh(vertices2, faces, colors=green_colors, alpha=0.5)

    print("[3] Adding highly transparent mesh (alpha=0.2) at position (3.0, 0, 0)")
    vertices3 = vertices.copy() + np.array([3.0, 0, 0], dtype=np.float32)
    blue_colors = create_vertex_colors(vertices3, [0, 0, 1])
    h3 = viz.add_mesh(vertices3, faces, colors=blue_colors, alpha=0.2)

    # Set camera to view all three meshes
    viz.set_camera_pose(eye=[2, 2, 4], target=[1.5, 0.5, 0.5])

    print("\n✓ Created three meshes with different transparency levels:")
    print("  - Red mesh:   alpha=1.0 (opaque)")
    print("  - Green mesh: alpha=0.5 (semi-transparent)")
    print("  - Blue mesh:  alpha=0.2 (highly transparent)")

    # Test get_alpha() method
    print("\n[4] Testing get_alpha() method:")
    alpha1 = viz.get_alpha(h1)
    alpha2 = viz.get_alpha(h2)
    alpha3 = viz.get_alpha(h3)
    print(f"  - Red mesh alpha:   {alpha1:.2f} (expected: 1.00)")
    print(f"  - Green mesh alpha: {alpha2:.2f} (expected: 0.50)")
    print(f"  - Blue mesh alpha:  {alpha3:.2f} (expected: 0.20)")

    # Verify values
    assert abs(alpha1 - 1.0) < 0.01, f"Red mesh alpha should be 1.0, got {alpha1}"
    assert abs(alpha2 - 0.5) < 0.01, f"Green mesh alpha should be 0.5, got {alpha2}"
    assert abs(alpha3 - 0.2) < 0.01, f"Blue mesh alpha should be 0.2, got {alpha3}"
    print("✓ get_alpha() returns correct values")

    viz.close()


def test_wireframe():
    """Test mesh wireframe parameter."""
    print("\n" + "=" * 70)
    print("Test 2: Mesh Wireframe (Edge Visibility)")
    print("=" * 70)

    viz = open_viz_or_skip(title="Mesh Wireframe Test", x=950, y=100, width=800, height=600)

    vertices, faces = create_test_mesh()

    # Create two meshes: one with wireframe, one without
    print("\n[1] Adding mesh WITHOUT wireframe (wireframe=False) at position (0, 0, 0)")
    red_colors = create_vertex_colors(vertices, [1, 0, 0])
    h1 = viz.add_mesh(vertices, faces, colors=red_colors, wireframe=False)

    print("[2] Adding mesh WITH wireframe (wireframe=True) at position (1.5, 0, 0)")
    vertices2 = vertices.copy() + np.array([1.5, 0, 0], dtype=np.float32)
    green_colors = create_vertex_colors(vertices2, [0, 1, 0])
    h2 = viz.add_mesh(vertices2, faces, colors=green_colors, wireframe=True)

    # Set camera to view both meshes
    viz.set_camera_pose(eye=[1, 1, 3], target=[0.75, 0.5, 0.5])

    print("\n✓ Created two meshes:")
    print("  - Red mesh:   wireframe=False (no edge lines)")
    print("  - Green mesh: wireframe=True (shows black edge lines)")

    viz.close()


def test_combined():
    """Test mesh with both alpha and wireframe."""
    print("\n" + "=" * 70)
    print("Test 3: Combined Alpha + Wireframe")
    print("=" * 70)

    viz = open_viz_or_skip(title="Combined Test", x=100, y=400, width=800, height=600)

    vertices, faces = create_test_mesh()

    # Create transparent mesh with wireframe
    print("\n[1] Adding transparent mesh with wireframe at position (0, 0, 0)")
    red_colors = create_vertex_colors(vertices, [1, 0, 0])
    h1 = viz.add_mesh(vertices, faces, colors=red_colors, alpha=0.6, wireframe=True)

    print("[2] Adding opaque mesh without wireframe at position (1.5, 0, 0)")
    vertices2 = vertices.copy() + np.array([1.5, 0, 0], dtype=np.float32)
    blue_colors = create_vertex_colors(vertices2, [0, 0, 1])
    h2 = viz.add_mesh(vertices2, faces, colors=blue_colors, alpha=1.0, wireframe=False)

    # Set camera
    viz.set_camera_pose(eye=[1, 1, 3], target=[0.75, 0.5, 0.5])

    print("\n✓ Created two meshes with combined settings:")
    print("  - Red mesh:   alpha=0.6, wireframe=True (transparent with edges)")
    print("  - Blue mesh:  alpha=1.0, wireframe=False (opaque without edges)")

    viz.close()


def main():
    """Run tests interactively with visual verification."""
    print("\n" + "=" * 70)
    print("FrameViz Mesh Alpha and Wireframe Feature Test")
    print("=" * 70)

    try:
        # Test 1: Alpha transparency
        test_alpha_transparency()
        input("\nPress Enter to continue to next test...")

        # Test 2: Wireframe control
        test_wireframe()
        input("\nPress Enter to continue to next test...")

        # Test 3: Combined
        test_combined()

        print("\n" + "=" * 70)
        print("✓ All mesh tests completed!")
        print("=" * 70)

        print("\n✓ All tests passed!")
        return 0

    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

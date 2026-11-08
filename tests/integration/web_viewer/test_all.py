"""Comprehensive test for all FrameViz features."""

__test__ = False

import frameviz as fv
import numpy as np
import time


def test_primitives(viz):
    """Test primitive shapes."""
    print("\n" + "=" * 50)
    print("Testing Primitives")
    print("=" * 50)
    
    # Box
    box = viz.add_box(size=[1, 1, 1], pos=[0, 0, 0.5], color='red')
    print(f"  Box: {box}")
    
    # Sphere
    sphere = viz.add_sphere(radius=0.4, pos=[2, 0, 0.4], color='blue')
    print(f"  Sphere: {sphere}")
    
    # Cylinder
    cylinder = viz.add_cylinder(radius=0.3, height=1.0, pos=[-2, 0, 0.5], color='green')
    print(f"  Cylinder: {cylinder}")
    
    # Cone
    cone = viz.add_cone(radius=0.3, height=0.8, pos=[0, 2, 0.4], color='yellow')
    print(f"  Cone: {cone}")
    
    # Plane
    plane = viz.add_plane(width=2, height=2, pos=[0, -2, 0.01], color=[0.5, 0.5, 0.5])
    print(f"  Plane: {plane}")
    
    return box, sphere, cylinder


def test_rgba_transparency(viz):
    """Test RGBA transparency support."""
    print("\n" + "=" * 50)
    print("Testing RGBA Transparency")
    print("=" * 50)
    
    # Opaque red box
    box1 = viz.add_box(size=[0.8, 0.8, 0.8], pos=[4, 0, 0.4], color=[1, 0, 0, 1.0])
    print(f"  Opaque red box: {box1}")
    
    # Semi-transparent green box
    box2 = viz.add_box(size=[0.8, 0.8, 0.8], pos=[4.3, 0.3, 0.7], color=[0, 1, 0, 0.5])
    print(f"  Semi-transparent green box (alpha=0.5): {box2}")
    
    # Very transparent blue box
    box3 = viz.add_box(size=[0.8, 0.8, 0.8], pos=[4.6, 0.6, 1.0], color=[0, 0, 1, 0.3])
    print(f"  Transparent blue box (alpha=0.3): {box3}")
    
    return box1, box2, box3


def test_points(viz):
    """Test point cloud rendering."""
    print("\n" + "=" * 50)
    print("Testing Point Cloud")
    print("=" * 50)
    
    # Random point cloud
    n = 500
    positions = np.random.randn(n, 3).astype(np.float32) * 0.5 + [6, 0, 1]
    colors = (np.random.rand(n, 3) * 255).astype(np.uint8)
    
    points = viz.add_points(positions, colors=colors, size=5)
    print(f"  Point cloud ({n} points): {points}")
    
    return points


def test_lines(viz):
    """Test line rendering."""
    print("\n" + "=" * 50)
    print("Testing Lines")
    print("=" * 50)
    
    # Helix
    t = np.linspace(0, 4 * np.pi, 100)
    positions = np.column_stack([
        np.cos(t) - 4,
        np.sin(t),
        t / 4
    ]).astype(np.float32)
    
    lines = viz.add_lines(positions, color='cyan', width=2)
    print(f"  Helix line: {lines}")
    
    return lines


def test_mesh(viz):
    """Test mesh rendering."""
    print("\n" + "=" * 50)
    print("Testing Mesh")
    print("=" * 50)
    
    # Simple pyramid
    vertices = np.array([
        [0, 0, 0],      # Base corners
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0.5, 0.5, 1],  # Apex
    ], dtype=np.float32)
    
    faces = np.array([
        [0, 1, 4],  # Sides
        [1, 2, 4],
        [2, 3, 4],
        [3, 0, 4],
        [0, 2, 1],  # Base
        [0, 3, 2],
    ], dtype=np.uint32)
    
    colors = np.array([
        [255, 0, 0],    # Red
        [0, 255, 0],    # Green
        [0, 0, 255],    # Blue
        [255, 255, 0],  # Yellow
        [255, 255, 255], # White apex
    ], dtype=np.uint8)
    
    mesh = viz.add_mesh(vertices, faces, colors=colors)
    viz.set_transform(mesh, pos=[-4, 2, 0])
    print(f"  Pyramid mesh: {mesh}")
    
    return mesh


def test_transforms(viz, box, sphere):
    """Test transform operations."""
    print("\n" + "=" * 50)
    print("Testing Transforms")
    print("=" * 50)
    
    # Move box up
    viz.set_transform(box, pos=[0, 0, 1.5])
    print("  Moved box up")
    time.sleep(0.5)
    
    # Rotate box
    viz.set_transform(box, pos=[0, 0, 1.5], quat=[0, 0, 0.383, 0.924])  # 45° around Z
    print("  Rotated box 45°")
    time.sleep(0.5)
    
    # Change color
    viz.set_color(sphere, color='purple')
    print("  Changed sphere color to purple")
    time.sleep(0.5)
    
    # Toggle visibility
    viz.set_visible(box, False)
    print("  Hidden box")
    time.sleep(0.5)
    viz.set_visible(box, True)
    print("  Shown box")


def test_gizmo(viz, box):
    """Test Gizmo functionality."""
    print("\n" + "=" * 50)
    print("Testing Gizmo")
    print("=" * 50)
    
    # Attach translate gizmo
    viz.attach_gizmo(box, mode='translate', size=1.5)
    print("  Attached translate gizmo (size=1.5)")
    print("  → Drag the arrows to move the box!")
    time.sleep(3)
    
    # Switch to rotate mode
    viz.attach_gizmo(box, mode='rotate', size=1.2)
    print("  Switched to rotate gizmo (size=1.2)")
    print("  → Drag the circles to rotate!")
    time.sleep(3)
    
    # Switch to scale mode
    viz.attach_gizmo(box, mode='scale')
    print("  Switched to scale gizmo")
    print("  → Drag to scale!")
    time.sleep(3)
    
    # Detach
    viz.detach_gizmo()
    print("  Detached gizmo")


def test_picking(viz):
    """Test picking configuration."""
    print("\n" + "=" * 50)
    print("Testing Picking")
    print("=" * 50)
    
    # Configure picking
    viz.set_pick_config(
        enabled=True,
        mode='object',  # Highlight objects
        button=2,  # Right click
        ctrl_modifier=False  # No need for Ctrl
    )
    print("  Enabled picking: Right-click on objects")
    print("  → Try right-clicking on objects!")
    print("  → Selected objects will be highlighted yellow")
    time.sleep(5)
    
    # Switch to point mode
    viz.set_pick_config(mode='point')
    print("  Switched to point mode - shows axes at pick location")
    time.sleep(3)
    
    # Switch back to object mode
    viz.set_pick_config(mode='object')
    print("  Switched back to object mode")


def test_camera(viz):
    """Test camera control."""
    print("\n" + "=" * 50)
    print("Testing Camera")
    print("=" * 50)
    
    # Set specific camera pose
    viz.set_camera_pose(eye=[10, 10, 8], target=[0, 0, 1], up=[0, 0, 1])
    print("  Set camera: eye=[10,10,8] target=[0,0,1]")
    time.sleep(2)
    
    # Animate camera orbit
    print("  Animating camera orbit...")
    for i in range(36):
        angle = i * 10 * np.pi / 180
        x = 10 * np.cos(angle)
        y = 10 * np.sin(angle)
        viz.set_camera_pose(eye=[x, y, 6], target=[0, 0, 0.5], up=[0, 0, 1])
        time.sleep(0.05)
    
    # Reset to default
    viz.reset_camera()
    print("  Reset camera")


def main():
    print("=" * 60)
    print("FrameViz Comprehensive Test")
    print("=" * 60)
    
    viz = fv.open()
    print(f"Connected! scene={viz.scene_id}, view={viz.view_id}")
    
    # Clear scene
    viz.clear_scene()
    print("Cleared scene")
    
    # Run all tests
    box, sphere, cylinder = test_primitives(viz)
    test_rgba_transparency(viz)
    test_points(viz)
    test_lines(viz)
    test_mesh(viz)
    test_transforms(viz, box, sphere)
    test_gizmo(viz, box)
    test_picking(viz)
    test_camera(viz)
    
    print("\n" + "=" * 60)
    print("✅ All tests complete!")
    print("=" * 60)
    
    # Keep connection open
    print("\nPress Ctrl+C to exit...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        viz.close()
        print("\nClosed.")


if __name__ == "__main__":
    main()

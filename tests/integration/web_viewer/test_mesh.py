"""Test mesh rendering with various configurations."""

__test__ = False

import frameviz as fv
import numpy as np
import time


def create_cube_mesh():
    """Create a simple cube mesh."""
    vertices = np.array([
        # Front face
        [-0.5, -0.5,  0.5],
        [ 0.5, -0.5,  0.5],
        [ 0.5,  0.5,  0.5],
        [-0.5,  0.5,  0.5],
        # Back face
        [-0.5, -0.5, -0.5],
        [ 0.5, -0.5, -0.5],
        [ 0.5,  0.5, -0.5],
        [-0.5,  0.5, -0.5],
    ], dtype=np.float32)
    
    faces = np.array([
        # Front
        [0, 1, 2], [0, 2, 3],
        # Back
        [5, 4, 7], [5, 7, 6],
        # Top
        [3, 2, 6], [3, 6, 7],
        # Bottom
        [4, 5, 1], [4, 1, 0],
        # Right
        [1, 5, 6], [1, 6, 2],
        # Left
        [4, 0, 3], [4, 3, 7],
    ], dtype=np.uint32)
    
    return vertices, faces


def create_sphere_mesh(radius=0.5, segments=16):
    """Create a UV sphere mesh."""
    vertices = []
    faces = []
    
    for i in range(segments + 1):
        theta = i * np.pi / segments
        for j in range(segments):
            phi = j * 2 * np.pi / segments
            x = radius * np.sin(theta) * np.cos(phi)
            y = radius * np.sin(theta) * np.sin(phi)
            z = radius * np.cos(theta)
            vertices.append([x, y, z])
    
    for i in range(segments):
        for j in range(segments):
            p1 = i * segments + j
            p2 = i * segments + (j + 1) % segments
            p3 = (i + 1) * segments + (j + 1) % segments
            p4 = (i + 1) * segments + j
            faces.append([p1, p2, p3])
            faces.append([p1, p3, p4])
    
    return np.array(vertices, dtype=np.float32), np.array(faces, dtype=np.uint32)


def main():
    print("=" * 60)
    print("FrameViz Mesh Rendering Test")
    print("=" * 60)
    
    viz = fv.open()
    print(f"Connected! scene={viz.scene_id}, view={viz.view_id}")
    
    # Clear scene
    viz.clear_scene()
    
    # Test 1: Simple triangle
    print("\n--- Test 1: Simple Triangle ---")
    vertices = np.array([
        [0, 0, 0],
        [1, 0, 0],
        [0.5, 0.866, 0],
    ], dtype=np.float32)
    faces = np.array([[0, 1, 2]], dtype=np.uint32)
    
    tri = viz.add_mesh(vertices, faces)
    print(f"Triangle mesh: {tri}")
    
    # Test 2: Cube mesh
    print("\n--- Test 2: Cube Mesh ---")
    cube_verts, cube_faces = create_cube_mesh()
    cube = viz.add_mesh(cube_verts, cube_faces)
    viz.set_transform(cube, pos=[2, 0, 0.5])
    print(f"Cube mesh: {cube}")
    
    # Test 3: Cube with vertex colors
    print("\n--- Test 3: Cube with Vertex Colors ---")
    colors = np.array([
        [255, 0, 0],    # Red
        [0, 255, 0],    # Green
        [0, 0, 255],    # Blue
        [255, 255, 0],  # Yellow
        [255, 0, 255],  # Magenta
        [0, 255, 255],  # Cyan
        [255, 128, 0],  # Orange
        [128, 0, 255],  # Purple
    ], dtype=np.uint8)
    
    colored_cube = viz.add_mesh(cube_verts, cube_faces, colors=colors)
    viz.set_transform(colored_cube, pos=[4, 0, 0.5])
    print(f"Colored cube: {colored_cube}")
    
    # Test 4: Sphere mesh
    print("\n--- Test 4: Sphere Mesh ---")
    sphere_verts, sphere_faces = create_sphere_mesh(radius=0.5, segments=16)
    sphere = viz.add_mesh(sphere_verts, sphere_faces)
    viz.set_transform(sphere, pos=[0, 2, 0.5])
    print(f"Sphere mesh: {sphere}")
    
    # Test 5: Transform and color operations
    print("\n--- Test 5: Transform & Color ---")
    viz.set_color(cube, color=[0, 1, 0])  # Make cube green
    print("Set cube color to green")
    
    time.sleep(1)
    
    viz.set_transform(cube, pos=[2, 0, 1.5], quat=[0, 0, 0.383, 0.924])  # Rotate 45°
    print("Transformed cube")
    
    print("\n" + "=" * 60)
    print("✅ Mesh tests complete!")
    print("Check the browser to see the meshes.")
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

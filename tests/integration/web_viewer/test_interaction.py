"""Test interactive features: Gizmo, Picking, Camera control."""

__test__ = False

from frameviz import FrameVizClient, Viz
import numpy as np
import time

def main():
    print("Connecting to FrameViz...")
    client = FrameVizClient()
    client.connect()
    
    # Create scene and view
    scene_result = client.send_command("create_scene", {})
    scene_id = scene_result.get("scene_id", "s_1")
    
    view_result = client.send_command("create_view", {"scene_id": scene_id})
    view_id = view_result.get("view_id", "v_1")
    
    viz = Viz(client, scene_id, view_id)
    
    # Clear and set up scene
    viz.clear_scene()
    
    # Add some primitives to interact with
    box1 = viz.add_box(size=[1, 1, 1], pos=[0, 0, 0.5], color="red")
    print(f"Added box: {box1}")
    
    sphere1 = viz.add_sphere(radius=0.5, pos=[2, 0, 0.5], color="blue")
    print(f"Added sphere: {sphere1}")
    
    cylinder1 = viz.add_cylinder(radius=0.3, height=1.0, pos=[-2, 0, 0.5], color="green")
    print(f"Added cylinder: {cylinder1}")
    
    # Configure picking (Ctrl + Right-click)
    print("\n--- Picking Config ---")
    print("Enabling picking with Ctrl + Right-click")
    viz.set_pick_config(enabled=True, button=2, ctrl_modifier=True)
    
    # Set camera position
    print("\n--- Camera Control ---")
    print("Setting camera to view from above-front")
    viz.set_camera_pose(eye=[5, 5, 4], target=[0, 0, 0], up=[0, 0, 1])
    time.sleep(1)
    
    # Attach gizmo to box
    print("\n--- Gizmo ---")
    print(f"Attaching translate gizmo to box ({box1})")
    viz.attach_gizmo(box1, mode="translate")
    
    print("\n✅ Interactive features enabled!")
    print("\nInstructions:")
    print("  • Drag the gizmo arrows to move the red box")
    print("  • Ctrl + Right-click on objects to pick them")
    print("  • Check browser console for picked/transformed events")
    print("\nSwitching gizmo modes in 5 seconds...")
    
    time.sleep(5)
    
    # Switch to rotate mode
    print("\nSwitching gizmo to ROTATE mode")
    viz.attach_gizmo(box1, mode="rotate")
    time.sleep(5)
    
    # Switch to scale mode
    print("\nSwitching gizmo to SCALE mode")
    viz.attach_gizmo(box1, mode="scale")
    time.sleep(5)
    
    # Move gizmo to sphere
    print(f"\nMoving gizmo to sphere ({sphere1})")
    viz.attach_gizmo(sphere1, mode="translate")
    time.sleep(5)
    
    # Detach gizmo
    print("\nDetaching gizmo")
    viz.detach_gizmo()
    
    # Animate camera
    print("\n--- Camera Animation ---")
    for i in range(36):
        angle = i * 10 * np.pi / 180
        x = 5 * np.cos(angle)
        y = 5 * np.sin(angle)
        viz.set_camera_pose(eye=[x, y, 4], target=[0, 0, 0], up=[0, 0, 1])
        time.sleep(0.1)
    
    print("\n✅ Test complete!")
    print("Closing connection...")
    client.close()

if __name__ == "__main__":
    main()

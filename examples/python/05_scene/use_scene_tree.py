"""Move a child between parent frames and inspect its local and world poses.

Run this file with the matching FrameViz SDK. Press Enter at each step.
"""
import frameviz as fv


def build(viz):
    first = viz.add_node(name="Left frame", position=[-1, 0, 0])
    second = viz.add_node(name="Right frame", position=[1, 0, 0])
    for parent in (first, second):
        viz.add_axes(parent=parent, length=0.4)

    box = viz.add_box(parent=first, name="Box", tags={"example": "reparent"},
                      position=[0, 0, 0.25], size=[0.5, 0.5, 0.5], color="orange")
    marker = viz.add_sphere(parent=box, position=[0, 0, 0.5], radius=0.1, color="blue")
    viz.set_camera_pose([3, -5, 3], [0, 0, 0.3])
    return second, box, marker


def main():
    viz = fv.open(title="Scene tree")
    try:
        second, box, marker = build(viz)
        input("Press Enter to change parent while preserving the box's world pose. ")
        viz.set_parent(box, second)
        print("Local position:", viz.get_transform(box)["position"])
        print("World position:", viz.get_transform(box, space="world")["position"])
        input("Press Enter to move the box to a specified pose in the new frame. ")
        # Seven elements are local translation xyz followed by quaternion xyzw.
        viz.set_parent(box, second, local_transform=[0, 0, 0.25, 0, 0, 0, 1])
        viz.set_geometry_scale(box, [2, 1, 1])
        print("Marker world position:", viz.get_transform(marker, space="world")["position"])
        for item in viz.get_display_state(include_bounds=True)["objects"]:
            print(item["name"] or item["type"], item["parent"],
                  item["world_transform"]["position"], item.get("tags"), item.get("world_bounds"))
        input("The box is wider; the blue marker kept its local offset. Enter to exit. ")
    finally:
        viz.close()


if __name__ == "__main__":
    main()

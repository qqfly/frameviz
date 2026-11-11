"""Animate a planar three-link arm using local poses in the FrameViz scene tree."""

import math
import time

import frameviz as fv

LENGTHS = (0.8, 0.7, 0.6)
JOINT_OFFSETS = ((0, 0, 0.1), (LENGTHS[0], 0, 0), (LENGTHS[1], 0, 0))


def build_arm(viz):
    joints, links = [], []
    colors = ([0.9, 0.2, 0.2], [0.2, 0.9, 0.2], [0.2, 0.2, 0.9])
    for index, (length, offset, color) in enumerate(zip(LENGTHS, JOINT_OFFSETS, colors), 1):
        joint = viz.add_node(parent=joints[-1] if joints else None,
                             position=offset, name=f"Joint {index}")
        link = viz.add_box(size=[length, 0.1, 0.1], parent=joint,
                           position=[length / 2, 0, 0], color=color, name=f"Link {index}")
        joints.append(joint)
        links.append(link)
    return joints, links


def set_joint_angles(viz, joints, angles):
    viz.set_object_transforms([
        {"handle": joint, "position": offset,
         "quaternion": [0, 0, math.sin(angle / 2), math.cos(angle / 2)]}
        for joint, offset, angle in zip(joints, JOINT_OFFSETS, angles)
    ])


def main():
    viz = fv.open()
    try:
        viz.add_plane(width=6, height=6, color=[0.3, 0.3, 0.3, 0.5])
        viz.add_axes(length=1)
        joints, _ = build_arm(viz)
        viz.set_camera_pose(eye=[4, 4, 3], target=[1.2, 0, 0.1], up=[0, 0, 1])
        viz.add_text_2d("Planar arm · local joint poses", x=12, y=12, color="white")
        for step in range(200):
            t = step * 0.05
            set_joint_angles(viz, joints, (
                0.6 * math.sin(t), 0.8 * math.sin(t * 0.7 + 0.5),
                0.6 * math.sin(t * 0.9 + 1.2),
            ))
            time.sleep(0.03)
        input("Animation complete. Press Enter to exit...")
    finally:
        viz.close()


if __name__ == "__main__":
    main()

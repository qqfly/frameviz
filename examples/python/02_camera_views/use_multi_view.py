"""Open two Views with different cameras. Use --app for desktop windows."""

import argparse

import frameviz as fv


def build(independent=False, *, app=False):
    window_mode = 2 if app else 1
    left = fv.open(title="Front View", window_mode=window_mode, reuse_browser=False)
    try:
        right = fv.open(title="Top View", window_mode=window_mode, reuse_browser=False,
                        share_scene=None if independent else left.scene_id)
    except BaseException:
        left.close()
        raise
    return left, right


def populate(left, right, independent=False):
    box = left.add_box(size=[0.8, 0.6, 0.6], position=[0, 0, 0.3], color="#4682b4")
    if independent:
        right.add_sphere(radius=0.3, position=[0, 0, 0.3], color="orange")
    left.set_camera_pose([3, -4, 2], [0, 0, 0.3])
    right.set_camera_pose([0, 0, 4], [0, 0, 0.3], [0, 1, 0])
    return box


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--independent", action="store_true")
    parser.add_argument("--app", action="store_true", help="Prefer desktop App windows")
    args = parser.parse_args()
    left, right = build(args.independent, app=args.app)
    try:
        box = populate(left, right, args.independent)
        for view in (left, right):
            print(f"scene_id={view.scene_id} view_id={view.view_id}")
        if args.app:
            input("Rotate one window and compare the other. Enter to move the box. ")
        else:
            input("Rotate one View or refresh a tab. Enter to move the box. ")
        left.set_transform(box, position=[0.7, 0, 0.3])
        input("Check which Views show the move. Enter to exit. ")
    finally:
        right.close()
        left.close()


if __name__ == "__main__":
    main()

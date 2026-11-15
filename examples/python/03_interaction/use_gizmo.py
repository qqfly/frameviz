"""Click an object and drag its Gizmo. Use --mode rotate or --mode both to compare."""

import argparse

import frameviz as fv


def build(viz, mode="translate", size=0.8):
    box = viz.add_box(position=[-0.6, 0, 0.3], size=[0.6, 0.6, 0.6], color="#4682b4")
    sphere = viz.add_sphere(position=[0.6, 0, 0.3], radius=0.3, color="orange")
    # The low three bits enable XYZ translation, the next three enable XYZ rotation.
    mask = {"translate": 0x07, "rotate": 0x38, "both": 0x3F}[mode]
    viz.set_pick_config(enabled=True, mode="object", button=0, ctrl_modifier=False)
    viz.set_camera_pose([2, -4, 2.5], [0, 0, 0.3])

    def picked(event):
        if event.get("handle") in (box, sphere):
            viz.attach_gizmo(event["handle"], mask=mask, size=size, scale_mode="world")

    def moved(event):
        print("World pose:", event["world_transform"], flush=True)

    viz.on_pick(picked)
    viz.on_transform(moved)
    return box, sphere


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["translate", "rotate", "both"], default="translate")
    parser.add_argument("--size", type=float, default=0.8)
    args = parser.parse_args()
    viz = fv.open(title="Gizmo")
    try:
        build(viz, args.mode, args.size)
    except BaseException:
        viz.close()
        raise
    print("Click an object and drag its handles. Ctrl+C to exit.")
    viz.keep_running()


if __name__ == "__main__":
    main()

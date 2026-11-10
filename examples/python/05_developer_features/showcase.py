"""Small, deterministic scenes used by the README media.

Run with an installed matching FrameViz App/Host, for example:
    python examples/python/05_developer_features/showcase.py instances
The synthetic data demonstrates APIs, not throughput or measured sensor data.
"""
import argparse
import time

import frameviz as fv
import numpy as np


def configure(viz, eye, target=(0, 0, 0), up=(0, 0, 1)):
    viz.set_view_config(show_axes=False, show_grid=False, background=(1, 1, 1))
    viz.set_camera_pose(eye, target, up=up)


def mesh(viz):
    """Indexed triangles with interpolated per-vertex RGB colors."""
    x, y = np.meshgrid(np.linspace(-1.5, 1.5, 22), np.linspace(-1.5, 1.5, 22))
    z = 0.65 * np.cos(1.6 * x) * np.sin(1.6 * y)
    vertices = np.column_stack((x.ravel(), y.ravel(), z.ravel())).astype(np.float32)
    faces = []
    for row in range(21):
        for col in range(21):
            i = row * 22 + col
            faces.extend(((i, i + 1, i + 22), (i + 1, i + 23, i + 22)))
    faces = np.asarray(faces, dtype=np.uint32)
    t = ((z.ravel() + 0.65) / 1.3).astype(np.float32)
    colors = np.column_stack((0.15 + 0.8 * t, 0.6 - 0.3 * t, 0.9 - 0.7 * t))
    handle = viz.add_mesh(vertices, faces, colors=colors, smooth_shading=True)
    configure(viz, (5.4, -7.2, 5.5))
    return {"handle": handle, "vertices": vertices, "faces": faces, "colors": colors}


def instances(viz):
    """169 colored boxes, updated with full replacement arrays."""
    x, y = np.meshgrid(np.linspace(-2, 2, 13), np.linspace(-2, 2, 13))
    xy = np.column_stack((x.ravel(), y.ravel())).astype(np.float32)
    positions, colors = instance_frame(xy, 0)
    handle = viz.add_instances("box", positions=positions, size=(0.22, 0.22, 0.22), colors=colors)
    configure(viz, (7.5, -9.5, 8), (0, 0, 0.5))
    return {"handle": handle, "xy": xy, "count": len(positions)}


def instance_frame(xy, phase):
    z = 0.55 + 0.4 * np.sin(xy[:, 0] * 1.5 + phase) * np.cos(xy[:, 1] * 1.5 + phase)
    positions = np.column_stack((xy, z)).astype(np.float32)
    colors = np.column_stack((0.2 + 0.7 * z, 0.45 + 0.25 * (1 - z), 0.9 - 0.65 * z)).astype(np.float32)
    return positions, colors


def picking(viz):
    box = viz.add_box(size=(0.9, 0.9, 0.9), pos=(-0.8, 0, 0.45), color=(0.2, 0.5, 0.87))
    sphere = viz.add_sphere(radius=0.48, pos=(0.9, 0, 0.48), color=(0.95, 0.62, 0.18))
    configure(viz, (4, -7.5, 4.5), (0, 0, 0.5))
    viz.set_pick_config(enabled=True, mode="object", button=0)
    events = []

    def picked(event):
        if event.get("handle") in (box, sphere):
            events.append(event)
            viz.attach_gizmo(event["handle"], mask=0x07, size=0.8, scale_mode="world")

    viz.on_pick(picked)
    viz.on_transform(lambda event: events.append(event))
    return {"box": box, "sphere": sphere, "events": events}


def shared(viz):
    box = viz.add_box(size=(0.95, 0.75, 0.9), pos=(-0.7, 0, 0.45), color=(0.2, 0.5, 0.87))
    sphere = viz.add_sphere(radius=0.38, pos=(0.85, 0, 0.38), color=(0.95, 0.62, 0.18))
    configure(viz, (4, -6, 4), (0, 0, 0.4))
    return {"box": box, "sphere": sphere}


def labels(viz, url):
    """Load a served STL/DAE URL; file:// and arbitrary local paths are not URLs."""
    model = viz.load_mesh(url, color=(0.2, 0.55, 0.8))
    label = viz.add_text_3d("Loaded STL", pos=(0, 0, 1.5), font_size=23, color="black", background_color="rgba(245,248,252,0.92)")
    overlay = viz.add_text_2d("World label + screen overlay", x=32, y=540, font_size=18, color="black")
    configure(viz, (4.5, -6.5, 4.0), (0, 0, 0.6))
    return {"handle": model, "label": label, "overlay": overlay}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("mesh", "instances", "picking", "labels"))
    parser.add_argument("--model-url", help="HTTP(S) URL of an STL or DAE, required for labels")
    args = parser.parse_args()
    if args.case == "labels" and not args.model_url:
        parser.error("labels requires --model-url")
    viz = fv.open(title=f"FrameViz: {args.case}")
    try:
        data = labels(viz, args.model_url) if args.case == "labels" else globals()[args.case](viz)
        if args.case == "instances":
            print("Ctrl+C to stop")
            for i in range(180):
                positions, colors = instance_frame(data["xy"], i / 20)
                viz.update_instances(data["handle"], positions=positions, colors=colors)
                time.sleep(0.05)
        elif args.case == "mesh":
            input("Vertex colors. Enter: uniform color... ")
            viz.set_color(data["handle"], (0.2, 0.55, 0.8))
            input("Enter: wireframe... ")
            viz.set_render_mode("wireframe")
        elif args.case == "picking":
            print("Click an object, then drag its translation handles. Ctrl+C to stop.")
            viz.keep_running()
            return
        print("Ctrl+C to close.")
        viz.keep_running()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        viz.close()


if __name__ == "__main__":
    main()

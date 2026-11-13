"""Display the pinned SO-101 model and drive its joints with FrameViz sliders."""

import argparse
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import frameviz as fv
import numpy as np

from so101_model import MODEL_FILES, ensure_so101_model


# Binary STL stores a normal, three vertices and an attribute field per triangle.
STL_TRIANGLE = np.dtype([
    ("normal", "<f4", 3), ("vertices", "<f4", (3, 3)), ("attribute", "<u2"),
])


def read_stl(path):
    data = path.read_bytes()
    count = int.from_bytes(data[80:84], "little")
    if not count or len(data) != 84 + count * STL_TRIANGLE.itemsize:
        raise ValueError(f"Invalid SO-101 binary STL: {path}")
    corners = np.frombuffer(data, dtype=STL_TRIANGLE, offset=84)["vertices"]
    vertices, indices = np.unique(corners.reshape(-1, 3), axis=0, return_inverse=True)
    return vertices, indices.reshape(-1, 3).astype(np.uint32)


def vector(element, key, default):
    return np.fromstring(element.get(key, default), sep=" ")


def local_pose(element):
    position = vector(element, "pos", "0 0 0").tolist()
    quat = vector(element, "quat", "1 0 0 0")
    return {"position": position,
            "quaternion": (quat[[1, 2, 3, 0]] / np.linalg.norm(quat)).tolist()}


@dataclass
class Joint:
    name: str
    handle: str
    rest: dict
    axis: np.ndarray
    limits: np.ndarray
    angle: float = 0.0

    def pose(self):
        # The six hinges in this pinned model pivot at their body origins.
        # Compose the rest orientation with the local hinge rotation (xyzw).
        x, y, z, w = self.rest["quaternion"]
        i, j, k = self.axis * math.sin(self.angle / 2)
        s = math.cos(self.angle / 2)
        return {"position": self.rest["position"], "quaternion": [
            w * i + x * s + y * k - z * j,
            w * j - x * k + y * s + z * i,
            w * k + x * j - y * i + z * s,
            w * s - x * i - y * j - z * k,
        ]}


def read_model(path):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != MODEL_FILES["so101.xml"][1]:
        raise ValueError("Use so101.xml from the pinned SO-101 revision in the example README")
    return ET.fromstring(data)


class So101:
    def __init__(self, viz, model_path):
        self.viz = viz
        model_path = Path(model_path)
        model = read_model(model_path)
        self.bodies = {}
        self.geometry = []
        self.joints = []
        colors = {m.attrib["name"]: vector(m, "rgba", ".7 .7 .7 1").tolist()
                  for m in model.findall("./asset/material")}
        paths = {m.get("name", Path(m.attrib["file"]).stem):
                 model_path.parent / "assets" / m.attrib["file"]
                 for m in model.findall("./asset/mesh")}
        meshes = {}

        def add_body(body, parent):
            name = body.attrib["name"]
            rest = local_pose(body)
            handle = viz.add_node(parent=parent, name=name, pose=rest)
            self.bodies[name] = handle
            hinge = body.find("joint")
            if hinge is not None:
                axis = vector(hinge, "axis", "0 0 1")
                self.joints.append(Joint(hinge.attrib["name"], handle, rest,
                                         axis / np.linalg.norm(axis), vector(hinge, "range", "")))

            for geom in body.findall("geom"):
                if geom.get("class") != "visual" and geom.get("group") not in ("1", "2"):
                    continue
                options = dict(parent=handle, name=name, pose=local_pose(geom),
                               color=colors[geom.attrib["material"]])
                kind = geom.attrib["type"]
                if kind == "mesh":
                    path = paths[geom.attrib["mesh"]]
                    if path not in meshes:
                        meshes[path] = read_stl(path)
                    drawable = viz.add_mesh(*meshes[path], **options)
                elif kind == "box":
                    drawable = viz.add_box(size=(2 * vector(geom, "size", "")).tolist(), **options)
                elif kind == "cylinder":
                    radius, half_height = vector(geom, "size", "")
                    drawable = viz.add_cylinder(radius=float(radius), height=float(2 * half_height), **options)
                else:
                    raise ValueError(f"Unsupported SO-101 visual geometry: {kind}")
                self.geometry.append((name, drawable))

            for child in body.findall("body"):
                add_body(child, handle)

        add_body(model.find("./worldbody/body"), None)
        viz.set_view_config(show_axes=False)
        viz.set_camera_pose([.72, -.83, .58], [.08, 0, .19])

    def update(self):
        self.viz.set_object_transforms([
            {"handle": joint.handle, "pose": joint.pose()} for joint in self.joints
        ])

    def add_controls(self):
        viz = self.viz
        group = viz.add_widget("group", "SO-101 joint angles")
        controls = {}
        for joint in self.joints:
            lower, upper = joint.limits
            control = viz.add_widget("number", f"{joint.name} (rad)", joint.angle,
                                     parent=group, minimum=float(lower), maximum=float(upper),
                                     step=.01, update_mode="continuous")
            controls[joint.name] = control

            def change(event, joint=joint):
                joint.angle = event["value"]
                viz.set_transform(joint.handle, pose=joint.pose())

            viz.on_widget_change(control, change)

        def reset(_):
            for joint in self.joints:
                joint.angle = 0.0
                viz.set_widget_value(controls[joint.name], 0.0)
            self.update()

        viz.on_widget_change(viz.add_widget("button", "Reset pose", parent=group), reset)
        viz.set_pick_config(enabled=True, mode="object", button=0, ctrl_modifier=False)
        viz.on_pick(lambda event: print(event["name"]) if event.get("name") else None)
        return controls


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", nargs="?", type=Path,
                        help="Path to the pinned so101.xml (default: use the model cache)")
    parser.add_argument("--cache-dir", type=Path, help="Root directory for downloaded models")
    parser.add_argument("--controls", action="store_true", help="Show joint sliders")
    args = parser.parse_args()
    try:
        model_path = (ensure_so101_model(args.cache_dir, show_progress=True)
                      if args.model is None else args.model.expanduser())
    except (OSError, RuntimeError) as error:
        parser.error(str(error))

    print("Opening FrameViz and building the SO-101 scene…", file=sys.stderr, flush=True)
    viz = fv.open(title="SO-101 · FrameViz")
    try:
        robot = So101(viz, model_path)
        if args.controls:
            robot.add_controls()
    except (OSError, ValueError) as error:
        viz.close()
        parser.error(str(error))
    except BaseException:
        viz.close()
        raise
    print("SO-101 scene ready. Press Ctrl+C to close.", file=sys.stderr, flush=True)
    viz.keep_running()

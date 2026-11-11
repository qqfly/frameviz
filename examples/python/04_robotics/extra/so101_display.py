"""Display the external MuJoCo Menagerie SO-101 model using generic scene nodes."""
import argparse
from pathlib import Path

import frameviz as fv
import mujoco as mj
import numpy as np


def xyzw(q):
    return q[[1, 2, 3, 0]].tolist()


class So101:
    def __init__(self, viz, model_path):
        self.viz = viz
        self.model = mj.MjModel.from_xml_path(str(Path(model_path).resolve()))
        self.data = mj.MjData(self.model)
        mj.mj_forward(self.model, self.data)
        self.bodies = {}
        self.geometry = {}
        for body in range(1, self.model.nbody):
            parent = int(self.model.body_parentid[body])
            self.bodies[body] = viz.add_node(
                parent=self.bodies.get(parent), pose=self.local_pose(body, parent),
                name=self.model.body(body).name, tags={"body_index": body},
            )
        for geom, group in enumerate(self.model.geom_group):
            if group in (1, 2):
                self.geometry[geom] = self.add_geometry(geom)
        viz.set_view_config(show_axes=False)
        viz.set_camera_pose([.72, -.83, .58], [.08, 0, .19])

    def local_pose(self, body, parent):
        data = self.data
        inverse = np.empty(4)
        relative = np.empty(4)
        mj.mju_negQuat(inverse, data.xquat[parent])
        mj.mju_mulQuat(relative, inverse, data.xquat[body])
        offset = data.xmat[parent].reshape(3, 3).T @ (data.xpos[body] - data.xpos[parent])
        return {"position": offset.tolist(), "quaternion": xyzw(relative)}

    def add_geometry(self, geom):
        model = self.model
        body = int(model.geom_bodyid[geom])
        material = int(model.geom_matid[geom])
        rgba = model.mat_rgba[material] if material >= 0 else model.geom_rgba[geom]
        options = dict(parent=self.bodies.get(body), name=model.body(body).name,
                       tags={"geom_index": geom}, position=model.geom_pos[geom].tolist(),
                       quaternion=xyzw(model.geom_quat[geom]), color=rgba.tolist())
        geom_type = int(model.geom_type[geom])
        size = model.geom_size[geom]
        if geom_type == mj.mjtGeom.mjGEOM_BOX:
            return self.viz.add_box(size=(2 * size).tolist(), **options)
        if geom_type == mj.mjtGeom.mjGEOM_CYLINDER:
            return self.viz.add_cylinder(radius=float(size[0]), height=float(2 * size[1]), **options)
        if geom_type == mj.mjtGeom.mjGEOM_MESH:
            mesh = model.geom_dataid[geom]
            start, end = model.mesh_vertadr[mesh], model.mesh_vertadr[mesh] + model.mesh_vertnum[mesh]
            first, last = model.mesh_faceadr[mesh], model.mesh_faceadr[mesh] + model.mesh_facenum[mesh]
            return self.viz.add_mesh(model.mesh_vert[start:end], model.mesh_face[first:last], **options)
        raise ValueError(f"SO-101 demo has no display mapping for visual geom type {geom_type}")

    def update(self):
        mj.mj_forward(self.model, self.data)
        self.viz.set_object_transforms([
            {"handle": handle, "pose": self.local_pose(body, self.model.body_parentid[body])}
            for body, handle in self.bodies.items()
        ])


    def add_controls(self):
        viz, model = self.viz, self.model
        group = viz.add_widget("group", "SO-101 joint angles")
        controls = {}
        addresses = {}
        for joint in range(model.njnt):
            if model.jnt_type[joint] != mj.mjtJoint.mjJNT_HINGE:
                continue
            name = model.joint(joint).name
            address = int(model.jnt_qposadr[joint])
            lower, upper = model.jnt_range[joint]
            control = viz.add_widget("number", f"{name} (rad)", float(self.data.qpos[address]),
                                     parent=group, minimum=float(lower), maximum=float(upper),
                                     step=.01, update_mode="continuous")
            controls[name] = control
            addresses[control] = address

            def change(event, qpos_address=address):
                self.data.qpos[qpos_address] = event["value"]
                self.update()

            viz.on_widget_change(control, change)

        def reset(_):
            self.data.qpos[:] = model.qpos0
            self.update()
            for control, address in addresses.items():
                viz.set_widget_value(control, float(self.data.qpos[address]))

        viz.on_widget_change(viz.add_widget("button", "Reset pose", parent=group), reset)
        viz.set_pick_config(enabled=True, mode="object", button=0, ctrl_modifier=False)
        viz.on_pick(lambda event: print(event["name"]) if event.get("name") else None)
        return controls


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", help="Path to the separately downloaded so101.xml")
    parser.add_argument("--controls", action="store_true", help="Show joint sliders")
    args = parser.parse_args()
    viz = fv.open(title="SO-101 · MuJoCo display")
    try:
        robot = So101(viz, args.model)
        if args.controls:
            robot.add_controls()
        viz.keep_running()
    finally:
        viz.close()

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", help="Path to the separately downloaded so101.xml")
    args = parser.parse_args()
    viz = fv.open(title="SO-101 · MuJoCo display")
    try:
        So101(viz, args.model)
        viz.keep_running()
    finally:
        viz.close()

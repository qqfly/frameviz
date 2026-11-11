//! Conservative world-space bounds for geometry already held by the Host.
use super::{Host, Pose, SceneObject};
use serde::Serialize;
use serde_json::Value;

#[derive(Clone, Copy, Serialize)]
pub(super) struct Bounds {
    min: [f64; 3],
    max: [f64; 3],
}

impl Bounds {
    fn empty() -> Self {
        Self {
            min: [f64::INFINITY; 3],
            max: [f64::NEG_INFINITY; 3],
        }
    }

    fn centered(half: [f64; 3]) -> Self {
        Self {
            min: half.map(|x| -x.abs()),
            max: half.map(f64::abs),
        }
    }

    fn include(&mut self, point: [f64; 3]) -> Option<()> {
        if !point.iter().all(|v| v.is_finite()) {
            return None;
        }
        for (axis, value) in point.into_iter().enumerate() {
            self.min[axis] = self.min[axis].min(value);
            self.max[axis] = self.max[axis].max(value);
        }
        Some(())
    }

    fn finished(self) -> Option<Self> {
        self.min.iter().all(|x| x.is_finite()).then_some(self)
    }

    fn transform(&self, pose: &Pose, scale: [f64; 3]) -> Option<Self> {
        let mut result = Self::empty();
        for mask in 0..8 {
            let corner = std::array::from_fn(|axis| {
                scale[axis]
                    * if (mask & (1 << axis)) == 0 {
                        self.min[axis]
                    } else {
                        self.max[axis]
                    }
            });
            let p = pose.rotate(corner);
            result.include(std::array::from_fn(|i| p[i] + pose.pos[i]))?;
        }
        result.finished()
    }
}

fn vector(value: &Value) -> Option<[f64; 3]> {
    let values = value.as_array()?;
    let [x, y, z] = values.as_slice() else {
        return None;
    };
    Some([x.as_f64()?, y.as_f64()?, z.as_f64()?])
}

fn primitive(data: &Value) -> Option<Bounds> {
    let params = &data["params"];
    let number = |key, default| {
        params[key]
            .as_f64()
            .filter(|v| *v != 0.0)
            .unwrap_or(default)
    };
    let radius = number("radius", 0.5);
    let height = number("height", 1.0) * 0.5;
    let bounds = match data["type"].as_str()? {
        "box" => Bounds::centered(vector(&params["size"]).unwrap_or([1.0; 3]).map(|v| v * 0.5)),
        "sphere" => Bounds::centered([radius; 3]),
        "cylinder" => Bounds::centered([radius, radius, height]),
        "cone" => Bounds::centered([radius, height, radius]),
        "plane" => Bounds::centered([number("width", 1.0) * 0.5, height, 0.0]),
        "axes" => {
            let radius = number("radius", 0.02).abs() * 2.0;
            let length = number("length", 1.0);
            Bounds {
                min: [length.min(0.0) - radius; 3],
                max: [length.max(0.0) + radius; 3],
            }
        }
        "arrow" => {
            let radius = number("radius", 0.05).abs() * 1.5;
            let (start, end) = vector(&params["start"])
                .zip(vector(&params["end"]))
                .unwrap_or(([0.0; 3], [0.0, 0.0, number("length", 1.0)]));
            Bounds {
                min: std::array::from_fn(|i| start[i].min(end[i]) - radius),
                max: std::array::from_fn(|i| start[i].max(end[i]) + radius),
            }
        }
        _ => return None,
    };
    Some(bounds)
}

impl Host {
    fn geometry_vectors<const N: usize>(
        &self,
        reference: &Value,
    ) -> Option<impl Iterator<Item = [f64; N]> + '_> {
        let buffer = self.buffers.get(reference["buffer_id"].as_str()?)?;
        if buffer.dtype != "f32" || buffer.data.len() % (N * 4) != 0 {
            return None;
        }
        Some(buffer.data.chunks_exact(N * 4).map(|row| {
            std::array::from_fn(|i| {
                f32::from_le_bytes(row[i * 4..i * 4 + 4].try_into().unwrap()) as f64
            })
        }))
    }

    pub(super) fn geometry_bounds(&self, obj: &SceneObject, world: &Pose) -> Option<Bounds> {
        let data = obj.data.as_ref()?;
        let mut local = Bounds::empty();
        match obj.object_type.as_str() {
            "primitive" => local = primitive(data)?,
            "instances" => {
                let shape = primitive(data)?;
                let mut rotations = self.geometry_vectors::<4>(&data["quats"]);
                let mut scales = self.geometry_vectors::<3>(&data["scales"]);
                for pos in self.geometry_vectors::<3>(&data["positions"])? {
                    let quat = match rotations.as_mut() {
                        Some(values) => Pose::normalized(values.next()?).ok()?,
                        None => [0.0, 0.0, 0.0, 1.0],
                    };
                    let scale = match scales.as_mut() {
                        Some(values) => values.next()?,
                        None => [1.0; 3],
                    };
                    let instance = shape.transform(&Pose { pos, quat }, scale)?;
                    local.include(instance.min)?;
                    local.include(instance.max)?;
                }
            }
            "mesh" | "lines" | "points" => {
                if let Some(chunks) = data["chunks"].as_array() {
                    for chunk in chunks {
                        for point in self.geometry_vectors::<3>(&chunk["positions"])? {
                            local.include(point)?;
                        }
                    }
                } else {
                    let ref_key = if obj.object_type == "mesh" {
                        "vertices"
                    } else {
                        "positions"
                    };
                    for point in self.geometry_vectors::<3>(&data[ref_key])? {
                        local.include(point)?;
                    }
                }
            }
            _ => return None,
        }
        local
            .finished()?
            .transform(world, obj.geometry_scale.unwrap_or([1.0; 3]))
    }
}

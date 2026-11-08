use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::mpsc::UnboundedSender;

pub const MAX_BUFFER_BYTES: usize = 256 * 1024 * 1024;
const MAX_TOTAL_BUFFER_BYTES: usize = 512 * 1024 * 1024;

const LOG_BUFFER_LIMIT: usize = 1000;
const SNAPSHOT_BASE64_LIMIT: usize = 256 * 1024;

// P1-1: Warning threshold for large point clouds (soft limit, logs warning only)
const POINT_COUNT_WARNING_THRESHOLD: usize = 5_000_000;

#[derive(Debug)]
pub struct HostError {
    pub code: String,
    pub message: String,
}

impl HostError {
    pub(crate) fn new(code: &str, message: impl Into<String>) -> Self {
        Self {
            code: code.to_string(),
            message: message.into(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Pose {
    pub pos: [f64; 3],
    pub quat: [f64; 4],
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scale: Option<[f64; 3]>,
}

impl Pose {
    fn identity() -> Self {
        Self {
            pos: [0.0, 0.0, 0.0],
            quat: [0.0, 0.0, 0.0, 1.0],
            scale: None,
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct SceneObject {
    pub handle: String,
    pub object_type: String,
    pub scene_id: String,
    pub pose: Pose,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub color: Option<Vec<f64>>,
    pub visible: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ViewOverlay {
    pub handle: String,
    pub object_type: String,
    pub view_id: String,
    pub data: Value,
}

#[derive(Clone, Debug)]
pub struct ViewInfo {
    pub scene_id: Option<String>,
    pub title: String,
    pub width: u32,
    pub height: u32,
    pub view_config: serde_json::Map<String, Value>,
    pub camera_controls: serde_json::Map<String, Value>,
    pub camera_pose: Option<Value>,
    #[allow(dead_code)]
    pub decorations: bool,
}

#[derive(Clone, Debug)]
pub struct BufferEntry {
    pub data: Vec<u8>,
    received: Vec<(usize, usize)>,
    pub size_bytes: usize,
    pub dtype: String,
    pub shape: Option<Vec<usize>>,
}

#[derive(Clone, Debug, Serialize)]
pub struct BufferSnapshot {
    pub dtype: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub shape: Option<Vec<usize>>,
    pub size_bytes: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data_base64: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct SceneSnapshot {
    pub scene_id: String,
    pub objects: Vec<SceneObject>,
    pub buffers: HashMap<String, BufferSnapshot>,
}

#[derive(Clone, Debug, Serialize)]
pub struct LogEntry {
    pub seq: u64,
    pub ts_ms: u64,
    pub level: String,
    pub logger: String,
    pub msg: String,
    pub fields: HashMap<String, Value>,
}

#[derive(Clone, Debug)]
struct LogConfig {
    min_level: String,
    event_sink: bool,
}

#[derive(Clone, Debug)]
struct GizmoState {
    #[allow(dead_code)]
    handle: String,
    #[allow(dead_code)]
    mode: Option<String>,
}

pub struct Host {
    scene_counter: u64,
    view_counter: u64,
    buffer_counter: u64,
    handle_counter: u64,
    buffers: HashMap<String, BufferEntry>,
    objects: HashMap<String, SceneObject>,
    overlays: HashMap<String, ViewOverlay>,
    views: HashMap<String, ViewInfo>,
    scenes: HashMap<String, u64>,
    logs: Vec<LogEntry>,
    log_seq: u64,
    log_config: LogConfig,
    log_sender: Option<UnboundedSender<LogEntry>>,
    gizmos: HashMap<String, GizmoState>,
}

impl Host {
    fn default_view_config() -> serde_json::Map<String, Value> {
        let mut config = serde_json::Map::new();
        config.insert("show_grid".to_string(), Value::Bool(false));
        config.insert("show_ground".to_string(), Value::Bool(false));
        config.insert("show_axes".to_string(), Value::Bool(true));
        config.insert(
            "grid_color".to_string(),
            json!([0.27, 0.27, 0.27]),
        );
        config.insert(
            "grid_sub_color".to_string(),
            json!([0.2, 0.2, 0.2]),
        );
        config.insert("axes_length".to_string(), json!(0.2));
        config.insert("axes_radius".to_string(), json!(0.002));
        config.insert("background".to_string(), json!([1.0, 1.0, 1.0]));
        config
    }

    fn default_camera_controls() -> serde_json::Map<String, Value> {
        let mut config = serde_json::Map::new();
        let is_macos = std::env::consts::OS == "macos";
        let preset = if is_macos { "trackpad" } else { "cad" };
        let mouse_buttons = if preset == "trackpad" {
            json!({ "left": "rotate", "middle": "zoom", "right": "pan" })
        } else {
            json!({ "left": "rotate", "middle": "pan", "right": "none" })
        };
        config.insert("rotate_sensitivity".to_string(), json!(0.5));
        config.insert("pan_sensitivity".to_string(), json!(1.0));
        config.insert("zoom_sensitivity".to_string(), json!(1.0));
        config.insert("zoom_to_cursor".to_string(), Value::Bool(false));
        config.insert("orbit_enabled".to_string(), Value::Bool(true));
        config.insert("pan_enabled".to_string(), Value::Bool(true));
        config.insert("zoom_enabled".to_string(), Value::Bool(true));
        config.insert("damping".to_string(), Value::Bool(false));
        config.insert("mouse_preset".to_string(), Value::String(preset.to_string()));
        config.insert("mouse_buttons".to_string(), mouse_buttons);
        config.insert("fov".to_string(), json!(30.0));
        config
    }
    pub fn new(log_sender: Option<UnboundedSender<LogEntry>>) -> Self {
        Self {
            scene_counter: 0,
            view_counter: 0,
            buffer_counter: 0,
            handle_counter: 0,
            buffers: HashMap::new(),
            objects: HashMap::new(),
            overlays: HashMap::new(),
            views: HashMap::new(),
            scenes: HashMap::new(),
            logs: Vec::with_capacity(LOG_BUFFER_LIMIT),  // P3-3: Pre-allocate log buffer
            log_seq: 0,
            log_config: LogConfig {
                min_level: "info".to_string(),
                event_sink: false,
            },
            log_sender,
            gizmos: HashMap::new(),
        }
    }

    pub fn store_buffer_data(
        &mut self,
        buffer_id: &str,
        offset_bytes: usize,
        data: &[u8],
    ) -> Result<(), HostError> {
        if self.build_buffer_ref_counts().get(buffer_id).copied().unwrap_or(0) > 0 {
            return Err(HostError::new("ERR_BUFFER_IN_USE", "Referenced buffers are immutable; upload a replacement"));
        }
        let entry = self
            .buffers
            .get_mut(buffer_id)
            .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Buffer not found: {}", buffer_id)))?;
        if offset_bytes.checked_add(data.len()).map_or(true, |end| end > entry.size_bytes) {
            return Err(HostError::new(
                "ERR_BUFFER_RANGE",
                format!(
                    "Buffer range exceeded: {} + {} > {}",
                    offset_bytes,
                    data.len(),
                    entry.size_bytes
                ),
            ));
        }
        let mut ranges = entry.received.clone();
        if !data.is_empty() { ranges.push((offset_bytes, offset_bytes + data.len())); }
        ranges.sort_unstable();
        let mut merged: Vec<(usize, usize)> = Vec::new();
        for (start, end) in ranges {
            if let Some(last) = merged.last_mut() {
                if start <= last.1 { last.1 = last.1.max(end); continue; }
            }
            merged.push((start, end));
        }
        if merged.len() > 4096 { return Err(HostError::new("ERR_RESOURCE_LIMIT", "Too many disjoint upload ranges")); }
        entry.received = merged;
        entry.data[offset_bytes..offset_bytes + data.len()].copy_from_slice(data);
        Ok(())
    }

    pub fn get_buffer_data(&self, buffer_id: &str) -> Option<Vec<u8>> {
        self.buffers.get(buffer_id).map(|entry| entry.data.clone())
    }

    pub fn build_scene_snapshot(&self, scene_id: &str) -> Result<SceneSnapshot, HostError> {
        let mut objects: Vec<SceneObject> = Vec::new();
        let mut buffer_ids: Vec<String> = Vec::new();

        for obj in self.objects.values() {
            if obj.scene_id == scene_id {
                objects.push(obj.clone());
                if let Some(data) = &obj.data {
                    buffer_ids.extend(self.collect_buffer_ids(data));
                }
            }
        }

        let mut buffers = HashMap::new();
        for buffer_id in buffer_ids.into_iter() {
            if let Some(entry) = self.buffers.get(&buffer_id) {
                let data_base64 = if entry.data.len() <= SNAPSHOT_BASE64_LIMIT {
                    Some(BASE64.encode(&entry.data))
                } else {
                    None
                };
                buffers.insert(
                    buffer_id,
                    BufferSnapshot {
                        dtype: entry.dtype.clone(),
                        shape: entry.shape.clone(),
                        size_bytes: entry.size_bytes,
                        data_base64,
                    },
                );
            }
        }

        Ok(SceneSnapshot {
            scene_id: scene_id.to_string(),
            objects,
            buffers,
        })
    }

    pub fn command_buffers(&self, args: &Value) -> Vec<(String, BufferSnapshot, Vec<u8>)> {
        let mut ids = self.collect_buffer_ids(args);
        ids.sort(); ids.dedup();
        ids.into_iter().filter_map(|id| self.buffers.get(&id).map(|entry| (id, BufferSnapshot {
            dtype: entry.dtype.clone(), shape: entry.shape.clone(), size_bytes: entry.size_bytes, data_base64: None
        }, entry.data.clone()))).collect()
    }

    pub fn resource_counts(&self) -> Value {
        json!({"objects":self.objects.len(),"buffers":self.buffers.len(),"buffer_bytes":self.buffers.values().map(|b| b.size_bytes).sum::<usize>(),"views":self.views.len(),"scenes":self.scenes.len()})
    }

    pub fn view_snapshot(&self, view_id: &str) -> Value {
        let view = self.views.get(view_id);
        json!({
            "view_config": view.map(|v| &v.view_config),
            "camera_controls": view.map(|v| &v.camera_controls),
            "camera_pose": view.and_then(|v| v.camera_pose.as_ref()),
            "overlays": self.overlays.values().filter(|o| o.view_id == view_id).collect::<Vec<_>>()
        })
    }

    pub fn handle_command(&mut self, name: &str, args: &mut Value) -> Result<Value, HostError> {
        if !args.is_object() { return Err(HostError::new("ERR_INVALID_ARGS", "args must be an object")); }
        for key in ["scene_id", "view_id"] {
            if let Some(value) = args.get(key) {
                if value.as_str().map_or(true, str::is_empty) { return Err(HostError::new("ERR_INVALID_ARGS", format!("{} must be a nonempty string", key))); }
            }
        }
        let counters = (self.scene_counter, self.view_counter, self.buffer_counter, self.handle_counter);
        let result = self.execute_command(name, args);
        if result.is_ok() {
            // Legacy add_* may create a scene, but only after the complete command succeeds.
            if let Some(scene) = args.get("scene_id").and_then(Value::as_str) {
                if matches!(name, "attach_scene" | "add_primitive" | "add_points" | "add_lines" | "add_mesh" | "add_instances" | "load_mesh" | "add_text_3d") { self.ensure_scene(scene); }
            }
        } else {
            (self.scene_counter, self.view_counter, self.buffer_counter, self.handle_counter) = counters;
        }
        result
    }

    fn execute_command(&mut self, name: &str, args: &mut Value) -> Result<Value, HostError> {
        if matches!(name, "add_points" | "add_lines" | "add_mesh" | "add_instances" | "update_instances") {
            self.validate_buffer_refs(args)?;
        }
        // Validate scope before any mutation, including updates and clones.
        if let Some(handle) = args.get("handle").and_then(Value::as_str) {
            if let Some(obj) = self.objects.get(handle) {
                if let Some(scope) = args.get("scene_id").and_then(Value::as_str) {
                    if scope != obj.scene_id { return Err(HostError::new("ERR_INVALID_SCOPE", "Object belongs to another scene")); }
                }
            }
            if let Some(obj) = self.overlays.get(handle) {
                if let Some(scope) = args.get("view_id").and_then(Value::as_str) {
                    if scope != obj.view_id { return Err(HostError::new("ERR_INVALID_SCOPE", "Overlay belongs to another view")); }
                }
            }
        }
        if matches!(name, "set_object_colors" | "set_object_alphas" | "set_object_visibilities" | "set_object_transforms") {
            let items = args.get("items").and_then(Value::as_array)
                .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "items must be an array"))?;
            for item in items {
                let handle = self.require_string(item, "handle")?;
                if item.get("view_id").map_or(false, |v| v.as_str().map_or(true, str::is_empty)) {
                    return Err(HostError::new("ERR_INVALID_ARGS", "view_id must be a nonempty string"));
                }
                let obj = self.objects.get(&handle).ok_or_else(|| HostError::new("ERR_NOT_FOUND", "Object not found"))?;
                for scope in [args.get("scene_id"), item.get("scene_id")].into_iter().flatten() {
                    if scope.as_str() != Some(obj.scene_id.as_str()) { return Err(HostError::new("ERR_INVALID_SCOPE", "Object belongs to another scene")); }
                }
                if item.get("target").map_or(false, |t| t.as_str() != Some("scene")) {
                    return Err(HostError::new("ERR_INVALID_ARGS", "Object batches only accept scene targets"));
                }
                match name {
                    "set_object_colors" => {
                        let color = self.get_optional_color(item, "rgba")?;
                        if color.is_none() { return Err(HostError::new("ERR_INVALID_ARGS", "rgba is required")); }
                        self.assert_color_range(color.as_ref(), "rgba")?;
                    }
                    "set_object_alphas" => {
                        let alpha = item.get("alpha").and_then(Value::as_f64).ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "alpha must be a number"))?;
                        if !(0.0..=1.0).contains(&alpha) { return Err(HostError::new("ERR_INVALID_ARGS", "alpha must be in [0, 1]")); }
                    }
                    "set_object_visibilities" => { self.require_bool(item, "visible")?; }
                    "set_object_transforms" => {
                        let pose = item.get("pose").ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "pose is required"))?;
                        self.parse_pose(Some(pose))?;
                    }
                    _ => unreachable!(),
                }
            }
        }
        self.add_log("debug", "host", format!("Received command: {}", name), HashMap::new());
        match name {
            // Scene & View
            "create_scene" => {
                let scene_id = self
                    .get_optional_string(args, "scene_id")
                    .unwrap_or_else(|| self.next_scene_id());
                self.ensure_scene(&scene_id);
                Ok(json!({ "scene_id": scene_id }))
            }
            "create_view" => {
                let scene_id = self
                    .get_optional_string(args, "scene_id")
                    .unwrap_or_else(|| self.next_scene_id());
                self.ensure_scene(&scene_id);
                let view_id = self
                    .get_optional_string(args, "view_id")
                    .unwrap_or_else(|| self.next_view_id());
                let title = self
                    .get_optional_string(args, "title")
                    .unwrap_or_else(|| "FrameViz".to_string());
                let width = self.get_optional_u64(args, "width").unwrap_or(800) as u32;
                let height = self.get_optional_u64(args, "height").unwrap_or(600) as u32;
                let decorations = args.get("window_decorations")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(true); // Default: true (decorations enabled)
                self.views.insert(
                    view_id.clone(),
                    ViewInfo {
                        scene_id: Some(scene_id.clone()),
                        title,
                        width,
                        height,
                        view_config: Host::default_view_config(),
                        camera_controls: Host::default_camera_controls(),
                        camera_pose: None,
                        decorations,
                    },
                );
                Ok(json!({ "view_id": view_id, "scene_id": scene_id }))
            }
            "clear_scene" => {
                let scene_id = self.require_scene_id(args, name)?;
                let mut counts = self.build_buffer_ref_counts();
                let handles: Vec<String> = self
                    .objects
                    .iter()
                    .filter(|(_, obj)| obj.scene_id == scene_id)
                    .map(|(handle, _)| handle.clone())
                    .collect();
                for handle in handles {
                    if let Some(obj) = self.objects.remove(&handle) {
                        self.release_buffers(self.collect_buffer_ids_from_object(&obj), &mut counts);
                    }
                }
                if let Some(view_id) = self.get_optional_string(args, "view_id") {
                    let overlay_handles: Vec<String> = self
                        .overlays
                        .iter()
                        .filter(|(_, overlay)| overlay.view_id == view_id)
                        .map(|(handle, _)| handle.clone())
                        .collect();
                    for handle in overlay_handles {
                        self.overlays.remove(&handle);
                    }
                }
                Ok(json!({}))
            }
            "set_object_colors" => {
                let items = args.get("items").and_then(|v| v.as_array()).ok_or_else(|| {
                    HostError::new("ERR_INVALID_ARGS", "items must be an array")
                })?;
                let scene_id = self.get_optional_string(args, "scene_id");
                for item in items {
                    let mut item_mut = item.clone();
                    if let (Some(sid), Some(obj)) = (&scene_id, item_mut.as_object_mut()) {
                        obj.entry("scene_id").or_insert_with(|| json!(sid));
                    }
                    self.handle_command("set_color", &mut item_mut)?;
                }
                Ok(json!({}))
            }
            "set_object_alphas" => {
                let items = args.get("items").and_then(|v| v.as_array()).ok_or_else(|| {
                    HostError::new("ERR_INVALID_ARGS", "items must be an array")
                })?;
                let scene_id = self.get_optional_string(args, "scene_id");
                for item in items {
                    let mut item_mut = item.clone();
                    if let (Some(sid), Some(obj)) = (&scene_id, item_mut.as_object_mut()) {
                        obj.entry("scene_id").or_insert_with(|| json!(sid));
                    }
                    self.handle_command("set_alpha", &mut item_mut)?;
                }
                Ok(json!({}))
            }
            "set_object_visibilities" => {
                let items = args.get("items").and_then(|v| v.as_array()).ok_or_else(|| {
                    HostError::new("ERR_INVALID_ARGS", "items must be an array")
                })?;
                let scene_id = self.get_optional_string(args, "scene_id");
                for item in items {
                    let mut item_mut = item.clone();
                    if let (Some(sid), Some(obj)) = (&scene_id, item_mut.as_object_mut()) {
                        obj.entry("scene_id").or_insert_with(|| json!(sid));
                    }
                    self.handle_command("set_visible", &mut item_mut)?;
                }
                Ok(json!({}))
            }
            "destroy_scene" => {
                let scene_id = self.require_scene_id(args, name)?;
                let mut counts = self.build_buffer_ref_counts();
                let handles: Vec<String> = self
                    .objects
                    .iter()
                    .filter(|(_, obj)| obj.scene_id == scene_id)
                    .map(|(handle, _)| handle.clone())
                    .collect();
                for handle in handles {
                    if let Some(obj) = self.objects.remove(&handle) {
                        self.release_buffers(self.collect_buffer_ids_from_object(&obj), &mut counts);
                    }
                }
                for view in self.views.values_mut() {
                    if view.scene_id.as_deref() == Some(scene_id.as_str()) {
                        view.scene_id = None;
                    }
                }
                self.scenes.remove(&scene_id);
                Ok(json!({}))
            }
            "destroy_view" => {
                let view_id = self.require_string(args, "view_id")?;
                let handles: Vec<String> = self
                    .overlays
                    .iter()
                    .filter(|(_, overlay)| overlay.view_id == view_id)
                    .map(|(handle, _)| handle.clone())
                    .collect();
                for handle in handles {
                    self.overlays.remove(&handle);
                }
                self.gizmos.remove(&view_id);
                self.views.remove(&view_id);
                Ok(json!({}))
            }
            "attach_scene" => {
                let view_id = self.require_string(args, "view_id")?;
                let scene_id = self.require_scene_id(args, name)?;
                let view = self.views.entry(view_id.clone()).or_insert(ViewInfo {
                    scene_id: Some(scene_id.clone()),
                    title: "FrameViz".to_string(),
                    width: 1280,
                    height: 720,
                    view_config: Host::default_view_config(),
                    camera_controls: Host::default_camera_controls(),
                    camera_pose: None,
                    decorations: true,  // Default: true
                });
                view.scene_id = Some(scene_id.clone());
                Ok(json!({ "view_id": view_id, "scene_id": scene_id }))
            }
            "list_scenes" => {
                let mut scene_counts: HashMap<String, usize> = HashMap::new();
                for scene_id in self.scenes.keys() {
                    scene_counts.insert(scene_id.clone(), 0);
                }
                for obj in self.objects.values() {
                    *scene_counts.entry(obj.scene_id.clone()).or_insert(0) += 1;
                }
                let mut scenes: Vec<Value> = scene_counts
                    .into_iter()
                    .map(|(scene_id, object_count)| json!({ "scene_id": scene_id, "object_count": object_count }))
                    .collect();
                scenes.sort_by(|a, b| {
                    a.get("scene_id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .cmp(b.get("scene_id").and_then(|v| v.as_str()).unwrap_or(""))
                });
                Ok(json!({ "scenes": scenes }))
            }
            "list_views" => {
                let mut views: Vec<Value> = self
                    .views
                    .iter()
                    .map(|(view_id, view)| {
                        json!({
                            "view_id": view_id,
                            "scene_id": view.scene_id,
                            "title": view.title,
                            "width": view.width,
                            "height": view.height
                        })
                    })
                    .collect();
                views.sort_by(|a, b| {
                    a.get("view_id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .cmp(b.get("view_id").and_then(|v| v.as_str()).unwrap_or(""))
                });
                Ok(json!({ "views": views }))
            }
            "get_view_config" => {
                let view_id = self.require_string(args, "view_id")?;
                if let Some(view) = self.views.get(&view_id) {
                    Ok(Value::Object(view.view_config.clone()))
                } else {
                    Err(HostError::new("ERR_NOT_FOUND", format!("View not found: {}", view_id)))
                }
            }
            "get_camera_controls" => {
                let view_id = self.require_string(args, "view_id")?;
                if let Some(view) = self.views.get(&view_id) {
                    Ok(Value::Object(view.camera_controls.clone()))
                } else {
                    Err(HostError::new("ERR_NOT_FOUND", format!("View not found: {}", view_id)))
                }
            }
            "get_scene_snapshot" => {
                let scene_id = self.require_scene_id(args, name)?;
                let snapshot = self.build_scene_snapshot(&scene_id)?;
                Ok(serde_json::to_value(snapshot).unwrap_or_else(|_| json!({})))
            }

            // Buffer management
            "create_buffer" => {
                let size_bytes = self.require_usize(args, "size_bytes")?;
                let dtype = self.require_string(args, "dtype")?;
                let dtype_size = self.get_dtype_size(&dtype)?;
                if size_bytes > MAX_BUFFER_BYTES || self.buffers.values().map(|b| b.size_bytes).sum::<usize>().checked_add(size_bytes).map_or(true, |n| n > MAX_TOTAL_BUFFER_BYTES) {
                    return Err(HostError::new("ERR_RESOURCE_LIMIT", "Buffer allocation limit exceeded"));
                }
                let shape = self.get_optional_usize_array(args, "shape");
                if args.get("shape").is_some() && shape.is_none() {
                    return Err(HostError::new("ERR_INVALID_ARGS", "Invalid buffer shape"));
                }
                if let Some(ref shape_val) = shape {
                    let expected = shape_val.iter().try_fold(dtype_size, |n, d| n.checked_mul(*d))
                        .ok_or_else(|| HostError::new("ERR_RESOURCE_LIMIT", "Buffer shape overflows"))?;
                    if expected != size_bytes {
                        return Err(HostError::new(
                            "ERR_BUFFER_SIZE_MISMATCH",
                            format!("Shape mismatch: expected {} bytes, got {}", expected, size_bytes),
                        ));
                    }
                }
                let mut data = Vec::new();
                data.try_reserve_exact(size_bytes).map_err(|_| HostError::new("ERR_RESOURCE_LIMIT", "Buffer allocation failed"))?;
                data.resize(size_bytes, 0);
                let buffer_id = format!("b_{}", self.next_buffer_id());
                self.buffers.insert(
                    buffer_id.clone(),
                    BufferEntry {
                        data,
                        received: Vec::new(),
                        size_bytes,
                        dtype,
                        shape,
                    },
                );
                Ok(json!({ "buffer_id": buffer_id }))
            }
            "free_buffer" => {
                let buffer_id = self.require_string(args, "buffer_id")?;
                if !self.buffers.contains_key(&buffer_id) {
                    return Err(HostError::new(
                        "ERR_NOT_FOUND",
                        format!("Buffer not found: {}", buffer_id),
                    ));
                }
                if self.build_buffer_ref_counts().get(&buffer_id).copied().unwrap_or(0) > 0 {
                    return Ok(json!({"retained": true}));
                }
                self.buffers.remove(&buffer_id);
                Ok(json!({"retained": false}))
            }

            // Primitives & geometry
            "add_primitive" => {
                let handle = format!("h_{}", self.next_handle_id());
                let scene_id = self.require_scene_id(args, name)?;
                let ptype = self.require_string(args, "type")?;
                let pose = self.parse_pose(args.get("pose"))?;
                let color = self.get_optional_color(args, "color")?;
                self.assert_color_range(color.as_ref(), "add_primitive.color")?;
                let params = args.get("params").cloned().unwrap_or_else(|| json!({}));

                self.objects.insert(
                    handle.clone(),
                    SceneObject {
                        handle: handle.clone(),
                        object_type: "primitive".to_string(),
                        scene_id,
                        pose,
                        color,
                        visible: true,
                        group_id: None,
                        data: Some(json!({ "type": ptype, "params": params })),
                    },
                );
                Ok(json!({ "handle": handle, "object_type": "primitive" }))
            }
            "add_points" => {
                let handle = format!("h_{}", self.next_handle_id());
                let scene_id = self.require_scene_id(args, name)?;
                let positions = self.require_value(args, "positions")?;
                let group_id = args
                    .get("group_id")
                    .and_then(|v| v.as_str())
                    .map(|v| v.to_string());
                
                // P1-1: Soft warning for large point clouds
                if let Some(buffer_ref) = positions.as_object() {
                    if let Some(shape) = buffer_ref.get("shape").and_then(|v| v.as_array()) {
                        if let Some(n_points) = shape.first().and_then(|v| v.as_u64()) {
                            if n_points as usize > POINT_COUNT_WARNING_THRESHOLD {
                                let estimated_mb = (n_points as usize * 12) / 1_000_000;
                                self.add_log(
                                    "warn",
                                    "host",
                                    format!(
                                        "Large point cloud: {} points (~{}MB). Consider using chunked upload for better performance.",
                                        n_points, estimated_mb
                                    ),
                                    HashMap::new(),
                                );
                            }
                        }
                    }
                }
                
                let colors = args.get("colors").cloned();
                let color = self.get_optional_color(args, "color")?;
                self.assert_color_range(color.as_ref(), "add_points.color")?;
                let size = self.get_optional_f64(args, "size").unwrap_or(3.0);
                self.objects.insert(
                    handle.clone(),
                    SceneObject {
                        handle: handle.clone(),
                        object_type: "points".to_string(),
                        scene_id,
                        pose: Pose::identity(),
                        color,
                        visible: true,
                        group_id,
                        data: Some(json!({ "positions": positions, "colors": colors, "size": size })),
                    },
                );
                Ok(json!({ "handle": handle, "object_type": "points" }))
            }
            "add_lines" => {
                let handle = format!("h_{}", self.next_handle_id());
                let scene_id = self.require_scene_id(args, name)?;
                let positions = self.require_value(args, "positions")?;
                let indices = args.get("indices").cloned();
                let width = self.get_optional_f64(args, "width").unwrap_or(1.0);
                let color = self.get_optional_color(args, "color")?;
                self.assert_color_range(color.as_ref(), "add_lines.color")?;
                self.objects.insert(
                    handle.clone(),
                    SceneObject {
                        handle: handle.clone(),
                        object_type: "lines".to_string(),
                        scene_id,
                        pose: Pose::identity(),
                        color,
                        visible: true,
                        group_id: None,
                        data: Some(json!({ "positions": positions, "indices": indices, "width": width })),
                    },
                );
                Ok(json!({ "handle": handle, "object_type": "lines" }))
            }
            "add_mesh" => {
                let handle = format!("h_{}", self.next_handle_id());
                let scene_id = self.require_scene_id(args, name)?;
                let vertices = self.require_value(args, "vertices")?;
                let faces = self.require_value(args, "faces")?;
                let normals = args.get("normals").cloned();
                let colors = args.get("colors").cloned();
                let faces_format = args.get("faces_format").cloned();
                let mut color = self.get_optional_color(args, "color")?;
                if let Some(alpha) = args.get("alpha").and_then(|v| v.as_f64()) {
                    let base = color.unwrap_or_else(|| vec![1.0, 1.0, 1.0, 1.0]);
                    let mut rgba = if base.len() >= 3 { base } else { vec![1.0, 1.0, 1.0, 1.0] };
                    if rgba.len() < 4 {
                        rgba.push(alpha);
                    } else {
                        rgba[3] = alpha;
                    }
                    color = Some(rgba);
                }
                self.objects.insert(
                    handle.clone(),
                    SceneObject {
                        handle: handle.clone(),
                        object_type: "mesh".to_string(),
                        scene_id,
                        pose: Pose::identity(),
                        color,
                        visible: true,
                        group_id: None,
                        data: Some(json!({
                            "vertices": vertices,
                            "faces": faces,
                            "faces_format": faces_format,
                            "wireframe": args.get("wireframe"),
                            "smooth_shading": args.get("smooth_shading"),
                            "normals": normals,
                            "colors": colors
                        })),
                    },
                );
                Ok(json!({ "handle": handle, "object_type": "mesh" }))
            }
            "add_instances" => {
                let handle = format!("h_{}", self.next_handle_id());
                let scene_id = self.require_scene_id(args, name)?;
                let inst_type = self.require_string(args, "type")?;
                let positions = self.require_value(args, "positions")?;
                let quats = args.get("quats").cloned();
                let scales = args.get("scales").cloned();
                let colors = args.get("colors").cloned();
                let params = args.get("params").cloned().unwrap_or_else(|| json!({}));
                let mut color = self.get_optional_color(args, "color")?;
                if let Some(alpha) = args.get("alpha").and_then(|v| v.as_f64()) {
                    let base = color.unwrap_or_else(|| vec![1.0, 1.0, 1.0, 1.0]);
                    let mut rgba = if base.len() >= 3 { base } else { vec![1.0, 1.0, 1.0, 1.0] };
                    if rgba.len() < 4 {
                        rgba.push(alpha);
                    } else {
                        rgba[3] = alpha;
                    }
                    color = Some(rgba);
                }
                self.assert_color_range(color.as_ref(), "add_instances.color")?;
                self.objects.insert(
                    handle.clone(),
                    SceneObject {
                        handle: handle.clone(),
                        object_type: "instances".to_string(),
                        scene_id,
                        pose: Pose::identity(),
                        color,
                        visible: true,
                        group_id: None,
                        data: Some(json!({
                            "type": inst_type,
                            "positions": positions,
                            "quats": quats,
                            "scales": scales,
                            "colors": colors,
                            "params": params,
                        })),
                    },
                );
                Ok(json!({ "handle": handle, "object_type": "instances" }))
            }
            "update_instances" => {
                let handle = self.require_string(args, "handle")?;
                
                // Get color first (before mutable borrow of objects)
                let mut color = self.get_optional_color(args, "color")?;
                if let Some(alpha) = args.get("alpha").and_then(|v| v.as_f64()) {
                    // Get existing color from object first
                    let existing_color = self.objects.get(&handle).and_then(|o| o.color.clone());
                    let base = color.or(existing_color).unwrap_or_else(|| vec![1.0, 1.0, 1.0, 1.0]);
                    let mut rgba = if base.len() >= 3 { base } else { vec![1.0, 1.0, 1.0, 1.0] };
                    if rgba.len() < 4 {
                        rgba.push(alpha);
                    } else {
                        rgba[3] = alpha;
                    }
                    color = Some(rgba);
                }
                if let Some(ref c) = color {
                    self.assert_color_range(Some(c), "update_instances.color")?;
                }

                let old_buffers = self.objects.get(&handle).map(|obj| self.collect_buffer_ids_from_object(obj)).unwrap_or_default();
                // Now get mutable borrow of object
                let obj = self
                    .objects
                    .get_mut(&handle)
                    .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Object not found: {}", handle)))?;
                
                if obj.object_type != "instances" {
                    return Err(HostError::new(
                        "ERR_INVALID_TYPE",
                        format!("Object {} is not an instances object", handle),
                    ));
                }

                // Update data fields if provided
                if let Some(data) = obj.data.as_mut() {
                    if let Some(map) = data.as_object_mut() {
                        if let Some(positions) = args.get("positions") {
                            map.insert("positions".to_string(), positions.clone());
                        }
                        if let Some(quats) = args.get("quats") {
                            map.insert("quats".to_string(), quats.clone());
                        }
                        if let Some(scales) = args.get("scales") {
                            map.insert("scales".to_string(), scales.clone());
                        }
                        if let Some(colors) = args.get("colors") {
                            map.insert("colors".to_string(), colors.clone());
                        }
                    }
                }

                // Apply color if provided
                if let Some(c) = color {
                    obj.color = Some(c);
                }

                let refs = self.build_buffer_ref_counts();
                for id in old_buffers { if !refs.contains_key(&id) { self.buffers.remove(&id); } }
                Ok(json!({}))
            }
            "load_mesh" => {
                let handle = format!("h_{}", self.next_handle_id());
                let scene_id = self.require_scene_id(args, name)?;
                let url = self.require_string(args, "url")?;
                let pose = self.parse_pose(args.get("pose"))?;
                let scale = if let Some(value) = args.get("scale") {
                    json!(self.require_vec3(value, "scale")?)
                } else {
                    json!([1.0, 1.0, 1.0])
                };
                let color = self.get_optional_color(args, "color")?;
                self.assert_color_range(color.as_ref(), "load_mesh.color")?;
                self.objects.insert(
                    handle.clone(),
                    SceneObject {
                        handle: handle.clone(),
                        object_type: "loaded_mesh".to_string(),
                        scene_id,
                        pose,
                        color,
                        visible: true,
                        group_id: None,
                        data: Some(json!({ "url": url, "scale": scale })),
                    },
                );
                Ok(json!({ "handle": handle, "object_type": "loaded_mesh" }))
            }
            "add_text_3d" => {
                let handle = format!("h_{}", self.next_handle_id());
                let scene_id = self.require_scene_id(args, name)?;
                let pose = self.parse_pose_from_pos(args.get("pos"))?;
                let data = json!({
                    "text": args.get("text").cloned().unwrap_or_else(|| Value::String(String::new())),
                    "font_size": args.get("font_size").cloned(),
                    "color": args.get("color").cloned(),
                    "background_color": args.get("background_color").cloned(),
                });
                self.objects.insert(
                    handle.clone(),
                    SceneObject {
                        handle: handle.clone(),
                        object_type: "text3d".to_string(),
                        scene_id,
                        pose,
                        color: None,
                        visible: true,
                        group_id: None,
                        data: Some(data),
                    },
                );
                Ok(json!({ "handle": handle, "object_type": "text3d" }))
            }
            "update_text_3d" => {
                let handle = self.require_string(args, "handle")?;
                let new_pose = if let Some(pos) = args.get("pos") {
                    Some(self.parse_pose_from_pos(Some(pos))?)
                } else {
                    None
                };
                let new_text = args.get("text").cloned();
                let new_font_size = args.get("font_size").cloned();
                let new_color = args.get("color").cloned();

                let obj = self
                    .objects
                    .get_mut(&handle)
                    .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Object not found: {}", handle)))?;

                if let Some(text) = new_text {
                    if let Some(data) = obj.data.as_mut() {
                        if let Some(map) = data.as_object_mut() {
                            map.insert("text".to_string(), text);
                        }
                    }
                }
                if let Some(pose) = new_pose {
                    obj.pose = pose;
                }
                if let Some(font_size) = new_font_size {
                    if let Some(data) = obj.data.as_mut() {
                        if let Some(map) = data.as_object_mut() {
                            map.insert("font_size".to_string(), font_size);
                        }
                    }
                }
                if let Some(color) = new_color {
                    if let Some(data) = obj.data.as_mut() {
                        if let Some(map) = data.as_object_mut() {
                            map.insert("color".to_string(), color);
                        }
                    }
                }
                Ok(json!({}))
            }
            "remove_text_3d" => {
                let handle = self.require_string(args, "handle")?;
                self.objects.remove(&handle);
                Ok(json!({}))
            }
            "add_text_2d" => {
                let handle = format!("h_{}", self.next_handle_id());
                let view_id = self.require_string(args, "view_id")?;
                self.assert_color_range(self.get_optional_color(args, "color")?.as_ref(), "add_text_2d.color")?;
                let data = json!({
                    "text": args.get("text").cloned().unwrap_or_else(|| Value::String(String::new())),
                    "x": args.get("x").cloned(),
                    "y": args.get("y").cloned(),
                    "font_size": args.get("font_size").cloned(),
                    "color": args.get("color").cloned(),
                });
                self.overlays.insert(
                    handle.clone(),
                    ViewOverlay {
                        handle: handle.clone(),
                        object_type: "text2d".to_string(),
                        view_id,
                        data,
                    },
                );
                Ok(json!({ "handle": handle, "object_type": "text2d" }))
            }
            "update_text_2d" => {
                let handle = self.require_string(args, "handle")?;
                let new_color = self.get_optional_color(args, "color")?;
                self.assert_color_range(new_color.as_ref(), "update_text_2d.color")?;
                let new_text = args.get("text").cloned();
                let new_x = args.get("x").cloned();
                let new_y = args.get("y").cloned();
                let new_font_size = args.get("font_size").cloned();

                let overlay = self
                    .overlays
                    .get_mut(&handle)
                    .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Overlay not found: {}", handle)))?;

                if let Some(color) = new_color {
                    overlay.data["color"] = json!(color);
                }
                if let Some(text) = new_text {
                    overlay.data["text"] = text;
                }
                if let Some(x) = new_x {
                    overlay.data["x"] = x;
                }
                if let Some(y) = new_y {
                    overlay.data["y"] = y;
                }
                if let Some(font_size) = new_font_size {
                    overlay.data["font_size"] = font_size;
                }
                Ok(json!({}))
            }
            "remove_text_2d" => {
                let handle = self.require_string(args, "handle")?;
                self.overlays.remove(&handle);
                Ok(json!({}))
            }
            "remove_object" => {
                let scene_id = self.get_optional_string(args, "scene_id");
                let view_id = self.get_optional_string(args, "view_id");
                if scene_id.is_some() && view_id.is_some() {
                    return Err(HostError::new(
                        "ERR_INVALID_SCOPE",
                        "Cannot specify both scene_id and view_id",
                    ));
                }
                if scene_id.is_none() && view_id.is_none() {
                    return Err(HostError::new(
                        "ERR_INVALID_SCOPE",
                        "Must specify either scene_id or view_id",
                    ));
                }
                let handle = self.require_string(args, "handle")?;
                if let Some(scene_id) = scene_id {
                    if !self.objects.contains_key(&handle) {
                        return Err(HostError::new(
                            "ERR_NOT_FOUND",
                            format!("Object not found: {}", handle),
                        ));
                    }
                    let mut counts = self.build_buffer_ref_counts();
                    if let Some(obj) = self.objects.remove(&handle) {
                        if obj.scene_id == scene_id {
                            self.release_buffers(self.collect_buffer_ids_from_object(&obj), &mut counts);
                        }
                    }
                } else if let Some(_view_id) = view_id {
                    if !self.overlays.contains_key(&handle) {
                        return Err(HostError::new(
                            "ERR_NOT_FOUND",
                            format!("Overlay not found: {}", handle),
                        ));
                    }
                    self.overlays.remove(&handle);
                }
                Ok(json!({}))
            }
            "remove_objects" => {
                let scene_id = self.require_scene_id(args, name)?;
                let handles = args.get("handles").and_then(Value::as_array)
                    .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "handles must be an array"))?;
                // Validate the whole batch before deleting anything.
                for value in handles {
                    let handle = value.as_str().ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "Invalid handle"))?;
                    let obj = self.objects.get(handle).ok_or_else(|| HostError::new("ERR_NOT_FOUND", "Object not found"))?;
                    if obj.scene_id != scene_id { return Err(HostError::new("ERR_INVALID_SCOPE", "Object belongs to another scene")); }
                }
                let mut counts = self.build_buffer_ref_counts();
                for value in handles {
                    if let Some(obj) = self.objects.remove(value.as_str().unwrap()) {
                        self.release_buffers(self.collect_buffer_ids_from_object(&obj), &mut counts);
                    }
                }
                Ok(json!({}))
            }
            "clone_object" => {
                let handle = self.require_string(args, "handle")?;
                let group_id = args
                    .get("group_id")
                    .and_then(|v| v.as_str())
                    .map(|v| v.to_string());
                let source = self
                    .objects
                    .get(&handle)
                    .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Object not found: {}", handle)))?
                    .clone();
                let new_handle = format!("h_{}", self.next_handle_id());
                let mut cloned = source.clone();
                cloned.handle = new_handle.clone();
                if let Some(group_id) = group_id {
                    cloned.group_id = Some(group_id);
                }
                let snapshot = serde_json::to_value(&cloned).unwrap();
                self.objects.insert(new_handle.clone(), cloned);
                Ok(json!({ "handle": new_handle, "object": snapshot }))
            }
            "is_object_alive" => {
                let handle = self.require_string(args, "handle")?;
                let alive = self.objects.contains_key(&handle) || self.overlays.contains_key(&handle);
                Ok(json!({ "alive": alive }))
            }

            // Transform & display
            "set_transform" => {
                let handle = self.require_string(args, "handle")?;
                let pose_value = args.get("pose").ok_or_else(|| {
                    HostError::new("ERR_INVALID_ARGS", "pose is required for set_transform")
                })?;
                let pose = self.parse_pose(Some(pose_value))?;
                let obj = self
                    .objects
                    .get_mut(&handle)
                    .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Object not found: {}", handle)))?;
                obj.pose = pose;
                Ok(json!({}))
            }
            "set_object_transforms" => {
                let items = args.get("items").and_then(|v| v.as_array()).ok_or_else(|| {
                    HostError::new("ERR_INVALID_ARGS", "items must be an array")
                })?;
                let scene_id = self.get_optional_string(args, "scene_id");
                for item in items {
                    if let Some(obj) = item.as_object() {
                        let handle = obj.get("handle").and_then(|v| v.as_str());
                        let pose_val = obj.get("pose");
                        if let (Some(handle), Some(pose_val)) = (handle, pose_val) {
                            let pose = self.parse_pose(Some(pose_val))?;
                            if let Some(target) = self.objects.get_mut(handle) {
                                if let Some(sid) = &scene_id {
                                    if &target.scene_id != sid {
                                        continue;
                                    }
                                }
                                target.pose = pose;
                            }
                        }
                    }
                }
                Ok(json!({}))
            }
            "set_color" => {
                let handle = self.require_string(args, "handle")?;
                let color = self.get_optional_color(args, "rgba")?;
                self.assert_color_range(color.as_ref(), "set_color.rgba")?;
                let explicit_target = self.get_optional_string(args, "target");
                let has_overlay = self.overlays.contains_key(&handle);
                let has_object = self.objects.contains_key(&handle);
                let target = explicit_target.unwrap_or_else(|| {
                    if has_overlay && !has_object {
                        "overlay".to_string()
                    } else {
                        "scene".to_string()
                    }
                });

                let old_refs = self.objects.get(&handle).and_then(|o| o.data.as_ref()).and_then(|data| data.get("colors"))
                    .map(|colors| self.collect_buffer_ids(colors)).unwrap_or_default();
                let mut counts = if old_refs.is_empty() { HashMap::new() } else { self.build_buffer_ref_counts() };
                if target == "overlay" {
                    if let Some(overlay) = self.overlays.get_mut(&handle) {
                        if let Some(color) = &color {
                            overlay.data["color"] = json!(color);
                        }
                    }
                    if let Some(map) = args.as_object_mut() {
                        map.insert("target".to_string(), Value::String("overlay".to_string()));
                    }
                } else if let Some(obj) = self.objects.get_mut(&handle) {
                    obj.color = color;
                    // Clear vertex colors flag when converting to uniform color
                    if let Some(data) = &mut obj.data {
                        if let Some(data_obj) = data.as_object_mut() {
                            data_obj.remove("colors");
                        }
                    }
                }
                let new_refs = self.objects.get(&handle).map(|o| self.collect_buffer_ids_from_object(o)).unwrap_or_default();
                self.release_buffers(old_refs.into_iter().filter(|id| !new_refs.contains(id)).collect(), &mut counts);
                Ok(json!({}))
            }
            "set_alpha" => {
                let handle = self.require_string(args, "handle")?;
                let alpha = args.get("alpha")
                    .and_then(|v| v.as_f64())
                    .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "alpha must be a number".to_string()))?;
                if !(0.0..=1.0).contains(&alpha) {
                    return Err(HostError::new("ERR_INVALID_ARGS", "alpha must be in [0.0, 1.0]".to_string()));
                }

                // Get existing color and update alpha
                if let Some(obj) = self.objects.get_mut(&handle) {
                    let base = obj.color.clone().unwrap_or_else(|| vec![1.0, 1.0, 1.0, 1.0]);
                    let mut rgba = if base.len() >= 3 { base } else { vec![1.0, 1.0, 1.0, 1.0] };
                    if rgba.len() < 4 {
                        rgba.push(alpha);
                    } else {
                        rgba[3] = alpha;
                    }
                    obj.color = Some(rgba);
                }
                Ok(json!({}))
            }
            "set_visible" => {
                let handle = self.require_string(args, "handle")?;
                let visible = self.require_bool(args, "visible")?;
                let explicit_target = self.get_optional_string(args, "target");
                let has_overlay = self.overlays.contains_key(&handle);
                let has_object = self.objects.contains_key(&handle);
                let target = explicit_target.unwrap_or_else(|| {
                    if has_overlay && !has_object {
                        "overlay".to_string()
                    } else {
                        "scene".to_string()
                    }
                });

                if target == "overlay" {
                    if let Some(overlay) = self.overlays.get_mut(&handle) {
                        overlay.data["visible"] = json!(visible);
                    }
                    if let Some(map) = args.as_object_mut() {
                        map.insert("target".to_string(), Value::String("overlay".to_string()));
                    }
                } else if let Some(obj) = self.objects.get_mut(&handle) {
                    obj.visible = visible;
                }
                Ok(json!({}))
            }

            // Getters
            "get_transform" => {
                let handle = self.require_string(args, "handle")?;
                let obj = self
                    .objects
                    .get(&handle)
                    .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Object not found: {}", handle)))?;
                Ok(json!({ "pose": obj.pose }))
            }
            "get_color" => {
                let handle = self.require_string(args, "handle")?;
                let obj = self
                    .objects
                    .get(&handle)
                    .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Object not found: {}", handle)))?;
                // Check if mesh has vertex colors (colors in data)
                if let Some(data) = &obj.data {
                    if matches!(data.get("colors"), Some(Value::Object(_))) {
                        return Ok(json!({ "has_vertex_colors": true }));
                    }
                }
                let mut rgba = obj.color.clone().unwrap_or_else(|| vec![1.0, 1.0, 1.0, 1.0]);
                if rgba.len() == 3 {
                    rgba.push(1.0);
                }
                Ok(json!({ "rgba": rgba }))
            }
            "get_alpha" => {
                let handle = self.require_string(args, "handle")?;
                let obj = self
                    .objects
                    .get(&handle)
                    .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Object not found: {}", handle)))?;
                let alpha = obj.color.as_ref()
                    .and_then(|c| if c.len() >= 4 { Some(c[3]) } else { None })
                    .unwrap_or(1.0);
                Ok(json!({ "alpha": alpha }))
            }
            "get_visible" => {
                let handle = self.require_string(args, "handle")?;
                let obj = self
                    .objects
                    .get(&handle)
                    .ok_or_else(|| HostError::new("ERR_NOT_FOUND", format!("Object not found: {}", handle)))?;
                Ok(json!({ "visible": obj.visible }))
            }
            "list_objects" => {
                let scene_id = self.require_scene_id(args, name)?;
                let include_internal = args
                    .get("include_internal")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(true); // Default true for backward compatibility.
                let mut objects = Vec::new();
                if include_internal {
                    for obj in self.objects.values() {
                        if obj.scene_id == scene_id {
                            objects.push(json!({
                                "handle": obj.handle,
                                "type": obj.object_type,
                                "visible": obj.visible
                            }));
                        }
                    }
                } else {
                    let mut groups: HashMap<String, (&SceneObject, usize)> = HashMap::new();
                    for obj in self.objects.values() {
                        if obj.scene_id != scene_id {
                            continue;
                        }
                        if let Some(group_id) = obj.group_id.as_ref() {
                            let entry = groups.entry(group_id.clone()).or_insert((obj, 0));
                            entry.1 += 1;
                            continue;
                        }
                        objects.push(json!({
                            "handle": obj.handle,
                            "type": obj.object_type,
                            "visible": obj.visible
                        }));
                    }
                    for (group_id, (rep, count)) in groups {
                        objects.push(json!({
                            "handle": group_id,
                            "type": rep.object_type,
                            "visible": rep.visible,
                            "group": true,
                            "group_size": count
                        }));
                    }
                }
                Ok(json!({ "objects": objects }))
            }

            // Camera
            "set_camera_pose" => {
                let view_id = self.require_string(args, "view_id")?;
                let eye_val = args
                    .get("eye")
                    .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "eye is required"))?;
                let target_val = args
                    .get("target")
                    .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "target is required"))?;
                let up_val = args
                    .get("up")
                    .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "up is required"))?;
                let _eye = self.require_vec3(eye_val, "eye")?;
                let _target = self.require_vec3(target_val, "target")?;
                let _up = self.require_vec3(up_val, "up")?;
                let view = self.views.get_mut(&view_id).ok_or_else(|| HostError::new("ERR_NOT_FOUND", "View not found"))?;
                view.camera_pose = Some(json!({"eye": _eye, "target": _target, "up": _up}));
                self.add_log(
                    "debug",
                    "core",
                    "Camera pose set".to_string(),
                    self.fields_from_args(args, &["view_id", "eye", "target"]),
                );
                Ok(json!({}))
            }
            "get_camera_pose" => {
                // Host-side cache is only updated by set_camera_pose (programmatic),
                // not by user interaction in the viewer. Always return empty here
                // and let the viewer's camera_pose_response event carry real-time data.
                let _view_id = self.require_string(args, "view_id")?;
                Ok(json!({}))
            }
            "reset_camera" => {
                let mode = self.get_optional_string(args, "mode").unwrap_or_else(|| "fit_scene".to_string());
                if mode == "fit_object" {
                    let fit_handle = self
                        .get_optional_string(args, "fit_handle")
                        .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "fit_handle is required when mode=fit_object"))?;
                    if !self.objects.contains_key(&fit_handle) {
                        return Err(HostError::new(
                            "ERR_NOT_FOUND",
                            format!("Object not found: {}", fit_handle),
                        ));
                    }
                }
                self.add_log(
                    "debug",
                    "core",
                    "Camera reset".to_string(),
                    self.fields_from_args(args, &["view_id", "mode"]),
                );
                Ok(json!({}))
            }
            "set_camera_controls" => {
                let view_id = self.require_string(args, "view_id")?;
                if let Some(view) = self.views.get_mut(&view_id) {
                    if let Some(obj) = args.as_object() {
                        for (key, value) in obj {
                            if key != "view_id" {
                                view.camera_controls.insert(key.clone(), value.clone());
                            }
                        }
                    }
                }
                self.add_log(
                    "debug",
                    "core",
                    "Camera controls configured".to_string(),
                    self.fields_from_args(args, &["view_id"]),
                );
                Ok(json!({}))
            }

            // Gizmo
            "attach_gizmo" => {
                let view_id = self.require_string(args, "view_id")?;
                let handle = self.require_string(args, "handle")?;
                let mode = self.get_optional_string(args, "mode");
                self.gizmos.insert(
                    view_id.clone(),
                    GizmoState {
                        handle: handle.clone(),
                        mode,
                    },
                );
                self.add_log(
                    "info",
                    "core",
                    "Gizmo attached".to_string(),
                    self.fields_from_args(args, &["view_id", "handle", "mode", "mask"]),
                );
                Ok(json!({}))
            }
            "set_gizmo_mode" => {
                let view_id = self.require_string(args, "view_id")?;
                let mode = self.get_optional_string(args, "mode");
                if let Some(state) = self.gizmos.get_mut(&view_id) {
                    if mode.is_some() {
                        state.mode = mode;
                    }
                }
                self.add_log(
                    "info",
                    "core",
                    "Gizmo config updated".to_string(),
                    self.fields_from_args(args, &["view_id", "mode", "mask", "size"]),
                );
                Ok(json!({}))
            }
            "detach_gizmo" => {
                let view_id = self.require_string(args, "view_id")?;
                self.gizmos.remove(&view_id);
                self.add_log(
                    "info",
                    "core",
                    "Gizmo detached".to_string(),
                    self.fields_from_args(args, &["view_id"]),
                );
                Ok(json!({}))
            }

            // Picking
            "set_pick_config" => {
                self.add_log(
                    "debug",
                    "core",
                    "Pick config set".to_string(),
                    self.fields_from_args(args, &["view_id", "enabled", "button"]),
                );
                Ok(json!({}))
            }
            "clear_pick_highlight" => {
                self.add_log(
                    "debug",
                    "core",
                    "Pick highlight cleared".to_string(),
                    self.fields_from_args(args, &["view_id"]),
                );
                Ok(json!({}))
            }
            "get_picked_info" => Ok(json!({
                "hit_type": "none",
                "handle": null,
                "point_world": null,
                "normal_world": null,
                "point_index": null
            })),
            "get_pick_config" => Ok(json!({})),

            // View control
            "set_view" => {
                self.add_log(
                    "debug",
                    "core",
                    "View preset changed".to_string(),
                    self.fields_from_args(args, &["view_id", "view", "fit_all"]),
                );
                Ok(json!({}))
            }
            "set_render_mode" => {
                self.add_log(
                    "debug",
                    "core",
                    "Render mode changed".to_string(),
                    self.fields_from_args(args, &["view_id", "mode"]),
                );
                Ok(json!({}))
            }
            "set_view_config" => {
                if let Some(view_id) = self.get_optional_string(args, "view_id") {
                    if let Some(view) = self.views.get_mut(&view_id) {
                        if let Some(config) = args.get("config").and_then(|v| v.as_object()) {
                            let mut updates = config.clone();
                            if updates.contains_key("show_ground") && !updates.contains_key("show_grid") {
                                if let Some(value) = updates.get("show_ground").cloned() {
                                    updates.insert("show_grid".to_string(), value);
                                }
                            }
                            if updates.contains_key("axes_size") && !updates.contains_key("axes_length") {
                                if let Some(value) = updates.get("axes_size").cloned() {
                                    updates.insert("axes_length".to_string(), value);
                                }
                            }
                            for (key, value) in updates {
                                if key == "axes_size" {
                                    continue;
                                }
                                view.view_config.insert(key, value);
                            }
                        }
                    }
                }
                self.add_log(
                    "debug",
                    "core",
                    "View config updated".to_string(),
                    self.fields_from_args(args, &["view_id"]),
                );
                Ok(json!({}))
            }
            "set_performance_mode" => {
                self.add_log(
                    "debug",
                    "core",
                    "Performance mode changed".to_string(),
                    self.fields_from_args(args, &["view_id", "mode"]),
                );
                Ok(json!({}))
            }
            "set_interaction_mode" => Ok(json!({})),

            // Logging
            "set_log_config" => {
                if let Some(min_level) = self.get_optional_string(args, "min_level") {
                    self.log_config.min_level = min_level.to_lowercase();
                }
                if let Some(sinks) = args.get("sinks").and_then(|v| v.as_array()) {
                    for sink in sinks {
                        if sink.get("type").and_then(|v| v.as_str()) == Some("event") {
                            let enabled = sink.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false);
                            self.log_config.event_sink = enabled;
                        }
                    }
                }
                Ok(json!({}))
            }
            "read_logs" => {
                let after_seq = self.get_optional_u64(args, "after_seq").unwrap_or(0);
                let limit = self.get_optional_u64(args, "limit").unwrap_or(50) as usize;
                let entries: Vec<LogEntry> = self
                    .logs
                    .iter()
                    .filter(|entry| entry.seq > after_seq)
                    .take(limit)
                    .cloned()
                    .collect();
                let next_after_seq = entries.last().map(|e| e.seq).unwrap_or(after_seq);
                Ok(json!({ "next_after_seq": next_after_seq, "entries": entries }))
            }

            _ => Err(HostError::new(
                "ERR_INVALID_ARGS",
                format!("Command not implemented: {}", name),
            )),
        }
    }

    fn add_log(&mut self, level: &str, logger: &str, msg: String, fields: HashMap<String, Value>) {
        let entry = LogEntry {
            seq: self.next_log_seq(),
            ts_ms: now_ms(),
            level: level.to_string(),
            logger: logger.to_string(),
            msg,
            fields,
        };
        self.logs.push(entry.clone());
        if self.logs.len() > LOG_BUFFER_LIMIT {
            self.logs.remove(0);
        }
        if self.should_emit_log_event(&entry) {
            if let Some(sender) = &self.log_sender {
                let _ = sender.send(entry);
            }
        }
    }

    fn should_emit_log_event(&self, entry: &LogEntry) -> bool {
        if !self.log_config.event_sink {
            return false;
        }
        log_level_value(&entry.level) >= log_level_value(&self.log_config.min_level)
    }

    fn next_scene_id(&mut self) -> String {
        self.scene_counter += 1;
        format!("s_{}", self.scene_counter)
    }

    fn next_view_id(&mut self) -> String {
        self.view_counter += 1;
        format!("v_{}", self.view_counter)
    }

    fn next_buffer_id(&mut self) -> u64 {
        self.buffer_counter += 1;
        self.buffer_counter
    }

    fn next_handle_id(&mut self) -> u64 {
        self.handle_counter += 1;
        self.handle_counter
    }

    fn next_log_seq(&mut self) -> u64 {
        self.log_seq += 1;
        self.log_seq
    }

    fn ensure_scene(&mut self, scene_id: &str) {
        self.scenes.entry(scene_id.to_string()).or_insert_with(now_ms);
    }

    fn require_scene_id(&self, args: &Value, name: &str) -> Result<String, HostError> {
        let scene_id = self
            .get_optional_string(args, "scene_id")
            .ok_or_else(|| HostError::new("ERR_MISSING_SCENE_ID", format!("Missing scene_id for {}", name)))?;
        Ok(scene_id)
    }

    fn require_string(&self, args: &Value, key: &str) -> Result<String, HostError> {
        self.get_optional_string(args, key)
            .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", format!("Missing {}", key)))
    }

    fn require_bool(&self, args: &Value, key: &str) -> Result<bool, HostError> {
        args.get(key)
            .and_then(|v| v.as_bool())
            .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", format!("Missing {}", key)))
    }

    fn require_usize(&self, args: &Value, key: &str) -> Result<usize, HostError> {
        self.get_optional_u64(args, key)
            .map(|v| v as usize)
            .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", format!("Missing {}", key)))
    }

    fn require_value(&self, args: &Value, key: &str) -> Result<Value, HostError> {
        args.get(key)
            .cloned()
            .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", format!("Missing {}", key)))
    }

    fn get_optional_string(&self, args: &Value, key: &str) -> Option<String> {
        args.get(key).and_then(|v| v.as_str()).map(|s| s.to_string())
    }

    fn get_optional_u64(&self, args: &Value, key: &str) -> Option<u64> {
        args.get(key).and_then(|v| v.as_u64())
    }

    fn get_optional_f64(&self, args: &Value, key: &str) -> Option<f64> {
        args.get(key).and_then(|v| v.as_f64())
    }

    fn get_optional_usize_array(&self, args: &Value, key: &str) -> Option<Vec<usize>> {
        args.get(key)
            .and_then(|v| v.as_array())
            .and_then(|items| items.iter().map(|item| item.as_u64().and_then(|n| usize::try_from(n).ok())).collect())
    }

    fn get_optional_color(&self, args: &Value, key: &str) -> Result<Option<Vec<f64>>, HostError> {
        let value = match args.get(key) {
            Some(v) => v,
            None => return Ok(None),
        };
        let arr = value
            .as_array()
            .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", format!("{} must be an array", key)))?;
        let mut result = Vec::new();
        for val in arr {
            let num = val.as_f64().ok_or_else(|| {
                HostError::new("ERR_INVALID_ARGS", format!("{} must be numeric", key))
            })?;
            result.push(num);
        }
        Ok(Some(result))
    }

    fn parse_pose(&self, pose_val: Option<&Value>) -> Result<Pose, HostError> {
        let mut pose = Pose::identity();
        let Some(pose_val) = pose_val else {
            return Ok(pose);
        };
        let Some(obj) = pose_val.as_object() else {
            return Err(HostError::new("ERR_INVALID_ARGS", "pose must be an object"));
        };
        if let Some(pos) = obj.get("pos") {
            pose.pos = self.require_vec3(pos, "pose.pos")?;
        }
        if let Some(quat) = obj.get("quat") {
            pose.quat = self.require_vec4(quat, "pose.quat")?;
        }
        if let Some(scale) = obj.get("scale") {
            pose.scale = Some(self.require_vec3(scale, "pose.scale")?);
        }
        Ok(pose)
    }

    fn parse_pose_from_pos(&self, pos_val: Option<&Value>) -> Result<Pose, HostError> {
        let mut pose = Pose::identity();
        if let Some(pos) = pos_val {
            pose.pos = self.require_vec3(pos, "pos")?;
        }
        Ok(pose)
    }

    fn require_vec3(&self, value: &Value, key: &str) -> Result<[f64; 3], HostError> {
        let arr = value.as_array().ok_or_else(|| {
            HostError::new(
                "ERR_INVALID_ARGS",
                format!("{} must be an array of length 3", key),
            )
        })?;
        if arr.len() != 3 {
            return Err(HostError::new(
                "ERR_INVALID_ARGS",
                format!("{} must be an array of length 3", key),
            ));
        }
        let mut out = [0.0; 3];
        for (idx, item) in arr.iter().enumerate() {
            out[idx] = item.as_f64().ok_or_else(|| {
                HostError::new(
                    "ERR_INVALID_ARGS",
                    format!("{} must contain only numbers", key),
                )
            })?;
        }
        Ok(out)
    }

    fn require_vec4(&self, value: &Value, key: &str) -> Result<[f64; 4], HostError> {
        let arr = value.as_array().ok_or_else(|| {
            HostError::new(
                "ERR_INVALID_ARGS",
                format!("{} must be an array of length 4", key),
            )
        })?;
        if arr.len() != 4 {
            return Err(HostError::new(
                "ERR_INVALID_ARGS",
                format!("{} must be an array of length 4", key),
            ));
        }
        let mut out = [0.0; 4];
        for (idx, item) in arr.iter().enumerate() {
            out[idx] = item.as_f64().ok_or_else(|| {
                HostError::new(
                    "ERR_INVALID_ARGS",
                    format!("{} must contain only numbers", key),
                )
            })?;
        }
        Ok(out)
    }

    fn assert_color_range(&self, color: Option<&Vec<f64>>, context: &str) -> Result<(), HostError> {
        let Some(color) = color else {
            return Ok(());
        };
        if color.len() < 3 {
            return Err(HostError::new(
                "ERR_INVALID_ARGS",
                format!("{}: color must be an array [r,g,b] with values in [0,1].", context),
            ));
        }
        let limit = color.len().min(4);
        for i in 0..limit {
            let val = color[i];
            if !(0.0..=1.0).contains(&val) || val.is_nan() {
                return Err(HostError::new(
                    "ERR_INVALID_ARGS",
                    format!("{}: color component {}={} out of range [0,1].", context, i, val),
                ));
            }
        }
        Ok(())
    }

    fn get_dtype_size(&self, dtype: &str) -> Result<usize, HostError> {
        match dtype {
            "f32" | "u32" => Ok(4),
            "u16" => Ok(2),
            "u8" => Ok(1),
            _ => Err(HostError::new(
                "ERR_INVALID_ARGS",
                format!("Unsupported dtype: {}", dtype),
            )),
        }
    }

    fn validate_buffer_refs(&self, value: &Value) -> Result<(), HostError> {
        if let Some(map) = value.as_object() {
            if map.contains_key("buffer_id") {
                let id = self.require_string(value, "buffer_id")?;
                let entry = self.buffers.get(&id).ok_or_else(|| HostError::new("ERR_NOT_FOUND", "Buffer not found"))?;
                if entry.size_bytes != 0 && entry.received.as_slice() != [(0, entry.size_bytes)] {
                    return Err(HostError::new("ERR_BUFFER_INCOMPLETE", "Buffer upload is incomplete"));
                }
                let dtype = self.require_string(value, "dtype")?;
                let shape = self.get_optional_usize_array(value, "shape").ok_or_else(|| HostError::new("ERR_INVALID_ARGS", "Buffer reference requires a valid shape"))?;
                let bytes = shape.iter().try_fold(self.get_dtype_size(&dtype)?, |n, d| n.checked_mul(*d));
                if dtype != entry.dtype || bytes != Some(entry.size_bytes) {
                    return Err(HostError::new("ERR_BUFFER_SIZE_MISMATCH", "Buffer reference does not match uploaded data"));
                }
            }
            for child in map.values() { self.validate_buffer_refs(child)?; }
        } else if let Some(items) = value.as_array() {
            for child in items { self.validate_buffer_refs(child)?; }
        }
        Ok(())
    }

    fn collect_buffer_ids(&self, data: &Value) -> Vec<String> {
        let mut ids = Vec::new();
        self.collect_buffer_ids_recursive(data, &mut ids);
        ids
    }

    fn collect_buffer_ids_recursive(&self, data: &Value, ids: &mut Vec<String>) {
        if let Some(map) = data.as_object() {
            if let Some(buffer_id) = map.get("buffer_id").and_then(|v| v.as_str()) {
                ids.push(buffer_id.to_string());
            }
            for value in map.values() {
                self.collect_buffer_ids_recursive(value, ids);
            }
        } else if let Some(arr) = data.as_array() {
            for value in arr {
                self.collect_buffer_ids_recursive(value, ids);
            }
        }
    }

    fn collect_buffer_ids_from_object(&self, obj: &SceneObject) -> Vec<String> {
        obj.data
            .as_ref()
            .map(|data| self.collect_buffer_ids(data))
            .unwrap_or_default()
    }

    fn build_buffer_ref_counts(&self) -> HashMap<String, usize> {
        let mut counts = HashMap::new();
        for obj in self.objects.values() {
            for buffer_id in self.collect_buffer_ids_from_object(obj) {
                *counts.entry(buffer_id).or_insert(0) += 1;
            }
        }
        counts
    }

    fn release_buffers(&mut self, buffer_ids: Vec<String>, counts: &mut HashMap<String, usize>) {
        for buffer_id in buffer_ids {
            if let Some(count) = counts.get_mut(&buffer_id) {
                if *count > 0 {
                    *count -= 1;
                }
                if *count == 0 {
                    self.buffers.remove(&buffer_id);
                    counts.remove(&buffer_id);
                }
            }
        }
    }

    fn fields_from_args(&self, args: &Value, keys: &[&str]) -> HashMap<String, Value> {
        let mut fields = HashMap::new();
        if let Some(map) = args.as_object() {
            for key in keys {
                if let Some(value) = map.get(*key) {
                    fields.insert((*key).to_string(), value.clone());
                }
            }
        }
        fields
    }
}

fn log_level_value(level: &str) -> i32 {
    match level {
        "trace" => 10,
        "debug" => 20,
        "info" => 30,
        "warn" => 40,
        "error" => 50,
        _ => 30,
    }
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

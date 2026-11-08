//! Viewer-related command handlers

use crate::registry::{RegisteredViewer, ViewerRegistry};
use serde_json::{json, Value};

/// Handle register_viewer command
pub fn handle_register_viewer(
    registry: &mut ViewerRegistry,
    client_id: u64,
    viewer_name: &str,
    scene_id: &str,
    view_id: &str,
) -> Value {
    let viewer = RegisteredViewer {
        viewer_name: viewer_name.to_string(),
        view_id: view_id.to_string(),
        scene_id: scene_id.to_string(),
        client_id,
    };
    
    registry.register(viewer);
    
    json!({
        "view_id": view_id,
        "scene_id": scene_id,
        "viewer_name": viewer_name,
    })
}

/// Handle get_viewer_by_name command
pub fn handle_get_viewer_by_name(
    registry: &ViewerRegistry,
    viewer_name: &str,
) -> Option<Value> {
    registry.get(viewer_name).map(|v| {
        json!({
            "view_id": v.view_id,
            "scene_id": v.scene_id,
            "viewer_name": v.viewer_name,
        })
    })
}

/// Handle list_viewers command
pub fn handle_list_viewers(registry: &ViewerRegistry) -> Value {
    let viewers: Vec<Value> = registry
        .list()
        .iter()
        .map(|v| {
            json!({
                "viewer_name": v.viewer_name,
                "view_id": v.view_id,
                "scene_id": v.scene_id,
            })
        })
        .collect();
    
    json!({ "viewers": viewers })
}

//! Viewer Registration Registry

use std::collections::HashMap;

/// Information about a registered viewer
#[derive(Clone, Debug)]
pub struct RegisteredViewer {
    pub viewer_name: String,
    pub view_id: String,
    pub scene_id: String,
    pub client_id: u64,
}

/// Registry for managing named viewers
pub struct ViewerRegistry {
    viewers: HashMap<String, RegisteredViewer>,
}

impl ViewerRegistry {
    /// Create a new empty registry
    pub fn new() -> Self {
        Self {
            viewers: HashMap::new(),
        }
    }

    /// Register a new viewer
    pub fn register(&mut self, viewer: RegisteredViewer) {
        self.viewers.insert(viewer.viewer_name.clone(), viewer);
    }

    /// Get a viewer by name
    pub fn get(&self, name: &str) -> Option<&RegisteredViewer> {
        self.viewers.get(name)
    }

    /// Remove a viewer by name
    pub fn remove(&mut self, name: &str) -> Option<RegisteredViewer> {
        self.viewers.remove(name)
    }

    /// List all registered viewers
    pub fn list(&self) -> Vec<&RegisteredViewer> {
        self.viewers.values().collect()
    }

    /// Remove all viewers for a specific client
    pub fn remove_by_client(&mut self, client_id: u64) {
        self.viewers.retain(|_, v| v.client_id != client_id);
    }

    /// Check if a viewer name is registered
    pub fn contains(&self, name: &str) -> bool {
        self.viewers.contains_key(name)
    }
}

impl Default for ViewerRegistry {
    fn default() -> Self {
        Self::new()
    }
}

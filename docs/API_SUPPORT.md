# Static API inventory

This table records command-name literals in the implementation. Presence does not prove equivalent signatures, rendering, compatibility, or test coverage. Use the versioned API contract and actual acceptance receipts.

| Command | Host | Core | Python | C++ |
|---|---|---|---|---|
| `add_instances` | present | present | present | present |
| `add_lines` | present | present | present | present |
| `add_mesh` | present | present | present | present |
| `add_node` | present | present | present | present |
| `add_points` | present | present | present | present |
| `add_primitive` | present | present | present | present |
| `add_text_2d` | present | present | present | present |
| `add_text_3d` | present | present | present | present |
| `add_widget` | present | present | present | present |
| `attach_gizmo` | present | present | present | present |
| `attach_scene` | present | not directly referenced | present | not directly referenced |
| `clear_pick_highlight` | present | present | present | not directly referenced |
| `clear_scene` | present | present | present | present |
| `clone_object` | present | present | present | present |
| `create_buffer` | present | present | present | not directly referenced |
| `create_scene` | present | not directly referenced | present | present |
| `create_view` | present | not directly referenced | present | present |
| `destroy_scene` | present | present | present | present |
| `destroy_view` | present | present | present | present |
| `detach_gizmo` | present | present | present | present |
| `free_buffer` | present | present | present | present |
| `get_alpha` | present | present | present | present |
| `get_camera_controls` | present | present | present | present |
| `get_camera_pose` | present | present | present | present |
| `get_camera_view` | present | not directly referenced | present | present |
| `get_color` | present | present | present | present |
| `get_display_state` | present | not directly referenced | present | present |
| `get_pick_config` | present | present | present | present |
| `get_picked_info` | present | present | present | not directly referenced |
| `get_render_endpoint` | present | not directly referenced | present | not directly referenced |
| `get_resource_counts` | present | not directly referenced | not directly referenced | not directly referenced |
| `get_scene_snapshot` | present | not directly referenced | not directly referenced | not directly referenced |
| `get_transform` | present | not directly referenced | present | present |
| `get_view_config` | present | present | present | present |
| `get_viewer_by_name` | present | not directly referenced | not directly referenced | not directly referenced |
| `get_visible` | present | not directly referenced | present | not directly referenced |
| `get_widget` | present | not directly referenced | present | present |
| `is_object_alive` | present | not directly referenced | present | present |
| `list_objects` | present | not directly referenced | present | not directly referenced |
| `list_scenes` | present | not directly referenced | present | not directly referenced |
| `list_viewers` | present | not directly referenced | not directly referenced | not directly referenced |
| `list_views` | present | not directly referenced | present | present |
| `list_widgets` | present | not directly referenced | present | present |
| `load_mesh` | present | present | present | present |
| `present_view` | present | not directly referenced | present | present |
| `read_logs` | present | not directly referenced | present | not directly referenced |
| `register_viewer` | present | not directly referenced | not directly referenced | not directly referenced |
| `remove_object` | present | present | present | present |
| `remove_objects` | present | present | present | present |
| `remove_text_2d` | present | present | not directly referenced | not directly referenced |
| `remove_text_3d` | present | present | not directly referenced | not directly referenced |
| `remove_widget` | present | present | present | present |
| `reset_camera` | present | present | present | present |
| `set_alpha` | present | present | present | present |
| `set_camera_controls` | present | present | present | present |
| `set_camera_pose` | present | present | present | present |
| `set_camera_view` | present | present | present | present |
| `set_color` | present | present | present | present |
| `set_geometry_scale` | present | present | present | present |
| `set_gizmo_mode` | present | present | present | present |
| `set_interaction_mode` | present | present | not directly referenced | not directly referenced |
| `set_log_config` | present | not directly referenced | present | not directly referenced |
| `set_object_alphas` | present | present | present | not directly referenced |
| `set_object_colors` | present | present | present | not directly referenced |
| `set_object_metadata` | present | present | present | present |
| `set_object_transforms` | present | present | present | present |
| `set_object_visibilities` | present | present | present | not directly referenced |
| `set_parent` | present | present | present | present |
| `set_performance_mode` | present | present | present | not directly referenced |
| `set_pick_config` | present | present | present | present |
| `set_render_mode` | present | present | present | present |
| `set_transform` | present | present | present | present |
| `set_view` | present | present | present | present |
| `set_view_config` | present | present | present | present |
| `set_visible` | present | present | present | present |
| `set_widget_value` | present | present | present | present |
| `u16` | present | present | not directly referenced | not directly referenced |
| `u8` | present | present | present | present |
| `update_instances` | present | present | present | present |
| `update_text_2d` | present | present | present | not directly referenced |
| `update_text_3d` | present | present | present | not directly referenced |
| `upload_buffer_chunk` | present | not directly referenced | present | not directly referenced |

use frameviz_server::Host;
use serde_json::{json, Value};

fn send(host: &mut Host, command: &str, mut args: Value) -> Value {
    host.handle_command(command, &mut args).unwrap()
}

fn add(host: &mut Host, command: &str, args: Value) -> Value {
    send(host, command, args)["handle"].clone()
}

fn transform(host: &mut Host, handle: &Value, space: &str) -> Value {
    send(host, "get_transform", json!({"handle": handle, "space": space, "matrix": true}))
}

fn assert_vector(actual: &Value, expected: &[f64]) {
    let actual = actual.as_array().unwrap();
    assert_eq!(actual.len(), expected.len());
    for (a, e) in actual.iter().zip(expected) {
        assert!((a.as_f64().unwrap() - e).abs() < 1e-9, "{actual:?} != {expected:?}");
    }
}

#[test]
fn reparent_and_detach_preserve_world_pose_of_a_rotated_subtree() {
    let mut host = Host::new(None);
    let s = std::f64::consts::FRAC_1_SQRT_2;
    let a = add(&mut host, "add_node", json!({
        "scene_id": "s", "pose": [3., 1., 0., 0., 0., s, s],
    }));
    let b = add(&mut host, "add_node", json!({
        "scene_id": "s", "pose": {"position": [-2., 4., 0.], "quaternion": [0., 0., -s, s]},
    }));
    let child = add(&mut host, "add_primitive", json!({
        "scene_id": "s", "type": "box", "parent": a, "pose": [2., 0., 0., 0., 0., 0., 1.],
    }));
    let tip = add(&mut host, "add_node", json!({
        "scene_id": "s", "parent": child, "pose": [1., 0., 0., 0., 0., 0., 1.],
    }));
    for parent in [b.clone(), Value::Null] {
        send(&mut host, "set_parent", json!({"handle": child, "parent": parent}));
        let world = transform(&mut host, &child, "world");
        assert_vector(&world["pose"]["pos"], &[3., 3., 0.]);
        assert_vector(&world["pose"]["quat"], &[0., 0., s, s]);
        assert_vector(&world["matrix"], &[0.,1.,0.,0., -1.,0.,0.,0., 0.,0.,1.,0., 3.,3.,0.,1.]);
        assert_vector(&transform(&mut host, &tip, "world")["pose"]["pos"], &[3., 4., 0.]);
    }
    send(&mut host, "set_parent", json!({
        "handle": child, "parent": b, "local_transform": [1., 0., 0., 0., 0., 0., 1.],
    }));
    assert_vector(&transform(&mut host, &child, "local")["pose"]["pos"], &[1., 0., 0.]);
    assert_vector(&transform(&mut host, &tip, "world")["pose"]["pos"], &[-2., 2., 0.]);
    send(&mut host, "set_parent", json!({
        "handle": child, "parent": null, "local_transform": [7., 0., 0., 0., 0., 0., 1.],
    }));
    assert_vector(&transform(&mut host, &tip, "world")["pose"]["pos"], &[8., 0., 0.]);
}

#[test]
fn rejected_reparent_does_not_change_pose_or_relationship() {
    let mut host = Host::new(None);
    let root = add(&mut host, "add_node", json!({"scene_id": "s"}));
    let child = add(&mut host, "add_node", json!({"scene_id": "s", "parent": root}));
    let foreign = add(&mut host, "add_node", json!({"scene_id": "other"}));
    let before = serde_json::to_value(host.build_scene_snapshot("s").unwrap()).unwrap();
    for args in [
        json!({"handle": root, "parent": child}),
        json!({"handle": root, "parent": root}),
        json!({"handle": child, "parent": foreign}),
        json!({"handle": child, "parent": "missing"}),
        json!({"handle": child, "parent": 42}),
        json!({"handle": child, "parent": null, "local_transform": [0,0,0,0,0,0,0]}),
        json!({"handle": child, "parent": null, "local_transform": {"scale": [2,2,2]}}),
    ] {
        assert!(host.handle_command("set_parent", &mut args.clone()).is_err(), "{args}");
        assert_eq!(serde_json::to_value(host.build_scene_snapshot("s").unwrap()).unwrap(), before);
    }
    let mut invalid = json!({"scene_id": "missing", "parent": root});
    assert!(host.handle_command("add_node", &mut invalid).is_err());
    assert_eq!(send(&mut host, "list_scenes", json!({}))["scenes"].as_array().unwrap().len(), 2);
}

#[test]
fn geometry_scale_does_not_inherit_and_visibility_does() {
    let mut host = Host::new(None);
    let root = add(&mut host, "add_primitive", json!({
        "scene_id": "s", "type": "box",
        "pose": {"pos": [1,0,0], "scale": [4,2,3]},
        "name": "link", "tags": {"kind": "root"},
    }));
    let child = add(&mut host, "add_primitive", json!({
        "scene_id": "s", "type": "box", "parent": root, "name": "link",
        "pose": {"position": [2,0,0], "quaternion": [0,0,0,2]},
    }));
    assert_vector(&transform(&mut host, &child, "world")["pose"]["pos"], &[3.,0.,0.]);
    let root_local = transform(&mut host, &root, "local");
    assert_vector(&root_local["geometry_scale"], &[4.,2.,3.]);
    assert_vector(&root_local["matrix"], &[1.,0.,0.,0., 0.,1.,0.,0., 0.,0.,1.,0., 1.,0.,0.,1.]);
    send(&mut host, "set_visible", json!({"handle": root, "visible": false}));
    let objects = send(&mut host, "list_objects", json!({"scene_id": "s"}));
    let child_info = objects["objects"].as_array().unwrap().iter().find(|o| o["handle"] == child).unwrap();
    assert_eq!(child_info["parent"], root);
    assert_eq!(child_info["name"], "link");
    assert_eq!(child_info["visible"], true);
    assert_eq!(child_info["effective_visible"], false);
    send(&mut host, "set_object_metadata", json!({"handle": child, "tags": {"i": 2}}));
    send(&mut host, "set_visible", json!({"handle": root, "visible": true}));
    let objects = send(&mut host, "list_objects", json!({"scene_id": "s"}));
    let child_info = objects["objects"].as_array().unwrap().iter().find(|o| o["handle"] == child).unwrap();
    assert_eq!(child_info["name"], "link");
    assert_eq!(child_info["tags"], json!({"i": 2}));
    assert_eq!(child_info["effective_visible"], true);
}

#[test]
fn chunked_point_cloud_is_one_object_and_subtree_removal_releases_all_chunks() {
    let mut host = Host::new(None);
    let parent = add(&mut host, "add_node", json!({"scene_id": "s"}));
    let chunks: Vec<Value> = (0..2).map(|_| {
        let buffer = send(&mut host, "create_buffer", json!({"size_bytes": 24, "dtype": "f32", "shape": [2,3]}));
        let id = buffer["buffer_id"].as_str().unwrap();
        host.store_buffer_data(id, 0, &[0; 24]).unwrap();
        json!({"positions": {"buffer_id": id, "dtype": "f32", "shape": [2,3]}})
    }).collect();
    let cloud = add(&mut host, "add_points", json!({"scene_id": "s", "parent": parent, "chunks": chunks}));
    let snapshot = send(&mut host, "get_scene_snapshot", json!({"scene_id": "s"}));
    assert_eq!(snapshot["objects"].as_array().unwrap().len(), 2);
    assert_eq!(snapshot["objects"][0]["handle"], parent);
    assert_eq!(snapshot["objects"][1]["handle"], cloud);
    assert_eq!(snapshot["objects"][1]["data"]["chunks"].as_array().unwrap().len(), 2);
    let listed = send(&mut host, "list_objects", json!({"scene_id": "s", "include_internal": true}));
    assert_eq!(listed["objects"].as_array().unwrap().len(), 2);
    send(&mut host, "remove_objects", json!({"scene_id": "s", "handles": [parent, cloud]}));
    assert_eq!(host.resource_counts()["objects"], 0);
    assert_eq!(host.resource_counts()["buffers"], 0);
}

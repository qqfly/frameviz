use frameviz_server::Host;
use serde_json::{json, Value};
fn command(h: &mut Host, name: &str, mut args: Value) -> Value { h.handle_command(name, &mut args).unwrap() }
fn scene(h: &mut Host, id: &str) { command(h, "create_scene", json!({"scene_id":id})); }
fn primitive(h: &mut Host, id: &str) -> Value { command(h,"add_primitive",json!({"scene_id":id,"type":"box"}))["handle"].clone() }
#[test] fn wrong_scene_removal_is_rejected_without_mutation() {
 let mut h=Host::new(None); scene(&mut h,"a"); scene(&mut h,"b"); let obj=primitive(&mut h,"a");
 assert!(h.handle_command("remove_object", &mut json!({"scene_id":"b","handle":obj})).is_err());
 assert_eq!(h.build_scene_snapshot("a").unwrap().objects.len(),1);
}
#[test] fn invalid_batch_removal_is_atomic() {
 let mut h=Host::new(None); scene(&mut h,"a"); let obj=primitive(&mut h,"a");
 assert!(h.handle_command("remove_objects", &mut json!({"scene_id":"a","handles":[obj,"missing"]})).is_err());
 assert_eq!(h.build_scene_snapshot("a").unwrap().objects.len(),1);
}
#[test] fn referenced_buffer_survives_sdk_release() {
 let mut h=Host::new(None); scene(&mut h,"a");
 let b=command(&mut h,"create_buffer",json!({"size_bytes":12,"dtype":"f32","shape":[1,3]}))["buffer_id"].clone();
 h.store_buffer_data(b.as_str().unwrap(),0,&[0;12]).unwrap();
 let obj=command(&mut h,"add_points",json!({"scene_id":"a","positions":{"buffer_id":b,"dtype":"f32","shape":[1,3]},"color":[0.2,0.4,0.6]}))["handle"].clone();
 command(&mut h,"free_buffer",json!({"buffer_id":b}));
 assert!(h.get_buffer_data(b.as_str().unwrap()).is_some());
 command(&mut h,"remove_object",json!({"scene_id":"a","handle":obj}));
 assert!(h.get_buffer_data(b.as_str().unwrap()).is_none());
}
#[test] fn point_snapshot_preserves_uniform_color() {
 let mut h=Host::new(None); scene(&mut h,"a");
 command(&mut h,"add_points",json!({"scene_id":"a","positions":{},"color":[0.2,0.4,0.6]}));
 assert_eq!(h.build_scene_snapshot("a").unwrap().objects[0].color,Some(vec![0.2,0.4,0.6]));
}
#[test] fn buffer_type_is_always_validated() {
 let mut h=Host::new(None);
 assert!(h.handle_command("create_buffer",&mut json!({"size_bytes":12,"dtype":"invalid"})).is_err());
}
#[test] fn allocation_limits_and_shape_overflow_are_rejected() {
 let mut h=Host::new(None);
 for args in [json!({"size_bytes":268435457u64,"dtype":"u8"}),json!({"size_bytes":8,"dtype":"f32","shape":[18446744073709551615u64,4]})] {
  assert!(h.handle_command("create_buffer",&mut args.clone()).is_err());
 }
}
#[test] fn overflowing_chunk_offset_is_rejected_without_panic() {
 let mut h=Host::new(None);let b=command(&mut h,"create_buffer",json!({"size_bytes":4,"dtype":"u8"}));
 assert!(h.store_buffer_data(b["buffer_id"].as_str().unwrap(),usize::MAX,&[1,2]).is_err());
 assert_eq!(h.get_buffer_data(b["buffer_id"].as_str().unwrap()).unwrap(),vec![0;4]);
}
#[test] fn batch_transform_cannot_cross_scenes() {
 let mut h=Host::new(None);scene(&mut h,"a");scene(&mut h,"b");let a=primitive(&mut h,"a");let b=primitive(&mut h,"b");
 assert!(h.handle_command("set_object_transforms",&mut json!({"scene_id":"a","items":[{"handle":a,"pose":{"pos":[9,0,0]}},{"handle":b,"pose":{"pos":[9,0,0]}}]})).is_err());
 assert_eq!(h.build_scene_snapshot("a").unwrap().objects[0].pose.pos,[0.,0.,0.]);
}
#[test] fn incomplete_or_overlapping_upload_cannot_be_committed() {
 let mut h=Host::new(None);scene(&mut h,"a");
 let b=command(&mut h,"create_buffer",json!({"size_bytes":12,"dtype":"f32","shape":[1,3]}))["buffer_id"].clone();
 let mut args=json!({"scene_id":"a","positions":{"buffer_id":b,"dtype":"f32","shape":[1,3]}});
 h.store_buffer_data(b.as_str().unwrap(),0,&[0;6]).unwrap();
 h.store_buffer_data(b.as_str().unwrap(),0,&[0;6]).unwrap();
 assert!(h.handle_command("add_points",&mut args).is_err());
 assert!(h.build_scene_snapshot("a").unwrap().objects.is_empty());
 h.store_buffer_data(b.as_str().unwrap(),6,&[0;6]).unwrap();
 assert!(h.handle_command("add_points",&mut args).is_ok());
 assert!(h.store_buffer_data(b.as_str().unwrap(),0,&[1;12]).is_err());
}
#[test] fn mismatched_buffer_reference_is_rejected() {
 let mut h=Host::new(None);scene(&mut h,"a");
 let b=command(&mut h,"create_buffer",json!({"size_bytes":12,"dtype":"f32","shape":[1,3]}))["buffer_id"].clone();
 h.store_buffer_data(b.as_str().unwrap(),0,&[0;12]).unwrap();
 assert!(h.handle_command("add_points",&mut json!({"scene_id":"a","positions":{"buffer_id":b,"dtype":"u8","shape":[12]}})).is_err());
}

#[test]
fn rejected_display_batches_are_atomic_at_every_position() {
    for (name, key, good, bad) in [
        ("set_object_colors", "rgba", json!([0,1,0]), json!([2,0,0])),
        ("set_object_alphas", "alpha", json!(0.3), json!(-1)),
        ("set_object_visibilities", "visible", json!(false), json!("false")),
        ("set_object_transforms", "pose", json!({"pos":[1,2,3]}), json!({"pos":[1,2]})),
    ] {
        for invalid_index in 0..3 {
            let mut host = Host::new(None);
            let handles: Vec<Value> = (0..3).map(|_| primitive(&mut host, "a")).collect();
            let before = serde_json::to_value(host.build_scene_snapshot("a").unwrap()).unwrap();
            let mut items: Vec<Value> = handles.into_iter().map(|handle| json!({"handle":handle,key:good})).collect();
            items[invalid_index][key] = bad.clone();
            assert!(host.handle_command(name, &mut json!({"scene_id":"a","items":items})).is_err());
            assert_eq!(before, serde_json::to_value(host.build_scene_snapshot("a").unwrap()).unwrap());
        }
    }
}

#[test]
fn failed_add_and_read_do_not_create_scenes() {
    let mut host = Host::new(None);
    assert!(host.handle_command("add_primitive", &mut json!({"scene_id":"missing"})).is_err());
    command(&mut host, "get_scene_snapshot", json!({"scene_id":"missing"}));
    assert_eq!(command(&mut host, "list_scenes", json!({})), json!({"scenes":[]}));
}

#[test]
fn invalid_scope_types_are_rejected_at_host_boundary() {
    let mut host = Host::new(None);
    let handle = primitive(&mut host, "a");
    for scope in [Value::Null, json!([]), json!(7)] {
        assert!(host.handle_command("set_transform", &mut json!({"handle":handle,"scene_id":scope,"pose":{"pos":[1,2,3]}})).is_err());
    }
    assert_eq!(host.build_scene_snapshot("a").unwrap().objects[0].pose.pos, [0.,0.,0.]);
}

#[test]
fn uniform_color_releases_only_the_last_shared_color_reference() {
    let mut host = Host::new(None);
    let mut refs = Vec::new();
    for _ in 0..2 {
        let id = command(&mut host, "create_buffer", json!({"size_bytes":12,"dtype":"f32","shape":[1,3]}))["buffer_id"].clone();
        host.store_buffer_data(id.as_str().unwrap(),0,&[0;12]).unwrap();
        refs.push(json!({"buffer_id":id,"dtype":"f32","shape":[1,3]}));
    }
    let a = command(&mut host,"add_points",json!({"scene_id":"a","positions":refs[0],"colors":refs[1]}))["handle"].clone();
    let b = command(&mut host,"clone_object",json!({"handle":a}))["handle"].clone();
    let color_id = refs[1]["buffer_id"].as_str().unwrap();
    command(&mut host,"set_color",json!({"handle":a,"rgba":[1,0,0]}));
    assert!(host.get_buffer_data(color_id).is_some());
    command(&mut host,"set_color",json!({"handle":b,"rgba":[0,1,0]}));
    assert!(host.get_buffer_data(color_id).is_none());
}

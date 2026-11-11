import type { FrameVizCore } from './core.js';

/** One replay path for both standalone and embedded viewers. */
export function applySceneSnapshot(core: FrameVizCore, snapshot: any): void {
  if (!core.acceptRevision(snapshot.revision)) return;
  core.handleCommand('clear_scene', { scene_id: snapshot.scene_id });
  core.createScene(snapshot.scene_id);
  for (const [bufferId, info] of Object.entries(snapshot.buffers ?? {}) as Array<[string, any]>) {
    core.handleCommand('create_buffer', info, { buffer_id: bufferId });
    if (info.data_base64 !== undefined) {
      core.storeBufferData(bufferId, 0, decodeBufferBase64(info.data_base64));
    }
  }
  for (const object of snapshot.objects ?? []) restoreSceneObject(core, object);
  core.restoreWidgets(snapshot.widgets ?? []);
  if (snapshot.view_config) core.handleCommand('set_view_config', { config: snapshot.view_config });
  if (snapshot.camera_controls) core.handleCommand('set_camera_controls', snapshot.camera_controls);
  if (snapshot.camera_pose) core.handleCommand('set_camera_pose', snapshot.camera_pose);
  core.handleCommand('set_render_mode', { mode: snapshot.render_mode ?? 'solid' });
  for (const overlay of snapshot.overlays ?? []) {
    core.handleCommand('add_text_2d', overlay.data, { handle: overlay.handle });
  }
}

export function decodeBufferBase64(encoded: string): Uint8Array {
  return Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
}

/** Restore one authoritative object, including while its model/buffers are loading. */
export function restoreSceneObject(core: FrameVizCore, object: any): void {
  const commands: Record<string, string> = {
    node: 'add_node', primitive: 'add_primitive', points: 'add_points', lines: 'add_lines', mesh: 'add_mesh',
    instances: 'add_instances', loaded_mesh: 'load_mesh', text3d: 'add_text_3d', text_3d: 'add_text_3d',
  };
  const command = commands[object.object_type];
  if (!command) return;
  const pose = object.pose && { ...object.pose, scale: object.geometry_scale ?? object.pose.scale };
  const args = { ...object.data, scene_id: object.scene_id, parent: object.parent, pose,
    pos: object.pose?.pos, color: object.color ?? object.data?.color, group_id: object.group_id };
  core.handleCommand(command, args, { handle: object.handle });
  if (pose) core.handleCommand('set_transform', { handle: object.handle, pose });
  if (object.color) core.handleCommand('set_alpha', { handle: object.handle, alpha: object.color[3] ?? 1 });
  core.handleCommand('set_visible', { handle: object.handle, visible: object.visible });
}

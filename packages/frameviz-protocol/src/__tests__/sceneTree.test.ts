import { describe, expect, it } from 'vitest';
import { validateCommandArgs } from '../commandValidation';

describe('rigid scene commands', () => {
  it('accepts both rigid pose forms and geometry scale as a separate field', () => {
    const pose = { position: [1, 2, 3], quaternion: [0, 0, 0, 1] };
    expect(validateCommandArgs('add_node', { scene_id: 's', pose, parent: null }).ok).toBe(true);
    expect(validateCommandArgs('set_transform', {
      handle: 'h', pose: [1, 2, 3, 0, 0, 0, 1], geometry_scale: [2, 1, 1],
    }).ok).toBe(true);
    expect(validateCommandArgs('get_transform', { handle: 'h', space: 'world', matrix: true }).ok).toBe(true);
  });

  it('accepts reparenting to a handle or the root with an optional rigid pose', () => {
    expect(validateCommandArgs('set_parent', { handle: 'h', parent: 'p' }).ok).toBe(true);
    expect(validateCommandArgs('set_parent', {
      handle: 'h', parent: null, local_transform: [1, 2, 3, 0, 0, 0, 1],
    }).ok).toBe(true);
    expect(validateCommandArgs('set_parent', {
      handle: 'h', parent: null, local_transform: { scale: [2, 2, 2] },
    }).ok).toBe(false);
    expect(validateCommandArgs('set_parent', { handle: 'h', parent: 12 }).ok).toBe(false);
  });

  it('accepts multiple point buffers in a single draw command', () => {
    const positions = { buffer_id: 'p', dtype: 'f32', shape: [4, 3] };
    expect(validateCommandArgs('add_points', { scene_id: 's', chunks: [{ positions }, { positions }] }).ok).toBe(true);
    expect(validateCommandArgs('add_points', { scene_id: 's', chunks: [{ positions }], positions }).ok).toBe(false);
  });
});

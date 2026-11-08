import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as THREE from 'three';
import { FrameVizCore } from '../core';

let resolveLoad: ((obj: THREE.Object3D) => void) | null = null;

vi.mock('three', async () => {
  const actual = await vi.importActual<typeof THREE>('three');
  return {
    ...actual,
    WebGLRenderer: vi.fn().mockImplementation(() => ({
      setSize: vi.fn(),
      setPixelRatio: vi.fn(),
      render: vi.fn(),
      dispose: vi.fn(),
      domElement: document.createElement('canvas'),
      // Required for SceneManager.createRenderer
      getContext: vi.fn().mockReturnValue({
        getExtension: vi.fn(),
        getParameter: vi.fn().mockReturnValue(16),
      }),
      capabilities: {
        maxTextureSize: 16384,
      },
      info: {
        render: { triangles: 0, points: 0, lines: 0 },
        memory: { geometries: 0, textures: 0 },
      },
    })),
  };
});

vi.mock('three/examples/jsm/renderers/CSS2DRenderer.js', () => {
  return {
    CSS2DRenderer: vi.fn().mockImplementation(() => ({
      setSize: vi.fn(),
      render: vi.fn(),
      domElement: document.createElement('div'),
    })),
  };
});

vi.mock('three/examples/jsm/controls/OrbitControls.js', () => {
  return {
    OrbitControls: vi.fn().mockImplementation(() => ({
      target: new THREE.Vector3(0, 0, 0),
      enableDamping: true,
      update: vi.fn(),
      dispose: vi.fn(),
    })),
  };
});

vi.mock('three/examples/jsm/controls/TransformControls.js', () => {
  return {
    TransformControls: vi.fn().mockImplementation(() => ({
      attach: vi.fn(),
      detach: vi.fn(),
      setMode: vi.fn(),
      setSize: vi.fn(),
      setSpace: vi.fn(),
      setTranslationSnap: vi.fn(),
      setRotationSnap: vi.fn(),
      setScaleSnap: vi.fn(),
      addEventListener: vi.fn(),
      dispose: vi.fn(),
      showX: true,
      showY: true,
      showZ: true,
      mode: 'translate',
      space: 'local',
      object: null,
      parent: null,
    })),
  };
});

vi.mock('../MeshLoader.js', () => {
  return {
    MeshLoader: class {
      load() {
        return new Promise<THREE.Object3D>((resolve) => {
          resolveLoad = resolve;
        });
      }
    }
  };
});

describe('FrameVizCore cleanup', () => {
  let container: HTMLElement;
  let core: FrameVizCore;

  beforeEach(() => {
    resolveLoad = null;
    container = document.createElement('div');
    container.style.width = '800px';
    container.style.height = '600px';
    document.body.appendChild(container);
    core = new FrameVizCore({ container });
  });

  afterEach(() => {
    if (container.parentNode) {
      document.body.removeChild(container);
    }
  });

  it('does not render partially uploaded or overlapping buffers', () => {
    core.handleCommand('create_buffer', { dtype: 'f32', size_bytes: 24 }, { buffer_id: 'b' });
    core.storeBufferData('b', 0, new Float32Array([1, 2, 3]));
    core.handleCommand('add_points', { positions: { buffer_id: 'b', dtype: 'f32' } }, { handle: 'p' });
    expect(core.getObjectCount()).toBe(0);
    core.storeBufferData('b', 0, new Float32Array([1, 2, 3]));
    expect(core.getObjectCount()).toBe(0);
    core.storeBufferData('b', 12, new Float32Array([4, 5, 6]));
    expect(core.getObjectCount()).toBe(1);
  });

  it('keeps clone material and geometry independent', () => {
    core.handleCommand('add_primitive', { type: 'box', color: [1, 0, 0] }, { handle: 'a' });
    core.handleCommand('clone_object', { handle: 'a' }, { handle: 'b' });
    const a = (core as any).objects.get('a');
    const b = (core as any).objects.get('b');
    expect(b.material).not.toBe(a.material);
    expect(b.geometry).not.toBe(a.geometry);
    core.handleCommand('set_color', { handle: 'b', rgba: [0, 1, 0, 1] });
    expect(a.material.color.r).toBe(1);
  });

  it('replays mutations made while a model is loading', async () => {
    core.handleCommand('load_mesh', { url: '/model.stl' }, { handle: 'm' });
    core.handleCommand('set_transform', { handle: 'm', pose: { pos: [2, 3, 4], quat: [0, 0, 0, 1] } });
    core.handleCommand('set_visible', { handle: 'm', visible: false });
    resolveLoad!(new THREE.Object3D());
    await Promise.resolve(); await Promise.resolve();
    const m = (core as any).objects.get('m');
    expect(m.position.toArray()).toEqual([2, 3, 4]);
    expect(m.visible).toBe(false);
  });

  it('updates grouped axes instances while preserving rotation, scale and object pose', () => {
    const buffer = (id: string, values: number[]) => {
      core.handleCommand('create_buffer', {dtype:'f32',size_bytes:values.length * 4}, {buffer_id:id});
      core.storeBufferData(id,0,new Float32Array(values));
      return {buffer_id:id,dtype:'f32'};
    };
    const positions = buffer('p',[0,0,0]);
    const quats = buffer('q',[0,0,Math.SQRT1_2,Math.SQRT1_2]);
    const scales = buffer('s',[2,3,4]);
    core.handleCommand('add_instances',{type:'axes',positions,quats,scales},{handle:'axes'});
    core.handleCommand('set_transform',{handle:'axes',pose:{pos:[5,0,0],quat:[0,0,0,1]}});
    core.handleCommand('update_instances',{handle:'axes',positions:buffer('p2',[10,20,30])});
    const obj=(core as any).objects.get('axes');
    expect(obj.position.toArray()).toEqual([5,0,0]);
    obj.traverse((child: THREE.Object3D)=>{
      if (!(child instanceof THREE.InstancedMesh)) return;
      const m=new THREE.Matrix4(),p=new THREE.Vector3(),q=new THREE.Quaternion(),s=new THREE.Vector3();
      child.getMatrixAt(0,m);m.decompose(p,q,s);
      expect(p.toArray()).toEqual([10,20,30]);
      s.toArray().forEach((value, i) => expect(value).toBeCloseTo([2,3,4][i], 6));
      expect(q.z).toBeCloseTo(Math.SQRT1_2);
    });
    core.handleCommand('remove_object',{handle:'axes'});
    expect((core as any).buffers.size).toBe(0);
  });

  it('clears pending renders after clear_scene', () => {
    const bufferId = 'b_1';
    core.handleCommand(
      'create_buffer',
      { dtype: 'f32', size_bytes: 12 },
      { buffer_id: bufferId }
    );
    core.handleCommand(
      'add_points',
      { scene_id: 's_1', positions: { buffer_id: bufferId, dtype: 'f32' }, size: 1 },
      { handle: 'p_1' }
    );
    expect(core.getObjectCount()).toBe(0);

    core.handleCommand('clear_scene', { scene_id: 's_1' });
    core.storeBufferData(bufferId, 0, new Float32Array([0, 0, 0]));

    expect(core.getObjectCount()).toBe(0);
  });

  it('clears pending renders when remove_object is called', () => {
    const bufferId = 'b_2';
    core.handleCommand(
      'create_buffer',
      { dtype: 'f32', size_bytes: 12 },
      { buffer_id: bufferId }
    );
    core.handleCommand(
      'add_points',
      { scene_id: 's_1', positions: { buffer_id: bufferId, dtype: 'f32' }, size: 1 },
      { handle: 'p_2' }
    );
    expect(core.getObjectCount()).toBe(0);

    core.handleCommand('remove_object', { handle: 'p_2' });
    core.storeBufferData(bufferId, 0, new Float32Array([0, 0, 0]));

    expect(core.getObjectCount()).toBe(0);
  });

  it('cancels pending load_mesh on remove_object', async () => {
    core.handleCommand(
      'load_mesh',
      { url: '/assets/mesh.dae', scene_id: 's_1' },
      { handle: 'm_1' }
    );
    core.handleCommand('remove_object', { handle: 'm_1' });

    expect(resolveLoad).not.toBeNull();
    if (resolveLoad) {
      resolveLoad(new THREE.Object3D());
    }

    await Promise.resolve();
    await Promise.resolve();

    expect(core.getObjectCount()).toBe(0);
  });

  it('disposes renderer and managers on dispose', () => {
    const sceneManager = core.getSceneManager();
    const renderer = sceneManager?.renderer as { dispose?: () => void } | undefined;
    expect(renderer).toBeDefined();

    core.dispose();

    expect(renderer?.dispose as any).toHaveBeenCalled();
  });

  it('emits view_destroyed only for the owning view', () => {
    const onEvent = vi.fn();
    const ownedCore = new FrameVizCore({ container, viewId: 'v_owner', onEvent });

    ownedCore.handleCommand('destroy_view', { view_id: 'v_other' });
    expect(onEvent).not.toHaveBeenCalled();

    ownedCore.handleCommand('destroy_view', { view_id: 'v_owner' });
    expect(onEvent).toHaveBeenCalledWith('view_destroyed', { view_id: 'v_owner' });

    ownedCore.dispose();
  });
});

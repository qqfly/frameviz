import { describe, it, expect, beforeEach, vi } from 'vitest';
import * as THREE from 'three';
import { GizmoManager } from '../GizmoManager';

// Mock CombinedTransformControls
const mockControls = {
  attach: vi.fn(),
  detach: vi.fn(),
  setMask: vi.fn(),
  dispose: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  size: 1,
  mask: 0x3F,
  scaleMode: 'world' as 'screen' | 'world',
  space: 'local' as 'world' | 'local',
  object: undefined as THREE.Object3D | undefined,
};

vi.mock('../controls/CombinedTransformControls.js', () => {
  return {
    CombinedTransformControls: vi.fn().mockImplementation(() => mockControls),
    GIZMO_MASK_ALL: 0x3F,
  };
});

// Mock OrbitControls
const mockOrbitControls = {
  enabled: true,
  update: vi.fn(),
  dispose: vi.fn(),
  target: new THREE.Vector3(),
};

vi.mock('three/examples/jsm/controls/OrbitControls.js', () => {
  return {
    OrbitControls: vi.fn().mockImplementation(() => mockOrbitControls),
  };
});

describe('GizmoManager', () => {
  let camera: THREE.PerspectiveCamera;
  let domElement: HTMLElement;
  let scene: THREE.Scene;
  let manager: GizmoManager;
  let sceneAddSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();

    // Reset mock state
    mockControls.size = 1;
    mockControls.mask = 0x3F;
    mockControls.scaleMode = 'world';
    mockControls.space = 'local';
    mockControls.object = undefined;
    mockOrbitControls.enabled = true;

    camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
    domElement = document.createElement('div');
    scene = new THREE.Scene();
    sceneAddSpy = vi.spyOn(scene, 'add');

    manager = new GizmoManager(camera, domElement, mockOrbitControls as any, scene);
  });

  describe('initialization', () => {
    it('should create CombinedTransformControls', () => {
      expect(manager.controls).toBeDefined();
    });

    it('should add controls to scene', () => {
      expect(sceneAddSpy).toHaveBeenCalledWith(mockControls);
    });

    it('should setup event listeners', () => {
      expect(mockControls.addEventListener).toHaveBeenCalledWith('mouseDown', expect.any(Function));
      expect(mockControls.addEventListener).toHaveBeenCalledWith('mouseUp', expect.any(Function));
      expect(mockControls.addEventListener).toHaveBeenCalledWith('change', expect.any(Function));
      expect(mockControls.addEventListener).toHaveBeenCalledWith('objectChange', expect.any(Function));
    });
  });

  describe('attach', () => {
    it('should attach to object with handle', () => {
      const mesh = new THREE.Mesh();

      manager.attach(mesh, 'test-handle');

      expect(mockControls.attach).toHaveBeenCalledWith(mesh);
      expect(manager.getAttachedHandle()).toBe('test-handle');
    });

    it('should attach with config', () => {
      const mesh = new THREE.Mesh();

      manager.attach(mesh, 'test-handle', { size: 2, mask: 0x07 });

      expect(mockControls.attach).toHaveBeenCalledWith(mesh);
      expect(mockControls.size).toBe(2);
      expect(mockControls.setMask).toHaveBeenCalledWith(0x07);
    });

    it('should attach with scale_mode config', () => {
      const mesh = new THREE.Mesh();

      manager.attach(mesh, 'test-handle', { scale_mode: 'screen' });

      expect(mockControls.scaleMode).toBe('screen');
    });
  });

  describe('detach', () => {
    it('should detach and clear handle', () => {
      const mesh = new THREE.Mesh();
      manager.attach(mesh, 'test-handle');

      manager.detach();

      expect(mockControls.detach).toHaveBeenCalled();
      expect(manager.getAttachedHandle()).toBeNull();
    });
  });

  describe('configure', () => {
    it('should configure size', () => {
      manager.configure({ size: 1.5 });

      expect(mockControls.size).toBe(1.5);
    });

    it('should configure mask', () => {
      manager.configure({ mask: 0x38 });

      expect(mockControls.setMask).toHaveBeenCalledWith(0x38);
    });

    it('should configure scale_mode', () => {
      manager.configure({ scale_mode: 'screen' });

      expect(mockControls.scaleMode).toBe('screen');
    });

    it('should configure multiple properties at once', () => {
      manager.configure({ size: 2.0, mask: 0x07, scale_mode: 'screen' });

      expect(mockControls.size).toBe(2.0);
      expect(mockControls.setMask).toHaveBeenCalledWith(0x07);
      expect(mockControls.scaleMode).toBe('screen');
    });

    it('should not change properties not specified in config', () => {
      mockControls.size = 1.5;
      mockControls.scaleMode = 'screen';

      manager.configure({ mask: 0x38 });

      expect(mockControls.size).toBe(1.5);
      expect(mockControls.scaleMode).toBe('screen');
      expect(mockControls.setMask).toHaveBeenCalledWith(0x38);
    });
  });

  describe('getAttachedHandle', () => {
    it('should return null when nothing is attached', () => {
      expect(manager.getAttachedHandle()).toBeNull();
    });

    it('should return handle when attached', () => {
      const mesh = new THREE.Mesh();
      manager.attach(mesh, 'my-handle');

      expect(manager.getAttachedHandle()).toBe('my-handle');
    });

    it('should return null after detach', () => {
      const mesh = new THREE.Mesh();
      manager.attach(mesh, 'my-handle');
      manager.detach();

      expect(manager.getAttachedHandle()).toBeNull();
    });
  });

  describe('transform callback', () => {
    it('should call callback on objectChange when attached', () => {
      const callback = vi.fn();
      manager.setTransformChangeCallback(callback);

      const mesh = new THREE.Mesh();
      mesh.position.set(1, 2, 3);
      mesh.quaternion.set(0, 0, 0, 1);
      mesh.scale.set(1, 1, 1);

      manager.attach(mesh, 'test-handle');
      mockControls.object = mesh;

      // Get the objectChange callback
      const objectChangeCallback = mockControls.addEventListener.mock.calls.find(
        (call: any[]) => call[0] === 'objectChange'
      )?.[1];

      if (objectChangeCallback) {
        objectChangeCallback();
      }

      expect(callback).toHaveBeenCalledWith('test-handle', {
        pos: [1, 2, 3],
        quat: [0, 0, 0, 1],
        scale: [1, 1, 1],
      });
    });

    it('should not call callback if not attached', () => {
      const callback = vi.fn();
      manager.setTransformChangeCallback(callback);

      const objectChangeCallback = mockControls.addEventListener.mock.calls.find(
        (call: any[]) => call[0] === 'objectChange'
      )?.[1];

      if (objectChangeCallback) {
        objectChangeCallback();
      }

      expect(callback).not.toHaveBeenCalled();
    });

    it('should not call callback if no object on controls', () => {
      const callback = vi.fn();
      manager.setTransformChangeCallback(callback);

      const mesh = new THREE.Mesh();
      manager.attach(mesh, 'test-handle');
      mockControls.object = undefined; // no object

      const objectChangeCallback = mockControls.addEventListener.mock.calls.find(
        (call: any[]) => call[0] === 'objectChange'
      )?.[1];

      if (objectChangeCallback) {
        objectChangeCallback();
      }

      expect(callback).not.toHaveBeenCalled();
    });
  });

  describe('mouseDown/mouseUp events', () => {
    it('should disable orbit controls on mouseDown', () => {
      const mouseDownCallback = mockControls.addEventListener.mock.calls.find(
        (call: any[]) => call[0] === 'mouseDown'
      )?.[1];

      if (mouseDownCallback) {
        mouseDownCallback();
      }

      expect(mockOrbitControls.enabled).toBe(false);
    });

    it('should enable orbit controls on mouseUp', () => {
      mockOrbitControls.enabled = false;

      const mouseUpCallback = mockControls.addEventListener.mock.calls.find(
        (call: any[]) => call[0] === 'mouseUp'
      )?.[1];

      if (mouseUpCallback) {
        mouseUpCallback();
      }

      expect(mockOrbitControls.enabled).toBe(true);
    });
  });

  describe('disposal', () => {
    it('should dispose controls', () => {
      manager.dispose();

      expect(mockControls.dispose).toHaveBeenCalled();
    });
  });
});

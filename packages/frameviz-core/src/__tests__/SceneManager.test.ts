import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as THREE from 'three';
import { SceneManager } from '../SceneManager';

// Mock WebGL Renderer to avoid WebGL context errors in jsdom
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

// Mock CSS2DRenderer since it's not available in jsdom
vi.mock('three/examples/jsm/renderers/CSS2DRenderer.js', () => {
  return {
    CSS2DRenderer: vi.fn().mockImplementation(() => ({
      setSize: vi.fn(),
      render: vi.fn(),
      domElement: document.createElement('div'),
    })),
  };
});

describe('SceneManager', () => {
  let container: HTMLElement;
  let sceneManager: SceneManager;

  beforeEach(() => {
    // Create a container element
    container = document.createElement('div');
    container.style.width = '800px';
    container.style.height = '600px';
    document.body.appendChild(container);

    // Create scene manager
    sceneManager = new SceneManager({ container });
  });

  afterEach(() => {
    if (sceneManager) {
      sceneManager.dispose();
    }
    if (container && container.parentNode) {
      document.body.removeChild(container);
    }
  });

  describe('initialization', () => {
    it('should create scene, camera, and renderers', () => {
      expect(sceneManager.scene).toBeInstanceOf(THREE.Scene);
      expect(sceneManager.camera).toBeInstanceOf(THREE.PerspectiveCamera);
      expect(sceneManager.renderer).toBeDefined();
      expect(sceneManager.labelRenderer).toBeDefined();
    });

    it('should set default background color', () => {
      expect(sceneManager.scene.background).toBeInstanceOf(THREE.Color);
      expect((sceneManager.scene.background as THREE.Color).getHex()).toBe(0xffffff);
    });

    it('should accept custom background color', () => {
      const customManager = new SceneManager({
        container,
        background: 0xff0000
      });
      expect((customManager.scene.background as THREE.Color).getHex()).toBe(0xff0000);
      customManager.dispose();
    });

    it('should set camera to Z-up coordinate system', () => {
      expect(sceneManager.camera.up.x).toBe(0);
      expect(sceneManager.camera.up.y).toBe(0);
      expect(sceneManager.camera.up.z).toBe(1);
    });

    it('should position camera at isometric view', () => {
      const pos = sceneManager.camera.position;
      expect(pos.x).toBeGreaterThan(0);
      expect(pos.y).toBeGreaterThan(0);
      expect(pos.z).toBeGreaterThan(0);
      // All coordinates should be equal for isometric view
      expect(pos.x).toBe(pos.y);
      expect(pos.y).toBe(pos.z);
    });

    it('should add default lighting to scene', () => {
      const lights = sceneManager.scene.children.filter(
        child => child instanceof THREE.Light
      );
      expect(lights.length).toBeGreaterThan(0);
    });

    it('should add grid and axes helpers', () => {
      const helpers = sceneManager.scene.children.filter(
        child =>
          child instanceof THREE.GridHelper ||
          (child.userData && child.userData.isViewAxesHelper === true)
      );
      expect(helpers.length).toBeGreaterThanOrEqual(2);
    });

    it('should not shrink default camera far plane below the initial range', () => {
      const initialFar = sceneManager.camera.far;

      sceneManager.updateClipPlanes(new THREE.Vector3(0, 0, 0));

      expect(sceneManager.camera.far).toBe(initialFar);
    });

    it('should keep explicit clip plane settings fixed', () => {
      const customManager = new SceneManager({
        container,
        cameraNear: 0.02,
        cameraFar: 5000,
      });

      customManager.camera.position.set(0.05, 0.05, 0.05);
      customManager.updateClipPlanes(new THREE.Vector3(0, 0, 0));

      expect(customManager.camera.near).toBe(0.02);
      expect(customManager.camera.far).toBe(5000);
      customManager.dispose();
    });
  });

  describe('object management', () => {
    it('should add object to scene', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial({ color: 0xff0000 })
      );

      sceneManager.addObject('test-cube', mesh);

      expect(sceneManager.hasObject('test-cube')).toBe(true);
      expect(sceneManager.getObject('test-cube')).toBe(mesh);
      expect(sceneManager.scene.children).toContain(mesh);
    });

    it('should remove object from scene', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial({ color: 0xff0000 })
      );

      sceneManager.addObject('test-cube', mesh);
      sceneManager.removeObject('test-cube');

      expect(sceneManager.hasObject('test-cube')).toBe(false);
      expect(sceneManager.getObject('test-cube')).toBeUndefined();
      expect(sceneManager.scene.children).not.toContain(mesh);
    });

    it('should replace object with same handle', () => {
      const mesh1 = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial({ color: 0xff0000 })
      );
      const mesh2 = new THREE.Mesh(
        new THREE.SphereGeometry(1),
        new THREE.MeshBasicMaterial({ color: 0x00ff00 })
      );

      sceneManager.addObject('test-obj', mesh1);
      sceneManager.addObject('test-obj', mesh2);

      expect(sceneManager.getObject('test-obj')).toBe(mesh2);
      expect(sceneManager.scene.children).not.toContain(mesh1);
      expect(sceneManager.scene.children).toContain(mesh2);
    });

    it('should return all object handles', () => {
      const mesh1 = new THREE.Mesh();
      const mesh2 = new THREE.Mesh();

      sceneManager.addObject('obj1', mesh1);
      sceneManager.addObject('obj2', mesh2);

      const handles = sceneManager.getObjectHandles();
      expect(handles).toContain('obj1');
      expect(handles).toContain('obj2');
      expect(handles).toHaveLength(2);
    });

    it('should get objects map', () => {
      const mesh = new THREE.Mesh();
      sceneManager.addObject('test', mesh);

      const objects = sceneManager.getObjects();
      expect(objects).toBeInstanceOf(Map);
      expect(objects.get('test')).toBe(mesh);
    });

    it('should clear all objects', () => {
      sceneManager.addObject('obj1', new THREE.Mesh());
      sceneManager.addObject('obj2', new THREE.Mesh());

      sceneManager.clearScene();

      expect(sceneManager.getObjectHandles()).toHaveLength(0);
    });
  });

  describe('buffer management', () => {
    it('should store and retrieve buffers', () => {
      const buffer = new ArrayBuffer(100);

      sceneManager.storeBuffer('test-buffer', buffer);

      expect(sceneManager.getBuffer('test-buffer')).toBe(buffer);
    });

    it('should return undefined for non-existent buffer', () => {
      expect(sceneManager.getBuffer('non-existent')).toBeUndefined();
    });

    it('should clear all buffers', () => {
      sceneManager.storeBuffer('buf1', new ArrayBuffer(50));
      sceneManager.storeBuffer('buf2', new ArrayBuffer(100));

      sceneManager.clearBuffers();

      expect(sceneManager.getBuffer('buf1')).toBeUndefined();
      expect(sceneManager.getBuffer('buf2')).toBeUndefined();
    });
  });

  describe('rendering', () => {
    it('should render without errors', () => {
      expect(() => sceneManager.render()).not.toThrow();
    });
  });

  describe('resize', () => {
    it('should call resize without errors', () => {
      // Note: jsdom doesn't properly update clientWidth/clientHeight
      // so we just verify resize doesn't throw
      expect(() => sceneManager.resize()).not.toThrow();
    });
  });

  describe('disposal', () => {
    it('should clean up all resources', () => {
      // Create a new container for this test to avoid interference with afterEach
      const testContainer = document.createElement('div');
      testContainer.style.width = '800px';
      testContainer.style.height = '600px';
      document.body.appendChild(testContainer);

      const testManager = new SceneManager({ container: testContainer });
      testManager.addObject('test', new THREE.Mesh());
      testManager.storeBuffer('buf', new ArrayBuffer(100));

      testManager.dispose();

      expect(testManager.getObjectHandles()).toHaveLength(0);
      expect(testManager.getBuffer('buf')).toBeUndefined();
      // Verify DOM elements are removed (dispose removes them)
      expect(testContainer.childNodes.length).toBe(0);

      // Clean up test container
      document.body.removeChild(testContainer);
    });
  });
});

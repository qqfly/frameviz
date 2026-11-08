import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as THREE from 'three';
import { CameraController, VIEW_PRESETS } from '../CameraController';

// Mock OrbitControls
vi.mock('three/examples/jsm/controls/OrbitControls.js', () => {
  return {
    OrbitControls: vi.fn().mockImplementation((camera, domElement) => ({
      target: new THREE.Vector3(0, 0, 0),
      enableDamping: false,  // P1-1: Changed to false for precise control
      enableZoom: false,     // P1-1: Custom zoom handler
      enableRotate: true,
      enablePan: true,
      update: vi.fn(),
      dispose: vi.fn(),
    })),
  };
});

describe('CameraController', () => {
  let camera: THREE.PerspectiveCamera;
  let domElement: HTMLElement;
  let controller: CameraController;

  beforeEach(() => {
    camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
    camera.position.set(5, 5, 5);
    camera.up.set(0, 0, 1);

    domElement = document.createElement('div');
    domElement.style.width = '800px';
    domElement.style.height = '600px';
    document.body.appendChild(domElement);

    controller = new CameraController({ camera, domElement });
  });

  afterEach(() => {
    controller.dispose();
    document.body.removeChild(domElement);
  });

  it('includes instance transforms and parent transforms in finite bounds', () => {
    const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(2,2,2),new THREE.MeshBasicMaterial(),2);
    mesh.setMatrixAt(0,new THREE.Matrix4().makeTranslation(1000,0,0));
    mesh.setMatrixAt(1,new THREE.Matrix4().makeTranslation(-1000,0,0));
    const group=new THREE.Group();group.position.set(10,20,30);group.add(mesh);
    const bounds=(controller as any).computeFiniteBounds([group]);
    expect(bounds.min.toArray()).toEqual([-991,19,29]);
    expect(bounds.max.toArray()).toEqual([1011,21,31]);
  });

  describe('initialization', () => {
    it('should create OrbitControls', () => {
      expect(controller.controls).toBeDefined();
      expect(controller.controls.target).toBeInstanceOf(THREE.Vector3);
    });

    it('should set enableDamping to false for precise control', () => {
      expect(controller.controls.enableDamping).toBe(false);  // P1-1: Changed default
    });
  });

  describe('VIEW_PRESETS', () => {
    it('should have all required view presets', () => {
      expect(VIEW_PRESETS.home).toBeDefined();
      expect(VIEW_PRESETS.front).toBeDefined();
      expect(VIEW_PRESETS.back).toBeDefined();
      expect(VIEW_PRESETS.left).toBeDefined();
      expect(VIEW_PRESETS.right).toBeDefined();
      expect(VIEW_PRESETS.top).toBeDefined();
      expect(VIEW_PRESETS.bottom).toBeDefined();
    });

    it('should have correct home view preset', () => {
      expect(VIEW_PRESETS.home.pos).toEqual([1, 1, 1]);
      expect(VIEW_PRESETS.home.target).toEqual([0, 0, 0]);
    });

    it('should have correct front view preset', () => {
      expect(VIEW_PRESETS.front.pos).toEqual([1, 0, 0]);
    });

    it('should have correct top view preset', () => {
      expect(VIEW_PRESETS.top.pos).toEqual([0, 0, 1]);
    });
  });

  describe('setView', () => {
    it('should set camera to front view', (done) => {
      controller.setView('front');

      // Wait for animation to complete
      setTimeout(() => {
        // Camera should be on +X axis looking at origin
        expect(camera.position.x).toBeGreaterThan(0);
        expect(camera.position.y).toBeCloseTo(0, 0);
        expect(camera.position.z).toBeCloseTo(0, 0);
        done();
      }, 350);
    });

    it('should set camera to top view', (done) => {
      controller.setView('top');

      setTimeout(() => {
        // Camera should be on +Z axis looking at origin
        expect(camera.position.z).toBeGreaterThan(0);
        expect(camera.position.x).toBeCloseTo(0, 0);
        expect(camera.position.y).toBeCloseTo(0, 0);
        done();
      }, 350);
    });

    it('should handle invalid view name gracefully', () => {
      const originalPos = camera.position.clone();
      controller.setView('invalid' as any);

      // Position should not change for invalid view
      expect(camera.position.equals(originalPos)).toBe(true);
    });

    it('should fit all objects when fitAll is true', (done) => {
      const objects = new Map<string, THREE.Object3D>();
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(10, 10, 10),
        new THREE.MeshBasicMaterial()
      );
      mesh.position.set(0, 0, 0);
      objects.set('test', mesh);

      controller.setView('front', true, objects);

      setTimeout(() => {
        // Camera should be farther away to fit the large box
        const distance = camera.position.length();
        expect(distance).toBeGreaterThan(10);
        done();
      }, 350);
    });

    it('should ignore NaN positions when fitting', (done) => {
      const objects = new Map<string, THREE.Object3D>();
      const geometry = new THREE.BufferGeometry();
      const positions = new Float32Array([Number.NaN, Number.NaN, Number.NaN, 1, 1, 1]);
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
      const points = new THREE.Points(geometry, new THREE.PointsMaterial());
      objects.set('points', points);

      controller.setView('home', true, objects);

      setTimeout(() => {
        expect(Number.isFinite(camera.position.x)).toBe(true);
        expect(Number.isFinite(camera.position.y)).toBe(true);
        expect(Number.isFinite(camera.position.z)).toBe(true);
        done();
      }, 350);
    });
  });

  describe('resetView', () => {
    it('should reset to home view', (done) => {
      // First move camera somewhere else
      camera.position.set(1, 0, 0);

      controller.resetView();

      setTimeout(() => {
        // Should be back to isometric view (equal components)
        expect(camera.position.x).toBeGreaterThan(0);
        expect(camera.position.y).toBeGreaterThan(0);
        expect(camera.position.z).toBeGreaterThan(0);
        done();
      }, 350);
    });
  });

  describe('zoom behavior', () => {
    it('should be disabled by default for performance', () => {
      expect(controller.isZoomToCursorEnabled()).toBe(false);  // P1-1: Changed default
    });

    it('should allow disabling zoom-to-cursor', () => {
      controller.setZoomToCursor(false);
      expect(controller.isZoomToCursorEnabled()).toBe(false);
    });

    it('should allow enabling zoom-to-cursor', () => {
      controller.setZoomToCursor(false);
      controller.setZoomToCursor(true);
      expect(controller.isZoomToCursorEnabled()).toBe(true);
    });
  });

  describe('handleZoom', () => {
    it('should zoom in on negative deltaY', () => {
      controller.setMousePreset('trackpad');
      const originalDistance = camera.position.length();
      const event = new WheelEvent('wheel', { deltaY: -100 });

      controller.handleZoom(event);

      const newDistance = camera.position.length();
      expect(newDistance).toBeLessThan(originalDistance);
    });

    it('should zoom out on positive deltaY', () => {
      controller.setMousePreset('trackpad');
      const originalDistance = camera.position.length();
      const event = new WheelEvent('wheel', { deltaY: 100 });

      controller.handleZoom(event);

      const newDistance = camera.position.length();
      expect(newDistance).toBeGreaterThan(originalDistance);
    });

    it('should invert wheel zoom in cad preset', () => {
      controller.setMousePreset('cad');
      const originalDistance = camera.position.length();
      const event = new WheelEvent('wheel', { deltaY: -100 });

      controller.handleZoom(event);

      const newDistance = camera.position.length();
      expect(newDistance).toBeGreaterThan(originalDistance);
    });

    it('uses a distance-scaled step when zooming in near the target', () => {
      controller.setMousePreset('trackpad');
      camera.position.set(0.09, 0, 0);
      camera.lookAt(0, 0, 0);
      controller.controls.target.set(0, 0, 0);
      const originalPosition = camera.position.clone();
      const originalTarget = controller.controls.target.clone();

      controller.handleZoom(new WheelEvent('wheel', { deltaY: -100 }));

      expect(camera.position.distanceTo(originalPosition)).toBeLessThan(0.05);
      expect(controller.controls.target.distanceTo(originalTarget)).toBeLessThan(0.05);
    });

    it('uses a distance-scaled step when zooming out near the target', () => {
      controller.setMousePreset('trackpad');
      camera.position.set(0.09, 0, 0);
      camera.lookAt(0, 0, 0);
      controller.controls.target.set(0, 0, 0);
      const originalPosition = camera.position.clone();

      controller.handleZoom(new WheelEvent('wheel', { deltaY: 100 }));

      expect(camera.position.distanceTo(originalPosition)).toBeLessThan(0.05);
    });
  });

  describe('fitToObjects', () => {
    it('should fit camera to single object', (done) => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(10, 10, 10),
        new THREE.MeshBasicMaterial()
      );
      mesh.position.set(0, 0, 0);

      controller.fitToObjects([mesh]);

      setTimeout(() => {
        // Camera should be positioned to see the box
        const distance = camera.position.length();
        expect(distance).toBeGreaterThan(10);

        // Target should be at box center
        expect(controller.controls.target.x).toBeCloseTo(0, 0);
        expect(controller.controls.target.y).toBeCloseTo(0, 0);
        expect(controller.controls.target.z).toBeCloseTo(0, 0);
        done();
      }, 350);
    });

    it('should fit camera to multiple objects', (done) => {
      const mesh1 = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      mesh1.position.set(-5, 0, 0);

      const mesh2 = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      mesh2.position.set(5, 0, 0);

      controller.fitToObjects([mesh1, mesh2]);

      setTimeout(() => {
        // Camera should be positioned to see both boxes
        const distance = camera.position.length();
        expect(distance).toBeGreaterThan(10);
        done();
      }, 350);
    });

    it('should handle empty object list', () => {
      const originalPos = camera.position.clone();
      controller.fitToObjects([]);

      // Position should not change
      expect(camera.position.equals(originalPos)).toBe(true);
    });
  });

  describe('update', () => {
    it('should call controls.update', () => {
      const updateSpy = vi.spyOn(controller.controls, 'update');
      controller.update();
      expect(updateSpy).toHaveBeenCalled();
    });
  });

  describe('disposal', () => {
    it('should dispose controls', () => {
      const disposeSpy = vi.spyOn(controller.controls, 'dispose');
      controller.dispose();
      expect(disposeSpy).toHaveBeenCalled();
    });

    it('should remove wheel event listener', () => {
      const removeListenerSpy = vi.spyOn(domElement, 'removeEventListener');
      controller.dispose();
      expect(removeListenerSpy).toHaveBeenCalledWith('wheel', expect.any(Function));
    });
  });
});

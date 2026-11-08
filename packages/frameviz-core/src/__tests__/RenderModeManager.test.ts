import { describe, it, expect, beforeEach } from 'vitest';
import * as THREE from 'three';
import { RenderModeManager, RENDER_MODES } from '../RenderModeManager';

describe('RenderModeManager', () => {
  let manager: RenderModeManager;
  let objects: Map<string, THREE.Object3D>;

  beforeEach(() => {
    manager = new RenderModeManager();
    objects = new Map();
  });

  describe('initialization', () => {
    it('should start with solid mode', () => {
      expect(manager.getCurrentMode()).toBe('solid');
    });
  });

  describe('RENDER_MODES constant', () => {
    it('should have correct modes in order', () => {
      expect(RENDER_MODES).toEqual(['solid', 'wireframe', 'points']);
    });
  });

  describe('setRenderMode', () => {
    it('should set solid mode on mesh', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      objects.set('mesh1', mesh);

      manager.setRenderMode('solid', objects);

      expect(mesh.visible).toBe(true);
      expect((mesh.material as THREE.Material & { wireframe: boolean }).wireframe).toBe(false);
    });

    it('should set wireframe mode on mesh', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      objects.set('mesh1', mesh);

      manager.setRenderMode('wireframe', objects);

      expect(mesh.visible).toBe(true);
      expect((mesh.material as THREE.Material & { wireframe: boolean }).wireframe).toBe(true);
    });

    it('should set points mode on mesh', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      const group = new THREE.Group();
      group.add(mesh);
      objects.set('group1', group);

      manager.setRenderMode('points', objects);

      expect(mesh.visible).toBe(false);
      // Points helper should be created and visible
      expect(group.children.length).toBeGreaterThan(1);
    });

    it('should handle array of materials', () => {
      const materials = [
        new THREE.MeshBasicMaterial(),
        new THREE.MeshBasicMaterial(),
      ];
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        materials
      );
      objects.set('mesh1', mesh);

      manager.setRenderMode('wireframe', objects);

      materials.forEach((mat) => {
        expect((mat as any).wireframe).toBe(true);
      });
    });

    it('should traverse groups and nested objects', () => {
      const mesh1 = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      const mesh2 = new THREE.Mesh(
        new THREE.SphereGeometry(1),
        new THREE.MeshBasicMaterial()
      );
      const group = new THREE.Group();
      group.add(mesh1);
      group.add(mesh2);
      objects.set('group1', group);

      manager.setRenderMode('wireframe', objects);

      expect((mesh1.material as THREE.Material & { wireframe: boolean }).wireframe).toBe(true);
      expect((mesh2.material as THREE.Material & { wireframe: boolean }).wireframe).toBe(true);
    });

    it('should keep points objects always visible', () => {
      const points = new THREE.Points(
        new THREE.BufferGeometry(),
        new THREE.PointsMaterial()
      );
      objects.set('points1', points);

      manager.setRenderMode('wireframe', objects);

      expect(points.visible).toBe(true);
    });

    it('should respect user visibility when switching modes', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      const group = new THREE.Group();
      group.add(mesh);
      group.userData.userVisible = false;
      objects.set('group1', group);

      manager.setRenderMode('wireframe', objects);

      expect(mesh.visible).toBe(false);

      manager.setRenderMode('points', objects);
      expect(mesh.visible).toBe(false);
    });

    it('should default to visible for objects without userVisible flag', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      objects.set('mesh1', mesh);

      manager.setRenderMode('points', objects);
      manager.setRenderMode('wireframe', objects);

      expect(mesh.visible).toBe(true);
    });

    it('should ignore invalid render mode', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      objects.set('mesh1', mesh);

      const previousMode = manager.getCurrentMode();
      manager.setRenderMode('invalid' as any, objects);

      expect(manager.getCurrentMode()).toBe(previousMode);
    });

    it('should create points helper only once', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      const group = new THREE.Group();
      group.add(mesh);
      objects.set('group1', group);

      manager.setRenderMode('points', objects);
      const childCount1 = group.children.length;

      manager.setRenderMode('solid', objects);
      manager.setRenderMode('points', objects);
      const childCount2 = group.children.length;

      // Should have same number of children (points helper reused)
      expect(childCount2).toBe(childCount1);
    });

    it('should update current mode', () => {
      manager.setRenderMode('wireframe', objects);
      expect(manager.getCurrentMode()).toBe('wireframe');

      manager.setRenderMode('points', objects);
      expect(manager.getCurrentMode()).toBe('points');
    });
  });

  describe('cycleRenderMode', () => {
    it('should cycle from solid to wireframe', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      objects.set('mesh1', mesh);

      const newMode = manager.cycleRenderMode(objects);

      expect(newMode).toBe('wireframe');
      expect(manager.getCurrentMode()).toBe('wireframe');
    });

    it('should cycle from wireframe to points', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      const group = new THREE.Group();
      group.add(mesh);
      objects.set('group1', group);

      manager.setRenderMode('wireframe', objects);
      const newMode = manager.cycleRenderMode(objects);

      expect(newMode).toBe('points');
      expect(manager.getCurrentMode()).toBe('points');
    });

    it('should cycle from points back to solid', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      objects.set('mesh1', mesh);

      manager.setRenderMode('points', objects);
      const newMode = manager.cycleRenderMode(objects);

      expect(newMode).toBe('solid');
      expect(manager.getCurrentMode()).toBe('solid');
    });

    it('should complete full cycle', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      objects.set('mesh1', mesh);

      expect(manager.getCurrentMode()).toBe('solid');
      manager.cycleRenderMode(objects); // -> wireframe
      expect(manager.getCurrentMode()).toBe('wireframe');
      manager.cycleRenderMode(objects); // -> points
      expect(manager.getCurrentMode()).toBe('points');
      manager.cycleRenderMode(objects); // -> solid
      expect(manager.getCurrentMode()).toBe('solid');
    });
  });

  describe('cleanupHelpers', () => {
    it('should remove helpers for deleted objects', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      const group = new THREE.Group();
      group.add(mesh);
      objects.set('group1', group);

      // Create points helper
      manager.setRenderMode('points', objects);
      expect(group.children.length).toBeGreaterThan(1);

      // Remove object and cleanup
      objects.clear();
      manager.cleanupHelpers(objects);

      // Helper should be removed from group
      expect(group.children.length).toBe(1); // Only original mesh
    });

    it('should keep helpers for existing objects', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      const group = new THREE.Group();
      group.add(mesh);
      objects.set('group1', group);

      manager.setRenderMode('points', objects);
      const childCount1 = group.children.length;

      manager.cleanupHelpers(objects);
      const childCount2 = group.children.length;

      expect(childCount2).toBe(childCount1);
    });
  });

  describe('disposal', () => {
    it('should clean up all resources', () => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial()
      );
      const group = new THREE.Group();
      group.add(mesh);
      objects.set('group1', group);

      manager.setRenderMode('points', objects);
      manager.dispose();

      // All helpers should be removed
      expect(group.children.length).toBe(1); // Only original mesh
    });
  });
});

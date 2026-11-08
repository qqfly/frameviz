import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import { GeometryFactory } from '../GeometryFactory';

describe('GeometryFactory', () => {
  let factory: GeometryFactory;

  beforeEach(() => {
    factory = new GeometryFactory();
  });

  describe('createMaterial', () => {
    it('should create material with RGB color', () => {
      const material = factory.createMaterial([1.0, 0.0, 0.0]);

      expect(material).toBeInstanceOf(THREE.MeshStandardMaterial);
      expect((material as THREE.MeshStandardMaterial).color.r).toBe(1.0);
      expect((material as THREE.MeshStandardMaterial).color.g).toBe(0.0);
      expect((material as THREE.MeshStandardMaterial).color.b).toBe(0.0);
      expect((material as THREE.MeshStandardMaterial).opacity).toBe(1.0);
      expect((material as THREE.MeshStandardMaterial).transparent).toBe(false);
    });

    it('should create material with RGBA color', () => {
      const material = factory.createMaterial([0.5, 0.5, 0.5, 0.5]);

      expect((material as THREE.MeshStandardMaterial).opacity).toBe(0.5);
      expect((material as THREE.MeshStandardMaterial).transparent).toBe(true);
      expect((material as THREE.MeshStandardMaterial).depthWrite).toBe(false);
    });

    it('should default to flat shading', () => {
      const material = factory.createMaterial([1, 1, 1]);

      expect((material as THREE.MeshStandardMaterial).flatShading).toBe(true);
    });

    it('should support doubleSide option', () => {
      const material = factory.createMaterial([1, 1, 1], { doubleSide: true });

      expect((material as THREE.MeshStandardMaterial).side).toBe(THREE.DoubleSide);
    });
  });

  describe('createPrimitive', () => {
    it('should create box primitive', () => {
      const obj = factory.createPrimitive('box', { size: [2, 3, 4] }, [1, 0, 0]);

      expect(obj).toBeInstanceOf(THREE.Mesh);
      const mesh = obj as THREE.Mesh;
      expect(mesh.geometry).toBeInstanceOf(THREE.BoxGeometry);

      const box = new THREE.Box3().setFromObject(mesh);
      expect(box.max.x - box.min.x).toBeCloseTo(2, 1);
      expect(box.max.y - box.min.y).toBeCloseTo(3, 1);
      expect(box.max.z - box.min.z).toBeCloseTo(4, 1);
    });

    it('should create sphere primitive', () => {
      const obj = factory.createPrimitive('sphere', { radius: 2 }, [0, 1, 0]);

      expect(obj).toBeInstanceOf(THREE.Mesh);
      const mesh = obj as THREE.Mesh;
      expect(mesh.geometry).toBeInstanceOf(THREE.SphereGeometry);
    });

    it('should create cylinder primitive', () => {
      const obj = factory.createPrimitive('cylinder', { radius: 1, height: 3 }, [0, 0, 1]);

      expect(obj).toBeInstanceOf(THREE.Mesh);
      const mesh = obj as THREE.Mesh;
      expect(mesh.geometry).toBeInstanceOf(THREE.CylinderGeometry);

      const box = new THREE.Box3().setFromObject(mesh);
      expect(box.max.x - box.min.x).toBeCloseTo(2, 1);
      expect(box.max.y - box.min.y).toBeCloseTo(2, 1);
      expect(box.max.z - box.min.z).toBeCloseTo(3, 1);
    });

    it('should create cone primitive', () => {
      const obj = factory.createPrimitive('cone', { radius: 1, height: 2 }, [1, 1, 0]);

      expect(obj).toBeInstanceOf(THREE.Mesh);
      const mesh = obj as THREE.Mesh;
      expect(mesh.geometry).toBeInstanceOf(THREE.ConeGeometry);
    });

    it('should create plane primitive', () => {
      const obj = factory.createPrimitive('plane', { width: 2, height: 3 }, [1, 0, 1]);

      expect(obj).toBeInstanceOf(THREE.Mesh);
      const mesh = obj as THREE.Mesh;
      expect(mesh.geometry).toBeInstanceOf(THREE.PlaneGeometry);
    });

    it('should create arrow primitive', () => {
      const obj = factory.createPrimitive('arrow', { length: 2 }, [1, 1, 1]);

      expect(obj).toBeInstanceOf(THREE.Group);
      expect(obj.children.length).toBeGreaterThan(0);
    });

    it('should create arrow with start and end points', () => {
      const obj = factory.createPrimitive(
        'arrow',
        {
          start: [0, 0, 0],
          end: [1, 1, 1],
        },
        [1, 0, 0]
      );

      expect(obj).toBeInstanceOf(THREE.Group);
      expect(obj.position.x).toBe(0);
      expect(obj.position.y).toBe(0);
      expect(obj.position.z).toBe(0);
    });

    it('should create axes primitive', () => {
      const obj = factory.createPrimitive('axes', { length: 1 }, [1, 1, 1]);

      expect(obj).toBeInstanceOf(THREE.Group);
      const group = obj as THREE.Group;
      // Should have 3 arrows (X, Y, Z)
      expect(group.children.length).toBe(3);
    });

    it('should fallback to box for unknown type', () => {
      const obj = factory.createPrimitive('unknown' as any, {}, [1, 1, 1]);

      expect(obj).toBeInstanceOf(THREE.Mesh);
      const mesh = obj as THREE.Mesh;
      expect(mesh.geometry).toBeInstanceOf(THREE.BoxGeometry);
    });
  });

  describe('applyPose', () => {
    it('should apply position', () => {
      const mesh = new THREE.Mesh();
      factory.applyPose(mesh, { pos: [1, 2, 3] });

      expect(mesh.position.x).toBe(1);
      expect(mesh.position.y).toBe(2);
      expect(mesh.position.z).toBe(3);
    });

    it('should apply quaternion', () => {
      const mesh = new THREE.Mesh();
      factory.applyPose(mesh, { quat: [0, 0, 0, 1] });

      expect(mesh.quaternion.x).toBe(0);
      expect(mesh.quaternion.y).toBe(0);
      expect(mesh.quaternion.z).toBe(0);
      expect(mesh.quaternion.w).toBe(1);
    });

    it('should apply scale', () => {
      const mesh = new THREE.Mesh();
      factory.applyPose(mesh, { scale: [2, 3, 4] });

      expect(mesh.scale.x).toBe(2);
      expect(mesh.scale.y).toBe(3);
      expect(mesh.scale.z).toBe(4);
    });

    it('should apply all pose components', () => {
      const mesh = new THREE.Mesh();
      factory.applyPose(mesh, {
        pos: [1, 2, 3],
        quat: [0, 0, 0.707, 0.707],
        scale: [2, 2, 2],
      });

      expect(mesh.position.x).toBe(1);
      expect(mesh.quaternion.z).toBeCloseTo(0.707, 2);
      expect(mesh.scale.x).toBe(2);
    });

    it('should handle null/undefined pose', () => {
      const mesh = new THREE.Mesh();
      const originalPos = mesh.position.clone();

      factory.applyPose(mesh, null as any);

      expect(mesh.position.equals(originalPos)).toBe(true);
    });
  });

  describe('createPoints', () => {
    it('should create points without colors', () => {
      const positions = new Float32Array([0, 0, 0, 1, 1, 1, 2, 2, 2]);
      const points = factory.createPoints(positions);

      expect(points).toBeInstanceOf(THREE.Points);
      expect(points.geometry.attributes.position.count).toBe(3);
      expect(points.geometry.attributes.color).toBeUndefined();
    });

    it('should create points with colors', () => {
      const positions = new Float32Array([0, 0, 0, 1, 1, 1]);
      const colors = new Uint8Array([255, 0, 0, 0, 255, 0]);

      const points = factory.createPoints(positions, colors);

      expect(points.geometry.attributes.color).toBeDefined();
      const colorAttr = points.geometry.attributes.color as THREE.BufferAttribute;
      expect(colorAttr.getX(0)).toBeCloseTo(1.0, 2); // 255/255
      expect(colorAttr.getY(0)).toBeCloseTo(0.0, 2);
      expect(colorAttr.getZ(0)).toBeCloseTo(0.0, 2);
    });

    it('should normalize uint8 colors to 0-1 range', () => {
      const positions = new Float32Array([0, 0, 0]);
      const colors = new Uint8Array([128, 64, 192]);

      const points = factory.createPoints(positions, colors);

      const colorAttr = points.geometry.attributes.color as THREE.BufferAttribute;
      expect(colorAttr.getX(0)).toBeCloseTo(128 / 255, 2);
      expect(colorAttr.getY(0)).toBeCloseTo(64 / 255, 2);
      expect(colorAttr.getZ(0)).toBeCloseTo(192 / 255, 2);
    });

    it('should accept custom point size', () => {
      const positions = new Float32Array([0, 0, 0]);
      const points = factory.createPoints(positions, undefined, 5);

      expect((points.material as THREE.PointsMaterial).size).toBe(5);
    });
  });

  describe('createLines', () => {
    it('should create lines with color', () => {
      const positions = new Float32Array([0, 0, 0, 1, 1, 1, 2, 2, 2]);
      const line = factory.createLines(positions, [1, 0, 0]);

      expect(line).toBeInstanceOf(THREE.Line);
      expect(line.geometry.attributes.position.count).toBe(3);

      const material = line.material as THREE.LineBasicMaterial;
      expect(material.color.r).toBe(1);
      expect(material.color.g).toBe(0);
      expect(material.color.b).toBe(0);
    });

    it('should accept line width parameter', () => {
      const positions = new Float32Array([0, 0, 0, 1, 1, 1]);
      const line = factory.createLines(positions, [1, 1, 1], 3);

      const material = line.material as THREE.LineBasicMaterial;
      expect(material.linewidth).toBe(3);
    });
  });

  describe('createMesh', () => {
    it('should create mesh with uniform color', () => {
      const vertices = new Float32Array([
        0, 0, 0,
        1, 0, 0,
        0, 1, 0,
      ]);
      const faces = new Uint32Array([0, 1, 2]);
      const meshColor: [number, number, number] = [1, 0, 0];

      const mesh = factory.createMesh(vertices, faces, undefined, undefined, meshColor);

      expect(mesh).toBeInstanceOf(THREE.Mesh);
      expect(mesh.geometry.attributes.position).toBeDefined();

      const material = mesh.material as THREE.MeshStandardMaterial;
      expect(material.color.r).toBe(1);
      expect(material.color.g).toBe(0);
      expect(material.color.b).toBe(0);
    });

    it('should create mesh with per-vertex colors', () => {
      const vertices = new Float32Array([
        0, 0, 0,
        1, 0, 0,
        0, 1, 0,
      ]);
      const faces = new Uint32Array([0, 1, 2]);
      const colors = new Uint8Array([
        255, 0, 0,   // Red
        0, 255, 0,   // Green
        0, 0, 255,   // Blue
      ]);

      const mesh = factory.createMesh(vertices, faces, undefined, colors);

      expect(mesh.geometry.attributes.color).toBeDefined();
      const material = mesh.material as THREE.MeshStandardMaterial;
      expect(material.vertexColors).toBe(true);
    });

    it('should create mesh with per-face colors', () => {
      const vertices = new Float32Array([
        0, 0, 0,
        1, 0, 0,
        1, 1, 0,
        0, 1, 0,
      ]);
      const faces = new Uint32Array([0, 1, 2, 0, 2, 3]);
      const colors = new Uint8Array([
        255, 0, 0,   // Face 0: red
        0, 255, 0,   // Face 1: green
      ]);

      const mesh = factory.createMesh(vertices, faces, undefined, colors);

      const colorAttr = mesh.geometry.attributes.color as THREE.BufferAttribute;
      expect(colorAttr).toBeDefined();
      expect(colorAttr.count).toBe(6);
      expect(colorAttr.getX(0)).toBeCloseTo(1.0, 2);
      expect(colorAttr.getY(0)).toBeCloseTo(0.0, 2);
      expect(colorAttr.getZ(0)).toBeCloseTo(0.0, 2);
      expect(colorAttr.getX(3)).toBeCloseTo(0.0, 2);
      expect(colorAttr.getY(3)).toBeCloseTo(1.0, 2);
      expect(colorAttr.getZ(3)).toBeCloseTo(0.0, 2);
    });

    it('should default to gray color when no color provided', () => {
      const vertices = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
      const faces = new Uint32Array([0, 1, 2]);

      const mesh = factory.createMesh(vertices, faces);

      const material = mesh.material as THREE.MeshStandardMaterial;
      expect(material.color.r).toBe(0.5);
      expect(material.color.g).toBe(0.5);
      expect(material.color.b).toBe(0.5);
    });

    it('should create mesh with wireframe overlay', () => {
      const vertices = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
      const faces = new Uint32Array([0, 1, 2]);

      const mesh = factory.createMesh(vertices, faces);

      // By default, wireframe should NOT be added (wireframe=false)
      const wireframe = mesh.children.find(
        child => child.userData.isWireframe === true
      );
      expect(wireframe).toBeUndefined();

      // When wireframe=true, it should be added
      const meshWithWireframe = factory.createMesh(vertices, faces, undefined, undefined, undefined, undefined, true);
      const wireframeChild = meshWithWireframe.children.find(
        child => child.userData.isWireframe === true
      );
      expect(wireframeChild).toBeDefined();
      expect(wireframeChild).toBeInstanceOf(THREE.LineSegments);
    });

    it('should handle transparent mesh color', () => {
      const vertices = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
      const faces = new Uint32Array([0, 1, 2]);
      const meshColor: [number, number, number, number] = [1, 0, 0, 0.5];

      const mesh = factory.createMesh(vertices, faces, undefined, undefined, meshColor);

      const material = mesh.material as THREE.MeshStandardMaterial;
      expect(material.transparent).toBe(true);
      expect(material.opacity).toBe(0.5);
    });

    it('should use DoubleSide for all meshes', () => {
      const vertices = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
      const faces = new Uint32Array([0, 1, 2]);

      const mesh = factory.createMesh(vertices, faces);

      const material = mesh.material as THREE.MeshStandardMaterial;
      expect(material.side).toBe(THREE.DoubleSide);
    });

    it('should compute vertex normals', () => {
      const vertices = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
      const faces = new Uint32Array([0, 1, 2]);

      const mesh = factory.createMesh(vertices, faces);

      expect(mesh.geometry.attributes.normal).toBeDefined();
    });

    it('should support smooth shading when enabled', () => {
      const vertices = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
      const faces = new Uint32Array([0, 1, 2]);

      const mesh = factory.createMesh(
        vertices,
        faces,
        undefined,
        undefined,
        [0.2, 0.4, 0.6],
        undefined,
        false,
        true
      );

      const material = mesh.material as THREE.MeshStandardMaterial;
      expect(material.flatShading).toBe(false);
    });

    it('should default to smooth shading', () => {
      const vertices = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
      const faces = new Uint32Array([0, 1, 2]);

      const mesh = factory.createMesh(vertices, faces);

      const material = mesh.material as THREE.MeshStandardMaterial;
      expect(material.flatShading).toBe(false);
    });

    it('should keep indexed topology for smooth-shaded vertex colors', () => {
      const vertices = new Float32Array([
        0, 0, 0,
        1, 0, 0,
        1, 1, 0,
        0, 1, 0,
      ]);
      const faces = new Uint32Array([0, 1, 2, 0, 2, 3]);
      const colors = new Uint8Array([
        255, 0, 0,
        0, 255, 0,
        0, 0, 255,
        255, 255, 0,
      ]);

      const mesh = factory.createMesh(
        vertices,
        faces,
        undefined,
        colors,
        undefined,
        undefined,
        false,
        true
      );

      expect(mesh.geometry.index).toBeDefined();
      expect(mesh.geometry.attributes.position.count).toBe(4);
    });

    it('should preserve custom normals when smooth shading is enabled', () => {
      const vertices = new Float32Array([
        0, 0, 0,
        1, 0, 0,
        0, 1, 0,
      ]);
      const faces = new Uint32Array([0, 1, 2]);
      const normals = new Float32Array([
        0, 0, 1,
        0, 0, 1,
        0, 0, 1,
      ]);
      const colors = new Uint8Array([
        255, 0, 0,
        0, 255, 0,
        0, 0, 255,
      ]);

      const mesh = factory.createMesh(
        vertices,
        faces,
        normals,
        colors,
        undefined,
        undefined,
        false,
        true
      );

      const normalAttr = mesh.geometry.attributes.normal as THREE.BufferAttribute;
      expect(Array.from(normalAttr.array as Float32Array)).toEqual(Array.from(normals));
    });
  });
});

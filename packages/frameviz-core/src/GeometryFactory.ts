import * as THREE from 'three';

export type Color3 = [number, number, number];
export type Color4 = [number, number, number, number];
export type ColorArray = Color3 | Color4;

export type Vector3Array = [number, number, number];

export interface Pose {
  pos?: Vector3Array;
  quat?: [number, number, number, number];
  scale?: Vector3Array;
}

export interface MaterialOptions {
  flatShading?: boolean;
  doubleSide?: boolean;
}

export interface PrimitiveParams {
  // Box
  size?: Vector3Array;

  // Sphere
  radius?: number;

  // Cylinder/Cone
  height?: number;

  // Plane
  width?: number;

  // Arrow
  length?: number;
  start?: Vector3Array;
  end?: Vector3Array;
}

export type PrimitiveType = 'box' | 'sphere' | 'cylinder' | 'cone' | 'plane' | 'arrow' | 'axes';

/**
 * Factory class for creating Three.js geometry objects.
 * Handles materials, primitives, points, lines, meshes, and pose transformations.
 */
export class GeometryFactory {
  /**
   * Create a material from color array.
   * Supports RGB or RGBA colors (values 0-1).
   */
  createMaterial(color: ColorArray, options: MaterialOptions = {}): THREE.Material {
    const c = new THREE.Color(color[0], color[1], color[2]);
    const alpha = color.length >= 4 && typeof color[3] === 'number' ? color[3] : 1.0;

    const material = new THREE.MeshStandardMaterial({
      color: c,
      transparent: alpha < 1.0,
      opacity: alpha,
      depthWrite: alpha >= 1.0, // Disable depth write for transparent objects
      flatShading: options.flatShading !== false, // Default to flat shading
      side: options.doubleSide ? THREE.DoubleSide : THREE.FrontSide,
    });

    return material;
  }

  /**
   * Create a primitive object (box, sphere, cylinder, cone, plane, arrow, axes).
   */
  createPrimitive(type: PrimitiveType, params: PrimitiveParams, color: ColorArray): THREE.Object3D {
    const material = this.createMaterial(color);
    let geometry: THREE.BufferGeometry | null = null;

    switch (type) {
      case 'box': {
        const s = params.size || [1, 1, 1];
        geometry = new THREE.BoxGeometry(s[0], s[1], s[2]);
        break;
      }
      case 'sphere': {
        const r = params.radius || 0.5;
        geometry = new THREE.SphereGeometry(r, 32, 32);
        break;
      }
      case 'cylinder': {
        const r = params.radius || 0.5;
        const h = params.height || 1;
        geometry = new THREE.CylinderGeometry(r, r, h, 32);
        geometry.rotateX(Math.PI / 2); // Align cylinder axis to +Z (Z-up convention)
        break;
      }
      case 'cone': {
        const r = params.radius || 0.5;
        const h = params.height || 1;
        geometry = new THREE.ConeGeometry(r, h, 32);
        break;
      }
      case 'plane': {
        const w = params.width || 1;
        const h = params.height || 1;
        geometry = new THREE.PlaneGeometry(w, h);
        break;
      }
      case 'arrow': {
        return this.createArrow(params, material);
      }
      case 'axes': {
        return this.createAxes(params);
      }
      default:
        geometry = new THREE.BoxGeometry(1, 1, 1);
    }

    return new THREE.Mesh(geometry, material);
  }

  /**
   * Create an arrow primitive.
   * Arrow is built along +Y axis, then transformed to target orientation.
   */
  private createArrow(params: PrimitiveParams, material: THREE.Material): THREE.Group {
    const radius = params.radius || 0.05;
    const group = new THREE.Group();

    // Handle start/end or length
    let length = params.length || 1;
    let arrowStart = new THREE.Vector3(0, 0, 0);
    let arrowEnd: THREE.Vector3 | null = null;
    let direction = new THREE.Vector3(0, 0, 1); // Default: +Z (Z-up convention)

    if (params.start && params.end) {
      arrowStart.set(params.start[0], params.start[1], params.start[2]);
      arrowEnd = new THREE.Vector3(params.end[0], params.end[1], params.end[2]);
      length = arrowStart.distanceTo(arrowEnd);
      direction = new THREE.Vector3().subVectors(arrowEnd, arrowStart).normalize();
    }

    // Create shaft (80% of length) - centered at origin along +Y
    const shaftLength = length * 0.8;
    const shaftGeo = new THREE.CylinderGeometry(radius * 0.5, radius * 0.5, shaftLength, 16);
    const shaft = new THREE.Mesh(shaftGeo, material);
    shaft.position.y = shaftLength / 2; // Center shaft so bottom is at y=0
    group.add(shaft);

    // Create head (20% of length) - on top of shaft
    const headLength = length * 0.2;
    const headGeo = new THREE.ConeGeometry(radius * 1.5, headLength, 16);
    const head = new THREE.Mesh(headGeo, material);
    head.position.y = shaftLength + headLength / 2; // Place on top of shaft
    group.add(head);

    // Now the arrow points along +Y starting from origin
    // Transform to final orientation and position
    if (params.start && params.end) {
      // Rotate from +Y to target direction
      const up = new THREE.Vector3(0, 1, 0);
      const quaternion = new THREE.Quaternion().setFromUnitVectors(up, direction);
      group.quaternion.copy(quaternion);
      // Position at start point
      group.position.copy(arrowStart);
    } else {
      // Default: point along +Z axis (Z-up convention)
      // Rotate from +Y to +Z
      group.rotation.x = -Math.PI / 2;
    }

    return group;
  }

  /**
   * Create an axes helper (RGB = XYZ).
   */
  private createAxes(params: PrimitiveParams): THREE.Group {
    const length = params.length || 1;
    const radius = params.radius || 0.02;
    const group = new THREE.Group();

    const axes: Array<{ color: number; axis: "x" | "y" | "z" }> = [
      { color: 0xff0000, axis: "x" },
      { color: 0x00ff00, axis: "y" },
      { color: 0x0000ff, axis: "z" },
    ];

    for (const axisInfo of axes) {
      const geometry = this.buildAxisGeometry(length, radius, axisInfo.axis);
      const material = new THREE.MeshStandardMaterial({ color: axisInfo.color });
      const mesh = new THREE.Mesh(geometry, material);
      group.add(mesh);
    }

    return group;
  }

  buildAxisGeometry(length: number, radius: number, axis: "x" | "y" | "z"): THREE.CylinderGeometry {
    const geometry = new THREE.CylinderGeometry(radius, radius, length, 8);
    geometry.translate(0, length / 2, 0);
    if (axis === "x") {
      geometry.rotateZ(-Math.PI / 2);
    } else if (axis === "z") {
      geometry.rotateX(Math.PI / 2);
    }
    return geometry;
  }

  /**
   * Apply pose transformation (position, rotation, scale) to an object.
   */
  applyPose(obj: THREE.Object3D, pose: Pose): void {
    if (!pose) return;

    if (pose.pos) {
      obj.position.set(pose.pos[0], pose.pos[1], pose.pos[2]);
    }
    if (pose.quat) {
      obj.quaternion.set(pose.quat[0], pose.quat[1], pose.quat[2], pose.quat[3]);
    }
    if (pose.scale) {
      obj.scale.set(pose.scale[0], pose.scale[1], pose.scale[2]);
    }
  }

  /**
   * Create a point cloud from position and color arrays.
   * Per-point colors should be Uint8Array (0-255) and will be normalized to 0-1.
   * Uniform color uses [0-1] floats (ColorArray).
   */
  createPoints(
    positions: Float32Array,
    colors?: Uint8Array,
    size: number = 1,
    color?: ColorArray
  ): THREE.Points {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

    let material: THREE.PointsMaterial;
    if (colors) {
      // Normalize u8 colors to 0-1
      const normalizedColors = new Float32Array(colors.length);
      for (let i = 0; i < colors.length; i++) {
        normalizedColors[i] = colors[i] / 255;
      }
      geometry.setAttribute('color', new THREE.Float32BufferAttribute(normalizedColors, 3));
      material = new THREE.PointsMaterial({ size, vertexColors: true, sizeAttenuation: false });
    } else {
      const baseColor = color ? new THREE.Color(color[0], color[1], color[2]) : new THREE.Color(0xffffff);
      material = new THREE.PointsMaterial({ size, color: baseColor, sizeAttenuation: false });
      if (color && color.length >= 4) {
        const alpha = typeof color[3] === 'number' ? color[3] : 1.0;
        material.opacity = alpha;
        material.transparent = alpha < 1.0;
      }
    }

    return new THREE.Points(geometry, material);
  }

  /**
   * Create a line object from positions.
   */
  createLines(
    positions: Float32Array,
    color: ColorArray,
    width: number = 1,
    indices?: Uint32Array
  ): THREE.Line | THREE.LineSegments {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

    const c = new THREE.Color(color[0], color[1], color[2]);
    const material = new THREE.LineBasicMaterial({ color: c, linewidth: width });

    if (indices && indices.length > 0) {
      geometry.setIndex(new THREE.BufferAttribute(indices, 1));
      return new THREE.LineSegments(geometry, material);
    }

    return new THREE.Line(geometry, material);
  }

  /**
   * Create a mesh from vertices and faces.
   * Supports per-vertex colors, per-face colors, and uniform mesh color.
   * @param alpha - Optional global opacity (0.0=transparent, 1.0=opaque)
   * @param wireframe - Whether to show wireframe overlay for edge visibility (default=false)
   * @param smoothShading - Whether to use smooth shading (default=true)
   */
  createMesh(
    vertices: Float32Array,
    faces: Uint32Array,
    normals?: Float32Array,
    colors?: Uint8Array,
    color?: ColorArray,
    alpha?: number,
    wireframe?: boolean,
    smoothShading: boolean = true
  ): THREE.Mesh {
    const geometry = new THREE.BufferGeometry();
    let material: THREE.MeshStandardMaterial;
    const useSmoothShading = smoothShading !== false;
    const addWireframeOverlay = (mesh: THREE.Mesh): void => {
      if (wireframe !== true) return;
      const wireframeMat = new THREE.LineBasicMaterial({
        color: 0x000000,
        transparent: true,
        opacity: 0.15,
        depthTest: true,
      });
      const wireframeGeo = new THREE.WireframeGeometry(mesh.geometry);
      const wireframeLines = new THREE.LineSegments(wireframeGeo, wireframeMat);
      wireframeLines.userData.isWireframe = true;
      mesh.add(wireframeLines);
    };

    if (colors) {
      const perVertexColors = colors.length === vertices.length;
      const perFaceColors = colors.length === faces.length && colors.length !== vertices.length;

      // Preserve indexed topology for smooth-shaded vertex colors.
      // If we expand to non-indexed triangles, computeVertexNormals becomes faceted.
      if (perVertexColors && useSmoothShading) {
        const normalizedColors = new Float32Array(colors.length);
        for (let i = 0; i < colors.length; i++) {
          normalizedColors[i] = colors[i] / 255;
        }

        geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
        geometry.setIndex(new THREE.Uint32BufferAttribute(faces, 1));
        geometry.setAttribute('color', new THREE.Float32BufferAttribute(normalizedColors, 3));
        if (normals) {
          geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
        } else {
          geometry.computeVertexNormals();
        }

        const meshAlpha = alpha !== undefined ? alpha : 1.0;
        const transparent = meshAlpha < 1.0;
        material = new THREE.MeshStandardMaterial({
          vertexColors: true,
          side: THREE.DoubleSide,
          flatShading: false,
          transparent,
          opacity: meshAlpha,
          depthWrite: !transparent,
        });

        const mesh = new THREE.Mesh(geometry, material);
        addWireframeOverlay(mesh);
        return mesh;
      }

      if (perVertexColors || perFaceColors) {
        // Expand vertices so each face has independent vertices.
        // Allows per-face colors and flat-shaded per-vertex colors.
        const faceCount = faces.length / 3;
        const expandedPositions = new Float32Array(faceCount * 9); // 3 vertices * 3 coords per face
        const expandedColors = new Float32Array(faceCount * 9); // 3 vertices * 3 colors per face
        const normalsData = normals;
        const expandedNormals = normalsData ? new Float32Array(faceCount * 9) : null;

        for (let f = 0; f < faceCount; f++) {
          const i0 = faces[f * 3];
          const i1 = faces[f * 3 + 1];
          const i2 = faces[f * 3 + 2];

          // Copy positions for this face
          expandedPositions[f * 9 + 0] = vertices[i0 * 3];
          expandedPositions[f * 9 + 1] = vertices[i0 * 3 + 1];
          expandedPositions[f * 9 + 2] = vertices[i0 * 3 + 2];
          expandedPositions[f * 9 + 3] = vertices[i1 * 3];
          expandedPositions[f * 9 + 4] = vertices[i1 * 3 + 1];
          expandedPositions[f * 9 + 5] = vertices[i1 * 3 + 2];
          expandedPositions[f * 9 + 6] = vertices[i2 * 3];
          expandedPositions[f * 9 + 7] = vertices[i2 * 3 + 1];
          expandedPositions[f * 9 + 8] = vertices[i2 * 3 + 2];

          if (perFaceColors) {
            // One color per face
            const r = colors[f * 3] / 255;
            const g = colors[f * 3 + 1] / 255;
            const b = colors[f * 3 + 2] / 255;

            // Set same color for all 3 vertices of this face
            expandedColors[f * 9 + 0] = r;
            expandedColors[f * 9 + 1] = g;
            expandedColors[f * 9 + 2] = b;
            expandedColors[f * 9 + 3] = r;
            expandedColors[f * 9 + 4] = g;
            expandedColors[f * 9 + 5] = b;
            expandedColors[f * 9 + 6] = r;
            expandedColors[f * 9 + 7] = g;
            expandedColors[f * 9 + 8] = b;
          } else if (perVertexColors) {
            // Per-vertex colors
            const r0 = colors[i0 * 3] / 255;
            const g0 = colors[i0 * 3 + 1] / 255;
            const b0 = colors[i0 * 3 + 2] / 255;
            const r1 = colors[i1 * 3] / 255;
            const g1 = colors[i1 * 3 + 1] / 255;
            const b1 = colors[i1 * 3 + 2] / 255;
            const r2 = colors[i2 * 3] / 255;
            const g2 = colors[i2 * 3 + 1] / 255;
            const b2 = colors[i2 * 3 + 2] / 255;

            expandedColors[f * 9 + 0] = r0;
            expandedColors[f * 9 + 1] = g0;
            expandedColors[f * 9 + 2] = b0;
            expandedColors[f * 9 + 3] = r1;
            expandedColors[f * 9 + 4] = g1;
            expandedColors[f * 9 + 5] = b1;
            expandedColors[f * 9 + 6] = r2;
            expandedColors[f * 9 + 7] = g2;
            expandedColors[f * 9 + 8] = b2;
          }

          if (expandedNormals && normalsData) {
            expandedNormals[f * 9 + 0] = normalsData[i0 * 3];
            expandedNormals[f * 9 + 1] = normalsData[i0 * 3 + 1];
            expandedNormals[f * 9 + 2] = normalsData[i0 * 3 + 2];
            expandedNormals[f * 9 + 3] = normalsData[i1 * 3];
            expandedNormals[f * 9 + 4] = normalsData[i1 * 3 + 1];
            expandedNormals[f * 9 + 5] = normalsData[i1 * 3 + 2];
            expandedNormals[f * 9 + 6] = normalsData[i2 * 3];
            expandedNormals[f * 9 + 7] = normalsData[i2 * 3 + 1];
            expandedNormals[f * 9 + 8] = normalsData[i2 * 3 + 2];
          }
        }

        geometry.setAttribute('position', new THREE.Float32BufferAttribute(expandedPositions, 3));
        geometry.setAttribute('color', new THREE.Float32BufferAttribute(expandedColors, 3));
        if (expandedNormals) {
          geometry.setAttribute('normal', new THREE.Float32BufferAttribute(expandedNormals, 3));
        } else {
          geometry.computeVertexNormals();
        }

        const meshAlpha = alpha !== undefined ? alpha : 1.0;
        const transparent = meshAlpha < 1.0;
        material = new THREE.MeshStandardMaterial({
          vertexColors: true,
          side: THREE.DoubleSide,
          flatShading: !useSmoothShading,
          transparent,
          opacity: meshAlpha,
          depthWrite: !transparent,
        });
        const mesh = new THREE.Mesh(geometry, material);
        addWireframeOverlay(mesh);
        return mesh;
      }
      console.warn(
        `[FrameVizCore] createMesh: colors size mismatch (colors=${colors.length}, vertices=${vertices.length}, faces=${faces.length})`
      );
    }
    // No colors - use indexed geometry with uniform color
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setIndex(new THREE.Uint32BufferAttribute(faces, 1));
    if (normals) {
      geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
    } else {
      geometry.computeVertexNormals();
    }

    // Use provided color or default gray
    const c = color || [0.5, 0.5, 0.5];
    const colorAlpha = c.length >= 4 && typeof c[3] === 'number' ? c[3] : 1.0;
    const meshAlpha = alpha !== undefined ? alpha : colorAlpha;
    const transparent = meshAlpha < 1.0;
    material = new THREE.MeshStandardMaterial({
      color: new THREE.Color(c[0], c[1], c[2]),
      transparent,
      opacity: meshAlpha,
      depthWrite: !transparent,
      side: THREE.DoubleSide,
      flatShading: !useSmoothShading,
    });

    // Create mesh with optional wireframe overlay for better edge visibility
    const mesh = new THREE.Mesh(geometry, material);
    addWireframeOverlay(mesh);

    return mesh;
  }
}

import * as THREE from 'three';

export type RenderMode = 'solid' | 'wireframe' | 'points';

export const RENDER_MODES: RenderMode[] = ['solid', 'wireframe', 'points'];

/**
 * Manages rendering modes for 3D objects.
 * Supports solid, wireframe, and points visualization modes.
 */
export class RenderModeManager {
  private currentMode: RenderMode = 'solid';
  private pointsHelpers = new Map<string, THREE.Points>();

  /**
   * Set the render mode for all objects.
   * @param mode - The render mode to apply
   * @param objects - Map of objects to update
   */
  setRenderMode(mode: RenderMode, objects: Map<string, THREE.Object3D>): void {
    if (!RENDER_MODES.includes(mode)) return;

    this.currentMode = mode;

    objects.forEach((obj) => {
      const userVisible = (obj as THREE.Object3D & { userData?: { userVisible?: boolean } }).userData
        ?.userVisible;
      const baseVisible = userVisible !== undefined ? userVisible : true;
      // Traverse all objects including Groups (like Collada models)
      obj.traverse((child) => {
        if (child.type === 'Mesh') {
          const mesh = child as THREE.Mesh;

          // Handle materials (could be array or single)
          const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          materials.forEach((mat) => {
            if (mat instanceof THREE.Material) {
              (mat as any).wireframe = (mode === 'wireframe');
            }
          });

          mesh.visible = baseVisible && (mode !== 'points');

          // Create/show/hide points helper for this mesh
          if (mode === 'points') {
            if (baseVisible) {
              if (!this.pointsHelpers.has(mesh.uuid)) {
                // Create points from mesh geometry
                const pointsMat = new THREE.PointsMaterial({
                  size: 3,
                  sizeAttenuation: false,
                  color: 0x4cc9f0,
                  vertexColors: mesh.geometry.attributes.color ? true : false,
                });
                const points = new THREE.Points(mesh.geometry, pointsMat);
                points.matrixAutoUpdate = false;
                this.pointsHelpers.set(mesh.uuid, points);

                if (mesh.parent) {
                  mesh.parent.add(points);
                }
              }

              const pts = this.pointsHelpers.get(mesh.uuid);
              if (pts) {
                pts.matrix.copy(mesh.matrix);
                pts.matrixWorld.copy(mesh.matrixWorld);
                pts.visible = true;
              }
            } else {
              const pts = this.pointsHelpers.get(mesh.uuid);
              if (pts) {
                pts.visible = false;
              }
            }
          } else {
            // Hide points helper if exists
            if (this.pointsHelpers.has(mesh.uuid)) {
              const pts = this.pointsHelpers.get(mesh.uuid);
              if (pts) {
                pts.visible = false;
              }
            }
          }
        }
      });

      // Handle Points objects visibility
      if (obj.type === 'Points') {
        obj.visible = baseVisible;
      }
    });
  }

  /**
   * Cycle to the next render mode.
   * @param objects - Map of objects to update
   * @returns The new render mode
   */
  cycleRenderMode(objects: Map<string, THREE.Object3D>): RenderMode {
    const currentIndex = RENDER_MODES.indexOf(this.currentMode);
    const nextIndex = (currentIndex + 1) % RENDER_MODES.length;
    const nextMode = RENDER_MODES[nextIndex];

    this.setRenderMode(nextMode, objects);

    return nextMode;
  }

  /**
   * Get the current render mode.
   */
  getCurrentMode(): RenderMode {
    return this.currentMode;
  }

  /**
   * Clean up points helpers for objects that no longer exist.
   * @param objects - Current map of objects
   */
  cleanupHelpers(objects: Map<string, THREE.Object3D>): void {
    const existingUuids = new Set<string>();

    objects.forEach((obj) => {
      obj.traverse((child) => {
        if (child.type === 'Mesh') {
          existingUuids.add(child.uuid);
        }
      });
    });

    // Remove helpers for deleted meshes
    for (const [uuid, helper] of this.pointsHelpers) {
      if (!existingUuids.has(uuid)) {
        if (helper.parent) {
          helper.parent.remove(helper);
        }
        helper.geometry.dispose();
        if (helper.material instanceof THREE.Material) {
          helper.material.dispose();
        }
        this.pointsHelpers.delete(uuid);
      }
    }
  }

  /**
   * Dispose all resources.
   */
  dispose(): void {
    this.pointsHelpers.forEach((helper) => {
      if (helper.parent) {
        helper.parent.remove(helper);
      }
      helper.geometry.dispose();
      if (helper.material instanceof THREE.Material) {
        helper.material.dispose();
      }
    });
    this.pointsHelpers.clear();
  }
}

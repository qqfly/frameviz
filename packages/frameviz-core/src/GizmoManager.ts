
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CombinedTransformControls, GIZMO_MASK_ALL } from './controls/CombinedTransformControls.js';

export interface GizmoConfig {
  size?: number;
  mask?: number; // 0x3F style mask
  scale_mode?: 'screen' | 'world';
}

export type TransformChangeCallback = (handle: string, pose: { pos: number[], quat: number[], scale: number[] }) => void;

export class GizmoManager {
  public controls: CombinedTransformControls;
  private attachedHandle: string | null = null;
  private onTransformChange: TransformChangeCallback | null = null;
  private orbitControls: OrbitControls;
  private scene: THREE.Scene;

  constructor(
    camera: THREE.Camera,
    domElement: HTMLElement,
    orbitControls: OrbitControls,
    scene: THREE.Scene
  ) {
    this.scene = scene;
    this.orbitControls = orbitControls;
    this.controls = new CombinedTransformControls(camera, domElement);

    // Setup listeners
    this.controls.addEventListener('mouseDown', () => {
      this.orbitControls.enabled = false;
    });

    this.controls.addEventListener('mouseUp', () => {
      this.orbitControls.enabled = true;
    });

    this.controls.addEventListener('change', () => {
      // Trigger render if needed, usually handled by main loop or invalidation
    });

    this.controls.addEventListener('objectChange', () => {
      if (this.controls.object && this.onTransformChange && this.attachedHandle) {
        const obj = this.controls.object;
        this.onTransformChange(this.attachedHandle, {
          pos: obj.position.toArray(),
          quat: obj.quaternion.toArray(),
          scale: obj.scale.toArray()
        });
      }
    });

    scene.add(this.controls);
  }

  public attach(object: THREE.Object3D, handle: string, config: GizmoConfig = {}): void {
    this.attachedHandle = handle;
    this.controls.attach(object);
    this.configure(config);
  }

  public detach(): void {
    this.attachedHandle = null;
    this.controls.detach();
  }

  public configure(config: GizmoConfig): void {
    if (config.size !== undefined) {
      this.controls.size = config.size;
    }
    if (config.mask !== undefined) {
      this.controls.setMask(config.mask);
    }
    if (config.scale_mode !== undefined) {
      this.controls.scaleMode = config.scale_mode;
    }
  }

  public getAttachedHandle(): string | null {
    return this.attachedHandle;
  }

  public dispose(): void {
    if (this.controls.parent === this.scene) {
      this.scene.remove(this.controls);
    }
    this.controls.dispose();
  }

  public setTransformChangeCallback(callback: TransformChangeCallback): void {
    this.onTransformChange = callback;
  }
}

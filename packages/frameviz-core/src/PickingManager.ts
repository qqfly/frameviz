import * as THREE from "three";

export type PickMode = "object" | "point";

export interface PickConfig {
  enabled?: boolean;
  mode?: PickMode;
  button?: number;
  ctrl_modifier?: boolean;
  highlight_color?: [number, number, number];
  marker_size?: number;
  point_threshold?: number;
  line_threshold?: number;
}

export interface PickInfo {
  hit_type: "none" | "object" | "point" | "line";
  handle: string | null;
  point_world: number[] | null;
  normal_world: number[] | null;
  point_index: number | null;
}

export interface PickingManagerOptions {
  scene: THREE.Scene;
  camera: THREE.Camera;
  domElement: HTMLElement;
  objects: Map<string, THREE.Object3D>;
  viewId?: string;
  onEvent?: (name: string, data: Record<string, unknown>) => void;
}

const DEFAULT_PICK_CONFIG: Required<PickConfig> = {
  enabled: false,
  mode: "object",
  button: 2,
  ctrl_modifier: false,
  highlight_color: [1, 1, 0],
  marker_size: 0.1,
  point_threshold: 0.01,
  line_threshold: 0.01,
};

/**
 * Handles picking (raycasting) and visual feedback.
 * Emits events via the optional onEvent callback.
 */
export class PickingManager {
  private scene: THREE.Scene;
  private camera: THREE.Camera;
  private domElement: HTMLElement;
  private objects: Map<string, THREE.Object3D>;
  private onEvent?: (name: string, data: Record<string, unknown>) => void;
  private viewId?: string;

  private raycaster = new THREE.Raycaster();
  private mouse = new THREE.Vector2();
  private config: Required<PickConfig> = { ...DEFAULT_PICK_CONFIG };

  private selectedHandle: string | null = null;
  private selectedOriginalMaterial: THREE.Material | THREE.Material[] | null = null;
  private selectedHighlightMaterial: THREE.Material | THREE.Material[] | null = null;
  private pickPointMarker: THREE.Object3D | null = null;

  private lastPickInfo: PickInfo = {
    hit_type: "none",
    handle: null,
    point_world: null,
    normal_world: null,
    point_index: null,
  };

  private readonly onMouseDown: (event: MouseEvent) => void;
  private readonly onContextMenu: (event: MouseEvent) => void;

  constructor(options: PickingManagerOptions) {
    this.scene = options.scene;
    this.camera = options.camera;
    this.domElement = options.domElement;
    this.objects = options.objects;
    this.onEvent = options.onEvent;
    this.viewId = options.viewId;

    this.onMouseDown = (event: MouseEvent) => this.handleMouseDown(event);
    this.onContextMenu = (event: MouseEvent) => event.preventDefault();

    this.domElement.addEventListener("mousedown", this.onMouseDown);
    this.domElement.addEventListener("contextmenu", this.onContextMenu);
  }

  setViewId(viewId: string | undefined): void {
    this.viewId = viewId;
  }

  setConfig(config: PickConfig): void {
    const wasEnabled = this.config.enabled;
    if (config.enabled !== undefined) this.config.enabled = config.enabled;
    if (config.mode !== undefined) this.config.mode = config.mode;
    if (config.button !== undefined) this.config.button = config.button;
    if (config.ctrl_modifier !== undefined) this.config.ctrl_modifier = config.ctrl_modifier;
    if (config.highlight_color !== undefined) this.config.highlight_color = config.highlight_color;
    if (config.marker_size !== undefined) this.config.marker_size = config.marker_size;
    if (config.point_threshold !== undefined) this.config.point_threshold = config.point_threshold;
    if (config.line_threshold !== undefined) this.config.line_threshold = config.line_threshold;

    if ((wasEnabled && !this.config.enabled) || config.mode !== undefined) {
      this.clearHighlight();
    }
  }

  getConfig(): Required<PickConfig> {
    return { ...this.config };
  }

  getLastPickInfo(): PickInfo {
    return { ...this.lastPickInfo };
  }

  suspendObjectHighlight(handle: string): (() => void) | undefined {
    if (this.selectedHandle !== handle) return;
    // Appearance commands must update the base material that deselection restores.
    this.clearHighlight();
    return () => this.highlightObject(handle);
  }

  clearHighlight(): void {
    if (this.selectedHandle && this.selectedOriginalMaterial) {
      const obj = this.objects.get(this.selectedHandle) as THREE.Mesh | undefined;
      if (obj && (obj as any).material) {
        (obj as any).material = this.selectedOriginalMaterial;
      }
    }
    this.disposeMaterial(this.selectedHighlightMaterial);
    this.selectedHandle = null;
    this.selectedOriginalMaterial = null;
    this.selectedHighlightMaterial = null;

    this.disposePickPointMarker();
  }

  dispose(): void {
    this.clearHighlight();
    this.domElement.removeEventListener("mousedown", this.onMouseDown);
    this.domElement.removeEventListener("contextmenu", this.onContextMenu);
  }

  private handleMouseDown(event: MouseEvent): void {
    if (!this.config.enabled) return;
    if (event.button !== this.config.button) return;
    if (this.config.ctrl_modifier && !event.ctrlKey) return;

    if (event.button === 2) {
      event.preventDefault();
    }

    const rect = this.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.mouse, this.camera);

    const visible = (object: THREE.Object3D): boolean => {
      for (let current: THREE.Object3D | null = object; current; current = current.parent) {
        if (!current.visible) return false;
      }
      return true;
    };
    this.scene.updateMatrixWorld(true);
    this.raycaster.params.Points.threshold = this.config.point_threshold;
    this.raycaster.params.Line.threshold = this.config.line_threshold;
    const drawables = [...this.objects.values()].filter(visible);
    const allIntersects = this.raycaster.intersectObjects(drawables, true).filter(hit => visible(hit.object));

    const modifiers = {
      ctrl: event.ctrlKey,
      shift: event.shiftKey,
      alt: event.altKey,
    };

    if (allIntersects.length === 0) {
      this.clearHighlight();
      this.lastPickInfo = {
        hit_type: "none",
        handle: null,
        point_world: null,
        normal_world: null,
        point_index: null,
      };
      this.emitEvent("picked", { view_id: this.viewId, hit_type: "none", modifiers });
      return;
    }

    const hit = allIntersects[0];
    let obj = hit.object;

    if (obj.userData?.isWireframe && obj.parent) {
      obj = obj.parent;
    }

    while (obj && !obj.userData?.handle && obj.parent && obj.parent !== this.scene) {
      obj = obj.parent;
    }

    const handle = obj.userData?.handle ?? null;
    const isPointCloud = hit.object instanceof THREE.Points;
    const isLine = obj instanceof THREE.Line;

    let hitType: PickInfo["hit_type"] = "object";
    if (isPointCloud) hitType = "point";
    else if (isLine) hitType = "line";

    let pointWorld: number[] = hit.point.toArray();
    let normalWorld: number[] = [0, 0, 1];
    let pointIndex: number | null = null;

    if (isPointCloud && hit.index !== undefined) {
      const positions = (hit.object as THREE.Points).geometry.attributes.position;
      pointWorld = new THREE.Vector3(
        positions.getX(hit.index), positions.getY(hit.index), positions.getZ(hit.index)
      ).applyMatrix4(hit.object.matrixWorld).toArray();
      pointIndex = hit.index + (hit.object.userData.pointOffset ?? 0);
    } else if (isLine && hit.index !== undefined) {
      pointWorld = hit.point.toArray();
      pointIndex = hit.index;
    } else if (hit.face) {
      normalWorld = hit.face.normal
        .clone()
        .applyMatrix3(new THREE.Matrix3().getNormalMatrix(hit.object.matrixWorld))
        .normalize()
        .toArray();
    }

    this.lastPickInfo = {
      hit_type: hitType,
      handle,
      point_world: pointWorld,
      normal_world: normalWorld,
      point_index: pointIndex,
    };

    if (this.config.mode === "point") {
      this.showPickPointMarker(pointWorld, normalWorld, isPointCloud || isLine);
    } else if (handle) {
      this.highlightObject(handle);
    }

    this.emitEvent("picked", {
      view_id: this.viewId,
      hit_type: hitType,
      handle,
      point_world: pointWorld,
      normal_world: normalWorld,
      point_index: pointIndex,
      modifiers,
    });
  }

  private highlightObject(handle: string): void {
    this.clearHighlight();
    const obj = this.objects.get(handle) as THREE.Mesh | THREE.Line | THREE.Points | undefined;
    if (!obj || !(obj as any).material) return;

    this.selectedHandle = handle;
    this.selectedOriginalMaterial = (obj as any).material;

    const hc = this.config.highlight_color;
    const highlightColor = new THREE.Color(hc[0], hc[1], hc[2]);

    if (obj instanceof THREE.Points) {
      const material = (obj.material as THREE.PointsMaterial).clone();
      material.size = (material.size || 0.01) * 1.5;
      if (!material.vertexColors) {
        material.color = highlightColor;
      }
      obj.material = material;
      this.selectedHighlightMaterial = material;
    } else if (obj instanceof THREE.Line) {
      const material = (obj.material as THREE.LineBasicMaterial).clone();
      material.linewidth = (material.linewidth || 1) * 2;
      const origColor = material.color.clone();
      material.color = origColor.lerp(highlightColor, 0.5);
      obj.material = material;
      this.selectedHighlightMaterial = material;
    } else {
      const materialValue = (obj as THREE.Mesh).material;
      const materials = Array.isArray(materialValue) ? materialValue : [materialValue];
      const cloned = materials.map((mat) => {
        const next = mat.clone() as THREE.MeshStandardMaterial;
        if ((next as any).emissive) {
          next.emissive = new THREE.Color(hc[0] * 0.3, hc[1] * 0.3, hc[2] * 0.3);
          next.emissiveIntensity = 1.0;
        }
        return next;
      });
      (obj as THREE.Mesh).material = Array.isArray(materialValue) ? cloned : cloned[0];
      this.selectedHighlightMaterial = Array.isArray(materialValue) ? cloned : cloned[0];
    }
  }

  private showPickPointMarker(point: number[], normal: number[], isPointCloud: boolean): void {
    this.disposePickPointMarker();

    const size = this.config.marker_size;
    const marker = new THREE.Group();

    if (isPointCloud || !normal || (normal[0] === 0 && normal[1] === 0 && normal[2] === 0)) {
      marker.add(new THREE.AxesHelper(size));
    } else {
      const zAxis = new THREE.Vector3(normal[0], normal[1], normal[2]).normalize();
      const worldX = new THREE.Vector3(1, 0, 0);
      let xAxis: THREE.Vector3;
      if (Math.abs(zAxis.dot(worldX)) > 0.9) {
        xAxis = new THREE.Vector3(0, 1, 0).cross(zAxis).normalize();
      } else {
        xAxis = worldX.clone().sub(zAxis.clone().multiplyScalar(zAxis.dot(worldX))).normalize();
      }
      const yAxis = zAxis.clone().cross(xAxis).normalize();

      marker.add(new THREE.ArrowHelper(xAxis, new THREE.Vector3(), size, 0xff0000, size * 0.2, size * 0.1));
      marker.add(new THREE.ArrowHelper(yAxis, new THREE.Vector3(), size, 0x00ff00, size * 0.2, size * 0.1));
      marker.add(new THREE.ArrowHelper(zAxis, new THREE.Vector3(), size, 0x0000ff, size * 0.2, size * 0.1));
    }

    marker.position.set(point[0], point[1], point[2]);
    this.scene.add(marker);
    this.pickPointMarker = marker;
  }

  private disposePickPointMarker(): void {
    if (!this.pickPointMarker) return;
    const marker = this.pickPointMarker;
    this.scene.remove(marker);
    marker.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (mesh.geometry) {
        mesh.geometry.dispose();
      }
      if (mesh.material) {
        this.disposeMaterial(mesh.material as THREE.Material | THREE.Material[]);
      }
    });
    this.pickPointMarker = null;
  }

  private disposeMaterial(material: THREE.Material | THREE.Material[] | null): void {
    if (!material) return;
    const materials = Array.isArray(material) ? material : [material];
    materials.forEach((mat) => {
      if (!mat) return;
      if (typeof mat.dispose === "function") {
        mat.dispose();
      }
    });
  }

  private emitEvent(name: string, data: Record<string, unknown>): void {
    if (this.onEvent) {
      this.onEvent(name, data);
    }
  }
}

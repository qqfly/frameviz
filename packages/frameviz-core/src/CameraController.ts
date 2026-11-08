import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

export interface ViewPreset {
  pos: [number, number, number];
  target: [number, number, number];
}

export type ViewPresetName = 'home' | 'front' | 'back' | 'left' | 'right' | 'top' | 'bottom';

/**
 * View presets for camera positions.
 * All presets use normalized directions that are scaled by distance.
 */
export const VIEW_PRESETS: Record<ViewPresetName, ViewPreset> = {
  home: { pos: [1, 1, 1], target: [0, 0, 0] },       // Isometric (+X+Y+Z)
  front: { pos: [1, 0, 0], target: [0, 0, 0] },      // Front (+X looking at origin)
  back: { pos: [-1, 0, 0], target: [0, 0, 0] },      // Back (-X looking at origin)
  left: { pos: [0, 1, 0], target: [0, 0, 0] },       // Left (+Y looking at origin)
  right: { pos: [0, -1, 0], target: [0, 0, 0] },     // Right (-Y looking at origin)
  top: { pos: [0, 0, 1], target: [0, 0, 0] },        // Top (+Z looking at origin)
  bottom: { pos: [0, 0, -1], target: [0, 0, 0] },    // Bottom (-Z looking at origin)
};

export interface CameraControllerOptions {
  camera: THREE.PerspectiveCamera;
  domElement: HTMLElement;
  initialDistance?: number;
}

/**
 * Manages camera controls, view presets, and zoom behavior.
 * Provides smooth camera animations and zoom-to-cursor functionality.
 */
export class CameraController {
  readonly controls: OrbitControls;
  private camera: THREE.PerspectiveCamera;
  private domElement: HTMLElement;
  private initialDistance: number;

  private raycasterZoom: THREE.Raycaster;
  private mouseZoom: THREE.Vector2;
  private tempVec = new THREE.Vector3();
  private tempBox = new THREE.Box3();
  private zoomToCursorEnabled: boolean = false;  // Default off for performance with large point clouds
  private zoomEnabled: boolean = true;
  private zoomSensitivity: number = 1.0;
  private invertWheelZoom: boolean = false;
  private wheelHandler: (event: WheelEvent) => void;
  private objectsProvider?: () => Map<string, THREE.Object3D>;
  private mousePreset: 'cad' | 'trackpad' | 'custom' = 'cad';
  private mouseButtons: {
    left: 'rotate' | 'pan' | 'zoom' | 'none';
    middle: 'rotate' | 'pan' | 'zoom' | 'none';
    right: 'rotate' | 'pan' | 'zoom' | 'none';
  } = { left: 'rotate', middle: 'pan', right: 'none' };

  constructor(options: CameraControllerOptions) {
    this.camera = options.camera;
    this.domElement = options.domElement;
    this.initialDistance = options.initialDistance ?? 1.5;

    // Initialize OrbitControls
    // NOTE(#45): OrbitControls has an inherent polar angle limitation (gimbal lock)
    // that restricts rotation near the poles (directly above/below). This is a
    // design trade-off in Three.js to keep the up-vector stable. Alternatives
    // (TrackballControls, ArcballControls) remove this restriction but lose the
    // fixed up-direction, which is undesirable for Z-up robotics/industrial scenes.
    // Decision: keep current behavior. See docs/INTERACTION.md
    this.controls = new OrbitControls(this.camera, this.domElement);
    this.controls.enableDamping = false;  // P1-1: Default off for precise control
    this.controls.enableZoom = false;
    this.controls.enableRotate = true;
    this.controls.enablePan = true;
    this.controls.rotateSpeed = 0.5;

    // P1-2: Default mouse preset based on platform
    // Mac users typically use trackpad, Windows/Linux use mouse
    const isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform);
    this.setMousePreset(isMac ? 'trackpad' : 'cad');

    // Initialize raycaster for zoom-to-cursor
    this.raycasterZoom = new THREE.Raycaster();
    this.mouseZoom = new THREE.Vector2();

    // Setup wheel event handler
    this.wheelHandler = this.handleZoom.bind(this);
    this.domElement.addEventListener('wheel', this.wheelHandler, { passive: false });
  }

  /**
   * Set camera to a predefined view.
   * @param viewName - Name of the view preset
   * @param fitAll - If true, adjusts distance to fit all objects in view
   * @param objects - Optional map of objects to fit in view
   */
  setView(
    viewName: ViewPresetName,
    fitAll: boolean = false,
    objects?: Map<string, THREE.Object3D>
  ): void {
    const preset = VIEW_PRESETS[viewName];
    if (!preset) return;

    let distance = this.initialDistance;
    let target: [number, number, number] = [...preset.target];

    if (fitAll && objects && objects.size > 0) {
      const box = this.computeFiniteBounds(objects.values());
      if (box && !box.isEmpty()) {
        const center = new THREE.Vector3();
        box.getCenter(center);
        target = [center.x, center.y, center.z];

        const size = new THREE.Vector3();
        box.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        if (Number.isFinite(maxDim) && maxDim > 0) {
          distance = maxDim * 2.5; // Adjust distance to fit all
        }
      }
    }

    // Normalize direction and apply distance
    const dir = new THREE.Vector3(...preset.pos).normalize();
    const newPos = dir.multiplyScalar(distance);

    // Animate camera movement
    const startPos = this.camera.position.clone();
    const startTarget = this.controls.target.clone();
    const endPos = new THREE.Vector3(
      target[0] + newPos.x,
      target[1] + newPos.y,
      target[2] + newPos.z
    );
    const endTarget = new THREE.Vector3(...target);

    this.animateCamera(startPos, endPos, startTarget, endTarget);
  }

  /**
   * Animate camera from start to end position/target.
   */
  private animateCamera(
    startPos: THREE.Vector3,
    endPos: THREE.Vector3,
    startTarget: THREE.Vector3,
    endTarget: THREE.Vector3,
    duration: number = 300
  ): void {
    const startTime = Date.now();

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const t = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3); // Ease out cubic

      this.camera.position.lerpVectors(startPos, endPos, eased);
      this.controls.target.lerpVectors(startTarget, endTarget, eased);
      this.controls.update();

      if (t < 1) {
        requestAnimationFrame(animate);
      }
    };

    animate();
  }

  /**
   * Reset camera to home view and fit all objects.
   */
  resetView(objects?: Map<string, THREE.Object3D>): void {
    this.setView('home', true, objects);
  }

  /**
   * Handle wheel event for zoom-to-cursor.
   * This method is bound to the wheel event and manages zoom behavior.
   */
  handleZoom(event: WheelEvent, objects?: Map<string, THREE.Object3D>): void {
    event.preventDefault();

    if (!this.zoomEnabled) {
      return;
    }

    const sensitivity = Math.max(0, this.zoomSensitivity);
    const zoomFactor = Math.pow(1.1, sensitivity);
    const deltaY = this.invertWheelZoom ? -event.deltaY : event.deltaY;
    const delta = deltaY > 0 ? zoomFactor : 1 / zoomFactor;

    if (!objects && this.objectsProvider) {
      objects = this.objectsProvider();
    }

    if (this.zoomToCursorEnabled && objects) {
      // Get mouse position in normalized device coordinates
      const rect = this.domElement.getBoundingClientRect();
      this.mouseZoom.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      this.mouseZoom.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      // Raycast to find point under cursor
      this.raycasterZoom.setFromCamera(this.mouseZoom, this.camera);
      this.raycasterZoom.params.Points.threshold = 0.05;
      this.raycasterZoom.params.Line.threshold = 0.05;
      const intersects = this.raycasterZoom.intersectObjects(
        Array.from(objects.values()),
        true
      );

      let zoomPoint: THREE.Vector3 | null = null;
      if (intersects.length > 0) {
        // Use intersection point
        zoomPoint = intersects[0].point.clone();
      } else {
        // Fallback: intersect with plane through target, perpendicular to camera
        const planeNormal = new THREE.Vector3();
        this.camera.getWorldDirection(planeNormal);
        const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(planeNormal, this.controls.target);
        zoomPoint = new THREE.Vector3();
        if (!this.raycasterZoom.ray.intersectPlane(plane, zoomPoint)) {
          zoomPoint = null;
        }
      }

      if (zoomPoint) {
        // Dolly camera along the cursor ray while keeping orientation.
        const cameraToZoomPoint = zoomPoint.clone().sub(this.camera.position);
        const distance = cameraToZoomPoint.length();
        if (distance > 1e-6) {
          const direction = cameraToZoomPoint.multiplyScalar(1 / distance);
          const newDistance = distance * delta;
          const newCameraPos = zoomPoint.clone().sub(direction.multiplyScalar(newDistance));
          const translation = newCameraPos.clone().sub(this.camera.position);
          this.camera.position.copy(newCameraPos);
          this.controls.target.add(translation);
        }
      } else {
        // Fallback: zoom towards target
        this.zoomTowardsTarget(delta);
      }
    } else {
      // Simple zoom towards target
      this.zoomTowardsTarget(delta);
    }

    this.controls.update();
  }

  /**
   * Simple zoom towards control target.
   * When camera gets very close to target, move target forward along view direction
   * to allow zooming "through" the target point.
   */
  private zoomTowardsTarget(delta: number): void {
    const direction = this.camera.position.clone().sub(this.controls.target);
    const currentDistance = direction.length();

    // Minimum distance before we start moving the target
    const minDistance = 0.1;

    if (delta < 1.0 && currentDistance < minDistance) {
      // Zooming in and very close to target - move target forward
      // Get camera's forward direction
      const forward = new THREE.Vector3();
      this.camera.getWorldDirection(forward);

      // Continue the normal multiplicative dolly at very close range, but
      // translate camera+target together so we can move through the focal point
      // without a sudden jump.
      const moveAmount = Math.max(currentDistance, 1e-3) * (1 - delta);
      const movement = forward.multiplyScalar(moveAmount);
      this.camera.position.add(movement);
      this.controls.target.add(movement);
    } else if (delta > 1.0 && currentDistance < minDistance) {
      // Zooming out from very close range - only move camera backward (keep
      // target fixed) so currentDistance grows and eventually exceeds minDistance,
      // returning to normal multiplicative dolly behavior.
      const backward = new THREE.Vector3();
      this.camera.getWorldDirection(backward).negate();
      const stepSize = Math.max(currentDistance, 1e-3) * (delta - 1);
      this.camera.position.add(backward.multiplyScalar(stepSize));
    } else {
      // Normal zoom behavior
      this.camera.position.copy(this.controls.target).add(direction.multiplyScalar(delta));
    }
  }

  /**
   * Enable or disable zoom-to-cursor behavior.
   * Warning: Enabling this with large point clouds may cause performance issues.
   */
  setZoomToCursor(enabled: boolean): void {
    this.zoomToCursorEnabled = enabled;

    // Warn if enabling with point clouds in scene
    if (enabled && this.objectsProvider) {
      const objects = this.objectsProvider();
      let hasPoints = false;
      let totalPoints = 0;
      objects.forEach((obj) => {
        obj.traverse((child) => {
          if ((child as THREE.Points).isPoints) {
            hasPoints = true;
            const geom = (child as THREE.Points).geometry;
            const posAttr = geom.getAttribute('position');
            if (posAttr) totalPoints += posAttr.count;
          }
        });
      });
      if (hasPoints && totalPoints > 100000) {
        console.warn(
          `[FrameViz] zoom_to_cursor enabled with ${(totalPoints / 1e6).toFixed(2)}M points. ` +
          `This may cause zoom lag. Consider disabling for better performance.`
        );
      }
    }
  }

  /**
   * Enable or disable zoom handling.
   */
  setZoomEnabled(enabled: boolean): void {
    this.zoomEnabled = enabled;
  }

  /**
   * Configure zoom sensitivity (1.0 = default).
   */
  setZoomSensitivity(value: number): void {
    if (!Number.isFinite(value)) {
      return;
    }
    this.zoomSensitivity = Math.max(0, value);
  }

  /**
   * Enable or disable orbit rotation.
   */
  setOrbitEnabled(enabled: boolean): void {
    this.controls.enableRotate = enabled;
  }

  /**
   * Enable or disable panning.
   */
  setPanEnabled(enabled: boolean): void {
    this.controls.enablePan = enabled;
  }

  /**
   * P1-1: Enable or disable camera damping (inertia).
   * When enabled, camera movement continues briefly after mouse release.
   */
  setDamping(enabled: boolean): void {
    this.controls.enableDamping = enabled;
    this.controls.dampingFactor = 0.05;  // Only effective when enabled
  }

  /**
   * P1-2: Set mouse button actions.
   */
  setMouseButtons(mapping: {
    left?: 'rotate' | 'pan' | 'zoom' | 'none';
    middle?: 'rotate' | 'pan' | 'zoom' | 'none';
    right?: 'rotate' | 'pan' | 'zoom' | 'none';
  }): void {
    const actionMap: Record<string, THREE.MOUSE | undefined> = {
      rotate: THREE.MOUSE.ROTATE,
      pan: THREE.MOUSE.PAN,
      zoom: THREE.MOUSE.DOLLY,
      none: undefined,
    };
    const left = mapping.left ?? 'rotate';
    const middle = mapping.middle ?? 'pan';
    const right = mapping.right ?? 'none';

    this.mouseButtons = { left, middle, right };
    this.mousePreset = 'custom';

    this.controls.mouseButtons = {
      LEFT: actionMap[left] ?? THREE.MOUSE.ROTATE,
      MIDDLE: actionMap[middle] ?? THREE.MOUSE.PAN,
      RIGHT: actionMap[right] as THREE.MOUSE,
    };

    // Auto-infer wheel direction for known presets.
    if (left === 'rotate' && middle === 'pan' && right === 'none') {
      this.invertWheelZoom = true; // CAD-style
    } else if (left === 'rotate' && middle === 'zoom' && right === 'pan') {
      this.invertWheelZoom = false; // Trackpad-style
    }
  }

  /**
   * P1-2: Set mouse button preset.
   * 'cad' = left:rotate, middle:pan (scroll=zoom), right:none
   * 'trackpad' = left:rotate, middle:zoom, right:pan
   */
  setMousePreset(preset: 'cad' | 'trackpad'): void {
    if (preset === 'cad') {
      this.setMouseButtons({ left: 'rotate', middle: 'pan', right: 'none' });
      this.invertWheelZoom = true;
      this.mousePreset = 'cad';
    } else if (preset === 'trackpad') {
      this.setMouseButtons({ left: 'rotate', middle: 'zoom', right: 'pan' });
      this.invertWheelZoom = false;
      this.mousePreset = 'trackpad';
    }
  }

  /**
   * P1-3: Set camera field of view.
   */
  setFov(fov: number): void {
    const clampedFov = Math.max(10, Math.min(120, fov));
    this.camera.fov = clampedFov;
    this.camera.updateProjectionMatrix();
  }

  /**
   * Get current FOV.
   */
  getFov(): number {
    return this.camera.fov;
  }

  getConfig(): Record<string, unknown> {
    return {
      rotate_sensitivity: this.controls.rotateSpeed,
      pan_sensitivity: this.controls.panSpeed,
      zoom_sensitivity: this.zoomSensitivity,
      zoom_to_cursor: this.zoomToCursorEnabled,
      orbit_enabled: this.controls.enableRotate,
      pan_enabled: this.controls.enablePan,
      zoom_enabled: this.zoomEnabled,
      damping: this.controls.enableDamping,
      mouse_preset: this.mousePreset,
      mouse_buttons: { ...this.mouseButtons },
      fov: this.camera.fov,
    };
  }

  /**
   * Provide a live object map for zoom-to-cursor raycasts.
   */
  setObjectsProvider(provider: () => Map<string, THREE.Object3D>): void {
    this.objectsProvider = provider;
  }

  /**
   * Get current zoom-to-cursor setting.
   */
  isZoomToCursorEnabled(): boolean {
    return this.zoomToCursorEnabled;
  }

  /**
   * Fit camera to show all provided objects.
   */
  fitToObjects(objects: THREE.Object3D[]): void {
    if (objects.length === 0) return;

    const box = this.computeFiniteBounds(objects);
    if (!box || box.isEmpty()) return;

    const center = new THREE.Vector3();
    box.getCenter(center);

    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    if (!Number.isFinite(maxDim) || maxDim <= 0) return;
    const distance = maxDim * 2.5;

    // Get current view direction
    const currentDir = this.camera.position.clone().sub(this.controls.target).normalize();

    // Position camera at distance in current direction
    const newPos = center.clone().add(currentDir.multiplyScalar(distance));

    this.animateCamera(
      this.camera.position.clone(),
      newPos,
      this.controls.target.clone(),
      center
    );
  }

  private computeFiniteBounds(objects: Iterable<THREE.Object3D>): THREE.Box3 | null {
    let hasBounds = false;
    const worldBox = new THREE.Box3();
    const localBox = this.tempBox;
    const point = this.tempVec;

    for (const obj of objects) {
      if (!obj || !obj.isObject3D) continue;
      obj.updateWorldMatrix(true, true);
      obj.traverse((child) => {
        const geometry = (child as THREE.Object3D & { geometry?: THREE.BufferGeometry }).geometry;
        const position = geometry?.attributes?.position as THREE.BufferAttribute | undefined;
        if (!position || typeof position.getX !== 'function') return;

        let localHas = false;
        localBox.makeEmpty();
        for (let i = 0; i < position.count; i += 1) {
          const x = position.getX(i);
          const y = position.getY(i);
          const z = position.getZ(i);
          if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
            continue;
          }
          if (!localHas) {
            localBox.min.set(x, y, z);
            localBox.max.set(x, y, z);
            localHas = true;
          } else {
            point.set(x, y, z);
            localBox.expandByPoint(point);
          }
        }

        if (!localHas) return;
        if (child instanceof THREE.InstancedMesh) {
          const baseBox = localBox.clone();
          const instanceMatrix = new THREE.Matrix4();
          localBox.makeEmpty();
          for (let i = 0; i < child.count; i++) {
            child.getMatrixAt(i, instanceMatrix);
            localBox.union(baseBox.clone().applyMatrix4(instanceMatrix));
          }
        }
        localBox.applyMatrix4(child.matrixWorld);
        if (!hasBounds) {
          worldBox.copy(localBox);
          hasBounds = true;
        } else {
          worldBox.union(localBox);
        }
      });
    }

    return hasBounds ? worldBox : null;
  }

  /**
   * Update controls (should be called in animation loop).
   */
  update(): void {
    this.controls.update();
  }

  /**
   * Dispose of resources.
   */
  dispose(): void {
    this.domElement.removeEventListener('wheel', this.wheelHandler);
    this.controls.dispose();
  }
}

import * as THREE from 'three';
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import { GeometryFactory } from './GeometryFactory.js';

export type PerformanceMode = 'quality' | 'balanced' | 'performance';

// Performance mode configurations for WebGL renderer
const PERF_CONFIGS: Record<PerformanceMode, {
  antialias: boolean;
  pixelRatio: number;
  powerPreference: 'high-performance' | 'low-power' | 'default';
}> = {
  quality: {
    antialias: true,
    pixelRatio: typeof window !== 'undefined' ? window.devicePixelRatio : 1,
    powerPreference: 'default',
  },
  balanced: {
    antialias: false,
    pixelRatio: typeof window !== 'undefined' ? Math.min(window.devicePixelRatio, 1.5) : 1,
    powerPreference: 'default',
  },
  performance: {
    antialias: false,
    pixelRatio: 1,
    powerPreference: 'high-performance',
  },
};

export interface SceneManagerOptions {
  container: HTMLElement;
  canvas?: HTMLCanvasElement;
  background?: number;
  cameraFov?: number;
  cameraNear?: number;
  cameraFar?: number;
  initialCameraDistance?: number;
  performanceMode?: PerformanceMode;  // Default: 'balanced'
  debug?: boolean;  // Enable debug logging (default: false)
}

export interface ViewEnvironmentConfig {
  showGrid?: boolean;
  showGround?: boolean;
  showAxes?: boolean;
  gridSize?: number;
  gridDivisions?: number;
  gridColor?: number[];
  gridSubColor?: number[];
  axesLength?: number;
  axesRadius?: number;
  axesSize?: number; // Legacy alias for axesLength
  background?: number[];
}

/**
 * Manages the Three.js scene, camera, renderers, and object storage.
 * Handles scene initialization, object lifecycle, and rendering.
 */
export class SceneManager {
  readonly scene: THREE.Scene;
  readonly camera: THREE.PerspectiveCamera;
  readonly renderer: THREE.WebGLRenderer;
  readonly labelRenderer: CSS2DRenderer;
  readonly container: HTMLElement;

  private static readonly ORIGIN = new THREE.Vector3(0, 0, 0);

  private objects = new Map<string, THREE.Object3D>();
  private buffers = new Map<string, ArrayBuffer>();
  private gridHelper?: THREE.GridHelper;
  private axesHelper?: THREE.Object3D;
  private showGrid: boolean = false;
  private showAxes: boolean = true;
  private debug: boolean = false;
  private adaptiveClipPlanes: boolean = true;  // Disabled when caller sets explicit cameraNear/cameraFar
  private adaptiveFarFloor: number = 1000;
  private envConfig: Required<Pick<ViewEnvironmentConfig, "gridSize" | "gridDivisions" | "axesLength" | "axesRadius">> & {
    gridColor: number;
    gridSubColor: number;
  } = {
    gridSize: 10,
    gridDivisions: 10,
    axesLength: 0.2,
    axesRadius: 0.002,
    gridColor: 0x444444,
    gridSubColor: 0x333333,
  };

  constructor(options: SceneManagerOptions) {
    this.container = options.container;
    this.debug = options.debug ?? false;

    // Ensure container is a positioning context and clips children.
    // Set via JS for reliability (Vue scoped styles may not apply to
    // dynamically-composed component hierarchies in Tauri WebView).
    if (!this.container.style.position || this.container.style.position === 'static') {
      this.container.style.position = 'relative';
    }
    this.container.style.overflow = 'hidden';

    // Initialize scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(options.background ?? 0xffffff);

    // Initialize camera - Z-up coordinate system
    const aspect = this.container.clientWidth / this.container.clientHeight;
    this.camera = new THREE.PerspectiveCamera(
      options.cameraFov ?? 30,  // 30° vFOV: less edge distortion on wide viewports
      aspect,
      options.cameraNear ?? 0.1,
      options.cameraFar ?? 1000
    );
    this.adaptiveFarFloor = this.camera.far;

    // Disable adaptive clip planes if caller explicitly configured cameraNear or cameraFar
    if (options.cameraNear !== undefined || options.cameraFar !== undefined) {
      this.adaptiveClipPlanes = false;
    }

    // Set initial camera position: isometric view from +X+Y+Z looking at origin
    const distance = options.initialCameraDistance ?? 1.5;
    this.camera.position.set(distance, distance, distance);
    this.camera.up.set(0, 0, 1); // Z-axis up
    this.camera.lookAt(0, 0, 0);

    // Initialize WebGL renderer with performance mode and fallback
    const perfMode = options.performanceMode ?? 'balanced';
    this.renderer = this.createRenderer(perfMode, options.canvas);
    // Pass false as 3rd arg: do NOT set inline width/height on the canvas.
    // We set responsive styles below instead.
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight, false);

    // Set canvas display styles directly (more reliable than CSS selectors for
    // dynamically-created elements in Vue scoped/Tauri WebView contexts).
    const canvas = this.renderer.domElement;
    canvas.style.display = 'block';
    canvas.style.position = 'absolute';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';

    if (!options.canvas) {
      this.container.appendChild(canvas);
    }

    // Initialize CSS2D renderer for 2D text overlays
    this.labelRenderer = new CSS2DRenderer();
    this.labelRenderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.labelRenderer.domElement.style.position = 'absolute';
    this.labelRenderer.domElement.style.top = '0px';
    this.labelRenderer.domElement.style.left = '0px';
    this.labelRenderer.domElement.style.width = '100%';
    this.labelRenderer.domElement.style.height = '100%';
    this.labelRenderer.domElement.style.pointerEvents = 'none';
    this.container.appendChild(this.labelRenderer.domElement);

    // Setup default lighting
    this.setupLighting();

    // Setup scene helpers
    this.setupHelpers();
  }

  /**
   * Create WebGL renderer with fallback configurations.
   * Tries progressively less demanding configs for Intel/integrated GPU compatibility.
   */
  private createRenderer(perfMode: PerformanceMode, externalCanvas?: HTMLCanvasElement): THREE.WebGLRenderer {
    const config = PERF_CONFIGS[perfMode];

    // Configurations to try, from preferred to fallback
    const configs: THREE.WebGLRendererParameters[] = [
      // Preferred: use performance mode settings
      {
        antialias: config.antialias,
        powerPreference: config.powerPreference,
        failIfMajorPerformanceCaveat: false,
      },
      // Fallback 1: default power preference
      {
        antialias: config.antialias,
        powerPreference: 'default',
        failIfMajorPerformanceCaveat: false,
      },
      // Fallback 2: minimal config (software rendering)
      {
        antialias: false,
        failIfMajorPerformanceCaveat: false,
      },
    ];

    for (const rendererConfig of configs) {
      try {
        const renderer = new THREE.WebGLRenderer({
          ...rendererConfig,
          canvas: externalCanvas
        });
        const gl = renderer.getContext();
        if (gl) {
          renderer.setPixelRatio(config.pixelRatio);
          console.log('[FrameViz] WebGL renderer created:', {
            perfMode,
            antialias: rendererConfig.antialias,
            powerPreference: rendererConfig.powerPreference,
            pixelRatio: config.pixelRatio,
          });
          return renderer;
        }
        renderer.dispose();
      } catch (e) {
        console.warn('[FrameViz] WebGL config failed:', rendererConfig, e);
      }
    }

    throw new Error('[FrameViz] WebGL not supported on this device');
  }


  /**
   * Setup default lighting for the scene.
   * Creates ambient light, directional lights from multiple angles.
   */
  private setupLighting(): void {
    // Ambient light for overall brightness
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);

    // Main directional light
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 10, 7);
    this.scene.add(directionalLight);

    // Fill light from opposite side
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
    fillLight.position.set(-5, -5, 5);
    this.scene.add(fillLight);

    // Top light for better depth perception
    const topLight = new THREE.DirectionalLight(0xffffff, 0.3);
    topLight.position.set(0, 0, 10);
    this.scene.add(topLight);
  }

  /**
   * Setup scene helpers (grid and axes).
   */
  private setupHelpers(): void {
    // Grid helper - rotated for Z-up coordinate system
    this.gridHelper = new THREE.GridHelper(
      this.envConfig.gridSize,
      this.envConfig.gridDivisions,
      this.envConfig.gridColor,
      this.envConfig.gridSubColor
    );
    this.gridHelper.rotation.x = Math.PI / 2; // Rotate to Z-up
    this.gridHelper.visible = this.showGrid;
    this.scene.add(this.gridHelper);

    // Axes helper (RGB = XYZ) - match primitive axes style
    this.axesHelper = this.createAxesHelper();
    this.axesHelper.visible = this.showAxes;
    this.scene.add(this.axesHelper);
  }

  private createAxesHelper(): THREE.Object3D {
    const length = this.envConfig.axesLength;
    const radius = this.envConfig.axesRadius;
    const group = new THREE.Group();
    group.userData.isViewAxesHelper = true;
    const geometryFactory = new GeometryFactory();
    const axes: Array<{ color: number; axis: "x" | "y" | "z" }> = [
      { color: 0xff0000, axis: "x" },
      { color: 0x00ff00, axis: "y" },
      { color: 0x0000ff, axis: "z" },
    ];

    for (const axisInfo of axes) {
      const geometry = geometryFactory.buildAxisGeometry(length, radius, axisInfo.axis);
      const material = new THREE.MeshStandardMaterial({ color: axisInfo.color });
      const mesh = new THREE.Mesh(geometry, material);
      group.add(mesh);
    }

    return group;
  }

  setEnvironment(config: ViewEnvironmentConfig): void {
    if (config.background) {
      const c = config.background;
      this.scene.background = new THREE.Color(c[0], c[1], c[2]);
    }
    const showGrid = config.showGrid ?? config.showGround;
    if (showGrid !== undefined && this.gridHelper) {
      this.showGrid = showGrid;
      this.gridHelper.visible = this.showGrid;
    }
    if (config.showAxes !== undefined && this.axesHelper) {
      this.showAxes = config.showAxes;
      this.axesHelper.visible = this.showAxes;
    }

    let rebuildGrid = false;
    if (config.gridSize !== undefined) {
      this.envConfig.gridSize = config.gridSize;
      rebuildGrid = true;
    }
    if (config.gridDivisions !== undefined) {
      this.envConfig.gridDivisions = config.gridDivisions;
      rebuildGrid = true;
    }
    if (config.gridColor) {
      this.envConfig.gridColor = new THREE.Color(
        config.gridColor[0],
        config.gridColor[1],
        config.gridColor[2]
      ).getHex();
      rebuildGrid = true;
    }
    if (config.gridSubColor) {
      this.envConfig.gridSubColor = new THREE.Color(
        config.gridSubColor[0],
        config.gridSubColor[1],
        config.gridSubColor[2]
      ).getHex();
      rebuildGrid = true;
    }
    if (rebuildGrid) {
      if (this.gridHelper) {
        this.scene.remove(this.gridHelper);
      }
      this.gridHelper = new THREE.GridHelper(
        this.envConfig.gridSize,
        this.envConfig.gridDivisions,
        this.envConfig.gridColor,
        this.envConfig.gridSubColor
      );
      this.gridHelper.rotation.x = Math.PI / 2;
      this.gridHelper.visible = this.showGrid;
      this.scene.add(this.gridHelper);
    }

    let rebuildAxes = false;
    if (config.axesLength !== undefined) {
      this.envConfig.axesLength = config.axesLength;
      rebuildAxes = true;
    } else if (config.axesSize !== undefined) {
      this.envConfig.axesLength = config.axesSize;
      rebuildAxes = true;
    }
    if (config.axesRadius !== undefined) {
      this.envConfig.axesRadius = config.axesRadius;
      rebuildAxes = true;
    }
    if (rebuildAxes) {
      if (this.axesHelper) {
        this.scene.remove(this.axesHelper);
      }
      this.axesHelper = this.createAxesHelper();
      this.axesHelper.visible = this.showAxes;
      this.scene.add(this.axesHelper);
    }
  }

  getEnvironment(): ViewEnvironmentConfig {
    const gridColor = new THREE.Color(this.envConfig.gridColor);
    const gridSubColor = new THREE.Color(this.envConfig.gridSubColor);
    const background = this.scene.background as THREE.Color | null;
    return {
      showGrid: this.showGrid,
      showGround: this.showGrid,
      showAxes: this.showAxes,
      gridSize: this.envConfig.gridSize,
      gridDivisions: this.envConfig.gridDivisions,
      gridColor: [gridColor.r, gridColor.g, gridColor.b],
      gridSubColor: [gridSubColor.r, gridSubColor.g, gridSubColor.b],
      axesLength: this.envConfig.axesLength,
      axesRadius: this.envConfig.axesRadius,
      background: background ? [background.r, background.g, background.b] : undefined,
    };
  }

  /**
   * Add an object to the scene and store it by handle.
   */
  addObject(handle: string, obj: THREE.Object3D): void {
    if (this.objects.has(handle)) {
      // Remove existing object with same handle
      this.removeObject(handle);
    }
    this.objects.set(handle, obj);
    this.scene.add(obj);
    if (this.debug) {
      console.log(`[SceneManager] Added object ${handle}, total objects: ${this.objects.size}, scene children: ${this.scene.children.length}`);
    }
  }

  /**
   * Remove an object from the scene by handle.
   * Note: Caller is responsible for calling disposeObject() if GPU resources need to be released.
   * This avoids double-disposal when caller already disposes (e.g., for CSS labels or performance).
   */
  removeObject(handle: string): void {
    const obj = this.objects.get(handle);
    if (obj) {
      obj.removeFromParent();
      // P3: Removed disposeObject call - caller handles disposal to avoid double traversal
      this.objects.delete(handle);
    }
  }

  /**
   * Recursively dispose GPU resources (geometry, material, textures).
   * This is critical to prevent GPU memory leaks during long-running sessions.
   */
  private disposeObject(obj: THREE.Object3D): void {
    obj.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        // Dispose geometry
        if (child.geometry) {
          child.geometry.dispose();
        }
        // Dispose material(s)
        if (child.material) {
          if (Array.isArray(child.material)) {
            child.material.forEach((mat) => this.disposeMaterial(mat));
          } else {
            this.disposeMaterial(child.material);
          }
        }
      } else if (child instanceof THREE.Line) {
        if (child.geometry) {
          child.geometry.dispose();
        }
        if (child.material) {
          if (Array.isArray(child.material)) {
            child.material.forEach((mat) => this.disposeMaterial(mat));
          } else {
            this.disposeMaterial(child.material);
          }
        }
      } else if (child instanceof THREE.Points) {
        if (child.geometry) {
          child.geometry.dispose();
        }
        if (child.material) {
          if (Array.isArray(child.material)) {
            child.material.forEach((mat) => this.disposeMaterial(mat));
          } else {
            this.disposeMaterial(child.material);
          }
        }
      }
    });
  }

  /**
   * Dispose a material and its textures.
   */
  private disposeMaterial(material: THREE.Material): void {
    material.dispose();
    // Dispose textures if present
    const mat = material as THREE.MeshStandardMaterial;
    if (mat.map) mat.map.dispose();
    if (mat.normalMap) mat.normalMap.dispose();
    if (mat.roughnessMap) mat.roughnessMap.dispose();
    if (mat.metalnessMap) mat.metalnessMap.dispose();
    if (mat.aoMap) mat.aoMap.dispose();
    if (mat.emissiveMap) mat.emissiveMap.dispose();
    if (mat.envMap) mat.envMap.dispose();
  }

  /**
   * Get an object by handle.
   */
  getObject(handle: string): THREE.Object3D | undefined {
    return this.objects.get(handle);
  }

  /**
   * Check if an object exists by handle.
   */
  hasObject(handle: string): boolean {
    return this.objects.has(handle);
  }

  /**
   * Get all object handles.
   */
  getObjectHandles(): string[] {
    return Array.from(this.objects.keys());
  }

  /**
   * Get all objects.
   */
  getObjects(): Map<string, THREE.Object3D> {
    return this.objects;
  }

  /**
   * Store a binary buffer by ID for later use.
   */
  storeBuffer(id: string, data: ArrayBuffer): void {
    this.buffers.set(id, data);
  }

  /**
   * Get a stored buffer by ID.
   */
  getBuffer(id: string): ArrayBuffer | undefined {
    return this.buffers.get(id);
  }

  /**
   * Clear all buffers.
   */
  clearBuffers(): void {
    this.buffers.clear();
  }

  /**
   * Clear all objects from the scene.
   */
  clearScene(): void {
    // Remove and dispose all objects
    for (const [handle, obj] of this.objects) {
      obj.removeFromParent();
      this.disposeObject(obj);
    }
    this.objects.clear();
  }

  /**
   * Dynamically adjust camera near/far clip planes based on distance to scene content.
   * Prevents near-plane clipping when zoomed in close to objects (e.g., point clouds).
   * Skipped when caller explicitly configured cameraNear/cameraFar at construction time.
   */
  updateClipPlanes(controlTarget?: THREE.Vector3): void {
    if (!this.adaptiveClipPlanes) return;
    // Use distance from camera to orbit target as the reference distance.
    // This is more stable than computing scene bounding box every frame.
    const target = controlTarget ?? SceneManager.ORIGIN;
    const distance = this.camera.position.distanceTo(target);

    // Scale near plane with distance: allows very close zoom without clipping.
    // Clamp to [0.001, 0.1] to avoid z-fighting at large distances and
    // ensure close-up viewing works.
    const near = Math.max(0.001, Math.min(0.1, distance * 0.001));
    // Scale far relative to near to maximize depth buffer precision.
    // The ratio near:far ≈ 1:100000 keeps precision acceptable across all zoom levels.
    const far = Math.max(this.adaptiveFarFloor, near * 100000, distance * 10);

    if (this.camera.near !== near || this.camera.far !== far) {
      this.camera.near = near;
      this.camera.far = far;
      this.camera.updateProjectionMatrix();
    }
  }

  /**
   * Render the scene.
   */
  render(): void {
    this.renderer.render(this.scene, this.camera);
    this.labelRenderer.render(this.scene, this.camera);

    // Debug log every 60 frames (approx 1 sec) - only when debug mode is enabled
    if (this.debug && (this.renderer.info.render.frame % 60) === 0) {
      console.log(`[SceneManager] Render stats: children=${this.scene.children.length}, objects=${this.objects.size}, canvas=${this.renderer.domElement.width}x${this.renderer.domElement.height}`);
    }
  }

  /**
   * Handle window/container resize.
   * @param explicitWidth - Optional explicit width (e.g., from ResizeObserver)
   * @param explicitHeight - Optional explicit height (e.g., from ResizeObserver)
   */
  resize(explicitWidth?: number, explicitHeight?: number): void {
    let width: number;
    let height: number;

    if (explicitWidth != null && explicitHeight != null && explicitWidth > 0 && explicitHeight > 0) {
      width = Math.round(explicitWidth);
      height = Math.round(explicitHeight);
    } else {
      // Use getBoundingClientRect for sub-pixel accuracy; more reliable than
      // clientWidth/Height in some WebView environments (e.g., Tauri).
      const rect = this.container.getBoundingClientRect();
      width = Math.round(rect.width);
      height = Math.round(rect.height);
    }

    if (width === 0 || height === 0) return;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();

    // false = don't set inline CSS styles; canvas display size is CSS-driven
    this.renderer.setSize(width, height, false);
    this.labelRenderer.setSize(width, height);
  }

  /**
   * Dynamically change the performance mode by recreating the renderer.
   * Note: This will cause a brief flicker, but all scene objects are preserved.
   * Returns the new canvas element so callers can rebind event listeners.
   */
  setPerformanceMode(mode: PerformanceMode): HTMLCanvasElement {
    const config = PERF_CONFIGS[mode];

    // Remove old renderer from DOM
    const oldCanvas = this.renderer.domElement;
    const parent = oldCanvas.parentElement;

    // Dispose old renderer
    this.renderer.dispose();

    // Create new renderer with updated performance mode
    const newRenderer = this.createRenderer(mode);
    newRenderer.setSize(this.container.clientWidth, this.container.clientHeight, false);

    // Apply responsive display styles to new canvas
    const newCanvas = newRenderer.domElement;
    newCanvas.style.display = 'block';
    newCanvas.style.position = 'absolute';
    newCanvas.style.top = '0';
    newCanvas.style.left = '0';
    newCanvas.style.width = '100%';
    newCanvas.style.height = '100%';

    // Replace canvas in DOM
    if (parent) {
      parent.replaceChild(newRenderer.domElement, oldCanvas);
    } else {
      this.container.appendChild(newRenderer.domElement);
    }

    // Update reference
    (this as { renderer: THREE.WebGLRenderer }).renderer = newRenderer;

    return newRenderer.domElement;
  }

  /**
   * Dispose all resources.
   */
  dispose(): void {
    this.clearScene();
    this.clearBuffers();
    this.renderer.dispose();
    this.container.removeChild(this.renderer.domElement);
    this.container.removeChild(this.labelRenderer.domElement);
  }
}

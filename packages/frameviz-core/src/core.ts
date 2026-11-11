import { restoreSceneObject } from './snapshot.js';
import * as THREE from "three";
import { GeometryFactory, type Pose, type ColorArray } from "./GeometryFactory.js";
import { LabelManager } from "./LabelManager.js";
import { RenderModeManager } from "./RenderModeManager.js";
import { SceneManager } from "./SceneManager.js";
import { CameraController } from "./CameraController.js";
import { GizmoManager } from "./GizmoManager.js";
import { PickingManager } from "./PickingManager.js";
import { MeshLoader } from "./MeshLoader.js";
import type { CreateViewArgs, CreateViewResult, FrameVizCoreOptions } from "./types.js";
import type { BufferRef } from "@frameviz/protocol";

interface BufferEntry {
  dtype: string;
  shape?: number[];
  size_bytes?: number;
  data: ArrayBuffer | ArrayBufferView | null;
  ranges?: Array<[number, number]>;
  receivedBytes: number;  // Track bytes received for multi-chunk uploads
}

interface PendingRender {
  handle: string;
  bufferIds: string[];
  check: () => boolean;
  execute: () => void;
}

export class FrameVizCore {
  public sceneRevision = 0;
  private sceneCounter = 0;
  private viewCounter = 0;
  private scenes = new Map<string, unknown>();
  private views = new Map<string, { scene_id: string }>();
  private readonly options: FrameVizCoreOptions;
  private readonly debug: boolean;
  private viewId?: string;
  private disposed = false;

  private sceneManager?: SceneManager;
  private geometryFactory?: GeometryFactory;
  private labelManager?: LabelManager;
  private renderModeManager?: RenderModeManager;
  private cameraController?: CameraController;
  private gizmoManager?: GizmoManager;
  private pickingManager?: PickingManager;
  private meshLoader?: MeshLoader;
  private keyboardShortcutsEnabled = true;
  private keydownHandler?: (event: KeyboardEvent) => void;

  private objects = new Map<string, THREE.Object3D>();
  private frames = new Map<string, THREE.Group>();
  private overlays2d = new Map<string, HTMLElement>();
  private buffers = new Map<string, BufferEntry>();
  private pendingRenders: PendingRender[] = [];
  private deferredMutations = new Map<string, Array<[string, Record<string, unknown>]>>();
  private pendingLoads = new Map<string, number>();
  private loadTokenCounter = 0;

  constructor(options: FrameVizCoreOptions = {}) {
    this.options = options;
    this.debug = options.debug === true;
    this.viewId = options.viewId;
    this.keyboardShortcutsEnabled = options.keyboardShortcuts !== false;

    if (options.container) {
      this.sceneManager = new SceneManager({
        container: options.container,
        canvas: options.canvas,
        performanceMode: options.performanceMode,
        background: options.background,
      });
      this.geometryFactory = new GeometryFactory();
      this.labelManager = new LabelManager();
      this.renderModeManager = new RenderModeManager();
      this.cameraController = new CameraController({
        camera: this.sceneManager.camera,
        domElement: this.sceneManager.renderer.domElement,
      });
      this.cameraController.setObjectsProvider(() => this.objects);
      this.gizmoManager = new GizmoManager(
        this.sceneManager.camera,
        this.sceneManager.renderer.domElement,
        this.cameraController.controls,
        this.sceneManager.scene
      );
      this.gizmoManager.setTransformChangeCallback((handle, pose) => this.onGizmoTransform(handle, pose));
      this.pickingManager = new PickingManager({
        scene: this.sceneManager.scene,
        camera: this.sceneManager.camera,
        domElement: this.sceneManager.renderer.domElement,
        objects: this.objects,
        viewId: this.viewId,
        onEvent: (name, data) => this.emitEvent(name, data),
      });
    }

    if (this.keyboardShortcutsEnabled) {
      this.enableKeyboardShortcuts();
    }
  }

  acceptRevision(revision: unknown): boolean {
    if (typeof revision !== 'number') return true;
    if (revision < this.sceneRevision) return false;
    this.sceneRevision = revision;
    return true;
  }

  /** Create a scene if needed and return its id. */
  createScene(sceneId?: string): string {
    const id = sceneId ?? `s_${++this.sceneCounter}`;
    if (!this.scenes.has(id)) {
      this.scenes.set(id, {});
    }
    return id;
  }

  /** Create a view and bind it to a scene. */
  createView(args: CreateViewArgs): CreateViewResult {
    const sceneId = this.createScene(args.scene_id);
    const viewId = args.view_id ?? `v_${++this.viewCounter}`;
    this.views.set(viewId, { scene_id: sceneId });
    return { view_id: viewId, scene_id: sceneId };
  }

  getCanvas(): HTMLCanvasElement | undefined {
    return this.options.canvas;
  }

  getSceneManager(): SceneManager | undefined {
    return this.sceneManager;
  }

  setViewId(viewId: string | undefined): void {
    this.viewId = viewId;
    this.pickingManager?.setViewId(viewId);
  }

  getObjectCount(options: { grouped?: boolean } = {}): number {
    const emptyNodes = [...this.frames.values()].filter(frame => frame.userData.emptyNode).length;
    if (!options.grouped) {
      return this.objects.size + emptyNodes;
    }
    const groupIds = new Set<string>();
    let count = emptyNodes;
    for (const obj of this.objects.values()) {
      const groupId = obj.userData?.group_id as string | undefined;
      if (groupId) {
        groupIds.add(groupId);
      } else {
        count += 1;
      }
    }
    return count + groupIds.size;
  }

  resize(width?: number, height?: number): void {
    this.sceneManager?.resize(width, height);
  }

  clearBuffers(): void {
    this.buffers.clear();
    this.pendingRenders = [];
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.disableKeyboardShortcuts();

    this.clearSceneContents();
    this.clearBuffers();
    this.pendingLoads.clear();
    this.renderModeManager?.dispose();
    this.pickingManager?.dispose();
    this.gizmoManager?.dispose();
    this.cameraController?.dispose();
    this.sceneManager?.dispose();

    this.objects.clear();
    this.overlays2d.clear();
    this.scenes.clear();
    this.views.clear();
    this.viewId = undefined;
    this.sceneManager = undefined;
    this.geometryFactory = undefined;
    this.labelManager = undefined;
    this.renderModeManager = undefined;
    this.cameraController = undefined;
    this.gizmoManager = undefined;
    this.pickingManager = undefined;
    this.meshLoader = undefined;
  }

  setKeyboardShortcutsEnabled(enabled: boolean): void {
    if (this.keyboardShortcutsEnabled === enabled) return;
    this.keyboardShortcutsEnabled = enabled;
    if (enabled) {
      this.enableKeyboardShortcuts();
    } else {
      this.disableKeyboardShortcuts();
    }
  }

  private enableKeyboardShortcuts(): void {
    if (this.keydownHandler || typeof window === "undefined") return;
    this.keydownHandler = (event: KeyboardEvent) => {
      if (!this.sceneManager || !this.cameraController) return;
      if (!this.keyboardShortcutsEnabled) return;

      const target = event.target as HTMLElement | null;
      if (target?.isContentEditable) return;
      if (target && target.tagName === "TEXTAREA") return;
      if (target && target.tagName === "SELECT") return;
      if (target && target.tagName === "INPUT") {
        const input = target as HTMLInputElement;
        if (input.type && input.type.toLowerCase() !== "range") {
          return;
        }
      }

      const key = event.key.toLowerCase();
      if (!event.ctrlKey && !event.metaKey) {
        if (key === " ") {
          event.preventDefault();
          this.cameraController.resetView(this.objects);
        } else if (key === "w") {
          this.renderModeManager?.cycleRenderMode(this.objects);
        }
        return;
      }

      if (event.ctrlKey || event.metaKey) {
        const viewMap: Record<string, string> = {
          "0": "home",
          "1": "front",
          "2": "left",
          "3": "top",
          "4": "back",
          "5": "right",
          "6": "bottom",
        };
        const view = viewMap[key];
        if (view) {
          event.preventDefault();
          const fitAll = key === "0";
          this.cameraController.setView(view as any, fitAll, this.objects);
        }
      }
    };
    window.addEventListener("keydown", this.keydownHandler);
  }

  private disableKeyboardShortcuts(): void {
    if (!this.keydownHandler || typeof window === "undefined") return;
    window.removeEventListener("keydown", this.keydownHandler);
    this.keydownHandler = undefined;
  }

  handleCommand(name: string, args: Record<string, unknown>, result: Record<string, unknown> = {}): void {
    const deferredHandle = args.handle as string;
    if (deferredHandle && !this.objects.has(deferredHandle) &&
        (this.pendingLoads.has(deferredHandle) || this.pendingRenders.some(p => p.handle === deferredHandle)) &&
        ['set_color', 'set_alpha'].includes(name)) {
      const changes = this.deferredMutations.get(deferredHandle) ?? [];
      // Only the latest value of each property matters while loading.
      this.deferredMutations.set(deferredHandle, [...changes.filter(([n]) => n !== name), [name, args]]);
      return;
    }
    if (this.debug) {
      console.log(`[FrameVizCore] handleCommand: ${name}`, { args, result });
    }
    if (!this.sceneManager || !this.geometryFactory) {
      console.warn('[FrameVizCore] Cannot handle command: sceneManager or geometryFactory not initialized');
      return;
    }

    const created = result.handle as string | undefined;
    if (created && [
      "add_node", "add_primitive", "add_points", "add_lines", "add_mesh",
      "add_instances", "load_mesh", "add_text_3d",
    ].includes(name)) {
      this.createFrame(created, args, name === "add_node");
    }

    switch (name) {
      case "add_node":
      case "set_object_metadata":
        // Metadata is authoritative on Host and accompanies interaction events.
        return;
      case "create_buffer": {
        const bufferId = (result as { buffer_id?: string }).buffer_id ?? (args.buffer_id as string);
        if (!bufferId) return;
        this.buffers.set(bufferId, {
          dtype: args.dtype as string,
          shape: args.shape as number[] | undefined,
          size_bytes: args.size_bytes as number | undefined,
          data: null,
          receivedBytes: 0,  // Initialize to 0, incremented by storeBufferData
        });
        return;
      }
      case "free_buffer": {
        if (result.retained === true) return;
        const bufferId = args.buffer_id as string;
        this.buffers.delete(bufferId);
        this.removePendingRendersForBuffer(bufferId);
        return;
      }
      case "add_primitive": {
        const handle = (result as { handle?: string }).handle;
        if (!handle) return;
        if (this.objects.has(handle)) return;
        const ptype = args.type as string;
        const params = (args.params as Record<string, unknown>) || {};
        const color = this.toColorArray(args.color as number[] | undefined);
        if (ptype === "text_3d") {
          if (!this.labelManager) return;
          const text = (params.text as string) ?? "";
          const height = typeof params.height === "number" ? params.height : undefined;
          const r = Math.round(color[0] * 255);
          const g = Math.round(color[1] * 255);
          const b = Math.round(color[2] * 255);
          const a = color.length >= 4 ? color[3] ?? 1 : 1;
          const cssColor = a < 1 ? `rgba(${r},${g},${b},${a})` : `rgb(${r},${g},${b})`;
          const label = this.labelManager.create3DText(text, [0, 0, 0], {
            color: cssColor,
            fontSize: height,
          });
          label.userData.handle = handle;
          label.userData.scene_id = args.scene_id;
          this.putDrawable(handle, label);
          return;
        }
        const shape = this.geometryFactory.createPrimitive(ptype as any, params, color);
        const obj = ptype === "arrow" && params.start && params.end ? new THREE.Group().add(shape) : shape;
        obj.userData.handle = handle;
        obj.userData.scene_id = args.scene_id;
          if (args.group_id) obj.userData.group_id = args.group_id;
        this.putDrawable(handle, obj);
        return;
      }
      case "add_points": {
        const handle = result.handle as string;
        if (!handle) return;
        const chunks = args.chunks as Array<{ positions: BufferRef; colors?: BufferRef }> | undefined;
        const parts = chunks ?? [{ positions: args.positions as BufferRef, colors: args.colors as BufferRef | undefined }];
        const size = (args.size as number) ?? 1;
        const color = this.toColorArray(args.color as number[] | undefined);
        const refs = parts.flatMap(part => part.colors ? [part.positions, part.colors] : [part.positions]);
        this.enqueueIfMissingBuffers(handle, refs, () => {
          let offset = 0;
          const points = parts.map(part => {
            const positions = this.getBufferTypedArray(part.positions) as Float32Array;
            const colors = part.colors ? this.getBufferTypedArray(part.colors) as Uint8Array : undefined;
            const points = this.geometryFactory!.createPoints(positions, colors, size, colors ? undefined : color);
            points.userData.pointOffset = offset;
            points.userData.hasVertexColors = Boolean(colors);
            offset += points.geometry.attributes.position.count;
            return points;
          });
          const obj = chunks ? new THREE.Group().add(...points) : points[0];
          obj.userData.handle = handle;
          obj.userData.scene_id = args.scene_id;
          obj.userData.group_id = args.group_id;
          obj.userData.colorBufferIds = parts.flatMap(part => part.colors ? [part.colors.buffer_id] : []);
          obj.userData.hasVertexColors = parts.some(part => part.colors);
          this.putDrawable(handle, obj);
        });
        return;
      }
      case "add_lines": {
        const handle = (result as { handle?: string }).handle;
        if (!handle) return;
        const posRef = args.positions as BufferRef;
        const idxRef = args.indices as BufferRef | undefined;
        const width = (args.width as number) ?? 1;
        const color = this.toColorArray(args.color as number[] | undefined);
        this.enqueueIfMissingBuffers(handle, [posRef, idxRef].filter(Boolean) as BufferRef[], () => {
          const positions = this.getBufferTypedArray(posRef) as Float32Array;
          const indices = idxRef ? (this.getBufferTypedArray(idxRef) as Uint32Array) : undefined;
          const obj = this.geometryFactory!.createLines(positions, color, width, indices);
          obj.userData.handle = handle;
          obj.userData.scene_id = args.scene_id;
          if (args.group_id) obj.userData.group_id = args.group_id;
          this.putDrawable(handle, obj);
        });
        return;
      }
      case "add_mesh": {
        const handle = (result as { handle?: string }).handle;
        if (!handle) return;
        const vertRef = args.vertices as BufferRef;
        const facesFormat = (args.faces_format as string | undefined) ?? "tri";
        const faceRef = facesFormat === "tri" ? (args.faces as BufferRef) : undefined;
        const polyFaces = facesFormat === "poly" ? (args.faces as { counts: BufferRef; indices: BufferRef }) : undefined;
        const normRef = args.normals as BufferRef | undefined;
        const colorRef = args.colors as BufferRef | undefined;
        const color = args.color as ColorArray | undefined;
        const alpha = args.alpha as number | undefined;
        const wireframe = args.wireframe as boolean | undefined;
        const smoothShading = (args.smooth_shading as boolean | undefined) ?? true;
        const requiredRefs = [vertRef, faceRef, normRef, colorRef].filter(Boolean) as BufferRef[];
        if (polyFaces) {
          requiredRefs.push(polyFaces.counts, polyFaces.indices);
        }
        this.enqueueIfMissingBuffers(handle, requiredRefs, () => {
          const vertices = this.getBufferTypedArray(vertRef) as Float32Array;
          let faces: Uint32Array;
          if (facesFormat === "poly" && polyFaces) {
            const counts = this.getBufferTypedArray(polyFaces.counts) as Uint32Array;
            const indices = this.getBufferTypedArray(polyFaces.indices) as Uint32Array;
            const colorsArray = colorRef ? (this.getBufferTypedArray(colorRef) as Uint8Array) : undefined;
            const useFaceColors = Boolean(colorsArray && colorsArray.length === counts.length * 3);
            const triResult = this.triangulatePolyFaces(
              vertices,
              counts,
              indices,
              useFaceColors ? colorsArray : undefined
            );
            faces = triResult.faces;
            const normals = normRef ? (this.getBufferTypedArray(normRef) as Float32Array) : undefined;
            const colors = useFaceColors ? triResult.faceColors : colorsArray;
            const obj = this.geometryFactory!.createMesh(
              vertices,
              faces,
              normals,
              colors,
              color,
              alpha,
              wireframe,
              smoothShading
            );
            if (colors) {
              obj.userData.hasVertexColors = true;
            }
            obj.userData.colorBufferId = colorRef?.buffer_id;
          obj.userData.handle = handle;
            obj.userData.scene_id = args.scene_id;
          if (args.group_id) obj.userData.group_id = args.group_id;
            this.putDrawable(handle, obj);
            return;
          } else {
            faces = this.getBufferTypedArray(faceRef as BufferRef) as Uint32Array;
          }
          const normals = normRef ? (this.getBufferTypedArray(normRef) as Float32Array) : undefined;
          const colors = colorRef ? (this.getBufferTypedArray(colorRef) as Uint8Array) : undefined;
          const obj = this.geometryFactory!.createMesh(
            vertices,
            faces,
            normals,
            colors,
            color,
            alpha,
            wireframe,
            smoothShading
          );
          if (colors) {
            obj.userData.hasVertexColors = true;
          }
          obj.userData.colorBufferId = colorRef?.buffer_id;
          obj.userData.handle = handle;
          obj.userData.scene_id = args.scene_id;
          if (args.group_id) obj.userData.group_id = args.group_id;
          this.putDrawable(handle, obj);
        });
        return;
      }
      case "add_instances": {
        const handle = (result as { handle?: string }).handle;
        if (!handle) return;
        const positionsRef = args.positions as BufferRef;
        const quatsRef = args.quats as BufferRef | undefined;
        const scalesRef = args.scales as BufferRef | undefined;
        const colorsRef = args.colors as BufferRef | undefined;
        const requiredRefs = [positionsRef, quatsRef, scalesRef, colorsRef].filter(Boolean) as BufferRef[];
        this.enqueueIfMissingBuffers(handle, requiredRefs, () => {
          const positions = this.getBufferTypedArray(positionsRef) as Float32Array;
          const quats = quatsRef ? (this.getBufferTypedArray(quatsRef) as Float32Array) : undefined;
          const scales = scalesRef ? (this.getBufferTypedArray(scalesRef) as Float32Array) : undefined;
          const colors = colorsRef ? (this.getBufferTypedArray(colorsRef) as Uint8Array) : undefined;
          const obj = this.createInstancedObject(
            args.type as string,
            args.params as Record<string, unknown> | undefined,
            positions,
            quats,
            scales,
            colors,
            args.color as number[] | undefined,
            args.alpha as number | undefined
          );
          if (!obj) return;
          obj.userData.instanceArgs = { ...args };
          obj.userData.colorBufferId = colorsRef?.buffer_id;
          obj.userData.handle = handle;
          obj.userData.scene_id = args.scene_id;
          if (args.group_id) obj.userData.group_id = args.group_id;
          this.putDrawable(handle, obj);
        });
        return;
      }
      case "update_instances": {
        const handle = args.handle as string;
        const previous = this.objects.get(handle);
        if (!previous?.userData.instanceArgs) return;
        const merged = { ...previous.userData.instanceArgs, ...args };
        const refs = [merged.positions, merged.quats, merged.scales, merged.colors].filter(Boolean) as BufferRef[];
        this.enqueueIfMissingBuffers(handle, refs, () => {
          const typed = (ref: BufferRef | undefined) => ref ? this.getBufferTypedArray(ref) : undefined;
          const next = this.createInstancedObject(merged.type, merged.params,
            typed(merged.positions) as Float32Array, typed(merged.quats) as Float32Array,
            typed(merged.scales) as Float32Array, typed(merged.colors) as Uint8Array,
            merged.color, merged.alpha, previous);
          if (!next) return;
          if (next === previous) {
            previous.userData.instanceArgs = merged;
            previous.userData.colorBufferId = merged.colors?.buffer_id;
            return;
          }
          const oldMeshes: THREE.Mesh[] = [];
          previous.traverse(child => { if ((child as THREE.Mesh).material) oldMeshes.push(child as THREE.Mesh); });
          let materialIndex = 0;
          next.traverse(child => {
            const mesh = child as THREE.Mesh;
            if (!mesh.material) return;
            const source = oldMeshes[materialIndex++];
            if (!source || args.colors) return;
            for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) material.dispose();
            mesh.material = Array.isArray(source.material) ? source.material.map(m => m.clone()) : source.material.clone();
          });
          next.position.copy(previous.position); next.quaternion.copy(previous.quaternion);
          next.scale.copy(previous.scale); next.visible = previous.visible;
          next.userData = { ...previous.userData, instanceArgs: merged, colorBufferId: merged.colors?.buffer_id };
          this.sceneManager!.removeObject(handle);
          this.disposeObject(previous);
          this.putDrawable(handle, next);
          if (this.gizmoManager?.getAttachedHandle() === handle) this.gizmoManager.attach(next, handle);
          this.pickingManager?.clearHighlight();
          this.renderModeManager?.cleanupHelpers(this.objects);
          this.renderModeManager?.setRenderMode(this.renderModeManager.getCurrentMode(), this.objects);
        });
        return;
      }
      case "load_mesh": {
        const handle = (result as { handle?: string }).handle;
        if (!handle) return;
        if (this.objects.has(handle)) return;
        const url = args.url as string;

        const color = args.color as number[] | undefined;
        if (!this.meshLoader) {
          this.meshLoader = new MeshLoader();
        }
        const token = ++this.loadTokenCounter;
        this.pendingLoads.set(handle, token);
        this.meshLoader
          .load(url, { color: color ? [color[0], color[1], color[2]] : undefined })
          .then((obj) => {
            if (this.pendingLoads.get(handle) !== token) {
              this.disposeObject(obj);
              return;
            }
            this.pendingLoads.delete(handle);
            if (this.objects.has(handle)) return;
            obj.userData.handle = handle;
            obj.userData.scene_id = args.scene_id;
          if (args.group_id) obj.userData.group_id = args.group_id;
            this.putDrawable(handle, obj);
            this.replayDeferred(handle);
            this.emitEvent('object_ready', { handle, view_id: this.viewId });
          })
          .catch((err) => {
            console.error("[FrameViz] load_mesh failed:", err);
            if (this.pendingLoads.get(handle) === token) {
              this.pendingLoads.delete(handle);
              this.deferredMutations.delete(handle);
              this.emitEvent('object_failed', { handle, view_id: this.viewId, message: String(err) });
            }
          });
        return;
      }
      case "set_transform": {
        this.setFramePose(args.handle as string, args);
        return;
      }
      case "set_geometry_scale": {
        this.setFramePose(args.handle as string, args);
        return;
      }
      case "set_parent": {
        const handle = args.handle as string;
        const frame = this.frames.get(handle);
        const parent = this.frameParent(result.parent ?? args.parent);
        if (!frame || !parent || parent === frame) return;
        parent.add(frame);
        const drawable = this.objects.get(handle);
        if (drawable) parent.add(drawable);
        this.setFramePose(handle, { pose: result.pose ?? args.local_transform });
        return;
      }
      case "set_object_transforms": {
        const items = args.items as Array<Record<string, unknown>>;
        if (Array.isArray(items)) {
          for (const item of items) this.setFramePose(item.handle as string, item);
        }
        return;
      }
      case "set_object_colors": {
        const items = args.items as Array<{ handle: string; rgba: number[] }>;
        if (Array.isArray(items)) {
          for (const item of items) {
            this.handleCommand("set_color", item);
          }
        }
        return;
      }
      case "set_object_alphas": {
        const items = args.items as Array<{ handle: string; alpha: number }>;
        if (Array.isArray(items)) {
          for (const item of items) {
            this.handleCommand("set_alpha", item);
          }
        }
        return;
      }
      case "set_object_visibilities": {
        const items = args.items as Array<{ handle: string; visible: boolean }>;
        if (Array.isArray(items)) {
          for (const item of items) {
            this.handleCommand("set_visible", item);
          }
        }
        return;
      }
      case "set_color": {
        const handle = args.handle as string;
        const rgba = (args.rgba as number[]) || (args.color as number[]);
        if (!rgba) return;
        const target = (args.target as string) || "scene";
        if (target === "overlay") {
          const overlay = this.overlays2d.get(handle);
          if (overlay) {
            const r = Math.round(rgba[0] * 255);
            const g = Math.round(rgba[1] * 255);
            const b = Math.round(rgba[2] * 255);
            const a = rgba.length >= 4 ? rgba[3] ?? 1 : 1;
            overlay.style.color = a < 1 ? `rgba(${r},${g},${b},${a})` : `rgb(${r},${g},${b})`;
          }
          return;
        }
        const obj = this.objects.get(handle);
        if (obj) {
          const instanceArgs = obj.userData.instanceArgs;
          if (instanceArgs) {
            obj.userData.instanceArgs = { ...instanceArgs, color: rgba, alpha: rgba[3] ?? 1 };
            delete obj.userData.instanceArgs.colors;
            obj.traverse(child => { if ((child as THREE.InstancedMesh).isInstancedMesh) (child as THREE.InstancedMesh).instanceColor = null; });

          }
          const removedColors: string[] = obj.userData.colorBufferIds ??
            (obj.userData.colorBufferId ? [obj.userData.colorBufferId] : []);
          if (removedColors.length > 0) {
            const ids: string[] = [...(obj.userData.bufferIds ?? [])];
            for (const id of removedColors) {
              const index = ids.lastIndexOf(id);
              if (index >= 0) ids.splice(index, 1);
            }
            obj.userData.bufferIds = ids;
            delete obj.userData.colorBufferId;
            delete obj.userData.colorBufferIds;
            this.releaseUnusedBuffers(removedColors);
          }
          const cssLabel = obj as THREE.Object3D & { isCSS2DObject?: boolean; element?: HTMLElement };
          const div = (cssLabel.element || (cssLabel as any).userData?.div) as HTMLDivElement | undefined;
          if (cssLabel.isCSS2DObject || div) {
            if (div) {
              const r = Math.round(rgba[0] * 255);
              const g = Math.round(rgba[1] * 255);
              const b = Math.round(rgba[2] * 255);
              const a = rgba.length >= 4 ? rgba[3] ?? 1 : 1;
              div.style.color = a < 1 ? `rgba(${r},${g},${b},${a})` : `rgb(${r},${g},${b})`;
            }
            return;
          }
          // Convert vertex-colored geometry to uniform color when needed
          if (obj.userData.hasVertexColors === true) {
            if (obj instanceof THREE.Mesh) {
              this.convertMeshToUniformColor(obj, rgba);
            } else if (obj instanceof THREE.Points) {
              this.convertPointsToUniformColor(obj, rgba);
            } else {
              obj.traverse(child => {
                if (child instanceof THREE.Points && child.userData.hasVertexColors) {
                  this.convertPointsToUniformColor(child, rgba);
                  child.userData.hasVertexColors = false;
                }
              });
              this.applyColor(obj, rgba);
            }
            obj.userData.hasVertexColors = false;
          } else {
            this.applyColor(obj, rgba);
          }
        }
        return;
      }
      case "set_alpha": {
        const handle = args.handle as string;
        const alpha = args.alpha as number;
        if (typeof alpha !== "number" || isNaN(alpha) || alpha < 0 || alpha > 1) return;
        const obj = this.objects.get(handle);
        if (obj) {
          this.applyAlpha(obj, alpha);
          if (obj.userData.instanceArgs) obj.userData.instanceArgs.alpha = alpha;
        }
        return;
      }
      case "get_color": {
        const handle = args.handle as string;
        const obj = this.objects.get(handle);
        if (!obj) return;

        // Check if mesh has vertex colors
        if (obj.userData.hasVertexColors === true) {
          (result as { has_vertex_colors: boolean }).has_vertex_colors = true;
          return;
        }

        const colorData = this.extractColorFromObject(obj);
        (result as { rgba: number[] }).rgba = colorData.rgba;
        return;
      }
      case "get_alpha": {
        const handle = args.handle as string;
        const obj = this.objects.get(handle);
        if (!obj) return;
        const alpha = this.extractAlphaFromObject(obj);
        (result as { alpha: number }).alpha = alpha;
        return;
      }
      case "set_visible": {
        const handle = args.handle as string;
        const obj = this.objects.get(handle);
        const target = (args.target as string) || "scene";
        if (target === "overlay") {
          const overlay = this.overlays2d.get(handle);
          if (overlay) {
            overlay.style.display = args.visible === false ? "none" : "";
          }
          return;
        }
        const visible = Boolean(args.visible);
        const frame = this.frames.get(handle);
        if (frame) frame.visible = visible;
        if (obj) {
          obj.visible = visible;
          (obj as THREE.Object3D & { userData: { userVisible?: boolean } }).userData.userVisible = visible;
          // Re-apply current render mode so points helpers respect visibility.
          if (this.renderModeManager) {
            this.renderModeManager.setRenderMode(this.renderModeManager.getCurrentMode(), this.objects);
          }
        }
        return;
      }
      case "set_view": {
        const view = (args.view as string) || "home";
        const fitAll = (args.fit_all as boolean | undefined) !== false;
        this.cameraController?.setView(view as any, fitAll, this.objects);
        return;
      }
      case "reset_camera": {
        const mode = (args.mode as string) || "fit_scene";
        if (mode === "fit_object") {
          const handle = args.fit_handle as string | undefined;
          const obj = handle ? this.objects.get(handle) : undefined;
          if (obj) {
            this.cameraController?.fitToObjects([obj]);
            return;
          }
        }
        this.cameraController?.resetView(this.objects);
        return;
      }
      case "set_render_mode": {
        const mode = (args.mode as string) || "solid";
        this.renderModeManager?.setRenderMode(mode as any, this.objects);
        return;
      }
      case "set_performance_mode": {
        const mode = (args.mode as 'performance' | 'balanced' | 'quality') || 'balanced';
        if (!this.sceneManager) return;

        // Save current camera state before rebuilding
        let savedCameraState: { position: THREE.Vector3; target: THREE.Vector3; up: THREE.Vector3 } | null = null;
        if (this.cameraController) {
          const camera = this.sceneManager.camera;
          const target = this.cameraController.controls.target.clone();
          savedCameraState = {
            position: camera.position.clone(),
            target: target,
            up: camera.up.clone(),
          };
        }

        const newCanvas = this.sceneManager.setPerformanceMode(mode);

        // Rebind CameraController to new canvas
        if (this.cameraController) {
          this.cameraController.dispose();
          this.cameraController = new CameraController({
            camera: this.sceneManager.camera,
            domElement: newCanvas,
          });
          this.cameraController.setObjectsProvider(() => this.objects);

          // Restore camera state
          if (savedCameraState) {
            const camera = this.sceneManager.camera;
            camera.position.copy(savedCameraState.position);
            camera.up.copy(savedCameraState.up);
            this.cameraController.controls.target.copy(savedCameraState.target);
            this.cameraController.controls.update();
          }
        }

        // Rebind GizmoManager to new canvas
        if (this.gizmoManager) {
          this.gizmoManager.dispose();
          this.gizmoManager = new GizmoManager(
            this.sceneManager.camera,
            newCanvas,
            this.cameraController!.controls,
            this.sceneManager.scene
          );
          this.gizmoManager.setTransformChangeCallback((handle, pose) => this.onGizmoTransform(handle, pose));
        }

        // Rebind PickingManager to new canvas
        if (this.pickingManager) {
          this.pickingManager.dispose();
          this.pickingManager = new PickingManager({
            scene: this.sceneManager.scene,
            camera: this.sceneManager.camera,
            domElement: newCanvas,
            objects: this.objects,
            viewId: this.viewId,
            onEvent: (name, data) => this.emitEvent(name, data),
          });
        }

        return;
      }
      case "set_camera_pose": {
        const eye = args.eye as number[] | undefined;
        const target = args.target as number[] | undefined;
        const up = args.up as number[] | undefined;
        if (this.cameraController && eye && target) {
          const camera = this.cameraController.controls.object;
          camera.position.set(eye[0], eye[1], eye[2]);
          if (up && up.length >= 3) {
            camera.up.set(up[0], up[1], up[2]);
          }
          this.cameraController.controls.target.set(target[0], target[1], target[2]);
          this.cameraController.controls.update();
        }
        return;
      }
      case "set_camera_controls": {
        if (this.cameraController) {
          const controls = this.cameraController.controls;
          const cfg = args as Record<string, unknown>;
          if (cfg.rotate_sensitivity !== undefined) controls.rotateSpeed = cfg.rotate_sensitivity as number;
          if (cfg.pan_sensitivity !== undefined) controls.panSpeed = cfg.pan_sensitivity as number;
          if (cfg.zoom_sensitivity !== undefined) {
            this.cameraController.setZoomSensitivity(cfg.zoom_sensitivity as number);
          }
          if (cfg.zoom_to_cursor !== undefined) {
            this.cameraController.setZoomToCursor(Boolean(cfg.zoom_to_cursor));
          }
          if (cfg.orbit_enabled !== undefined) {
            this.cameraController.setOrbitEnabled(Boolean(cfg.orbit_enabled));
          }
          if (cfg.pan_enabled !== undefined) {
            this.cameraController.setPanEnabled(Boolean(cfg.pan_enabled));
          }
          if (cfg.zoom_enabled !== undefined) {
            this.cameraController.setZoomEnabled(Boolean(cfg.zoom_enabled));
          }
          // P1-1: Damping control
          if (cfg.damping !== undefined) {
            this.cameraController.setDamping(Boolean(cfg.damping));
          }
          // P1-2: Mouse button mapping
          if (cfg.mouse_preset !== undefined) {
            this.cameraController.setMousePreset(cfg.mouse_preset as 'cad' | 'trackpad');
          }
          if (cfg.mouse_buttons !== undefined) {
            this.cameraController.setMouseButtons(cfg.mouse_buttons as {
              left?: 'rotate' | 'pan' | 'zoom' | 'none';
              middle?: 'rotate' | 'pan' | 'zoom' | 'none';
              right?: 'rotate' | 'pan' | 'zoom' | 'none';
            });
          }
          // P1-3: FOV control
          if (cfg.fov !== undefined) {
            this.cameraController.setFov(cfg.fov as number);
          }
        }
        return;
      }
      case "get_camera_controls": {
        if (!this.cameraController) return;
        const cfg = this.cameraController.getConfig();
        (result as { config?: Record<string, unknown> }).config = cfg as Record<string, unknown>;
        return;
      }
      case "set_keyboard_shortcuts": {
        const enabled = args.enabled as boolean | undefined;
        if (enabled !== undefined) {
          this.setKeyboardShortcutsEnabled(Boolean(enabled));
        }
        return;
      }
      case "attach_gizmo": {
        const handle = args.handle as string;
        const obj = this.objects.get(handle) ?? this.frames.get(handle);
        if (!obj || !this.gizmoManager) return;
        this.gizmoManager.attach(obj, handle, {
          size: args.size as number | undefined,
          mask: args.mask as number | undefined,
          scale_mode: args.scale_mode as 'screen' | 'world' | undefined,
        });
        return;
      }
      case "set_gizmo_mode": {
        if (!this.gizmoManager) return;
        if (args.mask !== undefined || args.size !== undefined || args.scale_mode !== undefined) {
          this.gizmoManager.configure({
            size: args.size as number | undefined,
            mask: args.mask as number | undefined,
            scale_mode: args.scale_mode as 'screen' | 'world' | undefined,
          });
        }
        return;
      }
      case "detach_gizmo": {
        this.gizmoManager?.detach();
        return;
      }
      case "set_pick_config": {
        if (!this.pickingManager) return;
        this.pickingManager.setConfig({
          enabled: args.enabled as boolean | undefined,
          mode: args.mode as any,
          button: args.button as number | undefined,
          ctrl_modifier: args.ctrl_modifier as boolean | undefined,
          highlight_color: args.highlight_color as [number, number, number] | undefined,
          marker_size: args.marker_size as number | undefined,
          point_threshold: args.point_threshold as number | undefined,
          line_threshold: args.line_threshold as number | undefined,
        });
        return;
      }
      case "clear_pick_highlight": {
        this.pickingManager?.clearHighlight();
        return;
      }
      case "get_picked_info": {
        const info = this.pickingManager?.getLastPickInfo();
        this.emitEvent("pick_info_response", {
          request_id: args.request_id,
          view_id: this.viewId,
          ...(info ?? {}),
        });
        return;
      }
      case "get_pick_config": {
        const cfg = this.pickingManager?.getConfig();
        if (cfg) {
          this.emitEvent("pick_config_response", {
          request_id: args.request_id,
            view_id: this.viewId,
            enabled: cfg.enabled,
            mode: cfg.mode,
            button: cfg.button,
            ctrl_modifier: cfg.ctrl_modifier,
            highlight_color: cfg.highlight_color,
            marker_size: cfg.marker_size,
            point_threshold: cfg.point_threshold,
            line_threshold: cfg.line_threshold,
          });
        }
        return;
      }
      case "get_camera_pose": {
        const pose = this.getCameraPose();
        if (pose) {
          this.emitEvent("camera_pose_response", {
          request_id: args.request_id,
            view_id: this.viewId,
            ...pose,
          });
        }
        return;
      }
      case "set_view_config": {
        if (!this.sceneManager) return;
        const config = args.config as Record<string, unknown> | undefined;
        if (config) {
          const axesLength = (config.axes_length ?? config.axes_size) as number | undefined;
          const axesRadius = config.axes_radius as number | undefined;
          this.sceneManager.setEnvironment({
            showGrid: config.show_grid as boolean | undefined,
            showGround: config.show_ground as boolean | undefined,
            showAxes: config.show_axes as boolean | undefined,
            gridColor: config.grid_color as number[] | undefined,
            gridSubColor: config.grid_sub_color as number[] | undefined,
            axesLength,
            axesRadius,
            background: config.background as number[] | undefined,
          });
          const width = config.width as number | undefined;
          const height = config.height as number | undefined;
          if (width && height) {
            this.sceneManager.resize(width, height);
          }
        }
        return;
      }
      case "get_view_config": {
        if (!this.sceneManager) return;
        const env = this.sceneManager.getEnvironment();
        (result as { config?: Record<string, unknown> }).config = {
          show_grid: env.showGrid,
          show_ground: env.showGround,
          show_axes: env.showAxes,
          grid_color: env.gridColor,
          grid_sub_color: env.gridSubColor,
          axes_length: env.axesLength,
          axes_radius: env.axesRadius,
          background: env.background,
        };
        return;
      }
      case "set_interaction_mode": {
        if (args.picking_enabled !== undefined) {
          this.pickingManager?.setConfig({ enabled: Boolean(args.picking_enabled) });
        }
        if (args.gizmo_enabled === false) {
          this.gizmoManager?.detach();
        }
        return;
      }
      case "remove_object":
      case "remove_text_3d":
      case "remove_objects": {
        const roots = name === "remove_objects" ? args.handles as string[] : [args.handle as string];
        const handles = Array.isArray(result.removed) ? result.removed as string[] : this.subtreeHandles(roots);
        for (const handle of handles) this.removeDrawableAndFrame(handle);
        return;
      }
      case "clone_object": {
        const sourceHandle = args.handle as string;
        const handle = (result as { handle?: string }).handle;
        const source = this.objects.get(sourceHandle);
        if (!handle) return;
        if (!source) {
          // Host supplies the clone's state at command time. Loading is independent
          // of the source, so removing either handle cannot strand the other.
          if (result.object) restoreSceneObject(this, result.object);
          return;
        }
        const cloned = source.clone(true);
        cloned.traverse((child) => {
          const mesh = child as THREE.Mesh;
          if (mesh.geometry) mesh.geometry = mesh.geometry.clone();
          if (mesh.material) {
            const cloneMaterial = (material: THREE.Material) => {
              const copy = material.clone();
              for (const key in copy) {
                const value = (copy as any)[key];
                if (value?.isTexture) (copy as any)[key] = value.clone();
              }
              return copy;
            };
            mesh.material = Array.isArray(mesh.material) ? mesh.material.map(cloneMaterial) : cloneMaterial(mesh.material);
          }
        });
        const original = this.frames.get(sourceHandle);
        const record = result.object as Record<string, unknown> | undefined;
        this.createFrame(handle, record ?? {
          parent: original?.parent?.userData.sceneNodeHandle,
          scene_id: source.userData.scene_id,
          pose: { pos: source.position.toArray(), quat: source.quaternion.toArray() },
          geometry_scale: source.scale.toArray(),
        });
        this.frames.get(handle)!.visible = source.userData.userVisible ?? source.visible;
        cloned.userData.handle = handle;
        cloned.userData.scene_id = source.userData.scene_id;
        const groupId = args.group_id as string | undefined;
        if (groupId) {
          cloned.userData.group_id = groupId;
        }
        this.putDrawable(handle, cloned);
        this.emitEvent('object_ready', { handle, view_id: this.viewId });
        return;
      }
      case "clear_scene": {
        this.clearSceneContents();
        return;
      }
      case "destroy_scene": {
        const sceneId = args.scene_id as string | undefined;
        this.clearSceneContents();
        if (sceneId) {
          this.scenes.delete(sceneId);
          for (const [viewId, view] of this.views) {
            if (view.scene_id === sceneId) {
              this.views.delete(viewId);
            }
          }
        }
        return;
      }
      case "destroy_view": {
        const viewId = args.view_id as string | undefined;
        if (viewId) {
          this.views.delete(viewId);
          if (this.viewId === viewId) {
            this.viewId = undefined;
            this.clearSceneContents();
            // Only the owning viewer should signal that local teardown is done.
            this.emitEvent("view_destroyed", { view_id: viewId });
          }
        }
        return;
      }
      case "add_text_3d": {
        const handle = (result as { handle?: string }).handle;
        if (!handle || !this.labelManager) return;
        const text = (args.text as string) || "";
        const pos = (args.pos as [number, number, number]) || [0, 0, 0];
        const label = this.labelManager.create3DText(text, pos, {
          color: args.color
            ? `rgb(${Math.round((args.color as number[])[0] * 255)},${Math.round((args.color as number[])[1] * 255)},${Math.round((args.color as number[])[2] * 255)})`
            : undefined,
          fontSize: args.font_size as number | undefined,
          backgroundColor: args.background_color as string | undefined,
        });
        label.userData.handle = handle;
        label.userData.scene_id = args.scene_id;
        this.putDrawable(handle, label);
        return;
      }
      case "update_text_3d": {
        const pos = args.pos as [number, number, number] | undefined;
        if (pos) this.setFramePose(args.handle as string, { pose: { pos } });
        const label = this.objects.get(args.handle as string);
        if (label && this.labelManager) {
          this.labelManager.updateLabel(label as any, {
            text: args.text as string | undefined,
            pos: args.pos as [number, number, number] | undefined,
            color: args.color as [number, number, number] | undefined,
            fontSize: args.font_size as number | undefined,
          });
        }
        return;
      }
      case "add_text_2d": {
        const handle = (result as { handle?: string }).handle;
        if (!handle) return;
        const overlay = this.options.overlay;
        if (!overlay) return;
        const div = document.createElement("div");
        div.textContent = (args.text as string) || "";
        div.style.position = "absolute";
        div.style.left = `${args.x ?? 0}px`;
        div.style.top = `${args.y ?? 0}px`;
        div.style.fontSize = `${args.font_size ?? 14}px`;
        if (args.color) {
          const color = args.color as number[];
          div.style.color = `rgb(${Math.round(color[0] * 255)},${Math.round(color[1] * 255)},${Math.round(color[2] * 255)})`;
        }
        div.style.whiteSpace = "pre";
        div.style.pointerEvents = "none";
        overlay.appendChild(div);
        this.overlays2d.set(handle, div);
        return;
      }
      case "update_text_2d": {
        const div = this.overlays2d.get(args.handle as string);
        if (!div) return;
        if (args.text !== undefined) div.textContent = args.text as string;
        if (args.x !== undefined) div.style.left = `${args.x}px`;
        if (args.y !== undefined) div.style.top = `${args.y}px`;
        if (args.font_size !== undefined) div.style.fontSize = `${args.font_size}px`;
        if (args.color !== undefined) {
          const color = args.color as number[];
          div.style.color = `rgb(${Math.round(color[0] * 255)},${Math.round(color[1] * 255)},${Math.round(color[2] * 255)})`;
        }
        return;
      }
      case "remove_text_2d": {
        const div = this.overlays2d.get(args.handle as string);
        if (div) {
          div.remove();
          this.overlays2d.delete(args.handle as string);
        }
        return;
      }
      default:
        return;
    }
  }

  storeBufferData(bufferId: string, offsetBytes: number, data: ArrayBuffer | ArrayBufferView): void {
    const entry = this.buffers.get(bufferId);
    if (!entry) {
      return;
    }
    const source = data instanceof ArrayBuffer
      ? new Uint8Array(data)
      : new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    if (!Number.isSafeInteger(offsetBytes) || offsetBytes < 0 || offsetBytes + source.byteLength > (entry.size_bytes ?? Infinity)) {
      throw new RangeError('Buffer chunk is outside the declared allocation');
    }
    if (!entry.data) {
      const totalSize = entry.size_bytes ?? (offsetBytes + source.byteLength);
      entry.data = new Uint8Array(totalSize);
    }
    const targetBuffer = entry.data instanceof ArrayBuffer
      ? new Uint8Array(entry.data)
      : new Uint8Array(entry.data.buffer);
    targetBuffer.set(source, offsetBytes);
    const ranges = [...(entry.ranges ?? []), [offsetBytes, offsetBytes + source.byteLength] as [number, number]].sort((a, b) => a[0] - b[0]);
    entry.ranges = [];
    for (const range of ranges) {
      const last = entry.ranges[entry.ranges.length - 1];
      if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
      else entry.ranges.push([...range]);
    }
    entry.receivedBytes = entry.ranges.reduce((sum, [start, end]) => sum + end - start, 0);
    this.processPendingRenders();
  }

  processPendingRenders(): void {
    const pending = this.pendingRenders;
    this.pendingRenders = [];
    for (const item of pending) {
      if (item.check()) {
        item.execute();
        this.replayDeferred(item.handle);
      } else {
        this.pendingRenders.push(item);
      }
    }
  }

  render(): void {
    if (!this.sceneManager) return;
    this.cameraController?.controls.update();
    this.sceneManager.updateClipPlanes(this.cameraController?.controls.target);
    this.sceneManager.render();
    this.renderModeManager?.cleanupHelpers(this.objects);
  }

  getCameraPose(): { eye: number[]; target: number[]; up: number[] } | null {
    if (!this.sceneManager || !this.cameraController) return null;
    const camera = this.sceneManager.camera;
    const target = this.cameraController.controls.target;
    return {
      eye: [camera.position.x, camera.position.y, camera.position.z],
      target: [target.x, target.y, target.z],
      up: [camera.up.x, camera.up.y, camera.up.z],
    };
  }

  private triangulatePolyFaces(
    vertices: Float32Array,
    counts: Uint32Array,
    indices: Uint32Array,
    faceColors?: Uint8Array
  ): { faces: Uint32Array; faceColors?: Uint8Array } {
    const triangles: number[] = [];
    const expandedColors: number[] | null = faceColors ? [] : null;
    let offset = 0;
    const vertex = (idx: number): [number, number, number] => [
      vertices[idx * 3],
      vertices[idx * 3 + 1],
      vertices[idx * 3 + 2],
    ];
    const sub = (a: [number, number, number], b: [number, number, number]) => [
      a[0] - b[0],
      a[1] - b[1],
      a[2] - b[2],
    ] as [number, number, number];
    const cross = (a: [number, number, number], b: [number, number, number]) => [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0],
    ] as [number, number, number];
    const dot = (a: [number, number, number], b: [number, number, number]) =>
      a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    const norm = (a: [number, number, number]) => Math.sqrt(dot(a, a));
    const normalize = (a: [number, number, number]) => {
      const n = norm(a) || 1;
      return [a[0] / n, a[1] / n, a[2] / n] as [number, number, number];
    };

    for (let f = 0; f < counts.length; f += 1) {
      const count = counts[f];
      if (count < 3 || offset + count > indices.length) {
        console.warn(`[FrameVizCore] triangulatePolyFaces: skipping face ${f} with invalid count (${count}) or out-of-bounds indices`);
        offset += count;
        continue;
      }
      const faceColorOffset = faceColors ? f * 3 : 0;
      const faceR = faceColors ? faceColors[faceColorOffset] : 0;
      const faceG = faceColors ? faceColors[faceColorOffset + 1] : 0;
      const faceB = faceColors ? faceColors[faceColorOffset + 2] : 0;
      const face = indices.subarray(offset, offset + count);
      offset += count;
      if (count === 3) {
        triangles.push(face[0], face[1], face[2]);
        if (expandedColors) {
          expandedColors.push(faceR, faceG, faceB);
        }
        continue;
      }
      let origin = vertex(face[0]);
      let normal: [number, number, number] | null = null;
      for (let i = 1; i + 1 < face.length; i += 1) {
        const v1 = sub(vertex(face[i]), origin);
        const v2 = sub(vertex(face[i + 1]), origin);
        const n = cross(v1, v2);
        if (norm(n) > 1e-8) {
          normal = normalize(n);
          break;
        }
      }
      if (!normal) {
        console.warn(`[FrameVizCore] triangulatePolyFaces: skipping face ${f} - degenerate face (cannot compute normal)`);
        continue;
      }
      const u = normalize(sub(vertex(face[1]), origin));
      const v = normalize(cross(normal, u));
      const coords: number[] = [];
      for (let i = 0; i < face.length; i += 1) {
        const p = sub(vertex(face[i]), origin);
        coords.push(dot(p, u), dot(p, v));
      }
      const contour: THREE.Vector2[] = [];
      for (let i = 0; i < coords.length; i += 2) {
        contour.push(new THREE.Vector2(coords[i], coords[i + 1]));
      }
      const localTris = THREE.ShapeUtils.triangulateShape(contour, []);
      if (!localTris || localTris.length === 0) {
        console.warn(`[FrameVizCore] triangulatePolyFaces: skipping face ${f} - triangulation failed`);
        continue;
      }
      for (const tri of localTris) {
        triangles.push(face[tri[0]], face[tri[1]], face[tri[2]]);
        if (expandedColors) {
          expandedColors.push(faceR, faceG, faceB);
        }
      }
    }
    return {
      faces: new Uint32Array(triangles),
      faceColors: expandedColors ? new Uint8Array(expandedColors) : undefined,
    };
  }

  private createInstancedObject(
    type: string,
    params: Record<string, unknown> | undefined,
    positions: Float32Array,
    quats?: Float32Array,
    scales?: Float32Array,
    colors?: Uint8Array,
    color?: number[],
    alpha?: number,
    existing?: THREE.Object3D
  ): THREE.Object3D | null {
    const count = Math.floor(positions.length / 3);
    if (count <= 0) return null;
    const hasQuat = quats && quats.length >= count * 4;
    const hasScale = scales && scales.length >= count * 3;
    const hasColors = colors && colors.length >= count * 3;

    const makeMaterial = (baseColor?: ColorArray) => {
      const c = baseColor ?? [1, 1, 1];
      const resolvedAlpha = alpha ?? (c.length >= 4 ? c[3] ?? 1 : 1);
      // IMPORTANT: Do NOT set vertexColors when using instanceColor!
      // vertexColors expects geometry.attributes.color (per-vertex colors),
      // but instanceColor is a separate mechanism for per-instance colors.
      // Setting vertexColors: true with instanceColor causes black rendering.
      return new THREE.MeshLambertMaterial({
        color: new THREE.Color(c[0], c[1], c[2]),
        transparent: resolvedAlpha < 1,
        opacity: resolvedAlpha,
        // vertexColors: false (default) - instanceColor works independently
      });
    };

    const applyInstances = (mesh: THREE.InstancedMesh) => {
      const mat = new THREE.Matrix4();
      const pos = new THREE.Vector3();
      const quat = new THREE.Quaternion();
      const scale = new THREE.Vector3();
      const colorObj = new THREE.Color();
      for (let i = 0; i < count; i += 1) {
        pos.set(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]);
        if (hasQuat) {
          quat.set(
            quats![i * 4],
            quats![i * 4 + 1],
            quats![i * 4 + 2],
            quats![i * 4 + 3]
          );
        } else {
          quat.identity();
        }
        if (hasScale) {
          scale.set(scales![i * 3], scales![i * 3 + 1], scales![i * 3 + 2]);
        } else {
          scale.set(1, 1, 1);
        }
        mat.compose(pos, quat, scale);
        mesh.setMatrixAt(i, mat);
        if (hasColors) {
          const r = colors![i * 3] / 255;
          const g = colors![i * 3 + 1] / 255;
          const b = colors![i * 3 + 2] / 255;
          colorObj.setRGB(r, g, b);
          mesh.setColorAt(i, colorObj);
        }
      }
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) {
        mesh.instanceColor.needsUpdate = true;
      }
    };

    if (existing) {
      const meshes: THREE.InstancedMesh[] = [];
      existing.traverse(child => { if ((child as THREE.InstancedMesh).isInstancedMesh) meshes.push(child as THREE.InstancedMesh); });
      if (meshes.length && meshes.every(mesh => mesh.instanceMatrix.count === count)) {
        for (const mesh of meshes) {
          applyInstances(mesh);
          if (!hasColors) mesh.instanceColor = null;
          mesh.computeBoundingBox(); mesh.computeBoundingSphere();
        }
        return existing;
      }
    }
    // When using per-instance colors, material color must be white [1,1,1] to avoid multiplication.
    // If no per-instance colors, use the uniform color parameter.
    const baseColor = hasColors ? undefined : (color ? this.toColorArray(color) : undefined);

    if (type === "box") {
      const size = (params?.size as number[] | undefined) ?? [1, 1, 1];
      const geometry = new THREE.BoxGeometry(size[0], size[1], size[2]);
      const material = makeMaterial(baseColor);
      const mesh = new THREE.InstancedMesh(geometry, material, count);
      applyInstances(mesh);
      return mesh;
    }

    if (type === "sphere") {
      const radius = (params?.radius as number | undefined) ?? 0.5;
      const geometry = new THREE.SphereGeometry(radius, 24, 24);
      const material = makeMaterial(baseColor);
      const mesh = new THREE.InstancedMesh(geometry, material, count);
      applyInstances(mesh);
      return mesh;
    }

    if (type === "axes") {
      const length = (params?.length as number | undefined) ?? 1.0;
      const radius = (params?.radius as number | undefined) ?? 0.02;
      const makeAxis = (colorHex: number, axis: "x" | "y" | "z") => {
        const geometry = this.geometryFactory!.buildAxisGeometry(length, radius, axis);
        const material = new THREE.MeshStandardMaterial({ color: colorHex });
        const mesh = new THREE.InstancedMesh(geometry, material, count);
        applyInstances(mesh);
        return mesh;
      };
      const group = new THREE.Group();
      group.add(makeAxis(0xff0000, "x"));
      group.add(makeAxis(0x00ff00, "y"));
      group.add(makeAxis(0x0000ff, "z"));
      return group;
    }

    return null;
  }

  private emitEvent(name: string, data: Record<string, unknown>): void {
    if (this.options.onEvent) {
      this.options.onEvent(name, data);
    }
  }

  private emitCommand(name: string, args: Record<string, unknown>): void {
    if (this.options.onCommand) {
      this.options.onCommand(name, args);
    }
  }

  private frameParent(parent: unknown): THREE.Object3D | undefined {
    return typeof parent === "string" ? this.frames.get(parent) : this.sceneManager?.scene;
  }

  private createFrame(handle: string, args: Record<string, unknown>, empty = false): void {
    if (this.frames.has(handle)) return;
    const frame = new THREE.Group();
    frame.userData.sceneNodeHandle = handle;
    frame.userData.scene_id = args.scene_id;
    frame.userData.emptyNode = empty;
    this.frames.set(handle, frame);
    this.frameParent(args.parent)?.add(frame);
    this.setFramePose(handle, args);
  }

  private setFramePose(handle: string, args: Record<string, unknown>): void {
    const input = args.pose as (Pose & { position?: Pose["pos"]; quaternion?: Pose["quat"] }) | number[] | undefined;
    const pose: Pose = Array.isArray(input)
      ? { pos: [input[0], input[1], input[2]], quat: [input[3], input[4], input[5], input[6]] }
      : { pos: input?.position ?? input?.pos ?? args.pos as Pose["pos"], quat: input?.quaternion ?? input?.quat };
    const scale = (args.geometry_scale ?? (Array.isArray(input) ? undefined : input?.scale) ?? args.scale) as Pose["scale"];
    const frame = this.frames.get(handle);
    if (frame) {
      this.geometryFactory?.applyPose(frame, pose);
      if (scale) frame.userData.geometryScale = scale;
    }
    const drawable = this.objects.get(handle);
    if (drawable) this.geometryFactory?.applyPose(drawable, { ...pose, scale });
  }

  private putDrawable(handle: string, drawable: THREE.Object3D): void {
    this.sceneManager?.addObject(handle, drawable);
    this.objects.set(handle, drawable);
    const frame = this.frames.get(handle);
    if (!frame) return;
    // Drawables and the unscaled frame are siblings. Child nodes attach to the frame.
    frame.parent?.add(drawable);
    drawable.position.copy(frame.position);
    drawable.quaternion.copy(frame.quaternion);
    if (frame.userData.geometryScale) drawable.scale.fromArray(frame.userData.geometryScale);
    drawable.visible = frame.visible;
    drawable.userData.userVisible = frame.visible;
  }

  private onGizmoTransform(handle: string, value: { pos: number[]; quat: number[]; scale: number[] }): void {
    const drawable = this.objects.get(handle);
    const frame = this.frames.get(handle);
    if (!frame && !drawable) return;
    const pose = { pos: value.pos, quat: value.quat };
    const groupId = drawable?.userData.group_id as string | undefined;
    const sceneId = frame?.userData.scene_id ?? drawable?.userData.scene_id;
    const args = { pose, scene_id: sceneId, ...(drawable && { geometry_scale: value.scale }) };
    if (!drawable) frame?.scale.set(1, 1, 1);
    if (groupId) {
      const items = [...this.objects].filter(([, obj]) => obj.userData.group_id === groupId)
        .map(([handle]) => ({ ...args, handle }));
      for (const item of items) this.setFramePose(item.handle, item);
      this.emitCommand("set_object_transforms", { scene_id: sceneId, items });
    } else {
      this.setFramePose(handle, args);
      this.emitCommand("set_transform", { ...args, handle });
    }
    this.emitEvent("transformed", {
      view_id: this.viewId, handle: groupId ?? handle, pose, ...(drawable && { scale: value.scale }),
    });
  }

  private subtreeHandles(roots: string[]): string[] {
    const handles = new Set(roots);
    for (const root of roots) {
      this.frames.get(root)?.traverse(frame => {
        const handle = frame.userData.sceneNodeHandle;
        if (this.frames.get(handle) === frame) handles.add(handle);
      });
    }
    return [...handles];
  }

  private removeDrawableAndFrame(handle: string): void {
    const bufferIds = [
      ...(this.objects.get(handle)?.userData.bufferIds ?? []),
      ...this.pendingRenders.filter(render => render.handle === handle).flatMap(render => render.bufferIds),
    ];
    this.frames.get(handle)?.removeFromParent();
    this.frames.delete(handle);
    this.deferredMutations.delete(handle);
    const obj = this.objects.get(handle);
    if (obj && this.sceneManager) {
      const cssLabel = obj as THREE.Object3D & { isCSS2DObject?: boolean; element?: HTMLElement };
      const labelDiv = (cssLabel.element || (cssLabel as any).userData?.div) as HTMLElement | undefined;
      if ((cssLabel.isCSS2DObject || labelDiv) && this.labelManager) {
        this.labelManager.removeLabel(obj as any);
      }
      this.disposeObject(obj);
      this.sceneManager.removeObject(handle);
      this.objects.delete(handle);
    }
    this.removePendingRendersForHandle(handle);
    this.pendingLoads.delete(handle);
    if (this.gizmoManager?.getAttachedHandle() === handle) {
      this.gizmoManager.detach();
    }
    if (this.pickingManager) {
      const info = this.pickingManager.getLastPickInfo();
      if (info.handle === handle) {
        this.pickingManager.clearHighlight();
      }
    }
    const overlay = this.overlays2d.get(handle);
    if (overlay) {
      overlay.remove();
      this.overlays2d.delete(handle);
    }
    this.releaseUnusedBuffers(bufferIds);
  }

  private clearSceneContents(): void {
    if (!this.sceneManager) return;
    for (const [handle, obj] of this.objects) {
      this.disposeObject(obj);
      this.sceneManager.removeObject(handle);
    }
    this.objects.clear();
    for (const frame of this.frames.values()) frame.removeFromParent();
    this.frames.clear();
    this.gizmoManager?.detach();
    this.pickingManager?.clearHighlight();
    for (const overlay of this.overlays2d.values()) {
      overlay.remove();
    }
    this.overlays2d.clear();
    this.renderModeManager?.cleanupHelpers(this.objects);
    this.pendingRenders = [];
    this.pendingLoads.clear();
    this.deferredMutations.clear();
    this.buffers.clear();
  }

  private replayDeferred(handle: string): void {
    const changes = this.deferredMutations.get(handle) ?? [];
    this.deferredMutations.delete(handle);
    for (const [name, args] of changes) this.handleCommand(name, args);
  }

  private releaseUnusedBuffers(ids: string[]): void {
    const referenced = new Set<string>();
    for (const object of this.objects.values()) for (const id of object.userData.bufferIds ?? []) referenced.add(id);
    for (const pending of this.pendingRenders) for (const id of pending.bufferIds) referenced.add(id);
    for (const id of ids) if (!referenced.has(id)) this.buffers.delete(id);
  }

  private enqueueIfMissingBuffers(handle: string, refs: BufferRef[], execute: () => void): void {
    const ready = () => refs.every(ref => {
      const entry = this.buffers.get(ref.buffer_id);
      return entry && entry.data && entry.receivedBytes >= (entry.size_bytes ?? entry.receivedBytes);
    });
    const finish = () => {
      const previousIds = this.objects.get(handle)?.userData.bufferIds ?? [];
      execute();
      const object = this.objects.get(handle);
      if (object) object.userData.bufferIds = refs.map(ref => ref.buffer_id);
      this.releaseUnusedBuffers(previousIds);
      this.replayDeferred(handle);
    };
    if (!ready()) {
      this.pendingRenders.push({ handle, bufferIds: refs.map(ref => ref.buffer_id), check: ready, execute: finish });
    } else finish();
  }

  private getBufferTypedArray(ref: BufferRef): ArrayBufferView {
    const entry = this.buffers.get(ref.buffer_id);
    if (!entry || !entry.data) {
      throw new Error(`Buffer not ready: ${ref.buffer_id}`);
    }
    return this.ensureTypedArray(entry.data, ref.dtype);
  }

  private ensureTypedArray(data: ArrayBuffer | ArrayBufferView, dtype?: string): ArrayBufferView {
    const buffer = ArrayBuffer.isView(data)
      ? data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength)
      : data;
    switch (dtype) {
      case "f32":
      case "float32":
        return data instanceof Float32Array ? data : new Float32Array(buffer);
      case "u16":
      case "uint16":
        return data instanceof Uint16Array ? data : new Uint16Array(buffer);
      case "u32":
      case "uint32":
        return data instanceof Uint32Array ? data : new Uint32Array(buffer);
      case "u8":
      case "uint8":
        return data instanceof Uint8Array ? data : new Uint8Array(buffer);
      default:
        return data instanceof Uint8Array ? data : new Uint8Array(buffer);
    }
  }

  private applyColor(obj: THREE.Object3D, rgba: number[]): void {
    obj.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (mesh.material) {
        const materialValue = mesh.material;
        const materials: THREE.Material[] = Array.isArray(materialValue)
          ? materialValue
          : [materialValue];
        materials.forEach((mat) => {
          if (mat && (mat as THREE.Material & { color?: THREE.Color }).color) {
            (mat as THREE.Material & { color: THREE.Color }).color.setRGB(rgba[0], rgba[1], rgba[2]);
          }
          // Also set alpha if rgba contains alpha component
          if (rgba.length >= 4) {
            mat.opacity = rgba[3];
            mat.transparent = rgba[3] < 1.0;
            mat.needsUpdate = true;
          }
        });
      }
    });
  }

  private applyAlpha(obj: THREE.Object3D, alpha: number): void {
    obj.traverse((child) => {
      const mesh = child as THREE.Mesh | THREE.InstancedMesh;
      if (mesh && mesh.material) {
        this.applyColorAlphaToMesh(mesh, undefined, alpha);
      }
    });
  }

  private extractColorFromObject(obj: THREE.Object3D): { rgba: number[] } {
    const stack = [obj];
    while (stack.length > 0) {
      const curr = stack.pop()!;
      const mesh = curr as THREE.Mesh;
      if (mesh.material) {
        const materialValue = mesh.material;
        const materials: THREE.Material[] = Array.isArray(materialValue)
          ? materialValue
          : [materialValue];
        for (const mat of materials) {
          if (mat && (mat as THREE.Material & { color?: THREE.Color }).color) {
            const c = (mat as THREE.Material & { color: THREE.Color }).color;
            let alpha = 1.0;
            if (mat && 'opacity' in mat && typeof mat.opacity === 'number') {
              alpha = mat.opacity;
            }
            return { rgba: [c.r, c.g, c.b, alpha] };
          }
        }
      }
      for (let i = curr.children.length - 1; i >= 0; i--) {
        stack.push(curr.children[i]);
      }
    }

    return { rgba: [1, 1, 1, 1] }; // Default to white
  }

  private extractAlphaFromObject(obj: THREE.Object3D): number {
    const stack = [obj];
    while (stack.length > 0) {
      const curr = stack.pop()!;
      const mesh = curr as THREE.Mesh;
      if (mesh.material) {
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const mat of materials) {
          if (mat && "opacity" in mat && typeof mat.opacity === "number") {
            return mat.opacity;
          }
        }
      }
      for (let i = curr.children.length - 1; i >= 0; i--) {
        stack.push(curr.children[i]);
      }
    }
    return 1.0;
  }

  private convertMeshToUniformColor(mesh: THREE.Mesh, rgba: number[]): void {
    const geometry = mesh.geometry;
    const newGeometry = new THREE.BufferGeometry();

    // Copy position and normal attributes, but not colors
    const position = geometry.attributes.position;
    const normal = geometry.attributes.normal;
    const index = geometry.index;

    newGeometry.setAttribute("position", position.clone());
    if (normal) {
      newGeometry.setAttribute("normal", normal.clone());
    }
    if (index) {
      newGeometry.setIndex(index.clone());
    }

    // Update material to not use vertex colors
    const material = mesh.material as THREE.MeshStandardMaterial;
    material.vertexColors = false;
    material.color.setRGB(rgba[0], rgba[1], rgba[2]);
    if (rgba.length >= 4) {
      material.opacity = rgba[3];
      material.transparent = rgba[3] < 1.0;
    }
    material.needsUpdate = true;

    // Replace geometry
    geometry.dispose();
    mesh.geometry = newGeometry;

    // Handle wireframe child objects (if present)
    mesh.traverse((child) => {
      if (child.userData.isWireframe === true && child instanceof THREE.LineSegments) {
        const oldWireframeGeo = child.geometry;
        const newWireframeGeo = new THREE.WireframeGeometry(newGeometry);
        child.geometry = newWireframeGeo;
        oldWireframeGeo.dispose();
      }
    });
  }

  private convertPointsToUniformColor(points: THREE.Points, rgba: number[]): void {
    const geometry = points.geometry as THREE.BufferGeometry;
    const newGeometry = new THREE.BufferGeometry();

    for (const [name, attribute] of Object.entries(geometry.attributes)) {
      if (name === "color") continue;
      newGeometry.setAttribute(name, attribute.clone());
    }
    if (geometry.index) {
      newGeometry.setIndex(geometry.index.clone());
    }

    const material = points.material as THREE.PointsMaterial;
    material.vertexColors = false;
    material.color.setRGB(rgba[0], rgba[1], rgba[2]);
    if (rgba.length >= 4) {
      material.opacity = rgba[3];
      material.transparent = rgba[3] < 1.0;
    }
    material.needsUpdate = true;

    geometry.dispose();
    points.geometry = newGeometry;
  }

  private disposeMaterial(material: THREE.Material | THREE.Material[]): void {
    const materials: THREE.Material[] = Array.isArray(material) ? material : [material];
    materials.forEach((mat) => {
      if (!mat) return;
      for (const key in mat) {
        const value = (mat as any)[key];
        if (value && value.isTexture) {
          value.dispose();
        }
      }
      if (typeof (mat as THREE.Material).dispose === "function") {
        (mat as THREE.Material).dispose();
      }
    });
  }

  private disposeObject(obj: THREE.Object3D): void {
    obj.traverse((child) => {
      const cssObject = child as THREE.Object3D & { isCSS2DObject?: boolean; element?: HTMLElement };
      if (cssObject.isCSS2DObject && cssObject.element?.parentNode) {
        cssObject.element.parentNode.removeChild(cssObject.element);
      }
      const mesh = child as THREE.Mesh;
      if (mesh.isMesh || (child as THREE.Line).isLine || (child as THREE.Points).isPoints) {
        if (mesh.geometry) {
          mesh.geometry.dispose();
        }
        if (mesh.material) {
          this.disposeMaterial(mesh.material as THREE.Material);
        }
      }
    });
  }

  private removePendingRendersForHandle(handle: string): void {
    this.pendingRenders = this.pendingRenders.filter((item) => item.handle !== handle);
  }

  private removePendingRendersForBuffer(bufferId: string): void {
    this.pendingRenders = this.pendingRenders.filter((item) => !item.bufferIds.includes(bufferId));
  }

  /**
   * Apply uniform color and/or alpha to a mesh's material.
   */
  private applyColorAlphaToMesh(
    mesh: THREE.Mesh | THREE.InstancedMesh,
    color?: number[],
    alpha?: number
  ): void {
    if (color === undefined && alpha === undefined) return;

    const materialValue = mesh.material;
    if (!materialValue) return;
    const materials: THREE.Material[] = Array.isArray(materialValue)
      ? materialValue
      : [materialValue];

    materials.forEach((mat) => {
      const typed = mat as THREE.MeshLambertMaterial | THREE.MeshStandardMaterial;
      if (color !== undefined && color.length >= 3 && typed.color) {
        typed.color.setRGB(color[0], color[1], color[2]);
      }

      if (alpha !== undefined) {
        typed.opacity = alpha;
        typed.transparent = alpha < 1;
        typed.depthWrite = alpha >= 1;
        typed.needsUpdate = true;
      }
    });
  }

  private toColorArray(color?: number[]): ColorArray {
    const base = color ?? [1, 1, 1];
    const r = base[0] ?? 1;
    const g = base[1] ?? 1;
    const b = base[2] ?? 1;
    if (base.length >= 4) {
      const a = base[3] ?? 1;
      return [r, g, b, a];
    }
    return [r, g, b];
  }
}


import {
    BoxGeometry,
    BufferGeometry,
    CylinderGeometry,
    DoubleSide,
    Euler,
    Float32BufferAttribute,
    Line,
    LineBasicMaterial,
    Matrix4,
    Mesh,
    MeshBasicMaterial,
    Object3D,
    OctahedronGeometry,
    PlaneGeometry,
    Quaternion,
    Raycaster,
    RingGeometry,
    TorusGeometry,
    Vector3,
    Camera,
    PerspectiveCamera,
    OrthographicCamera,
    type Intersection,
    type Object3DEventMap,
    type BaseEvent
} from 'three';

export const GIZMO_MASK = {
    TR_X: 1,
    TR_Y: 2,
    TR_Z: 4,
    ROT_X: 8,
    ROT_Y: 16,
    ROT_Z: 32
};

export const GIZMO_MASK_ALL = 0x3F;

const _raycaster = new Raycaster();
const _tempVector = new Vector3();
const _tempVector2 = new Vector3();
const _tempQuaternion = new Quaternion();
const _unit = {
    X: new Vector3(1, 0, 0),
    Y: new Vector3(0, 1, 0),
    Z: new Vector3(0, 0, 1)
};

const _changeEvent = { type: 'change' as const };
const _mouseDownEvent = { type: 'mouseDown' as const, mode: '' };
const _mouseUpEvent = { type: 'mouseUp' as const, mode: '' };
const _objectChangeEvent = { type: 'objectChange' as const };

// --- Helper Functions ---

function intersectObjectWithRay(object: Object3D, raycaster: Raycaster, includeInvisible?: boolean): Intersection | false {
    const allIntersections = raycaster.intersectObject(object, true);
    for (let i = 0; i < allIntersections.length; i++) {
        if (allIntersections[i].object.visible || includeInvisible) {
            return allIntersections[i];
        }
    }
    return false;
}

// --- Geometries & Materials ---

const gizmoMaterial = new MeshBasicMaterial({
    depthTest: false,
    depthWrite: false,
    fog: false,
    toneMapped: false,
    transparent: true,
    opacity: 0.8,
    side: DoubleSide
});

const gizmoLineMaterial = new LineBasicMaterial({
    depthTest: false,
    depthWrite: false,
    fog: false,
    toneMapped: false,
    transparent: true,
    side: DoubleSide
});

const matInvisible = gizmoMaterial.clone();
matInvisible.opacity = 0.15;

const matRed = gizmoMaterial.clone();
matRed.color.setHex(0xff0000);

const matGreen = gizmoMaterial.clone();
matGreen.color.setHex(0x00ff00);

const matBlue = gizmoMaterial.clone();
matBlue.color.setHex(0x0000ff);

const matWhiteTransparent = gizmoMaterial.clone();
matWhiteTransparent.opacity = 0.25;

const arrowGeometry = new CylinderGeometry(0, 0.05, 0.2, 12);
arrowGeometry.translate(0, 0.1, 0);

const arrowHeadGeometry = new CylinderGeometry(0, 0.1, 0.2, 12);
arrowHeadGeometry.translate(0, 0.8, 0);

const arrowShaftGeometry = new CylinderGeometry(0.04, 0.04, 0.2, 12);
arrowShaftGeometry.translate(0, 0.6, 0);

const pickerTranslateGeometry = new CylinderGeometry(0.15, 0.15, 0.4, 4);
pickerTranslateGeometry.translate(0, 0.7, 0);

function CreateRingGeometry(arc: number) {
    const geometry = new RingGeometry(0.5, 0.65, 32, 1, 0, arc * Math.PI * 2);
    return geometry;
}

const pickerRotateGeometry = new RingGeometry(0.5, 0.65, 12, 1, 0, Math.PI * 2);

class TransformControlsGizmo extends Object3D {
    public picker: Object3D;

    // Maps to store created objects by name
    private gizmoMap: Map<string, Object3D> = new Map();
    private helperMap: Map<string, Object3D> = new Map();
    private pickerMap: Map<string, Object3D> = new Map();

    constructor() {
        super();
        (this as any).type = 'TransformControlsGizmo';

        const matInvisible = new MeshBasicMaterial({ visible: false, depthTest: false, side: DoubleSide });

        // -- Gizmo Definitions (Combined) --

        // Translation Arrows (Bidirectional)
        const gizmoTranslate = {
            TR_X: [
                [new Mesh(arrowHeadGeometry, matRed), [0, 0, 0], [0, 0, -Math.PI / 2]],
                [new Mesh(arrowShaftGeometry, matRed), [0, 0, 0], [0, 0, -Math.PI / 2]],
                [new Mesh(arrowHeadGeometry, matRed), [0, 0, 0], [0, 0, Math.PI / 2]],
                [new Mesh(arrowShaftGeometry, matRed), [0, 0, 0], [0, 0, Math.PI / 2]]
            ],
            TR_Y: [
                [new Mesh(arrowHeadGeometry, matGreen), [0, 0, 0]],
                [new Mesh(arrowShaftGeometry, matGreen), [0, 0, 0]],
                [new Mesh(arrowHeadGeometry, matGreen), [0, 0, 0], [Math.PI, 0, 0]],
                [new Mesh(arrowShaftGeometry, matGreen), [0, 0, 0], [Math.PI, 0, 0]]
            ],
            TR_Z: [
                [new Mesh(arrowHeadGeometry, matBlue), [0, 0, 0], [Math.PI / 2, 0, 0]],
                [new Mesh(arrowShaftGeometry, matBlue), [0, 0, 0], [Math.PI / 2, 0, 0]],
                [new Mesh(arrowHeadGeometry, matBlue), [0, 0, 0], [-Math.PI / 2, 0, 0]],
                [new Mesh(arrowShaftGeometry, matBlue), [0, 0, 0], [-Math.PI / 2, 0, 0]]
            ]
        };

        const gizmoRotate = {
            ROT_X: [
                [new Mesh(CreateRingGeometry(1), matRed), null, [0, Math.PI / 2, 0]]
            ],
            ROT_Y: [
                [new Mesh(CreateRingGeometry(1), matGreen), null, [-Math.PI / 2, 0, 0]]
            ],
            ROT_Z: [
                [new Mesh(CreateRingGeometry(1), matBlue), null, [0, 0, 0]]
            ]
        };

        // Pickers (Larger volumes)
        const pickerTranslate = {
            TR_X: [
                [new Mesh(pickerTranslateGeometry, matInvisible), [0, 0, 0], [0, 0, -Math.PI / 2]],
                [new Mesh(pickerTranslateGeometry, matInvisible), [0, 0, 0], [0, 0, Math.PI / 2]]
            ],
            TR_Y: [
                [new Mesh(pickerTranslateGeometry, matInvisible), [0, 0, 0]],
                [new Mesh(pickerTranslateGeometry, matInvisible), [0, 0, 0], [Math.PI, 0, 0]]
            ],
            TR_Z: [
                [new Mesh(pickerTranslateGeometry, matInvisible), [0, 0, 0], [Math.PI / 2, 0, 0]],
                [new Mesh(pickerTranslateGeometry, matInvisible), [0, 0, 0], [-Math.PI / 2, 0, 0]]
            ]
        };

        const pickerRotate = {
            ROT_X: [
                [new Mesh(pickerRotateGeometry, matInvisible), null, [0, Math.PI / 2, 0]]
            ],
            ROT_Y: [
                [new Mesh(pickerRotateGeometry, matInvisible), null, [-Math.PI / 2, 0, 0]]
            ],
            ROT_Z: [
                [new Mesh(pickerRotateGeometry, matInvisible), null, [0, 0, 0]]
            ]
        };

        this.add(this.setupGizmo(gizmoTranslate, this.gizmoMap));
        this.add(this.setupGizmo(gizmoRotate, this.gizmoMap));

        this.picker = new Object3D();
        this.add(this.picker);
        this.picker.add(this.setupGizmo(pickerTranslate, this.pickerMap));
        this.picker.add(this.setupGizmo(pickerRotate, this.pickerMap));

        // Hide pickers
        this.picker.traverse((child: any) => { child.visible = false; });
    }

    private setupGizmo(gizmoMapDef: any, storeMap: Map<string, Object3D>): Object3D {
        const gizmo = new Object3D();

        for (const name in gizmoMapDef) {
            for (let i = gizmoMapDef[name].length; i--;) {
                const object = gizmoMapDef[name][i][0].clone();
                const position = gizmoMapDef[name][i][1];
                const rotation = gizmoMapDef[name][i][2];
                const scale = gizmoMapDef[name][i][3];
                const tag = gizmoMapDef[name][i][4];

                object.name = name;
                object.tag = tag;

                if (position) object.position.set(position[0], position[1], position[2]);
                if (rotation) object.rotation.set(rotation[0], rotation[1], rotation[2]);
                if (scale) object.scale.set(scale[0], scale[1], scale[2]);

                object.updateMatrix();

                if (object.geometry) object.geometry = object.geometry.clone();
                if (object.material) {
                    if (Array.isArray(object.material)) {
                        object.material = object.material.map((m: any) => m.clone());
                    } else {
                        object.material = (object.material as any).clone();
                    }
                }

                object.geometry.applyMatrix4(object.matrix);
                object.position.set(0, 0, 0);
                object.rotation.set(0, 0, 0);
                object.scale.set(1, 1, 1);

                gizmo.add(object);

                // Track objects for updates (last one wins if multiple parts per name, usually fine for main handle)
                storeMap.set(name, object);
            }
        }
        return gizmo;
    }

    public update(
        worldPosition: Vector3,
        worldQuaternion: Quaternion,
        eye: Vector3,
        camera: Camera,
        mask: number,
        activeAxis: string | null,
        space: string,
        size: number,
        dragging: boolean,
        scaleMode: 'screen' | 'world' = 'screen'
    ) {
        // Collect all handles
        this.traverse((child: any) => {
            if (child.name) {
                // Base visibility
                child.visible = true;

                // Mask Check
                if (child.name === 'TR_X' && !(mask & GIZMO_MASK.TR_X)) child.visible = false;
                if (child.name === 'TR_Y' && !(mask & GIZMO_MASK.TR_Y)) child.visible = false;
                if (child.name === 'TR_Z' && !(mask & GIZMO_MASK.TR_Z)) child.visible = false;

                if (child.name === 'ROT_X' && !(mask & GIZMO_MASK.ROT_X)) child.visible = false;
                if (child.name === 'ROT_Y' && !(mask & GIZMO_MASK.ROT_Y)) child.visible = false;
                if (child.name === 'ROT_Z' && !(mask & GIZMO_MASK.ROT_Z)) child.visible = false;

                // Position
                child.position.copy(worldPosition);
                // Rotate based on space (TR handles only, ROT handles usually stay local or need logic)
                // For combined:
                // Translation handles follow 'space'.
                // Rotation handles usually follow 'local' if we want to rotate 'intrinsic', or 'world' if extrinsic.
                // Standard gizmos usually draw rotation rings differently.
                // Here we simplify: if space==local, everything uses worldQuaternion.
                // If space==world:
                //   - Translation handles use Identity.
                //   - Rotation should behave consistently.

                if (space === 'local') {
                    child.quaternion.copy(worldQuaternion);
                } else {
                    child.quaternion.set(0, 0, 0, 1); // Identity
                }

                // Scale factor for constant screen size OR fixed world size
                let factor = 1;
                if (scaleMode === 'screen') {
                    if (camera instanceof OrthographicCamera) {
                        factor = (camera.top - camera.bottom) / camera.zoom;
                    } else if (camera instanceof PerspectiveCamera) {
                        factor = worldPosition.distanceTo(camera.position) * Math.min(1.9 * Math.tan(Math.PI * camera.fov / 360) / camera.zoom, 7);
                    }
                }

                child.scale.set(1, 1, 1).multiplyScalar(factor * size / (scaleMode === 'screen' ? 2.5 : 1.0));

                // Highlight
                if (child.material) {
                    child.material._color = child.material._color || child.material.color.clone();
                    child.material._opacity = child.material._opacity || child.material.opacity;

                    child.material.color.copy(child.material._color);
                    child.material.opacity = child.material._opacity;

                    if (activeAxis === child.name || (activeAxis && activeAxis.indexOf(child.name) !== -1)) {
                        child.material.color.setHex(0xffff00);
                        child.material.opacity = 1.0;
                    }
                }
            }
        });
    }
}

// --- Plane Class ---

class TransformControlsPlane extends Mesh {
    private eye = new Vector3();
    private _v1 = new Vector3();
    private _v2 = new Vector3();
    private _v3 = new Vector3();
    private _alignVector = new Vector3();
    private _dirVector = new Vector3();
    private _tempMatrix = new Matrix4();
    private _tempQuaternion = new Quaternion();

    constructor() {
        super(
            new PlaneGeometry(100000, 100000, 2, 2),
            new MeshBasicMaterial({ visible: false, wireframe: true, side: DoubleSide, transparent: true, opacity: 0.1, toneMapped: false })
        );
        (this as any).type = 'TransformControlsPlane';
    }

    public update(worldPosition: Vector3, worldQuaternion: Quaternion, eye: Vector3, axis: string | null, mode: string, space: string) {
        this.position.copy(worldPosition);
        this.eye.copy(eye);

        const quaternion = space === 'local' ? worldQuaternion : this._tempQuaternion.set(0, 0, 0, 1); // Identity
        const _unitX = new Vector3(1, 0, 0);
        const _unitY = new Vector3(0, 1, 0);
        const _unitZ = new Vector3(0, 0, 1);

        this._v1.copy(_unitX).applyQuaternion(quaternion);
        this._v2.copy(_unitY).applyQuaternion(quaternion);
        this._v3.copy(_unitZ).applyQuaternion(quaternion);

        this._alignVector.copy(this._v2);

        if (mode === 'translate') {
            if (axis === 'TR_X') {
                this._alignVector.copy(this.eye).cross(this._v1);
                this._dirVector.copy(this._v1).cross(this._alignVector);
            } else if (axis === 'TR_Y') {
                this._alignVector.copy(this.eye).cross(this._v2);
                this._dirVector.copy(this._v2).cross(this._alignVector);
            } else if (axis === 'TR_Z') {
                this._alignVector.copy(this.eye).cross(this._v3);
                this._dirVector.copy(this._v3).cross(this._alignVector);
            } else if (axis === 'TR_XYZ') {
                this._dirVector.set(0, 0, 0);
            }
        } else if (mode === 'rotate') {
            this._dirVector.set(0, 0, 0); // Always face camera
        }

        if (this._dirVector.length() === 0) {
            // Perpendicular to eye
            this.quaternion.setFromRotationMatrix(this._tempMatrix.lookAt(worldPosition, worldPosition.clone().add(this.eye), this._v2));
        } else {
            this._tempMatrix.lookAt(new Vector3(0, 0, 0), this._dirVector, this._alignVector);
            this.quaternion.setFromRotationMatrix(this._tempMatrix);
        }
    }
}

interface CombinedTransformControlsEventMap extends Object3DEventMap {
    change: BaseEvent;
    mouseDown: BaseEvent & { mode: string };
    mouseUp: BaseEvent & { mode: string };
    objectChange: BaseEvent;
}

export class CombinedTransformControls extends Object3D<CombinedTransformControlsEventMap> {
    public visible: boolean = false;
    public domElement: HTMLElement;
    public camera: Camera;
    public object: Object3D | undefined;
    public enabled: boolean = true;
    public axis: string | null = null;
    public mask: number = GIZMO_MASK_ALL;
    public space: 'world' | 'local' = 'local';
    public size: number = 1;
    public scaleMode: 'screen' | 'world' = 'world'; // Default to world scale (fixed size)
    public dragging: boolean = false;

    // Current active mode based on axis interaction ('translate' or 'rotate' or 'scale')
    // We keep 'scale' for compatibility though not primarily focused on mixed scale.
    // In combined mode, dragging a TR_ handle sets _currentMode = 'translate'.
    private _currentMode: 'translate' | 'rotate' | 'scale' = 'translate';

    private _gizmo: TransformControlsGizmo;
    private _plane: TransformControlsPlane;

    private worldPosition = new Vector3();
    private worldPositionStart = new Vector3();
    private worldQuaternion = new Quaternion();
    private worldQuaternionStart = new Quaternion();
    private cameraPosition = new Vector3();
    private cameraQuaternion = new Quaternion();
    private pointStart = new Vector3();
    private pointEnd = new Vector3();
    private rotationAxis = new Vector3();
    private rotationAngle = 0;
    private eye = new Vector3();

    private _offset = new Vector3();
    private _startNorm = new Vector3();
    private _endNorm = new Vector3();
    private _cameraScale = new Vector3();

    private _parentPosition = new Vector3();
    private _parentQuaternion = new Quaternion();
    private _parentQuaternionInv = new Quaternion();
    private _parentScale = new Vector3();

    private _worldScaleStart = new Vector3();
    private _worldQuaternionInv = new Quaternion();
    private _worldScale = new Vector3();

    private _positionStart = new Vector3();
    private _quaternionStart = new Quaternion();
    private _scaleStart = new Vector3();

    private _onPointerDown: (event: PointerEvent) => void;
    private _onPointerHover: (event: PointerEvent) => void;
    private _onPointerMove: (event: PointerEvent) => void;
    private _onPointerUp: (event: PointerEvent) => void;

    constructor(camera: Camera, domElement: HTMLElement) {
        super();
        this.domElement = domElement;
        this.camera = camera;

        // Bind handlers
        this._onPointerDown = this.onPointerDown.bind(this);
        this._onPointerHover = this.onPointerHover.bind(this);
        this._onPointerMove = this.onPointerMove.bind(this);
        this._onPointerUp = this.onPointerUp.bind(this);

        this.domElement.addEventListener('pointerdown', this._onPointerDown);
        this.domElement.addEventListener('pointermove', this._onPointerHover);
        this.domElement.addEventListener('pointerup', this._onPointerUp);

        this._gizmo = new TransformControlsGizmo();
        this.add(this._gizmo);

        this._plane = new TransformControlsPlane();
        this.add(this._plane);
    }

    public dispose() {
        this.domElement.removeEventListener('pointerdown', this._onPointerDown);
        this.domElement.removeEventListener('pointermove', this._onPointerHover);
        this.domElement.removeEventListener('pointermove', this._onPointerMove);
        this.domElement.removeEventListener('pointerup', this._onPointerUp);

        this.traverse((child: any) => {
            if (child.geometry) child.geometry.dispose();
            if (child.material) child.material.dispose();
        });
    }

    public attach(object: Object3D): this {
        this.object = object;
        this.visible = true;
        return this;
    }

    public detach(): this {
        this.object = undefined;
        this.visible = false;
        this.axis = null;
        return this;
    }

    public setMask(mask: number) {
        this.mask = mask;
        this.updateMatrixWorld(); // update visibility
    }

    updateMatrixWorld(force?: boolean) {
        if (this.object !== undefined) {
            this.object.updateMatrixWorld();
            if (this.object.parent === null) {
                // console.error('TransformControls: The attached 3D object must be a part of the scene graph.');
            } else {
                this.object.parent.matrixWorld.decompose(this._parentPosition, this._parentQuaternion, this._parentScale);
            }
            this.object.matrixWorld.decompose(this.worldPosition, this.worldQuaternion, this._worldScale);
            this._parentQuaternionInv.copy(this._parentQuaternion).invert();
            this._worldQuaternionInv.copy(this.worldQuaternion).invert();
        }

        this.camera.updateMatrixWorld();
        this.camera.matrixWorld.decompose(this.cameraPosition, this.cameraQuaternion, this._cameraScale);

        if (this.camera instanceof OrthographicCamera) {
            this.camera.getWorldDirection(this.eye).negate();
        } else {
            this.eye.copy(this.cameraPosition).sub(this.worldPosition).normalize();
        }

        super.updateMatrixWorld(force);

        // Update gizmo visibility based on mask
        this._gizmo.update(
            this.worldPosition,
            this.worldQuaternion,
            this.eye,
            this.camera,
            this.mask,
            this.axis,
            this.space,
            this.size,
            this.dragging,
            this.scaleMode
        );
        this._plane.update(this.worldPosition, this.worldQuaternion, this.eye, this.axis, this._currentMode, this.space);
    }

    // Interaction Logic
    private onPointerHover(event: PointerEvent) {
        if (!this.enabled || !this.object || this.dragging) return;
        const pointer = this.getPointer(event);
        _raycaster.setFromCamera(pointer as any, this.camera);

        const intersect = intersectObjectWithRay(this._gizmo.picker, _raycaster);
        if (intersect) {
            this.axis = intersect.object.name;
        } else {
            this.axis = null;
        }
    }

    private onPointerDown(event: PointerEvent) {
        if (!this.enabled || !this.object || this.dragging || event.button !== 0) return;
        const pointer = this.getPointer(event);

        if (this.axis !== null) {
            _raycaster.setFromCamera(pointer as any, this.camera);
            const planeIntersect = intersectObjectWithRay(this._plane, _raycaster, true);

            if (planeIntersect) {
                // Determine mode based on axis name
                if (this.axis.startsWith('TR_')) this._currentMode = 'translate';
                else if (this.axis.startsWith('ROT_')) this._currentMode = 'rotate';

                this.object.updateMatrixWorld();
                if (this.object.parent) this.object.parent.updateMatrixWorld();

                this._positionStart.copy(this.object.position);
                this._quaternionStart.copy(this.object.quaternion);
                this._scaleStart.copy(this.object.scale);

                this.object.matrixWorld.decompose(this.worldPositionStart, this.worldQuaternionStart, this._worldScaleStart);
                this.pointStart.copy(planeIntersect.point).sub(this.worldPositionStart);
            }

            this.dragging = true;
            _mouseDownEvent.mode = this._currentMode;
            this.dispatchEvent(_mouseDownEvent);

            this.domElement.setPointerCapture(event.pointerId);
            this.domElement.addEventListener('pointermove', this._onPointerMove);
        }
    }

    private onPointerMove(event: PointerEvent) {
        if (!this.enabled || !this.object || !this.dragging || !this.axis || event.button !== -1) return;
        const pointer = this.getPointer(event);
        _raycaster.setFromCamera(pointer as any, this.camera);

        const planeIntersect = intersectObjectWithRay(this._plane, _raycaster, true);
        if (!planeIntersect) return;

        this.pointEnd.copy(planeIntersect.point).sub(this.worldPositionStart);

        if (this._currentMode === 'translate') {
            this.handleTranslate();
        } else if (this._currentMode === 'rotate') {
            this.handleRotate();
        }

        this.dispatchEvent(_changeEvent);
        this.dispatchEvent(_objectChangeEvent);
    }

    private onPointerUp(event: PointerEvent) {
        if (!this.enabled || !this.dragging) return;
        if (event.button === 0) {
            _mouseUpEvent.mode = this._currentMode;
            this.dispatchEvent(_mouseUpEvent);
            this.dragging = false;
            this.axis = null;
            this.domElement.releasePointerCapture(event.pointerId);
            this.domElement.removeEventListener('pointermove', this._onPointerMove);
        }
    }

    private getPointer(event: PointerEvent) {
        const rect = this.domElement.getBoundingClientRect();
        return {
            x: (event.clientX - rect.left) / rect.width * 2 - 1,
            y: -(event.clientY - rect.top) / rect.height * 2 + 1,
            button: event.button
        };
    }

    // --- Transform Handlers ---

    private handleTranslate() {
        // Simplified translation logic port
        if (!this.object || !this.axis) return;

        this._offset.copy(this.pointEnd).sub(this.pointStart);

        // Helper to check axis presence in name
        // e.g. TR_X, TR_XY, TR_XYZ
        const hasX = this.axis.indexOf('X') !== -1;
        const hasY = this.axis.indexOf('Y') !== -1;
        const hasZ = this.axis.indexOf('Z') !== -1;
        const isPlane = (hasX && hasY) || (hasX && hasZ) || (hasY && hasZ);

        // Apply constraints
        let space = this.space;
        if (isPlane || this.axis === 'TR_XYZ') space = 'world'; // Align with standard behavior for multi-axis

        if (space === 'local' && this.axis !== 'TR_XYZ') {
            this._offset.applyQuaternion(this._worldQuaternionInv);
        }

        if (!hasX) this._offset.x = 0;
        if (!hasY) this._offset.y = 0;
        if (!hasZ) this._offset.z = 0;

        if (space === 'local' && this.axis !== 'TR_XYZ') {
            this._offset.applyQuaternion(this._quaternionStart).divide(this._parentScale);
        } else {
            this._offset.applyQuaternion(this._parentQuaternionInv).divide(this._parentScale);
        }

        this.object.position.copy(this._offset).add(this._positionStart);
    }

    private handleRotate() {
        if (!this.object || !this.axis) return;

        this._offset.copy(this.pointEnd).sub(this.pointStart);
        const ROTATION_SPEED = 20 / this.worldPosition.distanceTo(_tempVector.setFromMatrixPosition(this.camera.matrixWorld));

        const hasX = this.axis.indexOf('X') !== -1;
        const hasY = this.axis.indexOf('Y') !== -1;
        const hasZ = this.axis.indexOf('Z') !== -1;
        const hasE = this.axis.indexOf('E') !== -1; // Eye aligned

        if (hasE) {
            this.rotationAxis.copy(this.eye);
            this.rotationAngle = this.pointEnd.angleTo(this.pointStart);
            this._startNorm.copy(this.pointStart).normalize();
            this._endNorm.copy(this.pointEnd).normalize();
            this.rotationAngle *= (this._endNorm.cross(this._startNorm).dot(this.eye) < 0 ? 1 : -1);
        } else if (hasX || hasY || hasZ) {
            // Single axis rotation
            if (hasX) this.rotationAxis.copy(_unit.X);
            if (hasY) this.rotationAxis.copy(_unit.Y);
            if (hasZ) this.rotationAxis.copy(_unit.Z);

            _tempVector.copy(this.rotationAxis);
            if (this.space === 'local') {
                _tempVector.applyQuaternion(this.worldQuaternion);
            }

            // Check for in-plane (if axis parallel to eye)
            // Skipping detail check for now

            this.rotationAngle = this._offset.dot(_tempVector.cross(this.eye).normalize()) * ROTATION_SPEED;
        }

        // Apply rotate
        if (this.space === 'local' && !hasE) {
            this.object.quaternion.copy(this._quaternionStart);
            this.object.quaternion.multiply(_tempQuaternion.setFromAxisAngle(this.rotationAxis, this.rotationAngle)).normalize();
        } else {
            this.rotationAxis.applyQuaternion(this._parentQuaternionInv);
            this.object.quaternion.copy(_tempQuaternion.setFromAxisAngle(this.rotationAxis, this.rotationAngle));
            this.object.quaternion.multiply(this._quaternionStart).normalize();
        }
    }
}




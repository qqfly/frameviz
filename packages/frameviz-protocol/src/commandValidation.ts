type ValidationResult =
  | { ok: true }
  | { ok: false; error: string };

type Validator = (value: unknown) => boolean;
type Validators = Record<string, Validator>;

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isString = (value: unknown): value is string =>
  typeof value === "string";

const isNonEmptyString = (value: unknown): value is string =>
  isString(value) && value.trim().length > 0;

const isNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

const isInteger = (value: unknown): value is number =>
  isNumber(value) && Number.isInteger(value);

const isBoolean = (value: unknown): value is boolean =>
  typeof value === "boolean";

const isArrayOf = (value: unknown, item: Validator, length?: number): boolean =>
  Array.isArray(value) &&
  (length === undefined || value.length === length) &&
  value.every(item);

const isVec3 = (value: unknown): boolean => isArrayOf(value, isNumber, 3);

const isQuat = (value: unknown): boolean => isArrayOf(value, isNumber, 4);

const isColorComponent = (value: unknown): boolean =>
  isNumber(value) && value >= 0 && value <= 1;

const isColor = (value: unknown): boolean =>
  isArrayOf(value, isColorComponent, 3) || isArrayOf(value, isColorComponent, 4);

const isRgba = (value: unknown): boolean =>
  isArrayOf(value, isColorComponent, 4);

const isShape = (value: unknown): boolean =>
  isArrayOf(value, (item) => isInteger(item) && item > 0);

const isBufferRef = (
  value: unknown,
  expectedDtype?: string,
  expectedShape?: number[]
): boolean => {
  if (!isObject(value)) return false;
  if (!isNonEmptyString(value.buffer_id)) return false;
  if (!isNonEmptyString(value.dtype)) return false;
  if (expectedDtype && value.dtype !== expectedDtype) return false;

  if (value.shape !== undefined) {
    if (!isShape(value.shape)) return false;
    if (expectedShape) {
      const shape = value.shape as number[];
      if (shape.length !== expectedShape.length) return false;
      for (let i = 0; i < expectedShape.length; i += 1) {
        const expected = expectedShape[i];
        if (expected > 0 && shape[i] !== expected) return false;
      }
    }
  }
  return true;
};

const isNonzeroQuat = (value: unknown): boolean =>
  isQuat(value) && (value as number[]).some(component => component !== 0);

const isPose = (value: unknown, allowScale = true): boolean => {
  if (Array.isArray(value)) {
    return isArrayOf(value, isNumber, 7) && isNonzeroQuat(value.slice(3));
  }
  if (!isObject(value) || value.matrix !== undefined || value.geometry_scale !== undefined) return false;
  if (value.scale !== undefined && (!allowScale || !isVec3(value.scale))) return false;
  for (const [canonical, alias, check] of [
    ["position", "pos", isVec3],
    ["quaternion", "quat", isNonzeroQuat],
  ] as const) {
    const primary = value[canonical];
    const old = value[alias];
    if (primary !== undefined && !check(primary)) return false;
    if (old !== undefined && !check(old)) return false;
    if (primary !== undefined && old !== undefined && JSON.stringify(primary) !== JSON.stringify(old)) return false;
  }
  return true;
};

const isParent = (value: unknown): boolean => value === null || isNonEmptyString(value);
const isName = (value: unknown): boolean => isString(value) && new TextEncoder().encode(value).length <= 1024;
const isTags = (value: unknown): boolean =>
  isObject(value) && new TextEncoder().encode(JSON.stringify(value)).length <= 16 * 1024;
const nodeMetadata = { parent: isParent, name: isName, tags: isTags };
const nodeOptions = { ...nodeMetadata, pose: isPose, geometry_scale: isVec3 };
const poseOptions = { scene_id: isNonEmptyString, geometry_scale: isVec3 };

const isStringEnum = (values: string[]): Validator => (value) =>
  isString(value) && values.includes(value);

const isMouseButtonAction = isStringEnum(["rotate", "pan", "zoom", "none"]);

const isMouseButtons = (value: unknown): boolean => {
  if (!isObject(value)) return false;
  const allowed = new Set(["left", "middle", "right"]);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) return false;
  }
  if ("left" in value && !isMouseButtonAction(value.left)) return false;
  if ("middle" in value && !isMouseButtonAction(value.middle)) return false;
  if ("right" in value && !isMouseButtonAction(value.right)) return false;
  return true;
};
const validateObject = (
  value: unknown,
  required: Validators,
  optional: Validators = {},
  allowUnknown = false
): string | null => {
  if (!isObject(value)) return "args must be an object";
  const allowed = new Set([...Object.keys(required), ...Object.keys(optional)]);
  if (!allowUnknown) {
    for (const key of Object.keys(value)) {
      if (!allowed.has(key)) {
        return `unexpected field: ${key}`;
      }
    }
  }

  for (const [key, validator] of Object.entries(required)) {
    if (!(key in value)) {
      return `missing field: ${key}`;
    }
    if (!validator(value[key])) {
      return `invalid field: ${key}`;
    }
  }

  for (const [key, validator] of Object.entries(optional)) {
    if (key in value && !validator(value[key])) {
      return `invalid field: ${key}`;
    }
  }
  return null;
};

const validateRemoveObject = (args: unknown): string | null => {
  const error = validateObject(
    args,
    { handle: isNonEmptyString },
    { scene_id: isNonEmptyString, view_id: isNonEmptyString }
  );
  if (error) return error;
  const obj = args as Record<string, unknown>;
  const hasScene = obj.scene_id !== undefined;
  const hasView = obj.view_id !== undefined;
  if (hasScene === hasView) {
    return "scene_id and view_id must be mutually exclusive";
  }
  return null;
};

const validateResetCamera = (args: unknown): string | null => {
  const error = validateObject(
    args,
    { view_id: isNonEmptyString, mode: isStringEnum(["fit_scene", "fit_object"]) },
    { fit_handle: isNonEmptyString }
  );
  if (error) return error;
  const obj = args as Record<string, unknown>;
  if (obj.mode === "fit_object" && !isNonEmptyString(obj.fit_handle)) {
    return "fit_handle required when mode=fit_object";
  }
  return null;
};

const validateAddPrimitive = (args: unknown): string | null => {
  const error = validateObject(
    args,
    { scene_id: isNonEmptyString, type: isNonEmptyString },
    { ...nodeOptions, color: isColor, params: isObject }
  );
  if (error) return error;
  const obj = args as Record<string, unknown>;
  const type = obj.type as string;
  if (!isStringEnum(["box", "sphere", "cylinder", "cone", "plane", "arrow", "axes", "text_3d"])(type)) {
    return "invalid field: type";
  }
  return null;
};

const validateAddMesh = (args: unknown): string | null => {
  const error = validateObject(
    args,
    {
      scene_id: isNonEmptyString,
      vertices: (value) => isBufferRef(value, "f32", [0, 3]),
      faces: (value) => value !== undefined,
    },
    {
      ...nodeOptions,
      normals: (value) => isBufferRef(value, "f32", [0, 3]),
      colors: (value) => isBufferRef(value, "u8", [0, 3]),
      color: isColor,
      faces_format: isStringEnum(["tri", "poly"]),
      alpha: isNumber,
      wireframe: isBoolean,
      smooth_shading: isBoolean,
    }
  );
  if (error) return error;
  const obj = args as Record<string, unknown>;

  // Check mutual exclusivity of color and colors
  if (obj.color !== undefined && obj.colors !== undefined) {
    return "color and colors must be mutually exclusive";
  }
  const format = (obj.faces_format as string | undefined) ?? "tri";
  if (format === "tri") {
    if (!isBufferRef(obj.faces, "u32", [0, 3])) {
      return "invalid field: faces";
    }
    return null;
  }
  if (!isObject(obj.faces)) {
    return "invalid field: faces";
  }
  const faces = obj.faces as Record<string, unknown>;
  if (!isBufferRef(faces.counts, "u32", [0])) {
    return "invalid field: faces.counts";
  }
  if (!isBufferRef(faces.indices, "u32", [0])) {
    return "invalid field: faces.indices";
  }
  return null;
};

const validateRemoveObjects = (args: unknown): string | null =>
  validateObject(
    args,
    {
      handles: (value) => Array.isArray(value) && value.every(isNonEmptyString),
    },
    { scene_id: isNonEmptyString }
  );

const validateCloneObject = (args: unknown): string | null =>
  validateObject(
    args,
    { handle: isNonEmptyString },
    { group_id: isNonEmptyString }
  );

const validateAddInstances = (args: unknown): string | null =>
  validateObject(
    args,
    {
      scene_id: isNonEmptyString,
      type: isStringEnum(["box", "sphere", "axes"]),
      positions: (value) => isBufferRef(value, "f32", [0, 3]),
    },
    {
      quats: (value) => isBufferRef(value, "f32", [0, 4]),
      scales: (value) => isBufferRef(value, "f32", [0, 3]),
      colors: (value) => isBufferRef(value, "u8", [0, 3]),
      color: isColor,
      alpha: isNumber,
      params: isObject,
    }
  );

const validateUpdateInstances = (args: unknown): string | null =>
  validateObject(
    args,
    {
      handle: isNonEmptyString,
    },
    {
      positions: (value) => isBufferRef(value, "f32", [0, 3]),
      quats: (value) => isBufferRef(value, "f32", [0, 4]),
      scales: (value) => isBufferRef(value, "f32", [0, 3]),
      colors: (value) => isBufferRef(value, "u8", [0, 3]),
      color: isColor,
      alpha: isNumber,
    }
  );

const validateSetObjectColors = (args: unknown): string | null =>
  validateObject(
    args,
    {
      items: (value) =>
        Array.isArray(value) &&
        value.every((item) =>
          validateObject(item, { handle: isNonEmptyString, rgba: isRgba }, { scene_id: isNonEmptyString }) === null
        ),
    },
    { scene_id: isNonEmptyString }
  );

const validateSetObjectAlphas = (args: unknown): string | null =>
  validateObject(
    args,
    {
      items: (value) =>
        Array.isArray(value) &&
        value.every((item) =>
          validateObject(item, { handle: isNonEmptyString, alpha: isNumber }, { scene_id: isNonEmptyString }) === null
        ),
    },
    { scene_id: isNonEmptyString }
  );

const validateSetObjectVisibilities = (args: unknown): string | null =>
  validateObject(
    args,
    {
      items: (value) =>
        Array.isArray(value) &&
        value.every((item) =>
          validateObject(item, { handle: isNonEmptyString, visible: isBoolean }, { scene_id: isNonEmptyString }) === null
        ),
    },
    { scene_id: isNonEmptyString }
  );

const COMMAND_VALIDATORS: Record<string, (args: unknown) => string | null> = {
  create_buffer: (args) =>
    validateObject(
      args,
      { size_bytes: isInteger, dtype: isStringEnum(["f32", "u32", "u16", "u8"]) },
      { shape: isShape }
    ),
  upload_buffer_chunk: (args) =>
    validateObject(
      args,
      {
        buffer_id: isNonEmptyString,
        offset_bytes: isInteger,
        chunk_bytes: isInteger,
      },
      { data_base64: isNonEmptyString }
    ),
  free_buffer: (args) => validateObject(args, { buffer_id: isNonEmptyString }),

  create_scene: (args) => validateObject(args, {}, { scene_id: isNonEmptyString }),
  create_view: (args) =>
    validateObject(
      args,
      {},
      {
        view_id: isNonEmptyString,
        title: isNonEmptyString,
        width: isNumber,
        height: isNumber,
        scene_id: isNonEmptyString,
        mount: (value) =>
          validateObject(
            value,
            { kind: isNonEmptyString, element_id: isNonEmptyString },
            {}
          ) === null,
      }
    ),
  clear_scene: (args) =>
    validateObject(args, { scene_id: isNonEmptyString }, { view_id: isNonEmptyString }),
  destroy_scene: (args) => validateObject(args, { scene_id: isNonEmptyString }),
  destroy_view: (args) => validateObject(args, { view_id: isNonEmptyString }),
  attach_scene: (args) => validateObject(args, { view_id: isNonEmptyString, scene_id: isNonEmptyString }),
  present_view: (args) => validateObject(args, {
    browser_session: value => isString(value) && /^[A-Za-z0-9_-]{1,128}$/.test(value),
    view_id: isNonEmptyString,
  }),
  list_scenes: (args) => validateObject(args, {}),
  list_views: (args) => validateObject(args, {}),
  get_scene_snapshot: (args) => validateObject(args, { scene_id: isNonEmptyString }),

  add_node: (args) => validateObject(args, { scene_id: isNonEmptyString }, nodeOptions),
  add_primitive: validateAddPrimitive,
  add_points: (args) => {
    const positions = (value: unknown) => isBufferRef(value, "f32", [0, 3]);
    const colors = (value: unknown) => isBufferRef(value, "u8", [0, 3]) || isBufferRef(value, "u8", [0, 4]);
    const error = validateObject(args, { scene_id: isNonEmptyString }, {
      ...nodeOptions, positions, colors, color: isColor, size: isNumber, group_id: isNonEmptyString,
      chunks: (value) => Array.isArray(value) && value.length > 0 &&
        value.every(chunk => isObject(chunk) && isObject(chunk.positions) &&
          Array.isArray(chunk.positions.shape) &&
          validateObject(chunk, { positions }, { colors }) === null &&
          (chunk.colors === undefined || (isObject(chunk.colors) && Array.isArray(chunk.colors.shape) &&
            chunk.colors.shape[0] === chunk.positions.shape[0]))),
    });
    if (error || !isObject(args)) return error;
    if (args.chunks !== undefined) {
      if (["positions", "colors", "group_id"].some(key => args[key] !== undefined)) {
        return "chunks cannot be combined with positions, colors or group_id";
      }
      if (args.color !== undefined && (args.chunks as Array<Record<string, unknown>>).some(chunk => chunk.colors !== undefined)) {
        return "colors and color are mutually exclusive";
      }
    } else if (args.positions === undefined) {
      return "positions or chunks required";
    }
    if (args.colors !== undefined && args.color !== undefined) return "colors and color are mutually exclusive";
    return null;
  },
  add_lines: (args) =>
    validateObject(
      args,
      {
        scene_id: isNonEmptyString,
        positions: (value) => isBufferRef(value, "f32", [0, 3]),
      },
      {
        ...nodeOptions,
        indices: (value) => isBufferRef(value, "u32", [0, 2]),
        width: isNumber,
        color: isColor,
      }
    ),
  add_mesh: validateAddMesh,
  load_mesh: (args) =>
    validateObject(
      args,
      { scene_id: isNonEmptyString, url: isNonEmptyString },
      { ...nodeOptions, scale: isVec3, color: isColor }
    ),
  add_text_3d: (args) =>
    validateObject(
      args,
      {
        scene_id: isNonEmptyString,
        text: isNonEmptyString,
        pos: isVec3,
        font_size: isNumber,
        color: isColor,
      },
      { ...nodeOptions, background_color: isString }
    ),
  update_text_3d: (args) =>
    validateObject(
      args,
      { handle: isNonEmptyString },
      { text: isNonEmptyString, pos: isVec3, font_size: isNumber, color: isColor }
    ),
  remove_text_3d: (args) => validateObject(args, { handle: isNonEmptyString }),
  add_text_2d: (args) =>
    validateObject(
      args,
      {
        view_id: isNonEmptyString,
        text: isNonEmptyString,
        x: isNumber,
        y: isNumber,
        font_size: isNumber,
        color: isColor,
      },
      {}
    ),
  update_text_2d: (args) =>
    validateObject(
      args,
      { view_id: isNonEmptyString, handle: isNonEmptyString },
      { text: isNonEmptyString, x: isNumber, y: isNumber, font_size: isNumber, color: isColor }
    ),
  remove_object: validateRemoveObject,
  remove_objects: validateRemoveObjects,
  clone_object: validateCloneObject,
  is_object_alive: (args) => validateObject(args, { handle: isNonEmptyString }),

  set_transform: (args) =>
    validateObject(
      args,
      { handle: isNonEmptyString, pose: isPose },
      poseOptions
    ),
  set_parent: (args) => validateObject(args, { handle: isNonEmptyString, parent: isParent }, {
    scene_id: isNonEmptyString, local_transform: value => isPose(value, false),
  }),
  set_object_metadata: (args) => validateObject(args, { handle: isNonEmptyString }, {
    scene_id: isNonEmptyString, name: isName, tags: isTags,
  }),
  set_geometry_scale: (args) => validateObject(args, { handle: isNonEmptyString, geometry_scale: isVec3 }, {
    scene_id: isNonEmptyString,
  }),
  set_object_transforms: (args) =>
    validateObject(
      args,
      {
        items: (value) =>
          Array.isArray(value) &&
          value.every((item) =>
            validateObject(item, { handle: isNonEmptyString, pose: isPose }, poseOptions) === null
          ),
      },
      { scene_id: isNonEmptyString }
    ),
  set_object_colors: validateSetObjectColors,
  set_object_alphas: validateSetObjectAlphas,
  set_object_visibilities: validateSetObjectVisibilities,
  set_color: (args) =>
    validateObject(
      args,
      { handle: isNonEmptyString, rgba: isRgba },
      { target: isStringEnum(["scene", "overlay"]), view_id: isNonEmptyString, scene_id: isNonEmptyString }
    ),
  set_alpha: (args) =>
    validateObject(
      args,
      { handle: isNonEmptyString, alpha: isNumber },
      { target: isStringEnum(["scene", "overlay"]), view_id: isNonEmptyString, scene_id: isNonEmptyString }
    ),
  set_visible: (args) =>
    validateObject(
      args,
      { handle: isNonEmptyString, visible: isBoolean },
      { target: isStringEnum(["scene", "overlay"]), view_id: isNonEmptyString, scene_id: isNonEmptyString }
    ),
  get_transform: (args) => validateObject(args, { handle: isNonEmptyString }, {
    scene_id: isNonEmptyString, space: isStringEnum(["local", "world"]), matrix: isBoolean,
  }),
  get_color: (args) => validateObject(args, { handle: isNonEmptyString }),
  get_alpha: (args) => validateObject(args, { handle: isNonEmptyString }),
  get_visible: (args) => validateObject(args, { handle: isNonEmptyString }),
  list_objects: (args) =>
    validateObject(args, { scene_id: isNonEmptyString }, { include_internal: isBoolean }),
  get_view_config: (args) => validateObject(args, { view_id: isNonEmptyString }),
  get_camera_controls: (args) => validateObject(args, { view_id: isNonEmptyString }),

  set_camera_pose: (args) =>
    validateObject(
      args,
      { view_id: isNonEmptyString, eye: isVec3, target: isVec3, up: isVec3 },
      {}
    ),
  get_camera_pose: (args) => validateObject(args, { view_id: isNonEmptyString }),
  reset_camera: validateResetCamera,
  set_camera_controls: (args) =>
    validateObject(
      args,
      { view_id: isNonEmptyString },
      {
        zoom_to_cursor: isBoolean,
        orbit_enabled: isBoolean,
        pan_enabled: isBoolean,
        zoom_enabled: isBoolean,
        rotate_sensitivity: isNumber,
        pan_sensitivity: isNumber,
        zoom_sensitivity: isNumber,
        damping: isBoolean,
        mouse_preset: isStringEnum(["cad", "trackpad"]),
        mouse_buttons: isMouseButtons,
        fov: isNumber,
      }
    ),
  set_view: (args) =>
    validateObject(
      args,
      {
        view_id: isNonEmptyString,
        view: isStringEnum([
          "home",
          "front",
          "left",
          "top",
          "back",
          "right",
          "bottom",
        ]),
      },
      { fit_all: isBoolean }
    ),
  set_render_mode: (args) =>
    validateObject(
      args,
      { view_id: isNonEmptyString, mode: isStringEnum(["solid", "wireframe", "points"]) },
      {}
    ),
  set_keyboard_shortcuts: (args) =>
    validateObject(
      args,
      { view_id: isNonEmptyString, enabled: isBoolean },
      {}
    ),
  set_interaction_mode: (args) =>
    validateObject(
      args,
      {},
      { enabled: isBoolean, gizmo_enabled: isBoolean, picking_enabled: isBoolean }
    ),
  set_view_config: (args) =>
    validateObject(
      args,
      { view_id: isNonEmptyString, config: isObject },
      {}
    ),
  add_instances: validateAddInstances,
  update_instances: validateUpdateInstances,

  set_log_config: (args) =>
    validateObject(
      args,
      {},
      {
        min_level: isNonEmptyString,
        sinks: (value) =>
          Array.isArray(value) &&
          value.every(
            (sink) =>
              validateObject(
                sink,
                { type: isNonEmptyString },
                { enabled: isBoolean, path: isNonEmptyString },
                true
              ) === null
          ),
      },
      true
    ),
  read_logs: (args) =>
    validateObject(
      args,
      {},
      { after_seq: isInteger, limit: isInteger }
    ),

  attach_gizmo: (args) =>
    validateObject(
      args,
      {
        ...nodeOptions,
        view_id: isNonEmptyString,
        handle: isNonEmptyString,
      },
      {
        size: isNumber,
        mask: isInteger,
        scale_mode: isStringEnum(["screen", "world"]),
      }
    ),
  set_gizmo_mode: (args) =>
    validateObject(
      args,
      { view_id: isNonEmptyString },
      {
        size: isNumber,
        mask: isInteger,
        scale_mode: isStringEnum(["screen", "world"]),
      }
    ),
  detach_gizmo: (args) => validateObject(args, { view_id: isNonEmptyString }),

  set_pick_config: (args) =>
    validateObject(
      args,
      { view_id: isNonEmptyString },
      {
        enabled: isBoolean,
        mode: isStringEnum(["object", "point"]),
        button: (value) => isInteger(value) && value >= 0 && value <= 2,
        ctrl_modifier: isBoolean,
        highlight_color: isColor,
        marker_size: isNumber,
        point_threshold: isNumber,
        line_threshold: isNumber,
      }
    ),
  clear_pick_highlight: (args) => validateObject(args, { view_id: isNonEmptyString }),
  get_picked_info: (args) => validateObject(args, { view_id: isNonEmptyString }),
  get_pick_config: (args) => validateObject(args, { view_id: isNonEmptyString }),
};

export const validateCommandArgs = (
  name: string,
  args: unknown
): ValidationResult => {
  const validator = COMMAND_VALIDATORS[name];
  if (!validator) {
    return { ok: false, error: `unknown command: ${name}` };
  }
  const error = validator(args);
  if (error) {
    return { ok: false, error };
  }
  return { ok: true };
};

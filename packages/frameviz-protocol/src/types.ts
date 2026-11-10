import { ERROR_CODES, PROTOCOL_VERSION } from "./constants.js";

export type ProtocolVersion = `${number}.${number}.${number}`;
export type ErrorCode = (typeof ERROR_CODES)[number];

// P3-2: Branded Types to prevent ID type confusion at compile time
// These are still strings at runtime, but TypeScript prevents mixing them up
type Brand<T, B> = T & { readonly __brand: B };

export type Handle = Brand<string, 'Handle'>;
export type SceneId = Brand<string, 'SceneId'>;
export type ViewId = Brand<string, 'ViewId'>;
export type BufferId = Brand<string, 'BufferId'>;

// Helper to create branded IDs (for use in Host/SDK)
export function asHandle(s: string): Handle { return s as Handle; }
export function asSceneId(s: string): SceneId { return s as SceneId; }
export function asViewId(s: string): ViewId { return s as ViewId; }
export function asBufferId(s: string): BufferId { return s as BufferId; }


export type EnvelopeType = "cmd" | "resp" | "event";

export type JsonObject = Record<string, unknown>;

/** Client -> Host command envelope. */
export interface CommandEnvelope {
  protocol_version: ProtocolVersion;
  type: "cmd";
  id: string;
  name: string;
  args: JsonObject;
}

/** Error payload used in failed responses. */
export interface ErrorPayload {
  code: ErrorCode | string;
  message: string;
}

/** Host -> Client response envelope. */
export interface ResponseEnvelope {
  protocol_version: ProtocolVersion;
  type: "resp";
  id: string;
  ok: boolean;
  result: JsonObject | null;
  error: ErrorPayload | null;
}

/** Host -> Client event envelope. */
export interface EventEnvelope {
  protocol_version: ProtocolVersion;
  type: "event";
  name: string;
  data: JsonObject;
}

export type Envelope = CommandEnvelope | ResponseEnvelope | EventEnvelope;

/** Position + rotation in the Z-up right-handed coordinate system. */
export interface Pose {
  pos: [number, number, number];
  quat: [number, number, number, number];
  scale?: [number, number, number];
}

export type BufferDtype = "f32" | "u32" | "u16" | "u8";

/** Reference to a binary buffer owned by the Host. */
export interface BufferRef {
  buffer_id: BufferId;
  dtype: BufferDtype;
  shape: number[];
}

/** Standard log entry used by read_logs and log events. */
export interface LogEntry {
  seq: number;
  ts_ms: number;
  level: string;
  logger: string;
  msg: string;
  fields: JsonObject;
}

// ============================================================================
// Viewer Registration Types (Embedded UI Support)
// ============================================================================

export type ViewerName = Brand<string, 'ViewerName'>;
export function asViewerName(s: string): ViewerName { return s as ViewerName; }

/** Viewer info returned by registration and query commands */
export interface ViewerInfo {
  viewer_name: ViewerName;
  view_id: ViewId;
  scene_id: SceneId;
}

/** Args for register_viewer command (Viewer → Host) */
export interface RegisterViewerArgs {
  viewer_name: string;
  scene_id?: string;  // Optional, auto-created if not provided
}

/** Result of register_viewer command */
export interface RegisterViewerResult {
  view_id: string;
  scene_id: string;
  viewer_name: string;
}

/** Args for get_viewer_by_name command (SDK → Host) */
export interface GetViewerByNameArgs {
  viewer_name: string;
}

/** Result of get_viewer_by_name command */
export interface GetViewerByNameResult {
  view_id: string;
  scene_id: string;
  viewer_name: string;
}

/** Result of list_viewers command */
export interface ListViewersResult {
  viewers: ViewerInfo[];
}

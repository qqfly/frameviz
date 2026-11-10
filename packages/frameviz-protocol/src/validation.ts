import { PROTOCOL_VERSION } from "./constants.js";
import { isProtocolCompatible } from "./version.js";
import type {
  CommandEnvelope,
  Envelope,
  EventEnvelope,
  ResponseEnvelope
} from "./types.js";

type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; error: string };

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const hasOwn = (value: Record<string, unknown>, key: string): boolean =>
  Object.prototype.hasOwnProperty.call(value, key);

const hasString = (value: Record<string, unknown>, key: string): boolean =>
  typeof value[key] === "string" && value[key] !== "";

const hasBoolean = (value: Record<string, unknown>, key: string): boolean =>
  typeof value[key] === "boolean";

const isProtocolVersion = (value: Record<string, unknown>): boolean =>
  isProtocolCompatible(value.protocol_version, PROTOCOL_VERSION);

const hasOnlyKeys = (value: Record<string, unknown>, keys: string[]): boolean => {
  const allowed = new Set(keys);
  return Object.keys(value).every((key) => allowed.has(key));
};

const isErrorPayload = (value: unknown): boolean =>
  isObject(value) && hasString(value, "code") && hasString(value, "message");

export const isCommandEnvelope = (value: unknown): value is CommandEnvelope => {
  if (!isObject(value)) return false;
  if (!hasOnlyKeys(value, ["protocol_version", "type", "id", "name", "args"])) {
    return false;
  }
  return (
    isProtocolVersion(value) &&
    value.type === "cmd" &&
    hasString(value, "id") &&
    hasString(value, "name") &&
    isObject(value.args)
  );
};

export const isResponseEnvelope = (value: unknown): value is ResponseEnvelope => {
  if (!isObject(value)) return false;
  if (!hasOnlyKeys(value, ["protocol_version", "type", "id", "ok", "result", "error"])) {
    return false;
  }
  const ok = value.ok === true;
  return (
    isProtocolVersion(value) &&
    value.type === "resp" &&
    hasString(value, "id") &&
    hasBoolean(value, "ok") &&
    hasOwn(value, "result") &&
    hasOwn(value, "error") &&
    (ok
      ? isObject(value.result) && value.error === null
      : value.result === null && isErrorPayload(value.error))
  );
};

export const isEventEnvelope = (value: unknown): value is EventEnvelope => {
  if (!isObject(value)) return false;
  if (!hasOnlyKeys(value, ["protocol_version", "type", "name", "data"])) {
    return false;
  }
  return (
    isProtocolVersion(value) &&
    value.type === "event" &&
    hasString(value, "name") &&
    isObject(value.data)
  );
};

export const validateEnvelope = (value: unknown): ValidationResult<Envelope> => {
  if (isCommandEnvelope(value)) return { ok: true, value };
  if (isResponseEnvelope(value)) return { ok: true, value };
  if (isEventEnvelope(value)) return { ok: true, value };
  return { ok: false, error: "Invalid protocol envelope." };
};

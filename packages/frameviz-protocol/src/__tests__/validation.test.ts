import { describe, expect, it } from "vitest";
import { PROTOCOL_VERSION } from "../constants";
import {
  isCommandEnvelope,
  isEventEnvelope,
  isResponseEnvelope,
  validateEnvelope,
} from "../validation";

describe("protocol envelope validation", () => {
  it.each(["0.4.1", "0.4.99"])("accepts patch version %s", (version) => {
    expect(isCommandEnvelope({protocol_version: version, type: "cmd", id: "patch", name: "create_scene", args: {}})).toBe(true);
  });
  it.each(["0.5.0", "0.3.9", "0.04.1", "0.4.01", "0.4.1-beta", "0.4.9999999999"])("rejects unsupported version %s", (version) => {
    expect(isCommandEnvelope({protocol_version: version, type: "cmd", id: "bad", name: "create_scene", args: {}})).toBe(false);
  });
  it("accepts a valid command envelope", () => {
    const envelope = {
      protocol_version: PROTOCOL_VERSION,
      type: "cmd",
      id: "c_1",
      name: "create_scene",
      args: {},
    };

    expect(isCommandEnvelope(envelope)).toBe(true);
    expect(validateEnvelope(envelope).ok).toBe(true);
  });

  it("rejects a command envelope with extra keys", () => {
    const envelope = {
      protocol_version: PROTOCOL_VERSION,
      type: "cmd",
      id: "c_2",
      name: "create_scene",
      args: {},
      extra: 123,
    };

    expect(isCommandEnvelope(envelope)).toBe(false);
  });

  it("accepts an ok response envelope", () => {
    const envelope = {
      protocol_version: PROTOCOL_VERSION,
      type: "resp",
      id: "c_3",
      ok: true,
      result: {},
      error: null,
    };

    expect(isResponseEnvelope(envelope)).toBe(true);
  });

  it("accepts an error response envelope", () => {
    const envelope = {
      protocol_version: PROTOCOL_VERSION,
      type: "resp",
      id: "c_4",
      ok: false,
      result: null,
      error: { code: "ERR_INVALID_ARGS", message: "bad args" },
    };

    expect(isResponseEnvelope(envelope)).toBe(true);
  });

  it("rejects mismatched ok/error response envelopes", () => {
    const missingError = {
      protocol_version: PROTOCOL_VERSION,
      type: "resp",
      id: "c_5",
      ok: false,
      result: null,
      error: null,
    };
    const missingResult = {
      protocol_version: PROTOCOL_VERSION,
      type: "resp",
      id: "c_6",
      ok: true,
      result: null,
      error: null,
    };

    expect(isResponseEnvelope(missingError)).toBe(false);
    expect(isResponseEnvelope(missingResult)).toBe(false);
  });

  it("accepts a valid event envelope", () => {
    const envelope = {
      protocol_version: PROTOCOL_VERSION,
      type: "event",
      name: "viewer_ready",
      data: { view_id: "v_1" },
    };

    expect(isEventEnvelope(envelope)).toBe(true);
  });
});

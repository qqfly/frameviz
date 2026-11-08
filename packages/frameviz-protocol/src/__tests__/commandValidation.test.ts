import { describe, expect, it } from "vitest";
import { validateCommandArgs } from "../commandValidation";

describe("command argument validation", () => {
  it("accepts a valid create_buffer args", () => {
    const result = validateCommandArgs("create_buffer", {
      size_bytes: 12,
      dtype: "f32",
      shape: [1, 3],
    });
    expect(result.ok).toBe(true);
  });

  it("rejects invalid dtype in create_buffer", () => {
    const result = validateCommandArgs("create_buffer", {
      size_bytes: 12,
      dtype: "f64",
    });
    expect(result.ok).toBe(false);
  });

  it("rejects remove_object with both scene_id and view_id", () => {
    const result = validateCommandArgs("remove_object", {
      handle: "h_1",
      scene_id: "s_1",
      view_id: "v_1",
    });
    expect(result.ok).toBe(false);
  });

  it("requires fit_handle for reset_camera fit_object", () => {
    const result = validateCommandArgs("reset_camera", {
      view_id: "v_1",
      mode: "fit_object",
    });
    expect(result.ok).toBe(false);
  });

  it("rejects invalid add_points positions shape", () => {
    const result = validateCommandArgs("add_points", {
      scene_id: "s_1",
      positions: { buffer_id: "b_1", dtype: "f32", shape: [3] },
    });
    expect(result.ok).toBe(false);
  });

  it("rejects invalid render mode", () => {
    const result = validateCommandArgs("set_render_mode", {
      view_id: "v_1",
      mode: "invalid",
    });
    expect(result.ok).toBe(false);
  });

  it("accepts add_mesh with smooth_shading", () => {
    const result = validateCommandArgs("add_mesh", {
      scene_id: "s_1",
      vertices: { buffer_id: "b_v", dtype: "f32", shape: [3, 3] },
      faces: { buffer_id: "b_f", dtype: "u32", shape: [1, 3] },
      smooth_shading: true,
    });
    expect(result.ok).toBe(true);
  });

  it("rejects add_mesh with invalid smooth_shading type", () => {
    const result = validateCommandArgs("add_mesh", {
      scene_id: "s_1",
      vertices: { buffer_id: "b_v", dtype: "f32", shape: [3, 3] },
      faces: { buffer_id: "b_f", dtype: "u32", shape: [1, 3] },
      smooth_shading: "true",
    });
    expect(result.ok).toBe(false);
  });
});

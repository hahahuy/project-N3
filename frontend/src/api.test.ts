import { afterEach, describe, expect, it, vi } from "vitest";
import { apiUrl, previewVariant } from "./api";

describe("API boundary", () => {
  it("keeps browser requests under the local API prefix", () => {
    expect(apiUrl("/scenarios")).toMatch(/\/api\/scenarios$/);
  });

  afterEach(() => vi.restoreAllMocks());

  it("posts the typed preview request to the selected scenario", async () => {
    const response = {
      parent_scenario_id: "scene-1",
      variant_id: "scene-1--preview-a",
      status: "valid",
      behavior: { requested: "parameterized", status: "supported" },
      configuration: {},
      provenance: {},
      paths: [],
      validation: null,
      gates: [],
      replay_metrics: {},
      artifacts: [],
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(response), { status: 200 }),
    );

    await previewVariant("scene-1", {
      actor_edits: [{ actor_id: "ego", speed_multiplier: 1.1, heading_offset_rad: 0.1, timing_offset_s: 0, initial_gap_delta_m: 0 }],
      replay_mode: "waypoint",
      behavior: "parameterized",
      seed: 7,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/scenarios/scene-1/variants/preview",
      expect.objectContaining({ method: "POST", headers: { "Content-Type": "application/json" } }),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({ seed: 7, behavior: "parameterized" });
  });
});

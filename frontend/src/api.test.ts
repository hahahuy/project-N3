import { afterEach, describe, expect, it, vi } from "vitest";
import {
  addRecipeStep,
  addRollbackMarker,
  apiUrl,
  fetchActorTimeline,
  fetchCompare,
  fetchEsminiCapability,
  fetchLiveCapability,
  fetchLiveState,
  fetchEvidenceLayers,
  fetchGateTimeline,
  fetchLidarCapability,
  fetchLidarDescriptor,
  fetchNativeMapCapability,
  fetchPOVFrame,
  fetchPOVImageFrame,
  fetchRecipe,
  fetchVariantSensorStatus,
  fetchVariantLineage,
  lidarPayloadUrl,
  moveRecipeStep,
  previewVariant,
  redoRecipe,
  removeRecipeStep,
  restoreRollbackMarker,
  setRecipeStepActive,
  undoRecipe,
} from "./api";

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
      provenance: { simulator_version: "kinematic-open-loop-v1" },
      paths: [],
      validation: null,
      gates: [],
      replay_metrics: {},
      artifacts: [],
      recipe_steps: [],
      limits: {},
      violations: [],
      rollback_marker: null,
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

  it("keeps native map and LiDAR capability calls typed and local", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ available: false, unavailable_reason: "dataset_not_configured" }), { status: 200 }));
    await fetchNativeMapCapability("singapore-onenorth");
    await fetchLidarCapability();
    expect(fetch).toHaveBeenNthCalledWith(1, "/api/workspace/maps/singapore-onenorth/capability", undefined);
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/workspace/lidar/capability", undefined);
  });

  it("requests a timeline-selected simulator frame", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "rendered" }), { status: 200 }));
    await fetchPOVFrame("scene 1", "third-person", 1.25);
    expect(fetch).toHaveBeenCalledWith("/api/workspace/scenarios/scene%201/frames/third-person?time_s=1.25", undefined);
  });

  it("keeps live esmini capability and state requests separate from image frames", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ contract_version: "esmini-live-session-v1", status: "unavailable" }), { status: 200 }));
    await fetchLiveCapability();
    await fetchLiveState("live-1");
    expect(fetch).toHaveBeenNthCalledWith(1, "/api/esmini/live/capability", undefined);
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/esmini/live/sessions/live-1", undefined);
  });

  it("requests explicit image-frame and variant sensor-status contracts", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ status: "unavailable" }), { status: 200 }));
    await fetchPOVImageFrame("scene 1", "third-person", 1.25);
    await fetchVariantSensorStatus("scene 1");
    expect(fetch).toHaveBeenNthCalledWith(1, "/api/workspace/scenarios/scene%201/image-frames/third-person?time_s=1.25", undefined);
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/workspace/scenarios/scene%201/sensor-status", undefined);
  });

  it("requests the actor timeline and gate timeline for the selected scenario", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ contract_version: "workspace-actor-timeline-v1" }), { status: 200 }));
    const tracks = await fetchActorTimeline("scene 1");
    await fetchGateTimeline("scene 1");
    expect(fetch).toHaveBeenNthCalledWith(1, "/api/workspace/scenarios/scene%201/timeline", undefined);
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/workspace/scenarios/scene%201/gate-timeline", undefined);
    expect(tracks.contract_version).toBe("workspace-actor-timeline-v1");
  });

  it("surfaces a verbatim API error instead of an empty timeline", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "boom" }), { status: 500 }));
    await expect(fetchGateTimeline("scene-1")).rejects.toThrow("boom");
  });

  it("addresses the real private LiDAR descriptor and decimated payload", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ available: true, sample_data_token: "sample-data-1" }), { status: 200 }));
    await fetchLidarDescriptor("scene 1");
    expect(fetch).toHaveBeenCalledWith("/api/workspace/scenarios/scene%201/lidar", undefined);
    expect(lidarPayloadUrl("sample-data-1", 16)).toBe("/api/workspace/lidar/sample-data-1?decimation=16");
  });
});

describe("recipe, lineage and compare boundary", () => {
  afterEach(() => vi.restoreAllMocks());

  it("reads the ordered recipe document of the selected scenario", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ contract_version: "workspace-recipe-v1", steps: [] }), { status: 200 }));

    const document = await fetchRecipe("scene 1");

    expect(fetch).toHaveBeenCalledWith("/api/workspace/scenarios/scene%201/recipe", undefined);
    expect(document.contract_version).toBe("workspace-recipe-v1");
  });

  it("posts ordered recipe mutations with the constrained maneuver payload", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ contract_version: "workspace-recipe-v1" }), { status: 200 }));
    const step = {
      step_id: "step-1",
      name: "Ease off the lead",
      kind: "constrained-maneuver" as const,
      actor_edit: { actor_id: "lead", speed_multiplier: 0.9, heading_offset_rad: 0, timing_offset_s: 0, initial_gap_delta_m: -1, braking_mps2: 2 },
      active: true,
    };

    await addRecipeStep("scene 1", step);
    await setRecipeStepActive("scene 1", "step-1", false);
    await moveRecipeStep("scene 1", "step-1", "up");
    await removeRecipeStep("scene 1", "step-1");
    await addRollbackMarker("scene 1", "before the cut-in");
    await restoreRollbackMarker("scene 1", "marker-1");
    await undoRecipe("scene 1");
    await redoRecipe("scene 1");

    const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls.map((call) => call[0])).toEqual([
      "/api/workspace/scenarios/scene%201/recipe/steps",
      "/api/workspace/scenarios/scene%201/recipe/steps/step-1/active",
      "/api/workspace/scenarios/scene%201/recipe/steps/move",
      "/api/workspace/scenarios/scene%201/recipe/steps/step-1/remove",
      "/api/workspace/scenarios/scene%201/recipe/markers",
      "/api/workspace/scenarios/scene%201/recipe/markers/marker-1/restore",
      "/api/workspace/scenarios/scene%201/recipe/undo",
      "/api/workspace/scenarios/scene%201/recipe/redo",
    ]);
    for (const call of calls) {
      expect(call[1]).toMatchObject({ method: "POST", headers: { "Content-Type": "application/json" } });
    }
    expect(JSON.parse(String(calls[0][1]?.body))).toMatchObject({ step_id: "step-1", actor_edit: { actor_id: "lead", braking_mps2: 2 } });
    expect(JSON.parse(String(calls[1][1]?.body))).toEqual({ active: false });
    expect(JSON.parse(String(calls[2][1]?.body))).toEqual({ step_id: "step-1", direction: "up" });
    expect(JSON.parse(String(calls[4][1]?.body))).toEqual({ name: "before the cut-in" });
  });

  it("reads lineage, evidence layers and a synchronized comparison", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ contract_version: "workspace-variant-lineage-v1" }), { status: 200 }));

    await fetchVariantLineage("scene 1");
    await fetchEvidenceLayers("scene 1");
    await fetchCompare("scene 1", "scene 2", 1.25);

    expect(fetch).toHaveBeenNthCalledWith(1, "/api/workspace/scenarios/scene%201/lineage", undefined);
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/workspace/scenarios/scene%201/evidence-layers", undefined);
    expect(fetch).toHaveBeenNthCalledWith(3, "/api/workspace/scenarios/scene%201/compare?against=scene%202&time_s=1.25", undefined);
  });

  it("surfaces a verbatim recipe rejection instead of a silent local edit", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "actor_is_not_present_in_this_scenario:ghost" }), { status: 409 }));

    await expect(
      addRecipeStep("scene 1", {
        step_id: "step-ghost",
        name: "Move an absent actor",
        actor_edit: { actor_id: "ghost", speed_multiplier: 1, heading_offset_rad: 0, timing_offset_s: 0, initial_gap_delta_m: 0 },
      }),
    ).rejects.toThrow("actor_is_not_present_in_this_scenario:ghost");
  });
});

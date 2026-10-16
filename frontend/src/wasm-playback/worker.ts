import createEsminiModule from "../../wasm-esmini/dist/esmini.js";
import type { WasmFrame, WasmObjectState, WasmRoadGeometry, WasmWorkerRequest, WasmWorkerResponse } from "./types";

let scenario: {
  step_frame(dt: number): { simulation_time: number; object_states: unknown };
  reset(): void;
  get_road_geometry(): { lane_surfaces: unknown; road_marks: unknown };
} | null = null;

function vectorItems<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object" && "size" in value && "get" in value && typeof value.size === "function" && typeof value.get === "function") {
    const vector = value as { size(): number; get(index: number): T };
    return Array.from({ length: vector.size() }, (_, index) => vector.get(index));
  }
  return [];
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  if (error && typeof error === "object") {
    const candidate = error as { message?: unknown; what?: unknown; stack?: unknown };
    if (typeof candidate.message === "string") return candidate.message;
    if (typeof candidate.what === "string") return candidate.what;
    try { return JSON.stringify(error); } catch { return "unknown_wasm_error"; }
  }
  return String(error);
}

function normalizeRoad(value: { lane_surfaces: unknown; road_marks: unknown }): WasmRoadGeometry {
  return {
    lane_surfaces: vectorItems<{ left_boundary: unknown; right_boundary: unknown }>(value.lane_surfaces).map((surface) => ({
      left_boundary: vectorItems<WasmRoadGeometry["lane_surfaces"][number]["left_boundary"][number]>(surface.left_boundary),
      right_boundary: vectorItems<WasmRoadGeometry["lane_surfaces"][number]["right_boundary"][number]>(surface.right_boundary),
    })),
    road_marks: vectorItems<{ points: unknown }>(value.road_marks).map((mark) => ({ points: vectorItems<WasmRoadGeometry["road_marks"][number]["points"][number]>(mark.points) })),
  };
}

function frame(): WasmFrame {
  const value = scenario?.step_frame(0);
  return { simulation_time: value?.simulation_time ?? 0, object_states: vectorItems<WasmObjectState>(value?.object_states) };
}

async function init(xosc: string, xodr: string): Promise<WasmWorkerResponse> {
  const module = await createEsminiModule({ noInitialRun: true });
  module.FS.writeFile("/scenario.xosc", xosc);
  module.FS.writeFile("/smoke.xodr", xodr);
  const nextScenario = new module.OpenScenario("/scenario.xosc", {
    max_loop: 0,
    min_time_step: 0,
    max_time_step: 0,
    dt: 0.05,
  });
  scenario = nextScenario as typeof scenario;
  return { type: "ready", road: normalizeRoad(nextScenario.get_road_geometry()), frame: frame() };
}

self.onmessage = async (event: MessageEvent<WasmWorkerRequest>) => {
  try {
    if (event.data.type === "init") {
      self.postMessage(await init(event.data.xosc, event.data.xodr));
    } else if (!scenario) {
      throw new Error("wasm_scenario_not_initialized");
    } else if (event.data.type === "step") {
      scenario?.step_frame(event.data.dt);
      self.postMessage({ type: "frame", frame: frame() } satisfies WasmWorkerResponse);
    } else if (event.data.type === "reset") {
      scenario?.reset();
      self.postMessage({ type: "frame", frame: frame() } satisfies WasmWorkerResponse);
    } else if (event.data.type === "dispose") {
      scenario = null;
      self.close();
    }
  } catch (error) {
    self.postMessage({ type: "error", message: errorMessage(error) } satisfies WasmWorkerResponse);
  }
};

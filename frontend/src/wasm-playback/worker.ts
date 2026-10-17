import createEsminiModule from "../../wasm-esmini/dist/esmini.js";
import type { WasmFrame, WasmObjectState, WasmRoadGeometry, WasmWorkerRequest, WasmWorkerResponse } from "./types";
import { ENGINE_PRIME_DT, FIXED_DT, primeEngineScenario, resetEngineScenario } from "./types";

let scenario: {
  step_frame(dt: number): { simulation_time: number; object_states: unknown };
  get_simulation_time(): number;
  get_object_states(): unknown;
  reset(): void;
  get_road_geometry(): { lane_surfaces: unknown; road_marks: unknown };
} | null = null;
let playing = false;
let timer: ReturnType<typeof setTimeout> | null = null;

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

function currentFrame(): WasmFrame {
  return {
    simulation_time: scenario?.get_simulation_time() ?? 0,
    object_states: vectorItems<WasmObjectState>(scenario?.get_object_states()),
  };
}

function steppedFrame(): WasmFrame {
  if (!scenario) throw new Error("wasm_scenario_not_initialized");
  const value = scenario.step_frame(FIXED_DT);
  return { simulation_time: value.simulation_time, object_states: vectorItems<WasmObjectState>(value.object_states) };
}

function roadFilename(xosc: string): string {
  const match = xosc.match(/<LogicFile[^>]*filepath="([^"]+)"/i);
  const filepath = match?.[1]?.trim();
  if (!filepath) throw new Error("wasm_xosc_missing_logic_file");
  return filepath.split(/[\\/]/).pop() ?? filepath;
}

function stopClock(): void {
  playing = false;
  if (timer !== null) {
    clearTimeout(timer);
    timer = null;
  }
}

function step(): void {
  self.postMessage({ type: "frame", frame: steppedFrame() } satisfies WasmWorkerResponse);
}

function seek(timeS: number): void {
  if (!scenario || !Number.isFinite(timeS) || timeS < 0) throw new Error("wasm_invalid_seek_time");
  stopClock();
  resetEngineScenario(scenario);
  let frame = currentFrame();
  const steps = Math.ceil(timeS / FIXED_DT) + 1;
  for (let index = 0; index < steps && frame.simulation_time + FIXED_DT / 2 < timeS; index += 1) frame = steppedFrame();
  self.postMessage({ type: "frame", frame } satisfies WasmWorkerResponse);
}

function scheduleNextTick(): void {
  if (!playing || !scenario) return;
  timer = setTimeout(() => {
    timer = null;
    try {
      step();
      scheduleNextTick();
    } catch (error) {
      stopClock();
      self.postMessage({ type: "error", message: errorMessage(error) } satisfies WasmWorkerResponse);
    }
  }, FIXED_DT * 1000);
}

async function init(xosc: string, xodr: string): Promise<WasmWorkerResponse> {
  const module = await createEsminiModule({ noInitialRun: true });
  module.FS.writeFile("/scenario.xosc", xosc);
  module.FS.writeFile(`/${roadFilename(xosc)}`, xodr);
  const nextScenario = new module.OpenScenario("/scenario.xosc", {
    max_loop: 0,
    min_time_step: 0,
    max_time_step: 0,
    dt: ENGINE_PRIME_DT,
  });
  stopClock();
  scenario = nextScenario as typeof scenario;
  primeEngineScenario(nextScenario);
  return { type: "ready", road: normalizeRoad(nextScenario.get_road_geometry()), frame: currentFrame() };
}

self.onmessage = async (event: MessageEvent<WasmWorkerRequest>) => {
  try {
    if (event.data.type === "init") {
      self.postMessage(await init(event.data.xosc, event.data.xodr));
    } else if (!scenario) {
      throw new Error("wasm_scenario_not_initialized");
    } else if (event.data.type === "seek") {
      seek(event.data.time_s);
    } else if (event.data.type === "step") {
      step();
    } else if (event.data.type === "play") {
      if (!playing) {
        playing = true;
        scheduleNextTick();
      }
    } else if (event.data.type === "pause") {
      stopClock();
    } else if (event.data.type === "reset") {
      stopClock();
      resetEngineScenario(scenario);
      self.postMessage({ type: "frame", frame: currentFrame() } satisfies WasmWorkerResponse);
    } else if (event.data.type === "dispose") {
      stopClock();
      scenario = null;
      self.close();
    }
  } catch (error) {
    self.postMessage({ type: "error", message: errorMessage(error) } satisfies WasmWorkerResponse);
  }
};

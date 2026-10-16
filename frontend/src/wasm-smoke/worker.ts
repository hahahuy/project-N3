import createEsminiModule from "../../wasm-esmini/dist/esmini.js";
import xosc from "./fixture.xosc?raw";
import xodr from "./fixture.xodr?raw";

type SmokeRequest = { type: "run" };

function vectorLength(value: unknown): number {
  if (Array.isArray(value)) return value.length;
  if (value && typeof value === "object" && "size" in value && typeof value.size === "function") {
    return Number(value.size());
  }
  return 0;
}

self.onmessage = async (event: MessageEvent<SmokeRequest>) => {
  if (event.data.type !== "run") return;
  try {
    const module = await createEsminiModule({ noInitialRun: true });
    module.FS.writeFile("/scenario.xosc", xosc);
    module.FS.writeFile("/smoke.xodr", xodr);
    const scenario = new module.OpenScenario("/scenario.xosc", {
      max_loop: 0,
      min_time_step: 0,
      max_time_step: 0,
      dt: 0.05,
    });
    const frame = scenario.step_frame(0);
    const road = scenario.get_road_geometry();
    self.postMessage({
      type: "result",
      simulationTime: frame.simulation_time,
      objectCount: vectorLength(frame.object_states),
      laneSurfaceCount: vectorLength(road.lane_surfaces),
      roadMarkCount: vectorLength(road.road_marks),
    });
  } catch (error) {
    self.postMessage({ type: "error", message: error instanceof Error ? error.message : String(error) });
  }
};

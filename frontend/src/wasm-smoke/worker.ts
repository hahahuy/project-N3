import createEsminiModule from "../../wasm-esmini/dist/esmini.js";
import vehicleXosc from "./fixture.xosc?raw";
import pedestrianXosc from "./fixture-pedestrian.xosc?raw";
import xodr from "./smoke.xodr?raw";

type SmokeRequest = { type: "run" };
type SmokeObject = { name: string; type: string; kind: string };
type SmokeFixtureResult = {
  name: string;
  simulationTime: number;
  objectCount: number;
  laneSurfaceCount: number;
  roadMarkCount: number;
  objects: SmokeObject[];
};

function vectorItems<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object" && "size" in value && typeof value.size === "function") {
    const vector = value as { size(): number; get(index: number): T };
    return Array.from({ length: vector.size() }, (_, index) => vector.get(index));
  }
  return [];
}

async function probe(
  module: Awaited<ReturnType<typeof createEsminiModule>>,
  name: string,
  xoscText: string,
): Promise<SmokeFixtureResult> {
  module.FS.writeFile("/scenario.xosc", xoscText);
  module.FS.writeFile("/smoke.xodr", xodr);
  const scenario = new module.OpenScenario("/scenario.xosc", {
    max_loop: 0,
    min_time_step: 0,
    max_time_step: 0,
    dt: 0.01,
  });
  const frame = scenario.step_frame(0);
  const road = scenario.get_road_geometry();
  const objects = vectorItems<{ name: unknown; type: unknown; kind: unknown }>(frame.object_states).map((object) => ({
    name: String(object.name ?? ""),
    type: String(object.type ?? ""),
    kind: String(object.kind ?? ""),
  }));
  return {
    name,
    simulationTime: Number(frame.simulation_time ?? 0),
    objectCount: objects.length,
    laneSurfaceCount: vectorItems(road.lane_surfaces).length,
    roadMarkCount: vectorItems(road.road_marks).length,
    objects,
  };
}

self.onmessage = async (event: MessageEvent<SmokeRequest>) => {
  if (event.data.type !== "run") return;
  try {
    const module = await createEsminiModule({ noInitialRun: true });
    self.postMessage({
      type: "result",
      fixtures: [
        await probe(module, "vehicle", vehicleXosc),
        await probe(module, "pedestrian", pedestrianXosc),
      ],
    });
  } catch (error) {
    self.postMessage({ type: "error", message: error instanceof Error ? error.message : String(error) });
  }
};

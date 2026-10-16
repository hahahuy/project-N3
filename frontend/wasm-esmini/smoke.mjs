import { readFile } from "node:fs/promises";
import { Worker } from "node:worker_threads";
import { fileURLToPath } from "node:url";

const [xoscPath, xodrPath] = process.argv.slice(2);
if (!xoscPath || !xodrPath) {
  throw new Error("Usage: node smoke.mjs <scenario.xosc> <road.xodr>");
}

const modulePath = fileURLToPath(new URL("./dist/esmini.js", import.meta.url));
const xoscText = await readFile(xoscPath, "utf-8");
await readFile(xodrPath);

// Mirror the browser playback worker: the road file must be staged under the
// XOSC-declared LogicFile name, not a hardcoded name. (A hardcoded
// "/road.xodr" previously failed every run with an opaque {excPtr}.)
const roadFilename = (() => {
  const match = xoscText.match(/<LogicFile[^>]*filepath="([^"]+)"/i);
  const filepath = match?.[1]?.trim();
  if (!filepath) throw new Error("smoke XOSC declares no LogicFile filepath");
  return filepath.split(/[\\/]/).pop() ?? filepath;
})();

const workerSource = `
  const { parentPort, workerData } = require("node:worker_threads");
  (async () => {
    const { readFile } = await import("node:fs/promises");
    const { default: createModule } = await import(workerData.modulePath);
    const module = await createModule({ noInitialRun: true });
    module.FS.writeFile("/scenario.xosc", await readFile(workerData.xoscPath));
    module.FS.writeFile("/" + workerData.roadFilename, await readFile(workerData.xodrPath));
    const scenario = new module.OpenScenario("/scenario.xosc", {
      max_loop: 0,
      min_time_step: 0,
      max_time_step: 0,
      dt: 0.01,
    });
    const frame = scenario.step_frame(0);
    const road = scenario.get_road_geometry();
    // Emscripten vectors expose size()/get(), not .length: same helper as
    // the browser workers (the old .length reads always yielded undefined).
    const items = (value) => {
      if (Array.isArray(value)) return value;
      if (value && typeof value.size === "function" && typeof value.get === "function") {
        const out = [];
        for (let index = 0; index < value.size(); index++) out.push(value.get(index));
        return out;
      }
      return [];
    };
    const objects = items(frame.object_states).map((object) => ({
      name: String(object.name ?? ""),
      type: String(object.type ?? ""),
      kind: String(object.kind ?? ""),
    }));
    parentPort.postMessage({
      simulationTime: frame.simulation_time,
      objectCount: objects.length,
      laneSurfaceCount: items(road.lane_surfaces).length,
      roadMarkCount: items(road.road_marks).length,
      objects,
    });
  })().catch((error) => {
    parentPort.postMessage({
      error: error instanceof Error ? error.stack ?? error.message : JSON.stringify(error),
    });
  });
`;

const result = await new Promise((resolve, reject) => {
  const worker = new Worker(workerSource, {
    eval: true,
    workerData: { modulePath, xoscPath, xodrPath, roadFilename },
  });
  worker.once("message", resolve);
  worker.once("error", reject);
});

if (result.error) {
  throw new Error(result.error);
}

console.log(JSON.stringify(result));

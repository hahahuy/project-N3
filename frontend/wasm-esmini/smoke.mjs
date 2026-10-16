import { readFile } from "node:fs/promises";
import { Worker } from "node:worker_threads";
import { fileURLToPath } from "node:url";

const [xoscPath, xodrPath] = process.argv.slice(2);
if (!xoscPath || !xodrPath) {
  throw new Error("Usage: node smoke.mjs <scenario.xosc> <road.xodr>");
}

const modulePath = fileURLToPath(new URL("./dist/esmini.js", import.meta.url));
await readFile(xoscPath);
await readFile(xodrPath);

const workerSource = `
  const { parentPort, workerData } = require("node:worker_threads");
  (async () => {
    const { readFile } = await import("node:fs/promises");
    const { default: createModule } = await import(workerData.modulePath);
    const module = await createModule({ noInitialRun: true });
    module.FS.writeFile("/scenario.xosc", await readFile(workerData.xoscPath));
    module.FS.writeFile("/road.xodr", await readFile(workerData.xodrPath));
    const scenario = new module.OpenScenario("/scenario.xosc", {
      max_loop: 0,
      min_time_step: 0,
      max_time_step: 0,
      dt: 0.05,
    });
    const frame = scenario.step_frame(0);
    const road = scenario.get_road_geometry();
    parentPort.postMessage({
      simulationTime: frame.simulation_time,
      objectCount: frame.object_states.length,
      laneSurfaceCount: road.lane_surfaces.length,
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
    workerData: { modulePath, xoscPath, xodrPath },
  });
  worker.once("message", resolve);
  worker.once("error", reject);
});

if (result.error) {
  throw new Error(result.error);
}

console.log(JSON.stringify(result));

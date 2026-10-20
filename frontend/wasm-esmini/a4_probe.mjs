// A4 -- esminiJS (WASM) handling of the widened entity tags.
//
// Reuses the repository's own smoke.mjs calling convention (Worker + embind)
// against a scenario containing one vehicle, one Pedestrian and one MiscObject,
// and reports the exact `type` / `kind` strings the engine returns. Those
// strings decide whether a pedestrian kind/colour is a truthful increment or
// scope creep in the renderer.
//
// The identical XOSC is ALSO run through native esmini so the two engines can
// be compared on the same input.

import { readFile } from "node:fs/promises";
import { Worker } from "node:worker_threads";
import { fileURLToPath } from "node:url";

const [xoscPath, xodrPath] = process.argv.slice(2);
if (!xoscPath || !xodrPath) {
  throw new Error("Usage: node a4_probe.mjs <scenario.xosc> <road.xodr>");
}

const modulePath = fileURLToPath(new URL("./dist/esmini.js", import.meta.url));
const xoscText = await readFile(xoscPath, "utf-8");
const roadFilename =
  xoscText.match(/<LogicFile[^>]*filepath="([^"]+)"/i)?.[1]?.trim().split(/[\\/]/).pop();

const workerSource = `
  const { parentPort, workerData } = require("node:worker_threads");
  (async () => {
    const { readFile } = await import("node:fs/promises");
    const { default: createModule } = await import(workerData.modulePath);
    const module = await createModule({ noInitialRun: true });
    module.FS.writeFile("/scenario.xosc", await readFile(workerData.xoscPath));
    module.FS.writeFile("/" + workerData.roadFilename, await readFile(workerData.roadPath));
    const scenario = new module.OpenScenario("/scenario.xosc", {
      max_loop: 0, min_time_step: 0, max_time_step: 0, dt: 0.01,
    });
    const items = (value) => {
      if (Array.isArray(value)) return value;
      if (value && typeof value.size === "function" && typeof value.get === "function") {
        const out = [];
        for (let i = 0; i < value.size(); i++) out.push(value.get(i));
        return out;
      }
      return [];
    };
    // Step a few frames so post-init state is observable, then sample.
    let frame = scenario.step_frame(0.01);
    for (let i = 0; i < 50; i++) frame = scenario.step_frame(0.01);
    const objects = items(frame.object_states).map((o) => {
      const keys = [];
      for (const k of Object.keys(o)) keys.push(k);
      return {
        name: String(o.name ?? ""),
        object_type: String(o.object_type ?? ""),
        object_category: String(o.object_category ?? ""),
        legacy_type: String(o.type ?? ""),
        legacy_kind: String(o.kind ?? ""),
        ctrl_type: String(o.ctrl_type ?? ""),
        speed: Number(o.speed ?? NaN),
        x: Number(o.x ?? NaN),
        y: Number(o.y ?? NaN),
      };
    });
    parentPort.postMessage({
      ok: true,
      simulationTime: frame.simulation_time,
      objectCount: objects.length,
      objects,
    });
  })().catch((error) => {
    parentPort.postMessage({ ok: false, error: error instanceof Error ? (error.stack ?? error.message) : String(error) });
  });
`;

const result = await new Promise((resolve, reject) => {
  const worker = new Worker(workerSource, {
    eval: true,
    workerData: { modulePath, xoscPath, roadFilename, roadPath: xodrPath },
  });
  worker.once("message", resolve);
  worker.once("error", reject);
});

console.log(JSON.stringify(result, null, 2));
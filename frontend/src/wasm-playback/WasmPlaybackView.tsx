import { useEffect, useMemo, useRef, useState } from "react";
import type { WasmFrame, WasmRoadGeometry, WasmWorkerResponse } from "./types";
import { createWasmScenarioPair } from "../api";
import ThreePlaybackCanvas from "./ThreePlaybackCanvas";

const DT = 0.05;

function pointsForRoad(road: WasmRoadGeometry): Array<[number, number][]> {
  const surfaces = arrayItems<{ left_boundary: Array<{ x: number; y: number }>; right_boundary: Array<{ x: number; y: number }> }>(road?.lane_surfaces);
  return surfaces.flatMap((surface) => [surface.left_boundary, surface.right_boundary]).map((points) => Array.from(points).map((point) => [point.x, point.y]));
}

function arrayItems<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object" && "size" in value && "get" in value && typeof value.size === "function" && typeof value.get === "function") {
    const vector = value as { size(): number; get(index: number): T };
    return Array.from({ length: vector.size() }, (_, index) => vector.get(index));
  }
  return [];
}

function frameBounds(road: WasmRoadGeometry, frame: WasmFrame) {
  const points = [...pointsForRoad(road).flat(), ...frame.object_states.map((object) => [object.x, object.y] as [number, number])];
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  return { minX: Math.min(...xs, -10), maxX: Math.max(...xs, 10), minY: Math.min(...ys, -10), maxY: Math.max(...ys, 10) };
}

type Props = { scenarioId?: string };

export default function WasmPlaybackView({ scenarioId }: Props) {
  const workerRef = useRef<Worker | null>(null);
  const [status, setStatus] = useState("loading");
  const [road, setRoad] = useState<WasmRoadGeometry>({ lane_surfaces: [], road_marks: [] });
  const [frame, setFrame] = useState<WasmFrame>({ simulation_time: 0, object_states: [] });
  const [playing, setPlaying] = useState(false);
  const bounds = useMemo(() => frameBounds(road, frame), [road, frame]);
  const project = (x: number, y: number) => `${((x - bounds.minX) / Math.max(1, bounds.maxX - bounds.minX)) * 86 + 7},${93 - ((y - bounds.minY) / Math.max(1, bounds.maxY - bounds.minY)) * 86}`;

  useEffect(() => {
    const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    workerRef.current = worker;
    worker.onmessage = (event: MessageEvent<WasmWorkerResponse>) => {
      const message = event.data;
      if (message.type === "error") { setStatus(`error: ${message.message}`); setPlaying(false); return; }
      if (message.type === "ready") { setRoad(message.road); setFrame(message.frame); setStatus("ready"); return; }
      setFrame(message.frame);
    };
    const load = async () => {
      if (!scenarioId) {
        const [xosc, xodr] = await Promise.all([
          fetch(new URL("../wasm-smoke/fixture.xosc", import.meta.url)).then((response) => response.text()),
          fetch(new URL("../wasm-smoke/fixture.xodr", import.meta.url)).then((response) => response.text()),
        ]);
        worker.postMessage({ type: "init", xosc, xodr });
        return;
      }
      const pair = await createWasmScenarioPair(scenarioId);
      const [xosc, xodr] = await Promise.all([fetch(pair.openscenario).then((response) => response.text()), fetch(pair.opendrive).then((response) => response.text())]);
      worker.postMessage({ type: "init", xosc, xodr });
    };
    load().catch((error) => setStatus(`error: ${error instanceof Error ? error.message : String(error)}`));
    return () => { worker.postMessage({ type: "dispose" }); worker.terminate(); workerRef.current = null; };
  }, []);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => workerRef.current?.postMessage({ type: "step", dt: DT }), DT * 1000);
    return () => window.clearInterval(timer);
  }, [playing]);

  return <div className="wasm-playback-view">
    <ThreePlaybackCanvas road={road} frame={frame} />
    <div className="wasm-playback-controls">
      <button onClick={() => setPlaying((value) => !value)} disabled={status !== "ready"}>{playing ? "Pause" : "Play"}</button>
      <button onClick={() => workerRef.current?.postMessage({ type: "step", dt: DT })} disabled={status !== "ready"}>Step</button>
      <button onClick={() => { setPlaying(false); workerRef.current?.postMessage({ type: "reset" }); }} disabled={status !== "ready"}>Reset</button>
      <span>WASM {status} / t={frame.simulation_time.toFixed(2)} s / objects={frame.object_states.length}</span>
    </div>
    <small className="wasm-playback-warning">Synthetic playback fixture. Browser frames are preview-only and never feed Tier 0 metrics.</small>
  </div>;
}

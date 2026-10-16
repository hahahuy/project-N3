import { useEffect, useRef, useState } from "react";
import type { WasmActorLifecycle, WasmFrame, WasmRoadGeometry, WasmSceneSummary, WasmWorkerResponse } from "./types";
import { trackWasmActors } from "./types";
import { createWasmScenarioPair } from "../api";
import ThreePlaybackCanvas from "./ThreePlaybackCanvas";

type Props = { scenarioId?: string };

export default function WasmPlaybackView({ scenarioId }: Props) {
  const workerRef = useRef<Worker | null>(null);
  const [status, setStatus] = useState("loading");
  const [road, setRoad] = useState<WasmRoadGeometry>({ lane_surfaces: [], road_marks: [] });
  const [frame, setFrame] = useState<WasmFrame>({ simulation_time: 0, object_states: [] });
  const [playing, setPlaying] = useState(false);
  const [scene, setScene] = useState<WasmSceneSummary>({ simulation_time: 0, active_count: 0, ended_count: 0, actors: [] });
  const lifecycleRef = useRef<Map<number, WasmActorLifecycle>>(new Map());

  const applyFrame = (next: WasmFrame) => {
    setFrame(next);
    const summary = trackWasmActors(lifecycleRef.current, next);
    lifecycleRef.current = new Map(summary.actors.map((actor) => [actor.id, actor]));
    setScene(summary);
  };

  useEffect(() => {
    const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    workerRef.current = worker;
    worker.onmessage = (event: MessageEvent<WasmWorkerResponse>) => {
      const message = event.data;
      if (message.type === "error") { setStatus(`error: ${message.message}`); setPlaying(false); return; }
      if (message.type === "ready") { setRoad(message.road); lifecycleRef.current = new Map(); applyFrame(message.frame); setStatus("ready"); return; }
      applyFrame(message.frame);
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
  }, [scenarioId]);

  useEffect(() => {
    workerRef.current?.postMessage({ type: playing ? "play" : "pause" });
  }, [playing]);

  return <div className="wasm-playback-view">
    <ThreePlaybackCanvas road={road} frame={frame} />
    <div className="wasm-playback-controls">
      <button onClick={() => setPlaying((value) => !value)} disabled={status !== "ready"}>{playing ? "Pause" : "Play"}</button>
      <button onClick={() => workerRef.current?.postMessage({ type: "step" })} disabled={status !== "ready"}>Step</button>
      <button onClick={() => { setPlaying(false); workerRef.current?.postMessage({ type: "reset" }); }} disabled={status !== "ready"}>Reset</button>
      <span>WASM {status} / t={frame.simulation_time.toFixed(2)} s / objects={frame.object_states.length}{scene.ended_count > 0 ? ` / ended=${scene.ended_count}` : ""}</span>
    </div>
    <ul className="wasm-scene-ledger" aria-label="Actor lifecycle ledger">
      {scene.actors.map((actor) => (
        <li key={actor.id} data-status={actor.status}>
          <strong>{actor.name}</strong>
          <span>{actor.actor_kind} · {actor.status} · seen {actor.seen_count}× · last {actor.last_speed_mps.toFixed(2)} m/s</span>
        </li>
      ))}
    </ul>
     <small className="wasm-playback-warning">{scenarioId ? "Real scenario playback preview." : "Synthetic playback fixture."} Browser frames are preview-only and never feed Tier 0 metrics.</small>
  </div>;
}

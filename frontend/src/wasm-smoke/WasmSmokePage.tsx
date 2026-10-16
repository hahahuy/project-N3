import { useEffect, useState } from "react";
import WasmPlaybackView from "../wasm-playback/WasmPlaybackView";
import { fetchScenarios } from "../api";
import "../wasm-playback/playback.css";

type SmokeResult = { type: "result"; simulationTime: number; objectCount: number; laneSurfaceCount: number; roadMarkCount: number };

export default function WasmSmokePage() {
  const [status, setStatus] = useState("starting Worker");
  const [result, setResult] = useState<SmokeResult | null>(null);
  const [scenarioId, setScenarioId] = useState("");
  const [scenarios, setScenarios] = useState<Array<{ scenario_id: string }>>([]);

  useEffect(() => {
    const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    worker.onmessage = (event: MessageEvent<SmokeResult | { type: "error"; message: string }>) => {
      if (event.data.type === "error") {
        setStatus(`failed: ${event.data.message}`);
        return;
      }
      setResult(event.data);
      setStatus("passed");
    };
    worker.postMessage({ type: "run" });
    return () => worker.terminate();
  }, []);

  useEffect(() => {
    fetchScenarios().then(setScenarios).catch(() => setScenarios([]));
  }, []);

  return <main style={{ fontFamily: "ui-monospace, monospace", padding: 32, maxWidth: 1100 }}>
    <h1>esminiJS WASM P0 smoke</h1>
    <p>This diagnostic page runs the browser engine in a real Worker. It does not feed workspace metrics.</p>
    <p role="status">Status: {status}</p>
    {result && <dl>
      <dt>simulation time</dt><dd>{result.simulationTime}</dd>
      <dt>active objects</dt><dd>{result.objectCount}</dd>
      <dt>lane surfaces</dt><dd>{result.laneSurfaceCount}</dd>
      <dt>road marks</dt><dd>{result.roadMarkCount}</dd>
    </dl>}
    <p>Fixture: inline synthetic OpenSCENARIO/OpenDRIVE. Native replay and ADE/FDE are unchanged.</p>
    <label style={{ display: "block", marginTop: 16 }}>Scenario artifact
      <select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>
        <option value="">Synthetic fixture</option>
        {scenarios.map((scenario) => <option key={scenario.scenario_id} value={scenario.scenario_id}>{scenario.scenario_id}</option>)}
      </select>
    </label>
    <section aria-label="WASM playback preview" style={{ height: 520, marginTop: 24, border: "1px solid #304653", borderRadius: 6, overflow: "hidden" }}>
      <WasmPlaybackView key={scenarioId || "fixture"} scenarioId={scenarioId || undefined} />
    </section>
  </main>;
}

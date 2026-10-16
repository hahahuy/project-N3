import { useEffect, useState } from "react";
import WasmPlaybackView from "../wasm-playback/WasmPlaybackView";
import { fetchScenarios } from "../api";
import "../wasm-playback/playback.css";

type SmokeObject = { name: string; type: string; kind: string };
type SmokeFixtureResult = {
  name: string;
  simulationTime: number;
  objectCount: number;
  laneSurfaceCount: number;
  roadMarkCount: number;
  objects: SmokeObject[];
};
type SmokeResult = { type: "result"; fixtures: SmokeFixtureResult[] };

export default function WasmSmokePage() {
  const [status, setStatus] = useState("starting Worker");
  const [result, setResult] = useState<SmokeResult | null>(null);
  const [scenarioId, setScenarioId] = useState("");
  const [fixture, setFixture] = useState<"vehicle" | "pedestrian">("vehicle");
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

  const playbackKey = scenarioId || `fixture-${fixture}`;

  return <main style={{ fontFamily: "ui-monospace, monospace", padding: 32, maxWidth: 1100 }}>
    <h1>esminiJS WASM P0 smoke</h1>
    <p>This diagnostic page runs the browser engine in a real Worker. It does not feed workspace metrics.</p>
    <p role="status">Status: {status}</p>
    {result && result.fixtures.map((item) => (
      <section key={item.name} aria-label={`P0 probe: ${item.name} fixture`}>
        <h2>Fixture: {item.name}</h2>
        <dl>
          <dt>simulation time</dt><dd>{item.simulationTime}</dd>
          <dt>active objects</dt><dd>{item.objectCount}</dd>
          <dt>lane surfaces</dt><dd>{item.laneSurfaceCount}</dd>
          <dt>road marks</dt><dd>{item.roadMarkCount}</dd>
        </dl>
        <ul aria-label={`Engine object tags (${item.name})`}>
          {item.objects.map((object) => (
            <li key={object.name}>{object.name} · type={object.type || "?"} · kind={object.kind || "?"}</li>
          ))}
        </ul>
      </section>
    ))}
    <p>Fixture: inline synthetic OpenSCENARIO/OpenDRIVE. Native replay and ADE/FDE are unchanged.</p>
    <label style={{ display: "block", marginTop: 16 }}>Scenario artifact
      <select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>
        <option value="">Synthetic fixture (see picker below)</option>
        {scenarios.map((scenario) => <option key={scenario.scenario_id} value={scenario.scenario_id}>{scenario.scenario_id}</option>)}
      </select>
    </label>
    {!scenarioId && (
      <label style={{ display: "block", marginTop: 8 }}>Synthetic fixture
        <select value={fixture} onChange={(event) => setFixture(event.target.value === "pedestrian" ? "pedestrian" : "vehicle")}>
          <option value="vehicle">Vehicle only (P0 baseline)</option>
          <option value="pedestrian">Vehicle + Pedestrian + MiscObject (tag widening)</option>
        </select>
      </label>
    )}
    <section aria-label="WASM playback preview" style={{ height: 520, marginTop: 24, border: "1px solid #304653", borderRadius: 6, overflow: "hidden" }}>
      <WasmPlaybackView key={playbackKey} scenarioId={scenarioId || undefined} fixture={scenarioId ? undefined : fixture} />
    </section>
  </main>;
}

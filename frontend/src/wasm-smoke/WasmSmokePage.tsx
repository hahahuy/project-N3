import { useEffect, useState } from "react";
import WasmPlaybackView from "../wasm-playback/WasmPlaybackView";
import { fetchScenarios } from "../api";
import "../wasm-playback/playback.css";

type SmokeObject = { name: string; object_type: number; object_category: number };

const OBJECT_TYPE_LABELS: Record<number, string> = { 1: "Vehicle", 2: "Pedestrian", 3: "MiscObject" };
type SmokeFixtureResult = {
  name: string;
  simulationTime: number;
  objectCount: number;
  laneSurfaceCount: number;
  roadMarkCount: number;
  objects: SmokeObject[];
};
type SmokeResult = { type: "result"; fixtures: SmokeFixtureResult[] };

/** Recorded expectations (Node harness, engine 3.10.0-06065f9, 2026-10-16).
 *  Display-only review aid, never a gate: re-record after any engine rebuild. */
const P0_EXPECTED: SmokeFixtureResult[] = [
  {
    name: "vehicle", simulationTime: 0.01, objectCount: 1, laneSurfaceCount: 2, roadMarkCount: 2,
    objects: [{ name: "ego", object_type: 1, object_category: 0 }],
  },
  {
    name: "pedestrian", simulationTime: 0.01, objectCount: 3, laneSurfaceCount: 2, roadMarkCount: 2,
    objects: [
      { name: "ego", object_type: 1, object_category: 0 },
      { name: "walk1", object_type: 2, object_category: 0 },
      { name: "cone1", object_type: 3, object_category: 0 },
    ],
  },
];

const matchesExpected = (actual: SmokeFixtureResult, expected: SmokeFixtureResult): boolean =>
  Math.abs(actual.simulationTime - expected.simulationTime) < 1e-9
  && actual.objectCount === expected.objectCount
  && actual.laneSurfaceCount === expected.laneSurfaceCount
  && actual.roadMarkCount === expected.roadMarkCount
  && actual.objects.length === expected.objects.length
  && expected.objects.every((want) =>
    actual.objects.some((got) => got.name === want.name && got.object_type === want.object_type));

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
    {result && result.fixtures.map((item) => {
      const expected = P0_EXPECTED.find((want) => want.name === item.name);
      const pass = expected !== undefined && matchesExpected(item, expected);
      return (
        <section key={item.name} aria-label={`P0 probe: ${item.name} fixture`}>
          <h2>Fixture: {item.name} {expected !== undefined && (pass ? "✓ matches recorded" : "✗ DIFFERS from recorded")}</h2>
          <dl>
            <dt>simulation time</dt><dd>{item.simulationTime}</dd>
            <dt>active objects</dt><dd>{item.objectCount}</dd>
            <dt>lane surfaces</dt><dd>{item.laneSurfaceCount}</dd>
            <dt>road marks</dt><dd>{item.roadMarkCount}</dd>
          </dl>
          <ul aria-label={`Engine object tags (${item.name})`}>
            {item.objects.map((object) => (
              <li key={object.name}>{object.name} · {OBJECT_TYPE_LABELS[object.object_type] ?? `unknown(${object.object_type})`} · category={object.object_category}</li>
            ))}
          </ul>
        </section>
      );
    })}
    <details className="wasm-checklist">
      <summary>What to check on this page (recorded 2026-10-16, engine 3.10.0-06065f9)</summary>
      <ol>
        <li>P0 rows above both read ✓ (counts + object tags match the recorded table).</li>
        <li>Playback preview, each synthetic fixture: Play moves actors (ego drives, walk1 walks its 3→7 m trajectory, cone stays), Step advances one 0.01 s tick, Reset restarts.</li>
        <li>Ledger lists every engine actor with kind, lifecycle status and speed.</li>
        <li>Scenario attributes: declared road file matches the served road, lane/road-mark counts match P0, every entity shows tag, category, mass, bbox and source taxonomy.</li>
        <li>Real scenario via the picker (needs an imported workspace scenario): same four checks against exporter output.</li>
      </ol>
      <p>Browser frames are preview-only and never feed metrics. Re-record the table above after any engine rebuild.</p>
    </details>
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

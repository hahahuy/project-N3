import { useEffect, useState } from "react";
import { apiUrl, BatchResults, createBatch, exportBatchResult, fetchBatchResults, fetchBatchTrajectory, fetchScenario, fetchScenarios, fetchSettings, fetchSourceScenes, fetchTrajectory, importSourceScene, ScenarioSummary, SourceScene, SettingsView, TrajectoryResponse, updateSettings, VariantResult } from "./api";

function App() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selected, setSelected] = useState<ScenarioSummary | null>(null);
  const [trajectory, setTrajectory] = useState<TrajectoryResponse | null>(null);
  const [batch, setBatch] = useState<BatchResults | null>(null);
  const [selectedResult, setSelectedResult] = useState<VariantResult | null>(null);
  const [settings, setSettings] = useState<SettingsView | null>(null);
  const [sourceScenes, setSourceScenes] = useState<SourceScene[]>([]);
  const [artifactRoot, setArtifactRoot] = useState("");
  const [outputRoot, setOutputRoot] = useState("");
  const [datasetRoot, setDatasetRoot] = useState("");
  const [datasetVersion, setDatasetVersion] = useState("v1.0-mini");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [seed, setSeed] = useState(7);
  const [running, setRunning] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [replayEnabled, setReplayEnabled] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function refreshCatalog() {
    const [catalog, currentSettings, scenes] = await Promise.all([fetchScenarios(), fetchSettings(), fetchSourceScenes()]);
    setScenarios(catalog); setSettings(currentSettings); setSourceScenes(scenes);
    setArtifactRoot(currentSettings.artifact_root); setOutputRoot(currentSettings.output_root); setDatasetRoot(currentSettings.dataset_root ?? ""); setDatasetVersion(currentSettings.dataset_version);
  }
  useEffect(() => { refreshCatalog().catch((e) => setError(e.message)); }, []);
  useEffect(() => { if (!selected) return; Promise.all([fetchScenario(selected.scenario_id), fetchTrajectory(selected.scenario_id)]).then(([detail, paths]) => { setSelected(detail); setTrajectory(paths); }).catch((e) => setError(e.message)); }, [selected?.scenario_id]);

  async function applySettings() {
    setError(null); setNotice(null);
    try { await updateSettings({ artifact_root: artifactRoot, output_root: outputRoot, dataset_root: datasetRoot, dataset_version: datasetVersion }); await refreshCatalog(); setNotice("Local paths applied. The catalog has been refreshed."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not apply paths"); }
  }
  async function importScene(scene: SourceScene) {
    setImporting(scene.scene_token); setError(null); setNotice(null);
    try { const imported = await importSourceScene(scene.scene_token); await refreshCatalog(); const summary = (await fetchScenarios()).find((item) => item.scenario_id === imported.scenario_id); if (summary) setSelected(summary); setNotice(`${scene.name} imported as ${imported.scenario_id}.`); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not import scene"); } finally { setImporting(null); }
  }
  async function runBatch() {
    if (!selected) return; setRunning(true); setError(null); setSelectedResult(null);
    try { const job = await createBatch({ scenario_id: selected.scenario_id, generation_mode: "grid", speed_multipliers: [0.9, 1.0], initial_gap_deltas_m: [-2, 0], timing_offsets_s: [0, 0.25, 0.5, 0.75, 1], seed, replay_enabled: replayEnabled }); setBatch(await fetchBatchResults(job.job_id)); }
    catch (e) { setError(e instanceof Error ? e.message : "Batch failed"); } finally { setRunning(false); }
  }
  async function inspectResult(result: VariantResult) {
    if (!batch) return; setSelectedResult(result); setError(null);
    try { const [detail, paths] = await Promise.all([fetchScenario(result.variant_id).catch(() => null), fetchBatchTrajectory(batch.job.job_id, result.variant_id)]); if (detail) setSelected(detail); setTrajectory(paths); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load variant"); }
  }
  async function exportResult() {
    if (!batch || !selectedResult || selectedResult.status !== "valid") return; setExporting(true); setError(null);
    try { const result = await exportBatchResult(batch.job.job_id, selectedResult.variant_id); setSelectedResult({ ...selectedResult, artifacts: result.artifacts }); setNotice("OpenSCENARIO export is ready in the result artifacts."); }
    catch (e) { setError(e instanceof Error ? e.message : "Export failed"); } finally { setExporting(false); }
  }

  return <main className="shell">
    <header className="masthead"><div><p className="eyebrow">R2S / LOCAL LAB</p><h1>Scenario review, without the black box.</h1><p className="lede">A CPU-only browser surface for recorded trajectories and deterministic variation. Every score links back to a canonical artifact.</p></div><div className="health"><span className="pulse" /> LOCAL API<br /><strong>Connected boundary</strong></div></header>
    {error && <div className="error">{error}</div>}{notice && <div className="notice">{notice}</div>}
    <section className="settings-bar"><button className="settings-toggle" onClick={() => setSettingsOpen(!settingsOpen)}>LOCAL PATHS <span>{settingsOpen ? "−" : "+"}</span></button>{settings && <span className="settings-summary">artifacts: {settings.artifact_root_exists ? "ready" : "missing"} · dataset: {settings.dataset_root_exists ? "ready" : "missing"}</span>}{settingsOpen && <div className="settings-panel"><p className="muted">Enter paths visible to the FastAPI process. Browser folder access is intentionally not used.</p><div className="settings-grid"><PathInput label="Artifact directory" value={artifactRoot} onChange={setArtifactRoot} placeholder="scenarios" /><PathInput label="Output directory" value={outputRoot} onChange={setOutputRoot} placeholder="reports" /><PathInput label="nuScenes dataset root" value={datasetRoot} onChange={setDatasetRoot} placeholder="data/v1.0-mini" /><PathInput label="Dataset version" value={datasetVersion} onChange={setDatasetVersion} placeholder="v1.0-mini" /></div><button className="apply" onClick={applySettings}>APPLY PATHS</button></div>}</section>
    <section className="workspace">
      <aside className="catalog panel"><div className="panel-heading"><span>01 / CATALOG</span><span className="count">{scenarios.length} artifacts</span></div><h2>Source scenarios</h2><p className="muted">Validated artifacts discovered below the configured directory.</p><div className="scenario-list">{scenarios.length === 0 ? <div className="empty">No artifacts configured.<br /><small>Open LOCAL PATHS above, then import a source scene.</small></div> : scenarios.map((scenario) => <button className={`scenario ${selected?.scenario_id === scenario.scenario_id ? "active" : ""}`} key={scenario.scenario_id} onClick={() => setSelected(scenario)}><span className="scenario-dot" /><span><strong>{scenario.scenario_id}</strong><small>{scenario.artifact_type} · {scenario.duration_s.toFixed(2)} s</small></span><span className="arrow">→</span></button>)}</div><div className="source-scenes"><h3>nuScenes source scenes</h3>{sourceScenes.length === 0 ? <p className="muted">Dataset metadata is not reachable.</p> : sourceScenes.slice(0, 10).map((scene) => <div className="source-scene" key={scene.scene_token}><div><strong>{scene.name}</strong><small>{scene.sample_count} samples · {scene.vehicle_candidate_count} vehicles</small></div><button disabled={importing === scene.scene_token} onClick={() => importScene(scene)}>{importing === scene.scene_token ? "..." : "IMPORT"}</button></div>)}</div></aside>
      <section className="detail panel"><div className="panel-heading"><span>02 / INSPECT</span><span className="frame">{selected?.coordinate_frame ?? "waiting for artifact"}</span></div>{selected ? <><div className="title-row"><div><h2>{selected.scenario_id}</h2><p className="muted">{selected.parent_scenario_id ? `Child of ${selected.parent_scenario_id}` : "Baseline scenario"}</p></div><a className="download" href={apiUrl(selected.available_artifacts[0]?.url.replace("/api", "") ?? "")} target="_blank">Download JSON ↗</a></div><div className="stats"><Stat label="DURATION" value={`${selected.duration_s.toFixed(2)} s`} /><Stat label="ACTORS" value={`${selected.actors.length}`} /><Stat label="FRAME" value={selected.coordinate_frame} /><Stat label="DATASET" value={selected.provenance.dataset_name ?? "unknown"} /></div><TrajectoryPlot trajectory={trajectory} />{selectedResult && <ResultDetail result={selectedResult} onExport={exportResult} exporting={exporting} />}{selectedResult?.simulator_error && <div className="failure"><strong>SIMULATOR FAILURE</strong><p>{selectedResult.simulator_error}</p><pre>{JSON.stringify(selectedResult.replay_failure, null, 2)}</pre></div>}<div className="provenance"><h3>Provenance record</h3><div className="provenance-grid">{Object.entries(selected.provenance).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{value}</strong></div>)}</div></div></> : <div className="empty large">Select an imported scenario to inspect trajectories, provenance, and replay metadata.</div>}</section>
      <aside className="controls panel"><div className="panel-heading"><span>03 / GENERATE</span><span className="badge">DETERMINISTIC</span></div><h2>Variation batch</h2><p className="muted">Grid configuration in SI units. The API validates before it ranks.</p><label>Seed <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} /></label><label className="checkbox"><input type="checkbox" checked={replayEnabled} onChange={(e) => setReplayEnabled(e.target.checked)} /> Replay with esmini</label><div className="range-row"><Range label="Speed multiplier" value="0.9 — 1.0" unit="×" /><Range label="Initial gap delta" value="-2 — 0" unit="m" /><Range label="Timing offset" value="0 — 1.0" unit="s" /></div><button className="run" disabled={!selected || running} onClick={runBatch}>{running ? "RUNNING LOCAL JOB..." : "GENERATE 20 VARIANTS"}<span>↗</span></button>{batch && <BatchSummary batch={batch} onSelect={inspectResult} />}</aside>
    </section>
  </main>;
}

function PathInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) { return <label className="path-input"><span>{label}</span><input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} /></label>; }
function Stat({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><strong>{value}</strong></div>; }
function Range({ label, value, unit }: { label: string; value: string; unit: string }) { return <div className="range"><span>{label}</span><strong>{value} <em>{unit}</em></strong><div className="rail"><i /></div></div>; }
function TrajectoryPlot({ trajectory }: { trajectory: TrajectoryResponse | null }) { if (!trajectory) return <div className="plot empty">Loading trajectory...</div>; const paths = trajectory.paths; const xs = paths.flatMap((p) => p.states.map((s) => s.x_m)); const ys = paths.flatMap((p) => p.states.map((s) => s.y_m)); const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys); const point = (x: number, y: number) => `${((x - minX) / Math.max(1, maxX - minX)) * 88 + 6},${92 - ((y - minY) / Math.max(1, maxY - minY)) * 80}`; return <div><div className="plot"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><path d="M 0,50 L 100,50" className="lane" />{paths.map((path) => <polyline key={`${path.actor_id}-${path.path_kind}`} points={path.states.map((s) => point(s.x_m, s.y_m)).join(" ")} className={`path ${path.path_kind}`} />)}</svg><div className="legend"><span><i className="legend-recorded" /> recorded</span><span><i className="legend-replayed" /> replayed</span><span className="plot-note">{trajectory.map_warning}</span></div></div></div>; }
function ResultDetail({ result, onExport, exporting }: { result: VariantResult; onExport: () => void; exporting: boolean }) { return <div className="result-detail"><div className="result-detail-head"><h3>Variant result</h3><span className={`result-label ${result.status}`}>{result.status}</span></div><div className="config-grid">{Object.entries(result.configuration).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{String(value)}</strong></div>)}</div>{result.validation.reasons.length > 0 && <div className="reasons"><strong>Validation reasons</strong>{result.validation.reasons.map((reason) => <p key={`${reason.code}-${reason.state_index}`}>{reason.code}: {reason.message}</p>)}</div>}{result.ranking?.breakdown && <div className="score"><span>score</span><strong>{result.ranking.breakdown.total.toFixed(3)}</strong><small>risk {result.ranking.features.risk_signal.toFixed(3)} · novelty {result.ranking.features.novelty.toFixed(3)} · distance {result.ranking.features.minimum_distance_m?.toFixed(2) ?? "n/a"} m · TTC {result.ranking.features.minimum_ttc_s?.toFixed(2) ?? "n/a"} s</small></div>}<div className="result-artifacts">{result.artifacts.map((artifact) => <a key={artifact.path} href={apiUrl(artifact.url.replace("/api", ""))} target="_blank">{artifact.kind} ↗</a>)}{result.status === "valid" && <button onClick={onExport} disabled={exporting}>{exporting ? "EXPORTING..." : "EXPORT XOSC"}</button>}</div></div>; }
function BatchSummary({ batch, onSelect }: { batch: BatchResults; onSelect: (result: VariantResult) => void }) { return <div className="batch-summary"><div className="batch-top"><span>JOB COMPLETE</span><strong>seed {String(batch.manifest.seed)}</strong></div><div className="result-counts"><div className="valid"><strong>{batch.counts.valid}</strong><span>valid</span></div><div className="invalid"><strong>{batch.counts.invalid}</strong><span>invalid</span></div><div className="failed"><strong>{batch.counts.simulator_failed}</strong><span>simulator failed</span></div></div><div className="result-list">{batch.results.slice(0, 8).map((result) => <button className="result" key={result.variant_id} onClick={() => onSelect(result)}><span className={`status ${result.status}`} /> <span>{result.variant_id.slice(-16)}</span><strong>{result.ranking?.breakdown?.total.toFixed(3) ?? result.status}</strong></button>)}</div></div>; }

export default App;

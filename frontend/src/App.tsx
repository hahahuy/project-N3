import { useEffect, useState } from "react";
import { apiUrl, ActorMotionEdit, BatchResults, createBatch, createReplay, EsminiCapability, exportBatchResult, fetchBatchResults, fetchBatchTrajectory, fetchEsminiCapability, fetchReplay, fetchScenario, fetchScenarios, fetchSettings, fetchSourceScenes, fetchTrajectory, importSourceScene, PreviewResponse, previewVariant, ReplayJob, ScenarioSummary, SourceScene, SettingsView, TrajectoryPath, TrajectoryResponse, updateSettings, VariantResult } from "./api";

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
  const [esmini, setEsmini] = useState<EsminiCapability | null>(null);
  const [replayJob, setReplayJob] = useState<ReplayJob | null>(null);
  const [selectedActorId, setSelectedActorId] = useState<string | null>(null);
  const [motionEdits, setMotionEdits] = useState<Record<string, ActorMotionEdit>>({});
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [timelineTime, setTimelineTime] = useState(0);

  async function refreshCatalog() {
    const [catalog, currentSettings, scenes, capability] = await Promise.all([fetchScenarios(), fetchSettings(), fetchSourceScenes(), fetchEsminiCapability()]);
    setScenarios(catalog); setSettings(currentSettings); setSourceScenes(scenes);
    setEsmini(capability);
    setArtifactRoot(currentSettings.artifact_root); setOutputRoot(currentSettings.output_root); setDatasetRoot(currentSettings.dataset_root ?? ""); setDatasetVersion(currentSettings.dataset_version);
  }
  useEffect(() => { refreshCatalog().catch((e) => setError(e.message)); }, []);
  useEffect(() => { if (!selected) return; Promise.all([fetchScenario(selected.scenario_id), fetchTrajectory(selected.scenario_id)]).then(([detail, paths]) => { setSelected(detail); setTrajectory(paths); setSelectedActorId(detail.actors[0]?.actor_id ?? null); setMotionEdits(Object.fromEntries(detail.actors.map((actor) => [actor.actor_id, defaultEdit(actor.actor_id)]))); setPreview(null); setTimelineTime(0); }).catch((e) => setError(e.message)); }, [selected?.scenario_id]);

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
    try { const paths = await fetchBatchTrajectory(batch.job.job_id, result.variant_id); setTrajectory(paths); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load variant"); }
  }
  async function exportResult() {
    if (!batch || !selectedResult || selectedResult.status !== "valid") return; setExporting(true); setError(null);
    try { const result = await exportBatchResult(batch.job.job_id, selectedResult.variant_id); setSelectedResult({ ...selectedResult, artifacts: result.artifacts }); setNotice("OpenSCENARIO export is ready in the result artifacts."); }
    catch (e) { setError(e instanceof Error ? e.message : "Export failed"); } finally { setExporting(false); }
  }
  async function runReplay() {
    if (!selected) return;
    setError(null); setNotice(null);
    try {
      const job = await createReplay(selected.scenario_id);
      setReplayJob(job);
      const poll = async () => {
        const current = await fetchReplay(job.job_id);
        setReplayJob(current);
        if (current.status === "queued" || current.status === "running") window.setTimeout(poll, 500);
      };
      window.setTimeout(poll, 250);
    } catch (e) { setError(e instanceof Error ? e.message : "Replay failed"); }
  }

  function editForActor(actorId: string): ActorMotionEdit { return motionEdits[actorId] ?? defaultEdit(actorId); }
  function updateEdit(field: keyof Omit<ActorMotionEdit, "actor_id">, value: number) {
    if (!selectedActorId) return;
    setMotionEdits((current) => ({ ...current, [selectedActorId]: { ...editForActor(selectedActorId), [field]: value } }));
  }
  async function requestPreview() {
    if (!selected || !selectedActorId) return;
    setPreviewBusy(true); setError(null); setNotice(null);
    try { const result = await previewVariant(selected.scenario_id, { actor_edits: [editForActor(selectedActorId)], replay_mode: "waypoint", behavior: "parameterized", seed }); setPreview(result); setTimelineTime(0); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not preview variant"); }
    finally { setPreviewBusy(false); }
  }
  function resetPreview() {
    setPreview(null); setTimelineTime(0);
    setMotionEdits((current) => Object.fromEntries(Object.keys(current).map((actorId) => [actorId, defaultEdit(actorId)])));
    setNotice("Preview reset to the parent trajectory.");
  }
  function exportPreviewConfig() {
    if (!preview) return;
    const blob = new Blob([JSON.stringify({ parent_scenario_id: preview.parent_scenario_id, variant_id: preview.variant_id, configuration: preview.configuration, provenance: preview.provenance }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${preview.variant_id ?? preview.parent_scenario_id}-preview-config.json`; anchor.click(); URL.revokeObjectURL(url);
  }

  return <main className="shell">
     <header className="masthead"><div><p className="eyebrow">R2S / LOCAL LAB</p><h1>Scenario review, without the black box.</h1><p className="lede">A CPU-only browser surface for recorded trajectories and deterministic variation. Every score links back to a canonical artifact.</p></div><div className="health"><span className="pulse" /> LOCAL API<br /><strong>Connected boundary</strong><small>esmini: {esmini?.available ? (esmini.version ?? "available") : (esmini?.diagnostic ?? "checking")}</small></div></header>
    {error && <div className="error">{error}</div>}{notice && <div className="notice">{notice}</div>}
    <section className="settings-bar"><button className="settings-toggle" onClick={() => setSettingsOpen(!settingsOpen)}>LOCAL PATHS <span>{settingsOpen ? "−" : "+"}</span></button>{settings && <span className="settings-summary">artifacts: {settings.artifact_root_exists ? "ready" : "missing"} · dataset: {settings.dataset_root_exists ? "ready" : "missing"}</span>}{settingsOpen && <div className="settings-panel"><p className="muted">Enter paths visible to the FastAPI process. Browser folder access is intentionally not used.</p><div className="settings-grid"><PathInput label="Artifact directory" value={artifactRoot} onChange={setArtifactRoot} placeholder="scenarios" /><PathInput label="Output directory" value={outputRoot} onChange={setOutputRoot} placeholder="reports" /><PathInput label="nuScenes dataset root" value={datasetRoot} onChange={setDatasetRoot} placeholder="data/v1.0-mini" /><PathInput label="Dataset version" value={datasetVersion} onChange={setDatasetVersion} placeholder="v1.0-mini" /></div><button className="apply" onClick={applySettings}>APPLY PATHS</button></div>}</section>
    <section className="workspace">
      <aside className="catalog panel"><div className="panel-heading"><span>01 / CATALOG</span><span className="count">{scenarios.length} artifacts</span></div><h2>Source scenarios</h2><p className="muted">Validated artifacts discovered below the configured directory.</p><div className="scenario-list">{scenarios.length === 0 ? <div className="empty">No artifacts configured.<br /><small>Open LOCAL PATHS above, then import a source scene.</small></div> : scenarios.map((scenario) => <button className={`scenario ${selected?.scenario_id === scenario.scenario_id ? "active" : ""}`} key={scenario.scenario_id} onClick={() => setSelected(scenario)}><span className="scenario-dot" /><span><strong>{scenario.scenario_id}</strong><small>{scenario.artifact_type} · {scenario.duration_s.toFixed(2)} s</small></span><span className="arrow">→</span></button>)}</div><div className="source-scenes"><h3>nuScenes source scenes</h3>{sourceScenes.length === 0 ? <p className="muted">Dataset metadata is not reachable.</p> : sourceScenes.slice(0, 10).map((scene) => <div className="source-scene" key={scene.scene_token}><div><strong>{scene.name}</strong><small>{scene.sample_count} samples · {scene.vehicle_candidate_count} vehicles</small></div><button disabled={importing === scene.scene_token} onClick={() => importScene(scene)}>{importing === scene.scene_token ? "..." : "IMPORT"}</button></div>)}</div></aside>
        <section className="detail panel"><div className="panel-heading"><span>02 / INSPECT</span><span className="frame">{selected?.coordinate_frame ?? "waiting for artifact"}</span></div>{selected ? <><div className="title-row"><div><h2>{selected.scenario_id}</h2><p className="muted">{selected.parent_scenario_id ? `Child of ${selected.parent_scenario_id}` : "Baseline scenario"}</p></div><a className="download" href={apiUrl(selected.available_artifacts[0]?.url.replace("/api", "") ?? "")} target="_blank">Download JSON ↗</a></div><div className="stats"><Stat label="DURATION" value={`${selected.duration_s.toFixed(2)} s`} /><Stat label="ACTORS" value={`${selected.actors.length}`} /><Stat label="FRAME" value={selected.coordinate_frame} /><Stat label="DATASET" value={selected.provenance.dataset_name ?? "unknown"} /></div><ActorList actors={selected.actors} selectedActorId={selectedActorId} onSelect={setSelectedActorId} /><TrajectoryPlot trajectory={trajectory} previewPaths={preview?.paths ?? []} timelineTime={timelineTime} /><TimelineScrubber duration={selected.duration_s} value={timelineTime} onChange={setTimelineTime} />{replayJob && <ReplayStatus job={replayJob} />}{preview && <PreviewResult preview={preview} onExport={exportPreviewConfig} />}{selectedResult && <ResultDetail result={selectedResult} onExport={exportResult} exporting={exporting} />}{selectedResult?.simulator_error && <div className="failure"><strong>SIMULATOR FAILURE</strong><p>{selectedResult.simulator_error}</p><pre>{JSON.stringify(selectedResult.replay_failure, null, 2)}</pre></div>}<div className="provenance"><h3>Provenance record</h3><div className="provenance-grid">{Object.entries(selected.provenance).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{value}</strong></div>)}</div></div></> : <div className="empty large">Select an imported scenario to inspect trajectories, provenance, and replay metadata.</div>}</section>
        <aside className="controls panel"><div className="panel-heading"><span>03 / MOTION EDIT</span><span className="badge">U0 PREVIEW</span></div><h2>Actor variation</h2><p className="muted">Edit one recorded actor, then preview a deterministic child without mutating the parent.</p>{selectedActorId && <MotionEditor edit={editForActor(selectedActorId)} onChange={updateEdit} seed={seed} onSeedChange={setSeed} /> }<div className="unsupported">BEHAVIOR MODE <strong>UNSUPPORTED</strong><small>Executor is not implemented. No fallback is used.</small></div><div className="preview-actions"><button className="run" disabled={!selected || !selectedActorId || previewBusy} onClick={requestPreview}>{previewBusy ? "PREVIEWING..." : "PREVIEW VARIANT"}</button><button disabled={!selected || !selectedActorId || previewBusy} onClick={requestPreview}>VALIDATE</button><button disabled={!preview} onClick={resetPreview}>RESET</button><button disabled={!preview} onClick={exportPreviewConfig}>EXPORT CONFIG</button></div><div className="batch-divider" /><h3>Existing batch tools</h3><label className="checkbox"><input type="checkbox" checked={replayEnabled} onChange={(e) => setReplayEnabled(e.target.checked)} /> Replay with esmini</label><button className="apply" disabled={!selected || running} onClick={runBatch}>{running ? "RUNNING LOCAL JOB..." : "GENERATE BATCH"}</button><button className="apply" disabled={!selected || !esmini?.available || replayJob?.status === "running" || replayJob?.status === "queued"} onClick={runReplay}>{replayJob?.status === "running" || replayJob?.status === "queued" ? "REPLAY RUNNING..." : "RUN SELECTED WITH ESMINI"}</button>{batch && <BatchSummary batch={batch} onSelect={inspectResult} />}</aside>
    </section>
  </main>;
}

function PathInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) { return <label className="path-input"><span>{label}</span><input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} /></label>; }
function defaultEdit(actor_id: string): ActorMotionEdit { return { actor_id, speed_multiplier: 1, heading_offset_rad: 0, timing_offset_s: 0, initial_gap_delta_m: 0 }; }
function ActorList({ actors, selectedActorId, onSelect }: { actors: ScenarioSummary["actors"]; selectedActorId: string | null; onSelect: (id: string) => void }) { return <div className="actor-list"><h3>Recorded actors</h3>{actors.map((actor) => <button className={`actor-button ${selectedActorId === actor.actor_id ? "active" : ""}`} key={actor.actor_id} onClick={() => onSelect(actor.actor_id)}><span><strong>{actor.actor_id}</strong><small>{actor.actor_type} · {actor.sample_count} states</small></span><span>{selectedActorId === actor.actor_id ? "EDIT" : "→"}</span></button>)}</div>; }
function MotionEditor({ edit, onChange, seed, onSeedChange }: { edit: ActorMotionEdit; onChange: (field: keyof Omit<ActorMotionEdit, "actor_id">, value: number) => void; seed: number; onSeedChange: (value: number) => void }) { const fields: Array<[keyof Omit<ActorMotionEdit, "actor_id">, string, string]> = [["speed_multiplier", "Speed multiplier", "×"], ["heading_offset_rad", "Heading offset", "rad"], ["initial_gap_delta_m", "Initial gap", "m"], ["timing_offset_s", "Timing offset", "s"]]; return <div className="motion-editor"><h3>Edit {edit.actor_id}</h3><div className="motion-grid">{fields.map(([field, label, unit]) => <label key={field}>{label} <span>{unit}</span><input type="number" step="0.05" value={edit[field]} onChange={(e) => onChange(field, Number(e.target.value))} /></label>)}<label>Seed <span>deterministic</span><input type="number" value={seed} onChange={(e) => onSeedChange(Number(e.target.value))} /></label></div></div>; }
function TimelineScrubber({ duration, value, onChange }: { duration: number; value: number; onChange: (value: number) => void }) { return <div className="timeline"><div className="timeline-meta"><span>TIMELINE</span><span>{value.toFixed(2)} / {duration.toFixed(2)} s</span></div><input type="range" min="0" max={duration} step="0.01" value={Math.min(value, duration)} onChange={(e) => onChange(Number(e.target.value))} /></div>; }
function PreviewResult({ preview, onExport }: { preview: PreviewResponse; onExport: () => void }) { return <div className={`preview-status ${preview.status}`}><div className="result-detail-head"><h3>Preview result</h3><span className={`result-label ${preview.status}`}>{preview.status}</span></div><p className="muted">parent {preview.parent_scenario_id} · child {preview.variant_id ?? "not generated"}</p>{preview.status === "unsupported" ? <p className="unsupported-message">{preview.behavior.reason ?? "Unsupported behavior mode."}</p> : <><div className="gate-list">{preview.gates.map((gate) => <div className={`gate-row ${gate.status}`} key={gate.gate_id}><strong>{gate.gate_id}</strong><span>{gate.status}{gate.scientific_status !== "not-applicable" ? ` · ${gate.scientific_status}` : ""}</span></div>)}</div>{preview.validation && <div className="reasons"><strong>{preview.validation.valid ? "Validation passed" : "Validation reasons"}</strong>{preview.validation.reasons.map((reason) => <p key={`${reason.code}-${reason.state_index}`}>{reason.code}: {reason.message}</p>)}</div>}<div className="result-artifacts">{preview.artifacts.map((artifact) => <a key={artifact.path} href={apiUrl(artifact.url.replace("/api", ""))} target="_blank">{artifact.kind} ↗</a>)}<button onClick={onExport}>EXPORT CONFIG</button></div></>}</div>; }
function Stat({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><strong>{value}</strong></div>; }
function Range({ label, value, unit }: { label: string; value: string; unit: string }) { return <div className="range"><span>{label}</span><strong>{value} <em>{unit}</em></strong><div className="rail"><i /></div></div>; }
function TrajectoryPlot({ trajectory, previewPaths, timelineTime }: { trajectory: TrajectoryResponse | null; previewPaths: TrajectoryPath[]; timelineTime: number }) { if (!trajectory) return <div className="plot empty">Loading trajectory...</div>; const paths = [...trajectory.paths, ...previewPaths]; const xs = paths.flatMap((p) => p.states.map((s) => s.x_m)); const ys = paths.flatMap((p) => p.states.map((s) => s.y_m)); if (!xs.length || !ys.length) return <div className="plot empty">No trajectory states.</div>; const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys); const point = (x: number, y: number) => `${((x - minX) / Math.max(1, maxX - minX)) * 88 + 6},${92 - ((y - minY) / Math.max(1, maxY - minY)) * 80}`; return <div><div className="plot"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><path d="M 0,50 L 100,50" className="lane" />{paths.map((path, index) => <polyline key={`${path.actor_id}-${path.path_kind}-${index}`} points={path.states.map((s) => point(s.x_m, s.y_m)).join(" ")} className={`path ${path.path_kind}`} />)}</svg><div className="legend"><span><i className="legend-recorded" /> recorded</span><span><i className="legend-generated" /> generated</span><span><i className="legend-replayed" /> replayed</span><span className="plot-note">t={timelineTime.toFixed(2)}s · {trajectory.map_warning}</span></div></div></div>; }
function ResultDetail({ result, onExport, exporting }: { result: VariantResult; onExport: () => void; exporting: boolean }) { return <div className="result-detail"><div className="result-detail-head"><h3>Variant result</h3><span className={`result-label ${result.status}`}>{result.status}</span></div><div className="config-grid">{Object.entries(result.configuration).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{String(value)}</strong></div>)}</div>{result.gates.length > 0 && <div className="gate-list">{result.gates.map((gate) => <div className={`gate-row ${gate.status}`} key={gate.gate_id}><strong>{gate.gate_id}</strong><span>{gate.status} · {gate.scientific_status}</span></div>)}</div>}{result.replay_metric_aggregate && <div className="score"><span>replay ADE aggregate</span><strong>{result.replay_metric_aggregate.ade_m.mean.toFixed(3)} m</strong><small>median {result.replay_metric_aggregate.ade_m.median.toFixed(3)} · p95 {result.replay_metric_aggregate.ade_m.p95.toFixed(3)} · FDE {result.replay_metric_aggregate.fde_m?.mean.toFixed(3) ?? "n/a"} m</small></div>}{result.validation.reasons.length > 0 && <div className="reasons"><strong>Validation reasons</strong>{result.validation.reasons.map((reason) => <p key={`${reason.code}-${reason.state_index}`}>{reason.code}: {reason.message}</p>)}</div>}{result.ranking?.breakdown && <div className="score"><span>score</span><strong>{result.ranking.breakdown.total.toFixed(3)}</strong><small>risk {result.ranking.features.risk_signal.toFixed(3)} · novelty {result.ranking.features.novelty.toFixed(3)} · distance {result.ranking.features.minimum_distance_m?.toFixed(2) ?? "n/a"} m · TTC {result.ranking.features.minimum_ttc_s?.toFixed(2) ?? "n/a"} s</small></div>}<div className="result-artifacts">{result.artifacts.map((artifact) => <a key={artifact.path} href={apiUrl(artifact.url.replace("/api", ""))} target="_blank">{artifact.kind} ↗</a>)}{result.status === "valid" && <button onClick={onExport} disabled={exporting}>{exporting ? "EXPORTING..." : "EXPORT XOSC"}</button>}</div></div>; }
function ReplayStatus({ job }: { job: ReplayJob }) { return <div className="result-detail"><div className="result-detail-head"><h3>Esmini replay</h3><span className={`result-label ${job.status}`}>{job.status}</span></div>{job.failure_code && <p className="muted">failure: {job.failure_code}</p>}{job.error && <p>{job.error}</p>}{job.tool_version && <p className="muted">{job.tool_version} · exit {String(job.exit_code ?? "n/a")}</p>}<div className="result-artifacts">{Object.entries(job.artifacts).map(([kind, path]) => <a key={kind} href={apiUrl(path.replace("/api", ""))} target="_blank">{kind} ↗</a>)}</div></div>; }
function BatchSummary({ batch, onSelect }: { batch: BatchResults; onSelect: (result: VariantResult) => void }) { return <div className="batch-summary"><div className="batch-top"><span>JOB COMPLETE</span><strong>seed {String(batch.manifest.seed)}</strong></div><div className="result-counts"><div className="valid"><strong>{batch.counts.valid}</strong><span>valid</span></div><div className="invalid"><strong>{batch.counts.invalid}</strong><span>invalid</span></div><div className="failed"><strong>{batch.counts.simulator_failed}</strong><span>simulator failed</span></div></div>{batch.replay_metric_aggregate ? <div className="score"><span>replay ADE · provisional diagnostic</span><strong>{batch.replay_metric_aggregate.ade_m.mean.toFixed(3)} m</strong><small>median {batch.replay_metric_aggregate.ade_m.median.toFixed(3)} · p95 {batch.replay_metric_aggregate.ade_m.p95.toFixed(3)} · FDE {batch.replay_metric_aggregate.fde_m?.mean.toFixed(3) ?? "n/a"} m</small></div> : <p className="muted">No replay metrics available.</p>}<div className="result-list">{batch.results.slice(0, 8).map((result) => <button className="result" key={result.variant_id} onClick={() => onSelect(result)}><span className={`status ${result.status}`} /> <span>{result.variant_id.slice(-16)}</span><strong>{result.ranking?.breakdown?.total.toFixed(3) ?? result.status}</strong></button>)}</div></div>; }

export default App;

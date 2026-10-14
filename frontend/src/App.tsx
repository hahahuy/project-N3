import { useEffect, useState } from "react";
import { apiUrl, fetchScenarios, fetchWorkspaceDocument, fetchWorkspaceScenario, ScenarioSummary, TrajectoryResponse, WorkspaceDocument, WorkspaceScenario } from "./api";

type ViewType = "top-down" | "third-person" | "lidar";
type View = { id: number; type: ViewType };
type Panel = "recipe" | "catalog" | "layers" | "comments";
type Flyout = "metrics" | "gates" | "provenance" | "artifacts";

const viewLabels: Record<ViewType, string> = { "top-down": "Top-down", "third-person": "3rd-person POV", lidar: "LiDAR 3D" };

function App() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selected, setSelected] = useState<ScenarioSummary | null>(null);
  const [trajectory, setTrajectory] = useState<TrajectoryResponse | null>(null);
  const [workspaceDocument, setWorkspaceDocument] = useState<WorkspaceDocument | null>(null);
  const [workspaceScenario, setWorkspaceScenario] = useState<WorkspaceScenario | null>(null);
  const [panel, setPanel] = useState<Panel>("catalog");
  const [flyout, setFlyout] = useState<Flyout | null>(null);
  const [views, setViews] = useState<View[]>([{ id: 1, type: "top-down" }]);
  const [nextViewId, setNextViewId] = useState(2);
  const [activeTab, setActiveTab] = useState("Scenario studio");
  const [mode, setMode] = useState("select");
  const [timeline, setTimeline] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [catalogFilter, setCatalogFilter] = useState("");
  const [addViewOpen, setAddViewOpen] = useState(false);

  useEffect(() => { fetchScenarios().then(setScenarios).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, []);
  useEffect(() => {
    if (!selected) { setTrajectory(null); return; }
    Promise.all([fetchWorkspaceDocument(selected.scenario_id), fetchWorkspaceScenario(selected.scenario_id)])
      .then(([document, view]) => { setWorkspaceDocument(document); setWorkspaceScenario(view); setSelected(view.scenario); setTrajectory({ scenario_id: view.scenario.scenario_id, coordinate_frame: view.scenario.coordinate_frame, duration_s: view.scenario.duration_s, map_warning: view.layers.map_lanes.available ? "" : (view.layers.map_lanes.unavailable_reason ?? "Map lanes unavailable"), paths: view.paths, replay_metrics: view.metrics.per_actor }); setTimeline(0); })
      .catch((e) => setError(e.message));
  }, [selected?.scenario_id]);

  function selectPanel(next: Panel) { setPanel(panel === next ? "catalog" : next); setFlyout(null); }
  function addView(type: ViewType) {
    if (views.length >= 4 || type !== "top-down") return;
    setViews([...views, { id: nextViewId, type }]); setNextViewId(nextViewId + 1);
    setAddViewOpen(false);
  }
  function closeView(id: number) { setViews(views.filter((view) => view.id !== id)); }
  function resetLayout() { setViews([{ id: 1, type: "top-down" }]); setNextViewId(2); }

  return <main className="workspace-app">
    <header className="titlebar">
      <div className="brand"><span className="brand-mark">R2S</span><div><strong>Scenario workspace</strong><span>untitled scenario document</span></div></div>
      <div className="title-status"><AvailabilityChip label="connection" availability={workspaceDocument?.connection} loading={!workspaceDocument} /><AvailabilityChip label="esmini" availability={workspaceDocument?.esmini} loading={!workspaceDocument} /><AvailabilityChip label="dataset" availability={workspaceDocument?.dataset} loading={!workspaceDocument} /><button className="quiet-button">Export</button></div>
    </header>
    <nav className="toolbar" aria-label="Workspace toolbar">
      <ToolbarGroup label="History"><ToolButton label="Undo" shortcut="Ctrl+Z" disabled /><ToolButton label="Redo" shortcut="Ctrl+Shift+Z" disabled /></ToolbarGroup>
      <ToolbarGroup label="Import"><ToolButton label="Import scene" shortcut="I" onClick={() => selectPanel("catalog")} /></ToolbarGroup>
      <ToolbarGroup label="Edit"><ToolButton label="Select actors" shortcut="S" onClick={() => setMode("select")} /><ToolButton label="Edit motion" shortcut="E" disabled /><ToolButton label="Behavior mode" badge="unsupported" disabled /></ToolbarGroup>
      <ToolbarGroup label="Check / Run"><ToolButton label="Validate" shortcut="V" disabled /><ToolButton label="Replay" disabled /></ToolbarGroup>
      <ToolbarGroup label="Inspect"><ToolButton label="Measure" shortcut="M" onClick={() => setMode("measure")} /><ToolButton label="Compare" shortcut="C" disabled /></ToolbarGroup>
      <ToolbarGroup label="View"><div className="add-view-control"><ToolButton label="Add view" shortcut="Shift+V" onClick={() => setAddViewOpen(!addViewOpen)} />{addViewOpen && <AddViewMenu viewCount={views.length} onAdd={addView} />}</div></ToolbarGroup>
      <button className="command-search" aria-label="Search commands">Search commands <kbd>Alt+C</kbd></button>
    </nav>
    <div className="workspace-body">
      <aside className="left-rail" aria-label="Workspace navigation">
        <IconButton label="Recipe" active={panel === "recipe"} onClick={() => selectPanel("recipe")} icon="R" />
        <IconButton label="Catalog" active={panel === "catalog"} onClick={() => selectPanel("catalog")} icon="C" />
        <IconButton label="Map layers" active={panel === "layers"} onClick={() => selectPanel("layers")} icon="M" />
        <IconButton label="Comments" active={panel === "comments"} onClick={() => selectPanel("comments")} icon="#" />
      </aside>
      <aside className="left-panel">{panel === "catalog" && <Catalog scenarios={scenarios} selected={selected} loading={loading} filter={catalogFilter} onFilter={setCatalogFilter} onSelect={setSelected} />}{panel === "recipe" && <EmptyPanel title="Recipe" copy="Import a scene to start a recipe" />}{panel === "layers" && <EmptyPanel title="Map layers" copy="Map layers are unavailable until a scenario is selected." />}{panel === "comments" && <EmptyPanel title="Comments" copy="No comments in this document." />}</aside>
      <section className="view-manager" aria-label="View manager">
        <div className="view-manager-head"><div><span className="section-kicker">{activeTab.toUpperCase()}</span><strong>{selected?.scenario_id ?? "No scenario selected"}</strong></div><div className="mode-switcher" aria-label="Mode">{["select", "edit", "measure", "compare"].map((item) => <button key={item} className={mode === item ? "active" : ""} onClick={() => setMode(item)} disabled={item !== "select" && item !== "measure"}>{item}</button>)}</div><button className="reset-button" onClick={resetLayout}>Reset layout</button></div>
        {error && <div className="inline-error" role="alert">{error}</div>}
        <div className={`view-grid count-${views.length}`}>
          {views.map((view) => <ViewPane key={view.id} view={view} selected={selected} trajectory={trajectory} timeline={timeline} onClose={() => closeView(view.id)} />)}
          {views.length === 0 && <div className="empty-view"><strong>No views open.</strong><span>Add a view.</span><button onClick={() => addView("top-down")}>Add a Top-down view</button></div>}
        </div>
        <div className="timeline-bar"><span>G1-G7 gate lane</span><span className="gate-segment pass">pass</span><span className="gate-segment skipped">skipped</span><span className="gate-segment unavailable">not measured</span><label>playhead <input aria-label="Playhead" type="range" min="0" max={selected?.duration_s ?? 20} step=".01" value={timeline} onChange={(e) => setTimeline(Number(e.target.value))} /></label><strong>{timeline.toFixed(2)} s</strong></div>
      </section>
      <aside className="right-rail" aria-label="Inspection navigation">
        <IconButton label="Metrics" badge="0" active={flyout === "metrics"} onClick={() => setFlyout(flyout === "metrics" ? null : "metrics")} icon="M" />
        <IconButton label="Gates" badge="0" active={flyout === "gates"} onClick={() => setFlyout(flyout === "gates" ? null : "gates")} icon="G" />
        <IconButton label="Provenance" active={flyout === "provenance"} onClick={() => setFlyout(flyout === "provenance" ? null : "provenance")} icon="P" />
        <IconButton label="Artifacts" active={flyout === "artifacts"} onClick={() => setFlyout(flyout === "artifacts" ? null : "artifacts")} icon="A" />
        {flyout && <WorkspaceFlyout flyout={flyout} workspace={workspaceScenario} selected={selected} />}
      </aside>
    </div>
    <footer className="document-footer"><div className="document-tabs">{["Scenario studio", "Variant studio", "Replay", "Report"].map((tab) => <button className={activeTab === tab ? "active" : ""} key={tab} onClick={() => setActiveTab(tab)}>{tab}</button>)}</div><div className="status-bar"><span>selection: {selected?.scenario_id ?? "none"}</span><span>branch: main</span><span>rollback: n/a</span><span>PROVISIONAL: 0</span><span>frame: {selected?.coordinate_frame ?? "n/a"}</span></div></footer>
  </main>;
}

function ToolbarGroup({ label, children }: { label: string; children: React.ReactNode }) { return <div className="toolbar-group"><span>{label}</span><div>{children}</div></div>; }
function ToolButton({ label, shortcut, badge, disabled, onClick }: { label: string; shortcut?: string; badge?: string; disabled?: boolean; onClick?: () => void }) { return <button className="tool-button" disabled={disabled} title={`${label}${shortcut ? ` (${shortcut})` : ""}${disabled ? " - unavailable in this build" : ""}`} onClick={onClick}><span className="tool-icon">{label.slice(0, 1)}</span>{label}{badge && <small>{badge}</small>}</button>; }
function IconButton({ label, icon, badge, active, onClick }: { label: string; icon: string; badge?: string; active?: boolean; onClick: () => void }) { return <button className={`icon-button ${active ? "active" : ""}`} aria-label={label} title={label} onClick={onClick}><span>{icon}</span>{badge && <b>{badge}</b>}</button>; }
function StatusBadge({ status }: { status: string }) { return <span className={`status-badge ${status}`}>{status}</span>; }
function AvailabilityChip({ label, availability, loading }: { label: string; availability?: { available: boolean; unavailable_reason: string | null }; loading: boolean }) { const status = loading ? "loading" : availability?.available ? "available" : "unavailable"; return <span className={`chip ${status}`} title={availability?.unavailable_reason ?? status}>{label}: {status}</span>; }
function WorkspaceFlyout({ flyout, workspace, selected }: { flyout: Flyout; workspace: WorkspaceScenario | null; selected: ScenarioSummary | null }) { if (!workspace || !selected) return <div className="flyout"><span className="section-kicker">{flyout}</span><h2>Unavailable</h2><p>Select an imported scenario first.</p><StatusBadge status="unavailable" /></div>; if (flyout === "metrics") return <div className="flyout"><span className="section-kicker">METRICS</span><h2>{workspace.metrics.available ? "Replay metrics" : "Metrics unavailable"}</h2><p>{workspace.metrics.unavailable_reason ?? "Source: replay trace"}</p><StatusBadge status={workspace.metrics.available ? "available" : "n/a"} />{workspace.metrics.available && Object.entries(workspace.metrics.per_actor).map(([actorId, metric]) => <div className="flyout-row" key={actorId}><strong>{actorId}</strong><span>ADE {metric.ade_m?.toFixed(3) ?? "n/a"} · {metric.coverage_status ?? "unknown"}</span></div>)}</div>; if (flyout === "gates") return <div className="flyout"><span className="section-kicker">GATES</span><h2>G1-G7 gates</h2>{workspace.gates.length ? workspace.gates.map((gate) => <div className="flyout-row" key={gate.gate_id}><strong>{gate.gate_id}</strong><span><StatusBadge status={gate.status} /> {gate.scientific_status}</span></div>) : <p>No gate results available for this scenario.</p>}</div>; if (flyout === "provenance") return <div className="flyout"><span className="section-kicker">PROVENANCE</span><h2>{selected.scenario_id}</h2>{Object.entries(selected.provenance).map(([key, value]) => <div className="flyout-row" key={key}><strong>{key}</strong><span>{value}</span></div>)}</div>; return <div className="flyout"><span className="section-kicker">ARTIFACTS</span><h2>{selected.available_artifacts.length} available</h2>{selected.available_artifacts.map((artifact) => <a className="artifact-link" key={artifact.path} href={apiUrl(artifact.url.replace("/api", ""))} target="_blank">{artifact.kind} ↗</a>)}</div>; }
function EmptyPanel({ title, copy }: { title: string; copy: string }) { return <div className="panel-content"><span className="section-kicker">LEFT PANEL</span><h2>{title}</h2><p>{copy}</p></div>; }
function Catalog({ scenarios, selected, loading, filter, onFilter, onSelect }: { scenarios: ScenarioSummary[]; selected: ScenarioSummary | null; loading: boolean; filter: string; onFilter: (value: string) => void; onSelect: (scenario: ScenarioSummary) => void }) { const visible = scenarios.filter((scenario) => scenario.scenario_id.toLowerCase().includes(filter.toLowerCase())); return <div className="panel-content"><div className="panel-title"><span className="section-kicker">CATALOG</span><span className="count">{visible.length}/{scenarios.length}</span></div><input className="filter" value={filter} onChange={(event) => onFilter(event.target.value)} placeholder="Filter scenarios" aria-label="Filter scenarios" />{loading ? <div className="skeleton-list"><i /><i /><i /></div> : scenarios.length === 0 ? <div className="panel-empty">Import a scene to start a scenario.</div> : visible.length === 0 ? <div className="panel-empty">No scenarios match this filter.</div> : <div className="scenario-list">{visible.map((scenario) => <button className={selected?.scenario_id === scenario.scenario_id ? "selected" : ""} key={scenario.scenario_id} onClick={() => onSelect(scenario)}><span><strong>{scenario.scenario_id}</strong><small>{scenario.artifact_type} / {scenario.duration_s.toFixed(2)} s</small></span><em>:</em></button>)}</div>}</div>; }
function AddViewMenu({ viewCount, onAdd }: { viewCount: number; onAdd: (type: ViewType) => void }) { const atLimit = viewCount >= 4; return <div className="add-view-menu" role="menu"><button disabled={atLimit} onClick={() => onAdd("top-down")}><strong>Top-down</strong><small>{atLimit ? "maximum 4 views reached" : "available"}</small></button><button disabled><strong>3rd-person POV</strong><small>not in this build - U5</small></button><button disabled><strong>LiDAR 3D</strong><small>unavailable - no point-cloud access</small></button></div>; }
function ViewPane({ view, selected, trajectory, timeline, onClose }: { view: View; selected: ScenarioSummary | null; trajectory: TrajectoryResponse | null; timeline: number; onClose: () => void }) { return <article className="view-pane"><header><span className="view-icon">{view.type === "top-down" ? "T" : "3"}</span><strong>{viewLabels[view.type]}</strong><span className="view-target">{selected ? ` - ${selected.scenario_id}` : " - empty"}</span><select aria-label="Camera preset" defaultValue="default"><option value="default">Camera preset</option><option>North-up</option><option>Ego-up</option></select><button className="view-action">Layers</button><button className="view-action">Maximize</button><button className="close-view" aria-label={`Close view: ${viewLabels[view.type]}`} title={`Close view: ${viewLabels[view.type]}`} onClick={onClose}>x</button></header>{view.type !== "top-down" ? <div className="unavailable-view"><StatusBadge status={view.type === "lidar" ? "unavailable" : "unsupported"} /><strong>{viewLabels[view.type]} unavailable</strong><p>{view.type === "lidar" ? "not in this build - no point cloud access" : "not in this build - 3D foundation is U5"}</p></div> : <TopDownView selected={selected} trajectory={trajectory} timeline={timeline} />}</article>; }
function TopDownView({ selected, trajectory, timeline }: { selected: ScenarioSummary | null; trajectory: TrajectoryResponse | null; timeline: number }) { if (!selected) return <div className="canvas-empty">Select an imported scenario</div>; if (!trajectory) return <div className="canvas-empty">Loading Top-down view</div>; const paths = trajectory.paths; const xs = paths.flatMap((path) => path.states.map((state) => state.x_m)); const ys = paths.flatMap((path) => path.states.map((state) => state.y_m)); const minX = Math.min(...xs, 0), maxX = Math.max(...xs, 1), minY = Math.min(...ys, 0), maxY = Math.max(...ys, 1); const point = (x: number, y: number) => `${((x - minX) / Math.max(1, maxX - minX)) * 82 + 9},${91 - ((y - minY) / Math.max(1, maxY - minY)) * 80}`; return <div className="top-down"><svg viewBox="0 0 100 100" role="img" aria-label="Top-down trajectory view"><path className="road" d="M0 50 H100" />{paths.map((path) => <polyline key={path.actor_id} className={path.path_kind} points={path.states.map((state) => point(state.x_m, state.y_m)).join(" ")} />)}</svg><div className="view-legend"><span><i className="recorded-line" /> recorded</span><span><i className="generated-line" /> generated</span><span>t={timeline.toFixed(2)} s</span></div></div>; }

export default App;

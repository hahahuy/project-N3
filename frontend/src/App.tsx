import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { apiUrl, ArtifactLink, EsminiCapability, fetchEsminiCapability, fetchScenario, fetchScenarioArtifacts, fetchScenarios, fetchSettings, fetchTrajectory, ScenarioSummary, SettingsView, TrajectoryResponse } from "./api";
import { Icon, IconName } from "./icons";

type ViewType = "top-down" | "third-person" | "lidar";
type View = { id: number; type: ViewType };
type Panel = "recipe" | "catalog" | "layers" | "comments";
type Flyout = "metrics" | "gates" | "provenance" | "artifacts";
type Tool = { icon: IconName; label: string; shortcut?: string; disabled?: boolean; onClick?: () => void; menu?: React.ReactNode };
type StatusLine = { label: string; available: boolean; note?: string };
type CameraPreset = "default" | "north-up" | "ego-up";
type Command = { label: string; group: string; icon: IconName; shortcut?: string; disabled?: boolean; run: () => void };

const viewLabels: Record<ViewType, string> = { "top-down": "Top-down", "third-person": "3rd-person POV", lidar: "LiDAR 3D" };
const DOCUMENT_TABS = ["Scenario studio", "Variant studio", "Replay", "Report"] as const;
const PANEL_DEFAULT_WIDTH = 270;
const PANEL_MIN_WIDTH = 180;
const PANEL_MAX_WIDTH = 520;

function App() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selected, setSelected] = useState<ScenarioSummary | null>(null);
  const [trajectory, setTrajectory] = useState<TrajectoryResponse | null>(null);
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
  const [leftOpen, setLeftOpen] = useState(true);
  const [headerOpen, setHeaderOpen] = useState(true);
  const [dark, setDark] = useState(() => {
    const stored = window.localStorage.getItem("r2s-theme");
    if (stored === "dark" || stored === "light") return stored === "dark";
    return typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  const [capability, setCapability] = useState<EsminiCapability | null>(null);
  const [settings, setSettings] = useState<SettingsView | null>(null);
  const [panelWidth, setPanelWidth] = useState(PANEL_DEFAULT_WIDTH);
  const [resizing, setResizing] = useState(false);
  const dragRef = useRef({ startX: 0, startWidth: PANEL_DEFAULT_WIDTH });
  const [overflowOpen, setOverflowOpen] = useState(false);
  const groupsRef = useRef<HTMLDivElement | null>(null);
  const [hiddenTools, setHiddenTools] = useState<string[]>([]);
  const [maximized, setMaximized] = useState<number | null>(null);
  const [hiddenKinds, setHiddenKinds] = useState<string[]>([]);
  const [layersOpen, setLayersOpen] = useState<number | null>(null);
  const [presets, setPresets] = useState<Record<number, CameraPreset>>({});
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [artifacts, setArtifacts] = useState<ArtifactLink[] | null>(null);

  const toolbarGroups: { label: string; tools: Tool[] }[] = [
    { label: "History", tools: [{ icon: "undo", label: "Undo", shortcut: "Ctrl+Z", disabled: true }, { icon: "redo", label: "Redo", shortcut: "Ctrl+Shift+Z", disabled: true }] },
    { label: "Import", tools: [{ icon: "import", label: "Import scene", shortcut: "I", onClick: () => openPanel("catalog") }, { icon: "export", label: "Export", onClick: exportSelected, disabled: !selected }] },
    { label: "Edit", tools: [{ icon: "cursor", label: "Select actors", shortcut: "S", onClick: () => setMode("select") }, { icon: "edit", label: "Edit motion", shortcut: "E", disabled: true }, { icon: "behavior", label: "Behavior mode", disabled: true }] },
    { label: "Check / Run", tools: [{ icon: "validate", label: "Validate", shortcut: "V", disabled: true }, { icon: "replay", label: "Replay", disabled: true }] },
    { label: "Inspect", tools: [{ icon: "measure", label: "Measure", shortcut: "M", onClick: () => setMode("measure") }, { icon: "compare", label: "Compare", shortcut: "C", disabled: true }] },
    { label: "View", tools: [{ icon: "add-view", label: "Add view", shortcut: "Shift+V", onClick: () => setAddViewOpen(!addViewOpen), menu: addViewOpen ? <AddViewMenu viewCount={views.length} onAdd={addView} /> : undefined }] },
  ];

  useLayoutEffect(() => {
    const host = groupsRef.current;
    if (!host) return;
    const buttons = Array.from(host.querySelectorAll<HTMLButtonElement>(".tool-button"));
    const restore = () => buttons.forEach((button) => { button.style.display = ""; });
    let frame = 0;
    const measure = () => {
      restore();
      const available = host.clientWidth;
      if (available <= 0) return;
      const hidden: string[] = [];
      let used = 0;
      for (const group of Array.from(host.querySelectorAll<HTMLElement>(".toolbar-group"))) {
        const tools = Array.from(group.querySelectorAll<HTMLButtonElement>(".tool-button"));
        const overhead = Math.max(0, group.offsetWidth - tools.reduce((sum, tool) => sum + tool.offsetWidth, 0));
        if (used + overhead <= available) used += overhead;
        for (const tool of tools) {
          if (used + tool.offsetWidth <= available) used += tool.offsetWidth;
          else if (tool.dataset.tool) hidden.push(tool.dataset.tool);
        }
      }
      buttons.forEach((button) => { button.style.display = button.dataset.tool && hidden.includes(button.dataset.tool) ? "none" : ""; });
      setHiddenTools((previous) => previous.length === hidden.length && previous.every((item, index) => item === hidden[index]) ? previous : hidden);
    };
    const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(measure); };
    schedule();
    const observer = new ResizeObserver(schedule);
    observer.observe(host);
    window.addEventListener("resize", schedule);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); window.removeEventListener("resize", schedule); restore(); };
  }, [headerOpen, addViewOpen]);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.localStorage.setItem("r2s-theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => { fetchScenarios().then(setScenarios).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, []);
  useEffect(() => {
    fetchEsminiCapability().then(setCapability).catch(() => setCapability(null));
    fetchSettings().then(setSettings).catch(() => setSettings(null));
  }, []);
  useEffect(() => {
    if (!selected) { setArtifacts(null); return; }
    fetchScenarioArtifacts(selected.scenario_id).then((payload) => setArtifacts(payload.artifacts)).catch(() => setArtifacts(null));
  }, [selected?.scenario_id]);
  useEffect(() => {
    if (!selected) { setTrajectory(null); return; }
    Promise.all([fetchScenario(selected.scenario_id), fetchTrajectory(selected.scenario_id)])
      .then(([detail, paths]) => { setSelected(detail); setTrajectory(paths); setTimeline(0); setError(null); })
      .catch((e) => setError(e.message));
  }, [selected?.scenario_id]);

  function selectPanel(next: Panel) { setFlyout(null); if (leftOpen && panel === next) { setLeftOpen(false); return; } setLeftOpen(true); setPanel(next); }
  function openPanel(next: Panel) { setFlyout(null); setLeftOpen(true); setPanel(next); }
  function openFlyout(next: Flyout) { setFlyout(flyout === next ? null : next); }
  function addView(type: ViewType) {
    if (views.length >= 4 || type !== "top-down") return;
    setViews([...views, { id: nextViewId, type }]); setNextViewId(nextViewId + 1);
    setAddViewOpen(false);
  }
  function closeView(id: number) { setViews(views.filter((view) => view.id !== id)); if (maximized === id) setMaximized(null); }
  function resetLayout() { setViews([{ id: 1, type: "top-down" }]); setNextViewId(2); setMaximized(null); setHiddenKinds([]); }
  function exportSelected() {
    if (!selected) { setError("Select a scenario before exporting."); return; }
    const payload = { exported_at: new Date().toISOString(), source: "project-N3 local workspace", scenario: selected, trajectory };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${selected.scenario_id}.r2s.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
  function toggleKind(kind: string) { setHiddenKinds((previous) => previous.includes(kind) ? previous.filter((item) => item !== kind) : [...previous, kind]); }

  function startResize(event: React.PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    dragRef.current = { startX: event.clientX, startWidth: panelWidth };
    setResizing(true);
  }

  function resizeByKeyboard(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      if (panelWidth - 16 < PANEL_MIN_WIDTH) { setLeftOpen(false); return; }
      setPanelWidth(panelWidth - 16);
    }
    if (event.key === "ArrowRight") { event.preventDefault(); setLeftOpen(true); setPanelWidth(Math.min(PANEL_MAX_WIDTH, panelWidth + 16)); }
    if (event.key === "Home") { event.preventDefault(); setLeftOpen(true); setPanelWidth(PANEL_DEFAULT_WIDTH); }
  }

  useEffect(() => {
    if (!resizing) return;
    const onMove = (event: PointerEvent) => {
      const next = dragRef.current.startWidth + (event.clientX - dragRef.current.startX);
      if (next < PANEL_MIN_WIDTH) { setPanelWidth(PANEL_MIN_WIDTH); setLeftOpen(false); setResizing(false); return; }
      setLeftOpen(true);
      setPanelWidth(Math.min(PANEL_MAX_WIDTH, next));
    };
    const onRelease = () => setResizing(false);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onRelease);
    window.addEventListener("pointercancel", onRelease);
    return () => { window.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onRelease); window.removeEventListener("pointercancel", onRelease); };
  }, [resizing]);

  const bodyClass = `workspace-body${leftOpen ? "" : " left-collapsed"}`;
  const bodyStyle = { "--panel-width": `${leftOpen ? panelWidth : 0}px` } as React.CSSProperties;
  const esminiAvailable = capability?.available === true;
  const datasetAvailable = settings?.dataset_root_exists === true;
  const simulatorLines: StatusLine[] = [
    { label: "esmini", available: esminiAvailable, note: capability?.version ?? undefined },
    { label: "CARLA", available: false },
  ];
  const datasetLines: StatusLine[] = [{ label: "nuScenes", available: datasetAvailable, note: settings?.dataset_version ?? undefined }];
  const simulationTone = simulatorLines.every((line) => line.available) ? "all" : simulatorLines.some((line) => line.available) ? "some" : "off";
  const datasetTone = datasetLines.every((line) => line.available) ? "all" : "off";

  const commands: Command[] = [
    ...toolbarGroups.flatMap((group) => group.tools.map((tool) => ({ label: tool.label, group: group.label, icon: tool.icon, shortcut: tool.shortcut, disabled: tool.disabled, run: () => tool.onClick?.() }))),
    { label: "Reset layout", group: "View", icon: "compare", run: resetLayout },
    { label: maximized === null ? "Maximize first view" : "Restore maximized view", group: "View", icon: "add-view", disabled: views.length === 0, run: () => setMaximized(maximized === null ? views[0].id : null) },
    { label: dark ? "Switch to light mode" : "Switch to dark mode", group: "View", icon: dark ? "sun" : "moon", run: () => setDark(!dark) },
    { label: headerOpen ? "Minimize header" : "Restore header", group: "View", icon: "chevron-up", run: () => setHeaderOpen(!headerOpen) },
  ];
  const visibleCommands = commands.filter((command) => `${command.group} ${command.label}`.toLowerCase().includes(commandQuery.trim().toLowerCase()));

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && commandOpen) { setCommandOpen(false); return; }
      if (event.altKey && event.key.toLowerCase() === "c") { event.preventDefault(); setCommandOpen(true); return; }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setCommandOpen(true); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [commandOpen]);

  return <main className={`workspace-app${headerOpen ? "" : " header-collapsed"}`}>
    {headerOpen && <header className="titlebar">
      <div className="brand"><span className="brand-mark">R2S</span><div><strong>project-N3</strong><span>untitled scenario document</span></div></div>
      <div className="title-status"><StatusChip label={simulationTone === "off" ? "Simulation Off" : "Simulation On"} tone={simulationTone} lines={simulatorLines} /><StatusChip label={datasetTone === "off" ? "Dataset Off" : "Dataset On"} tone={datasetTone} lines={datasetLines} /><button className="theme-toggle" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} aria-pressed={dark} title={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={() => setDark(!dark)}><Icon name={dark ? "sun" : "moon"} /></button></div>
    </header>}
    <nav className="toolbar" aria-label="Workspace toolbar">
      <div className="toolbar-groups" ref={groupsRef}>
        {toolbarGroups.map((group) => <ToolbarGroup key={group.label}>{group.tools.map((tool) => <ToolButton key={tool.label} {...tool} />)}</ToolbarGroup>)}
      </div>
      <div className="toolbar-tail">
        <div className="toolbar-overflow-control">
          <button className={`toolbar-overflow${overflowOpen ? " active" : ""}`} aria-label="More tools" aria-expanded={overflowOpen} title="More tools" disabled={hiddenTools.length === 0} onClick={() => setOverflowOpen(!overflowOpen)}><Icon name="more" /></button>
          {overflowOpen && hiddenTools.length > 0 && <div className="add-view-menu overflow-menu" role="menu">{hiddenTools.map((label) => { const tool = toolbarGroups.flatMap((group) => group.tools).find((item) => item.label === label); return tool && <button key={label} role="menuitem" disabled={tool.disabled} onClick={() => { tool.onClick?.(); setOverflowOpen(false); }}><span className="overflow-menu-icon"><Icon name={tool.icon} /></span><span><strong>{tool.label}</strong><small>{tool.disabled ? "unavailable in this build" : tool.shortcut ? `shortcut ${tool.shortcut}` : "available"}</small></span></button>; })}</div>}
        </div>
        <button className="command-search" aria-label="Search commands" aria-expanded={commandOpen} onClick={() => setCommandOpen(true)}><Icon name="catalog" size={14} /> Search commands <kbd>Alt+C</kbd></button>
        <HeaderToggle open={headerOpen} onToggle={() => setHeaderOpen(!headerOpen)} />
      </div>
    </nav>
    <div className={bodyClass} style={bodyStyle}>
      <aside className="left-rail" aria-label="Workspace navigation">
        <IconButton icon="recipe" label="Recipe" active={leftOpen && panel === "recipe"} onClick={() => selectPanel("recipe")} />
        <IconButton icon="catalog" label="Catalog" active={leftOpen && panel === "catalog"} onClick={() => selectPanel("catalog")} />
        <IconButton icon="layers" label="Map layers" active={leftOpen && panel === "layers"} onClick={() => selectPanel("layers")} />
        <IconButton icon="comments" label="Comments" active={leftOpen && panel === "comments"} onClick={() => selectPanel("comments")} />
      </aside>
      <aside className="left-panel" aria-label={`${panel} panel`}>
        {panel === "catalog" && <Catalog scenarios={scenarios} selected={selected} loading={loading} filter={catalogFilter} onFilter={setCatalogFilter} onSelect={setSelected} />}{panel === "recipe" && <EmptyPanel title="Recipe" copy="Import a scene to start a recipe" />}{panel === "layers" && <EmptyPanel title="Map layers" copy="Map layers are unavailable until a scenario is selected." />}{panel === "comments" && <EmptyPanel title="Comments" copy="No comments in this document." />}
      </aside>
      <div className={`split-handle left${resizing ? " dragging" : ""}`} role="separator" aria-orientation="vertical" aria-label="Resize side panel" aria-valuenow={leftOpen ? panelWidth : 0} aria-valuemin={PANEL_MIN_WIDTH} aria-valuemax={PANEL_MAX_WIDTH} tabIndex={0} onPointerDown={startResize} onKeyDown={resizeByKeyboard} />
      <section className="view-manager" aria-label="View manager">
        <div className="view-manager-head"><div><span className="section-kicker">{activeTab.toUpperCase()}</span><strong>{selected?.scenario_id ?? "No scenario selected"}</strong></div><div className="mode-switcher" aria-label="Mode">{["select", "edit", "measure", "compare"].map((item) => <button key={item} className={mode === item ? "active" : ""} onClick={() => setMode(item)} disabled={item !== "select" && item !== "measure"}>{item}</button>)}</div><button className="reset-button" onClick={resetLayout}>Reset layout</button></div>
        {error && <div className="inline-error" role="alert">{error}</div>}
        {activeTab === "Scenario studio"
          ? <div className={`view-grid count-${views.length}${maximized !== null ? " maximized" : ""}`}>
            {views.map((view) => <ViewPane key={view.id} view={view} selected={selected} trajectory={trajectory} timeline={timeline} preset={presets[view.id] ?? "default"} onPreset={(next) => setPresets({ ...presets, [view.id]: next })} hiddenKinds={hiddenKinds} onToggleKind={toggleKind} layersOpen={layersOpen === view.id} onToggleLayers={() => setLayersOpen(layersOpen === view.id ? null : view.id)} maximized={maximized === view.id} onToggleMaximize={() => setMaximized(maximized === view.id ? null : view.id)} onClose={() => closeView(view.id)} />)}
            {views.length === 0 && <div className="empty-view"><strong>No views open.</strong><span>Add a view.</span><button onClick={() => addView("top-down")}>Add a Top-down view</button></div>}
          </div>
          : <div className="view-grid count-1"><div className="empty-view"><strong>{activeTab}</strong><span>Not available in this build.</span><button onClick={() => setActiveTab("Scenario studio")}>Back to Scenario studio</button></div></div>}
        <div className="timeline-bar"><span>G1-G7 gate lane</span><span className="gate-segment pass">pass</span><span className="gate-segment skipped">skipped</span><span className="gate-segment unavailable">not measured</span><label>playhead <input aria-label="Playhead" type="range" min="0" max={selected?.duration_s ?? 20} step=".01" value={timeline} onChange={(e) => setTimeline(Number(e.target.value))} /></label><strong>{timeline.toFixed(2)} s</strong></div>
      </section>
      <aside className="right-rail" aria-label="Inspection navigation">
        <IconButton icon="metrics" label="Metrics" badge="0" active={flyout === "metrics"} onClick={() => openFlyout("metrics")} />
        <IconButton icon="gates" label="Gates" badge="0" active={flyout === "gates"} onClick={() => openFlyout("gates")} />
        <IconButton icon="provenance" label="Provenance" active={flyout === "provenance"} onClick={() => openFlyout("provenance")} />
        <IconButton icon="artifacts" label="Artifacts" active={flyout === "artifacts"} onClick={() => openFlyout("artifacts")} />
        {flyout && <div className="flyout"><span className="section-kicker">{flyout}</span>{flyout === "metrics" && <><h2>Replay metrics</h2>{trajectory?.replay_metrics && Object.keys(trajectory.replay_metrics).length > 0 ? <div className="flyout-list">{Object.entries(trajectory.replay_metrics).map(([actor, metrics]) => <div className="flyout-row" key={actor}><strong>{actor}</strong><span>RMSE {metrics.position_rmse_m?.toFixed(3) ?? "n/a"} m</span><span>final {metrics.final_displacement_m?.toFixed(3) ?? "n/a"} m</span><span>{metrics.coverage_status ?? "recorded"}</span></div>)}</div> : <><p>No replay metrics for this scenario.</p><StatusBadge status="n/a" /></>}</>}
          {flyout === "gates" && <><h2>G1-G7 gates</h2><p>Gates are produced by the validation and generation pipeline. They are not computed in the browser.</p><StatusBadge status="unavailable" /></>}
          {flyout === "provenance" && <><h2>Provenance</h2>{selected ? (Object.keys(selected.provenance ?? {}).length > 0 ? <div className="flyout-list">{Object.entries(selected.provenance).map(([key, value]) => <div className="flyout-row" key={key}><strong>{key}</strong><span>{value}</span></div>)}</div> : <p>This scenario records no provenance fields.</p>) : <p>Select an imported scenario first.</p>}</>}
          {flyout === "artifacts" && <><h2>Artifacts</h2>{selected ? (artifacts && artifacts.length > 0 ? <div className="flyout-list">{artifacts.map((artifact) => <a className="flyout-row link" key={artifact.path} href={apiUrl(`/artifacts/${artifact.path}`)} target="_blank" rel="noreferrer"><strong>{artifact.kind}</strong><span>{artifact.path}</span></a>)}</div> : <p>No artifacts reported for this scenario.</p>) : <p>Select an imported scenario first.</p>}</>}
        </div>}
      </aside>
    </div>
    <footer className="document-footer"><div className="document-tabs">{DOCUMENT_TABS.map((tab) => <button className={activeTab === tab ? "active" : ""} key={tab} onClick={() => setActiveTab(tab)}>{tab}</button>)}</div><div className="status-bar"><span>selection: {selected?.scenario_id ?? "none"}</span><span>artifacts: {artifacts?.length ?? 0}</span><span>rollback: n/a</span><span>PROVISIONAL: 0</span><span>frame: {selected?.coordinate_frame ?? "n/a"}</span></div></footer>
    {commandOpen && <CommandPalette commands={visibleCommands} query={commandQuery} onQuery={setCommandQuery} onClose={() => { setCommandOpen(false); setCommandQuery(""); }} />}
  </main>;
}

function StatusChip({ label, tone, lines, openDelay = 500 }: { label: string; tone: string; lines: StatusLine[]; openDelay?: number }) {
  const [active, setActive] = useState(false);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const clear = () => { window.clearTimeout(timer.current); timer.current = undefined; };
  const close = () => { clear(); setActive(false); setOpen(false); };
  const hoverStart = () => { setActive(true); clear(); timer.current = window.setTimeout(() => setOpen(true), openDelay); };
  const reveal = () => { setActive(true); clear(); setOpen(true); };
  useEffect(() => () => clear(), []);
  return <span className={`chip status-chip ${tone}${active ? " active" : ""}`} tabIndex={0} aria-expanded={open} onMouseEnter={hoverStart} onMouseLeave={close} onFocus={reveal} onBlur={close} onClick={reveal}>
    {label}
    {open && <span className="status-chip-menu" role="tooltip">{lines.map((line) => <span className="status-chip-row" key={line.label}><span className={`status-dot ${line.available ? "on" : "off"}`} /><strong>{line.label}</strong><em>{line.available ? "available" : "unavailable"}</em>{line.note && <small>{line.note}</small>}</span>)}</span>}
  </span>;
}

function HeaderToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) { return <button className={`toolbar-toggle${open ? " active" : ""}`} aria-label={open ? "Minimize header" : "Restore header"} aria-expanded={open} title={open ? "Minimize header" : "Restore header"} onClick={onToggle}><Icon name={open ? "chevron-up" : "chevron-down"} /></button>; }
function ToolbarGroup({ children }: { children: React.ReactNode }) { return <div className="toolbar-group"><div>{children}</div></div>; }
function ToolButton({ icon, label, shortcut, disabled, onClick, menu }: Tool) { return <div className="add-view-control"><button className="tool-button" data-tool={label} disabled={disabled} title={`${label}${shortcut ? ` (${shortcut})` : ""}${disabled ? " - unavailable in this build" : ""}`} onClick={onClick}><Icon name={icon} />{label}</button>{menu}</div>; }
function IconButton({ label, icon, badge, active, onClick }: { label: string; icon: IconName; badge?: string; active?: boolean; onClick: () => void }) { return <button className={`icon-button ${active ? "active" : ""}`} aria-label={label} title={label} aria-pressed={active} onClick={onClick}><Icon name={icon} />{badge && <b>{badge}</b>}</button>; }
function StatusBadge({ status }: { status: string }) { return <span className={`status-badge ${status}`}>{status}</span>; }
function EmptyPanel({ title, copy }: { title: string; copy: string }) { return <div className="panel-content"><span className="section-kicker">LEFT PANEL</span><h2>{title}</h2><p>{copy}</p></div>; }
function Catalog({ scenarios, selected, loading, filter, onFilter, onSelect }: { scenarios: ScenarioSummary[]; selected: ScenarioSummary | null; loading: boolean; filter: string; onFilter: (value: string) => void; onSelect: (scenario: ScenarioSummary) => void }) { const visible = scenarios.filter((scenario) => scenario.scenario_id.toLowerCase().includes(filter.toLowerCase())); return <div className="panel-content"><div className="panel-title"><span className="section-kicker">CATALOG</span><span className="count">{visible.length}/{scenarios.length}</span></div><input className="filter" value={filter} onChange={(event) => onFilter(event.target.value)} placeholder="Filter scenarios" aria-label="Filter scenarios" />{loading ? <div className="skeleton-list"><i /><i /><i /></div> : scenarios.length === 0 ? <div className="panel-empty">Import a scene to start a scenario.</div> : visible.length === 0 ? <div className="panel-empty">No scenarios match this filter.</div> : <div className="scenario-list">{visible.map((scenario) => <button className={selected?.scenario_id === scenario.scenario_id ? "selected" : ""} key={scenario.scenario_id} onClick={() => onSelect(scenario)}><span><strong>{scenario.scenario_id}</strong><small>{scenario.artifact_type} / {scenario.duration_s.toFixed(2)} s</small></span><em>:</em></button>)}</div>}</div>; }
function AddViewMenu({ viewCount, onAdd }: { viewCount: number; onAdd: (type: ViewType) => void }) { const atLimit = viewCount >= 4; return <div className="add-view-menu" role="menu"><button disabled={atLimit} onClick={() => onAdd("top-down")}><strong>Top-down</strong><small>{atLimit ? "maximum 4 views reached" : "available"}</small></button><button disabled><strong>3rd-person POV</strong><small>not in this build - U5</small></button><button disabled><strong>LiDAR 3D</strong><small>unavailable - no point-cloud access</small></button></div>; }
function ViewPane({ view, selected, trajectory, timeline, preset, onPreset, hiddenKinds, onToggleKind, layersOpen, onToggleLayers, maximized, onToggleMaximize, onClose }: { view: View; selected: ScenarioSummary | null; trajectory: TrajectoryResponse | null; timeline: number; preset: CameraPreset; onPreset: (next: CameraPreset) => void; hiddenKinds: string[]; onToggleKind: (kind: string) => void; layersOpen: boolean; onToggleLayers: () => void; maximized: boolean; onToggleMaximize: () => void; onClose: () => void }) {
  const kinds = trajectory ? Array.from(new Set(trajectory.paths.map((path) => path.path_kind))) : [];
  return <article className={`view-pane${maximized ? " maximized" : ""}`}>
    <header>
      <span className="view-icon"><Icon name={view.type} /></span><strong>{viewLabels[view.type]}</strong><span className="view-target">{selected ? ` - ${selected.scenario_id}` : " - empty"}</span>
      <select aria-label="Camera preset" value={preset} onChange={(event) => onPreset(event.target.value as CameraPreset)}><option value="default">Auto-fit</option><option value="north-up">North-up</option><option value="ego-up">Ego-up</option></select>
      <div className="layers-control"><button className={`view-action${layersOpen ? " active" : ""}`} aria-expanded={layersOpen} onClick={onToggleLayers}>Layers</button>{layersOpen && <div className="layers-menu" role="menu">{kinds.length === 0 ? <p>No trajectory layers loaded.</p> : kinds.map((kind) => <button key={kind} role="menuitemcheckbox" aria-checked={!hiddenKinds.includes(kind)} onClick={() => onToggleKind(kind)}><span className={`status-dot ${hiddenKinds.includes(kind) ? "off" : "on"}`} />{kind}</button>)}</div>}</div>
      <button className={`view-action${maximized ? " active" : ""}`} onClick={onToggleMaximize}>{maximized ? "Restore" : "Maximize"}</button>
      <button className="close-view" aria-label={`Close view: ${viewLabels[view.type]}`} title={`Close view: ${viewLabels[view.type]}`} onClick={onClose}>x</button>
    </header>
    {view.type !== "top-down"
      ? <div className="unavailable-view"><StatusBadge status={view.type === "lidar" ? "unavailable" : "unsupported"} /><strong>{viewLabels[view.type]} unavailable</strong><p>{view.type === "lidar" ? "not in this build - no point cloud access" : "not in this build - 3D foundation is U5"}</p></div>
      : <TopDownView selected={selected} trajectory={trajectory} timeline={timeline} preset={preset} hiddenKinds={hiddenKinds} />}
  </article>;
}

function TopDownView({ selected, trajectory, timeline, preset, hiddenKinds }: { selected: ScenarioSummary | null; trajectory: TrajectoryResponse | null; timeline: number; preset: CameraPreset; hiddenKinds: string[] }) {
  if (!selected) return <div className="canvas-empty">Select an imported scenario</div>;
  if (!trajectory) return <div className="canvas-empty">Loading Top-down view</div>;
  const paths = trajectory.paths.filter((path) => !hiddenKinds.includes(path.path_kind));
  if (paths.length === 0) return <div className="canvas-empty">All trajectory layers are hidden. Re-enable them from Layers.</div>;
  const xs = paths.flatMap((path) => path.states.map((state) => state.x_m));
  const ys = paths.flatMap((path) => path.states.map((state) => state.y_m));
  const minX = Math.min(...xs, 0), maxX = Math.max(...xs, 1), minY = Math.min(...ys, 0), maxY = Math.max(...ys, 1);
  const point = (x: number, y: number) => `${((x - minX) / Math.max(1, maxX - minX)) * 82 + 9},${91 - ((y - minY) / Math.max(1, maxY - minY)) * 80}`;
  const ego = trajectory.paths.find((path) => path.actor_type === "vehicle") ?? trajectory.paths[0];
  const rotation = preset === "ego-up" && ego?.states.length ? -(ego.states[0].yaw_rad * 180) / Math.PI - 90 : 0;
  return <div className="top-down">
    <svg viewBox="0 0 100 100" role="img" aria-label={`Top-down trajectory view, camera preset ${preset}`}><g transform={`rotate(${rotation} 50 50)`}><path className="road" d="M0 50 H100" />{paths.map((path) => <polyline key={path.actor_id} className={path.path_kind} points={path.states.map((state) => point(state.x_m, state.y_m)).join(" ")} />)}</g></svg>
    <div className="view-legend"><span><i className="recorded-line" /> recorded</span><span><i className="generated-line" /> generated</span><span>t={timeline.toFixed(2)} s</span></div>
  </div>;
}

function CommandPalette({ commands, query, onQuery, onClose }: { commands: Command[]; query: string; onQuery: (value: string) => void; onClose: () => void }) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => { inputRef.current?.focus(); }, []);
  return <div className="palette-backdrop" onMouseDown={onClose}>
    <div className="palette" role="dialog" aria-label="Search commands" onMouseDown={(event) => event.stopPropagation()}>
      <input ref={inputRef} value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Search commands" aria-label="Search commands" />
      <div className="palette-list">
        {commands.length === 0 && <p className="palette-empty">No command matches this filter.</p>}
        {commands.map((command) => <button key={`${command.group}-${command.label}`} disabled={command.disabled} onClick={() => { command.run(); onClose(); }}><Icon name={command.icon} /><strong>{command.label}</strong><em>{command.group}</em>{command.shortcut && <kbd>{command.shortcut}</kbd>}</button>)}
      </div>
    </div>
  </div>;
}

export default App;
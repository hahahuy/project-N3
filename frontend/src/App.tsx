import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  ActorTimeline,
  ActorTrack,
  addRecipeStep,
  addRollbackMarker,
  apiUrl,
  ArtifactLink,
  ChannelAvailability,
  ComparePayload,
  EsminiCapability,
  EvidenceLayer,
  EvidenceLayers,
  fetchActorTimeline,
  fetchCompare,
  fetchEsminiCapability,
  fetchEvidenceLayers,
  fetchGateTimeline,
  fetchLidarDescriptor,
  fetchPOVFrame,
  fetchPOVImageFrame,
  fetchLiveCapability,
  fetchRecipe,
  fetchScenario,
  fetchScenarioArtifacts,
  fetchScenarios,
  fetchSettings,
  fetchTrajectory,
  fetchVariantLineage,
  fetchWorkspaceScenario,
  GateSegment,
  GateTimeline,
  LidarDescriptor,
  lidarPayloadUrl,
  moveRecipeStep,
  POVFrame,
  POVImageFrame,
  LiveCapability,
  LiveState,
  PreviewResponse,
  previewVariant,
  RecipeDocument,
  RecipeStep,
  RecipeStepRequest,
  redoRecipe,
  removeRecipeStep,
  restoreRollbackMarker,
  ScenarioSummary,
  setRecipeStepActive,
  SettingsView,
  TimelineSample,
  TrajectoryResponse,
  undoRecipe,
  VariantLineage,
  WorkspaceScenario,
} from "./api";
import { Icon, IconName } from "./icons";

type ViewType = "top-down" | "third-person" | "in-car" | "lidar";
type View = { id: number; type: ViewType };
type Panel = "recipe" | "catalog" | "layers" | "comments";
type Flyout = "metrics" | "gates" | "provenance" | "artifacts";
type Tool = { icon: IconName; label: string; shortcut?: string; disabled?: boolean; onClick?: () => void; menu?: React.ReactNode };
type StatusLine = { label: string; available: boolean; note?: string };
type CameraPreset = "default" | "north-up" | "ego-up";
type Command = { label: string; group: string; icon: IconName; shortcut?: string; disabled?: boolean; run: () => void };

const viewLabels: Record<ViewType, string> = { "top-down": "Top-down", "third-person": "3rd-person POV", "in-car": "In-car POV", lidar: "LiDAR 3D" };
const DOCUMENT_TABS = ["Scenario studio", "Variant studio", "Replay", "Report"] as const;
const PANEL_DEFAULT_WIDTH = 270;
const PANEL_MIN_WIDTH = 180;
const PANEL_MAX_WIDTH = 520;
const PLAYHEAD_STEP_S = 0.05;
const LIDAR_SYNC_TOLERANCE_S = 0.25;
const CHANNELS = ["position", "heading", "speed", "acceleration", "braking"] as const;
const CHANNEL_LABELS: Record<(typeof CHANNELS)[number], string> = { position: "Position", heading: "Heading", speed: "Speed", acceleration: "Acceleration", braking: "Braking" };
const MISSING = "n/a";

type ChannelName = (typeof CHANNELS)[number];

function channelValue(sample: TimelineSample | undefined, channel: ChannelName): number | null {
  if (!sample) return null;
  if (channel === "position") return Math.hypot(sample.x_m, sample.y_m);
  if (channel === "heading") return sample.yaw_rad;
  if (channel === "speed") return sample.speed_mps;
  if (channel === "acceleration") return sample.acceleration_mps2;
  return sample.braking_pressure;
}

function nearestSample(samples: TimelineSample[], timeS: number): TimelineSample | undefined {
  return samples.reduce<TimelineSample | undefined>(
    (best, sample) => (best === undefined || Math.abs(sample.time_s - timeS) < Math.abs(best.time_s - timeS) ? sample : best),
    undefined,
  );
}

function formatChannelValue(channel: ChannelName, value: number | null): string {
  if (value === null) return MISSING;
  if (channel === "position") return `${value.toFixed(2)} m`;
  if (channel === "heading") return `${value.toFixed(3)} rad`;
  if (channel === "speed") return `${value.toFixed(2)} m/s`;
  if (channel === "acceleration") return `${value.toFixed(3)} m/s2`;
  return value.toFixed(3);
}

function formatTimestamp(timeS: number | undefined): string {
  return timeS === undefined ? MISSING : timeS.toFixed(2);
}

type ActiveTrack = { track: ActorTrack; sample: TimelineSample | undefined };

type Measurement =
  | { status: "measured"; fromActorId: string; toActorId: string; from: TimelineSample; to: TimelineSample; distance_m: number; bearing_rad: number; heading_delta_rad: number; time_offset_s: number }
  | { status: "unavailable"; reason: string };

const MEASURE_REASON_NO_TRACKS = "requires_at_least_two_actor_tracks";
const MEASURE_REASON_NO_SAMPLE = "actor_state_unavailable_at_playhead";

function measureAt(activeTracks: ActiveTrack[], selected: ActiveTrack | null): Measurement | null {
  if (activeTracks.length < 2) return { status: "unavailable", reason: MEASURE_REASON_NO_TRACKS };
  const from = selected ?? activeTracks[0];
  const to = activeTracks.find((entry) => entry.track.actor_id !== from.track.actor_id);
  if (from.sample === undefined || to?.sample === undefined) return { status: "unavailable", reason: MEASURE_REASON_NO_SAMPLE };
  const fromSample = from.sample;
  const toSample = to.sample;
  return {
    status: "measured",
    fromActorId: from.track.actor_id,
    toActorId: to.track.actor_id,
    from: fromSample,
    to: toSample,
    distance_m: Math.hypot(toSample.x_m - fromSample.x_m, toSample.y_m - fromSample.y_m),
    bearing_rad: Math.atan2(toSample.y_m - fromSample.y_m, toSample.x_m - fromSample.x_m),
    heading_delta_rad: Math.atan2(Math.sin(toSample.yaw_rad - fromSample.yaw_rad), Math.cos(toSample.yaw_rad - fromSample.yaw_rad)),
    time_offset_s: toSample.time_s - fromSample.time_s,
  };
}

function measureSummary(measurement: Measurement | null): string {
  if (!measurement) return MISSING;
  if (measurement.status === "unavailable") return `${MISSING} (${measurement.reason})`;
  return `${measurement.distance_m.toFixed(2)} m ${measurement.fromActorId} -> ${measurement.toActorId} at ${measurement.from.time_s.toFixed(2)} s`;
}

function App() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selected, setSelected] = useState<ScenarioSummary | null>(null);
  const [trajectory, setTrajectory] = useState<TrajectoryResponse | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceScenario | null>(null);
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
  const [maneuver, setManeuver] = useState({ actor_id: "ego", steering_angle_rad: 0, acceleration_mps2: 0, braking_mps2: 0, target_speed_mps: null as number | null, start_time_s: 0, end_time_s: null as number | null });
  const [stepName, setStepName] = useState("Constrained maneuver");
  const [recipe, setRecipe] = useState<RecipeDocument | null>(null);
  const [markerName, setMarkerName] = useState("Checkpoint");
  const [lineage, setLineage] = useState<VariantLineage | null>(null);
  const [evidence, setEvidence] = useState<EvidenceLayers | null>(null);
  const [compareAgainst, setCompareAgainst] = useState<string>("");
  const [compare, setCompare] = useState<ComparePayload | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [povFrames, setPovFrames] = useState<Record<string, POVFrame | null>>({});
  const [povImages, setPovImages] = useState<Record<string, POVImageFrame | null>>({});
  const [liveCapability, setLiveCapability] = useState<LiveCapability | null>(null);
  const [liveState, setLiveState] = useState<LiveState | null>(null);
  const [lidar, setLidar] = useState<LidarDescriptor | null>(null);
  const [lidarDecimation, setLidarDecimation] = useState(8);
  const [actorTimeline, setActorTimeline] = useState<ActorTimeline | null>(null);
  const [gateTimeline, setGateTimeline] = useState<GateTimeline | null>(null);
  const [selectedActor, setSelectedActor] = useState<string | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);

  const toolbarGroups: { label: string; tools: Tool[] }[] = [
    { label: "History", tools: [{ icon: "undo", label: "Undo", shortcut: "Ctrl+Z", disabled: !recipe?.history.undoable, onClick: () => runRecipe(undoRecipe) }, { icon: "redo", label: "Redo", shortcut: "Ctrl+Shift+Z", disabled: !recipe?.history.redoable, onClick: () => runRecipe(redoRecipe) }] },
    { label: "Import", tools: [{ icon: "import", label: "Import scene", shortcut: "I", onClick: () => openPanel("catalog") }, { icon: "export", label: "Export", onClick: exportSelected, disabled: !selected }] },
    { label: "Edit", tools: [{ icon: "cursor", label: "Select actors", shortcut: "S", onClick: () => setMode("select") }, { icon: "edit", label: "Edit motion", shortcut: "E", onClick: () => setMode("edit"), disabled: !selected }, { icon: "behavior", label: "Behavior mode", disabled: true }] },
    { label: "Check / Run", tools: [{ icon: "validate", label: "Validate", shortcut: "V", disabled: true }, { icon: "replay", label: "Replay", disabled: true }] },
    { label: "Inspect", tools: [{ icon: "measure", label: "Measure", shortcut: "M", onClick: () => setMode("measure") }, { icon: "compare", label: "Compare", shortcut: "C", onClick: () => setMode("compare"), disabled: !selected }] },
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
    fetchLiveCapability().then(setLiveCapability).catch(() => setLiveCapability(null));
    fetchSettings().then(setSettings).catch(() => setSettings(null));
  }, []);
  useEffect(() => {
    if (!selected) { setArtifacts(null); setLidar(null); return; }
    fetchScenarioArtifacts(selected.scenario_id).then((payload) => setArtifacts(payload.artifacts)).catch(() => setArtifacts(null));
    fetchLidarDescriptor(selected.scenario_id).then(setLidar).catch(() => setLidar({ available: false, unavailable_reason: "lidar_descriptor_request_failed" }));
  }, [selected?.scenario_id]);
  useEffect(() => {
    if (!selected || !workspace) return;
    (['third-person', 'in-car'] as const).forEach((mode) => {
      if (!workspace.layers[mode === 'in-car' ? 'in_car' : 'third_person'].available) return;
      fetchPOVFrame(selected.scenario_id, mode, timeline).then((frame) => setPovFrames((current) => ({ ...current, [mode]: frame }))).catch(() => setPovFrames((current) => ({ ...current, [mode]: null })));
      fetchPOVImageFrame(selected.scenario_id, mode, timeline).then((frame) => setPovImages((current) => ({ ...current, [mode]: frame }))).catch(() => setPovImages((current) => ({ ...current, [mode]: null })));
    });
  }, [selected?.scenario_id, workspace, timeline]);
  useEffect(() => {
    if (!selected) { setTrajectory(null); return; }
    Promise.all([fetchScenario(selected.scenario_id), fetchTrajectory(selected.scenario_id), fetchWorkspaceScenario(selected.scenario_id)])
      .then(([detail, paths, liveWorkspace]) => { setSelected(detail); setTrajectory(paths); setWorkspace(liveWorkspace); setTimeline(0); setError(null); })
      .catch((e) => setError(e.message));
  }, [selected?.scenario_id]);
  useEffect(() => {
    if (!selected) { setActorTimeline(null); setGateTimeline(null); setTimelineError(null); return; }
    let cancelled = false;
    setTimelineError(null);
    Promise.all([fetchActorTimeline(selected.scenario_id), fetchGateTimeline(selected.scenario_id)])
      .then(([tracks, gates]) => {
        if (cancelled) return;
        setActorTimeline(tracks);
        setGateTimeline(gates);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setActorTimeline(null);
        setGateTimeline(null);
        setTimelineError(e.message);
      });
    return () => { cancelled = true; };
  }, [selected?.scenario_id]);
  useEffect(() => {
    if (!selected) { setRecipe(null); setLineage(null); setEvidence(null); return; }
    fetchRecipe(selected.scenario_id).then(setRecipe).catch(() => setRecipe(null));
    fetchVariantLineage(selected.scenario_id).then(setLineage).catch(() => setLineage(null));
    fetchEvidenceLayers(selected.scenario_id).then(setEvidence).catch(() => setEvidence(null));
  }, [selected?.scenario_id]);
  useEffect(() => {
    if (scenarios.length === 0 || !selected) return;
    setCompareAgainst((current) => {
      if (current && current !== selected.scenario_id && scenarios.some((item) => item.scenario_id === current)) return current;
      const other = scenarios.find((item) => item.scenario_id !== selected.scenario_id);
      return other?.scenario_id ?? "";
    });
  }, [scenarios, selected?.scenario_id]);
  useEffect(() => {
    if (mode !== "compare") { setCompare(null); setCompareError(null); return; }
    if (!selected || !compareAgainst || compareAgainst === selected.scenario_id) return;
    let cancelled = false;
    fetchCompare(selected.scenario_id, compareAgainst, timeline)
      .then((payload) => { if (!cancelled) { setCompare(payload); setCompareError(null); } })
      .catch((e: Error) => { if (!cancelled) { setCompare(null); setCompareError(e.message); } });
    return () => { cancelled = true; };
  }, [mode, selected?.scenario_id, compareAgainst, timeline]);

  function selectPanel(next: Panel) { setFlyout(null); if (leftOpen && panel === next) { setLeftOpen(false); return; } setLeftOpen(true); setPanel(next); }
  function openPanel(next: Panel) { setFlyout(null); setLeftOpen(true); setPanel(next); }
  function openFlyout(next: Flyout) { setFlyout(flyout === next ? null : next); }
  function addView(type: ViewType) {
    if (views.length >= 4) return;
    setViews([...views, { id: nextViewId, type }]); setNextViewId(nextViewId + 1);
    setAddViewOpen(false);
  }
  function closeView(id: number) { setViews(views.filter((view) => view.id !== id)); if (maximized === id) setMaximized(null); }
  function makeMain(id: number) { setViews((current) => { const chosen = current.find((view) => view.id === id); return chosen ? [chosen, ...current.filter((view) => view.id !== id)] : current; }); }
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
  const recipeSteps = recipe?.steps ?? [];
  function runRecipe(action: (scenarioId: string) => Promise<RecipeDocument>) {
    if (!selected) return;
    action(selected.scenario_id).then(setRecipe).catch((e: Error) => setError(e.message));
  }
  function applyManeuver() {
    if (!selected) return;
    const request: RecipeStepRequest = {
      step_id: `step-${recipeSteps.length + 1}-${Math.round(maneuver.start_time_s * 1000)}`,
      name: stepName.trim() || `Maneuver ${recipeSteps.length + 1}`,
      kind: "constrained-maneuver",
      actor_edit: { speed_multiplier: 1, heading_offset_rad: 0, timing_offset_s: 0, initial_gap_delta_m: 0, ...maneuver },
      active: true,
    };
    addRecipeStep(selected.scenario_id, request)
      .then((document) => {
        setRecipe(document);
        return previewVariant(selected.scenario_id, {
          actor_edits: document.steps.filter((step) => step.active).map((step) => step.parameters),
          recipe_steps: document.steps.map((step) => ({ step_id: step.step_id, name: step.name, kind: step.kind, actor_edit: step.parameters, active: step.active })),
          behavior: "parameterized",
          seed: 0,
        });
      })
      .then(setPreview)
      .catch((e: Error) => setError(e.message));
  }

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

  const durationS = gateTimeline?.time_domain.end_s ?? actorTimeline?.time_domain.end_s ?? selected?.duration_s ?? 0;
  const playhead = Math.min(Math.max(timeline, 0), durationS || 0);
  const activeTracks = useMemo(
    () => (actorTimeline?.tracks ?? []).map((track) => ({ track, sample: nearestSample(track.samples, playhead) })),
    [actorTimeline, playhead],
  );
  const selectedTrack = activeTracks.find((entry) => entry.track.actor_id === selectedActor) ?? null;
  const measurement = useMemo(() => measureAt(activeTracks, selectedTrack), [activeTracks, selectedTrack]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && commandOpen) { setCommandOpen(false); return; }
      if (event.altKey && event.key.toLowerCase() === "c") { event.preventDefault(); setCommandOpen(true); return; }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setCommandOpen(true); return; }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        if (!selected) return;
        event.preventDefault();
        runRecipe(event.shiftKey ? redoRecipe : undoRecipe);
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.isContentEditable || /^(INPUT|SELECT|TEXTAREA)$/.test(target.tagName))) return;
      if (event.shiftKey && event.key.toLowerCase() === "v") { event.preventDefault(); setAddViewOpen(true); return; }
      const shortcut = event.key.toLowerCase();
      if (shortcut === "s") { event.preventDefault(); setMode("select"); return; }
      if (shortcut === "e") { if (selected) { event.preventDefault(); setMode("edit"); } return; }
      if (shortcut === "m") { event.preventDefault(); setMode("measure"); return; }
      if (shortcut === "v") { event.preventDefault(); openPanel("catalog"); return; }
      if (event.key === "Escape" && selectedActor !== null) { setSelectedActor(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [commandOpen, selected?.scenario_id, selectedActor]);

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
         {panel === "catalog" && <Catalog scenarios={scenarios} selected={selected} loading={loading} filter={catalogFilter} onFilter={setCatalogFilter} onSelect={setSelected} />}{panel === "recipe" && <RecipePanel recipe={recipe} preview={preview} markerName={markerName} onMarkerName={setMarkerName} onAddMarker={(name) => runRecipe((id) => addRollbackMarker(id, name))} onRestore={(markerId) => runRecipe((id) => restoreRollbackMarker(id, markerId))} onToggleStep={(stepId, active) => runRecipe((id) => setRecipeStepActive(id, stepId, active))} onRemoveStep={(stepId) => runRecipe((id) => removeRecipeStep(id, stepId))} onMoveStep={(stepId, direction) => runRecipe((id) => moveRecipeStep(id, stepId, direction))} onUndo={() => runRecipe(undoRecipe)} onRedo={() => runRecipe(redoRecipe)} />}{panel === "layers" && <EvidenceLayerPanel evidence={evidence} workspace={workspace} />}{panel === "comments" && <EmptyPanel title="Comments" copy="No comments in this document." />}
      </aside>
      <div className={`split-handle left${resizing ? " dragging" : ""}`} role="separator" aria-orientation="vertical" aria-label="Resize side panel" aria-valuenow={leftOpen ? panelWidth : 0} aria-valuemin={PANEL_MIN_WIDTH} aria-valuemax={PANEL_MAX_WIDTH} tabIndex={0} onPointerDown={startResize} onKeyDown={resizeByKeyboard} />
      <section className="view-manager" aria-label="View manager">
        <div className="view-manager-head"><div><span className="section-kicker">{activeTab.toUpperCase()}</span><strong>{selected?.scenario_id ?? "No scenario selected"}</strong></div><div className="mode-switcher" aria-label="Mode">{["select", "edit", "measure", "compare"].map((item) => <button key={item} className={mode === item ? "active" : ""} aria-pressed={mode === item} onClick={() => setMode(item)} disabled={item === "compare" && (!selected || scenarios.length < 2)} title={item === "compare" && scenarios.length < 2 ? "Compare needs two scenarios in the catalog" : undefined}>{item}</button>)}</div><button className="reset-button" onClick={resetLayout}>Reset layout</button></div>
        {error && <div className="inline-error" role="alert">{error}</div>}
         {mode === "compare"
          ? <CompareSurface payload={compare} error={compareError} selected={selected} scenarios={scenarios} against={compareAgainst} onAgainst={setCompareAgainst} playhead={playhead} />
           : activeTab === "Scenario studio"
           ? <div className={`view-grid count-${views.length}${maximized !== null ? " maximized" : ""}`}>
              {views.map((view) => <ViewPane key={view.id} view={view} selected={selected} workspace={workspace} frame={povFrames[view.type]} imageFrame={povImages[view.type]} liveState={liveState} liveCapability={liveCapability} lidar={lidar} lidarDecimation={lidarDecimation} onLidarDecimation={setLidarDecimation} trajectory={preview?.paths.length ? { ...trajectory!, paths: preview.paths } : trajectory} timeline={playhead} activeTracks={activeTracks} selectedActor={selectedActor} measurement={measurement} mode={mode} onSelectActor={setSelectedActor} preset={presets[view.id] ?? "default"} onPreset={(next) => setPresets({ ...presets, [view.id]: next })} hiddenKinds={hiddenKinds} onToggleKind={toggleKind} layersOpen={layersOpen === view.id} onToggleLayers={() => setLayersOpen(layersOpen === view.id ? null : view.id)} maximized={maximized === view.id} onToggleMaximize={() => setMaximized(maximized === view.id ? null : view.id)} onMakeMain={() => makeMain(view.id)} onClose={() => closeView(view.id)} />)}
            {views.length === 0 && <div className="empty-view"><strong>No views open.</strong><span>Add a view.</span><button onClick={() => addView("top-down")}>Add a Top-down view</button></div>}
          </div>
          : activeTab === "Variant studio"
          ? <VariantStudio selected={selected} lineage={lineage} evidence={evidence} workspace={workspace} />
          : <div className="view-grid count-1"><div className="empty-view"><strong>{activeTab}</strong><span>Not available in this build.</span><button onClick={() => setActiveTab("Scenario studio")}>Back to Scenario studio</button></div></div>}
        <TimelineSurface
          timeline={actorTimeline}
          gates={gateTimeline}
          error={timelineError}
          playhead={playhead}
          durationS={durationS}
          activeTracks={activeTracks}
          selectedActor={selectedActor}
          measurement={measurement}
          onSelectActor={setSelectedActor}
          onPlayhead={(value) => setTimeline(Math.min(Math.max(value, 0), durationS || 0))}
          onStep={(delta) => setTimeline(Math.min(Math.max(playhead + delta, 0), durationS || 0))}
        />
      </section>
       <aside className="right-rail" aria-label="Inspection navigation">
        <IconButton icon="metrics" label="Metrics" badge="0" active={flyout === "metrics"} onClick={() => openFlyout("metrics")} />
        <IconButton icon="gates" label="Gates" badge={String(gateTimeline?.gates.length ?? 0)} active={flyout === "gates"} onClick={() => openFlyout("gates")} />
        <IconButton icon="provenance" label="Provenance" active={flyout === "provenance"} onClick={() => openFlyout("provenance")} />
        <IconButton icon="artifacts" label="Artifacts" active={flyout === "artifacts"} onClick={() => openFlyout("artifacts")} />
        {flyout && <div className="flyout"><span className="section-kicker">{flyout}</span><p className="flyout-time">playhead {playhead.toFixed(2)} s of {durationS.toFixed(2)} s / frame {activeTracks.find((entry) => entry.track.role === "ego")?.sample?.time_s === undefined ? MISSING : formatTimestamp(activeTracks.find((entry) => entry.track.role === "ego")?.sample?.time_s)} s</p>{flyout === "metrics" && <><h2>Replay metrics</h2>{trajectory?.replay_metrics && Object.keys(trajectory.replay_metrics).length > 0 ? <div className="flyout-list">{Object.entries(trajectory.replay_metrics).map(([actor, metrics]) => <div className="flyout-row" key={actor}><strong>{actor}</strong><span>RMSE {metrics.position_rmse_m?.toFixed(3) ?? "n/a"} m</span><span>final {metrics.final_displacement_m?.toFixed(3) ?? "n/a"} m</span><span>{metrics.coverage_status ?? "recorded"}</span></div>)}</div> : <><p>No replay metrics for this scenario.</p><StatusBadge status="n/a" /></>}</>}
          {flyout === "gates" && <><h2>G1-G7 gates</h2>{gateTimeline ? <div className="flyout-list">{(gateTimeline.gates).map((gate) => <div className="flyout-row" key={gate.gate_id}><strong>{gate.gate_id}</strong><StatusBadge status={gate.status} />{gate.scientific_status === "PROVISIONAL" && <StatusBadge status="PROVISIONAL" />}<span>{gate.start_s.toFixed(2)}-{gate.end_s.toFixed(2)} s</span><span>{gate.reasons.join(", ") || "no reasons"}</span></div>)}</div> : <><p>No gate timeline for this scenario.</p><StatusBadge status="n/a" /></>}</>}
          {flyout === "provenance" && <><h2>Provenance</h2>{selected ? (Object.keys(selected.provenance ?? {}).length > 0 ? <div className="flyout-list">{Object.entries(selected.provenance).map(([key, value]) => <div className="flyout-row" key={key}><strong>{key}</strong><span>{value}</span></div>)}</div> : <p>This scenario records no provenance fields.</p>) : <p>Select an imported scenario first.</p>}</>}
          {flyout === "artifacts" && <><h2>Artifacts</h2>{selected ? (artifacts && artifacts.length > 0 ? <div className="flyout-list">{artifacts.map((artifact) => <a className="flyout-row link" key={artifact.path} href={apiUrl(`/artifacts/${artifact.path}`)} target="_blank" rel="noreferrer"><strong>{artifact.kind}</strong><span>{artifact.path}</span></a>)}</div> : <p>No artifacts reported for this scenario.</p>) : <p>Select an imported scenario first.</p>}</>}
        </div>}
       </aside>
        {mode === "edit" && <section className="maneuver-dock" aria-label="Constrained maneuver editor"><span className="section-kicker">MANEUVER STEP</span><h2>Constrained edit</h2><p>Tier 1: kinematic-open-loop-v1. Displacement and per-axis velocity are rejected, never rewritten.</p><label>Step name <input value={stepName} onChange={(e) => setStepName(e.target.value)} /></label><label>Actor<select value={maneuver.actor_id} onChange={(e) => setManeuver({ ...maneuver, actor_id: e.target.value })}>{workspace?.actors.map((actor) => <option key={actor.actor_id}>{actor.actor_id}</option>)}</select></label><label>Steering / heading <input type="number" step="0.01" value={maneuver.steering_angle_rad} onChange={(e) => setManeuver({ ...maneuver, steering_angle_rad: Number(e.target.value) })} /></label><label>Acceleration <input type="number" step="0.1" value={maneuver.acceleration_mps2} onChange={(e) => setManeuver({ ...maneuver, acceleration_mps2: Number(e.target.value) })} /></label><label>Braking <input type="number" step="0.1" min="0" value={maneuver.braking_mps2} onChange={(e) => setManeuver({ ...maneuver, braking_mps2: Number(e.target.value) })} /></label><label>Target speed <input type="number" step="0.1" min="0" value={maneuver.target_speed_mps ?? ""} onChange={(e) => setManeuver({ ...maneuver, target_speed_mps: e.target.value === "" ? null : Number(e.target.value) })} /></label><label>Time range start <input type="number" step="0.05" min="0" value={maneuver.start_time_s} onChange={(e) => setManeuver({ ...maneuver, start_time_s: Number(e.target.value) })} /></label><label>Time range end <input type="number" step="0.05" min="0" value={maneuver.end_time_s ?? ""} onChange={(e) => setManeuver({ ...maneuver, end_time_s: e.target.value === "" ? null : Number(e.target.value) })} /></label><button onClick={applyManeuver}>Add step and preview Tier 1</button>{preview && <><StatusBadge status={preview.status} /><small>Limits: {String(preview.limits?.max_acceleration_mps2)} m/s2 accel, {String(preview.limits?.max_deceleration_mps2)} m/s2 brake. Violations: {preview.violations.length}. Parent immutable.</small></>}</section>}
    </div>
    <footer className="document-footer"><div className="document-tabs">{DOCUMENT_TABS.map((tab) => <button className={activeTab === tab ? "active" : ""} key={tab} onClick={() => setActiveTab(tab)}>{tab}</button>)}</div><div className="status-bar"><span>selection: {selected?.scenario_id ?? "none"}</span><span>artifacts: {artifacts?.length ?? 0}</span><span>branch: {lineage?.branch?.branch_id ?? MISSING}</span><span>config hash: {lineage?.fields?.config_hash ? String(lineage.fields.config_hash).slice(0, 12) : MISSING}</span><span>rollback: {recipe ? recipe.active_marker_id ?? "none" : MISSING}</span><span>recipe: {recipe ? `${recipe.active_step_count}/${recipe.step_count} steps` : MISSING}</span><span>time: {playhead.toFixed(2)} s / {durationS.toFixed(2)} s</span><span>PROVISIONAL: {gateTimeline?.provisional_count ?? "n/a"}</span><span>POV: {povFrames["in-car"]?.simulator ?? povFrames["third-person"]?.simulator ?? MISSING}</span><span>frame: {selected?.coordinate_frame ?? MISSING}</span></div></footer>
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
function stepParameterSummary(step: RecipeStep): string {
  const edit = step.parameters;
  const parts = [
    `steer ${edit.steering_angle_rad ?? 0} rad`,
    `accel ${edit.acceleration_mps2 ?? "n/a"} m/s2`,
    `brake ${edit.braking_mps2 ?? "n/a"} m/s2`,
    `target ${edit.target_speed_mps ?? "n/a"} m/s`,
    `speed x${edit.speed_multiplier}`,
    `t=${edit.start_time_s ?? 0}-${edit.end_time_s ?? "end"} s`,
  ];
  return parts.join(" / ");
}

function RecipePanel({ recipe, preview, markerName, onMarkerName, onAddMarker, onRestore, onToggleStep, onRemoveStep, onMoveStep, onUndo, onRedo }: {
  recipe: RecipeDocument | null;
  preview: PreviewResponse | null;
  markerName: string;
  onMarkerName: (value: string) => void;
  onAddMarker: (name: string) => void;
  onRestore: (markerId: string) => void;
  onToggleStep: (stepId: string, active: boolean) => void;
  onRemoveStep: (stepId: string) => void;
  onMoveStep: (stepId: string, direction: "up" | "down") => void;
  onUndo: () => void;
  onRedo: () => void;
}) {
  const steps = recipe?.steps ?? [];
  return <div className="panel-content recipe-panel">
    <span className="section-kicker">RECIPE</span>
    <h2>Named steps</h2>
    {recipe && <p className="recipe-history" aria-label="Recipe history">
      <span>revision {recipe.history.revision}</span>
      <button type="button" onClick={onUndo} disabled={!recipe.history.undoable} title={recipe.history.undoable ? "Undo the last recipe change" : recipe.history.undo_unavailable_reason ?? "Nothing to undo"}>Undo</button>
      <button type="button" onClick={onRedo} disabled={!recipe.history.redoable} title={recipe.history.redoable ? "Redo the last undone change" : recipe.history.redo_unavailable_reason ?? "Nothing to redo"}>Redo</button>
      <small>non-destructive / {recipe.mutation}</small>
    </p>}
    {recipe && !recipe.persistence.available && <p className="recipe-persistence" role="note"><StatusBadge status="unavailable" />{recipe.persistence.unavailable_reason}</p>}
    {steps.length === 0
      ? <p>Import a scene and add a constrained maneuver step.</p>
      : <ol className="recipe-list" aria-label="Ordered recipe steps">{steps.map((step) => <li className={`recipe-row ${step.active ? "" : "inactive"}`} key={step.step_id}>
        <strong>{step.index + 1}. {step.name}</strong>
        <StatusBadge status={step.status} />
        {step.active ? <StatusBadge status="active" /> : <StatusBadge status="inactive" />}
        <small>{step.parameters.actor_id} / {stepParameterSummary(step)}</small>
        {!step.active && step.inactive_reason && <small>inactive because {step.inactive_reason}</small>}
        {step.error && <small role="alert">API error: {step.error}</small>}
        {step.artifact ? <a className="recipe-artifact" href={step.artifact.url}>{step.artifact.kind}: {step.artifact.path}</a> : step.artifact_unavailable_reason && <small>artifact: {step.artifact_unavailable_reason}</small>}
        {step.violations.map((violation) => <small key={violation.code} role="alert">{violation.code}: observed {violation.observed} against limit {violation.limit} ({violation.provenance})</small>)}
        <span className="recipe-row-actions">
          <button type="button" aria-label={`Move ${step.name} up`} disabled={step.index === 0} onClick={() => onMoveStep(step.step_id, "up")}>up</button>
          <button type="button" aria-label={`Move ${step.name} down`} disabled={step.index === steps.length - 1} onClick={() => onMoveStep(step.step_id, "down")}>down</button>
          <button type="button" aria-pressed={step.active} onClick={() => onToggleStep(step.step_id, !step.active)}>{step.active ? "deactivate" : "activate"}</button>
          <button type="button" aria-label={`Remove ${step.name}`} onClick={() => onRemoveStep(step.step_id)}>remove</button>
        </span>
      </li>)}</ol>}
    <h3>Rollback markers</h3>
    {recipe && recipe.rollback_markers.length > 0 ? <ul className="marker-list" aria-label="Rollback markers">{recipe.rollback_markers.map((marker) => <li key={marker.marker_id}>
      <strong>{marker.name}</strong>
      <small>after {marker.step_count} steps / revision {marker.revision}{recipe.active_marker_id === marker.marker_id ? " / active" : ""}</small>
      <button type="button" aria-label={`Restore ${marker.name}`} onClick={() => onRestore(marker.marker_id)}>roll back</button>
    </li>)}</ul> : <p>No rollback markers. Add one before a risky step.</p>}
    <label>Marker name <input value={markerName} onChange={(event) => onMarkerName(event.target.value)} /></label>
    <button type="button" disabled={!recipe} onClick={() => onAddMarker(markerName)}>Add rollback marker</button>
    {preview && <><h3>Last preview</h3><small>Tier 1 {String(preview.provenance.simulator_version ?? "")}; rollback marker: {preview.rollback_marker ? "available" : "n/a"}</small></>}
  </div>;
}

function EvidenceLayerList({ evidence, title }: { evidence: EvidenceLayers | null; title: string }) {
  return <div className="evidence-panel">
    <h3>{title}</h3>
    {!evidence && <p><StatusBadge status="unavailable" />evidence layers were not returned by the API</p>}
    {evidence && <ul className="evidence-list" aria-label="Evidence layers">{evidence.layers.map((layer) => <EvidenceLayerRow key={layer.layer} layer={layer} />)}</ul>}
  </div>;
}

function EvidenceLayerRow({ layer }: { layer: EvidenceLayer }) {
  const fallback = layer.parent_fallback;
  return <li className={`evidence-row ${layer.layer} ${layer.status}`}>
    <strong>{layer.layer}</strong>
    <StatusBadge status={layer.status} />
    <small>{layer.source}</small>
    {!layer.unavailable_reason ? null : <small>reason: {layer.unavailable_reason}</small>}
    {layer.coverage === null ? null : <small>coverage {(layer.coverage * 100).toFixed(0)}%</small>}
    {fallback ? <small>parent sweep fallback: {String(fallback.available) === "true" ? "available" : `unavailable (${String(fallback.unavailable_reason)})`} - {String(fallback.note)}</small> : null}
  </li>;
}

function EvidenceLayerPanel({ evidence, workspace }: { evidence: EvidenceLayers | null; workspace: WorkspaceScenario | null }) {
  const metricProvenance = workspace?.metrics;
  return <div className="panel-content">
    <span className="section-kicker">MAP LAYERS</span>
    <h2>Evidence layers</h2>
    <EvidenceLayerList evidence={evidence ?? workspace?.evidence_layers ?? null} title="Trajectory and sensor layers" />
    {workspace?.sensor_status && <div className="evidence-metrics" aria-label="Variant sensor status">
      <h3>Variant sensor status</h3>
      <StatusBadge status={workspace.sensor_status.status} />
      <small>{workspace.sensor_status.unavailable_reason ?? "post-edit sensor frames available"}</small>
      <small>parent sweep: {workspace.sensor_status.parent_sweep.available ? "available" : `unavailable (${workspace.sensor_status.parent_sweep.unavailable_reason})`}</small>
    </div>}
    {metricProvenance && <div className="evidence-metrics">
      <h3>Metric provenance</h3>
      <StatusBadge status={metricProvenance.available ? "available" : "unavailable"} />
      <StatusBadge status={metricProvenance.scientific_status} />
      <small>{metricProvenance.available ? `source ${metricProvenance.source}` : metricProvenance.unavailable_reason}</small>
      {Object.entries(metricProvenance.provenance).map(([key, value]) => <small key={key}>{key}: {value}</small>)}
    </div>}
  </div>;
}

function VariantStudio({ selected, lineage, evidence, workspace }: { selected: ScenarioSummary | null; lineage: VariantLineage | null; evidence: EvidenceLayers | null; workspace: WorkspaceScenario | null }) {
  if (!selected) return <div className="view-grid count-1"><div className="empty-view"><strong>Variant studio</strong><span>Select an imported scenario to see its lineage.</span></div></div>;
  const field = (name: string) => {
    const value = lineage?.fields?.[name];
    const reason = lineage?.unavailable_reasons?.[name];
    return <div className="flyout-row" key={name}><strong>{name}</strong><span>{value === null || value === undefined ? MISSING : typeof value === "object" ? JSON.stringify(value) : String(value)}</span>{reason ? <span>{reason}</span> : null}</div>;
  };
  return <div className="variant-studio" role="region" aria-label="Variant studio">
    <div className="variant-lineage">
      <span className="section-kicker">LINEAGE</span>
      {lineage ? <>
        <p>branch {lineage.branch.branch_id} / root {lineage.branch.root_scenario_id} / depth {lineage.lineage_depth}</p>
        <ol aria-label="Variant lineage path">{lineage.lineage_path.map((node) => <li key={node.scenario_id}>{node.scenario_id} <StatusBadge status={node.present ? "available" : "unavailable"} />{node.unavailable_reason ? <small>{node.unavailable_reason}</small> : null}</li>)}</ol>
        {["branch_name", "parent_scenario_id", "seed", "config_hash", "run_id", "variant_configuration", "dataset_version", "generator_version", "transform_version", "source_scene_token"].map(field)}
        {lineage.child_scenario_ids.length > 0 && <p>children: {lineage.child_scenario_ids.join(", ")}</p>}
      </> : <p><StatusBadge status="unavailable" />lineage was not returned by the API</p>}
    </div>
    <div className="variant-layers">
      <EvidenceLayerList evidence={evidence ?? workspace?.evidence_layers ?? null} title="Evidence layers" />
    </div>
  </div>;
}

function CompareSide({ side, label, playhead }: { side: ComparePayload["sides"][number]; label: string; playhead: number }) {
  return <article className="compare-side" aria-label={`${label} side of the comparison`}>
    <header><strong>{side.scenario_id}</strong><span>{side.artifact_type}</span><StatusBadge status={side.branch_name ? "available" : "unsupported"} /></header>
    <dl>
      <dt>branch</dt><dd>{side.branch_id}{side.branch_name ? ` (${side.branch_name})` : " (name n/a)"}</dd>
      <dt>seed</dt><dd>{side.seed ?? MISSING}</dd>
      <dt>config hash</dt><dd>{side.config_hash ?? MISSING}</dd>
      <dt>frame</dt><dd>{side.coordinate_frame}</dd>
      <dt>duration</dt><dd>{side.duration_s.toFixed(2)} s</dd>
      <dt>layers</dt><dd>{side.layer_kinds.length > 0 ? side.layer_kinds.join(", ") : "none available"}</dd>
    </dl>
    <ul className="compare-side-layers" aria-label={`${label} evidence layers`}>{side.evidence_layers.map((layer) => <li key={layer.layer}><strong>{layer.layer}</strong> <StatusBadge status={layer.status} />{layer.unavailable_reason ? <small>{layer.unavailable_reason}</small> : null}</li>)}</ul>
    <small>playhead t={playhead.toFixed(2)} s</small>
  </article>;
}

function CompareSurface({ payload, error, selected, scenarios, against, onAgainst, playhead }: { payload: ComparePayload | null; error: string | null; selected: ScenarioSummary | null; scenarios: ScenarioSummary[]; against: string; onAgainst: (value: string) => void; playhead: number }) {
  const candidates = scenarios.filter((item) => item.scenario_id !== selected?.scenario_id);
  if (!selected) return <div className="view-grid count-1"><div className="empty-view"><strong>Compare</strong><span>Select a scenario to compare.</span></div></div>;
  return <section className="compare-surface" aria-label="Compare mode">
    <div className="compare-controls">
      <label>Left <input readOnly value={selected.scenario_id} aria-label="Left scenario" /></label>
      <label>Right <select aria-label="Right scenario" value={against} onChange={(event) => onAgainst(event.target.value)}>{candidates.length === 0 ? <option value="">no second scenario</option> : candidates.map((item) => <option key={item.scenario_id} value={item.scenario_id}>{item.scenario_id}</option>)}</select></label>
      <small>{payload ? `synchronized on ${payload.synchronization.mode} t=${payload.synchronization.time_s.toFixed(2)} s over 0.00-${payload.synchronization.time_domain.end_s.toFixed(2)} s` : "comparison payload not loaded"}</small>
    </div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {!payload && !error && <p>Comparison is loading.</p>}
    {payload && <>
      <div className="compare-sides">{payload.sides.map((side, index) => <CompareSide key={side.scenario_id} side={side} label={index === 0 ? "left" : "right"} playhead={playhead} />)}</div>
      {payload.synchronization.durations_differ && <p className="compare-note" role="note">{payload.synchronization.duration_unavailable_reason}</p>}
      <h3>Actor deltas at t={payload.synchronization.time_s.toFixed(2)} s</h3>
      <ul className="compare-actors" aria-label="Actor deltas">{payload.actors.map((actor) => <li key={actor.actor_id}>
        <strong>{actor.actor_id}</strong>
        <span>left {actor.left.status === "measured" ? `${actor.left.x_m?.toFixed(2)}, ${actor.left.y_m?.toFixed(2)} m` : MISSING}</span>
        <span>right {actor.right.status === "measured" ? `${actor.right.x_m?.toFixed(2)}, ${actor.right.y_m?.toFixed(2)} m` : MISSING}</span>
        <span>{actor.delta_unavailable_reason ? `${MISSING} (${actor.delta_unavailable_reason})` : `dpos ${actor.position_delta_m?.toFixed(3)} m / dyaw ${actor.heading_delta_rad?.toFixed(4)} rad / dspeed ${actor.speed_delta_mps?.toFixed(3)} m/s`}</span>
      </li>)}</ul>
      <h3>Metric comparison <StatusBadge status={payload.metric_scientific_status} /></h3>
      <ul className="compare-metrics" aria-label="Metric comparison">{payload.metrics.map((row) => <li key={row.metric}>
        <strong>{row.metric}</strong>
        <span>left {row.left_value === null ? MISSING : row.left_value.toFixed(3)} {row.unit}</span>
        <StatusBadge status={row.left_status} />
        <span>right {row.right_value === null ? MISSING : row.right_value.toFixed(3)} {row.unit}</span>
        <StatusBadge status={row.right_status} />
        <span>{row.delta === null ? `${MISSING} (${row.delta_unavailable_reason})` : `delta ${row.delta.toFixed(3)} ${row.unit}`}</span>
      </li>)}</ul>
      <h3>Gate comparison</h3>
      <ul className="compare-gates" aria-label="Gate comparison">{payload.gates.map((gate) => <li key={gate.gate_id}>
        <strong>{gate.gate_id}</strong>
        <StatusBadge status={gate.left_status ?? "unavailable"} />
        <span>vs</span>
        <StatusBadge status={gate.right_status ?? "unavailable"} />
        <StatusBadge status={gate.differs ? "fail" : "pass"} />
        {gate.left_scientific_status ? <StatusBadge status={gate.left_scientific_status} /> : null}
        {gate.right_scientific_status ? <StatusBadge status={gate.right_scientific_status} /> : null}
        <small>{[...gate.left_reasons, ...gate.right_reasons].join(", ") || "no reasons"}</small>
      </li>)}</ul>
    </>}
  </section>;
}
function Catalog({ scenarios, selected, loading, filter, onFilter, onSelect }: { scenarios: ScenarioSummary[]; selected: ScenarioSummary | null; loading: boolean; filter: string; onFilter: (value: string) => void; onSelect: (scenario: ScenarioSummary) => void }) { const visible = scenarios.filter((scenario) => scenario.scenario_id.toLowerCase().includes(filter.toLowerCase())); return <div className="panel-content"><div className="panel-title"><span className="section-kicker">CATALOG</span><span className="count">{visible.length}/{scenarios.length}</span></div><input className="filter" value={filter} onChange={(event) => onFilter(event.target.value)} placeholder="Filter scenarios" aria-label="Filter scenarios" />{loading ? <div className="skeleton-list"><i /><i /><i /></div> : scenarios.length === 0 ? <div className="panel-empty">Import a scene to start a scenario.</div> : visible.length === 0 ? <div className="panel-empty">No scenarios match this filter.</div> : <div className="scenario-list">{visible.map((scenario) => <button className={selected?.scenario_id === scenario.scenario_id ? "selected" : ""} key={scenario.scenario_id} onClick={() => onSelect(scenario)}><span><strong>{scenario.scenario_id}</strong><small>{scenario.artifact_type} / {scenario.duration_s.toFixed(2)} s</small></span><em>:</em></button>)}</div>}</div>; }
function AddViewMenu({ viewCount, onAdd }: { viewCount: number; onAdd: (type: ViewType) => void }) { const atLimit = viewCount >= 4; return <div className="add-view-menu" role="menu"><button disabled={atLimit} onClick={() => onAdd("top-down")}><strong>Top-down</strong><small>{atLimit ? "maximum 4 views reached" : "available"}</small></button><button disabled={atLimit} onClick={() => onAdd("third-person")}><strong>3rd-person POV</strong><small>simulator capability determines availability</small></button><button disabled={atLimit} onClick={() => onAdd("in-car")}><strong>In-car POV</strong><small>simulator capability determines availability</small></button><button disabled={atLimit} onClick={() => onAdd("lidar")}><strong>LiDAR 3D</strong><small>recorded payload capability determines availability</small></button></div>; }
function ViewPane({ view, selected, workspace, frame, imageFrame, liveState, liveCapability, lidar, lidarDecimation, onLidarDecimation, trajectory, timeline, activeTracks, selectedActor, measurement, mode, onSelectActor, preset, onPreset, hiddenKinds, onToggleKind, layersOpen, onToggleLayers, maximized, onToggleMaximize, onMakeMain, onClose }: { view: View; selected: ScenarioSummary | null; workspace: WorkspaceScenario | null; frame?: POVFrame | null; imageFrame?: POVImageFrame | null; liveState: LiveState | null; liveCapability: LiveCapability | null; lidar: LidarDescriptor | null; lidarDecimation: number; onLidarDecimation: (value: number) => void; trajectory: TrajectoryResponse | null; timeline: number; activeTracks: ActiveTrack[]; selectedActor: string | null; measurement: Measurement | null; mode: string; onSelectActor: (actorId: string) => void; preset: CameraPreset; onPreset: (next: CameraPreset) => void; hiddenKinds: string[]; onToggleKind: (kind: string) => void; layersOpen: boolean; onToggleLayers: () => void; maximized: boolean; onToggleMaximize: () => void; onMakeMain: () => void; onClose: () => void }) {
  const kinds = trajectory ? Array.from(new Set(trajectory.paths.map((path) => path.path_kind))) : [];
  return <article className={`view-pane${maximized ? " maximized" : ""}`}>
    <header>
      <span className="view-icon"><Icon name={view.type} /></span><strong>{viewLabels[view.type]}</strong><span className="view-target">{selected ? ` - ${selected.scenario_id}` : " - empty"}</span>
       <select aria-label="Camera preset" value={preset} onChange={(event) => onPreset(event.target.value as CameraPreset)}><option value="default">Auto-fit</option><option value="north-up">North-up</option><option value="ego-up">Ego-up</option></select>
      <div className="layers-control"><button className={`view-action${layersOpen ? " active" : ""}`} aria-expanded={layersOpen} onClick={onToggleLayers}>Layers</button>{layersOpen && <div className="layers-menu" role="menu">{kinds.length === 0 ? <p>No trajectory layers loaded.</p> : kinds.map((kind) => <button key={kind} role="menuitemcheckbox" aria-checked={!hiddenKinds.includes(kind)} onClick={() => onToggleKind(kind)}><span className={`status-dot ${hiddenKinds.includes(kind) ? "off" : "on"}`} />{kind}</button>)}</div>}</div>
       <button className="view-action" onClick={onMakeMain}>Make main</button><button className={`view-action${maximized ? " active" : ""}`} onClick={onToggleMaximize}>{maximized ? "Restore" : "Maximize"}</button>
      <button className="close-view" aria-label={`Close view: ${viewLabels[view.type]}`} title={`Close view: ${viewLabels[view.type]}`} onClick={onClose}>x</button>
    </header>
         {view.type === "top-down" ? <TopDownView selected={selected} workspace={workspace} trajectory={trajectory} timeline={timeline} activeTracks={activeTracks} selectedActor={selectedActor} measurement={measurement} mode={mode} onSelectActor={onSelectActor} preset={preset} hiddenKinds={hiddenKinds} /> : view.type === "lidar" ? <LidarView descriptor={lidar} decimation={lidarDecimation} onDecimation={onLidarDecimation} playhead={timeline} /> : liveState?.status === "running" || liveState?.status === "paused" ? <LivePOVView state={liveState} playhead={timeline} /> : frame ? <POVView frame={frame} imageFrame={imageFrame} playhead={timeline} /> : <div className="unavailable-view"><StatusBadge status={workspace?.layers[view.type === "in-car" ? "in_car" : "third_person"]?.available ? "loading" : "unavailable"} /><strong>{viewLabels[view.type]} {workspace?.layers[view.type === "in-car" ? "in_car" : "third_person"]?.available ? "loading" : "unavailable"}</strong><p>{liveCapability?.unavailable_reason ?? workspace?.layers[view.type === "in-car" ? "in_car" : "third_person"]?.unavailable_reason ?? "Select an imported scenario to query capability."}</p></div>}
  </article>;
}

function LivePOVView({ state, playhead }: { state: LiveState; playhead: number }) {
  return <div className="pov-view live-pov" role="img" aria-label={`Live esmini state at ${state.simulation_time_s.toFixed(2)} seconds for playhead ${playhead.toFixed(2)} seconds`}>
    <div className="pov-horizon" /><div className="pov-road" />
    {state.objects.map((object) => <span key={object.id} className="pov-actor live-actor" style={{ left: `${50 + object.x_m * 2}%`, top: `${58 - object.y_m * 2}%` }} title={`${object.id} native esmini state`} />)}
    <div className="view-legend"><span>native esminiLib state</span><span>browser-native renderer</span><span>t={state.simulation_time_s.toFixed(2)} s</span><span>no screenshot stream</span></div>
  </div>;
}

function LidarView({ descriptor, decimation, onDecimation, playhead }: { descriptor: LidarDescriptor | null; decimation: number; onDecimation: (value: number) => void; playhead: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "partial" | "error">("loading");
  const [metadata, setMetadata] = useState<LidarDescriptor | null>(null);
  useEffect(() => {
    if (!descriptor?.available || !descriptor.sample_data_token) { setStatus(descriptor ? "error" : "loading"); return; }
    let cancelled = false;
    setStatus("loading");
    fetch(lidarPayloadUrl(descriptor.sample_data_token, decimation)).then(async (response) => {
      if (!response.ok) throw new Error(`lidar_payload_${response.status}`);
      const header = response.headers.get("X-R2S-Lidar-Metadata");
      const next = header ? JSON.parse(header) as LidarDescriptor : descriptor;
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (cancelled) return;
      setMetadata(next);
      setStatus(next.returned_count && next.total_count && next.returned_count < next.total_count ? "partial" : "ready");
      const canvas = canvasRef.current; const context = canvas?.getContext("2d");
      if (!canvas || !context) return;
      canvas.width = canvas.clientWidth * devicePixelRatio; canvas.height = canvas.clientHeight * devicePixelRatio; context.scale(devicePixelRatio, devicePixelRatio);
      context.fillStyle = "#111923"; context.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
      context.fillStyle = "#8fd3ff";
      const points = new DataView(bytes.buffer); const count = Math.floor(bytes.byteLength / 16);
      const calibration = next.calibration_transform; const pose = next.ego_pose_transform;
      const rotate = (value: number[], quaternion: number[]) => { const [x, y, z] = value; const [w, qx, qy, qz] = quaternion; const tx = 2 * (qy * z - qz * y); const ty = 2 * (qz * x - qx * z); const tz = 2 * (qx * y - qy * x); return [x + w * tx + qy * tz - qz * ty, y + w * ty + qz * tx - qx * tz, z + w * tz + qx * ty - qy * tx]; };
      const transform = (value: number[], item: { translation_m: number[]; rotation_wxyz: number[] } | undefined) => item ? rotate(value, item.rotation_wxyz).map((part, index) => part + item.translation_m[index]) : value;
      for (let index = 0; index < count; index += 1) { const raw = [points.getFloat32(index * 16, true), points.getFloat32(index * 16 + 4, true), points.getFloat32(index * 16 + 8, true)]; const global = transform(transform(raw, calibration), pose); const px = canvas.clientWidth / 2 + global[0] * 7; const py = canvas.clientHeight / 2 - global[1] * 7; if (px >= 0 && py >= 0 && px < canvas.clientWidth && py < canvas.clientHeight) context.fillRect(px, py, 1.5, 1.5); }
    }).catch(() => { if (!cancelled) setStatus("error"); });
    return () => { cancelled = true; };
  }, [descriptor, decimation]);
  if (!descriptor) return <div className="unavailable-view"><StatusBadge status="loading" /><strong>LiDAR loading</strong><p>Resolving the recorded LIDAR_TOP sweep.</p></div>;
  if (!descriptor.available) return <div className="unavailable-view"><StatusBadge status="unavailable" /><strong>LiDAR unavailable</strong><p>{descriptor.unavailable_reason}</p></div>;
  const sweepTime = metadata?.timestamp_us === undefined ? undefined : metadata.timestamp_us / 1e6;
  const delta = sweepTime === undefined ? undefined : Math.abs(sweepTime - playhead);
  return <div className="lidar-view"><canvas ref={canvasRef} role="img" aria-label={`Recorded LIDAR_TOP point cloud for sweep at ${formatTimestamp(sweepTime)} seconds, playhead at ${playhead.toFixed(2)} seconds`} /><div className="lidar-controls"><label>decimation <select value={decimation} onChange={(event) => onDecimation(Number(event.target.value))}><option value="1">1x</option><option value="4">4x</option><option value="8">8x</option><option value="16">16x</option><option value="32">32x</option></select></label><StatusBadge status={status === "partial" ? "partial" : status === "ready" ? "valid" : status} /><span>{metadata?.returned_count ?? "n/a"}/{metadata?.total_count ?? "n/a"} points</span><span>playhead t={playhead.toFixed(2)} s</span><span>sweep t={formatTimestamp(sweepTime)} s</span><span>{delta === undefined ? MISSING : delta <= LIDAR_SYNC_TOLERANCE_S ? "synchronized" : `sweep_not_at_playhead ${(delta).toFixed(2)} s`}</span><span>{metadata?.frame ?? "sensor"} / {metadata?.transform_version ?? "n/a"}</span></div></div>;
}

function POVView({ frame, imageFrame, playhead }: { frame: POVFrame; imageFrame?: POVImageFrame | null; playhead: number }) {
  const camera = frame.camera_transform;
  const delta = Math.abs(frame.timestamp_s - playhead);
  return <div className="pov-view" role="img" aria-label={`${frame.mode} simulator frame at ${frame.timestamp_s.toFixed(2)} seconds for playhead ${playhead.toFixed(2)} seconds`}>{imageFrame?.status === "rendered" && imageFrame.artifact ? <img className="pov-artifact" src={apiUrl(`/artifacts/${imageFrame.artifact.path}`)} alt={`${frame.mode} esmini image frame at ${imageFrame.timestamp_s?.toFixed(2)} seconds`} /> : <><div className="pov-horizon" /><div className="pov-road" />{frame.actors.map((actor) => <span key={actor.actor_id} className={`pov-actor${actor.actor_id === "ego" ? " ego" : ""}`} style={{ left: `${50 + ((actor.transform.x_m - Number(camera.x_m)) * 2)}%`, top: `${58 - ((actor.transform.y_m - Number(camera.y_m)) * 2)}%` }} title={`${actor.actor_id} ${actor.actor_type}`} />)}</>}<div className="view-legend"><span>{imageFrame?.status === "rendered" ? "esmini-image-artifact" : frame.simulator}</span><span>{frame.mode}</span><span>playhead t={playhead.toFixed(2)} s</span><span>frame t={imageFrame?.timestamp_s?.toFixed(2) ?? frame.timestamp_s.toFixed(2)} s</span><span>{delta <= 0.001 ? "at playhead" : `nearest frame +${delta.toFixed(2)} s`}</span><span>{imageFrame?.frame_id ?? frame.frame_id}</span></div></div>;
}

function TopDownView({ selected, workspace, trajectory, timeline, activeTracks, selectedActor, measurement, mode, onSelectActor, preset, hiddenKinds }: { selected: ScenarioSummary | null; workspace: WorkspaceScenario | null; trajectory: TrajectoryResponse | null; timeline: number; activeTracks: ActiveTrack[]; selectedActor: string | null; measurement: Measurement | null; mode: string; onSelectActor: (actorId: string) => void; preset: CameraPreset; hiddenKinds: string[] }) {
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
   const mapLines = Object.values(workspace?.native_map?.layers ?? {}).flatMap((records) => records.flatMap((record) => Array.isArray(record.geometry) ? [record.geometry as [number, number][]] : []));
   return <div className="top-down">
     <svg viewBox="0 0 100 100" role="img" aria-label={`Top-down trajectory view at ${timeline.toFixed(2)} seconds, camera preset ${preset}`}><g transform={`rotate(${rotation} 50 50)`}>{mapLines.map((line, index) => <polyline key={`map-${index}`} className="native-map-line" points={line.map(([x, y]) => point(x, y)).join(" ")} />)}{paths.map((path) => <polyline key={path.actor_id} className={path.path_kind} points={path.states.map((state) => point(state.x_m, state.y_m)).join(" ")} />)}{mode === "measure" && measurement?.status === "measured" && <line className="measure-line" x1={point(measurement.from.x_m, measurement.from.y_m).split(",")[0]} y1={point(measurement.from.x_m, measurement.from.y_m).split(",")[1]} x2={point(measurement.to.x_m, measurement.to.y_m).split(",")[0]} y2={point(measurement.to.x_m, measurement.to.y_m).split(",")[1]} />}{activeTracks.length === 0 && paths.map((path) => { const state = nearestSample(path.states.map((item) => ({ ...item, acceleration_mps2: null, acceleration_source: null, braking_pressure: null, braking_source: null })), timeline); return state === undefined ? null : <circle key={`fallback-${path.actor_id}`} className="actor-state" cx={point(state.x_m, state.y_m).split(",")[0]} cy={point(state.x_m, state.y_m).split(",")[1]} r="1.2" />; })}{activeTracks.map(({ track, sample }) => sample === undefined ? null : <g key={track.actor_id} className={selectedActor === track.actor_id ? "actor-marker selected" : "actor-marker"} onClick={() => onSelectActor(track.actor_id)}><line className="actor-heading" x1={point(sample.x_m, sample.y_m).split(",")[0]} y1={point(sample.x_m, sample.y_m).split(",")[1]} x2={point(sample.x_m + Math.cos(sample.yaw_rad) * 6, sample.y_m + Math.sin(sample.yaw_rad) * 6).split(",")[0]} y2={point(sample.x_m + Math.cos(sample.yaw_rad) * 6, sample.y_m + Math.sin(sample.yaw_rad) * 6).split(",")[1]} /><circle cx={point(sample.x_m, sample.y_m).split(",")[0]} cy={point(sample.x_m, sample.y_m).split(",")[1]} r={track.role === "ego" ? 1.5 : 1.2}><title>{`${track.actor_id} at ${sample.time_s.toFixed(2)} s: speed ${formatChannelValue("speed", sample.speed_mps)}, acceleration ${formatChannelValue("acceleration", sample.acceleration_mps2)}, braking ${formatChannelValue("braking", sample.braking_pressure)}`}</title></circle></g>)}</g></svg>
    <div className="view-legend"><span><i className="recorded-line" /> recorded</span><span><i className="generated-line" /> generated</span><span><i className="replayed-line" /> replayed</span><span><i className="sensor-line" /> sensor-evidence</span><span>playhead t={timeline.toFixed(2)} s</span>{mode === "measure" && <span>measure: {measurement ? measureSummary(measurement) : "n/a"}</span>}</div>
  </div>;
}

function TimelineSurface({ timeline, gates, error, playhead, durationS, activeTracks, selectedActor, measurement, onSelectActor, onPlayhead, onStep }: { timeline: ActorTimeline | null; gates: GateTimeline | null; error: string | null; playhead: number; durationS: number; activeTracks: ActiveTrack[]; selectedActor: string | null; measurement: Measurement | null; onSelectActor: (actorId: string) => void; onPlayhead: (value: number) => void; onStep: (delta: number) => void }) {
  const domainStart = gates?.time_domain.start_s ?? timeline?.time_domain.start_s ?? 0;
  const domainEnd = gates?.time_domain.end_s ?? timeline?.time_domain.end_s ?? durationS;
  const span = Math.max(domainEnd - domainStart, 1e-6);
  const at = (timeS: number) => Math.min(100, Math.max(0, ((timeS - domainStart) / span) * 100));
  const polyline = (track: ActorTrack, channel: ChannelName) => track.samples
    .map((sample) => {
      const value = channelValue(sample, channel);
       return value === null ? null : `${at(sample.time_s)},${50 - Math.max(-1, Math.min(1, value / Math.max(1e-6, channelCeiling(track, channel)))) * 45}`;
    })
    .reduce<string[]>((segments, point, index, points) => {
      if (point === null) { if (segments.length) segments.push(""); return segments; }
      if (index > 0 && points[index - 1] === null && segments.length) segments.push("");
      segments.push(point);
      return segments;
    }, [])
    .filter((segment) => segment !== "");
  return <section className="timeline-surface" aria-label="Time-indexed actor timeline and gate lane">
    <div className="timeline-controls">
      <strong>playhead {playhead.toFixed(2)} s</strong>
      <span>of {durationS.toFixed(2)} s</span>
      <button className="playhead-step" aria-label="Step playhead back" onClick={() => onStep(-PLAYHEAD_STEP_S)} disabled={durationS === 0}>&lt;</button>
      <button className="playhead-step" aria-label="Step playhead forward" onClick={() => onStep(PLAYHEAD_STEP_S)} disabled={durationS === 0}>&gt;</button>
      <input aria-label="Playhead" type="range" min={0} max={durationS || 1} step={PLAYHEAD_STEP_S} value={playhead} disabled={durationS === 0} onChange={(event) => onPlayhead(Number(event.target.value))} />
      <span>selection: {selectedActor ?? "none"}</span>
    </div>
    {error && <p className="timeline-error" role="alert">{error}</p>}
    {!timeline && !error && <p className="timeline-empty">Select an imported scenario to load time-indexed actor tracks.</p>}
    {timeline && <ol className="actor-tracks" aria-label="Actor state tracks">{activeTracks.map(({ track, sample }) => <li key={track.actor_id} className={selectedActor === track.actor_id ? "actor-track selected" : "actor-track"}>
      <button className="track-label" aria-pressed={selectedActor === track.actor_id} onClick={() => onSelectActor(track.actor_id)}>{track.actor_id}{track.role === "ego" ? " (ego)" : ""}</button>
      <span className="track-time">t={formatTimestamp(sample?.time_s)} s</span>
      {CHANNELS.map((channel) => {
        const availability: ChannelAvailability = track.channels[channel];
        return <div className="track-channel" key={channel} data-channel={channel}>
          <span className="track-channel-name">{CHANNEL_LABELS[channel]}</span>
          {availability.available
            ? <svg className="track-spark" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={`${track.actor_id} ${CHANNEL_LABELS[channel].toLowerCase()} over time; at playhead ${formatChannelValue(channel, channelValue(sample, channel))}`}><line className="track-playhead" x1={at(playhead)} y1="0" x2={at(playhead)} y2="100" />{polyline(track, channel).map((points, index) => <polyline key={index} points={points} />)}</svg>
            : <span className="track-channel-missing" title={availability.unavailable_reason ?? ""}>{MISSING}</span>}
          <span className="track-channel-value">{formatChannelValue(channel, channelValue(sample, channel))}</span>
        </div>;
      })}
    </li>)}</ol>}
    {timeline && <ul className="gate-lane" aria-label="Gate lane">{(gates?.gates ?? []).map((gate: GateSegment) => <li key={gate.gate_id} className={`gate-segment ${gate.status}`} style={{ left: `${at(gate.start_s)}%`, width: `${Math.max(1.5, ((gate.end_s - gate.start_s) / span) * 100)}%` }} title={`${gate.gate_id}: ${gate.status}${gate.reasons.length ? ` (${gate.reasons.join(", ")})` : ""}`}>
      <span className="gate-id">{gate.gate_id}</span><span className="gate-status">{gate.status}</span>{gate.scientific_status === "PROVISIONAL" && <span className="gate-provisional">PROVISIONAL</span>}
      <span className="sr-only">{`${gate.gate_id} ${gate.status} from ${gate.start_s.toFixed(2)} to ${gate.end_s.toFixed(2)} seconds${gate.reasons.length ? `; reasons ${gate.reasons.join(", ")}` : ""}${gate.scientific_status === "PROVISIONAL" ? "; PROVISIONAL" : ""}`}</span>
    </li>)}</ul>}
    {timeline && <ul className="gate-lane-status" aria-label="Gate status list">{(gates?.gates ?? []).map((gate: GateSegment) => <li key={`${gate.gate_id}-status`}><strong>{gate.gate_id}</strong> <StatusBadge status={gate.status} />{gate.scientific_status === "PROVISIONAL" && <StatusBadge status="PROVISIONAL" />}<span>{gate.start_s.toFixed(2)}-{gate.end_s.toFixed(2)} s</span><span>{gate.reasons.join(", ") || "no reasons"}</span></li>)}</ul>}
    {measurement && <p className="measure-readout">Measure at {playhead.toFixed(2)} s: {measureSummary(measurement)}{measurement.status === "measured" ? `; bearing ${measurement.bearing_rad.toFixed(3)} rad; heading delta ${measurement.heading_delta_rad.toFixed(3)} rad; sample offset ${measurement.time_offset_s.toFixed(2)} s` : ""}</p>}
  </section>;
}

function channelCeiling(track: ActorTrack, channel: ChannelName): number {
  const values = track.samples.map((sample) => channelValue(sample, channel)).filter((value): value is number => value !== null).map((value) => Math.abs(value));
  return values.length ? Math.max(...values) || 1 : 1;
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

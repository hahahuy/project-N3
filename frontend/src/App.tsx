import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  ActorTimeline,
  ActorTrack,
  addRollbackMarker,
  apiUrl,
  API_BASE,
  INTERNAL_PHYSICS_MODE,
  ArtifactLink,
  ChannelAvailability,
  ComparePayload,
  EsminiCapability,
  EvidenceLayer,
  fetchActorTimeline,
  fetchCompare,
  fetchEsminiCapability,
  fetchGateTimeline,
  fetchLidarDescriptor,
  fetchSensorEvidence,
  fetchPOVFrame,
  fetchPOVImageFrame,
  fetchLiveCapability,
  createLiveScenarioPair,
  fetchLiveState,
  fetchRecipe,
  fetchScenario,
  fetchScenarioArtifacts,
  fetchScenarios,
  fetchSettings,
  fetchTrajectory,
  fetchVariantLineage,
  fetchWorkspaceScenario,
  fetchCameraEvidence,
  fetchTopDownState,
  fetchTopDownMap,
  TopDownMap,
  GateTimeline,
  LidarDescriptor,
  SensorEvidence,
  topDownImageUrl,
  lidarPayloadUrl,
  moveRecipeStep,
  POVFrame,
  POVImageFrame,
  LiveCapability,
  LiveState,
  RecipeDocument,
  RecipeStep,
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
import { getViewDescriptor, MAIN_VIEW, MAX_VIEWS, VIEW_REGISTRY, ViewType } from "./view-panels";
import { createPlayheadRequest } from "./evidence-request";
import WasmPlaybackView from "./wasm-playback/WasmPlaybackView";
import type { WasmOrbitState, WasmOverlayToggles } from "./wasm-playback/types";
import type { WasmTransportHandle } from "./wasm-playback/transport";
import { MOTION_GUARDRAILS } from "./motion-editor";
import VariantMotionEditor from "./motion-editor";

type View = { id: number; type: ViewType };
type CameraPov = "CAM_FRONT_RIGHT" | "CAM_FRONT" | "CAM_FRONT_LEFT" | "CAM_BACK_RIGHT" | "CAM_BACK_LEFT" | "CAM_BACK";
const CAMERA_POVS: CameraPov[] = ["CAM_FRONT_RIGHT", "CAM_FRONT", "CAM_FRONT_LEFT", "CAM_BACK_RIGHT", "CAM_BACK_LEFT", "CAM_BACK"];
type Panel = "versions" | "catalog" | "comments";
type Flyout = "metrics" | "provenance" | "guardrails";
type Tool = { icon: IconName; label: string; shortcut?: string; disabled?: boolean; badge?: string; note?: string; onClick?: () => void; menu?: React.ReactNode };
type StatusLine = { label: string; available: boolean; note?: string };
type Command = { label: string; group: string; icon: IconName; shortcut?: string; disabled?: boolean; run: () => void };

const viewLabels: Record<ViewType, string> = Object.fromEntries(VIEW_REGISTRY.descriptors.map((descriptor) => [descriptor.type, descriptor.label])) as Record<ViewType, string>;
const DOCUMENT_TABS = ["Scenario studio", "Variant studio", "Report"] as const;
const PANEL_DEFAULT_WIDTH = 270;
const PANEL_MIN_WIDTH = 180;
const PANEL_MAX_WIDTH = 520;
const TIMELINE_DEFAULT_HEIGHT = 236;
const TIMELINE_MIN_HEIGHT = 120;
const TIMELINE_MAX_HEIGHT = 520;
const PLAYHEAD_STEP_S = 0.05;
const LIDAR_SYNC_TOLERANCE_S = 0.25;
const CHANNELS = ["position", "heading", "speed", "acceleration", "braking"] as const;
const CHANNEL_LABELS: Record<(typeof CHANNELS)[number], string> = { position: "Position", heading: "Heading", speed: "Speed", acceleration: "Acceleration", braking: "Braking" };
const MISSING = "n/a";
const SELECTED_TOOL_NOTE = "You have selected this buttons";

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

function nearestSampleIndex(samples: TimelineSample[], timeS: number): number {
  let index = -1;
  let distance = Number.POSITIVE_INFINITY;
  samples.forEach((sample, candidate) => {
    const nextDistance = Math.abs(sample.time_s - timeS);
    if (nextDistance < distance) { distance = nextDistance; index = candidate; }
  });
  return index;
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

function displayScenarioId(scenarioId: string): string {
  if (!scenarioId.startsWith("nuscenes-")) return scenarioId;
  const firstHash = scenarioId.slice("nuscenes-".length).split("-", 1)[0];
  return `nuscenes-${firstHash.slice(0, 6)}`;
}

function displayBranchId(branchId: string): string {
  if (!branchId.startsWith("branch-")) return branchId;
  return `branch-${displayScenarioId(branchId.slice("branch-".length))}`;
}

function displayMapName(scenario: ScenarioSummary): string {
  const mapName = scenario.provenance.map_name?.toLowerCase() ?? "";
  if (mapName.includes("boston")) return "Boston Seaport";
  if (mapName.includes("queenstown")) return "Singapore Queenstown";
  if (mapName.includes("one-north") || mapName.includes("onenorth")) return "Singapore One North";
  if (mapName.includes("holland")) return "Singapore Holland Village";
  return scenario.provenance.map_name || "Map unavailable";
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


/** ADE/FDE between two actor trajectories, aligned by nearest sample time.
 *
 *  There is no replay trace in this workspace, so `replay_metrics` is empty and
 *  a baseline has nothing to be measured against. The meaningful comparison is
 *  a committed branch against the scenario it branched from: the parent is the
 *  reference and the child is the prediction. Recorded annotated actors come
 *  along for free because both sides carry the same actor set. */
type AdFdeRow = {
  actorId: string;
  actorType: string;
  samples: number | null;
  adeM: number | null;
  fdeM: number | null;
  unavailableReason: string | null;
};

function nearestByTime(samples: TimelineSample[], timeS: number): TimelineSample | undefined {
  let best: TimelineSample | undefined;
  let bestDelta = Number.POSITIVE_INFINITY;
  for (const sample of samples) {
    const delta = Math.abs(sample.time_s - timeS);
    if (delta < bestDelta) { bestDelta = delta; best = sample; }
  }
  return best;
}

function computeAdFde(reference: TimelineSample[] | undefined, edited: TimelineSample[] | undefined, actorId: string, actorType: string): AdFdeRow {
  if (!reference || reference.length === 0) return { actorId, actorType, samples: null, adeM: null, fdeM: null, unavailableReason: "no parent trajectory for this actor" };
  if (!edited || edited.length === 0) return { actorId, actorType, samples: null, adeM: null, fdeM: null, unavailableReason: "actor is absent from the selected version" };
  const distances: number[] = [];
  for (const sample of edited) {
    const against = nearestByTime(reference, sample.time_s);
    if (against) distances.push(Math.hypot(sample.x_m - against.x_m, sample.y_m - against.y_m));
  }
  if (distances.length === 0) return { actorId, actorType, samples: null, adeM: null, fdeM: null, unavailableReason: "no overlapping sample times" };
  return {
    actorId,
    actorType,
    samples: distances.length,
    adeM: distances.reduce((total, value) => total + value, 0) / distances.length,
    fdeM: distances[distances.length - 1]!,
    unavailableReason: null,
  };
}

function App() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selected, setSelected] = useState<ScenarioSummary | null>(null);
  const [trajectory, setTrajectory] = useState<TrajectoryResponse | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceScenario | null>(null);
  const [panel, setPanel] = useState<Panel>("catalog");
  const [flyout, setFlyout] = useState<Flyout | null>(null);
  const [views, setViews] = useState<View[]>([{ id: 1, type: MAIN_VIEW }]);
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
  const [timelineHeight, setTimelineHeight] = useState(TIMELINE_DEFAULT_HEIGHT);
  const [timelineOpen, setTimelineOpen] = useState(true);
  const [timelineResizing, setTimelineResizing] = useState(false);
  const timelineDragRef = useRef({ startY: 0, startHeight: TIMELINE_DEFAULT_HEIGHT });
  const [overflowOpen, setOverflowOpen] = useState(false);
  const groupsRef = useRef<HTMLDivElement | null>(null);
  const [hiddenTools, setHiddenTools] = useState<string[]>([]);
  const [draggingViewId, setDraggingViewId] = useState<number | null>(null);
  const [dropTargetViewId, setDropTargetViewId] = useState<number | null>(null);
  const [hiddenKinds, setHiddenKinds] = useState<string[]>([]);
  const [layersOpen, setLayersOpen] = useState<number | null>(null);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [artifacts, setArtifacts] = useState<ArtifactLink[] | null>(null);
  const [recipe, setRecipe] = useState<RecipeDocument | null>(null);
  const [markerName, setMarkerName] = useState("Checkpoint");
  const [lineage, setLineage] = useState<VariantLineage | null>(null);
  const [compareAgainst, setCompareAgainst] = useState<string>("");
  const [compare, setCompare] = useState<ComparePayload | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [povFrames, setPovFrames] = useState<Record<string, POVFrame | null>>({});
  const [povImages, setPovImages] = useState<Record<string, POVImageFrame | null>>({});
  const [liveCapability, setLiveCapability] = useState<LiveCapability | null>(null);
  const [liveState, setLiveState] = useState<LiveState | null>(null);
  const [liveSessionId, setLiveSessionId] = useState<string | null>(null);
  const [lidar, setLidar] = useState<LidarDescriptor | null>(null);
  const [sensorEvidence, setSensorEvidence] = useState<SensorEvidence | null>(null);
  const [sensorSweeps, setSensorSweeps] = useState(5);
  const [lidarDecimation, setLidarDecimation] = useState(8);
  const [cameraPovs, setCameraPovs] = useState<Record<number, CameraPov>>({});
  const [wasmOrbit, setWasmOrbit] = useState<WasmOrbitState>({ position: [20, 22, 26], target: [0, 0, 0] });
  // One shared default now that Scenario studio and Variant studio drive the same
  // preview state: exact cuboids on (the spec asks for bounding boxes to be
  // visible in Variant studio), recorded paths and the costly LiDAR cloud off.
  const [wasmToggles, setWasmToggles] = useState<WasmOverlayToggles>({ cuboids: true, paths: false, lidar: false });
  const [actorTimeline, setActorTimeline] = useState<ActorTimeline | null>(null);
  const [gateTimeline, setGateTimeline] = useState<GateTimeline | null>(null);
  const [selectedActor, setSelectedActor] = useState<string | null>(null);
  const [wasmTransport, setWasmTransport] = useState<WasmTransportHandle | null>(null);
  const [guardrailViolations, setGuardrailViolations] = useState<string[]>([]);
  const [adFdeRows, setAdFdeRows] = useState<AdFdeRow[]>([]);
  const [adFdeReason, setAdFdeReason] = useState<string | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);

  // ADE/FDE needs a parent to measure against. A baseline has none, so the
  // table reports that plainly instead of showing empty numbers.
  useEffect(() => {
    let cancelled = false;
    if (!selected) { setAdFdeRows([]); setAdFdeReason(null); return; }
    const parentId = selected.parent_scenario_id;
    if (!parentId) {
      setAdFdeRows([]);
      setAdFdeReason("This is a root scenario: there is no parent trajectory to measure ADE/FDE against.");
      return;
    }
    setAdFdeReason(null);
    Promise.all([fetchActorTimeline(selected.scenario_id), fetchActorTimeline(parentId)])
      .then(([edited, reference]) => {
        if (cancelled) return;
        const ids = new Set([...edited.tracks.map((t) => t.actor_id), ...reference.tracks.map((t) => t.actor_id)]);
        setAdFdeRows(Array.from(ids).sort().map((id) => {
          const editedTrack = edited.tracks.find((t) => t.actor_id === id);
          const referenceTrack = reference.tracks.find((t) => t.actor_id === id);
          return computeAdFde(referenceTrack?.samples, editedTrack?.samples, id, editedTrack?.actor_type ?? referenceTrack?.actor_type ?? MISSING);
        }));
      })
      .catch((e: Error) => { if (!cancelled) { setAdFdeRows([]); setAdFdeReason(e.message); } });
    return () => { cancelled = true; };
  }, [selected?.scenario_id, selected?.parent_scenario_id]);

  const toolbarGroups: { label: string; tools: Tool[] }[] = [
    { label: "History", tools: [{ icon: "undo", label: "Undo", shortcut: "Ctrl+Z", disabled: !recipe?.history.undoable, onClick: () => runRecipe(undoRecipe) }, { icon: "redo", label: "Redo", shortcut: "Ctrl+Shift+Z", disabled: !recipe?.history.redoable, onClick: () => runRecipe(redoRecipe) }] },
    { label: "Import", tools: [{ icon: "import", label: "Import scene", shortcut: "I", disabled: true, onClick: () => openPanel("catalog") }, { icon: "export", label: "Export", onClick: exportSelected, disabled: !selected }] },
    { label: "Edit", tools: [{ icon: "cursor", label: "Select actors", shortcut: "S", note: activeTab === "Scenario studio" ? SELECTED_TOOL_NOTE : undefined, disabled: activeTab === "Scenario studio", onClick: selectActors }, { icon: "edit", label: "Edit motion", shortcut: "E", onClick: openMotionEditor, disabled: !selected || !selectedActor }, { icon: "behavior", label: "Behavior mode", disabled: true }] },
    { label: "Check / Run", tools: [{ icon: "validate", label: "Validate", shortcut: "V", disabled: true }, { icon: "replay", label: "Replay", disabled: true }] },
    { label: "Inspect", tools: [{ icon: "measure", label: "Measure", shortcut: "M", onClick: () => setMode("measure") }] },
     { label: "View", tools: [{ icon: "add-view", label: "Add view", shortcut: "Shift+V", disabled: views.length >= MAX_VIEWS, onClick: () => setAddViewOpen(!addViewOpen), menu: addViewOpen && views.length < MAX_VIEWS ? <AddViewMenu viewCount={views.length} onAdd={selectAddedView} /> : undefined }] },
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

  const refreshScenarios = () => {
    setLoading(true);
    fetchScenarios().then(setScenarios).catch((e) => setError(e.message)).finally(() => setLoading(false));
  };
  useEffect(() => {
    refreshScenarios();
    const refreshOnFocus = () => refreshScenarios();
    window.addEventListener("focus", refreshOnFocus);
    return () => window.removeEventListener("focus", refreshOnFocus);
  }, []);
  useEffect(() => {
    fetchEsminiCapability().then(setCapability).catch(() => setCapability(null));
    fetchLiveCapability().then(setLiveCapability).catch(() => setLiveCapability(null));
    fetchSettings().then(setSettings).catch(() => setSettings(null));
  }, []);
  useEffect(() => {
    if (!selected) { setArtifacts(null); setLidar(null); setSensorEvidence(null); return; }
    fetchScenarioArtifacts(selected.scenario_id).then((payload) => setArtifacts(payload.artifacts)).catch(() => setArtifacts(null));
    fetchLidarDescriptor(selected.scenario_id).then(setLidar).catch(() => setLidar({ available: false, unavailable_reason: "lidar_descriptor_request_failed" }));
    if (!views.some((view) => view.type === "sensor-evidence")) { setSensorEvidence(null); return; }
    fetchSensorEvidence(selected.scenario_id, sensorSweeps).then(setSensorEvidence).catch(() => setSensorEvidence({ contract_version: "nuscenes-sensor-evidence-v1", channel: "LIDAR_TOP", status: "unavailable", unavailable_reason: "sensor_evidence_request_failed", sweeps: [], map_underlay: { available: false, source: "nuscenes-devkit-sensor-evidence", unavailable_reason: "sensor_evidence_request_failed" }, can_telemetry: { available: false, source: "nuScenes_CAN_bus", unavailable_reason: "sensor_evidence_request_failed" }, synchronization: { status: "unavailable", historical_sweep_smearing: "not_available" }, provenance: {}, artifact_visibility: "local_private" }));
  }, [selected?.scenario_id, sensorSweeps, views]);
  useEffect(() => {
    if (!liveSessionId) return;
    let cancelled = false;
    const poll = () => fetchLiveState(liveSessionId).then((state) => { if (!cancelled) setLiveState(state); }).catch(() => { if (!cancelled) setLiveState(null); });
    poll();
    const interval = window.setInterval(poll, 250);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [liveSessionId]);
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
    if (!selected) { setRecipe(null); setLineage(null); return; }
    fetchRecipe(selected.scenario_id).then(setRecipe).catch(() => setRecipe(null));
    fetchVariantLineage(selected.scenario_id).then(setLineage).catch(() => setLineage(null));
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
    if (views.length >= MAX_VIEWS) return null;
    const id = nextViewId;
    setViews([...views, { id, type }]); setNextViewId(id + 1);
    setAddViewOpen(false);
    return id;
  }
  function selectAddedView(type: ViewType) {
    setAddViewOpen(false);
    addView(type);
  }
  function closeView(id: number) { setViews(views.filter((view) => view.id !== id)); }
  function swapViews(sourceId: number, targetId: number) {
    if (sourceId === targetId) return;
    setViews((current) => {
      const sourceIndex = current.findIndex((view) => view.id === sourceId);
      const targetIndex = current.findIndex((view) => view.id === targetId);
      if (sourceIndex < 0 || targetIndex < 0) return current;
      const next = [...current];
      [next[sourceIndex], next[targetIndex]] = [next[targetIndex], next[sourceIndex]];
      return next;
    });
  }
  function startViewDrag(id: number, event: React.DragEvent<HTMLElement>) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(id));
    setDraggingViewId(id);
    setDropTargetViewId(null);
  }
  function dragOverView(id: number, event: React.DragEvent<HTMLElement>) {
    if (draggingViewId === null || draggingViewId === id) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDropTargetViewId(id);
  }
  function dropView(id: number, event: React.DragEvent<HTMLElement>) {
    event.preventDefault();
    const sourceId = Number(event.dataTransfer.getData("text/plain"));
    if (Number.isInteger(sourceId)) swapViews(sourceId, id);
    setDraggingViewId(null);
    setDropTargetViewId(null);
  }
  function endViewDrag() {
    setDraggingViewId(null);
    setDropTargetViewId(null);
  }
  function resetLayout() { setViews([{ id: 1, type: MAIN_VIEW }]); setNextViewId(2); setHiddenKinds([]); }
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
  function startNativeSession() {
    if (!selected || liveCapability?.available !== true) return;
    createLiveScenarioPair(selected.scenario_id)
      .then((state) => { setLiveSessionId(state.session_id); setLiveState(state); setError(null); })
      .catch((e: Error) => setError(e.message));
  }
  function runRecipe(action: (scenarioId: string) => Promise<RecipeDocument>) {
    if (!selected) return;
    action(selected.scenario_id).then(setRecipe).catch((e: Error) => setError(e.message));
  }
  function selectActors() {
    setMode("select");
    setActiveTab("Scenario studio");
  }

  function openMotionEditor() {
    if (!selected || !selectedActor) return;
    setActiveTab("Variant studio");
    setError(null);
  }

  function startResize(event: React.PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
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
    if (event.key === "End") { event.preventDefault(); setLeftOpen(true); setPanelWidth(PANEL_MAX_WIDTH); }
  }

  function resetPanelSize() { setLeftOpen(true); setPanelWidth(PANEL_DEFAULT_WIDTH); }

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

  function startTimelineResize(event: React.PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    timelineDragRef.current = { startY: event.clientY, startHeight: timelineHeight };
    setTimelineResizing(true);
  }

  function resizeTimelineByKeyboard(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setTimelineOpen(true);
      setTimelineHeight(Math.min(TIMELINE_MAX_HEIGHT, timelineHeight + 16));
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (timelineHeight - 16 < TIMELINE_MIN_HEIGHT) { setTimelineOpen(false); return; }
      setTimelineOpen(true);
      setTimelineHeight(timelineHeight - 16);
    }
    if (event.key === "Home") { event.preventDefault(); setTimelineOpen(true); setTimelineHeight(TIMELINE_DEFAULT_HEIGHT); }
    if (event.key === "End") { event.preventDefault(); setTimelineOpen(true); setTimelineHeight(TIMELINE_MAX_HEIGHT); }
  }

  function resetTimelineSize() { setTimelineOpen(true); setTimelineHeight(TIMELINE_DEFAULT_HEIGHT); }

  useEffect(() => {
    if (!timelineResizing) return;
    const onMove = (event: PointerEvent) => {
      const next = timelineDragRef.current.startHeight - (event.clientY - timelineDragRef.current.startY);
      if (next < TIMELINE_MIN_HEIGHT) { setTimelineHeight(TIMELINE_MIN_HEIGHT); setTimelineOpen(false); setTimelineResizing(false); return; }
      setTimelineOpen(true);
      setTimelineHeight(Math.min(TIMELINE_MAX_HEIGHT, next));
    };
    const onRelease = () => setTimelineResizing(false);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onRelease);
    window.addEventListener("pointercancel", onRelease);
    return () => { window.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onRelease); window.removeEventListener("pointercancel", onRelease); };
  }, [timelineResizing]);

  const bodyClass = `workspace-body${leftOpen ? "" : " left-collapsed"}${timelineOpen ? "" : " timeline-collapsed"}`;
  const bodyStyle = { "--panel-width": `${leftOpen ? panelWidth : 0}px`, "--timeline-height": `${timelineOpen ? timelineHeight : 0}px` } as React.CSSProperties;
  const esminiLibAvailable = liveCapability?.available === true;
  const datasetAvailable = settings?.dataset_root_exists === true;
  const simulatorLines: StatusLine[] = [
    // esminiLib is the library the native live sessions actually load; the
    // esmini CLI capability is a separate probe and can pass while the
    // library is missing, so report the library and say which one answered.
    {
      label: "esminiLib",
      available: esminiLibAvailable,
      // When it is up, show what loaded. When it is down, show why — a bare
      // library path next to "unavailable" reads like a version string.
      note: esminiLibAvailable
        ? liveCapability?.version ?? liveCapability?.library ?? capability?.version ?? undefined
        : liveCapability?.unavailable_reason ?? capability?.diagnostic ?? liveCapability?.library ?? undefined,
    },
    // The in-repo single-track follower. It is pure Python with no external
    // simulator and no CARLA client, so it is available whenever the api is —
    // but it stays a diagnostic, never replay evidence.
    { label: "internal single-track physics", available: true, note: INTERNAL_PHYSICS_MODE },
    { label: "CARLA", available: false, note: "not used; no client, no wheel mount" },
  ];
  const datasetLines: StatusLine[] = [{ label: "nuScenes", available: datasetAvailable, note: settings?.dataset_version ?? undefined }];
  const simulationTone = simulatorLines.every((line) => line.available) ? "all" : simulatorLines.some((line) => line.available) ? "some" : "off";
  const datasetTone = datasetLines.every((line) => line.available) ? "all" : "off";

  const commands: Command[] = [
    ...toolbarGroups.flatMap((group) => group.tools.map((tool) => ({ label: tool.label, group: group.label, icon: tool.icon, shortcut: tool.shortcut, disabled: tool.disabled, run: () => tool.onClick?.() }))),
    { label: "Reset layout", group: "View", icon: "compare", run: resetLayout },
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
  function focusActor(actorId: string) {
    setSelectedActor(actorId);
    const sample = activeTracks.find(({ track }) => track.actor_id === actorId)?.sample;
    if (!sample) return;
    const target: [number, number, number] = [sample.x_m, 1, -sample.y_m];
    setWasmOrbit({ position: [target[0] + 8, target[1] + 6, target[2] + 10], target });
  }

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
      if (shortcut === "s") { event.preventDefault(); selectActors(); return; }
      if (shortcut === "e") { if (selected && selectedActor) { event.preventDefault(); openMotionEditor(); } return; }
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
        <IconButton icon="provenance" label="Versions" active={leftOpen && panel === "versions"} onClick={() => selectPanel("versions")} />
        <IconButton icon="catalog" label="Catalog" active={leftOpen && panel === "catalog"} onClick={() => selectPanel("catalog")} />
        <IconButton icon="comments" label="Comments" active={leftOpen && panel === "comments"} onClick={() => selectPanel("comments")} />
        </aside>
      <aside className="left-panel" aria-label={`${panel} panel`}>
         {panel === "catalog" && <Catalog scenarios={scenarios} selected={selected} loading={loading} filter={catalogFilter} onFilter={setCatalogFilter} onSelect={setSelected} onRefresh={refreshScenarios} />}{panel === "versions" && <VersionTree scenarios={scenarios} selected={selected} onSelect={setSelected} />}{panel === "comments" && <EmptyPanel title="Comments" copy="No comments in this document." />}
      </aside>
       <div className={`split-handle left${resizing ? " dragging" : ""}`} role="separator" aria-orientation="vertical" aria-label="Resize side panel" aria-valuetext={leftOpen ? `${Math.round(panelWidth)} pixels` : "collapsed"} aria-valuenow={leftOpen ? panelWidth : 0} aria-valuemin={PANEL_MIN_WIDTH} aria-valuemax={PANEL_MAX_WIDTH} tabIndex={0} title="Drag to resize. Double-click to reset. Use Home/End for preset sizes." onPointerDown={startResize} onDoubleClick={resetPanelSize} onKeyDown={resizeByKeyboard} />
      <section className="view-manager" aria-label="View manager">
        {error && <div className="inline-error" role="alert">{error}</div>}
         {mode === "compare"
          ? <CompareSurface payload={compare} error={compareError} selected={selected} scenarios={scenarios} against={compareAgainst} onAgainst={setCompareAgainst} playhead={playhead} />
            : activeTab === "Scenario studio"
            ? <div className={`view-grid count-${views.length}`}>
                   {views.map((view, index) => <ViewPane key={view.id} view={view} dragging={draggingViewId === view.id} dropTarget={dropTargetViewId === view.id} onDragStart={(event) => startViewDrag(view.id, event)} onDragEnd={endViewDrag} onDragOver={(event) => dragOverView(view.id, event)} onDrop={(event) => dropView(view.id, event)}             common={{ trajectory, scenarioLoading: Boolean(selected) && !trajectory, timeline: playhead, hiddenKinds, onToggleKind: toggleKind, layersOpen: layersOpen === view.id, onToggleLayers: () => setLayersOpen(layersOpen === view.id ? null : view.id), onClose: () => closeView(view.id), wasmOrbit, onWasmOrbitChange: setWasmOrbit, wasmToggles, onWasmTogglesChange: setWasmToggles, onTransportChange: setWasmTransport, onActorPick: (actorId) => {
        if (!actorId) { setSelectedActor(null); return; }
        const match = actorTimeline?.tracks.find((track) => track.actor_id.toLowerCase() === actorId.toLowerCase());
        if (match) setSelectedActor(match.actor_id);
      } }} content={view.type === "top-down" ? { type: view.type, selected, activeTracks, selectedActor, measurement, mode, onSelectActor: focusActor } : view.type === "sensor-evidence" ? { type: view.type, evidence: sensorEvidence, onSensorSweeps: setSensorSweeps, decimation: lidarDecimation, onDecimation: setLidarDecimation } : view.type === "lidar" ? { type: view.type, descriptor: lidar, decimation: lidarDecimation, onDecimation: setLidarDecimation } : view.type === "real-camera" ? { type: view.type, pov: cameraPovs[view.id] ?? "CAM_FRONT", onPov: (pov) => setCameraPovs((current) => ({ ...current, [view.id]: pov })) } : { type: view.type as "third-person" | "in-car", frame: povFrames[view.type], imageFrame: povImages[view.type], liveState, liveCapability, workspace, onStartNativeSession: startNativeSession, isMainView: index === 0, focusActorId: selectedActor }} />)}
             {views.length === 0 && <div className="empty-view"><strong>No views open.</strong><span>Add a view.</span><button onClick={() => addView("top-down")}>Add a Top-down view</button></div>}
          </div>
          : activeTab === "Variant studio"
           ? <VariantMotionEditor scenarioId={selected?.scenario_id ?? null} actorId={selectedActor ?? selected?.actors[0]?.actor_id ?? null} wasmToggles={wasmToggles} onWasmTogglesChange={setWasmToggles} playhead={playhead} onPlayheadChange={(value) => setTimeline(Math.min(Math.max(value, 0), durationS || 0))} onTransportChange={setWasmTransport} onGuardrailsChange={setGuardrailViolations} onBranchCommitted={() => refreshScenarios()} />
          : <div className="view-grid count-1"><div className="empty-view"><strong>{activeTab}</strong><span>Not available in this build.</span><button onClick={() => setActiveTab("Scenario studio")}>Back to Scenario studio</button></div></div>}
         <div className={`split-handle top${timelineResizing ? " dragging" : ""}`} role="separator" aria-orientation="horizontal" aria-label="Resize timeline" aria-valuetext={timelineOpen ? `${Math.round(timelineHeight)} pixels` : "collapsed"} aria-valuenow={timelineOpen ? timelineHeight : 0} aria-valuemin={TIMELINE_MIN_HEIGHT} aria-valuemax={TIMELINE_MAX_HEIGHT} tabIndex={0} title="Drag to resize. Double-click to reset. Use Home/End for preset sizes." onPointerDown={startTimelineResize} onDoubleClick={resetTimelineSize} onKeyDown={resizeTimelineByKeyboard} />
  <TimelineSurface
          timeline={actorTimeline}
          gates={gateTimeline}
          error={timelineError}
          playhead={playhead}
          durationS={durationS}
          activeTracks={activeTracks}
          selectedActor={selectedActor}
          measurement={measurement}
           onSelectActor={focusActor}
          onPlayhead={(value) => setTimeline(Math.min(Math.max(value, 0), durationS || 0))}
           onStep={(delta) => setTimeline(Math.min(Math.max(playhead + delta, 0), durationS || 0))}
           wasmToggles={wasmToggles}
           onWasmTogglesChange={setWasmToggles}
           transport={wasmTransport}
        />
      </section>
       <aside className="right-rail" aria-label="Inspection navigation">
        <IconButton icon="metrics" label="Metrics" badge="0" active={flyout === "metrics"} onClick={() => openFlyout("metrics")} />
        <IconButton icon="provenance" label="Provenance" active={flyout === "provenance"} onClick={() => openFlyout("provenance")} />
        <IconButton icon="validate" label="Guardrails" active={flyout === "guardrails"} alert={guardrailViolations.length > 0} badge={guardrailViolations.length > 0 ? String(guardrailViolations.length) : undefined} onClick={() => openFlyout("guardrails")} />
        {flyout && <div className="flyout"><span className="section-kicker">{flyout}</span><p className="flyout-time">playhead {playhead.toFixed(2)} s of {durationS.toFixed(2)} s / frame {activeTracks.find((entry) => entry.track.role === "ego")?.sample?.time_s === undefined ? MISSING : formatTimestamp(activeTracks.find((entry) => entry.track.role === "ego")?.sample?.time_s)} s</p>{flyout === "metrics" && <><h2>ADE / FDE per actor</h2><p className="flyout-note">Parent scenario is the reference; the selected version is the prediction. Recorded annotated actors are included.</p>{adFdeReason && <p className="flyout-alert" role="note">{adFdeReason}</p>}{adFdeRows.length > 0 && <table className="flyout-table" aria-label="ADE and FDE per actor"><thead><tr><th scope="col">actor</th><th scope="col">samples</th><th scope="col">ADE</th><th scope="col">FDE</th></tr></thead><tbody>{adFdeRows.map((row) => <tr key={row.actorId} data-unavailable={row.unavailableReason !== null}><th scope="row" title={row.actorId}>{row.actorId}</th><td>{row.samples ?? MISSING}</td><td>{row.adeM === null ? MISSING : `${row.adeM.toFixed(3)} m`}</td><td>{row.fdeM === null ? MISSING : `${row.fdeM.toFixed(3)} m`}</td></tr>)}</tbody></table>}{adFdeRows.some((row) => row.unavailableReason) && <ul className="flyout-list flyout-metric-notes">{adFdeRows.filter((row) => row.unavailableReason).map((row) => <li key={row.actorId}>{row.actorId}: {row.unavailableReason}</li>)}</ul>}</>}
          {flyout === "guardrails" && <><h2>CAD motion guardrails</h2>{guardrailViolations.length > 0 && <p className="flyout-alert" role="alert">{guardrailViolations.length} guardrail {guardrailViolations.length === 1 ? "violation" : "violations"} in the current draft</p>}<div className="flyout-list">{[
            ["minimum keyframe interval", `${MOTION_GUARDRAILS.minimumKeyframeIntervalS.toFixed(2)} s`],
            ["maximum speed", `${MOTION_GUARDRAILS.maximumSpeedMps.toFixed(1)} m/s`],
            ["maximum acceleration", `${MOTION_GUARDRAILS.maximumAccelerationMps2.toFixed(1)} m/s2`],
            ["maximum braking", `${MOTION_GUARDRAILS.maximumBrakingMps2.toFixed(1)} m/s2`],
            ["maximum yaw rate", `${MOTION_GUARDRAILS.maximumYawRateRps.toFixed(1)} rad/s`],
            ["maximum turn angle", `${MOTION_GUARDRAILS.maximumTurnAngleRad.toFixed(2)} rad`],
          ].map(([label, value]) => <div className="flyout-row" key={label}><strong>{label}</strong><span>{value}</span></div>)}</div>{guardrailViolations.length > 0 && <ul className="flyout-list flyout-violations">{guardrailViolations.map((violation) => <li key={violation}>{violation}</li>)}</ul>}<p>The backend is authoritative and re-checks every limit on commit.</p></>}
          {flyout === "provenance" && <><h2>Provenance</h2>{selected ? (Object.keys(selected.provenance ?? {}).length > 0 ? <div className="flyout-list">{Object.entries(selected.provenance).map(([key, value]) => <div className="flyout-row" key={key}><strong>{key}</strong><span>{value}</span></div>)}</div> : <p>This scenario records no provenance fields.</p>) : <p>Select an imported scenario first.</p>}</>}
        </div>}
       </aside>
    </div>
     <footer className="document-footer"><div className="document-tabs">{DOCUMENT_TABS.map((tab) => <button className={activeTab === tab ? "active" : ""} key={tab} onClick={() => setActiveTab(tab)}>{tab}</button>)}</div><div className="status-bar"><span>api: {API_BASE}</span><span>scenarios: {scenarios.length}</span><span>source scenes: {settings?.source_scene_count ?? MISSING}</span><span>artifacts: {artifacts?.length ?? 0}</span><span>branch: {lineage?.branch?.branch_id ? displayBranchId(lineage.branch.branch_id) : MISSING}</span><span>config hash: {lineage?.fields?.config_hash ? String(lineage.fields.config_hash).slice(0, 12) : MISSING}</span><span>rollback: {recipe ? recipe.active_marker_id ?? "none" : MISSING}</span><span>recipe: {recipe ? `${recipe.active_step_count}/${recipe.step_count} steps` : MISSING}</span><span>time: {playhead.toFixed(2)} s / {durationS.toFixed(2)} s</span><span>PROVISIONAL: {gateTimeline?.provisional_count ?? "n/a"}</span><span>POV: {povFrames["in-car"]?.simulator ?? povFrames["third-person"]?.simulator ?? MISSING}</span><span>frame: {selected?.coordinate_frame ?? MISSING}</span></div></footer>
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
function ToolButton({ icon, label, shortcut, disabled, badge, note, onClick, menu }: Tool) { return <div className="add-view-control"><button className={`tool-button${badge ? " badged" : ""}`} data-tool={label} disabled={disabled} title={`${label}${shortcut ? ` (${shortcut})` : ""}${note ? ` - ${note}` : disabled ? " - unavailable in this build" : ""}`} onClick={onClick}><Icon name={icon} />{label}{badge && <b className={`tool-badge${disabled ? " locked" : ""}`} aria-hidden="true">{badge}</b>}</button>{menu}</div>; }
function IconButton({ label, icon, badge, active, alert, onClick }: { label: string; icon: IconName; badge?: string; active?: boolean; alert?: boolean; onClick: () => void }) { return <button className={`icon-button ${active ? "active" : ""}${alert ? " alert" : ""}`} aria-label={label} title={label} aria-pressed={active} onClick={onClick}><Icon name={icon} />{badge && <b>{badge}</b>}</button>; }
function StatusBadge({ status }: { status: string }) { return <span className={`status-badge ${status}`}>{status}</span>; }
function EmptyPanel({ title, copy }: { title: string; copy: string }) { return <div className="panel-content"><span className="section-kicker">LEFT PANEL</span><h2>{title}</h2><p>{copy}</p></div>; }
/** Branch tree for the scenario currently open in Scenario studio.
 *
 *  Scoped to the selected scenario rather than the whole catalog: the selected
 *  scene is the single root, and every version committed from it (a canvas
 *  motion edit) is a child, nested under the version it branched from. Editing
 *  the path and committing therefore links a new node directly below the one
 *  the user was looking at. Nothing is listed that is not reachable from the
 *  selection, so the panel answers "what did I make from this scene". */
function VersionTree({ scenarios, selected, onSelect }: { scenarios: ScenarioSummary[]; selected: ScenarioSummary | null; onSelect: (scenario: ScenarioSummary) => void }) {
  const byId = useMemo(() => new Map(scenarios.map((item) => [item.scenario_id, item])), [scenarios]);
  const childrenOf = useMemo(() => {
    const map = new Map<string, ScenarioSummary[]>();
    for (const item of scenarios) {
      if (!item.parent_scenario_id) continue;
      map.set(item.parent_scenario_id, [...(map.get(item.parent_scenario_id) ?? []), item]);
    }
    return map;
  }, [scenarios]);
  const [open, setOpen] = useState<string[]>([]);
  // A freshly committed branch must be visible without an extra click.
  useEffect(() => { if (selected) setOpen((current) => current.includes(selected.scenario_id) ? current : [...current, selected.scenario_id]); }, [selected?.scenario_id]);

  const toggle = (id: string) => setOpen((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);

  const node = (scenario: ScenarioSummary, depth: number): React.ReactNode => {
    const children = (childrenOf.get(scenario.scenario_id) ?? []).slice().sort((a, b) => a.scenario_id.localeCompare(b.scenario_id));
    const isOpen = open.includes(scenario.scenario_id);
    const isSelected = selected?.scenario_id === scenario.scenario_id;
    return <li key={scenario.scenario_id} role="treeitem" aria-selected={isSelected} aria-level={depth + 1}>
      <div className={`version-node${isSelected ? " selected" : ""}`}>
        {children.length > 0
          ? <button className="version-twisty" aria-label={`${isOpen ? "Collapse" : "Expand"} versions of ${scenario.scenario_id}`} aria-expanded={isOpen} onClick={() => toggle(scenario.scenario_id)}>{isOpen ? "\u25be" : "\u25b8"}</button>
          : <span className="version-twisty leaf" aria-hidden="true" />}
        <button className="version-label" aria-label={scenario.scenario_id} aria-pressed={isSelected} onClick={() => onSelect(scenario)} title={scenario.scenario_id}>
          <strong>{displayScenarioId(scenario.scenario_id)}</strong>
          <StatusBadge status={scenario.artifact_type} />
          <small>{scenario.duration_s.toFixed(1)} s{children.length > 0 ? ` \u00b7 ${children.length} version${children.length === 1 ? "" : "s"}` : ""}</small>
        </button>
      </div>
      {children.length > 0 && isOpen && <ul role="group">{children.map((child) => node(child, depth + 1))}</ul>}
    </li>;
  };

  const branchCount = selected ? countDescendants(selected.scenario_id, childrenOf) : 0;
  return <div className="panel-content version-tree-panel">
    <div className="panel-title"><span className="count">{selected ? branchCount : 0}</span><span className="section-kicker">Committed versions</span></div>
    {!selected
      ? <div className="panel-empty">Select a scenario in Scenario studio to see its version tree.</div>
      : <ul className="version-tree" role="tree" aria-label="Committed scenario versions">{node(byId.get(selected.scenario_id) ?? selected, 0)}</ul>}
    {selected && <small>Edit the motion in Variant studio and commit: each committed version is linked below the one it came from.</small>}
  </div>;
}

function countDescendants(id: string, childrenOf: Map<string, ScenarioSummary[]>): number {
  const children = childrenOf.get(id) ?? [];
  return children.length + children.reduce((total, child) => total + countDescendants(child.scenario_id, childrenOf), 0);
}

function CompareSide({ side, label, playhead }: { side: ComparePayload["sides"][number]; label: string; playhead: number }) {
  return <article className="compare-side" aria-label={`${label} side of the comparison`}>
    <header><strong title={side.scenario_id}>{displayScenarioId(side.scenario_id)}</strong><span>{side.artifact_type}</span><StatusBadge status={side.branch_name ? "available" : "unsupported"} /></header>
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
      <label>Left <input readOnly value={displayScenarioId(selected.scenario_id)} aria-label="Left scenario" title={selected.scenario_id} /></label>
      <label>Right <select aria-label="Right scenario" value={against} onChange={(event) => onAgainst(event.target.value)}>{candidates.length === 0 ? <option value="">no second scenario</option> : candidates.map((item) => <option key={item.scenario_id} value={item.scenario_id}>{displayScenarioId(item.scenario_id)}</option>)}</select></label>
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
 function Catalog({ scenarios, selected, loading, filter, onFilter, onSelect, onRefresh }: { scenarios: ScenarioSummary[]; selected: ScenarioSummary | null; loading: boolean; filter: string; onFilter: (value: string) => void; onSelect: (scenario: ScenarioSummary) => void; onRefresh: () => void }) { const visible = scenarios.filter((scenario) => scenario.scenario_id.toLowerCase().includes(filter.toLowerCase())); return <div className="panel-content"><div className="panel-title"><span className="count">{scenarios.length}</span><span className="section-kicker">Scenarios</span><button className="catalog-refresh" onClick={onRefresh} disabled={loading} aria-label="Refresh catalog" title="Refresh catalog"><Icon name="reload" size={14} /></button></div><input className="filter" value={filter} onChange={(event) => onFilter(event.target.value)} placeholder="Filter scenarios" aria-label="Filter scenarios" />{loading ? <div className="skeleton-list"><i /><i /><i /></div> : scenarios.length === 0 ? <div className="panel-empty">Import a scene to start a scenario.</div> : visible.length === 0 ? <div className="panel-empty">No scenarios match this filter.</div> : <div className="scenario-list">{visible.map((scenario) => <button className={selected?.scenario_id === scenario.scenario_id ? "selected" : ""} key={scenario.scenario_id} onClick={() => onSelect(scenario)}><span><strong title={scenario.scenario_id}>{displayScenarioId(scenario.scenario_id)}</strong><small>{scenario.artifact_type} / {scenario.duration_s.toFixed(2)} s</small><small>{displayMapName(scenario)}</small></span></button>)}</div>}</div>; }
function AddViewMenu({ viewCount, onAdd }: { viewCount: number; onAdd: (type: ViewType) => void }) {
  const atLimit = viewCount >= MAX_VIEWS;
   return <div className="add-view-menu" role="menu">{VIEW_REGISTRY.descriptors.filter((descriptor) => descriptor.type !== "lidar" && descriptor.type !== "in-car").map((descriptor) => <button key={descriptor.type} disabled={atLimit} onClick={() => onAdd(descriptor.type)}><strong>{descriptor.label}</strong><small title={descriptor.menuDescription}>{atLimit ? `maximum ${MAX_VIEWS} views reached` : descriptor.menuDescription}</small></button>)}</div>;
}

type ViewCommonProps = { trajectory: TrajectoryResponse | null; scenarioLoading: boolean; timeline: number; hiddenKinds: string[]; onToggleKind: (kind: string) => void; layersOpen: boolean; onToggleLayers: () => void; onClose: () => void; wasmOrbit: WasmOrbitState; onWasmOrbitChange: (orbit: WasmOrbitState) => void; wasmToggles: WasmOverlayToggles; onWasmTogglesChange: (toggles: WasmOverlayToggles) => void; onTransportChange: (handle: WasmTransportHandle | null) => void; onActorPick: (actorId: string | null) => void };
type ViewContent =
  | { type: "top-down"; selected: ScenarioSummary | null; activeTracks: ActiveTrack[]; selectedActor: string | null; measurement: Measurement | null; mode: string; onSelectActor: (actorId: string) => void }
  | { type: "sensor-evidence"; evidence: SensorEvidence | null; onSensorSweeps: (value: number) => void; decimation: number; onDecimation: (value: number) => void }
  | { type: "lidar"; descriptor: LidarDescriptor | null; decimation: number; onDecimation: (value: number) => void }
  | { type: "third-person" | "in-car"; frame?: POVFrame | null; imageFrame?: POVImageFrame | null; liveState: LiveState | null; liveCapability: LiveCapability | null; workspace: WorkspaceScenario | null; onStartNativeSession: () => void; isMainView?: boolean; focusActorId?: string | null }
  | { type: "real-camera"; pov: CameraPov; onPov: (pov: CameraPov) => void };

function ViewPane({ view, dragging, dropTarget, onDragStart, onDragEnd, onDragOver, onDrop, common, content }: { view: View; dragging: boolean; dropTarget: boolean; onDragStart: (event: React.DragEvent<HTMLElement>) => void; onDragEnd: () => void; onDragOver: (event: React.DragEvent<HTMLElement>) => void; onDrop: (event: React.DragEvent<HTMLElement>) => void; common: ViewCommonProps; content: ViewContent }) {
  const descriptor = getViewDescriptor(view.type);
  const kinds = common.trajectory ? Array.from(new Set(common.trajectory.paths.map((path) => path.path_kind))) : [];
  return <article className={`view-pane${dragging ? " dragging" : ""}${dropTarget ? " drop-target" : ""}`} onDragOver={onDragOver} onDrop={onDrop}>
    <header draggable onDragStart={onDragStart} onDragEnd={onDragEnd} aria-label={`${descriptor.label} view panel drag handle`}>
      <span className="view-icon"><Icon name={descriptor.icon} /></span><strong>{descriptor.label}</strong>
       {content.type === "real-camera" ? <CameraPovMenu pov={content.pov} onPov={content.onPov} /> : <div className="layers-control"><button className={`view-action${common.layersOpen ? " active" : ""}`} aria-expanded={common.layersOpen} onClick={common.onToggleLayers}>Layers</button>{common.layersOpen && <div className="layers-menu" role="menu">{kinds.length === 0 ? <p>No trajectory layers loaded.</p> : kinds.map((kind) => <button key={kind} role="menuitemcheckbox" aria-checked={!common.hiddenKinds.includes(kind)} onClick={() => common.onToggleKind(kind)}><span className={`status-dot ${common.hiddenKinds.includes(kind) ? "off" : "on"}`} />{kind}</button>)}</div>}</div>}
       <button className="close-view" aria-label={`Close view: ${descriptor.label}`} title={`Close view: ${descriptor.label}`} onClick={common.onClose}>x</button>
    </header>
    {renderViewContent(content, common, common.onTransportChange, common.onActorPick)}
  </article>;
}

function renderViewContent(content: ViewContent, common: ViewCommonProps, onTransport?: (handle: WasmTransportHandle | null) => void, onActorPick?: (actorId: string | null) => void) {
  const renderer = getViewDescriptor(content.type).renderer;
  if (renderer === "top-down" && content.type === "top-down") return <TopDownView selected={content.selected} trajectory={common.trajectory} timeline={common.timeline} activeTracks={content.activeTracks} selectedActor={content.selectedActor} measurement={content.measurement} mode={content.mode} onSelectActor={content.onSelectActor} hiddenKinds={common.hiddenKinds} />;
  if (renderer === "sensor-evidence" && content.type === "sensor-evidence") return typeof Worker !== "undefined" && selectedScenarioId(common) ? <WasmPlaybackView scenarioId={selectedScenarioId(common) ?? undefined} mode="sensor-evidence" playhead={common.timeline} toggles={common.wasmToggles} onTogglesChange={common.onWasmTogglesChange} orbit={common.wasmOrbit} onOrbitChange={common.onWasmOrbitChange} /> : <SensorEvidenceView evidence={content.evidence} decimation={content.decimation} onDecimation={content.onDecimation} onSweeps={content.onSensorSweeps} playhead={common.timeline} trajectory={common.trajectory} />;
  if (renderer === "lidar" && content.type === "lidar") return <LidarView descriptor={content.descriptor} decimation={content.decimation} onDecimation={content.onDecimation} playhead={common.timeline} />;
  if (renderer === "real-camera" && content.type === "real-camera") return <RealCameraView pov={content.pov} scenarioId={selectedScenarioId(common)} playhead={common.timeline} toggles={common.wasmToggles} />;
  const povContent = content as Extract<ViewContent, { type: "third-person" | "in-car" }>;
  if (povContent.type === "third-person" && typeof Worker !== "undefined" && selectedScenarioId(common)) return <WasmPlaybackView scenarioId={selectedScenarioId(common) ?? undefined} mode="third-person" playhead={common.timeline} toggles={common.wasmToggles} onTogglesChange={common.onWasmTogglesChange} orbit={common.wasmOrbit} onOrbitChange={common.onWasmOrbitChange} isMainView={povContent.isMainView} focusActorId={povContent.focusActorId} onTransport={onTransport} onActorPick={onActorPick} />;
  if (povContent.liveState?.status === "running" || povContent.liveState?.status === "paused" || povContent.liveState?.status === "reset") return <LivePOVView state={povContent.liveState} playhead={common.timeline} />;
  if (povContent.frame) return <POVView frame={povContent.frame} imageFrame={povContent.imageFrame} playhead={common.timeline} />;
  // A selected scenario whose trajectory has not arrived yet is still loading,
  // not unavailable. Rendering the esmini "unavailable" fallback in that window
  // reported a missing simulator for a scene that was merely slow to load.
  if (common.scenarioLoading) return <div className="unavailable-view"><StatusBadge status="loading" /><strong>{viewLabels[povContent.type]} loading</strong><p>Resolving the selected scenario. The workspace payload for a recorded nuScenes scene can take several seconds.</p></div>;
  const layer = povContent.workspace?.layers[povContent.type === "in-car" ? "in_car" : "third_person"];
  return <div className="unavailable-view"><StatusBadge status={layer?.available ? "loading" : "unavailable"} /><strong>{viewLabels[povContent.type]} {layer?.available ? "loading" : "unavailable"}</strong><p>{povContent.liveCapability?.unavailable_reason ?? layer?.unavailable_reason ?? "Select an imported scenario to query capability."}</p></div>;
}

function selectedScenarioId(common: ViewCommonProps): string | null {
  const scenarioId = common.trajectory?.scenario_id;
  return scenarioId ?? null;
}

function CameraPovMenu({ pov, onPov }: { pov: CameraPov; onPov: (pov: CameraPov) => void }) {
  const [open, setOpen] = useState(false);
  return <div className="layers-control"><button className={`view-action${open ? " active" : ""}`} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>camera pov</button>{open && <div className="layers-menu" role="menu">{CAMERA_POVS.map((option) => <button key={option} role="menuitemradio" aria-checked={pov === option} onClick={() => { onPov(option); setOpen(false); }}>{option}</button>)}</div>}</div>;
}

function RealCameraView({ pov, scenarioId, playhead, toggles }: { pov: CameraPov; scenarioId: string | null; playhead: number; toggles: WasmOverlayToggles }) {
  const [frame, setFrame] = useState<import("./api").CameraEvidenceFrame | null>(null);
  const requestRef = useRef<ReturnType<typeof createPlayheadRequest<{ id: string; channel: CameraPov; time: number }, import("./api").CameraEvidenceFrame>> | null>(null);
  if (!requestRef.current) requestRef.current = createPlayheadRequest(({ id, channel, time }: { id: string; channel: CameraPov; time: number }) => fetchCameraEvidence(id, channel, time));
  useEffect(() => {
    if (!scenarioId) return;
    let cancelled = false;
    requestRef.current?.request({ id: scenarioId, channel: pov, time: playhead }).then((next) => { if (!cancelled) setFrame(next); }).catch((error) => { if (!cancelled && error?.name !== "AbortError") setFrame(null); });
    return () => { cancelled = true; };
  }, [pov, scenarioId, playhead]);
  if (!frame || frame.status !== "rendered" || !frame.image?.url) return <div className="unavailable-view"><StatusBadge status="unavailable" /><strong>{pov}</strong><p>{frame?.unavailable_reason ?? "Select an imported scenario to query recorded camera evidence."}</p></div>;
  const recordedBoxOverlays = frame.recorded_cuboids.map((box, index) => {
    const corners = box.corners_2d as number[][] | undefined;
    if (!corners || corners.length < 4) return null;
    const points = corners.map((corner) => corner.join(",")).join(" ");
    return <polyline key={`box-${index}`} points={points} fill="none" stroke="#f27d72" strokeWidth="3" />;
  });
  return <div className="real-camera-view"><div className="real-camera-image"><img src={String(frame.image.url)} alt={`${pov} recorded camera at ${frame.resolved_time_s?.toFixed(2) ?? "n/a"} seconds`} />{(toggles.lidar || toggles.cuboids) && <svg className="real-camera-overlay" viewBox={`0 0 ${String(frame.image.width ?? 1600)} ${String(frame.image.height ?? 900)}`} preserveAspectRatio="none" aria-hidden="true">{toggles.lidar && frame.lidar_points.map((point, index) => <circle key={`lidar-${index}`} cx={point.u} cy={point.v} r="2" fill="#8fd3ff" opacity=".65" />)}{toggles.cuboids && recordedBoxOverlays}</svg>}</div><div className="view-legend"><span>{pov}</span><span>recorded nuScenes camera</span><span>t={frame.resolved_time_s?.toFixed(2) ?? "n/a"} s</span><span>recorded cuboids {frame.recorded_cuboids.length}</span><span>canonical cuboids {frame.canonical_cuboids.length}</span><span>LiDAR {toggles.lidar ? frame.lidar_points.length : "off"}</span></div></div>;
}

function LivePOVView({ state, playhead }: { state: LiveState; playhead: number }) {
  return <div className="pov-view live-pov" role="img" aria-label={`Live esmini state at ${state.simulation_time_s.toFixed(2)} seconds for playhead ${playhead.toFixed(2)} seconds`}>
    <div className="pov-horizon" /><div className="pov-road" />
    {state.objects.map((object) => <span key={object.id} className="pov-actor live-actor" style={{ left: `${50 + object.x_m * 2}%`, top: `${58 - object.y_m * 2}%` }} title={`${object.id} native esmini state`} />)}
    <div className="view-legend"><span>native esminiLib state</span><span>browser-native renderer</span><span>t={state.simulation_time_s.toFixed(2)} s</span><span>no screenshot stream</span></div>
  </div>;
}

function SensorEvidenceView({ evidence, decimation, onDecimation, onSweeps, playhead, trajectory }: { evidence: SensorEvidence | null; decimation: number; onDecimation: (value: number) => void; onSweeps: (value: number) => void; playhead: number; trajectory: TrajectoryResponse | null }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [showMap, setShowMap] = useState(true);
  const [showTrajectory, setShowTrajectory] = useState(true);
  const [showActors, setShowActors] = useState(true);
  const [status, setStatus] = useState("loading");
  useEffect(() => {
    if (!evidence || evidence.sweeps.length === 0) { setStatus(evidence?.unavailable_reason ?? "loading"); return; }
    let cancelled = false;
    setStatus("loading");
    Promise.all(evidence.sweeps.map(async (sweep) => { const response = await fetch(lidarPayloadUrl(sweep.sample_data_token ?? "", decimation)); if (!response.ok) throw new Error(`sensor_evidence_payload_${response.status}`); return new Uint8Array(await response.arrayBuffer()); }))
     .then((payloads) => { if (cancelled) return; const canvas = canvasRef.current; const context = canvas?.getContext("2d"); if (!canvas || !context) return; canvas.width = canvas.clientWidth * devicePixelRatio; canvas.height = canvas.clientHeight * devicePixelRatio; context.scale(devicePixelRatio, devicePixelRatio); context.fillStyle = "#101821"; context.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight); if (showMap && evidence.map_underlay.available) { context.strokeStyle = "#253b4b"; context.lineWidth = 1; (Object.values(evidence.map_underlay.layers ?? {}) as string[][]).forEach(() => { context.beginPath(); context.moveTo(canvas.clientWidth * .1, canvas.clientHeight * .7); context.lineTo(canvas.clientWidth * .9, canvas.clientHeight * .3); context.stroke(); }); } payloads.forEach((bytes, sweepIndex) => { context.fillStyle = sweepIndex === 0 ? "#8fd3ff" : "rgba(143,211,255,.32)"; const points = new DataView(bytes.buffer); for (let index = 0; index < Math.floor(bytes.byteLength / 16); index += 1) { const x = points.getFloat32(index * 16, true); const y = points.getFloat32(index * 16 + 4, true); const px = canvas.clientWidth / 2 + x * 6; const py = canvas.clientHeight / 2 - y * 6; if (px >= 0 && py >= 0 && px < canvas.clientWidth && py < canvas.clientHeight) context.fillRect(px, py, 1.5, 1.5); } }); if (showTrajectory && trajectory) { context.strokeStyle = "#e6b85c"; trajectory.paths.forEach((path) => { context.beginPath(); path.states.forEach((sample, index) => { const px = canvas.clientWidth / 2 + sample.x_m * 6; const py = canvas.clientHeight / 2 - sample.y_m * 6; if (index === 0) context.moveTo(px, py); else context.lineTo(px, py); }); context.stroke(); }); } if (showActors && evidence.annotations?.available) { context.strokeStyle = "#f27d72"; evidence.annotations.boxes.forEach((box) => { const center = box.translation_m as number[]; if (!center) return; context.strokeRect(canvas.clientWidth / 2 + center[0] * 6 - 3, canvas.clientHeight / 2 - center[1] * 6 - 3, 6, 6); }); } setStatus("ready"); })
      .catch(() => { if (!cancelled) setStatus("payload_unavailable"); });
    return () => { cancelled = true; };
  }, [evidence, decimation, showMap, showTrajectory, showActors, trajectory]);
  if (!evidence || evidence.sweeps.length === 0) return <div className="unavailable-view"><StatusBadge status={status === "loading" ? "loading" : "unavailable"} /><strong>Sensor Evidence unavailable</strong><p>{evidence?.unavailable_reason ?? "Resolving recorded LIDAR_TOP sweeps."}</p></div>;
  const referenceTime = evidence.timestamp_us ? evidence.timestamp_us / 1e6 : undefined;
  const delta = referenceTime === undefined ? undefined : Math.abs(referenceTime - playhead);
   return <div className="lidar-view sensor-evidence-view"><canvas ref={canvasRef} role="img" aria-label={`nuScenes Sensor Evidence view with ${evidence.nsweeps} LIDAR_TOP sweeps`} /><div className="lidar-controls"><label>sweeps <select value={evidence.requested_nsweeps ?? 5} onChange={(event) => onSweeps(Number(event.target.value))}>{[1, 2, 3, 5, 10].map((value) => <option key={value} value={value}>{value}</option>)}</select></label><label>decimation <select value={decimation} onChange={(event) => onDecimation(Number(event.target.value))}><option value="1">1x</option><option value="4">4x</option><option value="8">8x</option><option value="16">16x</option><option value="32">32x</option></select></label><label><input type="checkbox" checked={showMap} onChange={(event) => setShowMap(event.target.checked)} /> map underlay</label><label><input type="checkbox" checked={showTrajectory} onChange={(event) => setShowTrajectory(event.target.checked)} /> trajectory</label><label><input type="checkbox" checked={showActors} onChange={(event) => setShowActors(event.target.checked)} /> recorded boxes</label><StatusBadge status={status === "ready" ? "valid" : status} /><span>{evidence.synchronization.status}</span><span>reference timestamp {evidence.reference?.timestamp_us ?? evidence.timestamp_us ?? MISSING}</span><span>historical sweep smearing expected</span><span>{evidence.can_telemetry.available ? `CAN telemetry aligned (${evidence.can_telemetry.alignment_delta_us ?? 0} us)` : `CAN unavailable: ${evidence.can_telemetry.unavailable_reason ?? MISSING}`}</span><span>{evidence.map_underlay.available ? `map underlay: ${evidence.map_underlay.map_name ?? "available"}` : `map unavailable: ${evidence.map_underlay.unavailable_reason ?? MISSING}`}</span><span>{evidence.annotations?.available ? `${evidence.annotations.boxes.length} recorded boxes` : `annotations unavailable: ${evidence.annotations?.unavailable_reason ?? MISSING}`}</span></div></div>;
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
  return <div className="pov-view" role="img" aria-label={`${frame.mode} simulator frame at ${frame.timestamp_s.toFixed(2)} seconds for playhead ${playhead.toFixed(2)} seconds`}>{imageFrame?.status === "rendered" && imageFrame.artifact ? <img className="pov-artifact" src={apiUrl(`/artifacts/${imageFrame.artifact.path}`)} alt={`${frame.mode} esmini image frame at ${imageFrame.timestamp_s?.toFixed(2)} seconds`} /> : <><div className="pov-horizon" /><div className="pov-road" />{frame.actors.map((actor) => <span key={actor.actor_id} className={`pov-actor${actor.actor_id === "ego" ? " ego" : ""}`} style={{ left: `${50 + ((actor.transform.x_m - Number(camera.x_m)) * 2)}%`, top: `${58 - ((actor.transform.y_m - Number(camera.y_m)) * 2)}%` }} title={`${actor.actor_id} ${actor.actor_type}`} />)}</>}<div className="view-legend"><span>{imageFrame?.status === "rendered" ? "esmini-image-artifact" : frame.simulator}</span><span>{frame.mode}</span><span>playhead t={playhead.toFixed(2)} s</span><span>frame t={imageFrame?.timestamp_s?.toFixed(2) ?? frame.timestamp_s.toFixed(2)} s</span><span>{delta <= 0.001 ? "at playhead" : `nearest frame +${delta.toFixed(2)} s`}</span></div></div>;
}

function TopDownView({ selected, trajectory, timeline, activeTracks, selectedActor, measurement, mode, onSelectActor, hiddenKinds }: { selected: ScenarioSummary | null; trajectory: TrajectoryResponse | null; timeline: number; activeTracks: ActiveTrack[]; selectedActor: string | null; measurement: Measurement | null; mode: string; onSelectActor: (actorId: string) => void; hiddenKinds: string[] }) {
  const [pointCloud, setPointCloud] = useState<"none" | "lidar" | "radar">("lidar");
  const [mapState, setMapState] = useState<import("./api").TopDownState | null>(null);
  const [staticMap, setStaticMap] = useState<TopDownMap | null>(null);
  const [zoom, setZoom] = useState(1);
  const [showRecordedAudit, setShowRecordedAudit] = useState(false);
  useEffect(() => {
    const map = document.querySelector<HTMLElement>(".top-down");
    if (!map) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      setZoom((value) => Math.min(4, Math.max(.5, value * (event.deltaY < 0 ? 1.12 : .89))));
    };
    map.addEventListener("wheel", onWheel, { passive: false });
    return () => map.removeEventListener("wheel", onWheel);
  }, [trajectory, selected?.scenario_id]);
  useEffect(() => {
    const svg = document.querySelector<SVGElement>(".top-down svg");
    if (svg) svg.style.transform = `scale(${zoom})`;
    document.querySelectorAll<SVGGElement>(".top-down .actor-marker").forEach((marker, index) => {
      const track = activeTracks[index]?.track;
      const person = track?.role !== "ego" && /pedestrian|person/i.test(track?.actor_type ?? "");
      marker.classList.toggle("ego", track?.role === "ego");
      marker.classList.toggle("person", person);
      marker.classList.toggle("vehicle", track?.role !== "ego" && !person);
    });
  }, [activeTracks, zoom]);
  // Static geometry depends only on the scenario, so it is fetched once here.
  // Fetching it with every playhead change re-sent ~1.7MB per slider event.
  useEffect(() => {
    if (!selected) { setStaticMap(null); return; }
    let cancelled = false;
    fetchTopDownMap(selected.scenario_id)
      .then((next) => { if (!cancelled) setStaticMap(next); })
      .catch(() => { if (!cancelled) setStaticMap(null); });
    return () => { cancelled = true; };
  }, [selected?.scenario_id]);
  useEffect(() => {
    if (!selected) { setMapState(null); return; }
    let cancelled = false;
    fetchTopDownState(selected.scenario_id, timeline, false).then((next) => { if (!cancelled) setMapState(next); }).catch(() => { if (!cancelled) setMapState(null); });
    return () => { cancelled = true; };
  }, [selected?.scenario_id, timeline]);
  if (!selected) return <div className="canvas-empty">Select an imported scenario</div>;
  if (!trajectory) return <div className="canvas-empty">Loading Top-down view</div>;
  const paths = trajectory.paths.filter((path) => !hiddenKinds.includes(path.path_kind));
  if (paths.length === 0) return <div className="canvas-empty">All trajectory layers are hidden. Re-enable them from Layers.</div>;
  const xs = paths.flatMap((path) => path.states.map((state) => state.x_m));
  const ys = paths.flatMap((path) => path.states.map((state) => state.y_m));
  const minX = Math.min(...xs, 0), maxX = Math.max(...xs, 1), minY = Math.min(...ys, 0), maxY = Math.max(...ys, 1);
  const point = (x: number, y: number) => `${((x - minX) / Math.max(1, maxX - minX)) * 82 + 9},${91 - ((y - minY) / Math.max(1, maxY - minY)) * 80}`;
     const rotation = 0;
     const actorMarkerClass = (track: ActorTrack, isSelected: boolean) => `actor-marker ${track.role === "ego" ? "ego" : /pedestrian|person/i.test(track.actor_type) ? "person" : "vehicle"}${isSelected ? " selected" : ""}`;
    const mapLines: [number, number][][] = Object.values(staticMap?.layers ?? mapState?.map_layers ?? {}).flatMap((layer) => {
      if (!Array.isArray(layer)) return [];
      return layer.flatMap((polygon) => {
        if (!polygon || typeof polygon !== "object") return [];
        const exterior = (polygon as { exterior?: unknown }).exterior;
        return Array.isArray(exterior) ? [exterior.filter((point): point is [number, number] => Array.isArray(point) && point.length >= 2 && typeof point[0] === "number" && typeof point[1] === "number")] : [];
      });
    });
     const mapImage = null;
    return <div className="top-down" aria-busy={!mapState && !staticMap}>{mapImage && <img className="top-down-map" src={mapImage} alt="nuScenes full map underlay" />}{!mapState && !staticMap && <div className="view-loading-overlay"><span className="loading-spinner" aria-hidden="true" />Loading map layers</div>}
     <svg viewBox="0 0 100 100" role="img" aria-label={`Top-down trajectory view at ${timeline.toFixed(2)} seconds`}><g transform={`rotate(${rotation} 50 50)`}>{mapLines.map((line, index) => <polyline key={`map-${index}`} className="native-map-line" points={line.map(([x, y]) => point(x, y)).join(" ")} />)}{paths.map((path) => <polyline key={path.actor_id} className={path.path_kind} points={path.states.map((state) => point(state.x_m, state.y_m)).join(" ")} />)}{mode === "measure" && measurement?.status === "measured" && <line className="measure-line" x1={point(measurement.from.x_m, measurement.from.y_m).split(",")[0]} y1={point(measurement.from.x_m, measurement.from.y_m).split(",")[1]} x2={point(measurement.to.x_m, measurement.to.y_m).split(",")[0]} y2={point(measurement.to.x_m, measurement.to.y_m).split(",")[1]} />}{activeTracks.length === 0 && paths.map((path) => { const state = nearestSample(path.states.map((item) => ({ ...item, acceleration_mps2: null, acceleration_source: null, braking_pressure: null, braking_source: null })), timeline); return state === undefined ? null : <circle key={`fallback-${path.actor_id}`} className="actor-state" cx={point(state.x_m, state.y_m).split(",")[0]} cy={point(state.x_m, state.y_m).split(",")[1]} r="1.2" />; })}{activeTracks.map(({ track, sample }) => sample === undefined ? null : <g key={track.actor_id} className={actorMarkerClass(track, selectedActor === track.actor_id)} onClick={() => onSelectActor(track.actor_id)}><line className="actor-heading" x1={point(sample.x_m, sample.y_m).split(",")[0]} y1={point(sample.x_m, sample.y_m).split(",")[1]} x2={point(sample.x_m + Math.cos(sample.yaw_rad) * 6, sample.y_m + Math.sin(sample.yaw_rad) * 6).split(",")[0]} y2={point(sample.x_m + Math.cos(sample.yaw_rad) * 6, sample.y_m + Math.sin(sample.yaw_rad) * 6).split(",")[1]} /><circle cx={point(sample.x_m, sample.y_m).split(",")[0]} cy={point(sample.x_m, sample.y_m).split(",")[1]} r={track.role === "ego" ? 1.5 : 1.2}><title>{`${track.actor_id} at ${sample.time_s.toFixed(2)} s: speed ${formatChannelValue("speed", sample.speed_mps)}, acceleration ${formatChannelValue("acceleration", sample.acceleration_mps2)}, braking ${formatChannelValue("braking", sample.braking_pressure)}`}</title></circle></g>)}</g></svg>
  </div>;
}

function TimelineSurface({ timeline, gates, error, playhead, durationS, activeTracks, selectedActor, measurement, onSelectActor, onPlayhead, onStep, wasmToggles, onWasmTogglesChange, transport }: { timeline: ActorTimeline | null; gates: GateTimeline | null; error: string | null; playhead: number; durationS: number; activeTracks: ActiveTrack[]; selectedActor: string | null; measurement: Measurement | null; onSelectActor: (actorId: string) => void; onPlayhead: (value: number) => void; onStep: (delta: number) => void; wasmToggles: WasmOverlayToggles; onWasmTogglesChange: (toggles: WasmOverlayToggles) => void; transport: WasmTransportHandle | null }) {
  const [playing, setPlaying] = useState(false);
  const domainStart = gates?.time_domain.start_s ?? timeline?.time_domain.start_s ?? 0;
  const domainEnd = gates?.time_domain.end_s ?? timeline?.time_domain.end_s ?? durationS;
  const span = Math.max(domainEnd - domainStart, 1e-6);
  const egoTrack = timeline?.tracks.find((track) => track.role === "ego") ?? timeline?.tracks[0];
  const totalFrames = timeline ? Math.max(...timeline.tracks.map((track) => track.samples.length), 0) : 0;
  const currentFrame = egoTrack?.samples.length ? Math.min(egoTrack.samples.length, Math.max(1, nearestSampleIndex(egoTrack.samples, playhead) + 1)) : 0;
  useEffect(() => {
    if (!playing || durationS <= 0) return;
    const timer = window.setInterval(() => {
      const next = Math.min(durationS, playhead + PLAYHEAD_STEP_S);
      onPlayhead(next);
      if (next >= durationS) setPlaying(false);
    }, 50);
    return () => window.clearInterval(timer);
  }, [playing, playhead, durationS, onPlayhead]);
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
      <div className="timeline-playback">
        {transport ? <>
          <button className="playhead-play" aria-label={transport.playing ? "Pause 3D playback" : "Play 3D playback"} onClick={transport.toggle} disabled={!transport.ready}>{transport.playing ? "pause 3d" : "play 3d"}</button>
          <button className="playhead-step" aria-label="Step 3D playback one frame" onClick={transport.step} disabled={!transport.ready}>step 3d</button>
          <button className="playhead-step" aria-label="Reset 3D playback" onClick={transport.reset} disabled={!transport.ready}>reset 3d</button>
          <span className="timeline-transport-status" aria-label="3D playback status">3D {transport.status} / t={transport.timeS.toFixed(2)} s / objects={transport.objectCount}</span>
        </> : <span className="timeline-transport-status">no 3D preview mounted</span>}
        <button className="playhead-play" aria-label={playing ? "Pause playback" : "Play frames"} onClick={() => setPlaying((value) => !value)} disabled={durationS === 0}>{playing ? "pause" : "play"}</button>
        <button className="playhead-step" aria-label="Step playhead back" onClick={() => onStep(-PLAYHEAD_STEP_S)} disabled={durationS === 0}>&lt;</button>
        <button className="playhead-step" aria-label="Step playhead forward" onClick={() => onStep(PLAYHEAD_STEP_S)} disabled={durationS === 0}>&gt;</button>
      </div>
      <strong className="timeline-time">playhead {playhead.toFixed(2)} s <span>/ {durationS.toFixed(2)} s</span></strong>
      <span className="frame-counter" aria-label="Frame counter">frame {currentFrame || "-"} / {totalFrames || "-"}</span>
      <input className="playhead-range" aria-label="Playhead" type="range" min={0} max={durationS || 1} step={PLAYHEAD_STEP_S} value={playhead} disabled={durationS === 0} onChange={(event) => onPlayhead(Number(event.target.value))} />
      <span className="timeline-selection" title={selectedActor ? `Selected actor: ${selectedActor}` : "No actor selected"}>selection: {selectedActor ?? "none"}</span>
      <div className="timeline-toggles" aria-label="Timeline overlays">
        <label title="Recorded travel and heading"><input type="checkbox" checked={wasmToggles.paths} onChange={(event) => onWasmTogglesChange({ ...wasmToggles, paths: event.target.checked })} /> paths</label>
        <label title="LIDAR_TOP cloud, synchronized to the playhead"><input type="checkbox" checked={wasmToggles.lidar} onChange={(event) => onWasmTogglesChange({ ...wasmToggles, lidar: event.target.checked })} /> lidar</label>
        <label title="Show exact cuboids instead of actor skins"><input type="checkbox" checked={wasmToggles.cuboids} onChange={(event) => onWasmTogglesChange({ ...wasmToggles, cuboids: event.target.checked })} /> cuboids</label>
      </div>
    </div>
    {error && <p className="timeline-error" role="alert">{error}</p>}
    {!timeline && !error && <p className="timeline-empty">Select an imported scenario to load time-indexed actor tracks.</p>}
    {timeline && <ol className="actor-tracks" aria-label="Actor state tracks">{activeTracks.map(({ track, sample }) => <li key={track.actor_id} className={selectedActor === track.actor_id ? "actor-track selected" : "actor-track"}>
       <button className="track-label" aria-label={track.actor_id} aria-pressed={selectedActor === track.actor_id} onClick={() => onSelectActor(track.actor_id)}><strong>{track.actor_id}</strong><small>{track.role === "ego" ? "ego" : "instance"}</small></button>
       <span className="track-time">{formatTimestamp(sample?.time_s)} s</span>
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

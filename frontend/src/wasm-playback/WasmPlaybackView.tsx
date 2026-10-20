import { useEffect, useRef, useState } from "react";
import type { WasmActorLifecycle, WasmFrame, WasmGround, WasmLidarCloud, WasmLidarSweep, WasmRecordedPath, WasmRoadGeometry, WasmSceneSummary, WasmWorkerResponse, WasmOrbitState, WasmOverlayToggles } from "./types";
import { applyLidarTransform, assertWellFormedXml, decodeLidarPayloadFlat, globalToLocalFrame, nearestSweepAtOrBefore, selectSweepStride, trackWasmActors } from "./types";
import type { LidarRigidTransform } from "./types";
import { createWasmScenarioPair, fetchGroundLayers, fetchLidarSweeps, fetchScenarios, fetchWorkspaceScenario, fetchRecordedAnnotations, lidarPayloadUrl, type RecordedAnnotationTrack } from "../api";
import ThreePlaybackCanvas from "./ThreePlaybackCanvas";
import { ByteBoundedLru, selectSweepWindow } from "./bounded-cache";
import { acquireWasmRuntime, releaseWasmRuntime, type WasmScenarioRuntime } from "./runtime-manager";
import type { WasmTransportHandle } from "./transport";

type Props = { scenarioId?: string; fixture?: "vehicle" | "pedestrian"; mode?: "standalone" | "third-person" | "sensor-evidence"; playhead?: number; toggles?: WasmOverlayToggles; onTogglesChange?: (toggles: WasmOverlayToggles) => void; orbit?: WasmOrbitState; onOrbitChange?: (orbit: WasmOrbitState) => void; isMainView?: boolean; focusActorId?: string | null; showControls?: boolean; vehicleTint?: number; vehicleTints?: Record<string, number>; onTransport?: (handle: WasmTransportHandle | null) => void; onActorPick?: (actorId: string | null) => void };

const FIXTURE_FILES = {
  vehicle: "fixture.xosc",
  pedestrian: "fixture-pedestrian.xosc",
} as const;

/** Fetch an XML artifact with a well-formedness gate, refetching once on
 *  corruption. Multi-MB responses (full-map OpenDRIVE) have been observed
 *  truncated mid-attribute by the dev proxy; without this gate the engine
 *  dies with an opaque C++ `{excPtr}` and zero objects. */
async function fetchArtifactText(url: string, label: string): Promise<string> {
  let lastError: unknown = null;
  for (let attempt = 1; attempt <= 2; attempt++) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 30000);
    const text = await fetch(url, { signal: controller.signal }).then((response) => {
      if (!response.ok) throw new Error(`wasm_${label}_http_${response.status}`);
      return response.text();
    }).finally(() => window.clearTimeout(timeout));
    try {
      assertWellFormedXml(text, label);
      return text;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error(`wasm_${label}_unavailable`);
}

/** The api serializes WASM-pair materialization behind one non-blocking
 *  process lock and answers a second concurrent caller with HTTP 409
 *  `wasm_pair_busy_retry`. React StrictMode double-mounts, and one workspace can
 *  hold several playback views, so a self-inflicted collision is routine. A
 *  single-flight cache plus a bounded retry turns that transient 409 into a
 *  short wait instead of a permanently stuck load. */
const WASM_PAIR_RETRY_LIMIT = 5;
const WASM_PAIR_RETRY_BASE_MS = 250;

const scenarioSources = new Map<string, Promise<{ xosc: string; xodr: string }>>();

const isPairBusy = (error: unknown): boolean =>
  error instanceof Error && error.message.includes("wasm_pair_busy_retry");

const wait = (ms: number): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, ms));

function loadScenarioSource(scenarioId: string, attempt = 0): Promise<{ xosc: string; xodr: string }> {
  const cached = scenarioSources.get(scenarioId);
  if (cached) return cached;
  let pending!: Promise<{ xosc: string; xodr: string }>;
  pending = (async () => {
    try {
      const pair = await createWasmScenarioPair(scenarioId);
      const [xosc, xodr] = await Promise.all([
        fetchArtifactText(pair.openscenario, "xosc"),
        fetchArtifactText(pair.opendrive, "xodr"),
      ]);
      return { xosc, xodr };
    } catch (error) {
      // Only a dropped promise may be evicted; a live one must keep sharing.
      if (scenarioSources.get(scenarioId) === pending) scenarioSources.delete(scenarioId);
      if (isPairBusy(error) && attempt < WASM_PAIR_RETRY_LIMIT) {
        await wait(WASM_PAIR_RETRY_BASE_MS * 2 ** attempt);
        return loadScenarioSource(scenarioId, attempt + 1);
      }
      throw error;
    }
  })();
  scenarioSources.set(scenarioId, pending);
  return pending;
}

const asRigid = (value: { translation_m: number[]; rotation_wxyz: number[] } | undefined): LidarRigidTransform | undefined => {
  if (!value || value.translation_m.length !== 3 || value.rotation_wxyz.length !== 4) return undefined;
  return {
    translation_m: [value.translation_m[0], value.translation_m[1], value.translation_m[2]],
    rotation_wxyz: [value.rotation_wxyz[0], value.rotation_wxyz[1], value.rotation_wxyz[2], value.rotation_wxyz[3]],
  };
};

/** Fetch recorded-travel paths, the play-range sweep list, and the frame
 *  transform. Sweep payloads prefetch separately (effect below) so the cloud
 *  follows the playhead. Display-only: anything missing resolves to null
 *  (checkboxes stay disabled), never an invented overlay. Throws only for
 *  the caller to swallow best-effort. */
async function loadRecordedOverlays(
  scenarioId: string,
  setPaths: (paths: WasmRecordedPath[] | null) => void,
  setSweeps: (
    sweeps: WasmLidarSweep[] | null,
    frame: { originX: number; originY: number; heading: number } | null,
  ) => void,
): Promise<void> {
  const workspace = await fetchWorkspaceScenario(scenarioId);
  const parentId = workspace.scenario.parent_scenario_id;
  const parent = parentId && (await fetchScenarios()).some((scenario) => scenario.scenario_id === parentId)
    ? await fetchWorkspaceScenario(parentId).catch(() => null)
    : null;
  const toPaths = (paths: typeof workspace.paths, role: "origin" | "edited") => paths
    .filter((path) => path.path_kind === "recorded" || path.path_kind === "generated")
    .map((path) => ({
    actor_id: path.actor_id,
    actor_type: path.actor_type,
    role,
    points: path.states.map((state) => ({ x_m: state.x_m, y_m: state.y_m })),
  }));
  setPaths(parent ? [...toPaths(parent.paths, "origin"), ...toPaths(workspace.paths, "edited")] : toPaths(workspace.paths, "origin"));
  const provenance = workspace.scenario?.provenance ?? {};
  const frame = {
    originX: Number(provenance.coordinate_transform_origin_x_m),
    originY: Number(provenance.coordinate_transform_origin_y_m),
    heading: Number(provenance.coordinate_transform_heading_rad),
  };
  if (![frame.originX, frame.originY, frame.heading].every(Number.isFinite)) {
    setSweeps(null, null);
    return;
  }
  const listing = await fetchLidarSweeps(scenarioId);
  const sweeps = Array.isArray(listing.sweeps) ? listing.sweeps : [];
  setSweeps(sweeps.length > 0 ? selectSweepStride(sweeps) : null, sweeps.length > 0 ? frame : null);
}

/** Fetch, decode (full density) and move one sweep into the scenario local
 *  frame. Returns null when the sweep cannot be placed honestly. */
async function fetchSweepCloud(
  sweep: WasmLidarSweep,
  frame: { originX: number; originY: number; heading: number },
  signal?: AbortSignal,
): Promise<WasmLidarCloud | null> {
  const response = await fetch(lidarPayloadUrl(sweep.sample_data_token, 4), { signal });
  if (!response.ok) return null;
  const header = response.headers.get("X-R2S-Lidar-Metadata");
  if (!header) return null;
  const meta = JSON.parse(header) as { timestamp_us?: number; calibration_transform?: { translation_m: number[]; rotation_wxyz: number[] }; ego_pose_transform?: { translation_m: number[]; rotation_wxyz: number[] } };
  const calibration = asRigid(meta.calibration_transform);
  const pose = asRigid(meta.ego_pose_transform);
  if (!calibration || !pose) return null;
  const { count, xyz } = decodeLidarPayloadFlat(new Uint8Array(await response.arrayBuffer()));
  const local = new Float32Array(count * 3);
  for (let index = 0; index < count; index++) {
    const [gx, gy, gz] = applyLidarTransform(
      applyLidarTransform([xyz[index * 3], xyz[index * 3 + 1], xyz[index * 3 + 2]], calibration),
      pose,
    );
    const [lx, ly] = globalToLocalFrame(gx, gy, frame.originX, frame.originY, frame.heading);
    local[index * 3] = lx;
    local[index * 3 + 1] = gz;
    local[index * 3 + 2] = -ly;
  }
  return {
    sample_data_token: sweep.sample_data_token,
    timestamp_us: typeof meta.timestamp_us === "number" ? meta.timestamp_us : sweep.timestamp_us,
    time_s: sweep.time_s,
    point_count: count,
    xyz: local,
  };
}

export default function WasmPlaybackView({ scenarioId, fixture = "vehicle", mode = "standalone", playhead, toggles, onTogglesChange, orbit, onOrbitChange, isMainView = false, focusActorId = null, showControls = false, vehicleTint, vehicleTints, onTransport, onActorPick }: Props) {
  const workerRef = useRef<Worker | null>(null);
  const runtimeRef = useRef<WasmScenarioRuntime | null>(null);
  const [runtimeSnapshot, setRuntimeSnapshot] = useState<ReturnType<WasmScenarioRuntime["getSnapshot"]> | null>(null);
  const [status, setStatus] = useState("loading");
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [scene, setScene] = useState<WasmSceneSummary>({ simulation_time: 0, active_count: 0, ended_count: 0, actors: [] });
  const [playing, setPlaying] = useState(false);
  const [road, setRoad] = useState<WasmRoadGeometry>({ lane_surfaces: [], road_marks: [] });
  const [frame, setFrame] = useState<WasmFrame>({ simulation_time: 0, object_states: [] });
  const [ground, setGround] = useState<WasmGround | null>(null);
  const [paths, setPaths] = useState<WasmRecordedPath[] | null>(null);
  const [recordedTracks, setRecordedTracks] = useState<RecordedAnnotationTrack[]>([]);
  const [lidar, setLidar] = useState<WasmLidarCloud | null>(null);
  const [localToggles, setLocalToggles] = useState<WasmOverlayToggles>({ cuboids: false, paths: false, lidar: mode === "sensor-evidence" });
  const activeToggles = toggles ?? localToggles;
  const updateToggles = (next: WasmOverlayToggles) => { setLocalToggles(next); onTogglesChange?.(next); };
  const lifecycleRef = useRef<Map<number, WasmActorLifecycle>>(new Map());
  const sweepCacheRef = useRef(new ByteBoundedLru<string, WasmLidarCloud>({ maxBytes: 32 * 1024 * 1024, byteSize: (cloud) => cloud.xyz.byteLength }));
  const [lidarSweeps, setLidarSweeps] = useState<WasmLidarSweep[] | null>(null);
  const [lidarFrame, setLidarFrame] = useState<{ originX: number; originY: number; heading: number } | null>(null);
  const [lidarCached, setLidarCached] = useState(0);

  const applyFrame = (next: WasmFrame) => {
    setFrame(next);
    const summary = trackWasmActors(lifecycleRef.current, next);
    lifecycleRef.current = new Map(summary.actors.map((actor) => [actor.id, actor]));
    setScene(summary);
  };

  useEffect(() => {
    if (scenarioId) return;
    let cancelled = false;
    const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    workerRef.current = worker;
    worker.onmessage = (event: MessageEvent<WasmWorkerResponse>) => {
      const message = event.data;
      if (message.type === "error") { setStatus(`error: ${message.message}`); setPlaying(false); return; }
      if (message.type === "ready") { setRoad(message.road); lifecycleRef.current = new Map(); applyFrame(message.frame); setStatus("ready"); return; }
      applyFrame(message.frame);
    };
    const load = async () => {
        setGround(null);
      setPaths(null);
      setRecordedTracks([]);
       sweepCacheRef.current.clear();
      setLidarSweeps(null);
      setLidarFrame(null);
      setLidarCached(0);
      if (!scenarioId) {
        const [xosc, xodr] = await Promise.all([
          fetchArtifactText(new URL(`../wasm-smoke/${FIXTURE_FILES[fixture]}`, import.meta.url).toString(), "xosc"),
          fetchArtifactText(new URL("../wasm-smoke/smoke.xodr", import.meta.url).toString(), "xodr"),
        ]);
        worker.postMessage({ type: "init", xosc, xodr });
        if (cancelled) return;
        setStatus("ready");
        return;
      }
      const { xosc, xodr } = await loadScenarioSource(scenarioId);
      worker.postMessage({ type: "init", xosc, xodr });
      if (cancelled) return;
      // Best-effort context: a missing ground must never break playback.
      fetchGroundLayers(scenarioId)
        .then((json) => { if (cancelled) return; return setGround(
          json !== null && typeof json === "object" && Array.isArray((json as WasmGround).layers)
            ? (json as WasmGround)
            : null,
        ); })
        .catch(() => { if (!cancelled) setGround(null); });
      // Recorded overlays (paths + lidar sweep list): same best-effort rule.
      // Sweep payloads prefetch in the background (effect below) so the cloud
      // can follow the playhead instead of freezing on one static sweep.
      loadRecordedOverlays(
        scenarioId,
        (paths) => { if (!cancelled) setPaths(paths); },
        (sweeps, frame) => { if (!cancelled) { setLidarSweeps(sweeps); setLidarFrame(frame); } },
      ).catch(() => { if (!cancelled) { setPaths(null); setLidarSweeps(null); setLidarFrame(null); } });
    };
    load().catch((error) => { if (!cancelled) setStatus(`error: ${error instanceof Error ? error.message : String(error)}`); });
    return () => { cancelled = true; worker.postMessage({ type: "dispose" }); worker.terminate(); workerRef.current = null; };
  }, [scenarioId, fixture]);

  useEffect(() => {
    if (!scenarioId) return;
    let cancelled = false;
    let key: `scenario:${string}` = `scenario:${scenarioId}`;
    let runtime: WasmScenarioRuntime | null = null;
    const load = async () => {
      const { xosc, xodr } = await loadScenarioSource(scenarioId);
      if (cancelled) return;
      runtime = acquireWasmRuntime(key, { xosc, xodr });
      runtimeRef.current = runtime;
      setRuntimeSnapshot(runtime.getSnapshot());
      const unsubscribe = runtime.subscribe(() => { if (!cancelled) setRuntimeSnapshot(runtime?.getSnapshot() ?? null); });
      loadRecordedOverlays(scenarioId, (paths) => { if (!cancelled) setPaths(paths); }, (sweeps, frame) => { if (!cancelled) { setLidarSweeps(sweeps); setLidarFrame(frame); } }).catch(() => { if (!cancelled) { setPaths(null); setLidarSweeps(null); setLidarFrame(null); } });
      fetchRecordedAnnotations(scenarioId).then((payload) => { if (!cancelled && payload.status !== "unavailable") setRecordedTracks(payload.tracks); }).catch(() => { if (!cancelled) setRecordedTracks([]); });
      fetchGroundLayers(scenarioId).then((json) => { if (!cancelled) setGround(json !== null && typeof json === "object" && Array.isArray((json as WasmGround).layers) ? (json as WasmGround) : null); }).catch(() => { if (!cancelled) setGround(null); });
      return unsubscribe;
    };
    let unsubscribe: (() => void) | undefined;
    setScenarioError(null);
    load().then((cleanup) => { unsubscribe = cleanup; }).catch((error) => {
      if (cancelled) return;
      // Without this the view stayed "loading" forever: displayStatus reads the
      // runtime snapshot, and a failure before the runtime exists leaves no
      // snapshot at all, so the overlay spun with no way to report the cause.
      setScenarioError(error instanceof Error ? error.message : String(error));
    });
    return () => { cancelled = true; unsubscribe?.(); if (runtime) releaseWasmRuntime(key, runtime); runtimeRef.current = null; setRuntimeSnapshot(null); };
  }, [scenarioId]);

  useEffect(() => {
    if (scenarioId) { runtimeRef.current?.send(playing ? "play" : "pause"); return; }
    workerRef.current?.postMessage({ type: playing ? "play" : "pause" });
  }, [playing, scenarioId]);

  const sendPlaybackCommand = (type: "step" | "reset") => {
    setPlaying(false);
    if (scenarioId) runtimeRef.current?.send(type);
    else workerRef.current?.postMessage({ type });
  };

  useEffect(() => {
    const ready = scenarioId ? runtimeSnapshot?.status === "ready" : status === "ready";
    if (playhead === undefined || !ready) return;
    const timer = window.setTimeout(() => {
      if (scenarioId) runtimeRef.current?.send("seek", { time_s: playhead });
      else workerRef.current?.postMessage({ type: "seek", time_s: playhead });
    }, 75);
    return () => window.clearTimeout(timer);
  }, [playhead, status, scenarioId, runtimeSnapshot?.status]);

  // Background prefetch: full-density sweeps arrive oldest-first while the
  // user reviews; each cached sweep re-renders so the cloud can catch up.
  useEffect(() => {
    if (!lidarSweeps?.length || !lidarFrame) return;
    let cancelled = false;
    const controller = new AbortController();
    const inFlight = new Set<string>();
    (async () => {
      const candidateSweeps = selectSweepWindow(lidarSweeps, frame.simulation_time, 5);
      for (const sweep of candidateSweeps) {
        if (cancelled || controller.signal.aborted || sweepCacheRef.current.touch(sweep.sample_data_token) || inFlight.has(sweep.sample_data_token)) continue;
        inFlight.add(sweep.sample_data_token);
        try {
          const cloud = await fetchSweepCloud(sweep, lidarFrame, controller.signal);
          if (cancelled) return;
          if (cloud) {
            sweepCacheRef.current.set(sweep.sample_data_token, cloud);
            setLidarCached((value) => value + 1);
          }
        } catch {
          // Best-effort per sweep: a missing sweep only thins coverage.
        } finally { inFlight.delete(sweep.sample_data_token); }
      }
    })();
    return () => { cancelled = true; controller.abort(); };
  }, [lidarSweeps, lidarFrame, frame.simulation_time]);

  // Playhead-synced cloud: latest cached sweep at or before now. The label
  // always names the sweep time and its delta, so a stale cloud reads stale.
  const displayFrame = scenarioId ? (runtimeSnapshot?.frame ?? frame) : frame;
  const displayRoad = scenarioId ? (runtimeSnapshot?.road ?? road) : road;
  const displayStatus = scenarioId ? (runtimeSnapshot?.status ?? (scenarioError ? `error: ${scenarioError}` : "loading")) : status;

  // Publish transport controls so the shared timeline strip can drive this
  // view. Republished whenever the observable state changes and cleared on
  // unmount so a stale handle cannot outlive the runtime it points at.
  useEffect(() => {
    if (!onTransport) return;
    if (!scenarioId) return;
    onTransport({
      scenarioId,
      ready: displayStatus === "ready",
      playing,
      status: displayStatus,
      timeS: displayFrame.simulation_time,
      objectCount: displayFrame.object_states.length,
      toggle: () => setPlaying((value) => !value),
      step: () => sendPlaybackCommand("step"),
      reset: () => sendPlaybackCommand("reset"),
    });
    return () => onTransport(null);
  }, [onTransport, scenarioId, displayStatus, playing, displayFrame.simulation_time, displayFrame.object_states.length]);

  const activeSweep = lidarSweeps ? nearestSweepAtOrBefore(lidarSweeps, displayFrame.simulation_time) : null;
  const activeCloud = activeToggles.lidar && mode !== "third-person" && activeSweep ? sweepCacheRef.current.get(activeSweep.sample_data_token) ?? null : null;
  const lidarDelta = activeCloud ? displayFrame.simulation_time - activeCloud.time_s : null;

  useEffect(() => {
    if (scenarioId && runtimeSnapshot?.frame) applyFrame(runtimeSnapshot.frame);
  }, [scenarioId, runtimeSnapshot?.frame]);

   return <div className="wasm-playback-view" aria-busy={displayStatus !== "ready"}>
     {displayStatus !== "ready" && <div className="view-loading-overlay"><span className="loading-spinner" aria-hidden="true" />{displayStatus.startsWith("error") ? displayStatus.replace(/^error:\s*/, "") : "Loading playback scene"}</div>}
     <ThreePlaybackCanvas road={displayRoad} frame={displayFrame} ground={ground} showCuboids={activeToggles.cuboids} paths={activeToggles.paths ? paths : null} lidar={activeCloud} recordedTracks={recordedTracks} orbit={orbit} onOrbitChange={onOrbitChange} showResetView={isMainView} focusActorId={focusActorId} vehicleTint={vehicleTint} vehicleTints={vehicleTints} onActorPick={onActorPick} />
    {mode === "standalone" && <fieldset className="wasm-overlay-toggles">
      <legend>Overlays (display-only, recorded data)</legend>
      <label><input type="checkbox" checked={activeToggles.cuboids} onChange={(event) => updateToggles({ ...activeToggles, cuboids: event.target.checked })} /> Exact cuboids instead of skins</label>
      <label title={paths ? `${paths.length} recorded paths` : "Recorded paths unavailable for this source"}>
        <input type="checkbox" checked={activeToggles.paths} disabled={!paths} onChange={(event) => updateToggles({ ...activeToggles, paths: event.target.checked })} /> Recorded travel + heading
      </label>
      <label title={lidarSweeps ? `${lidarCached}/${lidarSweeps.length} sweeps cached${activeCloud ? ` · showing t=${activeCloud.time_s.toFixed(2)}s (Δ${(lidarDelta ?? 0).toFixed(2)}s)` : " · cloud pending"}` : "Recorded sweeps unavailable for this source"}>
        <input type="checkbox" checked={activeToggles.lidar} disabled={!lidarSweeps} onChange={(event) => updateToggles({ ...activeToggles, lidar: event.target.checked })} /> LIDAR_TOP cloud 1x (playhead-synced)
      </label>
    </fieldset>}
     {mode === "standalone" && <div className="wasm-playback-controls">
       <button onClick={() => setPlaying((value) => !value)} disabled={displayStatus !== "ready"}>{playing ? "Pause" : "Play"}</button>
       <button onClick={() => sendPlaybackCommand("step")} disabled={displayStatus !== "ready"}>Step</button>
       <button onClick={() => sendPlaybackCommand("reset")} disabled={displayStatus !== "ready"}>Reset</button>
       <span>WASM {displayStatus} / t={displayFrame.simulation_time.toFixed(2)} s / objects={displayFrame.object_states.length}{scene.ended_count > 0 ? ` / ended=${scene.ended_count}` : ""}</span>
     </div>}
     <small className="wasm-playback-warning">{scenarioId ? "Real scenario playback preview." : fixture === "pedestrian" ? "Synthetic pedestrian-tag fixture (Vehicle + Pedestrian + MiscObject)." : "Synthetic playback fixture."} Browser frames are preview-only and never feed Tier 0 metrics.</small>
   </div>;
}

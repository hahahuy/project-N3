import { useEffect, useMemo, useRef, useState } from "react";
import {
  createCanvasBranch,
  fetchTopDownMap,
  fetchWorkspaceScenario,
  recalculateTestingCarla,
  type CanvasKeyframe,
  type TestingPhysicsResponse,
  type TopDownMap,
  type TrajectoryState,
  type WorkspaceScenario,
} from "./api";
import WasmPlaybackView from "./wasm-playback/WasmPlaybackView";
import type { WasmOverlayToggles } from "./wasm-playback/types";
import type { WasmTransportHandle } from "./wasm-playback/transport";

type Bounds = { minX: number; minY: number; width: number; height: number };

const PHYSICS_RETRY_LIMIT = 4;
const PHYSICS_RETRY_BASE_MS = 200;

/** The visible window over the fitted projection, in viewBox units.
 *
 *  `x`/`y` pan and `size` is the zoom (100 = fitted, smaller = closer). One
 *  object instead of separate pan+zoom so the inverse projection below can
 *  never disagree with the rendered viewBox. */
export type MotionView = { x: number; y: number; size: number };

const MIN_ZOOM = 1;
const MAX_ZOOM = 8;
/** The fitted path is drawn across viewBox 9..91. Keep that region's centre
 *  inside the window so a zoom or drag can never lose the edited path. */
const clampViewAxis = (value: number, size: number): number => Math.min(50, Math.max(50 - size, value));

/** Rings from the canonical map payload, in the same local metric frame as
 *  the keyframes. Same extraction as the Top-down view: each polygon record
 *  carries an `exterior` ring of [x, y] pairs. Never fabricated — an absent
 *  map yields an empty list and the explicit unavailable state. */
function mapRings(map: TopDownMap | null): number[][][] {
  if (!map) return [];
  return Object.values(map.layers ?? {}).flatMap((layer) => {
    if (!Array.isArray(layer)) return [];
    return layer.flatMap((polygon) => {
      if (!polygon || typeof polygon !== "object") return [];
      const exterior = (polygon as { exterior?: unknown }).exterior;
      if (!Array.isArray(exterior)) return [];
      const ring = exterior.filter((point): point is [number, number] => Array.isArray(point) && point.length >= 2 && typeof point[0] === "number" && typeof point[1] === "number");
      return ring.length >= 2 ? [ring] : [];
    });
  });
}

/** Invert `project()` from a client-space point.
 *
 *  The canvas has a square `viewBox` but a non-square element box, and the
 *  default `preserveAspectRatio="xMidYMid meet"` letterboxes it. Dividing
 *  clientX by the element width therefore ignored the offset and the uniform
 *  scale, so a drag landed somewhere other than the cursor. Recomputing the
 *  letterbox from the measured rect keeps the inverse exact. */
export function clientToWorld(clientX: number, clientY: number, bounds: Bounds, view: MotionView = { x: 0, y: 0, size: 100 }): { x: number; y: number } | null {
  const svg = document.querySelector<SVGSVGElement>("svg.motion-canvas");
  if (!svg) return null;
  const rect = svg.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return null;
  const scale = Math.min(rect.width / view.size, rect.height / view.size);
  const offsetX = (rect.width - view.size * scale) / 2;
  const offsetY = (rect.height - view.size * scale) / 2;
  // Client coords are relative to the panned/zoomed window, not to the fitted
  // projection, so both the window origin and its size must be undone here.
  const viewX = view.x + (clientX - rect.left - offsetX) / scale;
  const viewY = view.y + (clientY - rect.top - offsetY) / scale;
  return {
    x: bounds.minX + ((viewX - 9) / 82) * bounds.width,
    y: bounds.minY + ((91 - viewY) / 80) * bounds.height,
  };
}

export const MOTION_GUARDRAILS = {
  minimumKeyframeIntervalS: 0.25,
  maximumSpeedMps: 20,
  maximumAccelerationMps2: 5,
  maximumBrakingMps2: 8,
  maximumYawRateRps: 2.5,
  maximumTurnAngleRad: 2,
} as const;

export function physicalYawDelta(current: number, previous: number): number {
  const raw = current - previous;
  if (Math.abs(Math.abs(raw) - 2 * Math.PI) < 1e-6) return raw;
  return Math.atan2(Math.sin(raw), Math.cos(raw));
}

export function sampleOriginTrajectory(states: TrajectoryState[], timeS: number): CanvasKeyframe {
  const rightIndex = Math.min(states.length - 1, Math.max(1, states.findIndex((state) => state.time_s >= timeS)));
  const right = states[rightIndex] ?? states[states.length - 1];
  const left = states[Math.max(0, rightIndex - 1)] ?? right;
  const fraction = (timeS - left.time_s) / Math.max(1e-6, right.time_s - left.time_s);
  return {
    keyframe_id: `canvas-kf-${Math.round(timeS * 1000)}`,
    time_s: timeS,
    x_m: left.x_m + (right.x_m - left.x_m) * fraction,
    y_m: left.y_m + (right.y_m - left.y_m) * fraction,
    yaw_rad: left.yaw_rad + physicalYawDelta(right.yaw_rad, left.yaw_rad) * fraction,
    speed_mps: left.speed_mps + (right.speed_mps - left.speed_mps) * fraction,
  };
}

export function originKeyframes(states: TrajectoryState[]): CanvasKeyframe[] {
  if (states.length < 2) return [];
  const stride = Math.max(1, Math.floor(states.length / 4));
  return states
    .filter((_, index) => index === 0 || index === states.length - 1 || index % stride === 0)
    .map((state, index) => ({
      keyframe_id: `origin-kf-${index + 1}`,
      time_s: state.time_s,
      x_m: state.x_m,
      y_m: state.y_m,
      yaw_rad: state.yaw_rad,
      speed_mps: state.speed_mps,
    }));
}

export function interpolateKeyframes(keyframes: CanvasKeyframe[], durationS: number, stepS = 0.05): CanvasKeyframe[] {
  if (keyframes.length < 2) return keyframes;
  return Array.from({ length: Math.floor(durationS / stepS) + 1 }, (_, index) => {
    const timeS = Math.min(durationS, index * stepS);
    const rightIndex = Math.min(keyframes.length - 1, Math.max(1, keyframes.findIndex((point) => point.time_s >= timeS)));
    const right = keyframes[rightIndex];
    const left = keyframes[Math.max(0, rightIndex - 1)];
    const fraction = right === left ? 0 : (timeS - left.time_s) / Math.max(1e-6, right.time_s - left.time_s);
    return {
      keyframe_id: `sample-${index}`,
      time_s: timeS,
      x_m: left.x_m + (right.x_m - left.x_m) * fraction,
      y_m: left.y_m + (right.y_m - left.y_m) * fraction,
      yaw_rad: left.yaw_rad + physicalYawDelta(right.yaw_rad, left.yaw_rad) * fraction,
      speed_mps: left.speed_mps + (right.speed_mps - left.speed_mps) * fraction,
    };
  });
}

export function validateKeyframes(keyframes: CanvasKeyframe[], origin: CanvasKeyframe[], durationS: number): string[] {
  const errors: string[] = [];
  const first = keyframes[0];
  const source = origin[0];
  if (!first || !source || Math.abs(first.x_m - source.x_m) > 1e-6 || Math.abs(first.y_m - source.y_m) > 1e-6 || Math.abs(physicalYawDelta(first.yaw_rad, source.yaw_rad)) > 1e-6) errors.push("The first keyframe must remain at the origin pose.");
  if (keyframes[keyframes.length - 1]?.time_s > durationS) errors.push("Keyframe time must not exceed the origin duration.");
  keyframes.forEach((point) => { if (point.speed_mps > MOTION_GUARDRAILS.maximumSpeedMps) errors.push(`Speed must stay at or below ${MOTION_GUARDRAILS.maximumSpeedMps.toFixed(1)} m/s.`); });
  for (let index = 1; index < keyframes.length; index += 1) {
    const previous = keyframes[index - 1];
    const current = keyframes[index];
    const dt = current.time_s - previous.time_s;
    if (dt < MOTION_GUARDRAILS.minimumKeyframeIntervalS) errors.push(`Keyframe ${index + 1} is too close in time; the gap is ${dt.toFixed(4)}s but the minimum is ${MOTION_GUARDRAILS.minimumKeyframeIntervalS.toFixed(2)}s.`);
    const acceleration = (current.speed_mps - previous.speed_mps) / Math.max(dt, 1e-6);
    if (acceleration > MOTION_GUARDRAILS.maximumAccelerationMps2) errors.push(`Acceleration exceeds the ${MOTION_GUARDRAILS.maximumAccelerationMps2.toFixed(1)} m/s2 guardrail.`);
    if (-acceleration > MOTION_GUARDRAILS.maximumBrakingMps2) errors.push(`Braking exceeds the ${MOTION_GUARDRAILS.maximumBrakingMps2.toFixed(1)} m/s2 guardrail.`);
    if (Math.abs(physicalYawDelta(current.yaw_rad, previous.yaw_rad)) / Math.max(dt, 1e-6) > MOTION_GUARDRAILS.maximumYawRateRps) errors.push(`Yaw rate exceeds the ${MOTION_GUARDRAILS.maximumYawRateRps.toFixed(2)} rad/s guardrail.`);
    if (index + 1 < keyframes.length && Math.abs(physicalYawDelta(keyframes[index + 1].yaw_rad, previous.yaw_rad)) > MOTION_GUARDRAILS.maximumTurnAngleRad) errors.push(`Turn angle exceeds the ${MOTION_GUARDRAILS.maximumTurnAngleRad.toFixed(2)} rad guardrail.`);
  }
  return [...new Set(errors)];
}

type Props = {
  scenarioId: string | null;
  actorId: string | null;
  /** Overlay toggles and playhead are owned by App so Scenario studio and
   *  Variant studio drive the same preview state from the same timeline strip. */
  wasmToggles: WasmOverlayToggles;
  onWasmTogglesChange: (toggles: WasmOverlayToggles) => void;
  playhead: number;
  onPlayheadChange: (value: number) => void;
  onTransportChange: (handle: WasmTransportHandle | null) => void;
  onGuardrailsChange: (violations: string[]) => void;
  /** Lets App refresh the catalog so the new branch appears in the tree. */
  onBranchCommitted: (scenarioId: string) => void;
};

/** Convert an internal-physics trace into committable keyframes.
 *
 *  The exported XOSC must show the path the follower actually drove, not the
 *  straight-line interpolation the user drew between handles. The trace arrives
 *  at the solver timestep (0.05 s), which is below the authoring minimum, so it
 *  is decimated to the minimum keyframe interval and anchored to keep the first
 *  and last samples. */
export function traceToKeyframes(trace: TrajectoryState[], actorId: string, durationS: number): CanvasKeyframe[] {
  if (trace.length === 0) return [];
  const step = Math.max(MOTION_GUARDRAILS.minimumKeyframeIntervalS, 0.05);
  const lastTraceTime = trace[trace.length - 1]!.time_s;

  // Anchor a uniform grid on both ends: it must start at 0 and finish exactly
  // on the origin duration, with every interval at or above the minimum.
  //
  // A fixed grid that ran 0, 0.25, 0.50, ... and then force-appended the final
  // sample always produced a short final interval whenever the duration was not
  // a whole multiple of the step, which is the normal case for nuScenes:
  // 19.4995698928833 s became 79 keyframes whose last gap was 0.2496 s, and the
  // authoring guard rejected the whole commit with "Keyframe 79 is too close in
  // time". Choosing the count first makes the spacing the safe quantity.
  const span = Math.max(step, Math.max(durationS, lastTraceTime));
  let count = Math.floor(span / step) + 1;
  while (count > 2 && span / (count - 1) < step) count -= 1;
  const spacing = span / Math.max(1, count - 1);

  const points: CanvasKeyframe[] = [];
  for (let index = 0; index < count; index += 1) {
    const time = index === count - 1 ? span : index * spacing;
    const state = sampleTraceAt(trace, time);
    points.push({
      keyframe_id: `physics-kf-${index + 1}`,
      time_s: time,
      x_m: state.x_m,
      y_m: state.y_m,
      yaw_rad: state.yaw_rad,
      speed_mps: state.speed_mps,
    });
  }

  // The decimated polyline is coarser than the 0.05 s solver trace, so the yaw
  // carried over from the trace no longer matches the direction of travel across
  // the polyline we actually export. Re-derive every interior heading from the
  // average of its incoming and outgoing segments so the nose lies along the
  // exported curve, and unwrap it so crossing +/-pi stays continuous instead of
  // flipping the whole car around.
  const headings = points.map((point, index) => {
    const previous = points[index - 1];
    const next = points[index + 1];
    const incoming = previous ? unitVector(point.x_m - previous.x_m, point.y_m - previous.y_m) : null;
    const outgoing = next ? unitVector(next.x_m - point.x_m, next.y_m - point.y_m) : null;
    if (incoming && outgoing) return Math.atan2(incoming.y + outgoing.y, incoming.x + outgoing.x);
    const single = outgoing ?? incoming;
    return single ? Math.atan2(single.y, single.x) : point.yaw_rad;
  });
  points.forEach((point, index) => {
    if (index === 0) return;
    point.yaw_rad = unwrapAngle(headings[index]!, point.yaw_rad);
  });
  void actorId;
  return points;
}

/** Linear interpolation of the trace at an arbitrary time, clamped to its span. */
function sampleTraceAt(trace: TrajectoryState[], time: number): TrajectoryState {
  const first = trace[0]!;
  const last = trace[trace.length - 1]!;
  if (time <= first.time_s) return first;
  if (time >= last.time_s) return last;
  let low = 0;
  let high = trace.length - 1;
  while (high - low > 1) {
    const mid = (low + high) >> 1;
    if (trace[mid]!.time_s <= time) low = mid;
    else high = mid;
  }
  const left = trace[low]!;
  const right = trace[high]!;
  const fraction = (time - left.time_s) / Math.max(1e-9, right.time_s - left.time_s);
  return {
    time_s: time,
    x_m: left.x_m + (right.x_m - left.x_m) * fraction,
    y_m: left.y_m + (right.y_m - left.y_m) * fraction,
    yaw_rad: left.yaw_rad + physicalYawDelta(right.yaw_rad, left.yaw_rad) * fraction,
    speed_mps: left.speed_mps + (right.speed_mps - left.speed_mps) * fraction,
  };
}

function unitVector(dx: number, dy: number): { x: number; y: number } | null {
  const length = Math.hypot(dx, dy);
  return length > 1e-9 ? { x: dx / length, y: dy / length } : null;
}

/** Shift `angle` by whole turns so it stays within half a turn of `reference`. */
function unwrapAngle(angle: number, reference: number): number {
  let result = angle;
  while (result - reference > Math.PI) result -= 2 * Math.PI;
  while (reference - result > Math.PI) result += 2 * Math.PI;
  return result;
}

export default function VariantMotionEditor({ scenarioId, actorId, wasmToggles, onWasmTogglesChange, playhead, onPlayheadChange, onTransportChange, onGuardrailsChange, onBranchCommitted }: Props) {
  const [originScenarioId, setOriginScenarioId] = useState(scenarioId);
  const [selectedActorId, setSelectedActorId] = useState(actorId);
  const [workspace, setWorkspace] = useState<WorkspaceScenario | null>(null);
  const [mapData, setMapData] = useState<TopDownMap | null>(null);
  const [view, setView] = useState<MotionView>({ x: 0, y: 0, size: 100 });
  const panRef = useRef<{ pointerId: number; originX: number; originY: number; startX: number; startY: number; viewSize: number } | null>(null);
  const [origin, setOrigin] = useState<CanvasKeyframe[]>([]);
  const [edited, setEdited] = useState<CanvasKeyframe[]>([]);
  const [duration, setDuration] = useState(0);
  const [selectedIndex, setSelectedIndex] = useState(1);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [commitState, setCommitState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [physicsState, setPhysicsState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [physicsResult, setPhysicsResult] = useState<TestingPhysicsResponse | null>(null);
  const [message, setMessage] = useState("");
  const [dirty, setDirty] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const physicsTimerRef = useRef<number | undefined>(undefined);
  const physicsRunningRef = useRef(false);
  const physicsJobRef = useRef<{ scenarioId: string; actorId: string; keyframes: CanvasKeyframe[] } | null>(null);
  const dragRef = useRef<{ index: number; pointerId: number } | null>(null);
  const dragBoundsRef = useRef<Bounds>({ minX: 0, minY: 0, width: 1, height: 1 });
  const dragViewRef = useRef<MotionView>({ x: 0, y: 0, size: 100 });
  const panBoundsRef = useRef(1);

  useEffect(() => { setOriginScenarioId(scenarioId); setSelectedActorId(actorId); }, [scenarioId, actorId]);
  useEffect(() => {
    if (!originScenarioId || !selectedActorId) return;
    let cancelled = false;
    setView({ x: 0, y: 0, size: 100 }); setBranchId(null); setCommitState("idle"); setPhysicsState("idle"); setPhysicsResult(null); setMessage(""); onPlayheadChange(0); setDirty(false);
    fetchWorkspaceScenario(originScenarioId).then((next) => {
      if (cancelled) return;
      const actor = next.actors.find((item) => item.actor_id === selectedActorId) ?? next.actors[0];
      const keyframes = originKeyframes(actor?.states ?? []);
      setWorkspace(next); setOrigin(keyframes); setEdited(keyframes); setDuration(next.scenario.duration_s); setSelectedIndex(keyframes.length > 1 ? 1 : 0); setSelectedActorId(actor?.actor_id ?? selectedActorId);
    }).catch((error: Error) => { if (!cancelled) setMessage(error.message); });
    return () => { cancelled = true; };
  }, [originScenarioId, selectedActorId]);

  useEffect(() => {
    if (!originScenarioId) { setMapData(null); return; }
    let cancelled = false;
    fetchTopDownMap(originScenarioId)
      .then((map) => { if (!cancelled) setMapData(map); })
      .catch(() => { if (!cancelled) setMapData(null); });
    return () => { cancelled = true; };
  }, [originScenarioId]);

  // The api serializes internal physics behind one non-blocking process lock
  // and answers a concurrent caller with 409 `testing_physics_busy_retry`.
  // Aborting the fetch did NOT help: the abort only drops the client side, the
  // worker subprocess keeps running and keeps holding the lock, so the next
  // debounced call collided and flipped the panel to "error" mid-drag. Instead
  // there is now exactly one request in flight, later edits coalesce into the
  // newest draft, and a busy reply is retried with backoff.
  // React attaches onWheel as a passive listener, so preventDefault there is
  // ignored and the page scrolls instead of the canvas zooming. A native
  // non-passive listener is the only way to own the gesture.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (event: WheelEvent) => { event.preventDefault(); zoomAtClientPoint(event); };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, []);

  const schedulePhysics = () => {
    if (!dirty || edited.length < 2 || !originScenarioId || !selectedActorId) return;
    physicsJobRef.current = { scenarioId: originScenarioId, actorId: selectedActorId, keyframes: edited };
    window.clearTimeout(physicsTimerRef.current);
    physicsTimerRef.current = window.setTimeout(() => { void pumpPhysics(); }, 500);
  };
  useEffect(() => { schedulePhysics(); return () => window.clearTimeout(physicsTimerRef.current); }, [dirty, edited, originScenarioId, selectedActorId]);

  async function pumpPhysics() {
    if (physicsRunningRef.current) return;
    const job = physicsJobRef.current;
    if (!job) return;
    physicsRunningRef.current = true;
    physicsJobRef.current = null;
    setPhysicsState("loading");
    try {
      let result: TestingPhysicsResponse | null = null;
      for (let attempt = 0; attempt <= PHYSICS_RETRY_LIMIT; attempt += 1) {
        try {
          result = await recalculateTestingCarla(job.scenarioId, { actor_id: job.actorId, keyframes: job.keyframes, coordinate_frame: "local_road_aligned", seed: 0 });
          break;
        } catch (error) {
          if (error instanceof Error && error.message.includes("testing_physics_busy_retry") && attempt < PHYSICS_RETRY_LIMIT) {
            await new Promise((resolve) => window.setTimeout(resolve, PHYSICS_RETRY_BASE_MS * 2 ** attempt));
            continue;
          }
          throw error;
        }
      }
      setPhysicsResult(result);
      setPhysicsState("ready");
    } catch {
      setPhysicsResult(null);
      setPhysicsState("error");
    } finally {
      physicsRunningRef.current = false;
      // Edits that landed while this run was in flight collapse into one rerun.
      if (physicsJobRef.current) void pumpPhysics();
    }
  }

  const draft = useMemo(() => interpolateKeyframes(edited, duration), [edited, duration]);
  const bounds = useMemo(() => {
    const points = [...origin, ...draft, ...(physicsResult?.trace ?? [])];
    const xs = points.map((point) => point.x_m), ys = points.map((point) => point.y_m);
    const minX = Math.min(...xs, 0) - 1, maxX = Math.max(...xs, 1) + 1, minY = Math.min(...ys, 0) - 1, maxY = Math.max(...ys, 1) + 1;
    return { minX, minY, width: Math.max(1, maxX - minX), height: Math.max(1, maxY - minY) };
  }, [origin, draft, physicsResult]);
  const project = (x: number, y: number) => `${((x - bounds.minX) / bounds.width) * 82 + 9},${91 - ((y - bounds.minY) / bounds.height) * 80}`;
  const selected = edited[selectedIndex] ?? edited[0];
  const violations = useMemo(() => validateKeyframes(edited, origin, duration), [edited, origin, duration]);
  useEffect(() => { onGuardrailsChange(violations); }, [violations, onGuardrailsChange]);

  const rings = useMemo(() => mapRings(mapData), [mapData]);
  const mapAvailable = rings.length > 0;
  const wasmAvailable = typeof Worker !== "undefined" && !/jsdom/i.test(typeof navigator === "undefined" ? "" : navigator.userAgent);

  function startPan(event: React.PointerEvent<SVGSVGElement>) {
    if (dragRef.current) return;
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const scale = Math.min(rect.width / view.size, rect.height / view.size);
    panRef.current = { pointerId: event.pointerId, originX: view.x, originY: view.y, startX: event.clientX, startY: event.clientY, viewSize: view.size };
    // viewBox units travelled per client pixel at the current zoom.
    panBoundsRef.current = 1 / scale;
    event.preventDefault();
  }
  function moveKeyframe(index: number, event: React.PointerEvent<SVGCircleElement>) {
    if (index === 0 || index === edited.length - 1) return;
    // Capture is an optimisation (it keeps the gesture alive outside the
    // handle), not a requirement: it throws NotFoundError for a pointer id the
    // element no longer owns, and that exception would abort the rest of this
    // handler and leave the drag dead before it started. Pointermove bubbles
    // from the handle to the svg either way, so the drag still tracks.
    try { event.currentTarget.setPointerCapture?.(event.pointerId); } catch { /* capture unavailable */ }
    dragRef.current = { index, pointerId: event.pointerId };
    // Freeze the projection for the whole gesture. `bounds` is fitted from the
    // edited path itself, so recomputing it mid-drag moved the mapping under
    // the cursor and the keyframe chased the pointer instead of following it.
    dragBoundsRef.current = bounds;
    dragViewRef.current = view;
    setSelectedIndex(index);
  }
  function dragKeyframe(event: React.PointerEvent<SVGSVGElement>) {
    const panDrag = panRef.current;
    if (panDrag && panDrag.pointerId === event.pointerId) {
      // Pan the view instead of moving a keyframe: the delta is expressed in
      // viewBox units so the map tracks the cursor at any element size.
      const units = panBoundsRef.current;
      const size = panDrag.viewSize;
      const nextX = panDrag.originX - (event.clientX - panDrag.startX) * units;
      const nextY = panDrag.originY - (event.clientY - panDrag.startY) * units;
      setView({ x: clampViewAxis(nextX, size), y: clampViewAxis(nextY, size), size });
      return;
    }
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const world = clientToWorld(event.clientX, event.clientY, dragBoundsRef.current, dragViewRef.current);
    if (!world) return;
    setEdited((current) => current.map((point, pointIndex) => pointIndex === drag.index ? { ...point, x_m: world.x, y_m: world.y } : point));
    setDirty(true);
  }
  function endKeyframeDrag(event: React.PointerEvent<SVGSVGElement>) {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null;
    if (panRef.current?.pointerId === event.pointerId) panRef.current = null;
  }
  function zoomAtClientPoint(event: { clientX: number; clientY: number; deltaY: number }) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const scale = Math.min(rect.width / view.size, rect.height / view.size);
    const offsetX = (rect.width - view.size * scale) / 2;
    const offsetY = (rect.height - view.size * scale) / 2;
    // Keep the point under the cursor fixed while the window resizes.
    const anchorX = view.x + (event.clientX - rect.left - offsetX) / scale;
    const anchorY = view.y + (event.clientY - rect.top - offsetY) / scale;
    const factor = event.deltaY < 0 ? 1 / 1.15 : 1.15;
    // Functional update: several wheel events can land in one frame, and
    // reading `view` from the closure would apply the same step to all of them.
    setView((current) => {
      const size = Math.min(100 / MIN_ZOOM, Math.max(100 / MAX_ZOOM, current.size * factor));
      const ratio = size / current.size;
      return {
        x: clampViewAxis(anchorX - (anchorX - current.x) * ratio, size),
        y: clampViewAxis(anchorY - (anchorY - current.y) * ratio, size),
        size,
      };
    });
  }
  function onCanvasKeyDown(event: React.KeyboardEvent<SVGSVGElement>) {
    if (event.key !== "Delete" && event.key !== "Backspace") return;
    event.preventDefault();
    deleteKeyframe();
  }
  function addKeyframe() {
    let bestIndex = -1, bestSpan = 0;
    for (let index = 0; index + 1 < edited.length; index += 1) { const span = edited[index + 1].time_s - edited[index].time_s; if (span >= 2 * MOTION_GUARDRAILS.minimumKeyframeIntervalS && span > bestSpan) { bestIndex = index; bestSpan = span; } }
    if (bestIndex < 0) return;
    const timeS = (edited[bestIndex].time_s + edited[bestIndex + 1].time_s) / 2;
    const actor = workspace?.actors.find((item) => item.actor_id === selectedActorId);
    const next = sampleOriginTrajectory(actor?.states ?? [], timeS);
    setEdited((current) => [...current, next].sort((a, b) => a.time_s - b.time_s)); setSelectedIndex(bestIndex + 1); setDirty(true);
  }
  function deleteKeyframe() { if (selectedIndex === 0 || selectedIndex === edited.length - 1 || edited.length <= 2) return; setEdited((current) => current.filter((_, index) => index !== selectedIndex)); setSelectedIndex((index) => Math.max(1, index - 1)); setDirty(true); }
  function commit() {
    // Commit what the follower actually drives. The internal physics trace is
    // the path the vehicle simulates; baking the drawn keyframes instead would
    // export a straight-line interpolation the simulator never reproduces.
    const solverTrace = physicsResult?.trace ?? [];
    const committed = solverTrace.length >= 2 ? traceToKeyframes(solverTrace, selectedActorId ?? "", duration) : edited;
    const usingSolver = committed !== edited;
    const errors = validateKeyframes(committed, origin, duration);
    if (errors.length || !originScenarioId || !selectedActorId) { setCommitState("error"); setMessage(errors.join(" ") || "Select an actor before committing."); return; }
    if (committed.length < 2) { setCommitState("error"); setMessage("Run the internal physics check before committing so the exported path follows the solver."); return; }
    setCommitState("loading"); setMessage("");
    createCanvasBranch(originScenarioId, { actor_id: selectedActorId, keyframes: committed, coordinate_frame: "local_road_aligned", branch_name: usingSolver ? "Internal physics motion edit" : "Canvas motion edit", seed: 0, include_origin_reference: true })
      .then((result) => { if (!result.validation.valid) throw new Error(result.validation.reasons.map((reason) => reason.message).join(" ")); setBranchId(result.scenario.scenario_id); onBranchCommitted(result.scenario.scenario_id); setCommitState("success"); setDirty(false); setMessage(usingSolver ? "Branch created from the internal physics path. Parent remains immutable." : "Branch created. Parent scenario remains immutable."); })
      .catch((error: Error) => { setCommitState("error"); setMessage(error.message); });
  }

  if (!originScenarioId || !selectedActorId) return <section className="motion-editor" role="region" aria-label="Variant studio"><div className="empty-view"><strong>Variant studio</strong><span>Select an actor in Scenario studio, then choose Edit motion.</span></div></section>;
  return <section className="motion-editor" role="region" aria-label="Variant studio">
    <div className="motion-editor-grid">
      <div className="motion-canvas-card">{!mapAvailable && <div className="motion-map-unavailable">Map geometry unavailable for this scenario. No map is fabricated.</div>}<svg ref={svgRef} className="motion-canvas" viewBox={`${view.x} ${view.y} ${view.size} ${view.size}`} role="application" tabIndex={0} aria-label="Editable top-down motion editor. Drag a keyframe to move it, drag the background to pan the map, use the wheel to zoom, press Delete to remove the selected keyframe." onPointerDown={startPan} onPointerMove={dragKeyframe} onPointerUp={endKeyframeDrag} onPointerCancel={endKeyframeDrag} onKeyDown={onCanvasKeyDown}>{rings.length > 0 && <g className="motion-map-geometry">{rings.map((ring, index) => <polyline key={index} points={ring.map(([x, y]) => project(x, y)).join(" ")} />)}</g>}{workspace?.actors.filter((actor) => actor.actor_id !== selectedActorId).map((actor) => { const state = actor.states[0]; if (!state) return null; const [x, y] = project(state.x_m, state.y_m).split(","); return <rect key={actor.actor_id} className="motion-obstacle" x={Number(x) - 1.5} y={Number(y) - 1} width="3" height="2" transform={`rotate(${(-state.yaw_rad * 180) / Math.PI} ${x} ${y})`}><title>{actor.actor_id} non-editable obstacle</title></rect>; })}<polyline className="motion-origin-path" points={origin.map((point) => project(point.x_m, point.y_m)).join(" ")} /><polyline className="motion-edited-path" points={draft.map((point) => project(point.x_m, point.y_m)).join(" ")} />{physicsResult && <polyline className="motion-physics-path" points={physicsResult.trace.map((point) => project(point.x_m, point.y_m)).join(" ")} />}{edited.map((point, index) => { const [cx, cy] = project(point.x_m, point.y_m).split(","); return <circle key={point.keyframe_id} className={`motion-keyframe${index === 0 || index === edited.length - 1 ? " locked" : ""}${index === selectedIndex ? " selected" : ""}`} cx={cx} cy={cy} r={index === selectedIndex ? 1.4 : 1} onPointerDown={(event) => moveKeyframe(index, event)} onClick={() => setSelectedIndex(index)}><title>{`keyframe ${index + 1}, t=${point.time_s.toFixed(2)}s${index === 0 ? ", locked origin" : index === edited.length - 1 ? ", locked horizon" : ""}`}</title></circle>; })}</svg><div className="motion-canvas-tools"><button type="button" className="motion-add-keyframe" aria-label="Add keyframe" title="Add keyframe at the midpoint of the widest valid interval" onClick={addKeyframe}>+</button><span className="motion-zoom-readout">zoom {Math.round(100 / view.size * 100) / 100}x</span></div><div className="motion-legend"><span><i className="origin" /> origin</span><span><i className="edited" /> edited</span><span><i className="obstacle" /> obstacle</span><span><i className="physics" /> internal physics</span><span>physics: {physicsState}</span></div></div>
      <aside className="motion-controls"><section className="motion-panel"><span className="section-kicker">EDIT OBJECT</span><h2>{selectedActorId}</h2><p>Only this actor is editable. First pose and origin horizon are locked.</p>{selected && <label>Velocity <output>{selected.speed_mps.toFixed(2)} m/s</output><input aria-label="Velocity" type="range" min="0" max={MOTION_GUARDRAILS.maximumSpeedMps} step="0.1" value={selected.speed_mps} disabled={selectedIndex === 0 || selectedIndex === edited.length - 1} onChange={(event) => { const speed = Number(event.target.value); setEdited((current) => current.map((point, index) => index === selectedIndex ? { ...point, speed_mps: speed } : point)); setDirty(true); }} /></label>}<button className="secondary" onClick={commit} disabled={commitState === "loading"}>{commitState === "loading" ? "Creating branch..." : "Commit branch"}</button>{message && <p className={`motion-message ${commitState}`} role="status">{message}</p>}</section><section className="motion-panel"><span className="section-kicker">WASM 3D PREVIEW</span>{wasmAvailable ? <WasmPlaybackView scenarioId={branchId ?? originScenarioId} mode="third-person" playhead={playhead} toggles={wasmToggles} onTransport={onTransportChange} vehicleTints={{ [selectedActorId]: 0xff8a3d, [`${selectedActorId}-origin-reference`]: 0x4f8cff }} /> : <div className="unavailable-view"><strong>WASM preview unavailable</strong><p>Browser worker runtime is unavailable in this environment.</p></div>}<div className="motion-status"><span>origin/reference: blue</span><span>edited: orange</span><span>obstacle bbox: red/pink</span><span>duration: {duration.toFixed(2)}s</span><span>collision count: {physicsResult?.collision_count ?? 0}</span></div></section></aside>
    </div>
  </section>;
}

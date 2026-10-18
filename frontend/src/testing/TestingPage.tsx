import { useEffect, useMemo, useRef, useState } from "react";
import { createCanvasBranch, fetchScenarios, fetchWorkspaceScenario, recalculateTestingCarla, type ScenarioSummary, type TestingPhysicsResponse } from "../api";
import WasmPlaybackView from "../wasm-playback/WasmPlaybackView";

type Point = { t: number; x: number; y: number; yaw: number; speed: number };
type Bounds = { minX: number; minY: number; width: number; height: number };

const DEFAULT_DURATION = 6;
const DT = 0.05;
const MIN_KEYFRAME_INTERVAL = 0.25;
const MAX_KEYFRAME_SPEED = 20;
const MAX_ACCELERATION = 5;
const MAX_DECELERATION = 8;
const MAX_YAW_RATE = 2.5;
const MAX_TURN_ANGLE = 2.0;

export default function TestingPage() {
  const [originKeyframes, setOriginKeyframes] = useState<Point[]>(initialKeyframes);
  const [keyframes, setKeyframes] = useState<Point[]>(initialKeyframes);
  const [originScenarioId, setOriginScenarioId] = useState("synthetic-variant-001");
  const [originActorId, setOriginActorId] = useState("lead");
  const [originScenarios, setOriginScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedKeyframe, setSelectedKeyframe] = useState(1);
  const [playhead, setPlayhead] = useState(0);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [commitState, setCommitState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [commitMessage, setCommitMessage] = useState("");
  const [wasmLoading, setWasmLoading] = useState(false);
  const [physicsState, setPhysicsState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [physicsMessage, setPhysicsMessage] = useState("");
  const [physicsResult, setPhysicsResult] = useState<TestingPhysicsResponse | null>(null);
  const [originReady, setOriginReady] = useState(false);
  const [duration, setDuration] = useState(DEFAULT_DURATION);
  const [draftDirty, setDraftDirty] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ index: number; pointerId: number; captureTarget: SVGCircleElement; bounds: Bounds } | null>(null);
  const physicsRequestRef = useRef(0);
  const physicsAbortRef = useRef<AbortController | null>(null);

  const draft = useMemo(() => interpolateKeyframes(keyframes, duration), [keyframes, duration]);
  const origin = useMemo(() => interpolateKeyframes(originKeyframes, duration), [originKeyframes, duration]);
  const physicsTrace = useMemo(() => physicsResult?.trace.map((state) => ({ t: state.time_s, x: state.x_m, y: state.y_m, yaw: state.yaw_rad, speed: state.speed_mps })) ?? [], [physicsResult]);
  const bounds = useMemo(() => fit([...origin, ...draft, ...physicsTrace]), [origin, draft, physicsTrace]);
  const project = (point: Point) => `${((point.x - bounds.minX) / bounds.width) * 82 + 9},${91 - ((point.y - bounds.minY) / bounds.height) * 80}`;
  const selected = keyframes[selectedKeyframe] ?? keyframes[0];

  useEffect(() => {
    fetchScenarios().then(setOriginScenarios).catch(() => setOriginScenarios([]));
  }, []);

  useEffect(() => {
    setBranchId(null);
    setCommitState("idle");
    setCommitMessage("");
    setPhysicsResult(null);
    setPhysicsState("idle");
    setPhysicsMessage("");
    setPlayhead(0);
    setDraftDirty(false);
    fetchWorkspaceScenario(originScenarioId).then((workspace) => {
      const path = workspace.paths.find((item) => item.actor_id === "lead") ?? workspace.paths.find((item) => item.actor_id !== "testing-barrier") ?? workspace.paths[0];
      const states = path?.states ?? [];
      const derived = states.length >= 2
        ? states.filter((_, index) => index === 0 || index === states.length - 1 || index % Math.max(1, Math.floor(states.length / 3)) === 0).map((state) => ({ t: state.time_s, x: state.x_m, y: state.y_m, yaw: state.yaw_rad, speed: state.speed_mps }))
        : initialKeyframes;
      const normalized = derived.map((point, index) => index === 0 ? { ...point, yaw: states[0]?.yaw_rad ?? point.yaw } : point);
      setOriginKeyframes(normalized);
      setKeyframes(normalized);
      setOriginActorId(path?.actor_id ?? "lead");
      setDuration(workspace.scenario.duration_s);
      setOriginReady(true);
    }).catch(() => setOriginReady(true));
  }, [originScenarioId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const requestId = ++physicsRequestRef.current;
      physicsAbortRef.current?.abort();
      const controller = new AbortController();
      physicsAbortRef.current = controller;
      if (!draftDirty) return;
      setPhysicsState("loading");
      recalculateTestingCarla(originScenarioId, toRequest(keyframes, undefined, false, originActorId), controller.signal).then((result) => {
        if (requestId !== physicsRequestRef.current) return;
        setPhysicsResult(result);
        setPhysicsMessage("");
        setPhysicsState("ready");
      }).catch((error: unknown) => {
        if (requestId !== physicsRequestRef.current) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
        setPhysicsResult(null);
        setPhysicsMessage("Internal physics recalculation failed or timed out; the draft remains editable.");
        setPhysicsState("error");
      });
    }, 700);
    return () => { window.clearTimeout(timer); physicsAbortRef.current?.abort(); };
  }, [keyframes, draftDirty, originScenarioId, originActorId]);

  function moveKeyframe(event: React.PointerEvent<SVGCircleElement>, index: number) {
    if (index === 0) return;
    const svg = svgRef.current;
    if (!svg) return;
    dragRef.current = { index, pointerId: event.pointerId, captureTarget: event.currentTarget, bounds };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    updateKeyframePosition(event.clientX, event.clientY, index, bounds);
    setSelectedKeyframe(index);
  }

  function updateKeyframePosition(clientX: number, clientY: number, index: number, dragBounds: Bounds) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const viewX = ((clientX - rect.left) / rect.width) * 100;
    const viewY = ((clientY - rect.top) / rect.height) * 100;
    const x = dragBounds.minX + ((viewX - 9) / 82) * dragBounds.width;
    const y = dragBounds.minY + ((91 - viewY) / 80) * dragBounds.height;
    setKeyframes((current) => current.map((point, pointIndex) => pointIndex === index ? { ...point, x, y } : point));
    setDraftDirty(true);
  }

  function dragKeyframe(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    updateKeyframePosition(event.clientX, event.clientY, drag.index, drag.bounds);
  }

  function endKeyframeDrag(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.captureTarget.hasPointerCapture?.(event.pointerId)) drag.captureTarget.releasePointerCapture?.(event.pointerId);
    dragRef.current = null;
  }

  function addKeyframe() {
    let bestIndex = -1;
    let bestSpan = 0;
    for (let index = 0; index + 1 < keyframes.length; index += 1) {
      const span = keyframes[index + 1].t - keyframes[index].t;
      if (span >= MIN_KEYFRAME_INTERVAL * 2 && span > bestSpan) { bestIndex = index; bestSpan = span; }
    }
    if (bestIndex < 0) return;
    const left = keyframes[bestIndex];
    const right = keyframes[bestIndex + 1];
    const t = (left.t + right.t) / 2;
    const next = sampleOriginAt(originKeyframes, t);
    setKeyframes((current) => [...current, next].sort((a, b) => a.t - b.t));
    setDraftDirty(true);
    setSelectedKeyframe(bestIndex + 1);
  }

  function deleteKeyframe() {
    if (selectedKeyframe === 0 || selectedKeyframe === keyframes.length - 1 || keyframes.length <= 2) return;
    setKeyframes((current) => current.filter((_, index) => index !== selectedKeyframe));
    setSelectedKeyframe((current) => Math.max(1, current - 1));
    setDraftDirty(true);
  }

  function commitBranch() {
    const localValidation = validateKeyframes(keyframes, originKeyframes);
    if (localValidation.length > 0) {
      setCommitState("error");
      setCommitMessage(localValidation.join(" "));
      return;
    }
    setCommitState("loading");
    setCommitMessage("");
    createCanvasBranch(originScenarioId, toRequest(keyframes, "Testing path draft", true, originActorId)).then((result) => {
      if (!result.validation.valid) {
        setCommitState("error");
        setCommitMessage(result.validation.reasons.map((reason) => reason.message).join(" "));
        return;
      }
      setBranchId(result.scenario.scenario_id);
      setCommitState("success");
      setCommitMessage("Branch created. Loading WASM pair separately...");
      setWasmLoading(true);
      setWasmLoading(false);
      setDraftDirty(false);
      setCommitMessage("Branch created. Loading WASM pair...");
      return undefined;
    }).catch((error: Error) => {
      setCommitState("error");
      setCommitMessage(error.message);
    });
  }

  return <main className="testing-page">
    <header className="testing-header"><div><span className="testing-kicker">LOCAL DIAGNOSTIC PROBE</span><h1>Edit-object path lab</h1><p>Draw a draft path in 2D, scrub time, then inspect the synchronized browser 3D preview.</p></div><a href="/">Back to workspace</a></header>
    <div className="testing-warning">Origin is immutable. Edit keyframes locally, inspect internal single-track physics, then commit a session-only child branch.</div>
    <section className="testing-grid">
      <div className="testing-canvas-card">
         <div className="testing-card-title"><div><strong>2D path editor</strong><span>Drag unlocked keyframes. Each point shows time and velocity.</span></div><div className="testing-legend"><span><span className="testing-dot dynamic" /> edited</span><span><span className="testing-dot muted" /> origin</span><span><span className="testing-dot carla" /> internal physics</span></div></div>
        <svg ref={svgRef} className="testing-canvas" viewBox="0 0 100 100" role="img" aria-label="Editable two dimensional motion path" onPointerMove={dragKeyframe} onPointerUp={endKeyframeDrag} onPointerCancel={endKeyframeDrag}>
          <defs><pattern id="testing-grid" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M 5 0 L 0 0 0 5" fill="none" stroke="var(--grid-line)" strokeWidth=".18" /></pattern></defs>
          <rect width="100" height="100" fill="url(#testing-grid)" />
          <polyline className="testing-path origin" points={origin.map(project).join(" ")} />
          <polyline className="testing-path desired" points={draft.map(project).join(" ")} />
          {physicsResult && <polyline className="testing-path carla" points={physicsTrace.map(project).join(" ")} />}
          {keyframes.map((point, index) => { const [cx, cy] = project(point).split(","); return <g key={`${point.t}-${index}`}><circle className={`testing-keyframe${index === 0 ? " locked" : ""}${selectedKeyframe === index ? " selected" : ""}`} cx={cx} cy={cy} r={selectedKeyframe === index ? "1.35" : "1"} onPointerDown={(event) => moveKeyframe(event, index)} onClick={() => setSelectedKeyframe(index)} /><text className="testing-keyframe-label" x={Number(cx) + 1.5} y={Number(cy) - 1.5}>{`t=${point.t.toFixed(2)} v=${point.speed.toFixed(2)}`}</text><title>keyframe {index + 1}, t={point.t.toFixed(2)}s, velocity={point.speed.toFixed(2)} m/s{index === 0 ? ", locked origin" : ""}</title></g>; })}
        </svg>
         <div className="testing-caption"><span>Blue: edited path</span><span>Gray: origin path</span><span>Amber: internal physics trace</span><span>Physics: {physicsState}</span></div>
      </div>
       <aside className="testing-controls">
         <section className="testing-panel"><span className="testing-kicker">ORIGIN SCENARIO</span><label>Origin scenario<select aria-label="Origin scenario" value={originScenarioId} onChange={(event) => setOriginScenarioId(event.target.value)}>{originScenarios.length === 0 && <option value="synthetic-variant-001">synthetic-variant-001</option>}{originScenarios.map((scenario) => <option key={scenario.scenario_id} value={scenario.scenario_id}>{scenario.scenario_id} · {scenario.duration_s.toFixed(2)}s</option>)}</select></label><p className="testing-note">Changing origin reloads trajectory, duration, keyframes and WASM preview.</p></section>
        <section className="testing-panel"><span className="testing-kicker">EDIT OBJECT</span><h2>One vehicle target</h2><p className="testing-note">{originReady ? "Origin loaded. Keyframe 1 is the fixed start pose." : "Loading origin path..."}</p><label>Selected keyframe <output>#{selectedKeyframe + 1}</output><input aria-label="Selected keyframe" type="range" min="0" max={keyframes.length - 1} step="1" value={selectedKeyframe} onChange={(event) => setSelectedKeyframe(Number(event.target.value))} /></label><label>Velocity <output>{selected.speed.toFixed(2)} m/s</output><input aria-label="Velocity" type="range" min="0" max={MAX_KEYFRAME_SPEED} step="0.1" value={selected.speed} disabled={selectedKeyframe === 0} onChange={(event) => setKeyframes((current) => current.map((point, index) => index === selectedKeyframe ? { ...point, speed: Number(event.target.value) } : point))} /></label><div className="testing-validation"><strong>CAD motion guardrails</strong><span>Δt ≥ {MIN_KEYFRAME_INTERVAL.toFixed(2)}s</span><span>velocity ≤ {MAX_KEYFRAME_SPEED.toFixed(1)} m/s</span><span>acceleration ≤ {MAX_ACCELERATION.toFixed(1)} m/s²</span><span>braking ≤ {MAX_DECELERATION.toFixed(1)} m/s²</span><span>yaw rate ≤ {MAX_YAW_RATE.toFixed(1)} rad/s</span><span>turn angle ≤ {MAX_TURN_ANGLE.toFixed(2)} rad</span></div><button className="testing-action" onClick={addKeyframe}>Add keyframe at widest origin-time gap</button><button className="testing-action testing-action-secondary" onClick={deleteKeyframe} disabled={selectedKeyframe === 0 || selectedKeyframe === keyframes.length - 1 || keyframes.length <= 2}>Delete selected keyframe</button><button className="testing-action testing-action-secondary" disabled={commitState === "loading" || wasmLoading} onClick={commitBranch}>{commitState === "loading" ? "Creating branch..." : wasmLoading ? "Loading WASM pair..." : "Commit branch and load WASM"}</button>{commitMessage && <p className={`testing-commit ${commitState}`}>{commitMessage}</p>}{physicsMessage && <p className="testing-commit error">{physicsMessage}</p>}<div className="testing-status"><span>Origin immutable</span><span>Internal physics: {physicsState}</span><span>Velocity required</span><span>Parent immutable</span></div></section>
        <section className="testing-panel"><span className="testing-kicker">3D PREVIEW</span><h2>{branchId ? "Origin + edited WASM preview" : "Origin WASM preview"}</h2><WasmPlaybackView scenarioId={branchId ?? originScenarioId} mode="third-person" playhead={playhead} showControls toggles={{ cuboids: true, paths: false, lidar: false }} vehicleTints={{ lead: 0xff8a3d, "lead-origin-reference": 0x4f8cff }} /><input className="testing-time" aria-label="Preview time" type="range" min="0" max={duration} step={DT} value={playhead} onChange={(event) => setPlayhead(Number(event.target.value))} /><div className="testing-status"><span>Internal physics ADE</span><span>Internal physics trace</span><span>Origin vehicle: blue</span><span>Edited vehicle: orange</span><span>Obstacle: barrier</span><span>Duration: {duration.toFixed(2)}s</span></div></section>
      </aside>
    </section>
  </main>;
}

function toRequest(points: Point[], branchName?: string, includeOriginReference = false, actorId = "lead") {
  return {
    actor_id: actorId,
    coordinate_frame: "local_road_aligned" as const,
    branch_name: branchName ?? "Testing physics draft",
    ...(includeOriginReference ? { include_origin_reference: true } : {}),
    seed: 0,
    keyframes: points.map((point, index) => ({ keyframe_id: `testing-kf-${index + 1}`, time_s: point.t, x_m: point.x, y_m: point.y, yaw_rad: point.yaw, speed_mps: point.speed })),
  };
}

function validateKeyframes(points: Point[], origin: Point[]): string[] {
  const errors: string[] = [];
  const first = points[0];
  const source = origin[0];
  if (!first || !source || Math.abs(first.x - source.x) > 1e-6 || Math.abs(first.y - source.y) > 1e-6) errors.push("The first keyframe must remain at the origin pose.");
  for (const point of points) if (point.speed > MAX_KEYFRAME_SPEED) errors.push(`Velocity must stay at or below ${MAX_KEYFRAME_SPEED.toFixed(1)} m/s.`);
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const dt = current.t - previous.t;
    if (dt < MIN_KEYFRAME_INTERVAL) errors.push(`Keyframe ${index + 1} is too close in time; use at least ${MIN_KEYFRAME_INTERVAL.toFixed(2)}s.`);
    const acceleration = (current.speed - previous.speed) / Math.max(dt, 1e-6);
    if (acceleration > MAX_ACCELERATION) errors.push(`Keyframe ${index + 1} exceeds the acceleration guardrail.`);
    if (-acceleration > MAX_DECELERATION) errors.push(`Keyframe ${index + 1} exceeds the braking guardrail.`);
    if (index + 1 < points.length) {
      const turn = Math.abs(points[index + 1].yaw - previous.yaw);
      if (turn > MAX_TURN_ANGLE) errors.push(`Keyframe ${index + 1} exceeds the turn-angle guardrail.`);
    }
  }
  return [...new Set(errors)];
}

function sampleOriginAt(points: Point[], time: number): Point {
  const rightIndex = Math.min(points.length - 1, Math.max(1, points.findIndex((point) => point.t >= time)));
  const right = points[rightIndex];
  const left = points[Math.max(0, rightIndex - 1)];
  const fraction = (time - left.t) / Math.max(1e-6, right.t - left.t);
  return { t: time, x: left.x + (right.x - left.x) * fraction, y: left.y + (right.y - left.y) * fraction, yaw: left.yaw + (right.yaw - left.yaw) * fraction, speed: left.speed + (right.speed - left.speed) * fraction };
}

const initialKeyframes: Point[] = [{ t: 0, x: 0, y: 0, yaw: 0, speed: 6 }, { t: 2, x: 12, y: 0, yaw: 0.04, speed: 6 }, { t: 4, x: 23, y: 3, yaw: 0.12, speed: 6 }, { t: 6, x: 33, y: 8, yaw: 0.2, speed: 6 }];
function interpolateKeyframes(keyframes: Point[], duration: number): Point[] { return Array.from({ length: Math.round(duration / DT) + 1 }, (_, index) => { const t = index * DT; const rightIndex = Math.min(keyframes.length - 1, keyframes.findIndex((point) => point.t >= t) < 0 ? keyframes.length - 1 : keyframes.findIndex((point) => point.t >= t)); const right = keyframes[rightIndex]; const left = keyframes[Math.max(0, rightIndex - 1)]; const span = Math.max(1e-6, right.t - left.t); const f = right === left ? 0 : Math.min(1, Math.max(0, (t - left.t) / span)); return { t, x: left.x + (right.x - left.x) * f, y: left.y + (right.y - left.y) * f, yaw: left.yaw + (right.yaw - left.yaw) * f, speed: left.speed + (right.speed - left.speed) * f }; }); }
function fit(points: Point[]): Bounds { const xs = points.map((point) => point.x); const ys = points.map((point) => point.y); const minX = Math.min(...xs) - 1; const maxX = Math.max(...xs) + 1; const minY = Math.min(...ys) - 1; const maxY = Math.max(...ys) + 1; return { minX, minY, width: Math.max(1, maxX - minX), height: Math.max(1, maxY - minY) }; }

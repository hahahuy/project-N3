export type WasmObjectState = {
  id: number;
  name: string;
  /** Engine-declared type id (esmini `Object::Type`: 1 = Vehicle, 2 = Pedestrian,
   *  3 = MiscObject). This is the authoritative kind signal: the binding does
   *  not populate `type`/`kind` (both come back empty), so never classify on them. */
  object_type: number;
  /** Engine-declared category id (per-tag `Category` enum, e.g. Vehicle CAR = 0). */
  object_category: number;
  /** Legacy optional labels; absent from engine states. Kept for compatibility only. */
  type?: string;
  kind?: string;
  x: number;
  y: number;
  z: number;
  h: number;
  width: number;
  length: number;
  height: number;
  speed: number;
};

export type WasmPoint = { x: number; y: number; z: number };
export type WasmLaneSurface = { left_boundary: WasmPoint[]; right_boundary: WasmPoint[] };
export type WasmRoadGeometry = { lane_surfaces: WasmLaneSurface[]; road_marks: Array<{ points: WasmPoint[] }> };
export type WasmFrame = { simulation_time: number; object_states: WasmObjectState[] };

/** Phase 2 scene-completeness contract: lifecycle/quality labels for review.
 *  These never steer the engine — the `WasmFrame` stays authoritative for
 *  positions, and inactive objects are never rendered as present. */
export type WasmActorLifecycleStatus = "active" | "ended";

export type WasmActorLifecycle = {
  id: number;
  name: string;
  first_seen_s: number;
  last_seen_s: number;
  seen_count: number;
  status: WasmActorLifecycleStatus;
  last_speed_mps: number;
  actor_kind: "vehicle" | "pedestrian" | "misc" | "unknown";
};

export type WasmSceneSummary = {
  simulation_time: number;
  active_count: number;
  ended_count: number;
  actors: WasmActorLifecycle[];
};

/** Map the engine `object_type` id onto a review label.
 *  Ordinals are esmini `Object::Type` (Entities.hpp): 1 Vehicle, 2 Pedestrian,
 *  3 MiscObject. Anything else is genuinely unknown — never guessed. */
export const actorKindOf = (
  object: Pick<WasmObjectState, "object_type">,
): "vehicle" | "pedestrian" | "misc" | "unknown" =>
  object.object_type === 1
    ? "vehicle"
    : object.object_type === 2
      ? "pedestrian"
      : object.object_type === 3
        ? "misc"
        : "unknown";

/** Fold one engine frame into the lifecycle registry.
 *  Pure function so the view and tests share the semantics. */
export const trackWasmActors = (
  registry: Map<number, WasmActorLifecycle>,
  frame: WasmFrame,
): WasmSceneSummary => {
  const next = new Map(registry);
  for (const object of frame.object_states) {
    const known = next.get(object.id);
    next.set(object.id, {
      id: object.id,
      name: object.name,
      first_seen_s: known?.first_seen_s ?? frame.simulation_time,
      last_seen_s: frame.simulation_time,
      seen_count: (known?.seen_count ?? 0) + 1,
      status: "active",
      last_speed_mps: object.speed,
      actor_kind: actorKindOf(object),
    });
  }
  const live = new Set(frame.object_states.map((object) => object.id));
  for (const [id, entry] of next) {
    if (!live.has(id) && entry.status === "active") {
      next.set(id, { ...entry, status: "ended" });
    }
  }
  const actors = [...next.values()].sort((a, b) => a.id - b.id);
  return {
    simulation_time: frame.simulation_time,
    active_count: actors.filter((actor) => actor.status === "active").length,
    ended_count: actors.filter((actor) => actor.status === "ended").length,
    actors,
  };
};

export type WasmWorkerRequest =
  | { type: "init"; xosc: string; xodr: string }
  | { type: "seek"; time_s: number }
  | { type: "step" }
  | { type: "play" }
  | { type: "pause" }
  | { type: "reset" }
  | { type: "dispose" };
export type WasmWorkerResponse = { type: "ready"; road: WasmRoadGeometry; frame: WasmFrame } | { type: "frame"; frame: WasmFrame } | { type: "error"; message: string };

export type WasmOverlayToggles = { cuboids: boolean; paths: boolean; lidar: boolean };
export type WasmOrbitState = { position: [number, number, number]; target: [number, number, number] };

/** Worker-owned fixed integration step, matching native `--fixed_timestep 0.01`
 *  (Q5 parity requirement — a UI-interval or rAF integrator would diverge). */
export const FIXED_DT = 0.01;

/** Convert engine/source heading to the Three.js yaw used by vehicle skins.
 * Source +x is forward at h=0; the skin mesh's length/nose axis is local +z,
 * and the render frame maps source +y to Three.js -z. */
export const renderVehicleYaw = (headingRad: number): number => Math.PI / 2 + headingRad;

/** Constructor/step dt that issues a true zero-dt frame.
 *  Native `ScenarioPlayer::Init()` ends with `Frame(0.0)`; without this prime
 *  the story machine never leaves its initial state and no maneuver event
 *  ever fires (actors hold at teleports). Must stay 0: with a nonzero engine
 *  dt configured, `step_frame(0)` resolves to that dt instead of zero. */
export const ENGINE_PRIME_DT = 0;

/** Issue the single zero-prime frame right after construction.
 *  Advances no sim time; all subsequent fixed steps are unaffected.
 *  Pure so the contract is unit-testable without loading the WASM artifact. */
export const primeEngineScenario = (scenario: { step_frame(dt: number): unknown }): void => {
  scenario.step_frame(ENGINE_PRIME_DT);
};

/** Reset-then-re-prime as one contract. `reset()` alone restores teleports
 *  but leaves Init-phase triggers (e.g. ego SpeedAction) unfired, so actors
 *  hold at zero speed forever after a mid/end-play reset — measured: ego
 *  x=0.00 speed=0.00 at t=1.00 and t=5.00 post-reset, x=8.78 speed=8.75 with
 *  the re-prime. Same missing-prime class as construction; pure and tested. */
export const resetEngineScenario = (scenario: { reset(): unknown; step_frame(dt: number): unknown }): void => {
  scenario.reset();
  primeEngineScenario(scenario);
};

export type WasmEntityAttributes = {
  name: string;
  tag: string;
  category: string;
  mass: string;
  dimensions: string;
  properties: Array<{ name: string; value: string }>;
};

export type WasmScenarioAttributes = {
  road: string | null;
  entities: WasmEntityAttributes[];
};

export type WasmGroundPolygon = {
  exterior: Array<[number, number]>;
  holes: Array<Array<[number, number]>>;
};

export type WasmGroundLayer = { name: string; polygons: WasmGroundPolygon[] };

/** Survey-grade ground context (sidewalk/crossing fills) in the scenario
 *  local frame. Rendered under the lane ribbons; never a metric input. */
export type WasmGround = { layers: WasmGroundLayer[] };

/** Recorded-travel overlay: one polyline per actor in the scenario local
 *  frame, drawn from the workspace `paths` (display-only, never a metric). */
export type WasmRecordedPath = {
  actor_id: string;
  actor_type: string;
  points: Array<{ x_m: number; y_m: number }>;
};

/** Recorded LIDAR_TOP cloud already moved into the scenario local frame
 *  (sensor→ego→global→local chain applied at decode time). One sweep of a
 *  playhead-synced series; display-only, never a metric input. Points are a
 *  flat xyz triplet array (full-density 1x would drown in tuple overhead). */
export type WasmLidarCloud = {
  sample_data_token: string;
  timestamp_us: number | null;
  time_s: number;
  point_count: number;
  xyz: Float32Array;
};

/** One addressable sweep of the scenario play range, oldest first. */
export type WasmLidarSweep = {
  sample_data_token: string;
  timestamp_us: number;
  time_s: number;
  payload_url: string;
};

/** Cap on prefetched full-density sweeps: ~30k points each, localhost only.
 *  Stride selection keeps the whole play range covered under this budget. */
export const MAX_LIDAR_SWEEPS = 24;

/** Even stride over the play range (always keeps the first and last sweep),
 *  so the cloud follows the whole scene under the prefetch budget. */
export const selectSweepStride = (sweeps: WasmLidarSweep[], maxSweeps: number = MAX_LIDAR_SWEEPS): WasmLidarSweep[] => {
  if (sweeps.length <= maxSweeps) return sweeps;
  const stride = Math.ceil(sweeps.length / maxSweeps);
  const picked = sweeps.filter((_, index) => index % stride === 0);
  if (picked[picked.length - 1] !== sweeps[sweeps.length - 1]) picked.push(sweeps[sweeps.length - 1]);
  return picked;
};

/** Latest sweep at or before the playhead — never a future cloud. Falls
 *  back to the first sweep before play starts; null when there is nothing. */
export const nearestSweepAtOrBefore = (sweeps: WasmLidarSweep[], timeS: number): WasmLidarSweep | null => {
  if (sweeps.length === 0) return null;
  let active = sweeps[0];
  for (const sweep of sweeps) {
    if (sweep.time_s > timeS) break;
    active = sweep;
  }
  return active;
};

export type LidarRigidTransform = {
  translation_m: [number, number, number];
  rotation_wxyz: [number, number, number, number];
};

/** Apply one rigid transform (quaternion rotate, then translate), mirroring
 *  the workspace LidarView math. Missing transform = identity. */
export const applyLidarTransform = (
  point: [number, number, number],
  item: LidarRigidTransform | undefined,
): [number, number, number] => {
  if (!item) return point;
  const [x, y, z] = point;
  const [w, qx, qy, qz] = item.rotation_wxyz;
  const tx = 2 * (qy * z - qz * y);
  const ty = 2 * (qz * x - qx * z);
  const tz = 2 * (qx * y - qy * x);
  const [ox, oy, oz] = item.translation_m;
  return [x + w * tx + qy * tz - qz * ty + ox, y + w * ty + qz * tx - qx * tz + oy, z + w * tz + qx * ty - qy * tx + oz];
};

/** nuScenes-global → scenario-local, mirroring
 *  `RoadAlignedTransform.to_local_state` (single source of truth stays
 *  Python; this is the display-only re-derivation, unit-locked by tests). */
export const globalToLocalFrame = (
  x_m: number,
  y_m: number,
  originX_m: number,
  originY_m: number,
  heading_rad: number,
): [number, number] => {
  const dx = x_m - originX_m;
  const dy = y_m - originY_m;
  const cos = Math.cos(heading_rad);
  const sin = Math.sin(heading_rad);
  return [cos * dx + sin * dy, -sin * dx + cos * dy];
};

/** Decode one `/workspace/lidar` binary payload to flat xyz triplets
 *  (float32 per 16 bytes, little-endian, 4th float padding — same layout
 *  LidarView reads). Flat: full-density 1x sweeps stay a single buffer. */
export const decodeLidarPayloadFlat = (bytes: Uint8Array): { count: number; xyz: Float32Array } => {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const count = Math.floor(bytes.byteLength / 16);
  const xyz = new Float32Array(count * 3);
  for (let index = 0; index < count; index++) {
    xyz[index * 3] = view.getFloat32(index * 16, true);
    xyz[index * 3 + 1] = view.getFloat32(index * 16 + 4, true);
    xyz[index * 3 + 2] = view.getFloat32(index * 16 + 8, true);
  }
  return { count, xyz };
};

/** Decode one `/workspace/lidar` binary payload (float32 xyz per 16 bytes,
 *  little-endian, 4th float padding — same layout LidarView reads). */
export const decodeLidarPayload = (bytes: Uint8Array): Array<[number, number, number]> => {
  const { count, xyz } = decodeLidarPayloadFlat(bytes);
  const points: Array<[number, number, number]> = [];
  for (let index = 0; index < count; index++) {
    points.push([xyz[index * 3], xyz[index * 3 + 1], xyz[index * 3 + 2]]);
  }
  return points;
};

/** Reject a truncated/corrupt artifact BEFORE it reaches the engine, where
 *  it would surface as an opaque C++ `{excPtr}`. Measured failure: the
 *  browser received 561 KB of a 3.9 MB OpenDRIVE (cut mid-attribute) and
 *  esmini died parsing it. Throws a human-readable error naming the label
 *  and received size, so the caller can refetch instead of showing excPtr. */
export const assertWellFormedXml = (text: string, label: string): void => {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.querySelector("parsererror")) {
    throw new Error(`wasm_${label}_truncated_or_corrupt received_bytes=${text.length}`);
  }
};

const CATEGORY_ATTR_BY_TAG: Record<string, string> = {
  Vehicle: "vehicleCategory",
  Pedestrian: "pedestrianCategory",
  MiscObject: "miscObjectCategory",
};

/** Read display-only entity/road attributes from already-fetched XOSC text.
 *  Never steers the engine: the Worker protocol is the sole motion path.
 *  Unknown tags and missing attributes render as `—`, never invented. */
export const parseXoscAttributes = (xoscText: string): WasmScenarioAttributes => {
  const doc = new DOMParser().parseFromString(xoscText, "application/xml");
  const attr = (el: Element | null | undefined, name: string): string => {
    const value = name ? el?.getAttribute(name) ?? null : null;
    return value === null || value === "" ? "—" : value;
  };
  const road = doc.querySelector("RoadNetwork > LogicFile")?.getAttribute("filepath") ?? null;
  const entities = Array.from(doc.querySelectorAll("Entities > ScenarioObject")).map((obj) => {
    const tag = obj.firstElementChild?.tagName ?? "—";
    const detail = obj.firstElementChild;
    const dims = detail?.querySelector("BoundingBox > Dimensions");
    const dimensions = dims
      ? `${dims.getAttribute("width") ?? "?"}×${dims.getAttribute("length") ?? "?"}×${dims.getAttribute("height") ?? "?"}`
      : "—";
    return {
      name: obj.getAttribute("name") ?? "—",
      tag,
      category: attr(detail, CATEGORY_ATTR_BY_TAG[tag] ?? ""),
      mass: attr(detail, "mass"),
      dimensions,
      properties: Array.from(detail?.querySelectorAll(":scope > Properties > Property") ?? []).map((prop) => ({
        name: prop.getAttribute("name") ?? "—",
        value: prop.getAttribute("value") ?? "—",
      })),
    };
  });
  return { road, entities };
};

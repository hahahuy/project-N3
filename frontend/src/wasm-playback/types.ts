export type WasmObjectState = {
  id: number;
  name: string;
  type: string;
  kind: string;
  x: number;
  y: number;
  z: number;
  h: number;
  width: number;
  length: number;
  height: number;
  object_category: number;
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
  actor_kind: "vehicle" | "unknown";
};

export type WasmSceneSummary = {
  simulation_time: number;
  active_count: number;
  ended_count: number;
  actors: WasmActorLifecycle[];
};

const ACTOR_KIND_VEHICLE = "vehicle";

export const actorKindOf = (object: Pick<WasmObjectState, "type" | "kind">): "vehicle" | "unknown" =>
  object.type.toLowerCase().includes(ACTOR_KIND_VEHICLE) || object.kind.toLowerCase().includes(ACTOR_KIND_VEHICLE)
    ? "vehicle"
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
  | { type: "step" }
  | { type: "play" }
  | { type: "pause" }
  | { type: "reset" }
  | { type: "dispose" };
export type WasmWorkerResponse = { type: "ready"; road: WasmRoadGeometry; frame: WasmFrame } | { type: "frame"; frame: WasmFrame } | { type: "error"; message: string };

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
};

export type WasmPoint = { x: number; y: number; z: number };
export type WasmLaneSurface = { left_boundary: WasmPoint[]; right_boundary: WasmPoint[] };
export type WasmRoadGeometry = { lane_surfaces: WasmLaneSurface[]; road_marks: Array<{ points: WasmPoint[] }> };
export type WasmFrame = { simulation_time: number; object_states: WasmObjectState[] };

export type WasmWorkerRequest = { type: "init"; xosc: string; xodr: string } | { type: "step"; dt: number } | { type: "reset" } | { type: "dispose" };
export type WasmWorkerResponse = { type: "ready"; road: WasmRoadGeometry; frame: WasmFrame } | { type: "frame"; frame: WasmFrame } | { type: "error"; message: string };

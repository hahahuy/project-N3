import type { WasmFrame, WasmRoadGeometry, WasmWorkerRequest, WasmWorkerResponse } from "./types";

export type WasmRuntimeKey = `scenario:${string}` | `fixture:${string}`;
export type WasmRuntimeSnapshot = { status: "loading" | "ready" | "error" | "disposed"; road: WasmRoadGeometry; frame: WasmFrame; error: string | null; generation: number };
export type WasmRuntimeSource = { xosc: string; xodr: string };
type Listener = () => void;

const EMPTY_ROAD: WasmRoadGeometry = { lane_surfaces: [], road_marks: [] };
const EMPTY_FRAME: WasmFrame = { simulation_time: 0, object_states: [] };

export class WasmScenarioRuntime {
  private worker: Worker | null = null;
  private listeners = new Set<Listener>();
  private refs = 0;
  private requestId = 0;
  private snapshot: WasmRuntimeSnapshot = { status: "loading", road: EMPTY_ROAD, frame: EMPTY_FRAME, error: null, generation: 0 };

  constructor(private readonly source: WasmRuntimeSource) {}

  getSnapshot = (): WasmRuntimeSnapshot => this.snapshot;
  subscribe = (listener: Listener): (() => void) => { this.listeners.add(listener); return () => this.listeners.delete(listener); };
  acquire(): void { this.refs += 1; if (this.refs === 1) this.start(); }
  release(): void { this.refs = Math.max(0, this.refs - 1); if (this.refs === 0) this.dispose(); }
  send(type: WasmWorkerRequest["type"], payload: Record<string, unknown> = {}): void { this.worker?.postMessage({ type, ...payload, requestId: ++this.requestId }); }

  private emit(): void { for (const listener of this.listeners) listener(); }
  private start(): void {
    this.worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    this.worker.onmessage = (event: MessageEvent<WasmWorkerResponse>) => {
      const message = event.data;
      if (message.type === "error") this.snapshot = { ...this.snapshot, status: "error", error: message.message };
      else if (message.type === "ready") this.snapshot = { status: "ready", road: message.road, frame: message.frame, error: null, generation: this.snapshot.generation + 1 };
      else this.snapshot = { ...this.snapshot, status: "ready", frame: message.frame, error: null };
      this.emit();
    };
    this.send("init", this.source);
  }
  private dispose(): void { if (!this.worker) return; this.send("dispose"); this.worker.terminate(); this.worker = null; this.snapshot = { ...this.snapshot, status: "disposed" }; this.emit(); }
}

const runtimes = new Map<WasmRuntimeKey, WasmScenarioRuntime>();
export function acquireWasmRuntime(key: WasmRuntimeKey, source: WasmRuntimeSource): WasmScenarioRuntime {
  let runtime = runtimes.get(key);
  if (!runtime) { runtime = new WasmScenarioRuntime(source); runtimes.set(key, runtime); }
  runtime.acquire();
  return runtime;
}

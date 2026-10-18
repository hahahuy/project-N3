import { afterEach, describe, expect, it, vi } from "vitest";
import { acquireWasmRuntime, releaseWasmRuntime } from "./runtime-manager";

class FakeWorker { static instances: FakeWorker[] = []; onmessage: ((event: MessageEvent) => void) | null = null; messages: unknown[] = []; constructor() { FakeWorker.instances.push(this); } postMessage(message: unknown) { this.messages.push(message); } terminate = vi.fn(); }

describe("WasmScenarioRuntime", () => {
  afterEach(() => { FakeWorker.instances = []; vi.unstubAllGlobals(); });
  it("shares one worker between subscribers and disposes after final release", () => {
    vi.stubGlobal("Worker", FakeWorker);
    const source = { xosc: "x", xodr: "r" };
    const first = acquireWasmRuntime("scenario:s1", source);
    const second = acquireWasmRuntime("scenario:s1", source);
    expect(FakeWorker.instances).toHaveLength(1);
    releaseWasmRuntime("scenario:s1", first);
    expect(FakeWorker.instances[0].terminate).not.toHaveBeenCalled();
    releaseWasmRuntime("scenario:s1", second);
    expect(FakeWorker.instances[0].terminate).toHaveBeenCalledTimes(1);
  });

  it("broadcasts one worker frame to both subscribers", () => {
    vi.stubGlobal("Worker", FakeWorker);
    const first = acquireWasmRuntime("scenario:frame", { xosc: "x", xodr: "r" });
    const second = acquireWasmRuntime("scenario:frame", { xosc: "x", xodr: "r" });
    const listener = vi.fn();
    first.subscribe(listener);
    second.subscribe(listener);
    const worker = FakeWorker.instances[0];
    worker.onmessage?.({ data: { type: "ready", road: { lane_surfaces: [], road_marks: [] }, frame: { simulation_time: 0, object_states: [] } } } as MessageEvent);
    expect(first.getSnapshot().status).toBe("ready");
    expect(second.getSnapshot().frame.simulation_time).toBe(0);
    expect(listener).toHaveBeenCalled();
    releaseWasmRuntime("scenario:frame", first);
    releaseWasmRuntime("scenario:frame", second);
  });

  it("rejects a changed source under an existing scenario key", () => {
    vi.stubGlobal("Worker", FakeWorker);
    const first = acquireWasmRuntime("scenario:source", { xosc: "x", xodr: "r" });
    expect(() => acquireWasmRuntime("scenario:source", { xosc: "x-tail-different", xodr: "r" })).toThrow("wasm_runtime_source_mismatch");
    releaseWasmRuntime("scenario:source", first);
  });
});

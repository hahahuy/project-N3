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
});

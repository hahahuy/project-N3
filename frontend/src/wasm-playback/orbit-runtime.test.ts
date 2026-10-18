import { describe, expect, it, vi } from "vitest";
import { OrbitRuntime } from "./orbit-runtime";

const initial = { position: [20, 22, 26] as [number, number, number], target: [0, 0, 0] as [number, number, number] };

describe("OrbitRuntime", () => {
  it("deduplicates snapshots and notifies on changes", () => {
    const runtime = new OrbitRuntime(initial);
    const listener = vi.fn();
    runtime.subscribe(listener);
    expect(runtime.update(initial)).toBe(false);
    expect(runtime.update({ position: [21, 22, 26], target: [0, 0, 0] })).toBe(true);
    expect(runtime.getRevision()).toBe(1);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("queues and atomically consumes commands", () => {
    const runtime = new OrbitRuntime(initial);
    runtime.enqueue({ type: "lock", actorId: "ego" });
    runtime.enqueue({ type: "reset", orbit: initial });
    expect(runtime.consumeCommands()).toEqual([{ type: "lock", actorId: "ego" }, { type: "reset", orbit: initial }]);
    expect(runtime.consumeCommands()).toEqual([]);
  });
});

import { describe, expect, it, vi } from "vitest";
import { ByteBoundedLru, byteLengthOfFloat32Array, selectSweepWindow } from "./bounded-cache";

describe("ByteBoundedLru", () => {
  it("evicts least-recently-used entries deterministically by bytes", () => {
    const disposed: string[] = [];
    const cache = new ByteBoundedLru<string, string>({ maxBytes: 6, byteSize: (value) => value.length, onDispose: (value) => disposed.push(value) });
    cache.set("a", "aa").set("b", "bbb"); cache.get("a"); cache.set("c", "cccc");
    expect(cache.keys()).toEqual(["a", "c"]); expect(disposed).toEqual(["bbb"]); cache.clear(); expect(disposed).toEqual(["bbb", "aa", "cccc"]); expect(cache.bytes).toBe(0);
  });
  it("replaces, deletes, clears, and disposes an oversized value", () => {
    const dispose = vi.fn(); const cache = new ByteBoundedLru<string, Float32Array>({ maxBytes: 8, byteSize: byteLengthOfFloat32Array, onDispose: dispose });
    const first = new Float32Array(1), second = new Float32Array(2), tooLarge = new Float32Array(3);
    cache.set("x", first).set("x", second); expect(cache.bytes).toBe(8); cache.set("too-large", tooLarge); expect(cache.has("too-large")).toBe(false); cache.clear();
    expect(dispose).toHaveBeenCalledWith(first, "x"); expect(dispose).toHaveBeenCalledWith(tooLarge, "too-large"); expect(cache.size).toBe(0); expect(cache.bytes).toBe(0);
  });
});

describe("selectSweepWindow", () => {
  const sweeps = [0, 1, 2, 3, 4, 5].map((time_s) => ({ time_s, id: time_s }));
  it("centers a small window on the active sweep", () => { expect(selectSweepWindow(sweeps, 3.2, 3).map((sweep) => sweep.id)).toEqual([2, 3, 4]); expect(selectSweepWindow(sweeps, -1, 3).map((sweep) => sweep.id)).toEqual([0, 1, 2]); expect(selectSweepWindow(sweeps, 99, 3).map((sweep) => sweep.id)).toEqual([3, 4, 5]); });
  it("handles empty, zero, and already-bounded inputs", () => { expect(selectSweepWindow([], 1, 3)).toEqual([]); expect(selectSweepWindow(sweeps, 1, 0)).toEqual([]); expect(selectSweepWindow(sweeps, 1, 10)).toEqual(sweeps); });
});

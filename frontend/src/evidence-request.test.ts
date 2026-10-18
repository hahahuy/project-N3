import { describe, expect, it, vi } from "vitest";
import { createPlayheadRequest } from "./evidence-request";

describe("createPlayheadRequest", () => {
  it("runs only the latest debounced request", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValue("latest");
    const request = createPlayheadRequest(fetcher);
    const first = request.request(1);
    const second = request.request(2);
    await expect(first).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(125);
    await expect(second).resolves.toBe("latest");
    expect(fetcher).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});

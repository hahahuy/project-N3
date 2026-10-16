// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import WasmPlaybackView from "./WasmPlaybackView";
import { trackWasmActors } from "./types";
import type { WasmFrame } from "./types";

vi.mock("./ThreePlaybackCanvas", () => ({
  default: () => <div data-testid="three-playback-canvas" />,
}));

class FakeWorker {
  static instances: FakeWorker[] = [];
  readonly messages: unknown[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor() {
    FakeWorker.instances.push(this);
  }

  postMessage(message: unknown): void {
    this.messages.push(message);
  }

  terminate(): void {}
}

afterEach(() => {
  FakeWorker.instances = [];
  vi.restoreAllMocks();
});

describe("WasmPlaybackView Worker protocol", () => {
  it("uses worker-owned play/pause and fixed-step protocol messages", async () => {
    vi.stubGlobal("Worker", FakeWorker);
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("<scenario />", { status: 200 }));

    render(<WasmPlaybackView />);
    const worker = await waitFor(() => {
      const instance = FakeWorker.instances[0];
      if (!instance) throw new Error("worker_not_created");
      expect(instance.messages).toContainEqual({ type: "init", xosc: "<scenario />", xodr: "<scenario />" });
      return instance;
    });

    worker.onmessage?.({ data: { type: "ready", road: { lane_surfaces: [], road_marks: [] }, frame: { simulation_time: 0, object_states: [] } } } as MessageEvent);
    await waitFor(() => expect((screen.getByRole("button", { name: "Play" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    expect(worker.messages).toContainEqual({ type: "play" });

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(worker.messages).toContainEqual({ type: "pause" });
    fireEvent.click(screen.getByRole("button", { name: "Step" }));
    expect(worker.messages).toContainEqual({ type: "step" });
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(worker.messages).toContainEqual({ type: "reset" });
  });

  it("tracks actor lifecycle without inventing presence", () => {
    const frame = (time: number, ids: number[]): WasmFrame => ({
      simulation_time: time,
      object_states: ids.map((id) => ({
        id, name: `actor-${id}`, type: "vehicle.car", kind: "vehicle",
        x: 0, y: 0, z: 0, h: 0, width: 1.8, length: 4.5, height: 1.5,
        object_category: 1, speed: 2.5,
      })),
    });

    const first = trackWasmActors(new Map(), frame(0, [0, 1]));
    expect(first.active_count).toBe(2);
    expect(first.ended_count).toBe(0);

    const second = trackWasmActors(new Map(first.actors.map((a) => [a.id, a])), frame(0.01, [0]));
    expect(second.active_count).toBe(1);
    expect(second.ended_count).toBe(1);
    expect(second.actors.find((a) => a.id === 1)?.status).toBe("ended");
    expect(second.actors.find((a) => a.id === 0)?.seen_count).toBe(2);
    expect(second.actors.every((a) => a.actor_kind === "vehicle")).toBe(true);
  });
});

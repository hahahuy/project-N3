// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import WasmPlaybackView from "./WasmPlaybackView";
import { actorKindOf, applyLidarTransform, assertWellFormedXml, decodeLidarPayload, decodeLidarPayloadFlat, ENGINE_PRIME_DT, FIXED_DT, globalToLocalFrame, nearestSweepAtOrBefore, parseXoscAttributes, primeEngineScenario, renderVehicleYaw, resetEngineScenario, selectSweepStride, trackWasmActors } from "./types";
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
  it("maps engine heading to the vehicle skin nose axis", () => {
    expect(renderVehicleYaw(0)).toBeCloseTo(Math.PI / 2);
    expect(renderVehicleYaw(Math.PI / 2)).toBeCloseTo(Math.PI);
    expect(renderVehicleYaw(-Math.PI / 2)).toBeCloseTo(0);
  });

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

  it("sends a controlled playhead seek after the worker is ready", async () => {
    vi.stubGlobal("Worker", FakeWorker);
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("<scenario />", { status: 200 }));

    render(<WasmPlaybackView playhead={1.25} />);
    const worker = await waitFor(() => {
      const instance = FakeWorker.instances[0];
      if (!instance) throw new Error("worker_not_created");
      return instance;
    });
    worker.onmessage?.({ data: { type: "ready", road: { lane_surfaces: [], road_marks: [] }, frame: { simulation_time: 0, object_states: [] } } } as MessageEvent);
    await waitFor(() => expect(worker.messages).toContainEqual({ type: "seek", time_s: 1.25 }));
  });

  it("coalesces rapid playhead changes before sending a seek", async () => {
    vi.stubGlobal("Worker", FakeWorker);
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("<scenario />", { status: 200 }));
    const view = render(<WasmPlaybackView playhead={1} />);
    const worker = await waitFor(() => {
      const instance = FakeWorker.instances[0];
      if (!instance) throw new Error("worker_not_created");
      return instance;
    });
    vi.useFakeTimers();
    worker.onmessage?.({ data: { type: "ready", road: { lane_surfaces: [], road_marks: [] }, frame: { simulation_time: 0, object_states: [] } } } as MessageEvent);
    view.rerender(<WasmPlaybackView playhead={2} />);
    view.rerender(<WasmPlaybackView playhead={3} />);
    await vi.advanceTimersByTimeAsync(75);
    expect(worker.messages.filter((message) => (message as { type?: string }).type === "seek")).toEqual([{ type: "seek", time_s: 3 }]);
    vi.useRealTimers();
  });

  it("loads the pedestrian fixture and shared road when requested", async () => {
    vi.stubGlobal("Worker", FakeWorker);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("<scenario />", { status: 200 }));

    render(<WasmPlaybackView fixture="pedestrian" />);
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes("fixture-pedestrian.xosc"))).toBe(true);
      expect(urls.some((url) => url.includes("smoke.xodr"))).toBe(true);
      expect(urls.some((url) => url.includes("fixture.xosc"))).toBe(false);
    });
  });

  it("primes with a single true-zero step so maneuver events fire", () => {
    // Regression lock for the frozen-playback defect: without one genuine
    // zero-dt frame after construction (native Frame(0.0) equivalent), the
    // story machine never starts and actors hold at teleports. With a nonzero
    // engine dt configured, step_frame(0) would resolve to that dt — hence
    // the prime constant must stay exactly 0 while playback stays at 0.01.
    expect(ENGINE_PRIME_DT).toBe(0);
    expect(FIXED_DT).toBe(0.01);
    const step_frame = vi.fn();
    primeEngineScenario({ step_frame });
    expect(step_frame).toHaveBeenCalledTimes(1);
    expect(step_frame).toHaveBeenCalledWith(0);
  });

  it("re-primes on reset so Init triggers refire after mid/end-play", () => {
    // Regression lock for the frozen-after-reset defect: reset() alone
    // restores teleports but ego's SpeedAction never restarts (measured
    // x=0.00 speed=0.00 post-reset vs moving with the re-prime).
    const calls: string[] = [];
    resetEngineScenario({
      reset: () => { calls.push("reset"); },
      step_frame: (dt: number) => { calls.push(`step:${dt}`); },
    });
    expect(calls).toEqual(["reset", "step:0"]);
  });

  it("maps global to scenario-local with the trajectory math", () => {
    // Mirrors RoadAlignedTransform.to_local_state: heading 0 = pure shift,
    // heading +90° rotates global +x onto local -y.
    expect(globalToLocalFrame(1010.13, 610.81, 1010.13, 610.81, 1.446)).toEqual([0, 0]);
    const [lx, ly] = globalToLocalFrame(2, 0, 0, 0, Math.PI / 2);
    expect(lx).toBeCloseTo(0, 9);
    expect(ly).toBeCloseTo(-2, 9);
  });

  it("applies lidar rigid transforms like the workspace view", () => {
    expect(applyLidarTransform([1, 2, 3], undefined)).toEqual([1, 2, 3]);
    const [x, y, z] = applyLidarTransform([1, 0, 0], {
      translation_m: [10, 0, 0],
      // +90° yaw quaternion (w, x, y, z).
      rotation_wxyz: [Math.SQRT1_2, 0, 0, Math.SQRT1_2],
    });
    expect(x).toBeCloseTo(10, 9);
    expect(y).toBeCloseTo(1, 9);
    expect(z).toBeCloseTo(0, 9);
  });

  it("decodes lidar payload float32 xyz triples", () => {
    const bytes = new Uint8Array(32);
    const view = new DataView(bytes.buffer);
    view.setFloat32(0, 1.5, true);
    view.setFloat32(4, -2.5, true);
    view.setFloat32(8, 0.25, true);
    view.setFloat32(12, 99, true); // padding float, skipped
    view.setFloat32(16, 4, true);
    view.setFloat32(20, 5, true);
    view.setFloat32(24, 6, true);
    expect(decodeLidarPayload(bytes)).toEqual([[1.5, -2.5, 0.25], [4, 5, 6]]);
    expect(decodeLidarPayload(new Uint8Array(0))).toEqual([]);
    const flat = decodeLidarPayloadFlat(bytes);
    expect(flat.count).toBe(2);
    expect(Array.from(flat.xyz)).toEqual([1.5, -2.5, 0.25, 4, 5, 6]);
  });

  it("rejects truncated artifacts before the engine sees them", () => {
    // The 561KB-of-3.9MB OpenDRIVE failure: cut mid-attribute, esmini died
    // with an opaque {excPtr}. The gate names the label and received size.
    expect(() => assertWellFormedXml("<OpenDRIVE></OpenDRIVE>", "xodr")).not.toThrow();
    expect(() => assertWellFormedXml('<road><geometry s="24', "xodr")).toThrow(/wasm_xodr_truncated_or_corrupt received_bytes=21/);
  });

  it("strides sweeps across the play range and never shows the future", () => {
    const sweeps = Array.from({ length: 39 }, (_, index) => ({
      sample_data_token: `sd-${index}`,
      timestamp_us: index * 500000,
      time_s: index * 0.5,
      payload_url: `/api/workspace/lidar/sd-${index}`,
    }));
    const picked = selectSweepStride(sweeps, 24);
    expect(picked.length).toBeLessThanOrEqual(24);
    expect(picked[0].time_s).toBe(0);
    expect(picked[picked.length - 1].time_s).toBe(19);
    expect(selectSweepStride(sweeps.slice(0, 3), 24)).toHaveLength(3);
    expect(nearestSweepAtOrBefore(picked, -1)?.time_s).toBe(0);
    expect(nearestSweepAtOrBefore(picked, 1.0)?.time_s).toBeLessThanOrEqual(1.0);
    expect(nearestSweepAtOrBefore(picked, 99)?.time_s).toBe(19);
    expect(nearestSweepAtOrBefore([], 5)).toBeNull();
  });

  it("classifies engine object_type ids without guessing", () => {
    // esmini Object::Type ordinals (source): 1 Vehicle, 2 Pedestrian, 3 MiscObject.
    expect(actorKindOf({ object_type: 1 })).toBe("vehicle");
    expect(actorKindOf({ object_type: 2 })).toBe("pedestrian");
    expect(actorKindOf({ object_type: 3 })).toBe("misc");
    expect(actorKindOf({ object_type: 0 })).toBe("unknown");
    expect(actorKindOf({ object_type: 99 })).toBe("unknown");
  });

  it("reads display-only attributes without inventing them", () => {
    const attrs = parseXoscAttributes(`<?xml version="1.0"?><OpenSCENARIO>
      <RoadNetwork><LogicFile filepath="smoke.xodr"/></RoadNetwork>
      <Entities>
        <ScenarioObject name="walk1"><Pedestrian name="human.pedestrian.adult" mass="75" model="" pedestrianCategory="pedestrian">
          <BoundingBox><Center x="0" y="0" z="0.85"/><Dimensions width="0.6" length="0.6" height="1.7"/></BoundingBox>
          <Properties><Property name="source_actor_type" value="human.pedestrian.adult"/></Properties>
        </Pedestrian></ScenarioObject>
        <ScenarioObject name="mystery"><WeirdThing/></ScenarioObject>
      </Entities></OpenSCENARIO>`);
    expect(attrs.road).toBe("smoke.xodr");
    expect(attrs.entities[0]).toEqual({
      name: "walk1", tag: "Pedestrian", category: "pedestrian", mass: "75",
      dimensions: "0.6×0.6×1.7",
      properties: [{ name: "source_actor_type", value: "human.pedestrian.adult" }],
    });
    expect(attrs.entities[1]).toEqual({
      name: "mystery", tag: "WeirdThing", category: "—", mass: "—",
      dimensions: "—", properties: [],
    });
    expect(parseXoscAttributes("<OpenSCENARIO/>").road).toBeNull();
  });

  it("expands ledger rows with declared XOSC attributes", async () => {
    vi.stubGlobal("Worker", FakeWorker);
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input: unknown) => {
      const url = String(input);
      if (url.endsWith(".xodr")) return new Response("<OpenDRIVE/>", { status: 200 });
      return new Response(`<?xml version="1.0"?><OpenSCENARIO>
        <RoadNetwork><LogicFile filepath="smoke.xodr"/></RoadNetwork>
        <Entities><ScenarioObject name="actor-0">
          <Vehicle name="vehicle.car" vehicleCategory="car" model3d="">
            <BoundingBox><Center x="0" y="0" z="0.9"/><Dimensions width="1.8" length="4.5" height="1.5"/></BoundingBox>
            <Properties><Property name="source_actor_type" value="vehicle.car"/></Properties>
          </Vehicle>
        </ScenarioObject></Entities></OpenSCENARIO>`, { status: 200 });
    });

    render(<WasmPlaybackView />);
    const worker = await waitFor(() => {
      const instance = FakeWorker.instances[0];
      if (!instance) throw new Error("worker_not_created");
      return instance;
    });
    worker.onmessage?.({ data: { type: "ready", road: { lane_surfaces: [], road_marks: [] }, frame: { simulation_time: 0, object_states: [] } } } as MessageEvent);
    worker.onmessage?.({
      data: {
        type: "frame",
        frame: {
          simulation_time: 0.01,
          object_states: [{
            id: 0, name: "actor-0", object_type: 1, object_category: 0,
            x: 0, y: 0, z: 0, h: 0, width: 1.8, length: 4.5, height: 1.5, speed: 1,
          }],
        },
      },
    } as MessageEvent);

    await screen.findByText("actor-0");
    // Shown twice by design: once in the scenario attributes panel, once in
    // the matching ledger row.
    expect(screen.getAllByText("source_actor_type=vehicle.car")).toHaveLength(2);
  });

  it("tracks actor lifecycle without inventing presence", () => {
    const frame = (time: number, ids: number[]): WasmFrame => ({
      simulation_time: time,
      object_states: ids.map((id) => ({
        id, name: `actor-${id}`, object_type: 1, object_category: 0,
        x: 0, y: 0, z: 0, h: 0, width: 1.8, length: 4.5, height: 1.5,
        speed: 2.5,
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

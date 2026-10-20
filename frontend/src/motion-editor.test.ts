// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { clientToWorld, physicalYawDelta, sampleOriginTrajectory, traceToKeyframes, validateKeyframes, MOTION_GUARDRAILS } from "./motion-editor";
import type { CanvasKeyframe, TrajectoryState } from "./api";

const origin: TrajectoryState[] = [
  { time_s: 0, x_m: 10, y_m: 2, yaw_rad: 3.13, speed_mps: 4 },
  { time_s: 1, x_m: 14, y_m: 2, yaw_rad: -3.13, speed_mps: 4 },
  { time_s: 2, x_m: 18, y_m: 4, yaw_rad: -3.0, speed_mps: 5 },
];

const keyframes = (): CanvasKeyframe[] => origin.map((state, index) => ({
  keyframe_id: `k${index}`,
  time_s: state.time_s,
  x_m: state.x_m,
  y_m: state.y_m,
  yaw_rad: state.yaw_rad,
  speed_mps: state.speed_mps,
}));

describe("motion editor contracts", () => {
  it("keeps a +/- pi wrap short but treats a full turn as physical", () => {
    expect(Math.abs(physicalYawDelta(-3.13, 3.13))).toBeLessThan(0.1);
    expect(Math.abs(physicalYawDelta(2 * Math.PI, 0))).toBeCloseTo(2 * Math.PI);
  });

  it("samples the origin trajectory with interpolated pose and speed", () => {
    const sample = sampleOriginTrajectory(origin, 0.5);
    expect(sample.x_m).toBe(12);
    expect(sample.y_m).toBe(2);
    expect(sample.speed_mps).toBe(4);
    expect(Math.abs(sample.yaw_rad)).toBeGreaterThan(3);
  });

  it("enforces origin pose, horizon, speed, and time interval", () => {
    const edited = keyframes();
    edited[0] = { ...edited[0], x_m: 11 };
    edited[1] = { ...edited[1], time_s: 0.1, speed_mps: MOTION_GUARDRAILS.maximumSpeedMps + 1 };
    expect(validateKeyframes(edited, keyframes(), 1)).toEqual(expect.arrayContaining([
      "The first keyframe must remain at the origin pose.",
      "Speed must stay at or below 20.0 m/s.",
      "Keyframe 2 is too close in time.",
    ]));
  });
});

describe("canvas coordinate mapping", () => {
  const bounds = { minX: 10, minY: 20, width: 100, height: 80 };
  const project = (x: number, y: number) => `${((x - bounds.minX) / bounds.width) * 82 + 9},${91 - ((y - bounds.minY) / bounds.height) * 80}`;

  const mountSquare = () => {
    document.body.innerHTML = `<svg class="motion-canvas" viewBox="0 0 100 100"></svg>`;
    const svg = document.querySelector("svg.motion-canvas")!;
    svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100, right: 100, bottom: 100, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
    return svg;
  };

  it("round-trips a point through project and back on a square canvas", () => {
    mountSquare();
    const [vx, vy] = project(55, 44).split(",").map(Number);
    const world = clientToWorld(vx, vy, bounds)!;
    expect(world.x).toBeCloseTo(55, 6);
    expect(world.y).toBeCloseTo(44, 6);
  });

  it("accounts for the letterbox when the element is wider than the viewBox", () => {
    document.body.innerHTML = `<svg class="motion-canvas" viewBox="0 0 100 100"></svg>`;
    const svg = document.querySelector("svg.motion-canvas")!;
    // 300x100 element: the square viewBox is scaled by 100/100 and centred,
    // leaving 100px of letterbox on each side.
    svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 300, height: 100, right: 300, bottom: 100, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
    const [vx, vy] = project(55, 44).split(",").map(Number);
    const world = clientToWorld(100 + vx, vy, bounds)!;
    expect(world.x).toBeCloseTo(55, 6);
    expect(world.y).toBeCloseTo(44, 6);
  });

  it("accounts for a panned viewBox so a drag still lands under the cursor", () => {
    document.body.innerHTML = `<svg class="motion-canvas" viewBox="0 0 100 100"></svg>`;
    const svg = document.querySelector("svg.motion-canvas")!;
    svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100, right: 100, bottom: 100, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
    const [vx, vy] = project(55, 44).split(",").map(Number);
    // Panning the viewBox by (12, -7) shifts which client pixel shows that
    // viewBox point, so the inverse must subtract the pan.
    const world = clientToWorld(vx - 12, vy + 7, bounds, { x: 12, y: -7, size: 100 })!;
    expect(world.x).toBeCloseTo(55, 6);
    expect(world.y).toBeCloseTo(44, 6);
  });

  it("returns null for a zero-sized canvas instead of dividing by zero", () => {
    document.body.innerHTML = `<svg class="motion-canvas" viewBox="0 0 100 100"></svg>`;
    const svg = document.querySelector("svg.motion-canvas")!;
    svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 0, height: 0, right: 0, bottom: 0, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
    expect(clientToWorld(10, 10, bounds)).toBeNull();
  });
});

describe("traceToKeyframes", () => {
  const trace = (count: number, at: (i: number) => TrajectoryState): TrajectoryState[] =>
    Array.from({ length: count }, (_, i) => at(i));

  it("decimates to the minimum keyframe interval instead of the solver timestep", () => {
    // 0.05 s solver samples over 2 s, minimum authoring interval 0.25 s.
    const result = traceToKeyframes(
      trace(41, (i) => ({ time_s: i * 0.05, x_m: i * 0.05, y_m: 0, yaw_rad: 0, speed_mps: 1 })),
      "actor-1",
      2,
    );
    for (let i = 1; i < result.length; i += 1) {
      expect(result[i]!.time_s - result[i - 1]!.time_s).toBeGreaterThanOrEqual(MOTION_GUARDRAILS.minimumKeyframeIntervalS - 1e-9);
    }
    expect(result[result.length - 1]!.time_s).toBeCloseTo(2, 6);
  });

  it("points the nose along a right-angle corner instead of the arrival heading", () => {
    // Drive east, then north. Every solver sample still carries the arrival
    // heading of its own segment, so the corner is only visible in the geometry.
    const corner: TrajectoryState[] = [];
    for (let i = 0; i <= 20; i += 1) corner.push({ time_s: i * 0.05, x_m: i * 0.25, y_m: 0, yaw_rad: 0, speed_mps: 5 });
    for (let i = 1; i <= 20; i += 1) corner.push({ time_s: 1 + i * 0.05, x_m: 5, y_m: i * 0.25, yaw_rad: Math.PI / 2, speed_mps: 5 });
    const result = traceToKeyframes(corner, "actor-1", 2);
    const cornerKey = result.find((point) => Math.abs(point.x_m - 5) < 1e-6 && Math.abs(point.y_m) < 1e-6);
    expect(cornerKey).toBeDefined();
    // Half of a 90 degree turn, not aligned with either leg.
    expect(Math.abs(cornerKey!.yaw_rad - Math.PI / 4)).toBeLessThan(0.2);
  });

  it("keeps heading continuous across the +/-pi wrap", () => {
    const wrap: TrajectoryState[] = [];
    for (let i = 0; i <= 60; i += 1) {
      const angle = Math.PI - (i * Math.PI) / 60;
      wrap.push({ time_s: i * 0.05, x_m: Math.cos(angle) * 10, y_m: Math.sin(angle) * 10, yaw_rad: angle, speed_mps: 5 });
    }
    const result = traceToKeyframes(wrap, "actor-1", 3);
    for (let i = 1; i < result.length; i += 1) {
      const jump = Math.abs(result[i]!.yaw_rad - result[i - 1]!.yaw_rad);
      expect(jump).toBeLessThan(Math.PI);
    }
  });

  it("keeps the first keyframe on the locked origin pose", () => {
    const result = traceToKeyframes(
      [{ time_s: 0, x_m: 1, y_m: 2, yaw_rad: 0.7, speed_mps: 3 }, { time_s: 1, x_m: 6, y_m: 2, yaw_rad: 0, speed_mps: 3 }],
      "actor-1",
      1,
    );
    expect(result[0]!.yaw_rad).toBeCloseTo(0.7, 6);
  });
});

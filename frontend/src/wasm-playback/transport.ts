import type { WasmOverlayToggles } from "./types";

/** Transport controls published by the active WASM playback view.
 *
 *  The playback view owns the worker runtime, so it owns Play/Pause/Step/Reset.
 *  The timeline strip is a sibling of the view manager rather than a child, so
 *  it cannot reach that state directly. Publishing a handle lets one control
 *  surface drive whichever preview is mounted, and the same strip is then used
 *  unchanged by Scenario studio and Variant studio. */
export type WasmTransportHandle = {
  scenarioId: string | null;
  ready: boolean;
  playing: boolean;
  status: string;
  timeS: number;
  objectCount: number;
  toggle: () => void;
  step: () => void;
  reset: () => void;
};

export type WasmTogglesPatch = Partial<WasmOverlayToggles>;

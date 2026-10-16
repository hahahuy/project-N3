# Interactive 3D Scenario Simulator Handoff

This proposal was supplied for the U5/Tier 1 esmini-WASM work and is retained
for review before implementation.

It proposes:

- building esminiJS as an ES module;
- running the WASM engine in a plain Worker;
- rendering road geometry and actor boxes through react-three-fiber;
- adding typed Worker RPC for playback, seek and actions;
- preserving native esmini as the Tier 0 measurement path;
- adding interaction only after a playback-only 3D slice is stable.

## Accepted Boundary For Review

The browser engine is for interaction and preview. Native backend esmini remains
the measurement path for replay traces and ADE/FDE. Browser frames must never
feed metric or acceptance code.

## Proposed Sequence

1. P0: build and load esminiJS as an ES module in a bare page.
2. P1: pin frontend dependencies and record one esmini version.
3. P2: add playback-only Worker/3D view, road geometry, actor boxes, cameras and
   timeline seek.
4. P3: add validated interactive injections and the action log.
5. P4: enforce the browser/native boundary, release hygiene and evidence.

The full analysis and source-specific code sketches are retained in the original
handoff supplied with this proposal. Before implementation, reconcile its file
paths and assumptions with the current repository and current upstream esmini
source.

## Current Repository Constraints

- Do not remove `run_esmini()`, `dat2csv`, replay jobs or native replay metrics.
- Do not compute ADE/FDE in the browser.
- Keep private nuScenes-derived artifacts outside git.
- Keep the template-map warning visible in any 3D view.
- Do not claim a WASM build is available until P0 has produced a reproducible
  artifact and a browser smoke result.

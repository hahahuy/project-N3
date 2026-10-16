# Interactive Object Selection Analysis

This proposal was supplied for the U5/esmini-WASM interactive simulator work.
It is retained as external implementation analysis and is not yet an accepted
project contract.

The original source is preserved in the accompanying proposal document:
[`wasm-interactive-simulator-handoff.md`](wasm-interactive-simulator-handoff.md).

Key conclusions:

- Hover and click selection are client-side concerns.
- Speed, lane-change and lane-offset injection are feasible through the
  esminiJS PlayerServer surface.
- Live storyboard parameter mutation is not reliable and should be implemented
  as a Worker-side scenario rewrite followed by reinitialisation.
- Injected actions disappear on reset, so an action log is required before
  timeline seek/reset can be presented as deterministic.
- Engine entity IDs are the injection key and must be validated/remapped after
  reset.

This file is intentionally a proposal snapshot. Verify every upstream API and
build claim against the selected esmini commit before implementation.

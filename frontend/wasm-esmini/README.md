# esminiJS WASM Build

Status: `P0 MODULE BUILD PASSED — BROWSER SMOKE PENDING`

This directory is the project-owned build seam for the external esminiJS
checkout. The upstream source is intentionally kept outside this repository.

## Source And Toolchain

- Upstream checkout: sibling `../esmini` during local development.
- Selected upstream tag: `v3.10.0`.
- Emscripten: `6.0.10`.
- Current upstream checkout was built successfully with its stock build script.
- The stock output is not yet the project artifact: it uses classic Emscripten
  module output and must be rebuilt with ES-module flags before integration.

## Required Output

The project build must eventually produce an ES module that can be imported by
a Worker and expose at least:

- `OpenScenario` construction;
- `step_frame()`;
- `get_object_states()`;
- `get_road_geometry()`;
- `reset()`;
- `get_simulation_time()`.

Do not commit generated `.js` or `.wasm` files until the build command,
upstream commit, Emscripten version and browser/Worker smoke are recorded in
`BUILD.md`. Browser output is preview/interaction only and must never feed
native replay metrics or `replay.csv`.

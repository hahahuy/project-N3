# esminiJS Build Record

Status: `P0 COMPLETE / BROWSER WORKER SMOKE PASSED`

## Inputs

- Upstream repository: `https://github.com/esmini/esmini`
- Upstream tag requested: `v3.10.0`
- Upstream commit used: `06065f929a7b7031098f9fa061afac3c7249d0e7`
- `externals/fmt` commit: `40626af88bd7df9a5fb80be7b25ac85b122d6c21`
- Emscripten: `6.0.10` (`d6c521a7f05449857c76bd99e396895583cf2083`)
- Host tools: CMake and Ninja

## Build

The source checkout is external to this repository. From the project root:

```bash
source /home/hahuy/github/emsdk/emsdk_env.sh
ESMINI_SOURCE_DIR=/home/hahuy/github/esmini frontend/wasm-esmini/build.sh
```

The wrapper copies the upstream fmt headers into a build-local directory and
applies `fmt-11.2.0-emscripten-cstdlib.patch`. It builds with:

- `MODULARIZE=1`
- `EXPORT_ES6=1`
- `EXPORT_NAME=createEsminiModule`
- `ENVIRONMENT=web,worker`
- `ALLOW_MEMORY_GROWTH=1`
- `FORCE_FILESYSTEM=1`
- separate WASM output disabled for the current probe (`SINGLE_FILE=0` is
  requested, but the current upstream/CMake output still emits a single JS
  module; verify this before relying on deployment MIME handling)

## Current Evidence

- Build completed successfully after applying the fmt compatibility patch.
- `frontend/wasm-esmini/dist/esmini.js` is an ES module.
- Node import returned a default factory function.
- The Node-based Worker smoke was attempted against a generated project
  XOSC/XODR pair. Module loading succeeded, but Node scenario construction was
  rejected by the `web,worker` target. This was not used as browser evidence.
- Browser Worker smoke passed at `/wasm-smoke` using the committed synthetic
  fixture: simulation time `0.05`, one active object, two lane surfaces and two
  road marks.
- No browser renderer or behavior injection is claimed.

The Node smoke harness remains `smoke.mjs` for diagnostics. The authoritative
P0 check is the browser page implemented under `frontend/src/wasm-smoke/`:

```bash
node frontend/wasm-esmini/smoke.mjs /path/to/scenario.xosc /path/to/road.xodr
```

The generated `dist/` output is a local probe result until the Worker scenario
smoke passes. Do not use it for Tier 0 metrics or replay evidence.

# /wasm-smoke — WASM diagnostic page and fixtures

Owner visual-review page (diagnostic-only, never in `VIEW_REGISTRY`). Browser
output is preview/interaction only and must never feed ADE/FDE, `replay.csv`,
gates, or reports (DEC-018).

## Files

| File | Role |
|---|---|
| `WasmSmokePage.tsx` | Page: P0 probe results (both fixtures) + playback preview with fixture / real-scenario picker |
| `worker.ts` | P0 probe: inits the engine on each fixture, one `step_frame(0)`, reports counts + per-object `name`/`type`/`kind` |
| `fixture.xosc` | Synthetic vehicle-only fixture (ego `Vehicle`, init-only, no trajectory) |
| `fixture-pedestrian.xosc` | Synthetic tag-widening fixture (ego `Vehicle` + `walk1` `Pedestrian` + `cone1` `MiscObject(other)`, init-only) |
| `smoke.xodr` | Straight two-lane road shared by both fixtures (both XOSCs declare `filepath="smoke.xodr"`) |
| `esmini.d.ts` | Ambient module declaration for the WASM artifact |

The playback renderer and Worker protocol live in `../wasm-playback/`
(`WasmPlaybackView` accepts `fixture="vehicle" | "pedestrian"` for the
synthetic fixtures, or `scenarioId` for a backend `wasm-pair`). The Node-side
headless equivalent of the probe is `../../wasm-esmini/smoke.mjs`.

## Expected values (engine 3.10.0, `step_frame(0)`)

| Fixture | sim time | objects | lane surfaces | road marks |
|---|---|---|---|---|
| vehicle | 0.01 | 1 (`ego`) | 2 | 2 |
| pedestrian | 0.01 | 3 (`ego`, `walk1`, `cone1`) | 2 | 2 |

Known engine behavior (measured via `smoke.mjs`, 2026-10-16): `type` and
`kind` come back as **empty strings for every object**, including the ego
vehicle. Object identity in the UI therefore comes from `name` only; the
renderer buckets everything as `unknown` (gray) until a name→taxonomy mapping
exists (which is the Q4 identity-key problem — do not invent one here).

## How to test everything

```bash
# 0. Build the WASM artifact first (dist/ is gitignored, nothing runs without it)
source "$EMSDK_DIR/emsdk_env.sh"
ESMINI_SOURCE_DIR="$PWD/../esmini" frontend/wasm-esmini/build.sh

# 1. Headless probe, both fixtures (needs only node + dist/)
node frontend/wasm-esmini/smoke.mjs frontend/src/wasm-smoke/fixture.xosc frontend/src/wasm-smoke/smoke.xodr
node frontend/wasm-esmini/smoke.mjs frontend/src/wasm-smoke/fixture-pedestrian.xosc frontend/src/wasm-smoke/smoke.xodr

# 2. API (host uvicorn; vite proxies to 127.0.0.1:8000)
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m uvicorn r2s_web.app:app \
  --app-dir src --port 8000

# 3. Frontend, then open the smoke page
cd frontend && npm run dev
# http://localhost:5173/wasm-smoke
```

On the page: P0 panel must show both fixtures with the table above; the
playback preview must play/step/reset on each synthetic fixture and on at
least one real scenario (needs local nuScenes data for `wasm-pair`).

## Deployment gap (read before debugging "it doesn't update")

The `:5173` server observed in this environment runs from a **different
checkout** (`node /app/frontend/...`, another mount namespace) — edits here
are invisible there until redeployed from this checkout. Verify in this repo
(tests, build, Node harness above); treat redeploy as a separate explicit
step. Never "fix" the page by editing the live environment.

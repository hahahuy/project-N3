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

The pedestrian fixture additionally carries a 3-vertex `FollowTrajectoryAction`
for `walk1` (x 3→7 over t 0–2 s) plus `Properties` on all three actors, so the
playback preview shows real trajectory motion and the attributes panel has
content. The probe itself only ever steps once, so P0 counts above are
unaffected by the trajectory.

Engine quirk learned the hard way: an Act `StartTrigger` with
`rule="greaterThanEqual"` never fires in esminiJS (the Act never starts and
all events stay dead — same frozen symptom as the missing prime). Use
`greaterThan` like the exporter does. The repo exporter never emits
`greaterThanEqual`, so production exports cannot hit this.

Known engine behavior (measured via `smoke.mjs`, 2026-10-16): the state
object has **no `type`/`kind` fields at all** — identity comes from the
numeric `object_type` (esmini `Object::Type`: 1 Vehicle, 2 Pedestrian,
3 MiscObject) plus `name`. The renderer and ledger classify on `object_type`
(vehicle gold, pedestrian green, misc violet, anything else gray); no
name→taxonomy mapping is invented (that mapping is the Q4 identity-key
problem — still open).

## Skins (schematic, 2026-10-16)

Actors render as procedural low-poly skins scaled to the **exact recorded
cuboid** (car body+cabin+wheels, pedestrian torso+head, traffic-cone cone,
plain box for unknown) — no model files, no new dependencies. Shapes are
illustrative, never measured: a car-looking box is still only a cuboid, and
the attributes panel shows the real numbers. Actor groups sit feet-on-road
(engine z + half recorded height + asphalt lift); ground fills stay beneath
them. Roads render as merged asphalt ribbons triangulated from the recorded lane boundaries, plus edge lines and
the recorded road marks (previously fetched but never drawn). "Complete"
means everything the data provides: no invented lane markings, shoulders,
sidewalks or textures — builder maps legitimately show unmarked asphalt.
Nothing here touches motion, metrics or reports.

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

On the page: P0 panel shows expected-vs-recorded per fixture (✓/✗ inline,
with the engine version the numbers were recorded on); the "What to check"
box lists the five checks in order. The playback preview must play/step/reset
on each synthetic fixture and on at least one real scenario (needs local
nuScenes data for `wasm-pair`). Open "Scenario attributes" under the ledger
to check the XOSC↔XODR correspondence: declared `LogicFile` vs served road
file, lane-surface/road-mark counts, and per-entity tag, category, mass,
bbox and properties — ledger rows expand to the same data for the engine
actor of the same name. For a real scenario the same panel shows the exported
attributes — that is the owner's XOSC-has-matching-OpenDRIVE check. For a
real scenario the playback canvas also draws the semantic ground underlay
(survey sidewalk/crossing fills under the lane ribbons, fetched best-effort
from `ground-layers`): ground must sit under the actors, never cover them,
and a missing ground must leave playback working.

## Deployment gap (read before debugging "it doesn't update")

The dev stack (`compose.dev.yml`: `project-n3-api-1`, `project-n3-frontend-1`)
bind-mounts **this checkout** (host repo dir → `/app`, `./frontend` →
`/app/frontend`), so working-tree edits are visible inside the containers —
`/app` is just not listable from a host shell (different mount namespace).
Redeploy = restart the dev stack so vite + uvicorn start clean:

```
docker compose -f compose.dev.yml restart api frontend
```

Backend is `:8001` (`8000` on the host belongs to other/manual servers —
leave them alone); frontend `:5173` proxies `/api` to the dev api. Verify
after restart: `:8001/api/health` ok and the served `WasmPlaybackView`
module mentions `fetchGroundLayers`. Never "fix" the page by editing the
live environment.

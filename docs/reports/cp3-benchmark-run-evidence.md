# CP3 Multi-Scene Benchmark Run Evidence

## Status

`RUNTIME-VERIFIED/PROVISIONAL`, `AGENT-SELECTED SCENE INDEX`, `NOT OWNER-APPROVED`

This report records the first real multi-scene nuScenes benchmark run on the
agent-selected provisional index. It clears the preparation blocker recorded in
`docs/reports/cp3-agent-selected-benchmark-index.md` and produces genuine
multi-scene evidence for CP3/CP4. It does not approve the benchmark index and it
creates no scientific acceptance claim.

## Metadata Index Blocker Resolution

The previous preparation attempt failed because every scene reloaded the full
trainval metadata tables. `sample_annotation.json` (about 557 MB),
`sample_data.json` (about 1.3 GB) and `ego_pose.json` (about 616 MB) were parsed
per scene, which exceeded the execution window.

`src/real2scenario/metadata_index.py` now streams those tables exactly once into
a compact local SQLite cache and answers scene-scoped queries from it:

- version string `nuscenes-metadata-index-v1`;
- small tables (`scene`, `sample`, `instance`, `calibrated_sensor`, `sensor`,
  `category`) are held as compact JSON;
- `sample_annotation`, LIDAR_TOP keyframe `sample_data` and the referenced
  `ego_pose` rows are projected per scene;
- the cache is validated against each source table's size and modification time
  and is rebuilt when the dataset changes;
- the cache lives outside the repository and holds derived metadata only, never
  raw sensor data;
- `SourceSceneAdapter` and the benchmark scripts reuse one process-shared index,
  and `extract_scenario` accepts an optional preloaded `tables` mapping.

Measured locally on `v1.0-trainval`:

```text
full index build:            ~41 s, ~0.9 GB peak RSS
persistent cache size:       ~787 MB
five-scene preparation:      ~0.8 s total (previously timed out)
five-scene benchmark run:    ~3 s wall clock including 48 esmini replays
```

Scene discovery and import output is unchanged: the new index reproduces the
previous table-scan results exactly on the bundled mini dataset.

## Commands

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/select_benchmark_scenes.py \
  --dataset-root "$NUSCENES_ROOT" \
  --output "$CP1_EVIDENCE_ROOT/benchmark-scenes-provisional.json"

ESMINI_BIN=... ESMINI_DAT2CSV=... PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python scripts/prepare_benchmark_scenes.py \
  --dataset-root "$NUSCENES_ROOT" \
  --scene-index "$CP1_EVIDENCE_ROOT/benchmark-scenes-provisional.json" \
  --output-root "$CP1_EVIDENCE_ROOT/prepared"

ESMINI_BIN=... ESMINI_DAT2CSV=... PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python scripts/run_benchmark_scenes.py \
  --dataset-root "$NUSCENES_ROOT" \
  --scene-index "$CP1_EVIDENCE_ROOT/benchmark-scenes-provisional.json" \
  --output-root "$CP1_EVIDENCE_ROOT/run"
```

## Run Configuration

```text
git revision:      4137164936c6535147491fb0f065bed8d4f8f729
dataset:           nuScenes v1.0-trainval, Singapore One-North
scene index:       agent-selected/provisional, 5 scenes, 41 samples each
generation:        grid, seed 7
                   speed multipliers [0.9, 1.0]
                   initial gap deltas [-2.0, 0.0] m
                   timing offsets [0.0, 0.5, 1.0] s
                   12 variants per scene, 60 total
simulator:         esmini v3.9.0 (GIT REV v3.9.0-0-efbf7ee1)
map template:      straight-two-lane-v1.xodr (regression template, not CP1 corridor)
validation limits: feasibility-v1 defaults
evidence class:    nuscenes_local, local_private
scientific status: PROVISIONAL
```

## Results

| Scene | Generated | Valid | Invalid | Simulator failed |
|---|---|---|---|---|
| scene-0380 | 12 | 12 | 0 | 0 |
| scene-0962 | 12 | 12 | 0 | 0 |
| scene-0945 | 12 | 0 | 12 | 0 |
| scene-0957 | 12 | 12 | 0 | 0 |
| scene-0981 | 12 | 12 | 0 | 0 |
| **total** | **60** | **48** | **12** | **0** |

Aggregate replay metrics over 192 replayed actor tracks:

```text
ADE (m): mean 15.31, median 0.29, p95 87.71, max 89.93

> **SUPERSEDED — do not quote these replay error magnitudes as current.**
> These figures predate both the replay-timing fixes and the `b52d423`
> contract changes, and are invalid. The current self-consistency baseline is
> ADE mean **0.0411 m**, median **0.0348 m**, p95 **0.1035 m**, max **0.1726 m**,
> FDE max **0.2052 m** over 3215 actor tracks on the full 850-scene
> `v1.0-trainval` set, esmini v3.9.0 — see
> `docs/reports/residual-replay-error-composition.md`. The generation,
> validation and gate structure below is unchanged; only the replay-derived
> error magnitudes are stale.
FDE (m): mean 18.72, median 0.31, p95 82.42, max 84.46
```

Gate funnel (`PROVISIONAL`):

```text
generated: 60
G1 pass 48 / evaluated 48
G2 pass 48 / evaluated 48
G3 pass 0  / evaluated 0   (road_match_unavailable)
G4 pass 48 / evaluated 60
G5 pass 0  / evaluated 0   (missing_event_definition)
G6 pass 0  / evaluated 60
G7 pass 60 / evaluated 60
```

## Findings

1. `scene-0945` is entirely invalid: the recorded ego/actor kinematics exceed the
   default jerk limit of `20 m/s^3` at multiple states, so no variant is
   exported or replayed. This is a source-data/limit interaction, not a pipeline
   failure, and no limit was changed to hide it.
2. Replay fidelity is strongly scene dependent **under the pre-fix exporter**
   (superseded). For the unedited configuration (speed multiplier `1.0`, gap
   delta `0.0`, timing offset `0.0`) the mean actor ADE was approximately
   `0.03 m` for `scene-0957`, `2.6 m` for `scene-0981`, `11.7 m` for
   `scene-0380` and `43.1 m` for `scene-0962`. **All four values are invalid**
   and must not be quoted. The scene dependence was an artifact of the replay
   timing defect — a timing anchor, not the map template — fixed across
   `7b1f053` and `b52d423`; see `docs/reports/replay-fidelity-root-cause-and-fix.md`
   and `docs/reports/residual-replay-error-composition.md`. ADE here always
   measures variant-versus-esmini self-consistency of the exported scenario,
   **not** similarity to the recorded nuScenes trajectory.
3. G3 remains `skipped` because no lane road-match evidence exists for these
   candidates. G5 remains `error` because the exported scenarios carry no event
   definition. Neither is fixed here; both stay visible in the aggregate.
4. `initial_gap_delta_m` changes non-ego actor positions by the requested offset
   and does not change ADE, confirming the metric is a variant/replay
   self-consistency measure rather than a perturbation-size measure.

## Boundaries

- The scene index remains agent-selected and provisional; owner approval is not
  requested and not implied.
- ADE/FDE, G6/G7 and the benchmark status remain `PROVISIONAL`; no threshold,
  pass/fail claim or CP3 acceptance is created.
- All artifacts are local and private; no nuScenes-derived data was added to the
  repository.
- CARLA remains unverified and post-MVP; this run is esmini only.
- The straight-two-lane regression template is used, so these results do not
  measure CP1 corridor map fidelity.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
docs consistency: PASS

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
223 passed, 1 warning (existing Starlette/httpx deprecation).
```

## Web Surface Follow-Up

A live smoke test through the Compose frontend proxy (`localhost:5173/api`)
exercised every endpoint the UI calls: health, settings, esmini, scenarios,
scenario detail, trajectory, source scenes, source-scene import, variant preview,
batch creation, batch results, result detail, trajectory, export and replay. It
also exposed a defect introduced by this slice: the shared metadata index held a
SQLite connection created in one request thread and reused by another, so
`POST /api/settings` failed intermittently with `sqlite3.ProgrammingError`.
The index now opens its connection with `check_same_thread=False` and guards all
queries with a lock, `tests/test_metadata_index.py` covers multi-thread reuse,
and the live endpoints pass after the fix.

## Next Action

Owner review of the provisional benchmark run, then either approve the
agent-selected index or replace it with an owner-chosen index. The open CP3
items after that are final scientific policy, G3 road-match evidence and G5 event
definitions; CP4 orchestration and CP5 reproducibility remain open as separate
gated tracks.
# Technology And Usage Guide

## 1. Technology Map

| Technology | Phase | Responsibility | Required for MVP |
| --- | --- | --- | --- |
| Python 3.11+ | M0-M4 | Core pipeline, data model, commands, tests | Yes |
| `pytest` | M0-M4 | Unit and integration test runner | Yes |
| `numpy`, `pandas`, `scipy` | M1-M3 | Trajectory processing, interpolation, numerical metrics | Yes, when implementation begins |
| `nuscenes-devkit` | M1 | Read nuScenes metadata, tracks, poses, and maps | Yes |
| OpenSCENARIO XML | M2-M4 | Portable scenario artifact | Yes |
| OpenDRIVE `.xodr` | M2-M4 | Road template used by the replay backend | Yes |
| esmini | M2-M4 | Headless OpenSCENARIO replay and batch validation | Yes |
| Streamlit and Plotly | M4 | Fast demonstration UI and top-down playback | Yes for UI demo |
| FastAPI | Later | API boundary for multi-user or React deployment | No |
| CARLA | Later | High-fidelity 3D visualization, sensor simulation, closed-loop tests | No |
| Docker | Later | Reproducible deployment/CI once native dependencies are stable | No |

Use the smallest tool that proves the next checkpoint. Installing CARLA, Docker, a database, and React before M2 creates operational work without proving that a recorded segment can be reconstructed correctly.

## 2. Local Python Environment

The foundation package intentionally has no runtime dependency until the corresponding ticket is implemented.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

Expected result at M0 is a passing schema test suite. At this point no full nuScenes dataset, OpenDRIVE map, or simulator binary is required.

When M1 begins, add pinned runtime packages to `pyproject.toml` rather than relying on unrecorded local installs. The expected initial set is:

```text
numpy
pandas
scipy
nuscenes-devkit
```

Add `lxml` only if a standard-library XML builder becomes insufficient. The exporter must stay deterministic regardless of XML library.

## 3. nuScenes Data Setup

The tracked `data/nuScenes-panoptic-v1.0-mini` directory contains panoptic material, not the object/ego trajectories needed by this project. Before R2S-102, obtain the nuScenes mini release through the official nuScenes process and preserve its license requirements.

Read [nuScenes and simulation guide](nuscenes-and-simulation-guide.md) before starting M1. It explains the dataset tables, coordinate frames, official visualization tools, expected local files, and the difference between trajectory replay and sensor-level replication.

The loader needs these metadata collections for trajectory reconstruction:

```text
scene.json
sample.json
sample_data.json
sample_annotation.json
ego_pose.json
calibrated_sensor.json
log.json
```

Lane-aware extraction also needs the appropriate nuScenes map data. The exact layout is validated by the R2S-101 preflight command once implemented.

Recommended local configuration:

```bash
export NUSCENES_ROOT="$HOME/datasets/nuscenes"
export NUSCENES_VERSION="v1.0-mini"
```

Rules:

- Do not hard-code a user home directory in source code.
- Do not commit the full dataset, access credentials, or raw data not permitted by the nuScenes terms.
- Store a source scene token, selected sample range, dataset version, and extraction version in each canonical scenario.
- Keep the nuScenes attribution and non-commercial/share-alike obligations from `data/LICENSE` with distributed derived artifacts where required.

## 4. OpenSCENARIO And OpenDRIVE

OpenSCENARIO (`.xosc`) describes entities, their initial conditions, actions, trajectories, and triggers. OpenDRIVE (`.xodr`) describes the road network. The MVP uses both because a vehicle trajectory needs a road context to replay and validate lane/drivable-area constraints.

For M2, use a small, versioned set of manually curated road templates such as a straight two-lane highway and a simple intersection:

```text
maps/
  highway-v1.xodr
  intersection-v1.xodr
```

The pipeline must record:

```text
source coordinate frame -> local road-aligned frame -> simulator frame
map reconstruction mode -> map template ID/version
```

This project does not claim a lossless nuScenes-map to OpenDRIVE conversion. A source segment that does not match a supported road template must be rejected or marked unsupported at M2, not silently distorted.

## 5. esmini Setup And Usage

esmini is the MVP execution backend. Install a tested esmini release for the team platform from its official distribution, then point the application to its executable without committing the local path.

```bash
export ESMINI_BIN="/absolute/path/to/esmini"
"$ESMINI_BIN" --help
```

The exact command line is encapsulated by R2S-204. It should accept explicit inputs and write outputs into a scenario-specific directory conceptually like this:

```bash
real2scenario replay \
  --scenario scenarios/baseline/<scenario-id>/baseline.xosc \
  --map maps/highway-v1.xodr \
  --output scenarios/baseline/<scenario-id>/replay.csv
```

The command interface above is a target contract, not yet an implemented CLI. The runner must capture:

- esmini executable/version
- complete command arguments excluding secrets
- timeout
- exit code
- stdout and stderr
- trace location
- source scenario and map template identifiers

Run esmini headlessly for batch generation and validation. A GUI run is useful only for manual inspection of one curated scenario.

## 6. Why esmini Is The MVP Backend

| Criterion | esmini | CARLA | MVP decision |
| --- | --- | --- | --- |
| Native purpose | Lightweight OpenSCENARIO/OpenDRIVE playback | General-purpose 3D driving simulation | Favor esmini |
| Headless batch execution | Small operational footprint and fast startup | Heavier server/client lifecycle and GPU-oriented environment | Favor esmini |
| Scenario artifact validation | Directly exercises generated `.xosc` files | OpenSCENARIO support is not the core complete workflow to rely on for this MVP | Favor esmini |
| Deterministic regression tests | Easier to run as an external replay tool | More sources of runtime variance and operational complexity | Favor esmini |
| 3D realism and sensor output | Limited | Strong: rendering, camera/LiDAR/radar, weather | Favor CARLA later |
| Closed-loop autonomy evaluation | Not the goal | Strong: run an ego agent/controller in an interactive world | Favor CARLA later |

The MVP research question is: “Can a recorded interaction be reconstructed, replayed, measured, and varied reproducibly?” esmini answers this with the least additional system complexity. CARLA would add 3D assets, a simulator server, client version matching, map import, synchronous tick handling, and likely GPU/deployment constraints before the team has validated the core data-to-scenario transformation.

This is not a statement that esmini is superior to CARLA overall. It is a sequencing decision. The canonical `Scenario` contract intentionally keeps CARLA viable once the team needs it.

## 7. When To Add CARLA

Add a CARLA adapter only after M3 has passed and one of these requirements is real:

- The demo requires 3D visualization instead of a top-down replay.
- The project needs camera, LiDAR, radar, weather, lighting, or occlusion effects.
- An autonomy stack must drive the ego vehicle in closed loop.
- Generated scenarios must be evaluated against perception, planning, or control behavior rather than fixed/open-loop trajectories.
- The team has a reproducible environment with supported CARLA server/client versions and sufficient GPU capacity.

CARLA integration should be a separate milestone, not a replacement for the esmini baseline. It consumes the canonical scenario and produces an additional replay trace/report:

```text
Canonical Scenario
  -> CARLA adapter
  -> CARLA world/entities/actions
  -> CARLA replay trace
  -> same metric and report contract
```

Before implementation, add a ticket for coordinate/map conversion boundaries. CARLA maps, asset semantics, actor blueprints, and behavior APIs are not interchangeable with a generated OpenSCENARIO file, so each unsupported behavior must fail explicitly rather than approximate silently.

## 8. Metrics And Validation Usage

The initial metrics are calculated after recorded and replay traces have been aligned to a documented common time grid:

| Metric | Unit | Interpretation |
| --- | --- | --- |
| Position RMSE | m | Typical planar deviation during replay. |
| Final displacement error | m | End-of-window drift. |
| Heading MAE | degrees or radians, stated explicitly | Orientation mismatch. |
| Speed MAE | m/s | Kinematic mismatch. |
| Minimum TTC | s | Risk signal; not a safety guarantee. |
| Minimum distance | m | Closest actor separation. |

The validator runs schema, kinematic, road, simulator, and risk checks in that order. A scenario that fails any required validity check must remain invalid even when it has an interesting TTC or a high novelty score.

## 9. UI Usage

Use Streamlit for M4 because it lets the team show the end-to-end workflow before maintaining a separate frontend and API deployment.

The dashboard must support this review sequence:

1. Select a documented source scenario.
2. Inspect ego and selected actors in a top-down timeline.
3. View baseline replay overlay and fidelity metrics.
4. Set speed/gap/timing parameters within stated ranges.
5. Generate and validate a batch.
6. Filter by validity first, then inspect score/TTC/diversity.
7. Export the `.xosc`, canonical JSON, trace, and report for one result.

Use FastAPI plus React only when the UI must support concurrent users, long-running queued jobs, separate deployment, or richer interaction than Streamlit can sustain. This must not change the canonical model or report contract.

## 10. Test Strategy

| Test level | Runs without | Examples |
| --- | --- | --- |
| Unit | Dataset and simulator | Schema invariants, transforms, TTC, metrics, deterministic IDs. |
| Fixture | Full dataset and simulator | Parse small sanitized canonical/trace/XML fixtures. |
| Integration | Optional external binaries | Export `.xosc`, execute esmini, parse replay trace. |
| Demo smoke test | Full automation where impractical | Curated UI walkthrough and exported artifact inspection. |

Every external integration failure must preserve enough context to reproduce it: source scenario ID, map version, command, config/seed, tool version, exit code, and logs.

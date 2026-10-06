# Architecture

## 1. Design Principles

- Keep recorded-data interpretation separate from simulator-specific export.
- Preserve provenance and deterministic generation parameters in every artifact.
- Fail a scenario explicitly instead of silently repairing implausible trajectories.
- Make each validation decision inspectable by a reviewer.
- Start with one process and module boundaries, not microservices.

## 2. Pipeline

```text
nuScenes metadata
  -> ingestion and event-window extraction
  -> canonical Scenario
  -> road-aligned local coordinate transform
  -> OpenSCENARIO exporter
  -> esmini runner
  -> replay trace and metrics
  -> constrained variant generator
  -> validation, ranking, export/report
```

The source coordinate frame, local reconstruction frame, and simulator frame must be named in each artifact. Coordinate transforms must be invertible where possible and unit-tested with known points.

## 3. Canonical Contract

`src/real2scenario/models.py` is the contract shared by every pipeline stage. It must not import nuScenes, esmini, CARLA, UI, or XML libraries.

| Type | Required fields | Invariant |
| --- | --- | --- |
| `State` | time, x, y, yaw, speed | Time is finite and non-negative; values use SI units. |
| `Actor` | ID, type, trajectory | Actor ID is unique in a scenario; timestamps strictly increase. |
| `Scenario` | ID, duration, ego ID, actors, provenance | Ego exists; scenario duration covers all states. |
| `VariantConfig` | speed multiplier, gap delta, timing offset, seed | Input values are serializable and must be stored with output. |

## 4. Module Boundaries

```text
src/real2scenario/
  models.py             Canonical dataclasses and validation
  ingestion/            nuScenes adapters and event mining
  map/                  Coordinate transforms and road templates
  export/               OpenSCENARIO XML generation
  simulation/           esmini process runner and trace parsing
  generation/           Controlled perturbation strategies
  validation/           Feasibility, replay metrics, ranking
  api/                  Optional FastAPI boundary
```

Rules:

- `ingestion` creates canonical objects; it does not write XML.
- `export` consumes canonical objects; it does not inspect nuScenes files.
- `simulation` only executes/reads simulator artifacts; it does not decide whether a case is rare.
- `validation` records every rejection reason as structured data.
- UI/API invoke orchestration functions but do not implement business rules.

## 5. Artifact Layout

```text
scenarios/
  baseline/<scenario-id>/
    scenario.json
    baseline.xosc
  generated/<parent-id>/<variant-id>/
    scenario.json
    scenario.xosc
    config.json
    replay.csv
    report.json
maps/
  highway.xodr
  intersection.xodr
reports/
```

Generated files are ignored by Git by default. A small curated set of fixture artifacts may be committed under `tests/fixtures/` when licensing permits.

## 6. Simulator Strategy

esmini is the MVP execution backend because it is lightweight and OpenSCENARIO-native. The first road maps are curated OpenDRIVE templates. A nuScenes segment is translated into a local road-aligned frame and replayed on the closest supported template.

This is an approximation. The report must expose `map_reconstruction_mode` and map/template version. Do not label this process as a direct nuScenes map conversion.

CARLA is an adapter added only after the canonical scenario, exporter, metrics, and review artifacts are stable. CARLA should consume the same canonical model rather than become the project data model.

## 7. Validity And Ranking

Each variant is evaluated independently in this order:

1. Schema validity: complete IDs, finite values, monotonic timestamps.
2. Kinematic validity: configured acceleration, deceleration, jerk, and yaw-rate limits.
3. Road validity: position stays inside an allowed lane/drivable corridor when the map mode supports it.
4. Simulator validity: XML parsing and esmini completion.
5. Quality/risk features: TTC, distance, variation magnitude, replay error.

The report must retain all check outcomes; it must not reduce a rejected scenario to a single boolean without reasons.

An initial transparent score is:

```text
score = novelty + risk_signal + replay_quality - feasibility_penalty
```

Weights are versioned configuration. A high score does not override failed validity checks.

## 8. Operational Requirements

- Python 3.11 or later.
- All external binary paths come from explicit configuration or environment variables, never hard-coded user paths.
- Each batch command writes a manifest containing command version, source IDs, map version, generator settings, and timestamp.
- The CI test suite must run without the full nuScenes dataset or esmini binary. Simulator integration tests are marked separately.

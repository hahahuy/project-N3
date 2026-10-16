# Wave 2 Implementation Report

## Scope

Implemented the next dependency-light Plan A slice:

- Optional raw keyframe provenance on canonical `State` values.
- ADE/FDE distribution aggregation.
- G4 physics and conservative G5 pre-event footprint gate evaluators.

This wave did not implement CP1 map builder, CP2 same-XOSC CARLA execution,
native simulator collision events, or batch orchestration for all gates.

## Files Changed

- `src/real2scenario/models.py`
  - Added optional `source_timestamp_us` and `source_record_token` fields.
  - Existing fixtures remain compatible because both fields are optional.
- `src/real2scenario/serialization.py`
  - Preserves optional state provenance when present without requiring it for old artifacts.
- `src/real2scenario/ingestion.py`
  - Carries source record tokens and source timestamps into extracted states.
- `src/real2scenario/metrics.py`
  - Added `MetricDistribution`, `ReplayMetricAggregate` and `aggregate_replay_metrics()`.
- `src/real2scenario/gates.py`
  - Added `evaluate_g4_g5()`.
  - G4 wraps the versioned physics feasibility report.
  - G5 requires event metadata and returns explicit `missing_event_definition` errors.
  - G5 currently uses a conservative footprint-radius pre-check; it is not a native simulator collision sensor.
- `src/real2scenario/__init__.py`
  - Exported new provenance/metric/gate APIs.
- `tests/test_models.py`, `tests/test_metrics.py`, `tests/test_gate_evaluators.py`
  - Added provenance, distribution and G4/G5 tests.
- `docs/plan-a-migration-checklist.md`
  - Updated implementation status for the Wave 2 slice.

## Evidence

```text
.venv/bin/python -m pytest -q
143 passed, 2 warnings in 2.40s
```

Targeted Wave 2 tests:

```text
50 passed, 1 warning in 0.12s
```

`git diff --check` passed. Remaining warnings are the known Starlette/httpx
deprecation and pytest cache permission warning.

## Contract Status

- Raw provenance fields are optional for backward compatibility, but ingestion now populates them for source states.
- ADE/FDE distributions are domain APIs; batch/report serialization of aggregate statistics is still open.
- G4 is executable at the domain layer and retains the existing validation version/config.
- G5 requires explicit event metadata and never infers the main event window.
- G5 is a conservative pre-check only until native simulator collision events are available.

## UNVERIFIED / Remaining Blockers

- Existing artifact fixtures do not all contain per-state raw provenance; migration/backfill is not performed.
- Aggregate ADE/FDE statistics are not yet wired into JSON/CSV batch reports or UI.
- G4/G5 are not yet represented as full G4/G5 entries in every `FunnelReport` from batch orchestration.
- G5 oriented footprint SAT/OBB accuracy and native simulator collision events remain open.
- G1/G2/G3/G6/G7 are not integrated into the batch pipeline.
- CP0 CARLA runtime sample evidence is not recorded in a phase report.
- CP1 map builder/road-match and CP2 same-XOSC CARLA interpreter remain open.

## Decision Log

- Optional provenance was chosen to preserve old artifact compatibility.
- Missing G5 event metadata is an explicit error, not an inferred event.
- No provisional threshold was promoted to a scientific final threshold.
- No Plan A scope, same-XOSC contract, license boundary or paper claim was changed.
- No raw nuScenes data or derived nuScenes artifact was added.
- No file was removed.

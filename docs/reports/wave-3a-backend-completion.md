# Wave 3A Backend Completion Report

## Scope

Implemented the first U0 authoring-compatible backend slice: actor-scoped
parameterized preview edits and a synthetic-fixture-compatible API endpoint.

## Files Changed

- `src/real2scenario/generation.py`: `ActorMotionEdit` and deterministic
  `preview_variant` with speed, heading, gap and timing edits.
- `src/real2scenario/__init__.py`: public exports.
- `src/r2s_web/schemas.py`: preview request/response and gate response models.
- `src/r2s_web/jobs.py`: synchronous `PreviewService` and private preview
  artifact output.
- `src/r2s_web/app.py`: `POST /api/scenarios/{scenario_id}/variants/preview`.
- `tests/test_models.py`, `tests/test_web_api.py`: focused contract tests.

## Tests

Focused command:

```text
.venv/bin/python -m pytest -q tests/test_models.py tests/test_web_api.py
31 passed, 2 warnings
```

Full-suite command:

```text
.venv/bin/python -m pytest -q
153 passed, 2 warnings
```

The warnings are an existing Starlette/httpx deprecation and a local pytest
cache permission warning.

## Runtime Evidence

The endpoint returns deterministic child IDs for repeated parent/config/seed
requests, generated paths, parent/config/seed provenance, validation reasons,
G4/G5/G6/G7 results and private artifact links. G6/G7 are explicitly marked
`PROVISIONAL`.

## Decisions Made

- Batch generation semantics were left unchanged; preview uses a separate
  actor-scoped primitive.
- `behavior` returns a structured `unsupported` response and never falls back
  to parameterized waypoint execution.
- Preview artifacts remain under the configured private output root.

## Unverified

- ADE/FDE values are not fabricated when no replay trace exists.
- No esmini replay is performed by the preview endpoint.
- Preview output contains edited time-indexed trajectory states, not generated
  camera, LiDAR, radar or simulator-rendered frames.
- The UI timeline does not yet retrieve or render a frame at the selected time.
- CP1 map acceptance, CP2 same-XOSC, CARLA execution, sensor/POV UI and final
  scientific thresholds remain unverified.
- Multi-actor/heading preview artifact persistence uses the existing v1 variant
  artifact envelope; response configuration/provenance is authoritative for
  those fields until a future schema version is approved.

## Blockers

The assigned domain and UI subagents were unable to write or execute tests;
their blocked reports are retained in `docs/reports/`. U0 frontend work remains
planned pending API consumption.

## Next Agent

Implement typed frontend preview consumption and U0 controls, then produce the
showcase evidence bundle without claiming CP1/CP2/CARLA completion.

## Files Not Touched

CP1 map builder, CP2 XOSC/CARLA runtime, simulator adapters and raw dataset
artifacts were not changed by this checkpoint.

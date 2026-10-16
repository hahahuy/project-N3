# Parallel Contract Completion Report

> Historical contract snapshot. Current status is in `docs/current/` and later
> dataset/CP1 reports.

## Scope

Implemented the remaining dataset-independent contracts while full nuScenes
data is being prepared:

- CP2 XOSC parser now exposes initial positions and trajectory vertices as a
  validated intermediate execution plan.
- Added normalized CARLA trace state and cleanup report contracts.
- Variant reports can now carry optional structured gate results without
  breaking existing report constructors.

## Files

- `src/real2scenario/xosc_subset.py`
- `src/real2scenario/carla_trace.py`
- `src/real2scenario/reporting.py`
- `src/real2scenario/__init__.py`
- `tests/test_xosc_subset.py`

## Evidence

```text
.venv/bin/python -m pytest -q
149 passed, 2 warnings in 2.48s
```

`git diff --check` passed.

## Status

- XOSC subset parse plan: `IMPLEMENTED` at domain-contract level.
- Same-XOSC hashes: `IMPLEMENTED`.
- Normalized CARLA trace schema: `IMPLEMENTED` at domain-contract level.
- Cleanup report schema: `IMPLEMENTED` at domain-contract level.
- Optional gate results in variant reports: `IMPLEMENTED`.
- CARLA interpreter/API execution: `OPEN`.
- Custom XODR import and same-XOSC CARLA run: `UNVERIFIED`.
- CP1 vector map builder: this report predates the external vector-map update;
  see `cp1-map-builder-prototype.md` for current prototype status.

## Explicit Non-Claims

- No CARLA runtime claim was added.
- No same-XOSC paired simulator evidence was generated.
- No OpenDRIVE map was generated from raster-only nuScenes files.
- No provisional threshold was promoted to a scientific final threshold.
- No restricted data or derived nuScenes artifact was added.
- No file was removed.

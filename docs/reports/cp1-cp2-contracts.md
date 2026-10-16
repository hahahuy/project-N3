# CP1/CP2 Contract Implementation Report

> Historical pre-trainval-data snapshot. Current CP1 data/prototype status is
> in `dataset-update.md` and `cp1-map-builder-prototype.md`.

## Scope

Implemented the verifiable, dependency-light parts of the approved CP1/CP2
technical contracts: the CP1 OpenDRIVE subset/manifest contract, deterministic
IDs, the CP2 fail-closed XOSC subset parser, and same-artifact SHA-256 identity.

## Files

- `src/real2scenario/mapbuilder/__init__.py`
- `src/real2scenario/xosc_subset.py`
- `src/real2scenario/__init__.py`
- `tests/test_mapbuilder_contract.py`
- `tests/test_xosc_subset.py`

## Evidence

```text
Targeted: 5 passed, 1 warning in 0.07s
Full suite: 148 passed, 2 warnings in 2.37s
```

`git diff --check` passed.

## Boundary

This report predates the external `v1.0-trainval` dataset update. The current
dataset contains Singapore One-North vector map expansion and a local line
prototype run; see the later reports named above.

The CARLA image contains an OpenDRIVE utility file and Python client, but this
report does not claim project-generated XODR import or same-XOSC CARLA execution.

## Status

- CP1 deterministic IDs/manifest/structural contract: `IMPLEMENTED`.
- CP1 real map builder and road-match: historical status; see later reports.
- CP2 XOSC subset parser/hash identity: `IMPLEMENTED`.
- CP2 CARLA interpreter, custom XODR import and paired runtime: `OPEN/UNVERIFIED`.

No restricted data or derived artifact was added. No file was removed.

# CP1 Map Builder Prototype Report

## Run

Command executed outside the repository using the local dataset:

```text
.venv/bin/python - <<'PY'
from real2scenario.mapbuilder import build_opendrive_from_nuscenes
build_opendrive_from_nuscenes(
    "$NUSCENES_ROOT",
    output_path="$LOCAL_ARTIFACT_ROOT/cp1-map/singapore-onenorth-v1.xodr",
)
PY
```

## Result

- Map: `singapore-onenorth`.
- Roads emitted: `2002`.
- Geometry records: `12061`.
- Unsupported arcline records: `0`.
- Structural subset validation: passed.
- XODR SHA-256: `b7bde84a554529110ea99ec9d1def93cab763a2c92aa06797e731b5eb2005d4c`.
- Artifact location: `$LOCAL_ARTIFACT_ROOT/cp1-map/` (outside the repository).

## Limitations

- Current prototype discretizes every path and emits deterministic `line`
  segments; it does not yet fit constant-curvature portions to OpenDRIVE `arc`.
- It does not yet emit complete OpenDRIVE `junction` elements for connector
  topology.
- Lane width currently uses the declared fallback `3.5 m` rather than polygon
  estimates.
- Continuity and lane-level road-match are not yet computed.
- No esmini or CARLA map-load evidence is claimed from this run.

## Status

`CP1 prototype implemented; CP1 acceptance remains PARTIAL/UNVERIFIED.`

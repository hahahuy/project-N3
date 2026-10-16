# CP1 Corridor Priority Handoff

## Priority Change

CP1 execution is scoped to a declared scene-local corridor around `scene-0061`.
Full Singapore One-North coverage is deferred until the corridor is accepted
and the larger benchmark/index is approved.

## Required Deliverable

- source map: `singapore-onenorth`;
- source scene: `scene-0061`;
- trajectory corridor crop with an explicit `30-50 m` buffer decision;
- explicit boundary policy and selected lane/connector tokens;
- topology closure for selected connectivity edges;
- repaired junction/reference/link semantics inside the corridor;
- private corridor XODR, manifest and hashes;
- raw per-state and per-actor road-match observations;
- provisional status only, with no forced match threshold or scientific pass/fail.

## Existing Baseline Evidence

- `docs/reports/cp1-external-map-road-match-evidence.md`
- `docs/reports/cp1-scene-0061-alignment-analysis.md`
- `docs/reports/cp1-occupancy-candidate-diagnostics.md`
- `docs/reports/cp1-topology-repair-evidence.md`

These are full-map or synthetic baselines and must not be mistaken for corridor
acceptance.

## Explicit Deferrals

- Full Singapore One-North coverage.
- Alternate LiDAR/vector providers.
- CP2 same-XOSC CARLA execution.
- Final scientific thresholds or G3 acceptance.

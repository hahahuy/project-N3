# nuScenes-devkit Backend Makeover Handoff

Status: `CURRENT / PHASE 1 COMPLETE / PHASE 2 IMPLEMENTED-TESTED / ACCEPTANCE PARTIAL`
Owner decision: use available nuScenes data and official `nuscenes-devkit==1.2.0`
to improve backend calculations, while preserving artifact, license and evidence
boundaries.

## Read This First

This is the authoritative implementation handoff for the nuScenes backend
makeover. Do not use archived Plan B roadmaps or old CP1-first handoffs to choose
the next task. Historical reports remain useful as evidence, but they do not
override this document or `docs/current/technical-contracts.md`.

## Completed Phase 1

- `NuScenesSourceAdapter` loads optional CAN `pose` messages lazily.
- CAN ego speed is selected by nearest timestamp within `100000` microseconds.
- No timestamp extrapolation is allowed.
- Missing CAN data or unmatched timestamps use finite-difference fallback.
- Provenance records adapter version, CAN status and sample count.
- Polygon lane widths prefer `polygon-cross-section-median-v1`.
- Area-over-centerline and constant-width fallbacks remain explicit.
- Canonical `State`, CP1 baseline, matcher tolerances and scientific thresholds
  were not changed.

Evidence:

- `src/real2scenario/nuscenes_backend.py`
- `src/real2scenario/ingestion.py`
- `src/real2scenario/mapbuilder/__init__.py`
- `tests/test_nuscenes_backend.py`
- `tests/test_ingestion.py`
- `docs/current/nuscenes-devkit-leverage-proposal.md`

## Phase 2 Objective

Build a coherent devkit-backed source capability layer, in this order:

1. Integrate CAN acceleration and yaw-rate into the Tier 1
   `kinematic-open-loop-v1` preview contract without changing the canonical
   `State` until the source-state extension is specified.
2. Extend the native map adapter with read-only records for `road_segment`,
   `road_block`, `stop_line`, `traffic_light`, `ped_crossing`, `walkway`,
   `lane_divider`, `road_divider` and `drivable_area`.
3. Add provenance-bearing map patch and road-ahead query services for the U1
   workspace. Do not replace the existing OpenDRIVE builder.
4. Serve a private, decimated `LIDAR_TOP` payload for the LiDAR POV with
   timestamp, calibration, frame and source-file provenance. Never commit point
   clouds or derived payloads.
5. Add nuScenes prediction evaluation as a separate advisory benchmark. Do not
   mix it with recorded-vs-replayed ADE/FDE or simulator self-consistency.
6. Expose CAN coverage, route blacklist and sensor capability status in reports.
7. Wire simulator-backed third-person and in-car POVs through esmini/CARLA
   capability contracts; do not claim a POV from a static placeholder.

## Phase 2 Implementation Evidence

Source-state, native map/query, private LiDAR descriptor, Workspace authoring,
timeline, gate, lineage, Compare and advisory prediction contracts are
implemented in `src/real2scenario/source_state.py`,
`src/real2scenario/kinematic.py`, `src/real2scenario/native_sources.py` and
`src/r2s_web/`.
Tier 1 propagation now includes explicit limit diagnostics, no silent clamps,
normalized trace output and a fail-closed footprint pre-check.
Focused evidence is in `tests/test_phase2_sources.py`, `tests/test_web_api.py`,
`tests/test_workspace_authoring.py`, `frontend/src/workspace.test.tsx` and
`docs/reports/workspace-live-acceptance.md`. Tier 1 esmini comparison, post-edit
sensor frames and CARLA same-XOSC remain open.

## Boundaries

- Raw nuScenes and derived artifacts remain local/private.
- CAN is a measured ego signal, not an intent or behavior ground truth.
- Route data is diagnostic only and must not overwrite recorded trajectories.
- CP1 `20/143 = 13.99%` remains immutable until a separate approved decision.
- Native map data is an oracle/input source; it does not replace project export
  or OpenSCENARIO contracts.
- Recorded LiDAR is evidence, not regenerated sensor output.
- CARLA same-XOSC remains post-MVP and is not part of this makeover.
- Do not add a heavy 3D/rendering dependency to the backend data layer.

## Required Verification

Every phase must include focused tests, full tests, docs consistency, capability
status, fallback behavior and a private-data review. A phase is not complete
because the devkit API imports; it needs deterministic contracts and evidence.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

## Next Agent Action

Finish the remaining acceptance sequence: add per-sample text equivalents and
review real CAN pedal availability; complete constrained maneuver UX and Tier 1
comparison; add explicit variant sensor fallback/status only where supported;
then implement esmini image-frame rendering and final browser evidence. Keep
CARLA same-XOSC post-MVP and do not replace missing frames with placeholders.

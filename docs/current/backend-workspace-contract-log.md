# Backend Workspace Contract Log

Status: `ACTIVE / BACKEND TASK REGISTER`
Consumer: frontend Workspace agents
Primary specification: `docs/current/ui-mvp-flow-spec.md`
Frontend log: `docs/current/frontend-workspace-log.md`

## Purpose

This is the contract register for data the Workspace needs but must not invent.
Backend work should update the status, endpoint, schema, tests, and evidence for
each item. Frontend agents should link their changes to these rows before using
new fields.

## Required contract work

| ID | Capability | Required fields / behavior | Milestone | Status |
|---|---|---|---|---|
| B-WORKSPACE-01 | Workspace document metadata | document name, branch, version, active scenario, connection/dataset/esmini status, coordinate frame, transform version | U1 | Implemented; `GET /api/workspace/documents/{scenario_id}` |
| B-WORKSPACE-02 | Scenario view payload | native map layers, actor pose/state timeline, role/ego marker, dimensions, recorded/generated paths, layer availability and reasons | U1/U5 | Implemented partial; real actor state and devkit map geometry are wired when dataset/devkit are available |
| B-WORKSPACE-03 | Recipe representation | ordered steps, id, kind, constrained maneuver params, status, active/inactive state, API error, artifact link | U2 | Implemented partial; preview response carries named ordered constrained steps and rollback marker |
| B-WORKSPACE-04 | Gate timeline | G1-G7 status, observed value, reason, scientific status, start/end extents aligned to actor time | U3 | Implemented partial; `workspace-gate-timeline-v1` returns every segment with status, reasons, observed values, scientific status and scenario-time or declared-event extents |
| B-WORKSPACE-05 | Variant lineage | parent scenario id, branch name, variant configuration, run id, seed, config hash | U4 | Partial; existing variant fields are not a complete lineage contract |
| B-WORKSPACE-06 | Metric availability | value, unit, status, scientific status, availability block, unavailable reason, mean/p95/max distinction | U3/U4 | Implemented partial; workspace and batch/preview surfaces expose explicit replay metric availability |
| B-WORKSPACE-07 | 3D/POV scene data | native/XODR map geometry, actor dimensions/transforms, third-person and in-car simulator frame source/status | U5 | Implemented partial; internal kinematic transform renderer is available with timestamped frame contract; `workspace-pov-image-v1` serves only real private esmini image artifacts and CARLA remains separate/unavailable |
| B-WORKSPACE-08 | LiDAR sweeps | sensor channel, timestamp, nearest-sweep offset, binary x/y/z/intensity payload, frame, calibration and transform version | U6 | Implemented partial; private descriptor and decimated payload routes serve real LIDAR_TOP with sensor/global transforms when configured |
| B-WORKSPACE-09 | LiDAR decimation | total count, returned count, decimation metadata, explicit availability/reason | U6 | Implemented in payload metadata |
| B-WORKSPACE-10 | Variant sensor status | explicit post-edit sensor-frame support status and parent-sweep fallback status/reason | U6 | Implemented partial; the `sensor-evidence` layer reports post-edit frames as `unsupported` with a reason and carries the recorded parent sweep as an explicit fallback |
| B-WORKSPACE-11 | Constrained maneuver edit | actor, time range, steering/heading, acceleration/braking, target speed, timing and limit profile; reject arbitrary displacement edits | U2 | Implemented partial; named recipe steps, explicit limits/violations, immutable-parent marker and Tier 1 provenance returned |
| B-WORKSPACE-12 | View layout and POV manager | main view, side views, rearrange/make-main, close, source/simulator/frame provenance | U1/U5/U6 | Partial; frontend supports add/rearrange/make-main/maximize/close and capability-labelled views |
| B-WORKSPACE-13 | Recipe document | ordered steps with index, id, name, kind, constrained maneuver parameters, step status, active/inactive state, API error, limit violations, artifact link; rollback markers; non-destructive undo/redo history; immutable parent | U2 | Implemented; `workspace-recipe-v1` on the recipe routes below |
| B-WORKSPACE-14 | Variant lineage and branch identity | parent scenario id, lineage path with presence flags, branch id/name and their source, variant configuration, seed, config hash, run id, generator/dataset/transform version, source scene token, child scenario ids, per-field completeness reasons | U4 | Implemented partial; `workspace-variant-lineage-v1`; a field that no artifact declares is `null` with an API-owned reason and is never defaulted |
| B-WORKSPACE-15 | Compare surface | left/right scenario descriptors with lineage identity, synchronized timestamp time domain, per-actor state deltas with availability, metric comparison with provenance and scientific status, gate comparison with statuses, reasons and scientific status, evidence layers per side | U4 | Implemented; `workspace-compare-v1` |
| B-WORKSPACE-16 | Evidence layers | one entry per `recorded`, `generated`, `replayed` and `sensor-evidence` layer with status, unavailable reason, source, provenance, coverage, scientific status and the surface that shows it | U1/U4/U6 | Implemented; `workspace-evidence-layers-v1` |
| B-WORKSPACE-17 | Variant sensor status | explicit `available`/`unsupported`/`unavailable` status for post-edit sensor frames, parent-sweep fallback availability, parent scenario id, source, timestamp and provenance; no regenerated-frame claim without an artifact | U6 | Implemented; `workspace-variant-sensor-v1` |
| B-WORKSPACE-18 | Esmini image frame artifacts | timestamp-addressable real esmini image artifacts, mode, frame id, simulator/version, artifact link, timestamp tolerance and unavailable reason; transform-only internal preview remains distinct | U5 | Implemented partial; `workspace-pov-image-v1`; serves only private artifacts produced by configured esmini capture and remains unavailable otherwise |

### Recipe status vocabulary (B-WORKSPACE-13)

Step status is fixed and separate from the scientific status vocabulary:

| Status | Meaning |
|---|---|
| `valid` | constrained parameters were accepted and are inside the Tier 1 kinematic limit profile |
| `invalid` | parameters were accepted but exceed a Tier 1 limit; `violations` names the limit, the observed value and the actor |
| `error` | the API rejected the step (unknown actor, non-finite value, end before start, unknown step); `error` carries the API message |

A step after the active rollback marker is `active: false` with
`inactive_reason: after_active_rollback_marker`; it keeps its parameters and its
status and is excluded from the applied preview. Undo and redo move between whole
document snapshots (steps, markers, active marker, preview) and never write to the
canonical scenario or its artifacts.

## Contract rules

- Every availability block must include a boolean and an API-owned reason when
  unavailable. Missing arrays are not an availability protocol.
- A field the backend cannot resolve is `null` with a named reason, never `0`,
  `""`, or an inferred default. A hash names the artifact content it covers.
- Recipe step status vocabulary (`valid`, `invalid`, `error`) is fixed separately
  by B-WORKSPACE-13.
- Status vocabulary is fixed: `pass`, `fail`, `skipped`, `error`, `valid`,
  `invalid`, `simulator-failed`, `unavailable`, `unsupported`, `PROVISIONAL`,
  and `not-applicable`.
- Preserve provenance: dataset/version, source scene token, transform version,
  reference-point convention, run id, seed, config hash, and artifact links.
- Do not make frontend-only compatibility aliases part of the public contract.
- Add API schema tests and web API tests for every contract change.

## Backend change protocol

Append a row after implementation:

| Date | ID | Endpoint/schema | Tests/evidence | Frontend impact | Status |
|---|---|---|---|---|---|
| 2026-10-14 | B-WORKSPACE-01,02,06,12 | Workspace document/scenario and native map capability/patch/road-ahead routes | `tests/test_web_api.py`, `docs/reports/backend-workspace-contract-slice.md` | Frontend may consume typed metadata, actor state arrays, capability blocks and native map queries; POV/LiDAR/maneuver payloads remain open | Implemented partial |
| 2026-10-14 | B-WORKSPACE-02,07,08,09,11,12 | Workspace scenario native geometry, maneuver fields, LiDAR capability/payload routes and frontend view manager | `tests/test_web_api.py`, `tests/test_phase2_sources.py`, `frontend/src/api.test.ts` | Top-down consumes real map/state payloads; edit controls submit constrained fields; POV/LiDAR remain explicit capability states | Implemented partial |
| 2026-10-14 | B-WORKSPACE-07,12 | `GET /api/workspace/scenarios/{scenario_id}/frames/{mode}`, `simulator-frame-v1` capability/frame schemas | `tests/test_web_api.py`, `frontend/src/api.test.ts` | Third-person and in-car panes synchronize timestamped internal transform frames to the Workspace playhead | Implemented partial |
| 2026-10-14 | B-WORKSPACE-08,09 | `GET /api/workspace/scenarios/{scenario_id}/lidar` descriptor and `GET /api/workspace/lidar/{sample_data_token}` binary payload | `tests/test_web_api.py`, `frontend/src/api.test.ts`, `docs/reports/workspace-live-acceptance.md` | LiDAR pane fetches real private payload, applies API calibration/ego transforms, exposes decimation and counts, and labels partial/unavailable states | Implemented partial; post-edit frames not claimed |
| 2026-10-14 | B-WORKSPACE-02,04 | `GET /api/workspace/scenarios/{scenario_id}/timeline` (`workspace-actor-timeline-v1`) and `GET /api/workspace/scenarios/{scenario_id}/gate-timeline` (`workspace-gate-timeline-v1`), plus `gates` on the scenario view payload | `tests/test_web_api.py`, `tests/test_nuscenes_backend.py`, `frontend/src/api.test.ts`, `frontend/src/workspace.test.tsx` | Actor tracks render position, heading, speed, acceleration and braking with per-channel availability; the gate lane shows pass/fail/skipped/error/unsupported plus PROVISIONAL with API-owned reasons and extents; missing values stay `n/a` | Implemented partial; brake pedal requires a source scene with recorded timestamps |
| 2026-10-14 | B-WORKSPACE-03,11 | Preview response recipe steps, Tier 1 limit/violation profile and rollback marker | `tests/test_web_api.py`, `frontend/src/api.test.ts` | Edit mode names ordered steps, selects start/end time, exposes limits/violations/provenance and browser history controls; parent remains immutable | Implemented partial; sensor frames and full persisted recipe API remain open |
| 2026-10-15 | B-WORKSPACE-06,10,13,14,15,16 | `workspace-recipe-v1`, `workspace-variant-lineage-v1`, `workspace-compare-v1`, `workspace-evidence-layers-v1`; recipe, lineage, compare and evidence-layer routes; metric provenance/scientific-status fields | `tests/test_workspace_authoring.py`, `tests/test_web_api.py`, `frontend/src/api.test.ts`, `frontend/src/workspace.test.tsx`; live browser smoke against explicit no-dataset local runtime | Recipe panel consumes ordered parameter/status rows, rollback markers and API undo/redo; Variant studio consumes branch/seed/config hash; Compare consumes synchronized deltas, metric/gate status and layer provenance; sensor-evidence remains unsupported for post-edit frames with parent fallback | Implemented partial; recipe history is in-process only, replay metrics remain PROVISIONAL, esmini image frames/CARLA same-XOSC remain separate |
| 2026-10-15 | B-WORKSPACE-17,18 | `workspace-variant-sensor-v1`, `workspace-pov-image-v1`; variant sensor-status and private esmini image-frame routes; optional capture configuration is API-owned and fail-closed | `tests/test_web_api.py`, `tests/test_esmini_backend.py`, `frontend/src/api.test.ts`, `frontend/src/workspace.test.tsx`; no static image is accepted as evidence | LiDAR/evidence surfaces consume explicit parent fallback; POV panes use an image artifact only when a real esmini capture manifest exists, otherwise retain the internal transform frame or named unavailable state | Implemented partial; capture requires a configured esmini runtime with viewer/off-screen support, and CARLA remains out of scope |

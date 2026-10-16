# Frontend Workspace Change Log

Status: `ACTIVE`
Owner: frontend agents
Primary specification: `docs/current/ui-mvp-flow-spec.md`
Backend contract log: `docs/current/backend-workspace-contract-log.md`

## Purpose

This document records frontend changes against the Workspace specification. Each
future frontend change must identify its milestone, the spec section it fulfils,
the API fields it consumes, and the verification performed. Do not mark a
milestone complete from a visual approximation alone.

## Current baseline

| Area | State | Evidence / next action |
|---|---|---|
| Workspace shell | Implemented for U1 | `frontend/src/App.tsx`, `frontend/src/styles.css`; verify desktop and tablet screenshots |
| Title bar and status chips | Implemented against current API | `GET /api/esmini` and `GET /api/settings` drive two-phase green chips; hover or click opens the detail list |
| Toolbar | Partial | U1 shell exists; disabled commands explain that they are unavailable in this build; overflow menu replaces scrolling |
| Left icon strip and panel | Partial | Catalog works from existing scenario endpoints; Recipe remains an honest empty state; panel is drag-resizable |
| Right icon strip and flyouts | Partial | Metrics, provenance, and artifacts now read live scenario data; G1-G7 gates still need a selected run or variant |
| View manager | Implemented for U1 | 0-4 views, close-last-view empty state, reset layout, responsive stacking |
| Top-down view | Implemented against current API | Recorded/generated trajectory overlay; map and actor geometry await backend fields |
| 3rd-person POV | Backend/UI wiring open | U5, requires simulator frame contract and renderer; native map data is available |
| LiDAR 3D | Backend/UI wiring open | U6, requires private decimated point-cloud payload and calibration contract; source data is available |
| Timeline | U1 placeholder only | Full gate lane and actor tracks are U3 |

## Change protocol

For every change, append a row:

| Date | Agent / change | Milestone + spec sections | Backend fields used | Verification | Open issues |
|---|---|---|---|---|---|
| 2026-10-14 | U1 workspace shell and Top-down view | U1; sections 4, 5, 6, 11 | Existing scenario and trajectory endpoints | `npm test`; `npm run build`; `git diff --check` | Screenshot evidence and real map geometry pending |
| 2026-10-14 | Dev proxy fix, backend wiring of dead controls, CAD restyle, dark mode, handbook | U1; sections 4, 5, 6, 9, 11, 13 | `/api/settings`, `/api/esmini`, `/api/scenarios/{id}/artifacts`, `/api/artifacts/{path}`, `/api/scenarios/{id}/trajectory` | `npm run build`; `npm test`; `pytest -q` (258 passed, 1 skipped); live proxy check of all consumed routes against local uvicorn | CARLA has no endpoint; no single-scenario export route; `frontend/src/{workspace,state,tokens.css}` layout from spec section 13 still not built |
| 2026-10-14 | Restore files dropped by merge `05cd7d5` | U1; sections 4, 11, 13 | Unchanged; this is a restoration only | `npm run build` (CSS 20.43 kB, was 10.77 kB); `npm test`; `scripts/check_docs_consistency.py`; proxy returns 200 | Merge reset six frontend/config files and four docs to pre-merge state while keeping the new `App.tsx`; `tsc` cannot detect this. Workspace endpoints from `49c6bc3` are client-side only and 404. |
| 2026-10-14 | Recorded LiDAR POV | U6; sections 6, 9, 10, 11 | `/api/workspace/scenarios/{id}/lidar`, `/api/workspace/lidar/{sample_data_token}`, `X-R2S-Lidar-Metadata` calibration/ego transforms, timestamp, frame, decimation and counts | `frontend/src/api.test.ts`; `npm test`; `npm run build`; local browser smoke evidence in `docs/reports/workspace-live-acceptance.md` | Canvas projection is recorded sensor data only; partial, unavailable and loading states are explicit; no post-edit sensor frame claim |
| 2026-10-15 | U2/U4 recipe, lineage, evidence and Compare workflow | U2/U4/U6; sections 3, 5, 7, 8, 9, 10, 11 | `workspace-recipe-v1`, `workspace-variant-lineage-v1`, `workspace-compare-v1`, `workspace-evidence-layers-v1`; metric provenance/scientific status | `frontend/src/api.test.ts`; `frontend/src/workspace.test.tsx` (36 total frontend tests); `scripts/workspace_browser_smoke.mjs`; `npm test`; `npm run build`; live browser smoke against local API with dataset explicitly unavailable | Recipe history is in-process and visibly unavailable for persistence; browser smoke with the incomplete default dataset was blocked by the existing `/api/settings` metadata-index failure, while the explicit no-dataset runtime returned 200 and no current console errors; raw/sensor artifacts remain local/private |
| 2026-10-15 | Browser acceptance and real POV/sensor capability boundary | U2/U3/U4/U5/U6; sections 5, 6, 8, 9, 10, 11, 12 | `workspace-variant-sensor-v1`, `workspace-pov-image-v1`, existing timeline/gate/LiDAR/frame contracts | Live browser walkthrough at desktop local runtime covered timeline/gate text equivalents, recipe parameter entry, Tier 1 valid preview, immutable-parent/rollback status, synchronized Compare, keyboard-addressable controls and evidence-layer status with zero console errors; mobile/reduced-motion/component/API suites remain green; `npm test` 37 passed, build passed | Explicit no-dataset runtime reports LiDAR and esmini image artifacts unavailable; transform POV remains available separately; esmini image capture requires configured viewer/off-screen support and a real private capture manifest; no CARLA same-XOSC |

## Frontend rules for future agents

- Implement only the current milestone unless the owner explicitly advances it.
- Keep unavailable features visible with a reason; do not hide them or fake data.
- Native map data is available through backend capability/patch/road-ahead routes;
  the remaining UI task is to consume those routes rather than label map data
  unavailable by default.
- Never render a metric, gate, or score without status and scientific status.
- Keep `PROVISIONAL`, `unsupported`, `unavailable`, and `skipped` explicit.
- Do not change backend contracts to simplify a component.
- Add component/API tests for each new behavior.
- Add desktop and tablet evidence under `docs/evidence/` for milestone work.
- Preserve exact Workspace nouns from the specification.

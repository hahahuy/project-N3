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
| 3rd-person POV | Intentionally unavailable | U5, requires map geometry and actor dimensions |
| LiDAR 3D | Intentionally unavailable | U6, requires point-cloud contract |
| Timeline | U1 placeholder only | Full gate lane and actor tracks are U3 |

## Change protocol

For every change, append a row:

| Date | Agent / change | Milestone + spec sections | Backend fields used | Verification | Open issues |
|---|---|---|---|---|---|
| 2026-10-14 | U1 workspace shell and Top-down view | U1; sections 4, 5, 6, 11 | Existing scenario and trajectory endpoints | `npm test`; `npm run build`; `git diff --check` | Screenshot evidence and real map geometry pending |
| 2026-10-14 | Dev proxy fix, backend wiring of dead controls, CAD restyle, dark mode, handbook | U1; sections 4, 5, 6, 9, 11, 13 | `/api/settings`, `/api/esmini`, `/api/scenarios/{id}/artifacts`, `/api/artifacts/{path}`, `/api/scenarios/{id}/trajectory` | `npm run build`; `npm test`; `pytest -q` (258 passed, 1 skipped); live proxy check of all consumed routes against local uvicorn | CARLA has no endpoint; no single-scenario export route; `frontend/src/{workspace,state,tokens.css}` layout from spec section 13 still not built |

## Frontend rules for future agents

- Implement only the current milestone unless the owner explicitly advances it.
- Keep unavailable features visible with a reason; do not hide them or fake data.
- Never render a metric, gate, or score without status and scientific status.
- Keep `PROVISIONAL`, `unsupported`, `unavailable`, and `skipped` explicit.
- Do not change backend contracts to simplify a component.
- Add component/API tests for each new behavior.
- Add desktop and tablet evidence under `docs/evidence/` for milestone work.
- Preserve exact Workspace nouns from the specification.

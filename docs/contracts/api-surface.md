# API Surface

The FastAPI application currently uses a flat `/api` namespace. The authoritative
route decorators are in `src/r2s_web/app.py`; this page groups routes by role
rather than duplicating every response field.

## Catalog and Artifacts

- `GET /api/scenarios`
- `GET /api/scenarios/{scenario_id}`
- `GET /api/scenarios/{scenario_id}/trajectory`
- `GET /api/scenarios/{scenario_id}/artifacts`
- `GET /api/artifacts/{artifact_path}`

## Workspace

- `GET /api/workspace/documents/{scenario_id}`
- `GET /api/workspace/scenarios/{scenario_id}`
- `GET /api/workspace/scenarios/{scenario_id}/timeline`
- `GET /api/workspace/scenarios/{scenario_id}/gate-timeline`
- `GET /api/workspace/scenarios/{scenario_id}/lineage`
- `GET /api/workspace/scenarios/{scenario_id}/compare`
- `GET/POST /api/workspace/scenarios/{scenario_id}/recipe/...`
- `GET /api/workspace/scenarios/{scenario_id}/frames/{mode}`
- `GET /api/workspace/scenarios/{scenario_id}/image-frames/{mode}`

## Dataset and Evidence

- `GET /api/source-scenes`
- `POST /api/source-scenes/{scene_token}/import`
- `GET /api/workspace/maps/{map_name}/...`
- `GET /api/workspace/scenarios/{scenario_id}/lidar`
- `GET /api/workspace/lidar/{sample_data_token}`
- `GET /api/workspace/scenarios/{scenario_id}/sensor-evidence`
- `GET /api/workspace/scenarios/{scenario_id}/top-down`
- `POST /api/workspace/scenarios/{scenario_id}/wasm-pair` (private XOSC/XODR
  materialization for browser preview; does not create a native session)

## Simulation and Generation

- `POST/GET /api/replays...`
- `POST /api/batches`
- `GET /api/batches/{job_id}/results...`
- `POST /api/scenarios/{scenario_id}/variants/preview`
- `POST/GET/DELETE /api/esmini/live/...`

When adding a route, update the Pydantic schema, API tests, frontend helper if
consumed, and the relevant subsystem contract register.

# Web Backend

Code: `src/r2s_web/`

The web backend adapts domain services to a local FastAPI API. It owns route
mapping, request validation, service composition, availability contracts,
filesystem confinement and web-session state.

## Source Map

| Module | Responsibility |
|---|---|
| `app.py` | App factory, route handlers, middleware and frontend static mount |
| `schemas.py` | Pydantic request/response contracts |
| `adapter.py` | Discover/load canonical artifacts and build web view models |
| `jobs.py` | Batch generation, preview orchestration and private outputs |
| `recipe.py` | In-process non-destructive recipe documents |
| `esmini.py` | Async subprocess replay and image artifact lookup |
| `live_session.py` | Optional native esminiLib lifecycle and state contract |
| `source_scenes.py` | Local nuScenes scene discovery/import |
| `lidar.py` | Private recorded LiDAR descriptors and payloads |
| `native_map.py` | Read-only devkit map queries |
| `frames.py` | Internal timestamped transform preview |
| `*_timeline.py`, `compare.py`, `lineage.py`, `evidence_layers.py` | Workspace projections |

## Route Shape

```text
HTTP request
  -> Pydantic request model
  -> route-local lookup/error mapping
  -> web service
  -> domain model or adapter
  -> response model / explicit unavailable payload
```

Routes should translate expected domain failures into stable HTTP responses.
Unexpected exceptions must not be converted into successful unavailable states.

## Important Boundaries

- `ArtifactAdapter.resolve_artifact()` is the artifact read boundary.
- `WebSettings.with_paths()` confines user-selected roots.
- `LiveSessionService` confines XOSC/XODR files and serializes native sessions
  because esminiLib state is process-global.
- `LidarService` exposes private decimated bytes and metadata, not raw dataset
  paths as a public filesystem API.
- `NativeMapService` exposes read-only normalized map records.
- `RecipeStore` never mutates canonical artifacts and remains in-process only.

## Known Limits

- Recipe state disappears on process restart.
- Batch creation is synchronous and still needs a public-exposure concurrency
  cap.
- Source-scene discovery is not paginated.
- Native esmini control remains unavailable unless the ABI supports it.

## Tests

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_web_api.py tests/test_live_session.py
```

Primary coverage is in `tests/test_web_api.py`, `tests/test_live_session.py`,
`tests/test_workspace_authoring.py` and adapter-specific tests.

The detailed field register remains in
[`../../current/backend-workspace-contract-log.md`](../../current/backend-workspace-contract-log.md).

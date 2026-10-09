# R2S-401 Local Web Demo Evidence

## Boundary

The local demo is split into a FastAPI adapter under `src/r2s_web` and a
React/Vite frontend under `frontend`. The adapter discovers strict baseline and
variant artifacts, maps canonical domain objects to API models, and calls the
public generation, validation, ranking, reporting, OpenSCENARIO, and optional
esmini APIs. React does not parse artifacts or duplicate domain calculations.

## Startup

```bash
python -m pip install -e ".[dev,web]"
uvicorn r2s_web.app:app --app-dir src --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The browser is available at `http://localhost:5173`; the API is at
`http://localhost:8000`. The backend uses `R2S_ARTIFACT_ROOT=scenarios` and
`R2S_OUTPUT_ROOT=reports` by default. `ESMINI_BIN` and `ESMINI_DAT2CSV` remain
shell-only optional settings.

## Point the demo at local scenes

Open the `LOCAL PATHS` control at the top of the browser. Enter paths visible
to the FastAPI process, then choose `APPLY PATHS`:

- `Artifact directory`: where canonical baseline/variant JSON files are read
  and where imported scenes are written. Default: `scenarios`.
- `nuScenes dataset root`: the directory containing the version directory.
  For this checkout the default is `data/v1.0-mini`.
- `Dataset version`: normally `v1.0-mini`.

After applying paths, the left catalog shows both existing artifacts and a
`nuScenes source scenes` section. Selecting `IMPORT` on a scene runs the
existing ingestion, interaction-selection, and road-alignment APIs, then writes
one canonical baseline artifact under `<artifact directory>/nuscenes/`.

The browser cannot grant a backend process access to an arbitrary folder using
a normal HTML folder picker. The path field is intentional: the path must be
visible to the machine/process running FastAPI. Absolute paths are accepted for
local use and are never written into committed artifacts or documentation.

The API equivalents are:

```text
GET  /api/settings
POST /api/settings
GET  /api/source-scenes
POST /api/source-scenes/{scene_token}/import
```

## Synthetic acceptance path

`tests/test_web_api.py` uses the committed sanitized fixture
`tests/fixtures/synthetic-variant-artifact.json` in a temporary project root.
It exercises:

- Empty artifact-root health state.
- Scenario catalog, detail, provenance, trajectory, and safe download routes.
- Recorded trajectory output and the local-template approximation warning.
- A 2 x 2 x 5 deterministic grid with seed `7` and 20 generated variants.
- Validation before ranking through the existing public APIs.
- Separate `simulator-failed` results when no esmini executable is configured.
- Stable variant IDs across two identical batch requests.
- Local nuScenes scene discovery and import into a local-road-aligned baseline.
- Generated-result review, generated trajectory styling, optional replay toggle,
  simulator failure detail, and valid-result OpenSCENARIO export.

Commands:

```bash
pytest -q
cd frontend && npm run build && npm test
```

No licensed nuScenes data, replay output, images, credentials, or
machine-specific absolute paths are committed.

# U0 Motion Editor Showcase Evidence

## Environment

- Date: 2026-10-12
- Frontend: Vite on `http://127.0.0.1:5173`
- API: project FastAPI app on `http://127.0.0.1:8001`
- Fixture: `tests/fixtures/synthetic-variant-artifact.json`
- Artifact root: `tests/fixtures`
- Output root: `reports/frontend-runtime`
- Dataset: intentionally disabled for the synthetic fixture run

## Startup

The repository `frontend/node_modules` directory was not writable and did not
contain Vite. Runtime verification used a writable temporary dependency install
under `$LOCAL_FRONTEND_ROOT` and a temporary Vite config with the same
source root, port and API proxy semantics. The project API was started with:

```text
R2S_PROJECT_ROOT=$PROJECT_ROOT \
R2S_ARTIFACT_ROOT=tests/fixtures \
R2S_OUTPUT_ROOT=reports/frontend-runtime \
NUSCENES_ROOT=$LOCAL_DATASET_ROOT \
.venv/bin/uvicorn r2s_web.app:app --host 0.0.0.0 --port 8001
```

Health response:

```json
{"status":"ok","artifact_root_configured":true,"scenario_count":1,"source_scene_count":0}
```

## Browser Flow

1. Opened the local frontend.
2. Confirmed the synthetic scenario appeared in the catalog.
3. Selected `synthetic-variant-001`.
4. Confirmed the recorded actor list, motion editor, timeline and unsupported
   behavior notice rendered.
5. Clicked `PREVIEW VARIANT` for the ego actor.
6. Confirmed the generated child ID appeared:
   `synthetic-variant-001--preview-aec1815e5d0ee3c4`.
7. Confirmed validation result and preview controls rendered.
8. Confirmed the final browser run had zero console errors.

## Expected Results

- Parent scenario remains visible.
- Generated preview path is overlaid with a distinct style.
- Preview status is `valid` for the neutral synthetic edit.
- G4/G5/G6/G7 response data is available in the preview panel.
- Behavior mode remains explicitly unsupported.
- Reset and export controls become enabled after preview.

## Limitations

- This is synthetic-fixture U0 product evidence only.
- No CARLA, same-XOSC, CP1 map acceptance, sensor or OSM claim is made.
- Frontend package installation in the repository directory remains blocked by
  filesystem permissions; the temporary dependency setup is not committed.
- No screenshot or recording is committed to the repository.

## Owner Runtime Confirmation

After the temporary host-only verification, repository dependency ownership was
corrected and the standard Compose stack was started successfully. Host ports
`5173` and `8001` were checked and available before startup. The owner
confirmed that the standard runtime flow runs correctly.

## UI0 Interaction Audit

- Review branch: `review/ui0-interaction-audit`
- Date: 2026-10-13
- Desktop viewport: 1280x900
- Mobile viewport: 390x844
- Fixture/runtime: the running local synthetic/API stack described above
- Initial browser console: one 404 was observed when selecting a generated
  batch result. The frontend attempted `GET /api/scenarios/{variant_id}` even
  though generated variants are served through the batch trajectory endpoint.
  This was fixed by using `fetchBatchTrajectory()` directly in
  `inspectResult()`; no backend contract was changed.

### Control Matrix

| Control | Result | Notes |
|---|---|---|
| `LOCAL PATHS` | PASS | Opens and closes the settings panel. |
| Path inputs + `APPLY PATHS` | PASS | Values submit and refresh the catalog with a success notice. |
| Scenario catalog buttons | PASS | Loads detail, actors, trajectory and provenance. |
| Actor buttons | PASS | Changes the selected actor/editor target. |
| Motion inputs and seed | PASS | Inputs remain editable and feed preview configuration. |
| `PREVIEW VARIANT` | PASS | Returns a valid deterministic child and generated overlay. |
| `VALIDATE` | PASS | Re-runs the preview/validation request and displays gate results. |
| `RESET` | PASS | Removes preview state and restores default edit values. |
| Preview `EXPORT CONFIG` | PASS | Starts a JSON download from the browser. |
| `Replay with esmini` checkbox | PASS | Toggles replay inclusion. |
| `GENERATE BATCH` | PASS | Produces 20 valid synthetic variants in the fixture run. |
| Batch result buttons | PASS after fix | Loads the selected variant trajectory without a 404 request. |
| `EXPORT XOSC` | PASS | Returns the export success notice and artifact link. |
| `RUN SELECTED WITH ESMINI` | PASS | Completed with exit 0 and displayed replay artifacts. |
| Timeline slider | PASS | Updates the displayed timeline timestamp. |
| Artifact links | PASS | Render as links to the local API artifact boundary. |

### Verification

```text
frontend: npm test -- --run
2 passed

frontend: npm run build
vite build succeeded

browser reload after fix: 0 console errors, 0 warnings
```

The generated batch-result 404 was the only UI defect found during this audit.
The local API, synthetic fixture, and esmini runtime remain local/private
evidence; this audit makes no CP1, CP2, CARLA, sensor, or scientific-threshold
claim.

## Next Checkpoint

Review the isolated branch and merge only after confirming the intended batch
variant trajectory contract. Keep clean-checkout dependency reproducibility and
owner review as separate release work.

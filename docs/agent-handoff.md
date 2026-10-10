# Agent Handoff: M5 Simulator-Backed UI

## Checkpoint

- Repository: `https://github.com/hahahuy/project-N3.git`
- Branch: `main`
- Current documented checkpoint: `main` after the M2 replay and M3 20-variant
  evidence updates.
- M2 evidence is in `docs/r2s-206-m2-replay-evidence.md`; M3 20-variant
  evidence is in `docs/r2s-306-20-variant-batch-evidence.md`.
- M4 R2S-401 local web demo is implemented and committed in `1982e00`.
- M4 R2S-402/R2S-403 local curated-scene and reproducibility documentation is
  present; the M4 review checklist still needs final human/demo sign-off.
- Approved M4 direction: local browser demo using FastAPI plus React, running
  on the current machine with local CPU, local esmini, and project-relative
  filesystem artifacts. See `docs/m4-local-demo-architecture.md`.
- Previous implementation checkpoints:
  - `f6df4c4` - Complete M3 batch reporting
  - `d1cd856` - Complete M3 generation and ranking
  - `61a38f1` - Complete M2 replay checkpoint
- The worktree was clean at the M4 implementation checkpoint; an untracked
  runtime `log.txt` may be present after local esmini execution and must not be
  committed.
- Latest verification after M3 reporting: `118 passed`,
  `python -m compileall -q src tests`, and `git diff --check`.

## What Exists

### Canonical contracts

`src/real2scenario/models.py` contains immutable dataclasses:

- `State`: time, position, yaw, and speed in SI units.
- `Actor`: ordered trajectory plus optional dimensions.
- `Scenario`: ego ID, actors, duration, coordinate frame, and provenance.
- `VariantConfig`: speed multiplier, initial gap delta, timing offset, and seed.

`src/real2scenario/serialization.py` provides strict schema-versioned baseline
and variant JSON artifacts. Required provenance must include dataset/version,
source scene/window, coordinate transform version, map reconstruction mode and
version, and generator version.

### M1 and M2 pipeline

- `preflight.py`: filesystem and metadata checks for local nuScenes data.
- `ingestion.py`: `SourceWindow` and `extract_scenario()` create a canonical
  scenario in `nuscenes_global` coordinates.
- `selection.py`: `SelectionConfig` and `select_interaction_actors()` choose
  one to three non-ego actors deterministically and store decisions in
  provenance.
- `coordinates.py`: source-to-`local_road_aligned` transform with provenance
  and inverse transform.
- `templates.py`: versioned straight-road OpenDRIVE template selection.
- `exporter.py`: deterministic `.xosc` generation and staged `.xodr` output.
- `simulation.py`: external esmini plus `dat2csv` execution and normalized
  `ReplayTrace`/`ReplayReport`.
- `metrics.py`: timestamp-aligned replay RMSE, final displacement, heading MAE,
  and speed MAE.
- `visualization.py`: top-down static plot and interactive scrub/play viewer.

### M3 constrained generation

- `generation.py`
  - `perturb_scenario()` creates an immutable child variant.
  - `generate_grid_variants()` creates stable Cartesian-product output.
  - `generate_random_variants()` creates seeded deterministic random output.
  - `BatchManifest` and serializers preserve order, IDs, configurations, and
    batch seed.
- `validation.py`
  - `FeasibilityLimits` is versioned and configurable.
  - `validate_feasibility()` checks acceleration, deceleration, jerk, yaw rate,
    and optional rectangular road boundary.
  - `FeasibilityReport` contains all structured rejection reasons.
- `ranking.py`
  - `compute_risk_features()` calculates timestamp-aligned minimum distance,
    conservative TTC, and parent-relative positional novelty.
  - `rank_scenario()` returns a transparent score breakdown.
  - A failed feasibility report is explicitly non-rankable.
- `reporting.py`
  - `VariantReport` status is exactly `valid`, `invalid`, or
    `simulator-failed`.
  - `AggregateReport` enforces `generated = valid + invalid + simulator_failed`.
  - JSON and CSV writers preserve artifact links, reasons, scores, and simulator
    errors.

Ticket evidence is in `docs/r2s-301-perturbation-evidence.md` through
`docs/r2s-305-reporting-evidence.md`.

## Important Current Limitation

Only these installed console commands exist today:

```text
real2scenario-preflight
real2scenario-devkit
real2scenario-visualize
```

M2/M3 generation, replay, validation, ranking, and reporting are public Python
APIs, not standalone CLI commands. Do not document or build UI calls around a
nonexistent `real2scenario replay` or `real2scenario generate` command. M4 may
add a local FastAPI plus React service boundary, but it must call the existing
APIs and preserve their contracts.

M4 contains a FastAPI application under `src/r2s_web` and a React/Vite frontend
under `frontend`. Do not replace this with Streamlit or introduce a second UI
framework.

The current UI can request optional esmini replay through `BatchService`, but
simulator execution is embedded directly in `src/r2s_web/jobs.py`. There is no
common simulator backend interface, no CARLA adapter, no CARLA capability
discovery, and no normalized CARLA trace contract yet. M5 must introduce those
boundaries before adding more simulator-specific UI logic.

## M4 Objective And Current Result

Build the smallest usable end-to-end UI around the existing canonical APIs:

1. Select or load a baseline/variant artifact.
2. Show provenance and source metadata.
3. Render recorded or generated top-down trajectories.
4. Configure and generate a deterministic batch.
5. Validate every generated variant.
6. Rank only valid variants and display score components.
7. Optionally export selected scenarios through the existing OpenSCENARIO
   writer and report writers.
8. Keep valid, invalid, and simulator-failed results visibly distinct.

The UI is an orchestration layer. It must not duplicate trajectory math,
validation thresholds, TTC, ranking, ID generation, or report reconciliation.

M4 implementation result:

- FastAPI endpoints exist for health, settings, source-scene import, scenario
  catalog/detail/trajectory, batch generation, result detail, export, and
  artifact download.
- React/Vite provides local path setup, source-scene import, scenario detail,
  trajectory display, batch controls, result status, simulator failure detail,
  and OpenSCENARIO export.
- The local batch service can generate, validate, rank, optionally replay with
  esmini, and persist reports under the local output root.
- M4 verification documented by `docs/r2s-401-local-web-demo.md` includes the
  synthetic API path and frontend build/test commands.

## First Steps For The Next Agent

1. Read `docs/pre-m4-procedure.md` completely.
2. Read `docs/wiki-cli-api-reference.md` for reproducible commands and API
   examples.
3. Run the clean-environment checks listed in the procedure.
4. Read `docs/m4-local-demo-architecture.md`; M4 is a local FastAPI plus React
   demo, not the shared customer platform.
5. Define the API adapter boundary before adding components. Keep the adapter
   responsible for loading artifacts, invoking APIs, and mapping result objects
   to response/view models.
6. Add UI smoke tests using synthetic fixtures before depending on licensed
   nuScenes data or an installed esmini binary.

## M4 Execution Plan (Completed)

The M4 slices below describe the completed baseline and are retained as context
for M5. Do not restart this work or redesign the canonical contracts.

### Slice 1: Project And API Skeleton

1. Add a backend package for the local FastAPI application. Keep it separate
   from `src/real2scenario`, which remains the canonical domain package.
2. Add a frontend package using the repository's selected React/TypeScript
   toolchain. Record the exact install and startup commands in the R2S-403
   documentation when chosen.
3. Add a health endpoint and a minimal React page that confirms the API is
   reachable.
4. Add a local configuration object for artifact root, optional dataset root,
   and optional esmini paths. Environment variables or command-line settings
   must supply machine-specific paths; do not hard-code them.

### Slice 2: Scenario Catalog And Detail

1. Define a backend adapter that discovers validated baseline/variant JSON
   artifacts below the configured project-relative artifact root.
2. Expose scenario summary data: scenario ID, parent ID when present, duration,
   coordinate frame, actor summaries, provenance, and available artifact links.
3. Add frontend scenario catalog and detail views.
4. The frontend must receive API response models; it must not open JSON files or
   construct filesystem URLs directly.

Suggested read-only endpoints:

```text
GET /api/health
GET /api/scenarios
GET /api/scenarios/{scenario_id}
GET /api/scenarios/{scenario_id}/artifacts
```

Endpoint names may change, but the separation between catalog, detail, and
artifact download should remain.

### Slice 3: Recorded And Replay Visualization

1. Add an API response model for trajectory series with actor ID, actor type,
   timestamps, positions, yaw, speed, and path kind.
2. Return recorded paths from the canonical scenario artifact.
3. Return replayed paths and metrics only when a normalized replay trace exists.
4. Add a top-down React view with a time slider and actor selection.
5. Use visibly different styles for recorded, replayed, and generated paths.
6. Show the coordinate frame and local-template approximation warning in the
   view; do not present the OpenDRIVE template as lossless map conversion.

Suggested endpoint:

```text
GET /api/scenarios/{scenario_id}/trajectory
```

The API should expose metrics and alignment metadata as structured fields,
including units and sample count. Do not recalculate metrics in React.

### Slice 4: Deterministic Batch Generation

1. Add a request model for speed multipliers, initial gap deltas, timing
   offsets, and seed. Keep SI units explicit in field names or UI labels.
2. Add a local job service that invokes `generate_grid_variants()` or
   `generate_random_variants()` through public package exports.
3. Validate every generated variant with `validate_feasibility()` before
   calling `rank_scenario()`.
4. Build `VariantReport` and `AggregateReport` using the existing reporting
   contract. Preserve `valid`, `invalid`, and `simulator-failed` as distinct
   statuses.
5. Write generated artifacts below a project-relative output directory and
   return stable job/result identifiers rather than absolute paths.
6. Add a frontend batch configuration panel and result summary table.

Suggested endpoints:

```text
POST /api/batches
GET  /api/batches/{batch_id}
GET  /api/batches/{batch_id}/results
GET  /api/batches/{batch_id}/results/{variant_id}
```

For the local demo, a bounded in-process or subprocess job implementation is
acceptable. Do not introduce Redis, Celery, PostgreSQL, object storage, or a
distributed worker queue for M4.

### Slice 5: Optional Replay And Export

1. Allow the user to select a generated valid variant for export/replay.
2. Call `select_opendrive_template()`, `write_openscenario()`, and optionally
   `run_esmini()` through a backend service.
3. Preserve simulator failures as `simulator-failed` with exit code, timeout,
   stderr, tool version, and trace path context.
4. Expose downloads for canonical JSON, `.xosc`, replay CSV, report JSON/CSV,
   and overlay image when present.
5. Keep replay optional for synthetic UI tests so the frontend test suite does
   not require a local esmini installation.

### Slice 6: R2S-402 And R2S-403 Evidence

1. Curate three local source scenarios: lead braking plus two supporting
   interaction types.
2. Ensure each has a baseline replay, a deterministic 20-variant batch, and a
   presentable valid result, or document the exact unavailable simulator state.
3. Add a project-relative curation index and do not commit raw nuScenes data,
   replay output, rendered images, or machine-specific paths.
4. Write the local setup/startup guide, demo script, UI smoke-test checklist,
   and clean-checkout verification note.
5. Record the expected valid/invalid/simulator-failed counts and browser steps.

## API And Domain Rules

- Use public exports from `real2scenario`; do not import private helpers.
- Keep Pydantic/API models separate from canonical dataclasses where practical.
- Do not change canonical model semantics to make JSON responses easier.
- Do not duplicate trajectory, validation, ranking, or report logic in FastAPI.
- Do not make React responsible for business decisions or artifact parsing.
- Preserve scenario ID, parent ID, seed, configuration, versions, provenance,
  and artifact references in every generated result.
- Return structured errors suitable for display; do not expose secrets or
  uncontrolled absolute paths.
- Treat a local job as auditable even though M4 has only one user.

## Suggested Local API View Models

The exact schema can evolve, but responses should cover these concepts:

```text
ScenarioSummary
  scenario_id, parent_scenario_id, duration_s, coordinate_frame, actors,
  provenance, available_artifacts

BatchRequest
  scenario_id, generation_mode, parameter_grid_or_ranges, seed,
  validation_limits, replay_enabled

JobStatus
  job_id, status, scenario_id, started_at, finished_at, error

VariantResult
  variant_id, status, validation, ranking, replay_metrics, artifacts
```

Use stable status values already defined by the reporting contract. Do not
replace them with a UI-only boolean such as `success`.

## Frontend Acceptance States

The React UI must demonstrate these states with the synthetic fixture before
using full local nuScenes data:

1. Empty/error state when no artifact root is configured.
2. Scenario catalog loaded.
3. Scenario detail with provenance and recorded path.
4. Replay overlay with metrics when a trace is available.
5. Batch form with visible units, ranges, and seed.
6. Batch running state with progress or an explicit local-job status.
7. Results with valid, invalid, and simulator-failed groups.
8. Invalid result with every structured rejection reason.
9. Valid result with score breakdown and risk/novelty components.
10. Artifact download links for the selected result.

## Do Not Build In M4 (Historical Boundary)

- User accounts or login screens.
- Project-level permissions.
- Shared-server deployment.
- PostgreSQL or S3-compatible storage.
- Redis/Celery or distributed workers.
- A workstation/local execution agent.
- Required server GPU infrastructure.
- CARLA integration.
- A new `real2scenario replay` or `real2scenario generate` CLI command unless
  the command is separately implemented, tested, and documented.

## M5 Objective: Simulator-Backed UI

M5 extends the local FastAPI plus React demo so a user can choose an execution
backend and run a supported scenario through esmini or CARLA from the browser.
M5 remains local-first: simulator binaries, CARLA installation, maps, assets,
and output directories are configured on the machine running FastAPI. Do not
turn M5 into the shared customer platform or add accounts, object storage,
PostgreSQL, or a distributed worker queue unless separately requested.

The M5 user flow is:

1. Open the local React application.
2. Select a canonical baseline or generated variant.
3. Open the simulator panel and inspect detected backend capabilities.
4. Choose `esmini` or `CARLA` only when the backend reports `available`.
5. Choose the execution mode supported by that backend, such as headless
   replay or rendered run.
6. Submit a simulator job with scenario ID, backend, backend version/config,
   timeout, seed, and output policy.
7. Watch job status and logs without blocking the browser request.
8. Inspect normalized trace, metrics, simulator-specific artifacts, and errors.
9. Compare the simulator result with the recorded/generated trajectory.
10. Download the report and all declared artifacts.

M5 success means the UI makes simulator choice and simulator health visible; it
does not imply that every scenario can run in every simulator. Unsupported map,
actor, sensor, or scenario features must be reported as unsupported rather than
silently approximated.

## M5 Execution Plan

Implement M5 in these vertical slices. Keep esmini and CARLA behind the same
application-level job contract, but do not force their internal execution
models to be identical.

### Slice 1: Common Simulator Contract

1. Add a simulator package separate from `real2scenario` domain models and
   separate from FastAPI route functions.
2. Define a backend protocol/interface with methods equivalent to:

```text
capabilities() -> SimulatorCapabilities
validate_input(request) -> list[StructuredIssue]
run(request, output_dir) -> SimulatorRunReport
```

3. Define capability and report models that include:

```text
SimulatorCapabilities
  backend_id: esmini | carla
  display_name
  available
  version
  supported_modes
  supported_formats
  configured_paths
  limitations
  error

SimulatorRunRequest
  scenario_id
  scenario_artifact
  backend_id
  mode
  timeout_s
  seed
  map_or_world_reference
  settings

SimulatorRunReport
  backend_id
  backend_version
  status: completed | failed | timed-out | unsupported
  command_or_launch_context
  exit_code
  timed_out
  stdout
  stderr
  normalized_trace_artifact
  simulator_artifacts
  metrics
  structured_issues
```

4. Keep `valid`, `invalid`, and `simulator-failed` result statuses. Add
   simulator backend/status fields instead of replacing the existing status
   contract.
5. Never expose raw secrets or uncontrolled absolute paths in API responses.
   Paths may be shown as safe artifact references and backend diagnostics may
   identify whether a configured path exists.

### Slice 2: Capability Discovery And Settings

1. Add backend settings for esmini and CARLA using environment variables or a
   local config file that is ignored by git.
2. Add capability probes that do not start a long simulation:
   - esmini executable and `dat2csv` availability plus version.
   - CARLA Python package, server executable, client version, and configured
     world/map roots.
3. Add an API endpoint such as:

```text
GET /api/simulators
GET /api/simulators/{backend_id}
```

4. Add a React simulator panel showing `available`, version, supported modes,
   missing configuration, and known limitations.
5. Disable run controls for unavailable backends while preserving a useful
   diagnostic message.

### Slice 3: Extract Esmini Backend

1. Move the current direct `run_esmini()` orchestration out of `jobs.py` into
   an `EsminiBackend` implementing the common simulator contract.
2. Preserve the existing `EsminiConfig`, `ReplayReport`, `ReplayTrace`,
   `dat2csv` normalization, timeout handling, exit code, stdout, stderr, and
   tool-version behavior.
3. Keep the OpenSCENARIO/OpenDRIVE preparation explicit:
   `select_opendrive_template()` -> `write_openscenario()` -> esmini ->
   `dat2csv` -> normalized trace -> metrics.
4. Ensure esmini output is written below the selected job output directory and
   does not leak a repository-root `log.txt`. Configure a log path explicitly
   or isolate execution in a temporary working directory.
5. Add backend tests using fake esmini and fake `dat2csv` executables for
   success, non-zero exit, timeout, missing executable, malformed trace, and
   missing OpenDRIVE/template cases.
6. Add one real local esmini smoke test only when `ESMINI_BIN` and
   `ESMINI_DAT2CSV` are configured; mark it optional in the test configuration.

### Slice 4: CARLA Scope And Adapter

CARLA is not an esmini drop-in replacement. The first M5 CARLA target is
trajectory playback in a known, curated CARLA world, not full nuScenes map
conversion, sensor reproduction, closed-loop autonomy, or arbitrary
OpenSCENARIO support.

1. Define the CARLA environment contract before writing UI controls:
   - CARLA client Python package version.
   - CARLA server/launcher command or connection URL.
   - CARLA version and compatible Python version.
   - Curated world/map identifier.
   - Vehicle blueprint mapping for supported actor types.
   - Fixed simulation timestep and synchronous/asynchronous mode.
   - Output recording format and trace conversion policy.
2. Add a `CarlaBackend` that can:
   - Connect to a configured local CARLA server or launch one through a
     configured command.
   - Load one supported curated world.
   - Spawn ego and supported vehicle actors from the canonical scenario.
   - Replay canonical positions/yaw at a fixed timestep in open-loop mode.
   - Record a normalized trace using the common report contract.
   - Stop and clean up actors/world state after completion or failure.
3. Keep the first CARLA actor mapping explicit. Unsupported actor types,
   dimensions, road topologies, sensors, or behavior must return structured
   `unsupported` issues.
4. Do not claim that a local OpenDRIVE template or nuScenes map is converted to
   a CARLA map. Record the CARLA world ID and map reconstruction mode in the
   report.
5. Add fake CARLA client tests for spawn, tick, trace, cleanup, and failure.
   Add an optional real CARLA integration test gated by environment variables.

### Slice 5: Simulator Job API

1. Extend the local job service so simulator execution is a separate job step
   from generation/validation/ranking.
2. Add request/response models equivalent to:

```text
POST /api/simulator-runs
GET  /api/simulator-runs/{job_id}
GET  /api/simulator-runs/{job_id}/logs
GET  /api/simulator-runs/{job_id}/artifacts
GET  /api/simulator-runs/{job_id}/trajectory
```

3. A run request must reference a canonical artifact or generated variant; it
   must not accept arbitrary paths from the browser.
4. Return `202` for a run accepted for local execution. Do not keep a long
   simulator process inside the HTTP request handler.
5. For the local machine, a bounded subprocess or background-thread runner is
   acceptable. Persist enough in-memory/local-file job state for the browser to
   reload a result during the current session.
6. Use separate artifact namespaces for backend outputs, for example:

```text
reports/<job-id>/simulators/esmini/...
reports/<job-id>/simulators/carla/...
```

7. Add simulator backend and run status to the React result detail view. The UI
   must show whether metrics came from recorded, esmini, or CARLA output.

### Slice 6: UI Integration

Add a simulator panel to the existing result detail view:

- Backend selector with capability status.
- Backend version and limitations.
- Mode selector, such as headless or rendered where supported.
- Timeout and fixed-timestep controls with units.
- CARLA world selector limited to supported curated worlds.
- Run/cancel/retry controls.
- Live or polled job status.
- Log/error drawer.
- Trace and artifact links.
- Recorded versus simulator trajectory overlay.
- Metrics grouped by backend.

Do not expose backend-specific controls unless the selected backend advertises
the capability. Do not show a single combined score that hides which simulator
produced it.

### Slice 7: M5 Evidence And Review

1. Add `docs/r2s-501-simulator-backend-evidence.md` for the common contract and
   capability matrix.
2. Add separate evidence for successful esmini and CARLA runs, including
   backend version, scenario ID, world/template ID, fixed timestep, actor
   mapping, trace sample count, artifacts, and metrics.
3. Document unavailable-backend behavior with no installed CARLA environment.
4. Add a clean local setup procedure that does not commit simulator binaries,
   credentials, licensed data, rendered output, or absolute paths.
5. Record exact UI steps for selecting each backend, running a scenario,
   inspecting results, and downloading artifacts.

## M5 Acceptance Gate

M5 is ready for review only when all of these are true:

- The UI discovers and reports esmini and CARLA capability status.
- The current esmini path runs through the common backend contract.
- At least one real esmini scenario run completes from the browser.
- At least one curated CARLA scenario run completes from the browser, or the
  project explicitly records a CARLA environment blocker and keeps all fake/
  optional tests green.
- Simulator failures preserve timeout, exit code, stdout/stderr, version, and
  structured issue context.
- Unsupported CARLA features fail explicitly and do not produce misleading
  replay results.
- Normalized traces and metrics have documented units, alignment, and sample
  counts.
- Recorded, esmini, and CARLA paths are visibly distinct in the UI.
- Simulator-specific artifacts are downloadable through the API.
- Existing M4 generation, validation, ranking, export, and artifact flows still
  pass without a simulator installed.
- No CARLA or esmini binary, raw dataset, secret, or machine-specific path is
  committed.

## Coordination Rules

- Work from a clean branch or a clearly named feature branch.
- Include the ticket ID in commits and pull requests, for example `R2S-401`.
- Do not modify canonical model semantics to simplify UI rendering.
- Do not add absolute paths, credentials, raw nuScenes data, replay output, or
  rendered images to git.
- Every new UI action must identify its input artifact, source scenario ID,
  configuration, seed, and output artifact paths/links.
- Keep simulator failures separate from invalid source/variant data.
- If an API contract is insufficient for UI, open a focused contract change
  with tests rather than reaching into private helpers.
- Update the wiki-ready docs when adding a CLI, changing an API contract, or
  changing an artifact field.

## Verification Before Handoff

```bash
source .venv/bin/activate
pytest -q
python -m compileall -q src tests
git diff --check
git status -sb
```

For UI work, also record:

- The exact startup command.
- The backend and frontend package/tool versions.
- The synthetic fixture or local artifact used.
- The actions exercised from load through export.
- The expected valid/invalid/simulator-failed counts.
- The API endpoints exercised and whether replay used real esmini or a fake
  executable.
- Screenshots or videos only outside git, unless explicitly curated and small.

## Known Limitations To Preserve

- The OpenDRIVE road is a local template approximation, not lossless nuScenes
  map conversion.
- Risk and TTC are signals, not safety guarantees.
- The current simulator integration depends on external esmini and `dat2csv`.
- The current CLI surface does not yet orchestrate the complete M3 pipeline.
- Licensed nuScenes data remains local-only and must not be committed.

## M4 Implementation Update (Completed)

R2S-401 is implemented and committed on `main` in `1982e00`. The local demo
consists of a FastAPI adapter in
`src/r2s_web` and a React/Vite frontend in `frontend`.

### Startup

Backend setup and startup:

```bash
python -m pip install -e ".[dev,web]"
uvicorn r2s_web.app:app --app-dir src --reload --port 8000
```

Frontend setup and startup, in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The browser runs at `http://localhost:5173` and the API at
`http://localhost:8000`. The backend defaults to project-relative `scenarios`
and `reports` roots. `R2S_ARTIFACT_ROOT`, `R2S_OUTPUT_ROOT`, `ESMINI_BIN`, and
`ESMINI_DAT2CSV` are shell configuration only.

### Implemented flow

- Strict baseline and variant artifact catalog, detail, provenance, trajectory,
  and safe download endpoints.
- Recorded trajectory output with explicit coordinate-frame and local-template
  approximation metadata.
- Deterministic grid and seeded random batch generation through public
  `real2scenario` APIs.
- Configurable feasibility limits, validation before ranking, structured invalid
  reasons, and stable per-variant result lookup.
- Distinct `valid`, `invalid`, and `simulator-failed` result statuses.
- Optional OpenSCENARIO export and esmini replay through environment-configured
  executables, with replay errors preserved in the result.
- React catalog, trajectory plot, provenance panel, batch controls, and result
  status summary.
- Frontend `LOCAL PATHS` settings for artifact directory, nuScenes dataset root,
  and dataset version, plus a source-scene list with one-click import.
- Generated result rows are selectable for trajectory inspection, validation and
  ranking detail, artifact links, simulator failure context, and valid-result
  OpenSCENARIO export. Replay can be enabled from the frontend.
- The checked-out `data/v1.0-mini` metadata is discovered automatically when no
  `NUSCENES_ROOT` override is set; imported derived artifacts are written under
  ignored `scenarios/nuscenes/`.

### Verification

- Python: `pytest -q` -> `122 passed`.
- Updated Python: `pytest -q` -> `124 passed` after generated trajectory and
  export coverage.
- Python source: `python -m compileall -q src tests` -> passed.
- Python whitespace: `git diff --check` -> passed.
- Frontend: `npm run build` -> Vite production build passed.
- Frontend: `npm test` -> 1 test passed.
- Synthetic input: `tests/fixtures/synthetic-variant-artifact.json`.
- Synthetic acceptance covers empty root, catalog/detail/trajectory/download,
  deterministic 20-variant generation with seed `7`, structured invalid
  reasons, and simulator failure when replay is requested without configured
  esmini paths.
- The three historical console commands were unavailable in the shell before
  M4 work (`command not found`); no CLI behavior was changed.

Detailed evidence is in `docs/r2s-401-local-web-demo.md`.
Curated local scene guidance is in `docs/r2s-402-403-curated-scenes.md`.

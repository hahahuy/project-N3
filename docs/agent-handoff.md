# Agent Handoff: Pre-M4 UI/UX Integration

## Checkpoint

- Repository: `https://github.com/hahahuy/project-N3.git`
- Branch: `main`
- Current documented checkpoint: `main` after the M2 replay and M3 20-variant
  evidence updates.
- M2 evidence is in `docs/r2s-206-m2-replay-evidence.md`; M3 20-variant
  evidence is in `docs/r2s-306-20-variant-batch-evidence.md`.
- M4 UI/UX and release work remain pending.
- Previous implementation checkpoints:
  - `f6df4c4` - Complete M3 batch reporting
  - `d1cd856` - Complete M3 generation and ranking
  - `61a38f1` - Complete M2 replay checkpoint
- Worktree was clean when this handoff was written.
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
add a thin orchestration CLI, Streamlit app, or service boundary, but it must
call the existing APIs and preserve their contracts.

## Pre-M4 Objective

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

## First Steps For The Next Agent

1. Read `docs/pre-m4-procedure.md` completely.
2. Read `docs/wiki-cli-api-reference.md` for reproducible commands and API
   examples.
3. Run the clean-environment checks listed in the procedure.
4. Choose the M4 UI technology. The current project documentation recommends
   Streamlit/Plotly for the first demo and postpones FastAPI/React until there
   is a concrete multi-user or deployment need.
5. Define the UI adapter boundary before adding components. Keep the adapter
   responsible for loading artifacts, invoking APIs, and mapping result objects
   to view models.
6. Add UI smoke tests using synthetic fixtures before depending on licensed
   nuScenes data or an installed esmini binary.

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
- The synthetic fixture or local artifact used.
- The actions exercised from load through export.
- The expected valid/invalid/simulator-failed counts.
- Screenshots or videos only outside git, unless explicitly curated and small.

## Known Limitations To Preserve

- The OpenDRIVE road is a local template approximation, not lossless nuScenes
  map conversion.
- Risk and TTC are signals, not safety guarantees.
- The current simulator integration depends on external esmini and `dat2csv`.
- The current CLI surface does not yet orchestrate the complete M3 pipeline.
- Licensed nuScenes data remains local-only and must not be committed.

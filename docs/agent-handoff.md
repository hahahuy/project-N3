# Handoff: Start M3 constrained generation

## Status

- Branch: `main`; the M2 implementation is present in the uncommitted worktree.
  Review, commit, and push it before beginning M3 work.
- Verification after M2: `79 passed`, `python -m compileall -q src tests` passed,
  and `git diff --check` passed.
- Python environment: `.venv` uses Python 3.11. Install with:

```bash
source .venv/bin/activate
pip install -e ".[dev,devkit]"
```

- Licensed nuScenes mini remains local-only in `data/v1.0-mini/`. Do not commit
  raw data, derived trajectories, replay files, rendered images, credentials, or
  machine-specific paths.

## Completed M1

- Canonical immutable contracts: `State`, `Actor`, `Scenario`, `VariantConfig`.
- Strict versioned JSON artifacts and required provenance in `serialization.py`.
- nuScenes metadata preflight and ingestion through `SourceWindow` and
  `extract_scenario`.
- Deterministic interaction selection using distance, TTC, and manual override;
  decisions are stored in provenance.
- Top-down source visualization through `real2scenario-visualize`.
- Real local evidence used `scene-0061`, 19.149566 seconds, ego plus three
  selected actors. See `docs/r2s-102-extraction-evidence.md` and
  `docs/r2s-104-visualization-evidence.md`.

## Completed M2

- `coordinates.py`: immutable `nuscenes_global` to `local_road_aligned`
  transform with version/origin/heading/axes provenance, inverse transform, and
  wrapped yaw handling.
- `templates.py` plus `templates/straight-two-lane-v1.xodr`: explicit versioned
  straight-road OpenDRIVE approximation. Unsupported topologies are rejected.
- `exporter.py`: deterministic OpenSCENARIO export for ego plus one to three
  actors. It stages the `.xodr` next to the `.xosc`; trajectory events use
  relative timing and a non-missed start trigger.
- `simulation.py`: external esmini plus `dat2csv` runner, fixed 0.05-second
  timestep, timeout/exit/stdout/stderr/version report, and normalized trace.
  Configure `ESMINI_BIN` and `ESMINI_DAT2CSV`; never commit their paths.
- `metrics.py`: replay position RMSE, final displacement, wrapped heading MAE,
  and speed MAE, aligned at recorded timestamps within overlap.
- `save_replay_overlay()` writes a labeled recorded-versus-replayed PNG.

## Real M2 Replay Evidence

- esmini `v3.9.0` completed a real `scene-0061` replay with exit code `0` and
  1,536 normalized states.
- Local artifacts remain in `/tmp/m2-scene-0061/`: baseline `.xosc`, staged
  `.xodr`, DAT, CSV, metrics JSON, and replay overlay PNG.
- Ego metrics: position RMSE `0.2574 m`, final displacement `0.1030 m`, heading
  MAE `0.0257 rad`, and speed MAE `0.1021 m/s` over 39 samples.
- Full metrics, reproducibility information, and approximation limitation are in
  `docs/m2-replay-evidence.md`.

## M3 Order

1. **R2S-301: parameterized perturbations**.
   - Add immutable transformations for speed multiplier, initial longitudinal
     gap, and timing offset.
   - Store parent scenario ID, complete config, seed, and generator version.
   - Test immutability, determinism, and expected trajectory changes.
2. **R2S-302: batch generator**.
   - Add deterministic grid/random generation with stable variant IDs and a
     manifest. Fixed configuration and seed must reproduce output order and IDs.
3. **R2S-303: feasibility validation**.
   - Add versioned configurable limits for acceleration, deceleration, jerk,
     yaw rate, and supported road boundaries.
   - Return all structured rejection reasons; do not silently clamp a variant.
4. **R2S-304: risk features and ranking**.
   - Implement documented minimum distance, TTC, novelty, and score breakdown.
   - Invalid variants cannot be ranked as valid; risk is not a safety guarantee.
5. **R2S-305: batch report exporter**.
   - Export per-variant reports and aggregate CSV/JSON. Enforce:
     `generated = valid + invalid + simulator-failed`.

## Required Workflow

After each ticket, add success and failure-path tests, run `pytest`, compile
with `python -m compileall -q src tests`, and run `git diff --check`. Before a
checkpoint commit, inspect status/diff/log; stage only intended source, tests,
and docs; never stage `data/`, `/tmp` artifacts, or generated simulator output.

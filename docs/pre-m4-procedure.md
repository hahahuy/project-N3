# Pre-M4 Procedure

This procedure is the review gate before building the M4 UI/UX. It is intended
for a new agent or teammate who needs to prove that the M3 contracts work before
connecting screens and controls.

## 1. Environment

Use Python 3.11 or newer. The existing environment was created with Python
3.11 and the optional devkit dependencies are required for nuScenes rendering.

```bash
python --version
source .venv/bin/activate
python -m pip install -e ".[dev,devkit]"
```

Do not install or configure esmini paths in source files. If replay is needed,
configure them in the shell only:

```bash
export ESMINI_BIN="/absolute/path/to/esmini"
export ESMINI_DAT2CSV="/absolute/path/to/dat2csv"
```

Do not copy those paths into docs, committed config, screenshots, or reports.

## 2. Baseline Verification

Run the complete test and source checks before changing UI code:

```bash
pytest -q
python -m compileall -q src tests
git diff --check
```

Expected current result: `118 passed`, with no compile or diff-check output.

If this fails, stop UI work and report the first failure with the commit,
Python version, command, and traceback.

## 3. Verify The Existing CLI Surface

The installed CLI commands are data inspection and visualization tools:

```bash
real2scenario-preflight --help
real2scenario-devkit --help
real2scenario-visualize --help
```

### Dataset preflight

With a complete licensed local dataset:

```bash
export NUSCENES_ROOT="$HOME/datasets/nuscenes"
export NUSCENES_VERSION="v1.0-mini"

real2scenario-preflight \
  --root "$NUSCENES_ROOT" \
  --version "$NUSCENES_VERSION" \
  --map-mode expansion
```

Use metadata-only mode only when maps are intentionally unavailable:

```bash
real2scenario-preflight \
  --root "$NUSCENES_ROOT" \
  --version "$NUSCENES_VERSION" \
  --map-mode none
```

Exit code `0` means ready. Exit code `1` means the report contains one or more
actionable missing or malformed input issues. `map-mode none` is not sufficient
for road-aware extraction.

### nuScenes inventory and rendering

These commands require a complete licensed release and `.[devkit]`:

```bash
real2scenario-devkit \
  --root "$NUSCENES_ROOT" \
  --version "$NUSCENES_VERSION" \
  inventory \
  --output /tmp/nuscenes-inventory.json

real2scenario-devkit \
  --root "$NUSCENES_ROOT" \
  --version "$NUSCENES_VERSION" \
  render \
  --scene-index 0 \
  --output /tmp/nuscenes-scene-0.png
```

Do not commit `/tmp` outputs or raw/derived dataset artifacts.

### Top-down artifact visualization

The visualizer accepts a validated baseline or variant JSON artifact:

```bash
real2scenario-visualize /tmp/scenario.json --output /tmp/top-down.png
real2scenario-visualize /tmp/scenario.json --show
```

The UI should reuse the same artifact loading and plotting semantics rather
than implement a second trajectory parser.

## 4. Synthetic M3 Smoke Test

Use a small in-memory scenario or a sanitized JSON fixture. The minimum smoke
test should exercise this order:

```python
from real2scenario import (
    FeasibilityLimits,
    VariantConfig,
    aggregate_report,
    generate_grid_variants,
    rank_scenario,
    validate_feasibility,
)

variants, manifest = generate_grid_variants(
    baseline,
    speed_multipliers=(1.0, 1.1),
    initial_gap_deltas_m=(0.0, -2.0),
    timing_offsets_s=(0.0, 0.25),
    seed=7,
)

for variant in variants:
    validation = validate_feasibility(variant, FeasibilityLimits())
    ranking = rank_scenario(variant, validation, parent_scenario=baseline)
    # Build VariantReport only after choosing valid/invalid/simulator-failed.
```

The batch must be deterministic:

- Same baseline, grid values, generator version, and seed produce the same
  variant order and IDs.
- Parent scenario remains unchanged.
- Invalid variants retain structured rejection reasons.
- Invalid variants have no valid ranking score.

For an M4 demo, use at least 20 variants from a fixed baseline. A 2 x 2 x 5
grid is a simple deterministic starting point.

## 5. Replay-Optional Smoke Test

Simulator integration is optional for unit and UI development. When esmini and
`dat2csv` are available:

1. Select a scenario in `local_road_aligned` coordinates.
2. Call `select_opendrive_template()` with the supported `straight_road`
   topology.
3. Call `write_openscenario()` to a temporary output directory.
4. Call `run_esmini()` with `EsminiConfig` configured from environment paths.
5. If `ReplayReport.completed` is true and `trace` is present, call
   `compute_scenario_replay_metrics()`.
6. If the runner fails, create a `simulator-failed` report containing exit code,
   timeout state, stderr, tool version, and trace path.

Never classify a simulator failure as a kinematic invalid result.

## 6. UI Acceptance Gate

Before declaring M4 UI work ready for review, demonstrate these states using a
synthetic fixture:

1. Baseline loaded with scenario ID, coordinate frame, duration, actors, and
   provenance visible.
2. Recorded path displayed with a distinct style.
3. Variant controls show units and allowed ranges for speed, gap, and timing.
4. Batch generation shows deterministic count and manifest seed.
5. Validation results appear before ranking results.
6. Invalid variants show every structured reason.
7. Valid variants show minimum distance, TTC, novelty, and score components.
8. Simulator-failed variants show tool/error context separately.
9. Export links point to canonical JSON, `.xosc`, replay trace, and report paths.
10. Reloading the same artifact reproduces the same displayed IDs and metadata.

## 7. Handoff Evidence

The next agent must leave a short note containing:

- Commit SHA and branch.
- UI startup command.
- Python and dependency setup command.
- Fixture or artifact input path, without machine-specific absolute paths.
- Screens/actions tested.
- Test command and result.
- Known failures or simulator availability.
- Any contract change proposed for the next agent.

If the UI requires a new CLI command, add it to `pyproject.toml`, test its
exit codes, document it in `docs/wiki-cli-api-reference.md`, and update the
agent handoff before handing off.

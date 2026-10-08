# Wiki-Ready CLI and API Reference

This page is intended to become the first GitHub Wiki reference for future
agents and teammates. It states what can be run from the shell today and what
must be called through the Python API.

## Command Inventory

| Command | Purpose | Requires | Output |
| --- | --- | --- | --- |
| `real2scenario-preflight` | Check nuScenes metadata and optional map expansion | Local dataset files | Human-readable readiness report and exit code |
| `real2scenario-devkit` | Inventory a complete nuScenes release or render one sample | `.[dev,devkit]`, licensed dataset | JSON inventory or PNG render |
| `real2scenario-visualize` | Plot or interactively view a validated scenario artifact | `.[dev,devkit]` for plotting | PNG or interactive viewer |

M3 generation, validation, ranking, reporting, and OpenSCENARIO replay do not
have console commands yet. Use the public APIs below. If M4 adds commands,
update this table and add CLI tests before using them in team documentation.

## CLI: Preflight

```bash
real2scenario-preflight \
  --root "$NUSCENES_ROOT" \
  --version "v1.0-mini" \
  --map-mode expansion
```

The command checks required tables under `<root>/<version>` and, in expansion
mode, checks `map.json` and referenced map files under `<root>/maps`.

Use `--map-mode none` only for metadata-only checks. The output includes:

- Dataset root.
- Metadata path.
- Selected map mode.
- `READY` or `NOT READY`.
- Every issue code, path, and remediation message.

Exit codes:

- `0`: all requested checks pass.
- `1`: one or more checks fail.
- Argument parsing errors: non-zero, from `argparse`.

## CLI: Devkit

Inventory:

```bash
real2scenario-devkit \
  --root "$NUSCENES_ROOT" \
  --version "v1.0-mini" \
  inventory \
  --output /tmp/nuscenes-inventory.json
```

Inventory includes table counts and scene metadata such as scene token, name,
sample count, first/last sample token, and log token.

Render a first sample:

```bash
real2scenario-devkit \
  --root "$NUSCENES_ROOT" \
  --version "v1.0-mini" \
  render \
  --scene-index 0 \
  --output /tmp/nuscenes-scene-0.png
```

Render a selected sample instead:

```bash
real2scenario-devkit \
  --root "$NUSCENES_ROOT" \
  --version "v1.0-mini" \
  render \
  --sample-token "$SAMPLE_TOKEN" \
  --output /tmp/sample.png
```

The devkit command requires complete local nuScenes metadata and raw sensor
files. It must not be used as a substitute for trajectory extraction.

## CLI: Visualization

Static output:

```bash
real2scenario-visualize /tmp/scenario.json --output /tmp/top-down.png
```

Interactive viewer:

```bash
real2scenario-visualize /tmp/scenario.json --show
```

Both commands consume a serialized baseline or variant artifact. The artifact
must pass strict serialization validation. It is not a raw nuScenes JSON file.

## API: Artifact Loading

```python
from pathlib import Path
from real2scenario import artifact_from_json

scenario, parent_id, config = artifact_from_json(
    Path("scenario.json").read_text(encoding="utf-8")
)
```

Interpretation:

- Baseline artifact: `parent_id is None`, `config is None`.
- Variant artifact: both `parent_id` and `config` are populated.
- Invalid schema, unknown fields, missing provenance, or malformed trajectories
  raise `ValueError`.

## API: Source Extraction And Selection

```python
from real2scenario import SourceWindow, extract_scenario

scenario = extract_scenario(
    dataset_root,
    SourceWindow(scene_token, start_sample_token, end_sample_token),
    actor_instance_tokens,
    version="v1.0-mini",
)
```

This returns `nuscenes_global` coordinates. For deterministic interaction
selection:

```python
from real2scenario import SelectionConfig, select_interaction_actors

selected = select_interaction_actors(
    scenario,
    SelectionConfig(max_distance_m=30.0, max_ttc_s=5.0, max_actors=3),
)
```

Selection decisions and selected actor IDs are stored in provenance.

## API: Coordinate And OpenDRIVE Preparation

```python
from real2scenario import (
    STRAIGHT_ROAD_TOPOLOGY,
    RoadAlignedTransform,
    select_opendrive_template,
    transform_to_local_road_aligned,
)

local_scenario = transform_to_local_road_aligned(
    scenario,
    RoadAlignedTransform(origin_x_m=0.0, origin_y_m=0.0, heading_rad=0.0),
)
selected, template = select_opendrive_template(
    local_scenario,
    topology=STRAIGHT_ROAD_TOPOLOGY,
)
```

The selected scenario must be in `local_road_aligned` coordinates. Unsupported
topologies fail explicitly. The template is a local approximation and must be
shown as such in UI copy.

## API: OpenSCENARIO And Replay

```python
from real2scenario import EsminiConfig, run_esmini, write_openscenario

xosc_path = write_openscenario(selected, template, output_dir / "scenario.xosc")
replay = run_esmini(
    xosc_path,
    output_dir / "replay.csv",
    EsminiConfig(),
)
```

`EsminiConfig` reads `ESMINI_BIN` and `ESMINI_DAT2CSV` when explicit values are
not supplied. `ReplayReport` preserves command, completion, timeout, exit code,
stdout, stderr, tool version, trace path, and optional normalized trace.

When replay succeeds:

```python
from real2scenario import compute_scenario_replay_metrics

metrics_by_actor = compute_scenario_replay_metrics(selected, replay.trace)
```

When replay fails, preserve the report as `simulator-failed`; do not pass it to
kinematic invalidation logic.

## API: Generation

Single variant:

```python
from real2scenario import VariantConfig, perturb_scenario

variant = perturb_scenario(
    selected,
    VariantConfig(
        speed_multiplier=1.1,
        initial_gap_delta_m=-2.0,
        timing_offset_s=0.25,
        seed=7,
    ),
)
```

Batch grid:

```python
from real2scenario import generate_grid_variants

variants, manifest = generate_grid_variants(
    selected,
    speed_multipliers=(0.9, 1.0, 1.1, 1.2),
    initial_gap_deltas_m=(-2.0, 0.0),
    timing_offsets_s=(0.0, 0.25, 0.5),
    seed=7,
)
```

Batch random:

```python
from real2scenario import generate_random_variants

variants, manifest = generate_random_variants(
    selected,
    count=20,
    speed_multiplier_range=(0.8, 1.2),
    initial_gap_delta_range_m=(-5.0, 2.0),
    timing_offset_range_s=(0.0, 0.5),
    seed=7,
)
```

Same input scenario, ranges, generator version, and seed must reproduce the
same ordered IDs, configurations, and trajectories.

## API: Validation, Ranking, Reporting

```python
from real2scenario import (
    FeasibilityLimits,
    VariantReport,
    aggregate_report,
    rank_scenario,
    validate_feasibility,
    write_aggregate_csv,
    write_aggregate_json,
    write_variant_report,
)

reports = []
for variant, config in zip(variants, manifest.configurations):
    validation = validate_feasibility(variant, FeasibilityLimits())
    ranking = rank_scenario(variant, validation, parent_scenario=selected)
    status = "valid" if validation.valid else "invalid"
    reports.append(
        VariantReport(
            variant_id=variant.scenario_id,
            status=status,
            scenario_artifact=f"generated/{variant.scenario_id}/scenario.json",
            xosc_artifact=None,
            replay_trace_artifact=None,
            report_artifact=f"generated/{variant.scenario_id}/report.json",
            validation=validation,
            ranking=ranking,
        )
    )

aggregate = aggregate_report(selected.scenario_id, tuple(reports))
write_aggregate_json(aggregate, output_dir / "aggregate.json")
write_aggregate_csv(aggregate, output_dir / "aggregate.csv")
for report in reports:
    write_variant_report(report, output_dir / report.report_artifact)
```

The production orchestration must add `.xosc`, replay trace, and
`simulator-failed` handling where external execution is enabled. The report
contract requires:

```text
generated = valid + invalid + simulator_failed
```

Display validity before score. A high risk or novelty score never overrides a
failed feasibility report.

## API Contract Rules For M4

- Use public exports from `real2scenario`; do not import private helpers.
- Keep SI units and coordinate-frame labels visible in controls and views.
- Preserve scenario ID, parent ID, seed, generator/validation/ranking versions,
  and provenance in every UI-created output.
- Keep recorded, replayed, and generated paths visually distinct.
- Keep invalid and simulator-failed states distinct.
- Treat risk/TTC as review signals, never as safety claims.
- Add tests for every new orchestration path and failure state.

# Scenario Processing

Code: `src/real2scenario/`

This is the simulator-independent domain layer. It defines canonical scenarios,
converts source records into them, creates controlled variants, validates
feasibility, runs replay normalization and calculates metrics.

## Source Map

| Module | Responsibility |
|---|---|
| `models.py` | `State`, `Actor`, `Scenario` and `VariantConfig` invariants |
| `serialization.py` | Versioned artifact JSON and provenance validation |
| `ingestion.py` | nuScenes metadata to global-frame canonical scenarios |
| `coordinates.py` | Coordinate transforms and frame provenance |
| `generation.py` | Deterministic grid/random variants and preview edits |
| `validation.py` | Kinematic and optional road-boundary feasibility |
| `gates.py` | G1-G7 diagnostic gate evaluation |
| `ranking.py` | Risk/novelty/replay-quality ranking |
| `exporter.py` | OpenSCENARIO output using a selected OpenDRIVE template |
| `simulation.py` | esmini subprocess invocation and trace parsing |
| `metrics.py` | Replay alignment and ADE/FDE/trajectory metrics |
| `metadata_index.py` | Cached scene-scoped nuScenes metadata access |

## Canonical Invariants

- `State` values are finite and time is non-negative.
- Actor timestamps are strictly increasing.
- Scenario actor IDs are unique and include the declared ego actor.
- Scenario duration covers every actor trajectory.
- Variant generation does not mutate the parent scenario.
- Serialization validates schema version, required fields and provenance.
- Validation reports violations without silently clamping values.
- Replay metrics require a normalized replay trace; missing traces are not zero.

## Processing Pipeline

```text
source metadata
  -> ingestion
  -> Scenario
  -> coordinate transform
  -> baseline artifact
  -> generation / preview
  -> validation
  -> gates and ranking
  -> export / replay / metrics / report
```

The domain layer must not import FastAPI, React or request-specific state.
External adapter assumptions belong at adapter boundaries and must be reflected
in provenance or explicit fallback status.

## Tests

Domain tests live under `tests/` and are grouped by module, including models,
serialization, ingestion, generation, validation, gates, simulation, metrics,
metadata indexing and map building.

Run the full suite with:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

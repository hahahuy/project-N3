# Real2Scenario

Real2Scenario transforms recorded nuScenes vehicle interactions into replayable OpenSCENARIO files, measures replay fidelity, and generates constrained rare-case variants.

The first MVP uses esmini for headless OpenSCENARIO execution. It deliberately supports local road-aligned reconstruction rather than claiming a lossless nuScenes-map to OpenDRIVE conversion.

## Current Scope

- Canonical, simulator-independent scenario schema.
- nuScenes trajectory extraction once the required metadata is available locally.
- Baseline OpenSCENARIO export and esmini replay.
- Controlled speed, gap, and timing perturbations.
- Validation, trajectory metrics, and a reviewable scenario report.

## Documentation

- [Product specification](docs/product-spec.md)
- [Architecture](docs/architecture.md)
- [MVP roadmap and tickets](docs/mvp-roadmap.md)
- [Review checklist](docs/review-checklist.md)
- [Technology and usage guide](docs/technology-guide.md)
- [nuScenes and simulation guide](docs/nuscenes-and-simulation-guide.md)
- [Original project brief](docs/description.md)

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The initial scaffold has no simulator or dataset dependency. See the Phase 0 tickets before adding nuScenes metadata or esmini.

## Data License

The included nuScenes-derived data is subject to the terms in [data/LICENSE](data/LICENSE), including non-commercial and attribution requirements. Do not add, redistribute, or use dataset material outside those terms.

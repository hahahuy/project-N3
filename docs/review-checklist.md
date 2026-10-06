# Code Review Checklist

Use this checklist together with the milestone checkpoint in `mvp-roadmap.md`. A reviewer should request changes when an unchecked applicable item lacks an explicit reason.

## General

- [ ] The ticket ID is included in the pull request title or description.
- [ ] The change is scoped to the ticket and avoids unrelated refactors.
- [ ] Public functions have type hints and clear docstrings where behavior is non-obvious.
- [ ] New behavior has automated tests or a documented reason why it cannot be automated.
- [ ] Error messages identify the failing scenario/config/artifact without exposing secrets.
- [ ] No machine-specific absolute paths, credentials, or large generated outputs are committed.
- [ ] Dataset license requirements remain visible and respected.

## Data And Schema

- [ ] Units are SI and named in fields/docs.
- [ ] Coordinate frame and origin are explicit.
- [ ] Time ordering is validated before interpolation or metric calculation.
- [ ] Actor IDs and scenario IDs are stable and unique.
- [ ] Source tokens, source window, dataset version, and extraction version are retained.
- [ ] Missing/invalid data produces a structured failure, not a silent fallback.

## Geometry And Metrics

- [ ] Heading comparison wraps angles correctly at `-pi`/`pi`.
- [ ] Time alignment policy is explicit and tested.
- [ ] Metrics report units, sample count, and handling of missing states.
- [ ] Threshold values are config, documented, and boundary-tested.
- [ ] Coordinate transforms have round-trip or known-point tests.

## OpenSCENARIO And Simulation

- [ ] Generated XML is tested structurally and has a stable golden fixture where useful.
- [ ] All simulator executable/map paths are configured externally.
- [ ] Subprocess timeout, return code, stdout, and stderr are recorded.
- [ ] Simulator failures remain distinguishable from invalid source/variant data.
- [ ] Map/template selection is explained in artifact metadata.
- [ ] Local reconstruction is not represented as lossless map conversion.

## Variant Generation And Validation

- [ ] A generated scenario does not mutate its baseline.
- [ ] Parent scenario ID, seed, parameter configuration, and generator version are stored.
- [ ] Same input config/seed reproduces IDs and output ordering.
- [ ] Feasibility checks report every failure reason.
- [ ] Invalid scenarios cannot be surfaced as valid ranked output.
- [ ] Risk metrics are not presented as safety guarantees.

## UI And Demo

- [ ] Recorded, replayed, and generated trajectories use distinct labels/styles.
- [ ] Controls expose units and permitted ranges.
- [ ] Results display validity status before score.
- [ ] Exported files can be linked back to source/provenance metadata.
- [ ] The intended demo flow works from a clean start using documented commands.

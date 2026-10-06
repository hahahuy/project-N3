# MVP Roadmap And Tickets

This document is the execution ledger. Every ticket should have one owner, a pull request, automated test evidence where applicable, and review evidence listed under its checkpoint. A ticket is not complete merely because code exists.

## Milestone Summary

| Milestone | Outcome | Review gate |
| --- | --- | --- |
| M0 | Reproducible repository and canonical contract | Contract review |
| M1 | Recorded segment can be inspected and extracted | Data review |
| M2 | Baseline OpenSCENARIO replays in esmini | Replay review |
| M3 | Constrained variants are generated and validated | Generation review |
| M4 | Demo UI and release evidence are complete | Demo review |

## M0: Foundation And Contract

### R2S-001: Repository bootstrap

- Deliverable: `pyproject.toml`, package layout, test layout, `.gitignore`, README.
- Acceptance criteria: `pip install -e ".[dev]"` and `pytest` run on a clean environment.
- Evidence: CI/local command output and clean `git status` after tests.
- Dependencies: none.

### R2S-002: Canonical scenario schema

- Deliverable: `State`, `Actor`, `Scenario`, provenance, and variant configuration models.
- Acceptance criteria: SI units documented; actor IDs unique; ego exists; timestamps strictly increase; invalid input raises a useful exception.
- Evidence: unit tests for valid scenario and each major invariant failure.
- Dependencies: R2S-001.

### R2S-003: Artifact and provenance convention

- Deliverable: scenario/variant ID format and JSON manifest contract.
- Acceptance criteria: every generated artifact has source dataset/version, source scene/window, map mode/version, generator version, and seed/config.
- Evidence: example JSON artifact checked into `tests/fixtures/` without restricted dataset content.
- Dependencies: R2S-002.

### Checkpoint M0: Contract Review

- [ ] Package installs using documented commands.
- [ ] No dataset path, local binary path, or secret is hard-coded.
- [ ] Canonical schema has unit tests for all invariants.
- [ ] Units and coordinate-frame fields are explicit.
- [ ] Reviewer can identify every artifact’s source and config from its manifest.
- [ ] Scope excludes simulator/UI dependencies from `models.py`.

## M1: Ingestion And Scenario Mining

### R2S-100: nuScenes onboarding and data inventory

- Deliverable: completed data inventory plus a short team walkthrough/notebook covering scene, sample, sample data, annotation, ego pose, calibration, and map records.
- Acceptance criteria: every team member can explain which files provide trajectories, which provide raw sensors/panoptic labels, and why the repository's current panoptic-only subset cannot reconstruct a scenario alone.
- Evidence: a checked-in onboarding note following `docs/nuscenes-and-simulation-guide.md`, a screenshot of one official-devkit rendering, and the selected source segment ID.
- Dependencies: R2S-001.

### R2S-101: nuScenes dataset preflight

- Deliverable: command that verifies required metadata files and gives actionable missing-file errors.
- Acceptance criteria: checks scene, sample, sample_data, sample_annotation, ego_pose, calibrated_sensor, and map availability needed by the selected mode.
- Evidence: tests using temporary directory fixtures for complete and incomplete metadata layouts.
- Dependencies: R2S-001.

### R2S-102: Ego and actor trajectory extraction

- Deliverable: adapter converting one configurable source window to canonical `Scenario`.
- Acceptance criteria: returns ego plus tracked actors with time, position, yaw, speed, dimensions, and source tokens.
- Evidence: one synthetic fixture test and one documented real-data smoke run.
- Dependencies: R2S-002, R2S-101.

### R2S-103: Interaction window and actor selection

- Deliverable: configurable selector using distance/TTC and manual override.
- Acceptance criteria: selected actors and rejection reasons are written into provenance; supports 1-3 non-ego actors.
- Evidence: tests for selection threshold, deterministic tie-break, and manual selection.
- Dependencies: R2S-102.

### R2S-104: Top-down source visualizer

- Deliverable: CLI plot or notebook that plays extracted trajectories in a local frame.
- Acceptance criteria: a reviewer can scrub/play a 8-20 second segment and distinguish ego from each actor.
- Evidence: screenshot/video and command in documentation.
- Dependencies: R2S-102.

### Checkpoint M1: Data Review

- [ ] Required trajectory data is available; panoptic masks alone are not treated as tracks.
- [ ] Team data inventory identifies which raw sensor and metadata files are locally available.
- [ ] One documented source segment has ego and at least one interacting actor.
- [ ] State timestamps are monotonic and in seconds.
- [ ] Coordinate frame and origin are displayed/documented.
- [ ] Selection rationale is retained in the scenario artifact.
- [ ] A reviewer can reproduce the extraction with one command/config.

## M2: Baseline Reconstruction And Replay

### R2S-201: Local coordinate transform

- Deliverable: source-to-local road-aligned transform and transform metadata.
- Acceptance criteria: round-trip error on test points is below configured numerical tolerance; transform uses documented axes/units.
- Evidence: unit tests including yaw wrapping and a visual overlay.
- Dependencies: R2S-102.

### R2S-202: OpenDRIVE template registry

- Deliverable: versioned supported `.xodr` templates and selector contract.
- Acceptance criteria: a source scenario records why a template was selected; unsupported topology is rejected rather than silently mapped.
- Evidence: registry unit test and one reviewable template diagram.
- Dependencies: R2S-201.

### R2S-203: OpenSCENARIO baseline exporter

- Deliverable: canonical scenario to `.xosc` exporter for ego plus 1-3 actors.
- Acceptance criteria: XML validates structurally; entity names are stable; all trajectory timing is explicit; output contains no user-machine paths.
- Evidence: XML parsing test and a golden-file diff test.
- Dependencies: R2S-002, R2S-202.

### R2S-204: esmini runner and trace parser

- Deliverable: configured subprocess runner and normalized replay trace.
- Acceptance criteria: timeout/error output is captured; exit status and esmini version are saved in report; runner is mockable in unit tests.
- Evidence: unit tests with a fake executable and an optional marked integration test.
- Dependencies: R2S-203.

### R2S-205: Replay fidelity metrics

- Deliverable: timestamp alignment, position RMSE, final displacement error, heading MAE, and speed MAE.
- Acceptance criteria: metric inputs/outputs have units; empty or mismatched traces fail clearly; known numeric examples pass.
- Evidence: unit tests with hand-calculated expected metrics.
- Dependencies: R2S-204.

### Checkpoint M2: Replay Review

- [ ] At least one baseline `.xosc` starts and completes in esmini.
- [ ] Original and replay trajectories are overlaid in one artifact.
- [ ] Metrics state units, timestamp alignment method, and sample count.
- [ ] Map reconstruction is labelled as local/template approximation.
- [ ] Failed simulator executions retain stderr/exit status in their report.
- [ ] Reviewer can regenerate baseline XML and replay trace from source config.

## M3: Variant Generation, Validation, And Ranking

### R2S-301: Parameterized perturbations

- Deliverable: speed multiplier, initial longitudinal gap, and timing offset transformations.
- Acceptance criteria: transformations never mutate their parent scenario; every child records complete parameter values and seed.
- Evidence: tests for immutability, deterministic output, and expected trajectory offsets.
- Dependencies: R2S-002, R2S-203.

### R2S-302: Batch generator

- Deliverable: grid/random batch command with a manifest and stable variant IDs.
- Acceptance criteria: a fixed config/seed produces the same IDs and configurations in the same order.
- Evidence: deterministic batch test and sample manifest.
- Dependencies: R2S-301.

### R2S-303: Feasibility validation

- Deliverable: kinematic and supported-road boundary checks with structured rejection reasons.
- Acceptance criteria: acceleration, deceleration, jerk, yaw-rate, and road boundary thresholds are configuration-driven.
- Evidence: boundary-value tests that pass at threshold and fail beyond it.
- Dependencies: R2S-201, R2S-301.

### R2S-304: Risk features and ranking

- Deliverable: minimum distance, TTC, novelty features, and versioned score breakdown.
- Acceptance criteria: a failed validity check cannot be ranked as valid; no collision/near-miss label is inferred without stated definition.
- Evidence: tests for TTC edge cases and score breakdown snapshot.
- Dependencies: R2S-303, R2S-205.

### R2S-305: Batch report exporter

- Deliverable: per-variant report and aggregate CSV/JSON summary.
- Acceptance criteria: counts reconcile exactly: generated = valid + invalid + simulator-failed; each result links all artifacts.
- Evidence: reconciliation test and sample batch report.
- Dependencies: R2S-302, R2S-303, R2S-304.

### Checkpoint M3: Generation Review

- [ ] A batch of at least 20 variants is generated from a fixed baseline.
- [ ] Seed/config reruns reproduce IDs and trajectories.
- [ ] Reports separate invalid, simulator-failed, and valid cases.
- [ ] Every rejection has one or more structured reasons.
- [ ] Kinematic/map thresholds are versioned configuration, not magic numbers.
- [ ] Score components are visible; “rare” and “safe” are not conflated.

## M4: Demo And Release

### R2S-401: MVP dashboard

- Deliverable: browser, trajectory playback, controls, results table, and export action.
- Acceptance criteria: the required demo flow in `product-spec.md` runs without direct file edits or terminal intervention after startup.
- Evidence: recorded 3-minute demo and UI smoke-test checklist.
- Dependencies: R2S-104, R2S-205, R2S-305.

### R2S-402: Demo scenario curation

- Deliverable: three labeled source segments: lead braking plus two additional supported interactions.
- Acceptance criteria: each has baseline replay, a 20-variant batch, and a known presentation-worthy valid variant.
- Evidence: curation index with artifact paths and metrics.
- Dependencies: R2S-305.

### R2S-403: Release and reproducibility pack

- Deliverable: setup guide, configuration examples, known limitations, demo script, and evidence bundle.
- Acceptance criteria: a new reviewer can set up the project and reproduce one curated batch from instructions.
- Evidence: clean-machine verification notes.
- Dependencies: R2S-401, R2S-402.

### Checkpoint M4: Demo Review

- [ ] The walkthrough selects, replays, varies, validates, ranks, and exports a scenario.
- [ ] The dashboard clearly distinguishes recorded, replayed, and generated paths.
- [ ] At least three curated source scenarios have complete evidence.
- [ ] Aggregate counts reconcile with per-variant reports.
- [ ] Limitations and licensing are visible in documentation/demo material.
- [ ] A reviewer can follow the script without undocumented manual steps.

## Suggested Review Cadence

- Review M0 before downloading or integrating a full dataset.
- Review M1 before committing to a simulator map representation.
- Review M2 before building a UI or batch generator.
- Review M3 before describing the project as rare-scenario generation.
- Review M4 with a clean checkout and the exact demo script.

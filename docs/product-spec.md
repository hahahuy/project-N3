# Product Specification: Real2Scenario

## 1. Problem

Recorded autonomous-driving datasets contain real interactions, but they are difficult to replay, edit, and use systematically for safety testing. Teams need a reproducible path from a recorded trajectory segment to a simulation-ready scenario and controlled variations of that scenario.

## 2. Product Statement

Real2Scenario is a scenario-mining workbench that converts a selected nuScenes interaction into an OpenSCENARIO replay, quantifies how faithfully it replays, then produces valid rare-case variations by changing a limited set of physical parameters.

The product is a testing and research tool. It does not make safety claims about a vehicle and does not replace closed-loop evaluation of an autonomy stack.

## 3. Primary User And Job

| User | Job to be done |
| --- | --- |
| AV researcher | Turn a recorded interaction into a reproducible simulation test case. |
| Safety/test engineer | Increase coverage around an observed edge case without hand-authoring every scenario. |
| Reviewer/demo audience | Understand provenance, replay quality, and why a generated case is considered valid and interesting. |

## 4. MVP Outcome

For at least three selected recorded segments, a user can:

1. Inspect ego and relevant actor trajectories in a top-down viewer.
2. Export a baseline OpenSCENARIO file and run it in esmini.
3. See recorded-versus-replayed trajectories and fidelity metrics.
4. Generate at least 20 deterministic variations by modifying speed, gap, or timing.
5. Review validation results and download a `.xosc` file plus its metadata report.

## 5. Demo Experience

The MVP UI has four working areas:

| Area | What it shows | Required interaction |
| --- | --- | --- |
| Scenario browser | Available source segments and event labels | Choose one segment. |
| Top-down playback | Ego, relevant actors, timeline, original/replay paths | Play, scrub, choose actor. |
| Variant controls | Speed multiplier, initial gap, timing offset, generation count | Generate deterministic variants. |
| Results panel | Validity, RMSE, speed error, minimum TTC/distance, export | Filter and inspect one result. |

The canonical demo is a lead-vehicle braking interaction. A cut-in is the preferred second event type. Pedestrian crossing and intersections are explicitly post-MVP because map alignment and validation are harder.

## 6. Functional Requirements

| ID | Requirement | MVP acceptance condition |
| --- | --- | --- |
| FR-01 | Load a source segment into a canonical scenario model. | Segment includes ego, 1-3 selected actors, time states, dimensions, and provenance. |
| FR-02 | Detect/select relevant actors. | Selection rationale is stored: distance, TTC, lane relation, or configured manual choice. |
| FR-03 | Export a baseline `.xosc`. | Generated XML parses and esmini starts it successfully. |
| FR-04 | Replay and compare trajectories. | Report includes position RMSE, final displacement, heading MAE, and speed MAE. |
| FR-05 | Generate constrained variants. | Each variant preserves parent ID, parameter config, generator version, and random seed. |
| FR-06 | Validate generated scenarios. | Report separates kinematic, map/road, and simulator validity checks. |
| FR-07 | Rank useful scenarios. | Results include a transparent risk/novelty score and the raw components. |
| FR-08 | Export review artifacts. | `.xosc`, canonical scenario JSON, replay trace, and JSON report are available per result. |

## 7. Explicit Non-Goals For MVP

- A lossless converter from nuScenes maps to OpenDRIVE.
- Full CARLA integration, camera rendering, or sensor synthesis.
- Closed-loop planning/control evaluation.
- A generative AI model for scenario creation.
- Support for every OpenSCENARIO feature or all traffic events.
- A claim that generated scenarios represent real-world likelihood.

## 8. Metrics

| Metric | Definition | Use |
| --- | --- | --- |
| Position RMSE | Root mean squared planar distance between aligned recorded/replayed states. | Primary replay fidelity. |
| Final displacement error | Planar distance at the final aligned timestamp. | Detect accumulated drift. |
| Heading MAE | Mean absolute wrapped yaw error. | Detect orientation mismatch. |
| Speed MAE | Mean absolute speed difference. | Detect dynamics mismatch. |
| Generation validity rate | Valid variants divided by generated variants. | Measure usable output. |
| Simulator completion rate | Runs completed without simulator error divided by attempted runs. | Integration reliability. |
| Minimum TTC/distance | Minimum pairwise values over a replay. | Risk signal, not safety proof. |
| Diversity | Unique valid parameter configurations or trajectory clusters. | Detect duplicate output. |

Thresholds are configuration, not universal truth. The team must record the threshold version used for every evaluation.

## 9. Data And Licensing Constraints

The committed panoptic mini files are insufficient for trajectory extraction. The pipeline additionally needs nuScenes metadata such as `scene.json`, `sample.json`, `sample_data.json`, `sample_annotation.json`, `ego_pose.json`, and calibration metadata. Map metadata is required for lane-aware extraction.

nuScenes material in this repository is subject to `data/LICENSE`. The team must preserve attribution and non-commercial/share-alike conditions, avoid committing credentials, and avoid publishing data or derived artifacts contrary to those terms.

## 10. Definition Of Done

The MVP is complete only when the following evidence is committed or attached to a release:

- Three source scenario IDs with provenance and source-window configuration.
- One successful baseline replay report for each source scenario.
- One generated batch of at least 20 variants per source scenario.
- Validation summary showing valid, invalid, and simulator-failed counts.
- A scripted 3-minute demo that runs without manual XML edits.
- Passing automated tests for schema, coordinate conversion, metric calculation, and deterministic variant configuration.

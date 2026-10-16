# CP1 Scene-0061 Alignment and Selection Analysis

## Scope

Compare the private `scene-0061` road-match baseline across actor scope,
coordinate frame and tolerance sensitivity before changing any production
threshold or matching algorithm.

## Matrix Results

| Row | Scope | Frame | States | Matched | Rate |
|---|---|---|---:|---:|---:|
| F0 all | 30 actors | `nuscenes_global` | 767 | 440 | 57.37% |
| F0 ego | ego only | `nuscenes_global` | 39 | 20 | 51.28% |
| F0 selected | 4 actors | `nuscenes_global` | 143 | 20 | 13.99% |
| F1 selected | 4 actors | exact rigid local transform | 143 | 20 | 13.99% |
| F1 ego | ego only | exact rigid local transform | 39 | 20 | 51.28% |

The raw global and exactly transformed local results are numerically equivalent.
The frame transform is therefore not the cause of the observed baseline.

The current interaction-selection scope is not representative of the all-actor
baseline: it selects four actors including ego and produces a much lower rate.
This is an actor-population/coverage finding, not a reason to tune thresholds.

## Failure Distribution

For the all-actor baseline:

- matched: `440`
- distance-only failures: `202`
- heading-only failures: `50`
- combined failures: `75`

For the current selected interaction scope:

- matched: `20`
- distance-only failures: `49`
- heading-only failures: `39`
- combined failures: `35`

Distance mismatch dominates the selected scope. Heading mismatch is also
material, including errors near the opposite-direction boundary in the full
population. The current centerline-only metric does not account for lane width,
vehicle footprint or connector/lane direction selection.

## Tolerance Sensitivity

The private matrix swept distance tolerances `0.25`, `0.5`, `1.0`, `2.0 m` and
heading tolerances `0.1`, `0.2`, `0.4`, `0.8`, `1.57`, `3.14 rad` for the selected
scope. The result remained far below the provisional 95% reference across the
matrix; loosening heading alone did not resolve the dominant distance failures.

No production tolerance was changed.

## Evidence

Aggregate-only private output:

- `$LOCAL_EVIDENCE_ROOT/cp1-scene-0061-analysis-matrix.json`

No raw actor trajectories, per-state records or derived map artifacts were
added to the repository.

## Decision

Do not change the matcher thresholds or claim frame correction. The next CP1
slice should add a separate diagnostic for lane-width/vehicle-footprint
occupancy and inspect nearest-candidate alternatives at joins and parallel
lanes. Actor selection must be reported explicitly when comparing road-match
rates.

## Non-claims

This analysis does not establish CP1 acceptance, G3 completion, map fidelity,
simulator loadability, CP2, CARLA or same-XOSC equivalence.

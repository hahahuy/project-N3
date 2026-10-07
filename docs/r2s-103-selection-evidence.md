# R2S-103: Interaction actor selection evidence

## Contract

`real2scenario.selection.select_interaction_actors` consumes a canonical
`Scenario` and returns a new canonical scenario containing the ego plus one to
three non-ego actors. It does not mutate the source scenario and has no nuScenes
or simulator dependency.

`SelectionConfig` is the versioned selection configuration:

- `max_distance_m`: minimum synchronized ego-to-actor planar distance threshold;
- `max_ttc_s`: minimum constant-velocity TTC threshold;
- `max_actors`: output cap from 1 through 3;
- `manual_actor_ids`: optional ordered override that bypasses automatic
  thresholds.

At every synchronized state, TTC projects each actor's speed/yaw vector onto
the line of sight. Non-closing actors have unavailable TTC (`null` in the JSON
manifest), not a finite risk value. This is an interaction-ranking signal, not
a safety guarantee.

## Determinism and provenance

Automatic candidates qualify when either threshold matches. They are sorted by:

1. minimum TTC;
2. minimum distance;
3. actor ID.

This deterministic tie-break governs the `max_actors` cap. The returned
scenario stores the versioned config, every candidate decision/rejection reason,
and the selected actor IDs in provenance JSON fields:

- `interaction_selection_version`;
- `interaction_selection_config`;
- `interaction_selection_decisions`;
- `selected_actor_ids`.

Manual override preserves the caller-provided actor order but rejects unknown,
duplicate, empty, ego, or over-cap actor lists clearly.

## Automated evidence

`tests/test_selection.py` covers:

- distance threshold selection and outside-threshold rejection reason;
- TTC-only selection;
- deterministic actor-ID tie-break under an output cap;
- manual override order, threshold bypass, and source immutability;
- invalid manual selections.

The tests use synthetic canonical trajectories only; no licensed nuScenes data
or derived coordinates are committed.

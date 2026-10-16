# Canonical Artifacts

Canonical artifacts are versioned JSON representations of a `Scenario`.

## Schema

- Baseline artifact: `schema_version`, `artifact_type=baseline`, `scenario`.
- Variant artifact: baseline fields plus `parent_scenario_id` and
  `variant_config`.
- Current schema constant: `real2scenario.serialization.SCHEMA_VERSION`.

`scenario` contains actor trajectories, coordinate frame, duration, ego actor
and string-valued provenance. Unknown fields are rejected by the serializer.

## Provenance

Baseline artifacts require the keys in
`real2scenario.serialization.REQUIRED_PROVENANCE_KEYS`, including dataset,
source scene/window, transform and generator versions. Derived fields must not
silently replace source fields.

## Mutation Rules

- Reading an artifact reconstructs validated domain objects.
- Variant generation creates a child and leaves the parent unchanged.
- Workspace recipe mutations are in-process and non-destructive.
- Generated/private artifacts belong under configured artifact/output roots.

Implementation: `src/real2scenario/serialization.py`.
Tests: `tests/test_serialization.py`, `tests/test_models.py`.

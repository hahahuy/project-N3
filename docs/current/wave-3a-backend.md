# Wave 3A — U0 Authoring-Compatible Backend (Historical Completion Context)

Status: `BACKEND-SLICE-COMPLETE`  
Checkpoint started on 2026-10-12. The first backend/domain and API slice is
complete; U0 frontend work and metric-availability wiring are now complete. This
document is retained as the completion context; current Tier 1 simulator work
is defined in `docs/current/technical-contracts.md` and
`docs/current/active-work.md`.

## Objective

Build the backend/domain slice needed for the U0 Motion Editor showcase before
implementing the full UI, sensor views, POV controls, CP1 acceptance or CP2
CARLA runtime.

## Scope

Implement:

- `ActorMotionEdit` or an equivalent backward-compatible edit model;
- parameterized actor edits for speed, heading, initial gap and timing;
- deterministic child variant IDs;
- parent immutability;
- preview variant service/API;
- structured G4/G5/G6/G7 results;
- ADE/FDE/coverage response fields where replay data exists;
- parent/config/seed/hash provenance;
- synthetic-fixture execution without CARLA.

Do not implement in this section:

- full waypoint drag editor;
- behavior executor;
- OSM activation;
- sensor regeneration;
- CARLA same-XOSC runtime;
- final scientific thresholds;
- public release of nuScenes-derived artifacts.

## Suggested API

```text
POST /api/scenarios/{scenario_id}/variants/preview
```

Example request:

```json
{
  "actor_edits": [
    {
      "actor_id": "instance-target",
      "speed_multiplier": 1.2,
      "heading_offset_rad": 0.1,
      "timing_offset_s": 0.2,
      "initial_gap_delta_m": -1.0
    }
  ],
  "replay_mode": "waypoint",
  "seed": 7
}
```

The response should identify the parent, child variant, config/hash, generated
trajectory, validation/gate statuses and artifact/provenance fields.

## Acceptance Criteria

- Parent scenario is byte/field immutable after preview.
- Same parent/config/version/seed produces the same child ID and trajectory.
- Recorded and generated paths are distinguishable in API output.
- Invalid edits return structured gate reasons.
- `behavior` returns `unsupported` and never falls back to waypoint.
- Temporary G6/G7 results include `scientific_status=PROVISIONAL`.
- Existing tests and no-simulator flows remain green.
- U0 can run with the synthetic fixture without a CARLA server.

## Verification

The backend slice was initially verified on 2026-10-12 with:

```text
.venv/bin/python -m pytest -q
201 passed, 1 warning
```

The current full-suite warning is the existing Starlette/httpx deprecation.
U0 browser evidence is recorded in
`docs/evidence/m4-ui/u0-motion-editor-showcase.md` and the later UI report.

## Required Report

The agent must write an English report using
`docs/current/agent-completion-template.md`, including tests, API evidence,
unverified CARLA/CP1/CP2 claims and the next agent.

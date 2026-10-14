# R2S-303 feasibility validation evidence

## Scope

`real2scenario.validate_feasibility` checks a canonical scenario against an
immutable `FeasibilityLimits` configuration. The limits are versioned and cover
acceleration, deceleration, jerk, yaw rate, and an optional axis-aligned road
boundary in the declared scenario frame.

The validator uses finite differences over each actor's actual timestamps,
accepts values exactly at configured limits, and returns every failure as a
structured `RejectionReason`. It checks all actors and states and does not
clamp values or stop after the first rejection. A `FeasibilityReport` records
the scenario ID, limit version, validity, and complete rejection list.

## Verification

```text
pytest -q
python -m compileall -q src tests
git diff --check
```

Tests cover exact kinematic boundaries, exceeded acceleration/deceleration/
jerk/yaw-rate limits, road-boundary edges and failures, all-actor inspection,
structured reason fields, and invalid limit configurations.

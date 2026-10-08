# R2S-304 risk and ranking evidence

## Scope

`real2scenario.compute_risk_features` reports the minimum pairwise trajectory
distance, a conservative timestamp-aligned time-to-collision estimate, and
mean positional novelty relative to an optional parent scenario. TTC is only
reported when actors are timestamp-aligned and the relative velocity projects
toward the other actor; it is a signal, not a collision or safety guarantee.

`rank_scenario` retains a versioned score breakdown for risk signal, novelty,
and optional replay quality. A scenario with a failed `FeasibilityReport` is
returned as `valid=False`, `rankable=False`, and has no score breakdown. It is
never converted into a valid low score. Weight configuration and ranking
version are explicit and validated.

## Verification

```text
pytest -q
python -m compileall -q src tests
git diff --check
```

Tests cover minimum distance, TTC, novelty, transparent score arithmetic,
invalid-variant exclusion, configuration validation, and feature parameter
failure paths.

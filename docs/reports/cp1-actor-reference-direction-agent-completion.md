# Agent Completion Report

## Scope

Implemented the next CP1 semantic-alignment slice: additive global actor-reference
sensitivity and direction-counterfactual diagnostics.

## Files Changed

- `src/real2scenario/road_match.py`
- `src/real2scenario/__init__.py`
- `tests/test_road_match.py`
- `docs/reports/cp1-actor-reference-direction-diagnostics.md`
- current CP1 context documents

## Tests

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_road_match.py`: 22 passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_models.py tests/test_mapbuilder_contract.py`: 43 passed.
- Baseline before this slice: full suite 201 passed, 1 warning.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py`: PASS before this slice.

## Runtime Evidence

The private scene-0061 run completed at
`$CP1_EVIDENCE_ROOT/semantic-follow-up/`. It evaluated 143 states
against 82 native and 82 generated-XODR lanes. Native classifications were 47
aligned, 53 annotation-only, 16 annotation-yaw-error, 3 true-reverse and 24
uncertain. The run card records git revision and XODR hash; raw outputs remain
outside the repository.

## Decisions Made

- Keep actor-reference hypotheses global and counterfactual.
- Keep missing ego/actor dimensions explicitly unsupported.
- Keep reverse direction counterfactual-only.
- Preserve the `20/143 = 13.99%` baseline and `PARTIAL/PROVISIONAL` CP1 status.

## Unverified

- No cross-scene evidence was run.
- No owner decision was made on source-reference convention or unresolved lateral/direction findings.

## Blockers

The attempted compileall command encountered pre-existing unwritable `__pycache__`
files. This is an environment permission issue, not a source test failure.

## Next Agent

Run the new diagnostics against the private scene-0061 native/canonical/XODR
bundle and add the resulting rows and classifications to the owner-review report.

## Files Not Touched

CARLA, UI, OSM, simulator runtime, dataset adapters, production actor selection,
matcher weights and final scientific thresholds.

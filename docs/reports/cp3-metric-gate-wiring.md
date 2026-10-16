# CP3 Metric and Diagnostic Gate Wiring

## Scope

Wire existing replay fidelity metrics and diagnostic gate evaluators through
variant reports, aggregate reports, batch API responses and the existing UI.

## Implemented

- Variant and aggregate reports serialize replay metrics and ADE/FDE aggregates.
- Aggregate CSV includes stable ADE/FDE and G4-G7 status columns.
- Batch variants expose G4/G5/G6/G7 diagnostics.
- Batch API and frontend expose aggregate metrics and gate status.
- Batch API and aggregate reports expose ordered G1-G7 status plus provisional
  cumulative funnel counts.
- Missing FDE is excluded from FDE distributions and displayed as `n/a`.

## Tests

```text
.venv/bin/python -m pytest -q
156 passed, 2 warnings
frontend: npm test -- --run
2 passed
frontend: npm run build
vite v8.3.4 ... build succeeded
```

## Controlled Replay Evidence

The web batch path was exercised with a deterministic in-process replay fixture
containing both `ego` and `lead` actors. The one-cell grid produced:

- `generated=1`, `valid=1`, `invalid=0`, `simulator_failed=0`;
- aggregate actor count `2`;
- ADE and FDE mean/median/p95/max all `0.0` for the zero-error trace;
- gate statuses `G4=pass`, `G5=error`, `G6=fail`, `G7=pass`;
- G6 and G7 retained `scientific_status=PROVISIONAL`;
- the single-result API returned the same aggregate as the batch response.

The fixture is a controlled API/reporting test, not external simulator or CP2
runtime evidence. A separate mixed four-variant test covers one valid, two
invalid and one simulator-failed result while preserving funnel reconciliation.

## Limits

Operational status reconciliation is unchanged. G6/G7 remain diagnostic with
`scientific_status=PROVISIONAL`. No final ADE/FDE thresholds, CP2/CARLA claim,
or CP4 full-funnel claim is made.

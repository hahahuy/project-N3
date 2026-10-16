# CP4 G1-G7 Orchestration

## Status

`IMPLEMENTED`, `TESTED`, `PROVISIONAL`, `NOT FINAL SCIENTIFIC ACCEPTANCE`

The CP4 gate slice now has an additive per-candidate G1-G7 orchestration
contract and cumulative funnel reconciliation. This does not finalize any
scientific threshold, establish CARLA execution, or upgrade CP4 to acceptance.

## Implemented Contracts

`src/real2scenario/gates.py` now provides:

- `evaluate_g1_xosc()` for fail-closed OpenSCENARIO subset validation;
- `evaluate_g2_simulator_completion()` with separate backend statuses;
- `evaluate_g3_road_match()` using the existing provisional road-match report;
- `evaluate_cp4_gates()` returning exactly ordered `G1` through `G7` results;
- `summarize_gate_funnel()` with evaluated, pass and cumulative counts.

All gate results retain `pass`, `fail`, `skipped` or `error` status and reason
metadata. G3 uses a caller-supplied provisional reference and does not emit a
final scientific claim. G2 distinguishes completed, failed, unverified and
skipped simulator states; CARLA is not implicitly treated as completed.

## Funnel Rules

- `evaluated_counts[Gx]` counts non-skipped, non-error results.
- `pass_counts[Gx]` counts direct pass results.
- `cumulative_pass_counts[Gx]` counts candidates passing every gate from G1
  through `Gx`.
- A skipped or error result blocks downstream cumulative eligibility.
- Scientific status remains `PROVISIONAL`.

## Verification

Focused CP4/API/reporting tests pass. Batch integration now emits all seven
ordered gate results and aggregate JSON/API responses include `gate_funnel` with
evaluated, direct-pass and cumulative counts. Replay-enabled synthetic evidence
produces G1 `pass`, G2 `pass`, G3 `skipped` and the existing G4-G7 diagnostics;
without replay, G2 remains explicitly unverified/skipped. Tests cover ordered
G1-G7 output, simulator status separation, funnel reconciliation and API
serialization.

A mixed four-variant controlled batch exercises operational reconciliation:

```text
generated: 4
valid: 1
invalid: 2
simulator_failed: 1
G2 direct passes: 1
G2 evaluated candidates: 2
scientific status: PROVISIONAL
```

Invalid candidates skip simulator execution and therefore do not count as G2
evaluated. One valid candidate completes the controlled fake replay and the
other valid candidate reaches the controlled simulator failure. This is a
deterministic synthetic API test, not external simulator evidence.

## Superseded Detail

The gate-level evidence behaviour described above is extended by
`docs/reports/cp4-gate-evidence-closure.md`: G3 now accepts versioned
`lane-road-match-evidence-v1` evidence for a single declared candidate, and G5
consumes an explicit operator-declared event window. A candidate without a
declared event is now `G5 skipped` instead of `G5 error`.

## Boundaries

- G1 is subset validation, not a complete external XSD certification.
- G2 records simulator completion but does not create runtime evidence.
- G3 remains dependent on an explicitly supplied lane-match report; no
  benchmark candidate has one yet.
- G4-G7 preserve their existing provisional contracts.
- Ranking remains separate from gate pass/fail and rarity claims.
- No final ADE/FDE, G6 or G7 threshold is selected.
- CP1 owner interpretation remains deferred as documented in
  `docs/reports/owner-interpretation-diagnostic.md`.

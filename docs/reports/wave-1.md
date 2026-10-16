# Wave 1 Implementation Report

## Scope

Implemented the first parallel-safe slice of Plan A migration:

- CP3 evaluator extensions for ADE/FDE, coverage and short-track reporting.
- CP4 temporary G6/G7 funnel contracts.
- CP5 source-code license and nuScenes-derived artifact boundary.

CP1 map builder and CP2 same-XOSC CARLA execution were not implemented in this
wave. No claim is made that CP0/CP1/CP2 are complete.

## Files Changed

- `src/real2scenario/metrics.py`
  - Added ADE and FDE fields.
  - Added `coverage_status` with `complete`/`insufficient_coverage`.
  - Added `ScenarioReplayMetrics` and explicit short-track exclusions.
- `src/real2scenario/gates.py`
  - Added versioned `GateResult`, `FunnelReport`, `FunnelSummary` contracts.
  - Added temporary provisional G6/G7 evaluation and summary.
  - Deliberately does not expose a final scientific valid count for provisional funnels.
- `src/real2scenario/__init__.py`
  - Exported the new metrics/gate APIs.
- `src/r2s_web/schemas.py`, `src/r2s_web/adapter.py`, `src/r2s_web/jobs.py`, `src/r2s_web/esmini.py`, `frontend/src/api.ts`
  - Added backward-compatible optional ADE/FDE/coverage fields to replay metric views.
- `tests/test_metrics.py`
  - Added ADE/FDE, insufficient coverage and short-track tests.
- `tests/test_gates.py`
  - Added provisional G6/G7 and funnel reconciliation tests.
- `LICENSE`, `NOTICE`, `README.md`
  - Added Apache-2.0 source-code boundary and local/private nuScenes-derived artifact policy.
- `docs/plan-a-migration-checklist.md`
  - Marked completed implementation slice and retained runtime/scientific blockers.

## Evidence

Command:

```text
.venv/bin/python -m pytest -q
138 passed, 2 warnings in 2.38s
```

Additional checks:

```text
```

passed. The two remaining warnings are pre-existing dependency/cache warnings:
Starlette/httpx deprecation and pytest cache permission warnings.

## Provisional Status

- G6/G7 results are development diagnostics only.
- `scientific_status=PROVISIONAL` is required by the gate contract.
- `FunnelSummary.final_valid_count` remains unavailable for provisional reports.
- ADE/FDE scientific thresholds remain unresolved; no pass/fail decision is made.

## UNVERIFIED / Remaining Blockers

- Raw per-state nuScenes annotation token/timestamp sidecar is not yet wired into ingestion artifacts.
- ADE/FDE aggregate mean/median/p95/max report serialization is not yet complete.
- G1, G2, G3, G4 and G5 executable gates are not yet integrated into batch orchestration.
- G6 currently uses the existing point-based risk features as a temporary diagnostic; footprint clearance and collision event integration remain open.
- CP0 CARLA runtime sample evidence is not recorded in a phase report.
- CP1 nuScenes map builder and lane-level road-match are not implemented.
- CP2 same-XOSC CARLA adapter/interpreter and paired runtime evidence are not implemented.
- Final Singapore One-North 5–10 scene benchmark index is not frozen.
- Scientific G6/G7 thresholds and ADE/FDE thresholds remain provisional/owner-required.

## Decision Log

- Technical details in this wave were self-resolved under the agent autonomy policy in `docs/plan-a-migration-checklist.md`.
- No Plan A scope, simulator contract, legal release policy or scientific final threshold was changed.
- No raw nuScenes data or derived nuScenes artifact was added to the repository.
- No file was removed.

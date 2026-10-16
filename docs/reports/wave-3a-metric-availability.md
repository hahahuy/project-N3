# Wave 3A Gate and Metric Response Wiring

## Status

`IMPLEMENTED`, `TESTED`, `RUNTIME-VERIFIED`, `PROVISIONAL METRICS PRESERVED`

This slice closes the last open Wave 3A item: the replay-metric response wiring.
Gate and metric responses are now explicit and identical in shape across the two
surfaces the UI consumes, and metrics are never fabricated or defaulted.

## What Was Missing

The preview endpoint already returned a structured G4–G7 gate response, but the
batch and preview surfaces exposed metrics differently: consumers had to infer
whether ADE/FDE existed from the status counts and the presence of a
`replay_metrics` object. That made "no replay trace" and "zero error" easy to
confuse, which is exactly the confusion the evidence policy forbids.

## Implemented

`src/r2s_web/schemas.py` adds `MetricAvailabilityView`:

```json
{
  "available": false,
  "unavailable_reason": "no_replay_trace_was_recorded",
  "alignment_method": null,
  "source": "none",
  "per_actor": {},
  "aggregate": null
}
```

- `POST /api/scenarios/{id}/variants/preview` responses now carry a `metrics`
  block that is always `available=false` with
  `unavailable_reason="preview_has_no_simulator_trace"`, because preview does
  not run a simulator.
- `GET /api/batches/{job}/results` now carries a `replay_metrics` block that is
  `available=true` with `source="replay_trace"`, the alignment method and the
  aggregate distribution when a trace exists, and `available=false` with
  `unavailable_reason="no_replay_trace_was_recorded"` otherwise.
- The `AggregateReport` domain object is still exposed on the job record so the
  benchmark aggregation path keeps working unchanged.

## Rules Preserved

- No metric is invented, interpolated or defaulted to zero when a trace is
  missing.
- `fde_m` stays `null` when replay coverage is incomplete; it is never replaced
  by zero.
- Per-actor metrics keep `coverage_status` and the recorded alignment method so
  a reviewer can see how the comparison was made.
- G6/G7 remain `PROVISIONAL`; gate statuses keep the fixed vocabulary
  `pass`/`fail`/`skipped`/`error`.

## Verification

Focused tests cover the unavailable case on both surfaces, the available case
with a controlled replay, the alignment method and aggregate wiring, and the
invariant that a preview never claims metrics.

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
docs consistency: PASS

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
259 passed, 1 warning (existing Starlette/httpx deprecation).
```

Live Compose smoke test against the local API:

```text
preview metrics: available=false, reason=preview_has_no_simulator_trace
batch metrics:   available=true, source=replay_trace, actor_count=4
```

## Boundaries

- No metric threshold, gate policy or scientific claim changes.
- Preview still performs no simulator execution.
- The UI must adopt the new fields; see `docs/current/ui-mvp-flow-spec.md`.

## Next Action

Frontend/UX agent work against the documented flow: adopt the metric
availability blocks, implement the state matrix, and build the full 2D/3D
authoring workspace on top of the internal kinematic simulator.
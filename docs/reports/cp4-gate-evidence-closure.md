# CP4 Gate Evidence Closure (G3 and G5)

## Status

`IMPLEMENTED`, `TESTED`, `RUNTIME-VERIFIED/PROVISIONAL`, `NOT FINAL SCIENTIFIC ACCEPTANCE`

This slice closes the two CP4 gates that could never report an evaluated
result. Before this change `G3` was `skipped` and `G5` was `error` for every
candidate in every batch, so the cumulative funnel could never advance past G3.
Both gates now consume explicit, validated evidence and report a real
evaluated, skipped or error state.

No CP1 policy, tolerance, threshold, actor scope or ground-truth interpretation
changed, and CP1 remains `PARTIAL/PROVISIONAL`.

## G3 Lane Road-Match Evidence

`src/real2scenario/road_match.py` adds a gate-level evidence contract:

```text
evidence_version:    lane-road-match-evidence-v1
scenario_id, coordinate_frame, algorithm_version
config:              max_distance_m, max_heading_error_rad (required)
overall:             state_count, matched_state_count, raw_match_rate,
                     provisional_95_status
diagnostic_status:   diagnostic
scientific_status:   PROVISIONAL
```

- `lane_road_match_evidence_from_report()` projects a full CP1 road-match report
  into evidence without hand-written JSON.
- `lane_road_match_evidence_to_dict()` / `..._from_dict()` are deterministic and
  fail closed: unknown fields, inconsistent counts, a `raw_match_rate` that does
  not match the counts, a missing explicit provisional status, missing matcher
  configuration, or any non-`PROVISIONAL`/non-`diagnostic` claim are rejected.
- `evaluate_g3_road_match()` accepts either the full report or the evidence
  summary, keeps the provisional `0.95` reference fixed as
  `G3_MINIMUM_MATCH_RATE`, and still reports missing evidence as an explicit
  skip with reason `road_match_unavailable`.

## G3 Request Contract

`POST /api/batches` accepts `lane_match_evidence`, keyed by `variant_id`:

```json
{
  "lane_match_evidence": {
    "<variant_id>": {
      "evidence_version": "lane-road-match-evidence-v1",
      "scenario_id": "<the same variant_id>",
      "coordinate_frame": "local_road_aligned",
      "algorithm_version": "lane-road-match-v1",
      "config": {"max_distance_m": 0.5, "max_heading_error_rad": 0.2},
      "selected_actor_ids": ["ego", "instance-..."],
      "overall": {
        "state_count": 143,
        "matched_state_count": 20,
        "raw_match_rate": 0.13986013986013987,
        "provisional_95_status": "below_95_percent"
      },
      "diagnostic_status": "diagnostic",
      "scientific_status": "PROVISIONAL"
    }
  }
}
```

The request payload is the canonical domain evidence record, validated by
`lane_road_match_evidence_from_dict()` at the request boundary. There is no
second, looser API shape for evidence.

Rules:

- Evidence applies only to the candidate whose `variant_id` is the key. A
  candidate without evidence keeps `G3 skipped`, so partial evidence never
  generalises to the rest of the batch.
- The evidence `scenario_id` must equal the candidate variant ID. A mismatch
  fails the job with `lane_match_evidence_scenario_mismatch` before any
  simulator work.
- Evidence for a key that matches no candidate is ignored and reported as
  `lane_match_evidence_unused` in the benchmark run card.
- The request schema forbids any minimum-match-rate field, so the API cannot
  move the `0.95` provisional reference (`422` on an attempt).
- `G3` remains `PROVISIONAL` even when it passes.

## G5 Declared Main Event

`POST /api/batches` accepts an explicit `event_declaration`:

```json
{
  "event_declaration": {
    "main_event_start_s": 1.0,
    "main_event_end_s": 5.0,
    "event_type": "interaction_window",
    "event_target_actor_id": "instance-...",
    "event_source": "operator_declared"
  }
}
```

- The declaration is validated before use and never inferred from trajectories.
  An end before the start, non-finite values, a window outside the scenario
  duration, an empty event type or an unknown target actor produce
  `G5 error` with `invalid_event_window`, `event_window_outside_scenario` or
  `unknown_event_target`.
- Unknown or incomplete declaration fields are rejected rather than ignored.
- The declaration is written into the variant artifact provenance with the
  `event_source` label, so the artifact and the gate result agree. The parent
  scenario is never mutated.
- `G5` observed values now record `main_event_start_s`, `main_event_end_s`,
  `event_type` and `event_source`.

### Status Semantics Change

| Condition | Before | After |
|---|---|---|
| No event declared | `error` / `missing_event_definition` | `skipped` / `event_definition_not_declared` |
| Malformed declaration | `error` | `error` with a specific reason |
| Valid declaration | `pass` / `fail` | `pass` / `fail` with observed window and source |

The old behaviour reported a pipeline error for every candidate even when the
caller had simply not declared an event, which inflated error counts and hid
real evaluation results. `skipped` means the capability was not declared;
`error` now means supplied evidence could not be used.

## Verification

Focused tests cover evidence round-trip and rejection, the fixed provisional
reference, G3 per-candidate application, mismatch and unused-key handling, API
rejection of a threshold override, declared and malformed events, and the
undeclared skip. Gate evaluator tests cover collision before the event start,
boundary strictness, declaration sourcing and validation errors.

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
docs consistency: PASS

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
240 passed, 1 warning (existing Starlette/httpx deprecation).
```

## Runtime Evidence

Five-scene provisional run with one unedited candidate per scene (esmini
`v3.9.0`), before and after declaring an operator event window per scene:

```text
undeclared:  evaluated G1 4, G2 4, G3 0, G4 5, G5 0, G6 5, G7 5
declared:    evaluated G1 4, G2 4, G3 0, G4 5, G5 5, G6 5, G7 5
declared passes: G1 4, G2 4, G3 0, G4 4, G5 3, G6 0, G7 5
```

`G5` moved from permanent error to a real evaluated split (3 pass, 2 fail on a
declared interaction window). `G3` stays `skipped` because no lane road-match
evidence exists for edited candidates; supplying it requires the CP1 follow-up
diagnostics and is deliberately not simulated here.

Live Compose smoke test (mini dataset, real esmini replay) with a declared
event:

```text
G1 pass, G2 pass, G3 skipped(road_match_unavailable), G4 pass,
G5 pass, G6 fail(collision_status_unverified), G7 pass
```

## Boundaries

- No road-match evidence was fabricated and no lane truth was invented.
- The `0.95` provisional reference, the actor scope, tolerances and CP1 ground
  truth are untouched.
- Declared events are `operator_declared` labels, not detected or validated
  ground-truth events; they exist so G5 can be evaluated at all.
- `G6`/`G7` remain provisional diagnostics; no final scientific claim.
- The provisional benchmark scene index remains agent-selected and unapproved.
- CARLA remains unverified and post-MVP.

## Next Action

CP1 follow-up: produce lane road-match evidence for benchmark candidates and
feed it through `lane_match_evidence`, which is what moves G3 from skipped to
evaluated. Then CP5 reproducibility and release evidence for the resulting
runs.
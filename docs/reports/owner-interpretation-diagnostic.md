# Owner Interpretation Diagnostic

## Decision

`DEFERRED / LATER OBJECTIVE`

The owner-interpretation review of the CP1 actor-reference and direction
diagnostic is intentionally deferred. This is a scheduling decision, not an
acceptance decision and not a change to the CP1 scientific interpretation.

## Preserved Boundaries

- CP1 remains `PARTIAL/PROVISIONAL`.
- The immutable selected-corridor baseline remains `20/143 = 13.99%`.
- The automatic four-actor scope remains unchanged.
- The annotation-center/no-correction convention remains unchanged for the
  current run.
- Ego dimensions remain unsupported and are not guessed.
- Reverse lane direction remains counterfactual-only.
- Native, canonical and generated-XODR results remain separate diagnostics.
- No actor-specific offset, tolerance change, lane reversal or threshold change
  is approved by this deferral.

## Deferred Questions

The following questions remain open for a later owner review:

1. Reconcile the actor-direction classification discrepancy between the earlier
   CP1 direction/footprint evidence and the new reference diagnostic.
2. Decide whether the unresolved lateral actors represent source-reference,
   native-map association, or lane-membership ambiguity.
3. Decide whether any globally supported reference convention is justified by
   repeated cross-scene evidence.
4. Confirm whether the automatic actor scope should remain the benchmark scope.

## Why Deferral Is Safe

The diagnostic APIs and private evidence bundle are reproducible and preserved.
The unresolved results do not block additive work that does not change CP1 map
truth, actor selection or scientific thresholds. Deferral avoids converting a
single-scene interpretation into a production policy while allowing the next
checkpoint work to proceed.

## Re-entry Condition

Reopen this objective before CP1 acceptance, final lane-direction policy,
scientific threshold selection, or any production actor-reference change. The
later review should use the private bundle under `$CP1_EVIDENCE_ROOT/semantic-follow-up/`
and include cross-scene evidence where available.

## Next Work Authorized

Proceed with additive CP4 G1-G7 orchestration and reconciliation work. Do not
use CP4 diagnostics to relabel the deferred CP1 findings or claim final
scientific pass/fail thresholds.

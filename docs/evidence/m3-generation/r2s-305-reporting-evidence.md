# R2S-305 batch report evidence

## Scope

`real2scenario.reporting` exports one `VariantReport` per generated variant and
an ordered `AggregateReport` for a batch. Every result has exactly one status:
`valid`, `invalid`, or `simulator-failed`. Reports retain validation version and
structured reasons, optional ranking details, simulator error text, and links
to the canonical scenario, OpenSCENARIO, replay trace, and report artifacts.

The aggregate enforces unique variant IDs and the reconciliation invariant:

```text
generated = valid + invalid + simulator_failed
```

Writers produce deterministic compact JSON and stable CSV rows at caller-
provided paths. They create only the requested output directories and never
embed machine-specific paths.

## Verification

```text
pytest -q
python -m compileall -q src tests
git diff --check
```

Tests cover reconciliation across all three statuses, artifact-link
serialization, structured validation reasons, deterministic filesystem output,
invalid status contracts, missing simulator errors, and duplicate IDs.

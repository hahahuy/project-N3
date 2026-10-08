# R2S-301 perturbation evidence

## Scope

`real2scenario.perturb_scenario` creates a deterministic child `Scenario` from
a baseline and `VariantConfig`. It does not mutate the parent. Speed scaling
changes state speed and longitudinal displacement relative to each actor's
initial state. Initial gap changes non-ego positions along the ego's initial
heading. Timing offset changes non-ego timestamps and extends the child
duration when necessary.

The child ID is a stable SHA-256-derived value from the parent ID, complete
configuration, and generator version. The child provenance records the parent,
generator version, every parameter, and the seed. A timing offset that would
create a negative timestamp is rejected; no value is silently clamped.

## Verification

```text
pytest -q
python -m compileall -q src tests
git diff --check
```

The test coverage includes deterministic reruns, parent immutability, expected
speed/gap/timing changes, non-zero heading, invalid negative timing, invalid
seed, and an empty generator version.

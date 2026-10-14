# R2S-302 batch generation evidence

## Scope

`generate_grid_variants` produces the Cartesian product of speed multiplier,
initial gap delta, and timing offset values in caller-provided order. Each
configuration is passed through the R2S-301 perturbation path, so variant IDs
and trajectories use the same deterministic contract.

`generate_random_variants` samples each parameter from an inclusive uniform
range using a private pseudo-random generator initialized from the batch seed.
Each generated configuration also receives a deterministic per-variant seed.

Both functions return the variants and a `BatchManifest`. The manifest records
the parent ID, generator version, mode, batch seed, ordered variant IDs, and
complete configurations. `batch_manifest_to_json` emits stable compact JSON.
Empty grids, invalid counts, reversed ranges, non-positive speed ranges, and
non-integer seeds are rejected without producing partial output.

## Verification

```text
pytest -q
python -m compileall -q src tests
git diff --check
```

The tests cover deterministic grid order and IDs, deterministic seeded random
output, manifest serialization, requested count and range preservation, and
invalid configuration paths.

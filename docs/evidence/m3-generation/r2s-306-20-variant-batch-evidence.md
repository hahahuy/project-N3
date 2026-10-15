# R2S-306 deterministic 20-variant batch evidence

## Scope

The M3 review gate requires at least 20 variants generated from one fixed
baseline. This evidence uses the sanitized synthetic baseline already shared by
the generation tests. It does not include licensed nuScenes content or generated
artifacts.

The batch uses a deterministic Cartesian product:

- Speed multipliers: `0.9`, `1.0`
- Initial gap deltas: `-2.0 m`, `0.0 m`
- Timing offsets: `0.0 s`, `0.25 s`, `0.5 s`, `0.75 s`, `1.0 s`
- Seed: `7`

This produces `2 x 2 x 5 = 20` variants. Repeating the same call produces the
same ordered variants, IDs, configurations, and trajectories.

## Verification

```bash
source .venv/bin/activate
pytest -q tests/test_generation.py -k twenty_variant
```

Observed result:

```text
1 passed, 12 deselected
```

The full repository verification also passes:

```bash
pytest -q
python -m compileall -q src tests
git diff --check
```

Observed result:

```text
118 passed
```

The test verifies the generation count and deterministic equality of the second
run. The existing reporting tests verify reconciliation across `valid`,
`invalid`, and `simulator-failed` statuses using the same aggregate report
contract.

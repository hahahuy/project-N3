# CP5 Reproducibility Manifest

## Scope

Implemented the independent CP5 packaging slice for local/private runs. This
does not touch CP1 map construction, road-match policy, simulator execution, or
scientific thresholds.

## Implemented

- Added `real2scenario.packaging.build_reproducibility_manifest()`.
- Added deterministic `manifest_to_json()` serialization.
- Recorded project version and git commit, Python/runtime metadata, caller-
  supplied dataset/map/simulator metadata, configuration hash, artifact
  visibility, and a sorted project-relative artifact inventory.
- Recorded SHA-256 and byte size for every inventoried artifact.
- Rejected missing files and files outside the declared artifact root so local
  host paths cannot be emitted as artifact identifiers.
- Exported the API from `real2scenario` and added focused tests.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
179 passed, 1 warning
```

The warning is the existing Starlette/httpx deprecation warning. The default
pytest cache path is not writable in this worktree, so verification disables
the cache provider; no source or test failure was observed.

## Limits

- This is a manifest builder, not a benchmark runner or dependency lockfile.
- Dataset, map, simulator, and git values are supplied by the caller; no
  restricted data or runtime artifacts are added to the repository.
- CP5 clean-checkout reproducibility, benchmark protocol, dependency lockfile,
  and reviewer sign-off remain open.

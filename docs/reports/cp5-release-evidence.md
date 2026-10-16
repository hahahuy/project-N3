# CP5 Reproducibility and Release Evidence

## Status

`IMPLEMENTED`, `RUNTIME-VERIFIED`, `ENGINEERING EVIDENCE ONLY`, `OWNER SIGN-OFF PENDING`

This slice closes the CP5 reproducibility and release-evidence gaps that were
open after the manifest contract was added: benchmark orchestration evidence,
clean-checkout verification, a dependency lockfile and a machine-readable
release evidence bundle. It creates no scientific acceptance and no owner
sign-off.

## Benchmark Reproducibility Manifest

`scripts/run_benchmark_scenes.py` now emits
`reproducibility-manifest.json` next to each run card through the existing
`build_reproducibility_manifest()` contract:

- every run artifact is inventoried by relative POSIX path with size and
  SHA-256 (756 artifacts for the current five-scene run);
- the configuration block records the grid, seed, actor limit, replay flag,
  dataset version, metadata index version and the scene index hash, and is
  hashed into `config_sha256`;
- project version, git commit, Python runtime, dataset and simulator metadata
  are recorded as caller-supplied values, including the resolved esmini tag;
- the run card and the manifest both record `git_working_tree_clean`, so a run
  produced from uncommitted sources is never presented as a release candidate;
- no host path, dataset location or simulator binary appears in the manifest.

The manifest deliberately does not record absolute dataset or evidence roots.
Those remain local/private and are referenced through the git revision,
`config_sha256` and the artifact inventory.

## Dependency Lockfile

`requirements.lock.txt` pins the verified environment (55 distributions) and
records the regeneration command. Local `file://` build artifacts, including the
CARLA devkit wheel, are excluded because they are not public installable
requirements; CARLA remains post-MVP and unverified.

## Clean-Checkout Verification

`scripts/verify_release.py` answers one question: does the committed repository
state reproduce its own verification evidence without the developer's working
tree?

- `--source head` exports `HEAD` with `git archive`, rejects unsafe archive
  members, and runs the documented verification commands against that export
  with `PYTHONPATH` pointed at the exported sources.
- `--source working-tree` snapshots the current sources with the same commands
  for pre-commit engineering evidence.
- Checks: full pytest suite, documentation consistency, restricted dataset or
  sensor content, absolute host paths in committed docs, presence of the
  lockfile, and license/notice presence.
- Output: a deterministic `release-evidence-v1` bundle with the git revision,
  tree hash, file count, per-check status and `sign_off.status=pending_owner`.

The verification runs with the current interpreter; the lockfile records the
dependency set. This is a source-reproducibility check, not a hermetic build.

## Defect Found and Fixed

The first clean-checkout run failed with `HEAD`, and the failure was real:

- `tests/test_web_api.py::test_settings_and_source_scene_import_can_use_configured_local_dataset`
  depended on the local, git-ignored `data/v1.0-mini` metadata directory, so the
  suite could not pass in a clean checkout. The test now skips with an explicit
  reason when the local dataset is absent, and clean-checkout verification
  reports `239 passed, 1 skipped`.

The remaining `HEAD` failures are the uncommitted state of the repository:
`requirements.lock.txt` and the reorganised `docs/current/` tree are not in the
committed revision, so the clean checkout of `HEAD` fails the documentation
check and reports a missing lockfile. That is a commit-state blocker, not a code
defect.

## Runtime Evidence

```text
--source head          (revision 41371649, working tree dirty)
  status: fail
  pytest:  1 failed, 123 passed   (local-dataset dependency, since fixed)
  docs:    fail                  (docs/current tree not committed)
  lockfile: missing
  restricted dataset content: pass
  committed host paths: pass

--source working-tree  (current sources)
  status: pass
  pytest:  239 passed, 1 skipped
  docs:    pass
  lockfile: present
  restricted dataset content: pass
  committed host paths: pass
  tree_sha256: ebce5730ba7e440d...
```

Bundles are stored outside the repository under the private evidence root. No
restricted data and no derived dataset artifact was added to the repository.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
docs consistency: PASS

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
247 passed, 1 warning (existing Starlette/httpx deprecation).
```

## Boundaries

- Owner sign-off, reviewer approval and release tagging remain owner actions.
- The manifest and release bundle are engineering evidence; they do not certify
  scientific results, CP3 acceptance or any license clearance beyond the
  existing Apache-2.0 boundary.
- The benchmark scene index remains agent-selected and unapproved, so this
  evidence attaches to a provisional run.
- CARLA remains unverified and post-MVP.

## Next Action

Commit the verified tree so `HEAD` verification can pass, then repeat the
release verification against the committed revision. Owner sign-off stays with
the owner.
# Local Artifact Bundle Index

Status: `CURRENT`
Scope: index of `local/private` evidence bundles held on the operator's host.

This file records that nuScenes-derived evidence bundles exist, what they
contain, and how to verify their integrity. It deliberately contains **no
absolute host paths**, per `docs/current/artifact-policy.md:17`. Bundles are
identified by a stable bundle name; the operator resolves them on the host.

None of these files are in the repository. `docs/README.md` and
`docs/current/artifact-policy.md:9-10` prohibit committing nuScenes-derived
`.xodr`, `.xosc`, replay CSV and derived scenario JSON. This index is the
committed counterpart of that local/private data.

---

## 1. Why this index exists

`docs/current/artifact-policy.md:13-16` requires every local/private run to have
a manifest containing versions, hashes, config and visibility, and records that
current batch/replay manifests are `PARTIAL`.

The bundles below predate or sit outside that requirement. This index supplies
the inventory and digest layer so a future agent can tell what exists and prove
a bundle has not changed, without committing restricted content.

It does not satisfy the full manifest contract. `dataset_version`,
`tool_version`, `config` and per-file hashes are still `PARTIAL` and remain
work for the owning track.

## 2. Bundle inventory

Digests are `sha256` over the sorted `sha256sum` listing of every file in the
bundle. Recompute with:

```bash
find <bundle> -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum
```

| Bundle | Files | Bytes | Digest (16) | Visibility |
|---|---:|---:|---|---|
| `cp1-evidence` | 5 | 28,661 | `7cccaf3ba319aa78` | local/private |
| `cp1-evidence-corridor` | 19 | 660,944 | `c308f9ec0f6b6099` | local/private |
| `cp1-evidence-final` | 19 | 12,222,895 | `8c1cfd3a55cd60f2` | local/private |
| `cp1-evidence-review` | 6 | 61,686 | `efce32edadc14e3f` | local/private |
| `r2s-evidence` | 801 | 61,272,073 | `1c07aa862c92e316` | local/private |

## 3. Bundle contents

| Bundle | Composition | Corresponds to |
|---|---|---|
| `cp1-evidence` | 5 `.json` | CP1 corridor diagnostic records |
| `cp1-evidence-corridor` | 11 `.json`, 3 `.xodr`, 1 `.xosc`, 1 `.dat`, 2 `.txt`, 1 `.md` | CP1 corridor external evidence; contains `semantic-follow-up/comparison-summary.md` |
| `cp1-evidence-final` | 5 `.xodr`, 4 `.xosc`, 2 `.json`, 2 `.dat`, 4 `.txt`, 1 `.stdout`, 1 `.stderr` | CP1 map load / topology repair run with esmini console capture |
| `cp1-evidence-review` | 2 `.md`, 2 `.json`, 1 `.yaml`, 1 `.csv` | CP1 manual review bundle (instructions, run card, scene identity, actor inventory, state review sheet) |
| `r2s-evidence` | 296 `.json`, 111 `.xodr`, 96 `.xosc`, 106 `.csv`, 96 `.dat`, 96 `.txt` | CP3 benchmark and CP5 release evidence |

`r2s-evidence` is organised by track:

```text
r2s-evidence/
  cp3-benchmark/
    prepared/       canonical scenario preparation
    run/            provisional benchmark run
    run-with-g3/    rerun with the G3 candidate gate evaluated
    cp1-review/     per-scene corridor review
    gate-evidence/  candidate road-match evidence
  cp5-release/      release and reproducibility evidence
```

## 4. Documentation already committed

The one substantive Markdown summary in these bundles,
`cp1-evidence-corridor/semantic-follow-up/comparison-summary.md`, is
**already committed** as `docs/reports/cp1-actor-reference-direction-diagnostics.md`.
The contents match; copying it again would duplicate the reference table and the
immutable `20/143 = 13.99%` statement. No copy was made.

The CP1 manual review template was extracted as
`docs/reports/cp1-corridor-review-template.md` because it is a blank form with
no private data. Its sibling instruction file (`cp1-evidence-review/review/README.md`)
was **not** committed because every step in it references sibling bundle files
that cannot be committed; it would be unusable in the repository.

## 5. What is deliberately absent

- No absolute host paths (`docs/current/artifact-policy.md:17`).
- No raw nuScenes data, point clouds, camera images or CAN messages.
- No `.xodr`, `.xosc`, replay CSV, `.dat` or derived canonical scenario JSON.
- No credentials, tokens or dataset licence text.
- No actor trajectories or coordinate data.

## 6. Verification

Per `docs/README.md`, no `DONE` from inspection alone. This index was produced
by:

- enumerating each bundle for file count and byte total;
- computing the per-bundle digest as described in Section 2;
- comparing `cp1-evidence-corridor/semantic-follow-up/comparison-summary.md`
  against `docs/reports/cp1-actor-reference-direction-diagnostics.md` for the
  shared hypothesis table and the `20/143 = 13.99%` baseline.

Digests are **host-state specific**. If a bundle is regenerated, its digest
changes and this index must be updated. Digests are not a substitute for the
per-file manifest required by `docs/current/artifact-policy.md:13-16`.

## 7. Unverified

- Bundle contents were inventoried by extension, not parsed. File counts and
  digests are accurate; semantic contents are not audited here.
- No `dataset_version`, `tool_version` or `config` field is recorded for any
  bundle. The manifest contract remains `PARTIAL`.
- The bundles' correspondence to specific commits in `docs/reports/` is
  inferred from naming and was not confirmed with the owning agent.

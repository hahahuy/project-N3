# Artifact Policy

| Artifact | Location | Commit | Public release | Rule |
|---|---|---:|---:|---|
| Source code/tests | repository | yes | yes | Apache-2.0 |
| Synthetic fixtures | repository | yes | yes | Must contain no restricted data |
| Metadata-only scene index | repository | conditional | conditional | No coordinate-rich/state data |
| Raw nuScenes data | external dataset root | no | no | Dataset terms apply |
| nuScenes-derived `.xodr`/`.xosc` | local/private | no | no | Until separate release approval |
| Replay CSV/PNG/video | local/private | no | no | May contain derived trajectories |
| Aggregate metrics | repository | conditional | conditional | Scrub restricted content first |

Every local/private run should have a manifest containing versions, hashes,
config and visibility. The reproducibility-manifest-v1 and release-evidence-v1
structures are implemented and tested, but acceptance remains conditional on a
run-specific inventory containing dataset, tool, map/XODR, input hash, file
inventory and visibility fields. A private evidence bundle or working-tree
verification is not release sign-off.
Avoid absolute host paths in committed documentation.

`docs/current/local-artifact-bundles.md` indexes the local/private evidence
bundles held on the operator host: inventory, composition, content digests and
verification method. It records what exists without committing restricted
content and without absolute host paths. It does not by itself satisfy the
run-manifest contract or owner release sign-off.

`docs/reports/cp1-corridor-review-template.md` is the blank CP1 corridor manual
review sheet, extracted from the same bundle family.

"Local/private" currently means a trusted local deployment policy, not a
technical access-control guarantee. The local API has no authentication and
must not be exposed to untrusted networks.

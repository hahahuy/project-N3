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
config and visibility. This is an active implementation requirement; current
batch/replay manifests are incomplete and remain `PARTIAL` until dataset,
tool, map/XODR, input hash, file inventory and visibility fields are persisted.
Avoid absolute host paths in committed documentation.

"Local/private" currently means a trusted local deployment policy, not a
technical access-control guarantee. The local API has no authentication and
must not be exposed to untrusted networks.

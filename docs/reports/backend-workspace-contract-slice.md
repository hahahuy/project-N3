# Backend Workspace Contract Slice

## Status

`IMPLEMENTED-PARTIAL`, `TESTED`, `U1`

This slice implements the first backend Workspace contracts from
`docs/current/backend-workspace-contract-log.md` without inventing unavailable
map, 3D or sensor data.

## Endpoints

- `GET /api/workspace/documents/{scenario_id}`
- `GET /api/workspace/scenarios/{scenario_id}`

## Implemented Contracts

### B-WORKSPACE-01

Workspace document metadata includes the document name, branch, version, active
scenario ID, connection/dataset/esmini availability, dataset/esmini versions,
coordinate frame, transform version and canonical provenance.

### B-WORKSPACE-02

Scenario view payload includes scenario summary, actor poses and roles, actor
dimensions with explicit availability/reason, recorded/generated paths, and
layer availability for map lanes, XODR geometry and LiDAR.

Map lanes, viewer XODR geometry and LiDAR are explicitly unavailable because
those artifacts are not currently exposed by the local canonical artifact
adapter. No placeholder geometry is returned.

### B-WORKSPACE-06

The scenario view uses the existing explicit metric availability contract:
`available`, `unavailable_reason`, source (`replay_trace` or `none`) and
per-actor metrics. No missing metric is defaulted to zero.

## Verification

`tests/test_web_api.py` covers the new endpoints and verifies dataset
unavailability, coordinate-frame metadata, actor dimension availability, and
explicit map/LiDAR reasons. The full Python suite and docs consistency check are
the required final checks.

## Remaining Workspace Contracts

B-WORKSPACE-03 recipe representation, B-WORKSPACE-04 gate timeline extents,
B-WORKSPACE-05 complete variant lineage, B-WORKSPACE-07 viewer-friendly 3D/XODR
geometry, and B-WORKSPACE-08 through B-WORKSPACE-10 LiDAR/sensor contracts remain
open until their backend artifacts exist.

# Backend Workspace Contract Log

Status: `ACTIVE / BACKEND TASK REGISTER`
Consumer: frontend Workspace agents
Primary specification: `docs/current/ui-mvp-flow-spec.md`
Frontend log: `docs/current/frontend-workspace-log.md`

## Purpose

This is the contract register for data the Workspace needs but must not invent.
Backend work should update the status, endpoint, schema, tests, and evidence for
each item. Frontend agents should link their changes to these rows before using
new fields.

## Required contract work

| ID | Capability | Required fields / behavior | Milestone | Status |
|---|---|---|---|---|
| B-WORKSPACE-01 | Workspace document metadata | document name, branch, version, active scenario, connection/dataset/esmini status, coordinate frame, transform version | U1 | Open |
| B-WORKSPACE-02 | Scenario view payload | map lane polylines, actor pose, role/ego marker, dimensions, recorded/generated paths, layer availability and reasons | U1/U5 | Partial; trajectories exist, map and dimensions missing |
| B-WORKSPACE-03 | Recipe representation | ordered steps, id, kind, params, status, active/inactive state, API error, artifact link | U2 | Open |
| B-WORKSPACE-04 | Gate timeline | G1-G7 status, observed value, reason, scientific status, start/end extents | U3 | Open |
| B-WORKSPACE-05 | Variant lineage | parent scenario id, branch name, variant configuration, run id, seed, config hash | U4 | Partial; existing variant fields are not a complete lineage contract |
| B-WORKSPACE-06 | Metric availability | value, unit, status, scientific status, availability block, unavailable reason, mean/p95/max distinction | U3/U4 | Partial; existing replay metrics need generic status handling |
| B-WORKSPACE-07 | 3D scene data | xodr/viewer geometry, actor dimensions with available/unsupported flag, 3D transforms | U5 | Open |
| B-WORKSPACE-08 | LiDAR sweeps | sensor channel, timestamp, nearest-sweep offset, binary x/y/z/intensity payload, frame, transform version | U6 | Open |
| B-WORKSPACE-09 | LiDAR decimation | total count, returned count, decimation metadata, explicit availability/reason | U6 | Open |
| B-WORKSPACE-10 | Variant sensor status | explicit post-edit sensor-frame support status and parent-sweep fallback status/reason | U6 | Open |

## Contract rules

- Every availability block must include a boolean and an API-owned reason when
  unavailable. Missing arrays are not an availability protocol.
- Status vocabulary is fixed: `pass`, `fail`, `skipped`, `error`, `valid`,
  `invalid`, `simulator-failed`, `unavailable`, `unsupported`, `PROVISIONAL`,
  and `not-applicable`.
- Preserve provenance: dataset/version, source scene token, transform version,
  reference-point convention, run id, seed, config hash, and artifact links.
- Do not make frontend-only compatibility aliases part of the public contract.
- Add API schema tests and web API tests for every contract change.

## Backend change protocol

Append a row after implementation:

| Date | ID | Endpoint/schema | Tests/evidence | Frontend impact | Status |
|---|---|---|---|---|---|
| 2026-10-14 | B-WORKSPACE-01..10 | No new contract yet | Existing API tests only | Frontend remains honest/unavailable where data is absent | Open / partial as listed above |

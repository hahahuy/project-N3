# nuScenes-devkit Phase 2 Evidence

Status: `IMPLEMENTED / TESTED / ADDITIVE / PROVISIONAL`

- `source-state-extension-v1` carries CAN `pose` acceleration and yaw-rate to
  `kinematic-open-loop-v1` without changing canonical `State`.
- Nearest timestamp matching remains bounded at `100000` microseconds and never
  extrapolates. Missing values carry explicit finite-difference provenance.
- Read-only native map/query contracts cover the declared layers and preserve
  local-private oracle provenance.
- Workspace API routes now expose native-map capability, patch record tokens and
  road-ahead queries with explicit dataset/devkit unavailable responses.
- `LidarPayloadContract` records channel, timestamp, source file, frame,
  calibration and decimation and rejects non-private visibility.
- Advisory minADE/minFDE is separate from replay fidelity metrics.
- Tier 1 now emits `normalized-replay-trace-v2`-compatible traces, reports
  acceleration/deceleration/jerk/yaw-rate violations without clamping, and
  provides a fail-closed footprint collision pre-check.

The CP1 `20/143 = 13.99%` baseline, matcher policies, licensing boundaries and
canonical schema are unchanged. No raw point cloud, map payload or prediction
dataset is committed. Esmini comparison, live dataset payload/UI wiring and
full Tier 1 acceptance evidence remain unverified follow-up work.

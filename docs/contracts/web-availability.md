# Web Availability

Optional capabilities must be explicit. A consumer must be able to distinguish
available, unavailable and unsupported behavior without guessing from missing
fields.

## Common Shape

```json
{
  "available": false,
  "unavailable_reason": "dataset_not_configured"
}
```

Richer contracts carry `status`, `source`, `provenance`, `artifact_visibility`
and a named reason where applicable.

## Rules

- Missing numeric data is not represented as zero.
- Missing artifacts are not represented as successful empty artifacts.
- Browser transform frames are not simulator image evidence.
- Recorded sensor evidence and post-edit sensor output are separate layers.
- Scientific results that are not final remain labelled `PROVISIONAL`.
- API errors should use a stable status and a concise API-owned reason.

## Key Contract Families

| Family | Examples |
|---|---|
| Workspace | `workspace-*` contracts for documents, timelines, recipes and compare |
| Sensor | `nuscenes-lidar-payload-v1`, `nuscenes-sensor-evidence-v1` |
| Simulator | `simulator-frame-v1`, `workspace-pov-image-v1`, `esmini-live-session-v1` |
| Evidence | recorded/generated/replayed/sensor-evidence availability and provenance |

Detailed field ownership is tracked in
[`../current/backend-workspace-contract-log.md`](../current/backend-workspace-contract-log.md).

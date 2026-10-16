# System Overview

Status: `REFERENCE`

Real2Scenario converts recorded driving interactions into canonical scenario
artifacts, optional OpenSCENARIO/esmini replay outputs, controlled variants,
metrics and reviewable evidence. The repository has four runtime layers:

```text
React workspace
    -> FastAPI routes and web services
        -> canonical artifacts and domain services
            -> dataset/simulator adapters
                -> nuScenes metadata, sensor data, maps and esmini
```

## Runtime Products

| Product | Entry point | Responsibility |
|---|---|---|
| Browser workspace | `frontend/src/App.tsx` | Views, user interaction, API state and explicit unavailable states |
| Web API | `src/r2s_web/app.py` | HTTP/WebSocket routing, orchestration and response contracts |
| Scenario core | `src/real2scenario/` | Canonical models, ingestion, generation, validation, replay and metrics |
| Local adapters | `src/r2s_web/nuscenes_adapter.py`, `src/real2scenario/nuscenes_backend.py`, `src/r2s_web/live_session.py` | Integrate external data/tools without leaking their native representations |

## Main Flows

### Recorded ingestion

```text
scene/sample tokens
  -> MetadataIndex / nuScenes source adapter
  -> extract_scenario()
  -> Scenario in nuScenes global coordinates
  -> local road-aligned transform
  -> baseline artifact under artifact_root
```

### Variant and preview

```text
Scenario + constrained edits
  -> preview_variant() or generate_*_variants()
  -> validate_feasibility()
  -> gates / ranking / report
  -> private generated artifact
```

### Replay

```text
Scenario
  -> OpenSCENARIO + OpenDRIVE template
  -> esmini subprocess
  -> normalized replay trace
  -> replay metrics and simulator evidence
```

### Workspace evidence

```text
scenario id
  -> ArtifactAdapter
  -> workspace service
  -> typed availability/provenance contract
  -> React view
```

The frontend must not infer domain truth from missing fields. The backend owns
availability, unavailable reasons, provenance and scientific status.

## Source Of Truth

- Current status, decisions and acceptance state: [`../current/README.md`](../current/README.md)
- Layer responsibilities and dependency rules: [`boundary-map.md`](boundary-map.md)
- Stable API/artifact/provenance rules: [`../contracts/README.md`](../contracts/README.md)
- Subsystem implementation reference: [`../subsystems/README.md`](../subsystems/README.md)
- Runtime and deployment procedures: [`../operations/README.md`](../operations/README.md)

Reports and evidence explain completed work or observed runs. They do not
override current decisions or contracts.

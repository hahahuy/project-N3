# Data Adapters

Adapters isolate external data and simulator semantics from the canonical
scenario model and web contracts.

| Adapter | Code | Output boundary |
|---|---|---|
| nuScenes ingestion | `real2scenario/ingestion.py`, `nuscenes_backend.py` | `Scenario` plus source provenance |
| Metadata cache | `real2scenario/metadata_index.py` | scene-scoped tables with cache status |
| nuScenes devkit | `r2s_web/nuscenes_adapter.py` | LiDAR, boxes, map, transforms and CAN evidence |
| Native map | `r2s_web/native_map.py` | read-only normalized map records |
| esmini subprocess | `real2scenario/simulation.py`, `r2s_web/esmini.py` | normalized replay trace and private artifacts |
| esmini native binding | `r2s_web/live_session.py` | bounded state/control session contract |

## Adapter Rules

1. Lazy-load optional dependencies and report unavailable reasons explicitly.
2. Keep raw vendor objects inside the adapter.
3. Preserve source timestamps, tokens, coordinate frames and tool versions.
4. Never expose raw private dataset paths through a public contract.
5. Distinguish recorded evidence, generated output and simulator state.

Detailed dataset and simulator contracts remain in
[`../../current/technical-contracts.md`](../../current/technical-contracts.md).

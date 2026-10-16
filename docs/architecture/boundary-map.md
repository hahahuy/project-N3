# Boundary Map

## Layer Responsibilities

| Layer | Owns | Must not do |
|---|---|---|
| Frontend | Presentation, interaction state, request lifecycle and view composition | Invent domain truth, silently replace unavailable data, or call filesystem paths directly |
| `r2s_web` | Routes, orchestration, availability blocks, API errors and web-specific adapters | Redefine canonical physics or hide external-data failures |
| `real2scenario` | Canonical models, ingestion, generation, validation, gates, replay normalization and metrics | Depend on FastAPI, React or browser state |
| Dataset adapter | Translate nuScenes/source records into canonical data plus provenance | Leak raw vendor objects into public contracts |
| Simulator adapter | Invoke esmini/native bindings and normalize state/traces | Describe browser transforms as simulator images or silently fall back to another simulator |
| Artifact boundary | Validate, read and write canonical/private artifacts | Mutate a parent scenario implicitly or bypass path confinement |

## Dependency Direction

```text
frontend -> r2s_web -> real2scenario
                         ^
                         |
             dataset/simulator adapters
```

`real2scenario` is the reusable domain layer. `r2s_web` may call it, but domain
modules should remain usable from tests and CLI tools without the web app.

## Data Ownership

| Data | Owner | Consumers |
|---|---|---|
| Canonical `Scenario` | `real2scenario.models` | generation, validation, export, web adapter |
| Artifact schema/provenance | `real2scenario.serialization` | filesystem adapter, reports, API |
| Availability and HTTP error shape | `r2s_web` | frontend and API clients |
| View layout and transient UI state | React | browser only |
| Scientific status and provisional labels | domain/report contracts | API and UI |

## Change Rules

1. Change canonical models or serialization only with impact analysis and
   artifact/test review.
2. Add a web capability as an explicit availability contract before wiring a
   frontend view.
3. Keep raw nuScenes data and private derived sensor artifacts outside git.
4. Preserve provenance whenever a boundary converts coordinates, metrics or
   simulator state.
5. Treat missing data as a named unavailable state, never as zero or an empty
   success response.

# Tracks 1-6 Disposition

Status: `CURRENT / ENGINEERING INVENTORY / PROVISIONAL`
Date: `2026-10-15`

This report records what the current checkout can prove without inventing native
runtime, sensor, metric or paper evidence.

| Track | Status | Evidence | Exact boundary or blocker |
|---|---|---|---|
| 1. Native esminiLib runtime proof | `HOST-AND-COMPOSE-SMOKE-VERIFIED` | `src/r2s_web/live_session.py`, `src/r2s_web/app.py`, `tests/test_live_session.py`, `tests/test_web_api.py`; `compose.dev.yml`; Compose API smoke | Upstream v3.10.0 was cloned outside the repository; host v3.9/v3.10 and the Compose-mounted runtime load/step successfully. The Compose proof returned four named objects at `t=0.05s`. Reset is implemented by reloading the same confined pair; native control remains explicitly unavailable because no stable public control ABI is present. |
| 2. Browser live 3D | `IMPLEMENTED/NATIVE-API-VERIFIED/PROVISIONAL` | `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/api.test.ts`, `frontend/src/workspace.test.tsx`, `src/r2s_web/app.py`, `tests/test_web_api.py`, Compose live API smoke | Browser-native state renderer and timeline-bound POV integration exist, the API returns actual native object state, and `/api/esmini/live/scenario-pairs` safely creates a private XOSC/XODR pair for a selected artifact. The UI creates and polls that session when capability is available; unavailable capability leaves the action disabled. Browser camera state is separate from the native viewer. Screenshot streaming is not used. |
| 3. Post-edit sensors | `UNSUPPORTED` | `src/r2s_web/sensor_status.py`, `tests/test_web_api.py` | No calibrated post-edit camera/LiDAR/radar generator or artifact manifest exists. Variant status remains `unsupported`; recorded parent-sweep fallback remains separate. |
| 4. Private runtime acceptance | `PARTIAL/PROVISIONAL` | `docs/reports/workspace-live-acceptance.md`, `tests/test_web_api.py`, `tests/test_simulation.py`, Compose smoke, host esmini mount | Private map/state/LiDAR and Compose native state acceptance are available. Image capture reaches esmini but fails closed as `capture_viewer_unavailable` because the container has no usable X11/display context; no capture manifest was generated. Variant post-edit camera/LiDAR/radar frames remain explicitly unsupported. |
| 5. CP1/CP3/CP4/CP5 engineering closure | `PARTIAL/PENDING-OWNER` | `docs/current/active-work.md`, CP1/CP3/CP4/CP5 reports, local release-evidence artifact | CP1 `20/143 = 13.99%` remains immutable and provisional. Scientific policies, benchmark approval and owner sign-off remain open. Working-tree release verification passes; committed HEAD proof requires the verified tree to be committed. |
| 6. CP6 paper evidence | `OPEN/OWNER-REQUIRED` | `docs/archive/plan-a-migration-checklist.md`, current evidence index | Research questions and final paper evidence are not approved. Existing engineering results remain provisional and are not promoted to final claims. |

CARLA same-XOSC remains post-MVP and is not part of this disposition.

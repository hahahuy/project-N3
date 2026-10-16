---
report_type: ui_object_frame_audit
status: COMPLETE
date: 2026-10-13
---

# UI Object Manipulation and Frame Generation Audit — 2026-10-13

## Finding

Object manipulation is implemented through the U0 parameterized preview flow.
The backend creates a deterministic child `Scenario` and regenerates the
edited actor's time-indexed `State` trajectory. The parent remains immutable.

The system does **not** currently generate frames after manipulation in the
sensor/rendering sense. There is no post-edit camera, LiDAR, radar or simulator
image generation, no frame artifact collection, and no timestamp-addressable
frame retrieval endpoint.

## Implemented Path

```text
UI speed/heading/gap/timing edit
  -> POST /api/scenarios/{id}/variants/preview
  -> ActorMotionEdit
  -> preview_variant()
  -> edited State trajectory per actor
  -> private previews/<variant>/scenario.json
  -> PreviewResponse.paths
  -> SVG recorded/generated trajectory overlay
```

The generated states preserve timestamps, position, yaw, speed and source
provenance fields. The UI timeline currently changes the displayed timestamp
label and does not replace the full-path SVG with a selected frame.

## Evidence

- `src/real2scenario/generation.py`: `_preview_actor()` creates new states.
- `src/r2s_web/jobs.py`: `PreviewService.preview()` persists the child scenario
  and returns generated paths.
- `src/r2s_web/adapter.py`: `trajectory_for_scenario()` serializes states into
  API paths.
- `frontend/src/App.tsx`: `TrajectoryPlot` renders polylines; the timeline
  updates `timelineTime` only.
- `tests/test_models.py`: deterministic, immutable edited trajectory contract.
- `tests/test_web_api.py`: deterministic preview and generated-path contract.
- `docs/evidence/m4-ui/u0-motion-editor-showcase.md`: browser overlay evidence.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_models.py tests/test_generation.py tests/test_web_api.py
47 passed, 1 warning
```

The warning is the existing Starlette/httpx deprecation warning.

## Required Follow-Up

Post-edit frame generation is an open `POST-U0` work item. It requires an
explicit contract for timestamp sampling, camera/sensor calibration or
simulator rendering, frame provenance, private artifact storage and a frame
retrieval API. It must not be inferred from the existing trajectory overlay.

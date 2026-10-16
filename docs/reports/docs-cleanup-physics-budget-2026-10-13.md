---
report_type: documentation_cleanup
status: COMPLETE
date: 2026-10-13
---

# Documentation Cleanup and Physics Budget Report — 2026-10-13

> **HISTORICAL SNAPSHOT — DO NOT USE FOR CURRENT ASSIGNMENT.** Its original
> CP1-first sequencing is superseded by the nuScenes-devkit makeover handoff:
> `docs/current/nuscenes-devkit-makeover-handoff.md`.

## Scope

Formalized the MVP physics budget and reconciled current documentation with the
latest CP2-A, CP3, CP4, CP5 and U0 implementation evidence. No application code,
dataset, simulator binary or restricted artifact was changed.

## Decisions Added

- Added `DEC-014 — MVP Physics Budget and Runtime Separation`.
- Defined Tier 0 esmini open-loop replay as the ADE/FDE measurement path.
- Defined Tier 1 `kinematic-open-loop-v1` as the lightweight MVP preview and
  feasibility runtime.
- Deferred controller/dynamics experiments to a separate diagnostic-only Tier 2.
- Explicitly excluded rigid-body, tire, suspension, powertrain and aerodynamic
  claims from the current MVP.

## Current-Context Cleanup

- Added the Tier 1 simulator contract and acceptance requirements to
  `docs/current/technical-contracts.md`.
- Added the Tier 1 simulator to `docs/current/active-work.md`.
- Updated `project-status.md`, `pm-agent-guide.md`, `next-agent-handoff.md` and
  `evidence-index.md` with current CP2-A/CP3/CP4/CP5 status and next work.
- Marked obsolete Wave 3A blocked-agent assignments as historical.
- Marked the Wave 3A backend page as completion context rather than the next
  execution section.
- Preserved historical reports and did not delete audit history.

## Current Next Tasks

1. CP1 owner interpretation and cross-scene semantic confirmation.
2. CP3 owner-approved benchmark index and final benchmark protocol.
3. CP5 owner sign-off and verified-tree release evidence.
4. Implement Tier 1 `kinematic-open-loop-v1` with normalized traces,
   diagnostics, collision pre-checks and esmini comparison.
5. Complete the full 2D/3D authoring workspace and frame-aware timeline.
6. Add approved post-edit frame/LiDAR evidence support.
7. Complete CP6 paper evidence.

CARLA same-XOSC remains separate post-MVP work.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
docs consistency: PASS
```

The full suite was rerun after the documentation updates:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
259 passed, 1 warning
```

The warning is the existing Starlette/httpx deprecation warning.

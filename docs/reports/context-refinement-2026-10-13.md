---
report_type: context_refinement
status: COMPLETE
date: 2026-10-13
---

# Context Refinement Report — 2026-10-13

> **HISTORICAL SNAPSHOT — DO NOT USE FOR CURRENT ASSIGNMENT.** Its original
> CP1 next-agent recommendation is superseded by the nuScenes-devkit makeover
> handoff: `docs/current/nuscenes-devkit-makeover-handoff.md`.

## Scope

Audited and reconciled the repository documentation according to
`docs/current/next-agent-handoff.md`. This was a documentation-management task;
no feature implementation, dataset adapter, map geometry, simulator runtime or
scientific threshold was changed.

## Docs Audited

- `MVP&ProjectSummary.md`
- `README.md` and `docs/README.md`
- `docs/current/project-status.md`
- `docs/current/active-work.md`
- `docs/current/decisions.md`
- `docs/current/technical-contracts.md`
- `docs/current/evidence-index.md`
- `docs/current/artifact-policy.md`
- `docs/current/ui-motion-editor.md`
- `docs/current/ui-showcase-checkpoint.md`
- `docs/current/platform-direction.md`
- `docs/current/late-future-platform-plan.md`
- `docs/plan-a-migration-checklist.md`
- current reports referenced by the status and evidence indexes
- archived Plan B directory banners and link references

## Files Changed

- Reconciled Plan A long-term simulator targets with DEC-011 current MVP
  acceptance in `docs/current/project-status.md` and `docs/current/decisions.md`.
- Updated the execution order to reflect completed Wave 3A/U0 work and the next
  owner/CP1 semantic-alignment follow-up.
- Removed the completed context-management row and duplicate U0 row from
  `docs/current/active-work.md`; clarified the remaining CP3 benchmark work.
- Marked the pre-repair full-map topology report and superseded corridor
  implementation report as historical while retaining both for audit history.
- Updated `docs/current/evidence-index.md` so superseded topology and corridor
  implementation reports cannot be read as current acceptance evidence.
- Fixed the moved architecture link in `docs/guides/technology-guide.md` and
  updated stale onboarding links and role guidance in `README.md`.
- Marked completed migration-checklist documentation tasks and corrected the
  moved CP1 report path in `docs/plan-a-migration-checklist.md`.
- Extended `scripts/check_docs_consistency.py` to validate relative Markdown
  links outside the archive while preserving the historical archive boundary.

## Current Status Changes

- Current MVP is explicitly esmini plus the internal lightweight kinematic
  preview; CARLA remains a post-MVP backend and long-term project target.
- CP1 remains `PARTIAL/CORRIDOR-EXTERNAL-VERIFIED`; the 40 m scene-0061
  corridor is structurally/runtime verified, while semantic road-match remains
  diagnostic and provisional.
- CP2 remains pure/fake-runtime planning only; no live CARLA or same-XOSC claim
  was added.
- U0 remains `SHOWCASE-READY` and is not CP1, CP2, CARLA or sensor completion.
- Full Singapore One-North coverage, OSM activation, alternate datasets and
  final scientific thresholds remain deferred or open.

## Links and Historical Records

- The current documentation link checker passes after the architecture path
  repair.
- Historical Plan B links are intentionally retained in archive documents and
  are covered by the archive banner rule rather than rewritten as current links.
- No historical report was deleted.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
docs consistency: PASS

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
201 passed, 1 warning
```

The warning is the existing Starlette/httpx deprecation warning. The cache
provider was disabled because the default pytest cache path is not writable in
this worktree.

## Remaining Unverified Claims

- Formal CP0 CARLA sample evidence remains incomplete.
- CP1 scientific acceptance, lane-level road-match acceptance, full topology
  semantics and CARLA map compatibility remain unverified.
- CP2 live CARLA execution, custom XODR import and paired same-XOSC traces remain
  unverified.
- Final ADE/FDE and G6/G7 scientific thresholds remain provisional/open.
- CP4 full G1-G7 orchestration, CP5 clean-checkout/release evidence and CP6
  paper evidence remain incomplete.
- Raw nuScenes and nuScenes-derived artifacts remain local/private and are not
  represented by repository runtime evidence.

## Next Implementation Agent

The next implementation agent should work on the owner-approved CP1
semantic-alignment follow-up described in
`docs/current/cp1-agent-handoff-next.md`. It must preserve the immutable
`20/143 = 13.99%` baseline, avoid silent direction/tolerance/actor-scope
changes, and keep CARLA and same-XOSC work on the separate post-MVP CP2 track.

## Files Not Touched

Application source, frontend source, tests, generated artifacts, private dataset
content and simulator binaries were not changed by this context-management
wave.

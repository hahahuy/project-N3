# CP1 Corridor Manual Review Template

Status: `TEMPLATE`
Purpose: blank review sheet for a scene-local CP1 corridor manual review.

Extracted from the CP1 manual review bundle on the operator host. The template
carries no private data — every field is empty. See
`docs/current/local-artifact-bundles.md` for the bundle inventory and for why
the bundle's sibling instruction file is not committed here.

## How to use

The bundle's instruction file sequences this work:

1. Open the bundle run card and fill in the reviewer name.
2. Verify scene identity.
3. Review every candidate in the actor inventory.
4. Freeze the selected actors.
5. Create private overlays for actors, centerlines, polygons, state indexes and
   frame axes.
6. Add one row per state to the state review sheet.
7. Fill the dimension review and keep ego unsupported unless an approved
   envelope exists.
8. Complete this summary before creating any exploratory actor run.

Overlays and review sheets are derived artifacts and stay local/private. Only
this summary's aggregate outcome may be committed, and only after scrubbing.

## Rules

- Do not delete failures.
- Do not guess dimensions.
- Do not reverse lanes only for failing actors.
- Do not replace the baseline with a favorable selection.
- The frozen baseline is 40 m corridor, line mode, 5 m resolution, 0.5 m
  distance, 0.2 rad heading.

---

## Review record

Scene:
Baseline run:
Reviewer:
Date:

### Baseline
- Selected actors:
- States:
- Raw match rate:
- XODR hash:

### Actor Decisions
| Actor | Decision | Evidence | Impact |
|---|---|---|---|

### State Failure Classes
| Class | Count | Notes |
|---|---:|---|

### Direction Review
- Reverse candidates:
- Evidence strength:
- Production policy changed: no

### Occupancy Review
- Occupied:
- Outside:
- Unsupported:
- Width source:
- Dimension source:

### Decision
- Baseline retained: yes
- CP1 corridor acceptance: not claimed
- Next technical action:

### Non-claims
- No G3 acceptance.
- No CARLA compatibility.
- No CP2/same-XOSC claim.
- No change to the immutable CP1 `20/143 = 13.99%` baseline.

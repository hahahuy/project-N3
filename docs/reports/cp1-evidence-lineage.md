# CP1 Evidence Lineage — Consolidated Record

Status: `CONSOLIDATED / HISTORICAL RECORD / PROVISIONAL`
Date: 2026-10-16
Purpose: one document replacing thirteen intermediate CP1 reports.

---

## 1. Why this file exists

CP1 accumulated a chain of ~26 reports between 2026-10-13 and 2026-10-15. Most
were later superseded by a better measurement, but each was cited somewhere, so
none could simply be deleted and the directory became hard to navigate.

This file condenses the **superseded intermediate chain** into a single
readable lineage. The reports that still carry live evidence are **retained
unchanged**; only the superseded intermediates were folded in here.

**Nothing was lost.** Where an intermediate number is scientifically interesting
it is preserved below, even though it is no longer current.

## 2. The CP1 lineage, oldest to newest

Each step lists the finding, what superseded it, and whether the number is still
meaningful.

| # | Report | Key finding | Superseded by |
|---|---|---|---|
| 1 | `cp1-map-builder-prototype` | Full-map line prototype emitted **2002 roads** and passed structural XODR validation. Continuity and lane road-match not yet computed. | scene-local corridor |
| 2 | `cp1-arc-fitting-foundation` | Pure deterministic line/arc geometry; curvature and max source-pose residual; synthetic tests for straights, known arcs and residuals. | builder integration |
| 3 | `cp1-line-arc-builder-integration` | `geometry_mode="line_arc"` emits constant-curvature OpenDRIVE arcs with a manifest carrying geometry mode, fitter version and residual, with explicit tolerance configuration. | `cp1-geometry-topology-follow-up` |
| 4 | `cp1-continuity-diagnostics` | Configurable position and heading tolerances; synthetic connectivity-join tests. Did **not** emit junctions. | corridor run |
| 5 | `cp1-continuity-junction-width` | Connector junction path and polygon-width path, with gap/heading/tolerance reporting. | `cp1-corridor-external-evidence` |
| 6 | `cp1-road-match-diagnostic` | Introduced the standalone `lane-road-match-v1` diagnostic and the explicit provisional 95% status vocabulary. Synthetic only. | external map run |
| 7 | `cp1-external-map-road-match-evidence` | First **external** nuScenes run on One-North + scene-0061: raw match rate **0.573664 (57.37%)**, provisional. | corridor run |
| 8 | `cp1-corridor-implementation` | Synthetic selection and closure for the scene-local corridor. | `cp1-corridor-external-evidence` |
| 9 | `cp1-final-map-load-topology-evidence` | Pre-repair full-map audit: **936 dangling junction references**, **15 dangling road links**. | `cp1-topology-repair-evidence` |
| 10 | `cp1-corridor-priority-handoff` | Declared the scene-local corridor as the active scope with a `40 m` first-run buffer. | the run it planned |
| 11 | `cp1-scene-0061-alignment-analysis` | Established exact global/local transform equivalence. F0 all-30-actors `57.37%`; F0/F1 interaction-selected 4 actors `20/143 = 13.99%`. | attribution + direction analyses |
| 12 | `cp1-occupancy-candidate-diagnostics` | Separate footprint and ranked-candidate baselines; fallback width and missing dimensions flagged as limitations. | `cp1-corridor-direction-footprint-analysis` |
| 13 | `cp1-cp2-contracts` | Pre-trainval historical XOSC subset contract snapshot. | current `technical-contracts.md` |

## 3. Numbers worth remembering but not quoting

These are real measurements that later work replaced. They are recorded so nobody
re-derives them or mistakes them for the current state.

- **`57.37%`** — raw road-match on the full One-North map for scene-0061 across
  all 30 vehicles. Superseded by the corridor-scope figure. Its significance is
  comparative: it shows the interaction-selected scope is *harder*, not that the
  corridor is worse.
- **`2002 roads`** — full-map line-prototype emission count. Useful as a scale
  reference only.
- **`936` dangling junction references / `15` dangling road links** — pre-repair
  topology defects. The repair reached **zero** of both, and the five corridors
  independently re-confirmed zero dangling references. Retaining the defect count
  documents what was actually fixed.
- **`13.99%` for all-30-actors vs selected-4** — identical, which is what proved
  the difference was actor scope rather than geometry.

## 4. What is retained, and why

Eleven reports are **retained unchanged** because they still carry live evidence:

| Report | Why it stays |
|---|---|
| `cp1-corridor-external-evidence` | Carries the immutable **20/143 = 13.99%** baseline |
| `cp1-corridor-attribution-analysis` | Disproves the corridor-crop hypothesis |
| `cp1-corridor-direction-footprint-analysis` | Separates the reverse-direction candidate from lateral-offset actors |
| `cp1-native-canonical-xodr-comparison` | Native == canonical; rules out conversion and OpenDRIVE export as the cause |
| `cp1-actor-reference-direction-diagnostics` | Reference/direction classification; rules out global actor-offset hypotheses |
| `cp1-private-sequence-self-verification` | 143-state lane-sequence classification |
| `cp1-geometry-topology-follow-up` | `centerline-repair-v1`, 12 repaired / 0 excluded, 80-link topology validation |
| `cp1-benchmark-scene-review` | Five corridors external-verified with polygon widths and arc residuals |
| `cp1-benchmark-gate-evidence` | 60 candidates measured; G3 evaluated rather than skipped; zero passes |
| `cp1-topology-repair-evidence` | Zero dangling references and zero unresolved-junction warnings in esmini |
| `cp1-corridor-review-template` | Blank owner review sheet; referenced by `artifact-policy.md` |

## 5. What the chain established, in one paragraph

Working forward from the chain: the map builder was built and structurally
validated at full-map scale; geometry was made continuous and junctions were
emitted; the first external run produced a real 57.37% match rate; topology
defects were found and repaired to zero; scope was narrowed to a scene-local
corridor, which produced 20/143 = 13.99%. Three later analyses then **excluded**
the obvious explanations: corridor cropping is not the cause (attribution),
map conversion is not the cause (native/canonical equivalence), and a global
actor-offset or lane-reversal policy is not the cause (reference/direction
diagnostics). The residual is a **lateral offset between the driven path and the
emitted corridor centerlines**, consistent with the low centreline match across
all five benchmark scenes. That residual remains unexplained and CP1 stays
`PARTIAL/PROVISIONAL`.

**The hypothesis that the map template was the primary cause is disproved** and
is recorded here so it is not reused. See also
`docs/reports/residual-replay-error-composition.md`.

## 6. Boundaries

- The immutable baseline is `20/143 = 13.99%`. This file does not change it.
- All figures here are `PROVISIONAL`.
- CARLA remains unverified and post-MVP.
- Raw nuScenes data and derived artifacts stay local/private.
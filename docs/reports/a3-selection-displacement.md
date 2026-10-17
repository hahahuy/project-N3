# A3 — Selection displacement from the pedestrian/cyclist emission widening

`scientific_status: PROVISIONAL`

Acceptance: WASM handoff `data-analysis-handoff-pedestrian-widening.md` §3 item A3.
Returns items 1 (A3 report) and 7 (deviations from §2) of §6.

## 0. Deviation from the requested scope, stated up front

The handoff asked for the **10-scene `v1.0-mini`** set. This machine has **no
`v1.0-mini` metadata tables** — `/mnt/backup/nuscenes/v1.0-mini/` contains only
`category.json`, `lidarseg.json` and `panoptic.json`, with no `scene.json`,
`sample.json`, `sample_annotation.json` or `instance.json`. The §2 ground facts
(476 vehicle + 227 human, 9/10 scenes with a pedestrian) therefore cannot be
reproduced or extended here.

I ran the analysis on **`v1.0-trainval`, all 850 scenes**, which is:

- the same set the `0.0411 m` replay baseline was measured on;
- 85x more scenes, so the displacement rate is far better resolved;
- the set the A2 pedestrian replay should use anyway.

Population: `vehicle.*` union `human.*` instance tokens per scene, exactly as
`SourceSceneAdapter.import_scene` does after the widening. The previous
behaviour is reproduced by restricting the candidate population to `vehicle.*`
before selection. Both paths use the identical `SelectionConfig`
(`max_actors=3`, `max_distance_m=30.0`, `max_ttc_s=5.0`) — no threshold was
changed for this measurement.

## 1. (i) How often a pedestrian displaces a vehicle

| quantity | value |
|---|---|
| scenes analysed | 850 |
| scenes where >=1 pedestrian is selected | **275 (32.35 %)** |
| scenes where >=1 vehicle is displaced | **271 (31.88 %)** |
| vehicles displaced | **420** |
| pedestrians added | **432** |
| scenes where the selected set shrank | **0** |

Every displaced vehicle was replaced. No scene lost a slot.

### Rank of the displaced vehicle within the *old* selection

| old rank | count | share |
|---|---|---|
| **1 (top-ranked)** | **271** | **64.52 %** |
| 2 | 117 | 27.86 % |
| 3 | 32 | 7.62 % |

So displacement does land disproportionately on the highest-ranked vehicle —
64.5 % of displaced vehicles were rank 1. That is the risk A3 asked me to test.

### But the ranking is not at fault

In the **35 scenes where the selected set ends up with zero vehicles**, I checked
whether the best qualifying vehicle had a *better* (lower) TTC than the
pedestrians that took the slots:

| check | result |
|---|---|
| vehicle genuinely out-ranked (correct behaviour) | **35** |
| vehicle had better TTC but still lost (**anomaly**) | **0** |
| no qualifying vehicle in the scene | **0** |

In every one of those scenes all three selected pedestrians had a strictly lower
TTC than the best qualifying vehicle. Examples:

| scene | best qualifying vehicle TTC / dist | selected pedestrian TTCs |
|---|---|---|
| scene-0047 | 0.961 s / 5.59 m | 0.422, 0.483, 0.515 |
| scene-0006 | 0.847 s / 3.92 m | 0.586, 0.650, 0.758 |
| scene-1014 | 3.135 s / 11.37 m | 0.616, 0.704, 1.941 |
| scene-1091 | 1.498 s / 5.97 m | 0.862, 1.018, 1.196 |

**There is no selection defect.** The question A3 raised — "does displacement
systematically drop the highest-risk vehicle" — is answered: it drops the
top-ranked vehicle *often*, but only ever in favour of genuinely more imminent
actors **by the configured metric**. The trade-off is a policy question about
whether TTC is the right severity proxy across object classes, not a bug.

## 2. (ii) Distance and TTC distributions

Selected actors only, n = 420 displaced vehicles and 432 added pedestrians.

| population | n | min | median | mean | p90 | max |
|---|---|---|---|---|---|---|
| added pedestrians, min distance (m) | 432 | 0.947 | **4.608** | 6.035 | — | 34.412 |
| displaced vehicles, min distance (m) | 420 | 2.571 | **9.857** | 11.732 | — | 64.557 |
| added pedestrians, min TTC (s) | 432 | 0.422 | **1.346** | 3.473 | — | 188.260 |
| displaced vehicles, min TTC (s) | 408 | 0.529 | **2.645** | — | — | see below |

> **`n` differs between the two displaced-vehicle rows: 420 for min-distance,
> 408 for min-TTC.** The TTC statistic is undefined for a track pair with no
> closing event inside the horizon, so 12 of the 420 pairs drop out. This
> report does **not** independently verify that the 12 are genuinely
> non-closing rather than unmeasured; treat the TTC row as `n = 408` and do not
> compare it to the 420 row as if they were the same population.

The pedestrians that win a slot are roughly **twice as close** (4.61 m vs
9.86 m) and **roughly twice as imminent** (1.35 s vs 2.65 s median TTC) than the
vehicles they displace. This is the metric working, not the metric failing.

### Latent numerical issue found while reporting this

`displaced vehicles, min TTC` has `max = 6.96e+141`. Mechanism:
`selection._ttc()` returns `distance_m / closing_speed_mps` whenever
`closing_speed_mps > 0`, with **no lower bound** on `closing_speed`. Near
parallel motion with a hair of closing rate produces an unbounded quotient
(observed range up to 6.96e+141; 3 of 408 values exceed 1e6).

**Impact on this analysis: none.** An enormous TTC simply fails the
`max_ttc_s = 5.0` threshold, which is the same outcome as `inf`. Selection is
unaffected and no number above is wrong. It is a robustness concern only,
because TTC has no finite upper bound and any future TTC threshold or report
will inherit that. I did not change it — that is a threshold-semantics decision,
not a diagnostic one.

## 3. (iii) Import outcomes

| quantity | old (vehicle-only) | new (vehicle+pedestrian) |
|---|---|---|
| scenes where import succeeds (`>=2` actors) | **850 / 850** | **850 / 850** |
| scenes that now fail | — | **0** |
| scenes that newly succeed | — | **0** |

**Zero regressions and zero improvements.** Every trainval scene had at least
one qualifying vehicle before the widening, so the widening never rescued a
scene and never broke one. This also means the widening cannot change the
population of importable scenes on this dataset.

## 4. Proposal (proposal only — no implementation, per A3)

A3 asks for a quota or weighting *if* displacement systematically drops the
highest-risk vehicle. It does drop rank 1 in 64.5 % of displacements, so the
proposal is warranted. Measured counterfactual for the minimal version —
**reserve one vehicle slot, pedestrians capped at `max_actors - 1`**:

| quantity | current | with vehicle-slot reservation | delta |
|---|---|---|---|
| scenes changed | — | **35 (4.12 %)** | — |
| scenes with >=1 vehicle | 815 (95.88 %) | **850 (100 %)** | +35 |
| pedestrian slots filled | 432 | 397 | **−35 (−8.1 %)** |
| scenes with >=1 pedestrian | 275 (32.35 %) | 275 (32.35 %) | 0 |

The quota is cheap and bounded: it changes 4.12 % of scenes and costs 8.1 % of
pedestrian slots, while restoring vehicle coverage to 100 %.

### But I recommend **not** applying it without a product decision

The quota would override the metric in exactly the 35 scenes where the metric
states the pedestrians are more imminent. Whether that override is correct
depends on something data cannot answer:

- If the product intent is **"most imminent interaction partner regardless of
  class"**, the current behaviour is right and a quota is a regression of intent.
- If the intent is **vehicle-interaction scenario generation** — which is what
  CP1/CP3/CP4 and the whole replay-fidelity line are about — then losing every
  vehicle in 4.12 % of scenes is a real capability loss, and the quota is
  justified.

The widening was owner-approved on 2026-10-16, which is evidence the owner
already wants pedestrians to compete. This analysis does not overturn that; it
quantifies the cost so the owner can confirm the magnitude is acceptable.

### Acceptance bar if the quota is adopted

1. Over the same 850-scene token-ascending index: scenes with >=1 selected
   vehicle = **850/850**, and scenes with >=1 selected pedestrian **>= 250**
   (so the quota must not silently defeat the widening).
2. Selected actor count per scene must never exceed `max_actors = 3`.
3. Zero import regressions, and at least one scene must not newly fail.
4. Determinism: identical index and seed produce identical selections.
5. A `selection_version` bump, because `interaction-selection-v1` semantics
   would change and previously recorded selection provenance becomes
   non-comparable.
6. Re-run the replay baseline afterwards, since selection changes which actors
   enter the exported scenario.

I have not implemented any of this and am not proposing a threshold change.

## 5. What this does not establish

- It says nothing about pedestrian **replay** fidelity. That is A2, and it is
  still unmeasured: native esmini 3.9.0 is available here, but the pedestrian
  sample under `max_actors=3` is small per scene, so A2 needs the wide index
  and per-category reporting with explicit n.
- It says nothing about `MiscObject` selection: `MiscObject` actors are
  unreachable by automatic selection today (selection is `vehicle.*` plus
  `human.*` only), so they are absent from every number above.
- Displacement is computed against the *previous vehicle-only ranking*, not
  against a ground-truth notion of "the right actors". There is no such ground
  truth in this project, and inventing one would be an invented fact.

## Reproduction

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  ~/r2s-diagnostic/scripts/a3_selection.py \
  --index ~/r2s-diagnostic/index/index-full-850.json \
  --out ~/r2s-diagnostic/out/a3_selection.csv
```

No esmini, no dataset writes, deterministic. ~110 s for 850 scenes.
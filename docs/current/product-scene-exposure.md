# Product Scene Exposure Assessment

Status: `CURRENT / RECOMMENDATION`
Date: 2026-10-15
Question: should the contest product environment expose all 850 nuScenes
scenes to judges, and can they browse or filter them today?

Related: `docs/current/environment-environments.md`,
`docs/current/demo-hardening-backlog.md`.

---

## 1. Answer in one line

**Judges cannot reach the other 843 scenes from the browser at all**, because the
scene browser is not wired into the UI. The question is therefore not "850 or a
few" — it is "none, until that UI is built". Recommendation below concerns what
to build, if anything.

## 2. What is actually exposed today

`GET /api/source-scenes` returns all 850 scenes. Verified through the public
gateway with the contest key:

```
/api/source-scenes -> 200, 850 scenes, ~4.2 s warm
```

But the frontend never calls it:

```bash
git grep "fetchSourceScenes|importSourceScene" -- frontend/src/App.tsx
  -> no matches
```

`fetchSourceScenes` and `importSourceScene` are declared in
`frontend/src/api.ts:120-121` and have never been called. The catalog panel calls
only `fetchScenarios()` (`App.tsx:257`), which returns **already-imported
artifacts**.

So the product environment currently shows judges exactly the 7 seeded curated
scenarios. The 850 exist only as an API surface reachable by a judge who opens
devtools and types a URL.

## 3. What filtering is possible

Not much, and less than the dataset actually supports.

### The API response lacks the fields you would filter on

`SourceScene` (`frontend/src/api.ts:307`) carries:

```ts
{ scene_token, name, description, sample_count,
  first_sample_token, last_sample_token, vehicle_candidate_count }
```

There is **no `location` field**. The nuScenes source data does have it, but only
indirectly — `scene.json` stores `log_token`, and the map name lives on the
referenced record in `log.json`. Measured across the local `v1.0-trainval`
release:

| Location | Scenes |
|---|---:|
| `boston-seaport` | 467 |
| `singapore-onenorth` | 183 |
| `singapore-queenstown` | 115 |
| `singapore-hollandvillage` | 85 |
| **Total** | **850** |

`SourceSceneAdapter._source_scene` (`src/r2s_web/source_scenes.py:164-174`)
never resolves `log_token` to `location`, so the API cannot answer "show me
Boston" or "show me One-North".

### Sample counts are nearly uniform

`nbr_samples` ranges only 32–41 across all 850 scenes. Filtering by scene length
would not narrow anything.

### What is genuinely usable for filtering

- `description` — free-text, e.g. *"Parked truck, construction, intersection,
  turn left, following a van"*. Genuinely descriptive and useful.
- `vehicle_candidate_count` — a weak proxy for how interesting a scene is.
- `name` — `scene-0061` style identifiers only.

## 4. Filtering capability today: none

There is no `/api/source-scenes?limit=&offset=&q=` — that is item **D-3/S-5** in
`docs/current/demo-hardening-backlog.md`, still open. The endpoint returns all
850 in one payload on every call.

So even if the UI were wired, judges would receive an unfiltered 850-row list
with no search box, no paging and no map filter.

## 5. Recommendation

**Do not expose all 850 for the contest. Keep the curated catalog.**

Reasons specific to a contest demo:

1. **A curated set tells a story.** The 7 seeded scenes are Singapore One-North
   scenes already used in the project's CP3 benchmark work
   (`docs/current/project-status.md`, five-scene provisional index). A judge who
   opens one and sees a gate lane, provenance and metrics understands the
   project in 30 seconds. A list of 850 identical-looking rows communicates
   nothing.
2. **Uncurated scenes are a liability.** Import runs
   `extract_scenario` + `select_interaction_actors` + a local road-aligned
   transform per scene, and **raises** if fewer than two actors match the
   distance/TTC thresholds (`source_scenes.py:107-110`). Some of the 850 will
   fail. A judge hitting an error on their first click is a bad demo.
3. **It is not free.** Even with paging, import is real compute per scene, on a
   host shared with `banking-agent` and `kavita`, with **no concurrency cap**
   (S-6, still open).
4. **Import writes artifacts.** `import_scene` writes to
   `artifact_root/nuscenes/`, i.e. the product scenarios volume. A judge sweeping
   850 scenes fills that volume and slows every later request.

### If you want a scene browser anyway

Minimum viable, in order:

| Step | Work | Why |
|---|---|---|
| 1 | Add `location` to `SourceScene` by resolving `log_token` against `log.json` | Enables "show me Boston"; one join in `_source_scene` |
| 2 | Implement **D-3/S-5**: `?limit=&offset=&q=&location=` | 4.2 s per call is the real blocker, not the row count |
| 3 | Wire `fetchSourceScenes` into the catalog as a second tab | Makes the capability reachable at all |
| 4 | Implement **S-6** before enabling import for anonymous judges | Otherwise import is an unbounded compute endpoint |
| 5 | Cap the visible list to a page, and label the result `850 total` | Keeps the promise honest |

Steps 1–3 are a contained change. Step 4 is the security precondition for
letting strangers run imports.

### A middle path worth considering

Expose the **catalog** (read-only browsing and search over all 850) but restrict
**import** to the curated set, or to a per-judge quota. Browsing is cheap and
impressive; importing is expensive and mutating. This gives judges the sense of
scale without the failure modes.

## 6. Answering the question as asked

> can they scout, filter out which map era to check with our current deployment

**Scout**: only by typing `/api/source-scenes` by hand in a browser with the
contest key. No UI.

**Filter by map**: not possible. The `location` field is absent from the API
response, and the UI has no filter of any kind.

**Should it be limited for the demo**: yes. The curated 7 is the right scope, and
it is what is already deployed. Adding a browser is a real improvement but should
be scheduled, not rushed before a contest.

## 7. Unverified

- Import failure rate across all 850 scenes was not measured. The claim in
  section 5.2 is inferred from the code path raising `ValueError` when fewer than
  two actors match, not from a sweep.
- No end-to-end browser test of the catalog was performed.
- `source-scenes` was timed warm only (4.2 s). Cold it is ~56 s, which is why
  D-3 matters if this is ever wired up.

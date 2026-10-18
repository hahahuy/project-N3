# Stale Code Audit — Project - N3

Date: 2026-10-15
Method: GitNexus graph (5,629 nodes / 10,872 edges / 493 flows, index refreshed) + text verification.

Legend: **[DEAD]** zero references outside its own definition.
**[TEST-ONLY]** no production caller, only tests.
**[UNUSED-UI]** no UI caller, but reachable/tested — product decision, not dead.

---

## TIER 1 — Confirmed dead code (safe to delete)

### Frontend: 12 orphaned exports in `frontend/src/api.ts`
Every one of these appears **only on its own definition line** — no UI file, no test file, no namespace import.

| Line | Export | Backing endpoint |
|---|---|---|
| 332 | `fetchWorkspaceDocument` | GET `/workspace/documents/{id}` |
| 342 | `createBatch` | POST `/batches` |
| 343 | `fetchBatchResults` | GET `/batches/{id}/results` |
| 344 | `fetchBatchTrajectory` | GET `/batches/{id}/results/{vid}/trajectory` |
| 345 | `exportBatchResult` | POST `/batches/{id}/results/{vid}/export` |
| 351 | `sendLiveCommand` | POST `/esmini/live/sessions/{id}/commands` |
| 352 | `createReplay` | POST `/replays` |
| 353 | `fetchReplay` | GET `/replays/{id}` |
| 354 | `updateSettings` | POST `/settings` |
| 355 | `fetchSourceScenes` | GET `/source-scenes` |
| 356 | `importSourceScene` | POST `/source-scenes/{token}/import` |
| 357 | `fetchCP1Review` | GET `/cp1/review` |

Note: `fetchSourceScenes`/`importSourceScene` became dead when the Import button was
disabled — the Catalog now sources scenarios from `fetchScenarios`.

### Python: 2 methods with no production caller
| Symbol | Location |
|---|---|
| `to_source_state` | `src/real2scenario/coordinates.py:58` |
| `by_name` | `src/real2scenario/xosc_subset.py:187` |

Each is referenced only from `tests/`. Neither is re-exported in
`src/real2scenario/__init__.py`.

### CSS: 1 unused rule
| Selector | Location |
|---|---|
| `.sr-only` | `frontend/src/styles.css:297` |

---

## TIER 2 — Backend endpoints with no UI caller (decision required)

### [UNUSED-UI] `road-ahead` — closest to dead, recommended removal
`GET /api/workspace/maps/{map_name}/road-ahead` → `app.py:494 native_map_road_ahead`
→ `native_map.py:36 road_ahead` → `real2scenario.native_sources.road_ahead_query`.

- **No UI caller**, and **no test at all** (`rg 'road.ahead' tests/` → 0 files).
- `gitnexus_impact road_ahead_query` → risk **LOW**, 2 impacted, both HTTP-boundary.
- It is the only chain in the repo with neither a client nor a test.

### [UNUSED-UI] `native map patch`
`GET /api/workspace/maps/{map_name}/patch`. The UI only calls
`fetchNativeMapCapability`; no patch/road-ahead client helper exists at all.
Test-covered, so it is contract surface, not dead code.

### Not stale — keep
`GET /api/health` is the Docker HEALTHCHECK probe
(`compose.dev.yml:48`, `compose.demo.yml:74`, `Dockerfile:37`, `Makefile:42`).

---

## TIER 3 — Verified clean

- **0** orphan Functions / Methods / Classes / TypeAliases / Consts in `src/` + `frontend/src/`.
- **0** circular imports (`enumeration: complete`, 0 cycles).
- **0** unused icons (24/24 keys referenced).
- **117/118** CSS classes referenced.
- 41 backend routes; only the 8 above lack a UI caller.

---

## False positives ruled out (important)

15 Python functions appear "test-only" in the graph. **9 are NOT dead:**

- 2 are script entry points — `benchmark_aggregate_to_dict`, `aggregate_benchmark_runs`
  → `scripts/run_benchmark_scenes.py`.
- 6 are intentional public API re-exported in `src/real2scenario/__init__.py` `__all__`:
  `interpret_for_execution`, `execute_exact_pose`, `build_exact_pose_plan`,
  `map_blueprints`, `diagnose_lane_sequence_triage`, `check_footprint_collisions`.
- Documented contract surface: `with_paths`, `integrate_kinematic_open_loop`,
  `evaluate_prediction_advisory`, `batch_manifest_to_json`, `write_variant_report`.

**Why the graph missed them:** module-qualified calls (`mod.func()`) and script entry
points do not always produce a `CALLS` edge — the documented `causes.receiverTyping`
resolver gap. This is why every graph finding above was text-verified before marking.

Index caveats carried from the analyzer: 101 property read/write sites span two languages
and 234/434 entry points never ranked, so **an absent flow does not mean absent code**.

---

## POST-AUDIT CORRECTION — superseded by the uncommitted working tree

This audit was taken at commit `a16ed55` (5,629 nodes). The working tree has
since changed, and two findings below are **no longer accurate**:

| Audit finding | Current working-tree state |
|---|---|
| `fetchSourceScenes` / `importSourceScene` are dead because the Import button was disabled | **Still dead, but the cause changed.** The Import tool is now explicitly `disabled: true` in the toolbar rather than removed, and the Catalog sources scenarios from `fetchScenarios`. The audit's "dead" conclusion holds; its stated reason is now incomplete. |
| `fetchCP1Review` is dead | Still dead. |
| No top-down image helper exists | **No longer true.** `topDownImageUrl` was added in `frontend/src/api.ts` and is called by `TopDownView`. |

The remaining Tier 1/Tier 2 findings (10 orphaned `api.ts` exports, 2 test-only
Python methods, `.sr-only`, `road-ahead`, native map patch) are **unaffected** by
the working-tree changes and still stand as written.

Note that this audit **preserves a documentation inconsistency by omission**: it
does not flag the newly added `/api/workspace/scenarios/{id}/top-down` backend
route as untested, which it is. The route has a frontend caller but no backend
test, so the "117/118 CSS, 0 orphan Functions" cleanliness figures in Tier 3 do
not imply test coverage of the new route.
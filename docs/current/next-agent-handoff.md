# Project - N3: Next Agent Handoff

**Project name: `Project - N3`** (repo `project-N3`, codename `Real2Scenario`).
Refer to the project by that name in all output.

Status: `READY FOR ACCEPTANCE / OWNER REVIEW`
Updated: 2026-10-16

## Read in order

1. `MVP&ProjectSummary.md` — long-term scope baseline
2. `docs/current/project-status.md` — checkpoint status and current claims
3. `docs/current/decisions.md` — append-only owner decisions
4. `docs/current/active-work.md` — work queue and acceptance groups
5. `docs/current/technical-contracts.md` — API and simulator contracts
6. `docs/current/evidence-index.md` — claim-to-evidence index
7. `docs/current/artifact-policy.md` — visibility and licensing boundaries
8. `docs/architecture/system-overview.md` and `boundary-map.md`

Consolidated history: `docs/reports/cp1-evidence-lineage.md` for CP1,
`docs/reports/residual-replay-error-composition.md` for the replay baseline.

## Three concurrent agents

The project runs three agents in parallel. **Read who owns what before touching
anything**, and do not silently change another agent's scope.

| Agent | Owns | Do not touch |
|---|---|---|
| **DataAnalysis** | Metrics and reliability of real2sim nuScenes → WASM/esmini player. Owns the replay baseline and residual analysis. | Do not change replay or export semantics while they are measuring. Changes invalidate their run. |
| **ProjectManager** | Context, docs, codebase hygiene, and issuing prompts when new open items appear. | — |
| **WASM-DATA** | Replacing the current view panel with the WASM/esmini player. Frontend and XOSC connector. | Do not reimplement their work. |

The tree is committed apart from **small in-flight WASM-DATA work** (see
`docs/current/active-work.md`). There is no pending uncommitted *baseline*
problem to solve — the `LIDAR_TOP` fix and its follow-ups are committed. Run
`git status --short` before assuming anything, and never commit another agent's
in-progress files.

## Current direction

```text
nuScenes v1.0-trainval
  -> devkit-backed source adapter
  -> canonical scenario and provenance
  -> native map / OpenDRIVE / OpenSCENARIO contracts
  -> native esmini replay (sole sanctioned metric source)
      + browser WASM player (preview/interaction only)
  -> metrics, gates, private sensor evidence, UI
```

The backend makeover is **complete** for the approved contracts. The active
track is **acceptance and closure**, not implementation.

## Current verified baseline

Full nuScenes `v1.0-trainval` **850-scene** set, **3215 actor tracks**, esmini
v3.9.0, at `b52d423`/`79a4a8a`/`3372ff0`:

| Metric | Value |
|---|---|
| ADE mean | `0.0411 m` |
| ADE median | `0.0348 m` |
| ADE p95 | `0.1035 m` |
| ADE max | `0.1726 m` |
| FDE max | `0.2052 m` |

Validity unchanged at **808/850** — no validity was traded for a better number.
Runtime cost **+14 %**.

**Read that with its metric role attached.** Measured on the identity grid, so
position ADE/FDE and heading are role A, a genuine recorded-versus-replayed
measurement: esmini reproduces the trajectory it was given. `speed_mae_mps` is
role B there. It establishes **neither map accuracy** (CP1 remains
`20/143 = 13.99 %`, G3 never evaluated) **nor threshold admissibility**.

**Every ADE/FDE figure before `b52d423` is invalid and must not be quoted.**

All figures are `PROVISIONAL`. **No threshold is proposed** — the aggregate is
still a pooled actor-track micro aggregate and scene-macro is missing.

## Remaining work: seven acceptance groups

Owners, evidence and exact next actions are in
`docs/reports/tracks-1-6-disposition.md`.

1. Private runtime/browser acceptance — `PROVISIONAL`
2. Native esmini control boundary — `OWNER-REQUIRED`
3. Image capture/display — `PROVISIONAL`
4. Post-edit sensor generation — `DEFERRED`
5. CP1/CP3/CP4/CP5 closure — `OWNER-REQUIRED`
6. CP6 paper/evidence closure — `OWNER-REQUIRED`
7. UI scope decision — `OWNER-REQUIRED`

## Non-negotiable boundaries

- Preserve canonical schemas and provenance contracts.
- Preserve CP1 `20/143 = 13.99 %`.
- Top-down stays the authoring/map/trajectory view.
- Sensor Evidence is recorded nuScenes evidence only, never post-edit output.
- Recorded data must not be described as regenerated sensor output.
- Raw nuScenes data and derived artifacts stay outside the repository.
- Keep prediction metrics separate from replay fidelity metrics.
- Keep provisional metrics and diagnostic gates explicitly provisional.
- Browser WASM is preview/interaction only; it never feeds ADE/FDE,
  `replay.csv`, gates or reports. Native esmini is the sole sanctioned metric
  source.
- No map-accuracy claim while G3 is unevaluated. No safety/TTC claim while G6
  fails for implementation reasons.
- CARLA same-XOSC remains post-MVP.
- No new architecture or dependency without an approved decision.
- Never reinterpret an unavailable capability as successful behaviour.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
cd frontend && npm test -- --run && npm run build
```

**Passing tests is not acceptance.** Every figure above remains `PROVISIONAL`
until owner sign-off.

## What to do next

Do not start a new architecture track. Either execute an acceptance group from
`docs/reports/tracks-1-6-disposition.md`, or work inside your own agent scope.
State exactly which capability is implemented, fallback, unavailable or
unverified. Do not claim completion from tests without runtime evidence and
owner sign-off.
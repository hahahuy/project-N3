# Forward Plan — WASM Interaction and Tier 2 Dynamics

**Status:** PROPOSAL — combined plan for the two open tracks
**Authority:** DEC-017 in `docs/current/decisions.md`
**Inputs:** `docs/guides/wasm-live-simulator-handoff.md`,
`docs/guides/interactive-object-selection-analysis.md`,
`docs/guides/tier2-bicycle-dynamics-analysis.md`

---

## 1. Current state, as of this merge

Two tracks were open. Both are still open, but for different reasons, and the
repo is further along than when this was first drafted.

| | Status | Blocker |
|---|---|---|
| Browser 3D interaction | **deferred by architecture, not by design** | WASM deferral in the Live Esmini Adapter Contract |
| Behaviour executor | **stub, intentionally** | `reason="behavior executor is not implemented"` in `jobs.py`; DEC-016 requires it stay `unsupported` |
| Tier 1 kinematic | **`IMPLEMENTED/TESTED/DIAGNOSTIC`** | none |
| Tier 2 dynamics | not started | scope |

DEC-017 resolves the first row in favour of the WASM runtime. Rows two and three
are unchanged.

---

## 2. The tiers, and why they do not merge

| | Runtime | Job | May feed ADE/FDE? |
|---|---|---|---|
| Tier 0 | native esmini subprocess, `src/real2scenario/simulation.py` | measurement | **yes, the only one** |
| Tier 1 | `src/real2scenario/kinematic.py` | variant feasibility, gates, authoring preview | no |
| Tier 1b (WASM) | browser Worker, DEC-017 | interactive preview and authoring | no |
| Tier 2 | Python backend | dynamics plausibility, diagnostic | no — DEC-014 calls it diagnostic only |

The sentence to carry through implementation:

> Tier 0 measures. Tier 1 and Tier 1b explore. Tier 2 explains. None substitutes
> for another, and the Tier 0 path is never removed because a newer tier exists.

Tier 1b is not a replacement for Tier 1 either. They serve different hosts —
`kinematic.py` is server-side and gate-authoritative for feasibility; the WASM
runtime is client-side and exploratory. Tier 1's `unsupported` results must not
start coming from the browser, because the browser has no gate authority.

**The failure to avoid:** reaching for Tier 2 because a preview feels
unrealistic. That inverts the purpose. The browser preview is kinematic by
design and must stay fast, deterministic and falsifiable. If a user says the
preview is not realistic, the correct response is a label plus a Tier 2 run in
the backend.

---

## 3. Sequence

```
P0  WASM builds at all                    <- the only real fork
P1  deps + toolchain wiring
P2  3D view replaces the third-person presentation layer
P3  picking + injection                   <- Analysis B
P4  action log + boundary enforcement
    ---------------------------
    T2-1  parameters + provenance
    T2-2  ODE core + analytic test        <- Analysis A
    T2-3  diagnostics + maneuvers
    T2-4  inverse-dynamics plausibility   <- first useful output
    T2-5  reference cross-check
```

P0 through P4 are the browser track. T2 runs in the Python backend and shares no
code with it, so it can proceed in parallel or be deferred without blocking MVP.

**P0 is the only fork.** If the WASM build fails on the host, everything above it
is re-planned. Do not start P2 before P0 resolves, and do not start T2 before
P0 resolves either — if the browser track collapses, the priority argument for
T2 changes.

---

## 4. What the user can actually do, honestly

Each row must be reachable before the next is claimed.

| After | Can the user | Still cannot |
|---|---|---|
| P2 | see the road, actors and cameras as a real 3D scene; orbit, follow, scrub, step | change anything |
| P3 | click any actor, read its state, fire a one-shot speed / lane change / lane offset on it | change a parameter live; reproduce a run after scrubbing back |
| P4 | reproduce any earlier state exactly, including their own interventions | see dynamics; get vehicle-level fidelity |
| T2-4 | get a report on whether a recorded manoeuvre demands physically plausible control inputs | get a prediction of what a real vehicle would do |
| T2-5 | compare Tier 2 against a reference simulator | use Tier 2 in a fidelity claim |

Rows three and four are where overclaiming happens. Both are easy to oversell in
UI copy, and both are the claims DEC-014 and DEC-017 forbid.

---

## 5. Cross-cutting risks

| Risk | Affects | Mitigation |
|---|---|---|
| A browser number reaches an ADE/FDE table | P4, T2-4 | Architectural barrier, not a comment. Test asserting no import path from `frontend/src/sim/` to `metrics.py`, plus disjoint trace filenames and contract ids. |
| `float32` at the WASM boundary leaks into a metric | P4 | Same test. State precision differs between the two runtimes by design; the trace contract id is what disambiguates. |
| Two esmini versions drift | all | Pin one version for native and WASM, record both in `BUILD.md`. `project-status.md` currently references v3.9 and v3.10 in the same sentence. |
| Interaction work dropped by a merge | P1-P4 | Already happened once in this repository. DEC-017 exists to prevent a second occurrence. |
| Tier 2 scope creep into powertrain modelling | T2 | The stopping line is Analysis A §2.3. No torque curves. |
| UI copy implies fidelity the model lacks | P2, P3, T2 | Every preview surface states its tier. The artifact `map_warning` is the precedent. |
| Committed `.wasm` blocked at release | P1 | Allowlist entry in `verify_release.py` plus `BUILD.md` provenance. |

---

## 6. Documentation debt created by DEC-017

Settled in this change: `decisions.md` gains DEC-017; `technical-contracts.md`
Live Esmini Adapter Contract and `next-agent-handoff.md` are amended to withdraw
the WebAssembly prohibition for the interaction path only.

Still outstanding, and someone with authority should close them:

1. `docs/current/active-work.md` — no row tracks the WASM interaction runtime.
   Add one with the same status vocabulary the table already uses.
2. `docs/current/backend-workspace-contract-log.md` B-WORKSPACE-07 covers 3D
   scene data and is `Open`; it should reference DEC-017.
3. `docs/current/evidence-index.md` records the live session as
   `IMPLEMENTED/NATIVE-API-VERIFIED/PROVISIONAL`. A WASM runtime needs its own
   evidence row when P0 passes.
4. Unrelated but noticed while reading: six doc files reference
   `src/PROJECT_N3_WEB/` while the actual package is `src/r2s_web/`. There is a
   `docs/current/naming-migration.md`, so this is presumably deliberate
   in-flight work. Flagging only, not touching.

None of the four blocks P0.

---

## 7. Deliberately out of scope

- Closed-loop autonomy or an ADAS stack. Injection is an open-loop perturbation.
- Sensor simulation. U6 LiDAR stays a recorded-evidence display.
- Multi-actor negotiation. Two actors colliding is storyboard semantics; three
  actors negotiating is an autonomy problem.
- Any browser-side metric computation, in any tier.
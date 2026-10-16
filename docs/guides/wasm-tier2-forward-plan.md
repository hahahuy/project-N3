# Forward Plan — Tier 2 Dynamics and Interactive 3D Together

**Status:** PROPOSAL — long-range plan for the project
**Inputs:** `docs/guides/wasm-interactive-simulator-handoff.md`,
`docs/guides/tier2-bicycle-dynamics-analysis.md`,
`docs/guides/interactive-object-selection-analysis.md`
**Audience:** planning sessions, and any agent picking up either track.

---

## 1. The single most important structural fact

The three tiers in `docs/current/decisions.md` DEC-014 are not competing
alternatives. They are three different jobs, and the common failure in this
project would be to let a newer tier quietly absorb an older tier's job.

| | Lives where | Job | May feed ADE/FDE? |
|---|---|---|---|
| **Tier 0** | native esmini subprocess, `src/real2scenario/simulation.py` | measurement instrument | **yes, this is the only one** |
| **Tier 1 / WASM** | browser Worker | interactive preview and authoring | no |
| **Tier 2** | Python backend | dynamics plausibility, diagnostic | no — DEC-014 calls it "diagnostic only" |

The single sentence to carry through all implementation:

> Tier 0 measures. Tier 1 explores. Tier 2 explains. None of them substitutes
> for another, and the Tier 0 path must never be removed because a newer tier
> exists.

Tier 1 is currently unimplemented (`kinematic-open-loop-v1` exists only as
threshold names in `src/real2scenario/validation.py`). The WASM work fills that
empty slot. Tier 2 is later, separate, and deliberately does not run in the
browser.

---

## 2. Why these two tracks are related but must not be merged

Both are on the roadmap and both concern "what happens when behaviour changes",
which makes them look like one feature. They are not.

- **Interaction (B)** is a **UI capability** on top of an existing engine. It
  changes *what the user can do*. It adds no physics. It ships in the browser.
- **Tier 2 (A)** is a **new engine** with forces. It changes *what is true*. It
  runs in the backend. It is not interactive and is not a browser feature.

The tempting failure is to reach for Tier 2 when an interaction feels
unrealistic. That inverts the purpose: the browser preview is kinematic *by
design*, and users need it to be fast, deterministic and falsifiable. Adding
dynamics to the browser would make it slower, less reproducible, and would still
not be validated.

If a user complains that the preview is not realistic, the correct response is a
label — "kinematic preview, not a dynamics prediction" — plus a Tier 2 run in
the backend. Not a browser rewrite.

---

## 3. Combined sequence

```
                    P0  WASM builds at all
                     |
                    P1  repo hygiene, version pin
                     |
                    P2  3D view, playback only          --- browser track
                     |
                    P3  picking + inject actions        --- Analysis B
                     |
                    P4  action log, boundary enforcement
                     |
        --------------+--------------
        |                             |
   T2-1  parameter sets          MVP shipped
        + provenance
        |
   T2-2  ODE core + analytic test      --- Analysis A, backend track
        |
   T2-3  diagnostics + maneuvers
        |
   T2-4  inverse-dynamics plausibility  --- first useful output
        |
   T2-5  reference cross-check          --- needs environment
```

The two tracks share P0-P4 infrastructure and nothing else. T2 can proceed in
parallel once the repo is stable, or be deferred entirely without blocking MVP.

**Sequencing rule:** P0 is the only real fork in the road. If the WASM build
fails on the host, everything above it is re-planned. Do not start Tier 2 before
P0 resolves.

---

## 4. What the user can do at each stage

This is the acceptance view. Each row must be honestly reachable before the next.

| After | Can the user… | Still cannot… |
|---|---|---|
| P2 | watch a scenario in 3D, orbit, follow ego, scrub, step frame | change anything |
| P3 | click any actor, read its state, fire a one-shot speed / lane change / lane offset on that actor | change a scenario parameter live; reproduce a run after scrubbing back |
| P4 | reproduce any earlier state exactly, including their own interventions | see dynamics; get vehicle-level fidelity |
| T2-4 | get a report saying whether a recorded manoeuvre demands physically plausible control inputs | get a prediction of what a real vehicle would do |
| T2-5 | compare Tier 2 against a reference simulator | use Tier 2 in a fidelity claim |

Rows three and four are where honesty matters most. Both are easy to oversell in
UI copy, and both are the exact claims DEC-014 forbids.

---

## 5. Cross-cutting risks

| Risk | Affects | Mitigation |
|---|---|---|
| A browser number reaches an ADE/FDE table | P4, T2-4 | Architectural barrier, not a doc line. A test that asserts no import path from the Worker to `metrics.py`, plus trace files with disjoint names. |
| Parameter assumptions read as measurements | T2-4 | Sensitivity output is mandatory. Never report a single Tier 2 trajectory without the prior it assumed. |
| UI copy implies fidelity the model does not have | P2, P3, T2 | Every preview surface states its tier and its limitations. The existing `map_warning` is the precedent — follow it. |
| Two esmini versions drift apart | all | Single pinned version for native and WASM. Recorded in the build artifact provenance. |
| Scope creep from Tier 2 into powertrain modelling | T2 | The stopping line in Analysis A §2.3. No torque curves. |
| Frontend work dropped by a merge | P1-P4 | Already happened once in this repository. Record the work in the project logs. |

---

## 6. Documentation and governance debt to settle before P2 merges

Both analyses contradict written contracts. Someone with authority needs to
decide, not just note:

1. `docs/current/technical-contracts.md` line 274 requires Tier 1 acceptance to
   add "no new heavy runtime dependency". A WASM engine does not satisfy this as
   written. Either amend the contract to name the WASM engine as the Tier 1
   implementation, or record an explicit exception.
2. `docs/current/technical-contracts.md` line 283 lists Tier 2's obligations.
   Analysis A §5.4 proposes `dynamic-bicycle-open-loop-v1` as the trace contract
   id. That name needs approval before code is written.
3. `docs/current/active-work.md` still lists Tier 1 as `OPEN/MVP`. Adding WASM
   changes what that row means.
4. `docs/current/backend-workspace-contract-log.md` B-WORKSPACE-07 covers 3D
   scene data and is also `Open`.

The analyses in the two companion documents are written to be executable as-is.
The governance above is a decision, not a blocker on starting P0.

---

## 7. What is deliberately not planned here

- Closed-loop autonomy or an ADAS stack. Tier 1 is open-loop playback; injecting
  an action is an open-loop perturbation, not a control loop.
- Sensor simulation. U6 LiDAR stays a recorded-evidence display.
- Multi-vehicle interaction beyond what the storyboard already expresses.
  Two actors colliding is storyboard semantics; three actors negotiating is an
  autonomy problem and out of scope.
- Any browser-side metric computation, in any tier.
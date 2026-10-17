# A6 — Mass/dimension defaults audit: mass is inert under position following

`scientific_status: PROVISIONAL`

Acceptance: WASM handoff `data-analysis-handoff-pedestrian-widening.md` §3 item A6
(protocol delivered by the WASM team 2026-10-16), §6 item 5.

**Verdict: `MASS_INERT_UNDER_POSITION_FOLLOWING__ASSUMPTION_HOLDS`.**

## 0. Protocol as delivered

Decide by construction, not statistics: same binary, same XOSC, only `mass`
differs. If mass enters the computation anywhere the trace must change; if all
traces are byte-identical, mass provably steers nothing on this path. The
protocol also requires a **determinism gate** before any variant is interpreted,
and requires the test trajectory to contain acceleration so that a constant-speed
line cannot produce a false pass.

Executed exactly as specified, on native esmini **`v3.10.0-0-06065f9`**,
`--fixed_timestep 0.01`, headless.

## 1. Step 1 — track selection

| requirement | selected |
|---|---|
| one real pedestrian track | `instance-096b9cbe53d54aa1acf58f41aba19171` |
| taxonomy | `human.pedestrian.adult` |
| duration >= 10 s | **15.50 s** |
| vertices >= 10 | **32** |
| speed range >= 1 m/s (accel present) | **1.30 m/s** |
| one static misc object | `cone1`, `movable_object.trafficcone`, static, 20 states |

A **real** nuScenes pedestrian track was used, not the synthetic fallback: it
satisfies every criterion including a 1.30 m/s speed range, so acceleration and
deceleration are genuinely present. The ego is the real nuScenes ego track from
the same scene. Only the cone is synthetic, because `MiscObject` is unreachable
by automatic selection and must be authored explicitly.

The scenario is emitted through the repository exporter
(`select_opendrive_template` + `build_openscenario_xml`), so the test covers the
real exporter output, including the `Pedestrian mass="75"` and
`MiscObject mass="0"` defaults under audit.

## 2. Step 2 — determinism gate (not skipped)

| run | exit | completed |
|---|---|---|
| `base.xosc` run 1 | 0 | yes |
| `base.xosc` run 2 | 0 | yes |

**Traces byte-identical → gate PASSED.** Had they differed, the protocol requires
reporting run-to-run variance and issuing no verdict.

## 3. Step 3 — single-variable variants, with a self-check

A first attempt at the variant matrix had a defect: the `cone1` variant varied
the *pedestrian* mass and left `MiscObject mass` at `0`, so the misc object was
never actually tested. That was caught by diffing each generated variant against
base and is recorded here because it is exactly the failure mode this protocol
is designed to expose. The matrix was rebuilt so **each variant differs from
base by exactly one `mass` attribute**, verified by `diff`:

| variant | sole difference from `base.xosc` |
|---|---|
| `walk1_mass750` | `<Pedestrian … mass="75">` → `mass="750"` |
| `cone1_mass100` | `<MiscObject … mass="0">` → `mass="100"` |
| `cone1_mass1` | `<MiscObject … mass="0">` → `mass="1"` |

Nothing else differs in any variant — not indentation, not declaration, not any
other attribute.

## 4. Steps 4–5 — replay and decision

All four variants completed with **exit 0**.

| variant | trace identical to base |
|---|---|
| `base` (ped 75, misc 0) | reference |
| `walk1_mass750` (ped **750**, misc 0) | **yes, byte-identical** |
| `cone1_mass100` (ped 75, misc **100**) | **yes, byte-identical** |
| `cone1_mass1` (ped 75, misc **1**) | **yes, byte-identical** |

Per-actor metrics are consequently identical across every variant:

| actor | ADE | FDE | coverage | samples |
|---|---|---|---|---|
| `ego` | 0.023515 | 2.699e-02 | complete | 40 |
| `walk1` | 0.024773 | 6.153e-05 | complete | 32 |
| `cone1` | 0.000000 | 3.411e-13 | complete | 20 |

### Decision-table mapping

| protocol row | observation | verdict |
|---|---|---|
| traces byte-identical across masses (gate passed) | all 3 variants byte-identical | **Mass inert under position-following, native 3.10, tested classes — assumption HOLDS** |
| diff non-empty | not observed | not applicable |
| engine crash on `mass=0` (misc) | **no crash** — exit 0, coverage `complete`, ADE 0.000000 | mass=0 does not even reach a validation failure on esmini 3.10; the protocol's retest `1` vs `100` was run anyway and both are inert |
| gate fails | gate passed | not applicable |

## 5. Mechanism

Under `followingMode="position"` the entity's motion is defined solely by
`FollowTrajectoryAction` against the polyline geometry. `mass` is consumed only
by mass-coupled dynamics — longitudinal resistance, and any controller that
computes forces or torques. With position following, the controller sets
displacement rather than force, so no term involving mass is ever evaluated on
this path.

This is consistent with the residual behaviour measured independently in
`docs/reports/residual-replay-error-composition.md` §7: the post-fix residual is
**100 % along-track**, starts at exactly `0.0000 m`, and is a pure geometric
path-following lag — which is exactly what a mass-insensitive controller
produces. Per population, quoting that report exactly:

| population | mean abs ADE | mean abs cross-track (ego) | along-track / distance |
|---|---|---|---|
| ego (`808` tracks) | 0.2618 m | median 0.0037 m, p95 0.0095 m | ~0.25 % |
| non-ego (`2406` tracks) | 0.0358 m | — | far smaller |

Do not reduce this to one blended percentage: ego and non-ego differ by ~7x.

Note that observation is **corroborating, not proof**: it constrains the
longitudinal channel and says nothing about mass on any other path.

## 6. Scope limits (explicit)

- Native esmini **3.10.0 only**. No claim about 3.9.0, other builds, or esminiJS.
- `FollowTrajectoryAction` + `followingMode="position"` only. **No claim about
  `timing` mode**, other controllers, triggers, or collision dynamics.
- Tested classes: `Pedestrian` and `MiscObject`. **Vehicles carry no `mass`
  attribute** in OpenSCENARIO and are out of scope; the exporter emits none.
- **Bounding-box dimensions were not varied.** The protocol's decision table is
  written about `mass`; this audit covers `mass` only. Dimension inertness is
  therefore **not established** by this report and would need the same
  single-variable treatment if it is ever claimed.
- Nothing about whether these defaults are *appropriate* — only that they are
  inert. Choosing better values is a product decision, not a measurement.

## 7. Answers to A6

| question | answer |
|---|---|
| does mass steer `FollowTrajectoryAction` under `position`? | **No**, native 3.10, `Pedestrian` and `MiscObject`, decided by construction |
| is the documented-as-inert assumption true or false? | **HOLDS**, with the mechanism in §5 |
| does `MiscObject mass=0` crash the engine? | **No** — exit 0, complete coverage |
| are the defaults therefore wrong? | Not a measurement question. They are inert; whether 75 kg and 0 kg are the right *documented* values is an owner decision |

## 8. Reproduction

```bash
export ESMINI_BIN="$HOME/esmini-3.10/bin/esmini"
export ESMINI_DAT2CSV="$HOME/esmini-3.10/bin/dat2csv"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  ~/r2s-diagnostic/scripts/a6_mass_audit.py
```

Artifacts in `~/r2s-diagnostic/a6/`: `base.xosc`, the three variant `.xosc`,
all trace CSVs, and `a6_verdict.json`.
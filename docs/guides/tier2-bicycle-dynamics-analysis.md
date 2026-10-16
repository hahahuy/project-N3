# Analysis A — Writing a Tier 2 Bicycle Dynamics Model

**Status:** ANALYSIS — not an implementation commitment
**Supersedes nothing.** Complements `docs/guides/wasm-interactive-simulator-handoff.md`.
**Contract reference:** `docs/current/technical-contracts.md` lines 255-283, DEC-014.

---

## 1. The question this answers

Tier 1 (`kinematic-open-loop-v1`) and the esmini engine are both kinematic. Tier 2
would be the first model in this project that has forces in it. The question is:
what does that actually look like, what does it produce, and where does it plug in.

The short answer: the mathematics is one afternoon. Everything that makes it
defensible is the other two weeks.

---

## 2. What "bicycle model" means here, and which variant

There are two different things people call a bicycle model. The distinction is
the whole point of Tier 2.

| Variant | Lateral equation | Has tyre forces? | In this project today? |
|---|---|---|---|
| Kinematic bicycle | `ψ̇ = v·tan(δ)/L` | No | Yes — esmini `vehicle.cpp:198-215` and the intended Tier 1 |
| **Dynamic bicycle** | `ψ̈ = (l_f·F_yf − l_r·F_yr)/I_z` | **Yes** | No |

Tier 2 means the dynamic variant. The state vector grows from
`(x, y, ψ, v)` to `(x, y, ψ, v, v_y, r)` where `v_y` is lateral velocity at the
centre of gravity and `r` is yaw rate.

### 2.1 Core equations

Slip angles, small-angle:

```
α_f = δ − atan((v_y + l_f·r) / v)
α_r = −atan((v_y − l_r·r) / v)
```

Lateral forces, linear tyre region:

```
F_yf = C_f · α_f
F_yr = C_r · α_r
```

Linearised lateral/yaw state equations, valid for small slip (the useful regime):

```
v̇_y = −(C_f + C_r)/(m·v) · v_y
      + (−(C_f·l_f − C_r·l_r)/(m·v) − v) · r
      + C_f/m · δ

ṙ   = (−(C_f·l_f − C_r·l_r)/(I_z·v)) · v_y
      − ((C_f·l_f² + C_r·l_r²)/(I_z·v)) · r
      + C_f·l_f/I_z · δ

ψ̇ = r
ẋ  = v·cos ψ − v_y·sin ψ
ẏ  = v·sin ψ + v_y·cos ψ
ṽ  = 0            (longitudinal handled separately, see 2.3)
```

where `v = √(v_x² + v_y²)`, `l_f`/`l_r` are CG-to-axle distances, `C_f`/`C_r`
are axle cornering stiffness in N/rad, `m` is mass, `I_z` is yaw inertia.

### 2.2 Beyond the linear region

The linear tyre above is only valid to roughly 4-6 degrees slip. For a hard
emergency manoeuvre, which is precisely what this project generates, you need
either:

- **Pacejka Magic Formula** `F_y = D·sin(C·atan(B·α − E·(B·α − atan(B·α))))` with
  `D = μ·F_z`. More parameters, handles peak and falloff.
- **Combined slip** via a friction ellipse: scale `F_y` and `F_x` so that
  `(F_x/(μF_z))² + (F_y/(μF_z))² ≤ 1`. This matters — a hard brake and a hard
  turn share the same friction budget, and an uncoupled model will happily
  produce more total force than the tyre has.

Recommendation: implement linear first as the reference, add Pacejka as a
declared option, make combined slip opt-in and label it in the trace. Do not ship
linear-only and call it Tier 2.

### 2.3 Longitudinal

Keep this simple and separate. A tractive/braking model with engine torque curve
and gear ratios is a different project. For Tier 2 scope:

- Longitudinal acceleration as a bounded input or a simple first-order response
- Regenerative + friction braking split is out of scope
- Declare `a_x` as an input with limits, not as a derived quantity

If you find yourself writing a torque curve, stop. That is Tier 3.

### 2.4 Load transfer

Without CG height, tyre load is constant and `μ` is uniform. With `h_cg` and
track width, longitudinal and lateral load transfer modify per-axle `μ`, which
is what makes a vehicle understeer on entry to a corner and oversteer on exit.
This is real vehicle behaviour and it is a large part of what makes emergency
manoeuvres interesting. Recommend including `h_cg` from the start; retrofitting it
changes results in ways that invalidate earlier runs.

---

## 3. The parameter problem — read this before estimating

**nuScenes does not contain mass, cornering stiffness, yaw inertia or CG height.**
It contains boxes and tracks. So for every Tier 2 parameter you must supply a
prior from outside the dataset.

Parameter table:

| Symbol | Meaning | Typical source | Can nuScenes give it? |
|---|---|---|---|
| `m` | mass | vehicle class lookup | No |
| `I_z` | yaw inertia | `≈ m(L_f·L_r)²/3`, or class lookup | No |
| `l_f`, `l_r` | axle distances | wheelbase from bbox length minus overhangs | Weakly |
| `C_f`, `C_r` | cornering stiffness | tyre spec sheets, or Pacejka B/C/D | No |
| `μ` | friction coefficient | surface + tyre class | No |
| `h_cg` | CG height | class lookup | No |
| `L`, `T` | wheelbase, track | bbox | Approximately |

### 3.1 Identifiability consequence

Given only `(x, y, ψ, v)` from a recorded track, `m`, `I_z`, `C_f` and `C_r`
are **not separately identifiable**. Four unknowns, and the recorded trajectory
constrains their combination. Any Tier 2 run is therefore conditional on an
assumed parameter set, and the honest output is a distribution over results, not
a single trajectory.

This is the single largest difference from Tier 1, which is assumption-free by
construction. Every Tier 1 claim transfers directly. Every Tier 2 claim inherits
the uncertainty of its parameters.

### 3.2 The legitimate way to use it anyway

There is a use that does not require knowing the parameters precisely, and it is
valuable enough to justify Tier 2 on its own:

**Inverse dynamics as a plausibility check.** Given a recorded trajectory, back
out the control inputs the manoeuvre *demands*:

```
a_x = v̇
δ_implied = solved from (ψ̈, r, v_y) given assumed parameters
```

Then ask whether `(δ_implied, a_x_implied)` are physically achievable. A
recorded manoeuvre requiring `a_y = 14 m/s²` on dry asphalt is either a
sensor-label error or a genuinely extreme event. That is a real finding about
data quality and about which recorded scenarios are worth turning into test
cases. This is a measurement use. It is not a prediction use.

---

## 4. Validation strategy

Four tiers, cheapest first. Do not skip tier 2 — it is what catches sign errors.

| Tier | Test | What it proves |
|---|---|---|
| 1 | Analytic: constant steer, constant speed | Steady-state cornering radius matches `R = L / (δ + K·v²)` where `K = m/L² · (l_r/C_f − l_f/C_r)`. Exact, no reference needed. |
| 2 | Physics invariants | Yaw-moment balance, energy non-increase in coast, no NaN, speed decay sign |
| 3 | Standard manoeuvres | ISO 3888 double lane change, ELW (emergency lane change), sine-with-dwell. Compare against published reference envelopes. |
| 4 | Cross-simulator | Same scenario on CARLA or an equivalent reference. The only real fidelity evidence. |

Tier 1 is the one that pays for itself. A constant-steer test with an analytic
answer catches sign and scaling errors that no amount of eyeballing a trajectory
will. Write it first.

Tier 4 is an environment problem, not a code problem, and it is where the
schedule will slip. `docs/evidence/m5-simulators/m5b-carla-feasibility-evidence.md`
already records a deferral for CARLA. Budget accordingly or accept Tier 2 as
tier-3-validated only, and say so.

---

## 5. Integration into this codebase

### 5.1 Where it plugs

`PreviewService.preview()` in `src/r2s_web/jobs.py` currently returns
`status="unsupported"` with `reason="behavior executor is not implemented"` for
the behaviour branch. That is the seam. Tier 2 becomes one executor behind it.

Expected module layout:

```
src/real2scenario/dynamics/
├── __init__.py
├── bicycle.py         # ODE right-hand side, state vector, integrators
├── parameters.py      # parameter set, priors, provenance, versioning
├── integrators.py     # semi-implicit Euler, RK4, fixed 0.05 s step
├── diagnostics.py     # limit violations, friction usage, stability flags
└── maneuvers.py       # ISO 3888, ELW, sine-with-dwell
```

### 5.2 Reuse, do not reinvent

| Existing | Use |
|---|---|
| `models.State` | Already SI, frozen, time-ordered, validated. Emits Tier 2 output directly. |
| `coordinates.RoadAlignedTransform` | Converts between recorded and road-aligned frames. Use it, and keep the frame versioned. |
| `metrics.compute_replay_metrics` | ADE/FDE computation already exists and is trace-shaped. |
| `validation.FeasibilityLimits` | Already carries kinematic limit names; extend with dynamics limits. |

### 5.3 The reference-point trap

This is the integration bug you will hit first.

nuScenes boxes and Tier 2 states are anchored differently. The bicycle model
outputs state at the **centre of gravity**; recorded annotations are commonly at
the **box centre** or **rear axle**. Comparing them without an explicit transform
produces a systematic longitudinal offset of the order of a metre — larger than
most ADE values you would be reporting.

`technical-contracts.md` line 272 already demands *"reference-point convention is
explicit and versioned, never inferred silently"*. That is not bureaucracy, it is
this bug. Decide the convention, encode it in the parameter set, and report the
offset.

### 5.4 Contract obligations

`technical-contracts.md` line 283 requires Tier 2 to declare *"a separate
replay/behavior mode, versioned parameters, capability status and diagnostic
metrics"*, and forbids it feeding final ADE/FDE claims or silently falling back
to waypoint replay.

Concretely:

- New trace contract id: `dynamic-bicycle-open-loop-v1`. Do not extend
  `normalized-replay-trace-v2` in place; it is a different claim.
- Every run emits `capability_status`: what the model can and cannot represent.
  A model with linear tyres must not claim emergency-manoeuvre validity.
- No silent fallback. If the model cannot run (missing parameters, out of range),
  it returns `unsupported` with a reason. Same shape as the current behaviour stub.
- Tier 2 runs in the Python backend. It must **not** go into the browser Worker
  described in the WASM handoff. DEC-014 calls Tier 2 *"diagnostic only"*.

---

## 6. Expected outputs

For one scenario, one parameter set:

```
reports/<job-id>/<variant-id>/tier2/
├── trajectory.json          # State records, dynamic-bicycle-open-loop-v1
├── diagnostics.json         # per-actor, per-timestep
├── parameters.json          # values + provenance + class priors used
├── maneuver_report.json     # tier 1-3 validation results
└── sensitivity.json         # result spread across parameter priors
```

Diagnostics worth emitting:

| Metric | Why |
|---|---|
| Peak lateral acceleration | Screening for physical impossibility |
| Peak yaw rate | Limit violations |
| Peak slip angle, front and rear | Reveals which axle is saturated |
| Friction ellipse utilisation | Catches combined-slip overreach |
| Understeer gradient | The key model-level validation number |
| Yaw-moment balance residual | Numerical sanity |
| Stability flag | Divergence detection |

`sensitivity.json` is not optional. It is how a reader knows how much of the
answer came from the model and how much came from the assumed mass.

---

## 7. Risks

| Risk | Severity | Note |
|---|---|---|
| Scope explosion into full vehicle dynamics | High | The stopping line is §2.3. Enforce it. |
| Parameters unfalsifiable from project data | High | §3.1. Mitigate with sensitivity output, not with confidence. |
| Feeding Tier 2 into ADE/FDE | Medium | Forbidden by contract. Needs an architectural barrier, not just a doc line — see the handoff's P4 grep test. |
| Reference simulator unavailable | Medium | Environment blocker already documented. Accept tier-3 validation and label it. |
| Reference-point mismatch | Medium | §5.3. Cheap to get right, expensive to debug late. |
| Results silently better than reality | Medium | A model that reproduces a track it was derived from is not validated. Hold out scenarios. |

---

## 8. Honest estimate

| Work | Days |
|---|---|
| ODE core, integrators, unit tests | 1-2 |
| Parameter set, priors, provenance | 2-3 |
| Diagnostics and invariants | 1-2 |
| Maneuver suite + analytic validation | 2-3 |
| Reference-point integration with `State` / `coordinates` | 1 |
| API wiring into `PreviewService` | 1 |
| Sensitivity study | 1-2 |
| Cross-simulator comparison | 2-5 plus environment setup |

Roughly two weeks to something internally defensible. Four to six weeks to
something with external fidelity evidence. The maths is not the cost.
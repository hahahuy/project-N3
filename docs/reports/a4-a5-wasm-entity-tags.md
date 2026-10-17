# A4 + A5 — Widened entity tags in esminiJS, and MiscObject category policy

`scientific_status: PROVISIONAL`

Acceptance: WASM handoff `data-analysis-handoff-pedestrian-widening.md` §3 items
A4 and A5, §6 items 4 and 5.

Engines: native esmini **`v3.10.0-0-06065f9`** and esminiJS **3.10.0 WASM**
(`frontend/wasm-esmini/dist/esmini.js`, upstream commit `06065f9`) — version-matched.

---

# A4 — esminiJS handling of `Pedestrian` and `MiscObject`

**Parse verdict: PASS.** The WASM engine loads all three widened entity types,
steps them, and reports their state. Three objects in, three objects out.

## 1. The exact strings the engine returns

Read from `frame.object_states` after 51 steps at `dt = 0.01`:

| entity | XOSC tag | `object_type` | `object_category` | `ctrl_type` |
|---|---|---|---|---|
| `ego` | `Vehicle` | **`1`** | `0` | `0` |
| `walk1` | `Pedestrian` | **`2`** | `0` | `0` |
| `cone1` | `MiscObject` | **`3`** | `5` | `0` |

Interpretation against esmini's enums: `object_type` 1 = Vehicle,
2 = Pedestrian, 3 = MiscObject. `object_category` is the class-specific enum, so
`walk1` = 0 = PEDESTRIAN and `cone1` = **5 = BARRIER** (because that scenario set
`miscObjectCategory="barrier"`).

**All values are numeric strings, not names.**

## 2. Defect in the existing probe: wrong field names

This is the actionable finding. The state object exposes:

```
name, id, model_id, ctrl_type, timestamp, x, y, z, h, p, r, road_id,
junction_id, t, lane_id, lane_offset, s, speed, center_offset_x/y/z,
width, length, height, object_type, object_category, has_ghost,
sensor_x/y/z, trail_x/y/z, wheel_angle, ...
```

It has **no `type` and no `kind` field**. Both `smoke.mjs` and the renderer read
`object.type` / `object.kind`, which silently return `""` for every entity. That
is precisely why the renderer currently buckets everything as `unknown`
(gray) and the ledger reports `actor_kind: vehicle | unknown` — the strings were
never wrong, they were **never read**.

Verified directly: `legacy_type` and `legacy_kind` probe as `""` for all three
objects while `object_type` / `object_category` return real values.

**Consequence for the renderer:** a `pedestrian` kind/colour increment is a
**truthful small increment**, not scope creep, and it needs no new engine work —
only a corrected field read plus a 3-way bucket on `object_type`
(`1` vehicle, `2` pedestrian, `3` misc/other).

## 3. Cross-engine parity

Both engines were run on the identical XOSC:

| XOSC | native 3.10 | esminiJS 3.10 WASM |
|---|---|---|
| as the exporter writes it today | `category not supported yet` (x2), `cone1` category `0` | `category not supported yet` (x2), `object_category = 0` |
| with corrected attribute names | no category errors, `cone1` category `5` | no category errors, `object_category = 5` |

**The two engines agree exactly**, on both the error path and the value path.
That is positive parity evidence for the widened tags on the classes tested.

## 4. Scope limits

- esminiJS 3.10.0 WASM build in `frontend/wasm-esmini/dist/` only; that file is
  a local probe result and must not be used for Tier 0 metrics.
- Tested: load, `step_frame`, `get_object_states`, three entity classes, one
  scenario, `dt = 0.01`.
- **Not** tested: `reset()` re-initialisation stability, `seek`/re-integrate,
  camera/POV, collision behaviour, or any class-count beyond the three above.
- A4's core question — do the new tags parse, and what strings come back — is
  answered. The §4 items in the handoff (entity-ID stability across `reset`,
  end-of-track hold) are **not** addressed here.

---

# A5 — MiscObject policy

## 5. What esmini actually does with each category value

Read from `Entities.hpp`, `MiscObject::SetCategory`. These 17 strings are
recognised:

```
none, obstacle, pole, tree, vegetation, barrier, building, parkingSpace,
patch, railing, trafficIsland, crosswalk, streetLamp, gantry,
soundBarrier, wind, roadMark
```

Anything else falls into the final `else`:

```cpp
LOG_ERROR("MiscObject category {} not supported yet", category);
```

`category_` then keeps its default, enum `NONE = 0`. The run is **not** aborted —
exit 0 — but an error-level line is emitted for every such object on every load.

## 6. Two exporter defects this exposed

### 6.1 Attribute-name case mismatch (the category is never read)

- esmini reads `miscObjectCategory` (lowercase `o`).
- The exporter writes `MiscObjectCategory` (capital `O`).

So the attribute the exporter emits **is never read**, whatever its value.
Confirmed empirically: rewriting the attribute to esmini's casing with the value
`barrier` makes the error disappear and makes `object_category` come back as `5`.

`other` is therefore not "conservative" — it is an **unrecognised** value, and it
costs one `LOG_ERROR` per object per load.

### 6.2 `Pedestrian` has no `pedestrianCategory` at all

The exporter emits `Pedestrian` with `name`, `mass` and `model` but **no**
`pedestrianCategory`. esmini reads `pedestrianCategory`, gets an empty string,
and logs `Pedestrian category  not supported yet`. Adding
`pedestrianCategory="pedestrian"` clears the error (verified).

## 7. Category is motion-inert, decided by construction

Same methodology as A6. With the attribute names corrected, seven categories were
replayed on the identical scenario:

| category | trace vs `barrier` |
|---|---|
| `obstacle`, `pole`, `tree`, `vegetation`, `building`, `none` | **byte-identical** |

So category, like mass, does not steer a `FollowTrajectoryAction` under
`followingMode="position"`. Consistent with A6's mechanism: the controller sets
displacement, so no category-dependent term is evaluated.

## 8. Recommendation

The handoff offers three options. **(i) keep `other` is rejected** — it is not
valid, it is never read, and it emits an error per object per load. Option (iii)
fail-closed-everything is safe but throws away a reachable class.

**Recommended: (ii), corrected.** Specifically:

1. Emit the attribute esmini actually reads: `miscObjectCategory`.
2. Emit `pedestrianCategory="pedestrian"` on `Pedestrian`.
3. Map the reachable nuScenes categories:

| nuScenes category | esmini value | quality |
|---|---|---|
| `movable_object.barrier` | `barrier` | **exact** |
| `movable_object.trafficcone` | `obstacle` | approximate — no cone in the enum |
| `movable_object.debris` | `obstacle` | approximate |
| `movable_object.pushable_pullable` | `obstacle` | approximate |
| `static_object.bicycle_rack` | `obstacle` | approximate |
| `animal` | **fail-closed** | no semantically honest value exists |

4. Fail closed on any unmapped taxonomy rather than emitting a default.

**Be explicit about what this buys:** it removes two `LOG_ERROR` lines per
MiscObject/Pedestrian load and makes the category truthful in the state record.
It changes **no replay number**, because §7 proves the category is inert under
position following. Anyone presenting this as a fidelity improvement would be
overclaiming; it is a log-hygiene and forward-compatibility fix.

Minor correction to the handoff's §2: the `MiscObject/other` row is labelled
"(5)" but lists six categories. The list, not the count, is what I used.

## 9. Scope limits

- Category inertness is established for `MiscObject` under
  `FollowTrajectoryAction` + `position` on native 3.10, and the same trace
  identity was observed on esminiJS. **No claim** about collision detection,
  sensors, or any controller that consults category.
- Whether the exporter should ever emit a `MiscObject` at all is untouched here:
  these actors remain unreachable by automatic selection.
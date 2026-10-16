# Analysis B — Interactive Object Selection and Behaviour Injection

**Status:** ANALYSIS — implementation analysis
**Authority:** DEC-017 in `docs/current/decisions.md`
**Companion:** `docs/guides/wasm-live-simulator-handoff.md`
**Question:** what must change so the user can select a non-ego actor in the 3D
view and drive behaviour changes on that specific actor.

---

## 1. Summary

Picking is easy. Three of the four desired interactions are already
mechanically available in the engine and need only an `embind.cpp` registration.
One — live parameter change — does not work, and cannot be made to work through
the engine's parameter API.

| Interaction | Feasible | Mechanism |
|---|---|---|
| Hover highlight | yes | client only |
| Click to select | yes | client only |
| Inject speed on the selected actor | **yes** | `PlayerServer::InjectSpeedAction` |
| Inject lane change | **yes** | `PlayerServer::InjectLaneChangeAction` |
| Inject lane offset | **yes** | `PlayerServer::InjectLaneOffsetAction` |
| Pause / resume / step | **yes** | `ScenarioPlayer::SetState` |
| **Change a scenario parameter live** | **no** | engine limitation, §6 |

Two consequences that are easy to miss:

- `InjectSpeedAction` has **no null guard** on the id lookup. §5.2.
- Injected actions **do not survive `reset()`**, so an action log is a design
  requirement, not a nicety. §7.

---

## 2. State available for picking

`get_object_states()` returns `ScenarioObjectState`, declared in the upstream
`esminijs.hpp` around lines 28-64. Relevant fields:

| Field | Type | Use |
|---|---|---|
| `id` | `int` | **engine entity id — the injection target key** |
| `name` | `string` | label plate |
| `x`, `y`, `z` | `float` | position |
| `h`, `p`, `r` | `float` | heading, pitch, roll |
| `width`, `length`, `height` | `float` | oriented bounding box |
| `object_type`, `object_category` | `int` | styling and filtering |
| `has_ghost` | `bool` | ghost is a replay marker — exclude from picking |

There is no colour, no model reference, no parent/child hierarchy. Enough for
boxes and labels.

Precision caveat: these are `float32`. Fine for rendering; not for measurement.
See the handoff §9.

---

## 3. Picking

Standard three.js. With react-three-fiber, raycasting is handled for you — pointer
events on a mesh carry identity.

```tsx
<mesh
  onPointerOver={(e) => { e.stopPropagation(); setHoverId(id) }}
  onPointerOut={() => setHoverId(null)}
  onClick={(e) => { e.stopPropagation(); select(id) }}
>
  <boxGeometry args={[state.width, state.height, state.length]} />
  <meshStandardMaterial color={colorFor(id, hoverId, selectedId)} />
</mesh>
```

Geometry convention: long axis `length` along local Z, local Y up, rotated by
heading about Y. esmini and OpenDRIVE are right-handed with Z up; three.js is Y
up. Convert once at the boundary, never per frame. The upstream reference
implementation is `esminiJS/example/viewer.js` — match its convention so future
diffs stay readable.

`e.stopPropagation()` is required, or clicking an actor also fires the ground
plane handler underneath and clears the selection.

There is no `is_ego` flag in the state. Identify ego from the scenario and style
it separately. Do not infer ego from position.

---

## 4. Selection state

```ts
const [selectedId, setSelectedId] = useState<number | null>(null)
const [hoverId, setHoverId] = useState<number | null>(null)
```

`selectedId` holds the engine entity `id`, not `name`. The injection path looks
up objects by integer id, so anything else fails silently.

Selection is client-only. Only the resulting actions need a Worker round trip.

---

## 5. Injection mechanism

### 5.1 The chain is already live

`PlayerServer::InjectSpeedAction` resolves its target as:

```cpp
a->object_ = player_->scenarioEngine->entities_.GetObjectById(action.id);
```

`ScenarioPlayer` constructs `player_server_` unconditionally in its constructor,
exposes it as a public member, and `esminijs.cpp` already calls
`SetInjectedActionsPtr()` on it. So the machinery exists; only a method on
`OpenScenario` plus one `.function(...)` line in `embind.cpp` is missing.

### 5.2 No null guard — validate client-side

The line above assigns whatever `GetObjectById` returns, with **no null check**. A
stale id dereferences null later in the action's lifetime.

Validate before every send:

```ts
function injectSpeed(targetId: number, mps: number, shape: number, dim: number, value: number) {
  if (!currentStates.some((s) => s.id === targetId)) {
    throw new Error(`actor ${targetId} no longer exists`)
  }
  worker.postMessage({ type: 'injectSpeed', targetId, mps, shape, dim, value })
}
```

Ids change across `reset()`. Clear `selectedId` on reset, or re-validate on every
panel render.

### 5.3 Action semantics that shape the UI

| Property | Value | Consequence |
|---|---|---|
| `max_num_executions_ = 1` | hardcoded | the action fires once and expires; re-triggering needs a new call |
| starts at current time | by construction | you cannot schedule a future injection |
| `transition_shape` | cubic / linear / sinusoidal / step | dropdown; not every shape suits every dimension |
| `transition_dim` | distance / rate / time | dropdown with units |
| lane change `mode` | 0 absolute, 1 relative | relative resolves against the actor's own lane at inject time |
| lane offset `target` | signed metres | signed input |

The panel is a **one-shot trigger with parameters**, not a set of toggles. Label
it "apply once". A switch that silently does nothing on the second click is worse
than a button.

---

## 6. Live parameter change does not work

The finding most likely to waste implementation time.

`ScenarioPlayer::SetVariableValue` delegates to `Parameters::setParameterValue`,
which mutates the stored parameter entry and nothing else. It does not
re-evaluate running storyboard elements, active conditions, or already
instantiated actions — storyboard elements resolve their parameter values at
instantiation.

So `setVariable("cutInSpeed", 15)` mid-run appears to succeed and changes nothing
visible. And it fails silently on an unknown name: the function returns `-1`, so
the wrapper must check it.

### 6.1 What works

**Rewrite the `.xosc` XML in the Worker before constructing the engine.**

The Worker already receives the file bytes to write into the Emscripten
filesystem. Parsing and rewriting parameter values in that text, then
constructing the scenario, is deterministic, fully controlled, and needs no
esmini plumbing. Recommended.

### 6.2 What to avoid

`setVariable` then `reset()` then replay is fragile: `ScenarioEngine` is
constructed during `reset()` and resolves the storyboard during construction, so
a variable set afterwards is too late for the initial state, and one set
beforehand is re-read from disk and lost. The correct ordering was not verified.
Do not build on it without testing.

### 6.3 UI consequence

Parameter changes are not instant. They require re-initialisation. The UI must
show this: editing a parameter marks the run dirty and applies on the next reset
or an explicit apply. A live slider would be a lie.

---

## 7. Injected actions do not survive reset — action log required

`reset()` deletes the player and constructs a fresh `ScenarioPlayer`, destroying
`player_server_` and its queued actions.

Consequence: **scrubbing backwards and replaying does not reproduce the original
run.** User interaction is a side effect that evaporates.

Design requirement:

```ts
type ActionRecord =
  | { t: number; kind: 'speed';      targetId: number; args: number[] }
  | { t: number; kind: 'laneChange'; targetId: number; args: number[] }
  | { t: number; kind: 'laneOffset'; targetId: number; args: number[] }
  | { t: number; kind: 'paramEdit';  name: string;     value: number }
```

The Worker keeps an ordered log. On `seek(t)` or `reset()` it re-runs from t=0
and re-injects every recorded action at its recorded time. Only then is the
timeline scrubber trustworthy.

The subtle part is remapping target ids across a re-init. If ids are not stable
across `reset()`, match on `name` at replay time and fail loudly on ambiguity
rather than guessing.

---

## 8. Change list

### Frontend

| File | Change |
|---|---|
| `src/sim/embind` surface via `wasmModule.ts` | expose injection methods |
| `src/sim/simWorker.ts` | action log, replay-on-seek, id remapping, id validation |
| `src/sim/protocol.ts` | inject / paramEdit / seek message types |
| `src/three/ActorBoxes.tsx` | pointer handlers, hover and selected materials, `stopPropagation`, exclude `has_ghost` |
| `src/three/Scenario3DCanvas.tsx` | selection context, clear-on-reset |
| `src/panels/ActorInspector.tsx` | **new** — name, type, dimensions, speed, lane, road id, actions |
| `src/panels/BehaviourPanel.tsx` | **new** — one-shot triggers with shape/dimension/value |
| `src/App.tsx` | swap the `third-person` presentation layer for `Scenario3DCanvas` |

### WASM build

| File | Change |
|---|---|
| `esminijs.hpp` / `esminijs.cpp` | `inject_speed`, `inject_lane_change`, `inject_lane_offset`, `injected_action_ongoing`, `set_paused` |
| `embind.cpp` | register each with `.function(...)` |

Use scalar parameters, not `value_object<SpeedActionStruct>`. Registering the
struct means pulling `PlayerServer` types into the embind surface and makes the JS
call site worse. Five scalars cost nothing.

### Backend

No change. Objects and geometry come from the engine in the browser.

---

## 9. Testing

| Test | Level |
|---|---|
| id ↔ box mapping resolves the right entity | pure function; jsdom has no WebGL so test the mapping, not the canvas |
| invalid id rejected before injection | pure function, unit tested |
| action log replays in order and yields state identical to the original run | integration against the real WASM module |
| replay after reset reproduces the pre-reset trajectory | same harness |
| parameter edit changes the run | integration; assert the outcome differs, since it will not change immediately |

The action-log determinism test justifies the whole design. If it fails, the
scrubber is lying to the user and the feature is not shippable.

---

## 10. Effort

| Work | Days |
|---|---|
| Picking, hover, selection, inspector | 1 |
| Three injections wired end to end | 1 |
| Action log, replay-on-seek, id remapping | 2 |
| Parameter rewrite path in the Worker | 1 |
| Integration tests with real WASM | 1-2 |

Add roughly six days on top of the handoff's P2-P3. The action log is the largest
single item and the easiest to under-budget, because it only becomes visible after
someone scrubs backwards and notices the world changed.
# Analysis B — Interactive Object Selection in the 3D Simulator

**Status:** ANALYSIS — implementation analysis for the U5 / WASM work
**Companion to:** `docs/guides/wasm-interactive-simulator-handoff.md`
**Question:** what must change so the user can click a non-ego object in the 3D
view and drive behaviour changes on that specific object.

---

## 1. Summary

Picking is easy. Acting on the picked object is easy for three actions and
**structurally impossible for one** of the things the original request assumed.

| Desired interaction | Feasible? | Mechanism |
|---|---|---|
| Hover to highlight an actor | Yes | Client-side only |
| Click to select an actor | Yes | Client-side only |
| Inject speed change on the selected actor | **Yes** | `PlayerServer::InjectSpeedAction`, verified |
| Inject lane change on the selected actor | **Yes** | `PlayerServer::InjectLaneChangeAction`, verified |
| Inject lane offset on the selected actor | **Yes** | `PlayerServer::InjectLaneOffsetAction`, verified |
| Pause / resume / step | **Yes** | `ScenarioPlayer::SetState`, verified |
| **Change a scenario parameter live** | **No** | Engine limitation, §6 |

There is also a consequence nobody expects: **injected actions do not survive
`reset()`**. That makes an action log a design requirement, not a nicety. §7.

---

## 2. What state is available for picking

`get_object_states()` returns `ScenarioObjectState`, declared in
`EnvironmentSimulator/Libraries/esminiJS/esminijs.hpp` lines 28-64. Fields
relevant to picking and rendering:

| Field | Type | Use |
|---|---|---|
| `id` | `int` | **engine entity id — the injection target key** |
| `name` | `string` | label plate |
| `x`, `y`, `z` | `float` | position |
| `h`, `p`, `r` | `float` | heading, pitch, roll |
| `width`, `length`, `height` | `float` | oriented bounding box |
| `object_type`, `object_category` | `int` | styling, filtering |
| `has_ghost` | `bool` | ghost is a replay marker, exclude from picking |

There is no per-actor colour, no model reference and no parent/child hierarchy.
That is enough for boxes and labels.

Note the precision: these are `float` (32-bit). At road-scale coordinates
(1 km road, coordinates in the thousands of metres) float32 resolution is roughly
0.1 mm — fine for rendering, and see `wasm-interactive-simulator-handoff.md` §6
for why these numbers must not be measured.

---

## 3. Picking implementation

Standard three.js. With react-three-fiber the raycasting is free — pointer events
on a mesh carry the object identity.

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

Geometry orientation: the OBB's long axis is `length` along local Z, with local Y
up, rotated by heading about Y. The scene needs one fixed convention — esmini and
OpenDRIVE are right-handed with Z up, three.js is Y up — so convert once at the
boundary and never per-frame. The upstream reference implementation is
`esminiJS/example/viewer.js`; match its convention so future diffs are readable.

`e.stopPropagation()` is required. Without it, clicking an actor also fires the
ground-plane handler underneath and clears the selection.

Ego versus non-ego: there is no "ego" flag in the state. Identify ego by the
scenario's actor, and render it differently. Do not infer it from position.

---

## 4. Selection state

```ts
const [selectedId, setSelectedId] = useState<number | null>(null)
const [hoverId, setHoverId] = useState<number | null>(null)
```

`selectedId` holds the engine entity `id`, not the `name`. This matters: the
injection path looks the object up by integer id, so anything else silently fails
(§5).

Selection is client-only state. It does not need a Worker round trip. Only the
resulting actions do.

---

## 5. Actions on the selected actor — verified mechanism

### 5.1 The path

`PlayerServer::InjectSpeedAction` (`EnvironmentSimulator/Modules/PlayerBase/PlayerServer.cpp:171-188`)
resolves the target as:

```cpp
a->object_ = player_->scenarioEngine->entities_.GetObjectById(action.id);
```

and `ScenarioPlayer` constructs `player_server_` unconditionally in its
constructor (`playerbase.cpp:79`), exposing it publicly (`playerbase.hpp:250-251`).
So the chain is already live and only needs a method on `OpenScenario` plus one
`.function(...)` line in `embind.cpp`. See the handoff §6 for the code sketch.

### 5.2 No null guard — client must validate

The line above assigns whatever `GetObjectById` returns, with **no null check**.
A stale id dereferences null later in the action's lifetime.

Every inject call must therefore be validated against the current object list
immediately before sending:

```ts
function injectSpeed(targetId: number, mps: number, shape: number, dim: number, value: number) {
  const alive = currentStates.some((s) => s.id === targetId)
  if (!alive) throw new Error(`actor ${targetId} no longer exists`)
  worker.postMessage({ type: 'injectSpeed', targetId, mps, shape, dim, value })
}
```

Ids change across `reset()`. A selection made before a reset is invalid after it.
Clear `selectedId` on reset, or re-validate on every render of the panel.

### 5.3 Action semantics that affect UI design

| Property | Value | Consequence |
|---|---|---|
| `max_num_executions_ = 1` | hardcoded (`PlayerServer.cpp:180`) | An injected action fires once and expires. Re-triggering requires a new inject call — there is no persistent "this actor now obeys X" mode. |
| Action starts at current time | by construction | You cannot schedule a future injection. Only now. |
| `transition_shape` | cubic / linear / sinusoidal / step | Expose as a dropdown; not all shapes are meaningful for all dimensions. |
| `transition_dim` | distance / rate / time | Expose as a second dropdown with units. |
| Lane change `mode` | 0 absolute, 1 relative | Relative targets offset from the actor's own lane at inject time. |
| Lane offset `target` | offset in metres | Signed. |

Design implication: the panel cannot be a set of toggles. It is a
**one-shot trigger with parameters**, and the UI should say so. "Apply once" beats
a switch that silently does nothing on the second click.

---

## 6. Live parameter change — the one thing that does not work

This is the finding most likely to waste implementation time.

`ScenarioPlayer::SetVariableValue` delegates to
`Parameters::setParameterValue` (`Parameters.cpp:123-150`), which **mutates the
stored parameter entry and nothing else**. It does not re-evaluate running
storyboard elements, active conditions, or already-instantiated actions. Storyboard
elements resolved their parameter values at instantiation.

So calling `setVariable("cutInSpeed", 15)` mid-run will appear to succeed and
change nothing visible. Worse, it is silent — no error is returned if the name is
wrong either; the function returns `-1` for an unknown name and the JS wrapper
must check that.

### 6.1 What actually works

**Rewrite the `.xosc` XML in the Worker before constructing the engine.**

The Worker already receives the file bytes as an `ArrayBuffer` to write into the
Emscripten FS. Parsing and rewriting parameter values in that text first, then
constructing `OpenScenario`, is deterministic, fully under your control, and needs
no esmini plumbing at all. This is the recommended implementation.

### 6.2 What to avoid

The alternative — `setVariable` then `reset()` then replay — is fragile. Ordering
matters (`ScenarioEngine` is constructed in `reset()` and resolves the storyboard
during construction, so a variable set *after* construction is too late for the
initial state, and one set *before* it is re-read from disk and lost), and the
correct ordering was not verified. Do not build on it without testing first.

### 6.3 UI consequence

Parameter changes are **not instant**. They require a re-initialisation. The UI
must show that: editing a parameter marks the run dirty, and the change applies on
the next reset or explicit apply. Presenting it as a live slider would be a lie.

---

## 7. Injected actions do not survive reset — action log required

`reset()` in `esminijs.cpp:559-578` deletes the player and constructs a fresh
`ScenarioPlayer`. That destroys `player_server_` and its queued injected actions.

The consequence: **scrub backwards and replay does not reproduce the original
run.** The user's interaction is not part of the scenario; it is a side effect
that evaporates.

Design requirement, not optional:

```ts
type ActionRecord =
  | { t: number; kind: 'speed';        targetId: number; args: number[] }
  | { t: number; kind: 'laneChange';   targetId: number; args: number[] }
  | { t: number; kind: 'laneOffset';   targetId: number; args: number[] }
  | { t: number; kind: 'paramEdit';    name: string;     value: number }
```

The Worker keeps an ordered log. On `seek(t)` or `reset()`, it replays the engine
from t=0 and re-injects every recorded action at its recorded time. Only then is
the timeline scrubber trustworthy.

Remapping target ids across a re-init is the subtle part. If ids are not stable
across `reset()`, match on `name` at replay time and fail loudly on ambiguity
rather than guessing.

---

## 8. Change list

Frontend, building on the handoff's P2 layout:

| File | Change |
|---|---|
| `src/three/ActorBoxes.tsx` | Pointer handlers, hover and selected materials, `stopPropagation`, exclude `has_ghost` |
| `src/three/Scenario3DCanvas.tsx` | Selection context, clear-on-reset, selection outline |
| `src/panels/ActorInspector.tsx` | **New.** Name, type, dimensions, current speed, lane, road id, selection actions |
| `src/panels/BehaviourPanel.tsx` | **New.** One-shot triggers with shape/dimension/value inputs |
| `src/sim/protocol.ts` | Message types for inject, paramEdit, seek-with-replay |
| `src/sim/simWorker.ts` | Action log, replay-on-seek, id remapping, id validation |
| `src/App.tsx` | D2/D3/D4 from the handoff: remove the whitelist and the unavailable placeholder |

WASM side:

| File | Change |
|---|---|
| `esminijs.hpp` / `.cpp` | `inject_speed`, `inject_lane_change`, `inject_lane_offset`, `injected_action_ongoing` |
| `embind.cpp` | Register each with `.function(...)`; use scalar parameters, not `value_object` |

Backend: **no change required.** Objects and geometry come from the engine in the
browser. Optionally add a convenience route returning `{xosc_url, xodr_url,
duration_s, coordinate_frame}` so the frontend does not have to dig through
`/artifacts`, but this is ergonomics, not necessity.

---

## 9. Testing

| Test | Level |
|---|---|
| Picking resolves the correct entity id | Vitest with jsdom is unsuitable — no WebGL. Test the id↔box mapping as a pure function. |
| Invalid id is rejected before injection | Pure function, unit tested |
| Action log replays in order and produces identical state to the original run | Integration test against the real WASM module. This is the test that proves determinism and is the single most valuable one in this feature. |
| Replay after reset reproduces the pre-reset trajectory | Same integration harness |
| Parameter edit changes the run | Integration test; assert the outcome differs, since §6 means it will not change immediately |

The action-log determinism test is the one that justifies the whole design. If it
fails, the scrubber is lying to the user and the feature is not shippable.

---

## 10. Effort

| Work | Days |
|---|---|
| Picking, hover, selection, inspector | 1 |
| Three inject actions wired end to end | 1 |
| Action log, replay-on-seek, id remapping | 2 |
| Parameter rewrite path in the Worker | 1 |
| Integration tests with real WASM | 1-2 |

Add roughly five days to the handoff's P2-P3 estimate. The action log is the
single largest item and the easiest to under-budget, because it only becomes
visible after someone scrubs backwards and notices the world changed.
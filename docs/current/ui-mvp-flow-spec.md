# Workspace UI/UX Specification (CAD-style Real2Sim workspace)

Status: `CURRENT DESIGN SPEC / IMPLEMENTATION PARTIAL`
Audience: frontend and UX engineers.
Supersedes: the former U0 three-rail MVP flow specification.

This is the authoritative workspace specification. It must be read with
`MVP&ProjectSummary.md`, `docs/current/project-status.md`, and
`docs/current/technical-contracts.md`. The current implementation milestone is
**U1: Workspace shell and Top-down view**. Later milestones must not be pulled
forward by inventing API data.

## 1. Product intent

The workspace lets an analyst take a recorded nuScenes interaction, rebuild it
as an editable top-down, 3D, in-car or third-person scene, inspect recorded
LiDAR and native map data, vary it through constrained driving maneuvers, replay
it through the supported simulator path, and audit every number back to a
private artifact. The metaphor is a
parametric CAD document: a scenario is a document, its construction is an
ordered recipe, variants are configurations, validation is a gate lane, and a
scenario can be inspected through several views.

Auditability beats spectacle. This is a simulator-backed analyst workspace,
not an autonomous-driving demo. Recorded sensor and map views must use actual
nuScenes/devkit data; simulator POVs must identify whether they come from
esmini, the internal preview, or CARLA.

## 2. Binding principles

- Never display a number without its status. `PROVISIONAL` is always visible.
- Absent is not zero. Missing metrics render as `n/a` with the API reason.
- Unsupported is a first-class state and must include its reason.
- Provenance is one click away from scenarios, variants, gates, and metrics.
- Failures are stated plainly; local API, dataset, and simulator availability
  must never degrade silently.
- Every change is a named, ordered, parameterised recipe step.
- Preview, rollback, and view changes are non-destructive by default.
- One selection updates every open view, timeline, recipe, and flyout.
- Collapsed panels retain a visible status summary or badge.
- Direct manipulation edits recipe parameters; it never writes trajectories.
- Steering, acceleration, braking and speed edits are constrained maneuver
  parameters. Users must not freely displace an actor or assign arbitrary
  per-axis velocity.
- 3D renders only recorded or pipeline-produced data. No decorative reality.
- Every POV identifies its source, frame, timestamp and simulator/rendering
  status.

## 3. Exact product nouns

Use these nouns in code and UI: **Workspace**, **Document tab**, **Scenario**,
**Source scene**, **Recipe**, **Step**, **Rollback marker**, **Variant**,
**Variant table**, **Branch**, **View**, **View manager**, **Run**, **Gate**, and
**Artifact**. Do not substitute project, model, window, canvas, test case, or
pipeline step.

## 4. Workspace regions

```text
Workspace
|-- Title bar: document, branch, version, connection/simulator/dataset chips, Export
|-- Toolbar: History | Import | Edit | Check/Run | Inspect | View | Search commands
|-- Left icon strip: Recipe | Catalog | Map layers | Comments
|-- Left panel: selected strip surface, resizable, minimum 200px
|-- View manager: main view plus 0-3 side views, dominant workspace area
|-- Right icon strip: Metrics | Gates | Provenance | Artifacts, persistent badges
|-- Right flyouts: read-only, overlay or docked, minimum 280px
|-- Gate lane bar and document tabs
|-- Status bar: selection, branch, rollback, time/frame, POV source, provisional count, transform version
```

The default workspace opens with exactly one Top-down main view. Users can open
side views, rearrange which view is main, resize side panes, maximize a view and
close views. Closing the last view is allowed and shows `No views open. Add a
view.`. Tablet layouts turn panels into overlay drawers, stack views vertically,
and preserve catalog -> inspect -> edit order.

## 5. Interaction contract

Modes are mutually exclusive and visible: Select (`S`), Edit (`E`), Measure
(`M`), and Compare (`C`). Icon buttons are 28px, have accessible names and
tooltips, and explain disabled reasons. Edit exposes constrained maneuver
controls: steering/heading change, acceleration, braking, target speed and
timing. It must reject arbitrary displacement edits and report the applied
profile, limits and unsupported fields. Search commands (`Alt+C`, `Ctrl/Cmd+K`)
lists enabled and unsupported commands.

Selection is single by default; Shift adds and Escape clears. Selecting an
actor in any surface updates every view. There is no ViewCube or corner
orientation widget. Camera presets live in view headers; `Home` resets a camera.
Undo/redo covers recipe edits, maneuver parameter edits, rollback markers and
view-manager actions, not camera or panel width changes.

## 6. View manager and U1 scope

Every view header contains an icon, view name and target, POV/source selector,
camera preset menu, layers menu, make-main, maximize/restore, and close. View
layouts are one main view with side views; two side-by-side; three with the main
view large and two stacked; and four in a 2x2 grid. Panes have draggable and
keyboard-operable splitters, minimum 280x200px, and are stored per document
tab. Reset layout restores one Top-down main view.

U1 delivers the shell, icon strips, flyout shells with badges, document tabs,
status bar, main/side view manager, add/rearrange/close actions, 1-4 layouts,
empty state, and the Top-down view with recorded versus generated overlays.
Top-down supports native nuScenes map layers, trajectories, actor boxes,
time-indexed state, and measure labels when supplied by the API. Recorded is
dashed neutral; generated is solid accent. Ego and unsupported dimensions use
shape or hatching as well as colour.

The view manager must expose these real view types rather than permanently
disabling them:

- Top-down map POV: native nuScenes vector/map layers and generated overlays.
- 3rd-person POV: simulator-rendered actor/world view from esmini or CARLA when
  that backend is available.
- In-car POV: ego-mounted simulator camera when the backend and camera contract
  are available.
- LiDAR POV: recorded `LIDAR_TOP` data loaded through the devkit, with timestamp,
  calibration, frame and decimation provenance.

Unavailable states remain valid only when the relevant local data, renderer or
simulator is genuinely unavailable, and must name that reason.

## 7. Existing tabs and inspection surfaces

Document tabs are Scenario studio, Variant studio, Replay, and Report. Each
remembers its view layout and panel widths; switching tabs does not change
scientific state. Metrics, Gates, Provenance, and Artifacts flyouts are
read-only. They show status and API reasons, never guessed values.

## 8. Milestones

| Milestone | Deliverable |
|---|---|
| U1 | Workspace shell, main/side view manager, Top-down map view |
| U2 | Recipe tree, rollback marker, constrained maneuver edit dialog, live preview |
| U3 | Gate lane, time-indexed timeline, actor state tracks, Measure mode |
| U4 | Variant studio, branches, Compare, metric lane, Report |
| U5 | 3rd-person and in-car simulator POV, XODR/native map layers, 3D actor boxes |
| U6 | Recorded LiDAR POV, devkit calibration/decimation and variant sensor status |

These milestones define the current MVP completion scope. They may be delivered
incrementally, but recipe, timeline, 3D, LiDAR, branches and compare data must
not be mocked as backend truth.

## 9. State matrix

| Surface | Loading | Empty | Error | Partial / skipped | Success |
|---|---|---|---|---|---|
| Recipe | skeleton rows | Import a scene to start a recipe | verbatim API error | inactive after marker | active steps + statuses |
| View manager | skeleton panes | No views open. Add a view. | error per pane | unavailable types with reason | 1-4 laid out |
| Top-down/map | skeleton canvas | Select an imported scenario | inline error | missing layers labelled | native/generated layers |
| 3rd-person/in-car | simulator loading | unavailable + backend reason | API reason | simulator capability label | rendered simulator POV |
| LiDAR | loading sweep | unavailable + data reason | API reason | decimation/coverage label | recorded point cloud with provenance |
| Timeline | skeleton tracks | n/a | error lane | skipped means not measured | time-indexed actor state and gates |
| Metrics / Measure | n/a | n/a with reason | n/a with reason | insufficient coverage | value, unit, status |

## 10. API and backend boundary

Continue consuming the existing endpoints in the prior MVP contract through
`frontend/src/api.ts`. Add typed clients and tests before using new fields.
Backend tasks are required for recipe/steps, branch lineage, constrained
maneuver parameters, time-indexed actor state, gate extents, actor dimensions
with availability, native/map and viewer-friendly XODR geometry, simulator POV
frames, point-cloud sweeps and payloads, and explicit variant sensor-frame
status. Do not hard-code missing values or reason strings beyond documented
contract values.

## 11. Visual and accessibility requirements

Define tokens in one place with three neutral surfaces, one accent, and
contrasting light/dark status colours for `pass`, `fail`, `skipped`, `error`,
`unsupported`, and `PROVISIONAL`. Status must never be colour-only. UI density
is compact: 12-14px text, 26-28px controls, hairline borders, visible 2px
splitters. Use one open icon set. Respect reduced motion, visible focus rings,
keyboard operation for all commands, view actions, splitters, rollback, and
timeline controls. Every view has a text equivalent.

## 12. Acceptance criteria

For each milestone, the primary flow works against the local API; loading,
empty, error, partial, and success states are screenshot-checked at desktop and
tablet widths; no metric or gate lacks status; provenance is one click away;
keyboard-only and reduced-motion walkthroughs work; collapsed surfaces retain
badges; and `npm test` plus `npm run build` pass. View-manager work must test
adding and closing each available view, 1-4 layouts, splitters, empty state,
the four-view limit, and that closing views never changes scenario data.

## 13. Code organisation

```text
frontend/src/
  App.tsx
  api.ts / api.test.ts
  tokens.css or equivalent
  workspace/ (shell, panels, views, inspection, timeline, variants)
  state/ (selection, mode, rollback, playhead, view layout)
```

The current code may remain incrementally structured while U1 is delivered, but
new UI must preserve the nouns, status vocabulary, and boundaries above.

## 14. Open decisions and defaults

Dark mode may be deferred; branches are not UI truth until the backend exists;
react-three-fiber or an equivalent renderer is allowed for browser 3D; closing
the last view is allowed; maximum open views is four; LiDAR variants show
explicit post-edit sensor support or parent-sweep fallback; layout is stored per
document tab; maximize/restore is included; the main view plus side views is the
default layout model.

# Workspace UI/UX Specification (CAD-style Real2Sim workspace)

Status: `CURRENT / PROPOSED v2`
Audience: frontend and UX engineers.
Supersedes: the former U0 three-rail MVP flow specification.

This is the authoritative workspace specification. It must be read with
`MVP&ProjectSummary.md`, `docs/current/project-status.md`, and
`docs/current/technical-contracts.md`. The current implementation milestone is
**U1: Workspace shell and Top-down view**. Later milestones must not be pulled
forward by inventing API data.

## 1. Product intent

The workspace lets an analyst take a recorded nuScenes interaction, rebuild it
as an editable top-down / 3D scene, vary it parametrically, replay it in
esmini, and audit every number back to a private artifact. The metaphor is a
parametric CAD document: a scenario is a document, its construction is an
ordered recipe, variants are configurations, validation is a gate lane, and a
scenario can be inspected through several views.

Auditability beats spectacle. This is not an autonomous-driving demo or a
sensor viewer.

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
- 3D renders only recorded or pipeline-produced data. No decorative reality.

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
|-- View manager: 0-4 views, dominant workspace area
|-- Right icon strip: Metrics | Gates | Provenance | Artifacts, persistent badges
|-- Right flyouts: read-only, overlay or docked, minimum 280px
|-- Gate lane bar and document tabs
|-- Status bar: selection, branch, rollback, provisional count, frame, transform version
```

The default workspace opens with exactly one Top-down view. Closing the last
view is allowed and shows `No views open. Add a view.`. Tablet layouts turn
panels into overlay drawers, stack views vertically, and preserve catalog ->
inspect -> edit order.

## 5. Interaction contract

Modes are mutually exclusive and visible: Select (`S`), Edit (`E`), Measure
(`M`), and Compare (`C`). Icon buttons are 28px, have accessible names and
tooltips, and explain disabled reasons. Behavior mode is visible as
`unsupported` with: `UNSUPPORTED - executor is not implemented. No fallback is
used.` Search commands (`Alt+C`, `Ctrl/Cmd+K`) lists enabled and unsupported
commands.

Selection is single by default; Shift adds and Escape clears. Selecting an
actor in any surface updates every view. There is no ViewCube or corner
orientation widget. Camera presets live in view headers; `Home` resets a camera.
Undo/redo covers recipe edits and view-manager actions, not camera or panel
width changes.

## 6. View manager and U1 scope

Every view header contains an icon, view name and target, camera preset menu,
layers menu, maximize/restore, and close. View layouts are: one full view; two
side-by-side; three with the earliest large and two stacked; four in a 2x2 grid.
Panes have draggable and keyboard-operable splitters, minimum 280x200px, and
are stored per document tab. Reset layout restores one Top-down view.

U1 delivers the shell, icon strips, flyout shells with badges, document tabs,
status bar, view manager, add/close actions, 1-4 layouts, empty state, and the
Top-down view with recorded versus generated overlays. Top-down supports map
lanes, trajectories, actor boxes, and measure labels when supplied by the API.
Recorded is dashed neutral; generated is solid accent. Ego and unsupported
dimensions use shape or hatching as well as colour.

U1 shows 3rd-person POV and LiDAR 3D in Add view but marks them unavailable
with an honest reason. 3rd-person POV is U5. LiDAR is U6 and requires recorded
point-cloud access; post-edit sensor frames are never fabricated.

## 7. Existing tabs and inspection surfaces

Document tabs are Scenario studio, Variant studio, Replay, and Report. Each
remembers its view layout and panel widths; switching tabs does not change
scientific state. Metrics, Gates, Provenance, and Artifacts flyouts are
read-only. They show status and API reasons, never guessed values.

## 8. Milestones

| Milestone | Deliverable |
|---|---|
| U1 | Workspace shell, view manager, Top-down view |
| U2 | Recipe tree, rollback marker, edit-step dialog, live preview |
| U3 | Gate lane, timeline, actor tracks, Measure mode |
| U4 | Variant studio, branches, Compare, metric lane, Report |
| U5 | 3rd-person POV, xodr map layer, 3D actor boxes |
| U6 | Recorded LiDAR view, decimation and variant handling |

Only the current milestone is in scope. Recipe, timeline, 3D, LiDAR, branches,
and compare data must not be mocked as backend truth.

## 9. State matrix

| Surface | Loading | Empty | Error | Partial / skipped | Success |
|---|---|---|---|---|---|
| Recipe | skeleton rows | Import a scene to start a recipe | verbatim API error | inactive after marker | active steps + statuses |
| View manager | skeleton panes | No views open. Add a view. | error per pane | unavailable types with reason | 1-4 laid out |
| Top-down | skeleton canvas | Select an imported scenario | inline error | missing layers labelled | all available layers |
| 3rd-person / LiDAR | skeleton or Loading sweep | unavailable + reason | API reason | decimation or unsupported label | only when data exists |
| Timeline | skeleton tracks | n/a | error lane | skipped means not measured | tracks + gates |
| Metrics / Measure | n/a | n/a with reason | n/a with reason | insufficient coverage | value, unit, status |

## 10. API and backend boundary

Continue consuming the existing endpoints in the prior MVP contract through
`frontend/src/api.ts`. Add typed clients and tests before using new fields.
Backend tasks are required for recipe/steps, branch lineage, gate extents,
actor dimensions with availability, viewer-friendly xodr geometry, point-cloud
sweeps and payloads, and explicit variant sensor-frame status. Do not hard-code
missing values or reason strings beyond documented contract values.

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

U1 is Top-down-only; dark mode may be deferred; branches are not UI truth until
the backend exists; recipe authoring is deferred; react-three-fiber is the
default future 3D stack; closing the last view is allowed; maximum open views
is four; LiDAR variants show unsupported with an optional parent sweep banner;
layout is stored per document tab; maximize/restore is included when available.

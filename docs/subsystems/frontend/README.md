# Frontend Workspace

Code: `frontend/src/`

The frontend is a React/Vite single-page workspace. It renders backend-owned
scenario, timeline, recipe, compare, LiDAR, live-session and availability data.

## Source Map

| File | Responsibility |
|---|---|
| `App.tsx` | Workspace shell, local UI state, feature components and event wiring |
| `api.ts` | Typed request helpers and API response types |
| `icons.tsx` | Shared SVG icon set |
| `styles.css` | Layout, theme tokens, responsive and reduced-motion rules |
| `main.tsx` | React mount and stylesheet entry |

`App.tsx` is intentionally still flat. Split it by feature only when a change
requires a stable seam; do not create a component hierarchy merely to mirror
the documentation tree.

## Data Flow

```text
user action
  -> local React state
  -> api.ts request helper
  -> FastAPI route
  -> typed availability/provenance payload
  -> view state and explicit loading/error/unavailable UI
```

The browser never reads artifact files directly. Artifact URLs are returned by
the API and remain subject to backend path confinement.

## Feature Areas

- Catalog: scenario discovery and selection.
- Workspace views: recorded/generated paths, internal POV transforms and view
  layout management.
- Timeline: actor channels, gates, playhead synchronization and Measure mode.
- Recipe: constrained maneuver steps, rollback markers and undo/redo state.
- Compare: synchronized scenario-side deltas and metric/gate provenance.
- Sensor Evidence: recorded `LIDAR_TOP` sweeps only; post-edit sensor frames
  remain explicitly unsupported.
- Live state: native esmini state when capability is available; browser camera
  state and image artifacts remain separate.

## UI Rules

- Never use missing numeric values as domain zeroes.
- Preserve backend status and unavailable reasons in visible text.
- Do not label browser transform frames as simulator image evidence.
- Use CSS tokens from `styles.css`; do not add hard-coded theme colors.
- Keep keyboard, narrow viewport and reduced-motion behavior covered.

## Tests and Commands

```bash
cd frontend
npm test -- --run
npm run build
```

Primary tests: `frontend/src/api.test.ts` and
`frontend/src/workspace.test.tsx`.

Detailed historical notes remain in
[`../../current/frontend-workspace-handbook.md`](../../current/frontend-workspace-handbook.md)
and [`../../current/frontend-workspace-log.md`](../../current/frontend-workspace-log.md).

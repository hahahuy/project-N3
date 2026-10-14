# Frontend Workspace Handbook

Status: `ACTIVE`
Owner: frontend agents
Primary specification: `docs/current/ui-mvp-flow-spec.md`
Backend contract register: `docs/current/backend-workspace-contract-log.md`
Architecture decision: `docs/architecture/m4-local-demo-architecture.md`

## Purpose

This handbook is the working entry point for anyone changing the browser
application under `frontend/`. It records how to run it, how its pieces fit
together, which backend endpoints exist, and which traps have already cost time.

Read it before the code. `docs/current/ui-mvp-flow-spec.md` decides *what* the
product should be; this file records *how the current implementation works* and
where it stops.

## Reading Order For A New Frontend Agent

1. `docs/README.md` - project-wide entry point and rules.
2. `docs/current/ui-mvp-flow-spec.md` - the authoritative Workspace spec. This
   is the contract your change is measured against.
3. This handbook.
4. `docs/current/frontend-workspace-log.md` - what changed, when, and what is
   still open.
5. `docs/current/backend-workspace-contract-log.md` - which backend fields you
   may consume.
6. `docs/evidence/m4-ui/` - previous runtime evidence, to see what "verified"
   looks like here.

## Running The Stack

Two processes. The backend must be running or every request fails.

```bash
# terminal 1 - API on :8000
python -m pip install -e ".[dev,web]"
uvicorn r2s_web.app:app --app-dir src --reload --port 8000

# terminal 2 - UI on :5173
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173`.

### The Dev Proxy (a real trap)

`frontend/vite.config.ts` proxies `/api` to `VITE_API_PROXY`, defaulting to
`http://127.0.0.1:8000` because that is where the documented local `uvicorn`
command listens.

It previously defaulted to `http://api:8000`, which is the **Docker Compose
service name**. That name only resolves inside the compose network, so the
normal local setup could not reach the API at all. If requests fail, check this
value before suspecting the backend.

- Local uvicorn: no override needed.
- Docker Compose: `compose.dev.yml` sets `VITE_API_PROXY=http://api:8000` for
  the frontend service.
- Compose maps the API to host port `8001` by default
  (`R2S_WEB_API_PORT`), while local uvicorn uses `8000`. Two docs still cite
  `8001`; both are correct for their own setup.

`strictPort` is on so a second Vite instance fails loudly instead of silently
moving to `5174` (which would break same-origin proxying assumptions).

`frontend/src/api.ts` reads `VITE_API_URL` (default `/api`). Setting it to an
absolute cross-origin URL bypasses the proxy and then depends on CORS, which
only allows `http://localhost:5173` and `http://127.0.0.1:5173`. Prefer the
proxy.

## Source Layout

The spec (`ui-mvp-flow-spec.md` §13) prescribes
`frontend/src/{workspace/, state/, tokens.css}`. **That layout was not built.**
The app is currently flat:

| File | Role |
|---|---|
| `App.tsx` | The whole shell: state, layout, and every component. One file by design so far. |
| `api.ts` | Typed request helpers. Every call goes through `request()`. |
| `api.test.ts` | The only committed frontend test. |
| `icons.tsx` | The whole SVG icon set, exported as `Icon` + `IconName`. |
| `styles.css` | All styling and the design tokens. |
| `main.tsx` | Mounts the app; imports `styles.css`. |

If `App.tsx` keeps growing, splitting it is the natural next refactor. Doing so
is a structural decision - record it in `frontend-workspace-log.md`.

## Design Tokens And Theming

`styles.css` defines every colour as a CSS custom property in `:root`, with a
`[data-theme="dark"]` block overriding the same names. **Never hardcode a hex
colour in a rule** - add a token instead, or the dark theme silently breaks.

The dark palette is not invented: it is the reference CAD application's own dark
tokens (`boston-terrier` #333 chrome, `tea-party` #1c1c1c viewport,
`seaport-500` #90cef1 accent, and so on).

`App` writes `document.documentElement.dataset.theme` and persists to
`localStorage` under `r2s-theme`, falling back to `prefers-color-scheme` on first
visit. `color-scheme: dark` is set so native scrollbars and form controls follow.

## Backend Endpoints

All routes are declared flat in `src/r2s_web/app.py`. The `/api` prefix is
written into each decorator; there is no router and no version segment.

### Used by the current UI

| Method | Path | Used for |
|---|---|---|
| GET | `/api/scenarios` | Catalog list |
| GET | `/api/scenarios/{id}` | Scenario detail |
| GET | `/api/scenarios/{id}/trajectory` | Recorded/replayed paths + replay metrics |
| GET | `/api/scenarios/{id}/artifacts` | Artifact links (Artifacts flyout) |
| GET | `/api/settings` | Dataset chip |
| GET | `/api/esmini` | Simulation chip |
| GET | `/api/artifacts/{path}` | Artifact download |

### Available but not surfaced yet

These have working client helpers in `api.ts` and working backend routes, but no
UI surface. They belong to later milestones - check `active-work.md` before
starting one.

| Method | Path | Client helper |
|---|---|---|
| GET | `/api/health` | - |
| GET | `/api/cp1/review` | `fetchCP1Review` |
| POST | `/api/settings` | `updateSettings` |
| GET | `/api/source-scenes` | `fetchSourceScenes` |
| POST | `/api/source-scenes/{token}/import` | `importSourceScene` |
| POST | `/api/scenarios/{id}/variants/preview` | `previewVariant` |
| POST/GET | `/api/replays`, `/api/replays/{id}` | `createReplay`, `fetchReplay` |
| POST | `/api/batches` | `createBatch` |
| GET | `/api/batches/{id}/results` and sub-routes | `fetchBatchResults`, `fetchBatchTrajectory` |
| POST | `/api/batches/{id}/results/{vid}/export` | `exportBatchResult` |

### Does not exist - do not look for it

- **No CARLA endpoint.** There is no `/api/carla*`, `/api/simulators*` or
  generic `/api/capabilities`. CARLA exists only in `src/real2scenario/`, and
  the Simulation chip lists it as unavailable. Full green on that chip is
  unreachable until a capability route exists.
- **No single-scenario export.** The only export route is batch/variant
  scoped. The toolbar Export therefore downloads a client-side JSON bundle of
  the already-loaded scenario and trajectory. It is not XOSC export and must not
  be described as such.
- **No `POST/PUT/DELETE` verbs at all**, and CORS allows only `GET`/`POST`.

## Interaction Contracts Worth Knowing

- **Rail panels toggle open/closed.** Clicking the active left-rail icon
  minimises the side panel; clicking it again restores it.
- **The splitter is drag-driven.** Drag past the minimum width and the panel
  minimises; drag back out and it restores. Keyboard: arrows resize, `Home`
  resets.
- **Status chips**: hover applies the highlight immediately; the list appears
  after 500ms or on click; leaving closes it in both cases. There is no latch.
- **Toolbar overflow**: tools that do not fit move into "More tools" rather than
  scrolling. The set is measured with a `ResizeObserver`.

## Traps Already Hit (please do not repeat them)

These are real bugs that were shipped and then fixed. Each is a symptom of one
underlying mistake.

1. **Fixed grid tracks vs. conditional children.** `.view-manager` once declared
   `grid-template-rows: 43px minmax(0,1fr) 34px` and then rendered a fourth
   child when an inline error appeared. The error consumed the `1fr` track, the
   viewport collapsed, and the timeline bar spilled into an implicit row. It is
   a flex column now. **Any container whose children appear conditionally should
   be flex or `auto` tracks, never a fixed track count.**
2. **`display: none` removes a grid item.** Hiding the left panel that way shifted
   every later item one track left, so the right rail inherited the `1fr` and
   stretched across the viewport. Collapse the track instead
   (`--panel-width: 0`) and keep the item in flow.
3. **Editing a rule that exists twice.** `.left-collapsed .left-panel` appeared in
   both the base sheet and the media query. A string edit hit the wrong one and
   the bug survived. Grep the compiled rules when a selector is ambiguous.
4. **Unguarded `response.json()`** produced `Unexpected end of JSON input` on an
   empty body. `request()` now reads text, parses defensively, and raises a
   message naming the path and status.
5. **Errors were never cleared** on success, so one transient failure left a
   permanent banner.
6. **jsdom does not load CSS.** Style assertions in a jsdom test pass vacuously.
   Verify styling by grepping the built CSS or by looking at the browser.

## Adding A Feature: Checklist

1. Confirm the milestone in `docs/current/active-work.md`. Implement only the
   current milestone.
2. Read the relevant spec section in `ui-mvp-flow-spec.md` and cite it.
3. Check `backend-workspace-contract-log.md` before consuming any new field.
   **Never change a backend contract to simplify a component.**
4. If the feature needs backend data that no route provides, say so and stop -
   do not fake it in the browser.
5. Add styling as tokens, never literals.
6. Add or extend a test in `api.test.ts` (API boundary) and a component
   behaviour test for anything with state.
7. Verify: `cd frontend && npm run build && npm test`, plus a browser pass with
   the backend running.
8. Append a row to `docs/current/frontend-workspace-log.md` with milestone, spec
   sections, backend fields used, and verification performed.
9. Run `scripts/check_docs_consistency.py` before finishing.

## House Rules

- Keep unavailable features **visible with a reason**, never silently absent.
- Never render a metric, gate, or score without its status. `PROVISIONAL`,
  `unsupported`, `unavailable`, and `skipped` are distinct words; do not merge
  them.
- Absent is not zero.
- Do not claim `DONE` from unit tests alone; runtime claims need the command,
  version, and output.
- Keep the exact Workspace nouns (`Scenario studio`, `Top-down`, `G1-G7 gate
  lane`, and so on).
- Evidence for milestone work goes under `docs/evidence/m4-ui/`.
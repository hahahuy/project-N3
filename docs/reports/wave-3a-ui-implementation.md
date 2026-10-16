# Wave 3A UI Implementation Report

## Scope

Started the U0 frontend integration against the Wave 3A preview endpoint.

## Files Changed

- `frontend/src/api.ts`: typed preview request/response models and API call.
- `frontend/src/api.test.ts`: preview request boundary test.
- `frontend/src/App.tsx`: actor selection, motion controls, preview/validate,
  reset, client-side config export, preview result/gate display and timeline.
- `frontend/src/styles.css`: responsive U0 editor, actor list, preview result,
  gate and timeline styles.

## Implemented Flow

```text
select scenario -> select actor -> edit speed/heading/gap/timing/seed
  -> preview variant -> display generated overlay and G4-G7/validation
  -> reset or export configuration
```

Behavior mode is visibly marked unsupported and is not offered as a fallback.
Parent paths remain rendered alongside generated preview paths.

The current preview overlay is trajectory-state visualization. It does not
generate post-edit sensor or simulator image frames, and the timeline currently
reports the selected time over the complete SVG paths rather than fetching a
timestamp-addressable rendered frame.

## Tests

- Backend regression: `.venv/bin/python -m pytest -q` -> `153 passed, 2 warnings`.
- `git diff --check` passed.
- Frontend `npm test` and `npm run build` could not run because frontend
  dependencies are not installed.

## Runtime Evidence

The host-only runtime was verified with a temporary writable dependency setup.
The project API returned healthy on port 8001, the frontend rendered on port
5173, the synthetic scenario loaded, preview returned a deterministic child,
and the final browser run had zero console errors. Full evidence is in
`docs/evidence/m4-ui/u0-motion-editor-showcase.md`.

The committed frontend dependency directory remains unwritable, so `npm ci`,
`npm test` and `npm run build` were not run from the repository directory.

## Unverified

- TypeScript compilation and Vitest execution.
- Browser flow and responsive layout.
- U0 evidence bundle and `SHOWCASE-READY` exit decision.
- CP1, CP2, CARLA same-XOSC, sensor and OSM claims remain out of scope.

## Next Agent

Install frontend dependencies with a writable `frontend/node_modules`, run
`npm test` and `npm run build`, then exercise the local browser flow and add
`docs/evidence/m4-ui/u0-motion-editor-showcase.md` only after runtime evidence
exists.

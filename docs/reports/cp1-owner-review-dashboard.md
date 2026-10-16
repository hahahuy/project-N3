# CP1 Owner Review Dashboard

## Status

`IMPLEMENTED`, `READ-ONLY`, `DIAGNOSTIC`, `PROVISIONAL`

The existing FastAPI/React server now exposes a compact owner-review checklist
for the CP1 scene-0061 corridor. It is intended to reduce friction when the
repository and private data are running on the server.

## Access

Build the frontend and start the existing app from the repository root:

```bash
cd /path/to/project-N3
npm --prefix frontend run build
.venv/bin/uvicorn r2s_web.app:app --app-dir src --host 0.0.0.0 --port 8000
```

Then open:

```text
http://<server-host>:8000/
```

Click `CP1 OWNER REVIEW` in the local paths bar. The underlying read-only JSON
contract is:

```text
GET http://<server-host>:8000/api/cp1/review
```

The service must be bound to `0.0.0.0` for access from another machine. Use the
server's firewall or SSH tunnel according to the deployment environment; this
change does not add authentication or public exposure controls.

## Checklist Contents

The page presents one card per owner decision:

- immutable `20/143 = 13.99%` corridor baseline and `57.37%` all-vehicle context;
- self-verified HMM/Viterbi evaluation for ego and the selected corridor actors;
  all-vehicle sequence evaluation remains outside the completed exploratory run;
- explicit lane topology and connector provenance;
- annotation/motion/lane direction review;
- geometry validation separate from trajectory failures;
- footprint and missing-dimension handling;
- automated low-confidence/manual-review intervals;
- CP1 scientific non-claims and provisional status.

Each card names what to verify, the owner action and the relevant repository
evidence paths.

The current self-verification has already closed the objective data checks for
the baseline, actor scope, corridor structure, crop attribution, direction
aggregate, occupancy aggregate and selected-scope sequence classifications.
The remaining owner action is policy confirmation, not a requirement to inspect
all failed states visually. See
`docs/reports/cp1-private-sequence-self-verification.md`.

## State And Safety

The dashboard is deliberately read-only. Checkbox state is stored in the
browser's local storage only, under `r2s-cp1-review-v1`; it is not a server-side
approval record and does not modify scenario data, actor selection, thresholds,
lane direction, map artifacts or CP1 status. The page cannot mark CP1 accepted.

The immutable baseline remains required in every later comparison. Completing
the browser checklist means only that the owner has locally marked each review
card; it is not scientific acceptance evidence.

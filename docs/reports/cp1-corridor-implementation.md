> Historical implementation report. Superseded by the private external run in
> `cp1-corridor-external-evidence.md`; retained for audit history.

# CP1 Scene-Local Corridor Implementation

## Scope

Implement the prioritized CP1 scene-local corridor boundary around `scene-0061`
without changing full-map/default builder behavior.

## Implemented

- Added `build_scene_local_corridor()` to the mapbuilder.
- Enforces `nuscenes_global` input for the first corridor path.
- Enforces a configurable `30-50 m` buffer; first-run default is `40 m`.
- Selects initial lane/connector records by closed trajectory-buffer centerline
  proximity semantics.
- Applies one-hop incident connectivity closure without recursive expansion.
- Passes the explicit selected token set to the existing XODR builder.
- Adds private corridor manifest fields for scene, actors, buffer, boundary
  policy, closure mode, initial/closure/final tokens and visibility.

## Tests

```text
.venv/bin/python -m pytest -q
175 passed, 2 warnings
```

Synthetic tests verify selected-token closure, manifest contract and buffer
validation. An existing private `log.txt` trailing-space artifact is the only
`git diff --check` finding.

## Next Run

Run the corridor against private `scene-0061` metadata and One-North map data,
then produce corridor-only XODR, topology audit, esmini probe and aggregate
road-match evidence under `$LOCAL_EVIDENCE_ROOT`. Do not commit
derived artifacts.

## Non-claims

No CP1 acceptance, complete junction semantics, CARLA compatibility, CP2 or
same-XOSC claim is made.

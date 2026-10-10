# M5 Phased Simulator Plan

## Purpose

This plan keeps the simulator work proportional to the current product goal.
The immediate goal is to prove that a scenario selected in the local browser
can run through esmini and produce reviewable evidence. It is not to build a
general simulator platform or a live 3D streaming product.

M4 must receive final human/demo review sign-off before implementation begins.

## M5A: Esmini Hardening and Demo Evidence

### Goal

Make the existing optional esmini replay reliable, visible, and easy to review
from the local React/FastAPI demo.

### In Scope

- Add a small esmini capability check: configured/not configured, executable
  availability, `dat2csv` availability, version, and a safe diagnostic message.
- Extract esmini orchestration from `r2s_web.jobs.BatchService` into a focused
  `EsminiBackend` or equivalent local service.
- Preserve the existing execution sequence:

  ```text
  canonical scenario
  -> select OpenDRIVE template
  -> export .xosc and .xodr
  -> run esmini
  -> normalize replay trace with dat2csv
  -> compute replay metrics
  ```

- Run esmini for one selected valid baseline or generated variant from the UI.
  Do not enable replay for every generated variant by default.
- Run simulator work as a separate local job so an HTTP request does not wait
  for a long-running simulator process.
- Show simulator status, version, output links, replay metrics, and structured
  failure details in the UI.
- Keep output under a job-specific directory, including stdout/stderr, replay
  trace, `.xosc`, `.xodr`, report, and recorded-versus-replayed overlay PNG.
- Add fake executable tests for success, missing configuration, non-zero exit,
  timeout, malformed trace, and missing template cases.
- Add one optional real local esmini browser smoke test when environment
  variables are configured.

### Optional Visual Proof

- An `Open in local esmini viewer` action may launch the native esmini window on
  the same machine as FastAPI.
- This action is optional convenience for a live mentor demo; it is not embedded
  in React and it is not required for automated tests.
- A static overlay PNG is the required visual artifact. One manually captured
  screenshot or short clip for a curated scenario may be used in presentation
  material, but stays outside Git unless explicitly approved.

### Explicit Non-Goals

- No live esmini viewport embedded in the browser.
- No video streaming, recording service, encoding pipeline, or media storage.
- No GPU requirement.
- No CARLA integration.
- No shared deployment, database, queue service, object storage, accounts, or
  local-agent infrastructure.

### Acceptance Criteria

- The UI reports whether esmini is available and why it is unavailable.
- A reviewer can select one valid scenario and submit an esmini run from the
  browser.
- The run is non-blocking and exposes completed, failed, and timed-out states.
- A completed run provides replay trace, metrics, logs, exported `.xosc`/`.xodr`,
  and an overlay PNG through safe artifact links.
- Failures retain exit code, timeout state, tool version, stdout/stderr, and a
  structured message.
- Existing M4 generation, validation, ranking, export, and no-simulator flows
  remain operational.

## M5B: CARLA Feasibility Spike

### Goal

Decide whether CARLA is worth building for this project. This is research and
technical validation, not a commitment to deliver a CARLA UI or adapter.

### In Scope

- Document one reproducible local CARLA environment: supported version, Python
  compatibility, server launch method, and one curated world.
- Run a minimal manual proof of concept with one supported vehicle-only scenario
  in open-loop trajectory playback.
- Identify the required mapping from canonical actors to CARLA blueprints and
  document unsupported actor types, map topologies, and sensor expectations.
- Measure setup effort, runtime stability, trace availability, and visual value
  compared with esmini.
- Produce a short decision record: proceed to M6, defer CARLA, or reject CARLA
  for this project.

### Explicit Non-Goals

- No common simulator abstraction required yet.
- No React simulator selector.
- No CARLA backend merged into the core application.
- No full nuScenes-to-CARLA map conversion.
- No sensor reproduction, camera/LiDAR output, closed-loop autonomy, or general
  OpenSCENARIO support.

### Exit Decision

Proceed to M6 only if CARLA provides clear value that esmini cannot provide for
the assessed project goal, and the curated scenario can run reliably in the
available local environment.

## M6: CARLA Adapter and Simulator Selection

### Prerequisite

M5A is complete, M5B recommends proceeding, and the team explicitly approves
the added setup and maintenance cost.

### Goal

Support a narrowly defined CARLA playback path alongside hardened esmini
execution, without claiming lossless nuScenes map conversion.

### In Scope

- Introduce a common simulator contract only after both esmini and CARLA have
  concrete supported execution paths.
- Add `EsminiBackend` and `CarlaBackend` behind that contract.
- Add capability discovery and a local UI selector that exposes only available
  supported backends and modes.
- Support one or more curated CARLA worlds, explicit vehicle blueprint mapping,
  fixed timestep policy, cleanup, normalized trace, metrics, logs, and artifact
  downloads.
- Return structured `unsupported` results for unsupported actors, maps, sensors,
  or behaviors instead of silently approximating them.
- Keep recorded, generated, esmini, and CARLA trajectories visually distinct.

### Explicit Non-Goals

- No full nuScenes map conversion to CARLA.
- No shared customer platform, distributed execution, multi-user accounts,
  object storage, or GPU service.
- No promise that every OpenSCENARIO file runs in CARLA.

### Acceptance Criteria

- The UI clearly reports supported backends, versions, modes, and limitations.
- Esmini remains functional through the common contract.
- One curated supported CARLA scenario can run locally, or a documented
  environment blocker is retained while fake/optional tests pass.
- All simulator-specific output remains local, reviewable, and downloadable.

## Recommended Order

1. Obtain final M4 human/demo review sign-off.
2. Implement M5A only.
3. Use M5A evidence and mentor feedback to decide whether visual proof is
   sufficient.
4. Run M5B only if the team still needs CARLA-level visualization or sensor
   capability.
5. Start M6 only after an explicit M5B go decision.

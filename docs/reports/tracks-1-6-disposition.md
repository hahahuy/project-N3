# Acceptance Tracks Disposition

Status: `CURRENT / ENGINEERING INVENTORY / PROVISIONAL / OWNER-REQUIRED`
Date: `2026-10-15`

This report records what the current checkout can prove without inventing native
runtime, sensor, metric, scientific or paper evidence. The seven tracks are
separate acceptance groups; implementation completion does not imply project
acceptance.

| Track | Status | Owner | Scope | Dependencies | Required evidence | Acceptance criteria | Exact next action | Blocker type |
|---|---|---|---|---|---|---|---|---|
| 1. Private runtime and browser acceptance | `PROVISIONAL` | Runtime/UI owner | Verify the Workspace live-session UI against configured private nuScenes data and native esmini: scenario-pair creation, polling, timeline synchronization, native object rendering, step and reset behavior. **Additionally: verify the recorded-evidence fixes currently in the working tree** — `LIDAR_TOP` token resolution, multisweep history depth and the `/top-down` route — against real private data before they are committed. | Private dataset, compatible mounted esmini runtime, configured browser/API environment. | A dated private run record with scenario/XOSC/XODR hashes, capability response, session state samples, timeline/renderer observations, step/reset observations and exact unavailable reasons. For the recorded-evidence fixes: confirmation that a known scene resolves to the correct `LIDAR_TOP` sweep, that `nsweeps=5` returns five distinct recorded sweeps, and that `/top-down` returns an official devkit map-underlay render. | All listed flows are observed on the configured private runtime, or each missing flow is recorded with its exact fail-closed reason. No transform preview or screenshot is counted as native state. The recorded-evidence fixes are confirmed against real data, and `/top-down` gains backend test coverage, before commit. | Run the browser walkthrough with private dataset and native runtime; attach the private evidence manifest and update this row. Separately, add `/top-down` backend coverage before the working tree is committed. | `ENVIRONMENTAL/DATA-RELATED` |
| 2. Native esmini control boundary | `OWNER-REQUIRED` | Runtime owner + project owner | Decide whether a compatible public control ABI can be implemented and verified; distinguish native reset from reset-by-reload. | ABI documentation/version compatibility and owner acceptance of the control boundary. | ABI inspection note, load/step/control/reset probe results and capability payload. | Either control is verified through a compatible public ABI, or `esminiLib_control_abi_unavailable` is formally accepted; reset-by-reload is labelled as reload, not native reset. | Record the ABI decision in the decision log and retain the unavailable capability unless a supported ABI is demonstrated. | `TECHNICAL/OWNER-RELATED` |
| 3. Image capture/display acceptance | `PROVISIONAL` | Simulator/runtime owner | Test configured/off-screen esmini image capture and display artifact publication. | Viewer or supported off-screen runtime, private capture configuration and artifact storage. | Real esmini image files plus timestamped `workspace-pov-image-v1` manifest, or runtime logs showing the exact failure. | Only real esmini image artifacts are marked rendered; otherwise retain `capture_viewer_unavailable` and document the environment limitation. Transform previews and screenshots are not substitutes. | Run capture on a runtime with viewer/off-screen support; if unavailable, preserve and publish the exact failure record. | `ENVIRONMENTAL` |
| 4. Post-edit sensor generation | `DEFERRED` | Project owner + sensor owner | Decide whether timestamp-addressable post-edit camera/LiDAR/radar artifacts are required for this MVP. Implement only calibrated, verifiable generation. | Owner scope decision, calibrated source data or an approved simulator renderer. | Decision record; if implemented, calibrated artifact manifest, timestamps, transforms and provenance; otherwise explicit unsupported response evidence. | If not approved or not technically reproducible, variant sensor status remains `unsupported` with `post_edit_sensor_frames_not_generated` and a separately proven recorded parent-sweep fallback. | Approve defer/implement scope. Until then, do not start a sensor generator or change the status contract. | `OWNER-RELATED/TECHNICAL/DATA-RELATED` |
| 5. CP1/CP3/CP4/CP5 engineering closure | `OWNER-REQUIRED` | Project owner | Close semantic/map interpretation, benchmark index/protocol/scientific policy, final gate policy and release sign-off. | Private diagnostic bundle, provisional benchmark run, CP4 evidence, reproducibility manifest and committed verified tree. | CP1 owner decision; CP3 approved scene index/protocol; CP4 approved gate/scientific policy; CP5 committed-HEAD release evidence and sign-off. | CP1 preserves immutable `20/143 = 13.99%`; provisional metrics remain provisional; CP5 release evidence is from the committed verified tree and is signed off. | Convene one owner review covering CP1, CP3, CP4 and CP5; record decisions and sign-off without changing metrics or thresholds implicitly. | `OWNER-RELATED` |
| 6. CP6 paper/evidence closure | `OWNER-REQUIRED` | Project owner + paper owner | Finalize research questions, evidence/reproducibility bundle, limitations, unavailable capabilities and provenance. | Accepted CP1/CP3/CP4/CP5 decisions and complete evidence inventory. | Approved RQs, final evidence bundle manifest, limitation/provenance section and separation of engineering diagnostics from paper claims. | Every paper-level claim maps to accepted evidence; provisional metrics and diagnostic gates are not promoted. | Approve RQs and paper evidence policy, then assemble the final bundle from accepted records only. | `OWNER-RELATED/DATA-RELATED` |
| 7. UI scope decision | `OWNER-REQUIRED` | Project owner + product/UI owner | Decide whether Behavior, Validate and Replay remain disabled for this MVP or receive a separately approved implementation scope. | Current UI/backend capability contracts and MVP scope decision. | Written scope decision; if retained disabled, UI/API screenshots or tests showing explicit unavailable/deferred states; if required, approved scope and acceptance plan. | Disabled controls are classified as deferred/unavailable rather than broken; no control silently maps to another mode. Any required implementation has its own approved scope before work begins. | Approve `deferred for MVP` or create a separate scoped work item; keep current fail-closed behavior until then. | `OWNER-RELATED` |

CARLA same-XOSC remains post-MVP and is not part of this disposition.

## Cross-cutting finding: repository hygiene blocks a clean release

This is not one of the seven tracks but it gates Track 5 CP5 release sign-off,
because release evidence is only meaningful if it is produced from a tree whose
contents are intended.

`git ls-files` shows **214 generated or machine-local files are tracked**:
`.playwright-mcp/` (213 console/screenshot log files) and `log.txt`. None of
these are covered by `.gitignore`, so they are not merely untracked noise — they
are in the commit history and in any `git archive` export of `HEAD`.

Consequences:

- The public release tree contains operator console logs and a local run log.
  `docs/current/artifact-policy.md` states the repository is the Apache-2.0
  public-release surface.
- `scripts/verify_release.py` clean-checkout verification inventories the tree,
  so these files are counted as release content.
- The stated project baseline in the PM instructions describes `log.txt` and
  `.playwright-mcp/` as "unrelated/generated worktree items" not to be
  committed. That framing is incorrect: they are already committed.

Owner decision required: whether to purge them from the tree (with a
`.gitignore` entry) as part of CP5, or to accept them as published content. The
recommended path is to purge and ignore, but purging rewrites published history,
so it is **owner-related**, not an agent decision.

Additionally, `frontend/package.json` now depends on `react-grab@^0.2.0`,
imported in `main.tsx` under `import.meta.env.DEV`. This is a new third-party
dependency added without a recorded approval decision, which the project's
non-negotiable boundaries reserve for an approved decision. It is dev-only and
tree-shaken out of the production bundle, so it is low runtime risk, but it must
be explicitly approved or removed before release sign-off.

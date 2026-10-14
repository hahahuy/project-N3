# Plan B -> Plan A Migration Checklist

> **Baseline:** `MVP&ProjectSummary.md` (Plan A) thắng các tài liệu cũ khi có mâu thuẫn.
>
> **Scope:** checklist trạng thái chuyển đổi, không phải quyết định thay thế cho các mục còn mở.
> Không đưa dữ liệu nuScenes hoặc artifact dẫn xuất bị hạn chế vào repository.

> **Current scope note:** Plan A still names esmini and CARLA as long-term
> targets, but DEC-011 supersedes current MVP simulator acceptance: esmini and
> the internal kinematic preview are current MVP backends; CARLA is post-MVP.

## Status Legend

- `DONE`: có implementation/evidence phù hợp Plan A.
- `PARTIAL`: có nền tảng hoặc chỉ đạt một phần tiêu chí.
- `OPEN`: chưa có implementation/evidence.
- `BLOCKED`: phụ thuộc môi trường, dữ liệu, quyết định hoặc thành phần chưa sẵn sàng.
- `REVIEW`: cần xác nhận lại trước khi sửa vì có nguy cơ đổi nghĩa artifact/API.
- `AGENT-DECIDABLE`: agent được phép tự quyết sau khi nghiên cứu và ghi rationale/evidence.
- `OWNER-REQUIRED`: không được tự quyết vì thay đổi phạm vi, pháp lý, hoặc claim khoa học.

## Agent Autonomy Policy

Agents are explicitly allowed to search online technical documentation, papers,
upstream API references and simulator specifications when needed to resolve
implementation blockers. Network research is allowed for documentation and
technical knowledge; it does not authorize downloading restricted nuScenes data,
derived artifacts, credentials, or unapproved simulator assets into the repo.

For every self-resolved blocker, the agent must record:

- the decision and alternatives considered;
- URLs or document references, access date, and relevant version;
- why the decision is compatible with Plan A;
- affected files/API/artifact schema;
- tests and runtime evidence;
- remaining uncertainty and rollback/compatibility impact.

Agents may self-decide technical implementation details when they do not change
Plan A scope or scientific/legal claims. They may choose conservative defaults,
reject unsupported cases, or defer a feature with a structured `unsupported`
status. They must not silently approximate missing semantics.

The following remain `OWNER-REQUIRED` unless the owner explicitly delegates them
in a later decision record:

- changing the Plan A requirement that both esmini and CARLA are required;
- changing `PLAN_A_CP2_CONTRACT=SAME_XOSC`;
- publishing or relicensing nuScenes-derived data/artifacts;
- converting provisional ADE/FDE/G6/G7 values into final scientific thresholds;
- changing the approved source-code license;
- changing the approved map-area scope or research questions.

When an owner-required decision blocks execution, agents should implement the
largest safe subset, record `blocked_by_owner_decision`, and continue with tests
and evidence that do not depend on the unresolved claim.

## Non-Negotiable Decisions

- [x] Mục đích học thuật.
- [x] Sản phẩm gồm công cụ mã mở và bài báo.
- [x] Phải hỗ trợ cả esmini và CARLA.
- [x] Một người thực hiện, không giới hạn thời gian.
- [x] CP2 contract: `PLAN_A_CP2_CONTRACT=SAME_XOSC`; cùng input `.xosc` bytes/hash cho esmini và CARLA.
- [x] CP0 runtime contract: mỗi simulator phải có ít nhất một sample run thành công; same-XOSC chỉ bắt buộc từ CP2.
- [x] Behavior wording: CP2 waypoint/reference tối thiểu; behavior claims tách theo `replay_mode` và không fallback.
- [x] Scene wording: `scene-0061` là CP0–CP2 smoke/regression; final 5–10 Singapore scenes vẫn mở.
- [x] G6/G7 temporary funnel policy: được phép dùng cho development/debug, luôn gắn `scientific_status=PROVISIONAL`.
- [x] Apache-2.0 áp dụng source code; nuScenes data và derived artifacts local/private only.
- [ ] ADE/FDE scientific threshold: `OWNER-REQUIRED`; `0.5 m`/`1.0 m` chỉ là provisional.
- [ ] Loại tình huống hiếm ưu tiên: `AGENT-DECIDABLE` cho implementation experiments, `OWNER-REQUIRED` cho final paper scope.
- [ ] G6/G7 scientific thresholds: `OWNER-REQUIRED` for final claims; temporary values are `AGENT-DECIDABLE` for development diagnostics only.

## Current Baseline

- Current branch: `plan-a/P0`.
- Current worktree includes pre-existing uncommitted changes; do not overwrite unrelated work.
- Python 3.12 virtual environment: `.venv/`.
- Baseline test evidence after installing dependencies: `133 passed, 2 warnings`.
- CARLA 0.9.16 Docker server/client handshake: verified locally.
- CARLA adapter exists in the worktree but is not yet a committed phase deliverable.
- Current CARLA mapping result for local `scene-0061` on `Town10HD_Opt`: rejected by waypoint validation (`74/143` states failed; max waypoint distance `3.785169 m`).
- Canonical source scenario must remain unchanged; CARLA execution mapping is a separate artifact.

## CP0 — Alignment and Environment

Status: `PARTIAL`

- [x] Python/package/test environment documented. Evidence: `pyproject.toml`, `README.md`.
- [x] nuScenes `v1.0-mini` metadata available locally. Evidence: `data/v1.0-mini/`, `src/real2scenario/preflight.py`.
- [x] Esmini baseline and `dat2csv` available. Evidence: `docs/evidence/m2-replay/r2s-206-m2-replay-evidence.md`.
- [x] CARLA 0.9.16 container and Python client handshake verified locally. Evidence: local run log; do not claim repository evidence until recorded in a phase report.
- [ ] Add reproducible CP0 environment manifest with Python, Docker image digest, CARLA server/client, esmini, dataset version and git commit.
- [x] CP0 runtime contract defined: at least one completed sample per simulator with logs/version/trace and CARLA lifecycle/cleanup evidence.
- [x] `scene-0061` approved as CP0–CP2 smoke/regression scene.
- [ ] Execute and record successful CARLA sample run; capability probe alone is insufficient.
- [x] Select MVP map area working scope: Singapore One-North, log `7e25a2c8ea1f41c5b0da1e69ecfa71a2`, map record `53992ee3023e5494b90c316c183be829`.
- [x] Local trainval dataset inventory: 850 scenes, 94 Singapore One-North scenes with downloaded sample sensor files in the current batch.
- [x] Candidate metadata-only working set of 50 Singapore One-North scenes generated outside the repository; final benchmark index remains owner-required.
- [x] Create an agent-selected provisional 5-scene Singapore One-North metadata index. Evidence: `docs/reports/cp3-agent-selected-benchmark-index.md`; final scientific benchmark approval remains open.
- [ ] Record dataset/license inventory without copying restricted data.
- [ ] Add `docs/license-notes.md` with unresolved derivative-artifact terms.
- [x] Add Plan A replacement banners to historical Plan B docs.
- [x] Update `README.md` so scope, simulator requirement and map limitations match Plan A.

Dependencies: none beyond local environment and project-owner decisions.

## CP1 — nuScenes Map to OpenDRIVE

Status: `PARTIAL` for the scoped scene-local corridor; `OPEN` for CP1 acceptance.

- [x] Preserve the existing `straight-two-lane` template as a regression path. Evidence: `src/real2scenario/templates.py`, `src/real2scenario/templates/straight-two-lane-v1.xodr`.
- [ ] Choose one approved nuScenes map area and associate scenes with its map record.
- [x] Local vector map expansion is available at `$NUSCENES_ROOT/maps/expansion/singapore-onenorth.json`; inventory: 936 lanes, 1,066 lane connectors, 2,002 arcline paths, 4,886 polygons.
- [x] Add `src/real2scenario/mapbuilder/` with a deterministic prototype lane/path-to-road conversion.
- [x] Add CP1 deterministic ID/manifest/structural subset contract. Evidence: `src/real2scenario/mapbuilder/`.
- [x] Add gated line/arc geometry and verify the current line-mode corridor on real local data; full acceptance remains open.
- [x] Prototype emits deterministic line geometry from all 2,002 local arcline records; arc fitting remains open. Evidence: `docs/reports/cp1-map-builder-prototype.md`.
- [x] Emit conservative connector junctions and repair dangling references/links in the scoped corridor; full junction semantics remain open.
- [x] Estimate effective polygon widths with an explicitly labelled fallback; cross-section boundary validation remains open.
- [x] Validate position and heading continuity diagnostically at road/junction joins.
- [x] Add local XML/subset/esmini load checks without downloading an XSD; full schema semantics remain open.
- [ ] Add source-map/XODR overlay evidence.
- [x] Add lane-level road-match for ego and selected corridor actors; report raw rate and provisional `95%` status without declaring pass/fail.
- [ ] Keep template mode as default until project owner explicitly approves switching defaults.

Dependencies: approved map area, local map expansion, geometry verification, local simulator tooling.

Current scoped result: the `scene-0061` corridor is runtime/topology verified,
but raw road-match is `20/143` (`13.99%`) and CP1 acceptance remains open.
Full Singapore One-North coverage is deferred future work.

## CP2 — Cross-Simulator Replay

Status: `PARTIAL`

- [x] Canonical scenario to OpenSCENARIO export for esmini.
- [x] Esmini headless replay, normalized trace and overlay evidence.
- [x] Separate CARLA world-frame adapter with anchor, waypoint validation and provenance. Evidence: `src/real2scenario/carla_adapter.py`.
- [x] CP2 input contract approved: same `.xosc` bytes/hash plus declared `.xodr`/map companion hash for esmini and CARLA.
- [x] Define/version `r2s-xosc-subset-v1` and fail-closed parser/hash identity contract. Evidence: `src/real2scenario/xosc_subset.py`.
- [x] Expose validated XOSC initial positions/trajectory plan for a future CARLA interpreter. Evidence: `ValidatedXoscScenario`.
- [x] Define normalized CARLA trace and cleanup report contracts. Evidence: `src/real2scenario/carla_trace.py`.
- [ ] Implement CARLA XOSC adapter/interpreter; reject unsupported features explicitly at runtime. Technical parser/tool choices are `AGENT-DECIDABLE`.
- [ ] Add CARLA backend run/trace/cleanup contract around the adapter.
- [ ] Run the same hashed source `.xosc` through esmini and CARLA with logs and artifact manifests.
- [ ] Compare simulator traces using the same declared timebase and metrics.
- [ ] Keep waypoint/reference replay distinct from behavior-parameterized replay.
- [x] Behavior mode policy approved: unsupported with structured reason until implemented; never silently fall back to waypoint mode.

Dependencies: CP0, CP1 or an explicitly approved execution-world policy, CARLA runtime, simulator contract decision.

## CP3 — ADE/FDE Evaluator

Status: `OPEN` for Plan A metrics; `PARTIAL` for Plan B metrics.

- [x] Existing timestamp alignment uses recorded timestamps and linear replay interpolation. Evidence: `src/real2scenario/metrics.py`.
- [x] Existing heading and speed auxiliary metrics.
- [x] Ground truth contract approved: raw `sample_annotation`/`ego_pose` keyframes with rigid, versioned frame transform only.
- [x] FDE coverage policy approved: raw final timestamp when covered, otherwise `insufficient_coverage`.
- [ ] Preserve raw nuScenes keyframe annotation identity/timestamp provenance.
- [x] Canonical states support optional source timestamp/token provenance; ingestion populates it for extracted source states. Evidence: `src/real2scenario/models.py`, `src/real2scenario/ingestion.py`.
- [x] Define evaluator input as raw annotation ground truth, not smoothed ground truth.
- [x] Implement ADE per actor at raw keyframe timestamps. Evidence: `src/real2scenario/metrics.py`.
- [x] Implement FDE per actor at the declared final timestamp policy. Evidence: `src/real2scenario/metrics.py`.
- [x] Aggregate per actor and report mean, median, p95 and max. Evidence: `src/real2scenario/metrics.py`, `src/real2scenario/benchmark.py`.
- [x] Domain aggregate API reports ADE/FDE mean/median/p95/max; batch/report serialization remains open. Evidence: `src/real2scenario/metrics.py`.
- [x] Report coverage and exclude actors shorter than `2 s` with an explicit ID list/reason. Evidence: `ScenarioReplayMetrics`.
- [ ] Add leave-one-keyframe-out interpolation baseline.
- [ ] If smoothing is used, store it as a separate versioned artifact and report smoothing error separately.
- [x] Preserve existing RMSE/final displacement/heading/speed metrics as auxiliary metrics.
- [ ] Keep ADE/FDE threshold status `PROVISIONAL`, never report provisional values as achieved/not achieved.
- [x] Separate benchmark aggregates by evidence class and simulator; replay-mode-specific benchmark execution remains open. Evidence: `src/real2scenario/benchmark.py`.

Dependencies: CP2 trace contract and raw annotation provenance; FDE/short-track working policies are approved, but still require implementation evidence.

## CP4 — Variants and G1–G7 Validity Funnel

Status: `PARTIAL` for generation; `OPEN` for Plan A gates.

- [x] Speed, gap and timing perturbations with deterministic seed/config/IDs.
- [x] Existing kinematic feasibility checks for acceleration, deceleration, jerk and yaw rate.
- [x] Existing ranking is separated from currently invalid feasibility reports.
- [x] G5 working contract approved: oriented-rectangle footprint pre-check plus native simulator collision event when available.
- [x] G4 domain evaluator exposes versioned physics gate result. Evidence: `src/real2scenario/gates.py`.
- [x] G5 domain evaluator requires event metadata and reports missing-event errors. Evidence: `src/real2scenario/gates.py`.
- [x] G4 supports an optional configured maximum speed limit; batch integration remains open.
- [x] G5 evaluates the trajectory states at their actual pre-event timestamps; native collision runtime remains open.
- [x] G6 temporary funnel contract approved: OR of TTC/clearance plus `no_collision`, diagnostic/provisional only.
- [x] G6 reports collision status as unverified unless an evaluator supplies `no_collision=true`.
- [x] G7 temporary funnel contract approved: normalized parameter-space distance, diagnostic/provisional only.
- [x] Temporary reports must include rare/diversity config versions, thresholds, horizon, normalization bounds and `scientific_status=PROVISIONAL`.
- [x] G1: supported OpenSCENARIO subset validation with structured result; complete external XSD certification remains open.
- [x] G2: simulator completion status gate with esmini and CARLA status separately recorded; runtime evidence remains open.
- [x] G3: provisional lane/road-match gate using an explicit map geometry report; final CP1/CP4 acceptance remains open.
- [ ] G4: expose existing physics checks as a named gate with config/version and per-variant result.
- [ ] G5: define and implement unintended-collision detection using actor footprint/dimensions and event window.
- [x] G6: implement temporary rare-event gate using configurable TTC/minimum-distance policy; final scientific values remain `OWNER-REQUIRED`. Evidence: `src/real2scenario/gates.py`.
- [x] G7: implement temporary configurable diversity/near-duplicate contract; final epsilon claim remains `OWNER-REQUIRED`. Evidence: `src/real2scenario/gates.py`.
- [x] Store each gate state as `pass`, `fail`, `skipped` or `error` with reason and config version.
- [x] Produce provisional funnel counts G1→G7 and reconciliation tests.
- [ ] Keep ranking downstream of all required validity gates and separate from rarity/safety claims.

Dependencies: CP1 map matcher, CP2 simulator traces, CP3 metrics, unresolved G5/G6/G7 definitions.

## CP5 — Open-Source Research Packaging

Status: `PARTIAL`

- [x] Python package, tests, Docker/local web setup and deterministic fixture exist.
- [ ] Add a clean-checkout reproducibility record with exact Python/frontend/package/tool versions. A reusable local/private manifest builder now exists in `src/real2scenario/packaging.py`; see `docs/reports/cp5-reproducibility-manifest.md`.
- [ ] Add a benchmark runner/protocol for the approved scene set.
- [ ] Include git commit, seed, config hash, dataset/version and map/converter versions in every benchmark manifest. The manifest builder covers these fields when supplied by the caller; benchmark integration remains open.
- [ ] Separate synthetic/no-simulator, licensed-local-nuScenes and optional simulator evidence.
- [ ] Freeze frontend dependency versions and preserve lockfile.
- [ ] Add release artifact classification: source code, synthetic fixtures, metadata-only indexes, derived nuScenes artifacts and runtime outputs.
- [x] Resolve code license and derivative-data publication policy before release: Apache-2.0 source, nuScenes-derived artifacts local/private.
- [x] Source license/release boundary approved: Apache-2.0 for source code; nuScenes-derived artifacts local/private only.
- [x] Add root `LICENSE` and `NOTICE`, and document the boundary in `README.md`.
- [ ] Add limitations: map approximation, simulator differences, unavailable sensors/closed loop and provisional thresholds.
- [ ] Complete CP5 human/reviewer sign-off; implementation alone is not acceptance evidence.

Dependencies: CP0–CP4 evidence, license decisions, approved benchmark set.

## CP6 — Paper

Status: `OPEN`

- [ ] Create paper outline and method/data provenance section.
- [ ] Confirm research questions; implementation experiments may be selected by agents, but final paper RQs remain `OWNER-REQUIRED`.
- [ ] Define experiment matrix and baselines.
- [ ] Include ADE/FDE, auxiliary metrics, gate funnel and failure taxonomy.
- [ ] Report provisional threshold status rather than presenting provisional thresholds as scientific conclusions.
- [ ] Include reproducibility and licensing boundaries.
- [ ] Add result-generation commands that do not require restricted data in the repository.
- [ ] Draft limitations and threats to validity.
- [ ] Complete manuscript review and final evidence bundle.

Dependencies: CP3–CP5 and owner-approved RQs.

## Agent Queue

Agents may work sequentially on the same worktree unless a separate branch/worktree is explicitly created. Each agent must preserve unrelated changes, add tests before implementation when practical, use online technical research when useful, and record decisions/evidence in its phase report. Agents must stop only for `OWNER-REQUIRED` decisions, missing required local runtime/data, legal ambiguity, or a contradiction with Plan A; ordinary implementation choices are not blockers.

| Order | Agent scope | Output | Status |
|---:|---|---|---|
| 1 | CP0 alignment/documentation | P0 report, banners, README/license notes, environment/scene proposal | `ASSIGNED` |
| 2 | CP1 map builder | mapbuilder module, tests, raw road-match/continuity evidence; preserve template default | `QUEUED` |
| 3 | CP2 simulator contract | esmini/CARLA execution contract, explicit replay modes, real-run evidence | `QUEUED` |
| 4 | CP3 evaluator | raw annotation provenance, ADE/FDE, baselines, mode/simulator-separated reports | `QUEUED` |
| 5 | CP4 gates | G1–G7 gate model, funnel report, reconciliation and negative tests | `QUEUED` |
| 6 | CP5 packaging | reproducibility/benchmark/license boundary pack and reviewer checklist | `QUEUED` |
| 7 | CP6 paper | outline, RQ/experiment matrix, result/evidence template; no invented results | `QUEUED` |

## Open Decisions for Project Owner

- [x] Approve CP2 same-XOSC contract.
- [x] Approve CP0 per-simulator sample-run evidence contract.
- [x] Approve behavior replay semantics by checkpoint.
- [x] Approve `scene-0061` as CP0–CP2 smoke/regression scene.
- [x] Approve temporary G6/G7 funnel semantics.
- [x] Approve Apache-2.0 source license and local/private derived-artifact policy.
- [ ] Approve/freeze final map area scene index of 5–10 Singapore One-North scenes.
- [x] Define FDE final timestamp policy: raw actor-final timestamp when covered, otherwise `insufficient_coverage`.
- [x] Define short-track handling: exclude `<2 s` from headline ADE/FDE and report the excluded actor/reason.
- [x] Define G5 working collision geometry and missing-event behavior.
- [x] Define G6/G7 temporary development semantics; scientific thresholds remain provisional.
- [ ] Approve final research questions.

## Evidence Rules

- Do not claim a simulator run without command, version, world/map, logs, trace and cleanup evidence.
- Do not claim ADE/FDE threshold achieved/not achieved while thresholds are provisional.
- Do not treat RMSE as ADE without explicit metric definition.
- Do not treat TTC/risk ranking as a rare-event validity gate.
- Do not treat rectangular boundary checks as lane-level road-match.
- Do not mutate canonical nuScenes coordinates to make a simulator run.
- Do not add licensed nuScenes data or restricted derived artifacts to the repository.
- No file removal is authorized by this checklist.
- Online research is allowed for technical solutions, but every external source used by an agent must be recorded in the phase report with URL/version/date.
- A technical decision made by an agent is not an owner decision and must not change Plan A scope, legal release policy, final scientific thresholds, or paper claims.

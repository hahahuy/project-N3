# Project Documentation

## Project identity

**This project is `Project - N3`.** Use that name when referring to the project
in prose — in documentation, slides, commit messages and discussion.

| name | value | role |
|---|---|---|
| **Project name** | **`Project - N3`** | how the project is referred to in prose |
| Code / codename | `Real2Scenario` | the pipeline's own name |
| Repo / remote | `project-N3` | the git repository and checkout directory name |

### Code identifiers — do not rename

`real2scenario` (`pyproject.toml`, the Python distribution name),
`real2scenario-local-demo` (`frontend/package.json`) and the import package
`r2s_web` are settled by packaging.

### Operational identifiers — do not rename

These appear throughout the guides and deployment docs. They are **live
infrastructure names**, not ways of writing the project name. Renaming any of
them breaks a running deployment or orphans a Docker volume:

| identifier | what it is |
|---|---|
| `project-n3` | Docker Compose project name (dev stack) |
| `project-n3-prod` | Docker Compose project name (production stack) |
| `project-n3-prod-api` / `-gateway` / `-cloudflared` | generated container names |
| `project-n3-metadata-cache`, `project-n3-prod-reports` | named Docker volumes |
| `project-n3.hahuy.cloud` | public DNS name and TLS certificate CN |
| `project-N3-3.10.0-local` | local esmini build directory |

Docker derives container and volume names from the Compose project name, so
"fixing" one of these strings to read like the project name would create a
second empty stack rather than rename the existing one.

## Reading Order

New agents and sessions must read these files first:

1. `MVP&ProjectSummary.md`
2. `README.md`
3. `docs/current/pm-agent-guide.md`
4. `docs/current/project-status.md`
5. `docs/current/decisions.md`
6. `docs/current/active-work.md`
7. `docs/current/technical-contracts.md`
8. `docs/current/evidence-index.md`
9. `docs/current/artifact-policy.md`
10. `docs/current/next-agent-handoff.md`
11. `docs/current/nuscenes-devkit-makeover-handoff.md`

For implementation work, read the new reference map after the current context:

1. `docs/architecture/system-overview.md`
2. `docs/architecture/boundary-map.md`
3. The relevant page under `docs/subsystems/`
4. The relevant page under `docs/contracts/`

Use `docs/current/` for status, decisions, handoffs and acceptance state. Use
`docs/subsystems/` for code ownership and wiring. Use `docs/contracts/` for
stable caller obligations. Use `docs/operations/` for runtime and deployment.

Agents changing the browser application must also read:

1. `docs/current/frontend-workspace-handbook.md`
2. `docs/current/frontend-workspace-log.md`
3. `docs/current/backend-workspace-contract-log.md`

Reports under `docs/reports/` record completed work and must not override
current decisions. The active implementation plan is
`docs/current/nuscenes-devkit-makeover-handoff.md`.

Controlling documents for deployment state:

- `docs/current/environment-environments.md` - development and product environments
- `docs/current/demo-hardening-backlog.md` - public exposure hardening status
- `docs/current/product-scene-exposure.md` - whether to expose all 850 scenes
- `docs/reports/cp1-evidence-lineage.md` - `r2s` to `project-N3` rename record
- `docs/current/mission-batch-concurrency-benchmark.md` - S-6 cap selection
- `docs/guides/production-push.md` - promote and rollback command helper
- `docs/current/local-artifact-bundles.md` - local/private evidence index
- `docs/guides/huong-dan-slides-thuyet-trinh.md` - judge-facing presentation guide
  (how to state the numbers honestly, and which claims not to make)
- `docs/current/wasm-window-performance-devops-handoff.md` - WASM/esmini window
  performance and devops plan

## Documentation Rules

- Plan A in `MVP&ProjectSummary.md` is the project scope baseline.
- New reports must be written in English.
- Do not claim `DONE` from unit tests alone; runtime claims require command,
  version, logs, trace/artifacts and cleanup evidence.
- Provisional thresholds must remain labelled `PROVISIONAL`.
- Do not add raw nuScenes data or nuScenes-derived artifacts to the repository.
- Update `docs/current/project-status.md` and `docs/current/active-work.md` when
  a work item changes status.
- Every agent completion report must include scope, files, tests, evidence,
  decisions, unverified items, blockers and next agent.

## Directory Map

- `docs/current/`: source of truth for current status and contracts.
- `docs/current/nuscenes-devkit-makeover-handoff.md`: active implementation plan.
- `docs/reports/`: English phase and implementation reports.
- `docs/evidence/`: runtime or acceptance evidence grouped by milestone. The M1-M5
  waves are **historical**; see `docs/evidence/README.md`.
- `docs/experiments/`: exploratory results not yet accepted as evidence.
- `docs/guides/`: setup and operational guides.
- `docs/architecture/`: current architecture and API boundaries.
- `docs/subsystems/`: implementation reference by runtime subsystem.
- `docs/contracts/`: canonical artifacts, web availability and API surface.
- `docs/operations/`: operational entrypoints grouped separately from domain docs.
- `docs/proposals/`: unaccepted implementation proposals and expert handoffs;
  proposals must be reconciled with current code before implementation.

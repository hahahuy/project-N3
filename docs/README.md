# Project Documentation

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

Agents changing the browser application must also read:

1. `docs/current/frontend-workspace-handbook.md`
2. `docs/current/frontend-workspace-log.md`
3. `docs/current/backend-workspace-contract-log.md`

Historical files under `docs/archive/` are quarantined and are not current
contracts, plans or assignments. Reports under `docs/reports/` record completed
work and must not override current decisions. The active implementation plan is
`docs/current/nuscenes-devkit-makeover-handoff.md`.

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
- `docs/evidence/`: runtime or acceptance evidence grouped by milestone.
- `docs/experiments/`: exploratory results not yet accepted as evidence.
- `docs/guides/`: setup and operational guides.
- `docs/architecture/`: current architecture and API boundaries.
- `docs/archive/plan-b/`: stale historical Plan B material.
- `docs/archive/plan-a-migration-checklist.md`: historical migration ledger.

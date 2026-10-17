# `docs/evidence/` — milestone acceptance evidence

These files record ticket-level evidence from the **Plan A / R2S wave**
(milestones M1–M5). They are retained for audit history.

## Status: HISTORICAL

The authoritative status for every layer is
[`docs/current/evidence-index.md`](../current/evidence-index.md), which
classifies them:

| milestone | status | directory |
|---|---|---|
| M1 ingestion | `HISTORICAL` | `m1-ingestion/` |
| M2 replay | `HISTORICAL` | `m2-replay/` |
| M3 generation | `HISTORICAL` | `m3-generation/` |
| M4 UI | `HISTORICAL/PARTIAL` | `m4-ui/` |
| M5 simulators | `HISTORICAL/UNVERIFIED` | `m5-simulators/` |

**Nothing here overrides a current decision.** For anything you intend to
present, work from `docs/current/`.

## Why these files are kept even though they are historical

The `r2s-*` filenames are the only surviving record that the R2S tickets were
actually executed, and the ticket IDs preserve the project's pre-rename
identity (`r2s` → `project-N3`). The rename record is
[`docs/reports/cp1-evidence-lineage.md`](../reports/cp1-evidence-lineage.md).

Most of these files have no inbound link from any other document. That is
**orphaned from the live index, not disposable** — deleting them would remove
the audit trail behind the milestone-completion claims that
`evidence-index.md` makes.

## The one live exception

[`m4-ui/u0-motion-editor-showcase.md`](m4-ui/u0-motion-editor-showcase.md) is
**live**. It carries `SHOWCASE-READY` / `TESTED` rows in
`evidence-index.md` and `active-work.md`.

## Relationship to `docs/reports/`

They are different layers and do not duplicate each other:

- `docs/evidence/` — runtime/acceptance evidence keyed to ticket IDs
- `docs/reports/` — phase and implementation narrative, including the current
  data-analysis reports

See [`docs/README.md`](../README.md) for the full taxonomy.
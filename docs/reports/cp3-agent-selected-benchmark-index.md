# CP3 Agent-Selected Benchmark Index

## Status

`AGENT-SELECTED`, `PROVISIONAL`, `NOT OWNER-APPROVED`, `PREPARATION-INCOMPLETE`

The user authorized the implementation agent to select a provisional benchmark
set without waiting for owner approval. The selection is therefore usable for
engineering preparation and diagnostic comparison only. It must not be treated
as the final scientific benchmark index.

## Selection

Command:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/select_benchmark_scenes.py \
  --dataset-root "$NUSCENES_ROOT" \
  --output "$CP1_EVIDENCE_ROOT/benchmark-scenes-provisional.json"
```

Selection policy:

```text
location: singapore-onenorth
dataset: nuScenes v1.0-trainval
count: 5
ordering: largest sample_count descending, scene token ascending tie-break
approval: not requested
```

The selected scenes are recorded outside the repository in
`$CP1_EVIDENCE_ROOT/benchmark-scenes-provisional.json`:

```text
scene-0380
scene-0962
scene-0945
scene-0957
scene-0981
```

All five currently have 41 samples in the local metadata inventory. The run
card records the scene/log metadata hashes and the git revision.

## Preparation Result

The initial all-five canonical preparation command was attempted with
`scripts/prepare_benchmark_scenes.py`, but exceeded the 120-second execution
window before producing the private output directory. The current importer
repeatedly scans large `sample_annotation.json`, `sample.json` and related
trainval tables for each scene. No repository artifact or raw dataset was
created by the timed-out attempt.

This is a performance/preparation blocker, not a benchmark result. No real
multi-scene metrics, gate counts or simulator evidence are claimed.

**Superseded**: the blocker is cleared by the cached metadata index and the first
real multi-scene run recorded in `docs/reports/cp3-benchmark-run-evidence.md`.

## Next Action

Optimize or cache metadata indexing for incremental scene preparation, then run
one scene at a time into a private evidence root. Only after all five scenes are
prepared should the existing `benchmark-aggregate-v1` contract aggregate their
reports. Keep the set agent-selected/provisional until the owner changes that
decision.

**Completed** by `docs/reports/cp3-benchmark-run-evidence.md`; the remaining
action is owner review of the provisional run and of this index.

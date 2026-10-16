# CP3 Benchmark Aggregate

## Status

`IMPLEMENTED`, `TESTED`, `PROVISIONAL`, `BENCHMARK-RUN-OPEN`

The project now has a deterministic multi-scene benchmark aggregation contract.
It aggregates completed per-scene reports without mixing evidence provenance or
promoting provisional metrics to final scientific results.

## Implemented

`src/real2scenario/benchmark.py` provides:

- `BenchmarkRun` with explicit scene, evidence class, simulator and visibility;
- `aggregate_benchmark_runs()` with deterministic scene ordering;
- aggregate status counts for generated, valid, invalid and simulator-failed;
- separate counts by evidence class and simulator;
- replay ADE/FDE aggregation when replay metrics exist;
- G1-G7 provisional funnel aggregation;
- deterministic JSON-safe serialization through `benchmark_aggregate_to_dict()`.

Supported evidence classes:

```text
synthetic
nuscenes_local
other_local
```

Supported simulator classes:

```text
none
esmini
carla_unverified
```

The serialized benchmark aggregate contains no host paths, dataset roots,
trajectory artifacts or raw scene data.

## Verification

Focused benchmark tests cover:

- deterministic scene ordering;
- evidence/simulator class separation;
- provisional funnel serialization;
- duplicate run and scene rejection;
- absence of artifact paths from the aggregate payload.

## Current Evidence

This slice adds the aggregation contract and synthetic tests. It does not yet
freeze the owner-approved 5-10 scene index or execute a real multi-scene
nuScenes/esmini benchmark. Those remain separate evidence tasks.

## Boundaries

- ADE/FDE remain diagnostic and provisional.
- G6/G7 remain diagnostic and provisional.
- Synthetic, local licensed nuScenes and simulator evidence must remain visibly
  separated.
- CARLA is represented only as `carla_unverified` when supplied by a caller; no
  CARLA runtime claim is created.
- No final threshold or CP3 acceptance claim is made.

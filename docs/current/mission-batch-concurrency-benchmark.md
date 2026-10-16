# Mission — Batch Concurrency Benchmark and Cap Selection

Status: `PROPOSED / NOT STARTED / NO CAP CURRENTLY ENFORCED`
Owner: unassigned. Requires an owner-approved threshold before implementation.

This mission exists to replace a guessed number with a measured one. **No
concurrency cap is currently enforced**, and the product environment is publicly
reachable. This is the remaining open security item in
`docs/current/demo-hardening-backlog.md` section 3.

Related: `docs/current/product-scene-exposure.md`,
`docs/guides/datastreaming.md`.

---

## 1. Problem statement

`POST /api/batches` runs variant generation synchronously inside the request
handler:

```python
# src/r2s_web/jobs.py:85-94
def create(self, request: BatchRequest) -> JobStatus:
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    ...
    self._run(record, request)      # blocking, in-request
```

There is no semaphore, no queue and no cap. Two consequences:

1. **Resource exhaustion.** N concurrent requests occupy N workers for the full
   generation duration. The host has 12 cores shared with `banking-agent`,
   `kavita`, `searxng`, two public sites and a `carla` container.
2. **Incorrect HTTP semantics.** The endpoint returns `202 Accepted`
   (`src/r2s_web/app.py:383`) while running synchronously.

### What already has a cap

The live simulator path does, and is the reference pattern:

```python
MAX_SESSIONS = 4                              # src/r2s_web/live_session.py:21
if len(self.sessions) >= self.max_sessions:
    raise RuntimeError("live_session_limit_reached")   # :308-309
```

Batch generation needs the same discipline.

### Aggravating factor

`ops/nginx/demo.conf` sets `proxy_read_timeout 600s`. A saturated worker is
therefore held open for up to ten minutes per request rather than failing fast.
That makes the failure slower and more expensive than it needs to be.

## 2. Why the threshold is deferred, not chosen

A cap chosen by intuition would be arbitrary. The correct value depends on
measured per-variant cost, which has never been recorded. **The recommendation
below is a starting point for the benchmark, not an approved threshold.**

Immediate mitigation until this mission completes: judges are known, few, and
hold a shared key, so the abuse surface is small. It is not zero — a judge
clicking a large grid once can still saturate the box.

## 3. Scope

### In scope

1. Measure per-variant generation cost and peak memory.
2. Measure host headroom with and without other containers.
3. Determine the request-level cost floor (`sample_count`, `actor_count`, grid
   dimensions).
4. Select a cap from the measurements.
5. Implement bounded concurrency with an explicit, documented rejection reason.
6. Decide whether generation should leave the request thread so `202` is truthful.
7. Bound `reports/` and `scenarios/` growth.

### Out of scope

- Scientific policy, gate thresholds, CP1 baseline. Untouched.
- Variant generation semantics. Untouched.
- The live-session cap, which is already correct.

## 4. Method

### 4.1 Measurements required

| ID | Measurement | Why it decides the cap |
|---|---|---|
| M-1 | Wall time per variant, grid and random, across the seeded scenes | Sets per-request cost |
| M-2 | Peak RSS during a batch | Decides memory-bound vs CPU-bound |
| M-3 | Host CPU saturation with N batches concurrent | Finds the knee |
| M-4 | Effect on `banking-agent` and `kavita` latency at that load | Non-negotiable constraint: other services must not degrade |
| M-5 | `esmini` replay cost per variant, if available | Replay may dominate |
| M-6 | Request-level floor: cost of a minimal batch (1 variant) | Prevents trivially cheap floods |

**M-4 is the binding constraint.** The cap is not "how much CPU is free" but
"how much can be taken before another tenant notices".

### 4.2 Method

Use the existing deterministic grid runner rather than inventing a harness:

```bash
scripts/run_benchmark_scenes.py --help
# baseline evidence: docs/reports/cp3-benchmark-run-evidence.md
```

Vary `count`, `speed_multipliers` and `initial_gap_deltas_m` to span
1, 20 and 100 variants. Record host `load average`, per-container CPU and the
`banking-agent` and `kavita` response times concurrently.

Reproducibility rules from `docs/README.md` apply: record command, version,
logs, artifacts and cleanup. Provisional results stay labelled `PROVISIONAL`.

### 4.3 Environment constraints to record with every run

- `hhf-server`, 12 cores, 31 GB RAM.
- Other containers running concurrently. Either quiesce them or record their load;
  a benchmark taken on an idle host will overstate the cap.
- Index cache warm. A cold metadata index adds ~56 s and would distort results.

## 5. Selection criteria

The cap should be the **lowest** value that keeps legitimate judge use smooth,
subject to these:

| Criterion | Requirement |
|---|---|
| Non-interference | `banking-agent` and `kavita` p95 latency must not regress materially at the cap |
| Headroom | Sustained CPU below the level where interactive requests degrade |
| Legitimate use | A 20-variant grid, the project's documented grid size, completes comfortably |
| Fast failure | Excess requests rejected in milliseconds, not held for the generation duration |
| Honest semantics | Either run off-thread so `202` is true, or return `200`/`201` truthfully |

### Starting hypothesis to test, not to adopt

Given 12 cores and a mostly-idle host, a candidate range is **2 to 4 concurrent
batches**, mirroring `MAX_SESSIONS = 4`. This is a hypothesis. If M-4 shows even
two concurrent batches degrade another service, the cap drops to 1 plus a queue.

Do not adopt this number without running M-1 to M-4.

## 6. Implementation requirements

Whatever the benchmark selects:

1. A configurable limit, not a hardcoded constant. Default must be safe.
2. Rejection carries a verbatim reason following the existing vocabulary, so the
   UI can render it as an explicit availability block
   (`docs/current/ui-mvp-flow-spec.md`).
3. The limit appears in `GET /api/settings` or an equivalent capability surface,
   so the UI can state it rather than discover it.
4. Tests: N concurrent requests never exceed the cap; excess is rejected with the
   documented status and reason.
5. No silent queueing without a bound. An unbounded queue is the same
   exhaustion problem with extra steps.

## 7. Verification

Per `docs/README.md`, no `DONE` from unit tests alone:

- Measurement logs for M-1 to M-6, with the environment recorded.
- Selected cap with the reasoning that connects it to M-4.
- Concurrency test proving the cap holds.
- Evidence that `banking-agent` and `kavita` were unaffected during the runs.
- Updated `docs/current/demo-hardening-backlog.md` section 3 and
  `docs/current/active-work.md`.

## 8. Interim risk

Until this mission completes:

- The product environment is publicly reachable and uncapped.
- A judge requesting a large grid can saturate the host and affect
  `banking-agent`, `kavita` and the two public sites.
- The product `api` container is capped at 2 CPU / 4 GB, which bounds the damage
  but causes jobs to fail rather than preventing saturation.

## 9. Unverified

- No measurement in section 4.1 has been performed. All cost figures are absent,
  which is precisely why the threshold is deferred.
- The interaction between `proxy_read_timeout 600s` and a saturated worker has
  not been observed under real load.
- Whether variant generation is safe to move off the request thread has not been
  assessed.
